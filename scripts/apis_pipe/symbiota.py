"""
Symbiota API client

Provides a concrete SpeciesAPI implementation for Symbiota-based portals.
Each portal runs its own instance of the Symbiota software with different
endpoint paths and response formats. This module abstracts those
differences and normalizes all output to the predefined schema.

HTTP calls use the base-class ``_fetch_JSON`` helper and constructs the full URL from ``self.base`` for each endpoint.
"""

import re
from itertools import product

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
    API client for a single Symbiota portal instance.

    Attributes
    ----------
    BASE_URL : str
        Empty string placeholder; the real URL is supplied at construction time
        via *base_url* and stored as ``self.base``.
    base : str
        Normalized base URL with the trailing slash removed.
    portal_name : str
        Human-readable portal identifier used in log messages.
    """

    BASE_URL = ""

    def __init__(self, portal_name: str):
        """
        Parameters
        ----------
        portal_name : str
            Short internal identifier for the target portal
            (e.g. ``"mycoportal"``). Must be a key in
            ``config.SYMBIOTA_PORTAL_BY_NAME``.

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

    def _extract_taxonomy(self, data: dict) -> list[dict[str, str]]:
        """
        Extract taxonomy hierarchy fields from an api/v2/taxonomy/{id} response.

        Builds a rankid → list-of-names index. When a rankid has multiple entries
        (e.g. two families), the cartesian product is returned so the caller can
        emit one row per combination — capturing the ambiguity rather than silently
        dropping it.
        """
        rank_index: dict[int, list[str]] = {}
        for entry in data.get("classification", []):
            rid = entry.get("rankid")
            name = entry.get("scientificName", "")
            if rid is not None and name and str(name).strip():
                rank_index.setdefault(int(rid), []).append(str(name).strip())

        kingdom = str(data.get("kingdomName") or (rank_index.get(10, [""])[0]) or "")
        col_values: dict[str, list[str]] = {"kingdom": [kingdom]}
        for col, rid in _RANK_IDS.items():
            col_values[col] = rank_index.get(rid, [""])

        return [
            dict(zip(col_values.keys(), combo))
            for combo in product(*col_values.values())
        ]

    # ---------------------------------------------------------
    # Taxon ID resolution (internal helpers)
    # ---------------------------------------------------------

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the portal's internal taxon ID from raw search results.

        Returns the tid of the first result.

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
        Extract the accepted taxon ID from a ``api/v2/taxonomy/{id}`` response.

        If the taxon is a synonym, follows the ``accepted.id`` pointer.
        Otherwise returns the taxon's own ``id``.

        Parameters
        ----------
        raw_data : dict
            Parsed JSON from ``api/v2/taxonomy/{id}``.

        Returns
        -------
        str
            Internal ID of the accepted taxon.
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

    def _extract_synonym_pairs(self, syn_html: str) -> list[tuple[str, str]]:
        """
        Extract (name, author) pairs from italic synonym entries in HTML.

        Parameters
        ----------
        syn_html : str
            The inner HTML of the ``synonymDiv`` element.

        Returns
        -------
        list[tuple[str, str]]
            List of ``(name, author)`` pairs for species-level synonyms.
        """
        pairs = []
        for match in re.finditer(r"<i>(.*?)</i>([^<]*)", syn_html):
            name = match.group(1).strip()
            author = re.sub(r"^[,\s]+|[,\s]+$", "", match.group(2).strip())
            if name and not self._is_infraspecific(name):
                pairs.append((name, author))
        return pairs

    # ---------------------------------------------------------
    # Required template methods
    # ---------------------------------------------------------

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the portal for *name* and return the raw search results.

        Tries both Symbiota search endpoints in order, returning the raw
        response dict as soon as either yields results.

        1. ``api/v2/taxonomy/search``: primary endpoint (e.g. MyCoPortal).
        2. ``api/v2/taxonomy``: primary endpoint for most other portals.

        Parameters
        ----------
        name : str
            Normalised scientific name.

        Returns
        -------
        dict
            Raw search response from the portal, or ``{}`` if both endpoints
            fail or return no results.
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

    def _fetch_synonym_data(self, raw_data: dict) -> list[dict]:
        """
        Fetch the accepted taxon's raw synonym entries.

        Owns the API calls for the synonym pipeline:

        1. Calls ``_extract_internal_id`` to resolve the taxon ID (with
           autocomplete fallback).
        2. Fetches the taxonomy record for the resolved ``id``.
        3. Calls ``_extract_internal_accepted_id`` to get the accepted ``id``
           from the taxonomy response (no API call).
        4. Scrapes the HTML taxa page for the accepted taxon's synonyms.

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            Raw synonym entries as returned by ``_scrape_synonyms``:
            ``[{"name": str, "author": str, "id": str}, ...]``.
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

        # Step 3: scrape synonym records from the accepted taxon's HTML page.
        html_text = self._fetch_HTML(
            url=f"{self.BASE_URL}/taxa/index.php",
            params={"tid": self.accepted_id},
            timeout=30,
        )

        syn_match = re.search(r'id="synonymDiv"[^>]*>(.*?)</div>', html_text, re.DOTALL)
        if not syn_match:
            return []

        syn_html = syn_match.group(1)
        pairs = self._extract_synonym_pairs(syn_html)

        # Note: The raw HTML response for a search of the accepted ID page does not provide synonym IDs. In future, we could attempt to provide syonym IDs by making additional API calls for each synonym name to resolve their IDs. For now, I've removed the ID field.
        return [{"name": name, "author": author} for name, author in pairs]

    def _fetch_synonym_search_term_data(
        self, _raw_data: dict, _synonym_data: list[dict]
    ) -> dict:
        """
        Return the accepted taxon's taxonomy record for the synonym search term.

        ``_fetch_synonym_data`` already resolved the accepted taxon ID and stored
        it as ``self.accepted_id``. When the queried name was itself the accepted
        name, ``raw_data`` is correct. When it was a synonym, ``raw_data`` has the
        synonym's ``sciname`` — so we fetch ``/api/v2/taxonomy/{accepted_id}`` to
        get the right name and author.

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.
        synonym_data : list of dict
            Raw synonym entries (unused here).

        Returns
        -------
        dict
            The accepted taxon's taxonomy record, or ``raw_data`` on failure.
        """
        # Always fetch the full taxonomy record for consistent classification data.
        return self._fetch_JSON(
            f"{self.BASE_URL}/api/v2/taxonomy/{self.accepted_id}"
        )  # TODO: add error handling for failed request

    def _compile_synonym_search_term(
        self, synonym_search_term_data: dict
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term from the
        Symbiota query result.

        Parameters
        ----------
        synonym_search_term_data : dict
            The query result dict returned by ``_fetch_synonym_search_term_data``.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if the name
            cannot be determined or is infraspecific.
        """
        name = normalize_query_string(
            synonym_search_term_data.get("sciname", "")
            or synonym_search_term_data.get("scientificName", "")
        )
        if not name or self._is_infraspecific(name):
            return []
        genus, species = self._extract_genus_species(name)
        taxonomies = self._extract_taxonomy(synonym_search_term_data)
        return [
            self._format_row(
                **{
                    "api_name": self.portal_name,
                    **taxonomy,
                    "genus": genus,
                    "species": species,
                    "api_internal_id": str(self.accepted_id),
                    "author": synonym_search_term_data.get("author", ""),
                    "original_source": synonym_search_term_data.get("source") or "",
                    "status": "Accepted",
                    "api_link": f"{self.BASE_URL}/taxa/index.php?tid={self.accepted_id}"
                    if self.accepted_id
                    else "",
                }
            )
            for taxonomy in taxonomies
        ]

    def _compile_synonyms(self, synonym_data: list[dict]) -> list[dict]:
        """
        Convert raw synonym entries into pipeline-standard synonym records.

        Deduplicates by name (case-insensitive) and formats each entry using
        ``_format_synonym``.

        Parameters
        ----------
        synonym_data : list of dict
            Raw synonym entries as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_synonym``.
        """
        seen = set()
        results = []
        for item in synonym_data:
            name = normalize_query_string(item["name"])
            if not name or self._is_infraspecific(name):
                continue
            if name not in seen:
                seen.add(name)
                genus, species = self._extract_genus_species(name)
                results.append(
                    self._format_row(
                        **{
                            "api_name": self.portal_name,
                            "genus": genus,
                            "species": species,
                            "api_internal_id": str(
                                self.accepted_id
                            ),  # symbiota portals only have accepted ID
                            "author": item.get("author", ""),
                            "status": "Synonym",
                            "api_link": f"{self.BASE_URL}/taxa/index.php?taxon={self.accepted_id}"
                            if self.accepted_id
                            else "",
                        }
                    )
                )
        return results
