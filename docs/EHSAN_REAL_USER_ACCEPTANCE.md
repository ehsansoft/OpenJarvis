# Phase 0.5: Real User Acceptance

Branch: `feature/ehsan-real-user-acceptance`. Foundation changes remain in this
working tree. Project Intelligence migrations have not started.

## Publication verification: 2026-10-09

The reviewed publication gate expands the earlier 611 tests to **704 passed**.
It covers the required control-plane suite, operator compatibility, standalone
research security, MCP shutdown ownership, permission inventory and evidence
packaging. The five Foundation tools now have explicit read/network permission
requirements; denied dispatch never reaches their implementations.

The full cross-platform suite was also attempted on Windows: **8,968 passed,
50 failed, 11 errors, 79 skipped**, with **66.21% coverage** (60% required).
This is not a full Windows pass. Three fixture contracts introduced by Phase
0.5 and the omitted permission inventory were corrected and their suites pass.
Remaining failures include POSIX shell/permission/sysfs assumptions, Windows
path handling, optional integration environments and trace database teardown.
The Ubuntu full-suite and designated Windows CI jobs must independently pass
on the published head before project-state migration is considered.

The real-machine finalizer completed all 11 steps successfully, reusing the
running loopback server. Inspection found that its old recursive ZIP writer
included synthetic pytest databases. Success and failure bundles now include
only numbered text/JSON reports and redact secret environment values and token
patterns. Existing bundles are preserved; use the new curated publication
evidence rather than sharing an earlier bundle containing test directories.

Fresh live acceptance still distinguishes automated inference checks from the
unloaded Kokoro and human microphone/Telegram/editor gates. No model was pulled,
no external recurring workflow was enabled, and no project state was migrated.
The branch is being published for draft-PR CI; this document does not claim a
merge, tag, deployment or completed human acceptance.

## Prioritized findings and implementation

| Priority | Finding | Change |
| --- | --- | --- |
| P0 | Scheduler daemon had no system and reported dry runs as success | Execution requires a system; `scheduler start` invokes the canonical server |
| P0 | Scheduler stored `ask()` dictionaries as SQLite text | Extract content and propagate error results; retain task/log tables |
| P0 | Telegram allow-list was omitted from both construction paths | Both paths forward it; adapter checks inbound and outbound chat ids |
| P0 | Serve wired a native channel to one system, then wrapped it in a bridge without a system | One server system; native adapter → ChannelBridge → system → adapter reply |
| P0 | Task notifications could broadcast across opted-in users | Task metadata selects one matching opted-in session; no destination means no notification |
| P0 | Private knowledge could reach capability-ranked remote research models | Personal preset enables fail-closed private routing; private model failure cannot fall back remotely |
| P1 | Multiple owners and teardown could retain background workers | OS-held scheduler/server locks, lifecycle ownership, callback draining, idempotent poller registration |
| P1 | Local Qwen vision capabilities were absent; embed-only models could enter chat pool | Inspect installed Ollama metadata; use local aliases and exclude embeddings |
| P1 | Personal research assumed Qwen 4B | Use `local/research`; protect CLI and HTTP research planners |
| P1 | Voice chat did not reuse Voicebox TTS | Loaded-model-only Voicebox WAV adapter; configured Voicebox never falls back to cloud TTS |
| P1 | Skill danger checks missed declared shell/write tools | Infer dangerous capabilities from allowed-tools/steps; add read-only audit with translations and conflicts |
| P1 | Security/telemetry wrappers inherited permissive model availability | Delegate `can_serve()`; reject private HTTP remote overrides before memory or agents, including streaming |
| P1 | Newly started finalizer server had two-second model probes | Give cold-start roster discovery the same 30-second timeout as existing servers |

The server's bridge is the canonical inbound route. It registers native
`on_message()` callbacks; it is not a BaseChannel and must not be passed to
`JarvisSystem.wire_channel()`. That older method remains an SDK compatibility
path for standalone native adapters. Serve never wires both paths.

## Routing and installed models

| Alias/use | Policy |
| --- | --- |
| `local/code` | Installed qwen2.5-coder:7b preferred for coding |
| `local/fast` | Installed qwen3.5:2b preferred; optional when absent |
| `local/research`, `local/vision`, `local/auto` | Installed local models ranked by declared capabilities |
| `nomic-embed-text` | Local 768-dimensional knowledge embeddings, never chat generation |
| `free/*` on `/router/v1` | Public/synthetic requests; may use positively qualified free remote providers |
| Personal `/v1`, chat, ask, channels, scheduled prompts, private research | With `private_routing=true`, `free/*` is constrained to local execution; explicit remote model ids are rejected |

The control-plane preset enables `[intelligence] private_routing=true` and
`allow_private_remote=false`. The latter is the explicit configuration opt-in
for private remote inference; leave it false. Upstream generic presets retain
their existing routing behavior. An editor can attach repository files itself,
so use its default **local-code** model for private projects. Public aliases are
an explicit client choice, not an automatic privacy classifier. Web search and
other network tools can send their query text externally: do not provide private
chunks to them. Inference privacy does not sandbox every network tool.

Ollama storage observed on this workstation: `D:\Ollama-Models`, approximately
7.64 GB; the user-profile store is empty. All three requested models are already
installed. No model pulls, cache migrations, or project migrations are required.
The personal config sets `[engine.ollama] num_ctx=4096` for this 16 GB CPU
machine. Live switching between the 7B and 2B models caused allocation failures
at the previous 16K default; the 4K checks passed. Larger requests and concurrent
inference still need load testing. Explicit per-request context overrides take
precedence.
The existing nomic embedder is immediately compatible. Existing lexical memory
is not silently reindexed or converted to a vector database.

The native Windows extension was missing from the Foundation virtual environment.
It was built successfully with the existing Rust/MSVC/Maturin toolchain using
`uv run maturin develop --manifest-path rust/crates/openjarvis-python/Cargo.toml`.
Future installer syncs include `--group desktop-native` so they retain the required
native memory/security extension. No PATH or compiler installation was needed.

## Acceptance command and evidence

From this checkout:

```powershell
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
uv run jarvis acceptance --live
# Optionally transcribe an existing synthetic WAV with loaded Whisper:
uv run jarvis acceptance --live --speech-fixture D:\AI-Control\OpenJarvis\support\voicebox-stt-acceptance.wav
```

The command runs isolated regression fixtures for all requested interaction
surfaces, local alias inference, an actual synthetic vision image, local nomic
embedding, a real scheduled prompt in a separate acceptance SQLite file, a real
CLI chat, memory index/search, and synthetic local Deep Research. It creates
`acceptance.json`, regression output, and an allow-listed support ZIP under
`D:\AI-Control\OpenJarvis\support`. It never enables personal schedules or
Telegram, imports live community skills, downloads models, or modifies editor
configurations. `--skip-regression` records tests as NOT_RUN; it is for focused
runtime diagnosis, not full acceptance.

PASS/AUTOMATED_PASS, FAIL, BLOCKED and MANUAL_REQUIRED are distinct. Automated
voice/chat fixtures do not certify a real microphone or human listening. Live
Telegram and editor acceptance require the manual steps below. The gate remains
`ready_for_personal_automations=false` while these human checks remain open.

Only curated reports/logs and templates enter the ZIP. Credential/config stores,
chat databases, project chunks and model files are excluded. Token patterns and
secret environment values are redacted. Inference response text is hashed rather
than saved. Inspect a ZIP before sharing it externally.

### Workstation evidence: 2026-10-08

- Final expanded regression suite: **611 passed**, including the required
  control-plane suite plus Ollama, security-wrapper and telemetry regressions.
  Ruff checks, formatting and `git diff --check` passed. Deprecation warnings
  remain for existing FastAPI/Starlette interfaces. GitHub CI was not run.
- Live acceptance: all seven local/free alias checks (local inference scope),
  real red-image vision, nomic 768-dimensional embedding, scheduled inference,
  CLI chat, memory index/search, local Deep Research and Voicebox STT passed.
- Actual editor API: local-code completion HTTP 200; models and health HTTP 200.
  Private remote overrides return HTTP 400 for both streaming and non-streaming.
  Current server PID at verification: 18996; listener `127.0.0.1:8000`.
- The full Foundation finalizer verified doctor, Voicebox/MCP, machine and free
  rosters, 600 project metadata entries and the existing daily inventory task.
  Its final cold-server probe failed. After correcting the timeout, the final
  tests and server probe were rerun; successful earlier probes were reused and
  their provenance retained. No repeat project scan or migration was needed.
- Curated acceptance ZIP:
  `D:\AI-Control\OpenJarvis\support\acceptance-phase05-final-20261008-183738.zip`.
  Expanded machine evidence ZIP:
  `D:\AI-Control\OpenJarvis\support\openjarvis-phase05-20261008-183738.zip`.
  The latter includes local machine/project metadata and should be treated as
  personal support evidence. Earlier failed evidence bundles are preserved.

TTS remains blocked by unloaded Kokoro; microphone/listening, real Telegram,
editor clients, community Hermes source/import review and research answer
quality remain manual acceptance. Personal scheduler/channel config remains
disabled, and no Project Intelligence migrations have started.

## Manual Telegram setup

1. In Telegram, open **@BotFather**, run `/newbot`, and copy its token privately.
   Keep the bot token out of repository files and shell literals.
2. Stop the existing OpenJarvis server through its owning terminal before doing
   the one-time chat-id lookup. Do not run `jarvis channel listen` alongside
   `jarvis serve`; that creates a competing bot poller.
3. Set the token in the server's PowerShell session using hidden input:

```powershell
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
$telegramCredential = [pscredential]::new('telegram', (Read-Host 'Telegram bot token' -AsSecureString))
$env:TELEGRAM_BOT_TOKEN = $telegramCredential.GetNetworkCredential().Password
```

4. Open your new bot in Telegram, click Start and send `acceptance ping`.
   With the server still stopped, obtain only the chat id:

```powershell
try {
    $telegramUpdates = Invoke-RestMethod -Uri ('https://api.telegram.org/bot' + $env:TELEGRAM_BOT_TOKEN + '/getUpdates')
    $telegramUpdates.result | ForEach-Object { $_.message.chat.id } | Sort-Object -Unique
} catch { Write-Error 'Telegram lookup failed. Check the token privately; do not share the exception URL.' }
```

5. Merge these sections into **the existing**
   `D:\AI-Control\OpenJarvis\config.toml`, replacing the chat-id placeholder.
   Do not duplicate existing TOML tables. Leave the token exclusively in the
   environment. An empty allow-list permits all chats in the generic adapter;
   always configure a nonempty allow-list for this personal deployment.

```toml
[channel]
enabled = true
default_channel = "telegram"
default_agent = "orchestrator"

[channel.telegram]
allowed_chat_ids = "YOUR_NUMERIC_CHAT_ID"
parse_mode = "Markdown"

[scheduler]
enabled = false
poll_interval = 10
db_path = "D:\\AI-Control\\OpenJarvis\\scheduler.db"
```

6. Start exactly one loopback server in that same PowerShell:
   `uv run jarvis serve --host 127.0.0.1 --port 8000`.
   Send `Reply TELEGRAM_OK`, then `/notify telegram`. Verify one reply each.
   A second, unlisted Telegram account must receive no reply. Restart the server
   in the same token-bearing shell and confirm history isolation and one reply
   per message. Messages arriving during restart are not a durable delivery SLA.
7. After accepting chat, explicitly restart the same server with
   `uv run jarvis serve --scheduler --scheduler-poll-interval 10` for one bounded
   schedule test. Do not start a separate scheduler or channel daemon.

In another shell with the same OPENJARVIS_HOME:

```powershell
uv run jarvis scheduler create "Reply SCHEDULED_OK" --type once --value "2099-01-01T00:00:00+00:00" --agent none --notify-chat YOUR_NUMERIC_CHAT_ID
# Copy the returned task id:
uv run jarvis scheduler run TASK_ID
uv run jarvis scheduler logs TASK_ID
```

Expect a real model response in the log and one Telegram notification in your
opted-in session. A missing `/notify telegram`, wrong destination, or missing
token must not broadcast elsewhere. For cron, use an explicit IANA timezone:

```powershell
uv run jarvis scheduler create "Summarize the day" --type cron --value "0 9 * * *" --timezone Asia/Tehran --agent none --notify-chat YOUR_NUMERIC_CHAT_ID
uv run jarvis scheduler pause TASK_ID
```

Cron is evaluated in that timezone and stored as UTC. One-time schedules require
an explicit UTC offset; intervals must be positive. Both `scheduler run-task`
(lookup by agent) and `scheduler run TASK_ID` delegate to the owned task API.

## Exact OpenCode and Kilo merges

Neither CLI was found on this session's PATH. No editor was installed or
reconfigured. Determine your installed version with `opencode --version` or
`kilo --version` before selecting a template.

For OpenCode v2, merge `configs/editors/opencode.openjarvis.jsonc` into your
existing project `opencode.jsonc`: add the `providers.openjarvis` object and set
`model` to `openjarvis/local-code`. Preserve all unrelated providers, agents,
permissions and MCP settings. Its `package`, `settings`, `modelID` and plural
`providers` fields match the [v2 provider documentation](https://opencode.ai/v2/docs/providers).
For OpenCode v1, use `configs/editors/opencode-v1.openjarvis.jsonc` instead: merge
`provider.openjarvis`, then select `openjarvis/local/code`; it uses singular
`provider`, `npm` and `options`, matching the [v1 provider documentation](https://opencode.ai/docs/providers).
Run `/models` and select that local coding model. Ask it to return a two-line
Python function in chat without applying file changes. Private repository work
must stay on a `local/*` model. For explicitly public research, select the
template's public research model.

For Kilo CLI 1.x, merge `configs/editors/kilo.openjarvis.jsonc` into your existing
project `kilo.jsonc`: add only the `provider.openai-compatible.models` entries and
the endpoint `options.baseURL=http://127.0.0.1:8000/router/v1`; set `model` to
`openai-compatible/openjarvis-local-code`. If that provider already serves a
different endpoint, retain it and use a separate custom provider profile through
the Kilo Providers UI rather than overwriting it. Run `kilo models` and choose
the local coding model. These paths/model-id mappings follow the [Kilo CLI](https://kilo.ai/docs/code-with-ai/platforms/cli)
and [custom-model documentation](https://kilo.ai/docs/code-with-ai/agents/custom-models).
For Kilo's VS Code extension, use Settings → Providers → Custom provider →
OpenAI Compatible; base URL is the router endpoint above, model `local/code`.
The CLI JSON template is not a VS Code settings export.

If local server authentication is enabled, provide OPENJARVIS_API_KEY privately
in the editor's global/trusted credential settings. Do not place credentials in
project config or Git. Project-level Kilo configs cannot resolve secret env
references. With authentication disabled on loopback, leave the key empty (or
use a non-secret placeholder only if the client requires one).

## Voice, research and Hermes manual checks

Run `uv run jarvis chat -m local/fast`, then
`uv run jarvis chat --voice -m local/fast`. Press Enter to record, speak a short
sentence, and inspect the transcription and listen to the response. The personal
configuration uses `speech.backend="voicebox"` and `tts_backend="voicebox"`.
Load **the already cached Kokoro model** in Voicebox before TTS; the adapter
refuses to load/download models itself. Keep STT on an already loaded Whisper
model. The current Voicebox service was already bound beyond loopback; this work
does not change its exposure. Changing that existing service's binding requires
the user's separate instruction.

Hermes research/coding/productivity resolver/import tests use isolated fixtures;
scripts are excluded, declared dangerous tools require explicit confirmation,
translations/untranslated tools and existing-install conflicts are reported.
Audit an existing cache without fetching or importing:

```powershell
uv run jarvis skill audit hermes --category research
uv run jarvis skill audit hermes --category coding
uv run jarvis skill audit hermes --category productivity
```

After reviewing an individual benign cached skill, its install command is
`uv run jarvis skill install hermes:CATEGORY/SKILL_NAME`. The installer refreshes
the source cache first. Do not use `--with-scripts`, `--yes-dangerous`, `--force`,
or bulk sync without reviewing the concrete source and its requested behavior.
No live community skill is imported by acceptance checks.
Live cached audits currently report `cache_present=false` for all three
categories. The isolated fixtures translate `Read` to `file_read`, report
`MysteryTool` as untranslated, skip `scripts/`, and detect an existing target
as a conflict. `Bash`/`Write` declarations trigger the dangerous-capability
approval gate before any import. A real community skill still needs source
review before installation.

## Remaining acceptance limits

Human Telegram account/token, real microphone/audio-device listening, editor
client configuration and creative/research answer quality remain separate gates.
No paid-provider qualification, release, push, deployment or Project Intelligence
migration is claimed. Exactly-once execution after a process crash is not
guaranteed: a crash between external side effects and SQLite completion can cause
a retry. Keep scheduled tools read-only until that risk is accepted.
The live `free/*` acceptance checks used the installed local pool. Remote free
entitlement discovery does not certify those providers' inference quality.
Blocked native-extension builds or unloaded Voicebox models must remain visible
in evidence rather than being described as a full acceptance pass.
