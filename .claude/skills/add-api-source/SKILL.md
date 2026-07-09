---
name: add-api-source
description: Add a new biodiversity/taxonomic data source (a new SpeciesAPI client) to the synonym-search pipeline. Use this whenever the user wants to integrate a new external species/taxonomy database or API into the project, wants to "add support for" a named organization's data, or gives you API docs/credentials for a new source to wire into the pipeline. Also use when the user asks to extend, register, or hook up a new data provider anywhere in scripts/apis_pipe/.
---

# Add a new API source

This project aggregates species-name synonyms from many external biodiversity
databases (GBIF, Catalogue of Life, PBDB, MycoBank, and others), each behind a
shared `SpeciesAPI` contract in `scripts/apis_pipe/base.py`. Adding a new
source means writing one new client file plus registering it in six other
places — skipping any one of them produces a client that works in isolation
but is invisible to the router, the pipeline, the frontend, or the test
suite, with no error to point at what's missing.

The canonical, battle-tested checklist for this lives in this repo's
**CLAUDE.md**, under "Adding a new API source" — it is already loaded into
your context every session, so treat it as the source of truth for the file
list, the credential-handling pattern, and the known gotchas (self-referencing
synonym networks, untracked fixture directories, etc.). This skill exists to
make sure that checklist actually gets *run*, end to end, in order, without
skipping steps under time pressure — reread CLAUDE.md's section now if it
isn't fresh in mind.

## Before writing any code

Ask the user (skip questions you can already answer from context):

1. **Which organization/database?** Get the exact name and, if they have it,
   a link to API docs.
2. **Do you have credentials already**, or does this source need an account?
   If credentials are needed, never ask the user to paste them into chat —
   write a throwaway probe script for them to run locally against their own
   `.env` (see "Probing an unfamiliar API" below).
3. Confirm you understand **which kingdom(s)** this source covers
   (Animalia/Plantae/Fungi/all) — this determines which `router.py` lists it
   joins.

## Probing an unfamiliar API

Do not guess field names, auth flows, or endpoint behavior. In order of
preference:

1. Look for an OpenAPI/Swagger spec — sometimes at a predictable path
   (`/openapi.json`, `/swagger.json`), sometimes embedded in a Scalar/Swagger-UI
   page's JS config even when the rendered page shows no visible content
   (fetch the raw HTML, don't just render it).
2. If the base URL returns an HTML shell with an embedded config object
   (common with Scalar-based docs), read that config for the real OpenAPI
   YAML/JSON path and fetch it directly.
3. If no docs are reachable this way, write a small probe script (using
   `requests`, writing output to a file if it's long) and have the user run
   it locally against their own credentials — never ask them to paste secrets
   into the conversation.
4. Test the "query resolves to a synonym" path explicitly during probing, not
   just the "query resolves to the accepted name" path — some APIs return a
   synonym's full sibling-synonym network (including a pointer back to
   itself) when you query the synonym directly, which is easy to get subtly
   wrong (see the CLAUDE.md gotcha about this).

## The six registration points

Implement the `SpeciesAPI` subclass first (see `scripts/apis_pipe/base.py`
for the five-method contract, and any existing client such as `col.py` or
`pbdb.py` as a worked example), then work through CLAUDE.md's numbered
checklist top to bottom:

1. `scripts/apis_pipe/<name>.py` — the client itself.
2. `scripts/config.py` — `APIPortal` entry + `ALL_PORTALS`.
3. `scripts/utils/router.py` — kingdom list membership.
4. `scripts/utils/call_apis_pipe.py` — `_PORTAL_REGISTRY` entry.
5. `frontend/lib/sources.ts` — `SourceDef` entry. **If `label` != `backendName`,
   add `aliases: [backendName]`** — forgetting this makes results resolve to
   a key nothing recognizes and get silently filtered to zero, with no
   visible error anywhere. This has bitten this exact project twice.
6. Test wiring: `tests/fixtures/queries.py`, `tests/fixtures/_fetchers.py`,
   `tests/scripts/apis_pipe/test_<name>.py` (subclassing `BaseApiTest`).

## Before calling it done

- Run `python tests/fixtures/regenerate_fixtures.py` to record real fixture
  data against the live API rather than hand-writing fixture JSON.
- **`git status --short tests/fixtures/<name>/`** and confirm the new fixture
  files are staged/committed, not left untracked. A feature that "works
  locally" but whose fixtures were never committed fails for anyone else
  (or CI) with a bare `FileNotFoundError`, with nothing in the diff pointing
  at why.
- Write an explicit test asserting that the *searched* name itself appears in
  the output when the query resolves to a synonym — `BaseApiTest`'s standard
  scenarios don't check this, so a source whose data model can
  self-reference can pass the whole suite while silently dropping the exact
  name the user searched for.
- Run `pytest -m "not integration" tests/` and confirm nothing else broke.
- Consider whether the new source needs a live smoke test end to end through
  `scripts/utils/call_apis_pipe.call_apis()`, not just the unit tests, since
  that's the actual code path the frontend calls.
