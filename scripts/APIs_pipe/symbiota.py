"""
Symbiota API client

Provides a concrete SpeciesAPI implementation for Symbiota-based portals.
Each portal runs its own instance of the Symbiota software with different
endpoint paths and response formats. This module abstracts those
differences and normalizes all output to the predefined schema.

HTTP calls use the base-class ``_fetch_JSON`` helper and constructs the full URL from ``self.base`` for each endpoint.
"""

import re

# import xml.etree.ElementTree as ET  # only needed if taxonomy extraction is re-enabled
from urllib.parse import urlparse

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

# Rankid ranges for taxonomy column extraction from api/v2/taxonomy/{id}.
# Commented out: only needed if _extract_taxonomy is re-enabled.
# _RANK_RANGES: dict[str, tuple[int, int]] = {
#     "Phylum": (25, 45),
#     "Class": (50, 75),
#     "Family": (130, 155),
#     "Subfamily": (155, 170),
# }


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

    def __init__(self, base_url: str, portal_name: str = ""):
        """
        Parameters
        ----------
        base_url : str
            Root URL of the target portal,
            e.g. ``"https://mycoportal.org/portal"``.
        portal_name : str, optional
            Label for log messages. When omitted, the first subdomain component
            is derived from *base_url* (``"mycoportal"`` from ``"mycoportal.org"``).
        """
        self.BASE_URL = base_url.rstrip("/")
        if portal_name:
            self.portal_name = portal_name
        else:
            host = urlparse(base_url).netloc  # e.g. "mycoportal.org"
            self.portal_name = host.split(".")[0]  # e.g. "mycoportal"

    # ---------------------------------------------------------
    # Schema helpers (commented out: standard _format_synonym used instead)
    # ---------------------------------------------------------

    # def _empty_record(self) -> dict:
    #     """Return a blank record with every output column set to an empty string."""
    #     return {col: "" for col in COLUMNS}

    # def _build_record(self, taxonomy: dict, **fields) -> dict:
    #     """Build a single output record by merging empty defaults, taxonomy, and field overrides."""
    #     return {**self._empty_record(), **taxonomy, "Source Name": self.portal_name, **fields}

    # def _split_binomial(self, name: str) -> tuple[str, str]:
    #     """Split a binomial scientific name into (genus, species epithet)."""
    #     parts = name.split()
    #     return (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")

    # def _extract_taxonomy(self, data: dict) -> dict:
    #     """
    #     Extract taxonomy hierarchy fields from an api/v2/taxonomy/{id} response.
    #     Returns Kingdom, Phylum, Class, Family, Subfamily using _RANK_RANGES.
    #     """
    #     rank_index: dict[int, str] = {}
    #     for entry in data.get("classification", []):
    #         rid = entry.get("rankid")
    #         name = entry.get("scientificName", "")
    #         if rid is not None and name and str(name).strip():
    #             rank_index[int(rid)] = str(name).strip()
    #     def lowest_in_range(lo: int, hi: int) -> str:
    #         return next((rank_index[r] for r in range(lo, hi + 1) if r in rank_index), "")
    #     return {
    #         "Kingdom": str(data.get("kingdomName") or lowest_in_range(10, 15) or ""),
    #         "Phylum": lowest_in_range(*_RANK_RANGES["Phylum"]),
    #         "Class": lowest_in_range(*_RANK_RANGES["Class"]),
    #         "Family": lowest_in_range(*_RANK_RANGES["Family"]),
    #         "Subfamily": lowest_in_range(*_RANK_RANGES["Subfamily"]),
    #     }

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
    # HTML synonym scraping extractors (internal helpers)
    # ---------------------------------------------------------

    # NOTE: the below is unnecessary, as symbiota portals do not provide separate pages for recognized synonyms, only the page for the accepted taxon, whose ID we already know from the search results.
    # def _extract_synonym_ids(self, syn_html: str) -> dict[str, int]:
    #     """
    #     Extract a name-to-id mapping from synonym ``<a>`` links in HTML.

    #     Parameters
    #     ----------
    #     syn_html : str
    #         The inner HTML of the ``synonymDiv`` element.

    #     Returns
    #     -------
    #     dict[str, int]
    #         Mapping of synonym name strings to their internal taxon IDs.
    #     """
    #     id_map: dict[str, int] = {}
    #     for a_match in re.finditer(
    #         r"<a[^>]*[?&]tid=(\d+)[^>]*>(.*?)</a>", syn_html, re.DOTALL
    #     ):
    #         inner_name = re.search(r"<i>([^<]+)</i>", a_match.group(2))
    #         if inner_name:
    #             id_map[inner_name.group(1).strip()] = int(a_match.group(1))
    #     return id_map

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
        # Try both endpoints in order, returning the first successful response with results. While most portals will use /api/v2/taxonomy for both search queries and ID lookups, some (e.g. MyCoPortal) use /api/v2/taxonomy/search for name queries and api/v2/taxonomy for direct ID lookups, and may fail silently on a search query in api/v2/taxonomy, so we need to check both in this exact order.
        for endpoint in ("api/v2/taxonomy/search", "api/v2/taxonomy"):
            data = self._fetch_JSON(f"{self.BASE_URL}/{endpoint}", search_params)
            if data == {}:
                # _fetch_JSON returns {} on RequestException (network/HTTP error).
                print(
                    f"[{self.portal_name}] '{endpoint}' returned an error; trying next endpoint."
                )
                continue

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
            else:
                print(
                    f"[{self.portal_name}] '{endpoint}' returned no results for '{name}'."
                )
                continue

        print(
            f"[{self.portal_name}] All search endpoints returned no results for '{name}'. Attempting autocomplete search."
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
        self, raw_data: dict, synonym_data: list[dict]
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
        # If the query was already the accepted name, we can skip the extra request and just return raw_data.
        query_id = self._extract_internal_id(raw_data)
        if str(self.accepted_id) == str(query_id):
            return raw_data
        else:
            # Otherwise, query was a synonym — fetch the accepted taxon's record to get the correct name and author.
            accepted_data = self._fetch_JSON(
                f"{self.BASE_URL}/api/v2/taxonomy/{self.accepted_id}"
            )
            return accepted_data  # TODO: add error handling for failed request

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
        name = synonym_search_term_data.get(
            "sciname", ""
        ) or synonym_search_term_data.get("scientificName", "")
        if (
            not name or self._is_infraspecific(name)
        ):  # TODO: should we be doing an infraspecific check here? Need to investigate further how to handle this.
            return []
        return [
            self._format_row(
                name=name,
                author=synonym_search_term_data.get("author", ""),
                api_link=f"{self.BASE_URL}/taxa/index.php?tid={self.accepted_id}"
                if self.accepted_id
                else "",  # URL is the same for all synonyms since Symbiota redirects synonym searches to the accepted taxon page.
            )
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
            name = item["name"]
            if name.lower() not in seen:
                seen.add(name.lower())
                results.append(
                    self._format_row(
                        name=name,
                        author=item.get("author", ""),
                        api_link=f"{self.BASE_URL}/taxa/index.php?taxon={self.accepted_id}"
                        if self.accepted_id
                        else "",  # URL is the same for all synonyms since Symbiota redirects synonym searches to the accepted taxon page.
                    )
                )
        return results
