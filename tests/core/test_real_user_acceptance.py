"""Phase 0.5: real composition, persistent state, privacy, and safe imports."""

import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from openjarvis.channels._stubs import ChannelMessage
from openjarvis.channels.telegram import TelegramChannel
from openjarvis.core.config import JarvisConfig
from openjarvis.core.events import EventBus, EventType
from openjarvis.engine._base import EngineConnectionError
from openjarvis.engine.privacy import PrivatePoolEngine
from openjarvis.intelligence.free_pool import FreePoolEngine
from openjarvis.scheduler.scheduler import TaskScheduler
from openjarvis.scheduler.store import SchedulerStore
from openjarvis.server.channel_bridge import ChannelBridge
from openjarvis.server.session_store import SessionStore
from openjarvis.system import JarvisSystem
from tests.intelligence.test_free_pool import _FakeEngine


def test_legacy_named_scheduler_run_uses_owned_server(tmp_path, monkeypatch):
    import httpx
    from click.testing import CliRunner

    from openjarvis.cli import scheduler_cmd

    store = SchedulerStore(tmp_path / "tasks.db")
    task = TaskScheduler(store).create_task(
        "Read-only fixture", "once", "2099-01-01T00:00:00+00:00", agent="none"
    )
    monkeypatch.setattr(scheduler_cmd, "_get_store", lambda: store)
    post = MagicMock(return_value=httpx.Response(200, json={"success": True}))
    monkeypatch.setattr(httpx, "post", post)
    result = CliRunner().invoke(scheduler_cmd.scheduler, ["run-task", "none"])
    assert result.exit_code == 0, result.output
    post.assert_called_once()
    assert f"/tasks/{task.id}/run" in post.call_args.args[0]


def make_system():
    config = JarvisConfig()
    config.agent.context_from_memory = False
    engine = _FakeEngine(["qwen3.5:2b", "qwen2.5-coder:7b", "nomic-embed-text"])
    engine.generate = MagicMock(return_value={"content": "EXECUTED", "usage": {}})
    return JarvisSystem(
        config,
        EventBus(record_history=True),
        engine,
        "ollama",
        "qwen3.5:2b",
        agent_name="none",
    )


def test_due_prompt_executes_system_and_persists_across_restart(tmp_path):
    system = make_system()
    path = tmp_path / "tasks.db"
    store = SchedulerStore(path)
    scheduler = TaskScheduler(store, system, bus=system.bus, poll_interval=1)
    task = scheduler.create_task(
        "Do the acceptance prompt", "once", "2020-01-01T00:00:00+00:00", agent="none"
    )
    done = threading.Event()
    system.bus.subscribe(EventType.SCHEDULER_TASK_END, lambda event: done.set())
    scheduler.start()
    original_thread = scheduler._thread
    scheduler.start()
    assert scheduler._thread is original_thread
    assert done.wait(3)
    assert scheduler.stop()
    system.engine.generate.assert_called_once()
    assert system.engine.generate.call_args.args[0][-1].content == task.prompt
    assert store.get_run_logs(task.id)[0]["result"] == "EXECUTED"
    store.close()
    restarted = SchedulerStore(path)
    assert restarted.get_task(task.id)["status"] == "completed"
    assert len(restarted.get_run_logs(task.id)) == 1
    restarted.close()


def test_scheduler_rejects_second_owner_and_unbound_execution(tmp_path):
    first_store = SchedulerStore(tmp_path / "tasks.db")
    second_store = SchedulerStore(tmp_path / "tasks.db")
    first = TaskScheduler(first_store, make_system())
    second = TaskScheduler(second_store, make_system())
    with pytest.raises(RuntimeError, match="requires"):
        TaskScheduler(second_store).start()
    first.start()
    try:
        with pytest.raises(RuntimeError, match="Another runtime"):
            second.start()
    finally:
        first.stop()
    second.start()
    assert second.stop()
    first_store.close()
    second_store.close()


def test_slow_scheduler_shutdown_retains_ownership_and_prevents_duplicate_thread(
    tmp_path,
):
    system = make_system()
    entered = threading.Event()
    release = threading.Event()

    def generate(*args, **kwargs):
        entered.set()
        release.wait(3)
        return {"content": "completed"}

    system.engine.generate.side_effect = generate
    store = SchedulerStore(tmp_path / "tasks.db")
    scheduler = TaskScheduler(store, system)
    scheduler.create_task("slow", "once", "2020-01-01T00:00:00+00:00", agent="none")
    scheduler.start()
    assert entered.wait(1)
    thread = scheduler._thread
    scheduler.request_stop()
    assert not scheduler.wait_stopped(timeout=0.01)
    assert scheduler._ownership.file is not None
    scheduler.start()
    assert scheduler._thread is thread
    release.set()
    assert scheduler.wait_stopped(timeout=2)
    store.close()


@pytest.mark.parametrize("path", ["builder", "cli"])
def test_telegram_allowlist_forwarded(path, monkeypatch):
    from openjarvis.cli.channel_cmd import _get_channel
    from openjarvis.core.registry import ChannelRegistry
    from openjarvis.system.builder import SystemBuilder

    config = JarvisConfig()
    config.channel.enabled = True
    config.channel.default_channel = "telegram"
    config.channel.telegram.bot_token = "test-only-token"
    config.channel.telegram.allowed_chat_ids = "111,222"
    ChannelRegistry.register("telegram")(TelegramChannel)
    channel = (
        _get_channel("telegram", config)
        if path == "cli"
        else SystemBuilder(config)._resolve_channel(config, EventBus())
    )
    assert channel._allowed_chat_ids == "111,222"


def test_native_inbound_reply_isolation_restart_and_targeted_notifications(tmp_path):
    system = make_system()
    store = SessionStore(str(tmp_path / "sessions.db"))
    channel = TelegramChannel(bot_token="test-only-token", allowed_chat_ids="111,222")
    channel.connect = MagicMock()
    channel.disconnect = MagicMock()
    channel.send = MagicMock(return_value=True)
    bridge = ChannelBridge({"telegram": channel}, store, system.bus, system=system)
    bridge.connect()
    bridge.connect()
    channel.connect.assert_called_once()
    for chat, content in [("111", "PRIVATE_A"), ("222", "PRIVATE_B")]:
        assert channel.dispatch_message(
            ChannelMessage("telegram", "same-sender", content, "55", chat)
        )
    assert not channel.dispatch_message(
        ChannelMessage("telegram", "same-sender", "REJECT", "56", "999")
    )
    assert system.engine.generate.call_count == 2
    channel.send.assert_called_with(
        "222", "EXECUTED", conversation_id="55", metadata={"reply_to": "55"}
    )
    assert "PRIVATE_A" not in str(store.get_or_create("222", "telegram"))
    bridge.handle_incoming("111", "/notify telegram", "telegram")
    bridge.handle_incoming("222", "/notify telegram", "telegram")
    channel.send.reset_mock()
    tasks = SchedulerStore(tmp_path / "tasks.db")
    scheduler = TaskScheduler(tasks, system, bus=system.bus)
    for success in (True, False):
        system.engine.generate.side_effect = (
            None if success else RuntimeError("failure")
        )
        task = scheduler.create_task(
            "scheduled",
            "once",
            "2099-01-01T00:00:00+00:00",
            agent="none",
            metadata={"notify": {"channel": "telegram", "chat_id": "111"}},
        )
        scheduler.run_task(task.id)
        assert bool(tasks.get_run_logs(task.id)[0]["success"]) == success
    scheduler.stop()
    tasks.close()
    assert channel.send.call_count == 2
    assert all(call.args[0] == "111" for call in channel.send.call_args_list)
    bridge.disconnect()
    bridge.connect()
    assert len(channel._handlers) == 1
    bridge.disconnect()
    store.close()
    restored = SessionStore(str(tmp_path / "sessions.db"))
    assert "PRIVATE_A" in str(restored.get_or_create("111", "telegram"))
    restored.close()


def test_channel_accepts_message_during_poller_startup(tmp_path):
    system = make_system()
    store = SessionStore(str(tmp_path / "sessions.db"))
    channel = TelegramChannel(bot_token="test-only-token", allowed_chat_ids="111")
    channel.connect = lambda: channel.dispatch_message(
        ChannelMessage("telegram", "sender", "startup", "55", "111")
    )
    channel.disconnect = MagicMock()
    channel.send = MagicMock(return_value=True)
    bridge = ChannelBridge({"telegram": channel}, store, system.bus, system=system)
    bridge.connect()
    channel.send.assert_called_once()
    bridge.disconnect()
    store.close()


def test_local_aliases_embedder_exclusion_and_remote_privacy():
    local = _FakeEngine(
        ["qwen3.5:2b", "qwen2.5-coder:7b", "nomic-embed-text"],
        metadata=[
            {
                "id": "qwen3.5:2b",
                "capabilities": ["vision", "tools", "thinking"],
                "context_length": 262144,
            },
        ],
    )
    remote = _FakeEngine(["remote"], is_cloud=True, free_ids=["remote"])
    remote.generate = MagicMock(return_value={"content": "remote"})
    pool = FreePoolEngine([("ollama", local), ("nararouter", remote)])
    assert pool.generate([], model="local/fast")["content"] == "qwen3.5:2b"
    assert pool.generate([], model="local/code")["content"] == "qwen2.5-coder:7b"
    assert pool.generate([], model="local/vision")["content"] == "qwen3.5:2b"
    assert all("embed" not in candidate.model_id for candidate in pool.candidates)
    protected = PrivatePoolEngine([("ollama", local), ("nararouter", remote)])
    local.generate = MagicMock(side_effect=RuntimeError("local unavailable"))
    with pytest.raises(EngineConnectionError):
        protected.generate([], model="free/research")
    with pytest.raises(EngineConnectionError):
        protected.generate([], model="remote")
    remote.generate.assert_not_called()


def test_explicit_cron_timezone_and_offset_validation(tmp_path):
    store = SchedulerStore(tmp_path / "tasks.db")
    scheduler = TaskScheduler(store)
    task = scheduler.create_task(
        "p", "cron", "0 9 * * *", metadata={"timezone": "Asia/Tehran"}
    )
    assert datetime.fromisoformat(task.next_run).astimezone(timezone.utc).hour == 5
    with pytest.raises(ValueError, match="offset"):
        scheduler.create_task("p", "once", "2099-01-01T00:00:00")
    store.close()


@pytest.mark.parametrize("category", ["research", "coding", "productivity"])
def test_hermes_categories_safe_import_translation_and_conflicts(tmp_path, category):
    from openjarvis.skills.importer import SkillImporter
    from openjarvis.skills.parser import SkillParser
    from openjarvis.skills.sources.hermes import HermesResolver
    from openjarvis.skills.tool_translator import ToolTranslator

    root = tmp_path / "cache"
    source = root / "skills" / category / "sample"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: sample\ndescription: Acceptance fixture\n---\n"
        "Read a file. MysteryTool tool.",
        encoding="utf-8",
    )
    (source / "scripts").mkdir()
    (source / "scripts" / "danger.py").write_text(
        "raise RuntimeError('must never execute')"
    )
    resolved = HermesResolver(root).list_skills()
    assert len(resolved) == 1 and resolved[0].category == category
    importer = SkillImporter(SkillParser(), ToolTranslator(), tmp_path / "installed")
    result = importer.import_skill(resolved[0])
    assert result.success and not result.scripts_imported
    assert result.translated_tools and "MysteryTool" in result.untranslated_tools
    assert not (result.target_path / "scripts").exists()
    assert importer.import_skill(resolved[0]).skipped
    audit = importer.audit_skill(resolved[0])
    assert audit["conflict"] and audit["translated_tools"]
    assert audit["untranslated_tools"] == ["MysteryTool"]
    assert not audit["scripts_imported"]


def test_skill_allowed_tools_cannot_hide_dangerous_capabilities(tmp_path):
    from openjarvis.skills.importer import SkillImporter
    from openjarvis.skills.parser import SkillParser
    from openjarvis.skills.sources.base import ResolvedSkill
    from openjarvis.skills.tool_translator import ToolTranslator

    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: dangerous\ndescription: fixture\n"
        "allowed-tools: Bash Write\n---\nBody",
        encoding="utf-8",
    )
    importer = SkillImporter(SkillParser(), ToolTranslator(), tmp_path / "installed")
    resolved = ResolvedSkill("dangerous", "hermes", source, "coding", "fixture", "")
    assert importer.audit_skill(resolved)["dangerous_capabilities"]
    result = importer.import_skill(resolved)
    assert not result.success and result.requires_confirmation
    assert not result.target_path.exists()


def test_server_owns_task_scheduler_startup_shutdown(tmp_path):
    from fastapi.testclient import TestClient

    from openjarvis.server.app import create_app

    system = make_system()
    system.scheduler_store = SchedulerStore(tmp_path / "tasks.db")
    system.scheduler = TaskScheduler(system.scheduler_store, system, bus=system.bus)
    app = create_app(system.engine, system.model, bus=system.bus, runtime_system=system)
    task = system.scheduler.create_task(
        "API prompt", "once", "2099-01-01T00:00:00+00:00", agent="none"
    )
    with TestClient(app) as client:
        assert app.state.task_scheduler._system is system
        assert app.state.task_scheduler._bus is system.bus
        assert system.scheduler._thread.is_alive()
        response = client.post(f"/v1/scheduler/tasks/{task.id}/run")
        assert response.status_code == 200
        assert response.json()["result"] == "EXECUTED"
        assert client.post(f"/v1/scheduler/tasks/{task.id}/run").status_code == 409
        assert client.post("/v1/scheduler/tasks/missing/run").status_code == 404
    assert system.scheduler._thread is None
    assert not app.state._managed_workers


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("instrumented", [True, False])
def test_private_http_rejects_remote_override_before_agent_or_memory(
    stream, instrumented
):
    from fastapi.testclient import TestClient

    from openjarvis.server.app import create_app

    local = _FakeEngine(["qwen3.5:2b"])
    private = PrivatePoolEngine([("ollama", local)])
    if instrumented:
        from openjarvis.telemetry.instrumented_engine import InstrumentedEngine

        private = InstrumentedEngine(private, EventBus())
    config = JarvisConfig()
    config.intelligence.private_routing = True
    agent = MagicMock()
    memory = MagicMock()
    client = TestClient(
        create_app(
            private, "local/fast", config=config, agent=agent, memory_backend=memory
        )
    )
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "openai/gpt-4o",
            "stream": stream,
            "messages": [{"role": "user", "content": "SYNTHETIC_PRIVATE_CHUNK"}],
        },
    )
    assert response.status_code == 400
    assert client.app.state.engine.can_serve("local/fast")
    assert client.get("/router/v1").json()["recommended_model_alias"] == "local/code"
    agent.run.assert_not_called()
    memory.search.assert_not_called()
