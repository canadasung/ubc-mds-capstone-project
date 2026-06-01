"""
GBIF API client.

SpeciesAPI implementation for GBIF. GBIF is a... (todo: fill in)
"""

from .base import SpeciesAPI


class GBIFAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for GBIF.
    """

    BASE_URL = "https://api.gbif.org/v1"

    def fetch_query_data(self, name: str) -> dict:
        """
        Query the GBIF backbone taxonomy to find a precise match for a species. Uses the '/species/match' endpoint with strict matching enabled.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response from GBIF containing match details, including
                the match type, taxonomic rank, and usage keys.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/species/match",
            params={"name": name, "strict": "true"},
        )

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Extract the id for the accepted species name from the match data.

        If the matched taxon is classified as a synonym, GBIF provides an 'acceptedUsageKey' pointing to the currently accepted name.

        Args:
            match_data (dict): The dictionary returned by the `search` method.

        Returns:
            str: The internal ID of the accepted name.
        """
        if "acceptedUsageKey" in raw_data:
            return str(raw_data["acceptedUsageKey"])
        return str(raw_data["usageKey"])

    def fetch_synonym_data(self, raw_data: dict) -> list[dict]:
        """
        Fetch the raw synonyms list for an accepted taxon from GBIF.

        Args:
            usage_key (int): The GBIF usage key of the accepted taxon.

        Returns:
            list[dict]: The ``"results"`` array from the GBIF synonyms endpoint,
                or an empty list when the request fails.
        """
        usage_key = self._extract_internal_accepted_id(raw_data)

        data = self._fetch_JSON(
            f"{self.BASE_URL}/species/{usage_key}/synonyms",
            params={"limit": 500},
        )
        return data.get("results", [])

    def compile_synonyms(self, synonym_data: list[dict]) -> list[dict]:
        """
        Convert raw GBIF synonym records into pipeline-standard synonym dicts.


        Args:
        todo: have AI adjust

        Returns:
            list[dict]: Pipeline-standard synonym records.
        """
        candidates = []
        seen = set()
        for item in synonym_data:
            if item.get("rank") == "SPECIES" and item.get("canonicalName"):
                if item not in seen:
                    seen.add(item)
                    candidates.append(
                        self._format_synonym(
                            name=item["canonicalName"],
                            author=item.get("authorship", ""),
                            publication_year=self._extract_year(),
                            publication_name=item.get("publishedIn", ""),
                            api_link=f"https://www.gbif.org/species/{item.get('key')}",
                        )
                    )
        return candidates

    def get_synonyms(self, name: str) -> list[dict]:
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

        usage_key = self._extract_internal_accepted_id(match)
        authorship = match.get("authorship", "")

        accepted_record = self._format_synonym(
            name=match.get("canonicalName") or name,
            author=authorship,
            publication_date=self._extract_year(authorship),
            publication_name=match.get("publishedIn", ""),
            api_link=f"https://www.gbif.org/species/{usage_key}",
        )

        raw_results = self._fetch_synonyms_page(usage_key)
        synonym_records = self._synonyms(raw_results, query_name=name)

        return [accepted_record] + synonym_records
