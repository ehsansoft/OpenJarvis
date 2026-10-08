"""Tests for safe whole-drive metadata inventory."""

from __future__ import annotations

from pathlib import Path

from openjarvis.projects.inventory import scan_drive_inventory, write_inventory


def test_inventory_finds_projects_without_reading_contents(tmp_path: Path) -> None:
    projects = tmp_path / "Projects"
    projects.mkdir()
    app = projects / "app"
    app.mkdir()
    (app / "package.json").write_text('{"name":"app"}', encoding="utf-8")
    (app / "index.ts").write_text("export const x = 1;", encoding="utf-8")

    outside = tmp_path / "old-copy"
    outside.mkdir()
    (outside / "pyproject.toml").write_text("[project]\nname='old'\n", encoding="utf-8")

    result = scan_drive_inventory(tmp_path, max_files=1000)

    assert result.files_seen == 3
    assert result.code_file_count == 1
    assert str(app) in result.project_roots
    assert str(outside) in result.project_roots
    assert any(
        item["kind"] == "project-consolidation" for item in result.recommendations
    )


def test_inventory_suppresses_cache_and_nested_project_false_positives(
    tmp_path: Path,
) -> None:
    cache = tmp_path / ".cvi-cache" / "one"
    cache.mkdir(parents=True)
    (cache / "package.json").write_text("{}", encoding="utf-8")

    root = tmp_path / "Projects" / "platform"
    child = root / "apps" / "admin"
    child.mkdir(parents=True)
    (root / "package.json").write_text("{}", encoding="utf-8")
    (child / "package.json").write_text("{}", encoding="utf-8")

    result = scan_drive_inventory(tmp_path, max_files=1000)

    assert str(cache) not in result.project_roots
    assert str(root) in result.project_roots
    assert str(child) not in result.project_roots


def test_inventory_marks_truncation(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"{index}.txt").write_text("x", encoding="utf-8")
    result = scan_drive_inventory(tmp_path, max_files=2)
    assert result.truncated is True
    assert result.files_seen == 2


def test_inventory_persists_json(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    result = scan_drive_inventory(tmp_path)
    target = tmp_path / "state" / "inventory.json"
    write_inventory(result, target)
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert '"schema_version": 1' in text
