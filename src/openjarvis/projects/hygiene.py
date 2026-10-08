"""Read-only disk hygiene scanners.

Cleanup scanning identifies rebuildable/stale directories without deleting them.
Duplicate scanning verifies exact duplicate files using a bounded two-stage hash.
No file is modified, moved, or removed by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from openjarvis.projects.inventory import _is_link_or_junction


_SYSTEM_SKIP_NAMES = frozenset(
    {
        "$RECYCLE.BIN",
        "System Volume Information",
        "Windows",
        "Program Files",
        "Program Files (x86)",
        "ProgramData",
        ".git",
        ".svn",
        ".hg",
    }
)

_LOW_RISK_CLEANUP_NAMES = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".parcel-cache",
        ".turbo",
        ".cache",
        "coverage",
        ".coverage",
    }
)

_REVIEW_CLEANUP_NAMES = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".venv",
        "venv",
        "vendor",
    }
)

_DUPLICATE_SKIP_NAMES = _SYSTEM_SKIP_NAMES | _LOW_RISK_CLEANUP_NAMES | frozenset(
    {
        "node_modules",
        "vendor",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
        ".next",
        ".nuxt",
    }
)


@dataclass(slots=True)
class CleanupCandidate:
    path: str
    kind: str
    risk: str
    files: int
    bytes: int
    modified_at: str
    truncated: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CleanupReport:
    schema_version: int
    generated_at: str
    root: str
    candidate_count: int
    estimated_bytes: int
    candidates: list[dict[str, Any]]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DuplicateGroup:
    sha256: str
    size: int
    files: list[str]
    reclaimable_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DuplicateReport:
    schema_version: int
    generated_at: str
    root: str
    files_considered: int
    bytes_hashed: int
    duplicate_groups: list[dict[str, Any]]
    duplicate_file_count: int
    reclaimable_bytes: int
    truncated: bool
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _directory_stats(
    root: Path,
    *,
    max_files: int,
) -> tuple[int, int, float, bool]:
    files = 0
    total_bytes = 0
    newest_mtime = 0.0
    truncated = False
    stack = [root]

    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue

        for entry in entries:
            if _is_link_or_junction(entry):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue

            files += 1
            total_bytes += stat.st_size
            newest_mtime = max(newest_mtime, stat.st_mtime)
            if files >= max_files:
                truncated = True
                stack.clear()
                break

    return files, total_bytes, newest_mtime, truncated


def scan_cleanup_candidates(
    root: str | os.PathLike[str],
    *,
    min_age_days: int = 30,
    max_candidates: int = 500,
    max_files_per_candidate: int = 250_000,
    skip_names: Iterable[str] | None = None,
) -> CleanupReport:
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"Cleanup root does not exist: {base}")

    skip = frozenset(skip_names or _SYSTEM_SKIP_NAMES)
    candidates: list[CleanupCandidate] = []
    errors: list[str] = []
    stack = [base]
    now = datetime.now(timezone.utc).timestamp()
    age_seconds = max(0, min_age_days) * 86400

    while stack and len(candidates) < max_candidates:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            if len(errors) < 100:
                errors.append(f"{current}: {type(exc).__name__}: {exc}")
            continue

        for entry in entries:
            if _is_link_or_junction(entry):
                continue
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue

            name = entry.name
            path = Path(entry.path)
            if name in skip:
                continue

            if name in _LOW_RISK_CLEANUP_NAMES or name in _REVIEW_CLEANUP_NAMES:
                files, size, newest, truncated = _directory_stats(
                    path,
                    max_files=max_files_per_candidate,
                )
                age = now - newest if newest else age_seconds
                if age < age_seconds:
                    continue

                risk = "low" if name in _LOW_RISK_CLEANUP_NAMES else "review"
                reason = (
                    "Generated cache/artifact; normally rebuildable."
                    if risk == "low"
                    else (
                        "Rebuildable in many projects, but removal can be "
                        "expensive or break an offline/dev workflow."
                    )
                )
                modified = (
                    datetime.fromtimestamp(newest, tz=timezone.utc).isoformat()
                    if newest
                    else ""
                )
                candidates.append(
                    CleanupCandidate(
                        path=str(path),
                        kind=name,
                        risk=risk,
                        files=files,
                        bytes=size,
                        modified_at=modified,
                        truncated=truncated,
                        reason=reason,
                    )
                )
                if len(candidates) >= max_candidates:
                    break
                # Candidate size walk already traversed descendants. Do not
                # descend again through the main discovery walk.
                continue

            stack.append(path)

    candidates.sort(key=lambda item: item.bytes, reverse=True)
    return CleanupReport(
        schema_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        root=str(base),
        candidate_count=len(candidates),
        estimated_bytes=sum(item.bytes for item in candidates),
        candidates=[item.to_dict() for item in candidates],
        errors=errors,
    )


def _sample_hash(path: Path, size: int, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        digest.update(handle.read(chunk_size))
        if size > chunk_size:
            handle.seek(max(0, size - chunk_size))
            digest.update(handle.read(chunk_size))
    return digest.hexdigest()


def _sha256(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def scan_duplicate_files(
    root: str | os.PathLike[str],
    *,
    min_size_bytes: int = 1 * 1024 * 1024,
    max_files: int = 750_000,
    max_groups: int = 500,
    skip_names: Iterable[str] | None = None,
) -> DuplicateReport:
    """Find exact duplicates without exposing file contents.

    Stage 1 groups files by size. Stage 2 hashes only size collisions using a
    first/last sample, then SHA-256 verifies surviving candidates.
    """
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"Duplicate-scan root does not exist: {base}")

    skip = frozenset(skip_names or _DUPLICATE_SKIP_NAMES)
    size_groups: dict[int, list[Path]] = defaultdict(list)
    files_considered = 0
    errors: list[str] = []
    truncated = False
    stack = [base]

    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            if len(errors) < 100:
                errors.append(f"{current}: {type(exc).__name__}: {exc}")
            continue

        for entry in entries:
            if _is_link_or_junction(entry):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in skip:
                        stack.append(Path(entry.path))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue

            if stat.st_size < min_size_bytes:
                continue
            files_considered += 1
            size_groups[stat.st_size].append(Path(entry.path))
            if files_considered >= max_files:
                truncated = True
                stack.clear()
                break

    sample_groups: dict[tuple[int, str], list[Path]] = defaultdict(list)
    bytes_hashed = 0

    for size, paths in size_groups.items():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                signature = _sample_hash(path, size)
                bytes_hashed += min(size, 2 * 1024 * 1024)
                sample_groups[(size, signature)].append(path)
            except OSError as exc:
                if len(errors) < 100:
                    errors.append(f"{path}: {type(exc).__name__}: {exc}")

    exact: dict[tuple[int, str], list[Path]] = defaultdict(list)
    for (size, _sample), paths in sample_groups.items():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                digest = _sha256(path)
                bytes_hashed += size
                exact[(size, digest)].append(path)
            except OSError as exc:
                if len(errors) < 100:
                    errors.append(f"{path}: {type(exc).__name__}: {exc}")

    groups: list[DuplicateGroup] = []
    for (size, digest), paths in exact.items():
        if len(paths) < 2:
            continue
        ordered = sorted(str(path) for path in paths)
        groups.append(
            DuplicateGroup(
                sha256=digest,
                size=size,
                files=ordered,
                reclaimable_bytes=size * (len(ordered) - 1),
            )
        )

    groups.sort(key=lambda item: item.reclaimable_bytes, reverse=True)
    groups = groups[:max_groups]

    return DuplicateReport(
        schema_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        root=str(base),
        files_considered=files_considered,
        bytes_hashed=bytes_hashed,
        duplicate_groups=[item.to_dict() for item in groups],
        duplicate_file_count=sum(max(0, len(item.files) - 1) for item in groups),
        reclaimable_bytes=sum(item.reclaimable_bytes for item in groups),
        truncated=truncated,
        errors=errors,
    )


def _write_report(report: Any, path: str | os.PathLike[str]) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(target)
    return target


def write_cleanup_report(
    report: CleanupReport,
    path: str | os.PathLike[str],
) -> Path:
    return _write_report(report, path)


def write_duplicate_report(
    report: DuplicateReport,
    path: str | os.PathLike[str],
) -> Path:
    return _write_report(report, path)


__all__ = [
    "CleanupCandidate",
    "CleanupReport",
    "DuplicateGroup",
    "DuplicateReport",
    "scan_cleanup_candidates",
    "scan_duplicate_files",
    "write_cleanup_report",
    "write_duplicate_report",
]
