# Hermes Agent team-of-agents research and OpenJarvis implications

Prepared 2026-10-14, Asia/Tehran. Local baseline: branch
`feature/ehsan-guided-operations`, commit `5743176f`. This is research and a
proposal, not an implementation or activation report. Every release claim
carries a version and date; every feature claim carries an official source.

## Why this note exists

Hermes Agent is being installed on this workstation and is the reference for
"manage a team of agents". This note records what Hermes actually ships in
October 2026, which of those capabilities OpenJarvis does and does not have,
and the bounded improvements, capabilities, skills and publishing ideas that
follow from that comparison.

## Hermes state of play (primary sources)

Release index: <https://github.com/NousResearch/hermes-agent/releases>.
License MIT; docs <https://hermes-agent.nousresearch.com/docs>.

| Version | Label | Released |
| --- | --- | --- |
| v0.22.0 | "The Threshold Release" | 13 Oct 2026 (published 14 Oct) |
| v0.21.7 | patch roll-up | 11 Oct 2026 |
| v0.21.6 | patch, security fixes | 8 Oct 2026 |
| v0.21.0 | — | 31 Aug 2026 |

v0.22.0 ships one backend/gateway for every profile, live subagent steering,
Kanban scheduling, delegation child routing with fallback providers, a
600-plugin catalog, and a codebase reduction from 1.06M to 698K lines.
v0.21.6 contains security fixes relevant to us: dashboard auth hardening and a
repository git-filter hardening that covers session snapshots, **subagent
worktrees**, kanban and worktree cleanup
(<https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6>).

Explicitly reverted and therefore *not* shipping: Collective Wisdom (org skill
marketplace), parallel group-chat rounds in Bot Mode, full isolation of named
profiles from the root `auth.json`, and blocking approval prompts.

Install on Windows native is `iex (irm https://hermes-agent.nousresearch.com/install.ps1)`
or signed MSIX (Windows 11 22H2+); data lives in `%LOCALAPPDATA%\hermes`,
config in `~/.hermes/config.yaml`, runtime Python 3.14, dependencies through its
own `hermes pm` package manager (<https://hermes-agent.nousresearch.com/docs/getting-started/installation>).

## The three team primitives, by exact name

### 1. `delegate_task` — structured subagent delegation

Source: <https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation>

- Children are isolated AIAgent instances with inherited tool access and their
  own terminal sessions; only the final summary enters the parent context.
- Up to 10 concurrent children by default (`delegation.max_concurrent_children`),
  `output_schema` contracts with one bounded correction retry, optional images.
- `role="leaf"` (default) vs `role="orchestrator"` nesting, gated by
  `delegation.max_spawn_depth` (default 1) with a global kill switch.
- Leaf children are blocked from `delegate_task`, `clarify`, `memory` writes,
  `send_message` and `cronjob` — they cannot talk to the user, write shared
  memory, cause side effects or schedule work in the parent's name.
- `delegation.worktree_isolation: true` gives each child its own git worktree
  on branch `hermes-subagent/<id>`.
- Live transcripts, `/steer`, `subagent.steer` RPC, stall monitor (450 s idle),
  per-child model pinning ("frontier planner, inexpensive workers"), and
  `/review` which spawns an independent full-privilege reviewer subagent.

### 2. Kanban — durable multi-agent task board

Source: <https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban>

- Every task is a row in `~/.hermes/kanban.db`; every worker is a full OS
  process with its own identity; peers read/write tasks directly.
- States: `triage | todo | ready | running | blocked | review | done | archived`,
  dependency links, comments as the inter-agent protocol, workspaces
  (`scratch` / `dir:` / `worktree`), per-board SQLite isolation.
- Dispatcher runs in the gateway on a tick (default 60 s): reclaims stale
  claims, promotes ready tasks, atomically claims, spawns assigned profiles.
- **Auto routing**: `kanban.auto_decompose: true` runs a decomposer that reads
  the profile roster plus `hermes profile describe --auto` descriptions and
  emits a JSON task graph (what to spawn, who it goes to, what depends on what).
- Nine collaboration patterns: fan-out, pipeline, voting/quorum, long-running
  journal, human-in-the-loop, `@mention`, thread-scoped workspace, fleet
  farming, triage specifier. GitHub PR completion contracts read branch
  protection and required checks.

### 3. Bot Mode — the named roster

Source: <https://hermes-agent.nousresearch.com/docs/user-guide/bot-mode>

- Each Bot is a **profile**: own config, memory, skills, credentials, chat
  history under `~/.hermes/profiles/<name>/`; roster UI with sections/search.
- `message_agent(target="researcher", message=...)` validates against the live
  roster, attributes messages, returns typed failure codes
  (`provider_auth_or_access`, `target_busy`, `delivery_timeout`).
- The teammate roster (names + roles) is injected into every Bot Chat system
  prompt. Group rooms: 2–6 bots, up to three serial rounds, `@mention` routing,
  `@user` escalates to the human with a "needs you" badge.
- `hermes peer add|dm|run|status|stop` allows cross-machine bot-to-bot DMs.

Supporting layers: profiles as the base unit with an explicit vocabulary
(Profile / Agent / Bot Mode bot / Messaging bot / Subagent), one gateway and
one desktop backend serving all profiles, seven terminal sandbox backends with
an unoverrideable hardline blocklist, a Skills Hub with install-time security
scanning and a hash ledger, `skills.write_approval` staging for agent-authored
skills, FTS5 cross-session memory with `memory.write_approval`, and working
directory checkpoints with `/rollback`
(<https://hermes-agent.nousresearch.com/docs/user-guide/security>).

## Where OpenJarvis stands today

Verified locally: dependency-free control desk at `127.0.0.1:18080/control`,
single server owning scheduler and Telegram routing, Ollama local aliases
(`local/fast`, `local/code`, `local/vision`), `security.private_operations`
default-deny read-only profile (active in the live config), keyed `/router/v1`,
capability catalog with accepted-vs-live fields, approval-gated setup, a
bounded notification delivery outbox, eight authored instruction-only skills,
scoped hash-bound knowledge index, and Model Lab synthetic checks.

**Already equivalent or better:** single-owner execution (no competing
scheduler/poller), explicit approval boundaries, evidence/finalizer ZIPs with
credential scanning, local-first inference with no account requirement, and
project/space inventory.

**Genuine gaps, ranked by how much they block "a team of agents":**

1. No durable task board with states, dependencies, reviews or assignees — the
   scheduler stores future work, not collaborative work in progress.
2. No agent roster: `default_agent = "orchestrator"` plus ad-hoc `--agent`
   names; no role descriptions, no routing surface, no statuses.
3. No real agent-to-agent messaging: `delegate_agent` exists as a translated
   tool name with no roster-validated delivery, attribution or failure codes.
4. Delegation is not a contract: no output schema, no concurrency bound, no
   depth gate, no per-child tool denial, no worktree isolation, no steer/stop.
5. Shell authority is a host-side `shell_exec` behind an approval gate; there
   is no always-on hardline floor and no container/WSL sandbox backend.
6. Skills have an audit but no install-time quarantine ledger and no staging
   approval for agent-authored skills.
7. Memory has FTS plus a scoped vector cache but no write gate concept beyond
   the private-operations policy, and no working-directory checkpoints.

## Proposed improvements, in dependency order

Each slice keeps the AGENTS.md rules: one scheduler, one server owner,
loopback by default, read-only unless approved, focused regression tests.

**T1 — Agent roster registry.** SQLite table (extend `agents.db`) with name,
role description, model alias, tool policy profile, memory scope, privacy
label and status; surfaced in the capability catalog and a control-desk Team
view. Acceptance: roster is queryable by CLI and API, unknown names cannot be
addressed, descriptions round-trip into a routing prompt. No behavior change.

**T2 — Task board on the existing scheduler store.** Add task states
`triage|ready|running|blocked|review|done`, dependency edges and comments;
drive dispatch from the existing scheduler tick so no second loop exists.
Acceptance: stale claims are reclaimed atomically, a blocked dependency never
runs, review state requires an explicit reviewer decision, restart preserves
every row.

**T3 — Routed decomposition (optional, approval-gated).** A `local/fast`
decomposer that reads the roster and proposes a task graph; it writes
*proposals* only. Acceptance: proposals carry reason strings and are never
auto-adopted; a malformed graph fails closed; no task is created without an
explicit approve action.

**T4 — Structured delegation with contracts.** Implement `delegate_task` as a
real tool: bounded concurrency (start at 3), `output_schema` contract, depth
gate (default 1, orchestrator role off), leaf children denied memory write,
channel send and scheduling; transcripts into `traces.db`; Steer/Stop buttons
in the desk. Acceptance: a denied child capability is never entered, a child
cannot schedule in the parent's name, partial results survive a parent restart.

**T5 — Independent reviewer role.** A reviewer pass pinned to a separate model
that only reads the diff and evidence and returns approve/request-changes;
feeds T2's review state. This is the machine version of the documented
"one writer, one reviewer" rule.

**T6 — Security depth.** Always-on hardline blocklist (recursive delete,
partition writes, pipe-to-shell) that no approval mode can override; per-surface
fail-closed defaults for cron and unattended runs; protected write paths
(`~/.ssh`, `credentials.toml`, `integration-secrets.json`, `wp-config.php`,
`.env`). Learn from Hermes v0.21.6: dashboard auth and worktree/snapshot
filters are exactly where their CVEs were.

**T7 — Skills governance.** Install-time quarantine plus a hash/fingerprint
ledger (`lock.json` equivalent) and `skills.write_approval` staging so any
future agent-authored skill lands as a pending diff, not a committed change.

**T8 — Sandboxed shell.** First WSL2 or Docker backend for `shell_exec` with
read-only repo mounts; keep native execution only for approved Windows tasks.

## Capabilities to add to the catalog

- `team.board`, `team.roster`, `team.message` — after T1–T2.
- `delegate.contract`, `review.independent` — after T4–T5.
- `sandbox.wsl` / `sandbox.docker` — after T8.
- `skills.quarantine`, `skills.staging` — after T7.
- `eval.trajectory_export` — Model Lab results in ShareGPT-style trajectories
  so local evaluations become reusable datasets (Hermes batch processing is
  the reference, <https://hermes-agent.nousresearch.com/docs>).
- `tools.lazy_loading` — rare tools behind on-demand loading; Hermes reports
  desktop schema tokens dropping 13,367 → 6,883, which matters on a 4K-context
  local model.

## Skills to author next

Already covered by the guided-operations branch: bounded-debugging,
weekly-review, document-to-actions, grounded-note, editor-handoff,
workstation-brief, private-project-plan, local-research-note.

Still missing from the 2026-10-12 research table, in order:

| Skill | Form | Boundary |
| --- | --- | --- |
| `source-ledger` | claim IDs, URLs, dates, content hashes, source-vs-conclusion split | public sources only, no silent adoption |
| `workstation-doctor` | read-only version/listener/storage evidence with remediation proposals | never modifies PATH or services |
| `dependency-review` | deterministic checks plus model explanation | explicit public query preview before any network use |

New team-flavored skills once T1–T5 exist:

| Skill | Form | Boundary |
| --- | --- | --- |
| `route-task` | choose a roster member from role descriptions, emit a task proposal | proposal only, no auto-assign |
| `review-request` | produce diff, evidence paths and acceptance commands for the reviewer | read-only, one reviewer |
| `fleet-triage` | split one objective into board tasks with dependencies | draft graph, explicit approval |
| `handoff-journal` | long-running work journal with resume notes | local notes, no scheduling |

Do not port Hermes bundles that spawn agents, send mail, deploy or manage
accounts; the ecosystem note already blocks those categories
(`docs/research/EHSAN_ECOSYSTEM_SOURCES_2026-10-12.md`).

## Publishing ideas (GitHub projects)

Prerequisite for all of them: restore push authentication; publishing has been
historically blocked and no recent commit has seen CI.

1. **`agentskills-auditor`** — standalone CLI that validates SKILL.md bundles
   against the agentskills.io specification and reports exact/adapted/unsupported
   tool semantics, parameterized and snake_case tools, executable resources
   outside `scripts/`, dangerous capabilities, conflicts, and provenance
   (source URL/commit/license/content hash). Built already inside
   `src/openjarvis/skills/tool_translator.py` and `importer.py`; extraction is
   mostly packaging. Serves every harness that reads SKILL.md.
2. **`loopback-audit`** — one command that lists listeners, their owning
   process, firewall rules, service-config bind settings and flags anything
   not on loopback, with evidence output. We just did this manually for Ollama
   (`expose=1` → `OLLAMA_HOST=http://0.0.0.0:11434`), Voicebox (`0.0.0.0:17493`)
   and the dashboard. Small, Windows-first, no dependencies.
3. **`control-board`** — the durable multi-agent task board as a dependency-free
   package: SQLite states, dependency edges, atomic claims, comment protocol,
   dispatcher driven by a caller-supplied tick. Hermes has this in-tree; a
   standalone embeddable version would serve OpenCode/Claude Code/Codex users.
4. **`task-contract`** — an open handoff format (task ID, repo, base commit,
   dirty state, role, allowed files/tools, privacy label, runtime owner,
   acceptance commands, evidence paths, blocker, handoff owner) with a validator
   and generator. The task contract is already specified in prose in the
   2026-10-12 research; standardizing it is publishable and directly useful to
   the one-writer/one-reviewer rule.
5. **`local-model-eval-pack`** — the synthetic qualification suite (12 coding,
   10 research, 8 routing, 20 retrieval cases) as a runnable benchmark with
   digest-bound results and trajectory export. Local-model comparisons are a
   crowded topic, but a *privacy-preserving, no-execution* suite for small
   machines is not.
6. **`capability-readiness`** — the installed/configured/accepted/live/
   observation-age readiness model as a small spec and CLI, born from finding 8
   of the upgrade research (a catalog that said READY while the API was offline).

Recommendation: ship **2** first (hours of work, immediate value, no
decisions needed), then **1** and **4** together (they reinforce the skill
work in Phase B), and treat **3** as the flagship only after T1–T2 prove the
data model locally.

## Sources

- <https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.0>
- <https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.7>
- <https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6>
- <https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation>
- <https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban>
- <https://hermes-agent.nousresearch.com/docs/user-guide/bot-mode>
- <https://hermes-agent.nousresearch.com/docs/user-guide/profiles>
- <https://hermes-agent.nousresearch.com/docs/user-guide/security>
- <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills>
- <https://hermes-agent.nousresearch.com/docs/getting-started/installation>
- <https://agentskills.io/specification>
- <https://github.com/NousResearch/hermes-agent-self-evolution>
- Local: `docs/research/EHSAN_ECOSYSTEM_SOURCES_2026-10-12.md`,
  `docs/research/EHSAN_OPENJARVIS_UPGRADE_RESEARCH_2026-10-12.md`,
  `docs/EHSAN_GUIDED_OPERATIONS.md`
