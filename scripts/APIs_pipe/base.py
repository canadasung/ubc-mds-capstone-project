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

    def _fetch(
        self, url: str, params: dict = {}, timeout: int = 10
    ) -> requests.Response | None:
        """
        Make a GET request to the specified URL with error handling.

        Parameters
        ----------
        url : str
            The full URL to send the GET request to.
        params : dict, optional
            Query parameters to include in the request. Default is an empty dict.
        timeout : int, optional
            Request timeout in seconds. Default is 10.

        Returns
        -------
        requests.Response or None
            The response object if the request is successful; None if an error occurs.
        """
        try:
            response = requests.get(
                url, params=params, headers=self.HEADERS, timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"{type(self).__name__} fetch error [{url}]: {e}")
            return None

    def _fetch_JSON(self, url: str, params: dict = {}, timeout: int = 10) -> dict:
        """
        Make a GET request to a REST JSON endpoint and return the parsed response.

        Used by children that query standard REST APIs returning JSON. On network
        or HTTP error, prints a message and returns an empty dict.

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

        response = self._fetch(url, params=params, timeout=timeout)
        return response.json() if response is not None else {}

    def _fetch_XML(self, url: str, params: dict = {}, timeout: int = 10) -> ET.Element:
        """
        Make a GET request and return the parsed XML root element.

        Used by children that consume XML responses. On network, HTTP, or
        parse error, prints a message and returns an empty ``ET.Element``.

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
        xml.etree.ElementTree.Element
            Parsed root element of the XML response, or an empty element
            on any error.
        """
        response = self._fetch(url, params=params, timeout=timeout)
        if response is not None:
            try:
                return ET.fromstring(response.text)
            except ET.ParseError:
                print(f"{type(self).__name__} error parsing XML.")
        return ET.Element(
            "empty"
        )  # tag name chosen to avoid confusion with valid root tags in responses, will be treated as empty by _is_empty()

    def _fetch_HTML(self, url: str, params: dict = {}, timeout: int = 10) -> str:
        """
        Make a GET request and return the raw HTML response text.

        Used by children that scrape HTML pages. On network or HTTP error,
        prints a message and returns an empty string.

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
        str
            Raw HTML text of the response, or ``""`` on any error.
        """
        response = self._fetch(url, params=params, timeout=timeout)
        return response.text if response is not None else ""

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
            # TODO: put this in a config, rather than having it inside this file so a user could add if needed
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

    # def _extract_publication_name(self, string: str) -> str:
    #     """
    #     Extract a publication name from a string.

    #     Parameters
    #     ----------
    #     string : str
    #         A string that may contain a publication name, such as a full citation or the "published in" field from an API response.

    #     Returns
    #     -------
    #     str
    #         The publication name string, or ``""`` if not found.
    #     """
    #     return "Not yet implemented"

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

    def _format_row(
        self,
        name: str,
        author: str | None = "U",
        publication_year: str | None = "U",
        publication_name: str | None = "U",
        api_link: str | None = "U",
    ) -> dict:
        """
        Construct a pipeline-standard row record.

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
        # TODO: check for None and throw an exception if needed
        # Add clean input function so that user really cannot put in "U" (or whatever the signifier is)
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

    # add type hinting for raw_data
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

    def _extract_internal_accepted_id(self, raw_data) -> str:
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
        # update print statement
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
    def _fetch_synonym_data(self, raw_data: dict | ET.Element | str):
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
    def _fetch_synonym_search_term_data(
        self,
        raw_data: dict | ET.Element | str,
        synonym_data: list | dict | ET.Element | str,
    ):
        """
        Retrieve search term data from the source, re-querying if necessary.

        The search term is the taxon name/ID that was used in the synonym search. For APIs that search synonyms based off of the initial query (and likely do not have synonym/accepted flagging in their data), this will be the original query's data. For APIs that must resolve to the accepted name to access synonyms, this will be the accepted name's data. Essentially, this is whichever data the the synonym search did not capture.

        If neither raw_data nor synonym_data include the search term records directly, this method issues a second request to obtain its metadata.

        Parameters
        ----------
        raw_data : dict or xml.etree.ElementTree.Element
            The parsed response returned by ``_fetch_query_data``.

        Returns
        -------
        any
            Raw search term data in the source's native format (type varies by
            subclass — commonly a ``list`` or ``dict`` or ``xml.etree.ElementTree.Element``).
        """
        pass

    @abstractmethod
    def _compile_synonyms(
        self, synonym_data: list | dict | ET.Element | str
    ) -> list[dict]:
        """
        Convert raw synonym data into pipeline-standard synonym records.

        Parameters
        ----------
        synonym_data : any
            API-specific raw synonym data as returned by ``_fetch_synonym_data``
            (type varies by subclass).
        current_key : str, optional
            The accepted taxon's internal key. Used by subclasses that receive
            both accepted and synonym records in the same data structure (e.g.
            Index Fungorum) to exclude the accepted record from synonym output.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, each produced by
            ``_format_synonym``.
        """
        pass

    @abstractmethod
    def _compile_synonym_search_term(
        self, synonym_search_term_data: list | dict | ET.Element | str
    ) -> list[dict]:
        """
        Convert raw synonym search term data into a pipeline-standard record for the search term.

        Parameters
        ----------
        search_term_data : any
            The raw synonymsearch term data returned by ``_fetch_synonym_search_term_data``
            (type varies by subclass).
        current_key : str, optional
            The accepted taxon's internal key. Used by subclasses that receive
            both accepted and synonym records in the same data structure (e.g.
            Index Fungorum) to exclude the synonym records from accepted output.

        Returns
        -------
        list of dict
            A one-item list containing the synonymsearch term record, or ``[]`` if
            the synonym search term name cannot be determined from ``synonym_search_term_data``.
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
        assert raw_data is not None  # make this an exception with error message

        synonym_data = self._fetch_synonym_data(raw_data)
        assert (
            synonym_data is not None
        )  # ensure that synonym_data is not None for the next step. Note that synonym data should never be None unless there is a bug in the child class's _fetch_synonym_data implementation, since even an empty result should be represented as an empty list/dict/ET.Element rather than None.

        # `synonym_search_term_data` is the data for the search term of `_fetch_synonym_data`, either the accepted ID or the original query ID, depending on the API. For APIs that must resolve to the accepted name to access synonyms, this will be the accepted ID, but for those that do not need to resolve, this will be the original query ID. While some APIs may include the search term's data in the synonym search response, others may not, so this step ensures that we have the search term's data regardless of the API's structure.
        synonym_search_term_data = self._fetch_synonym_search_term_data(
            raw_data, synonym_data
        )
        assert (
            synonym_search_term_data is not None
        )  # ensure that synonym_search_term_data is not None for the next step. Note that synonym_search_term_data should never be None unless there is a bug in the child class's _fetch_synonym_search_term_data implementation, since even an empty result should be represented as an empty list/dict/ET.Element rather than None.

        search_term = []
        synonyms = []

        # Compile search term and synonym records only if their respective raw data is not empty.
        if not self._is_empty(synonym_data):
            synonyms = self._compile_synonyms(synonym_data)
        if not self._is_empty(synonym_search_term_data):
            search_term = self._compile_synonym_search_term(synonym_search_term_data)

        return search_term + synonyms
