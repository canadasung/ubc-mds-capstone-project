---
name: update-readme
description: Update this project's README files (root README.md, huggingface_readme.md, frontend/frontend_readme.md) so they accurately describe the current state of the code. Use this whenever the user asks to update, review, sync, or fix the README, docs, or documentation, or after a feature/source/deployment change that the README doesn't reflect yet — new API sources, new endpoints, changed project structure, new credentials, new deployment steps.
---

# Update README documentation

This project has **three** README-style files, each with a distinct
audience and a distinct set of files it must stay in sync with. Before
editing, identify which one(s) are actually affected — most changes only
touch one.

| File | Audience | Kept in sync with |
|---|---|---|
| `README.md` (root) | Anyone browsing the repo | Data Sources list, Field availability table, Project Structure tree, Credentials section, Deployment section, Pipeline Design checklist |
| `huggingface_readme.md` | Whoever manages the deployed backend Space | Backend endpoints, credentials required for live sources, `ALLOWED_ORIGINS` CORS setup. **Needs valid HF Space YAML frontmatter** (title/emoji/colorFrom/colorTo/sdk/app_port) since this file becomes the Space's actual `README.md` when copied over — see the `deploy` skill. |
| `frontend/frontend_readme.md` | Frontend contributors | `frontend/` layout, local-run steps, deployment section |

## Reference material for accuracy

Don't describe behavior you haven't confirmed. Read the actual current code
before writing a claim about it, especially:

- `scripts/apis_pipe/base.py`, `scripts/config.py`, `scripts/utils/schema.py`,
  `scripts/utils/router.py`, `scripts/utils/call_apis_pipe.py` — pipeline
  behavior and the source registry.
- Each client's own docstring under `scripts/apis_pipe/` (e.g. `col.py`,
  `gbif.py`, `pbdb.py`) — each documents its own "Fields implemented" section;
  this is the ground truth for the root README's field-availability table,
  not a guess.
- `backend_api/routers/*.py` — the actual endpoint list and behavior.
- All of `frontend/` — component structure, for the frontend README's layout
  section.
- `tests/` — for the Tests section (unit vs. integration split, fixture
  regeneration commands).

If something in the README can't be verified against the code (e.g. a
citation format, an external org's exact name), say so rather than inventing
it.

## Writing rules

These apply to every README file and to any docstrings touched along the way
(this project's `CLAUDE.md` states these project-wide, restated here since
they're easy to slip on mid-edit):

- No em-dashes, no emoji, anywhere in the file.
- Professional, neutral, direct tone. No excessive adjectives.
- Concise and precise — say what's true, not what sounds impressive.
- Python docstrings encountered along the way: NumPy style, concise,
  jargon-free.

## Process

1. Confirm which of the three files are actually in scope for the change —
   don't touch all three by default.
2. Read the current content of each in-scope file in full before editing, so
   additions match the existing section structure and heading style rather
   than being bolted on at the end.
3. Cross-check every factual claim (source lists, field tables, endpoint
   lists, file trees) against the current code, not against what the README
   used to say.
4. Show line numbers when describing the edits you're making.
5. If you're revising a section that lists "how to add a new source" or
   similar process documentation, keep it in sync with the `add-api-source`
   skill and CLAUDE.md's own checklist — these have drifted out of sync with
   the actual code before (missing steps for `router.py` registration and
   fixture-commit reminders were both found missing from an older README
   revision in this project's history).
