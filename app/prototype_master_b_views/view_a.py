"""
View A — Table View

Reads:  st.session_state["search_results"]  (pd.DataFrame | None)
Writes: st.session_state["selected_record"] (dict | None)
"""

import streamlit as st


def render() -> None:
    st.subheader("Table View")

    st.info("Run a search to populate this view.")
