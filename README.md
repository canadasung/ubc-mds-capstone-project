# ubc-mds-project

Repository for the UBC MDS DSCI 591 Group 8 Capstone Project in partnership with Beaty Biodiversity Museum

---

## Executive Summary

Taxonomy, including species names and ranks, is constantly changing with the advent of new scientific methods. Curators at the Beaty Biodiversity Museum have to keep track of all of these changes in order to keep the collections current, but finding and evaluating information can be time consuming. This web app synthesizes current information online regarding species name synonyms and taxonomy and provides it to curators, who can then decide which designation they'd like to incorporate into the museum's database.

---

## Background & Context

The [Beaty Biodiversity Museum](https://beatymuseum.ubc.ca/) at the University of British Columbia houses one of Canada's largest natural history collections. Keeping taxonomic records accurate is an ongoing challenge, as consensus on species names, synonyms, and classification shifts regularly with research and new scientific methods.

This project was developed as part of the UBC Master of Data Science (MDS) DSCI 591 Capstone Program (2025–2026), in partnership with the museum's informatics team.

---

## Project Structure

```
ubc-mds-project/
├── app/
│   ├── prototype.py              # Streamlit app entry point
│   ├── prototype_node_graph.py   # node graph visualization prototype
│   ├── prototype_pipe.py         # pipeline-based query prototype
│   ├── prototype_taxonomy.py     # taxonomy tree visualization prototype
│   └── prototype_timeline.py     # timeline visualization prototype
├── data/
│   └── sample/                   # sample query result CSVs for testing/demos
│       ├── ...
├── deprecated/                   # files that are unused in the code base and may not be up to date
│   ├── ...         `       
├── notebooks/                    # demonstrate usage of some scripts
│   ├── APIs/
│   │   ├── BryophytePortal.ipynb
│   │   └── ...
│   ├── apis_pipe/                # notebooks and logs for the pipeline-based API layer
│   │   ├── demo_query.py
│   │   ├── log_gbif_explained.md
│   │   └── log_symbiota_explained.md
│   └── utils/
│       ├── fuzzy_search.ipynb
│       ├── portals_error_missing.ipynb
│       └── router.ipynb
├── reports/
│   ├── images/
│   ├── proposal.ipynb
│   └── proposal.pdf
├── scripts/
│   ├── APIs/                     # individual API client scripts
│   │   ├── planned_scripts/      # scripts that are partially implemented and may be fully implemented in the future
│   │   │   └── iNat.py
│   │   ├── GBIF.py
│   │   └── ...
│   ├── apis_pipe/                # pipeline-based API clients with unified interface
│   │   ├── base.py               # abstract base class for pipeline API clients
│   │   ├── col.py
│   │   ├── gbif.py
│   │   ├── genbank.py
│   │   ├── index_fungorum.py
│   │   ├── mushroomobs.py
│   │   ├── symbiota.py
│   │   └── tropicos.py
│   └── utils/
│       ├── aggregator.py         # merges results across APIs
│       ├── call_APIs.py          # aggregates all API calls (original layer)
│       ├── call_apis_pipe.py     # aggregates all pipeline API calls
│       ├── fuzzy_search.py       # performs fuzzy matching on search query
│       ├── normalize_query_string.py
│       ├── router.py             # routes queries to appropriate APIs
│       └── synonyms.py           # handles taxonomic synonym expansion
├── tests/
│   ├── APIs/                     # tests for each fully implemented API
│   │   ├── test_GBIF.py
│   │   └── ...
│   ├── apis_pipe/                # tests for pipeline-based API layer
│   │   ├── test_API_online.py    # checks that external APIs are reachable
│   │   └── test_env_configured.py
│   ├── app/
│   │   ├── test_prototype.py
│   │   └── test_prototype_taxonomy.py
│   ├── utils/
│   │   ├── test_call_apis.py
│   │   ├── test_fuzzy_search.py
│   │   └── test_normalize_query_string.py
│   └── conftest.py
├── .env.example                  # Template for environment variables
├── .gitignore
├── environment.yml               # Conda environment
├── pyproject.toml                # sets up scripts folder as package so that API scripts can be called from tests, notebooks, and app
├── LICENSE
├── paths.py                      # defines paths to root and each major folder
└── README.md
```

---

## Environment Setup

### 1. Create the Conda environment

From the root of the repository, run:

```bash
conda env create -f environment.yml
```

### 2. Activate the environment

```bash
conda activate mds-project
```

### 4. Set up credentials

#### Local development

This project uses a `.env` file for secrets and credentials:

1. Copy the example file into `.env`:

```bash
cp .env.example .env
```

1. Open `.env` and replace the placeholder values with your own (see comments in the file for details).

1. Never commit `.env` — it is listed in `.gitignore`.

#### CI (GitHub Actions)

The GenBank tests require an `ENTREZ_EMAIL` environment variable. To enable these tests in CI, add it as a repository secret:

1. Go to your repository on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Set **Name** to `ENTREZ_EMAIL` and **Secret** to your email address
4. Click **Add secret**

If the secret is not set, the GenBank tests will fail on Github.

---

## Running the App

With the environment active, launch the Streamlit app from the root of the repository:

```bash
streamlit run app/prototype.py
```

Alternatively, run any of the other prototype apps:

```bash
streamlit run app/prototype.py
streamlit run app/prototype_node_graph.py
......
```

Then open your browser to `http://localhost:8501`.

---

## Usage Guide

Each prototype app offers a different view of the same taxonomic data. All apps share the same basic workflow:

1. **Search** — Enter a species name (e.g. *Amanita muscaria*) in the search bar.
2. **Review** — The app queries the selected databases and displays synonyms, taxonomy, or occurrence data.
3. **Decide** — Use the results to evaluate which name or classification to adopt.

If no exact match is found, the app suggests alternatives via fuzzy search ("Did you mean?").

---

### `prototype.py` — Synonym Table (original layer)

Results are displayed as a single table where each row is a species name and each column is a database source, with a checkmark (✓) indicating which sources recognize that name. The searched name is always shown first in bold. Use **Advanced filters** to enable or disable individual sources.

---

### `prototype_pipe.py` — Synonym Table (pipeline layer)

The most comprehensive synonym view. Queries a wider set of sources: GBIF, eleven Symbiota portals. Results are split into two tables: **Accepted Species Name** and **Known Synonyms & Aliases**. Each shows which databases recognize the name. Sources are organized into three groups in the **Advanced filters** panel: Global Backbone, Symbiota Portals, and Independent APIs.

---

### `prototype_node_graph.py` — Interactive Node Graph

Displays synonym results as a visual graph. The search query appears as a central node on the left. Each queried database appears as a row of nodes extending to the right, with individual synonym nodes branching off further right. Clicking any node opens the corresponding database search page in a new tab (where available). Use the sidebar to select which databases to include.

---

### `prototype_taxonomy.py` — Taxonomy Comparison

Queries for the full taxonomic classification (kingdom → species) of the entered name, and displays each source's classification side by side in a table. Any rank where sources disagree is **highlighted in red**.

---

### `prototype_timeline.py` — Publication Timeline *(uses mock data)*

Visualizes synonyms as an interactive timeline, with each synonym positioned at its year of first publication. Synonyms appear as info cards on the timeline showing author, publication name, and a link to the source. This prototype currently uses mock data and does not yet query live APIs.

---

## Contributors

| Name | GitHub |
|------|--------|
| [William Song] | [@handle](https://github.com/canadasung) |
| [Molly Kessler] | [@handle](https://github.com/kessler24) |
| [Wendy Frankel] | [@handle](https://github.com/wendyf55) |
| [Johnson Chuang] | [@handle](https://github.com/stoyq) |

---

## Citations

GBIF:
'Tools returning results directly from the GBIF search API (e.g. spocc, dismo and the occ_data() and occ_search() functions of rgbif) will not assign single DOIs for data downloaded. It is up to the user to identify dataset publishers and properly acknowledge each of them when citing the data.

For data obtained via occurrence search API-based tools, we recommend using a derived dataset as an easy way of obtaining a DOI for citing the data. The rOpenSci documentation site provides instructions on how to cite GBIF-mediated data in rgbif.' **something to do before we make this repository public!**

Catalogue of Life:
Bánki, O., Roskov, Y., Döring, M., Ower, G., Hernández Robles, D. R., Plata Corredor, C. A., Stjernegaard Jeppesen, T., Örn, A., Pape, T., Hobern, D., Garnett, S., Little, H., DeWalt, R. E., Miller, J., Orrell, T., Aalbu, R., Abbott, J., Abreu, C., Acero P, A., et al. (2026). Catalogue of Life (2026-04-18 XR). Catalogue of Life Foundation, Amsterdam, Netherlands. <https://doi.org/10.48580/dgxjw>

Index Fungorum:
IndexFungorum (2025). Published on the Internet <http://www.indexfungorum.org>, The Royal Botanic Gardens, Kew. [Retrieved 1 May 2026].

NCBI (Basically, GenBank):
Entrez® Programming Utilities Help [Internet]. Bethesda (MD): National Center for Biotechnology Information (US); 2010-. Available from: <https://www.ncbi.nlm.nih.gov/books/NBK25501/>

Mushroom Observer:
Wilson, N., Hollinger, J., et al. 2006-present. Mushroom Observer. <https://mushroomobserver.org>

---

## License

This project is licensed under the [MIT License](LICENSE).
