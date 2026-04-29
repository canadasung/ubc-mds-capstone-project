import re

import requests

BASE_URL = "https://mushroomobserver.org/api2"

# Maps rank abbreviations found in MushroomObserver names to category keys.
# Order matters: longer/more specific patterns must come before shorter ones
# (e.g. "subsect." before "sect.", "subsp." before "sp.").
_RANK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bsubsp\.\s*", re.IGNORECASE), "subspecies"),
    (re.compile(r"\bssp\.\s*", re.IGNORECASE), "subspecies"),
    (re.compile(r"\bs\.\s*", re.IGNORECASE), "subspecies"),
    (re.compile(r"\bvar\.\s*", re.IGNORECASE), "varieties"),
    (re.compile(r"\bv\.\s*", re.IGNORECASE), "varieties"),
    (re.compile(r"\bform\.\s*", re.IGNORECASE), "forms"),
    (re.compile(r"\bfo\.\s*", re.IGNORECASE), "forms"),
    (re.compile(r"\bf\.\s*", re.IGNORECASE), "forms"),
    (re.compile(r"\bsubsect\.\s*", re.IGNORECASE), "subsections"),
    (re.compile(r"\bsect\.\s*", re.IGNORECASE), "sections"),
    (re.compile(r"\bsubgen\.\s*", re.IGNORECASE), "subgenera"),
    (re.compile(r"\bsubg\.\s*", re.IGNORECASE), "subgenera"),
    (re.compile(r"\bser\.\s*", re.IGNORECASE), "series"),
    (re.compile(r"\bstirps\s*", re.IGNORECASE), "stirps"),
    (re.compile(r"\b(gr\.|gp\.|clade|complex|group)\s*", re.IGNORECASE), "groups"),
    (re.compile(r"\bcv\.\s*", re.IGNORECASE), "cultivars"),
]


def _parse_synonym(full_name: str, species_prefix: str) -> tuple[str, str]:
    """
    Determine the rank category and terminal epithet for a synonym name.

    Returns (category, epithet). Category defaults to "synonyms" for
    species-level names with no rank abbreviation.
    """
    after_prefix = full_name.removeprefix(species_prefix).strip()

    for pattern, category in _RANK_PATTERNS:
        epithet = pattern.sub("", after_prefix).strip()
        if epithet != after_prefix:
            return category, epithet

    # No rank abbreviation found — treat as a species-level synonym
    epithet = after_prefix if after_prefix else full_name
    return "synonyms", epithet


def get_mushroom_observer_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names from MushroomObserver.

    Keys are the queried species name and all MO synonyms that are not misspellings
    and have no infraspecific rank abbreviation (var., subsp., f., etc.).
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if no matching name is found on MushroomObserver.

    Note: rank category data (subspecies, varieties, forms, etc.) is in-progress
    and will be populated in the empty lists in a future update.

    Example:
        {"Amanita muscaria": [], "Agaricus muscarius": []}
    """
    resp = requests.get(
        f"{BASE_URL}/names",
        params={"name": species_name, "format": "json", "detail": "high"},
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("number_of_records", 0) == 0:
        return {}

    synonyms: list[str] = [species_name]
    seen: set[str] = set([species_name])

    for result in data.get("results", []):
        for synonym in result.get("synonyms", []):
            full_name = synonym.get("name", "")
            if not full_name or full_name in seen or " sp." in full_name:
                continue
            seen.add(full_name)

            # Skip misspellings and infraspecific taxa — keep only species-level synonyms
            if synonym.get("misspelled", False):
                continue
            category, _ = _parse_synonym(full_name, species_name)
            if category != "synonyms":
                continue

            synonyms.append(full_name)

            # epithet = full_name.removeprefix(species_name).strip() or full_name
            # categories.setdefault("misspellings", [])
            # if epithet not in categories["misspellings"]:
            #     categories["misspellings"].append(epithet)

            # category, epithet = _parse_synonym(full_name, species_name)
            # categories.setdefault(category, [])
            # if epithet not in categories[category]:
            #     categories[category].append(epithet)

    return {name: [] for name in synonyms}


if __name__ == "__main__":
    import json

    result = get_mushroom_observer_synonyms("Amanita muscaria")
    print(json.dumps(result, indent=2))
