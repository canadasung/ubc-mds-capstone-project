"""
Prototype Master B — Streamlit skeleton
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure the project root is on sys.path so `scripts` is importable
# regardless of which directory Streamlit is launched from.
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.utils.normalize_query_string import normalize_query_string  # noqa: E402
from prototype_master_views import view_table, view_timeline, view_node, view_taxonomy, view_debug

# ── Search toggle ─────────────────────────────────────────────────────────────
# Flip to False once the real API pipeline is ready.
USE_MOCK_DATA: bool = True

# ── Paths ─────────────────────────────────────────────────────────────────────
_APP_DIR = Path(__file__).parent
_SAMPLE_DIR = _APP_DIR.parent / "data" / "sample"


# ── Search helpers ────────────────────────────────────────────────────────────
class SearchError(ValueError):
    """Raised when a search produces no results or cannot be executed."""


def _query_to_filename(query: str) -> str:
    """Convert a query string to the snake_case filename used in file names.

    Uses normalize_query_string for whitespace/casing, then converts to filename format.

    'Amanita muscaria'  →  'amanita_muscaria'
    ' AMANITA  MUSCARIA '  →  'amanita_muscaria'
    """
    normalized = normalize_query_string(query)           # strip, collapse whitespace, capitalize first
    filename = normalized.lower().replace(" ", "_")      # lowercase + spaces → underscores
    filename = re.sub(r"[^a-z0-9_]", "", filename)      # strip any remaining non-alphanumeric chars
    return filename


def _list_available_samples() -> list[str]:
    """Return human-readable names for all available sample CSV files."""
    return [
        normalize_query_string(f.stem.removeprefix("sample_table_data_").replace("_", " "))
        for f in sorted(_SAMPLE_DIR.glob("sample_table_data_*.csv"))
    ]


def _mock_search(query: str, **kwargs) -> pd.DataFrame:
    """Read the pre-computed sample CSV that matches *query*.

    File naming: data/sample/sample_table_data_{filename}.csv
    e.g. 'Amanita muscaria' → sample_table_data_amanita_muscaria.csv
    """
    csv_path = _SAMPLE_DIR / f"sample_table_data_{_query_to_filename(query)}.csv"
    if not csv_path.exists():
        available = _list_available_samples()
        hint = f"  Available samples: {', '.join(available)}" if available else ""
        raise SearchError(f"No sample data found for '{query}'.{hint}")
    return pd.read_csv(csv_path)


def _live_search(query: str, **kwargs) -> pd.DataFrame:
    """Call the real API pipeline and return aggregated results.

    TODO: replace the stub below once the frontend pipeline is ready.
    Suggested wiring:
        from scripts.APIs.GBIF import get_gbif_synonyms
        ...
        return aggregated_dataframe
    """
    raise SearchError(
        "Live search is not yet implemented. "
        "Set USE_MOCK_DATA = True or implement _live_search()."
    )


def run_search(query: str, **kwargs) -> pd.DataFrame:
    """Dispatch to mock or live backend based on USE_MOCK_DATA."""
    query = query.strip()
    if not query:
        raise SearchError("Search query must not be empty.")
    return _mock_search(query, **kwargs) if USE_MOCK_DATA else _live_search(query, **kwargs)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Prototype Master B",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Left search-panel: distinct background so it reads as a separate zone */
    [data-testid="stHorizontalBlock"]:first-child
        > [data-testid="stColumn"]:first-child {
        background-color: #eef2f9;
        border-radius: 0.5rem;
        padding: 0.75rem;
    }

    /* Restore visible border on text inputs inside the left panel so they
       don't blend into the coloured background */
    [data-testid="stHorizontalBlock"]:first-child
        > [data-testid="stColumn"]:first-child
        [data-baseweb="input"] {
        background-color: #ffffff;
        border: 1px solid #b0bccf !important;
        border-radius: 0.375rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state defaults ────────────────────────────────────────────────────
st.session_state.setdefault("search_results", None)      # pd.DataFrame | None
st.session_state.setdefault("selected_record", None)     # dict | None
st.session_state.setdefault("pinned_records", [])        # list[dict]
st.session_state.setdefault("search_panel_open", True)   # bool
st.session_state.setdefault("debug_mode", True)          # bool
st.session_state.setdefault("active_tab", "Debug")       # str — matches debug_mode=True default
st.session_state.setdefault("last_search_query", "")     # str — backing store for the search field

# ── Top-level layout: left panel | right panel ───────────────────────────────
# Column ratio shrinks to a thin strip when the search panel is collapsed.
_panel_open = st.session_state["search_panel_open"]
left_col, right_col = st.columns([1, 3] if _panel_open else [0.07, 0.93])

# Deferred rerun flag — set to True anywhere in the script that needs a rerun,
# then st.rerun() is called once at the very end after all columns have rendered.
# This ensures right_col (and its widgets) always renders before the rerun,
# so widget state like view_mode is never wiped mid-run.
_rerun_needed = False

# ═══════════════════════════════════════════════════════════════════════════
# LEFT — Search panel
# ═══════════════════════════════════════════════════════════════════════════
with left_col:
    # Collapse / expand toggle button — always visible
    _toggle_icon = "◀" if _panel_open else "▶"
    if st.button(_toggle_icon, key="toggle_search_panel", help="Toggle search panel"):
        st.session_state["search_panel_open"] = not _panel_open
        _rerun_needed = True

    if _panel_open:
        st.header("Search")

        # Use value= (not key=) so Streamlit does not own the state.
        # Widget-owned state gets wiped when the widget doesn't render (e.g.
        # panel collapsed); a plain session_state key is never touched by Streamlit.
        _debug_toggled = st.toggle("Debug Mode", value=st.session_state["debug_mode"])
        if _debug_toggled != st.session_state["debug_mode"]:
            st.session_state["debug_mode"] = _debug_toggled
            if _debug_toggled:
                st.session_state["active_tab"] = "Debug"
            elif st.session_state.get("active_tab") == "Debug":
                st.session_state["active_tab"] = "Table"
            _rerun_needed = True

        # Wrapping in a form means pressing Enter in the text field is
        # equivalent to clicking the Search button.
        #
        # Restore widget state from the backing store if it was wiped (e.g.
        # after the panel was collapsed and the widget didn't render).
        # We can't drop key= on a form input — without it, text typed before
        # submission would be lost on every rerun.
        if "search_query" not in st.session_state:
            st.session_state["search_query"] = st.session_state["last_search_query"]

        with st.form("search_form"):
            query = st.text_input(
                label="Search query",
                placeholder="Enter species name (e.g. Amanita muscaria)",
                key="search_query",
            )

            with st.expander("Advanced options", expanded=False):
                st.caption("Advanced search options will go here.")

            search_btn = st.form_submit_button("Search", use_container_width=True, type="primary")

    # ── Search handler ────────────────────────────────────────────────────
    # Guard: search_btn / query are only defined when the panel is open.
    if _panel_open and search_btn and query:
        try:
            df = run_search(query)
            st.session_state["search_results"] = df
            st.session_state["selected_record"] = None    # clear stale selection
            st.session_state["last_search_query"] = query # persist to backing store
            _rerun_needed = True
        except SearchError as e:
            st.error(str(e))

# ═══════════════════════════════════════════════════════════════════════════
# RIGHT — Views
# ═══════════════════════════════════════════════════════════════════════════
with right_col:

    # ── View-layout toggle ────────────────────────────────────────────────
    view_mode = st.radio(
        "View layout",
        options=["Tabs layout", "Quadrants layout"],
        horizontal=True,
        key="view_mode",
        label_visibility="collapsed",
    )
    st.divider()

    # ── TAB MODE ──────────────────────────────────────────────────────────
    if view_mode == "Tabs layout":
        _debug_on = st.session_state["debug_mode"]
        _tab_options = (
            ["Debug", "Table", "Timeline", "Node", "Taxonomic"]
            if _debug_on
            else ["Table", "Timeline", "Node", "Taxonomic"]
        )

        # Clamp stored tab to a valid option (e.g. after debug mode is turned off)
        if st.session_state.get("active_tab") not in _tab_options:
            st.session_state["active_tab"] = _tab_options[0]

        active_tab = st.segmented_control(
            "View",
            options=_tab_options,
            key="active_tab",
            label_visibility="collapsed",
        )

        if active_tab == "Debug":
            view_debug.render()
        elif active_tab == "Table":
            view_table.render()
        elif active_tab == "Timeline":
            view_timeline.render()
        elif active_tab == "Node":
            view_node.render()
        elif active_tab == "Taxonomic":
            view_taxonomy.render()

    # ── QUADRANT MODE ─────────────────────────────────────────────────────
    else:
        top_left, top_right = st.columns(2)
        bot_left, bot_right = st.columns(2)

        with top_left:  view_table.render()
        with top_right: view_timeline.render()
        with bot_left:  view_node.render()
        with bot_right: view_taxonomy.render()
        # Note: Debug View is intentionally excluded from the quadrant layout.

# ── Deferred rerun ────────────────────────────────────────────────────────────
# Called here — after both columns have fully rendered — so all keyed widgets
# (e.g. view_mode) are registered before the rerun wipes unrendered widget state.
if _rerun_needed:
    st.rerun()
