"""
FishBase HTML scraping client.

FishBase (fishbase.se) is the world's largest online information system for
fish species, covering taxonomy, biology, ecology, and distribution.  It does
not expose a public REST/JSON API, so this client scrapes two HTML pages per
query:

1. ``/summary/{Genus}-{Species}`` — FishBase redirects any name (accepted or
   synonym) to the accepted species page, providing the ``SpecCode`` and
   accepted name via embedded metadata; no separate synonym-resolution request
   is needed.
2. ``/nomenclature/{SpecCode}`` — lists all names (accepted and synonyms) as
   anchor tags whose query-string parameters contain all fields needed:
   ``GenusName``, ``SpeciesName``, ``Author``, ``Status``, ``Misspelling``,
   ``SpecCode``.

Subspecific names (``SpeciesName`` containing a space) and misspellings
(``Misspelling=1``) are excluded during compilation.

FishBase does not provide taxonomy and returns both accepted and synonym results in the nomenclature web scrape. As such, all results are fetched and compiled using the synonym flow (``_fetch_synonym_data`` and ``_compile_synonyms``), and the accepted flow (``_fetch_accepted_data`` and ``_compile_accepted``), which would normally handle the accepted name information and the taxonomy information, returns blank. The status flag is applied dynamically using the ``Status`` field.

Documentation
-------------
FishBase does not publish API documentation.  The scraping targets are
https://www.fishbase.se/summary/{Genus}-{Species} and
https://www.fishbase.se/nomenclature/{SpecCode}.

Fields implemented
------------------
- author: both rows
- publication_year: both rows
- status: both rows
- api_link: both rows
"""

import re
from urllib.parse import unquote_plus

from scripts.config import FISHBASE_PORTAL

from .base import SpeciesAPI


class FishBaseAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for FishBase via HTML scraping.
    """

    BASE_URL = FISHBASE_PORTAL.base_url

    # Extracts SpecCode from language-selector links: SpeciesSummary.php?id=69&lang=...
    _SPEC_CODE_RE = re.compile(r"SpeciesSummary\.php\?id=(\d+)", re.IGNORECASE)

    # Extracts accepted genus and species from the og:url meta tag:
    # content="https://www.fishbase.us/summary/Gadus-morhua.html"
    _OG_URL_RE = re.compile(r"/summary/([A-Za-z]+)-([A-Za-z]+)\.html")

    # Matches every SynonymSummary.php href and captures its raw query string.
    # Must allow spaces — FishBase encodes values like "accepted name" without %20.
    _SYN_LINK_RE = re.compile(r"SynonymSummary\.php\?([^\"'<>]+)")

    # Strips the trailing ", YYYY" year from a FishBase author string.
    _YEAR_SUFFIX_RE = re.compile(r",\s*(\d{4})$")

    def _fetch_query_data(self, name: str) -> str:
        """
        Fetch the summary page HTML for *name* from ``/summary/{Genus}-{Species}``.

        FishBase serves the accepted species page for both accepted names and
        synonyms, so no separate synonym-resolution request is needed.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Gadus morhua"``).

        Returns
        -------
        str
            Raw HTML of the summary page, or ``""`` if the name is malformed
            or the request fails.
        """
        parts = name.split()
        if len(parts) < 2:
            # TODO: add error
            return ""
        genus, species = parts[0], parts[1]
        return self._fetch_HTML(f"{self.BASE_URL}/summary/{genus}-{species}")

    def _extract_accepted_name(
        self, html: str, fallback_genus: str = "", fallback_species: str = ""
    ) -> tuple[str, str]:
        """
        Extract the accepted genus and species from the ``og:url`` meta tag in summary HTML.

        Falls back to the provided genus/species if the tag is absent.

        Parameters
        ----------
        html : str
            Raw HTML of the summary page.
        fallback_genus : str, optional
            Genus to return if the ``og:url`` pattern is not found.
        fallback_species : str, optional
            Species to return if the ``og:url`` pattern is not found.

        Returns
        -------
        tuple[str, str]
            ``(genus, species)`` of the accepted name.
        """
        m = self._OG_URL_RE.search(html)
        if m:
            return m.group(1), m.group(2)
        return fallback_genus, fallback_species

    def _extract_internal_id(self, raw_data: str | dict) -> str:
        """
        Extract the FishBase SpecCode from summary page HTML or a params dict.

        When *raw_data* is a ``dict`` (e.g. a parsed synonym URL params dict),
        reads the ``"SpecCode"`` key directly.  When it is a ``str``, applies
        ``_SPEC_CODE_RE`` against language-selector link hrefs in the HTML.

        Parameters
        ----------
        raw_data : str or dict
            Either raw HTML of the summary page (from ``_fetch_query_data``) or
            a URL-decoded synonym params dict (from ``_extract_synonym_params``).

        Returns
        -------
        str
            The SpecCode digits, or ``""`` if not found.
        """
        if isinstance(raw_data, dict):
            return raw_data.get("SpecCode", "")
        m = self._SPEC_CODE_RE.search(raw_data)
        return m.group(1) if m else ""

    def _extract_author(self, string: str) -> str:
        """
        Normalise a FishBase author string.

        Parameters
        ----------
        string : str
            Raw author string from a synonym link's ``Author`` parameter.

        Returns
        -------
        str
            ``""`` when *string* is ``"not given"`` (case-insensitive);
            otherwise *string* unchanged.
        """
        if string.strip().lower() == "not given":
            return ""
        return string

    def _fetch_synonym_data(self, raw_data: str) -> str:
        """
        Fetch the nomenclature page HTML for the SpecCode found in *raw_data*.

        Extracts the SpecCode from the summary HTML, then fetches
        ``/nomenclature/{SpecCode}``.

        Parameters
        ----------
        raw_data : str
            Raw HTML of the summary page as returned by ``_fetch_query_data``.

        Returns
        -------
        str
            Raw HTML of the ``/nomenclature/{SpecCode}`` page, or ``""`` if
            no SpecCode is found or the request fails.
        """
        spec_code = self._extract_internal_id(raw_data)
        if not spec_code:
            return ""
        return self._fetch_HTML(f"{self.BASE_URL}/nomenclature/{spec_code}")

    def _fetch_accepted_data(self, _raw_data: str, _synonym_data: str) -> dict:
        """
        Return ``{}`` — not used for FishBase.

        The accepted name is included in the nomenclature HTML and compiled
        directly by ``_compile_synonyms``.

        Parameters
        ----------
        _raw_data : str
            Unused.
        _synonym_data : str
            Unused.

        Returns
        -------
        dict
            Always ``{}``.
        """
        return {}

    def _compile_accepted(self, _accepted_data: dict) -> list[dict]:
        """
        Return ``[]`` — not used for FishBase.

        The accepted name is compiled by ``_compile_synonyms`` alongside all
        synonym records.

        Parameters
        ----------
        _accepted_data : dict
            Unused (always ``{}``).

        Returns
        -------
        list of dict
            Always ``[]``.
        """
        return []

    def _extract_publication_year(self, string: str) -> str:
        """
        Extract the four-digit year from a FishBase author string.

        FishBase encodes author and year together (e.g. ``"Linnaeus, 1758"``).
        Applies ``_YEAR_SUFFIX_RE`` to capture the trailing year.

        Parameters
        ----------
        string : str
            Raw author string from a synonym link's ``Author`` parameter.

        Returns
        -------
        str
            Four-digit year, or ``""`` if not found.
        """
        m = self._YEAR_SUFFIX_RE.search(string)
        return m.group(1) if m else ""

    def _extract_synonym_params(self, html: str) -> list[dict]:
        """
        Parse URL-decoded parameter dicts from every ``SynonymSummary.php`` link in HTML.

        Applies ``_SYN_LINK_RE`` and URL-decodes each query string.

        Parameters
        ----------
        html : str
            Raw HTML of the ``/nomenclature/{SpecCode}`` page.

        Returns
        -------
        list of dict
            One URL-decoded parameter dict per synonym anchor found.
        """
        params_list = []
        for m in self._SYN_LINK_RE.finditer(html):
            params = {}
            for part in m.group(1).split("&"):
                if "=" in part:
                    key, _, val = part.partition("=")
                    params[key] = unquote_plus(val)
            params_list.append(params)
        return params_list

    def _compile_synonyms(self, synonym_data: str) -> list[dict]:
        """
        Convert nomenclature page HTML into pipeline-standard synonym records.

        Includes the accepted name alongside synonyms.  Excludes misspellings
        (``Misspelling=1``) and subspecific names (``SpeciesName`` containing a
        space).  Deduplicates by canonical binomial name.

        Parameters
        ----------
        synonym_data : str
            Raw HTML of the ``/nomenclature/{SpecCode}`` page as returned by
            ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
        """
        candidates = []
        seen: set[str] = set()
        for params in self._extract_synonym_params(synonym_data):
            genus = params.get("GenusName", "").strip()
            species = params.get("SpeciesName", "").strip()
            if not genus or not species:
                continue
            if params.get("Misspelling", "0") == "1":
                continue
            name = f"{genus} {species}"
            if self._is_infraspecific(name) or name in seen:
                continue
            seen.add(name)
            author_raw = params.get("Author", "")
            spec_code = self._extract_internal_id(params)
            candidates.append(
                self._format_row(
                    **{
                        "api_name": FISHBASE_PORTAL.display_name,
                        "genus": genus,
                        "species": species,
                        "api_internal_id": spec_code,
                        "author": self._extract_author(author_raw),
                        "publication_year": self._extract_publication_year(author_raw),
                        "status": self._extract_status(params.get("Status", "")),
                        "api_link": f"{self.BASE_URL}/nomenclature/{spec_code}"
                        if spec_code
                        else "",  # TODO: note that the individual synonyms do have their own detail pages in fishbase, but with a different more complicated URL. This URL goes to a table showing all the synonyms for the accepted name
                    }
                )
            )
        return candidates
