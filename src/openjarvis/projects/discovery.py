"""Local project discovery for the personal project fabric.

The scanner is metadata-first. It identifies project roots and reads only small
project metadata files; it does not ingest source code, secrets, generated
assets, model weights, uploads, or dependency directories.
"""

from __future__ import annotations

import configparser
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_DEFAULT_IGNORES = frozenset(
    {
        ".cache",
        ".git",
        ".idea",
        ".next",
        ".nuxt",
        ".pytest_cache",
        ".tox",
        ".venv",
        ".vscode",
        "__pycache__",
        "backup",
        "backups",
        "build",
        "cache",
        "caches",
        "coverage",
        "dist",
        "logs",
        "node_modules",
        "target",
        "temp",
        "tmp",
        "uploads",
        "vendor",
        "venv",
    }
)

_PROJECT_MARKERS = (
    ".git",
    "pyproject.toml",
    "package.json",
    "composer.json",
    "Cargo.toml",
    "go.mod",
    "wp-config.php",
)

_LANGUAGE_MARKERS = {
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "package.json": "JavaScript/TypeScript",
    "tsconfig.json": "TypeScript",
    "composer.json": "PHP",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
}

_HEADER_READ_LIMIT = 32 * 1024


@dataclass(slots=True)
class ProjectRecord:
    """A lightweight, serializable description of a local project."""

    project_id: str
    name: str
    path: str
    project_type: str
    languages: list[str]
    frameworks: list[str]
    markers: list[str]
    git: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def _slugify(value: str) -> str:
    value = value.replace("\\", "/").strip("/")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
    return slug or "project"


def _safe_text(path: Path, limit: int = _HEADER_READ_LIMIT) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def _wordpress_headers(path: Path) -> tuple[bool, bool]:
    plugin = False
    theme = False
    for php_file in sorted(path.glob("*.php"))[:20]:
        text = _safe_text(php_file)
        if re.search(r"(?im)^\s*Plugin Name\s*:", text):
            plugin = True
            break

    style = path / "style.css"
    if style.is_file():
        theme = bool(re.search(r"(?im)^\s*Theme Name\s*:", _safe_text(style)))
    return plugin, theme


def _markers(path: Path) -> list[str]:
    return [marker for marker in _PROJECT_MARKERS if (path / marker).exists()]


def _detect_type(path: Path, markers: list[str]) -> tuple[str, list[str]]:
    plugin, theme = _wordpress_headers(path)
    frameworks: list[str] = []

    if plugin:
        frameworks.append("WordPress")
        project_type = "wordpress-plugin"
    elif theme:
        frameworks.append("WordPress")
        project_type = "wordpress-theme"
    elif "wp-config.php" in markers:
        frameworks.append("WordPress")
        project_type = "wordpress-site"
    elif "pyproject.toml" in markers:
        project_type = "python"
    elif "package.json" in markers:
        project_type = "node"
    elif "composer.json" in markers:
        project_type = "php"
    elif "Cargo.toml" in markers:
        project_type = "rust"
    elif "go.mod" in markers:
        project_type = "go"
    elif ".git" in markers:
        project_type = "git"
    else:
        project_type = "generic"

    if (path / "woocommerce").exists() or "woocommerce" in path.name.lower():
        frameworks.append("WooCommerce")
    return project_type, sorted(set(frameworks))


def _detect_languages(path: Path, markers: list[str]) -> list[str]:
    languages = {
        language
        for marker, language in _LANGUAGE_MARKERS.items()
        if marker in markers or (path / marker).exists()
    }
    suffix_map = {
        ".php": "PHP",
        ".py": "Python",
        ".js": "JavaScript",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".rs": "Rust",
        ".go": "Go",
    }
    try:
        for child in list(path.iterdir())[:200]:
            if child.is_file():
                language = suffix_map.get(child.suffix.lower())
                if language:
                    languages.add(language)
    except OSError:
        pass
    return sorted(languages)


def _read_git_metadata(path: Path) -> dict[str, Any]:
    git_path = path / ".git"
    if not git_path.exists():
        return {"is_repo": False, "branch": "", "remote": ""}

    branch = ""
    remote = ""
    if git_path.is_dir():
        head = _safe_text(git_path / "HEAD", limit=4096).strip()
        prefix = "ref: refs/heads/"
        if head.startswith(prefix):
            branch = head[len(prefix) :]
        elif head:
            branch = head[:12]

        parser = configparser.ConfigParser()
        try:
            parser.read(git_path / "config", encoding="utf-8")
            if parser.has_section('remote "origin"'):
                remote = parser.get('remote "origin"', "url", fallback="")
        except (OSError, configparser.Error):
            pass

    return {"is_repo": True, "branch": branch, "remote": remote}


def _iter_directories(
    root: Path,
    *,
    max_depth: int,
    ignore_names: frozenset[str],
) -> Iterable[tuple[Path, int]]:
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        yield current, depth
        if depth >= max_depth:
            continue
        try:
            children = sorted(
                (child for child in current.iterdir() if child.is_dir()),
                key=lambda item: item.name.lower(),
                reverse=True,
            )
        except OSError:
            continue
        for child in children:
            name = child.name
            if name in ignore_names or name.startswith("."):
                continue
            stack.append((child, depth + 1))


def discover_projects(
    root: str | os.PathLike[str],
    *,
    max_depth: int = 4,
    ignore_names: Iterable[str] | None = None,
) -> list[ProjectRecord]:
    """Discover local project roots beneath *root*."""
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"Project root does not exist: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"Project root is not a directory: {base}")
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    ignores = frozenset(ignore_names or _DEFAULT_IGNORES)
    records: list[ProjectRecord] = []
    seen_paths: set[Path] = set()

    for path, _depth in _iter_directories(
        base, max_depth=max_depth, ignore_names=ignores
    ):
        if path == base:
            continue
        markers = _markers(path)
        if not markers:
            plugin, theme = _wordpress_headers(path)
            if not plugin and not theme:
                continue

        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)

        project_type, frameworks = _detect_type(path, markers)
        relative = path.relative_to(base).as_posix()
        records.append(
            ProjectRecord(
                project_id=_slugify(relative),
                name=path.name,
                path=str(resolved),
                project_type=project_type,
                languages=_detect_languages(path, markers),
                frameworks=frameworks,
                markers=sorted(markers),
                git=_read_git_metadata(path),
            )
        )

    records.sort(key=lambda item: item.path.lower())
    return records


def write_registry(
    records: Iterable[ProjectRecord],
    path: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
) -> Path:
    """Atomically persist discovered project records as JSON."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(Path(root).expanduser().resolve()) if root else "",
        "projects": [record.to_dict() for record in records],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def load_registry(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a previously-written project registry."""
    source = Path(path).expanduser()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        raise ValueError(f"Invalid project registry: {source}")
    return data


__all__ = ["ProjectRecord", "discover_projects", "load_registry", "write_registry"]
