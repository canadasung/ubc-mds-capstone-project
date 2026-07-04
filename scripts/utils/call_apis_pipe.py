"""
Top-level entry point for the species data pipeline.

Receives a search query and a list of portal display names from the frontend,
calls ``get_synonyms`` on each requested portal, and returns the concatenated
results as a single DataFrame.

Typical usage:
    from scripts.utils.call_apis_pipe import call_apis
    df = call_apis("Amanita muscaria", ["GBIF", "MyCoPortal"])
"""

from typing import Callable, List

import pandas as pd

from scripts.apis_pipe.base import SpeciesAPI
from scripts.apis_pipe.col import COLAPI
from scripts.apis_pipe.fishbase import FishBaseAPI
from scripts.apis_pipe.gbif import GBIFAPI
from scripts.apis_pipe.genbank import GenBankAPI
from scripts.apis_pipe.index_fungorum import IndexFungorumAPI
from scripts.apis_pipe.itis import ITISAPI
from scripts.apis_pipe.mushroomobs import MushroomObserverAPI
from scripts.apis_pipe.mycobank import MycoBankAPI
from scripts.apis_pipe.pbdb import PaleobiologyDatabaseAPI
from scripts.apis_pipe.symbiota import SymbiotaAPI
from scripts.apis_pipe.tropicos import TropicosAPI
from scripts.config import (
    COL_PORTAL,
    FISHBASE_PORTAL,
    GBIF_PORTAL,
    GENBANK_PORTAL,
    INDEX_FUNGORUM_PORTAL,
    ITIS_PORTAL,
    MUSHROOM_OBSERVER_PORTAL,
    MYCOBANK_PORTAL,
    PBDB_PORTAL,
    SYMBIOTA_PORTALS,
    TROPICOS_PORTAL,
)
from scripts.utils.schema import empty_synonym_table

# Maps each portal's display_name to a zero-arg factory that returns a SpeciesAPI instance.
# Symbiota portals use a lambda so SymbiotaAPI resolves the name to its base URL via config.
_PORTAL_REGISTRY: dict[str, Callable[[], SpeciesAPI]] = {
    GBIF_PORTAL.display_name: GBIFAPI,
    COL_PORTAL.display_name: COLAPI,
    TROPICOS_PORTAL.display_name: TropicosAPI,
    INDEX_FUNGORUM_PORTAL.display_name: IndexFungorumAPI,
    GENBANK_PORTAL.display_name: GenBankAPI,
    MUSHROOM_OBSERVER_PORTAL.display_name: MushroomObserverAPI,
    FISHBASE_PORTAL.display_name: FishBaseAPI,
    ITIS_PORTAL.display_name: ITISAPI,
    PBDB_PORTAL.display_name: PaleobiologyDatabaseAPI,
    MYCOBANK_PORTAL.display_name: MycoBankAPI,
    **{
        p.display_name: (lambda name=p.display_name: SymbiotaAPI(name))
        for p in SYMBIOTA_PORTALS
    },
}


def call_apis(query: str, sources: List[str]) -> pd.DataFrame:
    """
    Retrieve synonyms for a species name from the requested portals.

    For each portal name in ``sources``, instantiates the corresponding API
    client, calls ``get_synonyms(query)``, and concatenates all non-empty
    results into a single DataFrame.

    Args:
        query: The scientific name to search (e.g. ``"Amanita muscaria"``).
        sources: Portal display names to query, as defined in ``scripts.config``
            (e.g. ``["GBIF", "MyCoPortal", "Lichen Portal"]``).

    Returns:
        A DataFrame of synonym records in the standard schema format, or an
        empty schema-format DataFrame if no portal returned results.
    """
    dfs = []
    for source in sources:
        print(source)
        factory = _PORTAL_REGISTRY.get(source)
        if factory is None:
            continue
        df = factory().get_synonyms(query)
        if not df.empty:
            dfs.append(df)

    if not dfs:
        return empty_synonym_table()
    return pd.concat(dfs, ignore_index=True)
