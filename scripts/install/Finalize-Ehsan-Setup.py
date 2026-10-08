"""Finalize and verify the Windows personal control-plane installation.

This script deliberately uses Python subprocess return codes rather than
PowerShell's $LASTEXITCODE, which is scope-sensitive in Windows PowerShell 5.1.
It is safe to rerun and writes a support bundle with command output but never
includes the credential store.
"""

from __future__ import annotations

import argparse
import json
import os
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


VERSION = "0.1.0-alpha.4.2"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


class Finalizer:
    def __init__(
        self,
        repo: Path,
        state: Path,
        projects: Path,
        *,
        run_cleanup: bool = False,
    ) -> None:
        self.repo = repo
        self.state = state
        self.projects = projects
        self.run_cleanup = run_cleanup
        self.support_root = state / "support"
        self.run_dir = self.support_root / f"finalize-alpha4.2-{_stamp()}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.env = os.environ.copy()
        self.env["OPENJARVIS_HOME"] = str(state)
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
            output = (exc.stdout or "") + "\nTIMEOUT\n"
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
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
            with urllib.request.urlopen(  # noqa: S310
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
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return True, json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return False, {"error": f"{type(exc).__name__}: {exc}"}

    def server_smoke(self) -> None:
        name = "13-server-smoke"
        report: dict[str, Any] = {
            "base": "http://127.0.0.1:8000",
            "started_by_finalizer": False,
            "models_ok": False,
        }

        ok, payload = self._http_get_json(
            "http://127.0.0.1:8000/router/v1/models",
            timeout=2,
        )
        process: subprocess.Popen[str] | None = None
        log_handle = None

        if not ok:
            log_path = self.run_dir / "13-server-process.txt"
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
                ok, payload = self._http_get_json(
                    "http://127.0.0.1:8000/router/v1/models",
                    timeout=2,
                )
                if ok:
                    break
                time.sleep(1.0)

        report["models_ok"] = ok
        report["models_response"] = payload
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                report["model_ids"] = [
                    item.get("id")
                    for item in data
                    if isinstance(item, dict)
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
                "returncode": 0 if ok else 1,
                "seconds": 0,
                "required": True,
            }
        )
        print(f"\n=== {name} ===")
        if not ok:
            raise RuntimeError(
                "OpenJarvis server did not expose /router/v1/models. "
                f"See {self.run_dir}"
            )
        print("Editor gateway reachable.")
        print(
            "Models: "
            + ", ".join(
                model for model in report.get("model_ids", []) if model
            )[:1000]
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
        (self.run_dir / "14-editor-configs.json").write_text(
            json.dumps(
                {
                    "destination": str(destination),
                    "files": copied,
                    "base_url": "http://127.0.0.1:8000/router/v1",
                    "recommended_model": "free/code",
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

        if self.run_cleanup:
            self.run(
                "09-cleanup",
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
            "recommended_editor_model": "free/code",
            "results": self.results,
        }
        (self.run_dir / "00-final-summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        zip_path = (
            self.support_root
            / f"openjarvis-finalize-alpha4.2-{_stamp()}.zip"
        )
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path in sorted(self.run_dir.rglob("*")):
                if path.is_file():
                    archive.write(
                        path,
                        arcname=path.relative_to(self.run_dir),
                    )
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
    args = parser.parse_args()

    finalizer = Finalizer(
        Path(args.repo),
        Path(args.state),
        Path(args.projects),
        run_cleanup=args.cleanup,
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
        print(f"\nFINALIZE FAILED: {exc}", file=sys.stderr)
        print(f"Evidence: {finalizer.run_dir}", file=sys.stderr)
        return 1

    print("\nOpenJarvis finalization complete.")
    print(f"Support ZIP: {zip_path}")
    print("Editor API: http://127.0.0.1:8000/router/v1")
    print("Editor model: free/code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
