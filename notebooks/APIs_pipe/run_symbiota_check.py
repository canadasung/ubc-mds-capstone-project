"""
Quick manual check for SymbiotaAPI functions.

Run from the project root:
    python notebooks/APIs_pipe/run_symbiota_check.py

Edit PORTAL, SPECIES_NAME, and SYNONYM_NAME below to probe different portals.
"""

from scripts.APIs_pipe.symbiota import SymbiotaAPI

# ── Configuration ─────────────────────────────────────────────────────────────
PORTAL       = "https://bryophyteportal.org/portal"   # swap to "https://lichenportal.org/portal" etc.
SPECIES_NAME = "Sphagnum monzonense"                # swap accepted name and synonym to test resolve path
# ──────────────────────────────────────────────────────────────────────────────

api = SymbiotaAPI(PORTAL)
print(f"\n portal_name : {api.portal_name}")
print(f" base        : {api.base}")

# ------------------------------------------------------------------
print("\n── _empty_record() ──────────────────────────────────────────")
print(api._empty_record())

# ------------------------------------------------------------------
print("\n── _extract_taxonomy() (static test with known data) ────────")
sample_api_response = {
    "kingdomName": "Fungi",
    "classification": [
        {"rankid": 30,  "scientificName": "Ascomycota"},
        {"rankid": 60,  "scientificName": "Lecanoromycetes"},
        {"rankid": 140, "scientificName": "Cladoniaceae"},
    ],
}
print(api._extract_taxonomy(sample_api_response))

# ------------------------------------------------------------------
print(f"\n── search('{SPECIES_NAME}') ──────────────────────────────────")
result = api.search(SPECIES_NAME)
if result:
    results_list = result.get("results", [])
    print(f" Found {len(results_list)} result(s)")
    if results_list:
        print(f" First hit : {results_list[0]}")
else:
    print(" No result returned (portal unreachable or name not found)")

# ------------------------------------------------------------------
print(f"\n── _get_tid('{SPECIES_NAME}') ────────────────────────────────")
tid = api._get_tid(SPECIES_NAME)
print(f" tid : {tid}")

# ------------------------------------------------------------------
if tid:
    print(f"\n── _resolve_accepted_tid({tid}) ─────────────────────────────")
    accepted_tid, meta = api._resolve_accepted_tid(tid)
    print(f" accepted_tid : {accepted_tid}")
    for k, v in meta.items():
        print(f"   {k:<16} : {v}")

    # ------------------------------------------------------------------
    print(f"\n── _scrape_synonyms({accepted_tid}, taxonomy) ───────────────")
    taxonomy = {k: meta.get(k, "") for k in ["Kingdom", "Phylum", "Class", "Family", "Subfamily"]}
    syns = api._scrape_synonyms(accepted_tid, taxonomy)
    print(f" Scraped {len(syns)} synonym(s)")
    for s in syns[:3]:   # show first 3
        print(f"   {s['Genus']} {s['Species']}  |  tid={s['Source Species ID']}  |  author={s['Author']}")

# ------------------------------------------------------------------
print(f"\n── synonyms('{SPECIES_NAME}') — full DataFrame ───────────────")
df = api.synonyms(SPECIES_NAME)
print(f" Shape : {df.shape}")
print(df.to_string(index=False))
