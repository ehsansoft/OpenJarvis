"""Tests for the keyless Kilo Gateway engine."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from openjarvis.core.config import JarvisConfig
from openjarvis.core.types import Message, Role
from openjarvis.engine._discovery import _make_engine
from openjarvis.engine.kilogateway import KiloGatewayEngine

_HOST = "https://gateway.example"

_ROSTER = {
    "data": [
        {"id": "nvidia/nemotron-3.5-lightning:free", "context_length": 131072},
        {"id": "kilo-auto/free"},
        {"id": "anthropic/claude-opus-5"},
        {"id": "stepfun/step-5-preview-free"},
    ]
}


class TestKiloGatewayEngine:
    def test_engine_identity(self) -> None:
        assert KiloGatewayEngine.engine_id == "kilogateway"
        assert KiloGatewayEngine.is_cloud is True
        # The gateway serves /models and /chat/completions at its root.
        assert KiloGatewayEngine._api_prefix == ""

    @respx.mock
    def test_health_is_keyless(self) -> None:
        route = respx.get(f"{_HOST}/models").mock(
            return_value=httpx.Response(200, json=_ROSTER)
        )
        engine = KiloGatewayEngine(host=_HOST)

        assert engine.health() is True
        headers = {k.lower() for k in route.calls.last.request.headers}
        assert "authorization" not in headers

    @respx.mock
    def test_health_false_on_connect_error(self) -> None:
        respx.get(f"{_HOST}/models").mock(
            side_effect=httpx.ConnectError("refused")
        )
        engine = KiloGatewayEngine(host=_HOST)
        assert engine.health() is False

    @respx.mock
    def test_free_roster_is_filtered_and_prefixed(self) -> None:
        route = respx.get(f"{_HOST}/models").mock(
            return_value=httpx.Response(200, json=_ROSTER)
        )
        engine = KiloGatewayEngine(host=_HOST)

        free_ids = engine.list_free_model_ids()
        # Paid models are excluded; free ids gain the engine prefix that
        # keeps multi-slash ids away from the OpenRouter heuristic.
        assert free_ids == [
            "kilo/nvidia/nemotron-3.5-lightning:free",
            "kilo/kilo-auto/free",
            "kilo/stepfun/step-5-preview-free",
        ]

        # Repeated lookups hit the TTL cache instead of the network.
        assert engine.can_serve("kilo/nvidia/nemotron-3.5-lightning:free") is True
        assert engine.can_serve("kilo/anthropic/claude-opus-5") is False
        assert engine.can_serve("qwen3-8b") is False
        assert engine.list_models() == free_ids
        assert route.call_count == 1

    @respx.mock
    def test_metadata_keeps_context_for_pool_ranking(self) -> None:
        respx.get(f"{_HOST}/models").mock(
            return_value=httpx.Response(200, json=_ROSTER)
        )
        engine = KiloGatewayEngine(host=_HOST)

        metadata = {item["id"]: item for item in engine.list_model_metadata()}
        assert metadata["kilo/nvidia/nemotron-3.5-lightning:free"][
            "context_length"
        ] == 131072
        assert "kilo/anthropic/claude-opus-5" not in metadata

    @respx.mock
    def test_generate_strips_prefix_on_the_wire(self) -> None:
        route = respx.post(f"{_HOST}/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "ok"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1},
                },
            )
        )
        engine = KiloGatewayEngine(host=_HOST)

        result = engine.generate(
            [Message(role=Role.USER, content="hi")],
            model="kilo/nvidia/nemotron-3.5-lightning:free",
        )

        payload = json.loads(route.calls.last.request.content)
        assert payload["model"] == "nvidia/nemotron-3.5-lightning:free"
        assert result["content"] == "ok"

    @respx.mock
    def test_unprefixed_wire_model_id_is_untouched(self) -> None:
        route = respx.post(f"{_HOST}/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "ok"}, "finish_reason": "stop"}
                    ],
                    "usage": {},
                },
            )
        )
        engine = KiloGatewayEngine(host=_HOST, free_only=False)

        engine.generate(
            [Message(role=Role.USER, content="hi")],
            model="nvidia/nemotron-3.5-lightning:free",
        )

        payload = json.loads(route.calls.last.request.content)
        assert payload["model"] == "nvidia/nemotron-3.5-lightning:free"

    def test_make_engine_reads_config(self) -> None:
        config = JarvisConfig()
        config.engine.kilogateway.host = "https://gw.example"
        config.engine.kilogateway.free_only = False

        engine = _make_engine("kilogateway", config)

        assert isinstance(engine, KiloGatewayEngine)
        assert engine._host == "https://gw.example"
        assert engine._free_only is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
