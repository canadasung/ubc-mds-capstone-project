"""
GenBank (NCBI Entrez) API client.

SpeciesAPI implementation for GenBank, a genetic sequence database maintained by NCBI that also exposes a Taxonomy section providing accepted names and synonyms for species.
"""

import xml.etree.ElementTree as ET

from .base import SpeciesAPI


class GenBankAPI(SpeciesAPI):
    """
    Implementation of SpeciesAPI for GenBank (NCBI Entrez).
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the NCBI Taxonomy database to find a record for a species name.

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
        data = self._fetch_JSON(
            f"{self.BASE_URL}/esearch.fcgi",
            params={"db": "taxonomy", "term": name, "retmode": "json"},
        )
        if not data.get("esearchresult", {}).get("idlist"):
            return {}
        return data

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
        return self._fetch_text(
            f"{self.BASE_URL}/efetch.fcgi",
            params={"db": "taxonomy", "id": ",".join(ids), "retmode": "xml"},
        )

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
            taxon_id = taxon.findtext("TaxId", "")
            other_names = taxon.find("OtherNames")
            if other_names is None:
                continue
            for syn_el in other_names.findall("Synonym"):
                syn_name = (syn_el.text or "").strip()
                if not syn_name or syn_name in seen:
                    continue
                seen.add(syn_name)
                candidates.append(
                    self._format_synonym(
                        name=syn_name,
                        api_link=f"https://www.ncbi.nlm.nih.gov/taxonomy/{taxon_id}",
                    )
                )
        return candidates
