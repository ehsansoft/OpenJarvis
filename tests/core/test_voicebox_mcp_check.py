"""Voicebox discovery must require capabilities, accepting both name styles."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("direct_dotted", [True, False])
@pytest.mark.parametrize("configured_dotted", [True, False])
@pytest.mark.parametrize("missing_from", [None, "direct", "configured"])
def test_probe_checks_all_four_tools_and_closes_clients(
    monkeypatch: pytest.MonkeyPatch,
    direct_dotted: bool,
    configured_dotted: bool,
    missing_from: str | None,
) -> None:
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install/Check-Voicebox-MCP.py"
    )
    spec = importlib.util.spec_from_file_location("voicebox_mcp_check", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def names(dotted):
        prefix = "voicebox." if dotted else "voicebox_"
        return [
            prefix + action
            for action in (
                "speak",
                "transcribe",
                "list_captures",
                "list_profiles",
            )
        ]

    direct = names(direct_dotted)
    configured = names(configured_dotted)
    if missing_from == "direct":
        direct.pop()
    if missing_from == "configured":
        configured.pop()
    monkeypatch.setattr(module, "_direct_probe", lambda: (direct, "{}"))
    monkeypatch.setattr(
        module,
        "load_config",
        lambda: SimpleNamespace(tools=SimpleNamespace(mcp=object())),
    )
    client = MagicMock()
    loader = MagicMock(
        return_value=(
            [SimpleNamespace(spec=SimpleNamespace(name=name)) for name in configured],
            [client],
        )
    )
    monkeypatch.setattr(module, "load_mcp_tools_from_config", loader)

    assert module.main() == {None: 0, "direct": 2, "configured": 3}[missing_from]
    if missing_from == "direct":
        loader.assert_not_called()
    else:
        client.close.assert_called_once()
