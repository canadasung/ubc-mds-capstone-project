# CLAUDE.md

Project guidance for Claude Code sessions working in this repo. Loaded
automatically at the start of each session.

## What this is

A biodiversity **Species Name Synonym Search** web app. A user enters a
scientific name and the app aggregates accepted names and synonyms from many
taxonomic data sources (Catalogue of Life, GBIF, Symbiota portals, Tropicos,
NCBI/Entrez, etc.), then presents them through several views (Overview, Detail,
Timeline, Relations, Taxonomy).

Originally built as a UBC MDS capstone for the Beaty Biodiversity Museum.

## Architecture

- **Frontend** (`frontend/`): Next.js (App Router) + React + Mantine v7 +
  TanStack Query + Zustand. Reads the backend URL from
  `NEXT_PUBLIC_API_BASE_URL` (see `frontend/.env.local.example`).
- **Backend** (`backend_api/`): FastAPI. App object is `backend_api.main:app`.
  Routers in `backend_api/routers/` (`search.py`, `taxonomy.py`).
- **Pipeline** (`scripts/apis_pipe/`): the API-client layer. `base.py` defines
  the `SpeciesAPI` abstract base class; each source (e.g. `col.py`) subclasses
  it. `get_synonyms` returns `accepted + synonyms` rows in a standard schema.
- `tests/` holds the pytest suite (config in `pyproject.toml`).
- `reports/` holds the final report (Quarto/markdown).
- `deprecated/`, `app/`, `notebooks/` are older prototypes/artifacts. The
  untracked `api/` directory is a stale leftover (the live app is in
  `backend_api/`).

## Running locally

Use the **`mds-project`** conda env (the `base` env lacks fastapi; system
Python has nothing). Env defined in `environment.yml`.

```bash
# Backend (from repo root, in the mds-project env)
uvicorn backend_api.main:app --reload --port 8000

# Frontend (from frontend/)
npm install        # first time, or after switching branches with different deps
npm run dev        # http://localhost:3000
npm run typecheck  # tsc --noEmit — run before considering frontend work done
```

## Secrets / environment

- Real secrets live in a gitignored **`.env`** (root) and
  **`frontend/.env.local`**. Templates: `.env.example`,
  `frontend/.env.local.example`. Never commit real values; never print them.
- Backend keys used: `ENTREZ_EMAIL`, `TROPICOS_API_KEY` (free), and an
  Anthropic key for kingdom detection in the Suggest feature. See `.env.example`
  for the up-to-date list.
- History has been scanned: no real `.env` and no hardcoded API keys were ever
  committed (only `.example` templates). Keep it that way.

## Conventions

- **Python docstrings: NumPy style.**
- **No em-dashes** and **no emoji** in code, docstrings, or report prose.
- Match the surrounding code's style (Mantine `size` props, naming, comment
  density).
- `@tabler/icons-react` resolves to a **local type shim** at
  `frontend/types/shims.d.ts`. An icon must be declared there or `tsc` fails
  with "has no exported member" — add `export const IconName: Icon;` when using
  a new icon.
- The COL client pins `DATASET_KEY` (currently COL26.5 = `315192`) in
  `scripts/apis_pipe/col.py`; update it when a newer COL release ships.

## Workflow

- Don't commit or push unless asked. If on `main`, branch first.
- Run the app / Playwright-screenshot to verify frontend changes (see the
  user's personal memory notes for the verify loop).

---

## Personal-project continuation notes

Plan for continuing this as a solo personal project (separate from the original
org repo).

### Provenance and licensing
- Continued from the UBC MDS capstone (original team: William Song, Molly
  Kessler, Wendy Frankel, Johnson Chuang). The solo continuation is William's
  own work; keep the original team credited in the README.
- Get written authorization from the org before public deployment, and keep a
  `LICENSE` (MIT is fine) in the public repo.
- Start from the public mirror of the repo, not the private org repo. Tag the
  as-delivered capstone state as a baseline, then develop on a branch.

### Secrets
- Assume the original keys (org/school accounts) are gone. Obtain personal API
  keys. Set them as platform environment variables in production; keep `.env`
  gitignored and `.env.example` current.

### Deployment architecture
- **Frontend -> Vercel** (already wired; repo has empty Vercel-deploy commits).
- **Backend (FastAPI + pipeline) -> Render / Railway / Fly.io**, not Vercel
  serverless: the pipeline makes many slow upstream API calls and would hit
  serverless timeouts. An always-on container fits better.
- Wire them with env config: frontend `NEXT_PUBLIC_API_BASE_URL` -> deployed
  backend URL; backend CORS -> allow the Vercel domain.
- Production risk is flaky upstream sources; the failed-source banner already
  surfaces this. Consider caching / rate-limit handling.

### Decoupling checklist before going public
- Replace any hardcoded `localhost` / port `8000` with env config.
- Remove org-specific names, internal URLs, and museum-specific branding not
  cleared for reuse.
- Note in README that pinned dataset keys (e.g. COL `DATASET_KEY`) need periodic
  updates.

### Solo workflow that still looks professional
- Protect `main`; use feature branches + PRs even when solo.
- Wire the pytest suite into GitHub Actions so the green check shows.
- README: what it does, screenshot/GIF, live demo link, local-setup steps,
  architecture diagram.
