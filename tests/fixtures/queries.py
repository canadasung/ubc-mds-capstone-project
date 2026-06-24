"""
Single source of truth for API test query names.

Imported by tests/fixtures/_fetchers.py (fixture generation/checking) and
tests/scripts/apis_pipe/ (unit tests). Edit query names here only.
"""

API_QUERIES: dict[str, dict[str, str]] = {
    "gbif": {
        "accepted": "Amanita muscaria",
        "synonym": "Agaricus muscarius",
        "not_found": "Not species",
    },
    "col": {
        "accepted": "Quercus robur",
        "synonym": "Quercus atrosanguinea",
        "not_found": "Not species",
    },
    "tropicos": {
        "accepted": "Quercus robur",
        "synonym": "Quercus pedunculata",
        "not_found": "Not species",
    },
    "fishbase": {
        "accepted": "Gadus morhua",
        "synonym": "Gadus callarias",
        "not_found": "Not species",
    },
    "genbank": {
        "accepted": "Amanita muscaria",
        "synonym": "Agaricus muscarius",
        "not_found": "Not species",
    },
    "index_fungorum": {
        "accepted": "Amanita muscaria",
        "synonym": "Agaricus muscarius",
        "not_found": "Not species",
    },
    "mushroom_observer": {
        "accepted": "Amanita muscaria",
        "synonym": "Amanita amerimuscaria",
        "not_found": "Not species",
    },
    "itis": {
        "accepted": "Oncorhynchus mykiss",
        "synonym": "Salmo mykiss",
        "not_found": "Not species",
    },
}
