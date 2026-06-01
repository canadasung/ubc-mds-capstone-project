# scripts/apis_pipe/index_fungorum.py

"""index_fungorum.py — Index Fungorum API client.

Concrete SpeciesAPI implementation for Index Fungorum, the global nomenclatural
database for fungi.

Index Fungorum exposes a legacy ASMX web service (XML over HTTP) rather than a
REST/JSON API. Both fetch methods use ``_fetch_text()`` from the base class
because all responses from this service are XML.

Main entry point: IndexFungorumAPI().synonyms(name)
"""

import xml.etree.ElementTree as ET

from .base import SpeciesAPI


class IndexFungorumAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for Index Fungorum.

    Index Fungorum is the global nomenclatural database for fungi.
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

    def search(self, name: str) -> str:
        """Verify whether a name exists in the Index Fungorum database.

        Satisfies the SpeciesAPI abstract base class requirement.

        Args:
            name (str): The scientific name to search for.

        Returns:
            dict: A match descriptor with 'name', 'matchType', and 'key' if the
                name resolves to a CurrentKey; an empty dict if not found.
        """

        # NOTE: come back to fix this. I don't think I should need XML parsing by default, just need to fix the index fungorum API more..?

        xml_text = self._fetch_text(
            f"{self.BASE}/NameSearch",
            params={
                "SearchText": name,
                "AnywhereInText": "false",  # only search for exact matches in the name field, not in any fields
                "MaxNumber": "50",  # get the top 50 matches, which should ensure we capture the accepted name even if there are many infraspecific records
            },
        )

        root = self._parse_xml(xml_text)

        if root is not None:
            records = root.findall("IndexFungorum")

        else:
            print("Error parsing XML response from Index Fungorum.")
            return ""

        current_key = self._find_current_key(records, name)

        return self._fetch_text(
            f"{self.BASE}/NamesByCurrentKey",
            params={"CurrentKey": str(current_key)},
        )

    # def _parse_xml(self, xml_text: str) -> list[ET.Element]:
    #     """
    #     Safely parse raw XML text into a list of IndexFungorum record elements.

    #     Overrides the base class ``_parse_xml`` to return the IndexFungorum-specific
    #     ``IndexFungorum`` child elements rather than the root element.

    #     Args:
    #         xml_text (str): The raw XML response from the ASMX web service.

    #     Returns:
    #         list[ET.Element]: A list of parsed 'IndexFungorum' XML record blocks.
    #             Returns an empty list if parsing fails.
    #     """
    #     try:
    #         root = ET.fromstring(xml_text)
    #         return root.findall("IndexFungorum")
    #     except ET.ParseError:
    #         return []

    def _fetch_name_search(self, name: str) -> str:
        """
        Fetch raw XML from the NameSearch endpoint for a given species name.

        Args:
            name (str): The scientific name to search for.

        Returns:
            str: Raw XML response text, or ``""`` on request failure.
        """
        return self._fetch_text(
            f"{self.BASE}/NameSearch",
            params={
                "SearchText": name,
                "AnywhereInText": "false",  # only search for exact matches in the name field, not in any fields
                "MaxNumber": "50",  # get the top 50 matches, which should ensure we capture the accepted name even if there are many infraspecific records
            },
        )

    def _find_current_key(self, records: list[ET.Element], name: str) -> int | None:
        """
        Search parsed IndexFungorum records for the CurrentKey matching *name*.

        Performs a case-insensitive exact match on the name field and returns
        the integer CurrentKey of the first matching record.

        Args:
            records (list[ET.Element]): Parsed ``IndexFungorum`` XML record elements.
            name (str): The scientific name to match against.

        Returns:
            int | None: The CurrentKey integer, or ``None`` if not found.
        """
        for record in records:
            rec_name = (record.findtext(self._TAGS["name"]) or "").strip()
            if rec_name.lower() == name.lower():
                key_str = record.findtext(self._TAGS["current_key"])
                if key_str:
                    try:
                        return int(key_str.strip())
                    except ValueError:
                        continue
        return None

    def _extract_internal_id(self, name: str) -> int | None:
        """
        Resolve a species name to its Index Fungorum internal CurrentKey ID.

        Args:
            name (str): The scientific name to search for.

        Returns:
            int | None: The integer CurrentKey, or None if the species is not found.
        """
        xml_text = self._fetch_name_search(name)
        if not xml_text:
            return None
        records = self._parse_xml(xml_text)
        return self._find_current_key(records, name)

    def _fetch_names_by_key(self, current_key: int) -> str:
        """
        Fetch raw XML for all names sharing a given CurrentKey.

        Args:
            current_key (int): The Index Fungorum CurrentKey to look up.

        Returns:
            str: Raw XML response text, or ``""`` on request failure.
        """
        return self._fetch_text(
            f"{self.BASE}/NamesByCurrentKey",
            params={"CurrentKey": str(current_key)},
        )

    def _synonyms(self, records: list[ET.Element], query_name: str) -> list[dict]:
        """
        Convert parsed IndexFungorum XML records into pipeline-standard synonym dicts.

        Filters to species-level records only (``rank == "sp."``), then builds
        and deduplicates the output list.

        Args:
            records (list[ET.Element]): Parsed ``IndexFungorum`` XML record elements.
            query_name (str): The original query name, used to seed deduplication.

        Returns:
            list[dict]: Pipeline-standard synonym records.
        """
        candidates = []
        for record in records:
            syn_name = (record.findtext(self._TAGS["name"]) or "").strip()
            rank = (record.findtext(self._TAGS["rank"]) or "").strip()
            author = (record.findtext(self._TAGS["authors"]) or "").strip()
            record_id = (record.findtext(self._TAGS["record_id"]) or "").strip()

            if syn_name and rank == "sp.":
                candidates.append(
                    self._format_synonym(
                        name=syn_name,
                        author=author,
                        api_link=(
                            f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                            if record_id
                            else ""
                        ),
                    )
                )
        return self._deduplicate_synonyms(candidates, seed={query_name.lower()})

    def get_synonyms(self, name: str) -> list[dict]:
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
        current_key = self._extract_internal_id(name)
        if not current_key:
            return []

        xml_text = self._fetch_names_by_key(current_key)
        if not xml_text:
            return []

        records = self.search(name)
        return self._synonyms(records, query_name=name)
