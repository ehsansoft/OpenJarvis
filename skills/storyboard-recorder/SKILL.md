---
name: storyboard-recorder
description: Turn a tutorial script into a shot-scraper video storyboard and record deterministic local browser screencasts.
version: 0.1.0
author: Ehsan OpenJarvis
---

# Storyboard Recorder

Record a browser screencast from a `storyboard.yml` using `shot-scraper video`
(v1.10+, June 2026). Deterministic, re-recordable, cursor-overlaid. Fallback:
Playwright context video recording (`recordVideo`) when the CLI is unavailable.

## Prerequisites (approval-gated)

- Tool availability first: `uvx shot-scraper video --help` — only after the
  reviewer approved the install and it landed on D: (uv cache redirected via
  `UV_CACHE_DIR=D:\AI-Control\caches\uv`).
- Local site reachable (WAMP flows start manually; approval gate).

## Storyboard build

- Source: the approved `tutorial-script` scene list — one storyboard scene per
  script scene, same order, same ids.
- Template: `configs/qa/templates/tutorial-storyboard.yml`. Key fields:
  `output`, `viewport` (default 1280×720), `cursor: true`, `server` (optional
  auto-start commands for node pilots; empty for WAMP), `scenes[].do` with
  `open / click / fill / wait_for / pause`.
- Placeholders: `{{BASE_URL}}`, `{{PROJECT}}`, `{{DATE}}`, `{{SLUG}}`.
- Selectors prefer stable text/roles/ids over CSS positions; if a scene flakes,
  make the selector stronger rather than adding fixed sleeps.

## Recording rules

- Demo data only: seed a demo dataset; never show real customer/personal data.
- Auth: WAMP-local admin only, staged as a storage-state JSON by the reviewer;
  never embed passwords in the YAML.
- Production sites: recording needs per-session explicit approval; default no.
- Pacing: 0.5–0.8 s pauses around actions; wait for a visible state change;
  2 s lead-in and a short settle at the end for trimming.
- Naming: `D:\Media\<project>\tutorials\raw\<date>-<slug>-take1.webm`
  (`shot-scraper video --mp4` for the handoff copy). Nothing leaves D:.

## Verification

- Watch the take once end-to-end: every script scene appears, in order; total
  duration within ~10% of the script target.
- Produce a scene list with timecodes for the board task and hand off to
  caption-sync + assembly (ffmpeg concat or the project's Remotion stack).

Instruction-only workspace procedure. No executable resources or additional authority.
