"""
ChecklistBank.py — Catalogue of Life / ChecklistBank API client

Queries the ChecklistBank API against the latest Catalogue of Life release
(3LR) to retrieve species-level synonyms for a given species name.

Main entry point: get_checklistbank_synonyms(query)
"""

import requests

CLB_BASE = "https://api.checklistbank.org"
DATASET = "3LR"  # Latest COL release


def main():
    import json

    result = get_checklistbank_synonyms("Amanita muscaria")
    print(json.dumps(result, indent=2))


def _binomial(label: str) -> str:
    """Return just the first two words (genus + species epithet) from a full name label."""
    parts = label.strip().split()
    return " ".join(parts[:2]) if len(parts) >= 2 else label.strip()


def get_checklistbank_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names from
    the Catalogue of Life via ChecklistBank.

    Keys are the accepted species name and all COL synonyms at SPECIES rank,
    truncated to genus + epithet only (e.g. "Amanita muscaria" not
    "Amanita muscaria (L.) Lam.").
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if no match is found.

    Example:
        {"Amanita muscaria": [], "Agaricus muscarius": []}
    """
    if not species_name or not species_name.strip():
        return {}

    # Step 1: Match the species name to get the taxon ID
    match_resp = requests.get(
        f"{CLB_BASE}/dataset/{DATASET}/match/nameusage",
        params={"q": species_name},
    )
    match_resp.raise_for_status()
    match_data = match_resp.json()

    if match_data.get("matchType") == "NONE" or "usage" not in match_data:
        return {}

    usage = match_data["usage"]
    accepted_name = _binomial(usage.get("label", species_name))
    taxon_id = usage.get("id")

    if not taxon_id:
        return {}

    # Step 2: Fetch synonyms for the matched taxon
    syn_resp = requests.get(
        f"{CLB_BASE}/dataset/{DATASET}/taxon/{taxon_id}/synonyms",
    )
    syn_resp.raise_for_status()
    syn_data = syn_resp.json()

    synonyms: list[str] = [accepted_name]

    # Response has three keys: homotypic (list), heterotypic (list),
    # heterotypicGroups (list of lists). Collect species-rank entries from all.
    all_items = (
        syn_data.get("homotypic", [])
        + syn_data.get("heterotypic", [])
    )
    for group in syn_data.get("heterotypicGroups", []):
        all_items += group

    for item in all_items:
        name = _binomial(item.get("label", "").strip())
        rank = item.get("name", {}).get("rank", "")
        if name and rank == "species" and name not in synonyms:
            synonyms.append(name)

    return {name: [] for name in synonyms}


if __name__ == "__main__":
    main()