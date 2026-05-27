"""
GenBank (NCBI Entrez) API client for taxonomy synonyms and sequence metadata.

This module queries two separate NCBI Entrez databases:
  - Taxonomy database: synonym discovery via OtherNames/Synonym elements.
  - Nucleotide database: genetic sequence records surfaced as occurrence-like
    entries (sequence titles, accession URLs, update dates).

NCBI E-utilities API: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

import time
import xml.etree.ElementTree as ET

import requests

from .base import SpeciesAPI


class GenBankAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for GenBank (NCBI Entrez).

    Queries NCBI Entrez for two distinct data types:
      - synonyms(): queries the NCBI Taxonomy database for species-level synonyms.
      - occurrences(): queries the NCBI Nucleotide database for genetic sequence
        metadata records associated with a taxon.

    search() is a no-op since GenBank is not used as a primary taxonomic backbone.

    Occurrence records represent NCBI nucleotide entries, not field observations:
    verbatimLocality holds the sequence title, eventDate is the NCBI record update
    date (not a collection date), and coordinates are always null.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, name: str) -> dict:
        """
        Not implemented for GenBank. GenBank is not a taxonomic backbone, so
        there is no meaningful taxonomy resolution to perform. Returns an empty
        dictionary so the pipeline's synonym-gathering phase is skipped cleanly.

        Args:
            name (str): The scientific name of the taxon (unused).

        Returns:
            dict: Always returns an empty dictionary.
        """
        return {}

    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve species-level synonyms from the NCBI Taxonomy database.

        Queries the Entrez taxonomy database (not the nucleotide database) to
        find synonyms listed under OtherNames/Synonym in the taxon record.

        Args:
            name (str): The scientific name to query.

        Returns:
            list[dict]: A list of synonym records with keys 'canonicalName',
                'author', 'date', 'publishedIn', and 'url'. Returns an empty
                list if no match is found or the request fails.
        """
        try:
            time.sleep(0.35)
            search_resp = requests.get(
                f"{self.BASE_URL}/esearch.fcgi",
                params={"db": "taxonomy", "term": name, "retmode": "json"},
                timeout=10,
            )
            search_resp.raise_for_status()
            ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            time.sleep(0.35)
            fetch_resp = requests.get(
                f"{self.BASE_URL}/efetch.fcgi",
                params={"db": "taxonomy", "id": ",".join(ids), "retmode": "xml"},
                timeout=10,
            )
            fetch_resp.raise_for_status()

            try:
                root = ET.fromstring(fetch_resp.text)
            except ET.ParseError:
                return []

            results = []
            seen = {name.lower()}

            for taxon in root.findall(".//Taxon"):
                taxon_id = taxon.findtext("TaxId", "")
                other_names = taxon.find("OtherNames")
                if other_names is None:
                    continue
                for syn_el in other_names.findall("Synonym"):
                    syn_name = (syn_el.text or "").strip()
                    if not syn_name or syn_name.lower() in seen:
                        continue
                    seen.add(syn_name.lower())
                    results.append(
                        {
                            "canonicalName": syn_name,
                            "author": "",
                            "date": "",
                            "publishedIn": "",
                            "url": f"https://www.ncbi.nlm.nih.gov/taxonomy/{taxon_id}",
                        }
                    )

            return results

        except requests.RequestException as e:
            print(f"GenBank Synonyms Network Error: {e}")
            return []
        except Exception as e:
            print(f"GenBank Synonyms Error: {e}")
            return []

    def occurrences(self, name: str, limit: int = 10) -> list[dict]:
        """
        Retrieve genetic sequence metadata records for a taxon from NCBI.

        Executes a two-step query:
        1. esearch.fcgi — retrieves internal UIDs for sequences matching the taxon.
        2. esummary.fcgi — fetches metadata for those UIDs (title, accession, date).

        Results are formatted to match the pipeline's standard occurrence dict, with
        the following caveats: verbatimLocality holds the sequence title (not a place
        name), eventDate is the NCBI record update date (not a collection date), and
        coordinates are always null.

        Args:
            name (str): The scientific name of the organism (e.g., 'Amanita muscaria').
            limit (int, optional): Maximum number of sequence records to retrieve.
                Defaults to 10 to stay within NCBI's rate limit of 3 requests/second.

        Returns:
            list[dict]: A list of dicts with keys: 'scientificName', 'eventDate',
                'decimalLatitude', 'decimalLongitude', 'verbatimLocality',
                'top_3_images', 'source', and 'occurrenceID' (URL to the NCBI record).
        """
        results = []
        try:
            # Respect NCBI's rate limit (max 3 requests per second)
            time.sleep(0.35)

            # 1. Search the Nucleotide database for the organism
            search_url = f"{self.BASE_URL}/esearch.fcgi"
            search_params = {
                "db": "nucleotide",
                "term": f"{name}[Organism]",
                "retmode": "json",
                "retmax": limit,
            }
            search_resp = requests.get(search_url, params=search_params, timeout=10)
            search_resp.raise_for_status()
            search_data = search_resp.json()

            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return []

            # 2. Fetch the metadata summary for those specific sequence IDs
            sum_url = f"{self.BASE_URL}/esummary.fcgi"
            sum_params = {
                "db": "nucleotide",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            sum_resp = requests.get(sum_url, params=sum_params, timeout=10)
            sum_resp.raise_for_status()
            sum_data = sum_resp.json()

            records = sum_data.get("result", {})

            # 3. Format strictly to the pipeline standard
            for uid in id_list:
                if uid in records:
                    rec = records[uid]

                    # Construct a direct URL to the NCBI sequence page
                    accession = rec.get("accessionversion", uid)
                    url = f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}"

                    results.append(
                        {
                            "scientificName": name,
                            "eventDate": rec.get("updatedate", ""),
                            "decimalLatitude": None,
                            "decimalLongitude": None,
                            # We use the sequence title as the "locality" so the UI has text to display
                            "verbatimLocality": rec.get("title", ""),
                            "top_3_images": [],  # DNA doesn't have field photos!
                            "source": "GenBank (NCBI)",
                            "occurrenceID": url,
                        }
                    )

        except requests.RequestException as e:
            print(f"GenBank API Network Error: {e}")
        except Exception as e:
            print(f"GenBank Parsing Error: {e}")

        return results
