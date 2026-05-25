"""
View B — Timeline View

Displays species name synonyms as an interactive Plotly timeline.
Each card is positioned at its year of first publication; cards alternate
above and below the axis to reduce overlap.  Clicking a source link
in a card opens the corresponding database page in a new tab.

Entries that have no publication year are listed in a collapsible table
below the chart.

Reads:  st.session_state["search_results"]   (pd.DataFrame | None)
        st.session_state["last_search_query"] (str)
Writes: (none — display only)
"""

from __future__ import annotations

import colorsys
import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── Color helper ──────────────────────────────────────────────────────────────

def _source_accent(index: int, total: int, lightness: float = 0.45) -> str:
    """Evenly-spaced hue on the color wheel — one accent color per source."""
    r, g, b = colorsys.hls_to_rgb(index / max(total, 1), lightness, 0.75)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


# ── Data helpers ──────────────────────────────────────────────────────────────

def _field(label: str, value: str, wrap_width: int = 22) -> str:
    """Format a greyed label + value pair, wrapping long values."""
    indent = "&nbsp;" * (len(label) + 2)
    lines  = textwrap.wrap(value, wrap_width)
    value_html = ("<br>" + indent).join(lines) if lines else value
    return f"<span style='color:#aaaaaa'>{label}</span>  {value_html}"


def _df_to_synonyms(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Split DataFrame rows into *(dated, undated)* synonym lists.

    'dated'   rows have a valid Publication Year and appear on the timeline.
    'undated' rows are returned separately for the collapsible fallback table.
    """
    dated:   list[dict] = []
    undated: list[dict] = []

    for _, row in df.iterrows():
        raw_year = row.get("Publication Year")
        has_year = pd.notna(raw_year) and str(raw_year).strip() not in ("", "nan")

        genus   = str(row.get("Genus",   "") or "").strip()
        species = str(row.get("Species", "") or "").strip()
        name    = f"{genus} {species}".strip()

        def _safe(col: str) -> str:
            v = row.get(col)
            return str(v).strip() if pd.notna(v) and str(v).strip() not in ("", "nan") else "—"

        url = row.get("Source Link")
        url = str(url) if pd.notna(url) and url else None

        entry: dict = {
            "name":             name,
            "author":           _safe("Author"),
            "publication_name": _safe("Publication Name"),
            "source":           {"name": str(row.get("Source Name", "")).strip(), "url": url},
            "status":           _safe("GBIF Accepted Status"),
        }

        if has_year:
            entry["publication_year"] = int(float(raw_year))
            dated.append(entry)
        else:
            undated.append(entry)

    return dated, undated


# ── Chart construction ────────────────────────────────────────────────────────

def _build_timeline(synonyms: list[dict], source_colors: dict[str, str]) -> go.Figure:
    """Return a Plotly figure with one annotated card per synonym."""
    sorted_syns = sorted(synonyms, key=lambda s: s["publication_year"])
    years = [s["publication_year"] for s in sorted_syns]

    # Alternate cards above / below the axis to reduce overlap
    y_pos = [0.5 if i % 2 == 0 else -0.5 for i in range(len(sorted_syns))]

    year_min = min(years) - 30
    year_max = max(years) + 30

    fig = go.Figure()

    # ── Horizontal axis bar ───────────────────────────────────────────────────
    fig.add_shape(
        type="line",
        x0=year_min, x1=year_max,
        y0=0,         y1=0,
        line=dict(color="#bdc3c7", width=2),
    )

    # ── Dotted tick lines from axis to each card ──────────────────────────────
    for year, y in zip(years, y_pos):
        tick_end = 0.18 if y > 0 else -0.18
        fig.add_shape(
            type="line",
            x0=year, x1=year,
            y0=0,    y1=tick_end,
            line=dict(color="#bdc3c7", width=1, dash="dot"),
        )

    # ── Info cards ────────────────────────────────────────────────────────────
    for syn, year, y in zip(sorted_syns, years, y_pos):
        src_name = syn["source"]["name"]
        src_url  = syn["source"]["url"]
        color    = source_colors.get(src_name, "#3498db")

        source_html = (
            f"<a href='{src_url}' target='_blank'>{src_name}</a>"
            if src_url else src_name
        )
        status_line = (
            f"<br>{_field('Status', syn['status'])}"
            if syn.get("status") and syn["status"] != "—" else ""
        )

        name_lines = textwrap.wrap(syn["name"], 22)
        card_html = (
            f"<b>{'<br>'.join(name_lines)}</b><br>"
            f"{_field('Year',        str(year))}<br>"
            f"{_field('Author',      syn['author'])}<br>"
            f"{_field('Publication', syn['publication_name'])}<br>"
            f"<span style='color:#aaaaaa'>Source</span>  {source_html}"
            f"{status_line}"
        )

        fig.add_annotation(
            x=year, y=y,
            text=card_html,
            showarrow=False,
            bgcolor="white",
            bordercolor=color,
            borderwidth=2,
            borderpad=12,
            font=dict(size=11, color="#333333", family="Courier New, monospace"),
            align="left",
            xanchor="center",
            yanchor="middle",
        )

    fig.update_layout(
        height=480,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(
            title="Year of Publication",
            range=[year_min, year_max],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            visible=False,
            range=[-1.4, 1.4],
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        dragmode="pan",
    )

    return fig


def _render_undated_table(entries: list[dict]) -> None:
    """Show entries with no publication year in a collapsible table."""
    label = f"{len(entries)} entr{'ies' if len(entries) != 1 else 'y'} without a publication year"
    with st.expander(label, expanded=False):
        rows = [
            {
                "Name":        e["name"],
                "Author":      e["author"],
                "Source":      e["source"]["name"],
                "Status":      e["status"],
            }
            for e in entries
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Public render entry-point ─────────────────────────────────────────────────

def render() -> None:
    df: pd.DataFrame | None = st.session_state.get("search_results")
    query: str = st.session_state.get("last_search_query", "").strip()

    st.subheader("Timeline View")

    if df is None or df.empty:
        st.info("Run a search to populate this view.")
        return

    if "Source Name" not in df.columns:
        st.error("Search results are missing the 'Source Name' column.")
        return

    dated, undated = _df_to_synonyms(df)

    if not dated:
        st.info("No publication years found in the results — timeline cannot be rendered.")
        if undated:
            _render_undated_table(undated)
        return

    # One accent color per source, consistent across both dated and undated entries
    all_sources   = sorted({e["source"]["name"] for e in dated + undated})
    source_colors = {
        src: _source_accent(i, len(all_sources))
        for i, src in enumerate(all_sources)
    }

    n = len(dated)
    st.markdown(
        f"**{n} name{'s' if n != 1 else ''}** with publication dates for *{query}*"
    )

    fig = _build_timeline(dated, source_colors)
    st.plotly_chart(fig, use_container_width=True)

    if undated:
        _render_undated_table(undated)
