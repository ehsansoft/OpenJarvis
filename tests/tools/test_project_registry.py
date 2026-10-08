"""Tests for the read-only project registry tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from openjarvis.core.config import JarvisConfig
from openjarvis.projects.discovery import ProjectRecord, write_registry
from openjarvis.tools.project_registry import ProjectRegistryTool


def test_project_registry_searches_metadata(tmp_path: Path) -> None:
    registry = tmp_path / "projects.json"
    write_registry(
        [
            ProjectRecord(
                project_id="livora-brain",
                name="Livora Brain",
                path=str(tmp_path / "Livora"),
                project_type="wordpress-plugin",
                languages=["PHP"],
                frameworks=["WordPress", "WooCommerce"],
                markers=[".git"],
                git={
                    "is_repo": True,
                    "branch": "main",
                    "remote": "https://github.com/example/livora.git",
                },
            )
        ],
        registry,
        root=tmp_path,
    )

    config = JarvisConfig()
    config.projects.registry_path = str(registry)
    with mock.patch(
        "openjarvis.tools.project_registry.load_config",
        return_value=config,
    ):
        result = ProjectRegistryTool().execute(query="woocommerce")

    assert result.success is True
    payload = json.loads(result.content)
    assert payload["count"] == 1
    assert payload["projects"][0]["project_id"] == "livora-brain"


def test_project_registry_reports_missing_registry(tmp_path: Path) -> None:
    config = JarvisConfig()
    config.projects.registry_path = str(tmp_path / "missing.json")
    with mock.patch(
        "openjarvis.tools.project_registry.load_config",
        return_value=config,
    ):
        result = ProjectRegistryTool().execute(query="anything")

    assert result.success is False
    assert "Run 'jarvis projects scan' first" in result.content
