# Unified Occurrence Aggregator

# scripts/core/aggregator.py
import requests

class SpeciesAggregator:
    """
    Aggregator for fetching and grouping occurrence records across multiple APIs.

    This class provides a unified interface to simultaneously query a primary 
    aggregator (like GBIF) and specialized regional databases (like Symbiota portals) 
    for physical occurrence data. It automatically expands searches to include 
    known synonyms, ensuring comprehensive data retrieval.
    """
    
    def __init__(self, clients: dict, router=None):
        """
        Initialize the SpeciesAggregator.

        Args:
            clients (dict): A dictionary mapping string keys to initialized API client
                instances. Keys must match the strings used in the `apis` argument of
                `occurrences()`. In practice these are the keys produced by
                `_make_clients()` in call_apis_pipe.py — e.g. "gbif", "col",
                "genbank", "mushroomobs", "symbiota_mycoportal", etc. Each value must
                implement a `.occurrences(name, limit)` method.
            router (TaxonRouter, optional): An optional router instance to dynamically
                determine which APIs to query based on taxonomy.
        """
        self.clients = clients
        self.router = router

    def occurrences(self, name: str, synonyms: list, apis: list, limit: int = 20) -> dict:
        """
        Retrieve occurrence records for a taxon and all of its known synonyms.

        Iterates through the primary name and all provided synonyms, querying 
        every requested API. If a database goes offline or times out, it catches 
        the exception and returns a structured warning status rather than 
        crashing the pipeline.

        Args:
            name (str): The primary accepted scientific name to search for.
            synonyms (list[str]): A list of string synonyms associated with the taxon.
            apis (list[str]): A list of dictionary keys indicating which APIs in 
                `self.clients` should be queried.
            limit (int, optional): The maximum number of records to retrieve per 
                name query. Defaults to 20.

        Returns:
            dict: A dictionary grouping the occurrence records and statuses by source.
                Example:
                {
                    "gbif": {
                        "status": "success", 
                        "data": [{...}, {...}]
                    },
                    "mycoportal": {
                        "status": "warning", 
                        "message": "The mycoportal database is currently down or timing out."
                    }
                }
        """
        results = {}
        
        # Combine the primary name and synonyms into a single list to search
        names_to_search = [name] + synonyms

        for api_key in apis:
            client = self.clients.get(api_key)
            if client is None:
                results[api_key] = {
                    "status": "error", 
                    "message": f"Configuration missing for {api_key}"
                }
                continue

            try:
                if hasattr(client, "occurrences"):
                    all_records = []
                    
                    # Search the database for the primary name AND all synonyms
                    for n in names_to_search:
                        records = client.occurrences(n, limit=limit)
                        if isinstance(records, list):
                            all_records.extend(records)
                            
                    results[api_key] = {"status": "success", "data": all_records}
                else:
                    results[api_key] = {"status": "error", "message": "Method not supported."}
                    
            except requests.exceptions.Timeout:
                # Specific warning for timeouts (database is hanging)
                results[api_key] = {
                    "status": "warning", 
                    "message": f"The {api_key} database is currently down or timing out."
                }
            except requests.exceptions.ConnectionError:
                # Catches DNS failures and dead servers (like NE Herbaria)
                results[api_key] = {
                    "status": "warning", 
                    "message": f"Connection failed. The {api_key} server is offline or unreachable."
                }
            except requests.exceptions.HTTPError as e:
                # Specific warning for server crashes/firewalls (e.g., 403, 500)
                results[api_key] = {
                    "status": "warning", 
                    "message": f"The {api_key} database rejected the request (Status {e.response.status_code})."
                }
            except Exception as e:
                # Catch-all for JSON parsing errors or other unexpected crashes
                results[api_key] = {"status": "error", "message": str(e)}
                
        return results