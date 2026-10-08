"""Tests for the native NaraRouter engine."""

from __future__ import annotations

import httpx
import pytest
import respx

from openjarvis.core.config import JarvisConfig
from openjarvis.engine._discovery import _make_engine
from openjarvis.engine.nararouter import NaraRouterEngine


class TestNaraRouterEngine:
    def test_engine_identity(self) -> None:
        assert NaraRouterEngine.engine_id == "nararouter"
        assert NaraRouterEngine.is_cloud is True

    def test_host_strips_trailing_v1(self) -> None:
        engine = NaraRouterEngine(host="https://router.example/v1/", api_key="secret")
        assert engine._host == "https://router.example"

    def test_without_key_does_not_probe(self) -> None:
        engine = NaraRouterEngine(host="https://router.example")
        assert engine.health() is False
        assert engine.list_models() == []
        assert engine.list_model_metadata() == []

    def test_live_roster_uses_bearer_auth(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARAROUTER_API_KEY", "nara-test")
        engine = NaraRouterEngine(host="https://router.example", free_only=False)
        with respx.mock:
            route = respx.get("https://router.example/v1/models").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "model-a", "context_length": 262144},
                            {"id": "model-b", "vision": True},
                        ]
                    },
                )
            )
            assert engine.list_models() == ["model-a", "model-b"]
            metadata = engine.list_model_metadata()

        assert route.calls.last.request.headers["Authorization"] == "Bearer nara-test"
        assert metadata[0]["context_length"] == 262144
        assert metadata[1]["vision"] is True

    def test_free_roster_uses_positive_evidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARAROUTER_API_KEY", "nara-test")
        engine = NaraRouterEngine(host="https://router.example")
        with respx.mock:
            respx.get("https://router.example/v1/models").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "paid-model", "pricing": {"input": 1, "output": 2}},
                            {"id": "nemotron-super-free"},
                            {
                                "id": "bonus-model",
                                "official_savings": "100% off",
                            },
                            {
                                "id": "zero-priced",
                                "pricing": {"input": 0, "output": 0},
                            },
                        ]
                    },
                )
            )
            free_ids = engine.list_free_model_ids()

        assert free_ids == [
            "nemotron-super-free",
            "bonus-model",
            "zero-priced",
        ]

    def test_default_model_listing_is_free_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARAROUTER_API_KEY", "nara-test")
        engine = NaraRouterEngine(host="https://router.example")
        with respx.mock:
            respx.get("https://router.example/v1/models").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "free-model"},
                            {"id": "paid-model"},
                        ]
                    },
                )
            )
            respx.get("https://router.example/api/plans").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "plans": [
                            {
                                "name": "Free",
                                "models": [{"id": "free-model"}],
                            },
                            {
                                "name": "Pro",
                                "models": [{"id": "paid-model"}],
                            },
                        ]
                    },
                )
            )
            assert engine.list_models() == ["free-model"]

    def test_public_free_plan_is_intersected_with_entitlements(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARAROUTER_API_KEY", "nara-test")
        engine = NaraRouterEngine(host="https://router.example")
        with respx.mock:
            respx.get("https://router.example/v1/models").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "data": [
                            {"id": "agnes-3-flash"},
                            {"id": "paid-model"},
                        ]
                    },
                )
            )
            respx.get("https://router.example/api/plans").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "plans": [
                            {
                                "name": "Free",
                                "models": [
                                    {"id": "agnes-3-flash"},
                                    {"id": "not-entitled"},
                                ],
                            },
                            {
                                "name": "Pro",
                                "models": [{"id": "paid-model"}],
                            },
                        ]
                    },
                )
            )
            free_ids = engine.list_free_model_ids()

        assert free_ids == ["agnes-3-flash"]

    def test_discovery_uses_configured_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NARAROUTER_API_KEY", "nara-test")
        config = JarvisConfig()
        config.engine.nararouter.host = "https://custom-router.example/v1"
        engine = _make_engine("nararouter", config)
        assert isinstance(engine, NaraRouterEngine)
        assert engine._host == "https://custom-router.example"

    def test_discovery_preserves_class_identity_after_registry_clear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from openjarvis.core.registry import EngineRegistry

        monkeypatch.setenv("NARAROUTER_API_KEY", "nara-test")
        EngineRegistry.clear()
        engine = _make_engine("nararouter", JarvisConfig())
        assert type(engine) is NaraRouterEngine
        assert EngineRegistry.get("nararouter") is NaraRouterEngine
