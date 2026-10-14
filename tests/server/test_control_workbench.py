"""Workbench acceptance: ownership, local privacy, browser boundaries and state."""

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.core.config import JarvisConfig
from openjarvis.core.events import EventBus
from openjarvis.scheduler.scheduler import TaskScheduler
from openjarvis.scheduler.store import SchedulerStore
from openjarvis.server import control_router
from openjarvis.server.auth_middleware import AuthMiddleware
from openjarvis.server.scheduler_routes import router as scheduler_router
from openjarvis.skills.manager import SkillManager


@pytest.fixture
def workbench(tmp_path, monkeypatch):
    config = JarvisConfig()
    config.engine.ollama.host = "http://127.0.0.1:11434"
    config.intelligence.private_routing = True
    config.intelligence.allow_private_remote = False
    bus = EventBus()
    manager = SkillManager(bus, overlay_dir=tmp_path / "overlays")
    manager.discover([Path(__file__).resolve().parents[2] / "skills"])
    system = SimpleNamespace(
        config=config,
        model="local/fast",
        bus=bus,
        skill_manager=manager,
        capability_policy=None,
        ask=MagicMock(return_value={"content": "local answer"}),
    )
    store = SchedulerStore(tmp_path / "scheduler.db")
    scheduler = TaskScheduler(store, system, bus=bus)
    app = FastAPI()
    app.state.config = config
    app.state.model = "local/fast"
    app.state.runtime_system = system
    app.state.task_scheduler = scheduler
    app.state._managed_workers = set()
    app.state._managed_worker_lock = threading.Lock()
    app.state._managed_runtime_stopping = False
    control_router.initialize_control(app)
    app.include_router(scheduler_router)
    monkeypatch.setattr(control_router, "get_config_dir", lambda: tmp_path)
    with TestClient(
        app, base_url="http://127.0.0.1:18080", headers={"X-Jarvis-Control": "1"}
    ) as client:
        yield client, system, scheduler, app
    scheduler.stop()
    store.close()


def test_private_chat_uses_owned_system_and_separate_histories(workbench):
    client, system, _, _ = workbench
    first = client.post(
        "/v1/control/chat",
        json={
            "prompt": "first",
            "history": [{"role": "user", "content": "Only conversation A"}],
        },
    )
    assert first.status_code == 200
    assert (
        system.ask.call_args.kwargs["prior_messages"][0].content
        == "Only conversation A"
    )
    assert "shell_exec" not in system.ask.call_args.kwargs["tools"]
    second = client.post("/v1/control/chat", json={"prompt": "conversation B"})
    assert second.status_code == 200
    assert system.ask.call_args.kwargs["prior_messages"] == []
    assert second.json()["private"] is True


def test_overview_uses_configured_endpoints_and_real_state(workbench, monkeypatch):
    client, system, _, _ = workbench
    observed = []

    async def probe(name, base, path):
        observed.append((name, base, path))
        return {"name": name, "url": base, "status": "RUNNING"}

    monkeypatch.setattr(control_router, "_probe", probe)
    result = client.get("/v1/control/overview")
    assert result.status_code == 200
    data = result.json()
    assert data["disk"]["free_bytes"] > 0
    assert data["active_tasks"] == 0
    assert data["private_routing"] is True
    assert (
        "Voicebox",
        system.config.projects.voicebox_host,
        "/models/status",
    ) in observed


def test_research_never_has_web_or_write_tools(workbench, monkeypatch):
    client, system, _, _ = workbench
    from openjarvis.core.types import ToolResult

    system.memory_backend = MagicMock()
    system.rate_limiter = None
    system.engine = MagicMock()
    system.engine.is_cloud = False
    system.engine._host = "http://127.0.0.1:11434"
    system.engine_key = "ollama"
    system.engine.generate.return_value = {"content": "26.58 GiB [1]"}
    retrieved = MagicMock(
        return_value=ToolResult(
            tool_name="retrieval",
            content="[1] runbook: recovered 26.58 GiB",
            success=True,
            metadata={"num_results": 1},
        )
    )
    monkeypatch.setattr("openjarvis.security.runtime.execute_secured_tool", retrieved)
    result = client.post(
        "/v1/control/chat", json={"prompt": "private question", "mode": "research"}
    )
    assert result.status_code == 200
    assert retrieved.call_args.args[0].tool_id == "retrieval"
    assert system.engine.generate.call_args.kwargs["model"] == "local/research"
    assert "26.58" in result.json()["sources"]
    system.ask.assert_not_called()
    retrieved.return_value.metadata = {}
    system.engine.generate.reset_mock()
    empty = client.post(
        "/v1/control/chat", json={"prompt": "unknown", "mode": "research"}
    )
    assert "No indexed source" in empty.json()["content"]
    system.engine.generate.assert_not_called()
    system.config.intelligence.allow_private_remote = True
    assert (
        client.post("/v1/control/chat", json={"prompt": "private"}).status_code == 409
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://attacker.example"},
        {"Host": "attacker.example"},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-Jarvis-Control": ""},
    ],
)
def test_cross_site_actions_are_rejected_before_execution(workbench, headers):
    client, system, _, _ = workbench
    result = client.post(
        "/v1/control/chat", json={"prompt": "injected"}, headers=headers
    )
    assert result.status_code == 403
    system.ask.assert_not_called()


def test_same_origin_and_api_key_are_supported(workbench):
    client, _, _, app = workbench
    secured = FastAPI()
    secured.state = app.state
    control_router.initialize_control(secured)
    secured.add_middleware(AuthMiddleware, api_key="fixture-key")
    with TestClient(secured, base_url="http://127.0.0.1:18080") as protected:
        assert protected.get("/v1/control/tasks").status_code == 401
        result = protected.get(
            "/v1/control/tasks", headers={"Authorization": "Bearer fixture-key"}
        )
        assert result.status_code == 200
    result = client.post(
        "/v1/control/chat",
        json={"prompt": "local"},
        headers={"Origin": "http://127.0.0.1:18080"},
    )
    assert result.status_code == 200


def test_real_document_retrieval_keeps_natural_question_searchable(workbench, tmp_path):
    from openjarvis.tools.storage.sqlite import SQLiteMemory

    client, system, _, _ = workbench
    memory = SQLiteMemory(tmp_path / "memory.db")
    memory.store("The approved cleanup recovered 26.58 GiB.", source="local-runbook.md")
    system.memory_backend = memory
    system.rate_limiter = None
    system.engine_key = "ollama"
    system.engine = MagicMock(is_cloud=False)
    system.engine._host = "http://127.0.0.1:11434"
    system.engine.generate.return_value = {"content": "26.58 GiB [1]"}
    try:
        result = client.post(
            "/v1/control/chat",
            json={
                "prompt": "How much disk space did the completed cleanup recover?",
                "mode": "research",
            },
        )
        assert result.status_code == 200
        assert "26.58 GiB" in result.json()["sources"]
        assert "local-runbook.md" in result.json()["sources"]
        system.engine.generate.assert_called_once()
    finally:
        memory.close()


def test_unreviewed_task_cannot_run_or_resume_from_dashboard(workbench):
    client, _, scheduler, _ = workbench
    task = scheduler.create_task(
        "edit files",
        "once",
        "2099-01-01T00:00:00Z",
        agent="orchestrator",
        tools="shell_exec",
    )
    scheduler.pause_task(task.id)
    assert (
        client.post(f"/v1/control/tasks/{task.id}/execute", json={}).status_code == 403
    )
    assert (
        client.post(f"/v1/control/tasks/{task.id}/state/resume", json={}).status_code
        == 403
    )


def test_task_create_execute_pause_and_history_use_same_sqlite_owner(workbench):
    client, system, scheduler, _ = workbench
    run_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    created = client.post(
        "/v1/control/tasks", json={"prompt": "/system", "run_at": run_at}
    )
    assert created.status_code == 200
    task_id = created.json()["id"]
    assert (
        client.post(f"/v1/control/tasks/{task_id}/state/pause", json={}).status_code
        == 200
    )
    assert client.get("/v1/control/tasks").json()["tasks"][0]["status"] == "paused"
    assert (
        client.post(f"/v1/control/tasks/{task_id}/state/resume", json={}).status_code
        == 200
    )
    result = client.post(f"/v1/control/tasks/{task_id}/execute")
    assert result.status_code == 200
    assert result.json()["success"] == 1
    assert scheduler._system is system
    system.ask.assert_called_once()
    assert (
        client.get(f"/v1/control/tasks/{task_id}/logs").json()["logs"][0]["result"]
        == "local answer"
    )
    assert client.get("/v1/control/tasks").json()["tasks"][0]["status"] == "completed"
    reopened = SchedulerStore(scheduler._store._db_path)
    try:
        assert reopened.get_task(task_id)["status"] == "completed"
    finally:
        reopened.close()


@pytest.mark.parametrize("run_at", ["2099-01-01T00:00:00", "2000-01-01T00:00:00Z"])
def test_task_needs_future_time_and_explicit_offset(workbench, run_at):
    client, _, _, _ = workbench
    assert (
        client.post(
            "/v1/control/tasks", json={"prompt": "test", "run_at": run_at}
        ).status_code
        == 422
    )


def test_instruction_and_changed_skills_cannot_execute(workbench):
    client, system, _, _ = workbench
    skills = client.get("/v1/control/skills").json()["skills"]
    assert len(skills) >= 3
    assert all(
        not skill["runnable"] for skill in skills if skill["kind"] == "instructions"
    )
    assert (
        client.post("/v1/control/skills/private-project-plan/run", json={}).status_code
        == 403
    )
    system.skill_manager.resolve("workstation-brief").steps[0].tool_name = "shell_exec"
    assert (
        client.post("/v1/control/skills/workstation-brief/run", json={}).status_code
        == 403
    )


def test_service_start_no_duplicate_no_download_and_loopback_only(
    workbench, monkeypatch
):
    client, system, _, _ = workbench
    http_client = MagicMock()
    http_client.__enter__.return_value = http_client
    http_client.get.return_value.is_success = True
    monkeypatch.setattr(control_router.httpx, "Client", lambda **kw: http_client)
    spawn = MagicMock()
    monkeypatch.setattr(control_router, "_spawn", spawn)
    assert (
        client.post("/v1/control/services/ollama/start", json={}).json()["status"]
        == "ALREADY_RUNNING"
    )
    spawn.assert_not_called()

    system.config.engine.ollama.host = "https://provider.example"
    assert client.post("/v1/control/services/ollama/start", json={}).status_code == 409
    spawn.assert_not_called()


def test_offline_ollama_start_is_fixed_loopback_and_idempotent(workbench, monkeypatch):
    import httpx

    client, _, _, _ = workbench
    http_client = MagicMock()
    http_client.__enter__.return_value = http_client
    http_client.get.side_effect = httpx.ConnectError("offline")
    monkeypatch.setattr(control_router.httpx, "Client", lambda **kw: http_client)
    monkeypatch.setattr(
        control_router.shutil, "which", lambda name: "installed-ollama.exe"
    )
    process = MagicMock(pid=1234)
    process.poll.return_value = None
    spawn = MagicMock(return_value=process)
    monkeypatch.setattr(control_router, "_spawn", spawn)
    first = client.post("/v1/control/services/ollama/start", json={})
    assert first.status_code == 200
    assert spawn.call_args.args[0] == ["installed-ollama.exe", "serve"]
    assert spawn.call_args.args[2]["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert client.post("/v1/control/services/ollama/start", json={}).status_code == 200
    spawn.assert_called_once()


def test_restart_waits_for_owned_shutdown_and_refuses_busy_requests(
    workbench, monkeypatch
):
    client, _, _, app = workbench
    server = SimpleNamespace(
        should_exit=False, config=SimpleNamespace(host="127.0.0.1", port=18080)
    )
    app.state.daemon_server = server
    spawn = MagicMock()
    monkeypatch.setattr(control_router, "_spawn", spawn)
    app.state._control_chat_lock.acquire()
    try:
        assert (
            client.post(
                "/v1/control/services/jarvis/restart",
                json={"confirm": "restart-jarvis"},
            ).status_code
            == 409
        )
    finally:
        app.state._control_chat_lock.release()
    assert (
        client.post(
            "/v1/control/services/jarvis/restart", json={"confirm": "restart-jarvis"}
        ).status_code
        == 200
    )
    assert server.should_exit
    assert "openjarvis.server.control_restart" in spawn.call_args.args[0]
    assert (
        client.post(
            "/v1/control/services/jarvis/restart", json={"confirm": "restart-jarvis"}
        ).status_code
        == 200
    )
    spawn.assert_called_once()


def test_dashboard_assets_use_no_external_services_and_no_traversal(workbench):
    client, _, _, _ = workbench
    page = client.get("/control")
    assert page.status_code == 200
    assert "Control Desk" in page.text
    assert client.get("/control/assets/control.js").status_code == 200
    assert client.get("/control/assets/control.css").status_code == 200
    assert client.get("/control/assets/credentials.toml").status_code == 422
