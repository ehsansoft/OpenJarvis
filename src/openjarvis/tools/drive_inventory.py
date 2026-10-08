"""Read-only tool for consulting the persisted drive inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openjarvis.core.config import load_config
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("drive_inventory")
class DriveInventoryTool(BaseTool):
    """Expose drive layout summaries and organization recommendations to agents."""

    tool_id = "drive_inventory"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="drive_inventory",
            description=(
                "Read the latest metadata-only drive inventory and organization "
                "recommendations. Use it for disk layout, duplicate project, "
                "storage, and workspace-organization questions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": [
                            "summary",
                            "recommendations",
                            "projects",
                            "top_level",
                            "extensions",
                        ],
                        "description": "Inventory section to return.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum list items, default 30.",
                    },
                },
            },
            category="projects",
            timeout_seconds=5.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        section = str(params.get("section", "summary")).strip().lower()
        try:
            limit = int(params.get("limit", 30))
        except (TypeError, ValueError):
            limit = 30
        limit = max(1, min(limit, 200))

        config = load_config()
        path = Path(config.projects.inventory_path).expanduser()
        if not path.exists():
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=(
                    f"Drive inventory not found: {path}. "
                    "Run 'jarvis projects inventory' first."
                ),
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=f"Could not load drive inventory: {exc}",
            )

        if section == "recommendations":
            payload: Any = data.get("recommendations", [])[:limit]
        elif section == "projects":
            payload = data.get("project_roots", [])[:limit]
        elif section == "top_level":
            payload = data.get("top_level", [])[:limit]
        elif section == "extensions":
            extension_counts = data.get("extension_counts", {})
            payload = dict(list(extension_counts.items())[:limit])
        else:
            payload = {
                "root": data.get("root", ""),
                "generated_at": data.get("generated_at", ""),
                "files_seen": data.get("files_seen", 0),
                "directories_seen": data.get("directories_seen", 0),
                "bytes_seen": data.get("bytes_seen", 0),
                "truncated": data.get("truncated", False),
                "projects_detected": len(data.get("project_roots", [])),
                "code_file_count": data.get("code_file_count", 0),
                "model_file_count": data.get("model_file_count", 0),
                "loose_root_files": len(data.get("loose_root_files", [])),
                "scan_errors": len(data.get("errors", [])),
            }

        return ToolResult(
            tool_name=self.tool_id,
            success=True,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            metadata={"inventory_path": str(path), "section": section},
        )


__all__ = ["DriveInventoryTool"]
