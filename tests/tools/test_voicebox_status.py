"""Tests for live Voicebox status tool."""

from __future__ import annotations

import json
from unittest import mock

from openjarvis.core.config import JarvisConfig
from openjarvis.tools.voicebox_status import VoiceboxStatusTool


def test_voicebox_status_tool_returns_live_models() -> None:
    config = JarvisConfig()
    config.projects.voicebox_host = "http://127.0.0.1:17493"

    payload = {
        "host": config.projects.voicebox_host,
        "reachable": True,
        "models": [
            {
                "model_name": "kokoro",
                "display_name": "Kokoro 82M",
                "downloaded": True,
                "loaded": True,
            }
        ],
        "model_count": 1,
        "downloaded_count": 1,
        "loaded_count": 1,
        "downloaded_models": ["kokoro"],
        "loaded_models": ["kokoro"],
        "storage_roots": [],
        "health": {"status": "ok"},
        "docs_url": "http://127.0.0.1:17493/docs",
    }

    with (
        mock.patch(
            "openjarvis.tools.voicebox_status.load_config",
            return_value=config,
        ),
        mock.patch(
            "openjarvis.tools.voicebox_status.detect_voicebox",
            return_value=payload,
        ),
    ):
        result = VoiceboxStatusTool().execute(section="models")

    assert result.success is True
    models = json.loads(result.content)
    assert models[0]["model_name"] == "kokoro"


def test_voicebox_status_tool_reports_unreachable() -> None:
    config = JarvisConfig()
    config.projects.voicebox_host = "http://127.0.0.1:17493"

    with (
        mock.patch(
            "openjarvis.tools.voicebox_status.load_config",
            return_value=config,
        ),
        mock.patch(
            "openjarvis.tools.voicebox_status.detect_voicebox",
            return_value={
                "host": config.projects.voicebox_host,
                "reachable": False,
                "error": "connection refused",
            },
        ),
    ):
        result = VoiceboxStatusTool().execute()

    assert result.success is False
    assert "connection refused" in result.content
