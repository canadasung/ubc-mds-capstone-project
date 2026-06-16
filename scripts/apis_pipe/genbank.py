"""
GenBank (NCBI Entrez) API client.

SpeciesAPI implementation for GenBank, a genetic sequence database maintained by NCBI that also exposes a Taxonomy section providing accepted names and synonyms for species.
"""

import xml.etree.ElementTree as ET

from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI
from scripts.config import GENBANK_PORTAL


class GenBankAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for GenBank (NCBI Entrez).
    """

    BASE_URL = GENBANK_PORTAL.base_url

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the NCBI Taxonomy database to find a record for a species name.

        Tries an exact ``[Scientific Name]`` search first (fast path, finds
        accepted names directly). If that returns no IDs, falls back to
        ``[All Names]``, which also matches synonyms stored as ``OtherNames``
        within an accepted name's record.

        Parameters
        ----------
        name : str
            The scientific name to search for (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict
            The JSON response from NCBI esearch, or ``{}`` if the request fails
            or returns no IDs.
        """
        # TODO: investigate Scientific Name vs. All Names further and do more testing!
        for term in (f"{name}[Scientific Name]", f"{name}[All Names]"):
            data = self._fetch_JSON(
                f"{self.BASE_URL}/esearch.fcgi",
                params={"db": "taxonomy", "term": term, "retmode": "json"},
            )
            if data.get("esearchresult", {}).get("idlist"):
                return data
        return {}

    def _extract_internal_id(self, raw_data: ET.Element) -> str:
        """
        Extract the NCBI taxonomy ID from a ``Taxon`` XML element.

        Parameters
        ----------
        raw_data : xml.etree.ElementTree.Element
            A single ``Taxon`` element from an efetch XML response.

        Returns
        -------
        str
            The ``TaxId`` text content, or ``""`` if absent.
        """
        return (raw_data.findtext("TaxId") or "").strip()

    def _fetch_synonym_data(self, raw_data: dict) -> ET.Element | None:
        """
        Fetch and parse the taxon XML for the IDs found in the search response.

        Parameters
        ----------
        raw_data : dict
            The JSON search response returned by ``_fetch_query_data``.

        Returns
        -------
        xml.etree.ElementTree.Element or None
            Parsed root element of the efetch XML response, or ``None`` on error.
        """
        ids = raw_data.get("esearchresult", {}).get("idlist", [])
        return self._fetch_XML(
            f"{self.BASE_URL}/efetch.fcgi",
            params={"db": "taxonomy", "id": ",".join(ids), "retmode": "xml"},
        )

    def _fetch_synonym_search_term_data(
        self, raw_data: dict, synonym_data: ET.Element
    ) -> ET.Element:
        """
        Return ``synonym_data`` directly.

        The efetch XML already in hand contains both the taxon's
        ``ScientificName`` (the search term) and its ``OtherNames/Synonym``
        elements (the synonyms). ``_compile_synonyms`` only extracts the
        synonym elements, so the search term record must be compiled separately
        from the same XML.

        Parameters
        ----------
        raw_data : dict
            The JSON search response returned by ``_fetch_query_data``.
        synonym_data : xml.etree.ElementTree.Element
            Parsed root element of the efetch XML response.

        Returns
        -------
        xml.etree.ElementTree.Element
            The same ``synonym_data`` element passed in.
        """
        return synonym_data

    def _compile_synonyms(self, synonym_data: ET.Element) -> list[dict]:
        """
        Extract pipeline-standard synonym records from a parsed NCBI taxon XML tree.

        Walks the ElementTree for ``OtherNames/Synonym`` elements and builds
        one record per unique synonym name.

        Parameters
        ----------
        synonym_data : xml.etree.ElementTree.Element
            Root element of the parsed efetch XML response.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for taxon in synonym_data.findall(".//Taxon"):
            taxon_id = self._extract_internal_id(taxon)
            other_names = taxon.find("OtherNames")
            if other_names is None:
                continue
            for syn_el in other_names.findall("Synonym"):
                syn_name = normalize_query_string((syn_el.text or "").strip())
                if not syn_name or syn_name in seen:
                    continue
                seen.add(syn_name)
                genus, species = self._extract_genus_species(syn_name)
                candidates.append(
                    self._format_row(
                        api_name=GENBANK_PORTAL.display_name,
                        genus=genus,
                        species=species,
                        api_internal_id=taxon_id,
                        api_link=f"https://www.ncbi.nlm.nih.gov/taxonomy/{taxon_id}",
                    )
                )
        return candidates

    def _compile_synonym_search_term(
        self, synonym_search_term_data: ET.Element
    ) -> list[dict]:
        """
        Extract the accepted taxon name from the efetch XML.

        Reads ``ScientificName`` from the first ``Taxon`` element in the
        efetch response, which is the name that was used as the synonym search term.

        Parameters
        ----------
        synonym_search_term_data : xml.etree.ElementTree.Element
            Parsed root element of the efetch XML response (same as
            ``synonym_data``).

        Returns
        -------
        list of dict
            One-item list with the search term record, or ``[]`` if no
            ``ScientificName`` is found.
        """
        for taxon in synonym_search_term_data.findall(".//Taxon"):
            sci_name = normalize_query_string(
                (taxon.findtext("ScientificName") or "").strip()
            )
            if not sci_name:
                continue
            genus, species = self._extract_genus_species(sci_name)
            taxon_id = self._extract_internal_id(taxon)
            return [
                self._format_row(
                    api_name=GENBANK_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=taxon_id,
                    api_link=f"https://www.ncbi.nlm.nih.gov/taxonomy/{taxon_id}",  # TODO: seems that all synonyms have the accepted names ID without separate pages. Need to investigate further and check against the API documentation to see if this is expected behaviour, but guessing it is because when I search a synonym on the website it only pulls up results for the page for the accepted name.
                )
            ]
        return []
