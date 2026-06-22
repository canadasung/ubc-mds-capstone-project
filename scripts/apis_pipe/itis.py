"""
ITIS API client.

ITIS (Integrated Taxonomic Information System) is an authoritative database of
biological names for plants, animals, fungi, and microbes, maintained by a
partnership of US federal agencies.  This client uses the ITIS JSON web service
to resolve names by TSN (Taxonomic Serial Number) and retrieve synonym lists,
publication data, and full taxonomic hierarchy.

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

from scripts.config import ITIS_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class ITISAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the ITIS JSON web service.
    """

    BASE_URL = ITIS_PORTAL.base_url
    # ITIS prefix-search endpoints can be slow for accepted names that match
    # many records, so we use a longer timeout than the base-class default.
    _TIMEOUT = 30

    def _extract_publication_year(self, authorship: str) -> str:
        """
        Extract a four-digit year from an ITIS authorship string.

        Returns the trailing year only when the string does not end with ``)``,
        which avoids false matches in parenthesised author strings.

        Parameters
        ----------
        authorship : str
            An ITIS authorship value, e.g. ``"L., 1753"`` or ``"(L.) Lam., 1783"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if not found or the string ends
            with ``)``.
        """
        stripped = authorship.strip()
        if not stripped.endswith(")"):
            match = re.search(r"(\d{4})\s*$", stripped)
            if match:
                return match.group(1)
        return ""

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

    def _build_original_source(self, publications: list, other_sources: list) -> str:
        """
        Build a comma-separated ``original_source`` string from ITIS publication records.

        Combines entries from both lists, sorts chronologically by year, and
        formats each as ``"Name [YYYY]"`` (or just ``"Name"`` when no year is
        available).

        Parameters
        ----------
        publications : list
            Publication records from ``getPublicationsFromTSN``.
        other_sources : list
            Other source records from ``getOtherSourcesFromTSN``.

        Returns
        -------
        str
            Comma-separated source string, or ``""`` if both lists are empty.
        """
        entries = []
        for pub in publications:
            if not pub:
                continue
            name = self._strip_links((pub.get("pubName") or "").strip())
            m = re.match(r"(\d{4})", pub.get("actualPubDate") or "")
            year = m.group(1) if m else ""
            if name:
                entries.append((year, name))
        for src in other_sources:
            if not src:
                continue
            name = self._strip_links((src.get("source") or "").strip())
            m = re.match(r"(\d{4})", src.get("acquisitionDate") or "")
            year = m.group(1) if m else ""
            if name:
                entries.append((year, name))
        entries.sort(key=lambda e: e[0] or "9999")
        parts = [f"{name} [{year}]" if year else name for year, name in entries]
        return ", ".join(parts)

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
        Extract the ITIS Taxonomic Serial Number (TSN) from a term record.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record (from ``_fetch_query_data`` or a synonym
            record).

        Returns
        -------
        str
            The TSN as a string.

        Raises
        ------
        LookupError
            When no ``tsn`` key is present in the record.
        """
        tsn = raw_data.get("tsn")
        if tsn is None:
            raise LookupError(
                f"{type(self).__name__} error: could not extract TSN from search result."
            )
        return str(tsn)

    def _fetch_accepted_tsn_data(self, tsn: str) -> list:
        """
        Fetch accepted name records for *tsn* from ``getAcceptedNamesFromTSN``.

        Parameters
        ----------
        tsn : str
            The TSN to resolve to an accepted name.

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

    def _extract_internal_accepted_id(self, accepted_names_data: list) -> str:
        """
        Extract the accepted TSN from pre-fetched accepted names data.

        Parameters
        ----------
        accepted_names_data : list
            The list returned by ``_fetch_accepted_tsn_data``.

        Returns
        -------
        str
            The ``acceptedTsn`` of the first record, or ``""`` if the list is
            empty.
        """
        if accepted_names_data:
            return str(
                accepted_names_data[0]["acceptedTsn"]
            )  # TODO: double check this functionality: should we be returning the first one if there are multiple? also add error
        return ""

    def _fetch_synonym_publication_data(self, tsn: str) -> tuple[list, list]:
        """
        Fetch publication and source records for a synonym TSN.

        Calls ``getPublicationsFromTSN`` and ``getOtherSourcesFromTSN`` in
        sequence and returns both filtered lists.

        Parameters
        ----------
        tsn : str
            The TSN of the synonym to fetch publication data for.

        Returns
        -------
        tuple[list, list]
            A ``(publications, other_sources)`` pair, each a filtered list.
        """
        pub_data = self._fetch_JSON(
            f"{self.BASE_URL}/getPublicationsFromTSN",
            params={"tsn": tsn},
            timeout=self._TIMEOUT,
        )
        src_data = self._fetch_JSON(
            f"{self.BASE_URL}/getOtherSourcesFromTSN",
            params={"tsn": tsn},
            timeout=self._TIMEOUT,
        )
        publications = [p for p in (pub_data.get("publications") or []) if p]
        other_sources = [s for s in (src_data.get("otherSources") or []) if s]
        return publications, other_sources

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Fetch augmented synonym records for the accepted taxon from ``getSynonymNamesFromTSN``.

        Also fetches the full taxonomy hierarchy (``getFullHierarchyFromTSN``)
        and stores it as ``self._hierarchy_data`` for ``_compile_accepted``.
        If the queried name is a synonym, resolves the accepted TSN first via
        ``_fetch_accepted_tsn_data``.  Each synonym record is augmented with
        pre-fetched ``publications`` and ``other_sources`` so that
        ``_compile_synonyms`` requires no network calls.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record as returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Augmented synonym records with ``publications`` and ``other_sources``
            fields, or ``[]`` if no synonyms are found.
        """
        tsn = self._extract_internal_id(raw_data)
        if raw_data.get("nameUsage") in ("not accepted", "invalid"):
            accepted_names_data = self._fetch_accepted_tsn_data(tsn)
            self._accepted_tsn = (
                self._extract_internal_accepted_id(accepted_names_data) or ""
            )
        else:
            self._accepted_tsn = tsn

        hierarchy = self._fetch_JSON(
            f"{self.BASE_URL}/getFullHierarchyFromTSN",
            params={"tsn": self._accepted_tsn},
            timeout=self._TIMEOUT,
        )
        self._hierarchy_data = [r for r in (hierarchy.get("hierarchyList") or []) if r]

        data = self._fetch_JSON(
            f"{self.BASE_URL}/getSynonymNamesFromTSN",
            params={"tsn": self._accepted_tsn},
            timeout=self._TIMEOUT,
        )
        synonyms = [s for s in (data.get("synonyms") or []) if s]  # TODO: add error

        for s in synonyms:
            syn_tsn = self._extract_internal_id(s)
            if syn_tsn:
                publications, other_sources = self._fetch_synonym_publication_data(
                    syn_tsn
                )
            else:
                publications, other_sources = [], []
            s["publications"] = publications
            s["other_sources"] = other_sources

        return synonyms

    def _fetch_accepted_data(self, _raw_data: dict, _synonym_data: list) -> dict:
        """
        Fetch the accepted taxon's full record from ``getFullRecordFromTSN``.

        Always uses ``self._accepted_tsn`` (set by ``_fetch_synonym_data``) to
        ensure consistent publication, source, and authorship fields regardless
        of whether the original query was an accepted name or a synonym.

        Parameters
        ----------
        _raw_data : dict
            The original query term record (unused here).
        _synonym_data : list
            Raw synonym records (unused here).

        Returns
        -------
        dict
            The accepted name's full record from ``getFullRecordFromTSN``.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/getFullRecordFromTSN",
            params={"tsn": self._accepted_tsn},
            timeout=self._TIMEOUT,
        )

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from an ITIS full record.

        Reads ``scientificName.combinedName`` and ``taxonAuthor.authorship``
        from the ``getFullRecordFromTSN`` response.

        Parameters
        ----------
        accepted_data : dict
            The accepted name's full record as returned by
            ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if the name
            cannot be determined.
        """
        sci_name_field = accepted_data.get("scientificName")
        name = ((sci_name_field or {}).get("combinedName") or "").strip()
        author = (
            (accepted_data.get("taxonAuthor") or {}).get("authorship") or ""
        ).strip()

        tsn = self._extract_internal_id(accepted_data)
        if not name:
            return []
        genus, species = self._extract_genus_species(name)
        publications = [
            p
            for p in (
                (accepted_data.get("publicationList") or {}).get("publications") or []
            )
            if p
        ]
        other_sources = [
            s
            for s in (
                (accepted_data.get("otherSourceList") or {}).get("otherSources") or []
            )
            if s
        ]
        taxonomy = self._extract_taxonomy(getattr(self, "_hierarchy_data", []))
        return [
            self._format_row(
                api_name=ITIS_PORTAL.display_name,
                genus=genus,
                species=species,
                api_internal_id=tsn,
                author=author,
                publication_year=self._extract_publication_year(author),
                original_source=self._build_original_source(
                    publications, other_sources
                ),
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
        Convert augmented ITIS synonym records into pipeline-standard dicts.

        Each record is expected to carry pre-fetched ``publications`` and
        ``other_sources`` lists stashed by ``_fetch_synonym_data``.
        Deduplicates by scientific name.

        Parameters
        ----------
        synonym_data : list
            Augmented synonym records as returned by ``_fetch_synonym_data``,
            each containing ``"sciName"``, ``"author"``, ``"tsn"``,
            ``"publications"``, and ``"other_sources"``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for item in synonym_data:
            syn_name = (item.get("sciName") or "").strip()
            if not syn_name or self._is_infraspecific(syn_name) or syn_name in seen:
                continue
            seen.add(syn_name)
            tsn = self._extract_internal_id(item)
            genus, species = self._extract_genus_species(syn_name)
            author = (item.get("author") or "").strip()

            candidates.append(
                self._format_row(
                    api_name=ITIS_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=tsn,
                    author=author,
                    publication_year=self._extract_publication_year(author),
                    original_source=self._build_original_source(
                        item.get("publications", []),
                        item.get("other_sources", []),
                    ),
                    status="Synonym",
                    api_link=(
                        f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                        if tsn
                        else ""
                    ),
                )
            )
        return candidates
