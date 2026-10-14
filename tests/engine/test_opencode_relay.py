"""Tests for the OpenCode CLI relay engine (free tier via the official CLI)."""

from __future__ import annotations

import os
import subprocess

import pytest

from openjarvis.core.config import JarvisConfig
from openjarvis.core.types import Message, Role
from openjarvis.engine._base import EngineConnectionError
from openjarvis.engine._discovery import _make_engine
from openjarvis.engine.opencode import _DEFAULT_ROSTER, OpenCodeEngine

_MODELS_STDOUT = "\n".join(
    [
        "opencode/mimo-v2.6-flash-free",
        "opencode/nemotron-3.5-lightning-free",
        "ollama/qwen3-8b",  # foreign provider rows are ignored
        "byNara/some-model",
    ]
)

_RUN_STDOUT = "\n".join(
    [
        '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}',
        '{"type":"text","timestamp":2,"part":{"type":"text","text":"RELAY_"}}',
        '{"type":"text","timestamp":3,"part":{"type":"text","text":"OK"}}',
        "not-json noise is ignored",
    ]
)


def _fake_binary(tmp_path) -> str:
    """Point the engine at a stub binary (resolution short-circuits)."""
    path = tmp_path / "opencode.cmd"
    path.write_text("@echo off\r\n", encoding="utf-8")
    return str(path)


def _install_fake_cli(engine: OpenCodeEngine, *, run_stdout: str = _RUN_STDOUT):
    """Replace the subprocess seam; returns the recorded call list."""
    calls: list[dict] = []

    def _run(args, *, input_text, cwd, timeout):
        calls.append(
            {"args": args, "input": input_text, "cwd": cwd, "timeout": timeout}
        )
        if args[1] == "models":
            return subprocess.CompletedProcess(
                args, 0, stdout=_MODELS_STDOUT, stderr=""
            )
        return subprocess.CompletedProcess(args, 0, stdout=run_stdout, stderr="")

    engine._run_cli = _run  # type: ignore[method-assign]
    return calls


class TestOpenCodeEngine:
    def test_engine_identity(self) -> None:
        assert OpenCodeEngine.engine_id == "opencode"
        # The relay runs locally but inference is remote: never zero-API-local.
        assert OpenCodeEngine.is_cloud is True

    def test_health_false_without_binary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr("openjarvis.engine.opencode.shutil.which", lambda _n: None)
        engine = OpenCodeEngine(path=str(tmp_path / "missing-opencode.cmd"))
        assert engine.health() is False

    def test_health_true_with_configured_binary(self, tmp_path) -> None:
        engine = OpenCodeEngine(path=_fake_binary(tmp_path))
        assert engine.health() is True

    def test_roster_from_cli_listing(self, tmp_path) -> None:
        engine = OpenCodeEngine(path=_fake_binary(tmp_path))
        _install_fake_cli(engine)

        assert engine.list_models() == [
            "opencode/mimo-v2.6-flash-free",
            "opencode/nemotron-3.5-lightning-free",
        ]
        # Everything the CLI advertises under opencode/ is free-tier.
        assert engine.list_free_model_ids() == engine.list_models()
        assert engine.can_serve("opencode/mimo-v2.6-flash-free") is True
        assert engine.can_serve("opencode/unknown-model") is False
        assert engine.can_serve("qwen3-8b") is False

    def test_roster_falls_back_to_default_when_cli_fails(self, tmp_path) -> None:
        engine = OpenCodeEngine(path=_fake_binary(tmp_path))

        def _boom(*_args, **_kwargs):
            raise OSError("cli unavailable")

        engine._run_cli = _boom  # type: ignore[method-assign]
        assert engine.list_models() == [
            f"opencode/{model_id}" for model_id in _DEFAULT_ROSTER
        ]

    def test_generate_relays_through_read_only_agent(self, tmp_path) -> None:
        engine = OpenCodeEngine(path=_fake_binary(tmp_path))
        calls = _install_fake_cli(engine)

        result = engine.generate(
            [
                Message(role=Role.SYSTEM, content="Be brief."),
                Message(role=Role.USER, content="Say the sentinel."),
            ],
            model="opencode/mimo-v2.6-flash-free",
        )

        run_call = next(c for c in calls if c["args"][1] == "run")
        # Read-only agent + JSON stream + prefixed model id.
        assert run_call["args"][2:] == [
            "--agent",
            "plan",
            "--format",
            "json",
            "-m",
            "opencode/mimo-v2.6-flash-free",
        ]
        # The prompt travels on stdin (no argv quoting path), role-tagged,
        # and ends with the assistant marker.
        assert "[system]\nBe brief." in run_call["input"]
        assert run_call["input"].endswith("[assistant]")
        # Relay runs in a disposable temp cwd.
        assert os.path.basename(run_call["cwd"] or "").startswith(
            "oj-opencode-relay-"
        )

        # NDJSON text parts are concatenated in order.
        assert result["content"] == "RELAY_OK"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["prompt_tokens"] >= 1

    def test_generate_rejects_unknown_model(self, tmp_path) -> None:
        engine = OpenCodeEngine(path=_fake_binary(tmp_path))
        _install_fake_cli(engine)

        with pytest.raises(EngineConnectionError, match="free roster"):
            engine.generate(
                [Message(role=Role.USER, content="hi")],
                model="opencode/not-in-roster",
            )

    def test_generate_surfaces_nonzero_exit(self, tmp_path) -> None:
        engine = OpenCodeEngine(path=_fake_binary(tmp_path))

        def _run(args, *, input_text, cwd, timeout):
            if args[1] == "models":
                return subprocess.CompletedProcess(
                    args, 0, stdout="opencode/mimo-v2.6-flash-free", stderr=""
                )
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")

        engine._run_cli = _run  # type: ignore[method-assign]

        with pytest.raises(EngineConnectionError, match="exited with 1"):
            engine.generate(
                [Message(role=Role.USER, content="hi")],
                model="opencode/mimo-v2.6-flash-free",
            )

    def test_make_engine_reads_config(self, tmp_path) -> None:
        config = JarvisConfig()
        config.engine.opencode.path = _fake_binary(tmp_path)
        config.engine.opencode.timeout = 42.0

        engine = _make_engine("opencode", config)

        assert isinstance(engine, OpenCodeEngine)
        assert engine._configured == _fake_binary(tmp_path)
        assert engine._timeout == 42.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
