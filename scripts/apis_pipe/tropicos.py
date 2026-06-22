"""
Tropicos API client.

Tropicos is a botanical nomenclature database maintained by the Missouri
Botanical Garden.  It covers vascular plants, bryophytes, algae, and fungi,
providing accepted names, synonym lists, and publication metadata.  Unlike most
other sources in this pipeline, Tropicos requires a registered API key for
every request; set ``TROPICOS_API_KEY`` in your ``.env`` file before use.

Documentation
-------------
https://services.tropicos.org/help

Fields implemented
------------------
- author: both rows
- publication_name: accepted name row only
- publication_year: accepted name row only
- status: both rows
- api_link: both rows
"""

import os
import re

from dotenv import load_dotenv

from scripts.config import TROPICOS_API_KEY_PLACEHOLDER, TROPICOS_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI

load_dotenv()


class TropicosAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the Tropicos botanical database.
    """

    BASE_URL = TROPICOS_PORTAL.base_url

    def __init__(self):
        """
        Load the Tropicos API key from the ``TROPICOS_API_KEY`` environment variable.

        Raises
        ------
        ValueError
            If ``TROPICOS_API_KEY`` is absent or still set to the placeholder value.
        """
        self.key = os.getenv("TROPICOS_API_KEY")
        if not self.key or self.key == TROPICOS_API_KEY_PLACEHOLDER:
            raise ValueError(
                "Tropicos API key not provided. Set TROPICOS_API_KEY in the `.env` file."
            )

    def _fetch_query_data(self, name: str) -> list:
        """
        Search the Tropicos ``/Name/Search`` endpoint for *name*.

        Parameters
        ----------
        name : str
            The scientific name to search for (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        list
            Raw JSON list from ``/Name/Search``, or ``[]`` if no results are
            found or the API returns an error record.
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

        if (
            not isinstance(results, list)
            or len(results) == 0
            or results[0].get("Error") == "No names were found"
        ):
            return []
        else:
            return results

    def _extract_internal_id(self, raw_data: list) -> str:
        """
        Extract the Tropicos NameId from the first record of *raw_data*.

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

    def _fetch_accepted_name_data(self, name_id: str) -> list:
        """
        Fetch the accepted names for *name_id* from ``/Name/{id}/AcceptedNames``.

        Parameters
        ----------
        name_id : str
            The Tropicos NameId to look up accepted names for.

        Returns
        -------
        list
            Raw JSON list from ``/Name/{id}/AcceptedNames``, or ``[]`` if no
            accepted names are found or the request fails.
        """
        result = self._fetch_JSON(
            f"{self.BASE_URL}/Name/{name_id}/AcceptedNames",
            params={
                "apikey": self.key,
                "format": "json",
            },
        )
        if isinstance(result, list) and len(result) > 0:
            return result
        return []

    def _extract_internal_accepted_id(
        self, accepted_names_data: list, fallback_id: str = ""
    ) -> str:
        """
        Extract the accepted NameId from pre-fetched accepted names data.

        Parameters
        ----------
        accepted_names_data : list
            The list returned by ``_fetch_accepted_name_data``.
        fallback_id : str, optional
            NameId to return when the list is empty, meaning the queried name
            is itself the accepted name.

        Returns
        -------
        str
            NameId of the accepted name, or *fallback_id* if none found.
        """
        if accepted_names_data:
            accepted_id = accepted_names_data[0].get("AcceptedName", {}).get("NameId")
            if accepted_id is not None:
                return str(accepted_id)
        return fallback_id

    def _fetch_synonym_data(self, raw_data: list) -> list:
        """
        Fetch raw synonym records for the accepted taxon from ``/Name/{id}/Synonyms``.

        Resolves the accepted NameId by calling ``_fetch_accepted_name_data``
        and ``_extract_internal_accepted_id``, stores it as ``self.accepted_id``,
        then fetches and returns the synonym list.

        Parameters
        ----------
        raw_data : list
            The list returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Raw JSON synonym list, or ``[]`` if no synonyms are found.
        """
        name_id = self._extract_internal_id(raw_data)
        accepted_names_data = self._fetch_accepted_name_data(name_id)
        self.accepted_id = self._extract_internal_accepted_id(
            accepted_names_data, fallback_id=name_id
        )

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
            or results[0].get("Error") == "No names were found"
        ):
            return []
        else:
            return results  # TODO: double check this error handling

    def _fetch_accepted_data(self, raw_data: list, synonym_data: list) -> list:
        """
        Return the accepted name's record for use as the synonym search term.

        When the queried name is already the accepted name, returns *raw_data*
        directly.  When it is a synonym, ``self.accepted_id`` differs from the
        queried NameId, so ``/Name/{accepted_id}`` is fetched and returned as a
        one-item list so ``_compile_accepted`` always receives the
        accepted name.

        Parameters
        ----------
        raw_data : list
            The list returned by ``_fetch_query_data``.
        synonym_data : list
            Raw synonym records (unused here).

        Returns
        -------
        list
            A one-item list whose first element is the accepted name's record.
        """
        name_id = self._extract_internal_id(raw_data)
        if self.accepted_id != name_id:
            result = self._fetch_JSON(
                f"{self.BASE_URL}/Name/{self.accepted_id}",
                params={"apikey": self.key, "format": "json"},
            )

            # /Name/{id} returns a single dict
            if isinstance(result, dict) and not result.get("Error"):
                return [result]
            return []
        else:
            return raw_data

    def _extract_author(self, string: str) -> str:
        """
        Extract the authorship from a Tropicos ``ScientificNameWithAuthors`` string.

        Strips the first two tokens (genus and species epithet) and returns
        everything after them.

        Parameters
        ----------
        string : str
            A ``ScientificNameWithAuthors`` value, e.g.
            ``"Amanita muscaria (L.) Lam."``.

        Returns
        -------
        str
            Authorship string (e.g. ``"(L.) Lam."``), or ``""`` if the input
            has fewer than three tokens.
        """
        parts = string.split()
        return " ".join(parts[2:]) if len(parts) > 2 else ""

    def _extract_publication_year(self, string: str) -> str:
        """
        Extract a four-digit year from a Tropicos ``DisplayDate`` string.

        Parameters
        ----------
        string : str
            A ``DisplayDate`` value, e.g. ``"1753"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if not found.
        """
        m = re.search(r"\d{4}", string)
        return m.group(0) if m else ""

    def _extract_status(self, string: str) -> str:
        """
        Map a Tropicos nomenclature status to ``"Accepted"`` or ``"Synonym"``.

        Tropicos uses ``"Legitimate"`` for accepted names rather than
        ``"accepted"``.  Falls back to the base-class implementation for
        standard ``"accepted"`` / ``"synonym"`` substrings.

        Parameters
        ----------
        string : str
            A ``NomenclatureStatusName`` value, e.g. ``"Legitimate"``.

        Returns
        -------
        str
            ``"Accepted"``, ``"Synonym"``, or ``""`` if neither matches.
        """
        if "Legitimate" in string:
            return "Accepted"
        return super()._extract_status(string)

    def _compile_accepted(self, accepted_data: list) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from a Tropicos search result.

        Uses the first record in *accepted_data*, which is always the
        accepted name's record as returned by ``_fetch_accepted_data``.

        Parameters
        ----------
        accepted_data : list
            The accepted name records returned by ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if the
            name cannot be determined.
        """
        if self._is_empty(accepted_data):
            return []
        item = accepted_data[0]
        name = normalize_query_string(item["ScientificName"])
        if not name or self._is_infraspecific(name):
            return []
        name_id = self._extract_internal_id(accepted_data)
        genus, species = self._extract_genus_species(name)
        return [
            self._format_row(
                **{
                    "api_name": TROPICOS_PORTAL.display_name,
                    "genus": genus,
                    "species": species,
                    "api_internal_id": name_id,
                    "author": item.get("Author", ""),
                    "publication_name": item.get("DisplayReference", ""),
                    "publication_year": self._extract_publication_year(
                        item.get("DisplayDate", "")
                    ),
                    "status": self._extract_status(
                        item.get("NomenclatureStatusName", "")
                    ),
                    "api_link": (
                        f"https://www.tropicos.org/name/{name_id}" if name_id else ""
                    ),
                }
            )
        ]

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw Tropicos synonym records into pipeline-standard dicts.

        Each record is expected to nest the name data under a ``"SynonymName"``
        key.  Deduplicates by canonical scientific name.

        Parameters
        ----------
        synonym_data : list
            Raw synonym records as returned by ``_fetch_synonym_data``.

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
                    **{
                        "api_name": TROPICOS_PORTAL.display_name,
                        "genus": genus,
                        "species": species,
                        "api_internal_id": syn_id,
                        "author": self._extract_author(
                            syn_info.get("ScientificNameWithAuthors", "")
                        ),
                        "status": "Synonym",
                        "api_link": (
                            f"https://www.tropicos.org/name/{syn_id}" if syn_id else ""
                        ),
                    }
                )
            )
        return candidates
