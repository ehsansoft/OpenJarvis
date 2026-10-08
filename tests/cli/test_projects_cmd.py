"""CLI tests for the local project fabric."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from openjarvis.cli.projects_cmd import projects
from openjarvis.core.config import JarvisConfig


def test_scan_writes_registry(tmp_path: Path) -> None:
    root = tmp_path / "Projects"
    root.mkdir()
    repo = root / "sample"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='sample'\n",
        encoding="utf-8",
    )

    registry = tmp_path / "ai-control" / "projects.json"
    config = JarvisConfig()
    config.projects.root = str(root)
    config.projects.registry_path = str(registry)

    with mock.patch("openjarvis.cli.projects_cmd.load_config", return_value=config):
        result = CliRunner().invoke(projects, ["scan"])

    assert result.exit_code == 0
    assert "Discovered 1 project(s)" in result.output
    assert registry.exists()


def test_list_requires_existing_registry(tmp_path: Path) -> None:
    config = JarvisConfig()
    config.projects.registry_path = str(tmp_path / "missing.json")

    with mock.patch("openjarvis.cli.projects_cmd.load_config", return_value=config):
        result = CliRunner().invoke(projects, ["list"])

    assert result.exit_code != 0
    assert "Project registry not found" in result.output
