# Frontend (Next.js)

React/Next.js frontend for the species synonym tool. It replaces the Streamlit
prototypes now kept in `../deprecated/app/` and talks to the FastAPI backend in
`../backend_api/`. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the design and
the Streamlit-to-React mapping.

## Prerequisites

- Node.js >= 18.18 (Next.js 14). The `mds-project` conda environment provides
  Node 20+ along with all Python dependencies, so no separate Node install is
  needed when it is active.

## Running locally

Open two terminal windows, one for the backend and one for the frontend.

### 1. Activate the conda environment (both terminals)

Run this first in each terminal before anything else:

```bash
conda activate mds-project
```

### 2. Terminal 1: start the FastAPI backend

From the repo root:

```bash
uvicorn backend_api.main:app --reload --port 8000
```

Leave this running. You should see `Uvicorn running on http://127.0.0.1:8000`.

### 3. Terminal 2: start the Next.js frontend

From the repo root:

```bash
cd frontend
npm install          # only needed the first time, or after pulling new changes
npm run dev
```

Leave this running too. You should see `Ready - started server on http://localhost:3000`.

### 4. Open the app in your browser

Navigate to [http://localhost:3000](http://localhost:3000).

> Next.js defers compilation until the first page load, so the terminal may look
> idle until you open this URL.

### First-time setup only

If you have not set up `.env.local` yet:

```bash
cd frontend
cp .env.local.example .env.local   # points at http://localhost:8000 by default
```

The backend already allows requests from `http://localhost:3000` by default. If
you host the API elsewhere, set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` and add
that frontend origin to the backend's `ALLOWED_ORIGINS` (read in
`backend_api/main.py`).

## Scripts

- `npm run dev`: dev server with hot reload.
- `npm run build` and `npm run start`: production build and serve.
- `npm run typecheck`: `tsc --noEmit`.
- `npm run lint`: Next.js ESLint.

## What it does

A collapsible search panel on the left and a switchable set of views on the
right, all driven by one shared search. This mirrors the deprecated Streamlit
prototype (`../deprecated/app/prototype_master.py`).

The five views, selected with the segmented control:

- **Overview** (`TableView`): a presence matrix marking which sources recognize
  each name, with links to each source's record. The searched name is shown first.
- **Detail** (`DetailView`): the raw record table for every selected source,
  downloadable as a CSV named from the query.
- **Relations** (`RelationsView`): a React Flow graph of synonyms grouped by
  genus, with links to each source.
- **Timeline** (`TimelineView`): a Plotly timeline placing each synonym at its
  publication year.
- **Taxonomy** (`TaxonomyView`): each source's classification shown side by side.
  The higher ranks (Kingdom, Phylum, Class, Family) are shaded by character edit
  distance from a backbone source (GBIF by default, user-selectable).

Live search streams results source by source via `/api/search/stream`, with a
progress indicator showing which source is being queried. If all sources return
no results, fuzzy suggestions appear as "Did you mean?" buttons. The Suggest
button calls `/api/suggest` to auto-select sources for the species' kingdom. The
Taxonomy view reads pre-computed sample data (`mock=true`).

## Layout

```
frontend/
├── app/
│   ├── layout.tsx        # Mantine providers + root layout
│   ├── providers.tsx     # TanStack Query client
│   ├── page.tsx          # AppShell: collapsible panel + view area
│   └── globals.css
├── components/
│   ├── SearchPanel.tsx   # search form, source filters, Suggest button
│   ├── ViewSwitcher.tsx  # SegmentedControl over the five views
│   ├── ResultsSummary.tsx# name and source counts beside the switcher
│   ├── ResultsArea.tsx   # empty/loading/error states + active-view dispatch
│   ├── TutorialModal.tsx # first-run walkthrough
│   └── views/
│       ├── TableView.tsx      # Overview: cross-source presence matrix
│       ├── DetailView.tsx     # Detail: raw record table + CSV download
│       ├── RelationsView.tsx  # Relations: React Flow graph grouped by genus
│       ├── TimelineView.tsx   # Timeline: Plotly synonyms by publication year
│       ├── TaxonomyView.tsx   # Taxonomy: per-source ranks, shaded by edit distance
│       └── PlotlyChart.tsx    # client-only Plotly wrapper
├── lib/
│   ├── api.ts            # fetch client
│   ├── types.ts          # TS mirrors of the FastAPI JSON
│   ├── fields.ts         # record column accessors (one place to remap)
│   ├── sources.ts        # source keys/labels/groups + backend name mapping
│   ├── hooks.ts          # TanStack Query hooks (server state)
│   ├── store.ts          # Zustand store (UI state)
│   ├── transforms.ts     # record to table/node/timeline shapes
│   └── taxonomyShading.ts# per-cell edit-distance shading for the Taxonomy view
├── types/shims.d.ts
└── ARCHITECTURE.md
```

## Next steps

1. Wire `/api/taxonomy` to live data (currently mock-only).
2. Regenerate the sample CSVs to include the `order` column so mock mode and the
   Taxonomy view stay in sync with the schema.
```
