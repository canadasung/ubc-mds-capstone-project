"""
GBIF API client.

SpeciesAPI implementation for GBIF. GBIF is an international open-data infrastructure that aggregates occurrence records and taxonomic data from institutions worldwide, enabling free access to hundreds of millions of biodiversity observations.
"""

import re

from scripts.config import GBIF_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class GBIFAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for GBIF.
    """

    BASE_URL = GBIF_PORTAL.base_url

    # Regular expression to extract a year from a GBIF "publishedIn" string.
    _PUBLISHED_IN_RE: re.Pattern = re.compile(r"\((\d{4})\)")

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the GBIF backbone taxonomy to find a precise match for a species.

        Uses the ``/species/match`` endpoint with strict matching enabled.
        Returns an empty dict when GBIF reports no match so that the base
        ``get_synonyms`` pipeline short-circuits cleanly.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict
            Parsed JSON match response, or ``{}`` if no match is found.
        """
        data = self._fetch_JSON(
            f"{self.BASE_URL}/species/match",
            params={"name": name, "strict": "true"},
        )
        # Check for a "NONE" matchType, which indicates no match found.
        if data.get("matchType") == "NONE":
            return {}

        return data

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the GBIF usage key from a raw API response dict.

        GBIF uses ``usageKey`` in ``/species/match`` responses and ``key`` in
        ``/species/{id}`` responses. This method handles both.

        Parameters
        ----------
        raw_data : dict
            A parsed GBIF API response containing either a ``usageKey`` or
            ``key`` field.

        Returns
        -------
        str
            The GBIF usage key for the queried taxon.

        Raises
        ------
        KeyError
            If neither ``usageKey`` nor ``key`` is present in ``raw_data``.
        """
        return str(raw_data.get("usageKey") or raw_data["key"])

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Extract the accepted taxon's GBIF usage key from match data.

        If the matched taxon is a synonym, GBIF provides an
        ``acceptedUsageKey`` pointing to the currently accepted name. Else, we get the "usageKey" or "key"

        Parameters
        ----------
        raw_data : dict
            The dictionary returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The GBIF usage key of the accepted taxon.
        """
        if "acceptedUsageKey" in raw_data:
            return str(raw_data["acceptedUsageKey"])
        else:
            return self._extract_internal_id(raw_data)

    def _fetch_synonym_data(self, raw_data: dict) -> list[dict]:
        """
        Fetch the raw synonyms list for an accepted taxon from GBIF.

        Parameters
        ----------
        raw_data : dict
            The parsed response returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            The ``"results"`` array from the GBIF synonyms endpoint,
            or ``[]`` when the request fails or returns no results.
        """
        self.accepted_id = self._extract_internal_accepted_id(raw_data)
        data = self._fetch_JSON(
            f"{self.BASE_URL}/species/{self.accepted_id}/synonyms",
            params={"limit": 500},
        )
        return data.get(
            "results", []
        )  # TODO: add error handling for failed request rather than just returning an empty list

    def _extract_publication_year(self, string: str) -> str:
        """
        Extract the publication year from a GBIF ``publishedIn`` string.

        Parameters
        ----------
        string : str
            A GBIF ``publishedIn`` value, e.g.
            ``"(1788). Hist. Fung. Halifax (Huddersfield) 2: 46"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if the pattern is absent.
        """
        m = self._PUBLISHED_IN_RE.search(string)
        return m.group(1) if m else ""

    def _fetch_synonym_search_term_data(
        self, raw_data: dict, synonym_data: list[dict]
    ) -> dict:
        """
        Return the accepted taxon's full species record for the synonym search term.

        When the ``/species/match`` hit is the accepted name itself, ``raw_data``
        already has the correct metadata. When the hit is a synonym, we fetch ``/species/{acceptedUsageKey}`` to get the accepted taxon's full record (same field structure as a match response: ``canonicalName``, ``authorship``, ``publishedIn``).

        Parameters
        ----------
        raw_data : dict
            The dictionary returned by ``_fetch_query_data``.
        synonym_data : list of dict
            Raw synonym records (unused here).

        Returns
        -------
        dict
            The accepted taxon's species record.
        """
        # Always fetch the full /species/{id} record for consistent authorship,
        # publishedIn, and taxonomicStatus regardless of whether the query matched
        # the accepted name directly or via a synonym.
        return self._fetch_JSON(
            f"{self.BASE_URL}/species/{self.accepted_id}"
        )  # TODO: add error handling for failed request

    def _compile_synonym_search_term(
        self, synonym_search_term_data: dict
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term from the
        GBIF match response.

        Parameters
        ----------
        synonym_search_term_data : dict
            The ``/species/match`` response dict.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if
            ``canonicalName`` is absent.
        """
        name = normalize_query_string(synonym_search_term_data["canonicalName"])
        if not name:
            return []

        published_in = synonym_search_term_data.get("publishedIn", "")
        key = self._extract_internal_id(synonym_search_term_data)
        genus, species = self._extract_genus_species(name)
        return [
            self._format_row(
                **{
                    "api_name": GBIF_PORTAL.display_name,
                    "kingdom": synonym_search_term_data.get("kingdom", ""),
                    "phylum": synonym_search_term_data.get("phylum", ""),
                    "class_": synonym_search_term_data.get("class", ""),
                    "family": synonym_search_term_data.get("family", ""),
                    "genus": genus,
                    "species": species,
                    "api_internal_id": key,
                    "author": synonym_search_term_data.get("authorship", ""),
                    "publication_year": self._extract_publication_year(published_in),
                    "publication_name": published_in,
                    "api_link": f"https://www.gbif.org/species/{key}",
                    "status": self._extract_status(
                        synonym_search_term_data.get("taxonomicStatus", "")
                    ),
                }
            )
        ]

    def _compile_synonyms(self, synonym_data: list[dict]) -> list[dict]:
        """
        Convert raw GBIF synonym records into pipeline-standard synonym dicts.

        Filters to species-rank results only and deduplicates by canonical name.

        Parameters
        ----------
        synonym_data : list of dict
            Raw synonym records as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_synonym``.
        """
        candidates = []
        seen = set()
        for item in synonym_data:
            canonical_name = normalize_query_string(item.get("canonicalName") or "")
            if item.get("rank") == "SPECIES" and canonical_name:
                if canonical_name not in seen:
                    seen.add(canonical_name)
                    published_in = item.get("publishedIn", "")
                    item_id = self._extract_internal_id(item)
                    genus, species = self._extract_genus_species(canonical_name)
                    candidates.append(
                        self._format_row(
                            **{
                                "api_name": GBIF_PORTAL.display_name,
                                "genus": genus,
                                "species": species,
                                "api_internal_id": item_id,
                                "author": item.get("authorship", ""),
                                "publication_year": self._extract_publication_year(
                                    published_in
                                ),
                                "publication_name": published_in,
                                "api_link": f"https://www.gbif.org/species/{item_id}",
                                "status": self._extract_status(
                                    item.get("taxonomicStatus", "")
                                ),
                            }
                        )
                    )
                    # TODO: bubble up as much as possible in terms of hardcoded strings/magic numbers
        return candidates
