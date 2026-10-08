"""Behavioral regression coverage for read-only Phase 1A review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from openjarvis.projects.review import (
    manifest_preview,
    registry_preview,
    validate_manifest,
)


def snapshot(tmp_path: Path, records: list[dict]) -> Path:
    source = tmp_path / "projects.json"
    source.write_text(json.dumps({"schema_version": 2, "projects": records}))
    return source


def project(index: int, *, role: str = "active") -> dict:
    return {
        "project_id": f"p{index}",
        "name": f"Project {index}",
        "path": f"D:\\Projects\\p{index}",
        "role": role,
        "git": {"remote": "https://user:secret@example.com/repo"},
    }


def test_review_batches_have_no_durable_identity_and_do_not_change_source(tmp_path):
    source = snapshot(tmp_path, [project(3), project(1), project(2, role="reference")])
    before = source.read_bytes()
    first = registry_preview(source, role="active", limit=1)
    second = registry_preview(
        source,
        role="active",
        offset=first["next_offset"],
        limit=1,
        expected_sha256=first["snapshot_sha256"],
    )
    assert [
        first["reviews"][0]["scanner_project_id"],
        second["reviews"][0]["scanner_project_id"],
    ] == ["p1", "p3"]
    assert second["next_offset"] is None
    assert first["confirmed_count"] == 0
    assert first["reviews"][0]["canonical_project_id"] is None
    assert "secret" not in json.dumps(first)
    assert registry_preview(source, role="active", limit=1) == first
    assert source.read_bytes() == before
    assert list(tmp_path.iterdir()) == [source]


def test_changed_snapshot_rejected(tmp_path):
    source = snapshot(tmp_path, [project(1)])
    old_hash = registry_preview(source)["snapshot_sha256"]
    source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(ValueError, match="snapshot changed"):
        registry_preview(source, expected_sha256=old_hash)


def test_windows_path_and_slug_collisions_flagged_without_merging(tmp_path):
    other = project(1)
    other["path"] = "d:/projects/P1"
    report = registry_preview(snapshot(tmp_path, [project(1), other]))
    assert report["total"] == 2
    assert report["duplicate_ids"] == ["p1"]
    assert report["duplicate_paths"] == ["d:\\projects\\p1"]
    assert all(p["identity_conflict"] for p in report["reviews"])
    assert len({p["review_id"] for p in report["reviews"]}) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"path": "relative/path"},
        {"path": "D:\\Projects\\..\\secrets"},
        {"role": "imaginary"},
        {"name": None},
    ],
)
def test_invalid_scanner_metadata_refused(tmp_path, change):
    with pytest.raises(ValueError):
        registry_preview(snapshot(tmp_path, [{**project(1), **change}]))


def test_future_scanner_version_not_migrated(tmp_path):
    source = tmp_path / "projects.json"
    source.write_text('{"schema_version":3,"projects":[]}')
    before = source.read_bytes()
    with pytest.raises(ValueError, match="schema_version 2"):
        registry_preview(source)
    assert source.read_bytes() == before


def test_optional_manifest_does_not_create_directory(tmp_path):
    report = manifest_preview(tmp_path, inferred={"tags": ["inferred"]})
    assert report["manifest_present"] is False
    assert report["effective"]["knowledge"]["privacy"] == "private-project"
    assert list(tmp_path.iterdir()) == []


def test_explicit_empty_overrides_and_safety_exclusions_survive(tmp_path):
    directory = tmp_path / ".openjarvis"
    directory.mkdir()
    manifest = directory / "project.toml"
    raw = (
        b'schema_version=1\ntags=[]\nrole="personal"\n[commands]\n'
        b'test=["dangerous", "--delete"]\n[knowledge]\n'
        b'include=["**/*"]\nexclude=[]\n'
    )
    manifest.write_bytes(raw)
    inferred = {"tags": ["inferred"], "knowledge": {"exclude": ["custom/**"]}}
    report = manifest_preview(tmp_path, inferred=inferred)
    assert report["effective"]["tags"] == []
    knowledge = report["effective"]["knowledge"]
    assert knowledge["exclude"] == []
    assert "**/wp-config.php" in knowledge["mandatory_exclusions"]
    assert report["commands_executed"] is False
    assert report["index_created"] is False
    assert report["manifest_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest.read_bytes() == raw
    assert inferred["tags"] == ["inferred"]


@pytest.mark.parametrize(
    "fields",
    [
        {"schema_version": True},
        {"schema_version": 2},
        {"migration_version": 1},
        {"unexpected": "value"},
        {"priority": True},
        {"priority": 6},
        {"tags": "not a list"},
        {"project_id": 3},
        {"project_id": "not-a-uuid"},
        {"role": "bogus"},
        {"production_url": "https://user:token@example.com"},
        {"production_url": "https://example.com?token=secret"},
        {"commands": {"test": "rm -rf"}},
        {"commands": {"test": []}},
        {"knowledge": {"privacy": "remote-private"}},
        {"knowledge": {"privacy": []}},
        {"knowledge": {"allow_secrets": True}},
        {"knowledge": {"include": ["../outside"]}},
        {"knowledge": {"include": ["D:\\outside"]}},
        {"knowledge": {"include": ["/outside"]}},
    ],
)
def test_invalid_manifest_refused(fields):
    with pytest.raises(ValueError):
        validate_manifest({"schema_version": 1, **fields})


def test_linked_manifest_directory_refused_before_read(tmp_path, monkeypatch):
    import stat
    from types import SimpleNamespace

    original = Path.lstat

    def linked(path, *args, **kwargs):
        if path.name == ".openjarvis":
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", linked)
    with pytest.raises(ValueError, match="links or junctions"):
        manifest_preview(tmp_path)


def test_large_manifest_refused_without_other_reads(tmp_path):
    directory = tmp_path / ".openjarvis"
    directory.mkdir()
    (directory / "project.toml").write_bytes(b"#" * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="64 KiB"):
        manifest_preview(tmp_path)
