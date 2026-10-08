# Foundation continuation — 2026-10-08

This records the earlier Foundation verification. The current Phase 0.5 local
routing, acceptance evidence, and remaining human gates are documented in
`EHSAN_REAL_USER_ACCEPTANCE.md`.

## Outcome

OpenJarvis is running on `http://127.0.0.1:8000`, bound to loopback.
The editor API is `http://127.0.0.1:8000/router/v1`; use `free/code`.
A real non-streaming completion returned `JARVIS_OK` with HTTP 200.
Foundation acceptance remains pending a green GitHub CI run. Phase 1 has not
started, and the foundation has not been tagged or promoted.

## Findings and changes

The checkout was clean at `f711edac`. It was fast-forwarded to
`081e63ce7a15e0dd90ca5955a30c1dedbaadf362` on
`feature/ehsan-control-plane-foundation`. That upstream patch restores the
already-imported NaraRouter class after registry resets instead of reloading
its module. The original failing test now passes unchanged.

Additional foundation fixes made locally:

| Files | Change and evidence |
| --- | --- |
| `scripts/install/Finalize-Ehsan-Setup.py`, `tests/core/test_ehsan_finalizer.py`, `AGENTS.md` | Give pytest per-run cache/temp paths. Existing Windows directories caused cache access warnings and a fatal cleanup `PermissionError`. A real child pytest run verifies isolation with a blocked legacy cache and confirms the old file is preserved. |
| `scripts/install/Finalize-Ehsan-Setup.py`, `tests/core/test_ehsan_finalizer.py` | Allow model discovery 30 seconds and avoid launching another server when the existing health/discovery API responds. The earlier two-second model-list probe caused a competing startup and Windows port-binding error during the second finalizer run. Two tests cover slow model discovery and actual model-discovery failure without spawning a competitor. |
| `scripts/install/Check-Voicebox-MCP.py`, `tests/core/test_voicebox_mcp_check.py` | Accept native `voicebox.*` and legacy `voicebox_*` names. Still require speak, transcribe, list captures and list profiles. Twelve cases cover both naming styles, missing tools and client closure. Live direct/configured discovery both pass. |
| `tests/engine/test_nararouter.py` | Explicitly verify the registry and instance retain the imported class identity after `EngineRegistry.clear()`. |
| `src/openjarvis/cli/projects_cmd.py`, `tests/cli/test_projects_cmd.py` | Restore the existing `Discovered N project(s)` CLI wording while retaining role counts. Keep the original assertion and add a role-count assertion. |
| `.github/workflows/ehsan-control-plane-ci.yml` | Set the state path in a runner step and include the new regressions. The previous workflow used `runner.temp` in job-level `env`, where that context is unavailable. |
| `tests/core/test_config.py` | Remove a duplicated, identical BOM test definition; the surviving regression retains its assertion. |

The workflow context correction follows
[GitHub's context availability reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability).

Mechanical Ruff import/format corrections were also required across:

```text
src/openjarvis/cli/__init__.py
src/openjarvis/cli/model.py
src/openjarvis/core/config.py
src/openjarvis/engine/_discovery.py
src/openjarvis/engine/nararouter.py
src/openjarvis/intelligence/free_pool.py
src/openjarvis/mcp/loader.py
src/openjarvis/projects/__init__.py
src/openjarvis/projects/discovery.py
src/openjarvis/projects/hygiene.py
src/openjarvis/projects/inventory.py
src/openjarvis/projects/machine_inventory.py
src/openjarvis/speech/voicebox_stt.py
src/openjarvis/tools/machine_inventory.py
tests/core/test_control_plane_config.py
tests/core/test_ehsan_control_plane_upgrade.py
tests/intelligence/test_free_pool.py
tests/mcp/test_loader.py
tests/mcp/test_transport.py
tests/projects/test_inventory.py
tests/projects/test_machine_inventory.py
tests/server/test_routes.py
tests/speech/test_voicebox_stt.py
```

## Verification

| Check | Result |
| --- | --- |
| Original NaraRouter failing test | 1 passed |
| NaraRouter + finalizer isolation regressions | 10 passed |
| Voicebox naming + finalizer isolation regressions | 13 passed |
| Finalizer isolation + existing-server smoke regressions | 3 passed |
| Focused control-plane suite, including first two new regressions | 222 passed |
| Expanded Windows workflow suite, after CLI fix | 135 passed |
| First successful real-machine finalizer | 240 passed; all 11 command/smoke results returned zero |
| Second real-machine finalizer, including CLI regression | 242 passed; ZIP inspection caught the competing-server smoke issue, subsequently fixed |
| Final real-machine finalizer after smoke fix | 244 passed; all 11 steps returned zero; existing server reused without a competing startup |
| Ruff check across `src/`, `tests/`, both changed install scripts | Pass |
| Ruff format check over the same files | Pass |
| Git diff whitespace check | Pass |
| `/health`, `/router/v1`, `/router/v1/models`, `/v1/info`, `/docs` | HTTP 200 |
| `/router/v1/chat/completions`, `free/code`, `stream=false` | HTTP 200; `JARVIS_OK` |
| Voicebox health + model status | HTTP 200; 18 registered model entries |
| Voicebox MCP | All four tools present through direct and configured discovery |
| Ollama discovery | Existing `qwen2.5-coder:7b` available |
| Free roster | One local and ten positively identified free Nara candidates at verification time |
| Python rate limiter | Python backend active; burst of one accepts first call and rejects second |
| Server scheduler | Startup reports active; managed-agent API returns zero agents |
| Windows metadata scan task | Ready; daily 03:00; first scheduled execution still pending |

Evidence outside the repository:

```text
D:\AI-Control\OpenJarvis\support\runtime-verification-20261008.json
D:\AI-Control\OpenJarvis\support\openjarvis-finalize-alpha4.3-20261008-164853.zip
D:\AI-Control\OpenJarvis\support\finalize-alpha4.3-20261008-164717\00-final-summary.json
D:\AI-Control\OpenJarvis\support\final-evidence-verification-20261008.json
```

The final ZIP passed its integrity check, excludes the credential
store, and contains no exact matches for saved credential values of eight or
more bytes. This check does not claim to detect every possible secret.

## Remaining risks and gates

- GitHub CI on the fetched baseline is red: the main workflow failed lint and
  its full test job; the control-plane workflow failed before creating a job.
  Local lint and the expanded control-plane suite pass after these changes.
  A fresh remote run is required; the full Linux/Rust/coverage suite has not
  been reproduced on this workstation. The remote test logs require
  authentication and were not accessible through the anonymous API.
- Current changes remain local and reviewable in `git diff`; they have not
  been pushed, tagged, or merged. CI must validate the published patch before
  claiming Gate 0 is complete.
- Voicebox currently binds `0.0.0.0:17493` and reports loaded/downloaded model
  inconsistencies. Its configuration and model storage were left intact.
- FastAPI/Starlette deprecation warnings remain. They did not fail the suites.
- The daily scan task is registered and ready, but its first actual scheduled
  execution has not occurred. Registration success is not execution evidence.
- The running server was launched during finalizer smoke verification and
  remained alive after the Windows uv wrapper exited. Its listener and API
  were checked afterward. It has no newly installed auto-restart service.

To start Jarvis again if it is stopped, run from the repository:

```powershell
$env:OPENJARVIS_HOME = 'D:\AI-Control\OpenJarvis'
uv run jarvis serve --host 127.0.0.1 --port 8000
```

## Next recommended slice

Review/publish the foundation patch, rerun GitHub CI and inspect its full test
failures if any remain. Once Gate 0 is green, establish the accepted foundation
baseline and begin Project Intelligence on its own feature branch.

Phase 1 should first audit the existing JSON schema-v2 project registry and its
consumers, then propose the canonical project model, classification evidence,
manifest validation, migration/dry-run plan, tests and implementation order.
The 144 active roots are scanner classifications, not human-confirmed project
priorities. No project-registry database migration has been run in this slice.
