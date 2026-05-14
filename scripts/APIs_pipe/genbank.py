import time

import requests

from .base import SpeciesAPI


class GenBankAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for GenBank (NCBI Entrez).

    GenBank is the NIH genetic sequence database. Unlike taxonomic or
    observational databases, this client interacts exclusively with the
    NCBI E-utilities API to query the 'nucleotide' database. It bypasses
    the pipeline's synonym phase and strictly maps DNA/RNA sequence data
    into the standard occurrence dictionary format used by the aggregator.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, name: str) -> dict:
        """
        Satisfies the SpeciesAPI abstract base class requirement.

        Because GenBank is used strictly as a genetic occurrence database in
        this pipeline rather than a primary taxonomic backbone, this method
        safely returns an empty dictionary.

        Args:
            name (str): The scientific name of the taxon (unused).

        Returns:
            dict: Always returns an empty dictionary.
        """
        return {}

    def synonyms(self, name: str) -> list[dict]:
        """
        Satisfies the SpeciesAPI abstract base class requirement.

        GenBank records genetic sequences, not historical taxonomic aliases.
        Therefore, this client opts out of the pipeline's synonym-gathering phase.

        Args:
            name (str): The scientific name to query.

        Returns:
            list[dict]: Always returns an empty list.
        """
        return []

    def occurrences(self, name: str, limit: int = 10) -> list[dict]:
        """
        Retrieve genetic sequences mapped to the pipeline's occurrence standard.

        This method executes a required two-step query against the NCBI API:
        1. Calls 'esearch.fcgi' to retrieve internal UIDs for the given taxon.
        2. Calls 'esummary.fcgi' to fetch the rich metadata for those UIDs.

        It parses the results into the standard Darwin Core-like dictionary format,
        using the sequence title as the 'locality' and constructing a direct
        hyperlink to the physical DNA sequence record on the NCBI website.

        Args:
            name (str): The scientific name of the organism (e.g., 'Amanita muscaria').
            limit (int, optional): The maximum number of genetic sequences to
                retrieve. Defaults to 10 to respect API rate limits.

        Returns:
            list[dict]: A list of occurrence dictionaries. Each dictionary contains
                'scientificName', 'eventDate', 'verbatimLocality' (sequence title),
                'source', and 'occurrenceID' (URL to the NCBI record).
        """
        results = []
        try:
            # Respect NCBI's rate limit (max 3 requests per second)
            time.sleep(0.35)

            # 1. Search the Nucleotide database for the organism
            search_url = f"{self.BASE_URL}/esearch.fcgi"
            search_params = {
                "db": "nucleotide",
                "term": f"{name}[Organism]",
                "retmode": "json",
                "retmax": limit,
            }
            search_resp = requests.get(search_url, params=search_params, timeout=10)
            search_resp.raise_for_status()
            search_data = search_resp.json()

            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []

            # 2. Fetch the metadata summary for those specific sequence IDs
            sum_url = f"{self.BASE_URL}/esummary.fcgi"
            sum_params = {
                "db": "nucleotide",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            sum_resp = requests.get(sum_url, params=sum_params, timeout=10)
            sum_resp.raise_for_status()
            sum_data = sum_resp.json()

            records = sum_data.get("result", {})

            # 3. Format strictly to the pipeline standard
            for uid in id_list:
                if uid in records:
                    rec = records[uid]

                    # Construct a direct URL to the NCBI sequence page
                    accession = rec.get("accessionversion", uid)
                    url = f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}"

                    results.append(
                        {
                            "scientificName": name,
                            "eventDate": rec.get("updatedate", ""),
                            "decimalLatitude": None,
                            "decimalLongitude": None,
                            # We use the sequence title as the "locality" so the UI has text to display
                            "verbatimLocality": rec.get("title", "Genetic Sequence"),
                            "top_3_images": [],  # DNA doesn't have field photos!
                            "source": "GenBank (NCBI)",
                            "occurrenceID": url,
                        }
                    )

        except requests.RequestException as e:
            print(f"GenBank API Network Error: {e}")
        except Exception as e:
            print(f"GenBank Parsing Error: {e}")

        return results
