"""
Catalogue of Life (COL) API client.

COL is a global taxonomic checklist maintained by a consortium of taxonomists
that aggregates accepted names and synonymies across all kingdoms.  This client
queries the ChecklistBank REST API, which hosts COL releases as versioned
datasets.  The dataset key is pinned to COL26.5 (``DATASET_KEY = 315192``) and
should be updated when a newer release is published.

Documentation
-------------
https://api.checklistbank.org/

Fields implemented
------------------
- Taxonomy (kingdom → subfamily): accepted name row only
- author: both rows
- original_source: both rows
- status: both rows
- api_link: both rows
"""

from scripts.config import COL_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class COLAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the Catalogue of Life via ChecklistBank.
    """

    BASE_URL = COL_PORTAL.base_url
    # COL26.5 — update this key when a newer COL release is published on ChecklistBank
    DATASET_KEY = 315192

    def _fetch_query_data(self, name: str) -> dict:
        """
        Search the Catalogue of Life for *name* and return the raw response.

        Uses the ``nameusage/search`` endpoint with exact matching.  Returns
        ``{}`` when the response reports no results.

        Parameters
        ----------
        name : str
            The scientific name to search for (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict
            Full JSON search response with a ``"result"`` list of matching
            name-usage records, or ``{}`` if no results are found.
        """
        data = self._fetch_JSON(
            f"{self.BASE_URL}/dataset/{self.DATASET_KEY}/nameusage/search",
            params={"q": name, "type": "EXACT"},
        )
        if data["empty"]:
            return {}
        else:
            return data

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the ChecklistBank taxon ID from a name-usage record.

        Parameters
        ----------
        raw_data : dict
            A single name-usage record (from search results or synonym list).

        Returns
        -------
        str
            The ``"id"`` field value, or ``""`` if absent.
        """
        return raw_data.get("id", "")

    def _extract_internal_accepted_id(self, results: list) -> str:
        """
        Return the ChecklistBank taxon ID of the accepted name from search results.

        Prefers the first record with ``status="accepted"``; falls back to the
        ``parentId`` of the first result when the hit is itself a synonym.

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
        Fetch homotypic and heterotypic synonym records for the accepted taxon.

        Resolves the accepted taxon ID from the search results, then queries
        ``/taxon/{id}/synonyms`` and returns both synonym lists combined.

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

    def _fetch_accepted_data(self, raw_data: dict, synonym_data: list) -> dict:
        """
        Return the accepted taxon record for use as the synonym search term.

        Fast path: returns the accepted record already present in the search
        results when the query matched an accepted name directly.  Slow path:
        resolves the accepted ID via ``parentId``, fetches ``/taxon/{id}``, and
        attaches ``/taxon/{id}/classification`` so ``_extract_taxonomy`` can
        find the hierarchy data.

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
        Extract taxonomy fields from a COL name-usage record.

        Locates the ``"classification"`` list under the ``"usage"`` wrapper
        (search results) or at the top level (direct ``/taxon/{id}`` records).

        Parameters
        ----------
        data : dict
            A COL name-usage record (search result or direct taxon record).

        Returns
        -------
        dict[str, str]
            Keys: ``"kingdom"``, ``"phylum"``, ``"class_"``, ``"order"``,
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

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from a COL name-usage record.

        Parameters
        ----------
        accepted_data : dict
            The accepted name-usage record returned by
            ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if the
            scientific name is absent.
        """
        # nameusage/search results wrap under "usage"; direct /taxon/{id} records do not
        usage = accepted_data.get("usage") or accepted_data
        name_obj = usage.get("name", {})
        sci_name = normalize_query_string(name_obj.get("scientificName", ""))
        if not sci_name:
            return []
        taxon_id = self._extract_internal_id(accepted_data)
        genus, species = self._extract_genus_species(sci_name)
        classification = self._extract_taxonomy(accepted_data)
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
        Convert raw ChecklistBank synonym records into pipeline-standard dicts.

        Skips infraspecific names (e.g. ``var.``/``subsp.``/``f.`` ranks and bare
        trinomials), which would otherwise collapse to their binomial via
        ``_extract_genus_species`` and produce rows that differ only by internal
        ID. Deduplicates by canonical scientific name across the homotypic and
        heterotypic synonym lists.

        Parameters
        ----------
        synonym_data : list
            Combined homotypic + heterotypic synonym records from
            ``_fetch_synonym_data``.

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
            if not syn_name or syn_name in seen or self._is_infraspecific(syn_name):
                continue
            seen.add(syn_name)
            taxon_id = self._extract_internal_id(s)
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
                            f"https://www.catalogueoflife.org/data/taxon/{taxon_id}"
                            if taxon_id
                            else ""
                        ),
                    }
                )
            )

        return candidates
