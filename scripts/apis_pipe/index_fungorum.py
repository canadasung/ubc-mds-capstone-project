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

from scripts.config import INDEX_FUNGORUM_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class IndexFungorumAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for Index Fungorum.

    Index Fungorum is the global nomenclatural database for fungi. Responses are
    XML so both fetch methods delegate to ``_fetch_text``, which returns a
    parsed ``ET.Element``.
    """

    BASE_URL = INDEX_FUNGORUM_PORTAL.base_url

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
        root = self._fetch_XML(
            f"{self.BASE_URL}/NameSearch",
            params={
                "SearchText": name,
                "AnywhereInText": "false",
                "MaxNumber": "50",
            },
            timeout=60,
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
        Extract the record number from an ``IndexFungorum`` XML record element.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            A single ``IndexFungorum`` record element.

        Returns
        -------
        str
            The ``RECORD_NUMBER`` value, or ``""`` if absent.
        """
        return (raw_data.findtext(self._TAGS["record_id"]) or "").strip()

    def _extract_internal_accepted_id(self, raw_data: ET.Element) -> str:
        """
        Extract the accepted name's record number from a ``NamesByCurrentKey`` root element.

        Every ``IndexFungorum`` child in the dataset shares the same
        ``CURRENT_NAME_RECORD_NUMBER``, so reading from the first record is sufficient.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            Root element of the ``NamesByCurrentKey`` response (a ``NewDataSet``
            containing ``IndexFungorum`` children).

        Returns
        -------
        str
            The ``CURRENT_NAME_RECORD_NUMBER`` value, or ``""`` if absent.
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
            return ET.Element("empty")
        return self._fetch_XML(
            f"{self.BASE_URL}/NamesByCurrentKey",
            params={"CurrentKey": current_key},
            timeout=60,
        )

    def _fetch_synonym_search_term_data(
        self, raw_data: ET.Element, synonym_data: ET.Element
    ) -> ET.Element:
        """
        Return ``synonym_data`` directly.

        The ``NamesByCurrentKey`` response already contains the accepted name
        record alongside all synonyms. Passing it through lets
        ``_compile_synonym_search_term`` find and compile the accepted name
        without an additional fetch.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            The record element returned by ``_fetch_query_data``.
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

        Iterates over ``IndexFungorum`` child elements, keeping only species-level
        records (``INFRASPECIFIC_x0020_RANK == "sp."``). Skips the accepted name
        record (handled by ``_compile_synonym_search_term``). Deduplicates by
        lower-cased name during iteration.

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
                continue  # accepted name — handled by _compile_synonym_search_term
            seen.add(syn_name)
            genus, species = self._extract_genus_species(syn_name)
            author = (record.findtext(self._TAGS["authors"]) or "").strip()
            year = (record.findtext(self._TAGS["year"]) or "").strip()
            original_source = (
                record.findtext(self._TAGS["original_source"]) or ""
            ).strip()
            candidates.append(
                self._format_row(
                    api_name=INDEX_FUNGORUM_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=record_id,
                    author=author,
                    publication_year=year,
                    original_source=original_source,
                    status="Synonym",
                    api_link=(
                        f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                        if record_id
                        else ""
                    ),
                )
            )
        return candidates

    def _compile_synonym_search_term(
        self, synonym_search_term_data: ET.Element
    ) -> list[dict]:
        """
        Extract the accepted name record from the ``NamesByCurrentKey`` response.

        Finds the record whose ``RECORD_NUMBER`` matches
        ``CURRENT_NAME_RECORD_NUMBER`` (i.e. the accepted name) and returns it
        as a single pipeline-standard row with ``status="Accepted"``.

        Parameters
        ----------
        synonym_search_term_data : xml.etree.ElementTree.Element
            Parsed root element from the ``NamesByCurrentKey`` response (same
            element passed through by ``_fetch_synonym_search_term_data``).

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if not found.
        """
        current_name_record = self._extract_internal_accepted_id(
            synonym_search_term_data
        )
        for record in synonym_search_term_data.findall("IndexFungorum"):
            record_id = self._extract_internal_id(record)
            if record_id != current_name_record:
                continue
            syn_name = normalize_query_string(
                (record.findtext(self._TAGS["name"]) or "").strip()
            )
            if not syn_name:
                return []
            genus, species = self._extract_genus_species(syn_name)
            author = (record.findtext(self._TAGS["authors"]) or "").strip()
            year = (record.findtext(self._TAGS["year"]) or "").strip()
            original_source = (
                record.findtext(self._TAGS["original_source"]) or ""
            ).strip()
            return [
                self._format_row(
                    api_name=INDEX_FUNGORUM_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=record_id,
                    author=author,
                    publication_year=year,
                    original_source=original_source,
                    status="Accepted",
                    api_link=(
                        f"https://www.indexfungorum.org/Names/NamesRecord.asp?RecordID={record_id}"
                        if record_id
                        else ""
                    ),
                )
            ]
        return []
