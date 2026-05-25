"""
View C — Node View

Displays species synonym search results as an interactive vis.js node graph.

Layout (left → right):
  [Query node]  →  [Source node]  →  [Name / synonym nodes …]

One source row is drawn per unique "Source Name" value in the results DataFrame.
Synonym nodes are drawn to the right of their source node.  Clicking a node
that carries a URL opens it in a new browser tab.

Reads:  st.session_state["search_results"]   (pd.DataFrame | None)
        st.session_state["last_search_query"] (str)
Writes: (none — display only)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

# normalize_query_string lives in scripts/, which is at the project root.
# prototype_master_b.py adds the root to sys.path before importing views,
# so this import is safe at runtime.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.utils.normalize_query_string import normalize_query_string  # noqa: E402


# ── Black-and-white node palette ─────────────────────────────────────────────
_QUERY_BG     = "#FFFFFF"   # query node
_QUERY_BORDER = "#333333"

_DB_BG        = "#EEEEEE"   # source / DB nodes — light grey so they read as "headers"
_DB_BORDER    = "#333333"

_SYN_BG       = "#FFFFFF"   # synonym / name nodes — plain white
_SYN_BORDER   = "#555555"   # slightly lighter border than DB nodes


# ── Layout constants (vis.js pixel coordinates) ───────────────────────────────
_ROW_HEIGHT    = 150   # vertical gap between source rows
_SYN_X_OFFSET  = 280   # x position of the first synonym node in a row
_SYN_X_SPACING = 110   # x distance between consecutive synonym nodes


# ── vis.js graph options ──────────────────────────────────────────────────────
_GRAPH_OPTIONS = """
var options = {
  "nodes": {
    "shape": "box",
    "font": { "multi": "html", "face": "monospace", "color": "#111111" },
    "borderWidth": 2,
    "borderWidthSelected": 3,
    "shadow": { "enabled": true, "color": "rgba(0,0,0,0.2)", "size": 6, "x": 2, "y": 2 },
    "margin": { "top": 10, "right": 14, "bottom": 10, "left": 14 },
    "chosen": false
  },
  "edges": {
    "arrows": { "to": { "enabled": false } },
    "smooth": false,
    "color": { "color": "#aaaaaa", "opacity": 0.8 },
    "width": 1.5,
    "chosen": false
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 150,
    "dragNodes": false,
    "zoomView": true,
    "navigationButtons": true
  },
  "physics": { "enabled": false }
}
"""

# Injected after the vis.js network is created: clicking a node opens its URL.
_CLICK_HANDLER_JS = """<script>
(function() {
  var toast = document.createElement("div");
  toast.style.cssText = [
    "position:fixed","bottom:24px","left:50%","transform:translateX(-50%)",
    "background:#333","color:#fff","padding:8px 18px","border-radius:6px",
    "font:13px/1.4 sans-serif","z-index:9999","opacity:0",
    "transition:opacity 0.25s","pointer-events:none"
  ].join(";");
  document.body.appendChild(toast);

  function showToast(msg) {
    toast.textContent = msg;
    toast.style.opacity = "1";
    clearTimeout(toast._t);
    toast._t = setTimeout(function() { toast.style.opacity = "0"; }, 2500);
  }

  network.on("click", function(params) {
    if (params.nodes.length > 0) {
      var node = nodes.get(params.nodes[0]);
      if (node && node.url) {
        window.open(node.url, "_blank");
      } else if (node) {
        showToast("No direct link available for this source");
      }
    }
  });
})();
</script>"""


# ── Source → search-page URL templates (used for the DB / source nodes) ──────
# Keyed by lowercase source name.  Set to None when no search page exists.
_SOURCE_URL_TEMPLATES: dict[str, str | None] = {
    "gbif":            "https://www.gbif.org/search?q={}",
    "genbank":         "https://www.ncbi.nlm.nih.gov/search/all/?term={}",
    "mushroomobs":     None,
    "mycoportal":      "https://mycoportal.org/portal/taxa/index.php?taxon={}",
    "bryophyteportal": "https://bryophyteportal.org/portal/taxa/index.php?taxon={}",
    "macroalgae":      "https://macroalgae.org/portal/taxa/index.php?taxon={}",
}


# ── Data helpers ──────────────────────────────────────────────────────────────

def _synonym_node_label(name: str) -> str:
    """Italic binomial label split across two lines; single-word names in bold."""
    parts = name.split()
    if len(parts) >= 2:
        return f"<b><i>{parts[0]}</i></b>\n<b><i>{' '.join(parts[1:])}</i></b>"
    return f"<b>{name}</b>"


def _df_to_results(df: pd.DataFrame) -> dict[str, list[dict]]:
    """Group the search-results DataFrame by source.

    Returns a dict of the form::

        {
            "GBIF": [
                {"name": "Amanita muscaria", "url": "https://…", "status": "Accepted"},
                {"name": "Agaricus muscarius", "url": "https://…", "status": "Synonym"},
                …
            ],
            …
        }
    """
    results: dict[str, list[dict]] = {}
    for source, group in df.groupby("Source Name", sort=False):
        rows: list[dict] = []
        for _, row in group.iterrows():
            genus   = str(row.get("Genus",   "")).strip()
            species = str(row.get("Species", "")).strip()
            full_name = normalize_query_string(f"{genus} {species}".strip())

            raw_url = row.get("Source Link")
            url = str(raw_url) if pd.notna(raw_url) and raw_url else None

            status = str(row.get("GBIF Accepted Status", "")).strip()

            rows.append({"name": full_name, "url": url, "status": status})
        results[str(source)] = rows
    return results


# ── Graph construction ────────────────────────────────────────────────────────

def _build_graph(query: str, results: dict[str, list[dict]]) -> str:
    """Build and return the vis.js graph as a complete HTML string.

    Args:
        query:   The species name that was searched (used for the centre node).
        results: Output of _df_to_results — one entry per source.
    """
    net = Network(height="650px", width="100%", bgcolor="#fafafa")
    net.set_options(_GRAPH_OPTIONS)

    sources    = list(results.keys())
    total_rows = len(sources)
    # Vertically centre the query node among all source rows
    query_y    = _ROW_HEIGHT * (total_rows + 1) / 2

    # ── Query node (far left) ────────────────────────────────────────────────
    net.add_node(
        "center",
        label=f"<b>{query}</b>\n<i>Search Query</i>",
        color={"background": _QUERY_BG, "border": _QUERY_BORDER},
        font={"color": "#111111", "size": 16},
        widthConstraint={"minimum": 200, "maximum": 260},
        heightConstraint={"minimum": 64},
        x=-_SYN_X_OFFSET,
        y=query_y,
        title=f"Query: {query}",
    )

    for row_idx, (source, name_rows) in enumerate(results.items()):
        count = len(name_rows)
        db_y  = _ROW_HEIGHT * (row_idx + 1)

        # ── Source / DB node ─────────────────────────────────────────────────
        noun     = "name" if count == 1 else "names"
        db_label = (
            f"<b>{source}</b>\n{count} {noun} found"
            if count
            else f"<b>{source}</b>\n<i>no results found</i>"
        )

        template = _SOURCE_URL_TEMPLATES.get(source.lower())
        db_url   = template.format(query.replace(" ", "+")) if template else None

        net.add_node(
            source,
            label=db_label,
            color={"background": _DB_BG, "border": _DB_BORDER},
            font={"color": "#111111", "size": 14},
            widthConstraint={"minimum": 180, "maximum": 240},
            heightConstraint={"minimum": 64},
            x=0,
            y=db_y,
            title=f"{source}: {count} {noun} found",
            url=db_url,
        )
        net.add_edge("center", source)

        # ── Name / synonym nodes (extend right) ──────────────────────────────
        for j, entry in enumerate(name_rows):
            name    = entry["name"]
            url     = entry["url"]
            status  = entry["status"]
            node_id = f"{source}|{name}"

            tooltip = f"{name}"
            if status:
                tooltip += f"\nStatus: {status}"
            tooltip += f"\n{url}" if url else "\n(no direct link available)"

            net.add_node(
                node_id,
                label=_synonym_node_label(name),
                color={"background": _SYN_BG, "border": _SYN_BORDER},
                font={"color": "#111111", "size": 13},
                widthConstraint={"minimum": 160, "maximum": 220},
                heightConstraint={"minimum": 64},
                x=_SYN_X_OFFSET + _SYN_X_SPACING * j,
                y=db_y,
                title=tooltip,
                url=url,
            )
            net.add_edge(source, node_id)

    html = net.generate_html()
    return html.replace("</body>", _CLICK_HANDLER_JS + "\n</body>")


# ── Public render entry-point ─────────────────────────────────────────────────

def render() -> None:
    df: pd.DataFrame | None = st.session_state.get("search_results")
    query: str = st.session_state.get("last_search_query", "").strip()

    st.subheader("Node View")

    if df is None or df.empty:
        st.info("Run a search to populate this view.")
        return

    required_cols = {"Source Name", "Genus", "Species"}
    missing = required_cols - set(df.columns)
    if missing:
        st.error(f"Search results are missing expected columns: {', '.join(sorted(missing))}")
        return

    results = _df_to_results(df)
    html    = _build_graph(query or "?", results)
    components.html(html, height=680, scrolling=False)
