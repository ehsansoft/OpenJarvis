# OpenCode and Kilo Code

OpenJarvis exposes a dedicated raw OpenAI-compatible endpoint for coding
clients that already implement their own agent and tool loop:

    http://127.0.0.1:8000/router/v1

Do not point editor agents at the ordinary personal-assistant endpoint unless
you explicitly want OpenJarvis' server-side agent around the editor agent.

## Stable free aliases

The editor gateway exposes stable model IDs:

- `free/code`
- `free/research`
- `free/fast`
- `free/vision`
- `free/auto`

They resolve at runtime across local zero-API-cost models and the current
NaraRouter Free-plan roster. NaraRouter itself is free-only by default in this
fork, so non-free Nara models are not advertised unless that policy is
explicitly disabled.

## OpenCode

A current OpenCode-compatible template is shipped at:

    configs/editors/opencode.openjarvis.jsonc

It uses the OpenAI-compatible runtime and maps friendly local model names to
the stable OpenJarvis aliases. The default is the coding alias.

## Kilo Code

A Kilo Code template is shipped at:

    configs/editors/kilo.openjarvis.jsonc

Kilo can also be configured from Settings -> Providers -> Custom provider:

- Provider API: OpenAI Compatible
- Base URL: `http://127.0.0.1:8000/router/v1`
- API key: leave empty while OpenJarvis is bound to loopback without auth
- Fetch models, or add `free/code` manually

Kilo's model `id` field can map a friendly config key to the API-facing
`free/code` alias.

## Why a separate editor endpoint?

OpenCode and Kilo Code already orchestrate file reads, edits, terminal calls,
and iterative coding. Sending those requests through a second autonomous
server agent would create nested tool loops. The `/router/v1` endpoint keeps
the model gateway, free-model routing, telemetry, and security boundary while
leaving the editor in charge of its own coding workflow.
