"""COL.py — Catalogue of Life API client.

Concrete SpeciesAPI implementation for the Catalogue of Life (COL), served via
the ChecklistBank API. COL is a global taxonomic checklist: it provides accepted
names and synonymies but hosts no occurrence data.

Main entry point: COLAPI().synonyms(name)
"""

from .base import SpeciesAPI


class COLAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for the Catalogue of Life (COL).

    The Catalogue of Life (often served via ChecklistBank) is a comprehensive
    global checklist of species. It provides authoritative taxonomic hierarchies
    and synonymies but does not host physical occurrence or observational data.

    Synonyms are returned in the pipeline-standard ``_format_synonym()`` format,
    consistent with all other SpeciesAPI implementations.
    """

    BASE = "https://api.checklistbank.org"
    # COL26.5 — update this key when a newer COL release is published on ChecklistBank
    DATASET_KEY = 315192

    def search(self, name: str) -> dict:
        """
        Search the Catalogue of Life for a specific taxonomic name.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response dictionary from the COL API containing matching
                name usages, status (accepted vs. synonym), and taxonomic IDs.
        """
        return self._fetch(
            f"{self.BASE}/dataset/{self.DATASET_KEY}/nameusage/search",
            params={"q": name},
        )

    def _get_accepted_id(self, results: list) -> str | None:
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

    def _fetch_col_synonyms(self, usage_id: str) -> dict:
        """
        Fetch raw synonym data for an accepted taxon from ChecklistBank.

        Args:
            usage_id (str): The ChecklistBank taxon ID of the accepted taxon.

        Returns:
            dict: Raw JSON response from the synonyms endpoint, containing
                ``"homotypic"`` and ``"heterotypic"`` keys.
        """
        return self._fetch(
            f"{self.BASE}/dataset/{self.DATASET_KEY}/taxon/{usage_id}/synonyms",
        )

    def _build_synonyms(self, raw_syns: list, query_name: str) -> list[dict]:
        """
        Convert raw ChecklistBank synonym records into pipeline-standard synonym dicts.

        Args:
            raw_syns (list): Combined homotypic + heterotypic records from
                ``_fetch_col_synonyms()``. Each record has ``"name"``,
                ``"authorship"``, ``"publishedIn"``, and ``"id"`` fields.
            query_name (str): The original query name, used to seed deduplication.

        Returns:
            list[dict]: Pipeline-standard synonym records.
        """
        candidates = []
        for s in raw_syns:
            syn_name = s.get("name", "")
            if not syn_name:
                continue
            taxon_id = s.get("id", "")
            candidates.append(
                self._format_synonym(
                    name=syn_name,
                    author=s.get("authorship", ""),
                    publication_name=s.get("publishedIn", ""),
                    api_link=(
                        f"https://www.catalogueoflife.org/data/taxon/{taxon_id}"
                        if taxon_id
                        else ""
                    ),
                )
            )
        return self._deduplicate_synonyms(candidates, seed={query_name.lower()})

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve taxonomic synonyms for a given scientific name.

        This process requires two steps: first, resolving the string name to a
        specific COL usage ID, and second, querying the synonyms endpoint using
        that ID.

        Args:
            name (str): The scientific name to search for.

        Returns:
            list[dict]: Pipeline-standard synonym records. Returns an empty list
                if the initial search fails, if no ID is found, or if the taxon
                has no recorded synonyms.
        """
        data = self.search(name)

        results = data.get("result", [])
        if not isinstance(results, list) or len(results) == 0:
            return []

        usage_id = self._get_accepted_id(results)
        if not usage_id:
            return []

        syns = self._fetch_col_synonyms(usage_id)
        raw_syns = syns.get("homotypic", []) + syns.get("heterotypic", [])
        return self._build_synonyms(raw_syns, query_name=name)
