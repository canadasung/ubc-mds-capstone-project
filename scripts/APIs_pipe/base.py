"""
This module defines the foundational architecture and abstract blueprint for the
project's biodiversity data aggregation pipeline.

It establishes a contract (the `SpeciesAPI` base class) that all external
database connectors must adhere to.
"""

import inspect
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod

import requests

from scripts.utils.normalize_strings import normalize_scientific_name


class SpeciesAPI(ABC):
    """
    Abstract base class establishing a unified contract for biodiversity database clients.

    Attributes
    ----------
    HEADERS : dict
        HTTP headers for requests that require a browser-like User-Agent.
        Portals and APIs that reject the default ``requests`` agent can use this.
    """

    HEADERS: dict = {"User-Agent": "Mozilla/5.0"}
    BASE_URL: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls) and not hasattr(cls, "BASE_URL"):
            raise TypeError(f"{cls.__name__} must define a BASE_URL class attribute.")

    # ------------------------------------------------------------------
    # Query methods (to be used by children to implement the required methods, can be optionally overridden but should work for most children as-is)
    # ------------------------------------------------------------------

    def _fetch_JSON(self, url: str, params: dict = {}, timeout: int = 10) -> dict:
        """
        Make a GET request to a REST JSON endpoint and return the parsed response.

        Used by children that query standard REST APIs returning JSON. On network
        or HTTP error, prints a message and returns an empty dict so callers can
        handle it cleanly.

        Parameters
        ----------
        url : str
            Full URL of the endpoint.
        params : dict, optional
            URL query parameters.
        timeout : int, optional
            Request timeout in seconds. Default is 10.

        Returns
        -------
        dict
            Parsed JSON response, or ``{}`` on any error.
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

    def _fetch_XML(
        self, url: str, params: dict = {}, timeout: int = 10
    ) -> ET.Element | None:
        """
        Make a GET request and return the parsed XML root element.

        Used by children that consume XML responses. On error, prints a
        message and returns ``None`` so callers can check for it.

        Parameters
        ----------
        url : str
            Full URL of the endpoint.
        params : dict, optional
            URL query parameters.
        timeout : int, optional
            Request timeout in seconds. Default is 10.

        Returns
        -------
        xml.etree.ElementTree.Element or None
            Parsed root element of the XML response, or ``None`` on any error.
        """
        try:
            resp = requests.get(
                url, params=params, headers=self.HEADERS, timeout=timeout
            )
            resp.raise_for_status()

            return self._parse_xml(resp.text)
        except requests.RequestException as e:
            print(f"{type(self).__name__} fetch error [{url}]: {e}")
            return None

    def _parse_xml(self, xml_text: str) -> ET.Element | None:
        """
        Safely parse an XML string and return the root element.

        Parameters
        ----------
        xml_text : str
            Raw XML response text.

        Returns
        -------
        xml.etree.ElementTree.Element or None
            The parsed root element, or ``None`` if parsing fails.
        """
        try:
            return ET.fromstring(xml_text)
        except ET.ParseError:
            print(f"{type(self).__name__} error parsing XML.")
            return None

    # ------------------------------------------------------------------
    # Helper methods (to be used by children in their implementations of the required methods,can be optionally overridden but should work for most children as-is)
    # ------------------------------------------------------------------

    def _is_infraspecific(self, string: str) -> bool:
        """
        Return True if *string* contains an infraspecific rank abbreviation.

        Uses a compiled regular expression to detect rank markers such as
        ``var.``, ``subsp.``, ``f.``, etc.

        Parameters
        ----------
        string : str
            A scientific name string to inspect.

        Returns
        -------
        bool
            True when an infraspecific rank marker is found, False otherwise.
        """
        _INFRASPECIFIC_RE: re.Pattern = re.compile(
            r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|subf\.|cv\.|sect\.|subsect\.|ser\.|subgen\.|subg\.)",
            re.IGNORECASE,
        )
        return bool(_INFRASPECIFIC_RE.search(string))

    def _extract_publication_year(self, string: str) -> str:
        """
        Extract a four-digit publication year from a scientific name string.

        Parameters
        ----------
        string : str
            A scientific name or authorship string that may contain a year.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if not found.
        """
        return "Not yet implemented"

    def _extract_author(self, string: str) -> str:
        """
        Extract the authorship string from a string.

        Parameters
        ----------
        string : str
            A string that may contain an authorship component, such as a scientific name or a full citation.

        Returns
        -------
        str
            The authorship string (e.g. ``"(L.) Lam."``), or ``""`` if not found.
        """
        return "Not yet implemented"

    def _extract_original_author(self, string: str) -> str:
        """
        Extract the original authorship string from a scientific name.

        The original author is the taxonomist who first formally described the
        taxon, typically shown in parentheses when the name has been subsequently
        combined (e.g. the ``"L."`` in ``"(L.) Lam."``).

        Parameters
        ----------
        string : str
            A scientific name string that may include a basionym authorship
            component.

        Returns
        -------
        str
            The original authorship string, or ``""`` if not found.
        """
        return "Not yet implemented"

    def _extract_publication_name(self, string: str) -> str:
        """
        Extract a publication name from a string.

        Parameters
        ----------
        string : str
            A string that may contain a publication name, such as a full citation or the "published in" field from an API response.

        Returns
        -------
        str
            The publication name string, or ``""`` if not found.
        """
        return "Not yet implemented"

    def _is_empty(self, input):
        """
        Return True if the input is blank, empty, or None.

        Parameters
        ----------
        input : list, str, dict, xml.etree.ElementTree.Element, or None
            The value to test for emptiness.

        Returns
        -------
        bool
            True if *input* is ``None``, ``""``, ``[]``, ``{}``, or an
            ``ET.Element`` with no children; False otherwise.
        """
        if input == {}:
            return True
        elif input == []:
            return True
        elif input == "":
            return True
        elif input is None:
            return True
        elif isinstance(input, ET.Element) and len(input) == 0:
            return True
        else:
            return False

    def _format_synonym(
        self,
        name: str,
        author: str = "U",
        publication_year: str = "U",
        publication_name: str = "U",
        api_link: str = "U",
    ) -> dict:
        """
        Construct a pipeline-standard synonym record.

        Parameters
        ----------
        name : str
            The scientific name.
        author : str, optional
            Authorship string (e.g. ``"(L.) Lam."``).
        publication_year : str, optional
            Publication year as a string (e.g. ``"1783"``).
        publication_name : str, optional
            Full publication citation string.
        api_link : str, optional
            Direct URL to the taxon record in the source database.

        Returns
        -------
        dict
            A record with keys ``name``, ``author``, ``publication_year``,
            ``publication_name``, and ``api_link``.
        """
        return {
            "name": name,
            "author": author,
            "publication_year": publication_year,
            "publication_name": publication_name,
            "api_link": api_link,
        }

    # def _deduplicate_synonyms(
    #     self,
    #     candidates: list[dict],
    #     seed: set[str] | None = None,
    # ) -> list[dict]:
    #     """
    #     Return *candidates* with duplicates removed, keyed by ``name``.

    #     Comparison is case-insensitive. The optional *seed* set pre-populates
    #     the seen names (e.g. ``{query_name.lower()}`` so the query itself is
    #     never repeated in the output).

    #     Args:
    #         candidates (list[dict]): Synonym records, each with a
    #             ``"name"`` key.
    #         seed (set[str] | None): Lower-cased names to treat as already seen.
    #             Defaults to an empty set.

    #     Returns:
    #         list[dict]: Deduplicated list preserving input order.
    #     """
    #     seen = set(seed) if seed else set()
    #     result = []
    #     for item in candidates:
    #         name = item.get("name", "").lower()
    #         if name and name not in seen:
    #             seen.add(name)
    #             result.append(item)
    #     return result

    # ------------------------------------------------------------------
    # ID methods (not required, but one or the other is likely needed for most children)
    # ------------------------------------------------------------------

    def _extract_internal_id(self, raw_data) -> str:
        """
        Resolve raw API response data to the source's internal database identifier.

        Parameters
        ----------
        raw_data : any
            The raw response data returned by the source API (type varies by
            subclass).

        Returns
        -------
        str
            The internal database identifier for the queried taxon.

        Raises
        ------
        NotImplementedError
            When the child class has not provided an implementation for this step.
        LookupError
            When the name cannot be resolved to an identifier.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _extract_internal_id()."
        )

    def _extract_internal_accepted_id(self, raw_data):
        """
        Extract the internal identifier of the accepted taxon from API response data.

        An *accepted* taxon is the currently valid name that a synonym refers to.
        For some APIs the full synonym list is only accessible via the accepted
        name's record, so this method is needed when the initial search result
        may itself be a synonym.

        Parameters
        ----------
        raw_data : any
            Parsed API response data (type varies by subclass — e.g., ``dict``
            for GBIF, ``list`` for COL).

        Returns
        -------
        any
            The accepted taxon's internal identifier (type varies by subclass).

        Raises
        ------
        NotImplementedError
            When the child class has not provided an implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _get_accepted_id()."
        )

    # ------------------------------------------------------------------
    # Required methods (must be implemented by all children)
    # ------------------------------------------------------------------

    @abstractmethod
    def _fetch_query_data(self, name: str):
        """
        Query the source for the given species name and return the raw response.

        Implementations should call ``_fetch_JSON`` for REST APIs returning JSON,
        or ``_fetch_text`` for XML or HTML endpoints, and perform any initial
        parsing needed to produce a usable data structure.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        Raw query data in the source's native format (type varies by
            subclass — commonly a ``list`` or ``dict`` or ``xml.etree.ElementTree.Element``).
        """
        pass

    @abstractmethod
    def _fetch_synonym_data(self, raw_data: dict | ET.Element):
        """
        Retrieve synonym data from the source, re-querying if necessary.

        If the initial response from ``_fetch_query_data`` does not include
        synonym records directly, this method extracts the accepted taxon's
        internal identifier and issues a second request to obtain its synonyms.

        Parameters
        ----------
        raw_data : dict or xml.etree.ElementTree.Element
            The parsed response returned by ``_fetch_query_data``.

        Returns
        -------
        any
            Raw synonym data in the source's native format (type varies by
            subclass — commonly a ``list`` or ``dict`` or ``xml.etree.ElementTree.Element``).
        """
        pass

    @abstractmethod
    def _compile_synonyms(self, synonym_data) -> list[dict]:
        """
        Convert raw synonym data into pipeline-standard synonym records.

        Parameters
        ----------
        synonym_data : any
            API-specific raw synonym data as returned by ``_fetch_synonym_data``
            (type varies by subclass).

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, each produced by
            ``_format_synonym``.
        """
        pass

    # ------------------------------------------------------------------
    # Public methods (used by external callers, can be overrriden by children if needed but should work for most children as-is)
    # ------------------------------------------------------------------

    def get_synonyms(self, name: str) -> list[dict]:
        """
        Retrieve taxonomic synonyms and publication metadata for a species name.

        Orchestrates the full pipeline: normalize the input, fetch raw query
        data, fetch synonym data, and compile results into the standard format.
        Returns an empty list at the first stage that yields no data.

        This is the only public method and the main entry point for callers.

        Parameters
        ----------
        name : str
            The species name search query (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        list of dict
            A list of synonym records (``dict``) or ``[]`` if, at any stage, no results are found.
        """
        name = normalize_scientific_name(name)

        raw_data = self._fetch_query_data(name)
        if self._is_empty(raw_data):
            return []
        assert raw_data is not None

        synonym_data = self._fetch_synonym_data(raw_data)
        if self._is_empty(synonym_data):
            return []
        assert synonym_data is not None

        synonyms = self._compile_synonyms(synonym_data)
        if self._is_empty(synonyms):
            return []
        assert synonyms is not None

        return synonyms
