"""
Debug View — raw inspection of the current search results DataFrame.

Only shown in Tab mode (never rendered in the quadrant layout).

Reads:  st.session_state["search_results"]  (pd.DataFrame | None)
Writes: (none — display only)
"""

import streamlit as st


def render() -> None:
    st.subheader("Debug View")

    df = st.session_state.get("search_results")

    if df is None:
        st.info("No search has been run yet.")
        return

    if df.empty:
        st.warning("Search returned an empty table.")
        return

    st.caption(f"{len(df)} rows × {len(df.columns)} columns")
    st.dataframe(
        df,
        width="stretch",
        column_config={
            "Source Link": st.column_config.LinkColumn("Source Link"),
        },
    )
