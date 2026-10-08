"""Tests for the read-only drive inventory advisor tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from openjarvis.core.config import JarvisConfig
from openjarvis.projects.inventory import scan_drive_inventory, write_inventory
from openjarvis.tools.drive_inventory import DriveInventoryTool


def test_drive_inventory_returns_recommendations(tmp_path: Path) -> None:
    project = tmp_path / "old-project"
    project.mkdir()
    (project / "package.json").write_text('{"name":"old"}', encoding="utf-8")
    inventory = scan_drive_inventory(tmp_path)
    path = tmp_path / "inventory.json"
    write_inventory(inventory, path)

    config = JarvisConfig()
    config.projects.inventory_path = str(path)
    with mock.patch(
        "openjarvis.tools.drive_inventory.load_config",
        return_value=config,
    ):
        result = DriveInventoryTool().execute(section="recommendations")

    assert result.success is True
    payload = json.loads(result.content)
    assert payload
    assert "priority" in payload[0]


def test_drive_inventory_missing_file_is_actionable(tmp_path: Path) -> None:
    config = JarvisConfig()
    config.projects.inventory_path = str(tmp_path / "missing.json")
    with mock.patch(
        "openjarvis.tools.drive_inventory.load_config",
        return_value=config,
    ):
        result = DriveInventoryTool().execute()

    assert result.success is False
    assert "jarvis projects inventory" in result.content
