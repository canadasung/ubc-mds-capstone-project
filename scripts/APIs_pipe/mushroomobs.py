"""
Mushroom Observer API client.

Mushroom Observer (https://mushroomobserver.org) is a community-driven database
of fungal observations.
"""

from .base import SpeciesAPI


class MushroomObserverAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for Mushroom Observer.
    """

    BASE_URL = "https://mushroomobserver.org/api2"

    def _fetch_query_data(self, name: str) -> dict:
        """
        Fetch raw data from the Mushroom Observer names endpoint.

        Parameters
        ----------
        name : str
            The scientific name to query.

        Returns
        -------
        dict
            JSON response from the ``/names`` endpoint,
            or ``{}`` on any network or HTTP error.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/names",
            params={
                "name": name,
                "include_synonyms": "true",
                "detail": "high",
                "format": "json",
            },
            timeout=15,
        )

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Flatten synonym records from all results into a single list.

        The Mushroom Observer API embeds synonyms directly inside each result
        record, so no second network request is needed.

        Parameters
        ----------
        raw_data : dict
            The full JSON response returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Flat list of raw synonym dicts extracted from all result records.
        """
        synonyms = []
        for result in raw_data.get("results", []):
            synonyms.extend(result.get("synonyms", []))
        return synonyms

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Filter and convert raw Mushroom Observer synonym records into pipeline-standard dicts.

        Skips misspellings, "sp." placeholders, infraspecific taxa, and
        duplicates. Deduplication is performed by case-sensitive name comparison
        as the loop fills candidates.

        Parameters
        ----------
        synonym_data : list
            Flat list of raw synonym dicts as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for synonym in synonym_data:
            full_name = synonym.get("name", "")
            if not full_name or full_name in seen:
                continue
            if " sp." in full_name:
                continue
            if synonym.get("misspelled", False):
                continue
            if self._is_infraspecific(full_name):
                continue
            seen.add(full_name)
            candidates.append(
                self._format_synonym(
                    name=full_name,
                    author=synonym.get("author", ""),
                )
            )
        return candidates
