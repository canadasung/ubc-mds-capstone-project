"""
GenBank (NCBI Entrez) API client for taxonomy synonyms.

This module queries the NCBI Entrez Taxonomy database for synonym discovery
via OtherNames/Synonym elements.

NCBI E-utilities API: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

import xml.etree.ElementTree as ET

from .base import SpeciesAPI


class GenBankAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for GenBank (NCBI Entrez).

    Queries the NCBI Taxonomy database for species-level synonyms.

    The two fetch methods use different base helpers because NCBI's Entrez
    API serves different content types per endpoint:

    - ``esearch.fcgi`` (used by ``search()``) returns JSON → uses ``_fetch()``.
    - ``efetch.fcgi`` (used by ``synonyms()``) returns XML → uses ``_fetch_text()``.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, name: str) -> dict:
        """
        Query the NCBI Taxonomy database to find a record for a species name.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response from NCBI esearch, containing the esearchresult
                with idlist, count, and other match details. Returns an empty dict
                if the request fails.
        """
        return self._fetch(
            f"{self.BASE_URL}/esearch.fcgi",
            params={"db": "taxonomy", "term": name, "retmode": "json"},
        )

    def _fetch_taxon_xml(self, ids: list[str]) -> str:
        """
        Fetch raw XML taxon records for a list of NCBI taxonomy IDs.

        Args:
            ids (list[str]): NCBI taxonomy IDs returned by ``search()``.

        Returns:
            str: Raw XML response text from the efetch endpoint,
                or ``""`` on request failure.
        """
        return self._fetch_text(
            f"{self.BASE_URL}/efetch.fcgi",
            params={"db": "taxonomy", "id": ",".join(ids), "retmode": "xml"},
        )

    def _build_synonyms(self, xml_root: ET.Element, query_name: str) -> list[dict]:
        """
        Extract pipeline-standard synonym records from a parsed NCBI taxon XML tree.

        Walks the ElementTree for ``OtherNames/Synonym`` elements and builds
        one record per unique synonym name.

        Args:
            xml_root (ET.Element): Root element of the parsed efetch XML response.
            query_name (str): The original query name, used to seed deduplication.

        Returns:
            list[dict]: Pipeline-standard synonym records.
        """
        candidates = []
        for taxon in xml_root.findall(".//Taxon"):
            taxon_id = taxon.findtext("TaxId", "")
            other_names = taxon.find("OtherNames")
            if other_names is None:
                continue
            for syn_el in other_names.findall("Synonym"):
                syn_name = (syn_el.text or "").strip()
                if not syn_name:
                    continue
                candidates.append(
                    self._format_synonym(
                        name=syn_name,
                        api_link=f"https://www.ncbi.nlm.nih.gov/taxonomy/{taxon_id}",
                    )
                )
        return self._deduplicate_synonyms(candidates, seed={query_name.lower()})

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve species-level synonyms from the NCBI Taxonomy database.

        Calls search() first to find taxonomy IDs for the name, then fetches
        the full taxon record and extracts synonyms from OtherNames/Synonym elements.

        Args:
            name (str): The scientific name to query.

        Returns:
            list[dict]: A list of synonym records with keys 'canonicalName',
                'author', 'date', 'publishedIn', and 'url'. Returns an empty
                list if no match is found or the request fails.
        """
        try:
            search_data = self.search(name)
            ids = search_data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            xml_text = self._fetch_taxon_xml(ids)
            if not xml_text:
                return []

            root = self._parse_xml(xml_text)
            if root is None:
                return []

            return self._build_synonyms(root, query_name=name)

        except Exception as e:
            print(f"GenBank Synonyms Error: {e}")
            return []
