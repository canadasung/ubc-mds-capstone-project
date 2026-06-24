"""
Abstract base class for biodiversity database API clients.

All external database connectors in ``apis_pipe`` subclass ``SpeciesAPI`` and
implement its three-phase pipeline contract.  The three phases are enforced by
naming convention:

- ``_fetch_*`` — network calls only; return raw responses without parsing.
- ``_extract_*`` — pure string extraction from already-fetched data; no I/O.
- ``_compile_*`` — row assembly; call helpers and read dict keys, no cleaning
  or network calls.

The single public entry point is ``get_synonyms(name)``, which orchestrates
all three phases and returns a schema-validated ``pd.DataFrame``.
"""

import inspect
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod

import pandas as pd
import requests

from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.schema import empty_synonym_table, make_synonym_row


class _Unset:
    """Sentinel for _format_row optional params that were not provided by the caller."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<NOT_PROVIDED>"


_UNSET = _Unset()


class SpeciesAPI(ABC):
    """
    Abstract base class establishing a unified contract for biodiversity database clients.

    Concrete subclasses must define a ``BASE_URL`` class attribute and implement
    the five abstract methods: ``_fetch_query_data``, ``_fetch_synonym_data``,
    ``_fetch_accepted_data``, ``_compile_synonyms``, and
    ``_compile_accepted``.  Optional helpers may be implemented and/or
    overridden to customise behavior for a specific source.

    Attributes
    ----------
    HEADERS : dict
        HTTP headers sent with every request.  Overrides the default
        ``requests`` User-Agent so that portals that reject bot agents respond
        normally.
    """

    HEADERS: dict = {"User-Agent": "Mozilla/5.0"}
    BASE_URL: str
    _INFRASPECIFIC_RE: re.Pattern = re.compile(
        r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|subf\.|cv\.|sect\.|subsect\.|ser\.|subgen\.|subg\.)",
        # TODO: put this in a config, rather than having it inside this file so a user could add if needed
        re.IGNORECASE,
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls) and not hasattr(cls, "BASE_URL"):
            raise TypeError(f"{cls.__name__} must define a BASE_URL class attribute.")

    # ------------------------------------------------------------------
    # Query methods (to be used by children to implement the required methods, can be optionally overridden but should work for most children as-is)
    # ------------------------------------------------------------------

    def _fetch(
        self, url: str, params: dict = {}, timeout: int = 10
    ) -> requests.Response:
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
        requests.Response
            The response object if the request is successful.

        Raises
        ------
        requests.RequestException
            If the request times out, the source is unreachable, or the
            response has a non-2xx HTTP status.
        """
        try:
            response = requests.get(
                url, params=params, headers=self.HEADERS, timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"{type(self).__name__} fetch error [{url}]: {e}")
            raise

    def _fetch_JSON(self, url: str, params: dict = {}, timeout: int = 10) -> dict:
        """
        Make a GET request to a REST JSON endpoint and return the parsed response.

        Used by children that query standard REST APIs returning JSON.

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
            Parsed JSON response.

        Raises
        ------
        requests.RequestException
            If the underlying request fails. See ``_fetch``.
        """

        response = self._fetch(url, params=params, timeout=timeout)
        return response.json()

    def _fetch_XML(self, url: str, params: dict = {}, timeout: int = 10) -> ET.Element:
        """
        Make a GET request and return the parsed XML root element.

        Used by children that consume XML responses. On a parse error of an
        otherwise successful response, prints a message and returns an empty
        ``ET.Element``.

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
            if the response body could not be parsed as XML.

        Raises
        ------
        requests.RequestException
            If the underlying request fails. See ``_fetch``.
        """
        response = self._fetch(url, params=params, timeout=timeout)
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

        Used by children that scrape HTML pages.

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
            Raw HTML text of the response.

        Raises
        ------
        requests.RequestException
            If the underlying request fails. See ``_fetch``.
        """
        response = self._fetch(url, params=params, timeout=timeout)
        return response.text

    # ------------------------------------------------------------------
    # Boolean checker methods (to be used by children in their implementations of the required methods,can be optionally overridden but should work for most children as-is)
    # ------------------------------------------------------------------

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

    def _is_infraspecific(self, string: str) -> bool:
        """
        Return True if *string* is an infraspecific scientific name.

        Two checks are applied:

        1. Rank-marker check — detects explicit infraspecific abbreviations
           such as ``var.``, ``subsp.``, ``f.``, etc. via ``_INFRASPECIFIC_RE``.
        2. Bare-trinomial check — any name with three or more whitespace-
           delimited tokens (e.g. ``"Gadus morhua morhua"``) is treated as
           infraspecific even without a rank marker.

        Parameters
        ----------
        string : str
            A scientific name string to inspect.

        Returns
        -------
        bool
            True when either check matches, False otherwise.
        """
        return bool(self._INFRASPECIFIC_RE.search(string)) or len(string.split()) >= 3

    # ------------------------------------------------------------------
    # Extraction helper methods (to be overriden by children in their implementations of the required methods)
    # ------------------------------------------------------------------

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

        Raises
        ------
        NotImplementedError
            When the child class has not provided an implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _extract_publication_year()."
        )

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

        Raises
        ------
        NotImplementedError
            When the child class has not provided an implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _extract_author()."
        )

    def _extract_publication_name(self, string: str) -> str:
        """
        Extract a publication name from a string.

        Parameters
        ----------
        string : str
            A string that may contain the title of the original publication of a species name, such as a citation of a journal or book.

        Returns
        -------
        str
            The publication name string, or ``""`` if not found.

        Raises
        ------
        NotImplementedError
            When the child class has not provided an implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _extract_publication_name()."
        )

    def _extract_status(self, string: str) -> str:
        """
        Map a raw status string to the schema's ``"Accepted"`` or ``"Synonym"``
        values by checking for those substrings.

        Parameters
        ----------
        string : str
            A raw status string from an API response, e.g. ``"accepted"``,
            ``"accepted name"``, ``"ambiguous synonym"``.

        Returns
        -------
        str
            ``"Accepted"``, ``"Synonym"``, or ``""`` if neither substring is found.
        """
        lower = string.lower()
        if "accepted" in lower:
            return "Accepted"
        if "synonym" in lower:
            return "Synonym"
        return ""

    def _extract_taxonomy(self, data: dict | list | str | ET.Element) -> dict[str, str]:
        """
        Extract taxonomy fields from a raw API response.

        Implementations should return a dict with any subset of the following
        keys, using ``class_`` (not ``class``) for the class rank to avoid the
        Python keyword conflict::

            {
                "kingdom":  str,
                "phylum":   str,
                "class_":   str,
                "order":    str,
                "family":   str,
                "subfamily": str,
            }

        Ranks not implemented should be omitted from the dict rather than included as
        empty strings; ``_format_row`` treats absent keys as ``UNAVAILABLE``.
        The dict is typically unpacked with ``**taxonomy`` directly into a
        ``_format_row`` call.

        Parameters
        ----------
        data : any
            Raw API response data in the source's native format (varies by
            subclass — e.g. a ``dict``, ``list``, or
            ``xml.etree.ElementTree.Element``).

        Returns
        -------
        dict[str, str]
            Taxonomy field dict with string values for each rank present.

        Raises
        ------
        NotImplementedError
            When the child class has not provided an implementation.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement _extract_taxonomy()."
        )

    def _extract_genus_species(self, name: str) -> tuple[str, str]:
        """
        Parse a scientific name string into its genus and species components.

        Parameters
        ----------
        name : str
            A scientific name string whose first two whitespace-delimited
            tokens are the genus and species epithet (e.g.
            ``"Amanita muscaria"`` or ``"Amanita muscaria var. flavivolvata"``).

        Returns
        -------
        tuple[str, str]
            ``(genus, species)`` extracted from the first two tokens of *name*.

        Raises
        ------
        ValueError
            If *name* contains fewer than two whitespace-delimited tokens.
        """
        parts = name.split()
        if len(parts) < 2:
            raise ValueError(
                f"Expected at least two tokens in scientific name, got {name!r}"
            )
        return parts[0], parts[1]

    def _format_row(
        self,
        api_name: str,
        genus: str,
        species: str,
        api_internal_id: str,
        kingdom: str = _UNSET,  # type: ignore[assignment]
        phylum: str = _UNSET,  # type: ignore[assignment]
        class_: str = _UNSET,  # type: ignore[assignment]
        order: str = _UNSET,  # type: ignore[assignment]
        family: str = _UNSET,  # type: ignore[assignment]
        subfamily: str = _UNSET,  # type: ignore[assignment]
        author: str = _UNSET,  # type: ignore[assignment]
        publication_name: str = _UNSET,  # type: ignore[assignment]
        publication_year: str = _UNSET,  # type: ignore[assignment]
        status: str = _UNSET,  # type: ignore[assignment]
        original_source: str = _UNSET,  # type: ignore[assignment]
        api_link: str = _UNSET,  # type: ignore[assignment]
    ) -> dict:
        """
        Construct a validated pipeline-standard row record.

        Parameters
        ----------
        api_name : str
            The name of the API source (e.g. ``"GBIF"``). Must be one of the
            recognised values in ``schema._API_NAMES``.
        genus : str
            Taxonomic genus (single word, no whitespace).
        species : str
            Taxonomic species epithet (single word, no whitespace).
        api_internal_id : str
            Unique identifier for this record in the source database.
        kingdom, phylum, class_, family, subfamily : str, optional
            Taxonomic rank values. Each must be a single word. Use ``class_``
            for the class rank (``"class"`` is a Python keyword).
        author : str, optional
            Authorship string (e.g. ``"(L.) Lam."``).
        publication_name : str, optional
            Full publication citation string.
        publication_year : str, optional
            Four-digit publication year (e.g. ``"1783"``).
        status : str, optional
            Taxonomic status — ``"Accepted"``, ``"Synonym"``, or omit to
            leave as ``UNAVAILABLE``.
        original_source : str, optional
            Name of the original data source cited by the API.
        api_link : str, optional
            Direct URL to the taxon record in the source database.

        Returns
        -------
        dict
            A fully validated schema row with all columns from
            ``SYNONYM_COLUMNS``.
        """
        optional = {
            "kingdom": kingdom,
            "phylum": phylum,
            "class": class_,
            "order": order,
            "family": family,
            "subfamily": subfamily,
            "author": author,
            "publication_name": publication_name,
            "publication_year": publication_year,
            "status": status,
            "original_source": original_source,
            "api_link": api_link,
        }
        provided = {k: v for k, v in optional.items() if not isinstance(v, _Unset)}
        return make_synonym_row(
            api_name=api_name,
            genus=genus,
            species=species,
            api_internal_id=api_internal_id,
            **provided,
        )

    # ------------------------------------------------------------------
    # ID methods (not required, but one or the other is likely needed for most children)
    # ------------------------------------------------------------------

    def _extract_internal_id(self, raw_data: dict | list | str | ET.Element) -> str:
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

    def _extract_internal_accepted_id(
        self, raw_data: dict | list | str | ET.Element
    ) -> str:
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
            f"{type(self).__name__} does not implement _extract_internal_accepted_id()."
        )

    # ------------------------------------------------------------------
    # Required methods (must be implemented by all children)
    # ------------------------------------------------------------------

    @abstractmethod
    def _fetch_query_data(self, name: str) -> dict | list | str | ET.Element:
        """
        Query the source for *name* and return the raw response.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict or list or str or xml.etree.ElementTree.Element
            Raw query data in the source's native format (varies by subclass).
        """
        pass

    @abstractmethod
    def _fetch_synonym_data(
        self, raw_data: dict | list | ET.Element | str
    ) -> dict | list | str | ET.Element:
        """
        Fetch synonym records for the taxon resolved from *raw_data*.

        For sources that list synonyms under an accepted-name endpoint, this
        method extracts the accepted taxon's internal identifier from
        *raw_data* and issues a second request.

        Parameters
        ----------
        raw_data : dict or list or str or xml.etree.ElementTree.Element
            The response returned by ``_fetch_query_data``.

        Returns
        -------
        dict or list or str or xml.etree.ElementTree.Element
            Raw synonym data in the source's native format (varies by subclass).
        """
        pass

    @abstractmethod
    def _fetch_accepted_data(
        self,
        raw_data: dict | list | str | ET.Element,
        synonym_data: dict | list | str | ET.Element,
    ) -> dict | list | str | ET.Element:
        """
        Fetch metadata for the accepted name.

        Parameters
        ----------
        raw_data : dict or list or str or xml.etree.ElementTree.Element
            The response returned by ``_fetch_query_data``.
        synonym_data : dict or list or str or xml.etree.ElementTree.Element
            The response returned by ``_fetch_synonym_data``.

        Returns
        -------
        dict or list or str or xml.etree.ElementTree.Element
            Raw search term data in the source's native format (varies by subclass).
        """
        pass

    @abstractmethod
    def _compile_synonyms(
        self, synonym_data: dict | list | str | ET.Element
    ) -> list[dict]:
        """
        Convert raw synonym data into pipeline-standard synonym records.

        Parameters
        ----------
        synonym_data : dict or list or str or xml.etree.ElementTree.Element
            Raw synonym data as returned by ``_fetch_synonym_data``
            (type varies by subclass).

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, each produced by ``_format_row``.
        """
        pass

    @abstractmethod
    def _compile_accepted(
        self, accepted_data: dict | list | str | ET.Element
    ) -> list[dict]:
        """
        Convert raw search term data into a one-item pipeline-standard record.

        Parameters
        ----------
        accepted_data : dict or list or str or xml.etree.ElementTree.Element
            Raw accepted as returned by
            ``_fetch_accepted_data`` (type varies by subclass).

        Returns
        -------
        list of dict
            A one-item list with the search term record, or ``[]`` if the name
            cannot be determined from ``accepted_data``.
        """
        pass

    # ------------------------------------------------------------------
    # Public methods (used by external callers, can be overrriden by children if needed but should work for most children as-is)
    # ------------------------------------------------------------------

    def get_synonyms(self, name: str) -> pd.DataFrame:
        """
        Retrieve taxonomic synonyms and publication metadata for a species name.

        Orchestrates the full pipeline: normalize the input, fetch raw query
        data, fetch synonym data, fetch accepted data (including taxonomy), and compile results into the standard format.

        This is the only public method and the main entry point for callers.

        Parameters
        ----------
        name : str
            The species name search query (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        pd.DataFrame
            A DataFrame of accepted and synonym records in schema format, or an empty
            schema-format DataFrame if no results are found.
        """
        name = normalize_query_string(name)

        raw_data = self._fetch_query_data(name)
        if self._is_empty(raw_data):
            return empty_synonym_table()
        print("_fetch_query_data")
        print(raw_data)

        synonym_data = self._fetch_synonym_data(raw_data)
        print("_fetch_synonym_data")
        if isinstance(synonym_data, ET.Element):
            print(ET.tostring(synonym_data, encoding="unicode"))
        else:
            print(synonym_data)

        accepted_data = self._fetch_accepted_data(raw_data, synonym_data)
        print("_fetch_accepted_data")
        if isinstance(accepted_data, ET.Element):
            print(ET.tostring(accepted_data, encoding="unicode"))
        else:
            print(accepted_data)

        accepted = []
        synonyms = []

        # Compile accepted and synonym records only if their respective raw data is not empty.
        if not self._is_empty(synonym_data):
            synonyms = self._compile_synonyms(synonym_data)
        if not self._is_empty(accepted_data):
            accepted = self._compile_accepted(accepted_data)

        rows = accepted + synonyms
        if not rows:
            return empty_synonym_table()
        return pd.DataFrame(rows)
