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
    Orchestrate the synonym and occurrence retrieval for requested sources.

    Initializes the required pipeline engines and routes the query. It sweeps
    official backbones, regional Symbiota portals, and independent databases
    for historical synonyms, aggregates them all into string names, and uses
    them to fetch robust occurrence records.

    Args:
        query (str): The scientific name to search.
        sources (Optional[List[str]]): An explicit list of API keys to query.
            If None, the TaxonRouter will dynamically determine the best sources.
        limit (int): The maximum number of occurrence records to retrieve per API.

    Returns:
        str: A master JSON-formatted string containing two primary keys:
             'synonyms' (metadata for the UI) and 'occurrences' (physical records).
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
