"""Space accounting and boundaries, with real filesystem metadata."""

import json
from unittest.mock import patch

import pytest

from openjarvis.projects.space_audit import scan_space_audit


def test_dependencies_measured_nested_caches_not_double_counted(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    cache = tmp_path / "node_modules" / ".cache"
    cache.mkdir(parents=True)
    (cache / "compiled").write_bytes(b"x" * 100)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    r = scan_space_audit(tmp_path)
    assert r["nonoverlapping_candidate_bytes"] == 100
    assert r["logical_bytes"] == 102
    assert len(r["candidates"]) == 2
    assert r["candidates"][0]["project_root"] == str(tmp_path)
    assert {
        str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    } == before
    json.dumps(r)


def test_models_and_canonical_media_are_not_cleanup_candidates(tmp_path):
    for relative in (
        "Ollama-Models/cache",
        "out/studio-next/build",
        ".git/cache",
        "artifacts/tmp",
    ):
        p = tmp_path / relative
        p.mkdir(parents=True)
        (p / "valuable").write_bytes(b"important")
    r = scan_space_audit(tmp_path)
    assert r["logical_bytes"] == 36
    assert r["candidates"] == []


def test_file_budget_marks_partial_accounting(tmp_path):
    for name in range(5):
        (tmp_path / str(name)).write_bytes(b"x")
    r = scan_space_audit(tmp_path, max_files=2)
    assert r["truncated"] is True
    assert r["files"] == 2


def test_links_and_windows_reparse_points_are_skipped(tmp_path):
    from types import SimpleNamespace

    entry = SimpleNamespace(
        path=str(tmp_path / "junction"),
        name="junction",
        stat=lambda **kw: SimpleNamespace(st_mode=0o040755, st_file_attributes=1024),
    )
    with patch("openjarvis.projects.space_audit.os.scandir") as scandir:
        scandir.return_value.__enter__.return_value = iter([entry])
        report = scan_space_audit(tmp_path)
    assert report["files"] == 0
    assert report["skipped_links_sample"] == [entry.path]
    assert scandir.call_count == 1


def test_root_link_is_rejected_before_traversal(tmp_path):
    import stat
    from types import SimpleNamespace

    with patch(
        "pathlib.Path.lstat", return_value=SimpleNamespace(st_mode=stat.S_IFLNK)
    ):
        with pytest.raises(ValueError, match="link or reparse"):
            scan_space_audit(tmp_path)
