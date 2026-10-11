# Practical local workflows — 2026-10-11

Dashboard added and verified across the October 11–12 session:
`http://127.0.0.1:18080/control`. See `docs/EHSAN_CONTROL_DESK.md`.

Runbook marker: EhsanWorkstationRunbook20261011.

## Completed cleanup

The user approved the previously reviewed three-path batch. It removed only
CVI `.render-tmp` and the two specified webpack caches. The receipt records
26.58 GiB recovered and D: free space rising from 18.41 to 44.99 GiB. Source,
Git history, models, installed dependencies, photos and `out/studio-next` were
preserved. No CVI job was running. Rebuilds regenerate the deleted caches.
Do not reuse the old cleanup approval for any other directory.

Receipt: `D:\AI-Control\OpenJarvis\support\space-audit-20261011\cleanup-receipt-20261011-190138.json`.

## Workstation facts and routing

Jarvis personal API: `http://127.0.0.1:18080/v1`.
Editor API: `http://127.0.0.1:18080/router/v1`.
Port 8000 was reserved by Windows, so no port reservation was removed.

The server is a background loopback service. Its Windows daemon launcher now
prefers the existing sibling `pythonw.exe`, keeping native libraries independent
of terminal-close events. No executable was installed. Manage it with
`uv run --no-sync jarvis status`, `jarvis stop` and `jarvis start`; start uses
the configured 18080 port and refuses to create a competing registered server.

Windows 11; approximately 15.7 GiB RAM; Intel Iris Xe integrated graphics.
These hardware facts come from cached machine inventory. Consult `ollama ps`
for actual CPU/GPU allocation instead of assuming the integrated GPU accelerates
inference. Ollama is local and three models are already installed:

- `local/fast`: qwen3.5:2b for chat and short planning.
- `local/code`: qwen2.5-coder:7b for private code work.
- `local/research` and `local/vision`: qwen3.5:2b capabilities, with task quality
  still requiring review.
- Embedding: nomic-embed-text; the compatible local embedder returns 768 dimensions.

Retain 4096-token local context initially, keep inference sequential on this
16 GiB workstation and benchmark latency before increasing context/concurrency.
Larger context and parallel requests increase memory use; keep-alive trades
reload latency for RAM occupancy. See the official Ollama FAQ:
<https://docs.ollama.com/faq>.

Use `free/*` for public material only. Live free entitlements are not permanent
model IDs or quality guarantees. Private project chunks remain local unless
the user explicitly approves their remote use. No model downloads are needed.

## Newly practical capabilities

The document store was empty before this work. This curated runbook is an
explicitly approved indexing source in the existing local memory store. This
is not whole-drive indexing, canonical Project Intelligence adoption or automatic
fact learning. The existing facts-extraction switch remains off.

Three authored skills are in the checkout's `skills` directory:

- `workstation-brief`: executable two-step read-only inventory pipeline.
- `private-project-plan`: instructions for one bounded local repository plan.
- `local-research-note`: instructions for grounded local synthesis and sources.

The last two are instructions, not standalone executable pipelines. They grant
no editing, deletion or remote-transmission authority. Community auto-sync is
off. Hermes research/coding/productivity audits found no local cached source;
no third-party scripts or dangerous capabilities were imported.

The server's existing scheduler is enabled. One read-only `/system` task,
`b85c0a0689c845b0`, really executed through the owned server, succeeded and is
completed with no next run. No recurring personal task or Telegram notification
is enabled. Existing SQLite task state is preserved; there is one server-owned
scheduler and no Telegram poller.

Local smoke checks passed for arithmetic on qwen3.5:2b (7.93 seconds), a tiny
addition function on qwen2.5-coder:7b (19.18 seconds), and 768-dimensional nomic
embeddings (1.03 seconds). These are small functional checks, not general model
qualification. Local vision correctly identified the larger bar in the cleanup
chart. Its CLI now evaluates the effective private routing policy when showing
privacy warnings, including telemetry wrappers.

Deep Research found the correct cleanup facts in this indexed runbook, but its
answer exceeded the requested format and omitted a source citation. Treat that
quality gate as open. A fixed public-only Ollama documentation query returned no
usable search sources on this network. Direct fetching of the official Ollama
FAQ worked. Empty search rows now remain empty instead of looking like sources.

Voice interaction remains deferred. Voicebox was observed running separately on
`0.0.0.0:17493` with downloaded models but none loaded. This is a real binding
gap: restrict it to loopback before relying on voice/MCP privacy. This work did
not change its binding, start it, download models or enable voice acceptance.

## Commands

```powershell
cd D:\AI-Tools\OpenJarvis
$env:OPENJARVIS_HOME='D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis skill run workstation-brief
uv run --no-sync jarvis memory search EhsanWorkstationRunbook20261011
uv run --no-sync jarvis ask -m local/research --agent deep_research --tools retrieval,think "Search the indexed runbook for the completed cleanup and report the freed space with its source."
uv run --no-sync jarvis scheduler list
uv run --no-sync jarvis acceptance --live --text-only
.\scripts\Start-Ehsan-OpenCode.ps1 -Mode chat -Model openjarvis/local-code
```

Keep model answers separate from deterministic receipts. Cite runbook/receipt
paths, state observation dates and flag unavailable evidence. The memory store
currently uses FTS; adding nomic vectors to a project-scoped knowledge workflow
belongs to the later reviewed knowledge phases, rather than a parallel database.

## Project and editor status

CVI remains the dirty canonical production checkout on
`migration/v12-generated-boundary`; no source changes, reset, new render or
Project Intelligence migration were made. CVI-Next is a separate non-Git
directory requiring reconciliation. Read-only manifest previews were produced;
they were not applied to canonical project records. The full space audit found
about 112.22 GiB logical data in CVI before cleanup and 11.32 GiB in CVI-Next.

OpenCode 2.0.26's bundled CLI is configured using its version-matched plural
`providers/package/settings` schema and has completed a local text turn. Its
existing provider was preserved. Kilo 7.8.8 is installed, but GUI acceptance is
still manual: use OpenAI-compatible API `http://127.0.0.1:18080/router/v1`,
model `local/code` and dummy key `local-only` if required; preserve existing
profiles and credentials. Telegram setup remains in
`docs/EHSAN_REAL_USER_ACCEPTANCE.md`; a real token/chat allow-list and reply test
are still needed. Neither client is marked accepted solely from templates.

Other measured cleanup candidates remain review-only: `.pnpm-store` 8.54 GiB,
`.cvi-cache` 5.81 GiB and the inventoried npm cache 2.72 GiB. The mixed AI cache
contains model weights, so do not delete it wholesale. These estimates are from
the earlier read-only inventory and need a fresh preflight before another batch.

Capabilities still awaiting practical use: project-scoped semantic retrieval,
multi-project priority/task ownership, recurring reminders and Telegram delivery,
real Kilo GUI work, broader model evaluation, and voice interaction. Each requires
its own acceptance; enabling everything at once would not establish usability.

## Prioritized improvements

1. Make the control plane a daily workbench: use the brief, indexed runbook,
   local repository planning and one bounded code task with tests/diff.
2. Add explicit project roles and priorities after reviewing scanner proposals;
   reconcile CVI versus CVI-Next before adopting canonical project records.
3. Implement approval plans with exact scope, dry run, expiry and a receipt before
   expanding recurring or destructive automations. This phase is proposed, not
   a database migration performed by this setup.
4. Add scoped retrieval/provenance and embeddings using the existing stores;
   preserve private routing and avoid indexing node_modules, secrets and outputs.
5. Build a small model evaluation set for real coding/research tasks; measure
   correctness, latency and memory separately from successful model loading.
6. Finish Kilo GUI and Telegram allow-list/reply/restart acceptance before relying
   on those clients. Voice interaction stays deferred as requested.

GitHub native push authentication remains a publishing blocker. Preserve the
existing drafts and review local commits; local tests are not GitHub CI.
