"""
prototype.py — Streamlit app for fungal species synonym search

Provides a search interface that queries GBIF, GenBank, MushroomObserver,
MyCoPortal, IndexFungorum, and Catalogue of Life for species-level synonyms
of a given fungal species name, and displays the results from each API side by side.

To run:
    cd app/
    streamlit run prototype.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pandas as pd
import streamlit as st

from scripts.APIs.call_APIs import call_apis
from scripts.utils.fuzzy_search import fuzzy_search

st.title("Species Name Synonym Search")

# If a "Did you mean?" suggestion was clicked on the previous run, pre-fill the input with it
if "pending_query" in st.session_state:
    st.session_state["query_input"] = st.session_state.pop("pending_query")

query = st.text_input(
    "Enter a species name", placeholder="e.g. Amanita muscaria", key="query_input"
)

source_labels = {
    "gbif": "GBIF",
    "genbank": "GenBank",
    "mushroomobs": "Mushroom Observer",
    "mycoportal": "MyCoPortal",
    "bryophyteportal": "BryophytePortal",
    "macroalgae": "Macroalgae",
    "indexfungorum": "Index Fungorum",
    "col": "Catalogue of Life",
}

with st.expander("Advanced filters"):
    st.write("Sources to query")
    selected_labels = [
        label for label in source_labels.values() if st.checkbox(label, value=True)
    ]

selected_sources = [
    src for src, label in source_labels.items() if label in selected_labels
]

if query:
    if not selected_sources:
        st.warning("Select at least one source to query.")
    else:
        with st.spinner("Querying selected sources..."):
            raw = call_apis(query, sources=selected_sources)
        results = json.loads(raw)

        # Report any per-source errors
        for source, label in source_labels.items():
            val = results.get(source, {})
            if isinstance(val, str):
                st.error(f"{label}: {val}")

        # Collect names from each source as lowercase sets for case-insensitive comparison
        source_names = {
            source: {n.lower() for n in results[source].keys()}
            for source in selected_sources
            if isinstance(results.get(source), dict)
        }

        # Deduplicate all names case-insensitively; query name always gets its own row
        query_lower = query.lower()
        seen_lower: set[str] = {query_lower}
        unique_names: list[str] = [query]
        for src_set in source_names.values():
            for name_lower in src_set:
                if name_lower not in seen_lower:
                    seen_lower.add(name_lower)
                    unique_names.append(name_lower)

        if all(len(names) == 0 for names in source_names.values()):
            # No results, so try fuzzy search for suggestions
            suggestions = fuzzy_search(query)
            if suggestions:
                st.write("No results found. Did you mean:")
                for suggestion in suggestions:
                    if st.button(suggestion):
                        st.session_state.pending_query = suggestion
                        st.rerun()
            else:
                st.write("No results found across any source.")
        else:
            rows = []
            for name in unique_names:
                name_lower = name.lower()
                is_query = name_lower == query_lower
                display_name = name[0].upper() + name[1:]
                checks = {
                    label: (
                        "✓"
                        if (is_query and len(source_names.get(src, set())) > 0)
                        else "✓"
                        if name_lower in source_names.get(src, set())
                        else ""
                    )
                    for src, label in source_labels.items()
                    if label in selected_labels
                }
                count = sum(1 for v in checks.values() if v)
                rows.append(
                    {
                        "Name": display_name,
                        **checks,
                        "_count": count,
                        "_is_query": is_query,
                    }
                )

            rows.sort(key=lambda r: (not r.pop("_is_query"), -r.pop("_count")))
            df = pd.DataFrame(rows)

            def bold_query_row(row):
                style = "font-weight: bold" if row.name == 0 else ""
                return [style] * len(row)

            col_config = {"Name": st.column_config.TextColumn(width="large")}
            for label in selected_labels:
                col_config[label] = st.column_config.TextColumn(width="small")

            st.dataframe(
                df.style.apply(bold_query_row, axis=1),
                hide_index=True,
                use_container_width=True,
                column_config=col_config,
            )
