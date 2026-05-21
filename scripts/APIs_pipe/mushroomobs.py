"""
scripts/apis_pipe/mushroomobs.py
--------------------------------
Mushroom Observer API v2 client for the UBC MDS species aggregation pipeline.

Mushroom Observer (https://mushroomobserver.org) is a community-driven database
of fungal observations. This module provides two capabilities:

    - **Synonyms**: Fetches historical species-level aliases for a given accepted
      name, filtering out misspellings, "sp." placeholders, and infraspecific taxa
      (varieties, forms, subspecies) so the output matches what other pipeline
      sources (GBIF, Symbiota) return.

    - **Occurrences**: Fetches georeferenced observation records that include at
      least one image, returning Darwin Core-compatible fields plus a
      ``top_3_images`` list used by the frontend gallery.

Usage::

    from scripts.apis_pipe.mushroomobs import MushroomObserverAPI

    api = MushroomObserverAPI()
    synonyms   = api.synonyms("Amanita muscaria")
    occurrences = api.occurrences("Amanita muscaria", limit=20)

Dependencies:
    - requests  (HTTP calls)
    - re        (rank-abbreviation parsing)
    - .base.SpeciesAPI (abstract base class enforced by the pipeline)
"""

import re

import requests

from .base import SpeciesAPI


class MushroomObserverAPI(SpeciesAPI):
    """
    Mushroom Observer API v2 client.

    Implements ``SpeciesAPI`` to supply fungal occurrence records and
    species-level synonyms from the Mushroom Observer community database.

    Attributes:
        BASE_URL (str): Root URL for all API v2 requests.
        HEADERS (dict): HTTP headers sent with every request. The User-Agent
            string is required — the API rejects requests from the default
            ``requests`` agent.
        _RANK_PATTERNS (list[tuple[re.Pattern, str]]): Ordered list of
            (compiled regex, category) pairs used by ``_parse_synonym`` to
            classify infraspecific rank abbreviations. Longer/more-specific
            patterns are listed before shorter ones to avoid false matches
            (e.g. ``subsp.`` before ``s.``).
    """

    BASE_URL = "https://mushroomobserver.org/api2"
    HEADERS = {"User-Agent": "Mozilla/5.0"}

    # Maps rank abbreviations found in MushroomObserver names to category keys.
    # Order matters: longer/more specific patterns must come before shorter ones.
    _RANK_PATTERNS: list[tuple[re.Pattern, str]] = [
        (re.compile(r"\bsubsp\.\s*", re.IGNORECASE), "subspecies"),
        (re.compile(r"\bssp\.\s*", re.IGNORECASE), "subspecies"),
        (re.compile(r"\bs\.\s*", re.IGNORECASE), "subspecies"),
        (re.compile(r"\bvar\.\s*", re.IGNORECASE), "varieties"),
        (re.compile(r"\bv\.\s*", re.IGNORECASE), "varieties"),
        (re.compile(r"\bform\.\s*", re.IGNORECASE), "forms"),
        (re.compile(r"\bfo\.\s*", re.IGNORECASE), "forms"),
        (re.compile(r"\bf\.\s*", re.IGNORECASE), "forms"),
        (re.compile(r"\bsubsect\.\s*", re.IGNORECASE), "subsections"),
        (re.compile(r"\bsect\.\s*", re.IGNORECASE), "sections"),
        (re.compile(r"\bsubgen\.\s*", re.IGNORECASE), "subgenera"),
        (re.compile(r"\bsubg\.\s*", re.IGNORECASE), "subgenera"),
    ]

    def search(self, name: str) -> dict:
        """
        No-op implementation required by ``SpeciesAPI``.

        Mushroom Observer is used exclusively for occurrences and synonym
        look-ups; it is not used as a primary taxonomic backbone. Callers
        should use ``occurrences()`` or ``synonyms()`` directly.

        Args:
            name (str): Ignored.

        Returns:
            dict: Always an empty dict.
        """
        return {}

    def _parse_synonym(self, full_name: str, species_name: str) -> tuple[str, str]:
        """
        Extract the taxonomic rank category and specific epithet from a full name string.

        Iterates through predefined regex patterns to identify infraspecific ranks
        (e.g., subspecies, varieties). If no specific rank is found, it defaults
        to the general "synonyms" category.

        Args:
            full_name (str): The complete taxonomic name string to parse.
            species_name (str): The base species name used to strip out the epithet.

        Returns:
            tuple[str, str]: A tuple containing the category string (e.g., "varieties")
                and the extracted epithet or cleaned name.
        """
        for pattern, category in self._RANK_PATTERNS:
            if pattern.search(full_name):
                return category, pattern.split(full_name)[-1]
        return "synonyms", full_name.removeprefix(species_name).strip() or full_name

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve a filtered list of taxonomic synonyms from Mushroom Observer.

        Queries the API v2 '/names' endpoint. It uses regex-based filtering
        to actively exclude misspellings, vague "sp." records, and infraspecific
        taxa, returning only clean, species-level historical aliases.

        Args:
            name (str): The accepted scientific name to query.

        Returns:
            list[dict]: A list of synonym records formatted for the main aggregator.
                Each dictionary contains 'canonicalName', 'author', 'date',
                'publishedIn', and 'url'. Returns an empty list if the query fails
                or no valid synonyms are found.
        """
        params = {
            "name": name,
            "include_synonyms": "true",
            "detail": "high",
            "format": "json",
        }

        try:
            resp = requests.get(
                f"{self.BASE_URL}/names",
                params=params,
                headers=self.HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Mushroom Observer Synonyms Error: {e}")
            return []

        if data.get("number_of_records", 0) == 0:
            return []

        results_list = []
        seen = {name.lower()}  # Prevent duplicates, starting with the search query

        for result in data.get("results", []):
            for synonym in result.get("synonyms", []):
                full_name = synonym.get("name", "")

                # Skip invalid, duplicate, or vague "sp." names
                if not full_name or full_name.lower() in seen or " sp." in full_name:
                    continue

                # Skip misspellings explicitly flagged by the MO database
                if synonym.get("misspelled", False):
                    continue

                # Filter out varieties/forms using the parser logic
                category, _ = self._parse_synonym(full_name, name)
                if category != "synonyms":
                    continue

                seen.add(full_name.lower())

                # Format to match Symbiota and GBIF pipeline requirements
                results_list.append(
                    {
                        "canonicalName": full_name,
                        "author": synonym.get("author", ""),
                        "date": "",
                        "publishedIn": "",
                        "url": f"https://mushroomobserver.org/name/show_name/{synonym.get('id', '')}",
                    }
                )

        return results_list

    def occurrences(self, name: str, limit: int = 20) -> list[dict]:
        """
        Retrieve observation records with associated images and geolocation data.

        Queries the API v2 '/observations' endpoint with the 'detail=high' flag
        to ensure nested image URLs and GPS coordinates are exposed. It extracts
        up to three primary images per record to support frontend UI galleries.

        Args:
            name (str): The scientific name of the taxon to search for.
            limit (int, optional): The maximum number of occurrence records to
                retrieve. Defaults to 20.

        Returns:
            list[dict]: A list of pipeline-compliant occurrence dictionaries. Each
                record includes standard Darwin Core-like keys (e.g., 'eventDate',
                'decimalLatitude') alongside a custom 'top_3_images' list.
        """
        params = {
            "name": name,
            "has_images": "true",
            "detail": "high",
            "format": "json",
        }

        try:
            resp = requests.get(
                f"{self.BASE_URL}/observations",
                params=params,
                headers=self.HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Mushroom Observer Occurrences Error: {e}")
            return []

        records = []
        # API v2 limits responses. We slice to enforce the pipeline limit.
        for item in data.get("results", [])[:limit]:
            # Extract top 3 image URLs
            images = []
            for img in item.get("primary_image", []) or item.get("images", []):
                if isinstance(img, dict) and img.get("original_url"):
                    images.append(img.get("original_url"))
                    if len(images) == 3:
                        break

            # Extract GPS if available
            location = item.get("location", {})
            lat = location.get("latitude") if isinstance(location, dict) else None
            lng = location.get("longitude") if isinstance(location, dict) else None

            # Build pipeline-compliant occurrence record
            rec = {
                "scientificName": item.get("consensus_name", {}).get("name") or name,
                "eventDate": item.get("date"),
                "decimalLatitude": lat,
                "decimalLongitude": lng,
                "verbatimLocality": location.get("name")
                if isinstance(location, dict)
                else location,
                "top_3_images": images,
                "source": "Mushroom Observer",
                "occurrenceID": f"https://mushroomobserver.org/{item.get('id', '')}",
            }
            records.append(rec)

        return records
