# scripts/examples/demo_query.py
#
# This is a demo to show the search pipeline from the beginning (from user search
# query to showing all the parsed and processed results). This file can be used to
# quickly prototype and test app functionalities without creating a UI component.

import json
import os

from scripts.utils.aggregator import SpeciesAggregator

# Import the centralized client builder
from scripts.utils.call_apis_pipe import _make_clients

# Core pipeline
from scripts.utils.router import TaxonRouter
from scripts.utils.synonyms import SynonymEngine

# Search query string (should be normalised with utils/normalize_query_string.py)
# `strictness` decides which databases to use. Setting to False means query all
# databases, while setting to True just performs search on 'universal apis`
# The need for `strictness` should be discussed (i.e. what constitutes an api as
# "universal"?)
q_name = "Amanita muscaria"
strictness = False

# The "tidy" output of this demo
# This emulates what an app with a UI might display/showcase to the user
def print_showcase(official_syns, gbif_occs, symbiota_syns):
    """Prints a clear summary to the terminal mapping the data to UI requirements."""
    print("\n" + "=" * 60)
    print(" 🎉 DATA SHOWCASE FOR STREAMLIT FRONTEND TEAM 🎉")
    print("=" * 60)

    print("\n1. TAXONOMY & TIMELINE DATA (From synonyms_official.json)")
    if official_syns:
        example = official_syns[0]  # Grab the first record
        print(f"  - Official Name: {example.get('name')}")
        print(
            f"  - Trustworthiness Score: {example.get('confidence')} (1.0 = Exact, 0.9 = Synonym)"
        )
        print(f"  - Source API: {example.get('source')}")
        print(f"  - Source URL: {example.get('url')}")

        # Find one with an author/date to show off
        historical = next((s for s in official_syns if s.get("author")), None)
        if historical:
            print(
                f"  - Historical Timeline Example: {historical.get('name')} by {historical.get('author')} in {historical.get('publishedIn')}"
            )

    print("\n2. UN-OFFICIAL LOCAL SYNONYMS (From synonyms_symbiota.json)")
    if "symbiota_mycoportal" in symbiota_syns and symbiota_syns["symbiota_mycoportal"]:
        print(
            f"  - MyCoPortal scraped {len(symbiota_syns['symbiota_mycoportal'])} local/historical names!"
        )
        print(
            f"  - Example: {symbiota_syns['symbiota_mycoportal'][-1].get('canonicalName')} {symbiota_syns['symbiota_mycoportal'][-1].get('author')}"
        )

    print("\n3. OCCURRENCE & IMAGE DATA (From occurrences_gbif.json)")
    if gbif_occs:
        # Find a record that successfully grabbed images
        img_record = next((o for o in gbif_occs if o.get("top_3_images")), None)
        print(f"  - Total Occurrences Pulled: {len(gbif_occs)}")
        if img_record:
            print(f"  - Top 3 Images Array: {img_record.get('top_3_images')}")
            print(f"  - Specimen Link: {img_record.get('occurrenceID', 'N/A')}")
            print(
                f"  - Geolocation: Lat {img_record.get('decimalLatitude')}, Lon {img_record.get('decimalLongitude')}"
            )

    print("\n4. RESILIENCE & WARNINGS")
    print(
        "  - If an API crashed during this run, you saw a specific yellow/red terminal warning above."
    )
    print(
        "  - Notice how the script DID NOT CRASH. It output safe empty lists [] to the JSON files."
    )
    print("=" * 60 + "\n")

# Main demo loop
# 1. First initialise all clients
# 2. Run the queries
# 3. Collect the results
# 4. Pass results to print_showcase() for tidy output
def run_demo():
    print("Initializing clients...")
    clients = _make_clients()

    # Extract the independent taxonomy backbones needed for the SynonymEngine
    gbif = clients.get("gbif")
    tropicos = clients.get("tropicos")
    index_fungorum = clients.get("index_fungorum")
    col = clients.get("col")

    # Build the engines
    print("Building engines...")
    router = TaxonRouter(gbif)
    syn_engine = SynonymEngine(gbif, tropicos, index_fungorum, col)
    agg = SpeciesAggregator(clients=clients, router=router)

    # Choose a query that spans both taxonomy and occurrence systems
    query_name = q_name
    print(f"\n--- Running Pipeline for: {query_name} ---")

    # 1. Route the query to determine appropriate databases
    print("Routing query...")
    selected_apis = router.route(query_name, strict=strictness)
    print(f"Databases selected: {selected_apis}")

    # 2. Get Synonyms (Returns the new rich dictionaries with metadata)
    print("Fetching synonyms and metadata...")
    synonyms_data = syn_engine.get_synonyms(query_name)

    # Extract just the string names to pass into the aggregator
    synonym_strings = []
    seen = {query_name.lower()}
    for s in synonyms_data:
        nm = s.get("name")
        if nm and nm.lower() not in seen:
            seen.add(nm.lower())
            synonym_strings.append(nm)

    # Fetch Unofficial Synonyms from Symbiota Portals ---
    print("Scraping unofficial synonyms from Symbiota portals...")
    symbiota_synonyms_data = {}
    for key in selected_apis:
        if key.startswith("symbiota_"):
            client = clients.get(key)
            if client and hasattr(client, "synonyms"):
                try:
                    s_syns = client.synonyms(query_name)
                    if s_syns:
                        symbiota_synonyms_data[key] = s_syns
                except Exception as e:
                    symbiota_synonyms_data[key] = [{"error": f"Scrape failed: {e}"}]

    # Fetch Synonyms from Independent Portals ---
    print("Fetching synonyms from independent portals...")
    independent_synonyms_data = {}

    # We ignore backbones (handled by the Engine) and Symbiota (handled above)
    backbones = ["gbif", "col", "tropicos", "index_fungorum"]

    # DYNAMIC LOGIC: Only query independent APIs that the Router explicitly selected!
    for key in selected_apis:
        if key not in backbones and not key.startswith("symbiota_"):
            client = clients.get(key)
            if client and hasattr(client, "synonyms"):
                try:
                    ind_syns = client.synonyms(query_name)
                    if ind_syns:
                        independent_synonyms_data[key] = ind_syns
                except Exception as e:
                    independent_synonyms_data[key] = [{"error": f"Failed: {e}"}]

    # 3. Get Occurrences
    print("Fetching occurrences and images...")
    occurrences_data = agg.occurrences(
        name=query_name, synonyms=synonym_strings, apis=selected_apis, limit=5
    )

    # 4. Save the results for the team to review
    print("\nWriting results to JSON files...")
    os.makedirs("notebooks/APIs_pipe/demo_results", exist_ok=True)

    # Save Official Synonyms
    with open(
        "notebooks/APIs_pipe/demo_results/synonyms_official.json", "w", encoding="utf-8"
    ) as f:
        json.dump(synonyms_data, f, indent=2)

    # Save Symbiota Synonyms
    with open(
        "notebooks/APIs_pipe/demo_results/synonyms_symbiota.json", "w", encoding="utf-8"
    ) as f:
        json.dump(symbiota_synonyms_data, f, indent=2)

    # Save Independent/Other API Synonyms
    with open(
        "notebooks/APIs_pipe/demo_results/synonyms_independent.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(independent_synonyms_data, f, indent=2)

    # Save GBIF Occurrences
    if "gbif" in occurrences_data:
        with open(
            "notebooks/APIs_pipe/demo_results/occurrences_gbif.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(occurrences_data["gbif"], f, indent=2)

    # Save Symbiota Occurrences
    symbiota_results = {
        k: v for k, v in occurrences_data.items() if k.startswith("symbiota_")
    }
    with open(
        "notebooks/APIs_pipe/demo_results/occurrences_symbiota.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(symbiota_results, f, indent=2)

    # Save Independent/Other API Occurrences
    independent_results = {
        k: v
        for k, v in occurrences_data.items()
        if k != "gbif" and not k.startswith("symbiota_")
    }
    with open(
        "notebooks/APIs_pipe/demo_results/occurrences_independent.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(independent_results, f, indent=2)

    print_showcase(
        synonyms_data,
        occurrences_data.get("gbif", {}).get("data", []),
        symbiota_synonyms_data,
    )

    print(
        "Success! Check the 'notebooks/APIs_pipe/demo_results/' folder to see the new data structures."
    )

# The main function
if __name__ == "__main__":
    run_demo()
