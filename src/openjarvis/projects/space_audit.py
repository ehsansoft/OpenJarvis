"""Metadata-only space audit, including dependencies omitted by normal inventory."""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

_SKIP = {"$recycle.bin", "system volume information"}
_CACHE = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".parcel-cache",
    ".turbo",
}
_REBUILD = {
    "node_modules",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "target",
    ".venv",
    "venv",
    "vendor",
}
_REVIEW = {
    "cache",
    "caches",
    ".cache",
    "temp",
    "tmp",
    "cvi-temp",
    ".cvi-cache",
    ".bun-cache-cvi",
    ".pnpm-store",
    "dist",
    "build",
    "coverage",
    ".render-tmp",
    ".tmp-remotion-cache",
}
_PROTECTED = {
    ".git",
    "ollama-models",
    "hf-cache",
    "models",
    "huggingface",
    "artifacts",
    "generations",
    "captures",
}
_MARKERS = {".git", "package.json", "pyproject.toml", "composer.json", "Cargo.toml"}


def scan_space_audit(
    root: str | Path,
    *,
    max_files: int = 3_000_000,
    progress: Callable[[int, str], None] | None = None,
) -> dict:
    """Read names/stat only. Never follow reparse points or generate a delete plan."""
    requested = Path(root).expanduser().absolute()
    for part in (requested, *requested.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(
            info, "st_file_attributes", 0
        ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
            raise ValueError("Audit root must not traverse a link or reparse point")
    base = requested.resolve()
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    if max_files < 1:
        raise ValueError("max_files must be positive")
    now = datetime.now(timezone.utc)
    candidates, breakdown, large_files, errors, links = [], [], [], [], []
    count = 0
    truncated = False
    last_progress = time.monotonic()

    def error(path, kind):
        if len(errors) < 200:
            errors.append({"path": str(path), "error": kind})

    def walk(path, depth, project, protected, candidate_parent):
        nonlocal count, truncated, last_progress
        if depth > 512 or count >= max_files:
            truncated = True
            return 0, 0, 0.0, 0
        try:
            with os.scandir(path) as iterator:
                entries = list(iterator)
        except OSError as exc:
            error(path, type(exc).__name__)
            return 0, 0, 0.0, 0
        if not candidate_parent and _MARKERS.intersection(e.name for e in entries):
            project = str(path)
        name = path.name.lower()
        protected = (
            protected
            or name in _PROTECTED
            or (name == "studio-next" and path.parent.name.lower() == "out")
        )
        kind = (
            "cache"
            if name in _CACHE
            else "dependency"
            if name in _REBUILD
            else "review"
            if name in _REVIEW
            else None
        )
        is_candidate = kind is not None and not protected
        parent_candidate = candidate_parent
        if is_candidate and not candidate_parent:
            candidate_parent = str(path)
        size, files, newest, hardlinks = 0, 0, 0.0, 0
        for entry in entries:
            if count >= max_files:
                truncated = True
                break
            try:
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode) or getattr(
                    info, "st_file_attributes", 0
                ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                    if len(links) < 200:
                        links.append(entry.path)
                    continue
                if stat.S_ISDIR(info.st_mode):
                    if entry.name.lower() in _SKIP:
                        continue
                    child = walk(
                        Path(entry.path),
                        depth + 1,
                        project,
                        protected,
                        candidate_parent,
                    )
                    size += child[0]
                    files += child[1]
                    newest = max(newest, child[2])
                    hardlinks += child[3]
                elif stat.S_ISREG(info.st_mode):
                    count += 1
                    if progress and count % 1000 == 0:
                        current = time.monotonic()
                        if current - last_progress >= 5:
                            progress(count, str(path))
                            last_progress = current
                    files += 1
                    size += info.st_size
                    newest = max(newest, info.st_mtime)
                    hardlinks += int(info.st_nlink > 1)
                    if info.st_size >= 256 * 1024 * 1024:
                        large_files.append(
                            {
                                "path": entry.path,
                                "bytes": info.st_size,
                                "protected": protected,
                            }
                        )
            except OSError as exc:
                error(entry.path, type(exc).__name__)
        if depth == 1 or ("cvi" in str(path).lower() and depth <= 6):
            breakdown.append(
                {
                    "path": str(path),
                    "bytes": size,
                    "files": files,
                    "protected": protected,
                }
            )
        if is_candidate and files:
            age = (now.timestamp() - newest) / 86400 if newest else None
            candidates.append(
                {
                    "path": str(path),
                    "kind": kind,
                    "bytes": size,
                    "files": files,
                    "newest_file_at": datetime.fromtimestamp(
                        newest, timezone.utc
                    ).isoformat()
                    if newest
                    else None,
                    "age_days": round(age, 1) if age is not None else None,
                    "risk": "rebuildable-cache-review"
                    if kind == "cache"
                    else "manual-review",
                    "project_root": project,
                    "nested_under": parent_candidate,
                    "hardlinked_files": hardlinks,
                    "action": "REVIEW_ONLY",
                    "reason": (
                        "Check active processes, tracked files and reproducibility "
                        "before approval; folder name is not proof of disposability. "
                        "Parent candidates may contain protected model or media stores."
                    ),
                }
            )
        return size, files, newest, hardlinks

    size, files, _, hardlinks = walk(base, 0, None, False, None)
    if progress:
        progress(count, str(base))
    candidates.sort(key=lambda x: (-x["bytes"], x["path"]))
    breakdown.sort(key=lambda x: (-x["bytes"], x["path"]))
    large_files.sort(key=lambda x: -x["bytes"])
    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "root": str(base),
        "read_only": True,
        "logical_bytes": size,
        "files": files,
        "hardlinked_files": hardlinks,
        "truncated": truncated,
        "size_limitations": (
            "Logical sizes are not promised freed disk space: hardlinks, compression, "
            "sparse files, skipped links and access errors matter. Parent candidates "
            "may include protected descendants; all require individual review."
        ),
        "nonoverlapping_candidate_bytes": sum(
            c["bytes"] for c in candidates if not c["nested_under"]
        ),
        "candidates": candidates,
        "breakdown": breakdown,
        "large_files": large_files[:100],
        "errors": errors,
        "skipped_links_sample": links,
        "excluded_system_directories": sorted(_SKIP),
        "approval_required": True,
    }
