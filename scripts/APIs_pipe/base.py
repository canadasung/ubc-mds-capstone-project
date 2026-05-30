"""
This module defines the foundational architecture and abstract blueprint for the
project's biodiversity data aggregation pipeline.

It establishes a strict contract (the `SpeciesAPI` base class) that all external
database connectors must adhere to.
"""

import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod

import requests


class SpeciesAPI(ABC):
    """
    Abstract base class establishing a unified contract for biodiversity database clients.

    This blueprint mandates that any integrated database client
    must implement two core methods and return data in strictly standardized formats.

    Shared class attributes
    -----------------------
    HEADERS : dict
        HTTP headers for requests that require a browser-like User-Agent.
        Portals and APIs that reject the default ``requests`` agent can use this
        directly by passing ``headers=self.HEADERS``.
    _INFRASPECIFIC_RE : re.Pattern
        Matches any infraspecific rank abbreviation (``var.``, ``subsp.``, ``ssp.``,
        ``f.``, ``fo.``, ``subf.``, ``cv.``, ``sect.``, ``subsect.``, ``ser.``,
        ``subgen.``, ``subg.``). Use ``_is_infraspecific()`` for filtering.
    """

    HEADERS: dict = {"User-Agent": "Mozilla/5.0"}

    _INFRASPECIFIC_RE: re.Pattern = re.compile(
        r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|subf\.|cv\.|sect\.|subsect\.|ser\.|subgen\.|subg\.)",
        re.IGNORECASE,
    )

    # ------------------------------------------------------------------
    # HTTP fetch helpers
    # ------------------------------------------------------------------

    def _fetch(self, url: str, params: dict = {}, timeout: int = 10) -> dict:
        """
        Make a GET request to a REST JSON endpoint and return the parsed response.

        Used by children that query standard REST APIs returning JSON. On network or HTTP error,
        prints a message and returns an empty dict so callers can handle it cleanly.

        Args:
            url (str): Full URL of the endpoint.
            params (dict): URL query parameters.
            timeout (int): Request timeout in seconds. Default is 10.

        Returns:
            dict: Parsed JSON response, or ``{}`` on any error.
        """
        try:
            resp = requests.get(
                url, params=params, headers=self.HEADERS, timeout=timeout
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"{type(self).__name__} fetch error [{url}]: {e}")
            return {}

    def _fetch_text(self, url: str, params: dict = {}, timeout: int = 10) -> str:
        """
        Make a GET request and return the raw response text.

        Used by children that consume XML or HTML responses. On error, prints a message and returns an empty
        string so callers can check for it.

        Args:
            url (str): Full URL of the endpoint.
            params (dict): URL query parameters.
            timeout (int): Request timeout in seconds. Default is 10.

        Returns:
            str: Raw response text, or ``""`` on any error.
        """
        try:
            resp = requests.get(
                url, params=params, headers=self.HEADERS, timeout=timeout
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"{type(self).__name__} fetch error [{url}]: {e}")
            return ""

    # ------------------------------------------------------------------
    # Shared data helpers
    # ------------------------------------------------------------------

    def _is_infraspecific(self, name: str) -> bool:
        """
        Return True if *name* contains an infraspecific rank abbreviation.

        Uses ``_INFRASPECIFIC_RE`` to detect rank markers such as ``var.``,
        ``subsp.``, ``f.``, etc. Children should call this instead of
        duplicating the regex check.

        Args:
            name (str): A taxonomic name string to test.

        Returns:
            bool: True when an infraspecific rank marker is found.
        """
        return bool(self._INFRASPECIFIC_RE.search(name))

    def _extract_year(self, authorship: str) -> str:
        """
        Extract a four-digit publication year from an authorship string.

        Matches the first year in the range 1700–2099. Returns an empty
        string when no year is found or when *authorship* is empty.

        Args:
            authorship (str): Authorship string, e.g. ``"(L.) Lam., 1783"``.

        Returns:
            str: Four-digit year string, or ``""`` if not found.
        """
        if not authorship:
            return ""
        match = re.search(r"\b(17|18|19|20)\d{2}\b", authorship)
        return match.group(0) if match else ""

    def _format_synonym(
        self,
        name: str,
        author: str = "",
        publication_date: str = "",
        publication_name: str = "",
        api_link: str = "",
    ) -> dict:
        """
        Construct a pipeline-standard synonym record dict.

        All children whose ``synonyms()`` method returns a ``list[dict]``
        should build each record with this helper to guarantee consistent
        key names across sources.

        Args:
            canonical_name (str): The accepted or synonym scientific name.
            author (str): Authorship string (e.g. ``"(L.) Lam."``).
            date (str): Publication year as a string (e.g. ``"1783"``).
            published_in (str): Full publication citation string.
            url (str): Direct URL to the taxon record in the source database.

        Returns:
            dict: Keys ``canonicalName``, ``author``, ``date``,
                ``publishedIn``, ``url``.
        """
        return {
            "name": name,
            "author": author,
            "publication_date": publication_date,
            "publication_name": publication_name,
            "api_link": api_link,
        }

    def _deduplicate_synonyms(
        self,
        candidates: list[dict],
        seed: set[str] | None = None,
    ) -> list[dict]:
        """
        Return *candidates* with duplicates removed, keyed by ``name``.

        Comparison is case-insensitive. The optional *seed* set pre-populates
        the seen names (e.g. ``{query_name.lower()}`` so the query itself is
        never repeated in the output).

        Args:
            candidates (list[dict]): Synonym records, each with a
                ``"name"`` key.
            seed (set[str] | None): Lower-cased names to treat as already seen.
                Defaults to an empty set.

        Returns:
            list[dict]: Deduplicated list preserving input order.
        """
        seen = set(seed) if seed else set()
        result = []
        for item in candidates:
            name = item.get("name", "").lower()
            if name and name not in seen:
                seen.add(name)
                result.append(item)
        return result

    def _parse_xml(self, xml_text: str) -> ET.Element | None:
        """
        Safely parse an XML string and return the root element.

        Args:
            xml_text (str): Raw XML response text.

        Returns:
            xml.etree.ElementTree.Element | None: The parsed root element,
                or ``None`` if parsing fails.
        """
        try:
            return ET.fromstring(xml_text)
        except ET.ParseError:
            return None

    # ------------------------------------------------------------------
    # Conventional helpers — children override as needed
    # ------------------------------------------------------------------

    def _get_internal_id(self, name: str):
        """
        Resolve a species name string to the API's internal database identifier.

        Args:
            name (str): The scientific name to resolve.

        Returns:
            The internal database identifier (type varies by source).

        Raises:
            NotImplementedError: When the child class has not provided an
                implementation for this step.
            LookupError: When the name cannot be resolved to an ID.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _get_internal_id()."
        )

    def _get_accepted_id(self, data):
        """
        Extract the internal ID of the *accepted* taxon from API response data.

        An *accepted* taxon is the currently valid name that a synonym refers
        to. For some APIs the full synonym list is only accessible via the
        accepted name's record, so this method is needed when the initial
        search result may be a synonym.

        Args:
            data: Parsed API response (type varies by source — e.g., ``dict``
                for GBIF, ``list`` for COL).

        Returns:
            The accepted taxon's internal identifier (type varies by source).

        Raises:
            NotImplementedError: When the child class has not provided an
                implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _get_accepted_id()."
        )

    def _build_synonyms(self, raw_data, query_name: str) -> list[dict]:
        """
        Convert raw API response data into pipeline-standard synonym records.

        This is the conventional final processing step that all children
        returning ``list[dict]`` synonyms should implement. It receives
        whatever raw data the corresponding ``_fetch_*`` method returned and
        produces the final list using ``_format_synonym()`` and
        ``_deduplicate_synonyms()``.

        COL and Symbiota are documented exceptions: COL returns raw
        ChecklistBank data processed downstream, and Symbiota returns a
        DataFrame.

        Args:
            raw_data: API-specific raw response data (type varies by source).
            query_name (str): The original query name, used to seed
                deduplication so the queried name is not repeated.

        Returns:
            list[dict]: Pipeline-standard synonym records.

        Raises:
            NotImplementedError: When the child class has not provided an
                implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _build_synonyms()."
        )

    # ------------------------------------------------------------------
    # Abstract interface — every child must implement both methods
    # ------------------------------------------------------------------

    @abstractmethod
    def search(self, name: str):
        """
        Queries the primary taxonomic backbone for a precise match.

        Args:
            name (str): The scientific name to search (e.g., "Amanita muscaria").

        Returns:
            dict | xml.etree.ElementTree.Element: The parsed database response
                containing the internal ID or taxonomy resolution for the name.
        """
        pass

    @abstractmethod
    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieves taxonomic synonyms and their associated publication metadata.

        Args:
            name (str): The primary accepted scientific name or target query.

        Returns:
            list[dict]: A list of dictionaries containing the synonyms. Clients
                MUST strive to return the following strict metadata keys (using
                empty strings if the specific database lacks the data):
                [
                    {
                        "canonicalName": "Amanita muscaria",
                        "author": "(L.) Lam.",
                        "date": "1783",
                        "publishedIn": "Encycl. Méth. Bot. 1(1): 111",
                        "url": "https://www.database.org/taxon/123"
                    },
                    ...
                ]
        """
        pass
