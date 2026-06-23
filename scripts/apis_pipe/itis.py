"""
ITIS API client.

SpeciesAPI implementation for ITIS (Integrated Taxonomic Information System),
a database of biological names maintained by a partnership of United States
federal agencies. ITIS provides authoritative taxonomic information for plants,
animals, fungi, and microbes, including synonym data.
"""

import re

from scripts.config import ITIS_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class ITISAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for ITIS.
    """

    BASE_URL = ITIS_PORTAL.base_url
    # ITIS prefix-search endpoints can be slow for accepted names that match
    # many records, so we use a longer timeout than the base-class default.
    _TIMEOUT = 30

    def _extract_publication_year(self, authorship: str) -> str:
        stripped = authorship.strip()
        if not stripped.endswith(")"):
            match = re.search(r"(\d{4})\s*$", stripped)
            if match:
                return match.group(1)
        return ""

    @staticmethod
    def _strip_links(text: str) -> str:
        text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", text, flags=re.IGNORECASE)
        text = re.sub(
            r"</?a[^>]*>", "", text, flags=re.IGNORECASE
        )  # unclosed/orphaned tags
        text = re.sub(r"https?://\S+", "", text)
        return text.strip()

    def _build_original_source(self, publications: list, other_sources: list) -> str:
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
        Search the ITIS database for a scientific name.

        Calls the ``getITISTermsFromScientificName`` endpoint, which performs a
        prefix search. Results are filtered for an exact case-insensitive match
        on the ``scientificName`` field.

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
            A single ITIS term record as returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The TSN of the matched record.

        Raises
        ------
        LookupError
            When no TSN is present in the record.
        """
        tsn = raw_data.get("tsn")
        if tsn is None:
            raise LookupError(
                f"{type(self).__name__} error: could not extract TSN from search result."
            )
        return str(tsn)

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Resolve a term record to the accepted name's TSN.

        If the record's ``nameUsage`` indicates a synonym (``"not accepted"``
        for plants and algae, ``"invalid"`` for animals and bacteria), fetches
        ``getAcceptedNamesFromTSN`` to find the accepted TSN. Otherwise returns
        the record's own TSN unchanged. Stores the result as
        ``self._accepted_tsn`` for use by ``_fetch_synonym_search_term_data``.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record as returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The TSN of the accepted name, or the original TSN if the record is already accepted, or blank if no accepted name is found.
        """
        tsn = self._extract_internal_id(raw_data)
        if raw_data.get("nameUsage") in ("not accepted", "invalid"):
            accepted_names_data = self._fetch_JSON(
                f"{self.BASE_URL}/getAcceptedNamesFromTSN",
                params={"tsn": tsn},
                timeout=self._TIMEOUT,
            )

            accepted_names = [
                n for n in (accepted_names_data.get("acceptedNames") or []) if n
            ]
            self._accepted_tsn = (
                str(accepted_names[0]["acceptedTsn"])
                if accepted_names
                else ""  # TODO: double check this functionality: should we be returning the first one if there are multiple? also add error
            )
        else:
            self._accepted_tsn = tsn
        return self._accepted_tsn

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Fetch raw synonym records for the accepted taxon resolved from the term record.

        Also fetches the full taxonomy hierarchy for the accepted name and stores
        it as ``self._hierarchy_data`` for use in ``_compile_synonym_search_term``.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record as returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Raw synonym records from ``getSynonymNamesFromTSN``, with null
            entries removed. Returns ``[]`` if no synonyms are found.
        """
        accepted_tsn = self._extract_internal_accepted_id(raw_data)

        hierarchy = self._fetch_JSON(
            f"{self.BASE_URL}/getFullHierarchyFromTSN",
            params={"tsn": accepted_tsn},
            timeout=self._TIMEOUT,
        )
        self._hierarchy_data = [r for r in (hierarchy.get("hierarchyList") or []) if r]

        data = self._fetch_JSON(
            f"{self.BASE_URL}/getSynonymNamesFromTSN",
            params={"tsn": accepted_tsn},
            timeout=self._TIMEOUT,
        )
        return [s for s in (data.get("synonyms") or []) if s]  # TODO: add error

    def _fetch_synonym_search_term_data(
        self, _raw_data: dict, _synonym_data: list
    ) -> dict:
        """
        Return the accepted taxon's full record for use as the synonym search term.

        Always fetches ``getFullRecordFromTSN`` using ``self._accepted_tsn`` so
        that publication, source, and authorship fields are consistently available
        regardless of whether the original query was an accepted name or a synonym.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record as returned by ``_fetch_query_data``.
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

    def _compile_synonym_search_term(
        self, synonym_search_term_data: dict
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term.

        Uses the full record from ``getFullRecordFromTSN``: ``scientificName``
        is a nested object with ``combinedName``, authorship is in
        ``taxonAuthor.authorship``.

        Parameters
        ----------
        synonym_search_term_data : dict
            The accepted name's full record as returned by
            ``_fetch_synonym_search_term_data``.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if the name
            cannot be determined.
        """
        sci_name_field = synonym_search_term_data.get("scientificName")
        name = ((sci_name_field or {}).get("combinedName") or "").strip()
        author = (
            (synonym_search_term_data.get("taxonAuthor") or {}).get("authorship") or ""
        ).strip()

        tsn = self._extract_internal_id(synonym_search_term_data)
        if not name:
            return []
        genus, species = self._extract_genus_species(name)
        publications = [
            p
            for p in (
                (synonym_search_term_data.get("publicationList") or {}).get(
                    "publications"
                )
                or []
            )
            if p
        ]
        other_sources = [
            s
            for s in (
                (synonym_search_term_data.get("otherSourceList") or {}).get(
                    "otherSources"
                )
                or []
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
        Convert raw ITIS synonym records into pipeline-standard synonym dicts.

        Calls ``getPublicationsFromTSN`` for each synonym to retrieve
        ``publication_name``. ``publication_year`` is parsed from the ``author``
        string. Taxonomy and ``original_source`` are left as UNAVAILABLE.

        Parameters
        ----------
        synonym_data : list
            Raw synonym records as returned by ``_fetch_synonym_data``. Each
            record contains a ``"sciName"``, ``"author"``, and ``"tsn"`` field.

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

            pub_data = self._fetch_JSON(
                f"{self.BASE_URL}/getPublicationsFromTSN",
                params={"tsn": tsn},
                timeout=self._TIMEOUT,
            )
            publications = [p for p in (pub_data.get("publications") or []) if p]
            src_data = self._fetch_JSON(
                f"{self.BASE_URL}/getOtherSourcesFromTSN",
                params={"tsn": tsn},
                timeout=self._TIMEOUT,
            )
            other_sources = [s for s in (src_data.get("otherSources") or []) if s]

            candidates.append(
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
                    status="Synonym",
                    api_link=(
                        f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                        if tsn
                        else ""
                    ),
                )
            )
        return candidates
