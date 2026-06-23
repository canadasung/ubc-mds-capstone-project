# Beaty Biodiversity Species Synonym Tool

A web application that aggregates species synonyms and taxonomic information from
online biodiversity databases and presents them to museum curators in several
linked views. Developed for the UBC MDS DSCI 591 Capstone (2025-2026) in
partnership with the Beaty Biodiversity Museum.

---

## Executive Summary

Curators at the Beaty Biodiversity Museum keep millions of physical specimens
organized and labeled according to the current scientific consensus on their
taxonomy. Because taxonomy changes over time, a single species can be referred to
by many different synonyms across publications. This application queries a set of
online biodiversity databases for a searched name, gathers the synonyms and
taxonomic data they return, and presents the combined results with direct links
back to each source. It is a decision-support tool: it surfaces and organizes
evidence but does not select or overwrite a name, leaving the final judgment to
the curator.

---

## Background and Context

The [Beaty Biodiversity Museum](https://beatymuseum.ubc.ca/) at the University of
British Columbia houses one of Canada's largest natural history collections.
Keeping taxonomic records accurate is an ongoing task, as consensus on species
names, synonyms, and classification shifts with new research and methods.
Curators currently consult many separate databases by hand to resolve these
differences. This application consolidates that lookup into one interface.

This project was developed as part of the UBC Master of Data Science (MDS) DSCI
591 Capstone Program (2025-2026), in partnership with the museum's informatics
team.

---

## Final Report

The final report is available at [reports/final-report.pdf](reports/final-report.pdf).

To regenerate it from source after editing [reports/final-report.md](reports/final-report.md):

```bash
quarto render reports/final-report.md
```

---

## Architecture

The system has three layers:

```
Browser (Next.js / React, port 3000)
        |
        |  HTTP / JSON (CORS)
        v
FastAPI backend (backend_api/, port 8000)
        |
        |  Python calls
        v
Data pipeline (scripts/)  ->  external biodiversity APIs
```

- **Frontend** ([frontend/](frontend/)): a Next.js application using React,
  Mantine, TanStack Query, and Zustand. It is a pure client of the backend's JSON
  API. See [frontend/ARCHITECTURE.md](frontend/ARCHITECTURE.md) for the design.
- **Backend** ([backend_api/](backend_api/)): a FastAPI service that wraps the
  Python pipeline and exposes HTTP endpoints.
- **Pipeline** ([scripts/](scripts/)): one client per source, each implementing
  the shared `SpeciesAPI` contract, plus utilities for routing, fuzzy matching,
  query normalization, and schema validation.

Live search streams results source by source as Server-Sent Events through
`/api/search/stream`, reporting progress as each source is queried. The Taxonomy
view currently reads pre-computed sample data (`data/sample/*.csv`).

---

## Views

A single query produces five linked views of the same data:

- **Overview**: every synonym returned by the search, alongside which databases
  recognize each name. The searched name is shown first.
- **Detail**: the full set of records from every database, with an option to
  download the results as a CSV file.
- **Relations**: an interactive graph of synonyms grouped by genus and/or species, with links to
  each source record.
- **Timeline**: each name placed at its year of first publication, with author and
  publication shown in chronological order.
- **Taxonomy**: the species' classification across ranks (Kingdom, Phylum, Class,
  Order, Family, Subfamily). Cells are shaded by edit distance against a
  comparison source (GBIF by default, user-selectable) so alternative spellings are
  distinguished from genuine disagreements.

If a search returns no results, the app offers fuzzy name suggestions
("Did you mean?") from the GBIF backbone.

---

## Data Sources

The application queries multiple databases, organized into three groups in the
source filter:

- **Global Backbone**: GBIF.
- **Symbiota Portals**: MyCoPortal, Lichen Portal, Bryophyte Portal, SERNEC,
  CCH2, NANSH, Southwest Biodiversity, Algae Herbarium Portal, Pterido Portal,
  CNH (Northeast Herbaria), and Mid-Atlantic Herbaria.
- **Independent APIs**: Catalogue of Life (COL), Tropicos, Index Fungorum,
  GenBank, FishBase, ITIS, and Mushroom Observer.

All source display names and base URLs are defined in one place,
[scripts/config.py](scripts/config.py), which is the single source of truth for
the rest of the pipeline.

GenBank and Tropicos require credentials (see [Credentials](#3-set-up-credentials)).
The other sources need no credentials.

---

## Data Schema

Each result is one row with 16 fields. Four are required and the rest are
optional, since not every source provides every field. Fields a source never
provides are marked `N/A` (unavailable), which is distinct from an empty string
(searched but not found). The schema and its validation rules are defined in
[scripts/utils/schema.py](scripts/utils/schema.py).

| Field | Required | Description |
|-------|----------|-------------|
| `api_name` | yes | Name of the source that provided the record (e.g. GBIF). |
| `kingdom`, `phylum`, `class`, `order`, `family`, `subfamily` | no | Taxonomic ranks. |
| `genus`, `species` | yes | Taxonomic genus and species. |
| `author` | no | Author of the taxonomic name. |
| `publication_name` | no | Publication where the name appeared. |
| `publication_year` | no | Four-digit year of publication. |
| `status` | no | `Accepted` or `Synonym` in the source's database. |
| `original_source` | no | Citation of the source's own data source, if provided. |
| `api_link` | no | Link to the record on the source's website. |
| `api_internal_id` | yes | Unique identifier for the record in the source's database. |

---

## Project Structure

```
ubc-mds-project/
├── backend_api/                  # FastAPI service wrapping the Python pipeline
│   ├── main.py                   # app entry point, CORS, router registration
│   └── routers/
│       ├── search.py             # /api/search, /api/search/stream, /api/suggest, /api/sources
│       └── taxonomy.py           # /api/taxonomy
├── frontend/                     # Next.js (React + Mantine) web client
│   ├── app/                      # App Router pages and layout
│   ├── components/               # search panel, view switcher, and the five views
│   ├── lib/                      # API client, query hooks, store, source registry
│   ├── ARCHITECTURE.md           # frontend design and Streamlit-to-React mapping
│   └── README.md
├── scripts/                      # Python data pipeline (installed as an editable package)
│   ├── config.py                 # source display names and base URLs (single source of truth)
│   ├── apis_pipe/                # one SpeciesAPI client per source
│   │   ├── base.py               # SpeciesAPI abstract base class
│   │   ├── gbif.py, col.py, genbank.py, index_fungorum.py, mushroomobs.py,
│   │   ├── symbiota.py, tropicos.py, fishbase.py, itis.py
│   └── utils/
│       ├── call_apis_pipe.py     # fans a query out to the requested sources
│       ├── router.py             # routes a query to sources by kingdom (via GBIF)
│       ├── fuzzy_search.py       # GBIF fuzzy name suggestions
│       ├── normalize_query_string.py
│       └── schema.py             # synonym table schema and row validation
├── data/sample/                  # pre-computed sample query results (CSV) for mock mode
├── notebooks/                    # usage demonstrations for the pipeline and utilities
│   ├── apis_pipe/
│   └── utils/
├── tests/                        # pytest suite
│   ├── utils/
│   └── conftest.py
├── deprecated/                   # legacy Streamlit prototypes and earlier API scripts
├── reports/                      # project proposal and report material
├── Dockerfile                    # backend image for the Hugging Face Space
├── environment.yml               # conda environment (mds-project)
├── requirements.txt              # backend-only pip dependencies (for the Space)
├── pyproject.toml                # installs scripts/ as an importable package
├── paths.py                      # repository path helpers
├── .env.example                  # template for credentials
├── README.hf.md                  # Hugging Face Space README
├── LICENSE
└── README.md
```

---

## Environment Setup

### 1. Create the conda environment

From the root of the repository:

```bash
conda env create -f environment.yml
```

This installs the Python dependencies, registers `scripts/` as an editable
package so it is importable from the backend, notebooks, and tests, and provides
Node.js and npm for the frontend.

### 2. Activate the environment

```bash
conda activate mds-project
```

### 3. Set up credentials

Some sources require credentials. Copy the template and fill in your values:

```bash
cp .env.example .env
```

- `ENTREZ_EMAIL`: an email address required by NCBI for GenBank requests. No
  account is needed.
- `TROPICOS_API_KEY`: a free key for the Tropicos API, available at
  <https://services.tropicos.org/help?requestkey>.

`.env` is listed in `.gitignore` and should never be committed. Sources other
than GenBank and Tropicos work without credentials.

#### CI (GitHub Actions)

The GenBank tests require `ENTREZ_EMAIL`. To enable them in CI, add it as a
repository secret: go to **Settings** > **Secrets and variables** > **Actions** >
**New repository secret**, set the name to `ENTREZ_EMAIL` and the value to your
email address. If the secret is not set, the GenBank tests fail in CI.

---

## Running Locally

The frontend depends on the backend. Start the backend first, then the frontend.

### Backend

With the environment active (added in the following code blocks as a reminder), 
from the repository root:

```bash
conda activate mds-project
uvicorn backend_api.main:app --reload --port 8000
```

The API is then available at <http://localhost:8000>.

### Frontend

In a second terminal, with the environment active from the repository root:

```bash
conda activate mds-project
cd frontend
cp .env.local.example .env.local   # points at http://localhost:8000 by default
npm install
npm run dev                        # http://localhost:3000
```

Open <http://localhost:3000> in your browser. The backend already allows requests
from `http://localhost:3000`. If you host the API elsewhere, set
`NEXT_PUBLIC_API_BASE_URL` in `.env.local` and add the frontend origin to the
backend's allowed origins (`ALLOWED_ORIGINS`).

Additional frontend scripts:

- `npm run build` and `npm run start`: production build and serve.
- `npm run typecheck`: `tsc --noEmit`.
- `npm run lint`: Next.js ESLint.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/search` | Synonym search. Reads sample data by default (`mock=true`). |
| `GET /api/search/stream` | Live source-by-source search, streamed as Server-Sent Events. |
| `GET /api/suggest` | Recommended sources for a name, routed by kingdom via GBIF. |
| `GET /api/sources` | List of known source keys. |
| `GET /api/taxonomy` | Per-source taxonomy comparison. Reads sample data by default. |

---

## Pipeline Design

Each source is implemented as a subclass of `SpeciesAPI`
([scripts/apis_pipe/base.py](scripts/apis_pipe/base.py)). The base class fixes the
order and signatures of five required methods so every source behaves
consistently while keeping the source-specific parsing isolated:

1. `_fetch_query_data`: resolve the searched name to the source's internal record.
2. `_fetch_synonym_data`: retrieve the synonyms for that record.
3. `_fetch_synonym_search_term_data`: retrieve metadata (and taxonomy, if
   available) for the searched record itself.
4. `_compile_synonyms`: format the synonym data into standard rows.
5. `_compile_synonym_search_term`: format the searched record into a standard row.

The two outputs are combined and returned as a DataFrame in the schema format.
The base class also provides optional helpers (for example, extracting a
publication year from a citation string) that a source can use or override.
To add a new source, implement the five required methods, then register it in two
places that must be kept in sync:

- Backend: [scripts/config.py](scripts/config.py) and
  [scripts/utils/call_apis_pipe.py](scripts/utils/call_apis_pipe.py), so the
  pipeline can query the source.
- Frontend: [frontend/lib/sources.ts](frontend/lib/sources.ts), so the source
  appears in the source filter in the app.

The source list is currently maintained separately in the backend and the
frontend, so both must be updated until they are consolidated into a single
source of truth.

---

## Tests

> **Note:** the test suite is significantly out of date and is not recommended for
> use at this time.

Run the suite from the repository root:

```bash
pytest tests/
```

Notes:

- `tests/utils/test_API_online.py` makes real HTTP requests and requires internet
  access.
- `tests/utils/test_env_configured.py` checks that `.env` exists and its values
  are filled in.

A GitHub Actions workflow runs the suite on every pull request.

---

## Deployment

- **Backend**: a Docker image ([Dockerfile](Dockerfile)) is deployed to a Hugging
  Face Space, which serves the FastAPI app on port 7860. The Space README is kept
  as [huggingface_readme.md](huggingface_readme.md) in this repository so it does not clash with this
  project README. Allowed frontend origins are configured through the
  `ALLOWED_ORIGINS` Space variable.
- **Frontend**: the Next.js app is deployed to Vercel and points at the backend
  through `NEXT_PUBLIC_API_BASE_URL`.

---

## Team

Developed by UBC MDS students for the DSCI 591 Capstone:

| Name | GitHub |
|------|--------|
| Molly Kessler | [@kessler24](https://github.com/kessler24) |
| Wendy Frankel | [@wendyf55](https://github.com/wendyf55) |
| Johnson Chuang | [@stoyq](https://github.com/stoyq) |
| William Song | [@canadasung](https://github.com/canadasung) |

- Project mentor: Payman Nickchi, UBC MDS Faculty.
- Capstone partner: Paul Bucci, Informatics Curator, Beaty Biodiversity Museum.

---

## Citations

GBIF: Tools that return results directly from the GBIF search API do not assign a
single DOI for the downloaded data. Users should identify dataset publishers and
acknowledge each of them when citing the data. For data obtained through the
occurrence search API, GBIF recommends creating a derived dataset to obtain a DOI
for citation.

Catalogue of Life: Banki, O., Roskov, Y., Doring, M., Ower, G., Hernandez Robles,
D. R., Plata Corredor, C. A., Stjernegaard Jeppesen, T., Orn, A., Pape, T., Hobern,
D., Garnett, S., Little, H., DeWalt, R. E., Miller, J., Orrell, T., Aalbu, R.,
Abbott, J., Abreu, C., Acero P, A., et al. (2026). Catalogue of Life (2026-04-18
XR). Catalogue of Life Foundation, Amsterdam, Netherlands.
<https://doi.org/10.48580/dgxjw>

Index Fungorum: IndexFungorum (2025). Published on the Internet
<http://www.indexfungorum.org>, The Royal Botanic Gardens, Kew. Retrieved 1 May
2026.

NCBI (GenBank): Entrez Programming Utilities Help [Internet]. Bethesda (MD):
National Center for Biotechnology Information (US); 2010-. Available from
<https://www.ncbi.nlm.nih.gov/books/NBK25501/>

Mushroom Observer: Wilson, N., Hollinger, J., et al. 2006-present. Mushroom
Observer. <https://mushroomobserver.org>

---

## License

This project is licensed under the [MIT License](LICENSE).
