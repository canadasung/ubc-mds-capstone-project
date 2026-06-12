---
title: Species Synonym API
emoji: 🍄
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Species Synonym API

FastAPI backend for the Beaty Biodiversity species-name synonym tool. Serves the
`/api/search`, `/api/sources`, and `/api/taxonomy` endpoints consumed by the
Next.js frontend (hosted separately on Vercel).

Currently serves the bundled sample data (`data/sample/*.csv`) via `mock=true`.

## CORS

Set the `ALLOWED_ORIGINS` Space variable to a comma-separated list of frontend
origins allowed to call this API, e.g.:

```
ALLOWED_ORIGINS=http://localhost:3000,https://your-app.vercel.app
```

> **Note:** when pushing to the Space, this file becomes the Space's `README.md`
> (the HF frontmatter above configures the Docker runtime). It is kept as
> `README.hf.md` in the source repo so it doesn't clash with the project README.
