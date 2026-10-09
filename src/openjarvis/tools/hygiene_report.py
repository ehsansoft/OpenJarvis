"""Read-only tool for cleanup and duplicate-file reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openjarvis.core.config import load_config
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("hygiene_report")
class HygieneReportTool(BaseTool):
    tool_id = "hygiene_report"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="hygiene_report",
            description=(
                "Read cleanup candidates or exact duplicate-file groups from "
                "the latest disk hygiene scans. Reports are advisory only."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "report": {
                        "type": "string",
                        "enum": ["cleanup", "duplicates"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum entries to return, default 30.",
                    },
                },
                "required": ["report"],
            },
            category="projects",
            timeout_seconds=5.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        report = str(params.get("report", "")).strip().lower()
        try:
            limit = max(1, min(int(params.get("limit", 30)), 200))
        except (TypeError, ValueError):
            limit = 30

        config = load_config()
        if report == "cleanup":
            path = Path(config.projects.cleanup_report_path).expanduser()
            list_key = "candidates"
        elif report == "duplicates":
            path = Path(config.projects.duplicate_report_path).expanduser()
            list_key = "duplicate_groups"
        else:
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content="'report' must be cleanup or duplicates.",
            )

        if not path.exists():
            command = (
                "jarvis projects cleanup-scan"
                if report == "cleanup"
                else "jarvis projects duplicates"
            )
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=f"Report not found: {path}. Run '{command}' first.",
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=f"Could not load hygiene report: {exc}",
            )

        payload = dict(data)
        payload[list_key] = list(data.get(list_key, []))[:limit]
        return ToolResult(
            tool_name=self.tool_id,
            success=True,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            metadata={"report_path": str(path), "report": report},
        )


__all__ = ["HygieneReportTool"]
