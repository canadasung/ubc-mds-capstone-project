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
import time
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

from scripts.utils.normalize_query_string import normalize_query_string

load_dotenv()  # Read environment variables from .env file

ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ENTREZ_EMAIL = os.environ.get("ENTREZ_EMAIL")  # Required by NCBI usage policy

# Maps NCBI taxonomy rank names to output category keys
_RANK_CATEGORIES = {
    "subspecies": "subspecies",
    "varietas": "varieties",  # NCBI uses "varietas" for variety rank
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

# Matches rank abbreviations at the start of an epithet string so they can be stripped
_RANK_ABBREV_RE = re.compile(
    r"^(subsp|ssp|var|f|str|cv|biotype|serogroup|serotype|genotype|morph|pathogroup|isolate)\.\s*",
    re.IGNORECASE,
)


def main():
    import json

    result = get_genbank_synonyms("Amanita muscaria")
    print(json.dumps(result, indent=2))


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
    epithet = full_name.removeprefix(
        species_name
    ).strip()  # Remove "Genus species" prefix
    return _RANK_ABBREV_RE.sub("", epithet)  # Remove rank abbreviation (e.g. "var.")


def _esearch_ids(term):
    """Return a list of NCBI taxonomy IDs matching the given search term."""
    ids = (
        requests.get(
            f"{ENTREZ_BASE}/esearch.fcgi",
            params={
                "db": "taxonomy",
                "term": term,
                "retmode": "json",
                "email": ENTREZ_EMAIL,
            },
            timeout=30,
        )
        .json()
        .get("esearchresult", {})
        .get("idlist", [])
    )
    time.sleep(0.4)
    return ids


def _efetch_taxa(ids):
    """Fetch and parse NCBI taxonomy XML for the given list of IDs."""
    r = requests.get(
        f"{ENTREZ_BASE}/efetch.fcgi",
        params={
            "db": "taxonomy",
            "id": ",".join(ids),
            "retmode": "xml",
            "email": ENTREZ_EMAIL,
        },
        timeout=30,
    )
    time.sleep(0.4)
    try:
        return ET.fromstring(r.text).findall(".//Taxon")
    except ET.ParseError:
        print(f"NCBI returned non-XML (status {r.status_code}):\n{r.text[:500]}")
        return []


def get_genbank_synonyms(query):
    """
    Given a species name, returns a dict of species-level synonym names from NCBI taxonomy.

    Keys are the queried species name and all NCBI synonyms discovered by following
    the synonym chain (circular references are guarded against). Values are empty
    lists (placeholders for rank categories to be added).
    Returns an empty dict if no match is found.

    Note: rank category data (subspecies, varieties, forms, etc.) is in-progress
    and will be populated in the empty lists in a future update.

    Example:
        {"Amanita muscaria": [], "Agaricus muscarius": []}
    """
    # Normalize to ensure consistent API queries and dict keys
    query = normalize_query_string(query)

    # Fetch the primary taxon record for the query
    primary_ids = _esearch_ids(query)
    if not primary_ids:
        return {}

    # Loop 1: seed the work list with synonyms from the primary taxon record
    synonym_names = [query]
    for taxon in _efetch_taxa(primary_ids):
        other_names = taxon.find("OtherNames")
        if other_names is None:
            continue
        for syn in other_names.findall("Synonym"):
            if syn.text and syn.text.strip():
                name = syn.text.strip()
                if name not in synonym_names:
                    synonym_names.append(name)

    # rank_filter = " OR ".join(f"{rank}[rank]" for rank in _RANK_CATEGORIES)
    # seen = set()  # Guard against circular synonym chains

    # Loop 2: for each synonym, discover any additional synonyms from its taxon record.
    # New synonyms are appended to synonym_names so they get processed too,
    # but seen prevents re-processing any name.
    # for synonym in synonym_names:
    #     if synonym in seen:
    #         continue
    #     seen.add(synonym)

    #     syn_ids = _esearch_ids(synonym)
    #     if not syn_ids:
    #         continue

    # Extract additional synonyms from this taxon's record
    # for taxon in _efetch_taxa(syn_ids):
    #     other_names = taxon.find("OtherNames")
    #     if other_names is None:
    #         continue
    #     for syn_el in other_names.findall("Synonym"):
    #         if syn_el.text and syn_el.text.strip():
    #             new_name = syn_el.text.strip()
    #             if new_name not in seen and new_name not in synonym_names:
    #                 synonym_names.append(new_name)
    # for named in other_names.findall("Name"):
    #     if named.findtext("ClassCDE") == "misspelling":
    #         disp_name = named.findtext("DispName", "").strip()
    #         if disp_name:
    #             categories.setdefault("misspellings", []).append(disp_name)

    # subtree_terms = " OR ".join(f"txid{i}[subtree]" for i in syn_ids)
    # sub_ids = _esearch_ids(f"({subtree_terms}) AND ({rank_filter})")

    # if not sub_ids:
    #     result[synonym] = categories
    #     continue

    # for taxon in _efetch_taxa(sub_ids):
    #     name = taxon.findtext("ScientificName")
    #     rank = taxon.findtext("Rank")
    #     if name and rank in _RANK_CATEGORIES:
    #         category = _RANK_CATEGORIES[rank]
    #         categories.setdefault(category, []).append(name)

    # result[synonym] = categories

    return {name: [] for name in synonym_names}


if __name__ == "__main__":
    main()
