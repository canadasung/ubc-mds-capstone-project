"""
Index Fungorum API client.

SpeciesAPI implementation for Index Fungorum, the global nomenclatural database
for fungi.

Index Fungorum exposes a legacy ASMX web service (XML over HTTP) rather than a
REST/JSON API. All fetch methods use ``_fetch_text()`` from the base class
because all responses from this service are XML.

Note that this service is notoriously slow and can time out on occasion, so the timeout for all requests is set to 60 seconds. Even so, the service still fails frequently for other reasons (e.g. server-side errors, network issues) in which case the fetch methods will return ``None`` or an empty dict as documented below.
"""

import xml.etree.ElementTree as ET

from .base import SpeciesAPI


class IndexFungorumAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for Index Fungorum.

    Index Fungorum is the global nomenclatural database for fungi. Responses are
    XML so both fetch methods delegate to ``_fetch_text``, which returns a
    parsed ``ET.Element``.
    """

    BASE_URL = "https://www.indexfungorum.org/ixfwebservice/fungus.asmx"

    # Index Fungorum encodes spaces as _x0020_ in its XML element names.
    _TAGS = {
        "name": "NAME_x0020_OF_x0020_FUNGUS",
        "record_id": "RECORD_x0020_NUMBER",
        "current_key": "CURRENT_x0020_NAME_x0020_RECORD_x0020_NUMBER",
        "rank": "INFRASPECIFIC_x0020_RANK",
        "authors": "AUTHORS",
    }

    def _fetch_query_data(self, name: str) -> ET.Element | None:
        """
        Search Index Fungorum for *name* and return the first exact-matching record.

        Queries the ``NameSearch`` endpoint and scans the XML response for a
        case-insensitive exact match on the name field. Returns the matching
        record element so that ``_fetch_synonym_data`` can extract its
        ``CURRENT_NAME_RECORD_NUMBER`` without needing the original query string.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        xml.etree.ElementTree.Element or None
            The first record element whose name field matches *name*, or
            ``None`` if no match is found.
        """
        root = self._fetch_text(
            f"{self.BASE_URL}/NameSearch",
            params={
                "SearchText": name,
                "AnywhereInText": "false",
                "MaxNumber": "50",
            },
            timeout=60,
        )
        if root is None:
            return None
        for record in root.findall("IndexFungorum"):
            rec_name = (record.findtext(self._TAGS["name"]) or "").strip()
            if rec_name.lower() == name.lower():
                return record
        return None

    def _extract_internal_accepted_id(self, raw_data: ET.Element) -> str:
        """
        Extract the accepted name's CurrentKey from a search result record.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            A single ``IndexFungorum`` record element as returned by
            ``_fetch_query_data``.

        Returns
        -------
        str
            The ``CURRENT_NAME_RECORD_NUMBER`` value, or ``""`` if absent.
        """
        return (raw_data.findtext(self._TAGS["current_key"]) or "").strip()

    def _fetch_synonym_data(self, raw_data: ET.Element) -> ET.Element | None:
        """
        Fetch all names sharing the accepted taxon's CurrentKey.

        Extracts the CurrentKey from the query record and queries the
        ``NamesByCurrentKey`` endpoint to retrieve every name (accepted and
        synonyms) associated with that key.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            The record element returned by ``_fetch_query_data``.

        Returns
        -------
        xml.etree.ElementTree.Element or None
            Parsed root element of the ``NamesByCurrentKey`` response, or
            ``None`` on error.
        """
        current_key = self._extract_internal_accepted_id(raw_data)
        if not current_key:
            return None
        return self._fetch_text(
            f"{self.BASE_URL}/NamesByCurrentKey",
            params={"CurrentKey": current_key},
            timeout=60,
        )

    def _compile_synonyms(self, synonym_data: ET.Element) -> list[dict]:
        """
        Convert raw ``NamesByCurrentKey`` XML into pipeline-standard synonym dicts.

        Iterates over ``IndexFungorum`` child elements, keeping only species-level
        records (``INFRASPECIFIC_x0020_RANK == "sp."``). Deduplicates by
        lower-cased name during iteration.

        Parameters
        ----------
        synonym_data : xml.etree.ElementTree.Element
            Parsed root element from the ``NamesByCurrentKey`` response.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_synonym``.
        """
        candidates = []
        seen = set()
        for record in synonym_data.findall("IndexFungorum"):
            syn_name = (record.findtext(self._TAGS["name"]) or "").strip()
            rank = (record.findtext(self._TAGS["rank"]) or "").strip()
            if not syn_name or rank != "sp.":
                continue
            if syn_name.lower() in seen:
                continue
            seen.add(syn_name.lower())
            author = (record.findtext(self._TAGS["authors"]) or "").strip()
            record_id = (record.findtext(self._TAGS["record_id"]) or "").strip()
            candidates.append(
                self._format_synonym(
                    name=syn_name,
                    author=author or "U",
                    api_link=(
                        f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                        if record_id
                        else "U"
                    ),
                )
            )
        return candidates
