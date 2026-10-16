# QA + Studio Configs

This directory holds the v2 QA and media-studio contracts.

- `sites/<name>.yaml` — per-site QA contract consumed by the `ui-audit` and
  `site-health` skills (and referenced by `storyboard-recorder` via `media_root`).
- `templates/tutorial-storyboard.yml` — storyboard template for
  `shot-scraper video` screencasts.
- `templates/narration-brief-fa.md` — Persian narration brief template for the
  human-narration (`human-fa`) mode of `tutorial-script`.

## Rules

1. Anything marked `TODO(user)` needs Ehsan's confirmation before first run.
2. Production URLs are excluded from automated checks; at most they appear in a
   report as a manual-check pointer.
3. All artifact roots live on drive D: (`D:\Media\…`, `D:\AI-Control\…`).
   Never write tools, caches or outputs to C:.
4. Auth via storage-state JSON staged by the reviewer (WAMP-local only);
   passwords never appear in these YAML files.

## Contract schema

| Field | Meaning |
|---|---|
| `site` / `kind` | identifier + site type (wordpress, node, video-studio) |
| `base_urls` | local origins to audit (WAMP vhosts / dev servers) |
| `auth` | `storage_state` path or `none` |
| `routes` | pages to audit: `path` + `wait_for` selector |
| `viewports` | screenshot matrix widths (full-page shots per route) |
| `checks` | `screenshots`, `console`, `lighthouse`, `links`, `visual_regression` |
| `outputs` | `artifacts` (support\qa), `report_dir` (reports), `media_root` (D:\Media\<project>\tutorials) |
