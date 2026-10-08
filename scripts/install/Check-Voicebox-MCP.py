"""Verify Voicebox MCP discovery through OpenJarvis' own MCP client."""

from __future__ import annotations

from openjarvis.core.config import load_config
from openjarvis.mcp.loader import load_mcp_tools_from_config


def main() -> int:
    config = load_config()
    tools, clients = load_mcp_tools_from_config(config.tools.mcp)
    try:
        names = sorted(
            tool.spec.name
            for tool in tools
            if "voicebox" in tool.spec.name.lower()
        )
        print("Voicebox MCP tools:")
        for name in names:
            print(f"  - {name}")
        if not names:
            print("No Voicebox MCP tools discovered.")
            return 2
        return 0
    finally:
        for client in clients:
            try:
                client.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
