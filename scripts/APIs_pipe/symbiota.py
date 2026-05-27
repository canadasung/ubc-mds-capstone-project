"""
Symbiota portal client for taxonomic name and synonym retrieval.

Provides a concrete SpeciesAPI implementation for Symbiota-based portals.
Each portal runs its own instance of the Symbiota software with different 
endpoint paths and response formats. This module abstracts those 
differences and normalizes all output to the predefined schema.
"""


import re
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
        """
        resp = requests.get(
            f"{self.base}/{endpoint}",
            params=params,
            headers=self.HEADERS,
            timeout=timeout,
        )
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
            for rid in range(lo, hi + 1):
                if rid in rank_index:
                    return rank_index[rid]
            return ""

        return {
            "Kingdom":   str(data.get("kingdomName") or lowest_in_range(10, 15) or ""),
            "Phylum":    lowest_in_range(*_RANK_RANGES["Phylum"]),
            "Class":     lowest_in_range(*_RANK_RANGES["Class"]),
            "Family":    lowest_in_range(*_RANK_RANGES["Family"]),
            "Subfamily": lowest_in_range(*_RANK_RANGES["Subfamily"]),
        }

    def search(self, name: str) -> dict | None:
        """
        Search for a taxon by scientific name.

        Tries three endpoints in order, stopping at the first successful response:

        1. ``api/v2/taxonomy/search``: primary endpoint (e.g. MyCoPortal).
        2. ``api/v2/taxonomy``: alternate path (e.g. Lichen Portal and others).
        3. ``taxa/taxasearch.php``: legacy fallback present on all portals.

        Parameters
        ----------
        name : str
            Scientific name to search for.

        Returns
        -------
        dict or None
            Normalized response. List responses are wrapped as
            ``{"results": [...]}``. Returns ``None`` when all three endpoints
            fail or return empty data.
        """
        search_params = {"taxon": name, "type": "EXACT", "limit": 100, "offset": 0}

        # Primary attempt 1: /api/v2/taxonomy/search  (e.g. MyCoPortal)
        # Primary attempt 2: /api/v2/taxonomy          (e.g. Lichen Portal, Macroalgae Portal)
        for endpoint in ("api/v2/taxonomy/search", "api/v2/taxonomy"):
            try:
                resp = self._get(endpoint, search_params)
                if resp.ok:
                    data = resp.json()
                    if isinstance(data, list):
                        data = {"results": data}
                    if data:
                        return data
            except Exception:
                continue

        # Fallback: legacy PHP endpoint present on all Symbiota installations
        try:
            resp = self._get("taxa/taxasearch.php", {"taxon": name, "format": "json"})
            try:
                result = resp.json()
                if isinstance(result, list):
                    result = {"results": result}
                return result or None
            except ValueError:
                root = ET.fromstring(resp.text)
                return {"xml_text": ET.tostring(root, encoding="unicode")}
        except Exception:
            pass

        return None

    # ---------------------------------------------------------
    # Synonym Scraping Logic
    # ---------------------------------------------------------
    def _get_tid(self, species_name: str) -> int | None:
        """
        Return the internal taxon ID for an exact name match.

        Parameters
        ----------
        species_name : str
            Scientific name to look up.

        Returns
        -------
        int or None
            Internal taxon ID, or ``None`` if not found.

        Notes
        -----
        Uses ``search()`` as the primary lookup. If no exact match is found,
        falls back to the autocomplete endpoint
        ``taxa/taxonomy/rpc/gettaxasuggest.php``.
        """
        # Primary: extract tid from search() results
        data = self.search(species_name)
        if data:
            for item in data.get("results", []):
                sciname = (
                    item.get("sciname")
                    or item.get("scientificName")
                    or item.get("taxon", "")
                )
                if re.match(rf"^{re.escape(species_name)}\s*$", sciname, re.IGNORECASE):
                    try:
                        return int(item["tid"])
                    except (KeyError, ValueError, TypeError):
                        pass

        # Fallback: legacy autocomplete endpoint
        try:
            resp = self._get("taxa/taxonomy/rpc/gettaxasuggest.php", {"term": species_name})
            resp.raise_for_status()
            for item in resp.json():
                label = item.get("label", "")
                if re.match(rf"^{re.escape(species_name)}(\s|$)", label):
                    return int(item["id"])
        except Exception:
            pass

        return None

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

        Notes
        -----
        When *tid* belongs to a synonym, a second request is made for the
        accepted taxon to obtain its full classification. If that request
        fails, the synonym's own classification is used.
        """
        resp = self._get(f"api/v2/taxonomy/{tid}", params={})
        resp.raise_for_status()
        data = resp.json()

        sciname = data.get("scientificName") or data.get("sciname") or ""
        author  = data.get("author") or ""

        if data.get("status") == "synonym":
            accepted      = data.get("accepted", {})
            accepted_tid  = int(accepted.get("tid", tid))
            accepted_name = accepted.get("scientificName") or accepted.get("sciname") or ""

            # Re-fetch the accepted taxon to get its full classification and author.
            try:
                acc_resp = self._get(f"api/v2/taxonomy/{accepted_tid}", params={})
                acc_resp.raise_for_status()
                acc_data = acc_resp.json()
                taxonomy = self._extract_taxonomy(acc_data)
                accepted_author = acc_data.get("author") or ""
            except Exception:
                taxonomy = self._extract_taxonomy(data)
                accepted_author = ""

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

            parts           = name.split()
            genus           = parts[0] if parts else ""
            species_epithet = parts[1] if len(parts) > 1 else ""
            syn_tid         = tid_map.get(name)
            src_link        = f"{self.base}/taxa/index.php?taxon={syn_tid}" if syn_tid else ""

            records.append({
                **self._empty_record(),
                **taxonomy,
                "Source Name":        self.portal_name,
                "Genus":              genus,
                "Species":            species_epithet,
                "Source Species ID":  str(syn_tid) if syn_tid else "",
                "Author":             author,
                "Publication Name":   "",
                "Publication Year":   "",
                "Source Link":        src_link,
                "GBIF Accepted Status": "Synonym",
            })

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
            if tid is None:
                return pd.DataFrame(columns=COLUMNS)

            accepted_tid, meta = self._resolve_accepted_tid(tid)
            taxonomy = {
                k: meta.get(k, "")
                for k in ["Kingdom", "Phylum", "Class", "Family", "Subfamily"]
            }

            parts           = species_name.split()
            queried_genus   = parts[0] if parts else ""
            queried_species = parts[1] if len(parts) > 1 else ""

            records: list[dict] = []
            seen: set[str] = {species_name}

            # Row 1 — the queried name itself
            records.append({
                **self._empty_record(),
                **taxonomy,
                "Source Name":        self.portal_name,
                "Genus":              queried_genus,
                "Species":            queried_species,
                "Source Species ID":  str(tid),
                # Author only populated when this IS the accepted name; for a
                # synonym the accepted row below is the authoritative record.
                "Author":             meta.get("author", "") if meta.get("status") == "Accepted" else "",
                "Publication Name":   "",
                "Publication Year":   "",
                "Source Link":        f"{self.base}/taxa/index.php?taxon={tid}",
                "GBIF Accepted Status": meta.get("status", ""),
            })

            # Row 2 — accepted name when the queried name was a synonym
            accepted_name = meta.get("accepted_name")
            if accepted_name and accepted_name not in seen:
                seen.add(accepted_name)
                acc_parts = accepted_name.split()
                records.append({
                    **self._empty_record(),
                    **taxonomy,
                    "Source Name":        self.portal_name,
                    "Genus":              acc_parts[0] if acc_parts else "",
                    "Species":            acc_parts[1] if len(acc_parts) > 1 else "",
                    "Source Species ID":  str(accepted_tid),
                    "Author":             meta.get("accepted_author") or "",
                    "Publication Name":   "",
                    "Publication Year":   "",
                    "Source Link":        f"{self.base}/taxa/index.php?taxon={accepted_tid}",
                    "GBIF Accepted Status": "Accepted",
                })

            # Remaining rows — scraped synonyms, deduplicated
            for syn in self._scrape_synonyms(accepted_tid, taxonomy):
                canonical = f"{syn['Genus']} {syn['Species']}".strip()
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    records.append(syn)

            return pd.DataFrame(records, columns=COLUMNS)

        except Exception:
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
            print(
                "Scraper Warning: 'beautifulsoup4' is not installed. Skipping HTML scrape."
            )
            return []

        try:
            soup = BeautifulSoup(html_text, "html.parser")
            records = []

            # Step 1: Locate the data table. (Graceful fail if missing)
            occ_table = soup.find("table")
            if not occ_table:
                print(
                    f"Scraper Warning ({self.base}): No data table found for '{query_name}'. Layout may have changed."
                )
                return []

            # Step 2: Extract column headers. (Graceful fail if missing)
            headers = [th.get_text(strip=True) for th in occ_table.find_all("th")]
            if not headers:
                print(
                    f"Scraper Warning ({self.base}): Table headers missing. Layout may have changed."
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
            # Catch-all graceful failure for entirely unexpected HTML anomalies
            print(
                f"Scraper Warning ({self.base}): HTML parsing failed gracefully. Error: {e}"
            )
            return []
