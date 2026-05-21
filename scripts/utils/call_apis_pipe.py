"""
Top-level entry point for the species data pipeline.

This module wires together all API clients, the TaxonRouter, the SynonymEngine,
and the SpeciesAggregator into a single callable function (`call_apis`). Callers
only need to provide a scientific name; the pipeline handles routing, synonym
discovery, and occurrence retrieval automatically.

Typical usage:
    from scripts.utils.call_apis_pipe import call_apis
    payload = call_apis("Amanita muscaria")

The returned JSON string has two top-level keys:
  - "synonyms": official, symbiota, and independent synonym records
  - "occurrences": per-source occurrence records and request statuses
"""

import json
from typing import List, Optional

from scripts.APIs_pipe.col import COLAPI

# import API client implementations
from scripts.APIs_pipe.gbif import GBIFAPI
from scripts.APIs_pipe.genbank import GenBankAPI
from scripts.APIs_pipe.index_fungorum import IndexFungorumAPI
from scripts.APIs_pipe.mushroomobs import MushroomObserverAPI
from scripts.APIs_pipe.symbiota import SymbiotaAPI
from scripts.APIs_pipe.tropicos import TropicosAPI
from scripts.utils.aggregator import SpeciesAggregator
from scripts.utils.router import TaxonRouter
from scripts.utils.synonyms import SynonymEngine

# Flexible alias for source strings
Source = str


def _make_clients() -> dict:
    """
    Initialize and return a dictionary of all active API clients.

    Each key is the canonical string identifier used throughout the pipeline
    (by TaxonRouter, SynonymEngine, and SpeciesAggregator). Symbiota portals
    are keyed by the pattern "symbiota_<portal>" so they can be identified as
    a group downstream.

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
        "symbiota_swbiodiversity": SymbiotaAPI("https://swbiodiversity.org/portal"),
        "symbiota_macroalgae": SymbiotaAPI("https://macroalgae.org/portal"),
        "symbiota_pterido": SymbiotaAPI("https://pteridoportal.org/portal"),
        "symbiota_neherbaria": SymbiotaAPI("https://neherbaria.org/portal"),
        "symbiota_midatlantic": SymbiotaAPI("https://midatlanticherbaria.org/portal"),
        "symbiota_portals": SymbiotaAPI("https://symbiota.org/symbiota-portals"),
    }
    return clients


def call_apis(
    query: str, sources: Optional[List[Source]] = None, limit: int = 20
) -> str:
    """
    Orchestrate synonym and occurrence retrieval for a scientific name.

    Runs the full pipeline in five steps:
      1. Fetch official synonyms from backbone APIs (GBIF, COL, Tropicos, Index Fungorum).
      2. Fetch synonyms from Symbiota portals and independent sources (e.g. Mushroom Observer).
      3. Consolidate all discovered names into a deduplicated list for occurrence searching.
      4. Query each selected API for occurrences under the primary name and all synonyms.
      5. Return a single JSON payload combining synonyms and occurrences.

    Args:
        query (str): The accepted scientific name to search (e.g. "Amanita muscaria").
        sources (Optional[List[str]]): Explicit list of API keys (matching keys in
            `_make_clients()`) to query. If None, TaxonRouter selects sources based
            on the taxon's kingdom.
        limit (int): Maximum occurrence records to retrieve per API per name query.
            Defaults to 20.

    Returns:
        str: JSON string with two top-level keys:
            - "synonyms": dict with "official", "symbiota", and "independent" sub-keys,
              each containing synonym records from those source groups.
            - "occurrences": dict keyed by API name, each value containing a "status"
              field ("success" / "warning" / "error") and either a "data" list or a
              "message" string.
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

    agg = SpeciesAggregator(clients=clients, router=router)

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

    # --- 3. Consolidate String Names for the Aggregator ---
    # We must extract ALL the names we just found so the occurrence search is complete!
    synonyms_list = []
    seen = {query.lower()}

    for s in official_syns:
        nm = s.get("name")
        if nm and nm.lower() not in seen:
            seen.add(nm.lower())
            synonyms_list.append(nm)

    # Add the local/independent string names as well
    for syn_dict in [symbiota_syns, independent_syns]:
        for api_key, syn_records in syn_dict.items():
            for rec in syn_records:
                nm = rec.get("canonicalName")
                if nm and nm.lower() not in seen:
                    seen.add(nm.lower())
                    synonyms_list.append(nm)

    # --- 4. Fetch Occurrences ---
    try:
        occurrences = agg.occurrences(
            query, synonyms=synonyms_list, apis=selected, limit=limit
        )
    except Exception as e:
        occurrences = {"status": "error", "message": f"Occurrence lookup failed: {e}"}

    # --- 5. Return the Master JSON Payload ---
    master_payload = {
        "synonyms": {
            "official": official_syns,
            "symbiota": symbiota_syns,
            "independent": independent_syns,
        },
        "occurrences": occurrences,
    }

    return json.dumps(master_payload, indent=2)
