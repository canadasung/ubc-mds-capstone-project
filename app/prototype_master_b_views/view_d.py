"""
View D — Taxonomic View

Reads:  st.session_state["selected_record"]
Writes: (none — display only)
"""

import streamlit as st


def render() -> None:
    st.subheader("Taxonomic View")

    st.info("Run a search to populate this view.")
