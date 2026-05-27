"""
Unified Symbiota API system data retrieval

This module serves as the dedicated connector between the application's data 
aggregation pipeline and Symbiota-based portals (such as MyCoPortal or the Lichen Portal). 
It is a concrete implementation of the `SpeciesAPI` blueprint.

Because every Symbiota portal is hosted independently and their data structures 
are historically inconsistent, this script acts as a specialized translator. It 
routes data requests, handles unexpected web page errors, and includes fallback 
mechanisms to extract data directly from the portal's website when standard 
database queries fail.
"""


import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import pandas as pd
import requests

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
# api/v2/taxonomy/{tid} classification array.  Boundaries are derived from
# observed Symbiota portal responses; the lowest rankid within each range wins.
_RANK_RANGES: dict[str, tuple[int, int]] = {
    "Phylum":    (25,  45),
    "Class":     (50,  75),
    "Family":    (130, 155),
    "Subfamily": (155, 170),
}


class SymbiotaAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for Symbiota-based portals.

    Symbiota is the underlying software for many regional and taxon-specific
    biodiversity portals (e.g., Lichen Portal, MyCoPortal, Bryophyte Portal).
    Because each portal hosts its own instance of the API, this client requires
    a specific base URL upon initialization.
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
        Initialize the Symbiota API client for a specific portal.

        Args:
            base_url (str): The root URL for the target Symbiota portal
                (e.g., ``"https://mycoportal.org/portal"``).
            portal_name (str, optional): Human-readable source name written to
                the "Source Name" DataFrame column (e.g., ``"mycoportal"``).
                If omitted, the first component of the domain is used
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
        Internal helper method to execute HTTP GET requests.

        Includes standard headers to bypass basic bot-blocking and catches
        known Symbiota security firewalls (403 Forbidden).

        Args:
            endpoint (str): The specific API endpoint to append to the base URL
                (e.g., ``"api/v2/taxonomy/search"``).
            params (dict): URL query parameters.
            timeout (int, optional): Request timeout in seconds. Defaults to 30.

        Returns:
            requests.Response: The raw response object from the API.

        Raises:
            RuntimeError: If the portal actively rejects the request (403 status),
                which typically indicates a missing API token or an IP block.
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
        Return a blank record dict pre-populated with every column in COLUMNS.

        Callers overwrite individual fields after calling this so every record
        is guaranteed to carry every column.
        """
        return {col: "" for col in COLUMNS}

    def _extract_taxonomy(self, data: dict) -> dict:
        """
        Extract taxonomy hierarchy fields from a raw ``api/v2/taxonomy/{tid}``
        response.

        The response exposes ``kingdomName`` at the top level and a
        ``classification`` list of parent taxa, each with a ``rankid`` integer
        and a ``scientificName`` string.  Observed Symbiota rankid ranges::

            Phylum 25-45 | Class 50-75 | Family 130-155 | Subfamily 155-170

        The lowest rankid found within each range is used, so the primary rank
        is always preferred over sub-ranks (e.g. Class over Subclass).

        Args:
            data (dict): Parsed JSON from ``api/v2/taxonomy/{tid}``.

        Returns:
            dict: Keys "Kingdom", "Phylum", "Class", "Family", "Subfamily"
                mapped to their string values, or ``""`` if absent.
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
        Search for taxonomic information on a specific species.

        Different Symbiota installations place the v2 search at different paths.
        This method tries them in order before falling back to the legacy PHP
        endpoint, so no per-portal configuration is required:

        1. ``api/v2/taxonomy/search`` — used by portals such as MyCoPortal.
        2. ``api/v2/taxonomy``        — used by portals such as Lichen Portal
                                        and Macroalgae Portal.
        3. ``taxa/taxasearch.php``    — legacy PHP fallback present on all portals.

        All three paths accept the same query parameters (``taxon``, ``type``,
        ``limit``, ``offset``). The response is always normalized to a dict so
        callers never have to handle XML or bare lists.

        Args:
            name (str): The scientific name to search for.

        Returns:
            dict | None: Normalized response dict. List responses are wrapped as
                ``{"results": [...]}``. Returns ``None`` if all three endpoints
                fail or return empty results.
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
        Find the internal taxon ID (tid) for an exact species name match.

        Uses ``search()`` as the primary lookup.  ``search()`` already cascades
        across both v2 REST paths (``api/v2/taxonomy/search`` and
        ``api/v2/taxonomy``) before the PHP fallback, so this method inherits
        full portal coverage automatically.  If ``search()`` returns no usable
        tid, the portal's legacy autocomplete endpoint is tried as a last resort.

        Args:
            species_name (str): The capitalized scientific name to search for.

        Returns:
            int | None: The internal taxon ID if found, otherwise ``None``.
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
        Resolve a taxon ID to its accepted form and extract full taxonomy metadata.

        Calls ``api/v2/taxonomy/{tid}`` to determine whether the given ID belongs
        to an accepted name or a synonym. If it is a synonym, a second API call is
        made for the accepted taxon so its full ``classification`` array is always
        available for ``_extract_taxonomy()``.

        Args:
            tid (int): The internal taxon ID to resolve.

        Returns:
            tuple[int, dict]: A 2-tuple of:

            - The accepted taxon ID (equals ``tid`` when already accepted).
            - A metadata dict with keys ``"Kingdom"``, ``"Phylum"``, ``"Class"``,
              ``"Family"``, ``"Subfamily"``, ``"sciname"``, ``"author"``,
              ``"status"`` (``"Accepted"`` or ``"Synonym"``), ``"accepted_tid"``,
              and ``"accepted_name"`` (``None`` when already accepted).
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

            # Re-fetch the accepted taxon to guarantee its full classification array.
            try:
                acc_resp = self._get(f"api/v2/taxonomy/{accepted_tid}", params={})
                acc_resp.raise_for_status()
                taxonomy = self._extract_taxonomy(acc_resp.json())
            except Exception:
                taxonomy = self._extract_taxonomy(data)

            return accepted_tid, {
                **taxonomy,
                "sciname":       sciname,
                "author":        author,
                "status":        "Synonym",
                "accepted_tid":  accepted_tid,
                "accepted_name": accepted_name,
            }

        taxonomy = self._extract_taxonomy(data)
        return tid, {
            **taxonomy,
            "sciname":       sciname,
            "author":        author,
            "status":        "Accepted",
            "accepted_tid":  tid,
            "accepted_name": None,
        }

    def _scrape_synonyms(self, accepted_tid: int, taxonomy: dict) -> list[dict]:
        """
        Scrape the HTML taxa page for synonym names, authors, and individual tids.

        Because Symbiota does not expose a synonym-list endpoint natively, this
        function downloads the raw HTML species profile and extracts data from the
        ``synonymDiv`` element using a two-pass approach:

        - **Pass 1** — collect ``name → tid`` pairs from ``<a href="…?tid=N">``
          links so each synonym can carry its own ``Source Species ID``.
        - **Pass 2** — extract each ``<i>name</i> author`` pair and look up its
          tid from the map built in Pass 1.

        All records inherit the accepted taxon's taxonomy hierarchy so every
        synonym row has consistent Kingdom / Phylum / Class / Family / Subfamily.

        Args:
            accepted_tid (int): Internal ID of the accepted taxon.
            taxonomy (dict): Taxonomy hierarchy from the accepted taxon applied
                to every synonym record.

        Returns:
            list[dict]: Records keyed by every column in COLUMNS.
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
        Retrieve taxonomic synonyms and return them as a pandas DataFrame.

        Orchestrates the full synonym discovery pipeline:

        1. ``_get_tid()``              — resolve the queried name to its portal tid.
        2. ``_resolve_accepted_tid()`` — follow synonym chains to the accepted taxon
                                         and fetch full taxonomy metadata.
        3. ``_scrape_synonyms()``      — scrape the HTML species page for all
                                         synonyms with their individual tids.

        Row ordering:

        1. The queried name (always first).
        2. The accepted name, if the queried name was itself a synonym.
        3. All scraped synonyms, deduplicated by canonical name.

        Column notes:

        - ``"Publication Name"`` and ``"Publication Year"`` are always ``""``
          because Symbiota portals do not expose publication details through the
          synonym list or the taxonomy API.
        - ``"GBIF Accepted Status"`` reflects the Symbiota portal's own
          accepted / synonym classification, not GBIF's backbone.

        Args:
            name (str): The scientific name to search for.

        Returns:
            pd.DataFrame: DataFrame with columns defined by COLUMNS. Returns an
                empty DataFrame (same columns) on any unrecoverable error.
        """
        if not name or not name.strip():
            return pd.DataFrame(columns=COLUMNS)

        # Capitalize first letter to match Symbiota's stored nomenclature
        species_name = name[0].upper() + name[1:]

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
                    "Author":             "",
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
        Retrieve occurrence records for a specific taxon.

        This method includes extensive error handling to manage Symbiota's
        tendency to return raw HTML error pages instead of valid JSON or XML
        when a query fails or times out.

        Args:
            name (str): The scientific name of the species.
            limit (int, optional): The maximum number of records to return.
                Defaults to 20.

        Returns:
            list | dict | xml.etree.ElementTree.Element: The parsed occurrence
                data. Returns an empty list if the API fails, returns an HTML
                error page, or returns unparseable data.
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
                f"Endpoint returned an HTML webpage instead of data. The URL might be outdated."
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
        =======================================================================
        [WARNING TO FUTURE PROJECT STAKEHOLDERS]
        This is a fragile HTML scraper used as a 'last resort' safety net when
        a Symbiota portal (like MyCoPortal) disables its programmatic API and
        returns a raw visual webpage instead of JSON.

        If the portal administrators redesign their website layout, change
        table class names, or restructure their HTML, THIS FUNCTION WILL FAIL.

        It is intentionally designed with strict 'fail gracefully' mechanisms.
        If the layout changes, it will catch the error, print a warning to the
        terminal, and return an empty list `[]` to prevent the main data
        pipeline from crashing.
        =======================================================================
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
