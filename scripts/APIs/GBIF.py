import requests

# Maps GBIF rank strings to output category keys
_RANK_CATEGORIES = {
    "SUBSPECIES": "subspecies",
    "VARIETY": "varieties",
    "FORM": "forms",
    "SPECIES": "synonyms",
}


def get_gbif_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names from GBIF.

    Keys are the accepted species name and all GBIF synonyms at SPECIES rank.
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if no backbone match is found.

    Note: rank category data (subspecies, varieties, forms, etc.) is in-progress
    and will be populated in the empty lists in a future update.

    Example:
        {"Amanita muscaria": [], "Agaricus muscarius": []}
    """
    match_resp = requests.get(
        "https://api.gbif.org/v1/species/match",
        params={"name": species_name, "strict": "true"},
    )
    match_resp.raise_for_status()
    match_data = match_resp.json()

    if match_data.get("matchType") == "NONE":
        return {}

    accepted_name = match_data.get("species", species_name)
    usage_key = match_data["usageKey"]

    synonyms_resp = requests.get(
        f"https://api.gbif.org/v1/species/{usage_key}/synonyms",
        params={"limit": 100},
    )
    synonyms_resp.raise_for_status()

    synonyms: list[str] = [accepted_name]

    for result in synonyms_resp.json().get("results", []):
        rank = result.get("rank", "")
        canonical = result.get("canonicalName", "")
        if not canonical or rank != "SPECIES":
            continue
        if canonical not in synonyms:
            synonyms.append(canonical)

        # category = _RANK_CATEGORIES[rank]
        # epithet = canonical.removeprefix(accepted_name).strip()
        # if not epithet:
        #     epithet = canonical
        # categories.setdefault(category, [])
        # if epithet not in categories[category]:
        #     categories[category].append(epithet)

    return {name: [] for name in synonyms}


if __name__ == "__main__":
    import json

    result = get_gbif_synonyms("Amanita muscaria")
    print(json.dumps(result, indent=2))
