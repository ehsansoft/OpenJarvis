# OpenJarvis upgrade research and proposed operating plan

Prepared 2026-10-12, Asia/Tehran. Local code baseline: branch
`feature/ehsan-practical-workflows`, commit `a184f6cc`. This is research and
planning, not an implementation or activation report.

## Recommendation

Make the existing workstation tools dependable before adding another agent
runtime or downloading models. First establish an enforced private-operations
permission profile; repair the skill compatibility audit before any community
import; qualify one editor and a small model evaluation set; then add scoped
knowledge and a one-shot notification pilot. Keep the existing JarvisSystem,
EventBus, scheduler store and channel owner.

The three installed Ollama models already cover small general/vision tasks,
bounded coding and local embeddings. The larger practical gaps are permissions,
source scope, usable skill semantics, task recovery and evidence freshness.

## Evidence and limits

Fresh observations are in
`D:\AI-Control\OpenJarvis\support\research-planning-20261012`:

- `live-audit.json`: loopback GET probes, installed model metadata, storage
  totals, read-only document counts and inspection of earlier evidence.
- `effective-config-audit.json`: selected effective defaults; no credentials.
- `hardware-and-listeners.json`: CIM hardware, listener addresses and D: space.
- `scheduler-readonly.json`: read-only task status, without prompt/result bodies.
- `capability-catalog.json`: current bounded live roster and readiness report.
- `nara-public-plans.json`, `nara-account-models.json`: public plans and filtered
  authenticated model metadata, with no inference or account/secret fields.
- `skill-compatibility-probes.json`, `ingestion-policy-probes.json`: pure
  declaration/path-name checks, not imported skills or project content.

Probes began at 12:49 Tehran time. At the 12:53 observation, D: had 44.96 GiB
free and RAM had about 1.08 GiB available of 15.69 GiB visible. Memory availability
is a changing snapshot, not an allocation budget or a hardware recommendation.
Ollama `/api/ps` was empty: no model was loaded by this research.

Earlier evidence was re-inspected rather than rerun:
`D:\AI-Control\OpenJarvis\support\ehsan-control-desk-evidence-20261012-001804.zip`.
Its ZIP integrity and payload hashes were checked. It records 785 finalizer
tests, 15 executed live checks and 11 browser checks passing during the preceding
session. These are historical results; they do not make an offline endpoint
currently operational. Voice was not run, and Telegram/OpenCode/Kilo human
acceptance remained separate. No regression or generation benchmark was rerun
for this documentation-only task.

Official documents and repository source were fetched. The detailed editor,
Hermes and Telegram source note is
[EHSAN_ECOSYSTEM_SOURCES_2026-10-12.md](EHSAN_ECOSYSTEM_SOURCES_2026-10-12.md).
Upstream `main` links can change; pin commits and hashes before installation.
Model tags, provider rosters and pricing are dated observations.

## Current assessment

| Area | Verified now | Status and practical implication |
| --- | --- | --- |
| Jarvis/dashboard | Configured `127.0.0.1:18080`; connection refused and no listener observed | Currently offline. Previously passed browser/restart acceptance. Cause of stopping was not diagnosed in this research. |
| Ollama | 0.40.2, three installed models, live metadata API | Working metadata service; listener is `::`:11434, a wildcard address. Loopback client URLs do not restrict the server listener. Firewall/LAN reachability was not tested. |
| Voicebox | No listener on 17493 and local GET failed | Offline; voice remains intentionally deferred. Previous session observed an all-interface listener, so verify its bind address before future use. |
| Private inference | `private_routing=true`, `allow_private_remote=false` | Configured and previously regression-tested. This protects inference; it does not by itself prevent a web tool from sending a private query. |
| Tool permissions | `security.capabilities.enabled=false`, `default_deny=false` | Enforcement subsystem exists but is inactive. Enabled tools include file writes, patching, shell execution and web search. Review this before enabling channels or more automations. |
| Scheduler | Enabled config, 10-second polling; two completed one-shot rows, no next runs | SQLite history is preserved. No server means no running scheduler now. No recurring personal task was added. |
| Telegram | Channels disabled, empty allow-list, no config token | Unused; real chat/notification acceptance is open. An empty generic allow-list is not a safe personal-bot setting. |
| Document memory | SQLite/FTS, three rows from one curated runbook | Working lexical foundation. This is not a project corpus or deployed semantic search. Automatic fact extraction remains off. |
| Skills | Enabled, auto-sync off; three authored workspace skills; Hermes cache absent | One reviewed inventory pipeline, two instructional recipes. Community compatibility is not established by an empty cache audit. |
| Project registry | 600 scanner proposals in existing catalog | Discovery evidence, not 600 approved active projects. Roles, canonical ownership and CVI/CVI-Next reconciliation remain open. |
| OpenCode | Earlier installed 2.0.26 CLI and local turn verified | Configuration is version-specific; current gateway outage blocks use through Jarvis until a manual start. Desktop acceptance remains open. |
| Kilo | Installed VS Code extension 7.8.8 inspected | GUI/provider and skill-tool acceptance remain manual. Current documentation is not proof of installed behavior. |
| Nara | Current free-plan intersection contains five aliases | Metadata access works. No remote completion was performed here; advertised capability, account visibility and qualified free inference are separate. |
| GitHub | Prior native push authentication failure | Publishing remains historically blocked; no credential inspection/change or fresh push was attempted. Local evidence is not GitHub CI. |

Local implementation evidence: [privacy policy](../../src/openjarvis/engine/privacy.py),
[system builder](../../src/openjarvis/system/builder.py),
[control routes](../../src/openjarvis/server/control_router.py),
[scheduler](../../src/openjarvis/scheduler/scheduler.py), and
[channel bridge](../../src/openjarvis/server/channel_bridge.py).

## Prioritized findings that change the plan

1. **Permissions must be explicit before expansion.** Dashboard chat has a
   restricted tool list, but generic channel chat calls `system.ask()` without
   such a list. Empty/omitted tool lists can inherit system tools. With capability
   enforcement disabled, local model routing is not an authorization boundary.
   Tool confirmation, secret scanning and other guards still exist; this is not
   a claim that every dangerous tool executes unrestricted. See
   [channel chat](../../src/openjarvis/server/channel_bridge.py),
   [orchestrator](../../src/openjarvis/system/orchestrator.py), and
   [dispatch gates](../../src/openjarvis/tools/_stubs.py).
2. **Default-deny alone is insufficient for private workflows.** Enabling it
   without an explicit policy currently grants a baseline including
   `network:fetch` and `memory:write`. An explicit personal policy should exclude
   outbound research and writes from ordinary private chat. Current capability
   resource patterns are checked against tool names, not filesystem paths;
   repository path containment requires a separate tested file policy. See
   [security setup](../../src/openjarvis/security/__init__.py) and
   [capability policy](../../src/openjarvis/security/capabilities.py).
3. **The editor gateway has an authentication gap.** The existing auth middleware
   protects `/v1`, `/api`, metrics and docs, but its path predicate does not include
   `/router/v1`. A configured server key must not be assumed to protect that raw
   gateway. Preserve loopback and add a focused auth regression before relying
   on keyed editor access. This is source inspection, not an exploitation test.
   [AuthMiddleware](../../src/openjarvis/server/auth_middleware.py).
4. **Hermes audits can report misleading compatibility.** Parameterized
   `Bash(git:*)` produced no dangerous capability in the local pure-function
   probe; metadata translation is not invoked; snake_case tools went unreported;
   `coding` misses upstream `software-development`. Resources outside `scripts/`
   also need examination. Repair these before any import. The
   [ecosystem note](EHSAN_ECOSYSTEM_SOURCES_2026-10-12.md) contains reproduction
   results and official source links.
5. **Existing bundled recipes are not all completed applications.** `think` is
   an echo scratchpad. A deterministic pipeline with several `think` steps does
   not independently extract todos or perform a security audit. For example,
   `todo-from-notes` needs an explicit model synthesis step or an agent-driven
   instructional adaptation. `dependency-audit` sends dependency information to
   web search; `file-organizer` includes POSIX shell commands and directory
   creation. Presence and a successful tool return are not useful-output
   acceptance. [ThinkTool](../../src/openjarvis/tools/think.py),
   [recipes](../../src/openjarvis/skills/data),
   [executor](../../src/openjarvis/skills/executor.py).
6. **Indexing is not ready for a whole project tree.** Name-only probes blocked
   `.env` and `credentials.toml`, but did not classify `wp-config.php`,
   `service.json` or generic `config.json` as sensitive. Generic configuration
   filenames cannot always be denied globally, so an explicit source allow-list
   is needed. Directory ingestion lacks the architecture's complete generated
   tree exclusion set and a project-root/size budget. File-level ingestion also
   takes a separate path. This research read no such private files.
   [File policy](../../src/openjarvis/security/file_policy.py),
   [ingestion](../../src/openjarvis/tools/storage/ingest.py).
7. **Reminder recovery needs a defined contract.** Telegram polling currently
   starts with `drop_pending_updates=True`. Scheduled results publish an
   in-memory end event; delivery failures are logged without a durable outbox.
   Job success is therefore not confirmed message delivery. Overdue schedules
   are polled on startup; recurring next runs are computed from execution time,
   without an explicit configurable misfire policy. A crash between execution
   and persistence is not an exactly-once guarantee.
   [Telegram](../../src/openjarvis/channels/telegram.py),
   [scheduler/store](../../src/openjarvis/scheduler/store.py),
   [notification dispatch](../../src/openjarvis/server/channel_bridge.py).
8. **Readiness needs to distinguish accepted from running.** The live catalog
   labeled scheduler READY from config/previous acceptance despite the offline
   personal API. It also searches PATH for editor CLIs, missing bundled desktop
   binaries/extensions. Add separate installed/configured/accepted/live fields,
   dependency propagation, observation age and selected-version evidence.
   [Catalog](../../src/openjarvis/core/capability_catalog.py).

These are findings and proposed fixes. No policy, auth path, importer, index,
polling behavior or service configuration was changed.

## Model plan: use what is installed

Hardware: Intel i5-1235U, ten reported cores/twelve logical processors, Iris Xe,
15.69 GiB visible RAM. The Windows GPU AdapterRAM field is not a reliable budget
for shared integrated graphics. Earlier generation showed CPU execution; current
`/api/ps` is empty, so there is no fresh GPU-offload result. Ollama documents
Windows Vulkan support, but that does not qualify this machine/driver/model.
[Hardware documentation](https://docs.ollama.com/gpu).

`D:\Ollama-Models` contains 23 blob/manifest files totaling 7,640,793,855 logical
bytes: 7.64 GB decimal, approximately 7.12 GiB. The profile model directory is
empty, and the existing `OLLAMA_MODELS` environment points to D:. This avoids a
duplicate-store recommendation. No new download is needed.

| Installed model | Local observation | Recommended bounded role | Evidence limit |
| --- | --- | --- | --- |
| `qwen3.5:2b` | 2.683 GB tag; Q8_0; completion/vision/tools/thinking metadata | `local/fast`, short private summaries, classification, simple screenshot questions; bounded `local/research` synthesis | Previous arithmetic and synthetic vision passes; multi-step research formatting/citations were weak. Not a qualified autonomous coding agent. |
| `qwen2.5-coder:7b` | 4.683 GB tag; Q4_K_M; completion/tools/insert metadata | `local/code`: explain a function, propose a small patch, generate a focused test | Previous tiny function check passed; repo-level tool use, PHP/TypeScript accuracy and latency still need evaluation. |
| `nomic-embed-text:latest` | 274 MB; F16; embedding-only; 768 dimensions | Local semantic retrieval after approved source/persistence design | Prior 768-dimensional probe passed. Model presence is not a vector index. |

Official model identities/capabilities are supported by the
[Qwen 3.5 catalog](https://ollama.com/library/qwen3.5:2b),
[Qwen Coder catalog](https://ollama.com/library/qwen2.5-coder:7b), and
[Nomic catalog](https://ollama.com/library/nomic-embed-text). Retain existing
digests in evaluation records; catalog `latest` changes do not justify a pull.

Keep configured `num_ctx=4096` initially. A published 256K or 32K architecture
window is not a practical RAM allocation on this laptop. Earlier 16K switching
caused allocation failures. Context and concurrent requests increase memory
requirements; evaluate sequentially before changing either. Use bounded
keep-alive rather than keeping all three models resident indefinitely.
[Ollama FAQ](https://docs.ollama.com/faq).

Proposed later settings, after an authorized restart/evaluation: one loaded
generation model, one parallel inference request, small embedding batches and
one embedding worker. The existing storage embedder defaults to eight workers,
so do not assume its default suits current RAM pressure. No environment setting
was changed here. [Local embedder](../../src/openjarvis/tools/storage/embeddings.py).

### Stable aliases and privacy

| Surface | Model choice | Permitted inputs |
| --- | --- | --- |
| Personal chat/planning | `local/fast`, `local/auto` | Approved local/private context; restricted tools |
| Private editor | `local/code` | Selected repository files; editor owns permissions and tool loop |
| Grounded local research | `local/research` | Explicitly indexed local sources, visible provenance |
| Screenshot work | `local/vision` | Approved synthetic or private image; no remote fallback |
| Public editor/research | `free/code`, `free/research`, `free/vision` | Explicitly public/synthetic requests; positive free evidence; measured capability |
| Embeddings | Existing `nomic-embed-text` adapter | Approved documents and queries, local endpoint |

`local/embed` is an architectural proposal, not an implemented chat alias.
Keep embedding-only models out of the generation pool. On the protected
personal path, `free/*` is constrained to local inference; on `/router/v1`, it
can select remote free candidates. An editor can attach project files itself,
so the alias is an explicit privacy decision, not an automatic classifier.
Remote model failure must never release private chunks to a fallback provider.
[Free pool](../../src/openjarvis/intelligence/free_pool.py).

### Model qualification before routing promotion

Proposed evaluation pack, using synthetic/public fixtures first:

- **Coding: 12 cases.** Four Python, four TypeScript and four PHP/WordPress
  cases: function explanation, failing-test repair, small patch and test
  generation. Score actual tests/AST/schema, patch scope, forbidden tool use and
  incomplete answers. Model-written tests alone are not the oracle.
- **Research: 10 cases.** Five cited factual queries, two conflicting-source
  questions, two absent-evidence questions and one adversarial source. Require
  exact claim/source association and abstention when evidence is absent.
- **Routing/tools: 8 cases.** Local outage, remote-only alias, changed roster,
  429/timeout, invalid tool arguments, partial stream, private context and
  concurrent request. Assert no private outbound payload and no duplicate tool
  side effect after partial streaming.
- **Retrieval: 20 queries over at most 20 approved documents.** Compare FTS
  versus hybrid using Recall@3, MRR, source correctness and stale-source handling.
  Require zero excluded/private-cross-project results. Test English/Persian
  separately; do not infer multilingual quality from embedding dimensions.
- Record digest, context, temperature, cold/warm latency, time to first token,
  token throughput, peak RAM, CPU/GPU execution and failures. Initial UI targets
  such as a 30-second small-chat response are proposals, not measured guarantees.

Alias promotion should require correctness and privacy gates plus acceptable
latency on the workstation. Increasing context, switching quantization or buying
a provider plan comes only after evidence identifies the bottleneck.

## Nara/ByNara: access, cost and useful limits

The product is NaraRouter by byNara, using
`https://router.bynara.id/v1`. It documents Chat Completions, Responses and
Anthropic-compatible surfaces, plus specialized embeddings/rerank/classification
and media endpoints. These are provider features, not implemented OpenJarvis
adapters. Jev is described for structured classification through System One;
do not assume any roster entry is interchangeable with a chat model.
[Official API documentation](https://router.bynara.id/docs).

At this observation, the public Free plan and authenticated roster intersected
at:

`agnes-2.5-flash`, `jev`, `laguna-s-2.1`, `nemotron-3-ultra-free`,
`nemotron-3.5-lightning-free`.

The public API reports Rp 0, 7,000,000 tokens/day and 15 requests/minute for Free.
These are published limits, not the remaining allowance of this account. Fifty
model records were visible to the authenticated metadata request; visibility is
not proof that all are free or that generation would succeed. The free-plan
intersection remains the conservative admission rule.
[Live plans](https://router.bynara.id/api/plans),
[pricing page](https://router.bynara.id/#pricing).

Paid plan fields showed 5,000/10,000/20,000/30,000 in `price_daily_idr` for the
listed tiers, while some `currency` fields said USD. The page labels these as
rupiah. Do not interpret them as USD prices or subscribe on this inconsistent
metadata; resolve currency, availability and billing in the provider dashboard
before any purchase. A model with `-free` in its name also appeared in paid-plan
lists: names alone are weaker evidence than a current plan intersection.

The provider's own policy describes shared capacity and upstream processing.
Nara advertises zero content retention at its gateway, but says content is sent
to the serving provider/publisher and subject to that provider's retention.
That is a vendor statement, not an independent security certification or
permission to send private project data.
[Provider privacy](https://router.bynara.id/privacy),
[homepage FAQ](https://router.bynara.id/#faq),
[fair-use policy](https://router.bynara.id/fair-use).

Proposed uses: public documentation comparison, synthetic patch evaluations,
public-source synthesis and public screenshot analysis after modality testing.
Keep private embeddings/reranking local. Image/video generation is separately
priced/permissioned and does not belong in the zero-API-cost chat pool.

Existing routing has a five-minute refresh default, deterministic heuristic
ranking and exception-based candidate fallback. Streaming fallback stops once
content/tool output is emitted. It is not yet an adaptive benchmark-based router.
Add endpoint type/modality/tool support, eligibility timestamp, per-provider
timeouts, 429 backoff and cooldown before promising reliable public workflows.
Opaque provider aliases do not establish the identity/quality of their upstream
weights. [Nara adapter](../../src/openjarvis/engine/nararouter.py),
[pool](../../src/openjarvis/intelligence/free_pool.py).

## Skills: what to use, adapt and defer

Use the reviewed `workstation-brief` now for cached inventory. Use
`private-project-plan` and `local-research-note` as instructions supplied to an
agent, not as independent executable applications. Keep auto-sync off.

Recommended additions are proposed procedures, not installed skills:

| Procedure | Value | First safe form |
| --- | --- | --- |
| Bounded bug investigation | Reproduce, isolate, explain and test a fix | Instruction-only; one repo, one issue, approved commands |
| Source/citation ledger | Distinguish source facts from conclusions | Selected public sources, claim IDs, URLs, dates and content hashes |
| Weekly review | Reconcile commitments and stalled work | Read local notes; output task proposals without creating schedules |
| Document-to-actions | Turn selected notes into actionable work | Draft tasks with source lines and uncertainty, no silent adoption |
| Workstation doctor | Explain environment/runtime/storage conflicts | Read-only version/listener evidence and proposed remediation |
| Editor handoff | Avoid duplicate work across agents | Task contract, branch/base commit, scope, tests and evidence |
| Dependency/security review | Find actionable project issues | Actual deterministic checks plus model explanation; explicit public query preview |

Hermes has suitable source procedures, including grounded citations, systematic
debugging and weekly review planning. Their original dependencies must be
reviewed; merely removing `scripts/` may remove essential verification.
[Official Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills),
[catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog).

Tool translation must preserve semantics, not just spelling. The current
`WebFetch -> web_search` mapping conflates page retrieval and search.
`Task -> delegate_agent` assumes a delegation capability that needs separate
authorization. A shell tool in one runtime is not a compatible Windows command
runner in another. Report mappings as exact/adapted/unsupported, and include
platform, arguments, scope, resources and privileges. Unknown dependencies must
block approval, not disappear from the audit. Agent Skills makes executables
optional and field support implementation-dependent.
[Tool translator](../../src/openjarvis/skills/tool_translator.py),
[specification](https://agentskills.io/specification).

For all candidates record source URL/commit/license, content hash, category,
original and translated tools, untranslated dependencies, dangerous capabilities,
conflicts and adaptation notes. Review all referenced resources, including those
under assets/templates/references. Import one audited bundle only after a later
installation request; no bulk sync or dangerous confirmation flags.

## Development agents: one owner for every change

| Tool | Proposed responsibility | Shared evidence |
| --- | --- | --- |
| OpenJarvis | Routing, selected local knowledge, readiness, tasks, dashboard and notifications | Source-linked runbook and execution/acceptance records |
| OpenCode | Terminal-first implementation OR read-only planning/review | One task contract, local alias, branch and actual test output |
| Kilo | VS Code navigation/debugging OR a bounded implementation task | Same contract, editor-specific permissions and inspected diff |
| Codex | Architecture/research, implementation OR independent review as assigned | AGENTS.md, scoped files, commit/diff, tests and unresolved findings |
| Hermes source | Reviewed procedures | Pinned source, compatibility audit, adapted instructions |

Choose one writer per branch/worktree. For a task, name the implementer and
reviewer explicitly; do not have OpenCode, Kilo and Codex all implement the same
issue. A reviewer can read the resulting diff without installing another
dependency tree. Shared knowledge should be a task contract and evidence files,
not an assumption that hidden chat histories synchronize.

Suggested task contract: task ID, repository/path, role (proposal only until
adopted), base commit, dirty-state summary, objective, allowed files/tools,
private/public label, runtime owner, acceptance commands, output paths, blocker
and handoff owner. CVI remains canonical and dirty; CVI-Next is not automatically
a replacement. No registry adoption or migration occurs through this document.

Codex supports scoped AGENTS.md and instruction-only skills; worktrees can
isolate changes but require extra files/dependencies. With D: storage and a dirty
production checkout, avoid automatically cloning full dependencies into multiple
worktrees. Review the installed environment before choosing one.
[Official instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[skills](https://learn.chatgpt.com/docs/build-skills),
[worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees).

OpenJarvis currently exposes Chat Completions and models on the editor gateway,
not `/router/v1/responses`. Do not assume Codex can use it merely because another
editor does. Match the installed client wire API; qualify stream/tool behavior
before changing a provider. Official Codex documentation supports local OSS
providers and custom-provider configuration, but neither path was configured or
run here. Codex's own provider, subscription and privacy are distinct from
OpenJarvis routing; do not reuse ChatGPT credentials as a gateway key.
[Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced),
[local route contract](../../src/openjarvis/server/routes.py).

An optional later read-only MCP facade could expose selected inventory and
memory tools to editors. Use explicit tool allow-lists and the same security
executor; never auto-discover every registered tool for that facade. This is a
proposed integration, not a live editor handshake.
[Local MCP server](../../src/openjarvis/mcp/server.py),
[official Codex MCP guidance](https://learn.chatgpt.com/docs/extend/mcp).

## Knowledge and dashboard improvements

There are existing but separate retrieval paths: dashboard/agent retrieval over
`memory.db`, in-memory DenseMemory/HybridMemory, and connectors' persistent
KnowledgeStore/HybridSearch used by `ask --research` and `/api/research`.
`jarvis memory index` does not populate all of them. Before adding vectors,
choose an owned adapter and a source/provenance contract; do not create a third
canonical store or silently switch the memory backend.
[Memory CLI](../../src/openjarvis/cli/memory_cmd.py),
[DenseMemory](../../src/openjarvis/tools/storage/dense.py),
[KnowledgeStore](../../src/openjarvis/connectors/store.py),
[HybridSearch](../../src/openjarvis/connectors/hybrid_search.py).

Setting `default_backend="hybrid"` is not a complete setup: that class needs
explicit sparse/dense instances, while the builder currently passes `db_path`.
DenseMemory is in-memory. The persistent KnowledgeStore constructor can apply
additive schema changes. None was instantiated or migrated by this research.
Keep the existing FTS store unchanged until a separate knowledge-phase decision.

Proposed scoped pilot: at most 20 specifically approved Markdown documents,
one project or the existing runbook, no account/media/archive directories.
Preflight prints exact paths, sizes, content-sensitivity findings and estimated
chunks without indexing. Exclude secrets, credential/runtime config stores,
WordPress config, dependencies, generated outputs, binaries and links escaping
the chosen root. Use content hashes, source paths/URLs, source date, chunk
offsets, project ID, privacy label and embedder digest. These are index metadata,
not automatic learned facts or a new project registry.

Nomic's model card recommends distinct `search_document:` and `search_query:`
prefixes. Both local embedder interfaces currently use unprefixed text. Add and
evaluate task-aware embedding methods before semantic promotion. The installed
metadata reports a 2048 architecture context while parameters mention 8192;
verify actual truncation/length behavior rather than promising 8K chunks.
Prefer small batches, cosine/RRF against FTS and lexical fallback.
[Nomic model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5),
[Ollama embeddings](https://docs.ollama.com/capabilities/embeddings).

Dashboard proposals:

- Separate live process/endpoint status from installed and historically
  accepted status; include observation time, stale evidence and actual bind.
- Show requested/selected model, provider, privacy label, routing reason,
  latency and source scope without exposing prompts/secrets in telemetry.
- Give tasks visible owner, timezone, last/next run, result state and separate
  delivery state; preview exact tool capabilities before creation.
- Give skills source/version/hash, instruction versus pipeline kind,
  compatibility and permission requirements. Do not turn every catalog item
  into a runnable button.
- Show research source excerpts, per-claim references, unknown/conflicting
  evidence, local/public routing and explicit notebook save/export.
- Keep arbitrary server launch/deletion/model-pull controls out of the initial
  desk. Add fixed project launch adapters only after scope and ownership review.

## Reminders and Telegram design

Prefer Telegram long polling over a new public webhook endpoint. A private
Windows workstation needs outbound access and a single poller, not port
forwarding. Telegram holds pending updates for at most 24 hours, and polling
and webhook delivery are mutually exclusive. Bot messages still traverse
Telegram's cloud even if model inference stays local.
[Bot API](https://core.telegram.org/bots/api),
[Telegram bot privacy](https://telegram.org/privacy/eu#6-3-what-data-bots-receive).

Useful later reminders: a generic break reminder, daily workstation brief,
weekly project review and a public research watchlist. The first two can be
deterministic; reminders should not require an LLM just to repeat a title.
Current scheduled prompts do invoke the model, so deterministic reminder
delivery needs a reviewed task/action adapter, not a misleading prompt template.

Persist schedules in UTC and evaluate cron in `Asia/Tehran`; display local time
and offset. Define overdue behavior explicitly (skip, run once or catch up with
a cap), OS sleep/offline behavior, grace windows, failure retries and maximum
execution time. Proposed notification outbox uses existing scheduler ownership
and, after explicit schema approval, run/destination idempotency keys, attempts,
next retry, delivery receipt and bounded redacted errors. Telegram API delivery
cannot guarantee exactly-once display after an ambiguous network failure.

First pilot, after permission/channel acceptance: one generic reminder five
minutes ahead, one allowed private chat, no project text or external research,
no recurrence. Validate allowed/unlisted chat, two-session isolation, Markdown
fallback, one poller, one scheduler, success/failure destination scope, restart
with offline message, duplicate update, network outage and 429 handling. The
API's message size/rate limits require splitting or brief notifications.
[Official FAQ](https://core.telegram.org/bots/faq),
[local bridge](../../src/openjarvis/server/channel_bridge.py).

## Upgrade comparison

Effort is an engineering estimate, not a promised delivery date. API costs below
exclude electricity and existing account subscriptions. Benefits and risks are
planning judgments based on the evidence above.

| Priority | Proposed upgrade | Benefit | Effort | Hardware/API cost | Principal dependency/risk |
| --- | --- | --- | --- | --- | --- |
| P0 | Private-operations capability profile | Makes tool authority distinct from inference privacy | 1-2 days | Negligible / local, zero API | Explicit grants and identity tests; default baseline permits network/memory writes |
| P0 | Editor auth path + live-state correctness | Prevents misleading keyed gateway/readiness claims | 0.5-1 day | Negligible / zero API | Preserve keyless loopback compatibility; distinguish fixtures/history/live |
| P0 operational gate | Reviewed loopback binding/lifetime plan | Dependable services with visible owners | 0.5 day plus manual check | Low RAM / zero API | Existing wildcard Ollama and offline endpoints; changes need a separate action request |
| P1 before imports | Skill compatibility auditor | Safe, truthful Hermes adoption | 1-2 days | Negligible / public source reads | Tool semantics, categories, resources, hashes and license |
| P1 | One editor + bounded task handoff | Productive coding without duplicate work | 0.5-1 day | 7B can pressure RAM / local | Server available, installed-version schema, actual diff/test evidence |
| P1 | Task-specific model evaluations | Select models by results | 1-2 days | Sequential CPU inference / local or qualified Free | RAM headroom; quality versus speed; no private remote fixtures |
| P2 | Scoped ingestion/provenance + hybrid pilot | Search relevant knowledge reliably | 2-4 days after design review | Small corpus fits; sequential embeddings / local | Explicit source scope and knowledge-store/schema approval |
| P2 | Reminder recovery + delivery outbox | Makes notifications auditable | 2-3 days plus human pilot | Low / ordinary bot API | Later schema approval, replay/misfire policy and Telegram disclosure |
| P2 | Public Nara qualification/cooldowns | Useful public research fallback | 1-2 days | Remote Free quota, no private chunks | Modality/endpoints, price ambiguity, rate limits and upstream trust |
| Later | WAMP/site adapters, inbox/calendar, voice | Broader personal operations | Scope separately | Service/account/model dependent | Exact project/account, credentials, write approval and human acceptance |

## Phased roadmap and acceptance gates

### Phase A: reliable permission and status baseline

Dependencies: current reviewed branch, preserved runtime config, no channel or
recurring activation. Scope source work to config/security/runtime dispatch and
readiness/auth routes. Add an explicit private read-only policy, tested identity
propagation and separation of outbound public research. Do not merely flip a
global switch in the user's current config.

Acceptance: private chat can retrieve the selected runbook/inventory; attempted
web search, shell, patch/write and unauthorized scheduling are rejected before
implementation entry; private model outage never sends an outbound payload;
malformed policy fails closed; keyed `/router/v1` rejects missing/wrong key;
keyless loopback remains compatible; offline API makes dependent execution
unavailable while preserving historical acceptance. Inspect a reviewable diff.

### Phase B: reviewed procedural skills

Depends on A for runtime use. Touch skill parser/importer/translator/resolver and
CLI audit. Normalize declarations and categories; report exact/adapted/unsupported
semantics and executable resources; audit without cloning/importing by default.
Acceptance includes `Bash(git:*)`, comma/list syntax, snake_case, unknown tools,
resource scripts outside scripts/, symlinks, naming conflicts and stale sources.
Only after a separate install request, review one procedure in each of research,
coding and productivity. No auto-sync or bulk import.

### Phase C: editor workflow and Model Lab

Depends on available loopback service and A. Verify OpenCode 2.0.26 and Kilo 7.8.8
with actual provider/tool traces; assign one writer and one reviewer. Run the
synthetic evaluation pack sequentially and bind results to digests. Touch editor
guides/launcher, evaluation harness and routing score evidence; do not change
aliases from a single successful answer. Acceptance: small patch passes fixed
tests, forbidden tool attempt is rejected, streamed tool calls preserve arguments,
restart loses no task record, and local fallback stays local.

### Phase D: selected knowledge

Depends on source/provenance design and explicit approval for any schema work.
First implement a dry-run allow-list preview; then evaluate at most 20 documents
through one selected existing storage adapter. Touch ingestion, embedding,
retrieval and dashboard research source displays. Acceptance: exclusions and
root containment, deterministic replacement, no duplicates after re-index,
source invalidation, model/dimension drift, cross-project isolation, offline
embedder FTS fallback and absent-evidence abstention. This phase is proposed;
Project Intelligence migrations are not authorized by this report.

### Phase E: one-shot reminder and channel acceptance

Depends on A, a chosen recovery contract and human Telegram setup. Touch existing
scheduler/store/bridge/Telegram adapter; never add a second scheduler or poller.
Use a generic one-shot first. Acceptance covers timezone, sleep/overdue behavior,
restart, success/failure delivery, 429 retry and duplicate/ambiguous delivery.
Recurrence requires a later explicit decision even after the pilot passes.

### Phase F: selective expansion

After preceding gates, choose one reusable WAMP/project-health adapter or a
public research watchlist. Add read-only account/site connectors first. Review
every credential, external message, filesystem write, deployment and model
download separately. Voice remains deferred until requested; its future gate
includes loopback binding and human STT/TTS/listening acceptance.

For any future code change follow focused regression tests, the AGENTS.md
control-plane suite and real-machine finalizer ZIP inspection. Live text
acceptance and human editor/channel acceptance remain separate. Full Windows
CI is not implied by the earlier selected-suite pass.

## Exact setup instructions for later use

These are instructions, not commands executed by this research. Steps that
start/rebind services, alter config or enable channels remain a separate action.

### Existing local desk and read-only inspection

```powershell
cd D:\AI-Tools\OpenJarvis
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis capabilities --json --timeout 3
uv run --no-sync jarvis scheduler list
uv run --no-sync jarvis memory search EhsanWorkstationRunbook20261011
```

For a later manual service start, use the configured address explicitly:

```powershell
uv run --no-sync jarvis start --host 127.0.0.1 --port 18080
uv run --no-sync jarvis status
```

Open `http://127.0.0.1:18080/control`. Check the actual process/listener, not just
`server.pid`. Do not remove stale state/locks to force startup. Leave Voicebox
off for text-only work. Before approving an Ollama bind change, identify the
current owner, quit it through its existing launcher and set loopback in that
owner's environment; start one owner and verify `Get-NetTCPConnection`. Never
launch another `ollama serve` beside the existing process to repair a binding.

### OpenCode 2.0.26 and Kilo VS Code

Preserve the working OpenCode configuration. If a merge is needed, use the
version-matched V2 `providers/package/settings` example in the
[ecosystem note](EHSAN_ECOSYSTEM_SOURCES_2026-10-12.md#opencode-one-coding-session-version-aware-configuration),
with `settings.baseURL=http://127.0.0.1:18080/router/v1` and
`modelID=local/code`. The generic remote schema currently conflicts with V2
docs; qualify against the installed CLI. Do not replace unrelated providers.

After the service is available:

```powershell
.\scripts\Start-Ehsan-OpenCode.ps1 -Mode models
.\scripts\Start-Ehsan-OpenCode.ps1 -Mode chat -Model openjarvis/local-code -Prompt 'Explain a two-line Python add function. Do not use tools or read or change files.'
```

For Kilo, retain existing profiles; create a separate OpenJarvis provider using
OpenAI-compatible API, base URL `http://127.0.0.1:18080/router/v1`, model
`local/code`. Leave the key empty for current keyless loopback; a non-secret
placeholder is acceptable only if required by the client. For future keyed
access, first fix/verify gateway auth and supply the real key through trusted
private settings. Test chat, then a read-only plan, then one explicitly assigned
small edit. A CLI JSON file is not a VS Code settings export.
[OpenCode V2 providers](https://opencode.ai/v2/docs/providers),
[Kilo compatible providers](https://kilo.ai/docs/ai-providers/openai-compatible).

### Hermes preview

```powershell
uv run --no-sync jarvis skill audit hermes
uv run --no-sync jarvis skill audit hermes --category research
uv run --no-sync jarvis skill audit hermes --category productivity
```

These inspect an existing cache and do not fetch it. The current cache is absent,
so results cannot certify imports. Use the unfiltered audit for coding until
category normalization is implemented. Do not run install/search/update/sync
as if they were read-only. Do not use dangerous/script/force flags for previews.

### Nara metadata

The existing credential store was used internally for bounded metadata reads;
it was not printed, changed or included in reports. Use
`uv run --no-sync jarvis model free --json` for current pool discovery;
metadata/eligibility is not a fresh completion or task-quality test. A new
credential should be added only after a later setup request through the existing
hidden-input `jarvis model nara-key` command, never a project file. Do not run a
private prompt against Nara to test connectivity; use public/synthetic fixtures
after an explicit remote qualification request.

### Telegram pilot, after the permission/recovery gates

1. Create a bot with BotFather; start it from your allowed personal account.
2. Stop the sole Jarvis owner before the one-time `getUpdates` chat-ID lookup.
   If an existing webhook is configured, inspect it and decide on polling before
   changing it. Never run a channel listener alongside the server poller.
3. Enter the token without a shell literal; print only the numeric chat ID:

```powershell
$telegramCredential = [pscredential]::new('telegram', (Read-Host 'Bot token' -AsSecureString))
$env:TELEGRAM_BOT_TOKEN = $telegramCredential.GetNetworkCredential().Password
try {
    $updates = Invoke-RestMethod -Uri ('https://api.telegram.org/bot' + $env:TELEGRAM_BOT_TOKEN + '/getUpdates')
    $updates.result | ForEach-Object { $_.message.chat.id } | Sort-Object -Unique
} catch { Write-Error 'Lookup failed; inspect privately. Do not share the token-bearing URL.' }
```

4. Merge, without duplicate TOML sections, `[channel] enabled=true`,
   `default_channel="telegram"`, `default_agent="orchestrator"` and
   `[channel.telegram] allowed_chat_ids="NUMERIC_CHAT_ID"`,
   `parse_mode="Markdown"`. Keep the token exclusively in the environment.
   The private profile/restricted channel tools must already be reviewed.
5. Start the single Jarvis server from the same token-bearing PowerShell:
   `uv run --no-sync jarvis start --host 127.0.0.1 --port 18080`.
   Send a generic chat, test an unlisted account and `/notify telegram`.
6. Only after accepting chat, review one future timestamp and notification
   destination. Proposed one-shot command (not executed):

```powershell
$pilotAt = (Get-Date).AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:sszzz')
uv run --no-sync jarvis scheduler create 'Reply only: Reminder, take a short break.' --type once --value $pilotAt --timezone Asia/Tehran --agent simple --tools think --notify-chat NUMERIC_CHAT_ID
# Use the returned ID to inspect its state and logs; do not create recurrence.
uv run --no-sync jarvis scheduler list
uv run --no-sync jarvis scheduler logs TASK_ID
```

Current scheduler config is already enabled, with a preserved default store.
Do not copy historical instructions that disable it or omit the selected host/
port. Treat generic model-generated reminder output as such until a deterministic
reminder adapter is implemented. Token persistence across OS login is a separate
credential-lifecycle decision, not solved by this process environment example.

## Three practical workflows and their prerequisites

1. **Workstation brief and next action.** Run the reviewed workstation skill,
   inspect current readiness and search the indexed cleanup runbook. Pick one
   action; treat cleanup candidates as proposals, not authority to delete.
   `uv run --no-sync jarvis skill run workstation-brief` and the read-only
   commands above do not need a running dashboard. Check inventory dates.
2. **Private plan -> implementation -> review.** After manually starting the
   existing service, select `local/code` in one editor. Give it a task contract,
   selected files and fixed tests. Ask for a plan first, authorize one bounded
   edit, then give Codex or the other editor the diff for independent review.
   Keep private chunks local and reuse one existing environment.
3. **Local evidence question -> source-backed note.** Search the runbook with
   `jarvis memory search`; after starting Jarvis, use dashboard Research to ask
   a focused question such as which approved cleanup recovered space. Inspect
   the displayed source, distinguish model text from receipt facts and save a
   browser note explicitly. Public research starts with a reviewed public query
   and source fetch; the earlier empty web search is not a usable-source pass.

## Recommended next development task

**Implement a tested private-operations permission profile and apply it through
the existing runtime interfaces, without activating it in the user's state yet.**

This comes first because more skills, Telegram messages and scheduled prompts
increase the number of inputs that can reach tools. Model privacy and an
instruction saying read-only do not enforce that authority. The current
dashboard's limited tools are a useful pattern to extend.

Bounded deliverable: an explicit read-only profile, distinct public-research
profile, consistent policy identity through chat/CLI/channel/scheduler/skill/MCP
dispatch, and focused tests proving denied implementations are never entered.
Allow memory retrieval and inventory; exclude writes, shell execution,
unapproved network queries and task creation. Keep approval actions separate
from a model's statement of permission. Preserve upstream defaults outside the
personal preset. Inspect the diff and selected-suite evidence before a later
user-approved activation. The skill audit repair is the next prerequisite for
imports; the editor auth gap is a separate small P0 fix.

Research outputs are the two Markdown notes and safe evidence reports. No
application code/configuration, credentials, models, services, skill installs,
files outside report creation, recurring jobs or project-state migrations were
changed. No permanent memory was updated.
