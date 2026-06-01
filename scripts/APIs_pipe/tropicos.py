"""
Tropicos API client.

SpeciesAPI implementation for Tropicos, a botanical database maintained by the Missouri Botanical Garden. Unlike open APIs, Tropicos requires a registered API key for all requests.
"""

import os

from dotenv import load_dotenv

from tests.APIs_pipe.test_env_configured import _PLACEHOLDER_TROPICOS

from .base import SpeciesAPI

load_dotenv()


class TropicosAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for Tropicos.
    """

    BASE_URL = "http://services.tropicos.org"

    def __init__(self):
        """
        Load the registered Tropicos API key from the TROPICOS_API_KEY environment variable.

        Raises
        ------
        ValueError
            If the TROPICOS_API_KEY environment variable is missing or is still the placeholder value.
        """
        self.key = os.getenv("TROPICOS_API_KEY")
        if not self.key or self.key == _PLACEHOLDER_TROPICOS:
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
        # The API returns an empty dict for network/HTTP errors, so we check for a list (successful response type) before returning.
        if not isinstance(results, list) or len(results) == 0:
            return []
        return results

    def _extract_internal_id(self, raw_data: list) -> str:
        """
        Extract the Tropicos NameId from the first search result.

        Parameters
        ----------
        raw_data : list
            The list returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The internal Tropicos NameId.

        Raises
        ------
        LookupError
            When no NameId can be found in the first result.
        """
        name_id = raw_data[0].get("NameId")
        if name_id is None:
            raise LookupError(
                f"{type(self).__name__} error: could not extract NameId from search result."
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
        accepted_id = self._extract_internal_accepted_id(raw_data)
        results = self._fetch_JSON(
            f"{self.BASE_URL}/Name/{accepted_id}/Synonyms",
            params={
                "apikey": self.key,
                "format": "json",
            },
        )
        if not isinstance(results, list):
            return []
        return results

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
            syn_name = syn_info.get("ScientificName")
            if not syn_name or syn_name in seen:
                continue
            seen.add(syn_name)
            syn_id = syn_info.get("NameId")
            candidates.append(
                self._format_synonym(
                    name=syn_name,
                    author=syn_info.get("Author", ""),
                    api_link=(
                        f"https://www.tropicos.org/name/{syn_id}" if syn_id else ""
                    ),
                )
            )
        return candidates
