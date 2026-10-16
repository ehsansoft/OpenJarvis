---
name: ui-audit
description: Run the per-site QA contract — responsive screenshot matrix, console errors, Lighthouse and link checks — read-only and local-first.
version: 0.1.0
author: Ehsan OpenJarvis
---

# UI Audit

Execute the QA contract in `configs/qa/sites/<site>.yaml`. Read-only: never
submit forms, never write to any site, database or CMS.

## Scope rules

- Local WAMP vhosts and local dev servers only. Production URLs are excluded
  from automated runs; they may appear in reports as manual-check pointers.
- Runners (all after install approval, all storage on D:): Playwright with
  `npm_config_cache=D:\AI-Control\caches\npm` and
  `PLAYWRIGHT_BROWSERS_PATH=D:\AI-Control\caches\playwright`; Lighthouse CLI via
  `npx lighthouse --output=json`; optional in-page axe-core scan for detailed
  a11y rules (axe-cli itself is deprecated upstream).

## Checks

1. Responsive matrix: contract viewports (default 360/768/1024/1440/1920),
   full-page screenshots, horizontal-overflow flag per viewport.
2. Console: per page, split page errors vs failed requests vs CSP/429 noise.
3. Lighthouse: performance / accessibility / best-practices / seo — scores plus
   failing audits keyed to each route in the contract.
4. Link check: bounded crawl (depth ≤ 2, ≤ 50 pages) — status codes, redirect
   chains, mixed content.
5. Optional visual regression: pixelmatch baseline diff when the contract
   enables it; baselines live in `support\qa\baselines\<site>\`.

## Outputs

- Artifacts: `D:\AI-Control\OpenJarvis\support\qa\<date>-<site>\`
  (`screenshots\`, `lighthouse\`, `console\`, `links.json`, `report.json`).
- Report: `reports\<date>-qa-<site>.md` — summary table (viewports × pages),
  top issues with evidence paths, Lighthouse trend vs the previous run, and a
  short "fix first" list feeding `css-fix-evidence`.
- Narrative polish uses `openjarvis/local-fast` only; no remote models for
  private sites.

## Discipline

- Run when the box is idle; one site at a time, sequential; never alongside
  heavy local model jobs (Lighthouse is CPU-hungry).
- Every run is one board task; report first, interpretation second.

Instruction-only workspace procedure. No executable resources or additional authority.
