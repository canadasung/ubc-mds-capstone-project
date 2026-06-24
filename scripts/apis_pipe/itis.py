"""
ITIS API client.

ITIS (Integrated Taxonomic Information System) is an authoritative database of
biological names for plants, animals, fungi, and microbes, maintained by a
partnership of US federal agencies.  This client uses the ITIS JSON web service
to resolve names by TSN (Taxonomic Serial Number) and retrieve synonym lists,
publication data, and full taxonomic hierarchy.

Unlike most API clients in this pipeline, which make two or three fetch calls
per query, ITIS requires at least ``4 + N`` calls per lookup — where N is the
number of synonyms.  This is because ITIS exposes data through small, specific endpoints. In particular, we call ``getITISTermsFromScientificName`` to get the TSN for the search,
``getAcceptedNamesFromTSN`` to get the accepted name TSN if the initial search is not accepted,
``getSynonymNamesFromTSN`` to get the list of synonyms for the accepted name, ``getFullHierarchyFromTSN`` for the taxonomic
hierarchy, and then ``getFullRecordFromTSN`` for the accepted name and each synonym name
``getFullRecordFromTSN``. To accommodate this,
``ITISAPI`` overrides ``get_synonyms`` with a custom orchestrator so that most fetch methods (besides the initial ``_fetch_query_data()``) can take in the accepted_id, rather than passing the raw data through. Note that as a result, ITIS may be extremely slow even if the endpoints are all working properly.

Documentation
-------------
https://www.itis.gov/ws_description.html

Fields implemented
------------------
- Taxonomy (kingdom → subfamily): accepted name row only
- author: both rows
- publication_year: both rows
- original_source: both rows
- status: both rows
- api_link: both rows
"""

import re

import pandas as pd

from scripts.config import ITIS_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.schema import empty_synonym_table

from .base import SpeciesAPI


class ITISAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the ITIS JSON web service.
    """

    BASE_URL = ITIS_PORTAL.base_url

    _TIMEOUT: int = 60

    _AUTHOR_YEAR_RE: re.Pattern = re.compile(r"(?<!\()\b(\d{4})\b(?!\))")

    def _fetch_query_data(self, name: str) -> dict:
        """
        Search the ITIS database for *name* via ``getITISTermsFromScientificName``.

        The endpoint performs a prefix search; results are filtered to the
        first exact case-insensitive match on ``scientificName``.

        Parameters
        ----------
        name : str
            The scientific name to search for (e.g. ``"Danaus plexippus"``).

        Returns
        -------
        dict
            The first exactly matching ITIS term record, or ``{}`` if no
            exact match is found.
        """
        data = self._fetch_JSON(
            f"{self.BASE_URL}/getITISTermsFromScientificName",
            params={"srchKey": name},
            timeout=self._TIMEOUT,
        )
        terms = data.get("itisTerms")
        if terms is None:  # TODO: add error
            return {}

        exact = next(
            (
                t
                for t in terms
                if t and normalize_query_string(t.get("scientificName") or "") == name
            ),
            None,
        )
        return exact if exact is not None else {}  # TODO: add error

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the ITIS Taxonomic Serial Number (TSN) from any ITIS record.

        Reads the ``"tsn"`` key, which is present on term records (from
        ``getITISTermsFromScientificName``), synonym list entries (from
        ``getSynonymNamesFromTSN``), and full records (from
        ``getFullRecordFromTSN``).

        Parameters
        ----------
        raw_data : dict
            Any ITIS record containing a ``"tsn"`` key.

        Returns
        -------
        str
            The TSN as a string.

        Raises
        ------
        LookupError
            When no ``"tsn"`` key is present in the record.
        """
        tsn = raw_data.get("tsn")
        if tsn is None:
            raise LookupError(
                f"{type(self).__name__} error: could not extract TSN from search result."
            )
        return str(tsn)

    def _fetch_internal_accepted_id_data(self, tsn: str) -> list:
        """
        Fetch accepted name records for a synonym TSN from ``getAcceptedNamesFromTSN``.

        Only called when ``_extract_internal_accepted_id`` determines that the
        queried name is not accepted.

        Parameters
        ----------
        tsn : str
            The TSN of the non-accepted (synonym) name to resolve.

        Returns
        -------
        list
            Filtered list of accepted name records, or ``[]`` on error or if
            no accepted names are found.
        """
        data = self._fetch_JSON(
            f"{self.BASE_URL}/getAcceptedNamesFromTSN",
            params={"tsn": tsn},
            timeout=self._TIMEOUT,
        )
        return [n for n in (data.get("acceptedNames") or []) if n]

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Resolve and return the accepted TSN for the query record.

        If the record's ``nameUsage`` indicates it is not accepted (``"not
        accepted"`` or ``"invalid"``), calls ``_fetch_internal_accepted_id_data``
        to retrieve the accepted TSN from ``getAcceptedNamesFromTSN``.
        Otherwise the record's own TSN is used.  Stores the result in
        ``self._accepted_id`` and returns it.

        Parameters
        ----------
        raw_data : dict
            The raw query record returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The accepted TSN, or ``""`` if it cannot be resolved.
        """
        tsn = self._extract_internal_id(raw_data)
        if raw_data.get("nameUsage") in ("not accepted", "invalid"):
            accepted_names_data = self._fetch_internal_accepted_id_data(tsn)
            # TODO: double check this functionality: should we be returning the first one if there are multiple? also add error
            self._accepted_id = (
                str(accepted_names_data[0]["acceptedTsn"])
                if accepted_names_data
                else ""
            )
        else:
            self._accepted_id = tsn

        return self._accepted_id

    def _fetch_synonym_data(self, accepted_id: str) -> list:
        """
        Fetch full records for every synonym of *accepted_id*.

        First calls ``getSynonymNamesFromTSN`` to get the synonym list, then
        calls ``getFullRecordFromTSN`` once per synonym TSN.  Returning full
        records makes publication and other-source data available to
        ``_compile_synonyms`` via ``_extract_original_source``, with no
        additional fetch calls needed there.

        Parameters
        ----------
        accepted_id : str
            The accepted taxon's TSN.

        Returns
        -------
        list
            Full records (from ``getFullRecordFromTSN``) for each synonym, or
            ``[]`` if none are found.
        """
        data = self._fetch_JSON(
            f"{self.BASE_URL}/getSynonymNamesFromTSN",
            params={"tsn": accepted_id},
            timeout=self._TIMEOUT,
        )
        synonyms = [s for s in (data.get("synonyms") or []) if s]
        full_records = []
        for synonym in synonyms:
            tsn = self._extract_internal_id(synonym)
            if tsn:
                record = self._fetch_JSON(
                    f"{self.BASE_URL}/getFullRecordFromTSN",
                    params={"tsn": tsn},
                    timeout=self._TIMEOUT,
                )
                if record:
                    full_records.append(record)
        return full_records

    def _fetch_accepted_data(self, accepted_id: str) -> dict:
        """
        Fetch the accepted taxon's full record from ``getFullRecordFromTSN``.

        Parameters
        ----------
        accepted_id : str
            The accepted taxon's TSN.

        Returns
        -------
        dict
            The full record from ``getFullRecordFromTSN``, containing
            ``"scientificName"``, ``"taxonAuthor"``, ``"publicationList"``, and
            ``"otherSourceList"`` among other fields, or ``{}`` on error.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/getFullRecordFromTSN",
            params={"tsn": accepted_id},
            timeout=self._TIMEOUT,
        )

    def _fetch_hierarchy_data(self, accepted_id: str) -> list:
        """
        Fetch the full taxonomic hierarchy for *accepted_id* from ``getFullHierarchyFromTSN``.

        Parameters
        ----------
        accepted_id : str
            The accepted taxon's TSN.

        Returns
        -------
        list
            Filtered ``hierarchyList`` records, or ``[]`` on error.
        """
        data = self._fetch_JSON(
            f"{self.BASE_URL}/getFullHierarchyFromTSN",
            params={"tsn": accepted_id},
            timeout=self._TIMEOUT,
        )
        return [r for r in (data.get("hierarchyList") or []) if r]

    def _extract_publication_year(self, authorship: str) -> str:
        """
        Extract a four-digit publication year from an ITIS authorship string.

        Matches a year that is not enclosed in parentheses, e.g. ``"L., 1753"``
        returns ``"1753"`` but ``"(L., 1753)"`` returns ``""``.

        Parameters
        ----------
        authorship : str
            An ITIS authorship value, e.g. ``"L., 1753"`` or ``"(L., 1678) Walbaum, 1792"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if not found.
        """
        m = self._AUTHOR_YEAR_RE.search(authorship)
        return m.group(1) if m else ""

    @staticmethod
    def _strip_links(text: str) -> str:
        """
        Strip HTML anchor tags and bare URLs from a text string.

        Parameters
        ----------
        text : str
            A string that may contain ``<a>`` tags or raw ``http(s)://`` URLs.

        Returns
        -------
        str
            Cleaned text with link markup and URLs removed.
        """
        text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(
            r"</?a[^>]*>", "", text, flags=re.IGNORECASE
        )  # unclosed/orphaned tags
        text = re.sub(r"https?://\S+", "", text)
        return text.strip()

    def _extract_taxonomy(self, hierarchy_list: list) -> dict[str, str]:
        """
        Extract taxonomy fields from an ITIS ``getFullHierarchyFromTSN`` response.

        Parameters
        ----------
        hierarchy_list : list
            The ``"hierarchyList"`` value from the ``getFullHierarchyFromTSN``
            response, each item being a dict with ``"rankName"`` and
            ``"taxonName"`` keys.

        Returns
        -------
        dict[str, str]
            Keys: ``"kingdom"``, ``"phylum"``, ``"class_"``, ``"order"``,
            ``"family"``, and ``"subfamily"``.
        """
        rank_to_field = {
            "Kingdom": "kingdom",
            "Phylum": "phylum",
            "Division": "phylum",  # botanical equivalent of Phylum
            "Class": "class_",
            "Order": "order",
            "Family": "family",
            "Subfamily": "subfamily",
        }
        found = {
            rank_to_field[r["rankName"]]: r["taxonName"]
            for r in hierarchy_list
            if r and r.get("rankName") in rank_to_field
        }
        return {field: found.get(field, "") for field in set(rank_to_field.values())}

    def _extract_original_source(self, data: dict) -> str:
        """
        Build a comma-separated ``original_source`` string from a ``getFullRecordFromTSN`` response.

        Reads ``"publicationList"`` and ``"otherSourceList"``, combines entries
        from both, sorts chronologically by year, and formats each as
        ``"Name [YYYY]"`` (or just ``"Name"`` when no year is available).

        Parameters
        ----------
        data : dict
            A full ITIS record containing ``"publicationList"`` and
            ``"otherSourceList"`` fields.

        Returns
        -------
        str
            Comma-separated source string, or ``""`` if both lists are empty.
        """
        publications = [
            p
            for p in ((data.get("publicationList") or {}).get("publications") or [])
            if p
        ]
        other_sources = [
            s
            for s in ((data.get("otherSourceList") or {}).get("otherSources") or [])
            if s
        ]
        entries = []
        for pub in publications:
            name = self._strip_links((pub.get("pubName") or "").strip())
            m = re.match(r"(\d{4})", pub.get("actualPubDate") or "")
            year = m.group(1) if m else ""
            if name:
                entries.append((year, name))
        for src in other_sources:
            name = self._strip_links((src.get("source") or "").strip())
            m = re.match(r"(\d{4})", src.get("acquisitionDate") or "")
            year = m.group(1) if m else ""
            if name:
                entries.append((year, name))
        entries.sort(key=lambda e: e[0] or "9999")
        parts = [f"{name} [{year}]" if year else name for year, name in entries]
        return ", ".join(parts)

    def _compile_accepted(
        self, accepted_data: dict, hierarchy_data: list
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name.

        Reads ``"scientificName" → "combinedName"`` for the display name,
        ``"taxonAuthor" → "authorship"`` for the author string, and delegates
        to ``_extract_original_source`` and ``_extract_taxonomy`` for source
        and hierarchy fields.

        Parameters
        ----------
        accepted_data : dict
            Full record from ``getFullRecordFromTSN``, as returned by
            ``_fetch_accepted_data``.
        hierarchy_data : list
            Filtered ``hierarchyList`` from ``getFullHierarchyFromTSN``, as
            returned by ``_fetch_hierarchy_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if
            ``"scientificName" → "combinedName"`` is absent or empty.
        """
        sci_name_field = accepted_data.get("scientificName")
        name = ((sci_name_field or {}).get("combinedName") or "").strip()
        if not name:
            return []

        author = (
            (accepted_data.get("taxonAuthor") or {}).get("authorship") or ""
        ).strip()
        tsn = self._extract_internal_id(accepted_data)
        genus, species = self._extract_genus_species(name)
        taxonomy = self._extract_taxonomy(hierarchy_data)
        return [
            self._format_row(
                api_name=ITIS_PORTAL.display_name,
                genus=genus,
                species=species,
                api_internal_id=tsn,
                author=author,
                publication_year=self._extract_publication_year(author),
                original_source=self._extract_original_source(accepted_data),
                status="Accepted",
                api_link=(
                    f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                    if tsn
                    else ""
                ),
                **taxonomy,
            )
        ]

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert full ITIS synonym records into pipeline-standard dicts.

        Each item in *synonym_data* is a ``getFullRecordFromTSN`` response, so
        name, author, and publication data are all read from the same record via
        ``_extract_original_source``.  Deduplicates by scientific name.

        Parameters
        ----------
        synonym_data : list
            Full records from ``getFullRecordFromTSN``, as returned by
            ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for item in synonym_data:
            sci_name_field = item.get("scientificName")
            syn_name = ((sci_name_field or {}).get("combinedName") or "").strip()
            if not syn_name or self._is_infraspecific(syn_name) or syn_name in seen:
                continue
            seen.add(syn_name)
            tsn = self._extract_internal_id(item)
            genus, species = self._extract_genus_species(syn_name)
            author = ((item.get("taxonAuthor") or {}).get("authorship") or "").strip()
            candidates.append(
                self._format_row(
                    api_name=ITIS_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=tsn,
                    author=author,
                    publication_year=self._extract_publication_year(author),
                    original_source=self._extract_original_source(item),
                    status="Synonym",
                    api_link=(
                        f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                        if tsn
                        else ""
                    ),
                )
            )
        return candidates

    def get_synonyms(self, name: str) -> pd.DataFrame:
        """
        Retrieve synonyms and accepted name for *name* from ITIS.

        Overrides the base-class orchestration to pass data explicitly between
        each step rather than through instance state.  The fetch sequence is:

        1. ``_fetch_query_data`` — term search by scientific name
        2. ``_extract_internal_accepted_id`` — resolves the accepted TSN,
           calling ``_fetch_internal_accepted_id_data`` only if needed
        3. ``_fetch_synonym_data`` — synonym TSN list, then one
           ``getFullRecordFromTSN`` call per synonym
        4. ``_fetch_accepted_data`` — full record for the accepted name
        5. ``_fetch_hierarchy_data`` — taxonomic hierarchy for the accepted name

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Danaus plexippus"``).

        Returns
        -------
        pd.DataFrame
            Schema-validated synonym table, or an empty table if the name is
            not found or no rows can be compiled.
        """
        name = normalize_query_string(name)

        raw_data = self._fetch_query_data(name)
        if self._is_empty(raw_data):
            self._warn_if_blank("_fetch_query_data", raw_data)
            return empty_synonym_table()
        print("_fetch_query_data")
        print(raw_data)

        accepted_id = self._extract_internal_accepted_id(raw_data)
        if not accepted_id:
            return empty_synonym_table()

        synonym_data = self._fetch_synonym_data(accepted_id)
        print("_fetch_synonym_data")
        print(synonym_data)
        accepted_data = self._fetch_accepted_data(accepted_id)
        print("_fetch_accepted_data")
        print(accepted_data)
        hierarchy_data = self._fetch_hierarchy_data(accepted_id)
        print("_fetch_hierarchy_data")
        print(hierarchy_data)

        accepted_rows = self._compile_accepted(accepted_data, hierarchy_data)
        synonym_rows = self._compile_synonyms(synonym_data)

        rows = accepted_rows + synonym_rows
        if not rows:
            return empty_synonym_table()
        return pd.DataFrame(rows)
