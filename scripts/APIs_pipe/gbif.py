"""
This module serves as the dedicated connector between the application's data
aggregation pipeline and the Global Biodiversity Information Facility (GBIF) API.
It is a concrete, fully realized implementation of the `SpeciesAPI` blueprint,
which can be found in base.py.

It automates the retrieval of exact taxonomic matches and resolves historical
synonyms through secondary API routing.
"""

import requests

from .base import SpeciesAPI


class GBIFAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for the Global Biodiversity Information Facility (GBIF).

    This client interacts directly with the GBIF REST API to perform taxonomic matching
    and retrieve historical synonyms.
    """

    BASE = "https://api.gbif.org/v1"

    def search(self, name: str) -> dict:
        """
        Query the GBIF backbone taxonomy to find a precise match for a species.

        Uses the '/species/match' endpoint with strict matching enabled.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response from GBIF containing match details, including
                the match type, taxonomic rank, and usage keys.
        """
        return self._fetch(
            f"{self.BASE}/species/match",
            params={"name": name, "strict": "true"},
        )

    def _get_accepted_id(self, match_data: dict) -> int:
        """
        Extract the correct GBIF usage key from match data.

        If the matched taxon is classified as a synonym, GBIF provides an
        'acceptedUsageKey' pointing to the currently accepted name. This method
        prioritizes the accepted key to ensure downstream queries use the valid taxon.

        Args:
            match_data (dict): The dictionary returned by the `search` method.

        Returns:
            int: The official numeric ID of the accepted name.
        """
        if "acceptedUsageKey" in match_data:
            return match_data["acceptedUsageKey"]
        return match_data["usageKey"]

    def _fetch_synonyms_page(self, usage_key: int) -> list[dict]:
        """
        Fetch the raw synonyms list for an accepted taxon from GBIF.

        Args:
            usage_key (int): The GBIF usage key of the accepted taxon.

        Returns:
            list[dict]: The ``"results"`` array from the GBIF synonyms endpoint,
                or an empty list when the request fails.
        """
        data = self._fetch(
            f"{self.BASE}/species/{usage_key}/synonyms",
            params={"limit": 500},
        )
        return data.get("results", [])

    def _build_synonyms(self, raw_results: list[dict], query_name: str) -> list[dict]:
        """
        Convert raw GBIF synonym records into pipeline-standard synonym dicts.

        Filters to SPECIES rank only, extracts authorship years, and deduplicates.

        Args:
            raw_results (list[dict]): The ``"results"`` list from GBIF's synonyms endpoint.
            query_name (str): The original query name, used to seed deduplication.

        Returns:
            list[dict]: Pipeline-standard synonym records.
        """
        candidates = []
        for item in raw_results:
            if item.get("rank") == "SPECIES" and item.get("canonicalName"):
                authorship = item.get("authorship", "")
                candidates.append(
                    self._format_synonym(
                        name=item["canonicalName"],
                        author=authorship,
                        publication_date=self._extract_year(authorship),
                        publication_name=item.get("publishedIn", ""),
                        api_link=f"https://www.gbif.org/species/{item.get('key')}",
                    )
                )
        return self._deduplicate_synonyms(candidates, seed={query_name.lower()})

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve species-level synonyms and metadata for a given scientific name.

        First resolves the name to its accepted usage key, then fetches and
        builds the synonym list. The accepted name itself is always the first
        record returned.

        Args:
            name (str): The scientific name to query.

        Returns:
            list[dict]: A list of dictionaries containing the canonical names and
                associated metadata. The first item is always the currently accepted
                taxon, followed by any discovered synonyms.
                Example:
                [
                    {
                        "canonicalName": "Amanita muscaria",
                        "author": "(L.) Lam.",
                        "date": "1783",
                        "publishedIn": "Encycl. Méth. Bot. 1(1): 111",
                        "url": "https://www.gbif.org/species/3328328"
                    },
                    ...
                ]
        """
        match = self.search(name)
        if match.get("matchType") == "NONE":
            return []

        usage_key = self._get_accepted_id(match)
        authorship = match.get("authorship", "")

        accepted_record = self._format_synonym(
            name=match.get("canonicalName") or name,
            author=authorship,
            publication_date=self._extract_year(authorship),
            publication_name=match.get("publishedIn", ""),
            api_link=f"https://www.gbif.org/species/{usage_key}",
        )

        raw_results = self._fetch_synonyms_page(usage_key)
        synonym_records = self._build_synonyms(raw_results, query_name=name)

        return [accepted_record] + synonym_records
