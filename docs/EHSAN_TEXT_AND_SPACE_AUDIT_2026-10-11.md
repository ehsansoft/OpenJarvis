# Text operation and D: cleanup review — 2026-10-11

This work continues Foundation / Phase 0.5 and the read-only Phase 1A/1B
branches. Voice interaction is deferred at the user's request. No Project
Intelligence migration, file removal, PATH change or model download occurred.

## Current workstation

Windows reserved ports 7914–8213, including the configured 8000; bind attempts
failed with WinError 10013. The workstation config now uses loopback port
18080. Its original config is backed up outside Git as
`D:\AI-Control\OpenJarvis\config.pre-text-space-audit-20261011.toml`.
No Windows port reservation was modified.

| Surface | Verified behavior | Remaining work |
| --- | --- | --- |
| Jarvis text | Health on `http://127.0.0.1:18080`; real CLI system question produces a dated factual inventory | General answers still depend on model quality |
| Ollama | qwen3.5:2b, qwen2.5-coder:7b and nomic-embed-text installed; local fast/code/research/vision and embedding acceptance pass | No extra downloads needed; benchmark quality separately |
| Public/free routing | Six positively entitled models discovered; synthetic `free/code` gateway request succeeds | Full provider qualification and failover benchmarks pending; gateway response alone does not identify the upstream provider |
| OpenCode | Bundled CLI v2.0.26; provider merged; real local-fast text turn returns `LOCAL_EDITOR_OK` | GUI workflow acceptance; use local-code for project work |
| Kilo | VS Code extension 7.8.8 installed; merge instructions/templates prepared | Actual client interaction remains manual; CLI was not found on PATH |
| Memory/research | Real isolated index/search and local DeepResearch acceptance pass | Canonical project-scoped knowledge adoption is a later approved phase |
| Scheduler | Real local scheduled execution and ownership regressions pass | Personal jobs remain disabled pending acceptance |
| Telegram | Allow-list, isolation, polling/restart and notification regressions exist | User token/chat allow-list and live reply/restart acceptance; disabled |
| Voicebox | Previous human listening acceptance exists | Service currently off; speech is NOT_RUN in this text-only acceptance |
| Projects/tasks | Scanner proposals and read-only review/catalog exist | No confirmed canonical project/task records or Phase 1C approval workflow migration |

Private routing stays local. `local/fast` maps to qwen3.5:2b; `local/code`
uses qwen2.5-coder:7b; nomic is the immediate local embedder. Use `free/*` only
for public material. Do not inject private project chunks into remote requests.
Installed capacity is not measured task quality or permission for autonomy.

## Fixes

- `jarvis projects space-audit` includes node_modules and other folders omitted
  by normal inventory. It reads metadata, skips reparse points, refuses linked
  roots, counts nested candidates without adding them twice, marks truncation,
  emits a progress heartbeat and never overwrites an existing report.
- Exact workstation-summary questions and `/system` use the existing
  machine_inventory tool through the normal executor, governance and loop guard.
  Output is factual, dated and explicitly cached. Unrelated/mutating prompts
  retain normal agent routing.
- Machine inventory's loopback probes now bypass environmental proxies while
  remote probes keep their proxy settings.
- `jarvis acceptance --live --text-only` skips live speech and microphone gates
  without marking them passed. It rejects a speech fixture in that mode.
- The finalizer honors the configured loopback port for probes, service startup,
  generated editor templates and evidence instead of assuming port 8000.

## Cleanup findings and approval boundary

Full scan: 2,678,562 files, no file-budget truncation; access errors and skipped
links remain measurement limits. CVI measures 112.22 GiB logically, CVI-Next
11.32 GiB. These are accessible logical sizes, not promises of physical space.

The proposed first batch totals **26.51 GiB** in three disjoint directories:

1. `D:\Projects\Ehsan-OS\CVI\.render-tmp` — 22.04 GiB temporary Remotion bundles.
2. `D:\Projects\Ehsan-OS\CVI\sidecars\remotion-v2.8.2-explainer-workspace\node_modules\.cache\webpack`
   — 3.89 GiB webpack cache.
3. `D:\Projects\Ehsan-OS\CVI\apps\cvi-studio-dashboard\node_modules\.cache\webpack`
   — 0.58 GiB webpack cache.

Git tracks zero files in these paths. No CVI renderer process was observed.
Recheck exact path containment, links, active jobs/processes and current sizes
before approved execution. Next builds will regenerate cache data and take
longer. No deletion was performed. The exact dry run and complete candidate CSV
are in `D:\AI-Control\OpenJarvis\support\space-audit-20261011`.

Do not remove the mixed `D:\AI-Control\caches` parent: 9.09 of its 14.03 GiB is
Hugging Face model data. Preserve Git history, models, databases, photos,
`out/studio-next`, source and installed dependencies. Review `.pnpm-store`
(8.54 GiB), `.cvi-cache` (5.81 GiB) and npm cache (2.72 GiB) in a separate batch.
Nested candidate rows overlap parent node_modules rows.

CVI remains a dirty repository on `migration/v12-generated-boundary` (759
status entries); CVI-Next is not a Git repository at inspection. Their production
state was not re-rendered or migrated. Do not treat the second tree as disposable
or replace the canonical control database based only on size or directory name.

## Text commands

```powershell
cd D:\AI-Tools\OpenJarvis
$env:OPENJARVIS_HOME='D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis status
uv run --no-sync jarvis chat -m local/fast
# In chat: /system; /quit ends the session.
uv run --no-sync jarvis capabilities --json
uv run --no-sync jarvis acceptance --live --text-only
uv run --no-sync jarvis projects space-audit D:\ --output D:\AI-Control\OpenJarvis\support\space-audit-next.json
```

Choose a fresh audit filename; there is no delete/apply switch. The default
file budget is three million; inspect `truncated`, access errors and link skips.

## OpenCode setup and launch

The installed v2.0.26 uses **`providers` / `package` / `settings`**, matching
`configs/editors/opencode.openjarvis.jsonc`. The v1 singular `provider` template
does not match this installed binary. Existing `bynara` configuration was
preserved in the merged `C:\Users\eehsa\.config\opencode\opencode.jsonc`.
Its original is `opencode.pre-openjarvis-20261011.jsonc` beside it; neither
configuration nor credentials is included in the evidence ZIP.

Merged provider: `openjarvis`; baseURL:
`http://127.0.0.1:18080/router/v1`; default: `openjarvis/local-code`.
For a fresh merge, copy only the `providers.openjarvis` object and desired
`model` setting from the version-matched generated template in
`D:\AI-Control\OpenJarvis\editor-configs`, preserving other providers/secrets.

```powershell
# No PATH changes or installation:
.\scripts\Start-Ehsan-OpenCode.ps1 -Mode models
.\scripts\Start-Ehsan-OpenCode.ps1 -Mode chat -Model openjarvis/local-fast
.\scripts\Start-Ehsan-OpenCode.ps1 -Mode chat -Directory D:\Projects\Ehsan-OS\CVI -Model openjarvis/local-code -Prompt 'Describe the next task; do not change files.'
```

The launcher adds localhost to NO_PROXY for its child only, preserving remote
proxy settings. The actual CLI is under
`%LOCALAPPDATA%\Programs\@opencodedesktop\resources\opencode-cli.exe`.
Desktop launch is available with `-Mode desktop`; if an existing GUI instance
keeps its old environment, close/reopen it through the launcher manually.
The catalog still requires human editor acceptance; a CLI test does not satisfy
that gate, and PATH-based detection may miss this bundled installation.

## Kilo merge instructions

For an OpenAI-compatible Kilo UI connection, set base URL
`http://127.0.0.1:18080/router/v1`, model `local/code` and, only if a nonempty
key is required, placeholder `local-only`. The loopback service needs no paid
provider credential. Preserve existing profiles and secrets; create/select a
separate OpenJarvis profile. Test a synthetic sentence before project work.

For a CLI supporting the supplied schema, merge only
`provider.openai-compatible` from the generated `kilo.openjarvis.jsonc` into
the existing provider object and choose `openai-compatible/openjarvis-local-code`.
Do not overwrite the whole configuration. Actual installed-client compatibility
and a real interaction remain unverified.

Telegram setup remains in `docs/EHSAN_REAL_USER_ACCEPTANCE.md`: set the local
token outside Git and an explicit allowed_chat_ids list, use the single server's
channel/scheduler ownership, then test inbound/reply/isolation/restart and
notifications before enabling personal jobs. No Telegram messages were sent.

## Evidence and next task

Required control-plane regression and focused coverage pass. Text live
acceptance: 252 regression tests, all 15 executed live checks PASS; voice and
microphone NOT_RUN; Telegram/OpenCode/Kilo human interaction gates remain manual.
The separate OpenCode CLI and workstation-summary probes pass.

Final combined control-plane/focused run: 324 passed. Ruff and diff checks pass.
The real-machine finalizer passed 628 targeted tests and its required steps.
Its optional Voicebox MCP check returned 2 with Voicebox off, as expected for
the current text-only scope. The inspected 12-file finalizer ZIP contains no
credentials, audio or runtime databases. Services/tasks were not started by
that verification run. Personal automations remain disabled.

Next authorized boundary: review the three-path cleanup plan and obtain explicit
approval before removing anything. Follow with CVI/CVI-Next role reconciliation
and one bounded local-code project task. Phase 1C approvals and canonical
Project Intelligence adoption remain future reviewed work. Existing PRs are
drafts; no merge, tag or stable promotion was performed.

Changes are committed on `feature/ehsan-text-space-audit`. Publishing this branch
is blocked: GitHub rejected the native Git push with invalid username/token.
No new PR was created; do not infer CI success from local checks. Existing draft
PR #4 remains open and unmerged. Workstation config/provider backups are outside
Git; the support ZIP stays on the workstation and includes no editor credentials.
