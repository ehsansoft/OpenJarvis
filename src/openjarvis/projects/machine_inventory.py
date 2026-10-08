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
    voicebox: dict[str, Any]
    wampserver: dict[str, Any]
    runtime_managers: dict[str, Any]
    package_caches: list[dict[str, Any]]
    hardware: dict[str, Any]
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
    "nvm": ("nvm", ["version"]),
    "fnm": ("fnm", ["--version"]),
    "volta": ("volta", ["--version"]),
}


def _run_full(
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
    output = (result.stdout or result.stderr or "").replace("\x00", "")
    return output.strip()


def _run(
    executable: str,
    args: list[str],
    *,
    timeout: float = 8.0,
) -> str:
    output = _run_full(executable, args, timeout=timeout)
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


def _powershell_json(script: str, *, timeout: float = 10.0) -> Any:
    if os.name != "nt":
        return None
    output = _run_full(
        "powershell.exe",
        ["-NoProfile", "-Command", script],
        timeout=timeout,
    )
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def detect_hardware() -> dict[str, Any]:
    """Detect CPU, memory, GPUs and fixed-drive capacity without mutation."""
    result: dict[str, Any] = {
        "cpu": [],
        "memory": {},
        "gpus": [],
        "disks": [],
    }
    if os.name != "nt":
        return result

    cpu = _powershell_json(
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,"
        "MaxClockSpeed | ConvertTo-Json -Compress"
    )
    result["cpu"] = _as_list(cpu)

    memory = _powershell_json(
        "Get-CimInstance Win32_ComputerSystem | "
        "Select-Object Manufacturer,Model,TotalPhysicalMemory | "
        "ConvertTo-Json -Compress"
    )
    if isinstance(memory, dict):
        result["memory"] = memory

    gpus = _powershell_json(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,VideoProcessor | "
        "ConvertTo-Json -Compress"
    )
    result["gpus"] = _as_list(gpus)

    nvidia = _where_all("nvidia-smi")
    if nvidia:
        output = _run_full(
            nvidia[0],
            [
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            timeout=8,
        )
        parsed: list[dict[str, Any]] = []
        for line in output.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 3:
                parsed.append(
                    {
                        "name": parts[0],
                        "memory_total_mb": parts[1],
                        "driver_version": parts[2],
                        "source": "nvidia-smi",
                    }
                )
        if parsed:
            result["nvidia"] = parsed

    disks = _powershell_json(
        "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
        "Select-Object DeviceID,VolumeName,FileSystem,Size,FreeSpace | "
        "ConvertTo-Json -Compress"
    )
    result["disks"] = _as_list(disks)
    return result


def _detect_port_listeners(port: int) -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    script = (
        f"Get-NetTCPConnection -LocalPort {port} -State Listen "
        "| Select-Object LocalAddress,LocalPort,OwningProcess "
        "| ConvertTo-Json -Compress"
    )
    return [
        item
        for item in _as_list(_powershell_json(script, timeout=5))
        if isinstance(item, dict)
    ]


def detect_runtime_managers() -> dict[str, Any]:
    managers: dict[str, Any] = {}
    commands = {
        "nvm": ["list"],
        "fnm": ["list"],
        "volta": ["list", "node"],
    }
    for name, args in commands.items():
        locations = _where_all(name)
        if not locations:
            continue
        output = _run_full(locations[0], args)
        managers[name] = {
            "executable": locations[0],
            "installed": [
                line.strip()
                for line in output.splitlines()
                if line.strip()
            ][:100],
        }
    return managers


def detect_package_caches() -> list[dict[str, Any]]:
    probes = (
        ("npm", ["config", "get", "cache"]),
        ("pnpm", ["store", "path"]),
        ("yarn", ["cache", "dir"]),
        ("pip", ["cache", "dir"]),
        ("uv", ["cache", "dir"]),
        ("composer", ["config", "--global", "cache-dir"]),
    )
    caches: list[dict[str, Any]] = []
    seen: set[str] = set()

    for name, args in probes:
        locations = _where_all(name)
        if not locations:
            continue
        raw = _run_full(locations[0], args)
        if not raw:
            continue
        first = raw.splitlines()[0].strip().strip('"')
        if (
            not first
            or first.lower().startswith("in ")
            or "error" in first.lower()
            or ":" in first and not Path(first).drive
        ):
            continue
        path = Path(first).expanduser()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        caches.append(
            {
                "manager": name,
                "path": str(path),
                "exists": path.exists(),
            }
        )
    return caches


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


def _normalize_voicebox_host(host: str) -> str:
    value = (
        host
        or os.environ.get("VOICEBOX_HOST", "")
        or "http://127.0.0.1:17493"
    ).strip()
    return value.rstrip("/")


def _http_json(url: str, *, timeout: float = 4.0) -> Any:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _voicebox_storage_roots() -> list[dict[str, Any]]:
    candidates: list[tuple[str, str]] = []

    for key in (
        "VOICEBOX_MODELS_DIR",
        "HUGGINGFACE_HUB_CACHE",
        "HF_HUB_CACHE",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            candidates.append((key, value))

    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        candidates.append(("HF_HOME", str(Path(hf_home) / "hub")))

    if os.name == "nt":
        user_profile = os.environ.get("USERPROFILE", "").strip()
        if user_profile:
            candidates.append(
                (
                    "huggingface-default",
                    str(Path(user_profile) / ".cache" / "huggingface" / "hub"),
                )
            )
        # This control-plane location is also the path used by the user's
        # Voicebox installation when configured to share AI-Control storage.
        candidates.append(
            (
                "ai-control",
                r"D:\AI-Control\caches\huggingface\hub",
            )
        )

    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for source, raw in candidates:
        path = Path(raw).expanduser()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "source": source,
                "path": str(path),
                "exists": path.exists(),
            }
        )
    return results


def _voicebox_engine_and_category(
    model_name: str,
    hf_repo_id: str,
    engine: str,
) -> tuple[str, str]:
    if engine:
        normalized = engine.lower()
    else:
        lowered = f"{model_name} {hf_repo_id}".lower()
        if "whisper" in lowered:
            normalized = "whisper"
        elif "qwen3-" in lowered and "tts" not in lowered:
            normalized = "qwen_llm"
        elif "customvoice" in lowered or "custom-voice" in lowered:
            normalized = "qwen_custom_voice"
        elif "qwen" in lowered and "tts" in lowered:
            normalized = "qwen"
        elif "kokoro" in lowered:
            normalized = "kokoro"
        elif "tada" in lowered:
            normalized = "tada"
        elif "chatterbox-turbo" in lowered:
            normalized = "chatterbox_turbo"
        elif "chatterbox" in lowered:
            normalized = "chatterbox"
        elif "luxtts" in lowered:
            normalized = "luxtts"
        else:
            normalized = ""

    if normalized == "whisper":
        category = "stt"
    elif normalized == "qwen_llm":
        category = "llm"
    elif normalized:
        category = "tts"
    else:
        category = "unknown"
    return normalized, category


def _hf_repo_cache_names(model_name: str, repo_id: str) -> list[str]:
    names: list[str] = []
    if repo_id and "/" in repo_id:
        org, repo = repo_id.split("/", 1)
        names.append(f"models--{org}--{repo}")

    lowered = model_name.lower()
    if lowered.startswith("whisper-"):
        size = lowered.removeprefix("whisper-")
        names.append(f"models--Systran--faster-whisper-{size}")
    return names


def _voicebox_cached(
    model_name: str,
    repo_id: str,
    roots: list[dict[str, Any]],
) -> bool:
    candidates = _hf_repo_cache_names(model_name, repo_id)
    if not candidates:
        return False
    for root in roots:
        if not root.get("exists"):
            continue
        base = Path(str(root.get("path", "")))
        for candidate in candidates:
            if (base / candidate).is_dir():
                return True
    return False


def detect_voicebox(
    host: str = "",
    *,
    timeout: float = 4.0,
) -> dict[str, Any]:
    """Detect a local Voicebox API and its registered model inventory."""
    base = _normalize_voicebox_host(host)
    result: dict[str, Any] = {
        "host": base,
        "reachable": False,
        "health": {},
        "models": [],
        "model_count": 0,
        "downloaded_count": 0,
        "loaded_count": 0,
        "available_count": 0,
        "downloaded_models": [],
        "loaded_models": [],
        "available_models": [],
        "state_inconsistencies": [],
        "profiles": [],
        "profile_count": 0,
        "storage_roots": _voicebox_storage_roots(),
        "listeners": _detect_port_listeners(17493),
        "exposed_all_interfaces": False,
        "openapi_url": f"{base}/openapi.json",
        "docs_url": f"{base}/docs",
        "error": "",
    }

    try:
        health = _http_json(f"{base}/health", timeout=timeout)
        if isinstance(health, dict):
            result["health"] = health
        result["reachable"] = True
    except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        # Some builds may have the models route alive even if /health differs.
        result["error"] = f"{type(exc).__name__}: {exc}"

    try:
        payload = _http_json(f"{base}/models/status", timeout=timeout)
    except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        if result["reachable"]:
            result["error"] = f"models/status: {type(exc).__name__}: {exc}"
        return result

    result["reachable"] = True
    result["error"] = ""
    raw_models = payload.get("models", []) if isinstance(payload, dict) else []
    models: list[dict[str, Any]] = []
    for item in raw_models if isinstance(raw_models, list) else []:
        if not isinstance(item, dict):
            continue
        model_name = str(item.get("model_name") or "")
        repo_id = str(item.get("hf_repo_id") or "")
        engine, category = _voicebox_engine_and_category(
            model_name,
            repo_id,
            str(item.get("engine") or ""),
        )
        cached = _voicebox_cached(
            model_name,
            repo_id,
            result["storage_roots"],
        )
        downloaded = bool(item.get("downloaded", False))
        loaded = bool(item.get("loaded", False))
        record = {
            "model_name": model_name,
            "display_name": str(item.get("display_name") or ""),
            "engine": engine,
            "category": category,
            "downloaded": downloaded,
            "loaded": loaded,
            "cached": cached,
            "available": downloaded or loaded or cached,
            "size_mb": item.get("size_mb", 0) or 0,
            "model_size": str(item.get("model_size") or ""),
            "hf_repo_id": repo_id,
        }
        # Preserve extra public status fields without assuming a fixed schema.
        for key in (
            "languages",
            "backend",
            "device",
            "status",
            "category",
            "type",
        ):
            if key in item:
                record[key] = item[key]
        models.append(record)

    downloaded = [
        item for item in models if bool(item.get("downloaded"))
    ]
    loaded = [item for item in models if bool(item.get("loaded"))]
    available = [
        item for item in models if bool(item.get("available"))
    ]
    inconsistencies = [
        {
            "model_name": item["model_name"],
            "downloaded": item["downloaded"],
            "loaded": item["loaded"],
            "cached": item["cached"],
        }
        for item in models
        if item["loaded"] and not item["downloaded"]
    ]
    listeners = result.get("listeners", [])
    result["exposed_all_interfaces"] = any(
        str(item.get("LocalAddress", "")) in {"0.0.0.0", "::"}
        for item in listeners
    )
    result["models"] = models
    result["model_count"] = len(models)
    result["downloaded_count"] = len(downloaded)
    result["loaded_count"] = len(loaded)
    result["available_count"] = len(available)
    result["downloaded_models"] = [
        item["model_name"] for item in downloaded if item["model_name"]
    ]
    result["loaded_models"] = [
        item["model_name"] for item in loaded if item["model_name"]
    ]
    result["available_models"] = [
        item["model_name"] for item in available if item["model_name"]
    ]
    result["state_inconsistencies"] = inconsistencies

    try:
        profiles_payload = _http_json(
            f"{base}/profiles",
            timeout=timeout,
        )
        if isinstance(profiles_payload, list):
            result["profiles"] = [
                item for item in profiles_payload if isinstance(item, dict)
            ][:500]
            result["profile_count"] = len(result["profiles"])
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        # Profiles are optional for model discovery and older builds can
        # expose a different profile surface. Keep the model scan healthy.
        pass

    return result


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


def _read_small_text(path: Path, limit: int = 512 * 1024) -> str:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def _wamp_active_versions(root: Path) -> dict[str, str]:
    active: dict[str, str] = {}
    keys = {
        "phpVersion": "php",
        "apacheVersion": "apache",
        "mysqlVersion": "mysql",
        "mariadbVersion": "mariadb",
    }
    for name in ("wampmanager.conf", "wampmanager.ini"):
        path = root / name
        if not path.is_file():
            continue
        text = _read_small_text(path)
        for raw_key, normalized in keys.items():
            match = __import__("re").search(
                rf"(?im)^\s*{raw_key}\s*=\s*[\"']?([^\"'\r\n;]+)",
                text,
            )
            if match:
                active[normalized] = match.group(1).strip()
    return active


def _wamp_virtual_hosts(root: Path) -> list[dict[str, Any]]:
    import re

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(
        root.glob("bin/apache/apache*/conf/extra/httpd-vhosts.conf")
    ):
        text = _read_small_text(path, limit=2 * 1024 * 1024)
        for block in re.findall(
            r"(?is)<VirtualHost\b[^>]*>(.*?)</VirtualHost>",
            text,
        ):
            name_match = re.search(r"(?im)^\s*ServerName\s+([^\s#]+)", block)
            root_match = re.search(
                r'(?im)^\s*DocumentRoot\s+["\']?([^"\'\r\n#]+)',
                block,
            )
            aliases = re.findall(
                r"(?im)^\s*ServerAlias\s+([^#\r\n]+)",
                block,
            )
            server_name = name_match.group(1).strip() if name_match else ""
            document_root = (
                root_match.group(1).strip().rstrip('"')
                if root_match
                else ""
            )
            if not server_name and not document_root:
                continue
            key = (server_name.lower(), document_root.lower())
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "server_name": server_name,
                    "document_root": document_root,
                    "aliases": [
                        item
                        for line in aliases
                        for item in line.split()
                        if item
                    ],
                    "config": str(path),
                }
            )
            if len(results) >= 200:
                return results
    return results


def _windows_hosts_entries() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    hosts = Path(system_root) / "System32" / "drivers" / "etc" / "hosts"
    text = _read_small_text(hosts, limit=256 * 1024)
    entries: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        entries.append({"address": parts[0], "names": parts[1:]})
    return entries[:500]


def _service_state(service_name: str) -> str:
    if os.name != "nt":
        return ""
    output = _run_full("sc.exe", ["query", service_name], timeout=5)
    for line in output.splitlines():
        if "STATE" in line and ":" in line:
            return line.split(":", 1)[1].strip()
    return ""


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _wamp_wordpress_sites(root: Path, vhosts: list[dict[str, Any]]) -> list[str]:
    sites: set[str] = set()
    www = root / "www"
    if www.is_dir():
        try:
            children = list(www.iterdir())
        except OSError:
            children = []
        for child in children[:1000]:
            if child.is_dir() and (child / "wp-config.php").is_file():
                sites.add(str(child))

    for item in vhosts:
        raw = str(item.get("document_root", "")).strip()
        if not raw:
            continue
        candidate = Path(raw.replace("/", os.sep))
        if (candidate / "wp-config.php").is_file():
            sites.add(str(candidate))
    return sorted(sites, key=str.lower)


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

    active_versions: dict[str, str] = {}
    virtual_hosts: list[dict[str, Any]] = []
    wordpress_sites: set[str] = set()
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
        active_versions.update(_wamp_active_versions(root))
        root_vhosts = _wamp_virtual_hosts(root)
        virtual_hosts.extend(root_vhosts)
        wordpress_sites.update(_wamp_wordpress_sites(root, root_vhosts))

    services = {
        name: state
        for name in (
            "wampapache64",
            "wampapache",
            "wampmysqld64",
            "wampmysqld",
            "wampmariadb64",
            "wampmariadb",
        )
        if (state := _service_state(name))
    }

    return {
        "detected": bool(roots),
        "roots": [str(root) for root in roots],
        "components": [item.to_dict() for item in components],
        "active_versions": active_versions,
        "virtual_hosts": virtual_hosts[:500],
        "wordpress_sites": sorted(
            {path.lower(): path for path in wordpress_sites}.values(),
            key=str.lower,
        ),
        "hosts_entries": _windows_hosts_entries(),
        "services": services,
        "ports": {
            "80": _port_open(80),
            "443": _port_open(443),
            "3306": _port_open(3306),
        },
    }


def analyze_machine_inventory(
    tools: list[ToolInstallation],
    ollama: dict[str, Any],
    voicebox: dict[str, Any],
    wamp: dict[str, Any],
    hardware: dict[str, Any] | None = None,
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

    if voicebox.get("reachable"):
        downloaded = int(voicebox.get("downloaded_count", 0) or 0)
        loaded = int(voicebox.get("loaded_count", 0) or 0)
        available = int(voicebox.get("available_count", 0) or 0)
        recommendations.append(
            {
                "priority": "low",
                "kind": "voicebox-local-service",
                "title": (
                    f"Voicebox detected with {available} available "
                    f"model(s), {downloaded} downloaded, {loaded} loaded"
                ),
                "recommendation": (
                    "Keep Voicebox bound to loopback for local use. Its "
                    "downloaded TTS/STT/LLM models can be reused by the "
                    "control plane through the local API instead of "
                    "downloading duplicate copies."
                ),
            }
        )
        if voicebox.get("exposed_all_interfaces"):
            recommendations.append(
                {
                    "priority": "high",
                    "kind": "voicebox-network-exposure",
                    "title": "Voicebox is listening on all network interfaces",
                    "recommendation": (
                        "Prefer a localhost-only bind when possible, or verify "
                        "Windows Firewall blocks untrusted networks. The local "
                        "Voicebox API can load models and generate/transcribe "
                        "audio, so it should not be broadly exposed."
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

    for disk in (hardware or {}).get("disks", []):
        try:
            size = int(disk.get("Size") or 0)
            free = int(disk.get("FreeSpace") or 0)
        except (TypeError, ValueError):
            continue
        if size <= 0:
            continue
        ratio = free / size
        drive = str(disk.get("DeviceID") or "?")
        if ratio < 0.08:
            recommendations.append(
                {
                    "priority": "high",
                    "kind": "disk-pressure",
                    "title": (
                        f"{drive} has only {free / (1024**3):.1f} GiB free "
                        f"({ratio * 100:.1f}%)"
                    ),
                    "recommendation": (
                        "Prioritize reviewed cleanup and move large archives or "
                        "model caches only after dependency checks. Keep at least "
                        "10-15% free space for Windows, package managers and builds."
                    ),
                }
            )
        elif ratio < 0.15:
            recommendations.append(
                {
                    "priority": "medium",
                    "kind": "disk-pressure",
                    "title": (
                        f"{drive} free space is {free / (1024**3):.1f} GiB "
                        f"({ratio * 100:.1f}%)"
                    ),
                    "recommendation": (
                        "Plan cleanup before large model downloads or build jobs."
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


def scan_machine_inventory(
    host: str = "",
    voicebox_host: str = "",
) -> MachineInventory:
    tools = detect_toolchain()
    ollama = detect_ollama(host)
    voicebox = detect_voicebox(voicebox_host)
    wamp = detect_wampserver()
    runtime_managers = detect_runtime_managers()
    package_caches = detect_package_caches()
    hardware = detect_hardware()
    return MachineInventory(
        schema_version=2,
        generated_at=datetime.now(timezone.utc).isoformat(),
        hostname=socket.gethostname(),
        platform=platform.system(),
        platform_release=platform.release(),
        tools=[item.to_dict() for item in tools],
        ollama=ollama,
        voicebox=voicebox,
        wampserver=wamp,
        runtime_managers=runtime_managers,
        package_caches=package_caches,
        hardware=hardware,
        recommendations=analyze_machine_inventory(
            tools,
            ollama,
            voicebox,
            wamp,
            hardware,
        ),
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
    "detect_hardware",
    "detect_ollama",
    "detect_voicebox",
    "detect_package_caches",
    "detect_runtime_managers",
    "detect_toolchain",
    "detect_wampserver",
    "scan_machine_inventory",
    "write_machine_inventory",
]
