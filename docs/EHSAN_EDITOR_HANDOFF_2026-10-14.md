# Editor handoff: OpenCode and Kilo through the OpenJarvis gateway

Verified 2026-10-14 on this workstation (updated the same evening after the
Kilo/OpenCode rework). Every command below ran against the live gateway
(`127.0.0.1:18080`) and produced the shown output. This documents what works,
not a proposal.

## Current state (all verified 2026-10-14)

| Piece | State | Evidence |
| --- | --- | --- |
| Jarvis gateway | running, loopback | `127.0.0.1:18080`, `/health` 200 |
| OpenCode CLI | **wired and answering** | v2.0.29, `OPENCODE_FREE_OK` + `OPENCODE_GATEWAY_OK` |
| Kilo CLI 7.8.8 | **wired and answering** | `kilo config check` clean; `KILO_FREE_OK` |
| Kilo Desktop | config written, needs relaunch | same provider block as global config |
| Hermes | **wired, local + ByNara** | `HERMES_LOCAL_OK`, `HERMES_NARA_OK`; profiles `coder`/`researcher` verified |

## OpenCode (reinstalled as npm CLI)

Config: `C:\Users\eehsa\.config\opencode\opencode.jsonc` (V2 shape)

The old `@opencodedesktop` install is gone (empty dir). OpenCode is now the
official v2 CLI:

```powershell
npm install -g @opencode/cli          # -> D:\AI-Control\windows\npm-global\opencode.cmd (on user PATH)
opencode --version                    # opencode v2.0.29
```

Providers in `opencode.jsonc`:

- `bynara` — direct NaraRouter models with `{file:./bynara.key}` credential
- `openjarvis` — the gateway, all 8 aliases (`local-code`, `local-fast`,
  `local-research`, `local-vision`, `code`, `research`, `fast`, `vision`);
  note the **dash** keys — pass `openjarvis/local-fast`, not `openjarvis/local/fast`
- default model: `openjarvis/local-code`

Verified runs:

```powershell
opencode run --model bynara/nemotron-3.5-lightning-free "Reply with exactly: OPENCODE_FREE_OK"
# -> OPENCODE_FREE_OK
opencode run --model openjarvis/local-fast "Reply with exactly: OPENCODE_GATEWAY_OK"
# -> OPENCODE_GATEWAY_OK
```

Model selection rule: private repositories use `openjarvis/local-code`
(never leaves the machine); public/synthetic work may use ByNara free models
explicitly.

## Kilo Code 7.8.8 (config-file wired)

Global config: `C:\Users\eehsa\.config\kilo\kilo.jsonc`
(backup: `kilo.jsonc.pre-openjarvis-20261014-184631.bak`)

Desktop config: `%APPDATA%\Kilo Desktop\plugins\kilo-server\runtime\config\kilo\kilo.jsonc`

Both now contain:

- `openjarvis` provider → `http://127.0.0.1:18080/router/v1` with the 8
  gateway aliases plus `qwen3-8b` (`id: qwen3-8b:latest`)
- `bynaraprovider` → `https://router.bynara.id/v1` with
  `"apiKey": "{env:NARAROUTER_API_KEY}"` (the key lives in the user
  environment; never written into the config)
- defaults: `model: openjarvis/local/code`, `small_model: openjarvis/local/fast`

Verified runs:

```powershell
kilo config check                     # No config warnings.
kilo models openjarvis                # lists all 9 models
kilo run --model bynaraprovider/nemotron-3.5-lightning-free "Reply with exactly: KILO_FREE_OK"
# -> KILO_FREE_OK
```

Kilo Desktop reads its isolated config at startup — relaunch the app once to
pick up the provider block (`.kilo-desktop-ownership.json` tracks which keys
the app owns).

Binary location: `%USERPROFILE%\.vscode\extensions\kilocode.kilo-code-7.8.8-win32-x64\bin\kilo.exe`
(extension updates may rename this path — re-resolve if missing).

## Delegation skills (both runtimes)

- **Hermes** `kilo-code` skill
  (`%LOCALAPPDATA%\hermes\skills\autonomous-ai-agents\kilo-code\SKILL.md`)
  teaches Hermes to drive `kilo run` headless with the verified model ids;
  the builtin `opencode` skill covers `opencode run`. Both follow the
  privacy law (private repos → `openjarvis/local/*`).
- **OpenJarvis** `editor-delegate` skill (`skills/editor-delegate/SKILL.md`)
  is the same contract for Jarvis agents: one bounded run, acceptance
  command, evidence reported back. `editor-handoff` remains the task-contract
  skill.

## Hermes (updated 2026-10-14 evening)

Config: `%LOCALAPPDATA%\hermes\config.yaml` (backup:
`config.yaml.pre-wiring-20261014.bak`)

- `model.provider: ollama`, `model.base_url: http://127.0.0.1:11434/v1`,
  `model.default: qwen3.5:2b` → local pool, no key, loopback only
- top-level `providers.bynara` with `key_env: NARAROUTER_API_KEY` (key in
  `%LOCALAPPDATA%\hermes\.env`, never displayed)
- `NARAROUTER_API_KEY` also set at **user environment scope** so Kilo and any
  new terminal can reach the ByNara free models

Profiles (each cloned with config, `.env`, SOUL, skills; all smoke-tested):

| Profile | Alias | Role | Verified |
| --- | --- | --- | --- |
| `default` | — | generalist | `HERMES_LOCAL_OK` |
| `coder` | `coder` | drives OpenCode/Kilo workers | `CODER_PROFILE_OK` |
| `researcher` | `researcher` | grounded research, sources required | `RESEARCHER_PROFILE_OK` |

Each profile has its own `SOUL.md` (identity + privacy law + evidence rules).

64k context gate: `qwen3-8b:latest` reports 40,960 tokens via GGUF metadata —
a `PARAMETER num_ctx 65536` Modelfile does **not** change the reported length
(verified with a throwaway `qwen3-8b-64k`, since removed), so Hermes stays on
`qwen3.5:2b` (262,144 reported). The 8B model remains fully available through
the gateway (`openjarvis/qwen3-8b`) for every other client.

Division of labor: OpenJarvis keeps the scheduler, reminders, memory,
projects, approvals and evidence. Hermes is a worker runtime on the same
model pools. If Hermes Telegram is ever enabled, use a **second bot token** —
one poller per token.

## Acceptance rules

- One writer per task; do not run Kilo and OpenCode as writers on the same
  checkout.
- Chat-only explanation first, then one bounded edit on a private repo with
  `openjarvis/local/code` / `openjarvis/local-code`.
- Free models need explicit user opt-in per task for anything non-synthetic.

## Open questions / next

- Kilo Desktop relaunch needed to verify its isolated config
- Hermes ByNara rate limits: the free tier throttles; sign-in raises it
- See `EHSAN_WIRING_GUIDE_2026-10-14.md` for the full verification matrix
  (dashboard model picker, Voicebox, local CT2 whisper, cleanup commands)
