"""Tests for disk hygiene report context tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from openjarvis.core.config import JarvisConfig
from openjarvis.tools.hygiene_report import HygieneReportTool


def test_hygiene_tool_limits_duplicate_groups(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.json"
    path.write_text(
        json.dumps(
            {
                "duplicate_groups": [
                    {"sha256": "a", "files": ["a", "b"]},
                    {"sha256": "b", "files": ["c", "d"]},
                ],
                "reclaimable_bytes": 100,
            }
        ),
        encoding="utf-8",
    )
    config = JarvisConfig()
    config.projects.duplicate_report_path = str(path)

    with mock.patch(
        "openjarvis.tools.hygiene_report.load_config",
        return_value=config,
    ):
        result = HygieneReportTool().execute(report="duplicates", limit=1)

    assert result.success is True
    payload = json.loads(result.content)
    assert len(payload["duplicate_groups"]) == 1
