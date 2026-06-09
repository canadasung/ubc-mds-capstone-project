"""
FishBase HTML scraping client.

SpeciesAPI implementation for FishBase (fishbase.se), the world's largest
online information system on fishes.

FishBase does not expose a public REST/JSON API. This client scrapes two
HTML pages per query:
  1. /summary/{Genus}-{Species} — resolves any name (accepted or synonym) to
     the accepted species and its internal SpecCode. FishBase serves the
     accepted species page regardless of whether the queried name is the
     accepted name or a synonym, so no separate synonym-resolution step is
     needed.
  2. /nomenclature/{SpecCode} — lists all names (accepted and synonyms) as
     HTML anchor tags whose href query parameters contain every field we need:
     GenusName, SpeciesName, Author, Status, Misspelling, SpecCode.

Subspecific names (SpeciesName containing a space) and misspellings
(Misspelling=1) are excluded during compilation.
"""

import re
from urllib.parse import unquote_plus

import requests

from .base import SpeciesAPI
from .config import FISHBASE_PORTAL


class FishBaseAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for FishBase.
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

    def _fetch_query_data(self, name: str) -> dict:
        """
        Resolve *name* to its accepted species and SpecCode via the summary page.

        Fetches ``/summary/{Genus}-{Species}``. FishBase automatically serves
        the accepted species page for both accepted names and synonyms, so no
        separate synonym-resolution request is needed.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Gadus morhua"``).

        Returns
        -------
        dict
            Keys ``"spec_code"``, ``"accepted_genus"``, ``"accepted_species"``,
            or ``{}`` if the name is not found.
        """
        parts = name.split()
        if len(parts) < 2:
            return {}
        genus, species = parts[0], parts[1]
        try:
            resp = requests.get(
                f"{self.BASE_URL}/summary/{genus}-{species}",
                headers=self.HEADERS,
                timeout=10,
            )
        except requests.RequestException as e:
            print(f"FishBaseAPI fetch error [{self.BASE_URL}/summary/]: {e}")
            return {}
        if not resp.ok or not resp.text:
            return {}

        spec_match = self._SPEC_CODE_RE.search(resp.text)
        if not spec_match:
            return {}
        spec_code = spec_match.group(1)

        og_match = self._OG_URL_RE.search(resp.text)
        if og_match:
            accepted_genus = og_match.group(1)
            accepted_species = og_match.group(2)
        else:
            accepted_genus, accepted_species = genus, species

        return {
            "spec_code": spec_code,
            "accepted_genus": accepted_genus,
            "accepted_species": accepted_species,
        }

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Return the SpecCode from the query result dict.

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The FishBase SpecCode, or ``""`` if absent.
        """
        return raw_data.get("spec_code", "")

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Scrape synonym parameter dicts from the ``/nomenclature/{SpecCode}`` page.

        Each synonym anchor tag encodes all required fields in its href query
        string (GenusName, SpeciesName, Author, Status, Misspelling, SpecCode).

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            One dict per synonym anchor, with URL-decoded parameter values.
            Returns ``[]`` on error or if the page has no synonym links.
        """
        spec_code = self._extract_internal_id(raw_data)
        if not spec_code:
            return []
        try:
            resp = requests.get(
                f"{self.BASE_URL}/nomenclature/{spec_code}",
                headers=self.HEADERS,
                timeout=10,
            )
        except requests.RequestException as e:
            print(f"FishBaseAPI fetch error [{self.BASE_URL}/nomenclature/]: {e}")
            return []
        if not resp.ok or not resp.text:
            return []

        synonyms = []
        for m in self._SYN_LINK_RE.finditer(resp.text):
            params = {}
            for part in m.group(1).split("&"):
                if "=" in part:
                    key, _, val = part.partition("=")
                    params[key] = unquote_plus(val)
            synonyms.append(params)
        return synonyms

    def _extract_publication_year(self, string: str) -> str:
        """
        Extract the four-digit year from a FishBase author string.

        FishBase encodes author and year together (e.g. ``"Linnaeus, 1758"``).

        Parameters
        ----------
        string : str
            Raw author string from the synonym link parameters.

        Returns
        -------
        str
            Four-digit year, or ``""`` if not found.
        """
        m = self._YEAR_SUFFIX_RE.search(string)
        return m.group(1) if m else ""

    def _extract_author(self, string: str) -> str:
        """
        Strip the trailing year suffix and return the author name.

        Parameters
        ----------
        string : str
            Raw author string from the synonym link parameters,
            e.g. ``"Linnaeus, 1758"``.

        Returns
        -------
        str
            Author name without the year (e.g. ``"Linnaeus"``), or the
            original string if no year suffix is present.
        """
        return self._YEAR_SUFFIX_RE.sub("", string).rstrip(", ").strip()

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw synonym parameter dicts into pipeline-standard synonym records.

        Excludes misspellings (``Misspelling=1``) and subspecific names
        (``SpeciesName`` contains a space). Deduplicates by canonical
        binomial name.

        Parameters
        ----------
        synonym_data : list of dict
            URL-decoded parameter dicts as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_synonym``.
        """
        candidates = []
        seen: set[str] = set()
        for params in synonym_data:
            genus = params.get("GenusName", "").strip()
            species = params.get("SpeciesName", "").strip()
            if not genus or not species:
                continue
            # Exclude subspecific names (e.g. "morhua morhua", "morhua callarias")
            if " " in species:
                continue
            if params.get("Misspelling", "0") == "1":
                continue
            name = f"{genus} {species}"
            if name in seen:
                continue
            seen.add(name)
            author_raw = params.get("Author", "")
            spec_code = params.get("SpecCode", "")
            candidates.append(
                self._format_synonym(
                    name=name,
                    author=self._extract_author(author_raw) or "U",
                    publication_year=self._extract_publication_year(author_raw),
                    api_link=(
                        f"{self.BASE_URL}/nomenclature/{spec_code}"
                        if spec_code
                        else "U"
                    ),
                )
            )
        return candidates
