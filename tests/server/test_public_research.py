import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.core.types import ToolResult
from openjarvis.server import public_research_router as module


def test_public_approval_does_not_attach_private_memory(monkeypatch):
    system = SimpleNamespace(
        bus=MagicMock(), rate_limiter=None, memory_backend=MagicMock()
    )
    engine = MagicMock()
    engine.generate.return_value = {"content": "Public answer"}
    app = FastAPI()
    app.include_router(module.router)
    app.state.runtime_system = system
    app.state.router_engine = engine
    app.state._control_chat_lock = threading.Lock()
    secured = MagicMock(
        return_value=ToolResult(
            tool_name="web_search",
            content="https://example.org Public fixture",
            success=True,
        )
    )
    monkeypatch.setattr(module, "execute_secured_tool", secured)
    client = TestClient(
        app, base_url="http://127.0.0.1", headers={"X-Jarvis-Control": "1"}
    )
    assert (
        client.post(
            "/v1/control/public-research", json={"query": "Public fixture"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/control/public-research",
            json={"query": "Public fixture", "approved_public": True},
        ).status_code
        == 200
    )
    system.memory_backend.retrieve.assert_not_called()
    assert secured.call_args.kwargs["agent_id"] == "public-research"
    assert engine.generate.call_args.kwargs["model"] == "free/research"
