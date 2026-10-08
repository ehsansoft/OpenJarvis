"""Tests for the personal control-plane config migration helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import tomlkit


def _module():
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "install"
        / "Upgrade-Ehsan-Config.py"
    )
    spec = importlib.util.spec_from_file_location(
        "ehsan_config_upgrade",
        script,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_voicebox_security_and_privacy(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "config.toml"
    path.write_text(
        '[engine]\ndefault = "ollama"\n\n'
        '[engine.nararouter]\n'
        'host = "https://router.bynara.id"\n\n'
        '[intelligence]\n'
        'default_model = "qwen3:4b"\n'
        'model_code = "qwen3:4b"\n\n'
        '[tools]\n'
        'enabled = ["file_read"]\n\n'
        '[server]\nhost = "0.0.0.0"\n',
        encoding="utf-8",
    )

    changes = module.upgrade(path)
    data = tomlkit.parse(path.read_text(encoding="utf-8"))

    assert data["projects"]["voicebox_host"] == "http://127.0.0.1:17493"
    assert data["speech"]["backend"] == "auto"
    assert data["speech"]["compute_type"] == "int8"
    assert data["security"]["profile"] == "personal"
    assert data["analytics"]["enabled"] is False
    assert data["server"]["host"] == "127.0.0.1"
    assert data["engine"]["nararouter"]["free_only"] is True
    assert data["intelligence"]["default_model"] == ""
    assert data["intelligence"]["model_code"] == "free/code"

    servers = json.loads(data["tools"]["mcp"]["servers"])
    voicebox = next(item for item in servers if item["name"] == "voicebox")
    assert voicebox["url"] == "http://127.0.0.1:17493/mcp"
    assert (
        voicebox["headers"]["X-Voicebox-Client-Id"]
        == "openjarvis"
    )
    assert "voicebox_status" in data["tools"]["enabled"]
    assert changes


def test_upgrade_preserves_existing_mcp_servers(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "config.toml"
    existing = [
        {
            "name": "other",
            "url": "http://127.0.0.1:9000/mcp",
        }
    ]
    path.write_text(
        "[tools.mcp]\n"
        "enabled = true\n"
        f"servers = '{json.dumps(existing)}'\n",
        encoding="utf-8",
    )

    module.upgrade(path)
    data = tomlkit.parse(path.read_text(encoding="utf-8"))
    servers = json.loads(data["tools"]["mcp"]["servers"])

    assert any(item["name"] == "other" for item in servers)
    assert any(item["name"] == "voicebox" for item in servers)
