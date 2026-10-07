"""Tests for the local project fabric discovery layer."""

from __future__ import annotations

import json
from pathlib import Path

from openjarvis.projects.discovery import (\n    discover_projects,\n    load_registry,\n    write_registry,\n)


def _make_git_repo(path: Path) -> None:
    git = path / ".git"
    git.mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "config").write_text(
        '[remote "origin"]\n    url = https://github.com/example/repo.git\n',
        encoding="utf-8",
    )


def test_discovers_mixed_projects_and_prunes_dependencies(tmp_path: Path) -> None:
    plugin = tmp_path / "livora-plugin"
    plugin.mkdir()
    _make_git_repo(plugin)
    (plugin / "livora.php").write_text(
        "<?php\n/*\nPlugin Name: Livora Example\n*/\n",
        encoding="utf-8",
    )

    node = tmp_path / "cvi"
    node.mkdir()
    (node / "package.json").write_text('{"name":"cvi"}', encoding="utf-8")
    (node / "tsconfig.json").write_text("{}", encoding="utf-8")

    ignored = node / "node_modules" / "fake-project"
    ignored.mkdir(parents=True)
    (ignored / "package.json").write_text("{}", encoding="utf-8")

    records = discover_projects(tmp_path, max_depth=4)
    by_name = {record.name: record for record in records}

    assert set(by_name) == {"cvi", "livora-plugin"}
    assert by_name["livora-plugin"].project_type == "wordpress-plugin"
    assert "WordPress" in by_name["livora-plugin"].frameworks
    assert by_name["livora-plugin"].git["branch"] == "main"
    assert by_name["livora-plugin"].git["remote"].endswith("repo.git")
    assert "TypeScript" in by_name["cvi"].languages


def test_registry_round_trip(tmp_path: Path) -> None:
    project = tmp_path / "python-tool"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\nname='python-tool'\n",
        encoding="utf-8",
    )

    records = discover_projects(tmp_path)
    registry_path = tmp_path / "state" / "projects.json"
    written = write_registry(records, registry_path, root=tmp_path)

    assert written == registry_path
    payload = load_registry(registry_path)
    assert payload["schema_version"] == 1
    assert payload["root"] == str(tmp_path.resolve())
    assert payload["projects"][0]["project_type"] == "python"

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    assert raw["projects"][0]["project_id"] == "python-tool"
