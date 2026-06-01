"""
FastAPI backend — wraps the existing scripts/ pipeline and exposes HTTP endpoints.

Run with:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# Make scripts/ importable when running from project root
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.router import ANIMALIA_APIS, PLANTAE_APIS, FUNGI_APIS, TaxonRouter
from scripts.apis_pipe.gbif import GBIFAPI

app = FastAPI(title="Species Synonym API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # tighten in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Shared state ──────────────────────────────────────────────────────────────

_router = TaxonRouter(gbif_client=GBIFAPI())

_SAMPLE_DIR = _PROJECT_ROOT / "data" / "sample"

_ALL_APIS: list[str] = list(dict.fromkeys(ANIMALIA_APIS + PLANTAE_APIS + FUNGI_APIS))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _query_to_filename(query: str) -> str:
    normalized = normalize_query_string(query)
    filename = normalized.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", filename)


def _mock_search(query: str):
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
    import pandas as pd
    return pd.read_csv(csv_path)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/sources")
def get_sources():
    """Return the list of all known API source keys."""
    return {"sources": _ALL_APIS}


@app.get("/api/search")
def search(
    query: str = Query(..., min_length=1),
    use_routing: bool = Query(True),
    mock: bool = Query(True),  # flip to False once live pipeline is ready
):
    """
    Search for species synonyms.

    Returns rows as a list of dicts (same shape as the CSV columns),
    plus the resolved source list.
    """
    query = query.strip()

    # Resolve which sources to search
    try:
        if use_routing:
            selected_sources = _router.route(query)
        else:
            selected_sources = list(_ALL_APIS)
    except Exception as e:
        selected_sources = list(_ALL_APIS)  # fall back gracefully

    # Fetch data
    if mock:
        df = _mock_search(query)
    else:
        raise HTTPException(status_code=501, detail="Live search not yet implemented.")

    return {
        "query": query,
        "sources": selected_sources,
        "results": df.to_dict(orient="records"),
    }