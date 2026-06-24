"""
Index Fungorum API client.

Index Fungorum is the global nomenclatural database for fungi, maintained by
the Royal Botanic Gardens Kew, CAB International, and the Landcare Research
Institute.  It exposes a legacy ASMX web service (XML over HTTP) rather than a
REST/JSON API; all responses are parsed as ``ET.Element`` via ``_fetch_XML``.
The service is notoriously slow and can time out, so all requests use a 60-
second timeout.

Documentation
-------------
http://www.indexfungorum.org/ixfwebservice/fungus.asmx

Fields implemented
------------------
- author: both rows
- publication_year: both rows
- original_source: both rows
- status: both rows
- api_link: both rows
"""

import xml.etree.ElementTree as ET

from scripts.config import INDEX_FUNGORUM_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class IndexFungorumAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for Index Fungorum.

    All responses are XML; fetch methods delegate to ``_fetch_XML``, which
    returns a parsed ``ET.Element``.
    """

    BASE_URL = INDEX_FUNGORUM_PORTAL.base_url

    _TIMEOUT: int = 60

    # Index Fungorum encodes spaces as _x0020_ in its XML element names.
    _TAGS = {
        "name": "NAME_x0020_OF_x0020_FUNGUS",
        "record_id": "RECORD_x0020_NUMBER",
        "current_key": "CURRENT_x0020_NAME_x0020_RECORD_x0020_NUMBER",
        "rank": "INFRASPECIFIC_x0020_RANK",
        "authors": "AUTHORS",
        "year": "YEAR_x0020_OF_x0020_PUBLICATION",
        "original_source": "PUBLISHED_x0020_LIST_x0020_REFERENCE",
    }

    def _fetch_query_data(self, name: str) -> ET.Element:
        """
        Search Index Fungorum for *name* and return the first exact-matching record element.

        Queries ``NameSearch`` and scans the XML response for a case-insensitive
        exact match on the name field.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        xml.etree.ElementTree.Element
            The first ``IndexFungorum`` record element whose name matches *name*,
            or an empty element if no match is found.
        """
        root = self._fetch_XML(
            f"{self.BASE_URL}/NameSearch",
            params={
                "SearchText": name,
                "AnywhereInText": "false",
                "MaxNumber": "50",
            },
            timeout=self._TIMEOUT,
        )
        if root is None:
            return ET.Element("empty")
        for record in root.findall("IndexFungorum"):
            rec_name = normalize_query_string(
                (record.findtext(self._TAGS["name"]) or "").strip()
            )
            if rec_name == name:
                return record
        return ET.Element("empty")

    def _extract_internal_id(self, raw_data: ET.Element) -> str:
        """
        Extract the record ID from an ``IndexFungorum`` XML element.

        Reads the field mapped by ``_TAGS["record_id"]``
        (``RECORD_x0020_NUMBER``).

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            A single ``IndexFungorum`` record element.

        Returns
        -------
        str
            The record number value, or ``""`` if the element is absent.
        """
        return (raw_data.findtext(self._TAGS["record_id"]) or "").strip()

    def _extract_internal_accepted_id(self, raw_data: ET.Element) -> str:
        """
        Extract the current-name key from a record or ``NamesByCurrentKey`` root.

        Reads the field mapped by ``_TAGS["current_key"]``
        (``CURRENT_x0020_NAME_x0020_RECORD_x0020_NUMBER``).  All
        ``IndexFungorum`` children in a ``NamesByCurrentKey`` response share the
        same value, so reading the first is sufficient.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            A single ``IndexFungorum`` element or the root element of a
            ``NamesByCurrentKey`` response.

        Returns
        -------
        str
            The ``_TAGS["current_key"]`` field value, or ``""`` if absent.
        """
        # When called from _fetch_synonym_data, raw_data is a single IndexFungorum
        # record element. When called from the compile methods, it is the
        # NamesByCurrentKey root element containing IndexFungorum children.
        record = (
            raw_data
            if raw_data.tag == "IndexFungorum"
            else raw_data.find("IndexFungorum")
        )
        if record is None:
            return ""
        return (record.findtext(self._TAGS["current_key"]) or "").strip()

    def _fetch_synonym_data(self, raw_data: ET.Element) -> ET.Element:
        """
        Fetch all names sharing the accepted taxon's CurrentKey from ``NamesByCurrentKey``.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            The record element returned by ``_fetch_query_data``.

        Returns
        -------
        xml.etree.ElementTree.Element
            Parsed root element of the ``NamesByCurrentKey`` response, or an
            empty element on error.
        """
        current_key = self._extract_internal_accepted_id(raw_data)
        if not current_key:
            return ET.Element("empty")
        return self._fetch_XML(
            f"{self.BASE_URL}/NamesByCurrentKey",
            params={"CurrentKey": current_key},
            timeout=self._TIMEOUT,
        )

    def _fetch_accepted_data(
        self, raw_data: ET.Element, synonym_data: ET.Element
    ) -> ET.Element:
        """
        Return *synonym_data* directly.

        The ``NamesByCurrentKey`` response already contains the accepted name
        record alongside all synonyms, so no additional fetch is needed.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            The record element returned by ``_fetch_query_data`` (unused here).
        synonym_data : xml.etree.ElementTree.Element
            Parsed root element from the ``NamesByCurrentKey`` response.

        Returns
        -------
        xml.etree.ElementTree.Element
            The same ``synonym_data`` element passed in.
        """
        return synonym_data

    def _compile_synonyms(self, synonym_data: ET.Element) -> list[dict]:
        """
        Convert raw ``NamesByCurrentKey`` XML into pipeline-standard synonym dicts.

        Keeps only species-level records (``_TAGS["rank"] == "sp."``),
        skips the accepted name record, and deduplicates by name.

        Parameters
        ----------
        synonym_data : xml.etree.ElementTree.Element
            Parsed root element from the ``NamesByCurrentKey`` response.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
        """
        current_name_record = self._extract_internal_accepted_id(synonym_data)
        candidates = []
        seen = set()
        for record in synonym_data.findall("IndexFungorum"):
            syn_name = normalize_query_string(
                (record.findtext(self._TAGS["name"]) or "").strip()
            )
            if not syn_name or syn_name in seen:
                continue
            # remove names with rank != "sp.", which indicates collection-level annotation (e.g. "Amanita sp."), not a synonym
            rank = (record.findtext(self._TAGS["rank"]) or "").strip()
            if rank != "sp.":
                continue
            record_id = self._extract_internal_id(record)
            if record_id == current_name_record:
                continue  # accepted name — handled by _compile_accepted
            seen.add(syn_name)
            genus, species = self._extract_genus_species(syn_name)
            candidates.append(
                self._format_row(
                    api_name=INDEX_FUNGORUM_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=record_id,
                    author=(record.findtext(self._TAGS["authors"]) or "").strip(),
                    publication_year=(
                        record.findtext(self._TAGS["year"]) or ""
                    ).strip(),
                    original_source=(
                        record.findtext(self._TAGS["original_source"]) or ""
                    ).strip(),
                    status="Synonym",
                    api_link=(
                        f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                        if record_id
                        else ""
                    ),
                )
            )
        return candidates

    def _compile_accepted(self, accepted_data: ET.Element) -> list[dict]:
        """
        Extract the accepted name record from the ``NamesByCurrentKey`` response.

        Finds the record whose ``RECORD_NUMBER`` equals
        ``CURRENT_NAME_RECORD_NUMBER`` and returns it as a single row with
        ``status="Accepted"``.

        Parameters
        ----------
        accepted_data : xml.etree.ElementTree.Element
            Parsed root element from the ``NamesByCurrentKey`` response.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if not found.
        """
        current_name_record = self._extract_internal_accepted_id(accepted_data)
        for record in accepted_data.findall("IndexFungorum"):
            record_id = self._extract_internal_id(record)
            if record_id != current_name_record:
                continue
            syn_name = normalize_query_string(
                (record.findtext(self._TAGS["name"]) or "").strip()
            )
            if not syn_name:
                return []
            genus, species = self._extract_genus_species(syn_name)
            return [
                self._format_row(
                    api_name=INDEX_FUNGORUM_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=record_id,
                    author=(record.findtext(self._TAGS["authors"]) or "").strip(),
                    publication_year=(
                        record.findtext(self._TAGS["year"]) or ""
                    ).strip(),
                    original_source=(
                        record.findtext(self._TAGS["original_source"]) or ""
                    ).strip(),
                    status="Accepted",
                    api_link=(
                        f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                        if record_id
                        else ""
                    ),
                )
            ]
        return []
