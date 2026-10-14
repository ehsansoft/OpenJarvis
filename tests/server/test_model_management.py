"""Tests for model pull / delete API endpoints and streaming resilience."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.app import create_app  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(engine_id="mock", models=None):
    engine = MagicMock()
    engine.engine_id = engine_id
    engine.health.return_value = True
    engine.list_models.return_value = models or ["test-model"]
    engine.generate.return_value = {
        "content": "Hello",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "test-model",
        "finish_reason": "stop",
    }

    async def mock_stream(messages, *, model, temperature=0.7, max_tokens=1024, **kw):
        for token in ["Hello", " ", "world"]:
            yield token

    engine.stream = mock_stream
    return engine


def _make_ollama_engine(models=None):
    """Create a mock engine that looks like OllamaEngine."""
    engine = _make_engine(engine_id="ollama", models=models)
    engine._host = "http://localhost:11434"
    return engine


def _app(engine, engine_name="mock"):
    return create_app(engine, "test-model", engine_name=engine_name)


# ---------------------------------------------------------------------------
# Model pull endpoint
# ---------------------------------------------------------------------------


class TestModelPull:
    def test_pull_requires_model_field(self):
        engine = _make_ollama_engine()
        client = TestClient(_app(engine, engine_name="ollama"))
        resp = client.post("/v1/models/pull", json={})
        assert resp.status_code == 400
        assert "model" in resp.json()["detail"].lower()

    def test_pull_rejects_non_ollama_engine(self):
        engine = _make_engine(engine_id="vllm")
        client = TestClient(_app(engine, engine_name="vllm"))
        resp = client.post("/v1/models/pull", json={"model": "foo"})
        assert resp.status_code == 501

    def test_pull_success(self):
        engine = _make_ollama_engine()
        client = TestClient(_app(engine, engine_name="ollama"))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(return_value=mock_resp)

            resp = client.post("/v1/models/pull", json={"model": "qwen3.5:4b"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["model"] == "qwen3.5:4b"
        instance.post.assert_awaited_once_with(
            "/api/pull",
            json={"name": "qwen3.5:4b", "stream": False},
        )

    def test_pull_ollama_unreachable(self):
        engine = _make_ollama_engine()
        client = TestClient(_app(engine, engine_name="ollama"))

        import httpx

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

            resp = client.post("/v1/models/pull", json={"model": "foo"})

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Model delete endpoint
# ---------------------------------------------------------------------------


class TestModelDelete:
    def test_delete_rejects_non_ollama(self):
        engine = _make_engine(engine_id="vllm")
        client = TestClient(_app(engine, engine_name="vllm"))
        resp = client.delete("/v1/models/test-model")
        assert resp.status_code == 501

    def test_delete_success(self):
        engine = _make_ollama_engine()
        client = TestClient(_app(engine, engine_name="ollama"))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.request = AsyncMock(return_value=mock_resp)

            resp = client.delete("/v1/models/qwen3:0.6b")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["model"] == "qwen3:0.6b"
        instance.request.assert_awaited_once_with(
            "DELETE",
            "/api/delete",
            json={"name": "qwen3:0.6b"},
        )


# ---------------------------------------------------------------------------
# Streaming resilience
# ---------------------------------------------------------------------------


class TestStreamingResilience:
    """Verify streaming handles errors gracefully."""

    def test_stream_error_returns_error_chunk(self):
        """When the engine raises during streaming, error is sent as content."""
        engine = _make_engine()

        async def failing_stream(messages, *, model, **kw):
            yield "partial"
            raise RuntimeError("model not found")

        engine.stream = failing_stream
        app = create_app(engine, "test-model")
        client = TestClient(app)

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "bad-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert resp.status_code == 200

        # Should contain partial content + error message + [DONE]
        text = resp.text
        assert "partial" in text
        assert "model not found" in text
        assert "[DONE]" in text

    def test_stream_tokens_arrive(self):
        """Verify tokens stream through correctly (not batched)."""
        engine = _make_engine()
        app = create_app(engine, "test-model")
        client = TestClient(app)

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert resp.status_code == 200

        # Collect tokens
        tokens = []
        for line in resp.text.strip().split("\n"):
            if line.startswith("data:") and "[DONE]" not in line:
                data = json.loads(line[5:].strip())
                content = data.get("choices", [{}])[0].get("delta", {}).get("content")
                if content:
                    tokens.append(content)

        assert tokens == ["Hello", " ", "world"]

    def test_stream_without_agent_uses_direct_engine(self):
        """When no tools in request, streaming should use engine.stream directly
        even if an agent is configured (for real token-by-token output)."""
        from openjarvis.agents._stubs import AgentResult

        engine = _make_engine()
        agent = MagicMock()
        agent.agent_id = "simple"
        agent._tools = []
        agent.run.return_value = AgentResult(
            content="agent response",
            turns=1,
        )

        app = create_app(engine, "test-model", agent=agent)
        client = TestClient(app)

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                # No tools — should use direct engine stream
            },
        )
        assert resp.status_code == 200

        # Should get engine tokens, not agent response
        tokens = []
        for line in resp.text.strip().split("\n"):
            if line.startswith("data:") and "[DONE]" not in line:
                data = json.loads(line[5:].strip())
                content = data.get("choices", [{}])[0].get("delta", {}).get("content")
                if content:
                    tokens.append(content)

        assert "".join(tokens) == "Hello world"
        # Agent.run should NOT have been called
        agent.run.assert_not_called()


# ---------------------------------------------------------------------------
# Models endpoint
# ---------------------------------------------------------------------------


class TestModelsEndpointExtended:
    def test_models_list_multiple(self):
        engine = _make_engine(
            models=["qwen3.5:4b", "qwen3.5:9b", "qwen3:0.6b"],
        )
        app = create_app(engine, "qwen3.5:4b")
        client = TestClient(app)
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()["data"]]
        assert "qwen3.5:4b" in ids
        assert "qwen3.5:9b" in ids
        assert "qwen3:0.6b" in ids

    def test_models_list_filters_embedding_only_models(self):
        engine = _make_engine(
            models=["nomic-embed-text", "all-minilm:latest", "qwen3.5:4b"],
        )
        client = TestClient(create_app(engine, "qwen3.5:4b"))

        resp = client.get("/v1/models")

        assert resp.status_code == 200
        assert [m["id"] for m in resp.json()["data"]] == ["qwen3.5:4b"]

    def test_models_list_returns_empty_when_only_embedders_are_installed(self):
        engine = _make_engine(
            models=["nomic-embed-text", "hf.co/BAAI/bge-m3:latest"],
        )
        client = TestClient(create_app(engine, "nomic-embed-text"))

        resp = client.get("/v1/models")

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_models_empty_engine(self):
        """When engine.list_models() returns empty, endpoint still succeeds."""
        engine = _make_engine(models=[])
        app = create_app(engine, "test-model")
        client = TestClient(app)
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        # The endpoint returns whatever list_models() gives
        assert resp.json()["object"] == "list"

    def test_models_list_offloads_engine_list_models(self):
        engine = _make_engine(models=["qwen3.5:4b"])
        app = create_app(engine, "qwen3.5:4b")
        client = TestClient(app)

        with patch(
            "openjarvis.server.routes.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as mock_to_thread:

            async def _fake_to_thread(fn, *args, **kwargs):
                # Only the engine listing yields model ids; pool/gateway
                # helpers return empty rows under this mock.
                if fn == engine.list_models:
                    return ["qwen3.5:4b"]
                return []

            mock_to_thread.side_effect = _fake_to_thread
            resp = client.get("/v1/models")

        assert resp.status_code == 200
        assert [m["id"] for m in resp.json()["data"]] == ["qwen3.5:4b"]
        # The engine listing still runs off the event loop, as the first await.
        assert mock_to_thread.await_args_list[0].args[0] == engine.list_models

    def test_models_list_includes_free_pool_candidates(self):
        """Concrete free-pool candidates appear beside the stable aliases.

        ``FreePoolEngine.list_models()`` only advertises the ``free/*`` and
        ``local/*`` aliases, but ``generate()`` also routes concrete candidate
        ids (raw local Ollama models). The picker must show them too, owned by
        their engine key — while embed-only models stay hidden.
        """
        from openjarvis.intelligence.free_pool import FreePoolEngine

        local = _make_ollama_engine(
            models=["qwen3-8b:latest", "all-minilm:latest", "nomic-embed-text"],
        )
        local.is_cloud = False
        pool = FreePoolEngine([("ollama", local)], allow_remote=False)
        client = TestClient(create_app(pool, "local/fast"))

        resp = client.get("/v1/models")

        assert resp.status_code == 200
        data = resp.json()["data"]
        ids = [m["id"] for m in data]

        # Stable aliases from pool.list_models() come first...
        assert "local/fast" in ids
        assert "free/auto" in ids
        # ...then the concrete local candidate models...
        assert "qwen3-8b:latest" in ids
        assert ids.index("local/fast") < ids.index("qwen3-8b:latest")

        owned = {m["id"]: m["owned_by"] for m in data}
        assert owned["qwen3-8b:latest"] == "ollama"
        assert owned["local/fast"] == "openjarvis"

        # Embed-only models stay out of the chat picker.
        assert "nomic-embed-text" not in ids
        assert "all-minilm:latest" not in ids

    def test_models_list_includes_engine_gateway_candidates(self):
        """Remote free-gateway candidates join the picker under their prefix.

        ``kilo/*``/``opencode/*`` ids must not be dropped by the direct-cloud
        filter: they resolve through their registered engines (verified by
        the cloud_router provider exemption), so the picker shows them with
        their engine key as owner.
        """
        from openjarvis.intelligence.free_pool import FreePoolEngine
        from openjarvis.engine._stubs import InferenceEngine

        class _KiloStub(InferenceEngine):
            engine_id = "kilogateway"
            is_cloud = True

            def __init__(self) -> None:
                self._free = [
                    "kilo/nvidia/nemotron-3.5-lightning:free",
                    "kilo/kilo-auto/free",
                ]

            def generate(self, messages, *, model, **kwargs):
                return {"content": "ok", "model": model, "usage": {}}

            async def stream(self, messages, *, model, **kwargs):
                yield "ok"

            def list_models(self):
                return list(self._free)

            def health(self):
                return True

            def list_free_model_ids(self):
                return list(self._free)

            def list_model_metadata(self):
                return [
                    {"id": model_id, "context_length": 131_072}
                    for model_id in self._free
                ]

        pool = FreePoolEngine([("kilogateway", _KiloStub())], allow_remote=True)
        client = TestClient(create_app(pool, "local/fast"))

        resp = client.get("/v1/models")

        assert resp.status_code == 200
        data = resp.json()["data"]
        ids = [m["id"] for m in data]

        assert "kilo/nvidia/nemotron-3.5-lightning:free" in ids
        assert "free/auto" in ids
        # Remote gateway rows come after the stable aliases.
        assert ids.index("free/auto") < ids.index("kilo/nvidia/nemotron-3.5-lightning:free")

        owned = {m["id"]: m["owned_by"] for m in data}
        assert owned["kilo/nvidia/nemotron-3.5-lightning:free"] == "kilogateway"

    def test_chat_routes_gateway_model_as_public_tier(self):
        """kilo/* bypasses the private gate and reaches its engine verbatim.

        The public free tier never receives injected memory/identity
        context; the explicit model selection is the per-task opt-in.
        """
        from openjarvis.core.config import JarvisConfig
        from openjarvis.engine.multi import MultiEngine

        cfg = JarvisConfig()
        cfg.intelligence.private_routing = True
        cfg.intelligence.allow_private_remote = False

        kilo = _make_engine(models=["kilo/kilo-auto/free"])
        kilo.can_serve.side_effect = lambda m: m.startswith("kilo/")
        kilo.generate.return_value = {
            "content": "K",
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
            "model": "kilo/kilo-auto/free",
            "finish_reason": "stop",
        }
        router = MultiEngine([("kilogateway", kilo)])

        engine = _make_engine(models=["free/auto"])
        engine.can_serve.return_value = False  # private pool: local only
        app = create_app(engine, "local/fast", config=cfg, router_engine=router)
        client = TestClient(app)

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "kilo/kilo-auto/free",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 16,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "K"
        kilo.generate.assert_called_once()
        sent_messages = kilo.generate.call_args.args[0]
        # No identity/memory system message was folded into the relay.
        assert len(sent_messages) == 1
        assert str(getattr(sent_messages[0], "role", "")).lower().endswith("user")

    def test_chat_private_gate_still_blocks_unknown_remote(self):
        """Non-gateway remote ids keep failing closed under private routing."""
        from openjarvis.core.config import JarvisConfig

        cfg = JarvisConfig()
        cfg.intelligence.private_routing = True
        cfg.intelligence.allow_private_remote = False

        engine = _make_engine(models=["free/auto"])
        engine.can_serve.return_value = False
        app = create_app(engine, "local/fast", config=cfg)
        client = TestClient(app)

        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "mystery/remote-model",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 16,
            },
        )

        assert resp.status_code == 400
        assert "local model" in resp.json()["detail"].lower()
        engine.generate.assert_not_called()

    def test_models_list_shows_gateway_rows_under_private_routing(self):
        """Gateway rows survive the private-pool wrap via the router engine."""
        from openjarvis.core.config import JarvisConfig
        from openjarvis.engine.multi import MultiEngine

        cfg = JarvisConfig()
        cfg.intelligence.private_routing = True

        kilo = _make_engine(models=["kilo/kilo-auto/free"])
        kilo.list_models.return_value = ["kilo/kilo-auto/free"]
        oc = _make_engine(models=["opencode/mimo-v2.6-flash-free"])
        oc.list_models.return_value = ["opencode/mimo-v2.6-flash-free"]
        router = MultiEngine([("kilogateway", kilo), ("opencode", oc)])

        engine = _make_engine(models=["free/auto"])
        app = create_app(engine, "local/fast", config=cfg, router_engine=router)
        client = TestClient(app)

        resp = client.get("/v1/models")

        assert resp.status_code == 200
        owned = {m["id"]: m["owned_by"] for m in resp.json()["data"]}
        assert owned["kilo/kilo-auto/free"] == "kilogateway"
        assert owned["opencode/mimo-v2.6-flash-free"] == "opencode"
