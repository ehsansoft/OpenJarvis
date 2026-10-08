# Ehsan OpenJarvis Control Plane — Target Architecture

Status: working design for the `feature/ehsan-control-plane-foundation` branch.

## 1. Product boundary

This fork should be a **local-first personal AI control plane**, not another
single-purpose chatbot and not a Livora-only system.

It coordinates:
- local models and zero-API-cost remote models;
- developer tools and editors;
- repositories and projects across `D:\Projects`;
- WampServer and local WordPress/PHP environments;
- Voicebox speech/transcription;
- research and current-information workflows;
- personal task/reminder/job/resume/project workflows;
- reusable site connectors for multiple domains.

The system should understand the workstation, select the right capability,
execute safe work, retain useful project knowledge, and improve routing and
recommendations from measured evidence.

## 2. High-level architecture

```text
┌──────────────────────────────── CLIENTS ────────────────────────────────┐
│ Codex VS Code │ OpenCode │ Kilo Code │ CLI │ Web UI │ future channels │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                    OpenAI-compatible / MCP interfaces
                                │
┌───────────────────────────────▼─────────────────────────────────────────┐
│                 OPENJARVIS LOCAL CONTROL PLANE :8000                    │
│                                                                         │
│  /router/v1  Direct editor/model gateway                               │
│  /v1         Personal agent API                                        │
│  /docs       Runtime/API discovery                                     │
│                                                                         │
│  Orchestrator ─ Capability Router ─ Approval/Security ─ Scheduler       │
└───────┬───────────────────┬────────────────────┬────────────────────────┘
        │                   │                    │
        ▼                   ▼                    ▼
┌──────────────┐   ┌──────────────────┐   ┌──────────────────────────────┐
│ MODEL FABRIC │   │  TOOL / MCP BUS  │   │ PROJECT + KNOWLEDGE FABRIC  │
│              │   │                  │   │                              │
│ Ollama       │   │ Voicebox MCP     │   │ Project registry            │
│ Nara free    │   │ filesystem       │   │ Repo/site manifests         │
│ future free  │   │ Git/GitHub       │   │ SQLite/FTS                  │
│ providers    │   │ browser/research │   │ embeddings / RAG            │
│ Voicebox LLM │   │ WAMP/WP adapters │   │ tasks / decisions / traces  │
└──────┬───────┘   └────────┬─────────┘   └──────────────┬───────────────┘
       │                    │                            │
       └────────────────────┴────────────┬───────────────┘
                                         ▼
                              EVAL / OBSERVABILITY LOOP
                              benchmark → evidence → route
                              → recommendation → tested PR
```

## 3. Model fabric

### 3.1 Stable capability aliases

Clients should depend on stable aliases, never volatile free-provider IDs:

| Alias | Purpose | Preferred behavior |
|---|---|---|
| `free/code` | coding/editor work | best eligible local or free coding model |
| `free/research` | synthesis/research | long-context/reasoning capable pool |
| `free/vision` | screenshots/images | vision-capable eligible model |
| `local/code` | offline coding | Ollama coding model only |
| `local/fast` | cheap local tasks | smallest adequate local LLM |
| `local/vision` | offline image work | installed local multimodal model |
| `local/embed` | RAG/indexing | installed embedding model |

Routing inputs should include capability, latency, context length, observed
quality, memory pressure, current provider entitlement, previous failures and
task cost.

### 3.2 Provider adapters

Implement providers behind one interface:

```text
discover() -> live models + capabilities + entitlement
health()
generate()/stream()
cost_policy() -> free / paid / local
usage()
benchmark_result()
```

NaraRouter is the first dynamic free provider. Additional free providers should
be adapters, not special cases scattered through the codebase.

### 3.3 Model lifecycle

Maintain a local model registry that merges:
- Ollama `/api/tags`;
- Voicebox `/models/status`;
- Hugging Face cache observations;
- benchmark history;
- hardware fit;
- model capability metadata.

Never auto-download a large model because it exists in a catalog. Recommend,
estimate disk/RAM impact, then require approval.

## 4. Voice fabric

Voicebox is a first-class sibling service.

```text
microphone/audio
    ↓
Voicebox Whisper/STT
    ↓
OpenJarvis orchestrator
    ↓
model router + tools
    ↓
Voicebox TTS
```

Use the canonical MCP endpoint `http://127.0.0.1:17493/mcp/` and REST status
endpoints for diagnostics. Prefer Voicebox's already-loaded models over loading
duplicate speech weights in OpenJarvis.

## 5. Project fabric

### 5.1 Canonical project registry

Every discovered root gets a persistent identity and role:

```text
active | reference | archive | template | generated | unknown
```

A project record should eventually include:
- canonical path and aliases;
- Git remote/branch/status/last activity;
- languages/frameworks/package managers;
- runtime requirements;
- local URL / WAMP vhost;
- production/staging URLs;
- site type (WordPress, WooCommerce, Node, Python, Remotion, etc.);
- owner/workspace tags;
- related repositories/components;
- health/test commands;
- last audit summary;
- open tasks/TODOs;
- knowledge-index status.

Reference repositories remain searchable but must not inflate the active-work
dashboard.

### 5.2 Project manifest

Add an optional `.openjarvis/project.toml` per important project. It is the
human-editable source for facts the scanner cannot safely infer.

Example:

```toml
name = "example-site"
role = "active"
kind = "wordpress"
local_url = "http://example.local"
production_url = "https://example.com"

[commands]
test = "..."
build = "..."
lint = "..."

[knowledge]
include = ["README.md", "docs/**", "src/**"]
exclude = [".env", "wp-config.php", "node_modules/**", "vendor/**"]
```

## 6. Environment Doctor

Environment Doctor should answer “why does this project work in one terminal
but not another?”

It needs:
- Python/uv/pip environments;
- Node/npm/pnpm/bun and NVM/FNM/Volta ownership;
- duplicate executable resolution order;
- PHP/Composer versions;
- WampServer Apache/MySQL/MariaDB/PHP versions and services;
- Ollama version/storage/models;
- Voicebox version/model cache;
- Git/GitHub CLI;
- disk/RAM/GPU pressure;
- project-specific runtime compatibility.

Output findings with severity, evidence and a command-safe remediation plan.
Never modify PATH or uninstall runtimes automatically.

## 7. Knowledge and RAG

Use two tiers:

**Tier A — lexical/local metadata**
- SQLite/FTS for project records, logs, notes, tasks and exact lookup.
- Cheap and always available.

**Tier B — semantic**
- local embedding provider;
- chunked docs/code summaries;
- project-scoped retrieval;
- provenance on every retrieved chunk.

Index source material, not secrets. Exclude credential files, caches, generated
trees, `node_modules`, `vendor`, build outputs and large binaries by default.

The semantic index must be rebuildable from source. It is not the source of
truth.

## 8. Developer/editor integration

Codex, OpenCode and Kilo Code should talk to the same editor gateway:

```text
base URL: http://127.0.0.1:8000/router/v1
model:    free/code
```

The editor path must stay direct and OpenAI-compatible. The personal-agent path
may use server tools, memory and orchestration.

Per-project agent context should come from:
1. root `AGENTS.md`;
2. project manifest;
3. relevant repo docs;
4. retrieved project knowledge;
5. current Git/test state.

Avoid stuffing the whole D: drive into every prompt.

## 9. Site fabric

Do not hard-code individual domains into core logic. Add reusable site records
and adapters.

Planned adapters:
- WordPress REST / application-password adapter;
- WooCommerce adapter;
- WP-CLI adapter for local WAMP sites;
- generic HTTP/site-health adapter;
- analytics/search-console connectors when credentials are explicitly added.

A site record links production URL ↔ project ↔ local vhost ↔ repository.

Write operations need an approval gate and audit entry.

## 10. Personal operations fabric

Build these as workflows on top of the same scheduler/tool system:
- reminders and recurring tasks;
- daily/weekly project briefing;
- research/news watchlists;
- job discovery and scoring;
- resume/CV variants from a canonical profile;
- new-project bootstrap;
- inbox/task triage when connectors are available.

Each workflow should have explicit inputs, schedule/trigger, output destination,
and history. Do not mix ephemeral chat history with durable task state.

## 11. Safe self-improvement loop

“Learn and improve itself” means **eval-driven adaptation**, not uncontrolled
self-modification.

```text
traces + failures + latency + benchmark tasks
                ↓
        scored evidence store
                ↓
 routing / prompt / tool recommendations
                ↓
       candidate code/config patch
                ↓
   focused tests + regression suite + evals
                ↓
         reviewable Git commit / PR
                ↓
           human promotion
```

Allowed automatic changes:
- short-lived routing decisions;
- benchmark scores;
- caches;
- derived indexes;
- recommendations.

Human-reviewed changes:
- source code;
- security policy;
- model downloads;
- filesystem reorganizations;
- website writes/deployments;
- scheduled external actions.

## 12. Observability and safety

Persist:
- selected model/provider and reason;
- fallbacks;
- latency and failures;
- tool calls;
- task/agent trace IDs;
- approval decisions;
- benchmark outcomes;
- project scanner findings.

Never persist plaintext secrets into support bundles or model prompts.

Personal HTTP services should remain loopback-bound. A service listening on
`0.0.0.0` should be surfaced as a security finding.

## 13. Build sequence

### Gate 0 — Foundation acceptance
Definition of done:
- focused control-plane suite green;
- GitHub CI green;
- `GET /health`, `GET /router/v1`, `GET /router/v1/models` work;
- editor completion works with `free/code`;
- Voicebox REST + MCP discovery works;
- no misleading Rust/rate-limit warning;
- finalizer creates a success ZIP.

### Phase 1 — Project Intelligence
Build canonical registry, roles, project manifests, repo summaries, tech-stack
detection, WAMP/site associations, active-work dashboard and project health.

### Phase 2 — Environment Doctor
PATH/runtime conflict analysis, per-project requirements, WAMP/Ollama/Voicebox
health, storage pressure and reviewed cleanup plans.

### Phase 3 — Knowledge Fabric
Project-scoped ingestion, provenance, local embeddings, semantic search and
knowledge freshness/rebuild commands.

### Phase 4 — Model Lab
Capability benchmarks, local/free model scorecards, hardware-aware routing,
roster change detection, failover and alias promotion rules.

### Phase 5 — Developer Autopilot
Task → inspect → plan → edit → test → diff → commit workflow with approval
boundaries, usable from Codex/OpenCode/Kilo.

### Phase 6 — Site Operations
Reusable WordPress/WooCommerce/WP-CLI/site-health adapters and audited,
approval-gated write workflows.

### Phase 7 — Personal Operations
Tasks/reminders, research/news digests, job finder, resume generation and
project bootstrap workflows.

### Phase 8 — Continuous Improvement
Eval-driven routing/prompt/tool optimization, regression dashboards and
candidate self-improvement PRs.

## 14. Immediate next implementation slice

Do **not** start Phase 1 until Gate 0 passes.

Current priority:
1. fix the NaraRouter registry-restoration identity regression;
2. rerun the focused suite;
3. finish Alpha 4.3 finalizer;
4. verify `/router/v1`, `/router/v1/models`, one editor chat completion and
   Voicebox MCP;
5. tag the foundation baseline;
6. begin Project Intelligence in a new feature branch.
