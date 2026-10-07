"""NaraRouter inference engine.

NaraRouter exposes an OpenAI-compatible API but is intentionally kept as a
first-class engine instead of being hidden behind the generic LiteLLM adapter.
That gives OpenJarvis a stable place for account-aware model discovery and
future Nara-specific routing metadata while keeping API credentials out of
configuration files.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from openjarvis.core.registry import EngineRegistry
from openjarvis.engine._openai_compat import _OpenAICompatibleEngine

logger = logging.getLogger(__name__)


def _normalize_host(host: str) -> str:
    """Return a host without a trailing OpenAI /v1 path segment."""
    base = host.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


@EngineRegistry.register("nararouter")
class NaraRouterEngine(_OpenAICompatibleEngine):
    """Inference through NaraRouter's OpenAI-compatible API.

    Credentials are read from NARAROUTER_API_KEY by the shared
    OpenAI-compatible base class. The engine deliberately refuses discovery
    when no key is present so adding it to OpenJarvis does not create an
    unauthenticated outbound probe on every local engine scan.
    """

    engine_id = "nararouter"
    is_cloud = True
    _default_host = "https://router.bynara.id"
    _api_prefix = "/v1"

    def __init__(
        self,
        host: str | None = None,
        *,
        api_key: str | None = None,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(
            host=_normalize_host(host) if host else None,
            api_key=api_key,
            timeout=timeout,
        )

    @property
    def has_credentials(self) -> bool:
        """Whether this engine has an API key available."""
        return bool(self._api_key)

    def health(self) -> bool:
        """Return false without credentials, otherwise probe the model roster."""
        if not self.has_credentials:
            return False
        return super().health()

    def list_models(self) -> list[str]:
        """List models currently entitled for the authenticated account."""
        if not self.has_credentials:
            return []
        return super().list_models()

    def list_model_metadata(self) -> list[dict[str, Any]]:
        """Return raw model records from NaraRouter's live model roster.

        OpenJarvis' generic list_models contract only returns model IDs. This
        richer method preserves provider metadata for the adaptive router
        planned on top of this foundation.
        """
        if not self.has_credentials:
            return []
        try:
            response = self._client.get(f"{self._api_prefix}/models")
            response.raise_for_status()
        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
        ) as exc:
            logger.warning(
                "Failed to fetch NaraRouter model metadata from %s: %s",
                self._host,
                exc,
            )
            return []

        payload = response.json()
        records = payload.get("data", [])
        if not isinstance(records, list):
            return []
        return [dict(item) for item in records if isinstance(item, dict)]


__all__ = ["NaraRouterEngine"]
