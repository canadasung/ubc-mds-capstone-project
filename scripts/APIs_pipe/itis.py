"""
ITIS API client.

SpeciesAPI implementation for ITIS (Integrated Taxonomic Information System),
a database of biological names maintained by a partnership of United States
federal agencies. ITIS provides authoritative taxonomic information for plants,
animals, fungi, and microbes, including synonym data.
"""

from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI
from .config import ITIS_PORTAL


class ITISAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for ITIS.
    """

    BASE_URL = ITIS_PORTAL.base_url

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

        Calls ``_extract_internal_accepted_id``,
        to get the accepted ID, then queries
        ``getSynonymNamesFromTSN`` with that ID.

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

        data = self._fetch_JSON(
            f"{self.BASE_URL}/getSynonymNamesFromTSN",
            params={"tsn": accepted_tsn},
        )
        return [s for s in (data.get("synonyms") or []) if s]  # TODO: add error

    def _fetch_synonym_search_term_data(
        self, raw_data: dict, _synonym_data: list
    ) -> dict:
        """
        Return the accepted taxon's record for use as the synonym search term.

        If the original query matched the accepted name directly, ``raw_data``
        is the search term. If the query matched a synonym, fetches the accepted
        taxon's full record from ``getFullRecordFromTSN`` using
        ``self._accepted_tsn`` stored by ``_fetch_synonym_data``.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record as returned by ``_fetch_query_data``.
        _synonym_data : list
            Raw synonym records (unused here).

        Returns
        -------
        dict
            The accepted name's record.
        """
        if raw_data.get("nameUsage") in ("not accepted", "invalid"):
            return self._fetch_JSON(
                f"{self.BASE_URL}/getFullRecordFromTSN",
                params={"tsn": self._accepted_tsn},
            )
        else:
            return raw_data

    def _compile_synonym_search_term(
        self, synonym_search_term_data: dict
    ) -> list[dict]:
        """
        Build a pipeline-standard record for the synonym search term.

        Handles two record shapes:

        - Term records (from ``getITISTermsFromScientificName``, returned when
          the query was already the accepted name): ``scientificName`` is a
          plain string, authorship is in ``author``.
        - Full records (from ``getFullRecordFromTSN``, fetched when the query
          was a synonym): ``scientificName`` is a nested object with
          ``combinedName``, authorship is in ``taxonAuthor.authorship``.

        Parameters
        ----------
        synonym_search_term_data : dict
            The accepted name's record as returned by
            ``_fetch_synonym_search_term_data``.

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if the name
            cannot be determined.
        """
        sci_name_field = synonym_search_term_data.get("scientificName")
        if isinstance(sci_name_field, dict):
            # Full record from getFullRecordFromTSN
            name = (sci_name_field.get("combinedName") or "").strip()
            author = (
                (synonym_search_term_data.get("taxonAuthor") or {}).get("authorship")
                or ""
            ).strip()
        else:
            # Term record from getITISTermsFromScientificName
            name = (sci_name_field or "").strip()
            author = (synonym_search_term_data.get("author") or "").strip()

        tsn = self._extract_internal_id(synonym_search_term_data)
        if not name:
            return []
        genus, species = self._extract_genus_species(name)
        return [
            self._format_row(
                api_name=ITIS_PORTAL.display_name,
                genus=genus,
                species=species,
                api_internal_id=tsn,
                author=author,
                api_link=(
                    f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                    if tsn
                    else ""
                ),
            )
        ]

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw ITIS synonym records into pipeline-standard synonym dicts.

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
            candidates.append(
                self._format_row(
                    api_name=ITIS_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=tsn,
                    author=(item.get("author") or "").strip(),
                    api_link=(
                        f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                        if tsn
                        else ""
                    ),
                )
            )
        return candidates
