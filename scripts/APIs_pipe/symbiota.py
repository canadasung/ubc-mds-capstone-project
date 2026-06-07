"""
Symbiota API client

Symbiota portal client for taxonomic name and synonym retrieval.

Provides a concrete SpeciesAPI implementation for Symbiota-based portals.
Each portal runs its own instance of the Symbiota software with different
endpoint paths and response formats. This module abstracts those
differences and normalizes all output to the predefined schema.

All HTTP calls go through the portal-specific ``_get()`` wrapper rather than
the base-class ``_fetch_JSON`` / ``_fetch_text`` helpers, since each Symbiota
portal has a dynamic base URL set at construction time. Two transport paths are
used for redundancy: the JSON REST API resolves taxon IDs and taxonomy, and the
HTML taxa page provides the synonym list.
"""

import re
import warnings
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pandas as pd
import requests

from ..utils.normalize_query_string import normalize_query_string
from .base import SpeciesAPI

# Canonical column order for all synonym DataFrames produced by this module.
# Matches the schema defined in data/sample/*.csv.
COLUMNS = [
    "Source Name",
    "Kingdom",
    "Phylum",
    "Class",
    "Family",
    "Subfamily",
    "Genus",
    "Species",
    "Source Species ID",
    "Author",
    "Publication Name",
    "Publication Year",
    "Source Link",
    "GBIF Accepted Status",
]

# Maps each taxonomy column to the rankid range that identifies it in the
# api/v2/taxonomy/{identifier} classification array. Boundaries are derived from
# observed Symbiota portal responses; the lowest rankid within each range wins.
_RANK_RANGES: dict[str, tuple[int, int]] = {
    "Phylum": (25, 45),
    "Class": (50, 75),
    "Family": (130, 155),
    "Subfamily": (155, 170),
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
        Source identifier written to the ``Source Name`` output column.
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
            Label for the ``Source Name`` output column. When omitted, the
            first subdomain component is derived from *base_url*
            (``"mycoportal"`` from ``"mycoportal.org"``).
        """
        self.base = base_url.rstrip("/")
        if portal_name:
            self.portal_name = portal_name
        else:
            host = urlparse(base_url).netloc  # e.g. "mycoportal.org"
            self.portal_name = host.split(".")[0]  # e.g. "mycoportal"

    def _get(self, endpoint: str, params: dict, timeout: int = 30):
        """
        Send a GET request to a portal endpoint.

        Parameters
        ----------
        endpoint : str
            Path relative to ``self.base``,
            e.g. ``"api/v2/taxonomy/search"``.
        params : dict
            URL query parameters.
        timeout : int, optional
            Request timeout in seconds. Default is 30.

        Returns
        -------
        requests.Response

        Raises
        ------
        RuntimeError
            If the portal returns HTTP 403.

        Notes
        -----
        Prints ``[portal_name] GET {endpoint} → HTTP {status_code}`` for
        every request so all HTTP activity is visible without needing a
        debugger.
        """
        resp = requests.get(
            f"{self.base}/{endpoint}",
            params=params,
            headers=self.HEADERS,
            timeout=timeout,
        )
        return resp

    # ---------------------------------------------------------
    # Schema Helpers
    # ---------------------------------------------------------

    def _empty_record(self) -> dict:
        """
        Return a blank record with every output column set to an empty string.

        Returns
        -------
        dict
            Keys matching ``COLUMNS``, all values ``""``.
        """
        return {col: "" for col in COLUMNS}

    def _build_record(self, taxonomy: dict, **fields) -> dict:
        """
        Build a single output record by merging empty defaults, taxonomy, and field overrides.

        Centralises the repeated ``{**_empty_record(), **taxonomy, "Source Name": ..., ...}``
        pattern used wherever a synonym row is constructed.

        Parameters
        ----------
        taxonomy : dict
            Taxonomy hierarchy fields (Kingdom, Phylum, Class, Family, Subfamily).
        **fields
            Additional column values to set on top of the defaults.

        Returns
        -------
        dict
            Complete record with all columns in ``COLUMNS``.
        """
        return {
            **self._empty_record(),
            **taxonomy,
            "Source Name": self.portal_name,
            **fields,
        }

    def _split_binomial(self, name: str) -> tuple[str, str]:
        """
        Split a binomial scientific name into genus and species epithet.

        Parameters
        ----------
        name : str
            Scientific name, e.g. ``"Amanita muscaria"``.

        Returns
        -------
        genus : str
            First token of *name*, or ``""`` when *name* is empty.
        species : str
            Second token of *name*, or ``""`` when *name* has fewer than two tokens.
        """
        parts = name.split()
        return (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")

    def _extract_taxonomy(self, data: dict) -> dict:
        """
        Extract taxonomy hierarchy fields from an ``api/v2/taxonomy/{identifier}`` response.

        Parameters
        ----------
        data : dict
            Parsed JSON response from ``api/v2/taxonomy/{identifier}``.

        Returns
        -------
        dict
            Keys ``"Kingdom"``, ``"Phylum"``, ``"Class"``, ``"Family"``,
            ``"Subfamily"`` mapped to their names, or ``""`` when absent.

        Notes
        -----
        Kingdom is read from the top-level ``kingdomName`` field. The remaining
        ranks are resolved from the ``classification`` array using the rankid
        ranges in ``_RANK_RANGES``; the lowest rankid within each range is used
        so the primary rank takes precedence over sub-ranks.
        """
        rank_index: dict[int, str] = {}
        for entry in data.get("classification", []):
            rid = entry.get("rankid")
            name = entry.get("scientificName", "")
            if rid is not None and name and str(name).strip():
                rank_index[int(rid)] = str(name).strip()

        def lowest_in_range(lo: int, hi: int) -> str:
            # Returns the name at the lowest rankid within [lo, hi], or "" if none found.
            return next(
                (rank_index[r] for r in range(lo, hi + 1) if r in rank_index), ""
            )

        return {
            "Kingdom": str(data.get("kingdomName") or lowest_in_range(10, 15) or ""),
            "Phylum": lowest_in_range(*_RANK_RANGES["Phylum"]),
            "Class": lowest_in_range(*_RANK_RANGES["Class"]),
            "Family": lowest_in_range(*_RANK_RANGES["Family"]),
            "Subfamily": lowest_in_range(*_RANK_RANGES["Subfamily"]),
        }

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    def search(self, name: str) -> dict:
        """
        Search for a taxon by scientific name.

        Tries both endpoints in order. Returns as soon as either yields results.
        If the first endpoint returns HTTP 200 with empty results, the second is
        still tried because different portals use different paths as their primary
        search endpoint:

        1. ``api/v2/taxonomy/search``: primary endpoint (e.g. MyCoPortal).
        2. ``api/v2/taxonomy``: primary endpoint for most other portals.

        Parameters
        ----------
        name : str
            Scientific name to search for.

        Returns
        -------
        dict
            Normalized response with a ``"results"`` key. List responses are
            wrapped as ``{"results": [...]}``. Returns ``{"results": []}``
            when the API responds with HTTP 2xx but no matching records.

        Raises
        ------
        RuntimeError
            When both endpoints fail due to a network or HTTP error.
        """
        search_params = {"taxon": name, "type": "EXACT", "limit": 100, "offset": 0}

        # Try api/v2/taxonomy/search first (e.g. MyCoPortal), then api/v2/taxonomy (most other portals).
        # Both endpoints are always attempted because different portals use different paths as their
        # primary search endpoint - one returning empty does not mean the other will too.
        got_empty_response = False
        for endpoint in ("api/v2/taxonomy/search", "api/v2/taxonomy"):
            try:
                resp = self._get(endpoint, search_params)
                if not resp.ok:
                    print(
                        f"[{self.portal_name}] '{endpoint}' returned non-2xx; trying next endpoint."
                    )
                    continue
                data = resp.json()
                if isinstance(data, list):
                    data = {"results": data}
                if isinstance(data, dict) and data.get("results"):
                    print(
                        f"[{self.portal_name}] '{endpoint}' succeeded: {len(data['results'])} result(s)."
                    )
                    return data
                # Endpoint responded with HTTP 200 but no matching records - record this and keep trying.
                print(
                    f"[{self.portal_name}] '{endpoint}' returned HTTP 200 but no results for '{name}'."
                )
                got_empty_response = True
            except Exception as e:
                print(f"[{self.portal_name}] '{endpoint}' raised an exception: {e}")
                warnings.warn(
                    f"{self.portal_name}: '{endpoint}' failed ({e}); trying next endpoint.",
                    stacklevel=2,
                )
                continue

        # At least one endpoint answered successfully (HTTP 200) but found no records.
        # This means the species is not in this portal, not that the API is broken.
        if got_empty_response:
            return {"results": []}

        raise RuntimeError(
            f"{self.portal_name}: both search endpoints failed for '{name}'."
        )

    # ---------------------------------------------------------
    # Internal ID resolution
    # ---------------------------------------------------------

    def _extract_internal_id(self, species_name: str) -> int:
        """
        Return the internal taxon ID for an exact name match.

        Parameters
        ----------
        species_name : str
            Scientific name to look up.

        Returns
        -------
        int
            Internal taxon ID.

        Raises
        ------
        LookupError
            When no matching taxon ID is found via either method.

        Notes
        -----
        Uses ``search()`` as the primary lookup. If no exact match is found,
        falls back to the autocomplete endpoint
        ``taxa/taxonomy/rpc/gettaxasuggest.php``.
        """
        # Primary: find an exact name match in search() results.
        # search() always returns a dict or raises, never None.
        data = self.search(species_name)
        for item in data.get("results", []):
            sciname = (
                item.get("sciname")
                or item.get("scientificName")
                or item.get("taxon", "")
            )
            if re.match(rf"^{re.escape(species_name)}\s*$", sciname, re.IGNORECASE):
                try:
                    tid = int(item["tid"])
                    print(
                        f"[{self.portal_name}] Found tid={tid} for '{species_name}' via search."
                    )
                    return tid
                except (KeyError, ValueError, TypeError) as e:
                    print(
                        f"[{self.portal_name}] Could not parse tid from search result: {e}"
                    )

        # Fallback: autocomplete endpoint when search returned no exact match.
        print(
            f"[{self.portal_name}] No exact match in search results for '{species_name}'; trying autocomplete."
        )
        try:
            resp = self._get(
                "taxa/taxonomy/rpc/gettaxasuggest.php", {"term": species_name}
            )
            resp.raise_for_status()
            for item in resp.json():
                label = item.get("label", "")
                if re.match(rf"^{re.escape(species_name)}(\s|$)", label):
                    tid = int(item["id"])
                    print(
                        f"[{self.portal_name}] Found tid={tid} for '{species_name}' via autocomplete."
                    )
                    return tid
            print(
                f"[{self.portal_name}] Autocomplete returned no match for '{species_name}'."
            )
        except Exception as e:
            print(
                f"[{self.portal_name}] Autocomplete raised an exception for '{species_name}': {e}"
            )
            warnings.warn(
                f"{self.portal_name}: autocomplete fallback failed for '{species_name}' ({e}).",
                stacklevel=2,
            )

        raise LookupError(
            f"{self.portal_name}: no taxon ID found for '{species_name}'."
        )

    # ---------------------------------------------------------
    # Accepted taxon resolution
    # ---------------------------------------------------------

    def _fetch_taxonomy(self, tid: int) -> dict:
        """
        Fetch and return the JSON taxonomy record for a taxon ID.

        Parameters
        ----------
        tid : int
            Internal taxon ID to fetch.

        Returns
        -------
        dict
            Parsed JSON response from ``api/v2/taxonomy/{tid}``.

        Raises
        ------
        ValueError
            If the response is not a JSON object (unexpected schema change).
        requests.HTTPError
            On non-2xx HTTP status.
        """
        resp = self._get(f"api/v2/taxonomy/{tid}", params={})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError(
                f"{self.portal_name}: api/v2/taxonomy/{tid} returned "
                f"{type(data).__name__} instead of a JSON object; "
                f"the response schema may have changed."
            )
        return data

    def _extract_taxon_meta(self, data: dict, tid: int) -> tuple[str, str, str]:
        """
        Extract and validate status, sciname, and author from a taxonomy response dict.

        Emits ``UserWarning`` when the status field is missing or unrecognised,
        but continues with safe defaults rather than raising.

        Parameters
        ----------
        data : dict
            Parsed JSON from ``_fetch_taxonomy()``.
        tid : int
            The taxon ID that was fetched, used in warning messages.

        Returns
        -------
        tuple[str, str, str]
            ``(status, sciname, author)`` where *status* is ``"accepted"``,
            ``"synonym"``, or an unrecognised value (treated as accepted).
        """
        status = data.get("status")
        if status is None:
            warnings.warn(
                f"{self.portal_name}: api/v2/taxonomy/{tid} response is missing "
                f"the 'status' field; treating as accepted. "
                f"The response schema may have changed.",
                stacklevel=2,
            )
        elif status not in ("accepted", "synonym"):
            warnings.warn(
                f"{self.portal_name}: api/v2/taxonomy/{tid} returned unrecognised "
                f"status '{status}'; treating as accepted.",
                stacklevel=2,
            )
        sciname = data.get("scientificName") or data.get("sciname") or ""
        author = data.get("author") or ""
        return status, sciname, author

    def _resolve_synonym_to_accepted(self, data: dict, tid: int) -> tuple[int, dict]:
        """
        Resolve a synonym taxon record to its accepted taxon, fetching classification.

        Makes a second API call to fetch the accepted taxon's full classification.
        Falls back to the synonym's own classification if that call fails.

        Parameters
        ----------
        data : dict
            Taxonomy record for the synonym taxon (from ``_fetch_taxonomy()``).
        tid : int
            Taxon ID of the synonym, used in warning messages.

        Returns
        -------
        accepted_tid : int
            Internal ID of the accepted taxon.
        meta : dict
            Combined taxonomy + metadata dict for the accepted taxon.
        """
        accepted = data.get("accepted") or {}
        if not accepted.get("tid"):
            warnings.warn(
                f"{self.portal_name}: synonym response for tid {tid} is missing "
                f"'accepted.tid'; the accepted taxon cannot be resolved.",
                stacklevel=2,
            )
        accepted_tid = int(accepted.get("tid", tid))
        accepted_name = accepted.get("scientificName") or accepted.get("sciname") or ""
        accepted_author = accepted.get("scientificNameAuthorship") or ""
        sciname = data.get("scientificName") or data.get("sciname") or ""
        author = data.get("author") or ""

        # Re-fetch the accepted taxon to get its full classification array.
        try:
            acc_data = self._fetch_taxonomy(accepted_tid)
            taxonomy = self._extract_taxonomy(acc_data)
            print(
                f"[{self.portal_name}] Classification resolved for accepted tid={accepted_tid}."
            )
        except Exception as e:
            warnings.warn(
                f"{self.portal_name}: could not fetch classification for accepted tid "
                f"{accepted_tid} ({e}); falling back to synonym's own classification.",
                stacklevel=2,
            )
            print(
                f"[{self.portal_name}] Using synonym's own classification as fallback for tid={accepted_tid}."
            )
            taxonomy = self._extract_taxonomy(data)

        print(
            f"[{self.portal_name}] '{sciname}' is a Synonym; accepted name is '{accepted_name}' (tid={accepted_tid})."
        )
        return accepted_tid, {
            **taxonomy,
            "sciname": sciname,
            "author": author,
            "status": "Synonym",
            "accepted_tid": accepted_tid,
            "accepted_name": accepted_name,
            "accepted_author": accepted_author,
        }

    def _resolve_accepted_tid(self, tid: int) -> tuple[int, dict]:
        """
        Resolve a taxon ID to its accepted form and return taxonomy metadata.

        Parameters
        ----------
        tid : int
            Internal taxon ID to resolve.

        Returns
        -------
        accepted_tid : int
            ID of the accepted taxon. Equal to *tid* when already accepted.
        meta : dict
            Keys ``"Kingdom"``, ``"Phylum"``, ``"Class"``, ``"Family"``,
            ``"Subfamily"``, ``"sciname"``, ``"author"``, ``"status"``
            (``"Accepted"`` or ``"Synonym"``), ``"accepted_tid"``, and
            ``"accepted_name"`` (``None`` when already accepted).
        """
        data = self._fetch_taxonomy(tid)
        status, sciname, author = self._extract_taxon_meta(data, tid)

        if status == "synonym":
            return self._resolve_synonym_to_accepted(data, tid)

        taxonomy = self._extract_taxonomy(data)
        print(f"[{self.portal_name}] '{sciname}' is Accepted (tid={tid}).")
        return tid, {
            **taxonomy,
            "sciname": sciname,
            "author": author,
            "status": "Accepted",
            "accepted_tid": tid,
            "accepted_name": None,
            "accepted_author": None,
        }

    # ---------------------------------------------------------
    # HTML synonym scraping
    # ---------------------------------------------------------

    def _fetch_taxa_page(self, tid: int) -> str:
        """
        Fetch the raw HTML taxa page for a given taxon ID.

        Parameters
        ----------
        tid : int
            Internal taxon ID whose page should be fetched.

        Returns
        -------
        str
            Raw HTML text of the taxa page.

        Raises
        ------
        requests.HTTPError
            On non-2xx HTTP status.
        """
        resp = self._get("taxa/index.php", {"tid": tid})
        resp.raise_for_status()
        return resp.text

    def _extract_synonym_tids(self, syn_html: str) -> dict[str, int]:
        """
        Extract a name-to-tid mapping from synonym ``<a>`` links in HTML.

        Performs Pass 1 of the synonym HTML parse: finds ``<a href="…?tid=N">``
        links and builds a ``{name: tid}`` dict for use in record construction.

        Parameters
        ----------
        syn_html : str
            The inner HTML of the ``synonymDiv`` element.

        Returns
        -------
        dict[str, int]
            Mapping of synonym name strings to their internal taxon IDs.
        """
        tid_map: dict[str, int] = {}
        for a_match in re.finditer(
            r"<a[^>]*[?&]tid=(\d+)[^>]*>(.*?)</a>", syn_html, re.DOTALL
        ):
            inner_name = re.search(r"<i>([^<]+)</i>", a_match.group(2))
            if inner_name:
                tid_map[inner_name.group(1).strip()] = int(a_match.group(1))
        return tid_map

    def _extract_synonym_pairs(self, syn_html: str) -> list[tuple[str, str]]:
        """
        Extract (name, author) pairs from italic synonym entries in HTML.

        Performs Pass 2 of the synonym HTML parse: finds ``<i>name</i> author``
        patterns and returns the pairs, excluding infraspecific taxa.

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

    def _scrape_synonyms(self, accepted_tid: int, taxonomy: dict) -> list[dict]:
        """
        Scrape the HTML species page for synonym records.

        Parameters
        ----------
        accepted_tid : int
            Internal ID of the accepted taxon.
        taxonomy : dict
            Taxonomy hierarchy fields inherited by every synonym record.

        Returns
        -------
        list of dict
            One record per synonym, keyed by every column in ``COLUMNS``.
            Returns an empty list when the page has no synonym section or the
            synonym section is empty.
        """
        html_text = self._fetch_taxa_page(accepted_tid)

        syn_match = re.search(r'id="synonymDiv"[^>]*>(.*?)</div>', html_text, re.DOTALL)
        if not syn_match:
            return []

        syn_html = syn_match.group(1)
        tid_map = self._extract_synonym_tids(syn_html)
        pairs = self._extract_synonym_pairs(syn_html)

        records = []
        for name, author in pairs:
            genus, species_epithet = self._split_binomial(name)
            syn_tid = tid_map.get(name)
            src_link = f"{self.base}/taxa/index.php?taxon={syn_tid}" if syn_tid else ""

            records.append(
                self._build_record(
                    taxonomy,
                    **{
                        "Genus": genus,
                        "Species": species_epithet,
                        "Source Species ID": str(syn_tid) if syn_tid else "",
                        "Author": author,
                        "Source Link": src_link,
                        "GBIF Accepted Status": "Synonym",
                    },
                )
            )

        print(
            f"[{self.portal_name}] Scraped {len(records)} synonym(s) from taxa page for tid={accepted_tid}."
        )
        return records

    # ---------------------------------------------------------
    # Required template methods
    # ---------------------------------------------------------

    def _fetch_query_data(self, name: str) -> dict:
        """
        Resolve *name* to its taxon ID and accepted-taxon metadata.

        Uses the JSON REST API (``_extract_internal_id`` + ``_resolve_accepted_tid``).

        Parameters
        ----------
        name : str
            Normalised scientific name.

        Returns
        -------
        dict
            ``{"tid": int, "accepted_tid": int, "meta": dict}`` where *meta*
            contains taxonomy hierarchy keys and status fields from
            ``_resolve_accepted_tid``.

        Raises
        ------
        LookupError
            When no taxon ID can be resolved for *name*.
        """
        tid = self._extract_internal_id(name)
        accepted_tid, meta = self._resolve_accepted_tid(tid)
        return {"tid": tid, "accepted_tid": accepted_tid, "meta": meta}

    def _fetch_synonym_data(self, raw_data: dict) -> list[dict]:
        """
        Scrape the accepted taxon's HTML page for synonym records.

        Uses the PHP taxa page (``_scrape_synonyms``) for redundancy: the JSON
        API provides ID/taxonomy resolution while the HTML page provides the
        synonym list.

        Parameters
        ----------
        raw_data : dict
            The dict returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            Raw synonym records in Symbiota's extended column format,
            as produced by ``_scrape_synonyms``.
        """
        accepted_tid = raw_data["accepted_tid"]
        meta = raw_data["meta"]
        taxonomy = {
            k: meta.get(k, "")
            for k in ["Kingdom", "Phylum", "Class", "Family", "Subfamily"]
        }
        return self._scrape_synonyms(accepted_tid, taxonomy)

    def _compile_synonyms(self, synonym_data: list[dict]) -> list[dict]:
        """
        Deduplicate synonym records produced by ``_fetch_synonym_data``.

        Deduplication is performed inside the loop as candidates are collected,
        keyed by the canonical ``"Genus Species"`` string.

        Parameters
        ----------
        synonym_data : list of dict
            Raw synonym records in Symbiota's extended column format.

        Returns
        -------
        list of dict
            Deduplicated synonym records preserving input order.
        """
        candidates = []
        seen: set[str] = set()
        for syn in synonym_data:
            canonical = f"{syn.get('Genus', '')} {syn.get('Species', '')}".strip()
            if canonical and canonical not in seen:
                seen.add(canonical)
                candidates.append(syn)
        return candidates

    # ---------------------------------------------------------
    # Public interface
    # ---------------------------------------------------------

    def get_synonyms(self, name: str) -> pd.DataFrame:
        """
        Return a DataFrame of the queried name and all its synonyms.

        Overrides the base-class method to return a DataFrame rather than
        ``list[dict]`` because Symbiota records carry taxonomy columns
        (Kingdom, Phylum, Class, Family, Subfamily) absent from the standard
        five-key format.

        Parameters
        ----------
        name : str
            Scientific name to search for.

        Returns
        -------
        pandas.DataFrame
            Columns as defined in ``COLUMNS``. Row order:

            1. The queried name.
            2. The accepted name, if the queried name is a synonym.
            3. All other synonyms scraped from the portal, deduplicated.

            Returns an empty DataFrame with the correct columns on any
            error or when the name is not found.

        Notes
        -----
        ``Publication Name`` and ``Publication Year`` are always empty because
        Symbiota portals do not expose publication metadata through the synonym
        list or taxonomy endpoint. ``GBIF Accepted Status`` reflects the
        portal's own accepted/synonym classification.
        """
        if not name or not name.strip():
            return pd.DataFrame(columns=COLUMNS)

        species_name = normalize_query_string(name)

        try:
            raw_data = self._fetch_query_data(species_name)
            tid = raw_data["tid"]
            accepted_tid = raw_data["accepted_tid"]
            meta = raw_data["meta"]
            taxonomy = {
                k: meta.get(k, "")
                for k in ["Kingdom", "Phylum", "Class", "Family", "Subfamily"]
            }
            queried_genus, queried_species = self._split_binomial(species_name)

            records: list[dict] = []
            seen: set[str] = set()

            # Row 1: the queried name itself.
            # Author is left blank when the queried name is a synonym; the accepted
            # row below carries the authoritative author string in that case.
            seen.add(species_name)
            records.append(
                self._build_record(
                    taxonomy,
                    **{
                        "Genus": queried_genus,
                        "Species": queried_species,
                        "Source Species ID": str(tid),
                        "Author": meta.get("author", "")
                        if meta.get("status") == "Accepted"
                        else "",
                        "Source Link": f"{self.base}/taxa/index.php?taxon={tid}",
                        "GBIF Accepted Status": meta.get("status", ""),
                    },
                )
            )

            # Row 2: accepted name, only added when the queried name was a synonym.
            accepted_name = meta.get("accepted_name")
            if accepted_name and accepted_name not in seen:
                seen.add(accepted_name)
                acc_genus, acc_species = self._split_binomial(accepted_name)
                records.append(
                    self._build_record(
                        taxonomy,
                        **{
                            "Genus": acc_genus,
                            "Species": acc_species,
                            "Source Species ID": str(accepted_tid),
                            "Author": meta.get("accepted_author") or "",
                            "Source Link": f"{self.base}/taxa/index.php?taxon={accepted_tid}",
                            "GBIF Accepted Status": "Accepted",
                        },
                    )
                )

            # Remaining rows: compiled synonyms, deduplicated against queried and accepted names.
            for syn in self._compile_synonyms(self._fetch_synonym_data(raw_data)):
                canonical = f"{syn['Genus']} {syn['Species']}".strip()
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    records.append(syn)

            print(
                f"[{self.portal_name}] Synonym lookup complete: {len(records)} record(s) built for '{species_name}'."
            )
            return pd.DataFrame(records, columns=COLUMNS)

        except Exception as e:
            print(
                f"[{self.portal_name}] get_synonyms() failed for '{species_name}': {e}"
            )
            warnings.warn(
                f"{self.portal_name}: get_synonyms() failed for '{species_name}' ({e}); "
                f"returning empty DataFrame.",
                stacklevel=2,
            )
            return pd.DataFrame(columns=COLUMNS)
