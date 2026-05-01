"""
fuzzy_search.py

Fuzzy species name lookup against the GBIF Backbone Taxonomy.

    from scripts.utils.fuzzy_search import fuzzy_search

    fuzzy_search("Amanita muscaria")  # exact match  -> "Amanita muscaria"
    fuzzy_search("Amanita muscara")   # no exact match -> ['Amanita muscaria', 'Amanitaria muscaria']
"""

import requests

GBIF_BASE = "https://api.gbif.org/v1"


def fuzzy_search(query):
    """
    Search the GBIF Backbone Taxonomy for a species name.

    Returns the matched name as a string if an exact match is found.
    Returns a list of up to 10 suggested name strings if no exact match is found.
    """
    # Try to match the query against the GBIF backbone taxonomy.
    # strict=false allows fuzzy matching, not just exact.
    match_resp = requests.get(
        f"{GBIF_BASE}/species/match",
        params={"name": query, "strict": "false"},
        timeout=10,
    )
    match_resp.raise_for_status()
    match = match_resp.json()

    # Case: NONE
    if match.get("matchType") == "NONE":
        return []

    # Case: EXACT
    # If GBIF found an exact match, return the accepted name immediately
    if match.get("matchType") == "EXACT":
        # "species" is only populated when the match is at species rank.
        # "canonicalName" is always present and covers genus/family matches.
        # e.g. searching "Amanita" (a genus) returns species=None,
        # so we fall back to canonicalName to avoid returning None.
        #print(f'species: {match.get("species")}')
        #print(f'canonicalName: {match.get("canonicalName")}')
        return match.get("species") or match.get("canonicalName")

    # Case: FUZZY or HIGHERRANK
    # No exact match, so fetch ranked suggestions for the query string
    suggest_query = match.get("species") or match.get("canonicalName") or query
    suggest_resp = requests.get(
        f"{GBIF_BASE}/species/suggest",
        params={"q": suggest_query, "limit": 10, "rank": "SPECIES"},
        timeout=10,
    )
    suggest_resp.raise_for_status()

    # Build a deduplicated list of candidate names.
    # The suggest endpoint can return the same species under multiple checklists.
    seen = set()
    suggestions = []
    for s in suggest_resp.json():
        name = s.get("canonicalName", "")
        if name and name not in seen:
            seen.add(name)
            suggestions.append(name)

    return suggestions


if __name__ == "__main__":
    for query in ["Amanita muscaria", "Amanita muscara", "fly agaric", " ", ""]:
        print(f"{query!r} -> {fuzzy_search(query)}")
