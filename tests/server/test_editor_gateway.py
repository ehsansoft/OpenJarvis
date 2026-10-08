"""Tests for the raw OpenAI-compatible editor gateway routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.agents._stubs import AgentResult  # noqa: E402
from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.server.app import create_app  # noqa: E402


class _MemorySpy:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str]] = []

    def submit(self, user_text: str, assistant_text: str = "") -> bool:
        self.submissions.append((user_text, assistant_text))
        return True

    def stop(self, timeout: float = 2.0) -> None:
        return None


def _config() -> JarvisConfig:
    cfg = JarvisConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.context_from_memory = True
    return cfg


def _engine():
    engine = MagicMock()
    engine.engine_id = "multi"
    engine.health.return_value = True
    engine.list_models.return_value = ["free/code", "free/research", "qwen3:4b"]
    engine.generate.return_value = {
        "content": "direct response",
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
        },
        "model": "free/code",
        "finish_reason": "stop",
    }
    return engine


def test_editor_gateway_bypasses_server_agent_and_memory() -> None:
    engine = _engine()
    agent = MagicMock()
    agent.agent_id = "orchestrator"
    agent.run.return_value = AgentResult(content="agent response", turns=1)
    memory = _MemorySpy()

    app = create_app(
        engine,
        "free/code",
        agent=agent,
        memory_service=memory,
        config=_config(),
    )
    client = TestClient(app)
    response = client.post(
        "/router/v1/chat/completions",
        json={
            "model": "free/code",
            "messages": [{"role": "user", "content": "Fix this code"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "direct response"
    assert not agent.run.called
    assert memory.submissions == []
    assert engine.generate.called


def test_editor_gateway_lists_stable_aliases() -> None:
    engine = _engine()
    app = create_app(engine, "free/code", config=_config())
    client = TestClient(app)

    response = client.get("/router/v1/models")

    assert response.status_code == 200
    model_ids = [item["id"] for item in response.json()["data"]]
    assert "free/code" in model_ids
    assert "free/research" in model_ids
