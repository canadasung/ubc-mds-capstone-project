"""
prototype_pipe.py — Streamlit app for species synonym search

The prototype takes a user query and submits it to all relevant databases
for a synonym search. The included databases include those powered by GBIF,
Symbiota, and indepedents. The results are collected and transformed into
our own table, which is then used by the different views we will support.
"""

import json
import re

import pandas as pd
import streamlit as st

from scripts.utils.call_APIs_pipe import call_apis
from scripts.utils.fuzzy_search import fuzzy_search

st.set_page_config(page_title="Species Name Synonym Search", layout="wide")
st.title("Species Name Synonym Search")

# If a "Did you mean?" suggestion was clicked on the previous run, pre-fill it
if "pending_query" in st.session_state:
    st.session_state["query_input"] = st.session_state.pop("pending_query")

query = st.text_input(
    "Enter a species name", placeholder="e.g. Amanita muscaria", key="query_input"
)

# Full list of sources
source_labels = {
    # GBIF
    "gbif": "GBIF",
    # Symbiota portals
    "symbiota_mycoportal": "MyCoPortal",
    "symbiota_lichen": "Lichen Portal",
    "symbiota_bryophyte": "Bryophyte Portal",
    "symbiota_sernec": "SERNEC",
    "symbiota_cch2": "CCH2",
    "symbiota_nansh": "NANSH",
    "symbiota_swbiodiversity": "SW Biodiversity",
    "symbiota_macroalgae": "Macroalgae.org",
    "symbiota_pterido": "PteridoPortal",
    "symbiota_neherbaria": "NE Herbaria Portal",
    "symbiota_midatlantic": "Mid-Atlantic Herbaria",
    # Independent APIs
    "col": "Catalogue of Life",
    "tropicos": "Tropicos",
    "index_fungorum": "Index Fungorum",
    "genbank": "GenBank",
    "mushroomobs": "Mushroom Observer",
}

# This is the advanced tab where the user can select which sources to query
with st.expander("Advanced filters (Source Databases)", expanded=False):
    selected_labels = []

    # Create three neat columns for our toggles
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 🌍 Global Backbone")
        if st.checkbox(source_labels["gbif"], value=True):
            selected_labels.append(source_labels["gbif"])

    with col2:
        st.markdown("### 🌿 Symbiota Portals")
        for key, label in source_labels.items():
            if key.startswith("symbiota_"):
                if st.checkbox(label, value=True):
                    selected_labels.append(label)

    with col3:
        st.markdown("### 🔬 Independent APIs")
        independent_keys = [
            "col",
            "tropicos",
            "index_fungorum",
            "genbank",
            "mushroomobs",
        ]
        for key in independent_keys:
            if st.checkbox(source_labels[key], value=True):
                selected_labels.append(source_labels[key])

selected_sources = [
    src for src, label in source_labels.items() if label in selected_labels
]

# For normalising query string. We should switch this to use utils/normalize_query_string.py
def display_name_for(name: str) -> str:
    """Helper: normalize display of a name (capitalize first char)"""
    if not name:
        return name
    return name[0].upper() + name[1:]

# Cleans and tidies up the results of occurrence results
def clean_occurrence_name(name: str) -> str:
    """Extracts a clean 'Genus species' binomial from messy occurrence strings."""
    if not name:
        return ""

    # 1. Strip out subspecies, varieties, and forms (and everything after them)
    name = re.sub(r"\b(var\.|subsp\.|ssp\.|f\.|fo\.).*", "", name, flags=re.IGNORECASE)

    # 2. Grab only the first two words
    words = name.split()
    if len(words) >= 2:
        return f"{words[0]} {words[1]}"
    return name.strip()

# A pipeline of things to do once the user clicks "Search"
if query:
    if not selected_sources:
        st.warning("Select at least one source to query.")
    else:
        with st.spinner(
            "Executing centralized pipeline (fetching synonyms & occurrences)..."
        ):
            # --- 1. CALL THE MASTER BACKEND ---
            raw_json = call_apis(query=query, sources=selected_sources, limit=20)
            master_data = json.loads(raw_json)

            syn_data = master_data.get("synonyms", {})
            occ_data = master_data.get("occurrences", {})

            # --- 2. SETUP TRACKING LISTS ---
            query_clean = clean_occurrence_name(query) or query
            unique_names = [query_clean]
            seen_lower = {query_clean.lower()}
            display_names_map = {query_clean.lower(): query_clean}

            source_names_found = {src: set() for src in selected_sources}

            def register_name(raw_nm, src_key=None):
                """Helper to clean, track, and map names to their sources."""
                clean_nm = clean_occurrence_name(raw_nm)
                if not clean_nm:
                    return None
                nm_lower = clean_nm.lower()

                if nm_lower not in seen_lower:
                    seen_lower.add(nm_lower)
                    unique_names.append(clean_nm)
                    display_names_map[nm_lower] = clean_nm

                if src_key and src_key in source_names_found:
                    source_names_found[src_key].add(nm_lower)
                return nm_lower

            # --- 3. PROCESS THE JSON PAYLOAD ---

            official_accepted_name = None  # <--- NEW: Track the true accepted name

            # A. Process Official Synonyms
            for s in syn_data.get("official", []):
                if isinstance(s, dict) and "error" not in s:
                    nm_lower = register_name(s.get("name"))

                    # The first valid name from the official backbone is our Accepted Name!
                    if nm_lower and not official_accepted_name:
                        official_accepted_name = nm_lower

                    # Try to match the official source text back to our toggles (e.g. GBIF)
                    src_str = s.get("source", "").lower()
                    for active_src in selected_sources:
                        if (
                            active_src.lower() in src_str
                            or source_labels.get(active_src, "").lower() in src_str
                        ):
                            if nm_lower:
                                source_names_found[active_src].add(nm_lower)

            # Fallback just in case the official backbone failed
            if not official_accepted_name:
                official_accepted_name = query_clean.lower()

            # B. Process Symbiota Synonyms
            for src, records in syn_data.get("symbiota", {}).items():
                if src in selected_sources:
                    for rec in records:
                        if isinstance(rec, dict) and "error" not in rec:
                            register_name(rec.get("canonicalName"), src)

            # C. Process Independent Synonyms
            for src, records in syn_data.get("independent", {}).items():
                if src in selected_sources:
                    for rec in records:
                        if isinstance(rec, dict) and "error" not in rec:
                            register_name(rec.get("canonicalName"), src)

            # D. Process Occurrences & Warnings
            for src in selected_sources:
                raw_occ = occ_data.get(src, {})

                # Check for UI warnings generated by the Aggregator
                if isinstance(raw_occ, dict):
                    if raw_occ.get("status") == "warning":
                        st.warning(
                            f"{source_labels.get(src)}: {raw_occ.get('message')}"
                        )
                    elif raw_occ.get("status") == "error":
                        st.error(f"{source_labels.get(src)}: {raw_occ.get('message')}")
                    records = raw_occ.get("data", [])
                else:
                    records = raw_occ if isinstance(raw_occ, list) else []

                # Extract names from occurrences
                if records and len(records) > 0:
                    source_names_found[src].add(
                        query_clean.lower()
                    )  # Give credit for query

                    for rec in records:
                        raw_name = (
                            rec.get("scientificName")
                            or rec.get("name")
                            or rec.get("canonicalName")
                        )
                        if raw_name:
                            register_name(raw_name, src)

        # --- 4. BUILD THE SPLIT UI TABLES OR FALLBACK ---

        # If we found literally nothing
        if len(unique_names) == 1 and all(
            len(s) == 0 for s in source_names_found.values()
        ):
            suggestions = fuzzy_search(query)

            if not suggestions:
                st.write("No results found, and no spelling suggestions available.")
            elif isinstance(suggestions, str):
                st.write(
                    f"Recognized as **{suggestions}**, but no records were found in the selected databases."
                )
            else:
                st.write("No exact match found. Did you mean:")
                for suggestion in suggestions:
                    if st.button(suggestion):
                        st.session_state.pending_query = suggestion
                        st.rerun()
        else:
            # --- NEW: Separate the rows into Accepted vs Synonyms ---
            accepted_rows = []
            synonym_rows = []

            for name in unique_names:
                name_lower = name.lower()
                display_name = display_name_for(display_names_map.get(name_lower, name))

                checks = {
                    label: (
                        "✓" if name_lower in source_names_found.get(src, set()) else ""
                    )
                    for src, label in source_labels.items()
                    if label in selected_labels
                }

                count = sum(1 for v in checks.values() if v)

                row_data = {"Name": display_name, **checks, "_count": count}

                if name_lower == official_accepted_name:
                    accepted_rows.append(row_data)
                else:
                    synonym_rows.append(row_data)

            # Sort the synonym rows by how many databases use them
            synonym_rows.sort(key=lambda r: -r.pop("_count"))
            for r in accepted_rows:
                r.pop("_count", None)  # clean up the hidden column

            # Define column configurations
            col_config = {"Name": st.column_config.TextColumn(width="large")}
            for label in selected_labels:
                col_config[label] = st.column_config.TextColumn(width="small")

            # Render Accepted Name Table
            st.markdown("### Accepted Species Name")
            if accepted_rows:
                df_acc = pd.DataFrame(accepted_rows)
                # Highlight the accepted name row
                st.dataframe(
                    df_acc,
                    hide_index=True,
                    width="stretch",
                    column_config=col_config,
                )

            # Render Synonyms Table
            if synonym_rows:
                st.markdown("### Known Synonyms & Aliases")
                df_syn = pd.DataFrame(synonym_rows)
                st.dataframe(
                    df_syn,
                    hide_index=True,
                    width="stretch",
                    column_config=col_config,
                )
            else:
                st.info("No historical synonyms found for this species.")
