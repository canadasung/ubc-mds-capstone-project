"""
GBIF_taxonomy.py — GBIF taxonomy API client

Queries the GBIF species/match endpoint and returns a dict mapping
standard taxonomic ranks to their names for the matched species.

Main entry point: get_gbif_taxonomy(species_name)
"""

import requests

RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]


def get_gbif_taxonomy(species_name: str) -> dict:
    """
    Given a species name, returns a dict mapping taxonomic ranks to names
    as reported by the GBIF backbone taxonomy.

    Keys are rank names (lowercase): kingdom, phylum, class, order, family,
    genus, species. Values are strings, or None if GBIF did not return that rank.
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
        "https://api.gbif.org/v1/species/match",
        params={"name": species_name, "strict": "true"},
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("matchType") == "NONE":
        return {}

    return {rank: data.get(rank) for rank in RANKS}


if __name__ == "__main__":
    import json

    result = get_gbif_taxonomy("Amanita muscaria")
    print(json.dumps(result, indent=2))