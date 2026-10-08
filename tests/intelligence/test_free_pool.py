"""Tests for the zero-API-cost model pool."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest

from openjarvis.core.types import Message
from openjarvis.engine._base import InferenceEngine
from openjarvis.engine._stubs import StreamChunk
from openjarvis.intelligence.free_pool import (
    FreePoolEngine,
    collect_free_models,
    rank_free_models,
)


class _FakeEngine(InferenceEngine):
    def __init__(
        self,
        models: list[str],
        *,
        is_cloud: bool = False,
        free_ids: list[str] | None = None,
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        self._models = models
        self.is_cloud = is_cloud
        self._free_ids = free_ids or []
        self._metadata = metadata or []

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"content": model, "model": model, "usage": {}}

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        yield model

    def list_models(self) -> list[str]:
        return list(self._models)

    def health(self) -> bool:
        return True

    def list_free_model_ids(self) -> list[str]:
        return list(self._free_ids)

    def list_model_metadata(self) -> list[dict[str, Any]]:
        return list(self._metadata)


def test_collects_all_local_models_as_zero_api_cost() -> None:
    local = _FakeEngine(["qwen3:4b", "qwen2.5-coder:7b"])
    candidates = collect_free_models([("ollama", local)])
    assert {item.model_id for item in candidates} == {
        "qwen3:4b",
        "qwen2.5-coder:7b",
    }
    assert all(item.local for item in candidates)


def test_public_nim_endpoint_is_not_treated_as_zero_api_cost() -> None:
    nim = _FakeEngine(["nvidia/model"])
    nim._host = "https://integrate.api.nvidia.com"
    assert collect_free_models([("nim", nim)]) == []


def test_private_self_hosted_nim_can_join_local_pool() -> None:
    nim = _FakeEngine(["self-hosted/model"])
    nim._host = "http://127.0.0.1:8001"
    candidates = collect_free_models([("nim", nim)])
    assert [item.model_id for item in candidates] == ["self-hosted/model"]
    assert candidates[0].local is True


def test_collects_only_explicit_nara_free_models() -> None:
    nara = _FakeEngine(
        ["paid-model", "nemotron-3-super-free"],
        is_cloud=True,
        free_ids=["nemotron-3-super-free"],
        metadata=[
            {"id": "paid-model", "context_length": 32_000},
            {
                "id": "nemotron-3-super-free",
                "context_length": 262_144,
                "reasoning": True,
            },
        ],
    )
    candidates = collect_free_models([("nararouter", nara)])
    assert [item.model_id for item in candidates] == ["nemotron-3-super-free"]
    assert "reasoning" in candidates[0].capabilities


def test_vision_alias_excludes_text_only_models() -> None:
    local = _FakeEngine(["qwen3:4b"])
    candidates = collect_free_models([("ollama", local)])
    ranked = rank_free_models(candidates, "vision")
    assert ranked == []


def test_local_first_beats_remote_specialist_by_default() -> None:
    local = _FakeEngine(["qwen3:4b"])
    remote = _FakeEngine(
        ["remote-coder-free"],
        is_cloud=True,
        free_ids=["remote-coder-free"],
        metadata=[{"id": "remote-coder-free"}],
    )
    candidates = collect_free_models(
        [("ollama", local), ("nararouter", remote)]
    )
    ranked = rank_free_models(candidates, "code", prefer_local=True)
    assert ranked[0].engine_key == "ollama"


def test_research_alias_prefers_free_long_context_remote() -> None:
    local = _FakeEngine(["qwen2.5-coder:7b"])
    remote = _FakeEngine(
        ["nemotron-long-free"],
        is_cloud=True,
        free_ids=["nemotron-long-free"],
        metadata=[
            {
                "id": "nemotron-long-free",
                "context_window": 1_000_000,
                "reasoning": True,
            }
        ],
    )
    pool = FreePoolEngine(
        [("ollama", local), ("nararouter", remote)],
        prefer_local=True,
    )

    result = pool.generate([], model="free/research")

    assert result["routing"]["selected_engine"] == "nararouter"
    assert result["routing"]["selected_model"] == "nemotron-long-free"


def test_code_routing_prefers_local_coder() -> None:
    local = _FakeEngine(["qwen3:4b", "qwen2.5-coder:7b"])
    candidates = collect_free_models([("ollama", local)])
    ranked = rank_free_models(candidates, "code")
    assert ranked[0].model_id == "qwen2.5-coder:7b"


@pytest.mark.asyncio
async def test_rich_stream_preserves_tool_calls() -> None:
    class _ToolEngine(_FakeEngine):
        async def stream_full(
            self,
            messages: Sequence[Message],
            *,
            model: str,
            **kwargs: Any,
        ) -> AsyncIterator[StreamChunk]:
            yield StreamChunk(
                tool_calls=[
                    {
                        "index": 0,
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path":"README.md"}',
                        },
                    }
                ]
            )
            yield StreamChunk(finish_reason="tool_calls")

    local = _ToolEngine(["qwen2.5-coder:7b"])
    pool = FreePoolEngine([("ollama", local)])
    chunks = [
        chunk
        async for chunk in pool.stream_full(
            [],
            model="free/code",
            tools=[
                {
                    "type": "function",
                    "function": {"name": "read_file"},
                }
            ],
        )
    ]

    assert chunks[0].tool_calls is not None
    assert chunks[0].tool_calls[0]["function"]["name"] == "read_file"
    assert chunks[-1].finish_reason == "tool_calls"


def test_virtual_alias_routes_and_records_selection() -> None:
    local = _FakeEngine(["qwen2.5-coder:7b"])
    pool = FreePoolEngine([("ollama", local)])
    result = pool.generate([], model="free/code")
    assert result["content"] == "qwen2.5-coder:7b"
    assert result["routing"]["requested_model"] == "free/code"
    assert result["routing"]["selected_engine"] == "ollama"
