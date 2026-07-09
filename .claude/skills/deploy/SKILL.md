---
name: deploy
description: Deploy or update the live frontend (Vercel) and backend (Hugging Face Space) for this project, or diagnose why a deployed change isn't showing up live. Use this whenever the user asks about deploying, going live, pushing to production, updating Vercel or Hugging Face, setting deployment secrets/environment variables, or reports that a live site doesn't reflect a recent code change.
---

# Deploy the frontend and backend

This project deploys to **two independent systems that do not know about
each other**. Most deployment confusion in this project has come from
treating them as one pipeline when they aren't — get this distinction right
first, before touching any files or settings.

| | Frontend | Backend |
|---|---|---|
| Host | Vercel | Hugging Face Space (Docker) |
| Source | This GitHub repo, root dir set to `frontend/` | A **separate git repository** at `huggingface.co/spaces/...`, unrelated to this GitHub repo |
| Deploy trigger | Automatic, on push to whichever branch is set as Vercel's Production environment (commonly `main`) | Manual: copy files into a local clone of the Space repo and `git push` there |

**The single most common failure mode**: pushing/merging to `main` on GitHub
updates Vercel automatically, but does **nothing** to the Hugging Face
Space. If a backend code change (new API source, bug fix in `scripts/` or
`backend_api/`) needs to go live, the manual copy-and-push step below is
required regardless of what happened on GitHub.

## Frontend (Vercel)

Already wired up; normally nothing to do beyond merging to the production
branch. If setting up fresh or troubleshooting:

- Root Directory must be `frontend`.
- `NEXT_PUBLIC_API_BASE_URL` is a Vercel **Environment Variable** (Project
  Settings, not committed to `.env.local`), pointing at the live backend URL.
- Vercel auto-deploys only the branch configured as its Production
  environment. Pushes to other branches produce Preview deployments, which
  is expected, not a bug, if the user reports "the live site didn't update"
  right after pushing a feature branch.

## Backend (Hugging Face Space)

The Space's git repo is a **separate local clone** from this project (e.g.
`~/Documents/GitHub/species-synonym-api`, sibling to this repo, not inside
it). To update it:

```bash
cd /path/to/this/repo
cp Dockerfile requirements.txt /path/to/species-synonym-api/
rm -rf /path/to/species-synonym-api/backend_api && cp -r backend_api /path/to/species-synonym-api/
rm -rf /path/to/species-synonym-api/scripts && cp -r scripts /path/to/species-synonym-api/
rm -rf /path/to/species-synonym-api/data && cp -r data /path/to/species-synonym-api/

cd /path/to/species-synonym-api
git add .
git commit -m "<describe the backend change>"
git push
```

**Do not copy:**
- `huggingface_readme.md` over the Space's own `README.md` — the Space's
  `README.md` carries the HF YAML frontmatter (`title`/`sdk`/`app_port`/etc.)
  that configures the Docker runtime itself; overwriting it with the plain
  project doc breaks the Space's configuration. Only touch it deliberately
  when updating the Space's description text, and keep the frontmatter.
- `.env` or `.env.example` — credentials go in the Space's own **Settings ->
  Variables and secrets** UI, never as a committed file.

**Only `backend_api/`, `scripts/`, or `data/sample/` changes require this
manual step.** Changes under `tests/`, root `README.md`, `CLAUDE.md`, or
anything frontend-only never need it — either they don't affect the running
Space, or (frontend files) Vercel already picked them up automatically.

### Setting credentials on the Space

Every credential a new API source needs (see the `add-api-source` skill)
must be added here too, or that source will fail live even if it works
locally with `.env`.

- **Secrets vs. Variables**: use Secrets for anything that is, or is paired
  with, a real login credential (an API key, or an email+password pair used
  for OAuth) — even if one half of the pair (e.g. a bare contact email like
  `ENTREZ_EMAIL`, which authenticates nothing and unlocks no account) would be
  harmless as a plain Variable on its own. Judge each credential by what it
  grants access to, not by whether it looks like "just an email address".
- **Type the raw value with no surrounding quotes.** The Secrets/Variables
  UI is a plain text field, not a `.env` parser — `.env.example` may show
  `KEY="value"` for local-file syntax, but typing the quote characters into
  the Space's web form makes them part of the literal value. This has caused
  a real, confusing OAuth failure in this project (400 error on a token
  endpoint) that looked like a credentials problem but was actually stray
  quote characters sent as part of the password.
- After adding or changing secrets, confirm the Space actually restarted
  (check the **Logs** tab for a new startup timestamp); if it looks stale,
  use the manual **Restart Space** action.

## Verifying a deploy

After either side redeploys:

1. Hit `https://<space>.hf.space/docs` and confirm the FastAPI Swagger UI
   loads — confirms the backend container is up at all.
2. From the live frontend, run a real search that exercises the specific
   thing that changed (a new source, a bug fix) and check the Network tab
   for the actual `/api/search/stream` response, not just that the page
   loads.
3. If a specific source shows as failed in the UI, the failed-source banner
   plus the browser's Network tab response body usually names the real
   underlying error (bad credentials, upstream API outage, etc.) — check
   that before assuming the deploy itself is broken.
