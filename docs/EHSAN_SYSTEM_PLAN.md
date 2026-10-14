# Ehsan system plan — OpenJarvis + Hermes + editors (2026-10-14)

One page for the whole system: what runs today, who owns what, and the
ordered roadmap.

## 1. Architecture (as built)

```
                 +---------------- OpenJarvis server (127.0.0.1:18080) ----------------+
                 |  scheduler | memory | approvals | Telegram (one bot) | model gateway |
                 +--------------------------------------------------------------------+
                    ^                ^                  ^                  ^
   dashboard (10 aliases,   /router/v1/* (editors: 41 ids: 3 Ollama + 10 aliases
   3 Ollama, 14 kilo/*,     + 14 kilo/* + 9 opencode/* + 5 ByNara raw)
   9 opencode/*)
                    |                |                  |                  |
             OpenJarvis UI     OpenCode CLI        Kilo Code         Hermes profiles
                                (opencode/*)       (kilo/*)          (12 role bots)
```

- **OpenJarvis** is the single owner of: scheduler/reminders, long-term
  memory, approval gates, the Telegram bot, and the model gateway.
- **Model tiers**: private/personal work runs local-only (Ollama
  qwen3.5:2b / qwen3-8b / qwen2.5-coder:7b, `local/*` aliases). Public or
  synthetic work may opt into free remote tiers per task: ByNara free pool,
  **Kilo Gateway** (keyless, 14 free models, `kilo/*`), **OpenCode relay**
  (official CLI, 9 free models, `opencode/*`).
- **Privacy law**: the gateway never sends memory/identity-injected context
  to remote tiers. Picking a `kilo/*` or `opencode/*` model IS the per-task
  opt-in; everything else stays fail-closed behind `private_routing`.
- **Hermes** runs 12 role profiles (all default to local qwen3.5:2b; any of
  them can use the gateway per task with `--provider openjarvis --model …`):
  coder, researcher, scout (info gathering), keeper (user/project knowledge),
  writer (articles), seo, plugindev (EhsanSoft/WordPress), webbuilder,
  newswire (news digests), translator (fa-IR), maintainer (ongoing dev),
  cleanup (disk reclaim, report-only).

## 2. Evidence status (2026-10-14)

- Regression sweep of every selectable model: **38/41 PASS** through the
  gateway; the 3 non-PASS were upstream conditions (Kilo 429 daily/provider
  rate limits, ByNara 502 outage), retried and documented in
  `support/guided-operations-20261012/model_regression_2026-10-14*.json`.
- Full Python suite: 1579 passed; only 5 pre-existing environmental
  failures (gemma_cpp live, credentials permissions).
- Hermes smoke: every profile answered through the gateway or local model.
- Disk: C: is critically low (3.4 GB free). Reclaim plan ready in
  `support/guided-operations-20261012/cleanup_report_2026-10-14.txt`
  (~8.3 GB safe-now caches, ~10.9 GB needs-decision). Report-only until
  approved item by item.

## 3. Roadmap (ordered)

1. **Daily tasks/reminders** — OpenJarvis scheduler owns them; add the first
   standing jobs: morning digest (newswire profile), disk report (cleanup
   profile, weekly), Ollama RAM hygiene (`ollama stop qwen3-8b` when idle).
2. **Telegram** — one bot token, wired into OpenJarvis only. Hermes bots run
   through the desktop app or profile gateways, never the same token. Goes
   live after the user completes the token step (manual gate open).
3. **Agent-to-agent** — OpenJarvis board is the bus: profiles read/write
   tasks there; coder and plugindev already report into the board. Next:
   scout → keeper handoff (facts found → durable knowledge) with explicit
   provenance.
4. **Cleanup execution** — after approval: run the four cache commands, then
   decide on hiberfil (powercfg), the two Downloads videos, and the
   qwen-tts-1.7B Voicebox model (~3.6 GB).
5. **Private-automation gates still open** (manual): Telegram live test,
   microphone/listening check, Hermes source review, research-answer quality
   review.

## 4. Operating rules (unchanged, restated)

- Private work → local Ollama only; public/synthetic → free pools with
  explicit per-task opt-in.
- No secrets in config files; keys live in env/user scope only.
- Cleanup/deletion is approval-gated: report first, human executes.
- Releases are never approved from static/mock checks alone (WampServer
  runtime evidence for EhsanSoft work).
