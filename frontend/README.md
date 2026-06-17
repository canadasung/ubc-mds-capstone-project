# Frontend (Next.js)

React/Next.js frontend for the species-synonym tool. Replaces the Streamlit
prototypes in `../app/` and talks to the FastAPI backend in `../backend_api/`.
See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the design and the
Streamlit→React mapping.

## Prerequisites

- Node.js ≥ 18.18 (Next.js 14)
- The FastAPI backend running locally:
  ```bash
  # from the repo root, with the conda env active
  uvicorn backend_api.main:app --reload --port 8000
  ```

## Setup

```bash
cd frontend
cp .env.local.example .env.local   # points at http://localhost:8000 by default
npm install
npm run dev                        # http://localhost:3000
```

The backend already allows CORS from `http://localhost:3000` (see
`backend_api/main.py`). If you host the API elsewhere, set `NEXT_PUBLIC_API_BASE_URL`
in `.env.local` and add that frontend origin to the CORS `allow_origins` list.

## Scripts

- `npm run dev` — dev server with hot reload
- `npm run build` / `npm run start` — production build / serve
- `npm run typecheck` — `tsc --noEmit`
- `npm run lint` — Next.js ESLint

## What it does

Mirrors `app/prototype_master.py`: a collapsible search panel (left) and a
switchable set of views (right) sharing one search.

- **Table** — cross-source presence matrix; ✓ links to each source's page.
- **Timeline** — Plotly timeline of synonyms by publication year.
- **Node** — React Flow graph: query → source → synonyms (click to open links).
- **Taxonomic** — per-source classification with disagreements highlighted red.
- **Debug** — raw record table (toggle "Debug" in the header).

Live search streams results source-by-source via `/api/search/stream`, with a
progress bar showing which source is currently being queried. If all sources
return empty, fuzzy suggestions appear as "Did you mean?" chips. The Suggest
button calls `/api/suggest` to auto-select the right sources for the species'
kingdom. The taxonomy view still uses pre-computed sample CSVs (`mock=true`).

## Layout

```
frontend/
├── app/
│   ├── layout.tsx        # Mantine + providers root
│   ├── providers.tsx     # TanStack Query client
│   ├── page.tsx          # AppShell: collapsible panel + view area
│   └── globals.css
├── components/
│   ├── SearchPanel.tsx   # search form + advanced source filters
│   ├── ViewSwitcher.tsx  # SegmentedControl (= st.segmented_control)
│   ├── ResultsArea.tsx   # empty/loading/error + active-view dispatch
│   └── views/
│       ├── TableView.tsx
│       ├── TimelineView.tsx
│       ├── PlotlyChart.tsx   # client-only Plotly wrapper
│       ├── NodeView.tsx
│       ├── TaxonomyView.tsx
│       └── DebugView.tsx
├── lib/
│   ├── api.ts            # fetch client
│   ├── types.ts          # TS mirrors of the FastAPI JSON
│   ├── fields.ts         # record column accessors (one place to remap)
│   ├── sources.ts        # source keys/labels/groups + api_name mapping
│   ├── hooks.ts          # TanStack Query hooks (server state)
│   ├── store.ts          # Zustand store (UI state)
│   └── transforms.ts     # record → table/node/timeline shapes
├── types/shims.d.ts
└── ARCHITECTURE.md
```

## Next steps

1. Wire `/api/taxonomy` to live data (currently mock-only; depends on the same
   `call_apis` pipeline that search now uses).
2. Regenerate sample CSVs to include the new `order` column so mock mode and
   the Taxonomy view stay in sync.
