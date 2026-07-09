---
name: update-claude-md
description: Capture a lesson learned, gotcha, or newly-discovered convention into this project's CLAUDE.md so future sessions don't rediscover it the hard way. Use this whenever the user says something like "remember this", "update CLAUDE.md", "capture this for next time", "note this gotcha", or right after you (Claude) personally spent real effort discovering a non-obvious bug, footgun, or convention that isn't already documented — even if the user doesn't explicitly ask, proactively suggest adding it.
---

# Update CLAUDE.md with a new lesson

`CLAUDE.md` is loaded into every session automatically. Its value is
proportional to how many real, hard-won lessons it captures versus how much
is generic advice a model would already know — so the bar for adding
something is "this cost real debugging time and would cost it again," not
"this is a nice-to-know fact."

## When to add something

Good candidates (all of these actually happened in this project):

- A bug that passed the whole test suite but was still wrong (e.g. a source
  silently dropping the exact name the user searched for).
- A silent-failure mode with no error message pointing at the cause (e.g. a
  frontend key mismatch that filters results to zero with nothing in the
  console).
- A gotcha specific to a third-party library or API's actual behavior, not
  its documented behavior (e.g. an OAuth token endpoint returning 400 for bad
  credentials, or a value field expecting no surrounding quotes).
- A workflow step that's easy to forget precisely because nothing errors
  when it's skipped (e.g. fixture files existing locally but never
  committed).

Bad candidates: things Claude would already know from training (general
Python/React/git knowledge), one-off decisions with no recurring relevance,
or content that duplicates what's already in a `.claude/skills/*/SKILL.md`
(link to the skill instead of repeating its content).

## Where it goes

`CLAUDE.md` is organized by topic, not chronologically. Find the existing
section the lesson belongs to (Conventions, Adding a new API source,
Workflow, etc.) and add it there, in the voice of a rule with its reason
attached — not a changelog entry. Compare:

- Bad: "On 2026-07-04 we fixed a bug where MycoBank synonyms were dropped."
- Good: "Test the case where the query resolves to a synonym whose own
  record contains a full, self-referencing synonym network... A naive
  implementation... will silently drop the exact name the user searched for."

If the lesson doesn't fit any existing section and represents a new
recurring category of task, consider whether it should become its own
`.claude/skills/` entry instead (see that convention) rather than growing
CLAUDE.md indefinitely — CLAUDE.md is for standing conventions and gotchas,
skills are for step-by-step procedures.

## Keep it tight

- State the rule, then the concrete failure scenario that justifies it, in
  1-3 sentences. Don't narrate the debugging session that led to it.
- If a `.claude/skills/*/SKILL.md` already covers the same workflow, add a
  one-line pointer there rather than duplicating the fix in both places —
  CLAUDE.md and the skills should never disagree about the same procedure.
- Re-read the section you're editing in full before appending, so the
  addition matches its existing voice and doesn't repeat something already
  stated two paragraphs up.
