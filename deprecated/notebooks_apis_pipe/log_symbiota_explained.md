# symbiota.py

## Overview

##### Architecture & Scope

symbiota.py is a generalized, object-oriented pipeline component. It inherits from the SpeciesAPI base class, meaning it follows a strict contract (search, synonyms, occurrences). Furthermore, it is not hardcoded to one website; it takes a base_url upon initialization so it can query any Symbiota portal (Lichen Portal, SERNEC, CCH2, etc.).

##### Information Target

symbiota.py is designed to fetch both basic taxonomic data and physical occurrence records. It has a dedicated occurrences() method to pull down lists of specimen data.

##### Synonyms
Because the official Symbiota API lacks a dedicated endpoint for synonyms, the synonyms() method cannot simply request a clean data payload through API search. While no standardized API is available, many Symbiota websites do publish synonyms. They are extracted using three-step HTML web scraping workaround as follows:

1. Identifier Lookup (_get_tid): It first queries the portal's hidden internal autocomplete script, ("/rpc/gettaxasuggest.php"), to quickly find the internal database numeric identifier (Taxon ID) for the user's string.
    - Note: RPC stands for Remote Procedure Call. This is a Symbiota defined hidden method build for internal database search but not for public API. This is accessible by the HTML scraping method because it's the mechanism of a user's browser searching a .php file.

2. Modernization Check (_resolve_accepted_tid): It uses the Symbiota v2 API ("/api/v2/taxonomy/{identifier}") to check if that Taxon ID belongs to a modern accepted name or an synonym. If it is an synonym, it automatically pivots to the modern ID.

3. Web Page Scraping (_scrape_synonyms): Finally, it downloads the raw HTML webpage for that species and uses Regular Expressions `re.search(r'id="synonymDiv"...)` to manually extract synonym names out of the HTML `<i>` tags.

Safety Mechanism: Because web scraping is fragile, the entire synonyms() method is wrapped in a protective try/except block. If the portal administrators ever redesign their website layout and break the scraper, the function will quietly fail and return an empty list ([]) to prevent the main pipeline from crashing.


##### Output Formatting

symbiota.py returns standardized lists, JSON dictionaries, or parsed XML trees, which are easily ingested by downstream aggregator pipelines.

## Initialization & Core Helpers
### __init__()
This constructor method initializes the class instance. Because Symbiota is a decentralized software framework powering numerous independent databases (e.g., MyCoPortal, SERNEC, Lichen Portal), the client must be anchored to a specific endpoint. By accepting the base_url as a dynamic parameter, the application can instantiate multiple portal-specific client objects from this single class definition.

### _get()
Helper function for requests.get(...). This function attaches a fake Web Browser header ("User-Agent": "Mozilla/5.0") to trick Symbiota firewalls into thinking a human is visiting to prevent the API calls from being blocked.

## Official API Endpoints
### search()
This asks the portal's taxasearch.php page if it recognizes a name. Symbiota servers are notoriously buggy and will sometimes reply with modern JSON data, and other times with old XML data. This function tries to read it as JSON first, and if that fails, safely parses it as an XML tree.

### occurrences()
This is the data-gatherer. It asks the occurrences/search.php page for a list of physical specimen records. It has heavy "defensive programming" built in: if a Symbiota portal crashes and returns a raw HTML error page (which happens frequently), this function detects the `<html` tag and safely returns an empty list [] so your Streamlit app doesn't crash.


## Custom Synonym Scraper
### _get_tid(self, species_name: str) (Step 1)
This method utilizes the portal's internal autocomplete endpoint (/rpc/gettaxasuggest.php). It accepts a species name string and returns the corresponding internal database identifier (tid). This identifier is required to access the species profile page.

### _resolve_accepted_tid(self, tid: int) (Step 2)
This method verifies the taxonomic status of the provided tid. If the identifier corresponds to a synonym, the profile page will not display the full synonym list. In such cases, this function automatically resolves and returns the tid of the currently accepted name to ensure accurate web scraping.

### _scrape_synonyms(self, accepted_tid: int) (Step 3)
This method executes the HTML extraction. It downloads the source code of the accepted species profile page and applies regular expressions (re.search) to locate the `<div id="synonymDiv">` container. It extracts the taxonomic names contained within the `<i>` tags, actively filtering out infraspecific ranks (subspecies or varieties).

Example scraped synonym output for "Trametes versicolor" with tid=189955:
```json
[
  {
    "canonicalName": "Coriolus versicolor",
    "author": "(L.) Quél.",
    "date": "",
    "publishedIn": "",
    "url": "https://mycoportal.org/portal/taxa/index.php?taxon=189955"
  },
  {
    "canonicalName": "Polyporus versicolor",
    "author": "(L.) Fr.",
    "date": "",
    "publishedIn": "",
    "url": "https://mycoportal.org/portal/taxa/index.php?taxon=189955"
  }
]
```

### synonyms(self, name: str) (The Orchestrator)
This is the public-facing method called by the aggregator pipeline. It orchestrates the synonym retrieval process through the following sequential steps:

1. Capitalizes the input name.

2. Retrieves the initial tid.

3. Resolves the tid to the accepted name.

4. Scrapes the HTML profile page.

5. Formats the extracted names into a standardized list of dictionaries.

All five steps are wrapped in a try/except block. In the event that a website changes its HTML layout, the function will silently fail and return an empty list.

Example of the final output from synonyms() when search for "Trametes versicolor" with tid=189955:
```json
[
  {
    "canonicalName": "Trametes versicolor",
    "author": "",
    "date": "",
    "publishedIn": "",
    "url": "https://mycoportal.org/portal/taxa/index.php?taxon=189955"
  },
  {
    "canonicalName": "Coriolus versicolor",
    "author": "(L.) Quél.",
    "date": "",
    "publishedIn": "",
    "url": "https://mycoportal.org/portal/taxa/index.php?taxon=189955"
  },
  {
    "canonicalName": "Polyporus versicolor",
    "author": "(L.) Fr.",
    "date": "",
    "publishedIn": "",
    "url": "https://mycoportal.org/portal/taxa/index.php?taxon=189955"
  }
]
```

### _scrape_occurrences_html()
Function to retrieve Physical Specimen Records via HTML scraping. Used as a fallback if a portal's API returns visual HTML instead of JSON.

- In-Memory Execution: Parses the html_text payload previously downloaded by the parent occurrences() method without initiating additional network requests.

- Table Identification: Locates specimen records by targeting DOM <table> elements with specific attributes (id="occTable", class="styledtable", or class="table").

- Dynamic Schema Generation: Extracts table headers (<th>) to dynamically establish dictionary keys, subsequently mapping the corresponding row values (<td>) to these headers to construct a standardized list of dictionaries.