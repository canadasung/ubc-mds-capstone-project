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

    BASE = "https://api.checklistbank.org"
    # COL26.5 — update this key when a newer COL release is published on ChecklistBank
    DATASET_KEY = 315192

    def search(self, name: str):
        """
        Search the Catalogue of Life for a specific taxonomic name.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response dictionary from the COL API containing matching
                name usages, status (accepted vs. synonym), and taxonomic IDs.
        """
        resp = requests.get(
            f"{self.BASE}/dataset/{self.DATASET_KEY}/nameusage/search",
            params={"q": name},
        )
        resp.raise_for_status()
        return resp.json()

    def _resolve_accepted_id(self, results: list) -> str | None:
        """
        Return the ChecklistBank taxon ID for the accepted name in results.

        If results contain an accepted name, its ID is returned directly.
        If the first result is a synonym, its parentId (which points to the
        accepted taxon) is returned instead.
        """
        # TODO: check into behavior if there are multiple accepted names and decide how we want to handle that
        accepted = next(
            (r for r in results if r.get("usage", {}).get("status") == "accepted"),
            None,
        )
        if accepted is not None:
            return accepted.get("id")

        first = results[0]
        return first.get("usage", {}).get("parentId")

    def synonyms(self, name: str):
        """
        Retrieve taxonomic synonyms for a given scientific name.

        This process requires two steps: first, resolving the string name to a
        specific COL usage ID, and second, querying the synonyms endpoint using
        that ID.

        Args:
            name (str): The scientific name to search for.

        Returns:
            list[dict]: A list of synonym records associated with the taxon.
                Returns an empty list if the initial search fails, if no ID is
                found, or if the taxon has no recorded synonyms.
        """
        data = self.search(name)

        results = data.get("result", [])
        if not isinstance(results, list) or len(results) == 0:
            return []

        usage_id = self._resolve_accepted_id(results)
        if not usage_id:
            return []

        resp = requests.get(
            f"{self.BASE}/dataset/{self.DATASET_KEY}/taxon/{usage_id}/synonyms"
        )
        resp.raise_for_status()

        syns = resp.json()
        return syns.get("homotypic", []) + syns.get("heterotypic", [])

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
