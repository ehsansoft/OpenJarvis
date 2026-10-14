# Wiring guide 2026-10-14: every client, every model, verified

Session scope: make OpenJarvis, Hermes, OpenCode and Kilo Code use the local
and free model pools uniformly, fix Voicebox, and give the dashboard the full
model picture. Everything below **ran today on this machine**; outputs are
quoted, not proposed.

## 1. Verification matrix

| Client | Local models | Free models | Verified with |
| --- | --- | --- | --- |
| OpenJarvis gateway | `local/*` → Ollama | `free/*` → Nara pool | `/health` 200, `/router/v1/models` 18 ids |
| Dashboard picker | 10 aliases **+ 3 raw Ollama ids** | via `free/*` (private routing keeps chat local) | `GET /v1/models` → 13 ids (see §2) |
| OpenCode CLI v2.0.29 | `openjarvis/local-fast` → `OPENCODE_GATEWAY_OK` | `bynara/nemotron-3.5-lightning-free` → `OPENCODE_FREE_OK` | `opencode run` |
| Kilo CLI 7.8.8 | `openjarvis/local/code` (config default) | `bynaraprovider/nemotron-3.5-lightning-free` → `KILO_FREE_OK` | `kilo run`, `kilo config check` clean |
| Kilo Desktop | provider block written | bynara block written | pending one app relaunch |
| Hermes default | Ollama `qwen3.5:2b` → `HERMES_LOCAL_OK` | ByNara → `HERMES_NARA_OK` | `hermes chat -q --oneshot` |
| Hermes `coder` | `CODER_PROFILE_OK` | via `kilo-code`/`opencode` skills | profile smoke |
| Hermes `researcher` | `RESEARCHER_PROFILE_OK` | ByNara for public research | profile smoke |
| Voicebox (TTS/STT) | kokoro + whisper-base loaded | — | roundtrip PASS |
| Faster-Whisper CT2 | `faster-whisper-large-v3-turbo-ct2` (1.6 GB) | — | `CT2_SMOKE: PASS` |

Key facts:

- **ByNara key**: `NARAROUTER_API_KEY` (50 chars, never printed) is now set at
  *user environment scope*; both Kilo configs read `{env:NARAROUTER_API_KEY}`,
  OpenCode reads `{file:./bynara.key}`. No secret exists in any config file.
- **qwen3-8b:latest** (Qwen3-8B-Q4_K_M, 4.68 GB → Ollama 5.0 GB) serves every
  client: gateway pool, `/router/v1/models`, dashboard picker, Kilo
  (`openjarvis/qwen3-8b`).
- **Hermes 64k gate**: the GGUF metadata pins 40,960 and a `num_ctx` override
  does not change the reported length (throwaway `qwen3-8b-64k` tested and
  removed). Hermes stays on `qwen3.5:2b` (262,144) and gets the 8B through
  the gateway instead.
- Dashboard chat runs under `private_routing=true / allow_private_remote=false`:
  `free/*` selections are remapped to `local/*` on purpose (fail-closed).
  Raw remote ids are therefore deliberately **not** listed in the picker.

## 2. Dashboard: full local model list (`/v1/models`)

Before: the Installed tab only showed the 10 stable aliases, so concrete
models like `qwen3-8b:latest` were invisible (and undeletable) in the UI.

Change (`src/openjarvis/server/routes.py`): the route now also exposes the
free-pool engine's **concrete candidates** — the same ids `generate()` can
actually route to — owned by their engine key, after the aliases, with the
existing embed-only and cloud filters applied:

```text
GET /v1/models  → 13 ids
free/auto … local/fast            [openjarvis]   (10 stable aliases)
qwen2.5-coder:7b                  [ollama]
qwen3-8b:latest                   [ollama]
qwen3.5:2b                        [ollama]
```

Frontend (`frontend/src/lib/api.ts`, `CommandPalette.tsx`):

- new `isPoolAlias()` — `free/*`/`local/*` are virtual: their delete buttons
  are gone (they were never deletable anyway; the call failed with an error
  toast), and they no longer trigger a bogus Ollama preload on selection.
- preload now only warms models owned by Ollama; cloud prefixes gained the
  missing `atlascloud/`.

Tests (all green):

- `tests/server/test_model_management.py` — 15 passed incl. the new
  `test_models_list_includes_free_pool_candidates` (aliases first, concrete
  candidate with `owned_by: ollama`, embed-only hidden)
- full `tests/server` — 51 passed; `tsc -b` exit 0; full frontend suite —
  92/92

Note: model *pull* and *delete* go straight to Ollama (`engine_name="ollama"`
gate passes on this deployment), so raw rows are fully manageable in the UI.

## 3. Voicebox

- Working state: server on `127.0.0.1:17493`, **kokoro TTS + whisper-base STT
  loaded**, roundtrip PASS (TTS 170,444 bytes / 3.55 s WAV → STT verbatim).
- Correct load call is `POST /models/download {"model_name":"kokoro"}`
  (`/models/load` body params are silently ignored — upstream
  jamiepine/voicebox#977, installed 0.5.0 predates the fix; see
  `docs/EHSAN_CAPABILITY_CATALOG_PHASE1B.md` before automating Voicebox).
- **LAN exposure**: the app still binds `0.0.0.0:17493` and two inbound
  firewall Allow rules exist. Run once as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\AI-Tools\OpenJarvis\scripts\install\Fix-VoiceboxLoopback.ps1"
```

  The script backs up the rules to `voicebox-firewall-rules.backup.json`,
  removes the inbound allows, and adds a loopback-only allow for TCP 17493.
  Restarting Voicebox afterwards to bind `127.0.0.1` is still the preferred
  app-side fix.
- **Reclaim ~3.6 GB**: an erroneous call started a `qwen-tts-1.7B` download
  that was still running at the time of writing. When
  `GET /models/status` shows `downloading: false`:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:17493/models/qwen-tts-1.7B/unload'
Invoke-RestMethod -Method Delete -Uri 'http://127.0.0.1:17493/models/qwen-tts-1.7B'
```

## 4. Local CT2 whisper (offline STT fallback)

Deps present (`faster_whisper`, `ctranslate2`), model dir is genuine
CTranslate2 format (`model.bin` 1.6 GB + config/tokenizer).

Verified: Voicebox TTS → `FasterWhisperBackend(model_size=<local path>)` →
`'Jarvis Local Whisper model is ready.'` (verbatim) → `CT2_SMOKE: PASS`.

Voicebox stays the primary STT (`[speech] backend = "voicebox"`). To fall
back when Voicebox is down, edit `D:\AI-Control\OpenJarvis\config.toml`:

```toml
[speech]
backend = "faster-whisper"
model = "D:\\AI-Control\\models\\faster-whisper-large-v3-turbo-ct2"
compute_type = "int8"
```

## 5. Delegation & bots: how the team is organized

- **OpenJarvis owns Telegram** (one bot token, one poller) plus scheduler,
  reminders, memory, approvals, evidence and the dashboard.
- **Hermes bots run where Hermes runs**: desktop app or
  `hermes -p coder gateway start`. Suggested lineup (already created):
  - `default` — generalist chat on Ollama
  - `coder` — implements via `opencode run` / `kilo run` (skills installed)
  - `researcher` — sources-required research, writes findings under
    `D:\AI-Control\OpenJarvis\support\`
- **Do not** give Hermes the Telegram token. A second token would be needed,
  and OpenJarvis already answers there.
- **Chat groups**: keep the OpenJarvis Telegram chat as the single front
  door; route coding work to the `coder` profile (Hermes kanban
  `kanban.db` already initialized) and research to `researcher`. Editors
  (OpenCode/Kilo) are workers, never parallel writers on one checkout.
- **Model law**: private → `openjarvis/local/*` / Ollama only; public or
  synthetic → ByNara free models with explicit opt-in per task.

## 6. Pending manual items

1. Run the Voicebox firewall script as Administrator (§3).
2. Relaunch Kilo Desktop once to verify its isolated config.
3. Delete `qwen-tts-1.7B` when its download settles (§3).
4. GitHub push auth is still broken — commits since `847bfe7` have not seen
   CI; PRs #2/#3 remain drafts.
5. `ready_for_personal_automations=false` gates unchanged: Telegram live,
   microphone/listening, Hermes source review, research quality.
