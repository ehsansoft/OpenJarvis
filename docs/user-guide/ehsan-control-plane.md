# Personal AI Control Plane on Windows

This fork can run as a local-first control plane while still using a rotating
pool of zero-API-cost remote models when they are positively identified as free.

## Windows install

From PowerShell:

    Set-ExecutionPolicy -Scope Process Bypass
    .\scripts\install\ehsan-control-plane-windows.ps1 -InstallScanTask

The installer keeps code and state separate:

- code: D:\AI-Tools\OpenJarvis
- runtime state: D:\AI-Control\OpenJarvis
- projects: D:\Projects

It does not store a NaraRouter API key in the repository or config file.
Set the key in the environment or your preferred secret manager.

## Free model pool

Run:

    jarvis model free

The pool includes:

- local models from healthy local engines such as Ollama (zero API cost)
- NaraRouter models only when the live roster provides positive free evidence

Stable aliases are exposed through the OpenAI-compatible server:

- free/auto
- free/code
- free/research
- free/vision
- free/fast

The pool refreshes periodically, so clients can keep using a stable alias even
when the provider changes the concrete free-model roster.

Start the local API:

    jarvis start

Use this OpenAI-compatible base URL from editor clients:

    http://127.0.0.1:8000/v1

For coding clients such as OpenCode or Kilo Code, choose model free/code.
For long-context research, choose free/research. For private or sensitive code,
prefer a concrete local model or configure policy to disallow remote candidates.

## Whole D-drive inventory

The inventory is metadata-only. It does not read ordinary file contents and it
does not move or delete anything.

Run once:

    jarvis projects inventory D:\

Install a daily native Windows Task Scheduler job:

    jarvis projects install-scan-task --root D:\ --daily-at 03:00

Check it:

    jarvis projects scan-task-status

Remove it:

    jarvis projects remove-scan-task

The report records approximate observed bytes, file and directory counts,
extension distribution, candidate project roots, model-weight files, loose
drive-root files, and non-destructive reorganization recommendations.

## Project fabric

Project discovery remains separate from whole-drive inventory:

    jarvis projects scan D:\Projects --max-depth 5
    jarvis projects list

This registry is the foundation for later incremental source indexing, project
cards, Git status/history, TODO/test health, project priority recommendations,
and OpenCode/Kilo Code worker handoffs.

## Safety model

The system does not autonomously reorganize the disk. Inventory and project
analysis produce proposals first. File moves, deletions, production deployments,
database changes, and self-modification should remain approval-gated.
