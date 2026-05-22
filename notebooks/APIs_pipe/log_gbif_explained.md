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

