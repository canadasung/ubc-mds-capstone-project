"""
NCBI_taxonomy.py — NCBI Taxonomy API client

Queries the NCBI Entrez API and returns a dict mapping standard taxonomic
ranks to their names for the matched species, parsed from the LineageEx
XML element.

Requires an ENTREZ_EMAIL environment variable (set in .env).

Main entry point: get_ncbi_taxonomy(species_name)
"""

import os
import time
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

load_dotenv()

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ENTREZ_EMAIL = os.environ.get("ENTREZ_EMAIL")

RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


def get_ncbi_taxonomy(species_name: str) -> dict:
    """
    Given a species name, returns a dict mapping taxonomic ranks to names
    as reported by the NCBI Taxonomy database.

    Keys are rank names (lowercase): kingdom, phylum, class, order, family,
    genus, species. Values are strings, or None if NCBI did not return that rank.
    Returns an empty dict if no match is found.

    Example:
        {
            "kingdom": "Fungi",
            "phylum": "Basidiomycota",
            "class": "Agaricomycetes",
            "order": "Agaricales",
            "family": "Amanitaceae",
            "genus": "Amanita",
            "species": "Amanita muscaria",
        }
    """
    # Step 1: esearch to get the taxonomy ID
    search_resp = requests.get(
        f"{ENTREZ_BASE}/esearch.fcgi",
        params={
            "db": "taxonomy",
            "term": species_name,
            "retmode": "json",
            "email": ENTREZ_EMAIL,
        },
    )
    search_resp.raise_for_status()
    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    time.sleep(0.4)

    if not ids:
        return {}

    # Step 2: efetch to get the full taxonomy record
    fetch_resp = requests.get(
        f"{ENTREZ_BASE}/efetch.fcgi",
        params={
            "db": "taxonomy",
            "id": ids[0],
            "retmode": "xml",
            "email": ENTREZ_EMAIL,
        },
    )
    fetch_resp.raise_for_status()
    time.sleep(0.4)

    try:
        root = ET.fromstring(fetch_resp.text)
    except ET.ParseError:
        return {}

    taxon = root.find(".//Taxon")
    if taxon is None:
        return {}

    # LineageEx contains all ancestor taxa with ScientificName and Rank
    taxonomy = {}
    lineage_ex = taxon.find("LineageEx")
    if lineage_ex is not None:
        for t in lineage_ex.findall("Taxon"):
            rank = (t.findtext("Rank") or "").lower()
            name = (t.findtext("ScientificName") or "").strip()
            if rank in RANKS and name:
                taxonomy[rank] = name

    # The species itself is the top-level ScientificName
    species_name_result = (taxon.findtext("ScientificName") or "").strip()
    if species_name_result:
        taxonomy["species"] = species_name_result

    if not taxonomy:
        return {}

    return {rank: taxonomy.get(rank) for rank in RANKS}


if __name__ == "__main__":
    import json

    result = get_ncbi_taxonomy("Amanita muscaria")
    print(json.dumps(result, indent=2))