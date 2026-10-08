"""Local machine/toolchain inventory for Windows development workstations.

This module is read-only. It detects executable locations and versions, local
Ollama models, and WampServer component installations. It never installs,
updates, removes, or reconfigures software.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(slots=True)
class ToolInstallation:
    name: str
    version: str = ""
    executable: str = ""
    locations: list[str] = field(default_factory=list)
    status: str = "available"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OllamaModelRecord:
    name: str
    size: int = 0
    digest: str = ""
    modified_at: str = ""
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WampComponent:
    kind: str
    path: str
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MachineInventory:
    schema_version: int
    generated_at: str
    hostname: str
    platform: str
    platform_release: str
    tools: list[dict[str, Any]]
    ollama: dict[str, Any]
    wampserver: dict[str, Any]
    recommendations: list[dict[str, str]]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TOOL_COMMANDS: dict[str, tuple[str, list[str]]] = {
    "git": ("git", ["--version"]),
    "node": ("node", ["--version"]),
    "npm": ("npm", ["--version"]),
    "npx": ("npx", ["--version"]),
    "pnpm": ("pnpm", ["--version"]),
    "yarn": ("yarn", ["--version"]),
    "corepack": ("corepack", ["--version"]),
    "bun": ("bun", ["--version"]),
    "deno": ("deno", ["--version"]),
    "python": ("python", ["--version"]),
    "py": ("py", ["--version"]),
    "pip": ("pip", ["--version"]),
    "uv": ("uv", ["--version"]),
    "php": ("php", ["--version"]),
    "composer": ("composer", ["--version"]),
    "mysql": ("mysql", ["--version"]),
    "mariadb": ("mariadb", ["--version"]),
    "docker": ("docker", ["--version"]),
    "wsl": ("wsl", ["--version"]),
    "ollama": ("ollama", ["--version"]),
    "winget": ("winget", ["--version"]),
    "choco": ("choco", ["--version"]),
    "scoop": ("scoop", ["--version"]),
}


def _run(
    executable: str,
    args: list[str],
    *,
    timeout: float = 8.0,
) -> str:
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            errors="replace",
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""

    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0].strip() if output else ""


def _where_all(executable: str) -> list[str]:
    paths: list[str] = []
    primary = shutil.which(executable)
    if primary:
        paths.append(str(Path(primary).resolve()))

    if os.name == "nt":
        try:
            result = subprocess.run(
                ["where.exe", executable],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                errors="replace",
            )
            if result.returncode == 0:
                for raw in result.stdout.splitlines():
                    raw = raw.strip()
                    if raw:
                        try:
                            path = str(Path(raw).resolve())
                        except OSError:
                            path = raw
                        if path not in paths:
                            paths.append(path)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            pass
    return paths


def detect_toolchain() -> list[ToolInstallation]:
    found: list[ToolInstallation] = []
    for name, (executable, args) in _TOOL_COMMANDS.items():
        locations = _where_all(executable)
        if not locations:
            continue
        version = _run(locations[0], args)
        found.append(
            ToolInstallation(
                name=name,
                version=version,
                executable=locations[0],
                locations=locations,
            )
        )
    return found


def _normalize_ollama_host(host: str) -> str:
    value = (host or "").strip() or "http://127.0.0.1:11434"
    return value.rstrip("/")


def detect_ollama(
    host: str = "",
    *,
    timeout: float = 4.0,
) -> dict[str, Any]:
    base = _normalize_ollama_host(host)
    result: dict[str, Any] = {
        "host": base,
        "reachable": False,
        "version": "",
        "models": [],
        "model_count": 0,
        "total_model_bytes": 0,
        "shared_digest_groups": [],
        "storage_roots": [],
    }

    storage_roots: list[str] = []
    configured = os.environ.get("OLLAMA_MODELS", "").strip()
    if configured:
        storage_roots.append(configured)
    if os.name == "nt":
        user_profile = os.environ.get("USERPROFILE", "").strip()
        if user_profile:
            default_root = str(Path(user_profile) / ".ollama" / "models")
            if default_root not in storage_roots:
                storage_roots.append(default_root)
    result["storage_roots"] = storage_roots

    try:
        request = Request(f"{base}/api/tags", headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        return result

    models = payload.get("models", [])
    records: list[OllamaModelRecord] = []
    digests: dict[str, list[str]] = {}

    for item in models if isinstance(models, list) else []:
        if not isinstance(item, dict):
            continue
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        record = OllamaModelRecord(
            name=str(item.get("name") or item.get("model") or ""),
            size=int(item.get("size") or 0),
            digest=str(item.get("digest") or ""),
            modified_at=str(item.get("modified_at") or ""),
            family=str(details.get("family") or ""),
            parameter_size=str(details.get("parameter_size") or ""),
            quantization_level=str(details.get("quantization_level") or ""),
        )
        records.append(record)
        if record.digest:
            digests.setdefault(record.digest, []).append(record.name)

    result["reachable"] = True
    result["models"] = [record.to_dict() for record in records]
    result["model_count"] = len(records)
    result["total_model_bytes"] = sum(record.size for record in records)
    result["shared_digest_groups"] = [
        {"digest": digest, "models": names}
        for digest, names in digests.items()
        if len(names) > 1
    ]

    version_locations = _where_all("ollama")
    if version_locations:
        result["version"] = _run(version_locations[0], ["--version"])
    return result


def _candidate_wamp_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("WAMP_HOME", "WAMPSERVER_HOME", "WAMP64_HOME"):
        value = os.environ.get(key, "").strip()
        if value:
            roots.append(Path(value))

    if os.name == "nt":
        for value in (
            r"C:\wamp64",
            r"C:\wamp",
            r"D:\wamp64",
            r"D:\wamp",
        ):
            roots.append(Path(value))

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _component_version(path: Path, args: list[str]) -> str:
    return _run(str(path), args)


def detect_wampserver() -> dict[str, Any]:
    roots = [root for root in _candidate_wamp_roots() if root.exists()]
    components: list[WampComponent] = []

    patterns: tuple[tuple[str, str, list[str]], ...] = (
        ("php", "bin/php/php*/php.exe", ["--version"]),
        ("apache", "bin/apache/apache*/bin/httpd.exe", ["-v"]),
        ("mysql", "bin/mysql/mysql*/bin/mysql.exe", ["--version"]),
        ("mysql-server", "bin/mysql/mysql*/bin/mysqld.exe", ["--version"]),
        ("mariadb", "bin/mariadb/mariadb*/bin/mariadb.exe", ["--version"]),
        ("mariadb-server", "bin/mariadb/mariadb*/bin/mariadbd.exe", ["--version"]),
    )

    for root in roots:
        for kind, pattern, args in patterns:
            for path in sorted(root.glob(pattern)):
                components.append(
                    WampComponent(
                        kind=kind,
                        path=str(path),
                        version=_component_version(path, args),
                    )
                )

    return {
        "detected": bool(roots),
        "roots": [str(root) for root in roots],
        "components": [item.to_dict() for item in components],
    }


def analyze_machine_inventory(
    tools: list[ToolInstallation],
    ollama: dict[str, Any],
    wamp: dict[str, Any],
) -> list[dict[str, str]]:
    recommendations: list[dict[str, str]] = []
    by_name = {item.name: item for item in tools}

    for name in ("node", "npm", "pnpm"):
        item = by_name.get(name)
        if item and len(item.locations) > 1:
            recommendations.append(
                {
                    "priority": "medium",
                    "kind": "multiple-tool-installations",
                    "title": f"{name} resolves from {len(item.locations)} locations",
                    "recommendation": (
                        "Review PATH ordering and keep one intentional toolchain "
                        "manager/source to reduce version drift."
                    ),
                }
            )

    if "node" in by_name and "corepack" not in by_name and "pnpm" in by_name:
        recommendations.append(
            {
                "priority": "low",
                "kind": "node-package-manager",
                "title": "pnpm is installed but Corepack was not detected",
                "recommendation": (
                    "Consider standardizing package-manager versions per project "
                    "using packageManager metadata or a single version manager."
                ),
            }
        )

    if ollama.get("reachable") and ollama.get("shared_digest_groups"):
        recommendations.append(
            {
                "priority": "low",
                "kind": "ollama-aliases",
                "title": "Multiple Ollama tags share one model digest",
                "recommendation": (
                    "These are usually aliases backed by the same blob, so do "
                    "not count them as duplicate disk usage without inspecting "
                    "the Ollama model store."
                ),
            }
        )

    if wamp.get("detected"):
        kinds: dict[str, int] = {}
        for item in wamp.get("components", []):
            kind = str(item.get("kind", ""))
            kinds[kind] = kinds.get(kind, 0) + 1
        multi = [kind for kind, count in kinds.items() if count > 1]
        if multi:
            recommendations.append(
                {
                    "priority": "medium",
                    "kind": "wamp-multiple-runtimes",
                    "title": "WampServer contains multiple runtime versions",
                    "recommendation": (
                        "Keep versions required by active sites, but map each "
                        "project to its PHP/database runtime before removing old "
                        "WampServer components."
                    ),
                }
            )

    return recommendations


def scan_machine_inventory(host: str = "") -> MachineInventory:
    tools = detect_toolchain()
    ollama = detect_ollama(host)
    wamp = detect_wampserver()
    return MachineInventory(
        schema_version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hostname=socket.gethostname(),
        platform=platform.system(),
        platform_release=platform.release(),
        tools=[item.to_dict() for item in tools],
        ollama=ollama,
        wampserver=wamp,
        recommendations=analyze_machine_inventory(tools, ollama, wamp),
        errors=[],
    )


def write_machine_inventory(
    inventory: MachineInventory,
    path: str | os.PathLike[str],
) -> Path:
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
    "MachineInventory",
    "OllamaModelRecord",
    "ToolInstallation",
    "WampComponent",
    "analyze_machine_inventory",
    "detect_ollama",
    "detect_toolchain",
    "detect_wampserver",
    "scan_machine_inventory",
    "write_machine_inventory",
]
