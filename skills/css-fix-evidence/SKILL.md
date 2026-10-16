---
name: css-fix-evidence
description: Bounded CSS/JS fixes with screenshot-based before/after acceptance; nothing is committed or deployed without approval.
version: 0.1.0
author: Ehsan OpenJarvis
---

# CSS Fix Evidence

Fix one bounded UI bug end-to-end with evidence: reproduce → patch local
sources → prove the fix with before/after screenshots.

## Contract (before touching code)

- One bug: route/URL, element selector, symptom, expected behavior — sourced
  from a `ui-audit` report or the reviewer.
- Repo + branch for the fix. Never edit produced/minified bundles: patch the
  source theme/plugin/component and rebuild if a build step exists.

## Procedure

1. Reproduce: capture the offending state in the matching viewport(s) from the
   site contract, plus console errors → `support\qa\<date>-<site>\baseline\`.
2. Diagnose read-only first (local models only for private repos, e.g.
   `openjarvis/local-code` via editor-delegate), then propose the minimal patch.
   Preference order: CSS → wrapper/custom properties → JS only when CSS cannot
   express the fix.
3. Implement in the repo (one editor per working directory at a time; no
   production writes, no production authentication).
4. Verify: clear whatever cache the flow needs (manual on WAMP), re-capture
   identical screenshots after changes → `…\after\`. Acceptance requires all of:
   visual diff resolved, no new console errors, overflow check passes on the
   affected viewports.

## Outputs

- Patch summary: diff, rationale, affected routes; before/after image paths;
  residual risks and follow-ups.
- Board task report. Commit only after explicit reviewer approval; deployment
  and production databases are always out of scope for the agent.

Instruction-only workspace procedure. No executable resources or additional authority.
