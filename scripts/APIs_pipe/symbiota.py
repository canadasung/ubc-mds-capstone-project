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

import requests

from .base import SpeciesAPI


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

    def __init__(self, base_url: str):
        """
        Initialize the Symbiota API client for a specific portal.

        Args:
            base_url (str): The root API URL for the target Symbiota portal
                (e.g., "https://lichenportal.org/portal/api").
        """
        self.base = base_url.rstrip("/")

    def _get(self, endpoint: str, params: dict):
        """
        Internal helper method to execute HTTP GET requests.

        Includes standard headers to bypass basic bot-blocking and catches
        known Symbiota security firewalls (403 Forbidden).

        Args:
            endpoint (str): The specific API endpoint to append to the base URL
                (e.g., "taxa/taxasearch.php").
            params (dict): URL query parameters.

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
        )
        if resp.status_code == 403:
            raise RuntimeError(f"403 Forbidden from {self.base}")
        return resp

    def search(self, name: str):
        """
        Search for taxonomic information on a specific species.

        Symbiota APIs are historically inconsistent with content types. This
        method attempts to parse the response as JSON first, falling back to
        XML if the portal's specific version does not support JSON.

        Args:
            name (str): The scientific name to search for.

        Returns:
            dict | xml.etree.ElementTree.Element: The parsed response data,
                either as a JSON dictionary or an XML Element tree.
        """
        resp = self._get("taxa/taxasearch.php", {"taxon": name, "format": "json"})
        try:
            return resp.json()
        except ValueError:
            return ET.fromstring(resp.text)

    # ---------------------------------------------------------
    # Synonym Scraping Logic
    # ---------------------------------------------------------
    def _get_tid(self, species_name: str) -> int | None:
        """
        Find the internal taxon ID (tid) for an exact species name match.

        Uses the portal's internal autocomplete search feature to quickly resolve 
        a string name to the database's primary numeric key.

        Args:
            species_name (str): The capitalized scientific name to search for.

        Returns:
            int | None: The internal taxon ID if found, otherwise None.
        """
        resp = self._get("taxa/taxonomy/rpc/gettaxasuggest.php", {"term": species_name})
        resp.raise_for_status()
        for item in resp.json():
            label = item.get("label", "")
            if re.match(rf"^{re.escape(species_name)}(\s|$)", label):
                return int(item["id"])
        return None

    def _resolve_accepted_tid(self, tid: int) -> tuple[int, str | None]:
        """
        Check if the given Taxon ID belongs to an accepted name or an outdated synonym.

        If the ID belongs to a synonym, this method automatically resolves and
        returns the ID of the modern, accepted taxon.

        Args:
            tid (int): The internal taxon ID to check.

        Returns:
            tuple[int, str | None]: A tuple containing the accepted taxon ID
                and the accepted scientific name (if the original was a synonym).
        """
        resp = self._get(f"api/v2/taxonomy/{tid}", params={})
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "synonym":
            accepted = data["accepted"]
            return accepted["tid"], accepted["scientificName"]
        return tid, None

    def _scrape_synonyms(self, accepted_tid: int) -> list[dict]:
        """
        Scrape the HTML taxa page for synonym names and author citations.

        Because Symbiota does not expose synonym endpoints natively, this function
        downloads the raw HTML species profile and uses Regular Expressions to
        extract taxonomy data directly from the 'synonymDiv' element.

        Args:
            accepted_tid (int): The internal ID of the accepted taxon.

        Returns:
            list[dict]: A list of dictionaries containing extracted synonym
                metadata (canonical name, author citation, and direct URL).
        """
        resp = self._get("taxa/index.php", {"tid": accepted_tid})
        resp.raise_for_status()

        syn_match = re.search(r'id="synonymDiv"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
        if not syn_match:
            return []

        names = []
        for match in re.finditer(r"<i>(.*?)</i>([^<]*)", syn_match.group(1)):
            name = match.group(1).strip()
            author = match.group(2).strip()
            author = re.sub(r"^[,\s]+|[,\s]+$", "", author)

            if name and not self._INFRASPECIFIC_RE.search(name):
                names.append(
                    {
                        "canonicalName": name,
                        "author": author,
                        "date": "",
                        "publishedIn": "",
                        "url": f"{self.base.replace('/api', '')}/taxa/index.php?taxon={accepted_tid}",
                    }
                )
        return names

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve taxonomic synonyms by orchestrating a web scrape of the portal.

        Args:
            name (str): The scientific name to search for.

        Returns:
            list[dict]: A list of formatted dictionaries containing the synonym
                data and associated metadata. Returns an empty list if the portal
                blocks the scrape or fails.
        """
        if not name or not name.strip():
            return []

        # Capitalize first letter to match Symbiota's exact stored nomenclature
        species_name = name[0].upper() + name[1:]

        try:
            tid = self._get_tid(species_name)
            if tid is None:
                return []

            accepted_tid, accepted_name = self._resolve_accepted_tid(tid)
            synonyms_data = self._scrape_synonyms(accepted_tid)

            seen = {species_name}
            base_url = (
                f"{self.base.replace('/api', '')}/taxa/index.php?taxon={accepted_tid}"
            )

            # 1. Add the queried name to the top of the list
            results = [
                {
                    "canonicalName": species_name,
                    "author": "",
                    "date": "",
                    "publishedIn": "",
                    "url": base_url,
                }
            ]

            # 2. If the user queried a synonym, explicitly add the accepted name too
            if accepted_name and accepted_name not in seen:
                seen.add(accepted_name)
                results.append(
                    {
                        "canonicalName": accepted_name,
                        "author": "",
                        "date": "",
                        "publishedIn": "",
                        "url": base_url,
                    }
                )

            # 3. Add all scraped synonyms, skipping duplicates
            for syn in synonyms_data:
                if syn["canonicalName"] not in seen:
                    seen.add(syn["canonicalName"])
                    results.append(syn)

            return results

        except Exception as e:
            return []

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
