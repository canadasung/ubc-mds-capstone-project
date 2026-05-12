"""
prototype_timeline.py — Streamlit app for fungal species synonym search with timeline visualization

Displays synonyms as an interactive timeline where each bubble represents a synonym
positioned at its year of first publication. Clicking a bubble expands it into an
info card directly on the timeline.

To run:
    cd app/
    streamlit run prototype_timeline.py
"""

import textwrap

import plotly.graph_objects as go
import streamlit as st


def _field(label: str, value: str, wrap_width: int = 22) -> str:
    """Format a label+value pair with continuation lines indented to align under the value."""
    indent = "&nbsp;" * (len(label) + 2)  # +2 for the two-space separator
    lines = textwrap.wrap(value, wrap_width)
    value_text = ("<br>" + indent).join(lines) if lines else value
    return f"<span style='color:#aaaaaa'>{label}</span>  {value_text}"


MOCK_DATA = {
    "Amanita muscaria": {
        "author": "John Doe",
        "publication_year": 1860,
        "publication_name": "New Book of Mushrooms Worldwide",
        "source": {"name": "GBIF", "url": "https://www.gbif.org/species/8168319"},
    },
    "Agaricus muscarius": {
        "author": "Jane Doe",
        "publication_year": 1753,
        "publication_name": "Old Book of Mushrooms",
        "source": {"name": "GBIF", "url": "https://www.gbif.org/species/5451774"},
    },
    "Other Synonym": {
        "author": "Jack Doe",
        "publication_year": 1950,
        "publication_name": "Mushrooms of BC",
        "source": {
            "name": "Wikipedia",
            "url": "https://en.wikipedia.org/wiki/Amanita_muscaria",
        },
    },
}


def mock_call_apis() -> list[dict]:
    """Return mock synonym data."""
    return [{"name": name, **fields} for name, fields in MOCK_DATA.items()]


def build_timeline(synonyms: list[dict]) -> go.Figure:
    sorted_syns = sorted(synonyms, key=lambda s: s["publication_year"])
    years = [s["publication_year"] for s in sorted_syns]

    # Stagger y positions above/below the timeline to reduce label overlap
    y_pos = [0.5 if i % 2 == 0 else -0.5 for i in range(len(sorted_syns))]

    fig = go.Figure()

    year_min = min(years) - 30
    year_max = max(years) + 30

    # Horizontal timeline bar
    fig.add_shape(
        type="line",
        x0=year_min,
        x1=year_max,
        y0=0,
        y1=0,
        line=dict(color="#bdc3c7", width=2),
    )

    # Vertical tick lines from timeline bar to each card
    for year, y in zip(years, y_pos):
        tick_end = 0.18 if y > 0 else -0.18
        fig.add_shape(
            type="line",
            x0=year,
            x1=year,
            y0=0,
            y1=tick_end,
            line=dict(color="#bdc3c7", width=1, dash="dot"),
        )

    # Info card annotation for each synonym
    for syn, year, y in zip(sorted_syns, years, y_pos):
        name_lines = textwrap.wrap(syn["name"], 22)
        text = (
            f"<b>{'<br>'.join(name_lines)}</b><br>"
            f"{_field('Year', str(syn['publication_year']))}<br>"
            f"{_field('Author', syn['author'])}<br>"
            f"{_field('Publication', syn['publication_name'])}<br>"
            f"<span style='color:#aaaaaa'>Source</span>  <a href='{syn['source']['url']}' target='_blank'>{syn['source']['name']}</a>"
        )
        fig.add_annotation(
            x=year,
            y=y,
            text=text,
            showarrow=False,
            bgcolor="white",
            bordercolor="#3498db",
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


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("Species Name Synonym Search")

if "pending_query" in st.session_state:
    st.session_state["query_input"] = st.session_state.pop("pending_query")

query = st.text_input(
    "Enter a species name",
    placeholder="e.g. Amanita muscaria",
    key="query_input",
)

if query:
    synonyms = mock_call_apis()

    if not synonyms:
        st.warning(f'No results found for "{query}".')
    else:
        st.markdown(f"**{len(synonyms)} synonyms found** for *{query.strip().title()}*")

        fig = build_timeline(synonyms)
        st.plotly_chart(fig, use_container_width=True)
