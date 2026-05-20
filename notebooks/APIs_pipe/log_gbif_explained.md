# gbif.py

## Overview

##### Scope of Information
The gbif.py module is designed to extract two distinct types of biological data from the Global Biodiversity Information Facility (GBIF) API:

1. Taxonomic Nomenclature (The Dictionary): It retrieves the official accepted species name, the scientist who named it, the publication year, and all historical synonyms associated with that species.

2. Physical Occurrences (The Museum Records): It retrieves records of physical sightings or collected specimens (e.g., GPS coordinates, observation dates, and field photos).

Understanding Darwin Core (DwC)
When this script retrieves physical occurrence records, it formats them using Darwin Core. Darwin Core is not a database, an API, or a piece of software. It is a universal data standard (essentially a standardized spreadsheet template) agreed upon by biologists globally. By ensuring our script pulls specific Darwin Core fields—like scientificName, eventDate, and occurrenceID, we guarantee that our data will perfectly match records pulled from other museums and databases later in the project.

Role in the Project Architecture
In this project, gbif.py acts as a Connector Module for the broader SpeciesAggregator pipeline (For the detail of SpeciesAggregator, please see SpeciesAggregator log file).

- The SpeciesAggregator pipeline is the master backend engine. Its job is to gather data from a dozen different biological databases (like Tropicos, Index Fungorum, and various Symbiota portals) at the exact same time.

- As a "connector module," gbif.py is simply the dedicated translator for GBIF. When the master pipeline says, "Go get me everything you have on Amanita muscaria," this script knows exactly how to format the URL, ask the GBIF API, clean up the response, and hand it back to the master pipeline in a standardized format.


##### Output Formatting
When the search() function successfully retrieves data from GBIF, it normalizes the raw API response into a clean list of dictionaries. Every dictionary in the returned list represents one recognized name (either the accepted species name or a synonym) and contains its specific metadata.

Dictionary Structure:

- name: The scientific string of the species or synonym.

- author: The scientist(s) who published the name.

- key: The unique GBIF identifier for that specific name.

- status: Indicates whether the name is "ACCEPTED" or a "SYNONYM".

Example Output (Cleaned):
```json
[
    {"name": "Amanita muscaria", "author": "(L.) Lam.", "key": 8168319, "status": "ACCEPTED"},
    {"name": "Agaricus muscarius", "author": "L.", "key": 5240296, "status": "SYNONYM"}
]
```

##### Synonym Resolution Logic
One of the most important features of this module is how it handles searches for alternate names.

If a user searches for a synonym that has a modern accepted name (e.g., searching for the less common or outdated Agaricus muscarius), the GBIF API will flag it as a "SYNONYM" and provide an acceptedUsageKey that points to the modern, accepted name (Amanita muscaria).

The algorithm then uses the key for the accepted name to get the full list of synonyms. This guarantees that the rest of your application is always working with the complete and up-to-date taxonomic framework, regardless of which historical name the user typed into the search bar.

## The search() Function
The search() function is the starting point for finding species names. Its primary job is to take a text string (like "Amanita muscaria") and ask the GBIF database to find an exact, authoritative match for it.

Here is a step-by-step breakdown of exactly how it works:

1. The Request (Asking the Database)
The function sends a web request to GBIF's official matching service. When it asks for the data, it provides two strict instructions:

- name: The scientific string you are searching for.

- strict: Set to true. This tells the database not to guess. If a name is misspelled, we want the database to safely return "Not Found" rather than guessing and accidentally returning data for the wrong species. This guarantees that our data remains highly accurate. We also have implemented fuzzy-matching mechanism in case a user inputs a typo. Please see the log for fuzzy_search.py for more information.

2. The Raw Response (Receiving the Data)
If the exact name exists in history, GBIF sends back a digital package (a JSON dictionary) containing the official, raw metadata about that specific name. This includes the accepted taxonomic name, the author who published it, its unique GBIF ID key, and its status (whether it is currently an accepted species or an older synonym).

Example Output (Raw):
```json
{
  "usageKey": 3328328,
  "scientificName": "Amanita muscaria (L.) Lam.",
  "canonicalName": "Amanita muscaria",
  "rank": "SPECIES",
  "status": "ACCEPTED",
  "confidence": 99,
  "matchType": "EXACT",
  "kingdom": "Fungi",
  "phylum": "Basidiomycota",
  "class": "Agaricomycetes",
  "order": "Agaricales",
  "family": "Amanitaceae",
  "genus": "Amanita",
  "species": "Amanita muscaria",
  "kingdomKey": 5,
  "phylumKey": 34,
  "classKey": 186,
  "orderKey": 1499,
  "familyKey": 4171,
  "genusKey": 2526057,
  "speciesKey": 3328328,
  "synonym": false
}
```

3. Processing and Handoff
Once this raw metadata is received, the function does not just blindly pass it along. Instead, it processes the data using the Synonym Resolution Logic described above.

If the metadata says the name is a synonym, the function automatically queries the database a second time using the modern accepted key.

Finally, it cleans up the raw response and hands it off as the standardized List of Dictionaries (described in the Output Formatting section), ready to be used by the rest of the application.


## Internal Helper: _resolve_usage_key()
Purpose: Retrieves the universally accepted usage key (the official numeric ID of the accepted name) for a given species string. This is a prerequisite step before querying for historical synonyms.

Execution Flow:

1. Queries the GBIF /species/match endpoint with strict=true.

2. Validates the matchType. If the match is not exactly "EXACT", it aborts and returns None.

3. Evaluates the taxonomic status of the returned record:

  - If "ACCEPTED", it returns the standard usageKey.

  - If "SYNONYM", it pivots and returns the acceptedUsageKey instead.

Pivot Rationale: It is critical to pivot to the acceptedUsageKey when a user searches for a common/fringe/outdated synonym term. GBIF's synonym lookup endpoint is strictly one-way: the input parameter must be the ID of the accepted name to successfully retrieve the complete list of related synonyms.

## The synonyms() Function
Purpose: Retrieves the complete historical list of alternate names (synonyms) for a given species.

Execution Flow:

1. Key Resolution (The Hidden Call): The function first invokes the internal _resolve_usage_key() helper. This crucial step guarantees that regardless of what name the user typed, the function obtains the exact numeric identifier for the modern, accepted species.

2. Data Retrieval: Using that accepted usage key, the function queries the GBIF /species/{key}/synonyms endpoint to download the raw historical naming data.

3. Data Standardization: It iterates through the raw API response and extracts only the essential nomenclature details. It maps GBIF's internal keys (like authorship or taxonomicStatus) to the unified dictionary schema mandated by the SpeciesAPI contract.

Output: Returns a clean, normalized list of dictionaries containing the canonicalName, author, date (if available), publishedIn, and source url for every known synonym.

## The occurrences() Function
Purpose: Retrieves physical occurrence records (such as museum specimens and field observations) for a specified scientific name directly from the GBIF database.

Execution Flow:

1. Data Retrieval: Queries the GBIF /occurrence/search endpoint using the provided scientific name and record limit.

2. Data Standardization: Parses the raw JSON response to extract specific observation details. It maps GBIF's internal data fields strictly to standard Darwin Core terms (e.g., mapping location data to decimalLatitude and decimalLongitude, and observation dates to eventDate).

3. Image Extraction: Scans the media objects attached to each GBIF occurrence record. It extracts up to three valid image URLs per record and stores them in a custom top_3_images array.

Output: Returns a standardized list of dictionaries, where each dictionary contains the spatial, temporal, and media data for a single physical occurrence.