"""
app_shiny.py
To run: shiny run app_shiny.py --reload
"""
import json
import sys
from pathlib import Path
import pandas as pd
from shiny import App, render, ui, reactive

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.APIs.call_APIs import call_apis

source_labels = {
    "gbif": "GBIF",
    "genbank": "GenBank",
    "mushroomobs": "Mushroom Observer",
}

# 1. UI Definition
app_ui = ui.page_fluid(
    ui.h2("Species Name Synonym Search"),
    ui.input_text("query", "Enter a species name", placeholder="e.g. Amanita muscaria", width="400px"),
    ui.accordion(
        ui.accordion_panel(
            "Advanced filters",
            ui.input_checkbox_group(
                "sources",
                "Sources to query",
                choices=source_labels,
                selected=list(source_labels.keys()),
            )
        )
    ),
    ui.output_ui("messages"),
    ui.output_data_frame("results_table")
)

# 2. Server Logic
def server(input, output, session):
    
    # Reactive calculation: runs only when input.query or input.sources changes
    @reactive.Calc
    def fetch_data():
        query = input.query()
        selected_sources = list(input.sources())
        
        if not query:
            return None, None
        if not selected_sources:
            return "warning", "Select at least one source to query."

        raw = call_apis(query, sources=selected_sources)
        results = json.loads(raw)
        return "success", results

    @output
    @render.ui
    def messages():
        status, data = fetch_data()
        if status == "warning":
            return ui.div(data, style="color: orange;")
            
        if status == "success" and data:
            errors = []
            for source, label in source_labels.items():
                val = data.get(source, {})
                if isinstance(val, str):
                    errors.append(ui.div(f"{label}: {val}", style="color: red;"))
            return ui.TagList(*errors)
        return ui.div()

    @output
    @render.data_frame
    def results_table():
        status, data = fetch_data()
        if status != "success" or not data:
            return pd.DataFrame()

        query = input.query()
        selected_sources = list(input.sources())
        selected_labels = [source_labels[s] for s in selected_sources]

        source_names = {
            source: {n.lower() for n in data[source].keys()}
            for source in selected_sources
            if isinstance(data.get(source), dict)
        }

        query_lower = query.lower()
        seen_lower: set[str] = {query_lower}
        unique_names: list[str] = [query]
        
        for src_set in source_names.values():
            for name_lower in src_set:
                if name_lower not in seen_lower:
                    seen_lower.add(name_lower)
                    unique_names.append(name_lower)

        if all(len(names) == 0 for names in source_names.values()):
            return pd.DataFrame([{"Name": "No results found across any source."}])

        rows = []
        for name in unique_names:
            name_lower = name.lower()
            is_query = name_lower == query_lower
            display_name = name[0].upper() + name[1:]
            
            checks = {
                label: (
                    "✓" if (is_query and len(source_names.get(src, set())) > 0)
                    else "✓" if name_lower in source_names.get(src, set())
                    else ""
                )
                for src, label in source_labels.items()
                if label in selected_labels
            }
            count = sum(1 for v in checks.values() if v)
            rows.append({
                "Name": display_name,
                **checks,
                "_count": count,
                "_is_query": is_query,
            })

        rows.sort(key=lambda r: (not r.pop("_is_query"), -r.pop("_count")))
        df = pd.DataFrame(rows)

        # Apply the exact same Pandas styling used in the Streamlit app
        # def bold_query_row(row):
        #     style = "font-weight: bold" if row.name == 0 else ""
        #     return [style] * len(row)

        # return render.DataGrid(df.style.apply(bold_query_row, axis=1), width="100%")
        return render.DataGrid(df, width="100%")

app = App(app_ui, server)