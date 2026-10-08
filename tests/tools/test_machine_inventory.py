"""Tests for machine inventory context tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from openjarvis.core.config import JarvisConfig
from openjarvis.tools.machine_inventory import MachineInventoryTool


def test_machine_inventory_tool_reads_ollama_section(tmp_path: Path) -> None:
    path = tmp_path / "machine.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": "now",
                "hostname": "devbox",
                "platform": "Windows",
                "platform_release": "11",
                "tools": [],
                "ollama": {"model_count": 3, "models": [{"name": "qwen"}]},
                "wampserver": {"detected": True},
                "recommendations": [],
            }
        ),
        encoding="utf-8",
    )
    config = JarvisConfig()
    config.projects.machine_inventory_path = str(path)

    with mock.patch(
        "openjarvis.tools.machine_inventory.load_config",
        return_value=config,
    ):
        result = MachineInventoryTool().execute(section="ollama")

    assert result.success is True
    payload = json.loads(result.content)
    assert payload["model_count"] == 3
