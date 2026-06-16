"""
View A — Table View

Displays all species names found across sources in a cross-source presence
matrix (Name × Source).  Each ✓ in a source column is a clickable link that
opens the corresponding database page for that name in a new tab.

The queried name is always first and bolded; remaining rows are sorted by the
number of sources that carry them.

Reads:  st.session_state["search_results"]   (pd.DataFrame | None)
        st.session_state["last_search_query"] (str)
Writes: st.session_state["selected_record"]  (dict | None)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure the project root is on sys.path so `scripts` is importable
# when this module is imported before the main app inserts the path.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.utils.normalize_query_string import normalize_query_string  # noqa: E402


# ── Data helpers ──────────────────────────────────────────────────────────────

def _build_presence_table(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return the cross-source presence matrix as a display-ready DataFrame.

    Columns: Name | <source 1> | <source 2> | …
    Values:  Source Link URL when the name appears in that source (shown as ✓
             via LinkColumn), empty string otherwise.

    The row matching *query* is placed first for bold styling.
    All other rows are sorted by descending count of sources.
    """
    query_normalized = normalize_query_string(query)
    sources: list[str] = []                          # ordered, first-seen
    presence: dict[str, dict[str, str]] = {}         # name → {source → url}

    for _, row in df.iterrows():
        genus   = str(row.get("Genus",   "") or "").strip()
        species = str(row.get("Species", "") or "").strip()
        name    = f"{genus} {species}".strip()
        source  = str(row.get("Source Name", "")).strip()

        raw_url = row.get("Source Link")
        url     = str(raw_url).strip() if pd.notna(raw_url) and str(raw_url).strip() else ""

        if source not in sources:
            sources.append(source)

        # First URL for this (name, source) pair wins — accepted rows come
        # before synonyms in the DataFrame so the canonical link is preferred.
        if name not in presence:
            presence[name] = {}
        if not presence[name].get(source):
            presence[name][source] = url

    rows: list[dict] = []
    for name, src_map in presence.items():
        url_cols = {src: src_map.get(src, "") for src in sources}
        count    = sum(1 for v in url_cols.values() if v)
        rows.append({
            "Name":      name,
            **url_cols,
            "_count":    count,
            "_is_query": normalize_query_string(name) == query_normalized,
        })

    rows.sort(key=lambda r: (not r["_is_query"], -r["_count"]))
    for r in rows:
        del r["_count"]
        del r["_is_query"]

    return pd.DataFrame(rows)


# ── Public render entry-point ─────────────────────────────────────────────────

def render() -> None:
    df: pd.DataFrame | None = st.session_state.get("search_results")
    query: str = st.session_state.get("last_search_query", "").strip()

    st.subheader("Table View")

    if df is None or df.empty:
        st.info("Run a search to populate this view.")
        return

    if "Source Name" not in df.columns:
        st.error("Search results are missing the 'Source Name' column.")
        return

    presence_df = _build_presence_table(df, query)
    sources     = [col for col in presence_df.columns if col != "Name"]

    # Bold the query row (always row 0 after sorting)
    def _bold_query(row: pd.Series) -> list[str]:
        return ["font-weight: bold" if row.name == 0 else ""] * len(row)

    col_config: dict = {
        "Name": st.column_config.TextColumn(width="large"),
        **{
            src: st.column_config.LinkColumn(
                label=src,
                display_text="✓",
                width="small",
            )
            for src in sources
        },
    }

    st.dataframe(
        presence_df.style.apply(_bold_query, axis=1),
        hide_index=True,
        width="stretch",
        column_config=col_config,
    )

    # No inline selection — ✓ links go directly to the source page.
    st.session_state["selected_record"] = None
