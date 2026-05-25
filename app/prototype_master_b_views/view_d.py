"""
View D — Taxonomic View

Displays the accepted taxonomy per source side by side, with disagreements
highlighted in red.

For each source the reference row is chosen as follows:
  - If the source has a row with GBIF Accepted Status == "Accepted", use that.
  - Otherwise use the first row returned by that source.
This means GBIF's accepted name drives its column, while other sources
(e.g. Mushroom Observer, MyCoPortal) show the name they returned as canonical.

Reads:  st.session_state["search_results"]   (pd.DataFrame | None)
        st.session_state["last_search_query"] (str)
Writes: (none — display only)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


# Taxonomic ranks in display order.
# Any rank that is absent from the DataFrame or entirely empty is suppressed.
_RANKS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Subfamily", "Genus", "Species"]


# ── Data helpers ──────────────────────────────────────────────────────────────

def _pick_reference_row(group: pd.DataFrame) -> pd.Series:
    """Return the single row that best represents the canonical name for a source.

    Prefers the row marked "Accepted" in GBIF Accepted Status; falls back to
    the first row when that column is absent or has no Accepted entry.
    """
    if "GBIF Accepted Status" in group.columns:
        accepted = group[group["GBIF Accepted Status"] == "Accepted"]
        if not accepted.empty:
            return accepted.iloc[0]
    return group.iloc[0]


def _build_taxonomy_df(df: pd.DataFrame) -> pd.DataFrame:
    """Build the source × rank comparison table.

    Returns a DataFrame indexed by source name, with one column per rank.
    Ranks absent from the data or entirely blank are excluded.
    """
    rows: list[dict] = []
    for source, group in df.groupby("Source Name", sort=False):
        ref = _pick_reference_row(group)
        row: dict = {"Source": str(source)}
        for rank in _RANKS:
            if rank not in df.columns:
                row[rank] = "—"
            else:
                val = ref.get(rank)
                row[rank] = str(val).strip() if pd.notna(val) and str(val).strip() else "—"
        rows.append(row)

    result = pd.DataFrame(rows).set_index("Source")

    # Drop ranks that are entirely "—" (column absent in data or all empty)
    result = result.loc[:, (result != "—").any(axis=0)]
    return result


def _synonym_counts(df: pd.DataFrame) -> dict[str, int]:
    """Return the number of synonym rows per source."""
    counts: dict[str, int] = {}
    for source, group in df.groupby("Source Name", sort=False):
        if "GBIF Accepted Status" in group.columns:
            counts[str(source)] = int((group["GBIF Accepted Status"] == "Synonym").sum())
        else:
            # No status column — treat every row beyond the first as a synonym
            counts[str(source)] = max(0, len(group) - 1)
    return counts


def _highlight_disagreements(df: pd.DataFrame) -> pd.DataFrame:
    """Return a same-shaped DataFrame of CSS strings, red where sources disagree."""
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for col in df.columns:
        unique_vals = df[col].replace("—", pd.NA).dropna().unique()
        if len(unique_vals) > 1:
            styles[col] = "background-color: #ff4b4b; color: white;"
    return styles


# ── Public render entry-point ─────────────────────────────────────────────────

def render() -> None:
    df: pd.DataFrame | None = st.session_state.get("search_results")
    query: str = st.session_state.get("last_search_query", "").strip()

    st.subheader("Taxonomic View")

    if df is None or df.empty:
        st.info("Run a search to populate this view.")
        return

    if "Source Name" not in df.columns:
        st.error("Search results are missing the 'Source Name' column.")
        return

    taxonomy_df  = _build_taxonomy_df(df)
    syn_counts   = _synonym_counts(df)
    n_sources    = len(taxonomy_df)

    # ── Caption ──────────────────────────────────────────────────────────────
    if query:
        st.caption(
            f"Accepted classification for **{query}** per source · "
            f"{n_sources} source{'s' if n_sources != 1 else ''} queried"
        )

    # ── Taxonomy table ────────────────────────────────────────────────────────
    st.dataframe(
        taxonomy_df.style.apply(_highlight_disagreements, axis=None),
        use_container_width=True,
    )

    # ── Disagreement / agreement summary ─────────────────────────────────────
    if n_sources > 1:
        disagreement_cols = [
            col for col in taxonomy_df.columns
            if taxonomy_df[col].replace("—", pd.NA).dropna().nunique() > 1
        ]
        if disagreement_cols:
            st.warning(
                f"Sources disagree on: **{', '.join(disagreement_cols)}** "
                f"({len(disagreement_cols)} rank{'s' if len(disagreement_cols) != 1 else ''})"
            )
        else:
            st.success("All sources agree on the taxonomy.")

    # ── Per-source synonym counts ─────────────────────────────────────────────
    if any(v > 0 for v in syn_counts.values()):
        with st.expander("Synonym counts per source", expanded=False):
            cols = st.columns(min(n_sources, 4))
            for i, (source, count) in enumerate(syn_counts.items()):
                with cols[i % len(cols)]:
                    st.metric(label=source, value=count, help=f"Synonym rows returned by {source}")
