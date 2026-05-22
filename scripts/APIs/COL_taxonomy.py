"""
COL_taxonomy.py — Catalogue of Life taxonomy API client

Queries the ChecklistBank API (latest COL release) and returns a dict
mapping standard taxonomic ranks to their names for the matched species.

Main entry point: get_col_taxonomy(species_name)
"""

import requests

CLB_BASE = "https://api.checklistbank.org"
DATASET = "3LR"  # Latest COL release

RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


def get_col_taxonomy(species_name: str) -> dict:
    """
    Given a species name, returns a dict mapping taxonomic ranks to names
    as reported by the Catalogue of Life via ChecklistBank.

    Keys are rank names (lowercase): kingdom, phylum, class, order, family,
    genus, species. Values are strings, or None if COL did not return that rank.
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
    resp = requests.get(
        f"{CLB_BASE}/dataset/{DATASET}/match/nameusage",
        params={"q": species_name},
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("matchType") == "NONE" or "usage" not in data:
        return {}

    usage = data["usage"]

    # The classification array lists ancestor taxa from kingdom down to genus.
    # Each entry has "rank" and "name" (the scientific name at that rank).
    taxonomy = {}
    for entry in usage.get("classification", []):
        rank = entry.get("rank", "").lower()
        if rank in RANKS:
            taxonomy[rank] = entry.get("name")

    # The species itself is in usage["name"] (excludes authorship)
    species_name_result = usage.get("name", "").strip()
    if species_name_result:
        taxonomy["species"] = species_name_result

    # Return all standard ranks, None for any that weren't returned
    return {rank: taxonomy.get(rank) for rank in RANKS}


if __name__ == "__main__":
    import json

    result = get_col_taxonomy("Amanita muscaria")
    print(json.dumps(result, indent=2))