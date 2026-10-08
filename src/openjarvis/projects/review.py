"""Read-only project review and manifest previews; no adoption or execution."""

from __future__ import annotations

import hashlib
import json
import stat
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

PROJECT_ROLES = (
    "active",
    "client",
    "personal",
    "reference",
    "archive",
    "template",
    "generated",
    "experimental",
    "unknown",
)
# These exclusions cannot be replaced by a project's include/exclude choices.
# A future indexer must enforce resolved paths and content checks separately.
KNOWLEDGE_EXCLUSIONS = (
    ".env*",
    "**/.env*",
    "wp-config.php",
    "**/wp-config.php",
    "**/*.pem",
    "**/*.key",
    "**/credentials*",
    "**/secrets*",
    "**/node_modules/**",
    "**/vendor/**",
    "**/.git/**",
    "**/.venv/**",
    "**/venv/**",
    "**/__pycache__/**",
    "**/cache/**",
    "**/caches/**",
    "**/.cache/**",
    "**/dist/**",
    "**/build/**",
    "**/target/**",
    "**/uploads/**",
    "**/models/**",
    "**/*.gguf",
    "**/*.safetensors",
)
_LIST_FIELDS = {
    "aliases",
    "tags",
    "languages",
    "frameworks",
    "package_managers",
    "related_sites",
    "related_repositories",
}
_TEXT_FIELDS = {"name", "project_type", "local_url", "production_url", "staging_url"}
_FIELDS = (
    _LIST_FIELDS
    | _TEXT_FIELDS
    | {
        "schema_version",
        "migration_version",
        "project_id",
        "role",
        "priority",
        "runtime_requirements",
        "commands",
        "knowledge",
    }
)


def _path_key(value: str) -> str:
    path = (
        PureWindowsPath(value)
        if "\\" in value or PureWindowsPath(value).drive
        else PurePosixPath(value)
    )
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(
            "Project paths must be absolute and contain no parent traversal"
        )
    return str(path).casefold() if isinstance(path, PureWindowsPath) else str(path)


def registry_preview(
    source: Path,
    *,
    role: str | None = None,
    offset: int = 0,
    limit: int = 20,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Audit a single immutable input snapshot and return a bounded review batch."""
    if role is not None and role not in PROJECT_ROLES:
        raise ValueError("Unknown project role")
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("Offset must be nonnegative and limit must be 1..100")
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("Registry snapshot changed; regenerate the review batch")
    data = json.loads(raw)
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 2
    ):
        raise ValueError(
            "Expected scanner registry schema_version 2; no migration performed"
        )
    records = data.get("projects")
    if not isinstance(records, list):
        raise ValueError("Registry projects must be a list")
    ids: Counter[str] = Counter()
    paths: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    proposals = []
    for index, record in enumerate(records):
        if not isinstance(record, dict) or any(
            not isinstance(record.get(key), str) or not record[key].strip()
            for key in ("project_id", "name", "path")
        ):
            raise ValueError(f"Invalid project metadata at record {index}")
        key = _path_key(record["path"])
        proposed_role = record.get("role", "unknown")
        if proposed_role not in PROJECT_ROLES:
            raise ValueError(f"Unknown scanner role at record {index}")
        ids[record["project_id"]] += 1
        paths[key] += 1
        roles[proposed_role] += 1
        identity = json.dumps([digest, index, record["project_id"], key])
        proposals.append(
            {
                "review_id": hashlib.sha256(identity.encode()).hexdigest(),
                "scanner_project_id": record["project_id"],
                "canonical_project_id": None,
                "name": record["name"],
                "path": record["path"],
                "proposed_role": proposed_role,
                "status": "pending",
                "identity_conflict": False,
            }
        )
    for proposal in proposals:
        proposal["identity_conflict"] = (
            ids[proposal["scanner_project_id"]] > 1
            or paths[_path_key(proposal["path"])] > 1
        )
    # Sorting is independent of scanner enumeration, including duplicate ties.
    proposals.sort(
        key=lambda p: (_path_key(p["path"]), p["scanner_project_id"], p["review_id"])
    )
    selected = [p for p in proposals if role is None or p["proposed_role"] == role]
    return {
        "schema_version": 1,
        "mode": "read-only-preview",
        "scope": "scanner-proposals-only",
        "snapshot_sha256": digest,
        "scanner_schema_version": 2,
        "total": len(records),
        "role_counts": dict(sorted(roles.items())),
        "duplicate_ids": sorted(k for k, count in ids.items() if count > 1),
        "duplicate_paths": sorted(k for k, count in paths.items() if count > 1),
        "confirmed_count": 0,
        "matching_count": len(selected),
        "offset": offset,
        "limit": limit,
        "reviews": selected[offset : offset + limit],
        "next_offset": offset + limit if offset + limit < len(selected) else None,
    }


def _strings(value: Any, label: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")


def validate_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """Validate explicit manifest fields, preserving empty overrides."""
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported manifest schema_version; expected 1")
    if (
        type(data.get("migration_version", 0)) is not int
        or data.get("migration_version", 0) != 0
    ):
        raise ValueError("Unsupported manifest migration_version; expected 0")
    if data.keys() - _FIELDS:
        raise ValueError(
            "Unknown manifest fields: " + ", ".join(sorted(data.keys() - _FIELDS))
        )
    for field in _LIST_FIELDS & data.keys():
        _strings(data[field], field)
    for field in _TEXT_FIELDS & data.keys():
        if not isinstance(data[field], str) or not data[field].strip():
            raise ValueError(f"{field} must be a nonempty string")
        if field.endswith("_url"):
            url = urlsplit(data[field])
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError(
                    f"{field} requires an HTTP URL without credentials/query/fragment"
                )
    if "project_id" in data:
        if not isinstance(data["project_id"], str):
            raise ValueError("project_id must be a UUID string")
        try:
            UUID(data["project_id"])
        except ValueError as exc:
            raise ValueError("project_id must be a UUID string") from exc
    if "role" in data and data["role"] not in PROJECT_ROLES:
        raise ValueError("Unknown manifest role")
    if "priority" in data and (
        type(data["priority"]) is not int or not 0 <= data["priority"] <= 5
    ):
        raise ValueError("priority must be an integer 0..5")
    for field in ("commands", "runtime_requirements"):
        if field not in data:
            continue
        if not isinstance(data[field], dict):
            raise ValueError(f"{field} must be a table")
        for name, value in data[field].items():
            if not name.strip():
                raise ValueError(f"{field} names cannot be empty")
            if field == "commands":
                _strings(value, f"commands.{name}")
                if (
                    not value
                    or not value[0].strip()
                    or any("\x00" in arg for arg in value)
                ):
                    raise ValueError("Commands require an argv list without NULs")
            elif not isinstance(value, str):
                raise ValueError("Runtime version constraints must be strings")
    knowledge = data.get("knowledge", {})
    if not isinstance(knowledge, dict) or knowledge.keys() - {
        "privacy",
        "include",
        "exclude",
    }:
        raise ValueError("Unknown knowledge fields or invalid table")
    privacy = knowledge.get("privacy", "private-project")
    if not isinstance(privacy, str) or privacy not in {
        "public",
        "project-public",
        "private-project",
    }:
        raise ValueError("Unknown knowledge privacy")
    for field in ("include", "exclude"):
        if field not in knowledge:
            continue
        _strings(knowledge[field], f"knowledge.{field}")
        for pattern in knowledge[field]:
            normalized = pattern.replace("\\", "/")
            if (
                not normalized
                or PureWindowsPath(pattern).drive
                or normalized.startswith("/")
                or ".." in normalized.split("/")
            ):
                raise ValueError(
                    "Knowledge patterns must stay relative to the project root"
                )
    return data


def manifest_preview(
    root: Path, *, inferred: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Preview the fixed manifest, refusing links/junctions and large files."""
    root = root.absolute()
    source = root / ".openjarvis" / "project.toml"
    for component in reversed((source, *source.parents)):
        try:
            attrs = component.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(attrs.st_mode)
            or getattr(attrs, "st_file_attributes", 0)
            & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("Manifest path cannot traverse links or junctions")
    if not root.is_dir():
        raise ValueError("Project root must be an existing directory")
    raw = b""
    explicit: dict[str, Any] = {}
    if source.exists():
        if not stat.S_ISREG(source.lstat().st_mode):
            raise ValueError("Manifest must be a regular metadata file")
        with source.open("rb") as handle:
            raw = handle.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise ValueError("Manifest exceeds 64 KiB metadata limit")
        try:
            explicit = validate_manifest(tomllib.loads(raw.decode("utf-8")))
        except (UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ValueError("Manifest is not valid UTF-8 TOML") from exc
    effective = {**(inferred or {}), **explicit}
    effective["knowledge"] = {
        **(inferred or {}).get("knowledge", {}),
        **explicit.get("knowledge", {}),
    }
    effective["knowledge"].setdefault("privacy", "private-project")
    effective["knowledge"]["mandatory_exclusions"] = list(KNOWLEDGE_EXCLUSIONS)
    return {
        "schema_version": 1,
        "mode": "read-only-preview",
        "project_root": str(root),
        "manifest_present": source.exists(),
        "manifest_sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        "explicit_overrides": explicit,
        "effective": effective,
        "commands_executed": False,
        "index_created": False,
        "adoption_status": "requires-reviewed-plan",
    }
