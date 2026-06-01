"""
Catalogue of Life API client.

SpeciesAPI implementation for the Catalogue of Life (COL), served via the ChecklistBank API. COL is a global taxonomic checklist that provides accepted names and synonymies.
"""

from .base import SpeciesAPI


class COLAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for the Catalogue of Life (COL).
    """

    BASE_URL = "https://api.checklistbank.org"
    # COL26.5 — update this key when a newer COL release is published on ChecklistBank
    DATASET_KEY = 315192

    def _fetch_query_data(self, name: str) -> dict:
        """
        Search the Catalogue of Life for a specific taxonomic name.

        Parameters
        ----------
        name : str
            The scientific name to search for (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict
            The full JSON search response, including a ``"result"`` key
            containing a list of matching name-usage records.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/nameusage/search",
            params={"q": name},
        )

    def _extract_internal_accepted_id(self, results: list) -> str:
        """
        Return the ChecklistBank taxon ID for the accepted name in results.

        If an accepted name is present, the ID of the first accepted record is
        returned. Otherwise, the ``parentId`` of the first result is used as a
        fallback (i.e. the record is a synonym, and its parent is the accepted name).

        Parameters
        ----------
        results : list
            The list of name-usage records from the ``"result"`` key of the
            search response.

        Returns
        -------
        str
            The internal ChecklistBank taxon ID of the accepted name.

        Raises
        ------
        LookupError
            When neither an accepted record nor a ``parentId`` can be found.
        """
        # TODO: check into behavior if there are multiple accepted names and decide how we want to handle that
        accepted = next(
            (r for r in results if r.get("usage", {}).get("status") == "accepted"),
            None,
        )
        if accepted is not None:
            return accepted.get("id")

        first = results[0]
        usage_id = first.get("usage", {}).get("parentId")
        if usage_id is not None:
            return usage_id
        else:
            raise LookupError(
                f"{type(self).__name__} error, was unable to extract internal accepted id."
            )

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Fetch raw synonym data for the accepted taxon.

        Extracts the results list from the search response, resolves the
        accepted taxon ID, then queries the synonyms endpoint.

        Parameters
        ----------
        raw_data : dict
            The full JSON search response returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Combined list of homotypic and heterotypic synonym records.
        """
        results = raw_data.get("result", [])
        usage_id = self._extract_internal_accepted_id(results)

        syns = self._fetch_JSON(
            f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/taxon/{usage_id}/synonyms",
        )

        return syns.get("homotypic", []) + syns.get("heterotypic", [])

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw ChecklistBank synonym records into pipeline-standard synonym dicts.

        Parameters
        ----------
        synonym_data : list
            List of raw synonym records as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for s in synonym_data:
            name_obj = s.get("name", {})
            syn_name = name_obj.get("scientificName", "")
            if not syn_name or syn_name in seen:
                continue
            seen.add(syn_name)
            taxon_id = s.get("id", "")
            candidates.append(
                self._format_synonym(
                    name=syn_name,
                    author=name_obj.get("authorship", ""),
                    # note for future: COl can fill original source using 'name_obj.get("link", "")'
                    api_link=(
                        f"https://www.catalogueoflife.org/data/taxon/{taxon_id}"
                        if taxon_id
                        else ""
                    ),
                )
            )

        return candidates
