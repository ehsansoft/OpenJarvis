"""Verify Voicebox MCP through both direct and configured paths."""

from __future__ import annotations

import json

from openjarvis.core.config import load_config
from openjarvis.mcp.client import MCPClient
from openjarvis.mcp.loader import load_mcp_tools_from_config
from openjarvis.mcp.transport import StreamableHTTPTransport

VOICEBOX_MCP_URL = "http://127.0.0.1:17493/mcp/"
VOICEBOX_HEADERS = {"X-Voicebox-Client-Id": "openjarvis"}
EXPECTED = {
    "voicebox_speak",
    "voicebox_transcribe",
    "voicebox_list_captures",
    "voicebox_list_profiles",
}


def _missing_tools(names: list[str]) -> list[str]:
    """Accept the native dotted namespace and older underscore tool names."""
    normalized = {
        "voicebox_" + name[len("voicebox.") :] if name.startswith("voicebox.") else name
        for name in names
    }
    return sorted(EXPECTED - normalized)


def _direct_probe() -> tuple[list[str], str]:
    transport = StreamableHTTPTransport(
        VOICEBOX_MCP_URL,
        headers=VOICEBOX_HEADERS,
        connect_timeout=5.0,
        request_timeout=30.0,
    )
    client = MCPClient(transport)
    try:
        init = client.initialize()
        specs = client.list_tools()
        names = sorted(spec.name for spec in specs)
        return names, json.dumps(init, ensure_ascii=False)
    finally:
        client.close()


def main() -> int:
    print(f"Voicebox MCP endpoint: {VOICEBOX_MCP_URL}")

    try:
        direct_names, init = _direct_probe()
    except Exception as exc:
        print(f"Direct Voicebox MCP probe failed: {type(exc).__name__}: {exc}")
        return 2

    print("Direct MCP tools:")
    for name in direct_names:
        print(f"  - {name}")
    missing = _missing_tools(direct_names)
    if missing:
        print("Missing expected direct tools: " + ", ".join(missing))
        print("Initialize response: " + init)
        return 2

    config = load_config()
    tools, clients = load_mcp_tools_from_config(config.tools.mcp)
    try:
        configured = sorted(
            tool.spec.name for tool in tools if "voicebox" in tool.spec.name.lower()
        )
        print("Configured OpenJarvis MCP tools:")
        for name in configured:
            print(f"  - {name}")
        missing = _missing_tools(configured)
        if missing:
            print("Missing configured tools: " + ", ".join(missing))
            return 3
    finally:
        for client in clients:
            try:
                client.close()
            except Exception:
                pass

    print("Voicebox MCP discovery OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
