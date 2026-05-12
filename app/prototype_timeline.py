"""
prototype_timeline.py — Streamlit app for fungal species synonym search with timeline visualization

Displays synonyms as an interactive timeline where each bubble represents a synonym
positioned at its year of first publication. Clicking a bubble opens an info card.

To run:
    cd app/
    streamlit run prototype_timeline.py
"""

import plotly.graph_objects as go
import streamlit as st

MOCK_DATA = {
    "Amanita muscaria": {
        "author": "John Doe",
        "publication_year": 1860,
        "publication_name": "New Book of Mushrooms",
    },
    "Agaricus muscarius": {
        "author": "Jane Doe",
        "publication_year": 1753,
        "publication_name": "Old Book of Mushrooms",
    },
    "Other Synonym": {
        "author": "Jack Doe",
        "publication_year": 1950,
        "publication_name": "Mushrooms of BC",
    },
}


def mock_call_apis() -> list[dict]:
    """Return mock synonym data."""
    return [{"name": name, **fields} for name, fields in MOCK_DATA.items()]


def build_timeline(synonyms: list[dict]) -> go.Figure:
    sorted_syns = sorted(synonyms, key=lambda s: s["publication_year"])
    years = [s["publication_year"] for s in sorted_syns]
    names = [s["name"] for s in sorted_syns]

    # Stagger y positions above/below the timeline to reduce label overlap
    y_pos = [0.35 if i % 2 == 0 else -0.35 for i in range(len(sorted_syns))]
    text_pos = ["top center" if y > 0 else "bottom center" for y in y_pos]

    fig = go.Figure()

    # Horizontal timeline bar
    year_min = min(years) - 15
    year_max = max(years) + 15
    fig.add_shape(
        type="line",
        x0=year_min,
        x1=year_max,
        y0=0,
        y1=0,
        line=dict(color="#bdc3c7", width=2),
    )

    # Vertical tick lines from timeline to each bubble
    for year, y in zip(years, y_pos):
        fig.add_shape(
            type="line",
            x0=year,
            x1=year,
            y0=0,
            y1=y,
            line=dict(color="#bdc3c7", width=1, dash="dot"),
        )

    fig.add_trace(
        go.Scatter(
            x=years,
            y=y_pos,
            mode="markers+text",
            text=names,
            textposition=text_pos,
            textfont=dict(size=11),
            marker=dict(
                size=18,
                color="#3498db",
                line=dict(color="white", width=2),
            ),
            customdata=[
                [s["name"], s["publication_year"], s["author"], s["publication_name"]]
                for s in sorted_syns
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Year: %{customdata[1]}<br>"
                "Author: %{customdata[2]}<br>"
                "Publication: %{customdata[3]}<br>"
                "<extra></extra>"
            ),
            selected=dict(marker=dict(size=24)),
            unselected=dict(marker=dict(opacity=0.5)),
        )
    )

    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(
            title="Year of Publication",
            range=[year_min, year_max],
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            visible=False,
            range=[-1.1, 1.1],
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        dragmode="select",
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
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            on_select="rerun",
            selection_mode="points",
            key="timeline_chart",
        )

        st.caption("Click a bubble to view details.")

        # Info card for selected point
        if event and event.selection and event.selection.points:
            pt = event.selection.points[0]
            name, year, author, publication_name = pt["customdata"]

            st.divider()
            st.markdown(
                f"""
<div style="border:1px solid #e0e0e0; border-radius:10px; padding:20px; background:#fafafa;">
  <h3 style="margin-top:0"><em>{name}</em></h3>
  <table style="border-collapse:collapse; width:100%;">
    <tr><td style="padding:4px 12px 4px 0; color:#666; width:140px;">Year published</td>
        <td style="padding:4px 0"><strong>{year}</strong></td></tr>
    <tr><td style="padding:4px 12px 4px 0; color:#666;">Author</td>
        <td style="padding:4px 0">{author}</td></tr>
    <tr><td style="padding:4px 12px 4px 0; color:#666;">Publication</td>
        <td style="padding:4px 0">{publication_name}</td></tr>
  </table>
</div>
""",
                unsafe_allow_html=True,
            )
