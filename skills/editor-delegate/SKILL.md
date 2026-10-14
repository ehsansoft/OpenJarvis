---
name: editor-delegate
description: Delegate bounded coding tasks to OpenCode or Kilo Code CLIs and return verified results.
version: 0.1.0
author: Ehsan OpenJarvis
---

# Editor Delegate

Run one bounded coding task in OpenCode or Kilo Code as an external implementer, then report evidence back. Verified wiring on this workstation (2026-10-14):

- OpenCode v2: `opencode` on PATH (`D:\AI-Control\windows\npm-global`). Models: `openjarvis/local-code` (private, via gateway), `openjarvis/local-fast`, `bynara/<free-model>` (public/synthetic only).
- Kilo Code: `%USERPROFILE%\.vscode\extensions\kilocode.kilo-code-7.8.8-win32-x64\bin\kilo.exe`. Models: `openjarvis/local/code`, `openjarvis/local/fast`, `openjarvis/qwen3-8b`, `bynaraprovider/<free-model>` (needs `NARAROUTER_API_KEY`).
- Both must run in the target repository's working directory; one editor per working directory at a time.

Procedure:

1. Contract the task: repository, branch/base, objective, permitted files, acceptance command, evidence path (mirror `editor-handoff`).
2. Choose the model with the privacy law: private code -> `openjarvis/local-*`; public/synthetic -> free model only with explicit user approval.
3. Execute one bounded run: `opencode run '<task>'` or `kilo run --model <id> '<task>'` in the repo directory.
4. Verify: run the acceptance command, inspect `git diff`, and record the editor's final output text.
5. Report: model used, files changed, acceptance result, remaining risks. Do not claim completion from the editor's message alone.

Instruction-only workspace procedure. No executable resources or additional authority.
