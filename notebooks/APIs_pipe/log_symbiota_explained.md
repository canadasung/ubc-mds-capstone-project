# symbiota.py

## Overview

##### Architecture & Scope

symbiota.py is a generalized, object-oriented pipeline component. It inherits from your SpeciesAPI base class, meaning it follows a strict contract (search, synonyms, occurrences). Furthermore, it is not hardcoded to one website; it takes a base_url upon initialization so it can query any Symbiota portal (Lichen Portal, SERNEC, CCH2, etc.).

##### Information Target

symbiota.py is designed to fetch both basic taxonomic data and physical occurrence records. It has a dedicated occurrences() method to pull down lists of specimen data.

##### Synonyms

Because the official Symbiota REST API lacks a synonym feature, the synonyms() method in this file simply returns an empty list (return []). It relies entirely on official taxasearch.php and search.php endpoints for its other data.

To get around the lack of an official synonym API, this script uses a complex three-step hack:

1. It queries a hidden internal RPC endpoint (gettaxasuggest.php) just to get an internal Taxon ID (tid).

2. It uses a v2 API endpoint to see if that ID is an accepted name or an outdated synonym.

3. Finally, it performs web scraping. It downloads the raw HTML webpage for that species and uses Regular Expressions (re.search(r'id="synonymDiv"...) to manually extract synonym names out of the HTML <i> tags.

##### A Quick Word of Caution
Because this method relies on web scraping (re.search parsing HTML tags) and internal RPC files (gettaxasuggest.php), it is "brittle." If the developers of the Symbiota software decide to rename id="synonymDiv" to something else in a future update, this specific method will quietly break and return empty lists.

However, since you have gbif.py and col.py serving as your primary, highly stable taxonomic backbones, having this Symbiota scraper act as a secondary fallback layer is a brilliant way to ensure no regional synonyms slip through the cracks!

##### Output Formatting

symbiota.py returns standardized lists, JSON dictionaries, or parsed XML trees, which are easily ingested by downstream aggregator pipelines.

## Initialization & Core Helpers
### __init__()
This is the setup function. Because Symbiota runs many different websites (Lichen Portal, SERNEC, MyCoPortal), this function takes the specific website URL and stores it. This allows your app to create 12 different Symbiota clients from this single class just by passing in different URLs.

### _get()
This is a "private" helper function (denoted by the underscore) that does all the actual downloading. Instead of writing requests.get(...) in every function, they all route through here. Crucially, this function attaches a fake Web Browser header ("User-Agent": "Mozilla/5.0") to trick Symbiota firewalls into thinking a real human is visiting, which prevents your app from being blocked.

## Official API Endpoints
### search()
This asks the portal's taxasearch.php page if it recognizes a name. Symbiota servers are notoriously buggy and will sometimes reply with modern JSON data, and other times with old XML data. This function tries to read it as JSON first, and if that fails, safely parses it as an XML tree.

### occurrences()
This is the data-gatherer. It asks the occurrences/search.php page for a list of physical specimen records. It has heavy "defensive programming" built in: if a Symbiota portal crashes and returns a raw HTML error page (which happens frequently), this function detects the `<html` tag and safely returns an empty list [] so your Streamlit app doesn't crash.


## Custom Synonym Scraper
### _get_tid(self, species_name: str) (Step 1)
This function abuses the website's autocomplete search bar feature (gettaxasuggest.php). You give it a string name, and it returns the website's hidden internal database ID for that species (the tid). You must have this ID to load the webpage.

### _resolve_accepted_tid(self, tid: int) (Step 2)
Sometimes a user searches for an outdated name. If you scrape the page for an outdated name, it won't list the synonyms. This function checks the ID to see if it is accepted. If it is an outdated synonym, it automatically finds the ID of the modern, accepted name so the scraper goes to the right page.

### _scrape_synonyms(self, accepted_tid: int) (Step 3)
This is where the actual web scraping happens. It downloads the raw HTML code of the species profile page. It uses Regular Expressions (re.search) to find the exact `<div id="synonymDiv">` box on the page, extracts all the text trapped inside the italic `<i>` tags, and filters out subspecies or varieties.

### synonyms(self, name: str) (The Orchestrator)
This is the public-facing function that your SynonymEngine actually calls. It runs the three scraping steps above in perfect order:

1. Capitalizes the name.

2. Gets the tid.

3. Resolves the accepted tid.

4. Scrapes the HTML page.

5. Formats the scraped names into the clean list of dictionaries ([{"canonicalName": "Amanita muscaria"}]) that your pipeline expects.
It wraps all of this in a massive try/except block so that if the website changes its HTML layout and breaks the scraper, it just quietly returns an empty list rather than crashing your entire project.

### _scrape_occurrences_html()
This retrieves Physical Specimen Records. It acts as an emergency "safety net" for the main aggregator. When the portal's API completely fails and returns a visual HTML webpage instead of machine-readable JSON, this function steps in to rescue the physical occurrence data.

It does not initiate a network request. It takes the html_text that was already downloaded by the main occurrences() function. It acts purely as a parser for data already in memory.

It hunts for data tables. It searches the page for `<table>` elements with specific identifiers (id="occTable", class="styledtable", or class="table").

It has a dynamic schema. It reads the `<th>` (table headers) dynamically and uses whatever text the portal chose as the dictionary keys. It maps the `<td>` (table row) values to those headers.