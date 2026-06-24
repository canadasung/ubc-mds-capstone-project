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

# Symbiota portal queries, keyed by fixture-folder slug. Each entry carries the
# portal's display_name (passed to SymbiotaAPI) plus the three scenario queries.
# Accepted/synonym names are sourced from
# notebooks/apis_pipe/get_synonyms_for_all_apis.ipynb (cell 21). Kept separate
# from API_QUERIES because of the extra portal_name key.
SYMBIOTA_QUERIES: dict[str, dict[str, str]] = {
    "mycoportal": {
        "portal_name": "MyCoPortal",
        "accepted": "Agaricus campestris",
        "synonym": "Psalliota villatica",
        "not_found": "Not species",
    },
    "lichen_portal": {
        "portal_name": "Lichen Portal",
        "accepted": "Xanthoria parietina",
        "synonym": "Physcia parietina",
        "not_found": "Not species",
    },
    "bryophyte_portal": {
        "portal_name": "Bryophyte Portal",
        "accepted": "Pohlia nutans",
        "synonym": "Webera nutans",
        "not_found": "Not species",
    },
    "cch2": {
        "portal_name": "CCH2",
        "accepted": "Heteromeles arbutifolia",
        "synonym": "Photinia arbutifolia",
        "not_found": "Not species",
    },
    "sernec": {
        "portal_name": "SERNEC",
        "accepted": "Magnolia grandiflora",
        "synonym": "Magnolia foetida",
        "not_found": "Not species",
    },
    "nansh": {
        "portal_name": "NANSH",
        "accepted": "Rudbeckia hirta",
        "synonym": "Coreopsis hirta",
        "not_found": "Not species",
    },
    "algae_herbarium_portal": {
        "portal_name": "Algae Herbarium Portal",
        "accepted": "Ulva intestinalis",
        "synonym": "Ilea intestinalis",
        "not_found": "Not species",
    },
    "pterido_portal": {
        "portal_name": "Pterido Portal",
        "accepted": "Dryopteris filix-mas",
        "synonym": "Nephrodium filix-mas",
        "not_found": "Not species",
    },
    "cnh": {
        "portal_name": "CNH",
        "accepted": "Impatiens capensis",
        "synonym": "Impatiens biflora",
        "not_found": "Not species",
    },
    "mid_atlantic": {
        "portal_name": "Mid-Atlantic Herbaria Consortium",
        "accepted": "Quercus rubra",
        "synonym": "Quercus maxima",
        "not_found": "Not species",
    },
    "swbiodiversity": {
        "portal_name": "swbiodiversity",
        "accepted": "Larrea tridentata",
        "synonym": "Larrea mexicana",
        "not_found": "Not species",
    },
}
