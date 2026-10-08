"""Tests for read-only cleanup and duplicate scanners."""

from __future__ import annotations

import os
import time
from pathlib import Path

from openjarvis.projects.hygiene import (
    scan_cleanup_candidates,
    scan_duplicate_files,
)


def test_duplicate_scan_verifies_exact_content(tmp_path: Path) -> None:
    payload = b"x" * (1024 * 1024 + 64)
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    different = tmp_path / "different.bin"
    first.write_bytes(payload)
    second.write_bytes(payload)
    different.write_bytes(b"y" * len(payload))

    result = scan_duplicate_files(tmp_path, min_size_bytes=1024)

    assert len(result.duplicate_groups) == 1
    group = result.duplicate_groups[0]
    assert set(group["files"]) == {str(first), str(second)}
    assert group["reclaimable_bytes"] == len(payload)


def test_cleanup_report_keeps_largest_candidates(tmp_path: Path) -> None:
    old = time.time() - (45 * 86400)
    sizes = [1024, 4096, 2048]
    for index, size in enumerate(sizes):
        cache = tmp_path / f"project-{index}" / "__pycache__"
        cache.mkdir(parents=True)
        artifact = cache / "artifact.pyc"
        artifact.write_bytes(b"x" * size)
        os.utime(artifact, (old, old))

    result = scan_cleanup_candidates(
        tmp_path,
        min_age_days=30,
        max_candidates=2,
    )

    assert result.candidate_count == 3
    assert result.returned_candidate_count == 2
    assert result.truncated is True
    returned_sizes = [item["bytes"] for item in result.candidates]
    assert returned_sizes == [4096, 2048]
    assert result.estimated_bytes == sum(sizes)


def test_cleanup_scan_finds_stale_cache_without_deleting(tmp_path: Path) -> None:
    cache = tmp_path / "app" / "__pycache__"
    cache.mkdir(parents=True)
    artifact = cache / "module.pyc"
    artifact.write_bytes(b"x" * 2048)

    old = time.time() - (45 * 86400)
    os.utime(artifact, (old, old))

    result = scan_cleanup_candidates(tmp_path, min_age_days=30)

    assert result.candidate_count == 1
    candidate = result.candidates[0]
    assert candidate["risk"] == "low"
    assert candidate["kind"] == "__pycache__"
    assert artifact.exists()
