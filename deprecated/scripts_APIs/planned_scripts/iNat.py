import requests
import pandas as pd

INAT_V2_BASE = "https://api.inaturalist.org/v2"

# ── 1. Headers (Method Override for v2) ────────────────────────────────────────
HEADERS = {
    "User-Agent": "BeatyMuseumCapstone/0.1 (DSCI591; contact=canadasung@gmail.com)",
    "X-HTTP-Method-Override": "GET",
    "Content-Type": "application/json"
}

# ── 2. Search Criteria (No Geographic Filters) ─────────────────────────────────
# Notice there is no lat, lng, radius, or place_id. 
# This automatically triggers a global search.
search_params = {
    "taxon_name": "Aureonarius armiae", 
    "quality_grade": "research",
    "per_page": 20
}

# ── 3. Fields Payload ──────────────────────────────────────────────────────────
payload = {
    "fields": {
        "id": True,             # Observation ID: url as /observations/id_value
        "uuid": True,           # Hexa code
        "observed_on": True,
        "location": True,       # The API will still return coordinates if they exist
        "place_guess": True,    # The text description of where it was found
        "species_guess": True,
        "tags": True,
        "locale": True,
        "outlinks": {
            "source": True,
            "url": True
        },
        "taxon": {
            "id": True,                       # Taxon ID
            "parent_id": True,
            "name": True,                     # Taxon name
            "iconic_taxon_id": True,
            "iconic_taxon_name": True,
            "is_active": True,
            "native": True,
            "observations_count": True,
            "wikipedia_url": True
        },
        "user": {
            "id": True,                # user id
            "login": True              # user login name 
        }
    }
}

# payload = {
#     "fields": {
#         "id": True,
#         "observed_on": True,
#         "taxon": {
#             "name": True
#         },
#         # Request the photos
#         "observation_photos": {
#             "photo": {
#                 "url": True,
#                 "license_code": True # Good practice if you plan to display them
#             }
#         }
#     }
# }

# payload = {
#     "fields": "all"
# }



# ── 4. Execute Global Request ──────────────────────────────────────────────────
response = requests.post(
    f"{INAT_V2_BASE}/observations", 
    params=search_params, 
    headers=HEADERS, 
    json=payload
)
response.raise_for_status()
data = response.json()
data





# ── 5. Flatten to Pandas ───────────────────────────────────────────────────────
global_rows = []
for obs in data.get("results", []):
    global_rows.append({
        "inat_id": obs.get("id"),
        "observed_on": obs.get("observed_on"),
        "taxon_id": obs.get("taxon", {}).get("id"),
        "taxon_name": obs.get("taxon", {}).get("name"),
        "observer": obs.get("user", {}).get("login"),
        "location_name": obs.get("place_guess"),
        "raw_coordinates": obs.get("location") 
    })

df_global = pd.DataFrame(global_rows)

print(f"Total global records retrieved: {len(df_global)}\n")
print(df_global)