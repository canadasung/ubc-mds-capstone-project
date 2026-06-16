"""
Taxonomy router — exposes the /api/taxonomy endpoint.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.router import ANIMALIA_APIS, PLANTAE_APIS, FUNGI_APIS, TaxonRouter

router = APIRouter()

_taxon_router = TaxonRouter()
_SAMPLE_DIR = _PROJECT_ROOT / "data" / "sample"
_ALL_APIS: list[str] = list(dict.fromkeys(ANIMALIA_APIS + PLANTAE_APIS + FUNGI_APIS))

_RANKS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Subfamily", "Genus", "Species"]


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
    import re
    normalized = normalize_query_string(query)
    filename = normalized.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", filename)


def _mock_search(query: str) -> pd.DataFrame:
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


def _pick_reference_row(group: pd.DataFrame) -> pd.Series:
    """Return the single row that best represents the canonical name for a source.

    Prefers the row with ``status`` equal to ``"Accepted"``; falls back to the
    first row when no accepted row exists.

    Parameters
    ----------
    group : pandas.DataFrame
        All rows returned by a single source.

    Returns
    -------
    pandas.Series
        The selected reference row.
    """
    if "status" in group.columns:
        accepted = group[group["status"] == "Accepted"]
        if not accepted.empty:
            return accepted.iloc[0]
    return group.iloc[0]


def _build_taxonomy(df: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Build the per-source taxonomy comparison from a search results DataFrame.

    For each source, one reference row is selected and its taxonomic ranks are
    extracted. Ranks that are absent or entirely empty across all sources are
    excluded from the output.

    Parameters
    ----------
    df : pandas.DataFrame
        Search results as returned by ``_mock_search``, with at least a
        ``api_name`` column and rank columns matching ``_RANKS``.

    Returns
    -------
    rows : list of dict
        One entry per source. Each dict contains ``"source"`` and one key per
        present rank, plus a ``"synonym_count"`` integer.
    present_ranks : list of str
        The subset of ``_RANKS`` that contained at least one non-empty value.
    """
    # Normalise column names to title-case for rank lookup
    col_map = {c.lower(): c for c in df.columns}
    rank_cols = [r for r in _RANKS if r.lower() in col_map]

    rows = []
    for source, group in df.groupby("api_name", sort=False):
        ref = _pick_reference_row(group)
        synonym_count = int((group.get("status", pd.Series()) == "Synonym").sum())

        entry: dict = {"source": str(source), "synonym_count": synonym_count}
        for rank in rank_cols:
            val = ref.get(col_map[rank.lower()])
            entry[rank] = str(val).strip() if pd.notna(val) and str(val).strip() else None

        rows.append(entry)

    # Keep only ranks with at least one non-None value
    present_ranks = [r for r in rank_cols if any(row.get(r) is not None for row in rows)]

    return rows, present_ranks


def _find_disagreements(rows: list[dict], ranks: list[str]) -> list[str]:
    """Identify ranks where sources return different values.

    Parameters
    ----------
    rows : list of dict
        Output of ``_build_taxonomy``.
    ranks : list of str
        Ranks to check, as returned by ``_build_taxonomy``.

    Returns
    -------
    list of str
        Names of ranks where at least two sources disagree.
    """
    disagreements = []
    for rank in ranks:
        values = {row[rank] for row in rows if row.get(rank) is not None}
        if len(values) > 1:
            disagreements.append(rank)
    return disagreements


@router.get("/api/taxonomy")
def taxonomy(
    query: str = Query(..., min_length=1),
    mock: bool = Query(True),
):
    """Return a per-source taxonomy comparison for a given species name.

    Parameters
    ----------
    query : str
        Species name to look up. Must be at least one character.
    mock : bool, optional
        If ``True``, results are read from pre-computed sample CSV files.
        If ``False``, the live API pipeline is called. Defaults to ``True``.

    Returns
    -------
    dict
        A dictionary with four keys:

        - ``"query"`` : the normalised search string.
        - ``"ranks"`` : list of rank names present in the data.
        - ``"sources"`` : list of per-source taxonomy dicts, each containing
          ``"source"``, ``"synonym_count"``, and one key per rank.
        - ``"disagreements"`` : list of rank names where sources disagree.

    Raises
    ------
    HTTPException
        404 if mock data is requested but no sample file exists for the query.
        501 if ``mock=False``, as live search is not yet implemented.
    """
    query = query.strip()

    if mock:
        df = _mock_search(query)
    else:
        raise HTTPException(status_code=501, detail="Live search is not yet implemented.")

    rows, present_ranks = _build_taxonomy(df)
    disagreements = _find_disagreements(rows, present_ranks)

    return {
        "query": query,
        "ranks": present_ranks,
        "sources": rows,
        "disagreements": disagreements,
    }