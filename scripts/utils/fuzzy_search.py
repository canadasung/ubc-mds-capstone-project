"""
fuzzy_search.py

Fuzzy species name lookup against the GBIF Backbone Taxonomy.

    from scripts.utils.fuzzy_search import fuzzy_search

    fuzzy_search("Amanita muscaria")  # exact match  -> ["Amanita muscaria"]
    fuzzy_search("Amanita muscara")   # no exact match -> ['Amanita muscaria', 'Amanitaria muscaria']
"""

import requests

GBIF_BASE = "https://api.gbif.org/v1"


def fuzzy_search(query):
    """
    Search the GBIF Backbone Taxonomy for a species name.

    Always returns a list. Returns a single-item list for exact species matches,
    or a deduplicated list of suggestions from /species/suggest otherwise.
    """
    # strict=false allows fuzzy matching, not just exact.
    match_resp = requests.get(
        f"{GBIF_BASE}/species/match",
        params={"name": query, "strict": "false"},
        timeout=30,
    )
    match_resp.raise_for_status()
    match = match_resp.json()

    match_type = match.get("matchType")

    # Case: EXACT at species rank or FUZZY — return single-item list with the resolved name.
    if (
        match_type == "EXACT" and match.get("rank") == "SPECIES"
    ) or match_type == "FUZZY":
        return [match.get("canonicalName")]

    suggest_query = query

    # All other cases (HIGHERRANK, NONE, or EXACT above species rank) fall through to /species/suggest.
    # /species/suggest is an independent prefix search and can surface candidates even when the backbone match fails entirely.
    suggest_resp = requests.get(
        f"{GBIF_BASE}/species/suggest",
        params={"q": suggest_query, "limit": 10, "rank": "SPECIES"},
        timeout=30,
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
