"""Regression coverage for real-machine finalizer test isolation."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _module():
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install/Finalize-Ehsan-Setup.py"
    )
    spec = importlib.util.spec_from_file_location("ehsan_finalizer_evidence", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_zip_excludes_test_state_and_redacts_tokens(tmp_path, monkeypatch):
    module = _module()
    run = tmp_path / "run"
    run.mkdir()
    secret = "private-acceptance-token-123"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", secret)
    (run / "00-final-summary.json").write_text('{"status":"ok"}')
    (run / "02-targeted-tests.txt").write_text(secret + " Bearer authorization-value")
    (run / "credentials.toml").write_text(secret)
    fixtures = run / "pytest-temp"
    fixtures.mkdir()
    (fixtures / "00-credentials.json").write_text(secret)
    (fixtures / "sessions.db").write_bytes(b"PRIVATE_CHAT")
    destination = tmp_path / "evidence.zip"
    module.write_evidence_zip(run, destination)
    with zipfile.ZipFile(destination) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == {
            "00-final-summary.json",
            "02-targeted-tests.txt",
        }
        payload = b"".join(bundle.read(name) for name in bundle.namelist())
        assert secret.encode() not in payload
        assert b"authorization-value" not in payload
        assert b"PRIVATE_CHAT" not in payload


def test_timeout_retains_byte_output_and_produces_failure_evidence(
    tmp_path, monkeypatch
):
    module = _module()
    finalizer = module.Finalizer(tmp_path, tmp_path / "state", tmp_path / "projects")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        MagicMock(side_effect=subprocess.TimeoutExpired(["fixture"], 1, b"partial")),
    )
    with pytest.raises(RuntimeError, match="exit code 124"):
        finalizer.run("02-targeted-tests", ["fixture"], timeout=1)
    assert (
        "partial\nTIMEOUT" in (finalizer.run_dir / "02-targeted-tests.txt").read_text()
    )
    assert finalizer.results[0]["returncode"] == 124


def test_finalizer_avoids_legacy_pytest_directories(tmp_path: Path) -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install/Finalize-Ehsan-Setup.py"
    )
    spec = importlib.util.spec_from_file_location("ehsan_finalizer", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    repo = tmp_path / "repo"
    state = tmp_path / "state"
    repo.mkdir()
    state.mkdir()
    (state / "config.toml").write_text("", encoding="utf-8")
    # A file blocks pytest's default cache just as a legacy ACL can on Windows.
    legacy_cache = repo / ".pytest_cache"
    legacy_cache.write_text("preserve legacy state", encoding="utf-8")
    probe = repo / "test_probe.py"
    probe.write_text(
        "def test_temp(tmp_path):\n"
        "    assert 'pytest-temp' in str(tmp_path)\n"
        "    (tmp_path / 'probe').write_text('ok')\n",
        encoding="utf-8",
    )
    finalizer = module.Finalizer(repo, state, tmp_path / "projects")

    class SuiteVerified(Exception):
        pass

    def run(name, args, **kwargs):
        if name == "01-config-upgrade":
            return
        assert name == "02-targeted-tests"
        # Exercise the actual pytest options assembled by finalize(), with a
        # small real suite. Cache warnings must fail rather than be hidden.
        options = args[args.index("--basetemp") :]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(probe),
                *options,
                "-W",
                "error::pytest.PytestCacheWarning",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert (finalizer.run_dir / "pytest-cache/v/cache/nodeids").is_file()
        assert legacy_cache.read_text(encoding="utf-8") == "preserve legacy state"
        raise SuiteVerified

    finalizer.run = run
    with pytest.raises(SuiteVerified):
        finalizer.finalize()


@pytest.mark.parametrize("models_available", [True, False])
def test_server_smoke_does_not_compete_with_existing_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, models_available: bool
) -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install/Finalize-Ehsan-Setup.py"
    )
    spec = importlib.util.spec_from_file_location("ehsan_finalizer_smoke", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    finalizer = module.Finalizer(tmp_path, tmp_path / "state", tmp_path)
    popen = MagicMock(side_effect=AssertionError("Attempted a competing server"))
    monkeypatch.setattr(module.subprocess, "Popen", popen)

    def get_json(url, *, timeout):
        if url.endswith("/models"):
            # Simulate discovery that cannot complete within two seconds.
            if not models_available or timeout < 10:
                return False, {"error": "Model discovery timed out"}
            return True, {"data": [{"id": "free/code"}]}
        return True, {"status": "ok"}

    finalizer._http_get_json = get_json
    if models_available:
        finalizer.server_smoke()
    else:
        with pytest.raises(RuntimeError, match="server did not expose"):
            finalizer.server_smoke()
    popen.assert_not_called()
    assert finalizer.results[-1]["returncode"] == (0 if models_available else 1)


def test_new_server_smoke_allows_cold_roster_discovery(tmp_path, monkeypatch):
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install/Finalize-Ehsan-Setup.py"
    )
    spec = importlib.util.spec_from_file_location("ehsan_cold_server", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    finalizer = module.Finalizer(tmp_path, tmp_path / "state", tmp_path)
    process = MagicMock()
    process.poll.return_value = None
    started = False

    def start(*args, **kwargs):
        nonlocal started
        started = True
        return process

    def probe(url, *, timeout):
        if not started:
            return False, {}
        if url.endswith("/models"):
            assert timeout >= 10
            return True, {"data": [{"id": "local/code"}]}
        return True, {"status": "ok"}

    monkeypatch.setattr(module.subprocess, "Popen", start)
    finalizer._http_get_json = probe
    finalizer.server_smoke()
    assert finalizer.results[-1]["returncode"] == 0
