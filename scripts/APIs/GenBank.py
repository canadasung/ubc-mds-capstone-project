"""
GenBank.py — NCBI Taxonomy API client

Queries the NCBI Entrez API to retrieve species names and their infraspecific
taxa (subspecies, varieties, forms, strains, etc.) from the NCBI taxonomy
database.

Requires an ENTREZ_EMAIL environment variable (set in .env) to identify
requests to the NCBI API, as required by their usage policy.

Main entry point: get_genbank_synonyms(query)
"""

import os
import re
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

load_dotenv()

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ENTREZ_EMAIL = os.environ.get("ENTREZ_EMAIL")

# Maps NCBI taxonomy rank names to output category keys
_RANK_CATEGORIES = {
    "subspecies": "subspecies",
    "varietas": "varieties",
    "forma": "forms",
    "strain": "strains",
    "biotype": "biotypes",
    "serogroup": "serogroups",
    "serotype": "serotypes",
    "genotype": "genotypes",
    "morph": "morphs",
    "pathogroup": "pathogroups",
    "isolate": "isolates",
}

_RANK_ABBREV_RE = re.compile(
    r"^(subsp|ssp|var|f|str|cv|biotype|serogroup|serotype|genotype|morph|pathogroup|isolate)\.\s*",
    re.IGNORECASE,
)


def clean_taxon_epithet(full_name, species_name):
    """
    Strip the species name prefix and rank abbreviation from a full taxon name,
    returning only the terminal epithet.

    Parameters:
    full_name (str): Complete NCBI scientific name (e.g. "Amanita muscaria subsp. flavivolvata").
    species_name (str): Species name prefix to remove (e.g. "Amanita muscaria").

    Returns:
    str: The terminal epithet with the species prefix and rank abbreviation removed.

    Examples:
        "Amanita muscaria subsp. flavivolvata" -> "flavivolvata"
        "Amanita muscaria var. formosa"        -> "formosa"
    """
    epithet = full_name.removeprefix(species_name).strip()
    return _RANK_ABBREV_RE.sub("", epithet)


def get_genbank_synonyms(query):
    """
    Search for a species and its infraspecific taxa in the NCBI taxonomy database.

    Parameters:
    query (str): Scientific name to search for (e.g. "Amanita muscaria").

    Returns:
    dict: Keys are species-rank scientific names matching the query. Values are
          dicts with category keys ("subspecies", "varieties", "forms", "strains",
          etc.) each mapping to a list of cleaned terminal epithets. Returns an
          empty dict if no match is found.

    Example:
        {"Amanita muscaria": {"subspecies": ["flavivolvata"], "varieties": ["formosa"], ...}}
    """
    ids = (
        requests.get(
            f"{ENTREZ_BASE}/esearch.fcgi",
            params={
                "db": "taxonomy",
                "term": query,
                "retmax": 10,
                "retmode": "json",
                "email": ENTREZ_EMAIL,
            },
        )
        .json()
        .get("esearchresult", {})
        .get("idlist", [])
    )

    if not ids:
        return {}

    subtree_terms = " OR ".join(f"txid{i}[subtree]" for i in ids)
    rank_filter = " OR ".join(f"{rank}[rank]" for rank in _RANK_CATEGORIES)
    sub_ids = (
        requests.get(
            f"{ENTREZ_BASE}/esearch.fcgi",
            params={
                "db": "taxonomy",
                "term": f"({subtree_terms}) AND ({rank_filter})",
                "retmax": 100,
                "retmode": "json",
                "email": ENTREZ_EMAIL,
            },
        )
        .json()
        .get("esearchresult", {})
        .get("idlist", [])
    )

    all_ids = set(ids) | set(sub_ids)

    r = requests.get(
        f"{ENTREZ_BASE}/efetch.fcgi",
        params={
            "db": "taxonomy",
            "id": ",".join(all_ids),
            "retmode": "xml",
            "email": ENTREZ_EMAIL,
        },
    )

    result = {}
    subordinates = []
    for taxon in ET.fromstring(r.text).findall(".//Taxon"):
        name = taxon.findtext("ScientificName")
        rank = taxon.findtext("Rank")
        if not name or not name.startswith(query):
            continue
        if rank in _RANK_CATEGORIES:
            subordinates.append((name, rank))
        else:
            result.setdefault(name, {cat: [] for cat in _RANK_CATEGORIES.values()})

    for name, rank in subordinates:
        parent = next((s for s in result if name.startswith(s + " ")), None)
        if parent:
            category = _RANK_CATEGORIES[rank]
            epithet = clean_taxon_epithet(name, parent)
            if epithet not in result[parent][category]:
                result[parent][category].append(epithet)

    return {
        species: {cat: epithets for cat, epithets in categories.items() if epithets}
        for species, categories in result.items()
    }
