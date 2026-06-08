# Frontend Migration: Streamlit → Next.js (React)

This document proposes the architecture for replacing the Streamlit prototypes
(`app/prototype_master.py` and friends) with a Next.js + React frontend that
talks to the existing FastAPI backend (`api/`).

The scaffold in this `frontend/` directory implements the proposal. It mirrors
`prototype_master.py`: a collapsible search panel on the left and a switchable
set of views (Table, Timeline, Node, Taxonomic, Debug) on the right, all driven
by one shared search.

---

## 1. Why we are moving

Streamlit's execution model is the root of the pain points:

- **Caching is awkward.** `@st.cache_data` / `@st.cache_resource` cache *Python
  function calls*, not HTTP responses, and invalidation is implicit. Every
  widget interaction re-runs the whole script top-to-bottom, so state has to be
  smuggled through `st.session_state` and manually re-hydrated (see the
  `_pending_source_updates` / deferred-`st.rerun()` dance in
  `prototype_master.py`).
- **UX control is limited.** Layout is constrained to Streamlit's column/expander
  primitives; custom interactions need `unsafe_allow_html` CSS injection and
  `components.html` iframes (the node graph is a pyvis iframe today).

React inverts both problems: the component tree only re-renders what changed,
and **TanStack Query** gives us a real request cache with explicit keys and
invalidation — a direct, principled replacement for `@st.cache_data`.

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Next.js / React, port 3000)                        │
│                                                              │
│  ┌────────────────┐   reads/writes    ┌───────────────────┐  │
│  │  Zustand store │ ◄──────────────►  │  React components │  │
│  │  (UI state)    │                   │  SearchPanel,     │  │
│  └────────────────┘                   │  ViewSwitcher,    │  │
│         ▲                             │  5 Views          │  │
│         │ submittedQuery              └─────────┬─────────┘  │
│         │                                       │            │
│         │                          useSearch / useTaxonomy   │
│         │                          useSources (TanStack Query)│
│         │                                       │            │
│         │                              ┌────────▼─────────┐  │
│         └──────────────────────────────│  lib/api.ts      │  │
│                                        │  (fetch client)  │  │
│                                        └────────┬─────────┘  │
└─────────────────────────────────────────────────┼───────────┘
                                                   │ HTTP (CORS)
                                  ┌────────────────▼────────────────┐
                                  │  FastAPI (api/, port 8000)       │
                                  │  /api/search  /api/taxonomy      │
                                  │  /api/sources                    │
                                  │  → scripts/ pipeline + CSV mock  │
                                  └──────────────────────────────────┘
```

The FastAPI backend is unchanged. The browser is a pure client of its JSON API.

---

## 3. State strategy — the Streamlit → React mapping

We split what Streamlit jammed into `st.session_state` into two layers with
clearly different responsibilities:

| Streamlit concept | React replacement | Lives in |
|---|---|---|
| `st.session_state["search_query"]`, `search_panel_open`, `active_tab`, `use_kingdom_routing`, `source_{key}` checkboxes, `debug_mode` | **Zustand store** (`lib/store.ts`) — plain UI state, synchronous, no re-run needed | client memory |
| `st.session_state["search_results"]` (the queried DataFrame) | **TanStack Query** cache (`useSearch`) keyed by `(query, useRouting)` | query cache |
| `@st.cache_resource` `TaxonRouter`, `@st.cache_data` | **TanStack Query** automatic request cache + `staleTime` | query cache |
| `_pending_source_updates` + deferred `st.rerun()` | _Nothing._ React state updates are synchronous and local; no re-run choreography exists | — |
| Per-source error (`st.error`) | `error` object from the query hook, rendered in-panel | component |
| "Did you mean?" fuzzy suggestions | 404 response body (`detail.available`) surfaced as clickable chips | component |

**Why two layers:** UI toggles (panel open, active view, which checkboxes) must
be instant and must not trigger network work — that's Zustand. Anything derived
from the server (results, taxonomy) is *server state* and belongs in a request
cache that dedupes, caches, and revalidates — that's TanStack Query. Conflating
the two is exactly what made the Streamlit version hard to reason about.

---

## 4. Data contract

The components consume the existing FastAPI JSON shapes (see `lib/types.ts`):

- `GET /api/sources` → `{ sources: string[] }` (source **keys**, e.g. `"gbif"`).
- `GET /api/search?query=&use_routing=&mock=true` →
  `{ query, sources: string[], results: SpeciesRecord[] }`, where each record is
  one flat row of the underlying CSV (snake_case columns: `api_name`, `genus`,
  `species`, `status`, `api_link`, `publication_year`, `author`,
  `publication_name`, rank columns, …).
- `GET /api/taxonomy?query=&mock=true` →
  `{ query, ranks, sources: [{ source, synonym_count, <Rank>: value }], disagreements }`.

> **Schema note.** The current Streamlit *master views* read title-case columns
> (`"Source Name"`, `"GBIF Accepted Status"`, `"Source Link"`, …), but the live
> FastAPI `/api/search` emits the snake_case CSV columns (`api_name`, `status`,
> `api_link`, …). The React client targets the **FastAPI contract**. The mapping
> between the two is isolated in one place — `lib/fields.ts` — so if the API's
> column names change, you edit a single file.

The Table, Timeline, and Node views transform `SpeciesRecord[]` on the client
(mirroring the logic in `view_table.py`, `view_timeline.py`, `view_node.py`).
The Taxonomic view consumes the already-shaped `/api/taxonomy` response
directly, so the disagreement logic stays server-side (single source of truth).

---

## 5. Component map (Streamlit file → React file)

| Streamlit | React | Notes |
|---|---|---|
| `prototype_master.py` (shell, columns, rerun loop) | `app/page.tsx` + `components/AppLayout` | Mantine `AppShell` with collapsible `navbar` = the left search panel |
| left search `st.form`, `Advanced options` expander, source checkboxes, `Select all` | `components/SearchPanel.tsx` | Mantine `TextInput` + `Button` + `Collapse` + `Checkbox` |
| `st.segmented_control("View", …)` | `components/ViewSwitcher.tsx` | Mantine `SegmentedControl` (1:1) |
| `view_table.py` | `components/views/TableView.tsx` | presence matrix, ✓ link cells, bold query row |
| `view_timeline.py` (Plotly) | `components/views/TimelineView.tsx` | `react-plotly.js`, dynamic import, ssr:false |
| `view_node.py` (pyvis iframe) | `components/views/NodeView.tsx` | **React Flow** (`@xyflow/react`) — native nodes, no iframe |
| `view_taxonomy.py` | `components/views/TaxonomyView.tsx` | consumes `/api/taxonomy`; red disagreement cells |
| `view_debug.py` | `components/views/DebugView.tsx` | raw record table |
| `st.session_state` | `lib/store.ts` (Zustand) + TanStack Query | see §3 |
| `@st.cache_*`, network | `lib/api.ts`, `lib/hooks.ts` | fetch client + query hooks |
| `scripts/...router`, `normalize_query_string` | stay in the backend | client never re-implements pipeline logic |

---

## 6. Library choices

- **Next.js (App Router) + TypeScript** — file-based routing, easy deploy, types
  across the API boundary.
- **Mantine v7** — chosen because the Streamlit widgets map almost one-to-one:
  `AppShell`(collapsible navbar) ↔ search panel, `SegmentedControl` ↔
  `st.segmented_control`, `Checkbox`/`TextInput`/`Tooltip`/`Table` ↔ the
  Streamlit equivalents. Lowest-friction faithful clone.
- **TanStack Query** — request cache / dedupe / revalidate; the principled
  replacement for `@st.cache_data`.
- **Zustand** — tiny global store for UI state (replaces the UI half of
  `st.session_state`).
- **React Flow (`@xyflow/react`)** — interactive node graph, replacing the pyvis
  HTML iframe with real React nodes (clickable, styleable, no sandbox).
- **react-plotly.js** — keeps the existing Plotly timeline logic almost verbatim.

---

## 7. Migration phases

1. **Stand up the shell (this scaffold).** Layout, search panel, view switcher,
   all five views wired to `mock=true`. Validate the UX clone against Streamlit.
2. **Harden the data contract.** Add a `/api/search` source-filter param so the
   server (not the client) honors deselected sources when routing is off; add a
   `/api/suggest` endpoint exposing `fuzzy_search` for proper "Did you mean?".
3. **Flip to live data.** Implement `_live_search` in the backend; the frontend
   only flips `mock=false` — no UI changes.
4. **Polish + deploy.** Loading skeletons, error boundaries, responsive layout;
   deploy frontend (Vercel/static) + backend (container) with env-based API URL.
5. **Retire Streamlit.** Keep `app/` in `deprecated/` until the React app reaches
   feature parity in production.

---

## 8. Running it

See `frontend/README.md`. In short: run FastAPI on :8000, then `npm install &&
npm run dev` in `frontend/` and open http://localhost:3000.
