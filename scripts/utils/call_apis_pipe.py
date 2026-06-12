"""
Top-level entry point for the species data pipeline.

This module wires together all API clients, the TaxonRouter, and the SynonymEngine
into a single callable function (`call_apis_pipe`). Callers only need to provide a
scientific name; the pipeline handles routing and synonym discovery automatically.

Typical usage:
    from scripts.utils.call_apis_pipe import call_apis
    payload = call_apis("Amanita muscaria")
"""

import json
from typing import List, Optional

from deprecated.synonyms import SynonymEngine
from scripts.apis_pipe.col import COLAPI

# import API client implementations
from scripts.apis_pipe.gbif import GBIFAPI
from scripts.apis_pipe.genbank import GenBankAPI
from scripts.apis_pipe.index_fungorum import IndexFungorumAPI
from scripts.apis_pipe.mushroomobs import MushroomObserverAPI
from scripts.apis_pipe.symbiota import SymbiotaAPI
from scripts.apis_pipe.tropicos import TropicosAPI
from scripts.utils.router import TaxonRouter

# Flexible alias for source strings
Source = str


def _make_clients() -> dict:
    """
    Initialize and return a dictionary of all active API clients.

    Each key is the canonical string identifier used throughout the pipeline
    (by TaxonRouter and SynonymEngine). Symbiota portals are keyed by the
    pattern "symbiota_<portal>" so they can be identified as a group downstream.

    Returns:
        dict: Mapping of string key → initialized SpeciesAPI instance.
    """
    clients = {
        "gbif": GBIFAPI(),
        "col": COLAPI(),
        "tropicos": TropicosAPI(),
        "index_fungorum": IndexFungorumAPI(),
        "genbank": GenBankAPI(),
        "mushroomobs": MushroomObserverAPI(),
        # Symbiota Portals
        "symbiota_mycoportal": SymbiotaAPI("https://mycoportal.org/portal"),
        "symbiota_lichen": SymbiotaAPI("https://lichenportal.org/portal"),
        "symbiota_bryophyte": SymbiotaAPI("https://bryophyteportal.org/portal"),
        "symbiota_cch2": SymbiotaAPI("https://cch2.org/portal"),
        "symbiota_sernec": SymbiotaAPI("https://sernecportal.org/portal"),
        "symbiota_nansh": SymbiotaAPI("https://nansh.org/portal"),
        "symbiota_swbiodiversity": SymbiotaAPI("https://swbiodiversity.org/seinet"),
        "symbiota_macroalgae": SymbiotaAPI("https://macroalgae.org/portal"),
        "symbiota_pterido": SymbiotaAPI("https://pteridoportal.org/portal"),
        "symbiota_neherbaria": SymbiotaAPI("https://neherbaria.org/portal"),
        "symbiota_midatlantic": SymbiotaAPI("https://midatlanticherbaria.org/portal"),
    }
    return clients


def call_apis(query: str, sources: Optional[List[Source]] = None) -> str:
    """
    Orchestrate synonym retrieval for a scientific name.

    Runs the full pipeline in three steps:
      1. Fetch official synonyms from backbone APIs (GBIF, COL, Tropicos, Index Fungorum).
      2. Fetch synonyms from Symbiota portals and independent sources (e.g. Mushroom Observer).
      3. Return a single JSON payload combining all synonym groups.

    Args:
        query (str): The accepted scientific name to search (e.g. "Amanita muscaria").
        sources (Optional[List[str]]): Explicit list of API keys (matching keys in
            `_make_clients()`) to query. If None, TaxonRouter selects sources based
            on the taxon's kingdom.

    Returns:
        str: JSON string with one top-level key:
            - "synonyms": dict with "official", "symbiota", and "independent" sub-keys,
              each containing synonym records from those source groups.
    """
    clients = _make_clients()

    # Initialize engines with required clients
    router = TaxonRouter(clients["gbif"])
    syn_engine = SynonymEngine(
        clients["gbif"],
        clients["tropicos"],
        clients["index_fungorum"],
        clients["col"],
    )

    # Decide which APIs to query
    selected = sources if sources else router.route(query)

    # --- 1. Fetch Official Synonyms ---
    try:
        official_syns = syn_engine.get_synonyms(query)
    except Exception as e:
        official_syns = [{"error": f"Official synonym lookup failed: {e}"}]

    # --- 2. Fetch Symbiota & Independent Synonyms ---
    symbiota_syns = {}
    independent_syns = {}
    backbones = ["gbif", "col", "tropicos", "index_fungorum"]

    for key in selected:
        client = clients.get(key)
        if client and hasattr(client, "synonyms"):
            if key.startswith("symbiota_"):
                try:
                    s_syns = client.synonyms(query)
                    if s_syns:
                        symbiota_syns[key] = s_syns
                except Exception:
                    pass
            elif key not in backbones:
                try:
                    ind_syns = client.synonyms(query)
                    if ind_syns:
                        independent_syns[key] = ind_syns
                except Exception:
                    pass

    # --- 3. Return the Master JSON Payload ---
    master_payload = {
        "synonyms": {
            "official": official_syns,
            "symbiota": symbiota_syns,
            "independent": independent_syns,
        },
    }

    return json.dumps(master_payload, indent=2)
