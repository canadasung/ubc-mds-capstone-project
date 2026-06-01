"""
GBIF API client.

SpeciesAPI implementation for GBIF. GBIF is an international open-data infrastructure that aggregates occurrence records and taxonomic data from institutions worldwide, enabling free access to hundreds of millions of biodiversity observations.
"""

import re

from .base import SpeciesAPI


class GBIFAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for GBIF.
    """

    BASE_URL = "https://api.gbif.org/v1"

    # Regular expression to extract a leading year from a GBIF "publishedIn" string.
    _PUBLISHED_IN_RE: re.Pattern = re.compile(r"^\((\d{4})\)\.\s*")

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
        if data.get("matchType") == "NONE":
            return {}
        return data

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Extract the accepted taxon's GBIF usage key from match data.

        If the matched taxon is a synonym, GBIF provides an
        ``acceptedUsageKey`` pointing to the currently accepted name.

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
        return str(raw_data["usageKey"])

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
        usage_key = self._extract_internal_accepted_id(raw_data)
        data = self._fetch_JSON(
            f"{self.BASE_URL}/species/{usage_key}/synonyms",
            params={"limit": 500},
        )
        return data.get("results", [])

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
        m = self._PUBLISHED_IN_RE.match(string)
        return m.group(1) if m else ""

    def _extract_publication_name(self, string: str) -> str:
        """
        Extract the publication name from a GBIF ``publishedIn`` string.

        Strips the leading year prefix (e.g. ``"(1788). "``) and returns
        the remainder as the publication name.

        Parameters
        ----------
        string : str
            A GBIF ``publishedIn`` value.

        Returns
        -------
        str
            The publication name, or the original string if no prefix is found.
        """
        return self._PUBLISHED_IN_RE.sub("", string)

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
            canonical_name = item.get("canonicalName")
            if item.get("rank") == "SPECIES" and canonical_name:
                if canonical_name not in seen:
                    seen.add(canonical_name)
                    published_in = item.get("publishedIn", "")
                    candidates.append(
                        self._format_synonym(
                            name=canonical_name,
                            author=item.get("authorship", ""),
                            publication_year=self._extract_publication_year(
                                published_in
                            ),
                            publication_name=self._extract_publication_name(
                                published_in
                            ),
                            api_link=f"https://www.gbif.org/species/{item.get('key')}",
                        )
                    )
        return candidates
