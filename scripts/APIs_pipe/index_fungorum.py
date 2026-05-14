# scripts/apis_pipe/index_fungorum.py

import xml.etree.ElementTree as ET

import requests

from .base import SpeciesAPI


class IndexFungorumAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for Index Fungorum.

    Index Fungorum is the global nomenclatural database for fungi. Because
    their direct /Synonymy endpoint frequently suffers from 500 Internal Server
    Errors, this client utilizes a robust two-step relational query design:
    1. Resolve the target species name to its internal database ID ('CurrentKey').
    2. Query for all historical names pointing to that specific ID.

    This client automatically parses the legacy XML responses into the
    pipeline's standard JSON-like dictionaries.
    """

    BASE = "https://www.indexfungorum.org/ixfwebservice/fungus.asmx"

    # Index Fungorum encodes spaces as _x0020_ in its XML tags
    _TAGS = {
        "name": "NAME_x0020_OF_x0020_FUNGUS",
        "record_id": "RECORD_x0020_NUMBER",
        "current_key": "CURRENT_x0020_NAME_x0020_RECORD_x0020_NUMBER",
        "rank": "INFRASPECIFIC_x0020_RANK",
        "authors": "AUTHORS",
    }

    def search(self, name: str) -> dict:
        """
        Satisfies the SpeciesAPI abstract base class requirement.
        Verifies if a name exists in the Index Fungorum database.
        """
        current_key = self._get_current_key(name)
        if current_key:
            return {"name": name, "matchType": "EXACT", "key": current_key}
        return {}

    def _parse_xml(self, xml_text: str) -> list[ET.Element]:
        """
        Safely parse raw XML text into ElementTree objects.

        Args:
            xml_text (str): The raw XML response from the ASMX web service.

        Returns:
            list[ET.Element]: A list of parsed 'IndexFungorum' XML record blocks.
                Returns an empty list if parsing fails.
        """
        try:
            root = ET.fromstring(xml_text)
            return root.findall("IndexFungorum")
        except ET.ParseError:
            return []

    def _get_current_key(self, name: str) -> int | None:
        """
        Query the NameSearch endpoint to resolve a species name to its internal ID.

        Args:
            name (str): The scientific name to search for.

        Returns:
            int | None: The integer representing the accepted 'CurrentKey' in the
                database. Returns None if the species is not found.
        """
        try:
            resp = requests.get(f"{self.BASE}/NameSearch", params={"SearchText": name})
            resp.raise_for_status()
        except requests.RequestException:
            return None

        records = self._parse_xml(resp.text)

        for record in records:
            rec_name = (record.findtext(self._TAGS["name"]) or "").strip()

            # Ensure we only grab the key if it's an exact match
            if rec_name.lower() == name.lower():
                key_str = record.findtext(self._TAGS["current_key"])
                if key_str:
                    try:
                        return int(key_str.strip())
                    except ValueError:
                        continue
        return None

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve a clean, pipeline-standard list of synonyms for a fungal name.

        Bypasses the unstable /Synonymy endpoint by mapping the name to its
        CurrentKey, then fetching all records associated with that key. Filters
        out infraspecific taxa to return only species-level ("sp.") synonyms.

        Args:
            name (str): The scientific name of the fungus.

        Returns:
            list[dict]: A list of synonym dictionaries formatted for the pipeline
                (canonicalName, author, date, publishedIn, url).
        """
        # Step 1: Find the internal database ID
        current_key = self._get_current_key(name)
        if not current_key:
            return []

        # Step 2: Ask for all records that share this ID
        try:
            resp = requests.get(
                f"{self.BASE}/NamesByCurrentKey",
                params={"CurrentKey": str(current_key)},
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Index Fungorum Synonyms Error: {e}")
            return []

        records = self._parse_xml(resp.text)
        results = []
        seen = set()

        for record in records:
            syn_name = (record.findtext(self._TAGS["name"]) or "").strip()
            rank = (record.findtext(self._TAGS["rank"]) or "").strip()
            author = (record.findtext(self._TAGS["authors"]) or "").strip()
            record_id = (record.findtext(self._TAGS["record_id"]) or "").strip()

            # Filter for species-level only, and prevent exact duplicates
            if syn_name and rank == "sp." and syn_name.lower() not in seen:
                seen.add(syn_name.lower())

                # Format to strictly match the pipeline standard!
                results.append(
                    {
                        "canonicalName": syn_name,
                        "author": author,
                        "date": "",
                        "publishedIn": "",
                        "url": f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                        if record_id
                        else "",
                    }
                )

        return results

    def occurrences(self, name: str, limit: int = 20) -> list[dict]:
        """
        Retrieve occurrence records for a specific taxon.

        Args:
            name (str): The scientific name of the fungus.
            limit (int, optional): Maximum records to return. Defaults to 20.

        Returns:
            list: Always returns an empty list. Index Fungorum is strictly a
                nomenclatural database detailing the naming of fungi; it does
                not store or expose physical specimen or observational data.
        """
        return []
