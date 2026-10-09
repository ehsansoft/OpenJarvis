# Phase 1B: workstation capability catalog

This phase adds one shared, read-only readiness service and two CLI views:

```powershell
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis capabilities
uv run --no-sync jarvis capabilities --json
```

The contract is version 1. Its JSON Schema is
`configs/openjarvis/schemas/capability-catalog-v1.schema.json`. Every capability
has an id, display name, status, configured/installed/accepted facts, reason,
evidence, observation time, next action, commands, privacy and dependencies.
Unknown installation state is represented by `null`, never inferred from a
missing optional editor CLI.

| Status | Meaning |
| --- | --- |
| READY | Current observations and applicable acceptance evidence agree. |
| MANUAL_SETUP | Configuration or presence exists, but acceptance is missing. |
| DISABLED | The capability is deliberately unconfigured or disabled. |
| BLOCKED | A required service, model state or prerequisite prevents use. |
| NOT_INSTALLED | An applicable component is positively absent. |
| NOT_APPLICABLE | The current workstation or selected-site context does not apply. |

READY describes the named surface. Registry/review READY means existing proposals
can be inspected; it does not mean projects were confirmed or adopted. Model
metadata alone does not qualify chat, vision, embedding or speech inference.
Synthetic speech does not qualify the microphone or the user's listening.

## Prioritized findings and fixes

1. Voicebox 0.5.0's installed `/models/load` accepts `model_size` as a query
   parameter, not `model_name` JSON. Posting `{"model_name":"kokoro"}` selects
   the default Qwen loader. Do not repeat that request. The matching upstream
   issue is <https://github.com/jamiepine/voicebox/issues/977>.
2. Voicebox `/generate/{id}/status` is an SSE stream. Jarvis previously parsed it
   as JSON. TTS now polls `/history/{id}`, then fetches the completed WAV. The
   regression reproduces the actual event-stream response and verifies one
   generation request, JSON polling and playable WAV output.
3. Workstation proxy variables could forward local model/audio requests through
   a proxy, causing intermittent local 503 errors. Ollama's synchronous and
   asynchronous clients, Voicebox STT/TTS, both embedders, MCP and finalizer bypass
   environment proxies for loopback URLs. Remote and LAN hosts retain their
   existing proxy behavior. Tests use a real loopback fixture with an unreachable
   proxy, including CGI-compatible lowercase environment variables.
4. Legacy acceptance reports could retain READY after a model was replaced under
   the same tag. New live reports carry a hash of model digests/capabilities and
   non-secret routing/speech settings. The catalog invalidates mismatches. Older
   reports without that hash require renewed acceptance.
5. Voicebox can report Whisper Base loaded while its downloaded flag is false.
   Loaded state proves installation; the catalog preserves the inconsistent
   upstream cache flag in diagnostic text instead of reporting NOT_INSTALLED.

## Evidence and boundaries

Metadata probes use explicit request timeouts, a total response deadline and
response-size limits. Loopback GETs are restricted to health, model lists and
profiles. Ollama `/api/show` is a read-only metadata POST. No redirects or proxy
forwarding occur. Nara uses bounded live entitlement/plan intersection without
inference; missing credentials and unavailable rosters are distinct states.

Only the newest existing acceptance report can qualify a capability. Its UTC
timestamp must be within 24 hours, individual checks must pass, and model/config
context must match. A newer failure never falls back to an older success.
Human gates require explicit human evidence bound to the current context; legacy
bare PASS records cannot certify an editor, Telegram, microphone or site.

The command does not start services, initialize/load/download models, open
SQLite, create a capability database, refresh caches, sync skills, index sources,
execute project commands, mutate configuration or enable personal automations.
It also skips the CLI's background update poll. Credential values are never
included; errors report their type and safe HTTP status instead of raw bodies.

The catalog covers local chat, the personal API, four local aliases, embeddings,
Ollama, Nara, Voicebox, Whisper, Kokoro, microphone/listening, vision, memory,
scoped project memory, Deep Research, public research, scheduler, Telegram,
OpenCode, Kilo, GitHub, MCP, Hermes, registry/review, WAMP, WordPress, WooCommerce,
doctor and hygiene. Sites are NOT_APPLICABLE until a site is selected. Scoped
project memory remains BLOCKED until its approved later phases exist.

## Voice acceptance on this workstation

The user explicitly authorized cached Kokoro activation and playback during this
continuation. Existing Kokoro weights, George voice vectors and English language
dependencies were inspected first. One Kokoro `/speak` request initialized the
cached engine. No model-download endpoint was called. The existing OpenJarvis
client binding and Voicebox default playback voice now select George/Kokoro;
captures select already-loaded Whisper Base instead of uncached Whisper Turbo.
Previous non-secret Voicebox settings are backed up outside Git in the support
directory. Other client bindings are preserved.

The user confirmed hearing the first synthetic George sentence clearly. A real
typed turn through `jarvis chat --voice -m local/fast` then generated and played a
reply. Microphone acceptance still requires the user to press Enter and speak:

```powershell
uv run --no-sync jarvis chat --voice -m local/fast
```

At the prompt, press Enter without typing, say a short English sentence, pause
for silence detection, inspect the transcription and listen to the reply.
Typing a message at the same prompt tests local inference and speech output.
Use `/quit` to exit. After a Voicebox restart, initialize an already-cached
Kokoro preset through its Generation UI before retrying; Jarvis intentionally
does not automatically load or download it.

Fresh technical acceptance and support evidence:

```powershell
uv run --no-sync jarvis acceptance --live --speech-fixture D:/AI-Control/OpenJarvis/support/kokoro-voice-acceptance.wav
uv run --no-sync python scripts/install/Finalize-Ehsan-Setup.py --no-start-services --no-install-scan-task
```

The finalizer's optional `--no-start-services` inspects the existing server and
fails with evidence if it is unavailable. `--no-install-scan-task` also preserves
the existing inventory task without installing or enabling one. Its default behavior remains compatible
with the existing setup workflow. Inspect the resulting ZIP and acceptance
BLOCKED/MANUAL_REQUIRED entries. ZIP generation uses explicit allow-lists and
excludes SQLite files, credentials, private project content and recorded audio.
Exact Telegram and version-matched OpenCode/Kilo merge instructions remain in
`docs/EHSAN_REAL_USER_ACCEPTANCE.md`; those manual integrations stay disabled or
unaccepted until independently exercised.

## Next bounded phase

Phase 1C is not implemented here. Its next task is the approvals contract and
CLI: propose/list/inspect/approve/reject, action scopes and expiry, snapshot/hash
binding, stale-plan rejection, dry-run evidence, redaction and tests. Keep the
existing registry format and SQLite schemas unchanged. Do not combine registry
adoption/migrations (1D), indexing (1F/1G), cleanup, deployments or automation
enablement with the approvals implementation.
