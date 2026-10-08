"""Filesystem metadata inventory for large project drives.

This scanner never reads ordinary file contents. It walks names and stat
metadata, records project markers, and produces non-destructive organization
recommendations. It is discovery, not an autonomous file mover.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "composer.json",
    "Cargo.toml",
    "go.mod",
    "wp-config.php",
}

_DEFAULT_IGNORES = frozenset(
    {
        "$RECYCLE.BIN",
        "System Volume Information",
        ".git",
        ".svn",
        ".hg",
        ".venv",
        "venv",
        "node_modules",
        "vendor",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".next",
        ".nuxt",
        "dist",
        "build",
        "target",
        "cache",
        "caches",
        "tmp",
        "temp",
    }
)

_PROJECT_DETECTION_SUPPRESS_NAMES = frozenset(
    {
        ".cvi-cache",
        ".pnpm-store",
        ".bun-cache-cvi",
        "hf-cache",
        "caches",
        "node_modules",
        "vendor",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
    }
)

_CODE_EXTENSIONS = {
    ".php",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".vue",
    ".svelte",
}
_MODEL_EXTENSIONS = {".gguf", ".safetensors", ".onnx", ".pt", ".pth"}


@dataclass(slots=True)
class DriveInventory:
    schema_version: int
    generated_at: str
    root: str
    files_seen: int
    directories_seen: int
    bytes_seen: int
    truncated: bool
    extension_counts: dict[str, int]
    top_level: list[dict[str, Any]]
    project_roots: list[str]
    code_file_count: int
    model_file_count: int
    loose_root_files: list[str]
    errors: list[str]
    recommendations: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_link_or_junction(entry: os.DirEntry[str]) -> bool:
    """Avoid symlink/junction loops when walking a whole Windows drive."""
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True

    isjunction = getattr(os.path, "isjunction", None)
    if callable(isjunction):
        try:
            return bool(isjunction(entry.path))
        except OSError:
            return True
    return False


def scan_drive_inventory(
    root: str | os.PathLike[str],
    *,
    ignore_names: Iterable[str] | None = None,
    max_files: int = 2_000_000,
    max_errors: int = 200,
) -> DriveInventory:
    """Walk a drive/root using filesystem metadata only."""
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"Inventory root does not exist: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"Inventory root is not a directory: {base}")
    if max_files < 1:
        raise ValueError("max_files must be >= 1")

    ignores = frozenset(ignore_names or _DEFAULT_IGNORES)
    extensions: Counter[str] = Counter()
    top: dict[str, dict[str, Any]] = {}
    projects: set[str] = set()
    canonical_projects: list[Path] = []
    errors: list[str] = []
    loose: list[str] = []
    files_seen = directories_seen = bytes_seen = 0
    code_files = model_files = 0
    truncated = False
    stack: list[Path] = [base]

    while stack:
        current = stack.pop()
        directories_seen += 1
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            if len(errors) < max_errors:
                errors.append(f"{current}: {type(exc).__name__}: {exc}")
            continue

        names = {entry.name for entry in entries}
        relative_parts: tuple[str, ...] = ()
        try:
            relative_parts = current.relative_to(base).parts
        except ValueError:
            pass

        suppressed_for_projects = any(
            part.lower() in _PROJECT_DETECTION_SUPPRESS_NAMES for part in relative_parts
        )
        markers = _PROJECT_MARKERS.intersection(names)
        if current != base and markers and not suppressed_for_projects:
            nested = any(
                root == current or root in current.parents
                for root in canonical_projects
            )
            independent_nested = ".git" in markers or "wp-config.php" in markers
            if not nested or independent_nested:
                projects.add(str(current))
                canonical_projects.append(current)

        for entry in entries:
            if _is_link_or_junction(entry):
                continue
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                if entry.name not in ignores:
                    stack.append(Path(entry.path))
                continue
            if not is_file:
                continue

            files_seen += 1
            try:
                size = entry.stat(follow_symlinks=False).st_size
            except OSError:
                size = 0
            bytes_seen += size
            path = Path(entry.path)
            try:
                rel = path.relative_to(base)
            except ValueError:
                rel = None
            if rel and len(rel.parts) > 1:
                owner = rel.parts[0]
                summary = top.setdefault(
                    owner, {"path": str(base / owner), "files": 0, "bytes": 0}
                )
                summary["files"] += 1
                summary["bytes"] += size
            elif len(loose) < 500:
                loose.append(entry.name)

            suffix = path.suffix.lower()
            if suffix:
                extensions[suffix] += 1
            if suffix in _CODE_EXTENSIONS:
                code_files += 1
            if suffix in _MODEL_EXTENSIONS:
                model_files += 1
            if files_seen >= max_files:
                truncated = True
                stack.clear()
                break

    inventory = DriveInventory(
        schema_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        root=str(base),
        files_seen=files_seen,
        directories_seen=directories_seen,
        bytes_seen=bytes_seen,
        truncated=truncated,
        extension_counts=dict(extensions.most_common(100)),
        top_level=sorted(top.values(), key=lambda x: x["bytes"], reverse=True),
        project_roots=sorted(projects, key=str.lower),
        code_file_count=code_files,
        model_file_count=model_files,
        loose_root_files=sorted(loose, key=str.lower),
        errors=errors,
        recommendations=[],
    )
    inventory.recommendations = analyze_inventory(inventory)
    return inventory


def analyze_inventory(
    inventory: DriveInventory,
    *,
    preferred_projects_root: str = r"D:\Projects",
    preferred_ai_root: str = r"D:\AI-Control",
) -> list[dict[str, str]]:
    """Generate non-destructive reorganization recommendations."""
    recs: list[dict[str, str]] = []
    canonical = Path(preferred_projects_root)
    outside = []
    for raw in inventory.project_roots:
        try:
            Path(raw).relative_to(canonical)
        except ValueError:
            outside.append(raw)
    if outside:
        recs.append(
            {
                "priority": "high",
                "kind": "project-consolidation",
                "title": f"{len(outside)} project root(s) are outside {canonical}",
                "recommendation": (
                    "Review them before consolidating active development. Never move "
                    "automatically because paths, environments, IDEs and deployments "
                    "may depend on the current location."
                ),
            }
        )

    names: dict[str, list[str]] = defaultdict(list)
    for raw in inventory.project_roots:
        names[Path(raw).name.lower()].append(raw)
    duplicates = {k: v for k, v in names.items() if len(v) > 1}
    if duplicates:
        recs.append(
            {
                "priority": "high",
                "kind": "duplicate-project-names",
                "title": f"{len(duplicates)} repeated project name(s) need review",
                "recommendation": (
                    "Compare Git remotes, branches and timestamps before deleting or "
                    "archiving any copy."
                ),
            }
        )

    if inventory.model_file_count:
        recs.append(
            {
                "priority": "medium",
                "kind": "model-storage",
                "title": f"{inventory.model_file_count} model-weight file(s) observed",
                "recommendation": (
                    f"Prefer known model/cache roots under {preferred_ai_root} or the "
                    "configured Hugging Face/Ollama stores instead of project copies."
                ),
            }
        )
    if inventory.loose_root_files:
        recs.append(
            {
                "priority": "medium",
                "kind": "drive-root-clutter",
                "title": f"{len(inventory.loose_root_files)} loose root file(s)",
                "recommendation": (
                    "Review user-owned files for named workspace/archive folders. "
                    "Leave system and installer-managed files where they are."
                ),
            }
        )
    if inventory.truncated:
        recs.append(
            {
                "priority": "high",
                "kind": "scan-truncated",
                "title": "Inventory hit its file limit",
                "recommendation": (
                    "Increase max_files or split the drive into scan roots."
                ),
            }
        )
    if not recs:
        recs.append(
            {
                "priority": "low",
                "kind": "healthy-layout",
                "title": "No obvious layout problems detected",
                "recommendation": "Keep periodic scans and canonical project roots.",
            }
        )
    return recs


def write_inventory(inventory: DriveInventory, path: str | os.PathLike[str]) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(
        json.dumps(inventory.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(target)
    return target


__all__ = [
    "DriveInventory",
    "analyze_inventory",
    "scan_drive_inventory",
    "write_inventory",
]
