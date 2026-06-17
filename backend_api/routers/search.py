"""
Search router — exposes /api/search, /api/search/stream, /api/suggest, and /api/sources.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import HTTPException

from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.router import ANIMALIA_APIS, PLANTAE_APIS, FUNGI_APIS, TaxonRouter
from scripts.utils.fuzzy_search import fuzzy_search as _fuzzy_search
from scripts.utils.call_apis_pipe import _PORTAL_REGISTRY

router = APIRouter()

_taxon_router = TaxonRouter()
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


@router.get("/api/suggest")
def suggest(query: str = Query(..., min_length=1)):
    """Return the recommended source list for a given species name.

    Calls the taxon router to determine the kingdom and returns the
    corresponding list of portal display names.

    Parameters
    ----------
    query : str
        Species name to route.

    Returns
    -------
    dict
        A dictionary with a single key ``"sources"`` containing a list of
        portal display names, e.g. ``["GBIF", "COL", "Index Fungorum"]``.
        Empty list if the kingdom cannot be determined.
    """
    display_names = _taxon_router.route(query.strip())
    return {"sources": display_names}


@router.get("/api/search/stream")
async def search_stream(
    request: Request,
    query: str = Query(..., min_length=1),
    sources: str = Query(""),
):
    """Stream synonym search results as Server-Sent Events.

    Emits one ``progress`` event before and after each source is queried,
    then either a ``result`` event (with the full SearchResponse payload) or
    a ``suggestions`` event (with fuzzy-match candidates) when the query
    returns no results.

    Parameters
    ----------
    query : str
        Species name to search.
    sources : str
        Comma-separated list of backend portal display names to query,
        e.g. ``"GBIF,COL,MyCoPortal"``. Unknown names are silently skipped.
    """
    display_names = [s.strip() for s in sources.split(",") if s.strip()]
    q = query.strip()

    async def generate():
        total = len(display_names)
        dfs = []

        for i, name in enumerate(display_names):
            # Stop before starting the next source if the client disconnected.
            if await request.is_disconnected():
                return

            yield f"data: {json.dumps({'type': 'progress', 'source': name, 'done': i, 'total': total})}\n\n"

            factory = _PORTAL_REGISTRY.get(name)
            if factory:
                try:
                    df = await asyncio.to_thread(lambda f=factory, qq=q: f().get_synonyms(qq))
                    if not df.empty:
                        dfs.append(df)
                except Exception:
                    pass  # skip failed source, continue with remaining

            yield f"data: {json.dumps({'type': 'progress', 'source': name, 'done': i + 1, 'total': total})}\n\n"

        if not dfs:
            try:
                suggestions = await asyncio.to_thread(_fuzzy_search, q)
            except Exception:
                suggestions = []
            yield f"data: {json.dumps({'type': 'suggestions', 'names': suggestions})}\n\n"
        else:
            combined = pd.concat(dfs, ignore_index=True)
            result = {
                "query": q,
                "sources": display_names,
                "results": combined.astype(object).where(pd.notna(combined), other=None).to_dict(orient="records"),
            }
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
        501 if ``mock=False``, as live search is not yet implemented on this endpoint
        (use ``/api/search/stream`` instead).
    """
    query = query.strip()

    try:
        selected_sources = _taxon_router.route(query) if use_routing else list(_ALL_APIS)
    except Exception:
        selected_sources = list(_ALL_APIS)

    if mock:
        df = _mock_search(query)
    else:
        raise HTTPException(status_code=501, detail="Use /api/search/stream for live search.")

    return {
        "query": query,
        "sources": selected_sources,
        "results": df.astype(object).where(pd.notna(df), other=None).to_dict(orient="records"),
    }
