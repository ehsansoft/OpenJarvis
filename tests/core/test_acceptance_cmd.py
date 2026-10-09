"""Evidence sharing and editor-template contracts for Phase 0.5."""

import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from openjarvis.cli.acceptance_cmd import (
    ACCEPTANCE_TESTS,
    check_cli_output,
    generate_support_zip,
)


def test_cli_acceptance_accepts_rich_stderr_and_rejects_missing_answer():
    check_cli_output(
        subprocess.CompletedProcess([], 0, "", "ACCEPTANCE_OK"), "ACCEPTANCE_OK"
    )
    with pytest.raises(RuntimeError):
        check_cli_output(
            subprocess.CompletedProcess([], 0, "prompt", ""), "ACCEPTANCE_OK"
        )
    with pytest.raises(RuntimeError):
        check_cli_output(
            subprocess.CompletedProcess([], 1, "ACCEPTANCE_OK", "error"),
            "ACCEPTANCE_OK",
        )


def test_acceptance_suite_references_real_tests():
    repo = Path(__file__).resolve().parents[2]
    assert all(
        (repo / path).exists() for paths in ACCEPTANCE_TESTS.values() for path in paths
    )


def test_support_zip_redacts_secrets_and_excludes_runtime_files(tmp_path, monkeypatch):
    secret = "test-private-secret-12345"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", secret)
    run = tmp_path / "acceptance"
    run.mkdir()
    (run / "credentials.toml").write_text(secret)
    (run / "private-project.txt").write_text("PRIVATE_CHUNK")
    (run / "regression.log").write_text("test output " + secret)
    archive = generate_support_zip(
        run, {"checks": [{"name": "fixture", "error": secret}]}, tmp_path
    )
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert set(bundle.namelist()) == {"acceptance.json", "regression.log"}
        payload = b"".join(bundle.read(name) for name in bundle.namelist())
        assert secret.encode() not in payload
        assert b"PRIVATE_CHUNK" not in payload


@pytest.mark.parametrize(
    "filename,provider_key",
    [
        ("opencode.openjarvis.jsonc", "providers"),
        ("opencode-v1.openjarvis.jsonc", "provider"),
        ("kilo.openjarvis.jsonc", "provider"),
    ],
)
def test_editor_templates_default_to_local_alias_and_live_api_contract(
    filename, provider_key
):
    from fastapi.testclient import TestClient

    from openjarvis.intelligence.free_pool import FreePoolEngine
    from openjarvis.server.app import create_app
    from tests.intelligence.test_free_pool import _FakeEngine

    repo = Path(__file__).resolve().parents[2]
    template = json.loads((repo / "configs" / "editors" / filename).read_text())
    provider_id, selected_key = template["model"].split("/", 1)
    provider = template[provider_key][provider_id]
    selected = provider["models"][selected_key]
    model_id = selected.get("modelID", selected.get("id", selected_key))
    assert model_id == "local/code"
    options = provider.get("settings", provider.get("options"))
    assert options["baseURL"] == "http://127.0.0.1:8000/router/v1"
    pool = FreePoolEngine([("ollama", _FakeEngine(["qwen2.5-coder:7b"]))])
    client = TestClient(create_app(pool, model_id))
    response = client.post(
        "/router/v1/chat/completions",
        json={
            "model": model_id,
            "messages": [{"role": "user", "content": "synthetic editor check"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "qwen2.5-coder:7b"
