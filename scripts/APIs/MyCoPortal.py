"""
MyCoPortal.py — MyCoPortal (Symbiota) API client

Queries the MyCoPortal portal to retrieve species-level synonym names
for a given fungal species name.

Uses three HTTP calls:
  1. gettaxasuggest RPC — find the taxon ID (tid) for the species name
  2. REST API /taxonomy/{tid} — resolve to the accepted taxon if input is a synonym
  3. Taxa HTML page — scrape synonym names from the embedded synonymDiv

Main entry point: get_mycoportal_synonyms(query)
"""

import re

import requests

BASE_URL = "https://mycoportal.org/portal"

_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Matches rank abbreviations that indicate an infraspecific taxon.
# No trailing \b — the abbreviation ends with "." (non-word char), so \b after it never fires.
_INFRASPECIFIC_RE = re.compile(
    r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|subf\.|cv\.|sect\.|subsect\.|ser\.)",
    re.IGNORECASE,
)


def main():
    import json

    result = get_mycoportal_synonyms("Gymnopus dryophilus")
    print(json.dumps(result, indent=2))


def _get_tid(species_name: str) -> int | None:
    """Return the taxon ID for an exact species name match, or None if not found."""
    resp = requests.get(
        f"{BASE_URL}/taxa/taxonomy/rpc/gettaxasuggest.php",
        params={"term": species_name},
        headers=_HEADERS,
    )
    resp.raise_for_status()
    for item in resp.json():
        label = item.get("label", "")
        # Label format: "Genus species (Author) Author2" — match on name part only
        if re.match(rf"^{re.escape(species_name)}(\s|$)", label):
            return int(item["id"])
    return None


def _resolve_accepted_tid(tid: int) -> int:
    """
    Return the accepted taxon's tid.
    If the taxon is already accepted, returns the same tid.
    If it's a synonym, returns the accepted taxon's tid.
    """
    resp = requests.get(f"{BASE_URL}/api/v2/taxonomy/{tid}", headers=_HEADERS)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "synonym":
        return data["accepted"]["tid"]
    return tid


def _scrape_synonyms(accepted_tid: int) -> list[str]:
    """
    Fetch the taxa HTML page for the accepted tid and return species-level
    synonym names parsed from the synonymDiv element.
    """
    resp = requests.get(
        f"{BASE_URL}/taxa/index.php",
        params={"tid": accepted_tid},
        headers=_HEADERS,
    )
    resp.raise_for_status()

    syn_match = re.search(
        r'id="synonymDiv"[^>]*>(.*?)</div>', resp.text, re.DOTALL
    )
    if not syn_match:
        return []

    names = []
    for name in re.findall(r"<i>(.*?)</i>", syn_match.group(1)):
        if name and not _INFRASPECIFIC_RE.search(name):
            names.append(name)
    return names


def get_mycoportal_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names from MyCoPortal.

    Keys are the queried species name and all species-rank synonyms found.
    Infraspecific names (var., subsp., f., etc.) are excluded.
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if the species is not found in MyCoPortal.

    Example:
        {"Gymnopus dryophilus": [], "Collybia dryophila": [], "Marasmius dryophilus": []}
    """
    if not species_name or not species_name.strip():
        return {}

    # gettaxasuggest returns no results for a lowercase genus (observed behaviour) —
    # capitalise the first character to match the portal's stored names
    species_name = species_name[0].upper() + species_name[1:]

    tid = _get_tid(species_name)
    if tid is None:
        return {}

    accepted_tid = _resolve_accepted_tid(tid)
    synonym_names = _scrape_synonyms(accepted_tid)

    seen: set[str] = {species_name}
    synonyms = [species_name]
    for name in synonym_names:
        if name not in seen:
            seen.add(name)
            synonyms.append(name)

    return {name: [] for name in synonyms}


if __name__ == "__main__":
    main()
