# Ehsan ecosystem research: skills, editors and Telegram

Checked 2026-10-12, Asia/Tehran. Research and planning only. No installs, imports,
configuration changes, external messages, service starts or recurring jobs were
performed. Public documentation was retrieved; local source files and installed
Kilo package documentation were inspected. Local pure-function probes were run
without importing a skill. Upstream `main` links are observations at this date,
not immutable package pins.

## Findings that should change the next development plan

| Priority | Finding | Evidence | Proposed acceptance criterion |
|---|---|---|---|
| P0 before external skill imports | Parameterized `allowed-tools` evade exact-name capability classification | [`importer.py:41`](../../src/openjarvis/skills/importer.py#L41), read-only probe below | `Bash(git:*)`, `shell_exec(...)`, `Write(...)` and comma-separated declarations classify consistently; dangerous imports refuse before any write |
| P1 | Declared tool metadata is not translated by the importer | [`importer.py:194`](../../src/openjarvis/skills/importer.py#L194), [`tool_translator.py:85`](../../src/openjarvis/skills/tool_translator.py#L85) | Audit lists body and metadata mappings separately; unsupported tool semantics are explicit blockers |
| P1 | Missing-tool detection ignores Hermes snake_case references | [`tool_translator.py:78`](../../src/openjarvis/skills/tool_translator.py#L78), upstream [systematic-debugging](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/skills/software-development/systematic-debugging/SKILL.md) | `terminal`, `read_file`, `search_files`, `web_extract`, `browser_navigate` produce mapped or unsupported results; no empty compatibility report for unsupported dependencies |
| P1 | Coding category audit misses the current upstream category | [`skill_cmd.py:255`](../../src/openjarvis/cli/skill_cmd.py#L255), [official catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) | Public category `coding` includes `software-development`; retain raw upstream category and cover `autonomous-ai-agents` separately |
| P1 before reminder pilot | Telegram restart currently drops queued messages | [`telegram.py:371`](../../src/openjarvis/channels/telegram.py#L371), [Bot API update delivery](https://core.telegram.org/bots/api#getting-updates) | Define discard-versus-replay policy explicitly; test offline update, duplicate delivery, task retry, and user-visible status |
| P1 | Installed editor behavior needs version-specific qualification | [OpenCode migration](https://opencode.ai/v2/docs/migrate-v1/), [Kilo bundled runtime TODO](https://github.com/Kilo-Org/kilocode/blob/main/packages/kilo-vscode/docs/non-agent-features/skills-system.md) | Real editor reply and harmless skill-tool trace; preserve unrelated provider/config fields |

These are proposed fixes, not changes made by this research. A declaration audit
gap is not proof of arbitrary execution: instruction-only imports and executable
manifests take different paths, and runtime policy still matters.

### Reproduced without importing or executing a skill

Using the current local `SkillParser`, `ToolTranslator` and `_dangerous_tools`:

```text
allowed-tools: Bash(git:*) Read
_dangerous_tools(...)                     -> []
translate_allowed_tools(...)             -> shell_exec(git:*) file_read
translate_markdown("Use terminal, read_file,
web_extract, and search_files.")          -> unchanged text; missing-tools []
```

The importer renders the original frontmatter after translating the body; it
does not call `translate_allowed_tools`. The parser recognizes `allowed-tools`
as a specification field but does not store a corresponding canonical manifest
field. The dangerous-tool helper examines raw declarations using exact matches.
See [parser.py](../../src/openjarvis/skills/parser.py),
[importer.py](../../src/openjarvis/skills/importer.py), and
[security.py](../../src/openjarvis/skills/security.py).

Also review policy detection for destructive instructions embedded in Markdown
and executable resources under `assets`, `templates` or `references`. Those
resource directories are copied even when `scripts/` is skipped. Skipping the
scripts directory alone does not establish an instruction-only bundle.

## Hermes: borrow audited procedures before adopting another runtime

Hermes uses `SKILL.md` with optional supporting resources. It supports hub
preview, security scanning, provenance and project trust. Its current scanner
blocks dangerous findings even with `--force`; normal hub installation may
include referenced scripts and resources. These protections belong to Hermes'
installer, not automatically to OpenJarvis' resolver. [Hermes skills system](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).

The Agent Skills specification treats scripts as optional executable resources
and `allowed-tools` as experimental, with support varying by implementation.
Therefore portability of the document format does not guarantee identical
tools, permissions or execution behavior. [Agent Skills specification](https://agentskills.io/specification).

Local OpenJarvis currently scans cached `skills/<category>/<name>/SKILL.md`.
It does not implement all of Hermes' hub registries or `optional-skills/`
discovery. Its audit command is read-only, but `search`, `install` and `sync`
can synchronize upstream Git and write cache/state. Do not present those as
read-only previews. [Hermes resolver](../../src/openjarvis/skills/sources/hermes.py),
[skill CLI](../../src/openjarvis/cli/skill_cmd.py).

Recommended candidates, subject to bundle review and adaptation:

| Candidate | Practical value | Compatibility boundary |
|---|---|---|
| `grounded-citations` | Source ledger, claim attribution and citation verification | Original uses `scripts/sources.py`, a writable ledger, shell and Hermes web tools; first adapt the procedure as text, without silently assuming the skipped script exists. [Source](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/skills/research/grounded-citations/SKILL.md) |
| `systematic-debugging` | Reproduce a bug, isolate cause and validate a focused fix | Calls `read_file`, `search_files`, `terminal`; Bash examples require Windows adaptation. [Source](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/skills/software-development/systematic-debugging/SKILL.md) |
| `weekly-review-planning` | Review commitments, stalled projects and next actions | Requires authoritative task/calendar sources; use local notes and drafts first, without OAuth or automatic writes. [Source](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/skills/productivity/weekly-review-planning/SKILL.md) |
| `document-to-action-items` / `meeting-action-items` | Turn selected documents into source-linked task proposals | Review dependencies and retain approval for task creation. [Catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| `arxiv` | Public academic literature discovery | Original references shell, a helper script and `web_extract`; audit dependencies rather than assuming a generic search tool is equivalent. [Source](https://raw.githubusercontent.com/NousResearch/hermes-agent/main/skills/research/arxiv/SKILL.md) |

Do not import macOS-only reminders, account management, email sending, deployment,
or agent-spawning bundles as a shortcut to workstation capability. No new Hermes
runtime is needed to use adapted procedures; a second gateway and scheduler
would add ownership and credential complexity.

### Safe integration sequence for a future approved change

1. Choose three procedures: research, coding and productivity. Retrieve only
   public source material and pin its commit/content hashes in a review report.
2. Read every declared dependency and referenced resource. Produce original and
   proposed names, source/category, translated/unsupported tools, platform
   requirements, resources, conflicts, write/network capability and hash.
3. Repair the audit gaps above. Use fixture bundles, including parameterized
   tools, lowercase tool names, ambiguous mappings and executable resources
   outside `scripts/`.
4. Create reviewed instruction-only adaptations with dependencies removed or
   clearly blocked. Do not claim equivalent functionality after removing a
   citation validator or external connector.
5. After a separate installation authorization, import one reviewed bundle;
   retain source provenance and run a harmless, bounded acceptance case.

Read-only commands against an existing cache:

```powershell
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis skill audit hermes --category research
uv run --no-sync jarvis skill audit hermes --category productivity
uv run --no-sync jarvis skill audit hermes
```

Use the unfiltered audit for current coding skills until category normalization
is repaired. An absent cache produces no skill evidence; it does not demonstrate
compatibility or successful imports.

## OpenCode: one coding session, version-aware configuration

Official V2 configuration uses `providers`, `package`, `settings.baseURL`, and
`modelID` for the ID sent upstream. Local records identify installed CLI 2.0.26;
do not overwrite its working configuration with V1 `provider/npm/options`
examples. [V2 providers](https://opencode.ai/v2/docs/providers),
[local October 11 audit](../EHSAN_TEXT_AND_SPACE_AUDIT_2026-10-11.md).

Proposed minimal merge, preserving all existing providers and unrelated fields:

```jsonc
{
  "model": "openjarvis/local-code",
  "providers": {
    "openjarvis": {
      "name": "OpenJarvis Local Control Plane",
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": { "baseURL": "http://127.0.0.1:18080/router/v1" },
      "models": {
        "local-code": { "modelID": "local/code", "name": "Private Code" },
        "local-fast": { "modelID": "local/fast", "name": "Local Fast" }
      }
    }
  }
}
```

This is a proposal, not a configuration change. The checked repo template still
defaults to port 8000; this workstation's selected port is 18080. Do not insert
actual credentials into the project configuration. [Repo template](../../configs/editors/opencode.openjarvis.jsonc).

V2 discovers project `.opencode/skills` and compatible `.agents/skills`
directories; extra skill sources use one array. Relative extra paths resolve
from the working directory. Prefer reviewed local folders to HTTP catalogs.
Portable frontmatter can be accepted without every field being interpreted.
[V2 skills](https://opencode.ai/v2/docs/skills).

Use an explicitly read-only planning/review agent before implementation. V2
permissions use ordered rules such as denying `edit` and `shell`; do not copy
V1 permission shapes blindly. [V2 agents](https://opencode.ai/v2/docs/agents),
[V2 configuration](https://opencode.ai/v2/docs/config).

Important documentation conflict: the fetched generic
[opencode.ai/config.json](https://opencode.ai/config.json) currently describes
legacy singular provider/options and object-shaped skills, while V2 docs show
the native shapes above. Installed CLI behavior and version-matched source must
qualify an edit; a generic schema error alone is insufficient reason to rewrite
the working V2 config. The [migration guide](https://opencode.ai/v2/docs/migrate-v1/)
also notes that V2 accepts some fields without implementing their behavior,
including LSP execution. Use actual lint/typecheck commands for those checks.

## Kilo: qualify the installed extension before sharing more capabilities

Installed package metadata confirms Kilo VS Code 7.8.8 in
`C:\Users\eehsa\.vscode\extensions\kilocode.kilo-code-7.8.8-win32-x64`.
Its bundled skills note lists execution integration, discovery and hot reload
as remaining work. The same TODO appears in the [official repository](https://github.com/Kilo-Org/kilocode/blob/main/packages/kilo-vscode/docs/non-agent-features/skills-system.md).
It might lag implementation: this is a reason for a real skill-tool trace,
not proof that skills cannot work.

Future manual setup: Settings → Providers → Custom provider; provider ID
`openjarvis`, OpenAI Compatible API, base URL
`http://127.0.0.1:18080/router/v1`; fetch models or enter `local/code`. Keep the
existing profile. Leave key empty for unauthenticated loopback, or configure
the actual server key privately if authentication is enabled. Test a chat-only
function explanation before allowing edits. [Kilo compatible providers](https://kilo.ai/docs/ai-providers/openai-compatible).

Current documentation describes `.kilo/skills` and `.agents/skills`, on-demand
loading, and skill tool traces. It also distinguishes its new platform from
legacy mode-specific directories. Verify against installed 7.8.8 rather than
certifying all current documentation features. [Kilo skills](https://kilo.ai/docs/customize/skills).

Custom agents can limit iterations and deny editing/shell actions; use one
read-only reviewer and one bounded implementer rather than several agents
editing the same checkout. [Kilo custom agents](https://kilo.ai/docs/customize/custom-modes).
Kilo CLI's `provider/options` config is a different product schema from OpenCode
V2. Its trusted/global config rules permit secret environment references while
project config cannot resolve them. Never treat the CLI template as a VS Code
settings export. [Kilo CLI](https://kilo.ai/docs/code-with-ai/platforms/cli).

## Telegram: outbound polling, explicit disclosure and recovery tests

Bot updates use either long polling or webhooks, not both. A webhook requires
Telegram to reach an HTTPS endpoint; polling fits a loopback workstation with
outbound Internet access. Updates expire after 24 hours. Offset confirmation
is important for avoiding repeats; webhook retries also require idempotency.
`sendMessage` text is limited to 4096 characters after entity parsing.
[Bot API](https://core.telegram.org/bots/api).

A personal reminder bot needs no paid broadcast option. Telegram advises at
most approximately one message/second in a chat, 20/minute in a group and
30/second for ordinary bulk notifications; handle 429 and retry guidance instead
of assuming unlimited free delivery. A user must first start the bot, and group
privacy mode changes which messages bots receive. [Bots FAQ](https://core.telegram.org/bots/faq).

Telegram is a cloud messaging route even if inference is local. Bots receive
messages and public profile information from users interacting with them.
Do not describe bot chat as an entirely local private surface. Prefer generic
reminder titles, task IDs and dashboard links; exclude private project excerpts
and secrets. [Telegram privacy](https://telegram.org/privacy/eu#6-3-what-data-bots-receive).

Future setup follows the existing [manual acceptance guide](../EHSAN_REAL_USER_ACCEPTANCE.md):
BotFather token via hidden input, one-time chat-ID lookup while the poller is
stopped, nonempty `allowed_chat_ids`, exactly one Jarvis-owned channel and
scheduler, and `/notify telegram` opt-in. Correct every example to the explicit
loopback host and port 18080 before executing it. The guide's step 7 `jarvis
serve --scheduler ...` lacks those overrides and could otherwise use its
historical port default. No setup or activation occurred during this research.

Start with a proposed one-shot generic reminder five minutes ahead, timezone
`Asia/Tehran`, and no repository tools. Accept only after: allowed chat gets one
reply; unlisted chat gets none; two chats retain isolated histories; Markdown
failure falls back to plain text; one notification follows success or failure;
restart preserves task state and the defined delivery behavior; retry does not
duplicate notifications. Recurrence remains a later, explicit decision.

## Recommended responsibilities and shared handoff

This is a proposed operating model, not an upstream feature guarantee:

- OpenJarvis owns model routing, selected knowledge, scheduler state, local
  dashboard and Telegram notifications.
- OpenCode or Kilo owns one active coding task, its approved diff and project
  checks; choose one writer per branch/worktree.
- Codex performs implementation or an independent read-only review according
  to the assigned role. Share reviewed files, not hidden conversation state.
- Hermes supplies reviewed procedural material first. Do not run a second
  Hermes scheduler or bot poller merely to gain those instructions.

Shared task handoff should contain repository/branch/base commit, dirty-state
summary, scope, allowed files/tools, acceptance commands, evidence paths and
remaining blockers. Claims of completion must come from the actual diff and
checks, not another agent's summary. The highest-value first change in this
area is a read-only skill compatibility auditor that normalizes declarations
and reports uncertainty before any import.
