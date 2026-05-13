"""
prototype_node_graph.py -- Species name synonym search (node graph)

Displays synonym search results as an interactive node graph.
The search query sits at the top left. Each database that found results
appears as a row below it. Synonyms for that database extend to the right
as a row of nodes.

Clicking a node opens the corresponding database search page in a new tab.
Nodes from sources without a search URL show a warning message instead.

To run (from the project root):
    streamlit run app/prototype_node_graph.py
"""

import colorsys
import json

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from scripts.APIs.call_APIs import call_apis


# ---------------------------------------------------------------------------
# Source configuration
#
# To add a new database, add one entry to each of the four dicts below.
# Set SOURCE_URLS to None if the database has no web search page.
# Colors follow a three-shade pattern per source:
#   SOURCE_COLORS  -- border/accent (darkest)
#   DB_BG_COLORS   -- database node fill (medium)
#   SYNONYM_COLORS -- synonym node fill (lightest)
# ---------------------------------------------------------------------------

SOURCE_LABELS = {
    "gbif":            "GBIF",
    "genbank":         "GenBank",
    "mushroomobs":     "Mushroom Observer",
    "mycoportal":      "MyCoPortal",
    "bryophyteportal": "Bryophyte Portal",
    "macroalgae":      "Macroalgae Portal",
}

# Use {} as the placeholder for the species name in each URL template.
SOURCE_URLS = {
    "gbif":            "https://www.gbif.org/search?q={}",
    "genbank":         "https://www.ncbi.nlm.nih.gov/search/all/?term={}",
    "mushroomobs":     None,
    "mycoportal":      "https://mycoportal.org/portal/taxa/index.php?taxon={}",
    "bryophyteportal": "https://bryophyteportal.org/portal/taxa/index.php?taxon={}",
    "macroalgae":      "https://macroalgae.org/portal/taxa/index.php?taxon={}",
}

def _source_color(index: int, total: int, lightness: float = 0.38) -> str:
    """Evenly-spaced hue on the color wheel at full saturation."""
    r, g, b = colorsys.hls_to_rgb(index / total, lightness, 1.0)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))

SOURCE_COLORS = {
    src: _source_color(i, len(SOURCE_LABELS))
    for i, src in enumerate(SOURCE_LABELS)
}

def _derive_color(hex_color: str, sat_factor: float, lightness: float | None = None) -> str:
    """Return a color derived from hex_color with adjusted HSL saturation and lightness.

    sat_factor multiplies the original saturation (0.5 = half, 0.25 = quarter, etc.).
    lightness, if given, overrides the original L value directly (0–1 scale).
    """
    r, g, b = (int(hex_color.lstrip("#")[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(h, lightness if lightness is not None else l, s * sat_factor)
    return "#{:02X}{:02X}{:02X}".format(int(r2 * 255), int(g2 * 255), int(b2 * 255))

DB_BG_COLORS   = {src: _derive_color(color, sat_factor=0.35)                for src, color in SOURCE_COLORS.items()}
SYNONYM_COLORS = {src: _derive_color(color, sat_factor=0.25, lightness=0.75) for src, color in SOURCE_COLORS.items()}

# Query node (the search term at the top left)
QUERY_NODE_BG     = "#FFFFFF"
QUERY_NODE_BORDER = "#CCCCCC"
QUERY_NODE_TEXT   = "#111111"

# DB nodes that failed to fetch
ERROR_BG     = "#EEEEEE"
ERROR_BORDER = "#9E9E9E"


# ---------------------------------------------------------------------------
# Layout constants (vis.js pixel coordinates)
#
# The query node is placed at (0, 0). DB nodes stack downward along x=0.
# Synonym nodes extend to the right of their DB row at increasing x values.
# ---------------------------------------------------------------------------

ROW_HEIGHT    = 150  # vertical distance between each source row
SYN_X_OFFSET  = 280  # x position of the first synonym in a row
SYN_X_SPACING = 110  # x distance between consecutive synonyms


# ---------------------------------------------------------------------------
# vis.js graph options
#
# Nodes are styled as fixed rectangular boxes. Physics is disabled so nodes
# stay in the positions we assign. Dragging nodes is also disabled to keep
# the grid layout intact.
# ---------------------------------------------------------------------------

GRAPH_OPTIONS = """
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
    "arrows": { "to": { "enabled": true, "scaleFactor": 0.6 } },
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

# JavaScript injected into the pyvis-generated HTML after the network is created.
# Each node carries a "url" property set in Python. On click, we open that URL
# in a new tab. If url is absent, we show a brief message instead of doing nothing.
CLICK_HANDLER_JS = """<script>
(function() {
  var toast = document.createElement("div");
  toast.style.cssText = [
    "position:fixed", "bottom:24px", "left:50%", "transform:translateX(-50%)",
    "background:#333", "color:#fff", "padding:8px 18px", "border-radius:6px",
    "font:13px/1.4 sans-serif", "z-index:9999", "opacity:0",
    "transition:opacity 0.25s", "pointer-events:none"
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


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_source(query: str, source: str) -> dict:
    """Fetch results for a single source. Cached independently so toggling a
    checkbox never re-queries sources that were already fetched."""
    return json.loads(call_apis(query, sources=[source]))

def fetch(query: str, sources: tuple[str, ...]) -> dict:
    """Merge per-source results for all selected sources."""
    results = {}
    for source in sources:
        results.update(fetch_source(query, source))
    return results


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _synonym_node_label(name: str) -> str:
    """Return an HTML label for a synonym node.

    Binomial names (two or more words) are split across two italic lines.
    Single-word names are shown in bold.
    """
    parts = name.split()
    if len(parts) >= 2:
        return f"<b><i>{parts[0]}</i></b>\n<b><i>{' '.join(parts[1:])}</i></b>"
    return f"<b>{name}</b>"


def build_graph(query: str, results: dict, expanded: set) -> str:
    """Build and return the vis.js node graph as an HTML string.

    Args:
        query:    The species name that was searched.
        results:  Dict mapping each source key to a synonym dict or error string.
        expanded: Source keys whose synonym nodes should be visible.

    Returns:
        A complete HTML string ready for streamlit components.html.
    """
    net = Network(height="650px", width="100%", bgcolor="#fafafa")
    net.set_options(GRAPH_OPTIONS)

    # Query node -- top left anchor of the whole layout
    net.add_node(
        "center",
        label=f"<b>{query}</b>\n<i>Search Query</i>",
        color={
            "background": QUERY_NODE_BG,
            "border":     QUERY_NODE_BORDER,
        },
        font={"color": QUERY_NODE_TEXT, "size": 16},
        widthConstraint={"minimum": 200, "maximum": 260},
        heightConstraint={"minimum": 64},
        x=0, y=0,
        title=f"Query: {query}",
    )

    # One row per database that returned results (or an error worth showing)
    row = 0
    for source, label in SOURCE_LABELS.items():
        if source not in results:
            continue
        data     = results[source]
        is_error = isinstance(data, str)
        count    = len(data) if isinstance(data, dict) else 0

        db_x = 0
        db_y = ROW_HEIGHT * (row + 1)
        row += 1

        if is_error:
            db_label = f"<b>{label}</b>\n<code>error fetching results</code>"
            bg       = ERROR_BG
            border   = ERROR_BORDER
            tooltip  = str(data)
        elif count == 0:
            db_label = f"<b>{label}</b>\n<i>no results found</i>"
            bg       = DB_BG_COLORS[source]
            border   = SOURCE_COLORS[source]
            tooltip  = f"{label}: no results found"
        else:
            noun     = "name" if count == 1 else "names"
            db_label = f"<b>{label}</b>\n{count} {noun} found"
            bg       = DB_BG_COLORS[source]
            border   = SOURCE_COLORS[source]
            tooltip  = f"{label}: {count} {noun} found"

        url_template = SOURCE_URLS.get(source)
        # Species names are plain Latin words, so replacing spaces is enough to make a valid URL
        db_url       = url_template.format(query.replace(" ", "+")) if url_template else None
        if not db_url and not is_error:
            tooltip += "\n(no direct link available for this source)"

        net.add_node(
            source,
            label=db_label,
            color={
                "background": bg,
                "border":     border,
            },
            font={"color": "#111111", "size": 14},
            widthConstraint={"minimum": 180, "maximum": 240},
            heightConstraint={"minimum": 64},
            x=db_x, y=db_y,
            title=tooltip,
            url=db_url,
        )
        net.add_edge("center", source)

        if source not in expanded or not isinstance(data, dict):
            continue

        # Synonym nodes extend to the right of the DB node in this row
        for j, name in enumerate(data.keys()):
            node_id  = f"{source}|{name}"
            node_url = url_template.format(name.replace(" ", "+")) if url_template else None
            tooltip  = name
            if node_url:
                tooltip += f"\n{node_url}"
            else:
                tooltip += "\n(no direct link available for this source)"

            net.add_node(
                node_id,
                label=_synonym_node_label(name),
                color={
                    "background": SYNONYM_COLORS[source],
                    "border":     SOURCE_COLORS[source],
                },
                font={"color": "#111111", "size": 13},
                widthConstraint={"minimum": 160, "maximum": 220},
                heightConstraint={"minimum": 64},
                x=SYN_X_OFFSET + SYN_X_SPACING * j,
                y=db_y,
                title=tooltip,
                url=node_url,
            )
            net.add_edge(source, node_id)

    html = net.generate_html()
    return html.replace("</body>", CLICK_HANDLER_JS + "\n</body>")


# ---------------------------------------------------------------------------
# Streamlit app
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Species name synonym search", layout="wide")

with st.sidebar:
    st.title("Species name synonym search")
    query = st.text_input("Species name", placeholder="e.g. Marchantia polymorpha")

    with st.expander("Databases", expanded=True):
        selected_sources = tuple(
            src for src, label in SOURCE_LABELS.items()
            if st.checkbox(label, value=True, key=f"src_{src}")
        )

if not query.strip():
    st.stop()

if not selected_sources:
    st.warning("Select at least one database to query.")
    st.stop()

with st.sidebar:
    with st.spinner("Querying databases..."):
        results = fetch(query.strip(), selected_sources)

# All sources that returned at least one result are shown expanded by default
expanded = {
    src for src in selected_sources
    if isinstance(results.get(src), dict) and results[src]
}

html = build_graph(query.strip(), results, expanded)
components.html(html, height=680, scrolling=False)
