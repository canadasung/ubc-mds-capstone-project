"""
Symbiota portal client for taxonomic name and synonym retrieval.

Provides a concrete SpeciesAPI implementation for Symbiota-based portals.
Each portal runs its own instance of the Symbiota software with different 
endpoint paths and response formats. This module abstracts those 
differences and normalizes all output to the predefined schema.
"""


import re
import warnings
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pandas as pd
import requests

from .base import SpeciesAPI
from ..utils.normalize_query_string import normalize_query_string

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
    "Phylum":    (25,  45),
    "Class":     (50,  75),
    "Family":    (130, 155),
    "Subfamily": (155, 170),
}


class SymbiotaAPI(SpeciesAPI):
    """
    API client for a single Symbiota portal instance.

    Attributes
    ----------
    base : str
        Normalized base URL with the trailing slash removed.
    portal_name : str
        Source identifier written to the ``Source Name`` output column.
    """

    # Symbiota portals frequently block default Python user agents to prevent
    # server scraping. Spoofing a standard browser header bypasses basic blocks.
    HEADERS = {"User-Agent": "Mozilla/5.0"}

    # Matches rank abbreviations that indicate an infraspecific taxon to filter them out.
    _INFRASPECIFIC_RE = re.compile(
        r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|subf\.|cv\.|sect\.|subsect\.|ser\.)",
        re.IGNORECASE,
    )

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
            host = urlparse(base_url).netloc   # e.g. "mycoportal.org"
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
        print(f"[{self.portal_name}] GET {endpoint} → HTTP {resp.status_code}")
        if resp.status_code == 403:
            raise RuntimeError(f"403 Forbidden from {self.base}")
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
            return next((rank_index[r] for r in range(lo, hi + 1) if r in rank_index), "")

        return {
            "Kingdom":   str(data.get("kingdomName") or lowest_in_range(10, 15) or ""),
            "Phylum":    lowest_in_range(*_RANK_RANGES["Phylum"]),
            "Class":     lowest_in_range(*_RANK_RANGES["Class"]),
            "Family":    lowest_in_range(*_RANK_RANGES["Family"]),
            "Subfamily": lowest_in_range(*_RANK_RANGES["Subfamily"]),
        }

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
        # primary search endpoint — one returning empty does not mean the other will too.
        got_empty_response = False
        for endpoint in ("api/v2/taxonomy/search", "api/v2/taxonomy"):
            try:
                resp = self._get(endpoint, search_params)
                if not resp.ok:
                    print(f"[{self.portal_name}] '{endpoint}' returned non-2xx; trying next endpoint.")
                    continue
                data = resp.json()
                if isinstance(data, list):
                    data = {"results": data}
                if isinstance(data, dict) and data.get("results"):
                    print(f"[{self.portal_name}] '{endpoint}' succeeded: {len(data['results'])} result(s).")
                    return data
                # Endpoint responded with HTTP 200 but no matching records — record this and keep trying.
                print(f"[{self.portal_name}] '{endpoint}' returned HTTP 200 but no results for '{name}'.")
                got_empty_response = True
            except Exception as e:
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
    # Synonym Scraping Logic
    # ---------------------------------------------------------
    def _get_tid(self, species_name: str) -> int:
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
        # search() always returns a dict or raises — never None.
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
                    print(f"[{self.portal_name}] Found tid={tid} for '{species_name}' via search.")
                    return tid
                except (KeyError, ValueError, TypeError) as e:
                    print(f"[{self.portal_name}] Could not parse tid from search result: {e}")

        # Fallback: autocomplete endpoint when search returned no exact match.
        print(f"[{self.portal_name}] No exact match in search results for '{species_name}'; trying autocomplete.")
        try:
            resp = self._get("taxa/taxonomy/rpc/gettaxasuggest.php", {"term": species_name})
            resp.raise_for_status()
            for item in resp.json():
                label = item.get("label", "")
                if re.match(rf"^{re.escape(species_name)}(\s|$)", label):
                    tid = int(item["id"])
                    print(f"[{self.portal_name}] Found tid={tid} for '{species_name}' via autocomplete.")
                    return tid
            print(f"[{self.portal_name}] Autocomplete returned no match for '{species_name}'.")
        except Exception as e:
            warnings.warn(
                f"{self.portal_name}: autocomplete fallback failed for '{species_name}' ({e}).",
                stacklevel=2,
            )

        raise LookupError(
            f"{self.portal_name}: no taxon ID found for '{species_name}'."
        )

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

        Raises
        ------
        ValueError
            If the API response is not a JSON object, indicating a structural
            change in the portal's response schema.

        Notes
        -----
        When *tid* belongs to a synonym, a second request is made for the
        accepted taxon to obtain its full classification. If that request
        fails, the synonym's own classification is used.

        A ``UserWarning`` is emitted when the response is missing the
        ``"status"`` field, contains an unrecognised status value, or when
        the synonym's ``"accepted"`` block does not include a ``"tid"``.
        In all three cases the function continues with safe defaults rather
        than raising.
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
        author  = data.get("author") or ""

        if status == "synonym":
            accepted = data.get("accepted") or {}
            if not accepted.get("tid"):
                warnings.warn(
                    f"{self.portal_name}: synonym response for tid {tid} is missing "
                    f"'accepted.tid'; the accepted taxon cannot be resolved.",
                    stacklevel=2,
                )
            accepted_tid    = int(accepted.get("tid", tid))
            accepted_name   = accepted.get("scientificName") or accepted.get("sciname") or ""
            accepted_author = accepted.get("scientificNameAuthorship") or ""

            # Re-fetch the accepted taxon to get its full classification array.
            try:
                acc_resp = self._get(f"api/v2/taxonomy/{accepted_tid}", params={})
                acc_resp.raise_for_status()
                taxonomy = self._extract_taxonomy(acc_resp.json())
                print(f"[{self.portal_name}] Classification resolved for accepted tid={accepted_tid}.")
            except Exception as e:
                warnings.warn(
                    f"{self.portal_name}: could not fetch classification for accepted tid "
                    f"{accepted_tid} ({e}); falling back to synonym's own classification.",
                    stacklevel=2,
                )
                print(f"[{self.portal_name}] Using synonym's own classification as fallback for tid={accepted_tid}.")
                taxonomy = self._extract_taxonomy(data)

            print(f"[{self.portal_name}] '{sciname}' is a Synonym; accepted name is '{accepted_name}' (tid={accepted_tid}).")
            return accepted_tid, {
                **taxonomy,
                "sciname":          sciname,
                "author":           author,
                "status":           "Synonym",
                "accepted_tid":     accepted_tid,
                "accepted_name":    accepted_name,
                "accepted_author":  accepted_author,
            }

        taxonomy = self._extract_taxonomy(data)
        print(f"[{self.portal_name}] '{sciname}' is Accepted (tid={tid}).")
        return tid, {
            **taxonomy,
            "sciname":          sciname,
            "author":           author,
            "status":           "Accepted",
            "accepted_tid":     tid,
            "accepted_name":    None,
            "accepted_author":  None,
        }

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

        Notes
        -----
        Uses two passes over the ``synonymDiv`` HTML fragment:

        1. Collect name-to-tid pairs from ``<a href="…?tid=N">`` links.
        2. Extract ``<i>name</i> author`` pairs and look up each tid.

        Infraspecific taxa are excluded.
        """
        resp = self._get("taxa/index.php", {"tid": accepted_tid})
        resp.raise_for_status()

        syn_match = re.search(r'id="synonymDiv"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
        if not syn_match:
            return []

        syn_html = syn_match.group(1)

        # Pass 1: name → tid map from <a href="…?tid=N"> links
        tid_map: dict[str, int] = {}
        for a_match in re.finditer(
            r'<a[^>]*[?&]tid=(\d+)[^>]*>(.*?)</a>', syn_html, re.DOTALL
        ):
            inner_name = re.search(r'<i>([^<]+)</i>', a_match.group(2))
            if inner_name:
                tid_map[inner_name.group(1).strip()] = int(a_match.group(1))

        # Pass 2: <i>name</i> + trailing author text
        records = []
        for match in re.finditer(r"<i>(.*?)</i>([^<]*)", syn_html):
            name   = match.group(1).strip()
            author = re.sub(r"^[,\s]+|[,\s]+$", "", match.group(2).strip())

            if not name or self._INFRASPECIFIC_RE.search(name):
                continue

            genus, species_epithet = self._split_binomial(name)
            syn_tid         = tid_map.get(name)
            src_link        = f"{self.base}/taxa/index.php?taxon={syn_tid}" if syn_tid else ""

            records.append(self._build_record(taxonomy, **{
                "Genus":              genus,
                "Species":            species_epithet,
                "Source Species ID":  str(syn_tid) if syn_tid else "",
                "Author":             author,
                "Source Link":        src_link,
                "GBIF Accepted Status": "Synonym",
            }))

        print(f"[{self.portal_name}] Scraped {len(records)} synonym(s) from taxa page for tid={accepted_tid}.")
        return records

    def synonyms(self, name: str) -> pd.DataFrame:
        """
        Return a DataFrame of the queried name and all its synonyms.

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
            tid = self._get_tid(species_name)
            accepted_tid, meta = self._resolve_accepted_tid(tid)
            taxonomy = {
                k: meta.get(k, "")
                for k in ["Kingdom", "Phylum", "Class", "Family", "Subfamily"]
            }

            queried_genus, queried_species = self._split_binomial(species_name)

            records: list[dict] = []
            seen: set[str] = {species_name}

            # Row 1 — the queried name itself.
            # Author is left blank when the queried name is a synonym; the accepted
            # row below carries the authoritative author string in that case.
            records.append(self._build_record(taxonomy, **{
                "Genus":              queried_genus,
                "Species":            queried_species,
                "Source Species ID":  str(tid),
                "Author":             meta.get("author", "") if meta.get("status") == "Accepted" else "",
                "Source Link":        f"{self.base}/taxa/index.php?taxon={tid}",
                "GBIF Accepted Status": meta.get("status", ""),
            }))

            # Row 2 — accepted name, only added when the queried name was a synonym.
            accepted_name = meta.get("accepted_name")
            if accepted_name and accepted_name not in seen:
                seen.add(accepted_name)
                acc_genus, acc_species = self._split_binomial(accepted_name)
                records.append(self._build_record(taxonomy, **{
                    "Genus":              acc_genus,
                    "Species":            acc_species,
                    "Source Species ID":  str(accepted_tid),
                    "Author":             meta.get("accepted_author") or "",
                    "Source Link":        f"{self.base}/taxa/index.php?taxon={accepted_tid}",
                    "GBIF Accepted Status": "Accepted",
                }))

            # Remaining rows — scraped synonyms, deduplicated
            for syn in self._scrape_synonyms(accepted_tid, taxonomy):
                canonical = f"{syn['Genus']} {syn['Species']}".strip()
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    records.append(syn)

            print(f"[{self.portal_name}] Synonym lookup complete: {len(records)} record(s) built for '{species_name}'.")
            return pd.DataFrame(records, columns=COLUMNS)

        except Exception as e:
            print(f"[{self.portal_name}] synonyms() failed for '{species_name}': {e}")
            warnings.warn(
                f"{self.portal_name}: synonyms() failed for '{species_name}' ({e}); "
                f"returning empty DataFrame.",
                stacklevel=2,
            )
            return pd.DataFrame(columns=COLUMNS)

    # ---------------------------------------------------------
    # Occurrences Logic
    # ---------------------------------------------------------
    def occurrences(self, name: str, limit: int = 20):
        """
        Retrieve occurrence records for a taxon.

        Parameters
        ----------
        name : str
            Scientific name of the species.
        limit : int, optional
            Maximum number of records to return. Default is 20.

        Returns
        -------
        list or dict or xml.etree.ElementTree.Element
            Parsed occurrence data. Returns an empty list when the response
            cannot be parsed.

        Raises
        ------
        RuntimeError
            When the portal returns an HTML page instead of JSON or XML,
            indicating the endpoint is unavailable or the URL is outdated.
        """
        resp = self._get(
            "occurrences/search.php",
            {"taxon": name, "limit": limit, "format": "json"},
        )

        text = resp.text.strip()

        # If response starts with "<" → it's HTML, not JSON
        if text.startswith("<!DOCTYPE html") or text.startswith("<html"):
            # Throw an error so the Aggregator knows the endpoint is broken!
            raise RuntimeError(
                "Endpoint returned an HTML page instead of data. The URL may be outdated."
            )

        # Try JSON
        try:
            return resp.json()
        except ValueError:
            pass

        # Try XML
        try:
            return ET.fromstring(text)
        except ET.ParseError:
            return []

    # ---------------------------------------------------------
    # Occurrences Logic & HTML Scraper
    # ---------------------------------------------------------
    def _scrape_occurrences_html(
        self, html_text: str, query_name: str, limit: int
    ) -> list[dict]:
        """
        Parse occurrence records from a raw HTML portal page.

        This method is a fallback used when the portal occurrence endpoint
        returns an HTML page instead of structured data. It is fragile: any
        change to the portal's HTML layout will cause it to fail silently
        and return an empty list.

        Parameters
        ----------
        html_text : str
            Raw HTML string from the portal occurrence page.
        query_name : str
            Scientific name that was queried, used in warning messages.
        limit : int
            Maximum number of records to return.

        Returns
        -------
        list of dict
            Parsed occurrence records. Returns an empty list on any parsing
            failure or when ``beautifulsoup4`` is not installed.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            warnings.warn(
                "'beautifulsoup4' is not installed; HTML occurrence scrape skipped.",
                stacklevel=2,
            )
            return []

        try:
            soup = BeautifulSoup(html_text, "html.parser")
            records = []

            # Step 1: Locate the data table. (Graceful fail if missing)
            occ_table = soup.find("table")
            if not occ_table:
                warnings.warn(
                    f"{self.portal_name}: no data table found for '{query_name}'; "
                    f"the portal's HTML layout may have changed.",
                    stacklevel=2,
                )
                return []

            # Step 2: Extract column headers. (Graceful fail if missing)
            headers = [th.get_text(strip=True) for th in occ_table.find_all("th")]
            if not headers:
                warnings.warn(
                    f"{self.portal_name}: table headers missing for '{query_name}'; "
                    f"the portal's HTML layout may have changed.",
                    stacklevel=2,
                )
                return []

            # Step 3: Iterate through rows and map to headers
            rows = occ_table.find_all("tr")
            for row in rows[1:]:  # Skip the header row
                cols = row.find_all("td")
                if not cols:
                    continue

                record = {}
                for i, col in enumerate(cols):
                    if i < len(headers):
                        raw_key = headers[i].lower()
                        val = col.get_text(separator=" ", strip=True)
                        record[raw_key] = val

                        # CRITICAL: Artificially inject "scientificName" so the
                        # Streamlit prototype_pipe.py can recognize the occurrence!
                        if (
                            "scientific name" in raw_key
                            or "taxon" in raw_key
                            or "name" in raw_key
                        ):
                            record["scientificName"] = val

                records.append(record)

                # Enforce limit manually since the API URL limit was ignored by the server
                if len(records) >= limit:
                    break

            return records

        except Exception as e:
            warnings.warn(
                f"{self.portal_name}: HTML occurrence parsing failed for '{query_name}' ({e}).",
                stacklevel=2,
            )
            return []
