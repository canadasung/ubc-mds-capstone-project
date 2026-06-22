"""
Symbiota API client.

Symbiota is open-source biodiversity data management software that powers
numerous natural history collection portals worldwide.  Each portal runs its
own instance with independent data, but the same API structure.  This module
provides a single ``SymbiotaAPI`` class that accepts a portal name at
construction time and resolves the correct base URL from ``config.py``.

The Symbiota API returns JSON from ``api/v2/taxonomy`` and HTML from
``/taxa/index.php``.  The JSON endpoints are used to resolve taxon IDs and
taxonomy; the HTML page is scraped for synonym entries.

Documentation
-------------
All implemented Symbiota portals have documentation available through Swagger.

- MyCoPortal: https://mycoportal.org/portal/api/v2/documentation
- Lichen Portal: https://lichenportal.org/portal/api/v2/documentation
- Bryophyte Portal: https://bryophyteportal.org/portal/api/v2/documentation
- CCH2: https://cch2.org/portal/api/v2/documentation
- SERNEC: https://sernecportal.org/portal/api/v2/documentation
- NANSH: https://nansh.org/portal/api/v2/documentation
- Algae Herbarium Portal: https://macroalgae.org/portal/api/v2/documentation
- Pterido Portal: https://pteridoportal.org/portal/api/v2/documentation
- CNH: https://neherbaria.org/portal/api/v2/documentation
- Mid-Atlantic Herbaria Consortium: https://midatlanticherbaria.org/portal/api/v2/documentation
- swbiodiversity: https://swbiodiversity.org/seinet/api/v2/documentation

Fields implemented
------------------
- Taxonomy (kingdom → subfamily): accepted name row only
- author: both rows
- original_source: accepted name row only
- status: both rows
- api_link: both rows
"""

import re

# import xml.etree.ElementTree as ET  # only needed if taxonomy extraction is re-enabled
from urllib.parse import urlparse

from scripts.config import SYMBIOTA_PORTAL_BY_NAME
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI

# Canonical column order for extended Symbiota synonym DataFrames.
# Commented out: currently using the standard _format_synonym schema from SpeciesAPI.
# COLUMNS = [
#     "Source Name",
#     "Kingdom",
#     "Phylum",
#     "Class",
#     "Family",
#     "Subfamily",
#     "Genus",
#     "Species",
#     "Source Species ID",
#     "Author",
#     "Publication Name",
#     "Publication Year",
#     "Source Link",
#     "GBIF Accepted Status",
# ]

# Maps each portal's display_name to the endpoint used for name search queries.
_SEARCH_ENDPOINT: dict[str, str] = {
    "MyCoPortal": "api/v2/taxonomy/search",
}
_DEFAULT_SEARCH_ENDPOINT = "api/v2/taxonomy"

# Exact rankid values used by Symbiota for each taxonomic rank.
# Kingdom (10) is read from the top-level kingdomName field instead.
_RANK_IDS: dict[str, int] = {
    "phylum": 30,
    "class_": 60,
    "order": 100,
    "family": 140,
}


class SymbiotaAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for a single Symbiota portal instance.

    Attributes
    ----------
    BASE_URL : str
        Empty string placeholder; the real URL is set at construction time
        from ``config.SYMBIOTA_PORTAL_BY_NAME`` and stored without a trailing
        slash.
    portal_name : str
        Human-readable portal identifier used in log messages and the
        ``api_name`` field.
    """

    BASE_URL = ""

    def __init__(self, portal_name: str):
        """
        Initialise the client for the named Symbiota portal.

        Parameters
        ----------
        portal_name : str
            Display name of the target portal (e.g. ``"MyCoPortal"``).  Must
            be a key in ``config.SYMBIOTA_PORTAL_BY_NAME``.

        Raises
        ------
        ValueError
            If *portal_name* is not a recognised Symbiota portal key.
        """
        portal = SYMBIOTA_PORTAL_BY_NAME.get(portal_name)
        if portal is None:
            raise ValueError(
                f"Unknown Symbiota portal key {portal_name!r}. "
                f"Must be one of: {sorted(SYMBIOTA_PORTAL_BY_NAME)}"
            )
        self.BASE_URL = portal.base_url.rstrip("/")
        self.portal_name = portal.display_name

    # ---------------------------------------------------------
    # Schema helpers
    # ---------------------------------------------------------

    def _extract_taxonomy(self, data: dict) -> dict[str, str]:
        """
        Extract taxonomy fields from a Symbiota ``api/v2/taxonomy/{id}`` response.

        Builds a rankid-to-names index from the ``"classification"`` list.
        When a rankid has multiple entries the first value is used.

        Parameters
        ----------
        data : dict
            Parsed JSON from ``api/v2/taxonomy/{id}``.

        Returns
        -------
        dict[str, str]
            Keys: ``"kingdom"``, ``"phylum"``, ``"class_"``, ``"order"``,
            and ``"family"``.
        """
        rank_index: dict[int, list[str]] = {}
        for entry in data.get("classification", []):
            rid = entry.get("rankid")
            name = entry.get("scientificName", "")
            if rid is not None and name and str(name).strip():
                rank_index.setdefault(int(rid), []).append(str(name).strip())

        kingdom = str(data.get("kingdomName") or (rank_index.get(10, [""])[0]) or "")
        result: dict[str, str] = {"kingdom": kingdom}
        for col, rid in _RANK_IDS.items():
            result[col] = rank_index.get(rid, [""])[0]
        return result

    # ---------------------------------------------------------
    # Taxon ID resolution (internal helpers)
    # ---------------------------------------------------------

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the portal's internal taxon ID (``tid``) from a search result.

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.

        Returns
        -------
        str
            Internal taxon ID (``tid``).
        """
        return raw_data["tid"]

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Extract the accepted taxon ``tid`` from a ``api/v2/taxonomy/{id}`` response.

        Returns the taxon's own ``tid`` when its status is ``"accepted"``, or
        follows the ``accepted.tid`` pointer when it is ``"synonym"``.

        Parameters
        ----------
        raw_data : dict
            Parsed JSON from ``api/v2/taxonomy/{id}``.

        Returns
        -------
        str
            Internal ``tid`` of the accepted taxon.

        Raises
        ------
        ValueError
            If the taxon status is neither ``"accepted"`` nor ``"synonym"``.
        """
        status = raw_data["status"]
        if status not in ("accepted", "synonym"):
            raise ValueError(f"{self.portal_name}: Unrecognised status '{status}'.")
        if status == "accepted":
            return raw_data["tid"]
        else:
            accepted = raw_data["accepted"]
            return accepted["tid"]

    # ---------------------------------------------------------
    # TODO: write title here
    # ---------------------------------------------------------

    def _extract_synonym_pairs(self, html: str) -> list[tuple[str, str]]:
        """
        Extract ``(name, author)`` pairs from the ``synonymDiv`` in taxa page HTML.

        Finds the ``synonymDiv`` element, then parses ``<i>name</i> author``
        entries within it.  Infraspecific names are excluded.

        Parameters
        ----------
        html : str
            Raw HTML of the taxa page (full page, not just the div).

        Returns
        -------
        list[tuple[str, str]]
            ``(name, author)`` pairs for species-level synonyms, or ``[]`` if
            the ``synonymDiv`` is not found.
        """
        syn_match = re.search(r'id="synonymDiv"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not syn_match:
            return []
        syn_html = syn_match.group(1)
        pairs = []
        for match in re.finditer(r"<i>(.*?)</i>([^<]*)", syn_html):
            name = match.group(1).strip()
            author = match.group(2).strip()
            if name and not self._is_infraspecific(name):
                pairs.append((name, author))
        return pairs

    # ---------------------------------------------------------
    # Required template methods
    # ---------------------------------------------------------

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the portal for *name* and return the first matching result dict.

        Tries ``api/v2/taxonomy/search`` first (some portals, e.g. MyCoPortal),
        then falls back to ``api/v2/taxonomy``.  If both fail, attempts an
        autocomplete lookup via ``taxa/taxonomy/rpc/gettaxasuggest.php``.

        Parameters
        ----------
        name : str
            Normalised scientific name.

        Returns
        -------
        dict
            First matching result dict from the portal, or ``{}`` if all
            endpoints fail or return no results.
        """
        search_params = {"taxon": name, "type": "EXACT", "limit": 100, "offset": 0}
        endpoint = _SEARCH_ENDPOINT.get(self.portal_name, _DEFAULT_SEARCH_ENDPOINT)
        data = self._fetch_JSON(f"{self.BASE_URL}/{endpoint}", search_params)

        if data != {}:
            # Some portals return a list directly, while others wrap it in a 'results' dict.
            if isinstance(data, list):
                results = data[0] if len(data) > 0 else {}
            else:
                results = data.get("results") or []
                results = results[0] if len(results) > 0 else {}

            if results:
                print(
                    f"[{self.portal_name}] '{endpoint}' returned results for '{name}'."
                )
                return results

        print(
            f"[{self.portal_name}] Search endpoint returned no results for '{name}'. Attempting autocomplete search."
        )

        # If neither API endpoint returned results, attempt to resolve the ID via autocomplete.
        items = self._fetch_JSON(
            f"{self.BASE_URL}/taxa/taxonomy/rpc/gettaxasuggest.php",
            {"term": name},
        )
        for item in items if isinstance(items, list) else []:
            label = item["label"]
            if re.match(rf"^{re.escape(name)}(\s|$)", label):
                print(
                    f"[{self.portal_name}] Found match for '{name}' via autocomplete."
                )
                return item

        print(
            f"[{self.portal_name}] All searches failed or returned no results for '{name}'."
        )
        return {}

    def _fetch_synonym_data(self, raw_data: dict) -> str:
        """
        Fetch the accepted taxon's taxa page HTML from ``/taxa/index.php``.

        Pipeline:

        1. ``_extract_internal_id`` → taxon ``tid`` from *raw_data*.
        2. Fetch ``api/v2/taxonomy/{tid}`` to check status.
        3. ``_extract_internal_accepted_id`` → accepted ``tid`` (no API call).
        4. Fetch and return ``/taxa/index.php?tid={accepted_tid}`` HTML.

        Stores the accepted ``tid`` as ``self.accepted_id`` for downstream use.

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.

        Returns
        -------
        str
            Raw HTML of the accepted taxon's taxa page, or ``""`` on error.
        """
        # Step 1: resolve id from search results
        id = self._extract_internal_id(raw_data)

        # Step 2: fetch taxonomy record to check the status, and use that to resolve to accepted id.
        taxonomy_data = self._fetch_JSON(f"{self.BASE_URL}/api/v2/taxonomy/{id}")
        if taxonomy_data == {}:
            raise RuntimeError(
                f"{self.portal_name}: failed to fetch api/v2/taxonomy/{id}."
            )
        self.accepted_id = self._extract_internal_accepted_id(taxonomy_data)

        # Step 3: fetch and return the raw HTML taxa page.
        return self._fetch_HTML(
            url=f"{self.BASE_URL}/taxa/index.php",
            params={"tid": self.accepted_id},
            timeout=30,
        )

    def _fetch_accepted_data(self, _raw_data: dict, _synonym_data: str) -> dict:
        """
        Fetch the accepted taxon's full taxonomy record from ``api/v2/taxonomy/{id}``.

        Always fetches using ``self.accepted_id`` (set by ``_fetch_synonym_data``)
        to ensure consistent name, author, and classification fields regardless
        of whether the original query was an accepted name or a synonym.

        Parameters
        ----------
        _raw_data : dict
            The dict returned by ``_fetch_query_data`` (unused here).
        _synonym_data : str
            Raw HTML taxa page (unused here).

        Returns
        -------
        dict
            The accepted taxon's ``api/v2/taxonomy/{id}`` record.
        """
        # Always fetch the full taxonomy record for consistent classification data.
        return self._fetch_JSON(
            f"{self.BASE_URL}/api/v2/taxonomy/{self.accepted_id}"
        )  # TODO: add error handling for failed request

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from a Symbiota taxonomy record.

        Parameters
        ----------
        accepted_data : dict
            The accepted taxon's taxonomy record returned by
            ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if the name
            cannot be determined or is infraspecific.
        """
        name = normalize_query_string(
            accepted_data.get("sciname", "") or accepted_data.get("scientificName", "")
        )
        if not name or self._is_infraspecific(name):
            return []
        genus, species = self._extract_genus_species(name)
        taxonomy = self._extract_taxonomy(accepted_data)
        return [
            self._format_row(
                **{
                    "api_name": self.portal_name,
                    **taxonomy,
                    "genus": genus,
                    "species": species,
                    "api_internal_id": str(self.accepted_id),
                    "author": accepted_data.get("author", ""),
                    "original_source": accepted_data.get("source") or "",
                    "status": "Accepted",
                    "api_link": f"{self.BASE_URL}/taxa/index.php?tid={self.accepted_id}"
                    if self.accepted_id
                    else "",
                }
            )
        ]

    def _compile_synonyms(self, synonym_data: str) -> list[dict]:
        """
        Convert taxa page HTML into pipeline-standard synonym records.

        Delegates parsing to ``_extract_synonym_pairs``, deduplicates by
        canonical name, and strips leading ``", "`` from raw author strings.

        Parameters
        ----------
        synonym_data : str
            Raw HTML of the accepted taxon's taxa page as returned by
            ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
        """
        seen = set()
        results = []
        for raw_name, raw_author in self._extract_synonym_pairs(synonym_data):
            name = normalize_query_string(raw_name)
            if not name or self._is_infraspecific(name):
                continue
            if name not in seen:
                seen.add(name)
                genus, species = self._extract_genus_species(name)
                author = raw_author.lstrip(", ")
                results.append(
                    self._format_row(
                        **{
                            "api_name": self.portal_name,
                            "genus": genus,
                            "species": species,
                            "api_internal_id": str(
                                self.accepted_id
                            ),  # symbiota portals only have accepted ID
                            "author": author,
                            "status": "Synonym",
                            "api_link": f"{self.BASE_URL}/taxa/index.php?taxon={self.accepted_id}"
                            if self.accepted_id
                            else "",
                        }
                    )
                )
        return results
