"""CLI tests for the local project fabric."""

from __future__ import annotations

import json
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
    assert "1 active, 0 reference, 0 archive" in result.output
    assert registry.exists()


def test_list_requires_existing_registry(tmp_path: Path) -> None:
    config = JarvisConfig()
    config.projects.registry_path = str(tmp_path / "missing.json")

    with mock.patch("openjarvis.cli.projects_cmd.load_config", return_value=config):
        result = CliRunner().invoke(projects, ["list"])

    assert result.exit_code != 0
    assert "Project registry not found" in result.output


def test_read_only_review_and_stale_hash(tmp_path: Path) -> None:
    registry = tmp_path / "projects.json"
    raw = b'{"schema_version":2,"projects":[]}'
    registry.write_bytes(raw)
    runner = CliRunner()
    result = runner.invoke(projects, ["review", "--registry", str(registry)])
    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["mode"] == "read-only-preview"
    assert report["total"] == 0
    registry.write_bytes(raw + b" ")
    result = runner.invoke(
        projects,
        [
            "review",
            "--registry",
            str(registry),
            "--expected-sha256",
            report["snapshot_sha256"],
        ],
    )
    assert result.exit_code != 0
    assert "snapshot changed" in result.output
    assert registry.read_bytes() == raw + b" "

    result = runner.invoke(projects, ["audit", "--registry", str(registry)])
    assert result.exit_code == 0
    audit = json.loads(result.output)
    assert audit["scope"] == "scanner-proposals-only"
    assert "reviews" not in audit
    assert registry.read_bytes() == raw + b" "


def test_manifest_cli_no_write_and_invalid_fields(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(projects, ["manifest-preview", str(tmp_path)])
    assert result.exit_code == 0
    assert json.loads(result.output)["commands_executed"] is False
    assert list(tmp_path.iterdir()) == []
    folder = tmp_path / ".openjarvis"
    folder.mkdir()
    manifest = folder / "project.toml"
    raw = 'schema_version=1\nunknown="secret"\n'
    manifest.write_text(raw)
    result = runner.invoke(projects, ["manifest-preview", str(tmp_path)])
    assert result.exit_code != 0
    assert "Unknown manifest fields: unknown" in result.output
    assert manifest.read_text() == raw
