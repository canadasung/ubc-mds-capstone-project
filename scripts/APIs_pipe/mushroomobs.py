"""
scripts/apis_pipe/mushroomobs.py
--------------------------------
Mushroom Observer API v2 client for the UBC MDS species aggregation pipeline.

Mushroom Observer (https://mushroomobserver.org) is a community-driven database
of fungal observations. This module provides synonyms: fetching historical
species-level aliases for a given accepted name, filtering out misspellings,
"sp." placeholders, and infraspecific taxa (varieties, forms, subspecies) so
the output matches what other pipeline sources (GBIF, Symbiota) return.
"""

import re

from .base import SpeciesAPI


class MushroomObserverAPI(SpeciesAPI):
    """
    Mushroom Observer API v2 client.

    Implements ``SpeciesAPI`` to supply fungal species-level synonyms from
    the Mushroom Observer community database.

    Attributes:
        BASE_URL (str): Root URL for all API v2 requests.
        _RANK_PATTERNS (list[tuple[re.Pattern, str]]): Ordered list of
            (compiled regex, category) pairs used by ``_parse_synonym`` to
            classify infraspecific rank abbreviations. Longer/more-specific
            patterns are listed before shorter ones to avoid false matches
            (e.g. ``subsp.`` before ``s.``).
    """

    BASE_URL = "https://mushroomobserver.org/api2"

    # Maps rank abbreviations found in MushroomObserver names to category keys.
    # Order matters: longer/more specific patterns must come before shorter ones.
    _RANK_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"\bsubsp\.\s*", re.IGNORECASE), "subspecies"),
        (re.compile(r"\bssp\.\s*", re.IGNORECASE), "subspecies"),
        (re.compile(r"\bs\.\s*", re.IGNORECASE), "subspecies"),
        (re.compile(r"\bvar\.\s*", re.IGNORECASE), "varieties"),
        (re.compile(r"\bv\.\s*", re.IGNORECASE), "varieties"),
        (re.compile(r"\bform\.\s*", re.IGNORECASE), "forms"),
        (re.compile(r"\bfo\.\s*", re.IGNORECASE), "forms"),
        (re.compile(r"\bf\.\s*", re.IGNORECASE), "forms"),
        (re.compile(r"\bsubsect\.\s*", re.IGNORECASE), "subsections"),
        (re.compile(r"\bsect\.\s*", re.IGNORECASE), "sections"),
        (re.compile(r"\bsubgen\.\s*", re.IGNORECASE), "subgenera"),
        (re.compile(r"\bsubg\.\s*", re.IGNORECASE), "subgenera"),
    ]

    def search(self, name: str) -> dict:
        """
        No-op implementation required by ``SpeciesAPI``.

        Mushroom Observer is used exclusively for synonym look-ups; it is not
        used as a primary taxonomic backbone. Callers should use ``synonyms()``
        directly.

        Args:
            name (str): Ignored.

        Returns:
            dict: Always an empty dict.
        """
        return {}

    def _parse_synonym(self, full_name: str, species_name: str) -> tuple[str, str]:
        """
        Extract the taxonomic rank category and specific epithet from a full name string.

        Iterates through predefined regex patterns to identify infraspecific ranks
        (e.g., subspecies, varieties). If no specific rank is found, it defaults
        to the general "synonyms" category.

        Args:
            full_name (str): The complete taxonomic name string to parse.
            species_name (str): The base species name used to strip out the epithet.

        Returns:
            tuple[str, str]: A tuple containing the category string (e.g., "varieties")
                and the extracted epithet or cleaned name.
        """
        for pattern, category in self._RANK_PATTERNS:
            if pattern.search(full_name):
                return category, pattern.split(full_name)[-1]
        return "synonyms", full_name.removeprefix(species_name).strip() or full_name

    def _fetch_names_data(self, name: str) -> dict:
        """
        Fetch raw synonym data from the Mushroom Observer names endpoint.

        Args:
            name (str): The accepted scientific name to query.

        Returns:
            dict: Parsed JSON response from the ``/names`` endpoint,
                or ``{}`` on any network or HTTP error.
        """
        return self._fetch(
            f"{self.BASE_URL}/names",
            params={
                "name": name,
                "include_synonyms": "true",
                "detail": "high",
                "format": "json",
            },
            timeout=15,
        )

    def _build_synonyms(self, data: dict, query_name: str) -> list[dict]:
        """
        Convert raw Mushroom Observer name data into pipeline-standard synonym dicts.

        Filters out misspellings, vague ``sp.`` records, and infraspecific taxa,
        then deduplicates the result.

        Args:
            data (dict): Parsed JSON response from ``_fetch_names_data()``.
            query_name (str): The original query name, used to seed deduplication.

        Returns:
            list[dict]: Pipeline-standard synonym records.
        """
        if data.get("number_of_records", 0) == 0:
            return []

        candidates = []
        for result in data.get("results", []):
            for synonym in result.get("synonyms", []):
                full_name = synonym.get("name", "")

                if not full_name or " sp." in full_name:
                    continue
                if synonym.get("misspelled", False):
                    continue

                category, _ = self._parse_synonym(full_name, query_name)
                if category != "synonyms":
                    continue

                candidates.append(
                    self._format_synonym(
                        name=full_name,
                        author=synonym.get("author", ""),
                        api_link=f"https://mushroomobserver.org/name/show_name/{synonym.get('id', '')}",
                    )
                )

        return self._deduplicate_synonyms(candidates, seed={query_name.lower()})

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve a filtered list of taxonomic synonyms from Mushroom Observer.

        Queries the API v2 '/names' endpoint, then filters and deduplicates the
        results via ``_build_synonyms()``.

        Args:
            name (str): The accepted scientific name to query.

        Returns:
            list[dict]: A list of synonym records formatted for the main aggregator.
                Each dictionary contains 'canonicalName', 'author', 'date',
                'publishedIn', and 'url'. Returns an empty list if the query fails
                or no valid synonyms are found.
        """
        data = self._fetch_names_data(name)
        if not data:
            return []
        return self._build_synonyms(data, query_name=name)
