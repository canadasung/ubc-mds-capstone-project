"""
app_dash.py
To run: python app_dash.py
"""
import json
import sys
from pathlib import Path
from dash import Dash, html, dcc, dash_table, Input, Output

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.APIs.call_APIs import call_apis

source_labels = {
    "gbif": "GBIF",
    "genbank": "GenBank",
    "mushroomobs": "Mushroom Observer",
}

app = Dash(__name__)

# 1. UI Definition
app.layout = html.Div([
    html.H2("Species Name Synonym Search"),
    
    # Input with debounce so it only triggers after the user stops typing
    dcc.Input(
        id="query-input",
        type="text",
        placeholder="e.g. Amanita muscaria",
        debounce=True, 
        style={"width": "300px", "marginBottom": "10px", "padding": "5px"}
    ),
    
    html.Details([
        html.Summary("Advanced filters", style={"cursor": "pointer"}),
        dcc.Checklist(
            id="source-checklist",
            options=[{"label": v, "value": k} for k, v in source_labels.items()],
            value=list(source_labels.keys()),
            inline=True,
            style={"marginTop": "10px"}
        )
    ], style={"marginBottom": "20px"}),
    
    html.Div(id="messages-container", style={"marginBottom": "10px"}),
    
    dash_table.DataTable(
        id="results-table",
        style_cell={"textAlign": "left", "padding": "10px", "fontFamily": "sans-serif"},
        style_header={"fontWeight": "bold"},
        # Make the very first row bold
        style_data_conditional=[
            {
                "if": {"row_index": 0},
                "fontWeight": "bold"
            }
        ]
    )
])

# 2. Server Logic Callback
@app.callback(
    Output("results-table", "data"),
    Output("results-table", "columns"),
    Output("messages-container", "children"),
    Input("query-input", "value"),
    Input("source-checklist", "value")
)
def update_table(query, selected_sources):
    if not query:
        return [], [], []

    if not selected_sources:
        return [], [], html.Div("Select at least one source to query.", style={"color": "orange"})

    raw = call_apis(query, sources=selected_sources)
    results = json.loads(raw)

    messages = []
    for source, label in source_labels.items():
        if source in selected_sources:
            val = results.get(source, {})
            if isinstance(val, str):
                messages.append(html.Div(f"{label}: {val}", style={"color": "red"}))

    selected_labels = [source_labels[s] for s in selected_sources]

    source_names = {
        source: {n.lower() for n in results[source].keys()}
        for source in selected_sources
        if isinstance(results.get(source), dict)
    }

    query_lower = query.lower()
    seen_lower = {query_lower}
    unique_names = [query]
    
    for src_set in source_names.values():
        for name_lower in src_set:
            if name_lower not in seen_lower:
                seen_lower.add(name_lower)
                unique_names.append(name_lower)

    if all(len(names) == 0 for names in source_names.values()):
        return [{"Name": "No results found across any source."}], [{"name": "Name", "id": "Name"}], messages

    rows = []
    for name in unique_names:
        name_lower = name.lower()
        is_query = name_lower == query_lower
        display_name = name[0].upper() + name[1:]
        
        row_dict = {"Name": display_name}
        count = 0
        
        for src in selected_sources:
            label = source_labels[src]
            if (is_query and len(source_names.get(src, set())) > 0) or name_lower in source_names.get(src, set()):
                row_dict[label] = "✓"
                count += 1
            else:
                row_dict[label] = ""

        row_dict["_count"] = count
        row_dict["_is_query"] = is_query
        rows.append(row_dict)

    rows.sort(key=lambda r: (not r.pop("_is_query"), -r.pop("_count")))

    # Dash datatables require explicit column definitions
    columns = [{"name": "Name", "id": "Name"}] + [{"name": l, "id": l} for l in selected_labels]

    return rows, columns, messages

if __name__ == "__main__":
    app.run(debug=True)