import requests

def get_gbif_synonyms(species_name: str) -> list[str]:
    """
    Given a species name, returns a deduplicated list of synonyms from the GBIF Backbone.
    """
    # Step 1: Match the name to the GBIF Backbone
    match_resp = requests.get(
        "https://api.gbif.org/v1/species/match",
        params={"name": species_name, "strict": "true"}
    )
    match_resp.raise_for_status()
    match_data = match_resp.json()

    if match_data.get("matchType") == "NONE":
        raise ValueError(f"No backbone match found for '{species_name}'")

    usage_key = match_data["usageKey"]

    # Step 2: Fetch synonyms using the backbone usageKey
    synonyms_resp = requests.get(
        f"https://api.gbif.org/v1/species/{usage_key}/synonyms",
        params={"limit": 100}
    )
    synonyms_resp.raise_for_status()
    synonyms_data = synonyms_resp.json()

    # Step 3: Extract, deduplicate, and return
    synonyms = list(dict.fromkeys(
        r["canonicalName"] for r in synonyms_data.get("results", [])
    ))
    return synonyms


if __name__ == "__main__":
    result = get_gbif_synonyms("Aureonarius armiae")
    print(f"Found {len(result)} synonyms:")
    for s in result:
        print(f"  {s}")
