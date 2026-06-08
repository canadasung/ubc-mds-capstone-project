"""
Mushroom Observer API client.

Mushroom Observer (https://mushroomobserver.org) is a community-driven database
of fungal observations.
"""

from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI
from .config import MUSHROOM_OBSERVER


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

    def _fetch_synonym_search_term_data(
        self, raw_data: dict, synonym_data: list
    ) -> dict:
        """
        Return ``raw_data`` as the search term data.

        Mushroom Observer embeds synonyms inside each result record; the synonym
        search term (the queried name) is one of the top-level result records
        in the same response.

        Parameters
        ----------
        raw_data : dict
            The full JSON response returned by ``_fetch_query_data``.
        synonym_data : list
            Flat list of raw synonym dicts (unused here).

        Returns
        -------
        dict
            The full JSON response dict.
        """
        return raw_data.get("results", [])  # TODO: add error handling

    def _compile_synonym_search_term(
        self, synonym_search_term_data: dict
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term from the
        Mushroom Observer response.

        Returns the first result that is not a misspelling and not infraspecific.

        Parameters
        ----------
        synonym_search_term_data : dict
            The full JSON response returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if no
            suitable result is found.
        """
        # TODO: bug here, this is duplicating the entry when the search term is a synonym itself. when the search term is an accepted name this is working as expected. Likely an issue with the formatting of how mushroom observer returns that the code is not matching. Seems like the returned data is not symmetrical whether you search an "accepted" name or a "synonym", even though mushroom observer itself does not classify anything to accepted or synonym
        for result in synonym_search_term_data:
            name = normalize_query_string(result["name"])
            if not name:
                continue
            if (
                " sp." in name
                or self._is_infraspecific(name)
                or result.get("misspelled", False)
            ):
                continue
            genus, species = self._extract_genus_species(name)
            return [
                self._format_row(
                    api_name=MUSHROOM_OBSERVER,
                    genus=genus,
                    species=species,
                    api_internal_id=str(result.get("id", "")),
                    author=result.get("author", ""),
                )
            ]
        return []

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
            full_name = normalize_query_string(full_name)
            if not full_name or full_name in seen:
                continue
            # removing rank incomplete names (rank marker above species level, e.g. "Amanita sp.", which indicates a collection-level annotation), misspelled, and infraspecific (rank markers below species level, e.g. "var.", "subsp.", etc) names
            if (
                " sp." in full_name
                or synonym.get("misspelled", False)
                or self._is_infraspecific(full_name)
            ):
                continue
            seen.add(full_name)
            genus, species = self._extract_genus_species(full_name)
            candidates.append(
                self._format_row(
                    api_name=MUSHROOM_OBSERVER,
                    genus=genus,
                    species=species,
                    api_internal_id=str(synonym.get("id", "")),
                    author=synonym.get("author", ""),
                )
            )
        return candidates
