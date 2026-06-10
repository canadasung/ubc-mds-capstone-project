"""
Tropicos API client.

SpeciesAPI implementation for Tropicos, a botanical database maintained by the Missouri Botanical Garden. Unlike open apis, Tropicos requires a registered API key for all requests.
"""

import os

from dotenv import load_dotenv

from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI
from .config import TROPICOS_API_KEY_PLACEHOLDER, TROPICOS_PORTAL

load_dotenv()


class TropicosAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for Tropicos.
    """

    BASE_URL = TROPICOS_PORTAL.base_url

    def __init__(self):
        """
        Load the registered Tropicos API key from the TROPICOS_API_KEY environment variable.

        Raises
        ------
        ValueError
            If the TROPICOS_API_KEY environment variable is missing or is still the placeholder value.
        """
        self.key = os.getenv("TROPICOS_API_KEY")
        if not self.key or self.key == TROPICOS_API_KEY_PLACEHOLDER:
            raise ValueError(
                "Tropicos API key not provided. Set TROPICOS_API_KEY in the `.env` file."
            )

    def _fetch_query_data(self, name: str) -> list:
        """
        Search the Tropicos database for a given scientific name.

        Parameters
        ----------
        name : str
            The scientific name to search for (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        list
            The raw JSON response list from the /Name/Search endpoint, or ``[]``
            if no results are found.
        """
        results = self._fetch_JSON(
            f"{self.BASE_URL}/Name/Search",
            params={
                "name": name,
                "type": "exact",
                "apikey": self.key,
                "format": "json",
            },
        )

        # Check for list without error
        if (
            not isinstance(results, list)
            or len(results) == 0
            or results["Error"] == "No names were found"
        ):
            return []
        else:
            return results

    def _extract_internal_id(self, raw_data: list) -> str:
        """
        Extract the Tropicos NameId from the first record in a raw results list.

        Parameters
        ----------
        raw_data : list
            A list of name records from the Tropicos API.

        Returns
        -------
        str
            The internal Tropicos NameId.

        Raises
        ------
        LookupError
            If ``NameId`` is absent from the first record.
        """
        name_id = raw_data[0].get("NameId")
        if name_id is None:
            raise LookupError(
                f"{type(self).__name__} error: could not extract NameId from record."
            )
        return str(name_id)

    def _extract_internal_accepted_id(self, raw_data: list) -> str:
        """
        Resolve a NameId to the accepted name's NameId.

        Queries the /Name/{id}/AcceptedNames endpoint. If the searched name is a
        synonym, the first accepted name's NameId is returned. If no accepted
        names are found (i.e. the searched name is itself the accepted name), the
        original NameId is returned unchanged.

        Parameters
        ----------
        raw_data : list
            The list returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The NameId of the accepted name.
        """
        name_id = self._extract_internal_id(raw_data)
        accepted = self._fetch_JSON(
            f"{self.BASE_URL}/Name/{name_id}/AcceptedNames",
            params={
                "apikey": self.key,
                "format": "json",
            },
        )

        if isinstance(accepted, list) and len(accepted) > 0:
            accepted_id = accepted[0].get("AcceptedName", {}).get("NameId")
            if accepted_id is not None:
                return str(accepted_id)
        return name_id

    def _fetch_synonym_data(self, raw_data: list) -> list:
        """
        Fetch raw synonym records for the accepted taxon resolved from the search results.

        Parameters
        ----------
        raw_data : list
            The list returned by ``_fetch_query_data``.

        Returns
        -------
        list
            The raw JSON synonym list from the /Name/{id}/Synonyms endpoint,
            or ``[]`` if no synonyms are found.
        """
        self.accepted_id = self._extract_internal_accepted_id(raw_data)
        results = self._fetch_JSON(
            f"{self.BASE_URL}/Name/{self.accepted_id}/Synonyms",
            params={
                "apikey": self.key,
                "format": "json",
            },
        )
        if (
            not isinstance(results, list)
            or len(results) == 0
            or results["Error"] == "No names were found"
        ):
            return []
        else:
            return results  # TODO: double check this error handling

    def _fetch_synonym_search_term_data(
        self, raw_data: list, synonym_data: list
    ) -> list:
        """
        Return the accepted name's data as the search term.

        When the queried name is already the accepted name, the first search
        result is returned directly. When the queried name is a synonym,
        ``self.accepted_id`` (cached by ``_fetch_synonym_data``) differs from the
        queried NameId, so we fetch the accepted name record from
        ``/Name/{self.accepted_id}`` and return it as a one-item list so that
        ``_compile_synonym_search_term`` always receives the accepted name, not
        the synonym that was searched.

        Parameters
        ----------
        raw_data : list
            The list returned by ``_fetch_query_data``.
        synonym_data : list
            Raw synonym records (unused here).

        Returns
        -------
        list
            A list whose first element is the accepted name's data.
        """
        name_id = self._extract_internal_id(raw_data)
        if self.accepted_id != name_id:
            result = self._fetch_JSON(
                f"{self.BASE_URL}/Name/{self.accepted_id}",
                params={"apikey": self.key, "format": "json"},
            )

            if (
                not isinstance(result, list)
                or len(result) == 0
                or result["Error"] == "No names were found"
            ):
                return []
            else:
                return [result]  # TODO: double check this error handling
        else:
            return raw_data

    def _compile_synonym_search_term(
        self, synonym_search_term_data: list
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term from the
        Tropicos search response.

        Uses the first search hit, which corresponds to the queried name (or
        the accepted name when the query resolves directly to one).

        Parameters
        ----------
        synonym_search_term_data : list
            The search results list returned by ``_fetch_synonym_search_term_data``.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if the
            name cannot be determined.
        """
        if self._is_empty(synonym_search_term_data):
            return []
        item = synonym_search_term_data[0]
        name = normalize_query_string(item["ScientificName"])
        if not name or self._is_infraspecific(name):
            return []
        name_id = self._extract_internal_id(synonym_search_term_data)
        genus, species = self._extract_genus_species(name)
        return [
            self._format_row(
                api_name=TROPICOS_PORTAL.display_name,
                genus=genus,
                species=species,
                api_internal_id=name_id,
                author=item.get("Author", ""),
                api_link=(
                    f"https://www.tropicos.org/name/{name_id}" if name_id else ""
                ),
            )
        ]

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw Tropicos synonym records into pipeline-standard synonym dicts.

        Parameters
        ----------
        synonym_data : list
            Raw synonym records as returned by ``_fetch_synonym_data``. Each
            record nests the actual name data under a ``"SynonymName"`` key.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for item in synonym_data:
            syn_info = item.get("SynonymName", {})
            if self._is_empty(syn_info):
                continue
            syn_name = normalize_query_string(syn_info.get("ScientificName", ""))
            if not syn_name or syn_name in seen or self._is_infraspecific(syn_name):
                continue
            seen.add(syn_name)
            syn_id = self._extract_internal_id(
                [syn_info]
            )  # wrapped in artifical list to conform with raw data formats
            # TODO: look into the raw data formats; why is it a list and we also get the first item? do we need anything else from the other items, or can we just normalize to the first item at fetch time?
            # TODO: not sure if this is the correct synonym ID, since it appears that all results are getting the accepted name's NameId. Need to investigate further and check against the API documentation.
            genus, species = self._extract_genus_species(syn_name)
            candidates.append(
                self._format_row(
                    api_name=TROPICOS_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=syn_id,
                    author=syn_info.get("Author", ""),
                    api_link=(
                        f"https://www.tropicos.org/name/{syn_id}" if syn_id else ""
                    ),
                )
            )
        return candidates
