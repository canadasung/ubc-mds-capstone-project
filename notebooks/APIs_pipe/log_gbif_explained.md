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


## _resolve_usage_key()

The _resolve_usage_key function acts as a smart filter to ensure your pipeline always uses the most accurate and up-to-date numeric ID (the "usage key") for a species, regardless of what the user typed in the search box.

Here is exactly how it works under the hood:

The Problem It Solves
When you search the GBIF database, it assigns a unique numeric ID to every single name it knows. However, not all names are equal.

- If a name is the current, scientifically accepted name, it just gets a standard usageKey.

- If a name is an old, outdated synonym, it gets a usageKey, but GBIF also attaches an acceptedUsageKey that points to the modern, correct species.

If you accidentally pass the ID of an outdated synonym into GBIF's synonym lookup endpoint later in your code, GBIF will get confused and return an empty list.

How The Function Works
The function takes the raw dictionary returned by the search() function and performs a simple check:


```python
    def _resolve_usage_key(self, match_data: dict) -> int:
        if "acceptedUsageKey" in match_data:
            return match_data["acceptedUsageKey"]
        return match_data["usageKey"]
```

1. The Synonym Scenario: It first looks for an "acceptedUsageKey". If a user typed an old name like "Agaricus muscarius", this key will exist. The function immediately grabs it and ignores the outdated usageKey.

2. The Accepted Name Scenario: If the user typed the perfectly correct modern name (like "Amanita muscaria"), there is no "acceptedUsageKey". The if statement fails, and it safely falls back to returning the standard "usageKey".

##### Why is it essential for your app?
By putting this helper function right before your .synonyms() method, you guarantee that your app acts like an expert taxonomist. It catches outdated user inputs, automatically pivots to the modern accepted taxonomy behind the scenes, and pulls the complete, correct list of synonyms every single time.

==========================================

## synonyms()

The synonyms() function is a standardized method defined in your SpeciesAPI base class. Its primary job is to take a single scientific string name (like "Amanita muscaria") and return a list of alternative names—such as historical classifications, misspellings, or related nomenclatural synonyms—recognized by that specific database.

Because every database is built differently, the actual internal logic of this function changes depending on which API client is running it.

Here is how it behaves across your different files:

1. The Two-Step APIs (GBIF, Tropicos, Catalogue of Life)
For highly structured relational databases, you cannot just ask for synonyms using a text string. The synonyms() method in these clients automatically performs a two-step process behind the scenes:

- It silently calls the search() method to convert your string text into a proprietary numeric ID (such as GBIF's usageKey or Tropicos's NameId).

- It then pings a dedicated synonyms endpoint using that specific ID to fetch the list of names.
(Note: If the search fails or returns a 404 error, the synonyms() function safely catches it and returns an empty list).

2. The Unsupported APIs (Symbiota, Mushroom Observer)
Some portals are built purely for occurrence observations and do not have endpoints dedicated to taxonomic synonymy. In clients like SymbiotaAPI, the synonyms() function is hardcoded to simply return an empty list []. This is a defensive programming tactic; it ensures that when your app loops through all clients, it doesn't crash when it hits a database that lacks this feature.

3. XML APIs (Index Fungorum)
Older databases like Index Fungorum return raw XML text rather than clean JSON. Its synonyms() method takes the name and returns an XML string that must be parsed downstream.

##### Why it is critical for your overall pipeline:
This function is the fuel for your SynonymEngine. When a user types a name into your Streamlit app, the engine calls .synonyms() on your authoritative taxonomic backbones (GBIF, Tropicos, COL, etc.) to gather all possible variations of that name.

By building this comprehensive master list of names first, your SpeciesAggregator can then cast a massive net across all the occurrence databases (like MyCoPortal or CCH2), ensuring you find physical records even if they were logged under an outdated scientific name 100 years ago!

==========================================

## occurrences()

The occurrences() function is the workhorse for finding real-world data in your pipeline. While the synonyms() function asks, "What other names does this species go by?", the occurrences() function asks, "Where and when has this species actually been seen, collected, or sequenced?"

Because your architecture is object-oriented, this function exists at three different levels, each doing a specific part of the job:

1. The Blueprint (base.py)
In your SpeciesAPI base class, occurrences() is defined as an abstract method. It enforces a strict rule: any database client you build must have a method that takes a scientific name and an optional limit, and it must return a list of occurrence dictionaries.

2. The Individual API Clients
Depending on which database you are querying, the occurrences() function behaves very differently:

- The Data Providers (gbif.py, symbiota.py, mushroomobs.py): In these files, the function actively sends a request to the database's occurrence endpoints. It asks for physical specimen records, citizen science observations, or image data, and parses the response into a usable list. For example, in mushroomobs.py, it specifically parses out the date, latitude, longitude, and image URLs.

- The Taxon-Only Databases (tropicos.py, col.py, index_fungorum.py): These databases are purely nomenclatural dictionaries; they don't store physical specimen data. Therefore, their occurrences() methods are hardcoded to simply return an empty list []. This safely tells the pipeline, "I have no physical data to give you."

3. The Master Orchestrator (aggregator.py)
This is where the real magic happens. In your SpeciesAggregator class, the occurrences() function acts as a massive net.

Instead of taking just one name, it takes the primary name and a list of all known synonyms. It then automatically iterates through every single active API client and asks them for records.

Python
```
# From your aggregator.py
def occurrences(self, name: str, synonyms: list, apis: list, limit: int = 20) -> dict:
```

- Error Handling: Because Symbiota portals are notorious for crashing or throwing 403 blocks, the aggregator's occurrences() function wraps every call in a try/except block. If the Lichen Portal goes offline, the function gracefully captures the error as a string and keeps querying the other databases so your app doesn't crash.

- The Output: It returns a massive master dictionary where the keys are the database names (e.g., "gbif", "mycoportal") and the values are the lists of physical records (or the error messages) it found.

##### How it powers your App
In your prototype_pipe.py Streamlit app, you don't actually display the raw occurrence data (like latitude/longitude). Instead, you use the occurrences() function as a proof of existence.

By setting the limit=3, the app quickly asks the aggregator to check if databases like GenBank or MyCoPortal have any records under a specific synonym. If occurrences() returns data, your app confidently draws a checkmark "✓" in that column!