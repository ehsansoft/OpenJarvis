"""Cost-free model pool spanning local engines and NaraRouter.

The pool treats local inference backends as zero API-cost and only admits remote
models when a provider can positively identify them as free. It exposes stable
virtual aliases (free/auto, free/code, free/research, free/vision, free/fast)
so editor integrations do not need to chase rotating provider model IDs.
"""

from __future__ import annotations

import ipaddress
import logging
import time
from urllib.parse import urlparse
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from openjarvis.core.types import Message
from openjarvis.engine._base import EngineConnectionError, InferenceEngine
from openjarvis.engine._stubs import StreamChunk

logger = logging.getLogger(__name__)

VIRTUAL_ALIASES = (
    "free/auto",
    "free/code",
    "free/research",
    "free/vision",
    "free/fast",
)


@dataclass(slots=True)
class FreeModelCandidate:
    """One zero-API-cost model that can participate in the pool."""

    model_id: str
    engine_key: str
    engine: InferenceEngine = field(repr=False)
    local: bool = True
    reason: str = "local"
    context_length: int = 0
    capabilities: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "engine": self.engine_key,
            "local": self.local,
            "reason": self.reason,
            "context_length": self.context_length,
            "capabilities": sorted(self.capabilities),
            "metadata": self.metadata,
        }


_LOCAL_ENGINE_KEYS = frozenset(
    {
        "ollama",
        "llamacpp",
        "vllm",
        "sglang",
        "mlx",
        "lmstudio",
        "exo",
        "nexa",
        "uzu",
        "lemonade",
        "gemma_cpp",
        "apple_fm",
        "afm",
    }
)


def _host_is_local_or_private(raw_host: str) -> bool:
    try:
        parsed = urlparse(
            raw_host if "://" in raw_host else f"http://{raw_host}"
        )
        hostname = parsed.hostname or ""
    except ValueError:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
    )


def _is_zero_api_local_engine(
    engine_key: str,
    engine: InferenceEngine,
) -> bool:
    """Return true only when an engine is clearly local/private.

    Some engines, notably NVIDIA NIM, inherit is_cloud=False even when
    their default host is a public SaaS endpoint. The free pool therefore
    cannot use not-is-cloud as proof of zero API cost.
    """
    if bool(getattr(engine, "is_cloud", False)):
        return False

    raw_host = (
        getattr(engine, "_host", "")
        or getattr(engine, "host", "")
        or ""
    )
    if isinstance(raw_host, str) and raw_host.strip():
        return _host_is_local_or_private(raw_host.strip())

    return engine_key in _LOCAL_ENGINE_KEYS

def _truthy_metadata(metadata: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = metadata.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.lower() in {
            "true",
            "yes",
            "supported",
            "enabled",
        }:
            return True
    return False


def _context_length(metadata: dict[str, Any]) -> int:
    for key in (
        "context_length",
        "max_context",
        "max_context_length",
        "context_window",
    ):
        value = metadata.get(key)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def infer_capabilities(model_id: str, metadata: dict[str, Any]) -> set[str]:
    """Infer coarse capabilities from provider metadata and model names."""
    lowered = model_id.lower()
    caps = {"text"}

    if _truthy_metadata(metadata, "vision", "supports_vision", "multimodal"):
        caps.add("vision")
    if any(tag in lowered for tag in ("vision", "-vl", "_vl", "multimodal")):
        caps.add("vision")

    if _truthy_metadata(metadata, "reasoning", "supports_reasoning", "thinking"):
        caps.add("reasoning")
    if any(
        tag in lowered
        for tag in ("reason", "thinking", "deepseek-r1", "qwq", "nemotron")
    ):
        caps.add("reasoning")

    if _truthy_metadata(metadata, "tools", "tool_use", "supports_tools"):
        caps.add("tools")

    if any(tag in lowered for tag in ("code", "coder", "codestral", "devstral")):
        caps.add("code")

    context = _context_length(metadata)
    if context >= 131_072:
        caps.add("long-context")
    if context >= 500_000:
        caps.add("very-long-context")
    return caps


def _nara_candidates(
    engine_key: str,
    engine: InferenceEngine,
) -> list[FreeModelCandidate]:
    free_method = getattr(engine, "list_free_model_ids", None)
    metadata_method = getattr(engine, "list_model_metadata", None)
    if not callable(free_method):
        return []

    try:
        free_ids = set(free_method())
    except Exception as exc:
        logger.debug("NaraRouter free roster discovery failed: %s", exc)
        return []
    if not free_ids:
        return []

    raw_metadata: list[dict[str, Any]] = []
    if callable(metadata_method):
        try:
            raw_metadata = metadata_method()
        except Exception as exc:
            logger.debug("NaraRouter metadata discovery failed: %s", exc)

    metadata_by_id = {
        str(item.get("id")): item
        for item in raw_metadata
        if isinstance(item, dict) and item.get("id")
    }

    candidates = []
    for model_id in sorted(free_ids):
        metadata = dict(metadata_by_id.get(model_id, {}))
        candidates.append(
            FreeModelCandidate(
                model_id=model_id,
                engine_key=engine_key,
                engine=engine,
                local=False,
                reason="provider-free-plan",
                context_length=_context_length(metadata),
                capabilities=infer_capabilities(model_id, metadata),
                metadata=metadata,
            )
        )
    return candidates


def collect_free_models(
    engines: Sequence[tuple[str, InferenceEngine]],
) -> list[FreeModelCandidate]:
    """Collect all zero-API-cost models from healthy engine instances."""
    candidates: list[FreeModelCandidate] = []
    seen: set[tuple[str, str]] = set()

    for engine_key, engine in engines:
        if engine_key == "nararouter":
            discovered = _nara_candidates(engine_key, engine)
        elif _is_zero_api_local_engine(engine_key, engine):
            try:
                model_ids = engine.list_models()
            except Exception as exc:
                logger.debug("Failed listing local models for %s: %s", engine_key, exc)
                continue
            discovered = [
                FreeModelCandidate(
                    model_id=model_id,
                    engine_key=engine_key,
                    engine=engine,
                    local=True,
                    reason="local-no-api-cost",
                    capabilities=infer_capabilities(model_id, {}),
                )
                for model_id in model_ids
            ]
        else:
            discovered = []

        for candidate in discovered:
            key = (candidate.engine_key, candidate.model_id)
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)

    candidates.sort(key=lambda item: (not item.local, item.engine_key, item.model_id))
    return candidates


def _score_candidate(
    candidate: FreeModelCandidate,
    task: str,
    *,
    prefer_local: bool,
) -> tuple[int, int, int, str]:
    score = 0
    caps = candidate.capabilities

    if task == "vision":
        if "vision" not in caps:
            return (-10_000, 0, 0, candidate.model_id)
        score += 100
    elif task == "code":
        score += 80 if "code" in caps else 0
        score += 20 if "reasoning" in caps else 0
    elif task == "research":
        score += 50 if "long-context" in caps else 0
        score += 30 if "very-long-context" in caps else 0
        score += 30 if "reasoning" in caps else 0
    elif task == "fast":
        score += 30 if candidate.local else 10
        score -= min(candidate.context_length // 100_000, 10)
    else:
        score += 15 if "reasoning" in caps else 0
        score += 10 if "long-context" in caps else 0

    local_priority = 1 if prefer_local and candidate.local else 0
    return (
        local_priority,
        score,
        candidate.context_length,
        candidate.model_id,
    )


def rank_free_models(
    candidates: Sequence[FreeModelCandidate],
    task: str = "auto",
    *,
    prefer_local: bool = True,
    allow_remote: bool = True,
) -> list[FreeModelCandidate]:
    """Rank free candidates for a task, with deterministic local-first policy."""
    filtered = [
        candidate
        for candidate in candidates
        if allow_remote or candidate.local
    ]
    if task == "vision":
        filtered = [
            candidate
            for candidate in filtered
            if "vision" in candidate.capabilities
        ]
    return sorted(
        filtered,
        key=lambda candidate: _score_candidate(
            candidate, task, prefer_local=prefer_local
        ),
        reverse=True,
    )


class FreePoolEngine(InferenceEngine):
    """Virtual inference engine that routes stable free/* aliases with failover."""

    engine_id = "free-pool"

    def __init__(
        self,
        engines: Sequence[tuple[str, InferenceEngine]],
        *,
        prefer_local: bool = True,
        allow_remote: bool = True,
        refresh_interval_seconds: float = 300.0,
    ) -> None:
        self._engines = list(engines)
        self._prefer_local = prefer_local
        self._allow_remote = allow_remote
        self._refresh_interval = max(0.0, refresh_interval_seconds)
        self._last_refresh = 0.0
        self._candidates: list[FreeModelCandidate] = []
        self._direct: dict[str, FreeModelCandidate] = {}
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> None:
        """Refresh local and remote free rosters after the configured TTL."""
        now = time.monotonic()
        if (
            not force
            and self._candidates
            and now - self._last_refresh < self._refresh_interval
        ):
            return
        candidates = collect_free_models(self._engines)
        direct: dict[str, FreeModelCandidate] = {}
        for candidate in candidates:
            # First candidate wins collisions; collection sorts local first.
            direct.setdefault(candidate.model_id, candidate)
        self._candidates = candidates
        self._direct = direct
        self._last_refresh = now

    @property
    def candidates(self) -> list[FreeModelCandidate]:
        self.refresh()
        return list(self._candidates)

    def _task_for_alias(self, model: str) -> str:
        if not model.startswith("free/"):
            return "auto"
        task = model.split("/", 1)[1]
        valid = {"auto", "code", "research", "vision", "fast"}
        return task if task in valid else "auto"

    def _choices(self, model: str) -> list[FreeModelCandidate]:
        self.refresh()
        if model in self._direct:
            return [self._direct[model]]
        if model not in VIRTUAL_ALIASES:
            return []
        return rank_free_models(
            self._candidates,
            self._task_for_alias(model),
            prefer_local=self._prefer_local,
            allow_remote=self._allow_remote,
        )

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> dict[str, Any]:
        choices = self._choices(model)
        if not choices:
            raise EngineConnectionError(f"No free model is available for {model!r}")

        errors: list[str] = []
        for candidate in choices:
            try:
                result = candidate.engine.generate(
                    messages,
                    model=candidate.model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                result.setdefault("routing", {})
                result["routing"].update(
                    {
                        "requested_model": model,
                        "selected_model": candidate.model_id,
                        "selected_engine": candidate.engine_key,
                        "free_reason": candidate.reason,
                    }
                )
                return result
            except Exception as exc:
                errors.append(f"{candidate.engine_key}/{candidate.model_id}: {exc}")
                logger.warning(
                    "Free model candidate failed (%s/%s): %s",
                    candidate.engine_key,
                    candidate.model_id,
                    exc,
                )

        raise EngineConnectionError(
            "All free model candidates failed: " + "; ".join(errors[-5:])
        )

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        choices = self._choices(model)
        if not choices:
            raise EngineConnectionError(f"No free model is available for {model!r}")

        errors: list[str] = []
        for candidate in choices:
            emitted = False
            try:
                async for token in candidate.engine.stream(
                    messages,
                    model=candidate.model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ):
                    emitted = True
                    yield token
                return
            except Exception as exc:
                if emitted:
                    raise
                errors.append(f"{candidate.engine_key}/{candidate.model_id}: {exc}")
                logger.warning(
                    "Free streaming candidate failed before first token "
                    "(%s/%s): %s",
                    candidate.engine_key,
                    candidate.model_id,
                    exc,
                )

        raise EngineConnectionError(
            "All free streaming candidates failed: " + "; ".join(errors[-5:])
        )

    async def stream_full(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Delegate rich streaming so editor tool calls survive free routing."""
        choices = self._choices(model)
        if not choices:
            raise EngineConnectionError(f"No free model is available for {model!r}")

        errors: list[str] = []
        for candidate in choices:
            emitted = False
            try:
                async for chunk in candidate.engine.stream_full(
                    messages,
                    model=candidate.model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ):
                    if (
                        chunk.content
                        or chunk.tool_calls
                        or chunk.finish_reason
                        or chunk.usage
                    ):
                        emitted = True
                    yield chunk
                return
            except Exception as exc:
                if emitted:
                    raise
                errors.append(
                    f"{candidate.engine_key}/{candidate.model_id}: {exc}"
                )
                logger.warning(
                    "Free rich-stream candidate failed before first chunk "
                    "(%s/%s): %s",
                    candidate.engine_key,
                    candidate.model_id,
                    exc,
                )

        raise EngineConnectionError(
            "All free rich-stream candidates failed: "
            + "; ".join(errors[-5:])
        )

    def list_models(self) -> list[str]:
        self.refresh()
        # Expose only stable aliases so this virtual engine never shadows
        # concrete model IDs owned by Ollama/NaraRouter in MultiEngine.
        return list(VIRTUAL_ALIASES) if self._candidates else []

    def health(self) -> bool:
        self.refresh()
        return bool(self._candidates)

    def close(self) -> None:
        # Underlying engines are owned by the caller/discovery layer.
        return None


__all__ = [
    "FreeModelCandidate",
    "FreePoolEngine",
    "VIRTUAL_ALIASES",
    "collect_free_models",
    "infer_capabilities",
    "rank_free_models",
]
