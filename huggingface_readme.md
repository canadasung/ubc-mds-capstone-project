# Species Synonym API

FastAPI backend for the Beaty Biodiversity species synonym tool. It wraps the
Python pipeline in `scripts/` and serves the JSON endpoints consumed by the
Next.js frontend (hosted separately on Vercel).

## Endpoints

- `GET /api/search`: synonym search. Reads bundled sample data by default (`mock=true`).
- `GET /api/search/stream`: live source-by-source search, streamed as Server-Sent Events.
- `GET /api/suggest`: recommended sources for a name, routed by kingdom via GBIF.
- `GET /api/sources`: list of known source keys.
- `GET /api/taxonomy`: per-source taxonomy comparison. Reads bundled sample data by default (`mock=true`).

`/api/search` and `/api/taxonomy` serve the bundled sample data
(`data/sample/*.csv`) by default. Live results come from `/api/search/stream`,
which calls the external biodiversity APIs directly.

## Credentials

Live search needs no credentials for most sources. Tropicos requires a registered
API key: set `TROPICOS_API_KEY` as a Space secret to include Tropicos in live
results. Without it, Tropicos is skipped and the other sources are unaffected.

## CORS

Set the `ALLOWED_ORIGINS` Space variable to a comma-separated list of frontend
origins allowed to call this API, e.g.:

```
ALLOWED_ORIGINS=http://localhost:3000,https://your-app.vercel.app
```

> **Note:** when pushing to the Space, this file becomes the Space's `README.md`
> (the HF frontmatter above configures the Docker runtime). It is kept as
> `README.hf.md` in the source repo so it does not clash with the project README.
