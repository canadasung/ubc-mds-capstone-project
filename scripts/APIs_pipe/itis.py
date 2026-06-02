"""
ITIS API client.

SpeciesAPI implementation for ITIS (Integrated Taxonomic Information System),
a database of biological names maintained by a partnership of United States
federal agencies. ITIS provides authoritative taxonomic information for plants,
animals, fungi, and microbes, including synonym data.
"""

from .base import SpeciesAPI


class ITISAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for ITIS.
    """

    BASE_URL = "https://www.itis.gov/ITISWebService/jsonservice"

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
        terms = data.get("itisTerms") or []
        exact = next(
            (
                t
                for t in terms
                if t and (t.get("scientificName") or "").lower() == name.lower()
            ),
            None,
        )
        return exact if exact is not None else {}

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
        Resolve a TSN to the accepted name's TSN.

        If the term record indicates the name is not accepted (i.e. it is a
        synonym), queries ``getAcceptedNamesFromTSN`` to obtain the accepted
        TSN. Otherwise, the original TSN is returned unchanged.

        Parameters
        ----------
        raw_data : dict
            A single ITIS term record as returned by ``_fetch_query_data``.

        Returns
        -------
        str
            The TSN of the accepted name.
        """
        tsn = self._extract_internal_id(raw_data)
        if raw_data.get("nameUsage") not in ("not accepted", "invalid"):
            return tsn
        data = self._fetch_JSON(
            f"{self.BASE_URL}/getAcceptedNamesFromTSN",
            params={"tsn": tsn},
        )
        accepted_names = [n for n in (data.get("acceptedNames") or []) if n]
        if accepted_names:
            return str(accepted_names[0]["acceptedTsn"])
        return tsn

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Fetch raw synonym records for the accepted taxon resolved from the term record.

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
        return [s for s in (data.get("synonyms") or []) if s]

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
            if not syn_name or syn_name in seen:
                continue
            seen.add(syn_name)
            tsn = item.get("tsn") or ""
            candidates.append(
                self._format_synonym(
                    name=syn_name,
                    author=(item.get("author") or "").strip(),
                    api_link=(
                        f"https://www.itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={tsn}"
                        if tsn
                        else ""
                    ),
                )
            )
        return candidates
