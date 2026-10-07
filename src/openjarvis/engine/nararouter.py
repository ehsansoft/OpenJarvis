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

    def _public_free_plan_ids(self) -> set[str]:
        """Read model aliases granted by NaraRouter's public Free plan."""
        try:
            response = self._client.get("/api/plans", timeout=10.0)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.debug("NaraRouter public plan discovery failed: %s", exc)
            return set()

        free_ids: set[str] = set()

        def _model_id(item: Any) -> str:
            if isinstance(item, str):
                return item.strip()
            if isinstance(item, dict):
                for key in ("id", "alias", "model", "model_id", "slug"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            return ""

        def _collect_models(plan: dict[str, Any]) -> None:
            for key in (
                "models",
                "model_ids",
                "aliases",
                "included_models",
                "includedModels",
            ):
                values = plan.get(key)
                if isinstance(values, list):
                    for item in values:
                        model_id = _model_id(item)
                        if model_id:
                            free_ids.add(model_id)

        def _is_free_plan(plan: dict[str, Any], hinted_key: str = "") -> bool:
            labels = [
                hinted_key,
                str(plan.get("name", "")),
                str(plan.get("slug", "")),
                str(plan.get("id", "")),
                str(plan.get("tier", "")),
            ]
            return any(label.strip().lower() == "free" for label in labels)

        def _walk(node: Any, hinted_key: str = "") -> None:
            if isinstance(node, dict):
                if _is_free_plan(node, hinted_key):
                    _collect_models(node)
                for key, value in node.items():
                    _walk(value, str(key))
            elif isinstance(node, list):
                for item in node:
                    _walk(item, hinted_key)

        _walk(payload)
        return free_ids

    def list_free_model_ids(self) -> list[str]:
        """Return live account models that are safe to use under the Free plan.

        The public plans endpoint is the preferred source because Nara documents
        it as the live mapping from plans to model aliases. The result is
        intersected with the authenticated account roster. If plan discovery is
        temporarily unavailable, conservative positive evidence in roster
        metadata is used as a fallback.
        """
        records = self.list_model_metadata()
        entitled = [
            str(record.get("id", "")).strip()
            for record in records
            if str(record.get("id", "")).strip()
        ]
        public_free = self._public_free_plan_ids()
        if public_free:
            return [model_id for model_id in entitled if model_id in public_free]

        free_ids: list[str] = []

        def _zero(value: Any) -> bool:
            if value is None or isinstance(value, bool):
                return False
            if isinstance(value, (int, float)):
                return float(value) == 0.0
            if isinstance(value, str):
                normalized = value.strip().lower().replace("$", "")
                return normalized in {"0", "0.0", "0.00", "free", "100% off"}
            return False

        for record in records:
            model_id = str(record.get("id", "")).strip()
            if not model_id:
                continue
            lowered = model_id.lower()
            explicit_id = (
                "-free" in lowered
                or lowered.endswith("/free")
                or lowered.endswith(":free")
            )

            plan = str(
                record.get("plan")
                or record.get("tier")
                or record.get("entitlement")
                or ""
            ).lower()
            explicit_plan = "free" in plan

            pricing = record.get("pricing")
            price_zero = False
            if isinstance(pricing, dict):
                known = [
                    pricing.get("input"),
                    pricing.get("output"),
                    pricing.get("prompt"),
                    pricing.get("completion"),
                    pricing.get("cache"),
                ]
                present = [value for value in known if value is not None]
                price_zero = bool(present) and all(_zero(value) for value in present)

            top_level_prices = [
                record.get(key)
                for key in (
                    "input_price",
                    "output_price",
                    "price_input",
                    "price_output",
                )
                if key in record
            ]
            if top_level_prices:
                price_zero = price_zero or all(
                    _zero(value) for value in top_level_prices
                )

            discount = str(
                record.get("discount")
                or record.get("official_savings")
                or record.get("savings")
                or ""
            ).strip().lower()
            explicit_discount = discount in {
                "100",
                "100%",
                "100% off",
                "free",
            }

            if explicit_id or explicit_plan or price_zero or explicit_discount:
                free_ids.append(model_id)

        return list(dict.fromkeys(free_ids))


__all__ = ["NaraRouterEngine"]
