# Jarvis Control Desk

Open **http://127.0.0.1:18080/control** on this workstation. The server is
already running. This dependency-free dashboard is served by the same Jarvis
API; it adds no Node installation, second scheduler, Telegram poller, external
fonts, analytics or cloud hosting. The existing upstream frontend stays intact.
The address follows the server's configured bind port on other installations.

## What you can do

| View | Real behavior |
| --- | --- |
| Overview | Live free space, local endpoint checks, active tasks and latest approved cleanup receipt. |
| Chat | Private text turns through the owned JarvisSystem, with separate caller histories and a restricted read-only tool set. Chats remain in page memory. |
| Research | Retrieve explicitly indexed documents, synthesize once with `local/research`, and inspect the actual retrieved sources. No-source queries do not call the model. |
| Tasks | Review and create a one-shot prompt; pause, resume, cancel, run and inspect execution logs in the existing scheduler SQLite store. |
| Projects | Paginated scanner proposals; no canonical adoption, migration or project source edits. |
| Servers | Check Jarvis/Ollama/Voicebox; restart Jarvis cleanly; start the installed Ollama on loopback, checking for an existing process first. |
| Skills | Inspect discovered manifests; execute only the reviewed workstation-brief pipeline through the standard executor. |
| Capabilities | Search/filter live catalog readiness and inspect the next acceptance action. |

The notebook saves an answer only when you click **Save in this browser**.
That browser-local note is separate from project records and automatic learned
facts. An optional server API key stays in tab session storage; never put real
provider credentials into prompts or screenshots.

## Server ownership and privacy

Private routing must be enabled with remote private routing disabled. Research
uses the owned protected engine, the stable `local/research` alias and the
standard secured retrieval executor. It shows source excerpts independently of
the model's citation quality. Multi-step CLI Deep Research remains available;
its broader quality gate is open. The dashboard's bounded synthesis avoids a
long tool loop on the small workstation model.

All new control APIs reject non-loopback hostnames and cross-origin browser
requests. Mutations require the custom dashboard header, and configured API-key
authentication remains in force. User/model text is rendered as text, never
injected as HTML. No arbitrary shell command, model download, deletion or
third-party skill import endpoint was added.

Task execution/resumption is restricted to the orchestrator and reviewed
read-only tool names. Other tasks require separate capability review in the
CLI. Cancel retains SQLite history. This dashboard does not enable cron or
recurring personal automations. A created one-shot task may run at its chosen
time after you confirm the exact prompt and timestamp.

Jarvis restart drains the old server before a windowless helper starts its
replacement at the actual bound address. Busy dashboard chat and managed task
requests block restart. Polling reconnects after the restart. Windows daemon
launches use the existing `pythonw.exe` with `CREATE_NO_WINDOW` when available;
console interpreters retain the detached fallback. No Python executable was
installed.

Voicebox is reachable but its observed listener is `0.0.0.0:17493`. Its models
were downloaded but not loaded at the last inventory. Voice remains deferred;
the dashboard offers status and a manual binding reminder. No Voicebox launch,
binding change, STT/TTS generation or model installation was performed.
WampServer and arbitrary project servers remain with their existing launchers.

If Jarvis itself is stopped, its dashboard is also unavailable. Start it with:

```powershell
cd D:\AI-Tools\OpenJarvis
$env:OPENJARVIS_HOME='D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis start
```

## Validation and continuation

Real Edge browser acceptance checked overview, private chat, reviewed skill
execution, capability filtering, memory search, grounded research, task
creation/run/logs, read-only projects, existing Ollama duplicate prevention and
Jarvis restart with retained task state. JavaScript exceptions were absent.
Desktop and mobile screenshots are in the evidence directory. This is automated
browser acceptance; your preferred layout and interaction remain yours to judge.

The browser-created task `c519d32dca844eba` executed `/system` and completed.
No active personal task was left by that test. Regression tests cover hostile
origins/hosts, API-key enforcement, conversation isolation, no-source research,
real FTS question lookup, task persistence, unsafe task/skill refusal and owned
restart. Existing model, memory, scheduler, channel and control-plane acceptance
remain separately reported.

```powershell
$env:OPENJARVIS_HOME='D:\AI-Control\OpenJarvis'
uv run --no-sync jarvis acceptance --live --text-only
```

Priorities next: project role/task reconciliation, scoped semantic retrieval with
the installed nomic embedder, task-specific model evaluations, then reviewed
recurring notifications. Kilo GUI and Telegram still require manual acceptance;
GitHub native push authentication blocks publishing the current local branch.
No Project Intelligence migration or stable promotion is part of this change.
