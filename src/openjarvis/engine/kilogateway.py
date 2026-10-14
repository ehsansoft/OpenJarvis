"""Kilo Gateway inference engine — keyless free-tier OpenAI-compatible gateway.

The Kilo Gateway (https://api.kilo.ai/api/gateway) exposes an OpenAI-compatible
API whose ``...:free`` / ``.../free`` models are reachable without credentials
on a rate-limited free tier (verified live: HTTP 200, ``usage.cost == 0``).

It stays a first-class engine instead of hiding behind LiteLLM because the
zero-cost pool needs the positive free-roster contract
(``list_free_model_ids``), and because gateway ids are multi-slash
(``nvidia/nemotron-3.5-lightning:free``) — the engine therefore advertises them
under a stable ``kilo/`` prefix so the direct-cloud router's OpenRouter
heuristic never claims them, and strips that prefix again on the wire.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from openjarvis.core.registry import EngineRegistry
from openjarvis.engine._openai_compat import _OpenAICompatibleEngine

logger = logging.getLogger(__name__)

#: Advertised prefix for every model this engine owns.
MODEL_PREFIX = "kilo/"

#: Free gateway models end their final path/parameter segment with ``free``
#: (``nvidia/x:free``, ``kilo-auto/free``, ``stepfun/step-5-preview-free``).
_ROSTER_TTL_SECONDS = 60.0


def _is_free_gateway_id(model_id: str) -> bool:
    last = model_id.rsplit("/", 1)[-1]
    return last.endswith("free")


@EngineRegistry.register("kilogateway")
class KiloGatewayEngine(_OpenAICompatibleEngine):
    """Inference through the Kilo Gateway's free tier.

    No API key is required for free models; an optional ``KILOGATEWAY_API_KEY``
    is picked up automatically by the shared OpenAI-compatible base class if
    the user provisions one later.
    """

    engine_id = "kilogateway"
    is_cloud = True
    _default_host = "https://api.kilo.ai/api/gateway"
    # The gateway serves /models and /chat/completions at its root.
    _api_prefix = ""

    def __init__(
        self,
        host: str | None = None,
        *,
        api_key: str | None = None,
        timeout: float = 120.0,
        free_only: bool = True,
    ) -> None:
        self._free_only = free_only
        self._roster_cache: list[dict[str, Any]] | None = None
        self._roster_at = 0.0
        super().__init__(
            host=host.rstrip("/") if host else None,
            api_key=api_key,
            timeout=timeout,
        )

    # -- roster -------------------------------------------------------------

    def _roster(self, *, force: bool = False) -> list[dict[str, Any]]:
        """Raw gateway model records, positively filtered to the free tier.

        TTL-cached so MultiEngine map refreshes and ``can_serve`` checks do
        not turn into a network call per lookup.
        """
        now = time.monotonic()
        if (
            not force
            and self._roster_cache is not None
            and now - self._roster_at < _ROSTER_TTL_SECONDS
        ):
            return self._roster_cache
        try:
            response = self._client.get(f"{self._api_prefix}/models", timeout=15.0)
            response.raise_for_status()
        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
        ) as exc:
            logger.warning(
                "Failed to list KiloGateway models from %s: %s", self._host, exc
            )
            return self._roster_cache or []
        payload = response.json()
        records = payload.get("data", [])
        free_records: list[dict[str, Any]] = []
        if isinstance(records, list):
            for item in records:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                if not _is_free_gateway_id(str(item["id"])):
                    continue
                record = dict(item)
                record["id"] = f"{MODEL_PREFIX}{record['id']}"
                free_records.append(record)
        self._roster_cache = free_records
        self._roster_at = now
        return free_records

    # -- InferenceEngine interface -----------------------------------------

    def health(self) -> bool:
        """Probe the keyless gateway roster with a bounded timeout.

        The gateway needs no credentials for the free tier, so a 200 on
        ``/models`` is sufficient evidence of health.
        """
        try:
            response = self._client.get(f"{self._api_prefix}/models", timeout=10.0)
            return response.status_code == 200
        except Exception as exc:
            logger.debug("KiloGateway health probe failed: %s", exc)
            return False

    def list_free_model_ids(self) -> list[str]:
        """Positive free-tier roster, engine-prefixed (``kilo/...``)."""
        return [str(record["id"]) for record in self._roster()]

    def list_model_metadata(self) -> list[dict[str, Any]]:
        """Free-tier records with provider metadata for pool ranking."""
        return list(self._roster())

    def list_models(self) -> list[str]:
        if self._free_only:
            return self.list_free_model_ids()
        # free_only=False is an escape hatch for account-gated models; the
        # generic contract still advertises the full gateway roster.
        try:
            response = self._client.get(f"{self._api_prefix}/models", timeout=15.0)
            response.raise_for_status()
        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
        ) as exc:
            logger.warning(
                "Failed to list KiloGateway models from %s: %s", self._host, exc
            )
            return []
        payload = response.json()
        records = payload.get("data", [])
        if not isinstance(records, list):
            return []
        return [
            f"{MODEL_PREFIX}{item['id']}"
            for item in records
            if isinstance(item, dict) and item.get("id")
        ]

    def can_serve(self, model: str) -> bool:
        """Strict free-roster membership so foreign raw ids never resolve here."""
        return model in self.list_models()

    def _resolve_model_id(self, model: str) -> str:
        """Strip the advertised ``kilo/`` prefix on the wire."""
        if model.startswith(MODEL_PREFIX):
            return model[len(MODEL_PREFIX) :]
        return model


__all__ = ["KiloGatewayEngine", "MODEL_PREFIX"]
