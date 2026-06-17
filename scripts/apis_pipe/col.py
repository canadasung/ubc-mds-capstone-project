"""
Catalogue of Life API client.

SpeciesAPI implementation for the Catalogue of Life (COL), served via the ChecklistBank API. COL is a global taxonomic checklist that provides accepted names and synonymies.
"""

from scripts.config import COL_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class COLAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for the Catalogue of Life (COL).
    """

    BASE_URL = COL_PORTAL.base_url
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
        data = self._fetch_JSON(
            f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/nameusage/search",
            params={"q": name, "type": "EXACT"},
        )
        if data["empty"]:
            return {}
        else:
            return data

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
            (r for r in results if r["usage"]["status"] == "accepted"),
            None,
        )
        if accepted is not None:
            return accepted["id"]

        first = results[0]
        usage_id = first["usage"]["parentId"]
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
        results = raw_data["result"]
        usage_id = self._extract_internal_accepted_id(results)

        syns = self._fetch_JSON(
            f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/taxon/{usage_id}/synonyms",
        )

        return syns.get("homotypic", []) + syns.get("heterotypic", [])

    def _fetch_synonym_search_term_data(
        self, raw_data: dict, synonym_data: list
    ) -> dict:
        """
        Return the accepted taxon record for the synonym search term.

        Two paths:

        1. Fast path — the accepted record is already in ``raw_data["result"]``
           (query matched the accepted name directly).
        2. Slow path — query matched a synonym; no accepted record is in the
           search results. Resolves the accepted ID via ``parentId`` using
           ``_extract_internal_accepted_id``, then fetches the taxon record
           from the ChecklistBank ``/taxon/{id}`` endpoint.

        Parameters
        ----------
        raw_data : dict
            The full JSON search response returned by ``_fetch_query_data``.
        synonym_data : list
            Raw synonym records (unused here).

        Returns
        -------
        dict
            The accepted name-usage record, or ``{}`` if it cannot be resolved.
        """
        results = raw_data["result"]

        # Fast path: accepted record already present in search results
        accepted = next(
            (r for r in results if r["usage"]["status"] == "accepted"),
            None,
        )
        if accepted is not None:
            return accepted

        # Slow path: query was a synonym — fetch accepted taxon by ID.
        # The /taxon/{id} response does not include classification, so we fetch
        # it separately and attach it so _extract_taxonomy can find it.
        try:
            accepted_id = self._extract_internal_accepted_id(results)
            taxon = self._fetch_JSON(
                f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/taxon/{accepted_id}",
            )
            if not taxon:  # TODO: add error handling for empty taxon
                return {}
            # Get and append classification information separately, as it is not returned by taxon/accepted_id
            classification = self._fetch_JSON(
                f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/taxon/{accepted_id}/classification",
            )
            taxon["classification"] = (
                classification if isinstance(classification, list) else []
            )
            return taxon
        except LookupError:
            # TODO: add error handling for this case
            return {}

    def _extract_taxonomy(self, data: dict) -> dict[str, str]:
        """
        Extract kingdom, phylum, class, order, family, and subfamily from a COL
        name-usage record.

        Locates the ``"classification"`` list under the ``"usage"`` wrapper
        (nameusage/search results) or at the top level (direct /taxon/{id}
        records).

        Parameters
        ----------
        data : dict
            A COL name-usage record (either search result or direct taxon record).

        Returns
        -------
        dict[str, str]
            Keys are ``"kingdom"``, ``"phylum"``, ``"class_"``, ``"order"``,
            ``"family"``, and ``"subfamily"``.
        """
        usage = data.get("usage") or data
        classification = usage.get("classification") or data.get("classification", [])
        rank_map = {
            item.get("rank", "").lower(): item.get("name", "")
            for item in classification
            if item.get("rank") and item.get("name")
        }
        return {
            "kingdom": rank_map.get("kingdom", ""),
            "phylum": rank_map.get("phylum", ""),
            "class_": rank_map.get("class", ""),
            "order": rank_map.get("order", ""),
            "family": rank_map.get("family", ""),
            "subfamily": rank_map.get("subfamily", ""),
        }

    def _compile_synonym_search_term(
        self, synonym_search_term_data: dict
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term from the
        COL accepted name-usage record.

        Parameters
        ----------
        synonym_search_term_data : dict
            The accepted name-usage record returned by
            ``_fetch_synonym_search_term_data``.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if the
            scientific name is absent.
        """
        # nameusage/search results wrap under "usage"; direct /taxon/{id} records do not
        usage = synonym_search_term_data.get("usage") or synonym_search_term_data
        name_obj = usage.get("name", {})
        sci_name = normalize_query_string(name_obj.get("scientificName", ""))
        if not sci_name:
            return []
        taxon_id = synonym_search_term_data.get("id", "")
        genus, species = self._extract_genus_species(sci_name)
        classification = self._extract_taxonomy(synonym_search_term_data)
        return [
            self._format_row(
                **{
                    "api_name": COL_PORTAL.display_name,
                    **classification,
                    "genus": genus,
                    "species": species,
                    "api_internal_id": str(taxon_id),
                    "author": name_obj.get("authorship", ""),
                    "original_source": name_obj.get("link", ""),
                    "status": self._extract_status(usage.get("status", "")),
                    "api_link": (
                        f"https://www.catalogueoflife.org/data/taxon/{taxon_id}"
                        if taxon_id
                        else ""
                    ),
                }
            )
        ]

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
            syn_name = normalize_query_string(name_obj.get("scientificName", ""))
            if not syn_name or syn_name in seen:
                continue
            seen.add(syn_name)
            taxon_id = s.get("id", "")
            genus, species = self._extract_genus_species(syn_name)
            candidates.append(
                self._format_row(
                    **{
                        "api_name": COL_PORTAL.display_name,
                        "genus": genus,
                        "species": species,
                        "api_internal_id": str(taxon_id),
                        "author": name_obj.get("authorship", ""),
                        "original_source": name_obj.get("link", ""),
                        "status": self._extract_status(s.get("status", "")),
                        "api_link": (
                            f"https://www.catalogueoflife.org/data/taxon/{taxon_id}"  # TODO: while we do have unique taxon_id for each synonym, they all route to the same page for "accepted" name. Likely desired behavior, but double check against API documentation to confirm that this is expected.
                            if taxon_id
                            else ""
                        ),
                    }
                )
            )

        return candidates
