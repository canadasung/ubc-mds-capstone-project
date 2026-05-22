"""
GenBank (NCBI Entrez) API client for retrieving genetic sequence metadata.

This module queries the NCBI nucleotide database via the E-utilities API to
surface genetic sequence records as occurrence-like entries in the pipeline.
It does not perform taxonomy resolution or synonym gathering — those phases
are skipped. Records contain sequence titles, accession URLs, and update dates
rather than field observation data.

NCBI E-utilities API: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

import time

import requests

from .base import SpeciesAPI


class GenBankAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for GenBank (NCBI Entrez).

    Queries the NCBI nucleotide database for genetic sequence metadata records
    associated with a taxon. Both search() and synonyms() are stubs that return
    empty results — GenBank is used only for sequence record discovery, not
    taxonomy resolution.

    Occurrence records represent NCBI nucleotide entries, not field observations:
    verbatimLocality holds the sequence title, eventDate is the NCBI record update
    date (not a collection date), and coordinates are always null.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, name: str) -> dict:
        """
        Not implemented for GenBank. GenBank is not a taxonomic backbone, so
        there is no meaningful taxonomy resolution to perform. Returns an empty
        dictionary so the pipeline's synonym-gathering phase is skipped cleanly.

        Args:
            name (str): The scientific name of the taxon (unused).

        Returns:
            dict: Always returns an empty dictionary.
        """
        return {}

    def synonyms(self, name: str) -> list[dict]:
        """
        Not implemented for GenBank. GenBank records genetic sequences, not
        taxonomic aliases, so there are no synonyms to retrieve. Returns an
        empty list to skip the pipeline's synonym-gathering phase.

        Args:
            name (str): The scientific name to query (unused).

        Returns:
            list[dict]: Always returns an empty list.
        """
        return []

    def occurrences(self, name: str, limit: int = 10) -> list[dict]:
        """
        Retrieve genetic sequence metadata records for a taxon from NCBI.

        Executes a two-step query:
        1. esearch.fcgi — retrieves internal UIDs for sequences matching the taxon.
        2. esummary.fcgi — fetches metadata for those UIDs (title, accession, date).

        Results are formatted to match the pipeline's standard occurrence dict, with
        the following caveats: verbatimLocality holds the sequence title (not a place
        name), eventDate is the NCBI record update date (not a collection date), and
        coordinates are always null.

        Args:
            name (str): The scientific name of the organism (e.g., 'Amanita muscaria').
            limit (int, optional): Maximum number of sequence records to retrieve.
                Defaults to 10 to stay within NCBI's rate limit of 3 requests/second.

        Returns:
            list[dict]: A list of dicts with keys: 'scientificName', 'eventDate',
                'decimalLatitude', 'decimalLongitude', 'verbatimLocality',
                'top_3_images', 'source', and 'occurrenceID' (URL to the NCBI record).
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
                            "verbatimLocality": rec.get("title", ""),
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
