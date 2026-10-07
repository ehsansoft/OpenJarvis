"""Read-only tool for resolving local projects from the project registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openjarvis.core.config import load_config
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.projects import load_registry
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("project_registry")
class ProjectRegistryTool(BaseTool):
    """Resolve project names, paths, types and Git metadata for agents."""

    tool_id = "project_registry"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="project_registry",
            description=(
                "Search or list the user's local project registry. Use this "
                "before reading files when the user refers to a project by "
                "name, site, technology, or partial path."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Optional case-insensitive search text. Empty "
                            "returns a compact project list."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results, default 20.",
                    },
                },
            },
            category="projects",
            timeout_seconds=5.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        query = str(params.get("query", "")).strip().lower()
        try:
            limit = int(params.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        config = load_config()
        path = Path(config.projects.registry_path).expanduser()
        if not path.exists():
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=(
                    f"Project registry not found: {path}. "
                    "Run 'jarvis projects scan' first."
                ),
            )

        try:
            registry = load_registry(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return ToolResult(
                tool_name=self.tool_id,
                success=False,
                content=f"Could not load project registry: {exc}",
            )

        matches = []
        for project in registry.get("projects", []):
            if not isinstance(project, dict):
                continue
            haystack = " ".join(
                [
                    str(project.get("project_id", "")),
                    str(project.get("name", "")),
                    str(project.get("path", "")),
                    str(project.get("project_type", "")),
                    " ".join(project.get("languages", []) or []),
                    " ".join(project.get("frameworks", []) or []),
                    str((project.get("git") or {}).get("remote", "")),
                ]
            ).lower()
            if query and query not in haystack:
                continue
            matches.append(project)
            if len(matches) >= limit:
                break

        payload = {
            "registry": str(path),
            "query": query,
            "count": len(matches),
            "projects": matches,
        }
        return ToolResult(
            tool_name=self.tool_id,
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            success=True,
            metadata={"registry_path": str(path), "count": len(matches)},
        )


__all__ = ["ProjectRegistryTool"]
