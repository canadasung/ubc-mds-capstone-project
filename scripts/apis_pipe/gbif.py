"""
GBIF API client.

GBIF (Global Biodiversity Information Facility) is an international open-data
infrastructure that aggregates occurrence records and taxonomic data contributed
by institutions worldwide.  This client uses the GBIF backbone taxonomy via the
``/species/match`` endpoint to resolve a name to a usage key, then retrieves its
synonym list from ``/species/{id}/synonyms``.

Documentation
-------------
https://www.gbif.org/developer/summary

Fields implemented
------------------
- Taxonomy (kingdom → family): accepted name row only
- author: both rows
- publication_name: both rows
- publication_year: both rows
- status: both rows
- api_link: both rows
"""

import re

from scripts.config import GBIF_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class GBIFAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the GBIF backbone taxonomy.
    """

    BASE_URL = GBIF_PORTAL.base_url

    # Matches a year wrapped in parentheses, e.g. "(1788)" in publishedIn strings.
    _PUBLISHED_IN_RE: re.Pattern = re.compile(r"\((\d{4})\)")
    # Matches a bare year NOT inside parentheses, e.g. "1860" in "Suckley, 1860".
    # Negative lookbehind/lookahead ensure the digits aren't enclosed in parens.
    _AUTHOR_YEAR_RE: re.Pattern = re.compile(r"(?<!\()\b(\d{4})\b(?!\))")

    def _fetch_query_data(self, name: str) -> dict:
        """
        Match *name* against the GBIF backbone taxonomy and return the raw hit.

        Uses ``/species/match`` with ``strict=true``.  Returns ``{}`` when
        GBIF reports ``matchType=NONE`` so the pipeline short-circuits cleanly.

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
        Extract the GBIF usage key from a raw API response.

        Handles both ``/species/match`` responses (``usageKey``) and
        ``/species/{id}`` responses (``key``).

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
        Extract the accepted taxon's usage key from a match response.

        Returns ``acceptedUsageKey`` when present (synonym hit), otherwise
        falls back to ``_extract_internal_id`` (accepted name hit).

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
        Fetch the raw synonym list for the accepted taxon from ``/species/{id}/synonyms``.

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

    def _extract_publication_year(self, published_in: str, author: str = "") -> str:
        """
        Extract the publication year from a GBIF ``publishedIn`` string, falling
        back to the ``authorship`` string if no year is found there.

        Parameters
        ----------
        published_in : str
            A GBIF ``publishedIn`` value, e.g.
            ``"(1788). Hist. Fung. Halifax (Huddersfield) 2: 46"``.
        author : str
            A GBIF ``authorship`` value, e.g. ``"Linnaeus, 1758"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if the pattern is absent in both.
        """
        m = self._PUBLISHED_IN_RE.search(published_in)
        if m:
            return m.group(1)
        m = self._AUTHOR_YEAR_RE.search(author)
        return m.group(1) if m else ""

    def _fetch_accepted_data(self, raw_data: dict, synonym_data: list[dict]) -> dict:
        """
        Fetch the accepted taxon's full ``/species/{id}`` record.

        Always fetches ``/species/{acceptedUsageKey}`` regardless of whether the
        initial match was an accepted name or a synonym, ensuring consistent
        ``authorship``, ``publishedIn``, and ``taxonomicStatus`` fields.

        Parameters
        ----------
        raw_data : dict
            The dictionary returned by ``_fetch_query_data``.
        synonym_data : list of dict
            Raw synonym records (unused here).

        Returns
        -------
        dict
            The accepted taxon's full species record from ``/species/{id}``.
        """

        return self._fetch_JSON(
            f"{self.BASE_URL}/species/{self.accepted_id}"
        )  # TODO: add error handling for failed request

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from the GBIF species record.

        Parameters
        ----------
        accepted_data : dict
            The accepted taxon's full record from ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if
            ``canonicalName`` is absent.
        """
        name = normalize_query_string(accepted_data["canonicalName"])
        if not name:
            return []

        published_in = accepted_data.get("publishedIn", "")
        key = self._extract_internal_id(accepted_data)
        genus, species = self._extract_genus_species(name)
        author = accepted_data.get("authorship", "")
        return [
            self._format_row(
                **{
                    "api_name": GBIF_PORTAL.display_name,
                    "kingdom": accepted_data.get("kingdom", ""),
                    "phylum": accepted_data.get("phylum", ""),
                    "class_": accepted_data.get("class", ""),
                    "order": accepted_data.get("order", ""),
                    "family": accepted_data.get("family", ""),
                    "genus": genus,
                    "species": species,
                    "api_internal_id": key,
                    "author": author,
                    "publication_year": self._extract_publication_year(
                        published_in, author
                    ),
                    "publication_name": published_in,
                    "api_link": f"https://www.gbif.org/species/{key}",
                    "status": self._extract_status(
                        accepted_data.get("taxonomicStatus", "")
                    ),
                }
            )
        ]

    def _compile_synonyms(self, synonym_data: list[dict]) -> list[dict]:
        """
        Convert raw GBIF synonym records into pipeline-standard synonym dicts.

        Filters to ``rank=SPECIES`` records only and deduplicates by canonical name.

        Parameters
        ----------
        synonym_data : list of dict
            Raw synonym records as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
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
                    author = item.get("authorship", "")
                    candidates.append(
                        self._format_row(
                            **{
                                "api_name": GBIF_PORTAL.display_name,
                                "genus": genus,
                                "species": species,
                                "api_internal_id": item_id,
                                "author": author,
                                "publication_year": self._extract_publication_year(
                                    published_in, author
                                ),
                                "publication_name": published_in,
                                "api_link": f"https://www.gbif.org/species/{item_id}",
                                "status": self._extract_status(
                                    item.get("taxonomicStatus", "")
                                ),
                            }
                        )
                    )

        return candidates
