"""tropicos.py — Tropicos API client.

Concrete SpeciesAPI implementation for Tropicos, the botanical database maintained
by the Missouri Botanical Garden. Tropicos requires a registered API key (loaded
from TROPICOS_API_KEY) and uses a relational model: names must first be resolved
to an internal NameId before taxonomic data can be queried.

Main entry point: TropicosAPI().synonyms(name)
"""

import os

from dotenv import load_dotenv

from .base import SpeciesAPI

load_dotenv()  # Load TROPICOS_API_KEY from .env

load_dotenv()  # necessary to load the tropicos api key


class TropicosAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for the Tropicos database.

    Tropicos is maintained by the Missouri Botanical Garden and focuses heavily
    on botanical (plant) data. Unlike open APIs, Tropicos requires a registered
    API key for all requests. Furthermore, it operates on a relational model where
    taxonomic data must be queried using a proprietary 'NameId' rather than just
    a string name.
    """

    BASE = "http://services.tropicos.org"

    def __init__(self, api_key: str | None = None):
        """
        Initialize the Tropicos API client.

        Args:
            api_key (str | None, optional): A registered Tropicos API key.
                If not provided, the client will attempt to load it from the
                TROPICOS_API_KEY environment variable.

        Raises:
            ValueError: If no API key is provided and the TROPICOS_API_KEY
                environment variable is missing.
        """
        self.key = api_key or os.getenv("TROPICOS_API_KEY")
        if not self.key:
            raise ValueError(
                "Tropicos API key not provided. "
                "Set TROPICOS_API_KEY in your environment or pass api_key explicitly."
            )

    def _params(self) -> dict:
        """
        Internal helper to construct standard required query parameters.

        Tropicos requires the API key and desired output format to be passed
        in the URL query string for every single request.

        Returns:
            dict: A dictionary containing the API key and JSON format flag.
        """
        return {"apikey": self.key, "format": "json"}

    def search(self, name: str) -> dict:
        """
        Search the Tropicos database to resolve a name to its internal NameId.

        Args:
            name (str): The scientific name to search for.

        Returns:
            dict: A standardized dictionary containing the 'name', 'matchType',
                and internal database 'key' (NameId). Returns an empty dictionary
                if the name is not found or the request fails.
        """
        results = self._fetch(
            f"{self.BASE}/Name/Search",
            params={"name": name, "type": "exact", **self._params()},
        )

        if isinstance(results, list) and len(results) > 0:
            first = results[0]
            if "NameId" in first:
                return {
                    "name": first.get("ScientificName", name),
                    "matchType": "EXACT",
                    "key": first.get("NameId"),
                }

        return {}

    def _fetch_synonym_list(self, name_id) -> list | dict:
        """
        Fetch raw synonym data for a Tropicos name ID.

        Args:
            name_id: The Tropicos NameId of the taxon.

        Returns:
            list | dict: Parsed JSON response — a list of synonym objects on
                success, or a dict containing an ``"Error"`` key when the taxon
                has no recorded synonyms.
        """
        return self._fetch(
            f"{self.BASE}/Name/{name_id}/Synonyms",
            params=self._params(),
        )

    def _build_synonyms(self, data: list, query_name: str) -> list[dict]:
        """
        Convert raw Tropicos synonym records into pipeline-standard synonym dicts.

        Args:
            data (list): The parsed JSON synonym list from ``_fetch_synonym_list()``.
            query_name (str): The original query name, used to seed deduplication.

        Returns:
            list[dict]: Pipeline-standard synonym records. Returns an empty list
                when *data* contains an error response.
        """
        if isinstance(data, dict) and data.get("Error"):
            return []

        candidates = []
        for item in data if isinstance(data, list) else []:
            # Tropicos nests the actual synonym data under "SynonymName"
            syn_info = item.get("SynonymName", {})
            syn_name = syn_info.get("ScientificName")
            if not syn_name:
                continue

            syn_id = syn_info.get("NameId")
            candidates.append(
                self._format_synonym(
                    name=syn_name,
                    author=syn_info.get("Author", ""),
                    api_link=f"https://www.tropicos.org/name/{syn_id}"
                    if syn_id
                    else "",
                )
            )

        return self._deduplicate_synonyms(candidates, seed={query_name.lower()})

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve a pipeline-standard list of taxonomic synonyms for a plant species.

        Performs a two-step relational query: first resolving the string name to
        a Tropicos NameId via ``search()``, then fetching and building the synonym
        list.

        Args:
            name (str): The scientific name of the plant.

        Returns:
            list[dict]: A list of synonym dictionaries formatted for the pipeline
                (canonicalName, author, date, publishedIn, url).
        """
        search_res = self.search(name)
        if not search_res or "key" not in search_res:
            return []

        try:
            data = self._fetch_synonym_list(search_res["key"])
            return self._build_synonyms(data, query_name=name)
        except Exception as e:
            print(f"Tropicos Synonyms Error: {e}")
            return []
