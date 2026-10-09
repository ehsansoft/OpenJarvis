"""Finalize and verify the Windows personal control-plane installation.

This script deliberately uses Python subprocess return codes rather than
PowerShell's $LASTEXITCODE, which is scope-sensitive in Windows PowerShell 5.1.
It is safe to rerun and writes a support bundle with command output but never
includes the credential store.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

VERSION = "0.1.0-alpha.4.3"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _open_url(request, *, timeout):
    """Workstation proxies must not intercept local service verification."""
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    host = urlsplit(url).hostname or ""
    try:
        loopback = host.lower() == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    if loopback:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


def write_evidence_zip(run_dir: Path, destination: Path) -> None:
    """Bundle numbered reports only, excluding pytest fixtures and databases."""
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.iterdir()):
            if (
                not path.is_file()
                or path.is_symlink()
                or not re.fullmatch(r"\d{2}-[\w-]+\.(txt|json)", path.name)
            ):
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            content = re.sub(r"bot\d{5,}:[A-Za-z0-9_-]+", "bot[REDACTED]", content)
            content = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[REDACTED]", content)
            for key, value in os.environ.items():
                if len(value) >= 8 and any(
                    marker in key.upper()
                    for marker in ("TOKEN", "API_KEY", "SECRET", "PASSWORD")
                ):
                    content = content.replace(value, "[REDACTED]")
            archive.writestr(path.name, content)


class Finalizer:
    def __init__(
        self,
        repo: Path,
        state: Path,
        projects: Path,
        *,
        run_cleanup: bool = False,
        start_services: bool = True,
        install_scan_task: bool = True,
    ) -> None:
        self.repo = repo
        self.state = state
        self.projects = projects
        self.run_cleanup = run_cleanup
        self.start_services = start_services
        self.install_scan_task = install_scan_task
        self.support_root = state / "support"
        self.run_dir = self.support_root / f"finalize-alpha4.3-{_stamp()}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.env = os.environ.copy()
        self.env["OPENJARVIS_HOME"] = str(state)
        local_bypass = self.env.get("no_proxy", self.env.get("NO_PROXY", ""))
        local_bypass = ",".join(filter(None, (local_bypass, "localhost,127.0.0.1,::1")))
        self.env["NO_PROXY"] = self.env["no_proxy"] = local_bypass
        self.results: list[dict[str, Any]] = []
        self.uv = shutil.which("uv") or "uv"
        self.git = shutil.which("git") or "git"

    def run(
        self,
        name: str,
        args: list[str],
        *,
        required: bool = True,
        timeout: float = 900,
    ) -> subprocess.CompletedProcess[str]:
        print(f"\n=== {name} ===")
        started = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                cwd=self.repo,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            output = proc.stdout or ""
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            output += "\nTIMEOUT\n"
            code = 124

        print(output.rstrip())
        (self.run_dir / f"{name}.txt").write_text(
            output,
            encoding="utf-8",
        )
        result = {
            "name": name,
            "returncode": code,
            "seconds": round(time.monotonic() - started, 2),
            "required": required,
        }
        self.results.append(result)
        if required and code != 0:
            raise RuntimeError(
                f"{name} failed with exit code {code}. "
                f"See {self.run_dir / (name + '.txt')}"
            )
        return subprocess.CompletedProcess(args, code, output, "")

    def _voicebox_reachable(self) -> bool:
        try:
            with _open_url(
                "http://127.0.0.1:17493/health",
                timeout=3,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") in {"healthy", "ok"}
        except Exception:
            return False

    def _http_get_json(
        self,
        url: str,
        *,
        timeout: float = 5,
    ) -> tuple[bool, Any]:
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json"},
            )
            with _open_url(request, timeout=timeout) as response:
                return True, json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return False, {"error": f"{type(exc).__name__}: {exc}"}

    def server_smoke(self) -> None:
        name = "12-server-smoke"
        report: dict[str, Any] = {
            "base": "http://127.0.0.1:8000",
            "started_by_finalizer": False,
            "services_start_allowed": self.start_services,
            "models_ok": False,
        }

        root_ok, root_payload = self._http_get_json(
            "http://127.0.0.1:8000/router/v1",
            timeout=2,
        )
        ok, payload = self._http_get_json(
            "http://127.0.0.1:8000/router/v1/models",
            # A live free-provider roster refresh can exceed a local probe's
            # two-second timeout even when the existing server is healthy.
            timeout=30,
        )
        health_ok, _health_payload = self._http_get_json(
            "http://127.0.0.1:8000/health",
            timeout=2,
        )
        process: subprocess.Popen[str] | None = None
        log_handle = None

        if health_ok and ok and not root_ok:
            raise RuntimeError(
                "An older OpenJarvis server is already running on port 8000. "
                "Stop it with Ctrl+C, then rerun finalization so the updated "
                "/router/v1 discovery endpoint can be verified."
            )

        # Do not start a competing server when an existing one responds but
        # its model discovery fails. Report that failure on the existing API.
        if not (root_ok or health_ok) and self.start_services:
            log_path = self.run_dir / "12-server-process.txt"
            log_handle = log_path.open("w", encoding="utf-8")
            process = subprocess.Popen(
                [
                    self.uv,
                    "run",
                    "jarvis",
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=self.repo,
                env=self.env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            report["started_by_finalizer"] = True

            deadline = time.monotonic() + 75
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                root_ok, root_payload = self._http_get_json(
                    "http://127.0.0.1:8000/router/v1",
                    timeout=2,
                )
                ok, payload = self._http_get_json(
                    "http://127.0.0.1:8000/router/v1/models",
                    timeout=30,
                )
                if ok and root_ok:
                    break
                time.sleep(1.0)

        report["router_root_ok"] = root_ok
        report["router_root_response"] = root_payload
        report["models_ok"] = ok
        report["models_response"] = payload
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                report["model_ids"] = [
                    item.get("id") for item in data if isinstance(item, dict)
                ]

        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if log_handle is not None:
            log_handle.close()

        (self.run_dir / f"{name}.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.results.append(
            {
                "name": name,
                "returncode": 0 if (ok and root_ok) else 1,
                "seconds": 0,
                "required": True,
            }
        )
        print(f"\n=== {name} ===")
        if not ok or not root_ok:
            raise RuntimeError(
                "OpenJarvis server did not expose the complete editor API "
                "(/router/v1 and /router/v1/models). "
                f"See {self.run_dir}"
            )
        print("Editor gateway reachable.")
        print(
            "Models: "
            + ", ".join(model for model in report.get("model_ids", []) if model)[:1000]
        )

    def copy_editor_templates(self) -> None:
        destination = self.state / "editor-configs"
        destination.mkdir(parents=True, exist_ok=True)
        source = self.repo / "configs" / "editors"
        copied: list[str] = []
        if source.is_dir():
            for path in source.iterdir():
                if path.is_file():
                    shutil.copy2(path, destination / path.name)
                    copied.append(path.name)
        (self.run_dir / "13-editor-configs.json").write_text(
            json.dumps(
                {
                    "destination": str(destination),
                    "files": copied,
                    "base_url": "http://127.0.0.1:8000/router/v1",
                    "recommended_model": "local/code",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def finalize(self) -> Path:
        config = self.state / "config.toml"
        if not config.exists():
            raise FileNotFoundError(f"OpenJarvis config not found: {config}")

        self.run(
            "01-config-upgrade",
            [
                self.uv,
                "run",
                "python",
                "scripts/install/Upgrade-Ehsan-Config.py",
                str(config),
            ],
        )
        self.run(
            "02-targeted-tests",
            [
                self.uv,
                "run",
                "pytest",
                "tests/core/test_config.py",
                "tests/core/test_control_plane_config.py",
                "tests/core/test_ehsan_control_plane_upgrade.py",
                "tests/core/test_ehsan_finalizer.py",
                "tests/core/test_voicebox_mcp_check.py",
                "tests/core/test_real_user_acceptance.py",
                "tests/core/test_acceptance_cmd.py",
                "tests/core/test_capability_catalog.py",
                "tests/core/test_loopback_http.py",
                "tests/security/test_capabilities.py",
                "tests/cli/test_standalone_security.py",
                "tests/operators/test_operators.py",
                "tests/server/test_mcp_tools_cache.py",
                "tests/scheduler",
                "tests/channels/test_telegram.py",
                "tests/server/test_channel_bridge.py",
                "tests/server/test_editor_gateway.py",
                "tests/server/test_research_planner.py",
                "tests/skills/test_sources.py",
                "tests/skills/test_importer.py",
                "tests/cli/test_chat_cmd.py",
                "tests/cli/test_memory_cmd.py",
                "tests/cli/test_serve_single_build.py",
                "tests/speech/test_voicebox_tts.py",
                "tests/cli/test_projects_cmd.py",
                "tests/engine/test_nararouter.py",
                "tests/intelligence/test_free_pool.py",
                "tests/projects/test_discovery.py",
                "tests/projects/test_inventory.py",
                "tests/projects/test_machine_inventory.py",
                "tests/projects/test_hygiene.py",
                "tests/tools/test_voicebox_status.py",
                "tests/speech/test_voicebox_stt.py",
                "tests/speech/test_discovery.py",
                "tests/mcp/test_transport.py",
                "tests/mcp/test_loader.py",
                "tests/security/test_rate_limiter.py",
                "tests/server/test_routes.py",
                # Old elevated Windows runs may leave inaccessible pytest
                # directories. Keep this run independent without deleting them.
                "--basetemp",
                str(self.run_dir / "pytest-temp"),
                "-o",
                f"cache_dir={self.run_dir / 'pytest-cache'}",
                "-q",
            ],
            timeout=1200,
        )
        self.run(
            "03-doctor",
            [self.uv, "run", "jarvis", "doctor"],
            required=False,
        )

        voicebox = self._voicebox_reachable()
        self.run(
            "04-voicebox-scan",
            [
                self.uv,
                "run",
                "jarvis",
                "projects",
                "voicebox-scan",
                "--host",
                "http://127.0.0.1:17493",
                "--json",
            ],
            required=voicebox,
        )
        self.run(
            "05-voicebox-mcp",
            [
                self.uv,
                "run",
                "python",
                "scripts/install/Check-Voicebox-MCP.py",
            ],
            required=voicebox,
        )
        self.run(
            "06-machine-scan",
            [self.uv, "run", "jarvis", "projects", "machine-scan", "--json"],
        )
        self.run(
            "07-free-models",
            [self.uv, "run", "jarvis", "model", "free", "--json"],
        )
        self.run(
            "08-projects",
            [
                self.uv,
                "run",
                "jarvis",
                "projects",
                "scan",
                str(self.projects),
                "--max-depth",
                "5",
                "--json",
            ],
            timeout=1200,
        )

        # Install/update the lightweight daily metadata service requested for
        # the workstation. This refreshes project, machine and drive inventory;
        # it intentionally does not hash duplicates or delete anything.
        if self.install_scan_task:
            self.run(
                "09-scheduled-scan-install",
                [
                    self.uv,
                    "run",
                    "jarvis",
                    "projects",
                    "install-scan-task",
                    "--root",
                    "D:\\",
                    "--daily-at",
                    "03:00",
                ],
                required=False,
            )
        self.run(
            "10-scheduled-scan-status",
            [
                self.uv,
                "run",
                "jarvis",
                "projects",
                "scan-task-status",
            ],
            required=False,
        )

        if self.run_cleanup:
            self.run(
                "11-cleanup",
                [
                    self.uv,
                    "run",
                    "jarvis",
                    "projects",
                    "cleanup-scan",
                    "D:\\",
                    "--min-age-days",
                    "30",
                    "--json",
                ],
                timeout=2400,
            )

        self.server_smoke()
        self.copy_editor_templates()

        summary = {
            "version": VERSION,
            "repo": str(self.repo),
            "state": str(self.state),
            "projects": str(self.projects),
            "voicebox_reachable": voicebox,
            "editor_api": "http://127.0.0.1:8000/router/v1",
            "personal_api": "http://127.0.0.1:8000/v1",
            "recommended_editor_model": "local/code",
            "results": self.results,
        }
        (self.run_dir / "00-final-summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        zip_path = self.support_root / f"openjarvis-finalize-alpha4.3-{_stamp()}.zip"
        write_evidence_zip(self.run_dir, zip_path)
        return zip_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default=r"D:\AI-Tools\OpenJarvis",
    )
    parser.add_argument(
        "--state",
        default=r"D:\AI-Control\OpenJarvis",
    )
    parser.add_argument(
        "--projects",
        default=r"D:\Projects",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Also rerun the slower whole-D cleanup ranking.",
    )
    parser.add_argument(
        "--no-start-services",
        action="store_true",
        help="Inspect the existing server; never start services for verification.",
    )
    parser.add_argument(
        "--no-install-scan-task",
        action="store_true",
        help="Inspect the existing inventory task without installing or enabling it.",
    )
    args = parser.parse_args()

    finalizer = Finalizer(
        Path(args.repo),
        Path(args.state),
        Path(args.projects),
        run_cleanup=args.cleanup,
        start_services=not args.no_start_services,
        install_scan_task=not args.no_install_scan_task,
    )
    try:
        zip_path = finalizer.finalize()
    except Exception as exc:
        failure = {
            "version": VERSION,
            "error": f"{type(exc).__name__}: {exc}",
            "results": finalizer.results,
        }
        (finalizer.run_dir / "00-final-failure.json").write_text(
            json.dumps(failure, indent=2),
            encoding="utf-8",
        )
        failure_zip = (
            finalizer.support_root
            / f"openjarvis-finalize-alpha4.3-failed-{_stamp()}.zip"
        )
        write_evidence_zip(finalizer.run_dir, failure_zip)
        print(f"\nFINALIZE FAILED: {exc}", file=sys.stderr)
        print(f"Evidence: {failure_zip}", file=sys.stderr)
        return 1

    print("\nOpenJarvis finalization complete.")
    print(f"Support ZIP: {zip_path}")
    print("Editor API: http://127.0.0.1:8000/router/v1")
    print("Editor model: local/code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
