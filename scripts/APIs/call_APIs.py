"""
call_APIs.py — Unified API query interface

Calls any combination of GBIF, GenBank, and MushroomObserver synonym APIs for a single species query and returns their results combined as a dict.
"""

import json
from typing import Literal

from scripts.APIs.BryophytePortal import get_bryophyteportal_synonyms
from scripts.APIs.COL import get_checklistbank_synonyms
from scripts.APIs.GBIF import get_gbif_synonyms
from scripts.APIs.GenBank import get_genbank_synonyms
from scripts.APIs.IndexFungorum import get_indexfungorum_synonyms
from scripts.APIs.Macroalgae import get_macroalgae_synonyms
from scripts.APIs.MushroomObs import get_mushroom_observer_synonyms
from scripts.APIs.MyCoPortal import get_mycoportal_synonyms

Source = Literal[
    "gbif",
    "genbank",
    "mushroomobs",
    "mycoportal",
    "bryophyteportal",
    "macroalgae",
    "indexfungorum",
    "col",
]


def main():
    result = call_apis("Amanita muscaria", sources=["gbif", "genbank", "mushroomobs"])
    print(result)


def call_apis(
    query: str,
    sources: list[Source] | None = None,
) -> str:
    """
    Query one or more taxonomy APIs and return their combined results as JSON.

    Parameters:
    query   : Scientific name to search (e.g. "Amanita muscaria").
    sources : Which APIs to call. Defaults to all three if omitted.
              Valid values: "gbif", "genbank", "mushroomobs".

    Returns a JSON string with a key per requested source. Each value is a dict
    whose keys are species-level synonym names (including the query itself) and
    whose values are empty lists (placeholders for rank categories to be added).
    Returns an error string for that source if the call failed.

    Note: rank category data (subspecies, varieties, forms, etc.) is in-progress
    and will be populated in the empty lists in a future update.

    Example output:
    {
      "gbif":        {"Amanita muscaria": [], "Agaricus muscarius": []},
      "genbank":     {"Amanita muscaria": [], "Agaricus muscarius": []},
      "mushroomobs": {"Amanita muscaria": [], "Agaricus muscarius": []}
    }
    """

    results = {}

    if sources is None:
        return json.dumps(results, indent=2)

    for source in sources:
        try:
            if source == "gbif":
                results["gbif"] = get_gbif_synonyms(query)
            elif source == "genbank":
                results["genbank"] = get_genbank_synonyms(query)
            elif source == "mushroomobs":
                results["mushroomobs"] = get_mushroom_observer_synonyms(query)
            elif source == "mycoportal":
                results["mycoportal"] = get_mycoportal_synonyms(query)
            elif source == "bryophyteportal":
                results["bryophyteportal"] = get_bryophyteportal_synonyms(query)
            elif source == "macroalgae":
                results["macroalgae"] = get_macroalgae_synonyms(query)
            elif source == "indexfungorum":
                results["indexfungorum"] = get_indexfungorum_synonyms(query)
            elif source == "col":
                results["col"] = get_checklistbank_synonyms(query)
            else:
                results[source] = f"Unknown source '{source}'"
        except Exception as e:
            results[source] = f"Error: {e}"

    return json.dumps(results, indent=2)


if __name__ == "__main__":
    main()
