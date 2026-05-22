"""COL.py — Catalogue of Life API client.

Concrete SpeciesAPI implementation for the Catalogue of Life (COL), served via
the ChecklistBank API. COL is a global taxonomic checklist: it provides accepted
names and synonymies but hosts no occurrence data, so `occurrences` is a no-op.

Main entry point: COLAPI().synonyms(name)
"""

import requests

from .base import SpeciesAPI


class COLAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for the Catalogue of Life (COL).

    The Catalogue of Life (often served via ChecklistBank) is a comprehensive
    global checklist of species. It provides authoritative taxonomic hierarchies
    and synonymies but does not host physical occurrence or observational data.
    """

    BASE = "https://api.catalogueoflife.org"

    def search(self, name: str):
        """
        Search the Catalogue of Life for a specific taxonomic name.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response dictionary from the COL API containing matching
                name usages, status (accepted vs. synonym), and taxonomic IDs.
        """
        resp = requests.get(f"{self.BASE}/nameusage/search", params={"q": name})
        resp.raise_for_status()
        return resp.json()

    def synonyms(self, name: str):
        """
        Retrieve taxonomic synonyms for a given scientific name.

        This process requires two steps: first, resolving the string name to a
        specific COL usage ID, and second, querying the synonyms endpoint using
        that ID.

        Note: If a valid taxon has no synonyms, the COL API natively returns an
        HTTP 404 (Not Found) for the synonyms endpoint. This method catches that
        specific 404 and safely returns an empty list.

        Args:
            name (str): The scientific name to search for.

        Returns:
            list[dict]: A list of synonym records associated with the taxon.
                Returns an empty list if the initial search fails, if no ID is
                found, or if the taxon has no recorded synonyms.
        """
        data = self.search(name)

        # If COL returns no results → skip
        results = data.get("result", [])
        if not isinstance(results, list) or len(results) == 0:
            return []

        usage_id = results[0].get("id")
        if not usage_id:
            return []

        resp = requests.get(f"{self.BASE}/nameusage/{usage_id}/synonyms")

        # A 404 from COL on this specific endpoint just means "no synonyms exist"
        if resp.status_code == 404:
            return []

        resp.raise_for_status()

        syns = resp.json()
        if not isinstance(syns, list):
            return []

        return syns

    def occurrences(self, name: str, limit: int = 20):
        """
        Retrieve occurrence records for a specific taxon.

        Args:
            name (str): The scientific name of the species.
            limit (int, optional): Maximum records to return. Defaults to 20.

        Returns:
            list: Always returns an empty list. The Catalogue of Life is purely
                a taxonomic checklist and naming database; it does not track
                or serve physical occurrence data.
        """
        return []
