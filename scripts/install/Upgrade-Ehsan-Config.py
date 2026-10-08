"""Idempotent config migration for the Windows personal control-plane preset."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import tomlkit


VOICEBOX_MCP = {
    "name": "voicebox",
    "url": "http://127.0.0.1:17493/mcp",
    "headers": {"X-Voicebox-Client-Id": "openjarvis"},
}


def _table(doc: Any, name: str) -> Any:
    value = doc.get(name)
    if value is None:
        value = tomlkit.table()
        doc[name] = value
    return value


def _merge_voicebox_mcp(mcp: Any) -> str:
    raw = str(mcp.get("servers") or "").strip()
    if not raw:
        return json.dumps([VOICEBOX_MCP], separators=(",", ":"))

    if not raw.startswith("[") and not raw.startswith("{"):
        # Preserve external-file configs; the user may maintain them manually.
        return raw

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return raw

    found = False
    for item in payload:
        if not isinstance(item, dict):
            continue
        if (
            item.get("name") == "voicebox"
            or item.get("url") == VOICEBOX_MCP["url"]
        ):
            item["name"] = "voicebox"
            item["url"] = VOICEBOX_MCP["url"]
            headers = item.setdefault("headers", {})
            if isinstance(headers, dict):
                headers.setdefault(
                    "X-Voicebox-Client-Id",
                    "openjarvis",
                )
            found = True
            break
    if not found:
        payload.append(dict(VOICEBOX_MCP))
    return json.dumps(payload, separators=(",", ":"))


def upgrade(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    doc = tomlkit.parse(text)
    changes: list[str] = []

    projects = _table(doc, "projects")
    if projects.get("voicebox_host") != "http://127.0.0.1:17493":
        projects["voicebox_host"] = "http://127.0.0.1:17493"
        changes.append("projects.voicebox_host")

    speech = _table(doc, "speech")
    if not speech.get("backend"):
        speech["backend"] = "auto"
        changes.append("speech.backend")
    if not speech.get("model"):
        speech["model"] = "base"
        changes.append("speech.model")
    if speech.get("compute_type") in (None, "", "float16"):
        speech["compute_type"] = "int8"
        changes.append("speech.compute_type")

    tools = _table(doc, "tools")
    enabled = tools.get("enabled")
    required_tools = [
        "project_registry",
        "drive_inventory",
        "machine_inventory",
        "voicebox_status",
        "hygiene_report",
    ]
    if enabled is not None and hasattr(enabled, "append"):
        for name in required_tools:
            if name not in enabled:
                enabled.append(name)
                changes.append(f"tools.enabled:{name}")

    mcp = tools.get("mcp")
    if mcp is None:
        mcp = tomlkit.table()
        tools["mcp"] = mcp
    if mcp.get("enabled") is not True:
        mcp["enabled"] = True
        changes.append("tools.mcp.enabled")
    merged_servers = _merge_voicebox_mcp(mcp)
    if str(mcp.get("servers") or "") != merged_servers:
        mcp["servers"] = merged_servers
        changes.append("tools.mcp.servers:voicebox")

    security = _table(doc, "security")
    if not security.get("profile"):
        security["profile"] = "personal"
        changes.append("security.profile")

    analytics = _table(doc, "analytics")
    if analytics.get("enabled") is not False:
        analytics["enabled"] = False
        changes.append("analytics.enabled")

    server = _table(doc, "server")
    if server.get("host") != "127.0.0.1":
        server["host"] = "127.0.0.1"
        changes.append("server.host")

    nara = _table(_table(doc, "engine"), "nararouter")
    if nara.get("free_only") is not True:
        nara["free_only"] = True
        changes.append("engine.nararouter.free_only")

    intelligence = _table(doc, "intelligence")
    if intelligence.get("default_model") == "qwen3:4b":
        intelligence["default_model"] = ""
        changes.append("intelligence.default_model")
    if intelligence.get("model_code") in (None, "", "qwen3:4b"):
        intelligence["model_code"] = "free/code"
        changes.append("intelligence.model_code")

    path.write_text(tomlkit.dumps(doc), encoding="utf-8", newline="\n")
    return changes


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: Upgrade-Ehsan-Config.py <config.toml>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).expanduser()
    if not path.exists():
        print(f"config not found: {path}", file=sys.stderr)
        return 2
    changes = upgrade(path)
    print("Control-plane config upgraded.")
    if changes:
        for change in changes:
            print(f"  + {change}")
    else:
        print("  no changes needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
