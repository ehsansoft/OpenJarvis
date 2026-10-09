"""Readiness, evidence freshness, safe probing and read-only regressions."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from openjarvis.cli.capabilities_cmd import capabilities
from openjarvis.core.capability_catalog import (
    MetadataProbe,
    build_catalog,
    discover_nara,
)
from openjarvis.core.config import JarvisConfig

NOW = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)


@pytest.fixture
def setup(tmp_path):
    cfg = JarvisConfig()
    cfg.intelligence.default_model = "local/fast"
    cfg.speech.backend = cfg.speech.tts_backend = "voicebox"
    cfg.projects.registry_path = str(tmp_path / "registry.json")
    cfg.projects.machine_inventory_path = str(tmp_path / "machine.json")
    cfg.tools.storage.db_path = str(tmp_path / "memory.db")
    Path(cfg.projects.registry_path).write_text(
        json.dumps(
            {
                "schema_version": 2,
                "projects": [
                    {
                        "project_id": "p",
                        "name": "project",
                        "path": "D:\\Projects\\p",
                        "role": "active",
                    }
                ],
            }
        )
    )
    return cfg, tmp_path


def probe(*, loaded=True, unavailable=None):
    calls = []

    def get(host, path, payload=None):
        calls.append((host, path, payload))
        if unavailable and unavailable in host:
            raise httpx.ConnectError("secret diagnostic must not escape")
        if path == "/health":
            return {"status": "healthy"}
        if path == "/api/tags":
            return {
                "models": [
                    {"name": name, "digest": name + "-digest"}
                    for name in (
                        "qwen3.5:2b",
                        "qwen2.5-coder:7b",
                        "nomic-embed-text:latest",
                    )
                ]
            }
        if path == "/api/show":
            return {
                "capabilities": ["embedding"]
                if "nomic" in payload["name"]
                else ["completion", "vision", "tools"]
                if "3.5" in payload["name"]
                else ["completion", "tools"]
            }
        if path == "/models/status":
            return {
                "models": [
                    {"model_name": "kokoro", "downloaded": True, "loaded": loaded},
                    {"model_name": "whisper-base", "downloaded": True, "loaded": True},
                ]
            }
        if path == "/profiles":
            return [
                {
                    "id": "profile",
                    "voice_type": "preset",
                    "preset_engine": "kokoro",
                    "preset_voice_id": "bm_george",
                }
            ]
        raise AssertionError(path)

    get.calls = calls
    return get


def evidence(setup, *, age=timedelta(), failed=None):
    cfg, root = setup
    fingerprint = build_catalog(
        cfg, root, now=NOW, probe=probe(), nara=lambda *args: None, which=lambda _: None
    )["context_sha256"]
    folder = root / "support" / "acceptance-fixture"
    folder.mkdir(parents=True)
    checks = [
        {
            "name": f"local/{task}",
            "status": "PASS",
            "evidence": {
                "routing": {
                    "selected_model": "qwen2.5-coder:7b"
                    if task == "code"
                    else "qwen3.5:2b",
                    "selected_engine": "ollama",
                }
            },
        }
        for task in ("code", "fast", "research", "vision")
    ]
    checks += [
        {"name": name, "status": "PASS"}
        for name in (
            "jarvis_chat_real",
            "nomic_local_embedding",
            "local_vision_image",
            "voicebox_service",
            "voicebox_stt_live",
            "voicebox_tts_stt_roundtrip",
            "scheduler_real_local_execution",
        )
    ]
    if failed:
        for check in checks:
            if check["name"] == failed:
                check["status"] = "FAIL"
    (folder / "acceptance.json").write_text(
        json.dumps(
            {
                "timestamp": (NOW - age).strftime("%Y%m%d-%H%M%S"),
                "checks": checks,
                "context_sha256": fingerprint,
            }
        )
    )


def catalog(setup, **kwargs):
    cfg, root = setup
    return build_catalog(
        cfg,
        root,
        now=NOW,
        probe=kwargs.pop("probe", probe()),
        nara=kwargs.pop("nara", lambda *args: ["current-free"]),
        which=lambda name: None,
        **kwargs,
    )


def records(report):
    return {r["id"]: r for r in report["capabilities"]}


def test_installed_models_are_not_accepted_without_evidence(setup):
    r = records(catalog(setup))
    assert r["local/fast"]["installed"] is True
    assert r["local/fast"]["configured"] is True
    assert r["local/fast"]["accepted"] is False
    assert r["local/fast"]["status"] == "MANUAL_SETUP"
    assert r["embeddings"]["status"] == "MANUAL_SETUP"


@pytest.mark.parametrize("loaded,expected", [(True, "READY"), (False, "BLOCKED")])
def test_kokoro_loaded_state_and_separate_human_gate(setup, loaded, expected):
    evidence(setup)
    r = records(catalog(setup, probe=probe(loaded=loaded)))
    assert r["kokoro-tts"]["status"] == expected
    assert r["microphone"]["accepted"] is False
    assert r["microphone"]["status"] == "MANUAL_SETUP"


def test_wrong_profile_cannot_be_ready(setup):
    evidence(setup)
    setup[0].speech.voice_id = "missing-profile"
    assert records(catalog(setup))["kokoro-tts"]["status"] == "BLOCKED"


def test_voicebox_unavailable_invalidates_old_acceptance(setup):
    evidence(setup)
    report = catalog(setup, probe=probe(unavailable="17493"))
    r = records(report)
    assert r["voicebox"]["status"] == "BLOCKED"
    assert r["kokoro-tts"]["status"] == "BLOCKED"
    assert "secret diagnostic" not in json.dumps(report)


@pytest.mark.parametrize("age", [timedelta(days=2), timedelta(days=-1)])
def test_stale_and_future_evidence_cannot_accept(setup, age):
    evidence(setup, age=age)
    report = catalog(setup)
    assert records(report)["local/fast"]["accepted"] is False
    assert report["acceptance_evidence"]["state"] == "stale-or-future"


def test_failed_evidence_is_not_promoted_from_model_presence(setup):
    evidence(setup, failed="local/fast")
    assert records(catalog(setup))["local/fast"]["status"] == "MANUAL_SETUP"


def test_dynamic_roster_is_observed_not_hardcoded_or_qualified(setup):
    one = records(catalog(setup, nara=lambda *args: ["a"]))["nara-free-pool"]
    two = records(catalog(setup, nara=lambda *args: ["b", "c"]))["nara-free-pool"]
    assert one["evidence"][0]["model_ids"] == ["a"]
    assert two["evidence"][0]["model_ids"] == ["b", "c"]
    assert two["accepted"] is False


def test_changed_weights_under_same_tag_invalidate_acceptance(setup):
    evidence(setup)
    normal = probe()

    def updated(host, path, payload=None):
        data = normal(host, path, payload)
        if path == "/api/tags":
            data["models"][0]["digest"] = "replacement-weights"
        return data

    record = records(catalog(setup, probe=updated))["local/fast"]
    assert record["accepted"] is False
    assert record["status"] != "READY"


def test_legacy_report_without_model_context_requires_new_acceptance(setup):
    evidence(setup)
    source = setup[1] / "support" / "acceptance-fixture" / "acceptance.json"
    report = json.loads(source.read_text())
    report.pop("context_sha256")
    source.write_text(json.dumps(report))
    assert records(catalog(setup))["local/fast"]["accepted"] is False


def test_configuration_change_invalidates_model_acceptance(setup):
    evidence(setup)
    setup[0].intelligence.allow_private_remote = True
    assert records(catalog(setup))["local/code"]["accepted"] is False


def test_registry_read_only_and_no_capability_store(setup):
    cfg, root = setup
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    report = catalog(setup)
    r = records(report)
    assert r["project-registry"]["status"] == "READY"
    assert r["project-registry"]["evidence"][0]["total"] == 1
    assert r["project-review"]["status"] == "READY"
    assert r["scoped-project-memory"]["status"] == "BLOCKED"
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not Path(cfg.tools.storage.db_path).exists()


def test_unavailable_api_and_timeout_are_bounded_failures(setup):
    evidence(setup)

    def failing(host, path, payload=None):
        if "8000" in host:
            raise httpx.ReadTimeout("do not leak raw exception")
        return probe()(host, path, payload)

    r = records(catalog(setup, probe=failing))
    assert r["personal-api"]["status"] == "BLOCKED"
    assert r["local/fast"]["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/models/load", {"model_name": "kokoro"}),
        ("/generate", {"text": "hi"}),
        ("/profiles", {}),
    ],
)
def test_metadata_probe_refuses_mutations(path, payload):
    with pytest.raises(ValueError):
        MetadataProbe()("http://127.0.0.1:17493", path, payload)


@pytest.mark.parametrize(
    "host",
    [
        "https://remote.example",
        "http://127.0.0.1@remote.example",
        "http://127.0.0.1?token=secret",
    ],
)
def test_loopback_probe_rejects_remote_and_secret_urls(host):
    with pytest.raises(ValueError):
        MetadataProbe()(host, "/health")


def test_http_timeout_no_proxy_no_redirect_and_valid_metadata(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://invalid.example:1")
    requests = []

    def handler(request):
        requests.append(request)
        assert request.extensions["timeout"]["read"] == 0.25
        return httpx.Response(200, json={"status": "healthy"})

    assert (
        MetadataProbe(0.25, httpx.MockTransport(handler))(
            "http://127.0.0.1:17493", "/health"
        )["status"]
        == "healthy"
    )
    assert len(requests) == 1


def test_malformed_credentials_remain_untouched(setup, monkeypatch):
    path = setup[1] / "credentials.toml"
    path.write_text("this is invalid TOML")
    monkeypatch.delenv("NARAROUTER_API_KEY", raising=False)
    assert discover_nara(setup[0], setup[1], 0.1) is None
    assert path.read_text() == "this is invalid TOML"
    assert list(setup[1].glob("credentials*")) == [path]


def test_cli_text_json_and_no_state_creation(setup, monkeypatch, tmp_path):
    import openjarvis.cli.capabilities_cmd as module

    report = catalog(setup)
    root = tmp_path / "missing-root"
    monkeypatch.setattr(module, "get_config_dir", lambda: root)
    monkeypatch.setattr(module, "get_config_path", lambda: root / "config.toml")
    monkeypatch.setattr(module, "build_catalog", lambda *args, **kwargs: report)
    runner = CliRunner()
    text = runner.invoke(capabilities)
    assert text.exit_code == 0
    assert "OPENJARVIS WORKSTATION CAPABILITIES" in text.output
    assert "Next:" in text.output
    data = runner.invoke(capabilities, ["--json"])
    assert data.exit_code == 0
    assert json.loads(data.output) == report
    assert not root.exists()


def test_json_contract_stability_and_all_requested_capabilities(setup):
    report = catalog(setup)
    expected = {
        "id",
        "display_name",
        "status",
        "configured",
        "installed",
        "accepted",
        "reason",
        "evidence",
        "observed_at",
        "next_action",
        "related_commands",
        "privacy",
        "dependencies",
    }
    assert report["schema_version"] == 1 and report["read_only"] is True
    assert len(report["capabilities"]) == 32
    assert len(records(report)) == 32
    for record in report["capabilities"]:
        assert set(record) == expected
        assert record["next_action"]
        assert record["status"] in {
            "READY",
            "MANUAL_SETUP",
            "DISABLED",
            "BLOCKED",
            "NOT_INSTALLED",
            "NOT_APPLICABLE",
        }
        assert set(record["dependencies"]) <= set(records(report))


def test_fresh_human_proof_is_context_bound_and_does_not_write_state(setup):
    evidence(setup)
    initial = catalog(setup)
    source = setup[1] / "support" / "acceptance-fixture" / "acceptance.json"
    report = json.loads(source.read_text())
    report["checks"].append(
        {
            "name": "microphone_and_listening",
            "status": "PASS",
            "evidence": {
                "confirmation": "human",
                "context_sha256": initial["context_sha256"],
            },
        }
    )
    source.write_text(json.dumps(report))
    before = source.read_bytes()
    assert records(catalog(setup))["microphone"]["status"] == "READY"
    assert source.read_bytes() == before
    setup[0].speech.voice_id = "different-profile"
    assert records(catalog(setup))["microphone"]["accepted"] is False


def test_legacy_automatic_pass_cannot_confirm_human_gate(setup):
    evidence(setup)
    source = setup[1] / "support" / "acceptance-fixture" / "acceptance.json"
    report = json.loads(source.read_text())
    report["checks"].append({"name": "microphone_and_listening", "status": "PASS"})
    source.write_text(json.dumps(report))
    assert records(catalog(setup))["microphone"]["accepted"] is False


def test_loaded_whisper_overrides_inconsistent_cached_flag(setup):
    evidence(setup)
    normal = probe()

    def inconsistent(host, path, payload=None):
        data = normal(host, path, payload)
        if path == "/models/status":
            data["models"][1]["downloaded"] = False
        return data

    record = records(catalog(setup, probe=inconsistent))["whisper-stt"]
    assert record["installed"] is True
    assert record["status"] == "READY"


def test_cli_bootstrap_skips_outbound_update_poll():
    import click

    from openjarvis.cli import _should_skip_update_check

    context = click.Context(click.Command("jarvis"))
    context.invoked_subcommand = "capabilities"
    assert _should_skip_update_check(context, ["capabilities", "--json"])


def test_contract_schema_matches_serialized_report(setup):
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "configs/openjarvis/schemas/capability-catalog-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text())
    report = catalog(setup)
    assert set(schema["required"]) == set(report)
    item = schema["properties"]["capabilities"]["items"]
    types = {
        "string": str,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
        "integer": int,
    }
    for record in report["capabilities"]:
        assert set(item["required"]) == set(record)
        for key, value in record.items():
            rule = item["properties"][key]
            if "enum" in rule:
                assert value in rule["enum"]
            if "type" in rule:
                allowed = rule["type"]
                allowed = [allowed] if isinstance(allowed, str) else allowed
                assert type(value) in tuple(types[name] for name in allowed)
        if record["status"] == "READY":
            assert record["configured"] and record["installed"] and record["accepted"]
