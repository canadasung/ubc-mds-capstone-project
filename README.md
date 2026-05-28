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
│       ├── sample_table_data_amanita_muscaria.csv
│       ├── sample_table_data_taraxacum_officinale.csv
│       └── sample_table_data_ursus_arctos.csv
├── deprecated/                   # files that are unused in the code base and may not be up to date
│   ├── AntWeb.py
│   ├── prototype_dash.py
│   └── prototype_shiny.py
├── notebooks/                    # demonstrate usage of some scripts
│   ├── APIs/
│   │   ├── BryophytePortal.ipynb
│   │   └── ...
│   ├── APIs_pipe/                # notebooks and logs for the pipeline-based API layer
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

Then open your browser to `http://localhost:8501`.

---

## Usage Guide

The app is designed to help museum curators quickly look up and evaluate current taxonomic information.

1. **Search** — Enter a species name in the search bar.
2. **Review** — The app retrieves current synonyms and taxonomic status from different data sources, e.g. GBIF, Catalogue of Life.
3. **Decide** — Choose the designation you'd like to incorporate (no app activity corresponds)

[Expand this section with screenshots or a short GIF once the app is more complete.]

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
