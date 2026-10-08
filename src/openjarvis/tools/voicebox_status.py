"""Read-only live status tool for the local Voicebox service."""

from __future__ import annotations

import json
from typing import Any

from openjarvis.core.config import load_config
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.projects.machine_inventory import detect_voicebox
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("voicebox_status")
class VoiceboxStatusTool(BaseTool):
    """Query the local Voicebox API without changing model state."""

    tool_id = "voicebox_status"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="voicebox_status",
            description=(
                "Read live status from the local Voicebox service, including "
                "registered, downloaded and loaded TTS/STT/LLM models."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["summary", "models", "health", "storage"],
                    }
                },
            },
            category="voice",
            timeout_seconds=8.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        section = str(params.get("section", "summary")).strip().lower()
        config = load_config()
        status = detect_voicebox(config.projects.voicebox_host)

        if not status.get("reachable"):
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=json.dumps(status, ensure_ascii=False, indent=2),
                metadata={"host": status.get("host", "")},
            )

        if section == "models":
            payload: Any = status.get("models", [])
        elif section == "health":
            payload = status.get("health", {})
        elif section == "storage":
            payload = status.get("storage_roots", [])
        elif section == "profiles":
            payload = status.get("profiles", [])
        else:
            payload = {
                "host": status.get("host", ""),
                "reachable": True,
                "model_count": status.get("model_count", 0),
                "downloaded_count": status.get("downloaded_count", 0),
                "loaded_count": status.get("loaded_count", 0),
                "available_count": status.get("available_count", 0),
                "profile_count": status.get("profile_count", 0),
                "downloaded_models": status.get("downloaded_models", []),
                "loaded_models": status.get("loaded_models", []),
                "docs_url": status.get("docs_url", ""),
            }

        return ToolResult(
            tool_name=self.tool_id,
            success=True,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            metadata={"host": status.get("host", ""), "section": section},
        )


__all__ = ["VoiceboxStatusTool"]
