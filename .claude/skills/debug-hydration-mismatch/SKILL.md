---
name: debug-hydration-mismatch
description: Diagnose and fix a React/Next.js hydration mismatch in the frontend (errors like "Hydration failed because the initial UI does not match what was rendered on the server", "Text content does not match", or "Prop did not match. Server: ... Client: ..."). Use this whenever the user reports a hydration error, a runtime error popup only in the browser, UI that flickers or briefly shows wrong content on page load, or a bug that only reproduces for a *returning* visitor and not a fresh session.
---

# Debug a hydration mismatch

Next.js renders each page twice: once on the server (no `localStorage`, no
`window`, no cookies from a returning visit) and once on the client during
hydration. If any component's rendered output depends on browser-only state,
the two renders can disagree, and React throws a hydration error — often
pointing at a component several layers removed from the actual cause, since
the mismatch is only detected where React first notices the DOM doesn't
match what it expected.

This project already hit this bug twice in one feature (a dark-mode toggle):
once from branching an icon's JSX on a color-scheme hook whose value differs
between server and client, and once from nesting a heading component inside
a Modal's own title element (an unrelated cause, but the same symptom). Don't
assume the fix is always about `localStorage` — read the actual error's
component stack first.

## Reproducing it reliably

The bug frequently **will not reproduce on a fresh page load** — it only
shows up for a visitor who already has some persisted browser state (a
`localStorage` value, a cookie, a `matchMedia` result) that differs from the
server's default assumption. A plain `curl` or fresh incognito tab often
looks fine. Simulate the real failing case directly:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

    page.goto("http://localhost:3000")
    page.wait_for_timeout(500)
    # Seed the exact persisted state a returning visitor would already have.
    page.evaluate("localStorage.setItem('some-key', 'some-value')")

    errors.clear()
    page.reload()  # the reload is what exposes the mismatch
    page.wait_for_timeout(2000)

    for e in errors:
        print(e)
    browser.close()
```

Read the **first** "Prop did not match. Server: ... Client: ..." warning in
the output and its component stack trace (printed just above/below it) —
that names the actual component and the actual differing values, which is
far more precise than the generic "Hydration failed" summary that follows it.

## The fix pattern, not just the symptom

Do not silence the warning (`suppressHydrationWarning` on the mismatched
element hides the symptom but the underlying wrong-content-on-first-paint
bug, and any real logic bug behind it, both remain). Instead, make the very
first client render match the server, one of two ways:

1. **If the differing output is presentational** (e.g. which of two icons is
   shown): render *all* variants unconditionally so server/client markup is
   always textually identical, and switch visibility purely via CSS keyed
   off an attribute that's already set correctly before hydration (e.g.
   Mantine's `[data-mantine-color-scheme]`, set synchronously by
   `ColorSchemeScript` in `<head>`). See
   `frontend/components/ColorSchemeToggle.tsx` and the corresponding rules in
   `frontend/app/globals.css` for the worked example in this project.
2. **If the differing output requires an effect** (state that's genuinely
   only knowable client-side, with no such attribute available): initialize
   state to the server-safe default, and update it in `useEffect` after
   mount, accepting a one-frame flash rather than a mismatch.

Also check for **invalid HTML nesting**, a different but common cause of the
same error class: a component that renders its own heading/paragraph
wrapper (e.g. Mantine's `Modal` `title` prop, which already renders an
`<h2>`) will produce invalid markup like `<h2><h4>...</h4></h2>` if you pass
it another heading component instead of plain text/inline content — browsers
silently "fix" this by moving the DOM around, which is itself a hydration
mismatch. The fix is to pass plain content, not a re-fix by re-wrapping it
later (this exact regression risk is why `frontend/components/TutorialModal.tsx`
has a comment at its `title={...}` call site warning against re-adding a
heading wrapper).

## After fixing

Re-run the same Playwright reproduction script with the same seeded state
and confirm zero console/page errors, not just that the page visually looks
right — a hydration error can occur even when the final rendered result
looks correct, because React discards and fully re-renders client-side on
mismatch, which is itself the bug (lost event handlers, double-fetch, visible
flash) even if the end state happens to look fine in a screenshot.
