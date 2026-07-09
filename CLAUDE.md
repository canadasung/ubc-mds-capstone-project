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

## Adding a new API source

Checklist (last done for PBDB and MycoBank) — all of these must be updated,
not just the client file:

1. `scripts/apis_pipe/<name>.py` — the `SpeciesAPI` subclass (see
   `scripts/apis_pipe/base.py` for the five-method contract).
2. `scripts/config.py` — add an `APIPortal` entry and list it in `ALL_PORTALS`.
3. `scripts/utils/router.py` — add the portal's display name to the relevant
   kingdom list(s) (`ANIMALIA_APIS` / `PLANTAE_APIS` / `FUNGI_APIS`).
4. `scripts/utils/call_apis_pipe.py` — register `display_name -> ClientClass`
   in `_PORTAL_REGISTRY`.
5. `frontend/lib/sources.ts` — add a `SourceDef` entry. **If `label` differs
   from `backendName`, add `aliases: [backendName]`.** `keyForApiName()`
   matches a record's `api_name` against `label`/`aliases`, not `backendName`
   — without the alias, results resolve to a key nothing recognizes and get
   silently filtered to zero with no visible error. (Hit this exact bug with
   PBDB: label `"PBDB"` vs backendName `"Paleobiology Database"`.)
6. `tests/fixtures/queries.py` — add an `accepted`/`synonym`/`not_found` entry.
7. `tests/fixtures/_fetchers.py` — add a `<name>_fixtures()` generator and
   list it in `ALL_FETCHERS`.
8. `tests/scripts/apis_pipe/test_<name>.py` — subclass `BaseApiTest`.
9. Generate real fixture data with `python tests/fixtures/regenerate_fixtures.py`
   rather than hand-writing fixture JSON — it exercises the real client
   against the live API and catches integration bugs the unit tests can't.
   **Then `git add` the new `tests/fixtures/<name>/` directory explicitly** —
   it's easy to run the script, see it work locally, and forget the files
   are untracked until CI or a fresh clone fails with `FileNotFoundError`.
   Run `git status --short tests/fixtures/<name>/` to confirm before calling
   the feature done.

For sources needing credentials beyond a simple key (OAuth2, etc.): validate
eagerly in `__init__` and raise `ValueError` if missing (see
`scripts/apis_pipe/tropicos.py`, `scripts/apis_pipe/mycobank.py`). Never ask
the user to paste credentials into chat — write a throwaway probe script they
run locally against their own `.env` values (writing output to a file if
it's long) so real response shapes can be inspected without exposing secrets.
If the source needs per-call dynamic headers (bearer tokens, custom Accept
negotiation) that `SpeciesAPI._fetch`/`_fetch_JSON` can't express, consider
whether the base class should grow an optional `headers` override instead of
the client reimplementing the request/error-handling stack from scratch —
check whether another existing client already hit the same wall before
assuming it's a one-off.

Don't guess field names, auth flows, or endpoint behavior for an external
API. Look for an OpenAPI/Swagger spec first — sometimes at a predictable
path, sometimes embedded in a Scalar/Swagger-UI page's JS config even when
the rendered page itself shows no visible content (check the raw HTML, not
just a rendered fetch). If no docs are reachable, get the user to run a probe
script against the real API before writing the client.

**Test the case where the query resolves to a synonym whose own record
contains a full, self-referencing synonym network** (not just a pointer up
to the accepted name) — some APIs (MycoBank) return the entire synonym group,
including the queried record itself, inside the hit's own `synonymy` block.
A naive implementation that says "skip resolving this id, it's the same as
what we already have" for the record's own id will silently drop the exact
name the user searched for from the output, while still returning the
accepted name and every *other* synonym — so nothing looks obviously broken
in a casual test. `BaseApiTest`'s standard scenarios don't assert that the
searched synonym name itself appears in the result, so this class of bug can
pass the whole test suite; write an explicit assertion for it when a source's
data model makes self-reference possible.

## Claude Code skills

Step-by-step playbooks for this project's recurring tasks live as Claude Code
Skills under `.claude/skills/` — invokable directly (`/add-api-source`, etc.)
or auto-triggered when the matching task comes up. They reference this file
for conventions rather than duplicate them, so update both if a workflow
changes.

- `add-api-source` — integrating a new external taxonomic data source.
- `update-readme` — keeping the three README files accurate.
- `deploy` — pushing frontend/backend changes live (Vercel + Hugging Face).
- `update-claude-md` — capturing a new lesson/gotcha into this file.
- `debug-hydration-mismatch` — diagnosing React/Next.js SSR-vs-client bugs.
- `refresh-fixtures` — checking recorded test fixtures against live APIs for
  upstream drift, not just when adding a new source.

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
