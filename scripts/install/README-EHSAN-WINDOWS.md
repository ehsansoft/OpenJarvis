# Ehsan OpenJarvis Windows Test Installer

Version: 0.1.0-alpha.2

This installer targets the development branch:

`feature/ehsan-control-plane-foundation`

Default layout:

- OpenJarvis code: `D:\AI-Tools\OpenJarvis`
- OpenJarvis state: `D:\AI-Control\OpenJarvis`
- projects: `D:\Projects`
- WampServer auto-detection includes `C:\wamp64`

## Install

1. Extract the installer bundle.
2. Double-click `Install-Ehsan-OpenJarvis.cmd`.
3. The installer checks/installs Git and uv with Winget when needed.
4. uv installs and manages Python 3.13 for the project.
5. The fork is cloned and the control-plane dependencies are installed.
6. Initial project and machine scans run automatically.

The installer does not modify WampServer, Ollama models, projects, or user files.

If alpha.1 was already installed, run `Repair-Ehsan-OpenJarvis.cmd`. It updates the branch, repairs the Windows PowerShell UTF-8 BOM issue in `config.toml`, keeps a backup, re-syncs dependencies, and runs Doctor + machine/model checks.

## Enable NaraRouter free models

Open PowerShell:

```powershell
cd D:\AI-Tools\OpenJarvis
uv run jarvis model nara-key
uv run jarvis model free
```

The API key is stored in OpenJarvis' local credential store and is not committed.

## First complete scan

Run `First-Run-Scan.cmd`.

It collects:

- config encoding/hash diagnostics (not config contents)

- OpenJarvis doctor output
- free local/Nara model pool
- Ollama model inventory
- Node/npm/pnpm and developer tool versions/paths
- NVM/FNM/Volta information
- package cache locations
- WampServer components, active versions, vhosts, local WordPress roots, services and ports
- D:\Projects registry
- metadata-only D: drive inventory
- cleanup candidates

Exact duplicate hashing is intentionally not included by default. To include it:

```powershell
.\First-Run-Scan.ps1 -IncludeDuplicates
```

The script creates:

`D:\AI-Control\OpenJarvis\support\openjarvis-first-run-YYYYMMDD-HHMMSS.zip`

Attach that ZIP for the next audit. Credentials are excluded.

## Start the server

Double-click `Start-Ehsan-OpenJarvis.cmd`, or run:

```powershell
cd D:\AI-Tools\OpenJarvis
uv run jarvis serve
```

Endpoints:

- personal agent API: `http://127.0.0.1:8000/v1`
- raw editor/router API: `http://127.0.0.1:8000/router/v1`
- recommended editor model alias: `free/code`

Do not clean/delete duplicate files until the generated reports have been reviewed.
