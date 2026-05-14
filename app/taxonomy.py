"""
taxonomy_comparison.py — Streamlit app for fungal taxonomy comparison

Provides a search interface that queries taxonomy APIs for a given fungal
species name and displays the full taxonomy (kingdom → species) from each
source side by side, with disagreements highlighted.

To run:
    cd app/
    streamlit run taxonomy_comparison.py
"""

import pandas as pd
import streamlit as st

from scripts.APIs.gbif_taxonomy import get_gbif_taxonomy

st.title("Taxonomy Comparison")

RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]

# Maps source key → (display label, fetcher function)
SOURCES = {
    "gbif": ("GBIF", get_gbif_taxonomy),
    # Future sources added here, e.g.:
    # "col": ("Catalogue of Life", get_col_taxonomy),
    # "indexfungorum": ("Index Fungorum", get_indexfungorum_taxonomy),
}

query = st.text_input("Enter a species name", placeholder="e.g. Amanita muscaria")

with st.expander("Advanced filters"):
    st.write("Sources to query")
    selected_sources = [
        key for key, (label, _) in SOURCES.items()
        if st.checkbox(label, value=True)
    ]

if query:
    if not selected_sources:
        st.warning("Select at least one source to query.")
    else:
        with st.spinner("Querying selected sources..."):
            results = {}
            for key in selected_sources:
                label, fn = SOURCES[key]
                try:
                    results[key] = fn(query)
                except Exception as e:
                    results[key] = None
                    st.error(f"{label}: {e}")

        # Check if every source returned nothing
        if all(not r for r in results.values()):
            st.warning(f"No taxonomy found for '{query}'.")
        else:
            # Build rows: one per source, columns = ranks
            rank_labels = [r.capitalize() for r in RANKS]
            rows = []
            for key in selected_sources:
                label, _ = SOURCES[key]
                data = results.get(key) or {}
                row = {"Source": label}
                row.update({r.capitalize(): data.get(r, "—") or "—" for r in RANKS})
                rows.append(row)

            df = pd.DataFrame(rows).set_index("Source")

            # Highlight cells where sources disagree (only visible with 2+ sources)
            def highlight_disagreements(df):
                styles = pd.DataFrame("", index=df.index, columns=df.columns)
                for col in df.columns:
                    vals = df[col].replace("—", None).dropna().unique()
                    if len(vals) > 1:
                        styles[col] = "background-color: #fff3cd"  # amber
                return styles

            st.dataframe(
                df.style.apply(highlight_disagreements, axis=None),
                use_container_width=True,
            )