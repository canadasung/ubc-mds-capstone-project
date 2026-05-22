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

## The search() Function
The search() function is the starting point for finding species names. Its primary job is to take a text string (like "Amanita muscaria") and ask the GBIF database to find an exact, authoritative match for it.

Here is a step-by-step breakdown of exactly how it works:

1. The Request (Asking the Database)
The function sends a web request to GBIF's official matching service. When it asks for the data, it provides two strict instructions:

- name: The scientific string you are searching for.

- strict: Set to true. This tells the database not to guess. If a name is misspelled, we want the database to safely return "Not Found" rather than guessing and accidentally returning data for the wrong species. This guarantees that our data remains highly accurate. We also have implemented fuzzy-matching mechanism in case a user inputs a typo. Please see the log for fuzzy_search.py for more information.

2. The Raw Response (Receiving the Data)
If the exact name exists in history, GBIF sends back a digital package (a JSON dictionary) containing the official, raw metadata about that specific name. This includes the accepted taxonomic name, the author who published it, its unique GBIF ID key, and its status flag as "ACCEPTED" or "SYNONYM". If the searched name is a synonym, it also provides an acceptedUsageKey.

Example of search() Output using Accepted Name (Raw):
```json
{
   "usageKey":8168319,
   "scientificName":"Amanita muscaria (L.) Lam.",
   "canonicalName":"Amanita muscaria",
   "rank":"SPECIES",
   "status":"ACCEPTED",
   "confidence":98,
   "matchType":"EXACT",
   "kingdom":"Fungi",
   "phylum":"Basidiomycota",
   "order":"Agaricales",
   "family":"Amanitaceae",
   "genus":"Amanita",
   "species":"Amanita muscaria",
   "kingdomKey":5,
   "phylumKey":34,
   "classKey":186,
   "orderKey":1499,
   "familyKey":4171,
   "genusKey":6005964,
   "speciesKey":8168319,
   "class":"Agaricomycetes"
}
```

Example of search() Output using Synonym Name (Raw):
```json
{
   "usageKey":5452473,
   "acceptedUsageKey":8168319,
   "scientificName":"Amanita muscaria var. vulgaris Alb. & Schwein.",
   "canonicalName":"Amanita muscaria vulgaris",
   "rank":"VARIETY",
   "status":"SYNONYM",
   "confidence":99,
   "matchType":"EXACT",
   "kingdom":"Fungi",
   "phylum":"Basidiomycota",
   "order":"Agaricales",
   "family":"Amanitaceae",
   "genus":"Amanita",
   "species":"Amanita muscaria",
   "kingdomKey":5,
   "phylumKey":34,
   "classKey":186,
   "orderKey":1499,
   "familyKey":4171,
   "genusKey":6005964,
   "speciesKey":8168319,
   "class":"Agaricomycetes"
}
```

## Internal Helper: _resolve_usage_key()
This helpfer function retrieves the universally accepted usage key (if acceptedUsageKey variable appears, example shown above), the official numeric ID of the accepted name, for a given species string from the search() function json result. This is a prerequisite step before querying for synonyms.

## The synonyms() Function
Purpose: Retrieves the complete historical list of alternate names (synonyms) for a given species. The returned result(s) doesn't include the accepted name but only the accepted name's synonyms.

Execution Flow:

1. Name Match: The function first search the queried name and return raw json result (see example above in the search() seciton).

2. Key Resolution: The function invokes the internal _resolve_usage_key() helper to identify whether the searched name is an accepted name or synonym. This step guarantees that regardless of what name the user typed, the function obtains the exact numeric identifier for the accepted species.

3. Data Retrieval: Using that accepted usage key, the function queries the GBIF /species/{key}/synonyms endpoint to download the raw synonym data.

Example of partial synonym result from GBIF synonym endpoint:
```json
{
   "offset":0,
   "limit":500,
   "endOfRecords":true,
   "results":[
      {
         "key":5455639,
         "nubKey":5455639,
         "nameKey":304921,
         "taxonID":"gbif:5455639",
         "sourceTaxonKey":176053019,
         "kingdom":"Fungi",
         "phylum":"Basidiomycota",
         "order":"Agaricales",
         "family":"Amanitaceae",
         "genus":"Amanita",
         "species":"Amanita muscaria",
         "kingdomKey":5,
         "phylumKey":34,
         "classKey":186,
         "orderKey":1499,
         "familyKey":4171,
         "genusKey":6005964,
         "speciesKey":8168319,
         "datasetKey":"d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",
         "constituentKey":"7ddf754f-d193-4cc9-b351-99906754a03b",
         "parentKey":6005964,
         "parent":"Amanita",
         "acceptedKey":8168319,
         "accepted":"Amanita muscaria (L.) Lam.",
         "scientificName":"Agaricus aureolus Kalchbr.",
         "canonicalName":"Agaricus aureolus",
         "authorship":"Kalchbr.",
         "nameType":"SCIENTIFIC",
         "rank":"SPECIES",
         "origin":"SOURCE",
         "taxonomicStatus":"SYNONYM",
         "nomenclaturalStatus":[
            
         ],
         "remarks":"",
         "publishedIn":"(1873). Icon. Sel. Hymenomyc. Hung. (Budapest) 1: 9.",
         "numDescendants":0,
         "lastCrawled":"2023-08-22T23:20:59.545+00:00",
         "lastInterpreted":"2023-08-22T23:00:38.245+00:00",
         "issues":[
            
         ],
         "class":"Agaricomycetes"
      },
      ...
    ]
}
```

4. Output: Returns a clean, normalized list of dictionaries containing the canonicalName, author, date (if available), publishedIn, and source url for every known synonym.

Example Output:
```json
[
  {
    "canonicalName": "Amanita muscaria",
    "author": "(L.) Lam.",
    "date": "1783",
    "publishedIn": "Encycl. Méth. Bot. 1(1): 111",
    "url": "https://www.gbif.org/species/8168319"
  },
  {
    "canonicalName": "Agaricus muscarius",
    "author": "L.",
    "date": "1753",
    "publishedIn": "Sp. pl. 2: 1172",
    "url": "https://www.gbif.org/species/5240296"
  },
  {
    "canonicalName": "Amanitaria muscaria",
    "author": "(L.) E.-J. Gilbert",
    "date": "1940",
    "publishedIn": "Icon. Mycol. 27(Suppl. 1): 76",
    "url": "https://www.gbif.org/species/5453472"
  },
  {
    "canonicalName": "Venenarius muscarius",
    "author": "(L.) Earle",
    "date": "1909",
    "publishedIn": "Bull. N.Y. Bot. Gard. 5: 450",
    "url": "https://www.gbif.org/species/5240297"
  }
]
```

## The occurrences() Function
Purpose: Retrieves physical occurrence records (such as museum specimens and field observations) for a specified scientific name directly from the GBIF database.

Execution Flow:

1. Data Retrieval: Queries the GBIF /occurrence/search endpoint using the provided scientific name and record limit.

2. Data Standardization: Parses the raw JSON response to extract specific observation details. It maps GBIF's internal data fields strictly to standard Darwin Core terms (e.g., mapping location data to decimalLatitude and decimalLongitude, and observation dates to eventDate).

3. Image Extraction: Scans the media objects attached to each GBIF occurrence record. It extracts up to three valid image URLs per record and stores them in a custom top_3_images array.

Output: Returns a standardized list of dictionaries, where each dictionary contains the spatial, temporal, and media data for a single physical occurrence.