# Editor handoff: OpenCode and Kilo through the OpenJarvis gateway

Verified 2026-10-14 on this workstation. Every command below ran against the
live gateway (`127.0.0.1:18080`) and produced the shown output. This documents
what works, not a proposal.

## Current state (all verified today)

| Piece | State | Evidence |
| --- | --- | --- |
| Jarvis gateway | running, loopback | `127.0.0.1:18080`, `/health` 200 |
| OpenCode | **wired and answering** | `opencode-cli run --model openjarvis/local-fast` -> `OPENCODE_GATEWAY_OK`, gateway log 200 |
| Kilo | UI-configured, steps below | no file to edit; globalStorage empty |
| Hermes | **wired, local + remote** | `HERMES_LOCAL_OK` via Ollama; ByNara provider configured |

## OpenCode (already configured)

Config: `C:\Users\eehsa\.config\opencode\opencode.jsonc` (V2 shape, CLI v2.0.27)

Two providers are already present and were audited 2026-10-11:

- `bynara` — direct NaraRouter models with `{file:./bynara.key}` credential
- `openjarvis` — the gateway, all 8 aliases (`code`, `research`, `fast`,
  `vision`, `local-code`, `local-fast`, `local-research`, `local-vision`)
- default model: `openjarvis/local-code`

Test command (verified):

```powershell
& "C:\Users\eehsa\AppData\Local\Programs\@opencodedesktop\resources\opencode-cli.exe" run `
  --model "openjarvis/local-fast" "Reply with exactly: OPENCODE_GATEWAY_OK"
# -> OPENCODE_GATEWAY_OK
```

Model selection rule: private repositories use `openjarvis/local-code`
(never leaves the machine); public/synthetic work may use `openjarvis/code`
(free/* pool, can route to ByNara).

## Kilo Code 7.8.8 (manual UI steps — no config file)

Kilo stores nothing in `globalStorage` and no `kilocode.*` keys exist in VS
Code `settings.json`; it is configured through its own panel:

1. VS Code -> Kilo panel -> Settings -> Providers -> **Custom provider**
2. Provider ID: `openjarvis`
3. API type: **OpenAI Compatible**
4. Base URL: `http://127.0.0.1:18080/router/v1`
5. Key: leave empty (loopback is unauthenticated) or enter the server key
6. Model: fetch models, or enter `local/code`
7. Keep the existing profile; add the provider alongside it

Acceptance: chat-only explanation first, then one bounded edit on a private
repo with `local/code`. One writer per task; do not run Kilo and OpenCode as
writers on the same checkout.

## Hermes (wired today)

Config: `%LOCALAPPDATA%\hermes\config.yaml` (backup:
`config.yaml.pre-wiring-20261014.bak`)

- `model.provider: ollama`, `model.base_url: http://127.0.0.1:11434/v1`,
  `model.default: qwen3.5:2b` -> local pool, no key, loopback only
- `model.providers.bynara.base_url: https://router.bynara.id/v1` with
  `key_env: NARAROUTER_API_KEY`; the key was copied from OpenJarvis' encrypted
  store into `%LOCALAPPDATA%\hermes\.env` (never displayed, file chmod 600)

Verified: `hermes chat -q ... --oneshot` -> `HERMES_LOCAL_OK` (local) and
`HERMES_NARA_OK` (ByNara). Both pools answer.

Named custom providers live under the **top-level** `providers:` key in
`config.yaml` (not `model.providers` — that nesting is silently ignored for
selection). The working entry:

```yaml
providers:
  bynara:
    base_url: https://router.bynara.id/v1
    key_env: NARAROUTER_API_KEY
    default_model: nemotron-3.5-lightning-free
```

Selecting the pool: `--provider bynara` on the CLI, or
`hermes config set model.provider bynara` to make it the default. Switching
back: `hermes config set model.provider ollama` (the default here).

Division of labor: OpenJarvis keeps the scheduler, reminders, memory,
projects, approvals and evidence. Hermes is a worker runtime on the same
model pools. If Hermes Telegram is ever enabled, use a **second bot token** —
one poller per token.

## Open questions / next

- Kilo acceptance run (UI steps above need a human click-through)
- Hermes ByNara rate limits: the free tier throttles; sign-in raises it
