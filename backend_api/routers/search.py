"""
Search router — exposes the /api/search and /api/sources endpoints.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
import pandas as pd

from fastapi import APIRouter, HTTPException, Query

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.router import ANIMALIA_APIS, PLANTAE_APIS, FUNGI_APIS, TaxonRouter
from scripts.apis_pipe.gbif import GBIFAPI

router = APIRouter()

_taxon_router = TaxonRouter(gbif_client=GBIFAPI())
_SAMPLE_DIR = _PROJECT_ROOT / "data" / "sample"
_ALL_APIS: list[str] = list(dict.fromkeys(ANIMALIA_APIS + PLANTAE_APIS + FUNGI_APIS))


def _query_to_filename(query: str) -> str:
    """Convert a search query to the snake_case filename stem used in sample files.

    Parameters
    ----------
    query : str
        Raw search query, for example ``"Amanita muscaria"``.

    Returns
    -------
    str
        Lowercase, underscore-separated filename stem with non-alphanumeric
        characters removed, for example ``"amanita_muscaria"``.
    """
    normalized = normalize_query_string(query)
    filename = normalized.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", filename)


def _mock_search(query: str):
    """Load pre-computed sample data for a given query from a CSV file.

    Parameters
    ----------
    query : str
        Species name to look up. Must match the stem of a file in
        ``data/sample/`` of the form ``sample_table_data_{name}.csv``.

    Returns
    -------
    pandas.DataFrame
        Contents of the matching CSV file.

    Raises
    ------
    HTTPException
        404 if no sample file exists for the query. The response body
        includes a list of available sample names.
    """

    csv_path = _SAMPLE_DIR / f"sample_table_data_{_query_to_filename(query)}.csv"
    if not csv_path.exists():
        available = [
            normalize_query_string(f.stem.removeprefix("sample_table_data_").replace("_", " "))
            for f in sorted(_SAMPLE_DIR.glob("sample_table_data_*.csv"))
        ]
        raise HTTPException(
            status_code=404,
            detail={"message": f"No sample data found for '{query}'.", "available": available},
        )
    return pd.read_csv(csv_path)


@router.get("/api/sources")
def get_sources():
    """Return the list of all known data source keys.

    Returns
    -------
    dict
        A dictionary with a single key ``"sources"`` containing an ordered
        list of API identifier strings.
    """
    return {"sources": _ALL_APIS}


@router.get("/api/search")
def search(
    query: str = Query(..., min_length=1),
    use_routing: bool = Query(True),
    mock: bool = Query(True),
):
    """Search for taxonomic synonyms for a given species name.

    Parameters
    ----------
    query : str
        Species name to search for. Must be at least one character.
    use_routing : bool, optional
        If ``True``, the set of sources queried is determined automatically
        based on the kingdom of the species. If ``False``, all known sources
        are queried. Defaults to ``True``.
    mock : bool, optional
        If ``True``, results are read from pre-computed sample CSV files.
        If ``False``, the live API pipeline is called. Defaults to ``True``.

    Returns
    -------
    dict
        A dictionary with three keys:

        - ``"query"`` : the normalised search string.
        - ``"sources"`` : list of source keys that were queried.
        - ``"results"`` : list of result records, each a flat dictionary
          corresponding to one row of the underlying data.

    Raises
    ------
    HTTPException
        404 if mock data is requested but no sample file exists for the query.
        501 if ``mock=False``, as live search is not yet implemented.
    """
    query = query.strip()

    try:
        selected_sources = _taxon_router.route(query) if use_routing else list(_ALL_APIS)
    except Exception:
        selected_sources = list(_ALL_APIS)

    if mock:
        df = _mock_search(query)
    else:
        raise HTTPException(status_code=501, detail="Live search is not yet implemented.")

    return {
        "query": query,
        "sources": selected_sources,
        "results": df.astype(object).where(pd.notna(df), other=None).to_dict(orient="records"),
    } 