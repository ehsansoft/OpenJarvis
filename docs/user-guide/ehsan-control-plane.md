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
Persist it in OpenJarvis' local restricted credential store with:

    jarvis model nara-key

The command prompts with hidden input. Server and CLI startup inject the saved
credential into the process before NaraRouter discovery.

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

Use the raw OpenAI-compatible editor gateway (it bypasses the server-side agent
and personal-memory injection so coding clients keep control of their own tool loop):

    http://127.0.0.1:8000/router/v1

The normal personal-assistant API remains:

    http://127.0.0.1:8000/v1

For coding clients such as OpenCode or Kilo Code, choose model free/code.
For long-context research, choose free/research. For private or sensitive code,
prefer a concrete local model or configure policy to disallow remote candidates.

## Developer machine inventory

Run:

    jarvis projects machine-scan

This captures the active developer toolchain and its executable locations,
including Node.js, npm, npx, pnpm, Yarn, Corepack, Bun, Deno, Python, pip, uv,
PHP, Composer, MySQL/MariaDB clients, Docker, WSL, Ollama, Winget, Chocolatey
and Scoop when present.

It also queries the configured Ollama API for local model names, digests, sizes,
families, parameter sizes and quantization levels, and detects common WampServer
roots plus installed PHP, Apache, MySQL and MariaDB runtime versions.

The daily Windows scan task refreshes this machine inventory together with the
project registry and drive inventory.

## Disk hygiene scans

Cleanup discovery is advisory and never deletes files:

    jarvis projects cleanup-scan D:\ --min-age-days 30

It targets generated/cache/build directories and separates low-risk cache
candidates from review-required folders such as node_modules, vendor, virtual
environments and build outputs.

Exact duplicate detection is opt-in because it reads candidate file bytes and
can generate significant disk I/O:

    jarvis projects duplicates D:\ --min-size-mb 1

The duplicate scanner first groups by file size, then uses a first/last sample
hash, and finally verifies candidates with SHA-256. Dependency trees, build
outputs and system directories are skipped by default to reduce noise.

Neither hygiene command removes, moves or changes files. Use the report to make
an explicit cleanup plan first.

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
