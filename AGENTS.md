# AGENTS.md — Ehsan OpenJarvis Control Plane

## Mission
Turn this OpenJarvis fork into a local-first personal development and operations
control plane for this Windows workstation.

The system must help with:
- coding and repository work from Codex, OpenCode, Kilo Code and CLI clients;
- local/free model routing through Ollama plus zero-API-cost providers;
- Voicebox speech/transcription integration;
- understanding and organizing D:\Projects and the rest of D: safely;
- WampServer / PHP / WordPress development environments;
- research, project planning, reminders, jobs/resumes and recurring workflows;
- multiple websites and projects, not one site-specific implementation.

## Sources of truth
Read these before architecture-level changes:
- `docs/EHSAN_CONTROL_PLANE_ARCHITECTURE.md`
- `docs/user-guide/ehsan-control-plane.md`
- `configs/openjarvis/examples/ehsan-control-plane.toml`
- `scripts/install/Finalize-Ehsan-Setup.py`

For OpenAI/Codex/API-specific behavior, use the official OpenAI developer docs
MCP when available rather than relying on memory.

## Non-negotiable engineering rules
1. Local-first. Bind personal services to loopback unless remote exposure is
   explicitly requested and secured.
2. Never commit API keys, passwords, tokens, cookies, WordPress secrets or
   credential-store contents.
3. Discovery, cleanup and duplicate scans are read-only by default.
4. Deletion, file moves, package removal, site changes, deployments and data
   migrations require an explicit plan, dry run and approval boundary.
5. Do not hard-code one website or one project. Build reusable project/site
   adapters and capability interfaces.
6. Prefer stable aliases such as `free/code`, `free/research`,
   `free/vision` and future `local/*` aliases over volatile provider model IDs.
7. Free provider rosters are dynamic. Discover entitlements live, cache briefly,
   benchmark continuously and fail over without assuming a model will exist
   tomorrow.
8. Avoid duplicate model downloads. Detect Ollama, Voicebox and Hugging Face
   caches before recommending or pulling another copy.
9. Preserve upstream compatibility. Keep custom behavior modular and avoid
   unnecessary namespace-wide rewrites.
10. Every bug fix needs a focused regression test. Run the smallest relevant
    tests first, then the control-plane suite.
11. Generated recommendations may propose self-improvements, but code changes
    must go through tests/evals and a reviewable Git diff/PR before becoming the
    stable control plane.
12. Windows PowerShell 5.1 has LASTEXITCODE scope pitfalls. For multi-step
    verification prefer Python subprocess return codes or immediate native-code
    checks without pipeline-wrapped scriptblocks.

## Current workstation defaults
- Repo: `D:\AI-Tools\OpenJarvis`
- State: `D:\AI-Control\OpenJarvis`
- Projects: `D:\Projects`
- WampServer: `C:\wamp64`
- Voicebox: `http://127.0.0.1:17493`
- OpenJarvis: `http://127.0.0.1:8000`
- Editor API: `http://127.0.0.1:8000/router/v1`
- Personal API: `http://127.0.0.1:8000/v1`
- Primary editor alias: `free/code`

Treat these as configurable defaults, not universal constants.

## Required pre-merge checks for control-plane work
Run focused tests for the touched subsystem, then at minimum:

```powershell
$env:OPENJARVIS_HOME="D:\AI-Control\OpenJarvis"
uv run pytest tests/core/test_config.py tests/core/test_control_plane_config.py tests/core/test_ehsan_control_plane_upgrade.py tests/engine/test_nararouter.py tests/intelligence/test_free_pool.py tests/projects/test_discovery.py tests/projects/test_inventory.py tests/projects/test_machine_inventory.py tests/projects/test_hygiene.py tests/tools/test_voicebox_status.py tests/speech/test_voicebox_stt.py tests/mcp/test_transport.py tests/mcp/test_loader.py tests/security/test_rate_limiter.py tests/server/test_routes.py -q
```

When the suite passes, run the real-machine finalizer and inspect its ZIP rather
than declaring success from unit tests alone.
