# gbif.py

## Overview

##### Scope of Information
Extracts both synonyms and physical occurrence records (using the Darwin Core fields). It acts as a comprehensive client for your SpeciesAggregator pipeline.

##### Output Formatting
Returns a list of dictionaries. This is highly structured and matches your SynonymEngine wrapper.

Python
```
[{"canonicalName": "Amanita muscaria"}, {"canonicalName": "Agaricus muscarius"}]
```

If a user searches for an outdated synonym (e.g., Agaricus muscarius), GBIF returns an acceptedUsageKey pointing to the modern accepted name (Amanita muscaria). It correctly detects this and pivots to the accepted key to grab the full list of synonyms.

## search()
The search function acts as the foundational taxonomic lookup for your pipeline. Its primary job is to take a string name (like "Amanita muscaria") and ask the GBIF backbone taxonomy to find an exact, authoritative match for it.

Here is a breakdown of exactly what it does:

1. The Request
It sends an HTTP GET request to GBIF's /species/match endpoint. It passes two parameters:

- name: The scientific string you are searching for.

- "strict": "true": This tells GBIF not to guess. It forces GBIF to only return high-confidence, exact matches rather than loosely fuzzy-matching misspellings (which your separate fuzzy_search.py handles later if needed).

2. The Output
It returns a structured JSON dictionary containing GBIF's official metadata about that name. This dictionary includes:

- Taxonomic lineage: The kingdom, phylum, class, etc., that the species belongs to (which is exactly what your TaxonRouter uses to decide which databases to query).

- Match status: Whether the name is currently "ACCEPTED" or if it is considered a "SYNONYM" of a different name.

- Usage Keys: The unique numeric IDs GBIF assigns to taxa (e.g., usageKey and acceptedUsageKey).

Why is it important?
In your pipeline, you can't just ask GBIF for "synonyms of Amanita muscaria" using the string name. GBIF's synonym API requires a numeric ID. The search function is the critical first step that converts a user's text input into the numeric usageKey that the rest of your GBIFAPI class (specifically the synonyms method) relies on to do its job.

==========================================

If you were to pass the name "Amanita muscaria" (the currently accepted scientific name) into the search function, GBIF would return a JSON dictionary that looks like this:

JSON
```
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
Why this is so useful for your pipeline:
1. Taxonomy Routing (kingdom, phylum, class): Notice the "kingdom": "Fungi". Your TaxonRouter takes this exact dictionary, reads that key, and realizes, "Ah, this is a fungus! I should query Index Fungorum and MyCoPortal, and skip the plant databases."

2. Canonical Name: It separates the clean "canonicalName": "Amanita muscaria" from the messy "scientificName": "Amanita muscaria (L.) Lam." (which includes the author citation).

==========================================

Example 2: Searching for an outdated synonym
If a user searches for an old, outdated name like "Agaricus muscarius", the GBIF output changes slightly. This is where your first gbif.py file shines:

JSON
```
{
  "usageKey": 5240296,
  "acceptedUsageKey": 3328328,
  "scientificName": "Agaricus muscarius L.",
  "canonicalName": "Agaricus muscarius",
  "rank": "SPECIES",
  "status": "SYNONYM",
  "confidence": 99,
  "matchType": "EXACT",
  "kingdom": "Fungi",
  "synonym": true,
  ...
}
```
Notice the presence of the acceptedUsageKey field here.

Because status is "SYNONYM", GBIF is saying: "I recognize this name, but its ID is 5240296, and the accepted modern ID is actually 3328328."

In your first gbif.py file, the _resolve_usage_key() helper method actively looks for this acceptedUsageKey. If it finds it, it safely pivots your pipeline to use the modern, correct ID (3328328) for all subsequent synonym and occurrence lookups!

==========================================

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

Python
```
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