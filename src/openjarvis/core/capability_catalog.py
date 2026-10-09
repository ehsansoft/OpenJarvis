"""Workstation readiness from bounded metadata and existing acceptance evidence.

No service construction, database opening, model generation/loading, subprocess
execution, cache refresh/write, skill sync or configuration changes occur here.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

from openjarvis.core.config import JarvisConfig
from openjarvis.intelligence.free_pool import collect_free_models, rank_free_models
from openjarvis.projects.review import registry_preview

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

STATUSES = (
    "READY",
    "MANUAL_SETUP",
    "DISABLED",
    "BLOCKED",
    "NOT_INSTALLED",
    "NOT_APPLICABLE",
)
ACCEPTANCE_COMMAND = "jarvis acceptance --live --speech-fixture <synthetic.wav>"


@dataclass(frozen=True)
class Capability:
    id: str
    display_name: str
    status: str
    configured: bool
    installed: bool | None
    accepted: bool
    reason: str
    evidence: list[dict[str, Any]]
    observed_at: str
    next_action: str
    related_commands: list[str]
    privacy: str
    dependencies: list[str]


def _read_json(path: Path, max_bytes: int = 4 * 1024 * 1024) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Metadata exceeds size limit")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected metadata object")
    return data


def acceptance_evidence(
    root: Path,
    now: datetime,
    max_age: timedelta = timedelta(hours=24),
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Latest report only: never fall back to an older pass after a newer failure."""
    candidates = list(
        islice((root / "support").glob("acceptance-*/acceptance.json"), 201)
    )
    if len(candidates) > 200:
        return {}, {"source": "acceptance", "state": "report-limit-exceeded"}
    if not candidates:
        return {}, {"source": "acceptance", "state": "missing"}
    try:
        source = max(candidates, key=lambda p: p.stat().st_mtime)
        report = _read_json(source)
        timestamp = report.get("timestamp", "")
        observed = datetime.strptime(timestamp, "%Y%m%d-%H%M%S").replace(
            tzinfo=timezone.utc
        )
        if not timedelta(0) <= now - observed <= max_age:
            return {}, {
                "source": source.name,
                "state": "stale-or-future",
                "observed_at": observed.isoformat(),
            }
        checks = report.get("checks")
        if not isinstance(checks, list):
            raise ValueError("Invalid checks")
        by_name = {
            c["name"]: c
            for c in checks
            if isinstance(c, dict) and isinstance(c.get("name"), str)
        }
        return by_name, {
            "source": str(source),
            "state": "fresh",
            "observed_at": observed.isoformat(),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "context_sha256": report.get("context_sha256"),
        }
    except (OSError, ValueError, TypeError):
        return {}, {"source": "acceptance", "state": "invalid"}


class MetadataProbe:
    """Only loopback HTTP metadata; no proxies, redirects or inference endpoints."""

    def __init__(
        self, timeout: float = 3.0, transport: httpx.BaseTransport | None = None
    ):
        self.timeout = timeout
        self.transport = transport

    def __call__(
        self, host: str, path: str, payload: dict | None = None
    ) -> dict | list:
        parsed = urlsplit(host)
        name = parsed.hostname or ""
        local = name.lower() == "localhost"
        if not local:
            try:
                local = ipaddress.ip_address(name).is_loopback
            except ValueError:
                pass
        if (
            not local
            or parsed.scheme not in {"http", "https"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Status endpoints must be loopback URLs without credentials"
            )
        if path not in {
            "/health",
            "/api/tags",
            "/api/show",
            "/models/status",
            "/profiles",
        }:
            raise ValueError("Not a metadata endpoint")
        if payload is not None and path != "/api/show":
            raise ValueError("Only Ollama show permits a read-only POST")
        with httpx.Client(
            timeout=self.timeout,
            trust_env=False,
            follow_redirects=False,
            transport=self.transport,
        ) as client:
            deadline = time.monotonic() + self.timeout
            with client.stream(
                "POST" if payload is not None else "GET",
                host.rstrip("/") + path,
                json=payload,
            ) as response:
                response.raise_for_status()
                raw = bytearray()
                for chunk in response.iter_bytes():
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("Metadata deadline exceeded")
                    raw.extend(chunk)
                    if len(raw) > 2 * 1024 * 1024:
                        raise ValueError("Metadata response exceeds size limit")
        data = json.loads(raw)
        if not isinstance(data, (dict, list)):
            raise ValueError("Invalid metadata response")
        return data


def discover_nara(config: JarvisConfig, root: Path, timeout: float) -> list[str] | None:
    """Reuse Nara's live entitlement/free-plan intersection; no inference."""
    from openjarvis.engine.nararouter import NaraRouterEngine

    key = os.environ.get("NARAROUTER_API_KEY", "")
    if not key:
        try:
            with (root / "credentials.toml").open("rb") as handle:
                raw = handle.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise ValueError("Credential metadata exceeds limit")
            key = (
                tomllib.loads(raw.decode("utf-8-sig"))
                .get("nararouter", {})
                .get("NARAROUTER_API_KEY", "")
            )
        except (OSError, ValueError, TypeError, AttributeError):
            return None
    if not key:
        return None
    host = config.engine.nararouter.host
    url = urlsplit(host)
    if (
        url.scheme != "https"
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError(
            "Configured Nara endpoint must use HTTPS without URL credentials"
        )

    # Its shared implementation uses a 10s plan-discovery timeout. Clamp every
    # request to the CLI's bound, including that explicit method timeout.
    class BoundedClient(httpx.Client):
        def get(self, *args, **kwargs):
            kwargs["timeout"] = timeout
            return super().get(*args, **kwargs)

    engine = NaraRouterEngine(host=host, api_key=key, timeout=timeout)
    engine._client.close()
    engine._client = BoundedClient(
        base_url=engine._host,
        headers={"Authorization": f"Bearer {key}"},
        timeout=timeout,
        follow_redirects=False,
    )
    try:
        return engine.list_free_model_ids()
    finally:
        engine.close()


def catalog_context_sha256(config: JarvisConfig, model_metadata: list) -> str:
    """Bind acceptance to current model weights and non-secret routing settings."""
    return hashlib.sha256(
        json.dumps(
            {
                "ollama_host": config.engine.ollama.host or "http://localhost:11434",
                "models": sorted(model_metadata, key=lambda m: m["id"]),
                "personal_api": [config.server.host, config.server.port],
                "default_model": config.intelligence.default_model,
                "speech_speed": config.speech.voice_speed,
                "voicebox_host": config.projects.voicebox_host,
                "speech_model": config.speech.model,
                "voice_id": config.speech.voice_id,
                "speech_backend": config.speech.backend,
                "tts_backend": config.speech.tts_backend,
                "channel_enabled": config.channel.enabled,
                "allowed_chat_ids": config.channel.telegram.allowed_chat_ids,
                "private_routing": config.intelligence.private_routing,
                "allow_private_remote": config.intelligence.allow_private_remote,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def build_catalog(
    config: JarvisConfig,
    root: Path,
    *,
    now: datetime | None = None,
    probe: Callable | None = None,
    nara: Callable | None = None,
    timeout: float = 3.0,
    which: Callable = shutil.which,
) -> dict[str, Any]:
    """Collect once and project the same facts into all capability records."""
    now = now or datetime.now(timezone.utc)
    observed_at = now.isoformat()
    probe = probe or MetadataProbe(timeout)
    checks, report_evidence = acceptance_evidence(root, now)
    failures: list[dict[str, str]] = []

    def get(host, path, payload=None):
        try:
            data = probe(host, path, payload)
            if path == "/profiles":
                if not isinstance(data, list):
                    raise ValueError("Invalid profile metadata")
            elif not isinstance(data, dict):
                raise ValueError("Invalid service metadata")
            if path in ("/api/tags", "/models/status") and not isinstance(
                data.get("models"), list
            ):
                raise ValueError("Invalid model metadata")
            if path == "/health" and data.get("status") not in {"ok", "healthy"}:
                raise ValueError("Unhealthy service")
            return data
        except (OSError, ValueError, TypeError, httpx.HTTPError) as exc:
            # No raw exception/response/config URLs or credentials in output.
            failures.append(
                {
                    "probe": path,
                    "failure_type": type(exc).__name__,
                    "service": "ollama"
                    if host == ollama_host
                    else "voicebox"
                    if host == config.projects.voicebox_host
                    else "personal-api",
                    "http_status": exc.response.status_code
                    if isinstance(exc, httpx.HTTPStatusError)
                    else None,
                }
            )
            return None

    ollama_host = config.engine.ollama.host or "http://localhost:11434"
    tags = get(ollama_host, "/api/tags")
    models = tags.get("models", []) if isinstance(tags, dict) else []
    model_metadata = []
    for model in models[:12]:
        if not isinstance(model, dict) or not isinstance(model.get("name"), str):
            continue
        info = get(ollama_host, "/api/show", {"name": model["name"]})
        model_metadata.append(
            {
                "id": model["name"],
                "digest": model.get("digest", ""),
                "capabilities": info.get("capabilities", [])
                if isinstance(info, dict)
                else [],
            }
        )
    snapshot = SimpleNamespace(
        is_cloud=False,
        _host=ollama_host,
        list_models=lambda: [m["id"] for m in model_metadata],
        list_model_metadata=lambda: model_metadata,
    )
    candidates = collect_free_models([("ollama", snapshot)])
    voice_health = get(config.projects.voicebox_host, "/health")
    voice_status = get(config.projects.voicebox_host, "/models/status")
    profiles = get(config.projects.voicebox_host, "/profiles") if voice_health else None
    voice_models = (
        voice_status.get("models", []) if isinstance(voice_status, dict) else []
    )
    api_host = f"http://{config.server.host}:{config.server.port}"
    api_health = get(api_host, "/health")
    try:
        roster = (nara or discover_nara)(config, root, timeout)
    except (OSError, ValueError, TypeError, httpx.HTTPError) as exc:
        failures.append(
            {
                "probe": "nara-free-roster",
                "failure_type": type(exc).__name__,
                "service": "nararouter",
                "http_status": None,
            }
        )
        roster = []
    machine = {}
    try:
        machine = _read_json(Path(config.projects.machine_inventory_path).expanduser())
    except (OSError, ValueError):
        pass
    registry = None
    try:
        registry = registry_preview(
            Path(config.projects.registry_path).expanduser(), limit=1
        )
    except (OSError, ValueError):
        pass
    records: list[Capability] = []
    context_sha256 = catalog_context_sha256(config, model_metadata)

    def human_passed(name):
        check = checks.get(name, {})
        detail = check.get("evidence", {})
        return (
            check.get("status") == "PASS"
            and isinstance(detail, dict)
            and detail.get("confirmation") == "human"
            and detail.get("context_sha256") == context_sha256
        )

    def passed(name, selected=None):
        check = checks.get(name, {})
        if (
            check.get("status") != "PASS"
            or report_evidence.get("context_sha256") != context_sha256
        ):
            return False
        if selected is not None:
            detail = check.get("evidence", {})
            if not isinstance(detail, dict):
                return False
            routing = detail.get("routing", {})
            if not isinstance(routing, dict):
                return False
            return (
                routing.get("selected_model") == selected
                and routing.get("selected_engine") == "ollama"
            )
        return True

    def add(
        id,
        name,
        *,
        configured=True,
        installed=True,
        accepted=False,
        blocked=False,
        applicable=True,
        reason,
        next_action,
        commands=(),
        privacy="local-private",
        dependencies=(),
        evidence=(),
    ):
        if not applicable:
            status = "NOT_APPLICABLE"
        elif blocked:
            status = "BLOCKED"
        elif installed is False:
            status = "NOT_INSTALLED"
        elif not configured:
            status = "DISABLED"
        elif accepted:
            status = "READY"
        else:
            status = "MANUAL_SETUP"
        records.append(
            Capability(
                id,
                name,
                status,
                configured,
                installed,
                accepted,
                reason,
                list(evidence) + [report_evidence],
                observed_at,
                next_action,
                list(commands),
                privacy,
                list(dependencies),
            )
        )

    add(
        "ollama",
        "Ollama",
        installed=True if tags else bool(which("ollama")),
        accepted=isinstance(tags, dict) and isinstance(tags.get("models"), list),
        blocked=tags is None,
        reason=(
            f"Live installed roster: {len(models)} models; no downloads or generation."
        ),
        next_action=(
            "Inspect the already installed Ollama service and loopback "
            "proxy exclusions if unreachable."
        ),
        commands=("ollama list",),
        evidence=(
            {"source": "/api/tags", "model_ids": [m["id"] for m in model_metadata]},
        ),
    )
    add(
        "personal-api",
        "Personal API",
        installed=True,
        accepted=bool(api_health),
        blocked=api_health is None,
        reason=(
            "Live health endpoint only; transport health does not prove "
            "model generation."
        ),
        next_action=(
            "Inspect jarvis doctor --json and existing server logs; "
            "correct loopback proxy exclusions manually."
        ),
        commands=("jarvis doctor --json",),
        evidence=({"source": "/health", "reachable": api_health is not None},),
    )
    for task in ("code", "fast", "research", "vision"):
        ranked = rank_free_models(candidates, task, allow_remote=False)
        selected = ranked[0].model_id if ranked else None
        alias = f"local/{task}"
        alias_accepted = passed(alias, selected) if selected else False
        add(
            alias,
            alias,
            installed=bool(selected) if tags else None,
            accepted=alias_accepted,
            blocked=tags is None or api_health is None,
            reason=(
                f"Selected installed model: {selected or 'none'}; acceptance "
                "must match this alias/model. Personal API health is "
                f"{'available' if api_health else 'unavailable'}."
            ),
            next_action=ACCEPTANCE_COMMAND
            if api_health
            else (
                "Check jarvis doctor --json and existing server logs; "
                "review loopback proxy exclusions before a manual restart."
            ),
            commands=(f"jarvis chat -m {alias}",),
            dependencies=("ollama", "personal-api"),
            evidence=(
                {"source": "shared-local-router-ranking", "selected_model": selected},
            ),
        )
    add(
        "local-chat",
        "Local Chat",
        installed=bool(candidates) if tags else None,
        configured=config.intelligence.default_model.startswith("local/"),
        accepted=passed("jarvis_chat_real"),
        blocked=tags is None or api_health is None,
        reason=(
            "CLI chat acceptance is separate from model presence and "
            "personal API health."
        ),
        next_action="jarvis chat -m local/fast; then run bounded acceptance.",
        commands=("jarvis chat -m local/fast",),
        dependencies=("local/fast",),
    )
    embed = next(
        (m for m in model_metadata if m["id"].split(":")[0] == "nomic-embed-text"), None
    )
    add(
        "embeddings",
        "Local Embeddings",
        installed=bool(embed) if tags else None,
        accepted=passed("nomic_local_embedding"),
        blocked=tags is None,
        reason=(
            "nomic compatibility requires existing 768-dimensional "
            "acceptance; no project indexing performed."
        ),
        next_action=ACCEPTANCE_COMMAND,
        dependencies=("ollama",),
        evidence=(
            {
                "source": "installed-model-metadata",
                "model_id": embed["id"] if embed else None,
                "dimensions": 768 if passed("nomic_local_embedding") else None,
            },
        ),
    )
    add(
        "nara-free-pool",
        "Nara Free Pool",
        configured=roster is not None,
        blocked=roster == [],
        installed=True,
        accepted=bool(roster) and human_passed("nara_inference_live"),
        reason=(
            f"Live positively entitled free roster: {len(roster or [])}; "
            "discovery is not inference qualification."
        ),
        next_action="jarvis model nara-key; then jarvis model free --json."
        if roster is None
        else (
            "jarvis model free --json; qualify entitled models in Phase 1I Model Lab."
        ),
        commands=("jarvis model free --json",),
        privacy="public-metadata",
        evidence=(
            {
                "source": "live-nara-entitlement-intersection",
                "model_ids": sorted(roster or []),
            },
        ),
    )
    add(
        "voicebox",
        "Voicebox Service",
        installed=True if voice_health else None,
        accepted=bool(voice_health) and passed("voicebox_service"),
        blocked=voice_health is None,
        reason="Live health metadata; no model initialization.",
        next_action=(
            "Keep the existing Voicebox app available, then run bounded acceptance."
        ),
        dependencies=(),
        evidence=({"source": "/health", "reachable": voice_health is not None},),
    )
    for id, label, model_name, acceptance_name, configured in (
        (
            "whisper-stt",
            "Whisper STT",
            f"whisper-{config.speech.model}",
            "voicebox_stt_live",
            config.speech.backend == "voicebox",
        ),
        (
            "kokoro-tts",
            "Kokoro TTS",
            "kokoro",
            "voicebox_tts_stt_roundtrip",
            config.speech.tts_backend == "voicebox",
        ),
    ):
        model = next(
            (
                m
                for m in voice_models
                if isinstance(m, dict) and m.get("model_name") == model_name
            ),
            {},
        )
        loaded = model.get("loaded") is True
        preset = any(
            p.get("preset_engine") == "kokoro"
            and p.get("voice_type") == "preset"
            and (
                not config.speech.voice_id
                or config.speech.voice_id
                in (p.get("id"), p.get("name"), p.get("preset_voice_id"))
            )
            for p in profiles or []
            if isinstance(p, dict)
        )
        ready_profile = preset if id == "kokoro-tts" else True
        add(
            id,
            label,
            configured=configured,
            installed=True if loaded else model.get("downloaded") if model else None,
            accepted=loaded and ready_profile and passed(acceptance_name),
            blocked=voice_status is None or not loaded or not ready_profile,
            reason=(
                f"{model_name}: cached={model.get('downloaded', 'unknown')}, "
                f"loaded={loaded}; configured preset "
                f"resolved={ready_profile}. Human listening is a separate "
                "gate."
            ),
            next_action=(
                "Voicebox Generation: select an existing Kokoro preset, "
                "generate/play synthetic English manually, then rerun acceptance. "
                "Do not POST model_name to legacy /models/load."
                if id == "kokoro-tts"
                else (
                    "Select/load cached Whisper manually in Voicebox, "
                    "then transcribe a synthetic WAV in acceptance."
                )
            ),
            commands=(ACCEPTANCE_COMMAND,),
            dependencies=("voicebox",),
            evidence=(
                {
                    "source": "/models/status",
                    "model": model_name,
                    "loaded": loaded,
                    "configured_profile_available": ready_profile,
                },
            ),
        )
    add(
        "microphone",
        "Microphone and Listening",
        installed=True if human_passed("microphone_and_listening") else None,
        accepted=human_passed("microphone_and_listening"),
        reason=(
            "Synthetic STT/TTS cannot prove the user's microphone, "
            "playback or listening acceptance."
        ),
        next_action=(
            "jarvis chat --voice -m local/fast; speak, inspect "
            "transcription and listen to the response."
        ),
        commands=("jarvis chat --voice -m local/fast",),
        dependencies=("whisper-stt", "kokoro-tts"),
    )
    vision_installed = bool(rank_free_models(candidates, "vision", allow_remote=False))
    add(
        "vision",
        "Vision",
        installed=vision_installed if tags else None,
        accepted=passed("local_vision_image"),
        blocked=tags is None or api_health is None,
        reason=(
            "Vision readiness requires the synthetic image check, not "
            "model-name inference."
        ),
        next_action=ACCEPTANCE_COMMAND,
        dependencies=("local/vision",),
    )
    add(
        "memory",
        "Lexical Memory",
        configured=config.tools.storage.default_backend == "sqlite",
        installed=Path(config.tools.storage.db_path).expanduser().exists(),
        accepted=passed("memory_index_real") and passed("memory_search_real"),
        reason=(
            "Existing document memory only; no database opened or "
            "source indexed by this command."
        ),
        next_action=(
            "jarvis memory search <query>; rerun synthetic acceptance "
            "if evidence is stale."
        ),
        commands=("jarvis memory search <query>",),
    )
    add(
        "scoped-project-memory",
        "Scoped Project Memory",
        configured=False,
        installed=False,
        blocked=True,
        reason=(
            "Phase 1F/1G is not implemented; scanner proposals are not "
            "approved index sources."
        ),
        next_action=(
            "Complete 1C approvals and reviewed 1D adoption before 1F/1G indexing."
        ),
        dependencies=("project-registry", "memory", "embeddings"),
    )
    add(
        "deep-research",
        "Deep Research",
        configured=config.deep_research.model.startswith("local/"),
        accepted=passed("deep_research_real"),
        blocked=api_health is None,
        reason=(
            "Local synthetic execution acceptance does not establish "
            "answer quality or a research library."
        ),
        next_action=(
            "Run bounded local Deep Research acceptance and inspect "
            "cited results manually."
        ),
        dependencies=("local/research",),
    )
    add(
        "public-research",
        "Web/Public Research",
        configured="web_search" in config.tools.enabled,
        accepted=human_passed("public_research_live"),
        reason=(
            "Web tool declaration alone is not an accepted "
            "search/provider workflow; private chunks stay local."
        ),
        next_action=(
            "Review and test one public query; Phase 1H adds outbound "
            "previews and the research library."
        ),
        privacy="public-metadata",
        dependencies=("nara-free-pool",),
    )
    add(
        "scheduler",
        "Scheduler",
        configured=config.scheduler.enabled,
        accepted=passed("scheduler_real_local_execution"),
        reason=(
            "Server-owned scheduler; synthetic execution acceptance "
            "does not enable personal recurring jobs."
        ),
        next_action=(
            "Review an exact task and notification plan before enabling "
            "the existing server-owned scheduler."
        ),
        commands=("jarvis scheduler list",),
    )
    telegram_configured = config.channel.enabled and bool(
        config.channel.telegram.allowed_chat_ids
    )
    add(
        "telegram",
        "Telegram",
        configured=telegram_configured,
        accepted=human_passed("telegram_live"),
        reason=(
            "Live allowed-chat/reply/restart/notification acceptance "
            "requires human proof; no polling started."
        ),
        next_action=(
            "Follow docs/EHSAN_REAL_USER_ACCEPTANCE.md Telegram setup "
            "with one server/poller and an explicit allow-list."
        ),
        privacy="external-session",
        dependencies=("scheduler",),
    )
    for id, label, executable in (
        ("opencode", "OpenCode", "opencode"),
        ("kilo", "Kilo Code", "kilo"),
        ("github", "GitHub", "git"),
    ):
        present = bool(which(executable))
        add(
            id,
            label,
            installed=True if present or human_passed(f"{id}_live") else None,
            accepted=human_passed(f"{id}_live"),
            reason=(
                f"CLI detected={present}; extension installs/account "
                "permissions and real client acceptance are not inferred."
            ),
            next_action=(
                "Review GitHub authentication and perform one read-only "
                "repository operation manually."
                if id == "github"
                else (
                    "Merge the version-matched template from "
                    "docs/EHSAN_REAL_USER_ACCEPTANCE.md; "
                    "use local/code for private work."
                )
            ),
            dependencies=() if id == "github" else ("local/code",),
            privacy="external-session" if id == "github" else "local-private",
        )
    add(
        "mcp",
        "MCP",
        configured=config.tools.mcp.enabled,
        accepted=human_passed("mcp_live"),
        reason=(
            "MCP configuration is present/disabled separately from a "
            "live tool handshake; no process spawned."
        ),
        next_action=(
            "Run the read-only scripts/install/Check-Voicebox-MCP.py "
            "manually and inspect its tool handshake."
        ),
        dependencies=("voicebox",),
    )
    add(
        "hermes",
        "Hermes Skills",
        configured=config.skills.enabled,
        installed=(root / "skill-cache" / "hermes" / "skills").is_dir(),
        accepted=human_passed("hermes_live_review"),
        reason=(
            "Cached community sources are not approved skills. No "
            "sync/import/script execution."
        ),
        next_action=(
            "jarvis skill audit hermes --category research; repeat "
            "coding/productivity and review translations/conflicts."
        ),
        commands=("jarvis skill audit hermes --category research",),
    )
    for id, label in (
        ("project-registry", "Project Registry"),
        ("project-review", "Project Review"),
    ):
        valid = registry is not None
        add(
            id,
            label,
            installed=valid,
            accepted=valid,
            blocked=not valid,
            reason=(
                f"{registry['total']} scanner proposals; "
                "zero confirmed adoption inferred."
                if valid
                else "Scanner registry missing or invalid; no migration performed."
            ),
            next_action=(
                "jarvis projects review --role active --limit 10; review "
                "proposals before adoption."
            ),
            commands=(
                "jarvis projects audit",
                "jarvis projects review --role active --limit 10",
            ),
            evidence=(
                {
                    "source": "registry-audit",
                    "total": registry["total"] if valid else None,
                    "role_counts": registry["role_counts"] if valid else {},
                    "snapshot_sha256": registry["snapshot_sha256"] if valid else None,
                },
            ),
        )
    wamp = machine.get("wampserver", {})
    machine_time = machine.get("generated_at", "")
    try:
        machine_fresh = (
            timedelta(0)
            <= now - datetime.fromisoformat(machine_time)
            <= timedelta(hours=24)
        )
    except (ValueError, TypeError):
        machine_fresh = False
    add(
        "wampserver",
        "WampServer",
        applicable=os.name == "nt",
        installed=wamp.get("detected") if machine_fresh else None,
        accepted=machine_fresh and human_passed("wampserver_live"),
        reason=(
            "Persisted machine inventory; runtime/site acceptance is "
            "not inferred from installation."
        ),
        next_action=(
            "jarvis projects machine-scan --json; review the project's "
            "PHP/database/runtime mapping."
        ),
        evidence=({"source": "machine-inventory", "fresh": machine_fresh},),
    )
    for id, label in (("wordpress", "WordPress"), ("woocommerce", "WooCommerce")):
        add(
            id,
            label,
            configured=False,
            installed=None,
            applicable=False,
            reason=(
                "Site applicability and runtime/plugin acceptance require "
                "an explicitly selected project; secrets are not read."
            ),
            next_action=(
                "Select and review one relevant project; Phase 1E adds "
                "reusable stack/site facts."
            ),
            dependencies=("project-review", "wampserver"),
        )
    add(
        "environment-doctor",
        "Environment Doctor",
        installed=sys.version_info >= (3, 10),
        accepted=human_passed("environment_doctor_live"),
        reason=(
            "Diagnostic command available; catalog does not execute "
            "version commands or remote diagnostic workflows."
        ),
        next_action="jarvis doctor --json; inspect every warning and failed check.",
        commands=("jarvis doctor --json",),
    )
    add(
        "workspace-hygiene",
        "Workspace Hygiene",
        configured="hygiene_report" in config.tools.enabled,
        accepted=human_passed("workspace_hygiene_live"),
        reason=(
            "Read-only scanners available; stale/missing reports "
            "require a separately requested scan. No cleanup performed."
        ),
        next_action=(
            "Review existing hygiene reports; request a bounded "
            "metadata scan if stale, never an automatic deletion."
        ),
        commands=("jarvis projects cleanup-scan --help",),
    )
    projected = [asdict(r) for r in records]
    by_id = {r["id"]: r for r in projected}
    for record in projected:
        if record["status"] == "READY":
            missing = [
                d for d in record["dependencies"] if by_id[d]["status"] != "READY"
            ]
            if missing:
                record["status"] = "BLOCKED"
                record["reason"] += " Dependencies awaiting readiness: " + ", ".join(
                    missing
                )
    return {
        "schema_version": 1,
        "observed_at": observed_at,
        "read_only": True,
        "context_sha256": context_sha256,
        "acceptance_evidence": report_evidence,
        "probe_failures": failures,
        "capabilities": projected,
    }
