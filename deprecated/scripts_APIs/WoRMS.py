"""
WoRMS.py — WoRMS (World Register of Marine Species) API client

Queries the WoRMS REST API to retrieve species-level synonym names
for a given species name.

Uses two HTTP calls:
  1. AphiaRecordsByName — find the valid AphiaID and accepted name for the species
  2. AphiaSynonymsByAphiaID — get all names linked to the accepted taxon

WoRMS returns HTTP 204 No Content when a name or synonym list is not found,
so both calls check the status code before parsing JSON.

Main entry point: get_worms_synonyms(query)
"""

import requests

from scripts.utils.normalize_query_string import normalize_query_string

BASE_URL = "https://www.marinespecies.org/rest"

# taxonRankID value for species-level records in WoRMS
_SPECIES_RANK_ID = 220


def main():
    import json

    result = get_worms_synonyms("Macrocystis pyrifera")
    print(json.dumps(result, indent=2))


def _lookup_name(species_name: str) -> tuple[int | None, str | None]:
    """
    Look up a species name in WoRMS and return (valid_AphiaID, valid_name).
    Returns (None, None) if the name is not found or no species-level record exists.

    Works for both accepted names and synonyms: valid_AphiaID always points to
    the accepted taxon regardless of which name is queried.
    """
    resp = requests.get(
        f"{BASE_URL}/AphiaRecordsByName/{species_name}",
        params={"like": "false", "marine_only": "false", "offset": 1},
    )
    if resp.status_code == 204 or not resp.text:
        return None, None
    resp.raise_for_status()

    for rec in resp.json():
        if rec.get("taxonRankID") == _SPECIES_RANK_ID:
            return rec["valid_AphiaID"], rec["valid_name"]
    return None, None


def _get_synonym_names(valid_aphia_id: int) -> list[str]:
    """
    Return species-level synonym names for the given accepted AphiaID.
    Returns an empty list if there are no synonyms or the API returns no content.
    """
    resp = requests.get(f"{BASE_URL}/AphiaSynonymsByAphiaID/{valid_aphia_id}")
    if resp.status_code == 204 or not resp.text:
        return []
    resp.raise_for_status()

    return [
        rec["scientificname"]
        for rec in resp.json()
        if rec.get("taxonRankID") == _SPECIES_RANK_ID
    ]


def get_worms_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names from WoRMS.

    Keys are the queried species name and all species-rank synonyms found.
    Infraspecific names are excluded by WoRMS rank ID filtering (not regex).
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if the species is not found in WoRMS.

    When the queried name is itself a synonym, the accepted name is included so
    that lookups work both ways.

    Example:
        {"Macrocystis pyrifera": [], "Macrocystis integrifolia": [], "Fucus giganteus": []}
    """
    if not species_name or not species_name.strip():
        return {}

    species_name = normalize_query_string(species_name)

    valid_aphia_id, valid_name = _lookup_name(species_name)
    if valid_aphia_id is None:
        return {}

    synonym_names = _get_synonym_names(valid_aphia_id)

    seen: set[str] = {species_name}
    synonyms = [species_name]
    # When the queried name is a synonym, include the accepted name so lookup is bidirectional
    if valid_name and valid_name != species_name and valid_name not in seen:
        seen.add(valid_name)
        synonyms.append(valid_name)
    for name in synonym_names:
        if name not in seen:
            seen.add(name)
            synonyms.append(name)

    return {name: [] for name in synonyms}


if __name__ == "__main__":
    main()
