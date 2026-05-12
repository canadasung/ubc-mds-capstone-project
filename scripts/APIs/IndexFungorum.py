"""
IndexFungorum.py — Index Fungorum API client

Queries the Index Fungorum web service to retrieve species-level synonyms
for a given fungal species name.

Uses two HTTP GET calls:
  1. NameSearch — find the accepted record key for the species
  2. NamesByCurrentKey — find all names that point to that key (synonyms)

Main entry point: get_indexfungorum_synonyms(query)
"""

import time
import xml.etree.ElementTree as ET

import requests

IF_BASE = "https://www.indexfungorum.org/ixfwebservice/fungus.asmx"

# Index Fungorum encodes spaces as _x0020_ in XML tag names
NAME_TAG = "NAME_x0020_OF_x0020_FUNGUS"
RECORD_TAG = "RECORD_x0020_NUMBER"
CURRENT_KEY_TAG = "CURRENT_x0020_NAME_x0020_RECORD_x0020_NUMBER"
INFRASPECIFIC_RANK_TAG = "INFRASPECIFIC_x0020_RANK"


def main():
    import json

    result = get_indexfungorum_synonyms("Amanita muscaria")
    print(json.dumps(result, indent=2))


def _parse_records(xml_text: str) -> list[ET.Element]:
    """Parse XML response and return all IndexFungorum record elements."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    return root.findall("IndexFungorum")


def _name_search(species_name: str) -> int | None:
    """
    Search Index Fungorum for a species name and return its accepted record key.
    Returns None if no match is found.
    """
    resp = requests.get(
        f"{IF_BASE}/NameSearch",
        params={
            "SearchText": species_name,
            "AnywhereInText": "false",
            "MaxNumber": "10",
        },
        timeout=30,
    )
    resp.raise_for_status()

    for record in _parse_records(resp.text):
        name = (record.findtext(NAME_TAG) or "").strip()
        rank = (record.findtext(INFRASPECIFIC_RANK_TAG) or "").strip()
        current_key = record.findtext(CURRENT_KEY_TAG)

        # Species-level records have rank "sp." and name matches query exactly
        if name.lower() == species_name.lower() and rank == "sp." and current_key:
            try:
                return int(current_key.strip())
            except ValueError:
                return None

    return None


def _names_by_current_key(key: int) -> list[str]:
    """
    Given an accepted record key, return all species-level names that list it
    as their current name — i.e. the synonyms.
    """
    resp = requests.get(
        f"{IF_BASE}/NamesByCurrentKey",
        params={"CurrentKey": str(key)},
        timeout=30,
    )
    resp.raise_for_status()

    names = []
    for record in _parse_records(resp.text):
        name = (record.findtext(NAME_TAG) or "").strip()
        rank = (record.findtext(INFRASPECIFIC_RANK_TAG) or "").strip()
        if name and rank == "sp.":
            names.append(name)
    return names


def get_indexfungorum_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names
    from Index Fungorum.

    Keys are the queried species name and all synonyms found.
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if no match is found.

    Example:
        {"Amanita muscaria": [], "Agaricus muscarius": []}
    """
    key = _name_search(species_name)
    if key is None:
        return {}

    time.sleep(0.5)
    synonym_names = _names_by_current_key(key)

    synonyms = [species_name] + [
        n for n in synonym_names if n.lower() != species_name.lower()
    ]
    return {name: [] for name in synonyms}


if __name__ == "__main__":
    main()