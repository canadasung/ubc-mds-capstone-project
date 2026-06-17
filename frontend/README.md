# Frontend (Next.js)

React/Next.js frontend for the species-synonym tool. Replaces the Streamlit
prototypes in `../app/` and talks to the FastAPI backend in `../backend_api/`.
See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the design and the
Streamlit→React mapping.

## Running locally

You need **two terminal windows** open at the same time — one for the backend, one for the frontend.

### 1. Activate the conda environment (both terminals)

Run this first in each terminal before doing anything else:

```bash
conda activate mds-project
```

### 2. Terminal 1 — start the FastAPI backend

From the repo root:

```bash
uvicorn backend_api.main:app --reload --port 8000
```

Leave this running. You should see `Uvicorn running on http://127.0.0.1:8000`.

### 3. Terminal 2 — start the Next.js frontend

From the repo root:

```bash
cd frontend
npm install          # only needed the first time, or after pulling new changes
npm run dev
```

Leave this running too. You should see `Ready - started server on http://localhost:3000`.

### 4. Open the app in your browser

Navigate to **[http://localhost:3000](http://localhost:3000)**.

> The app will not finish compiling until you actually visit this URL — Next.js defers compilation until the first page load, so the terminal may look idle until you open the browser.

### First-time setup only

If you haven't set up `.env.local` yet:

```bash
cd frontend
cp .env.local.example .env.local   # points at http://localhost:8000 by default
```

If you host the API elsewhere, set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` and add that frontend origin to the CORS `allow_origins` list in `backend_api/main.py`.

## Prerequisites

- Node.js ≥ 18.18 (Next.js 14)
- The `mds-project` conda environment (contains all Python dependencies)

## Scripts

- `npm run dev` — dev server with hot reload
- `npm run build` / `npm run start` — production build / serve
- `npm run typecheck` — `tsc --noEmit`
- `npm run lint` — Next.js ESLint

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
