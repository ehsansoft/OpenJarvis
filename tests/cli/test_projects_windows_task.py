"""Tests for the generated Windows project/inventory scan script."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from openjarvis.cli import projects_cmd


def test_scan_script_refreshes_projects_before_inventory(tmp_path: Path) -> None:
    state = tmp_path / "state"
    projects = tmp_path / "Projects"
    drive = tmp_path / "drive"
    output = state / "registry" / "drive-inventory.json"
    projects.mkdir()
    drive.mkdir()

    with (
        mock.patch.object(projects_cmd, "get_config_dir", return_value=state),
        mock.patch.object(projects_cmd.sys, "executable", r"C:\Python\python.exe"),
    ):
        script = projects_cmd._write_windows_scan_script(
            root=drive,
            projects_root=projects,
            output=output,
            max_files=12345,
        )

    text = script.read_text(encoding="utf-8")
    scan_pos = text.index("projects scan")
    inventory_pos = text.index("projects inventory")

    assert scan_pos < inventory_pos
    assert str(projects) in text
    assert str(drive) in text
    assert str(output) in text
    assert "--max-files 12345" in text
    assert "$LASTEXITCODE" in text
