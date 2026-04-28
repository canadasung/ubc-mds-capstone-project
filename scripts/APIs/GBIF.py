import requests


def get_gbif_synonyms(species_name: str) -> list[str]:
    """
    Given a species name, returns a dict where:
      - keys are distinct species-level names (2-token canonical names)
      - values are lists of subspecies/variety synonyms that fall under that key

    Returns a plain string message if no backbone match is found.
    """

    # Step 1: Match the name to the GBIF Backbone
    match_resp = requests.get(
        "https://api.gbif.org/v1/species/match",
        params={"name": species_name, "strict": "true"},
    )
    match_resp.raise_for_status()
    match_data = match_resp.json()

    if match_data.get("matchType") == "NONE":
        return f"No backbone match found for '{species_name}'"

    usage_key = match_data["usageKey"]

    # Step 2: Fetch synonyms using the backbone usageKey
    synonyms_resp = requests.get(
        f"https://api.gbif.org/v1/species/{usage_key}/synonyms",
        params={"limit": 100},
    )
    synonyms_resp.raise_for_status()
    synonyms_data = synonyms_resp.json()

    canonical_names: list[str] = list(
        dict.fromkeys(r["canonicalName"] for r in synonyms_data.get("results", []))
    )
    # Step 3: Separate species-level names (2 tokens) from infraspecific ones (3+ tokens)
    species_keys: list[str] = []
    infraspecific: list[str] = []

    for name in canonical_names:
        if len(name.split()) == 2:
            species_keys.append(name)
        else:
            infraspecific.append(name)

    # Step 4: Build the dict — every species key starts with an empty list
    result: dict[str, list[str]] = {key: [] for key in species_keys}

    # Step 5: Assign each infraspecific name under its matching species key
    # (matched by "Genus species" prefix)
    for sub in infraspecific:
        tokens = sub.split()
        parent = f"{tokens[0]} {tokens[1]}"
        if parent in result:
            result[parent].append(sub)
        else:
            # Parent species wasn't in the synonym list — add it on the fly
            result[parent] = [sub]

    return result


if __name__ == "__main__":
    import json

    result = get_gbif_synonyms("Amanita muscaria")

    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2))
