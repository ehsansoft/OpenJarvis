"""Read-only tool for the persisted developer workstation inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openjarvis.core.config import load_config
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("machine_inventory")
class MachineInventoryTool(BaseTool):
    tool_id = "machine_inventory"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="machine_inventory",
            description=(
                "Read the latest local machine inventory: Ollama models, "
                "WampServer runtimes, Node/npm/pnpm and other developer tools."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "summary",
                            "tools",
                            "ollama",
                            "wampserver",
                            "recommendations",
                        ],
                    }
                },
            },
            category="projects",
            timeout_seconds=5.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        section = str(params.get("section", "summary")).strip().lower()
        config = load_config()
        path = Path(config.projects.machine_inventory_path).expanduser()
        if not path.exists():
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=(
                    f"Machine inventory not found: {path}. "
                    "Run 'jarvis projects machine-scan' first."
                ),
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=f"Could not load machine inventory: {exc}",
            )

        if section == "tools":
            payload: Any = data.get("tools", [])
        elif section == "ollama":
            payload = data.get("ollama", {})
        elif section == "wampserver":
            payload = data.get("wampserver", {})
        elif section == "recommendations":
            payload = data.get("recommendations", [])
        else:
            payload = {
                "generated_at": data.get("generated_at", ""),
                "hostname": data.get("hostname", ""),
                "platform": data.get("platform", ""),
                "platform_release": data.get("platform_release", ""),
                "tools_detected": len(data.get("tools", [])),
                "ollama_models": data.get("ollama", {}).get("model_count", 0),
                "wampserver_detected": data.get("wampserver", {}).get(
                    "detected", False
                ),
            }

        return ToolResult(
            tool_name=self.tool_id,
            success=True,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            metadata={"inventory_path": str(path), "section": section},
        )


__all__ = ["MachineInventoryTool"]
