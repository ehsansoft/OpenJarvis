"""Bounded acceptance checks with shareable, secret-free evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import click

ACCEPTANCE_TESTS = {
    "scheduler_telegram_privacy": [
        "tests/core/test_real_user_acceptance.py",
        "tests/core/test_acceptance_cmd.py",
    ],
    "scheduler_create_run_notify": ["tests/scheduler"],
    "telegram_chat": [
        "tests/channels/test_telegram.py",
        "tests/server/test_channel_bridge.py",
    ],
    "jarvis_chat_and_voice": ["tests/cli/test_chat_cmd.py"],
    "voicebox_stt_tts": [
        "tests/speech/test_voicebox_stt.py",
        "tests/speech/test_voicebox_tts.py",
    ],
    "free_code_research_vision": ["tests/intelligence/test_free_pool.py"],
    "editor_templates": ["tests/server/test_editor_gateway.py"],
    "memory_index_search": ["tests/cli/test_memory_cmd.py"],
    "deep_research": [
        "tests/cli/test_deep_research_setup.py",
        "tests/server/test_research_planner.py",
    ],
    "hermes_safe_import": [
        "tests/skills/test_sources.py",
        "tests/skills/test_importer.py",
    ],
}


def redact(text: str) -> str:
    text = re.sub(r"bot\d{5,}:[A-Za-z0-9_-]+", "bot[REDACTED]", text)
    text = re.sub(r"(?i)(bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    for key, value in os.environ.items():
        if (
            any(
                marker in key.upper()
                for marker in ("TOKEN", "API_KEY", "SECRET", "PASSWORD")
            )
            and len(value) >= 8
        ):
            text = text.replace(value, "[REDACTED]")
    return text


def check_cli_output(result: subprocess.CompletedProcess, require: str = "") -> None:
    """Rich writes chat output to stderr; both streams are user-visible."""
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode or (require and require not in output):
        raise RuntimeError(
            f"CLI acceptance failed (exit {result.returncode}): "
            + redact(output[-500:])
        )


def generate_support_zip(run_dir: Path, report: dict, repo: Path) -> Path:
    """Package an explicit allow-list; never recurse over runtime state."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "acceptance.json").write_text(
        redact(json.dumps(report, indent=2)), encoding="utf-8"
    )
    archive = run_dir.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in ("acceptance.json", "regression.log"):
            source = run_dir / name
            if source.exists():
                bundle.writestr(name, redact(source.read_text(encoding="utf-8")))
        for name in (
            "docs/EHSAN_REAL_USER_ACCEPTANCE.md",
            "configs/editors/opencode.openjarvis.jsonc",
            "configs/editors/opencode-v1.openjarvis.jsonc",
            "configs/editors/kilo.openjarvis.jsonc",
        ):
            source = repo / name
            if source.exists():
                bundle.writestr(name, redact(source.read_text(encoding="utf-8")))
    return archive


@click.command("acceptance")
@click.option(
    "--live", is_flag=True, help="Run synthetic local inference and service checks."
)
@click.option("--output", type=click.Path(path_type=Path), default=None)
@click.option(
    "--speech-fixture",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Transcribe an existing synthetic WAV with the loaded Voicebox model.",
)
@click.option(
    "--skip-regression", is_flag=True, help="Record regression checks as not run."
)
def acceptance(
    live: bool, output: Path | None, speech_fixture: Path | None, skip_regression: bool
) -> None:
    """Verify Phase 0.5 and generate a support ZIP without enabling automations."""
    from openjarvis.core.paths import get_config_dir

    repo = Path(__file__).resolve().parents[3]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = (
        output
        or get_config_dir() / "support" / f"acceptance-{stamp}-{uuid.uuid4().hex[:6]}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "0.5",
        "timestamp": stamp,
        "checks": [],
        "automation_enabled": False,
    }
    checks = report["checks"]
    if not skip_regression:
        test_paths = sorted({p for paths in ACCEPTANCE_TESTS.values() for p in paths})
        missing = [p for p in test_paths if not (repo / p).exists()]
        if missing:
            raise click.ClickException(f"Acceptance test files missing: {missing}")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                *test_paths,
                "-q",
                "--basetemp",
                str(run_dir / "pytest-temp"),
                "-o",
                f"cache_dir={run_dir / 'pytest-cache'}",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        log = redact(result.stdout + result.stderr)
        (run_dir / "regression.log").write_text(log, encoding="utf-8")
        checks.append(
            {
                "name": "regression",
                "status": "PASS" if result.returncode == 0 else "FAIL",
                "summary": log.splitlines()[-1:],
            }
        )
        for name in ACCEPTANCE_TESTS:
            checks.append(
                {
                    "name": name,
                    "status": "AUTOMATED_PASS"
                    if result.returncode == 0
                    else "REVIEW_REQUIRED",
                    "scope": "isolated regression fixtures",
                }
            )
    else:
        checks.append({"name": "regression", "status": "NOT_RUN"})
    if live:
        try:
            report["context_sha256"] = _live_checks(checks, run_dir, speech_fixture)
        except Exception as exc:
            checks.append(
                {"name": "live_setup", "status": "FAIL", "error": redact(str(exc))}
            )
    for name, command in (
        ("microphone_and_listening", "jarvis chat --voice -m local/fast"),
        (
            "telegram_live",
            "Follow docs/EHSAN_REAL_USER_ACCEPTANCE.md; token and chat id required",
        ),
        (
            "opencode_live",
            "Merge the version-matched template, then select openjarvis/local-code",
        ),
        (
            "kilo_live",
            "Merge Kilo template, then select openai-compatible/openjarvis-local-code",
        ),
    ):
        checks.append({"name": name, "status": "MANUAL_REQUIRED", "command": command})
    report["ready_for_personal_automations"] = False
    archive = generate_support_zip(run_dir, report, repo)
    click.echo(
        json.dumps(
            {
                "report": str(run_dir / "acceptance.json"),
                "support_zip": str(archive),
                "checks": checks,
            },
            indent=2,
        )
    )
    if any(check["status"] == "FAIL" for check in checks):
        raise click.ClickException("Acceptance failures recorded; inspect the evidence")


def _live_checks(
    checks: list, run_dir: Path, speech_fixture: Path | None = None
) -> str:

    from openjarvis.connectors.embeddings import OllamaEmbedder
    from openjarvis.core.capability_catalog import (
        MetadataProbe,
        catalog_context_sha256,
    )
    from openjarvis.core.config import load_config
    from openjarvis.core.types import Message, Role
    from openjarvis.engine.ollama import OllamaEngine
    from openjarvis.intelligence.free_pool import FreePoolEngine

    config = load_config()
    metadata_probe = MetadataProbe(timeout=5)

    def record(name, action):
        try:
            detail = action()
            checks.append({"name": name, "status": "PASS", "evidence": detail})
        except Exception as exc:
            checks.append({"name": name, "status": "FAIL", "error": redact(str(exc))})

    def models():
        data = metadata_probe(config.engine.ollama.host, "/api/tags")
        return [{"name": m["name"], "size": m.get("size")} for m in data["models"]]

    record("installed_ollama_models", models)
    local = OllamaEngine(
        host=config.engine.ollama.host or None,
        timeout=120,
        num_ctx=config.engine.ollama.num_ctx or None,
    )
    pool = FreePoolEngine([("ollama", local)], allow_remote=False)
    for alias in (
        "local/fast",
        "local/code",
        "local/research",
        "local/vision",
        "free/code",
        "free/research",
        "free/vision",
    ):

        def infer(alias=alias):
            result = pool.generate(
                [Message(Role.USER, "Reply with ACCEPTANCE_OK.")],
                model=alias,
                max_tokens=64,
                temperature=0,
            )
            if not result.get("content", "").strip():
                raise RuntimeError("Empty model response")
            return {
                "routing": result.get("routing"),
                "output_sha256": hashlib.sha256(result["content"].encode()).hexdigest(),
                "scope": "text inference; vision image tested separately",
            }

        record(alias, infer)

    def embedding():
        vector = OllamaEmbedder(host=config.engine.ollama.host).embed(
            "Synthetic acceptance document"
        )
        if vector is None or len(vector) != 768 * 4:
            raise RuntimeError("Expected a 768-dimensional local embedding")
        return {"model": "nomic-embed-text", "dimensions": 768}

    record("nomic_local_embedding", embedding)

    def vision():
        import base64
        import struct
        import zlib

        def chunk(kind, data):
            return (
                struct.pack("!I", len(data))
                + kind
                + data
                + struct.pack("!I", zlib.crc32(kind + data))
            )

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack("!2I5B", 128, 128, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\0\0" * 128) * 128))
            + chunk(b"IEND", b"")
        )
        result = pool.generate(
            [
                Message(
                    Role.USER,
                    "What is the dominant color? One word.",
                    images=[base64.b64encode(png).decode()],
                )
            ],
            model="local/vision",
            max_tokens=32,
            temperature=0,
        )
        if "red" not in result.get("content", "").lower():
            raise RuntimeError("Vision probe did not identify the synthetic red image")
        return {"synthetic_image": "128x128 red", "routing": result.get("routing")}

    record("local_vision_image", vision)

    def scheduled_execution():
        from openjarvis.core.events import EventBus
        from openjarvis.scheduler.scheduler import TaskScheduler
        from openjarvis.scheduler.store import SchedulerStore
        from openjarvis.system import JarvisSystem

        bus = EventBus(record_history=True)
        system = JarvisSystem(
            config, bus, pool, "free-pool", "local/fast", agent_name="none"
        )
        store = SchedulerStore(run_dir / "synthetic-scheduler.db")
        scheduler = TaskScheduler(store, system, bus=bus)
        try:
            task = scheduler.create_task(
                "Reply ACCEPTANCE_OK", "once", "2099-01-01T00:00:00+00:00", agent="none"
            )
            scheduler.run_task(task.id)
            log = store.get_run_logs(task.id)[0]
            if not log["success"] or not log["result"]:
                raise RuntimeError("Scheduled inference failed")
            return {
                "task_id": task.id,
                "success": True,
                "scope": "isolated acceptance SQLite; real local inference",
            }
        finally:
            scheduler.stop()
            store.close()

    record("scheduler_real_local_execution", scheduled_execution)
    isolated = run_dir / "isolated-state"
    isolated.mkdir(exist_ok=True)
    config_file = isolated / "config.toml"
    config_file.write_text(
        '[engine]\ndefault="ollama"\n'
        "[engine.ollama]\nnum_ctx=4096\nhost="
        + json.dumps(config.engine.ollama.host or "http://localhost:11434")
        + "\n"
        '[intelligence]\ndefault_model="local/fast"\nprivate_routing=true\n'
        '[agent]\ndefault_agent="none"\ncontext_from_memory=false\n'
        "[telemetry]\nenabled=false\n"
        "[memory]\ndb_path=" + json.dumps(str(isolated / "memory.db")) + "\n",
        encoding="utf-8",
    )
    environment = dict(
        os.environ,
        OPENJARVIS_HOME=str(isolated),
        OPENJARVIS_CONFIG=str(config_file),
        JARVIS_SKIP_MODEL_PICK="1",
    )

    def cli_check(args, *, input_text=None, require=""):
        result = subprocess.run(
            [sys.executable, "-m", "openjarvis.cli", *args],
            input=input_text,
            cwd=Path(__file__).resolve().parents[3],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        check_cli_output(result, require)
        return {
            "command": args,
            "exit_code": 0,
            "scope": "isolated synthetic user data",
        }

    record(
        "jarvis_chat_real",
        lambda: cli_check(
            ["chat", "-a", "none", "-m", "local/fast", "--skip-runtime-panel"],
            input_text="Reply with ACCEPTANCE_OK.\n/exit\n",
            require="ACCEPTANCE_OK",
        ),
    )
    document = isolated / "acceptance.txt"
    document.write_text(
        "SyntheticAcceptanceToken is the test project identifier.", encoding="utf-8"
    )
    record("memory_index_real", lambda: cli_check(["memory", "index", str(document)]))
    record(
        "memory_search_real",
        lambda: cli_check(
            ["memory", "search", "SyntheticAcceptanceToken"], require="test project"
        ),
    )

    def deep_research():
        from openjarvis.agents.research_loop import ResearchAgent
        from openjarvis.connectors.hybrid_search import HybridSearch
        from openjarvis.connectors.store import KnowledgeStore

        store = KnowledgeStore(db_path=str(isolated / "synthetic-knowledge.db"))
        try:
            store.store(
                content="SyntheticAcceptanceToken has launch date 2099-01-02.",
                source="acceptance",
                doc_id="acceptance-fixture",
                title="Synthetic acceptance fixture",
            )
            agent = ResearchAgent(
                engine=pool,
                search=HybridSearch(store),
                model="local/research",
                max_iterations=2,
                max_tokens=256,
                num_ctx=config.engine.ollama.num_ctx or 4096,
                clarify_handler=lambda question: "Search the synthetic fixture",
            )
            result = agent.run("Search SyntheticAcceptanceToken; cite its launch date.")
            if not result.answer or not result.tool_calls:
                raise RuntimeError(
                    "Research agent did not search knowledge and produce an answer"
                )
            return {
                "iterations": result.iterations,
                "tool_calls": len(result.tool_calls),
                "scope": "local fixture; citations require human review",
            }
        finally:
            store.close()

    record("deep_research_real", deep_research)
    record(
        "voicebox_service",
        lambda: metadata_probe(config.projects.voicebox_host, "/health"),
    )
    voice_status = metadata_probe(config.projects.voicebox_host, "/models/status")
    if speech_fixture is not None:

        def transcribe_fixture():
            from openjarvis.speech.voicebox_stt import VoiceboxSpeechBackend

            audio = speech_fixture.read_bytes()
            result = VoiceboxSpeechBackend(
                host=config.projects.voicebox_host, require_loaded=True
            ).transcribe(audio)
            if not result.text:
                raise RuntimeError("Voicebox STT returned empty text")
            return {
                "text_present": True,
                "audio_sha256": hashlib.sha256(audio).hexdigest(),
                "scope": "operator-supplied synthetic WAV; no audio in ZIP",
            }

        record("voicebox_stt_live", transcribe_fixture)
    loaded_tts = any(
        m.get("model_name") == "kokoro" and m.get("loaded")
        for m in voice_status.get("models", [])
    )
    if not loaded_tts:
        checks.append(
            {
                "name": "voicebox_tts_live",
                "status": "BLOCKED",
                "reason": "Kokoro is not loaded; load the cached model manually.",
            }
        )
    else:

        def voice():
            from openjarvis.speech.voicebox_stt import VoiceboxSpeechBackend
            from openjarvis.speech.voicebox_tts import VoiceboxTTSBackend

            tts = VoiceboxTTSBackend(host=config.projects.voicebox_host)
            result = tts.synthesize(
                "This is a local acceptance test.",
                output_format="wav",
                voice_id=config.speech.voice_id,
            )
            (run_dir / "voicebox-acceptance.wav").write_bytes(result.audio)
            stt = VoiceboxSpeechBackend(
                host=config.projects.voicebox_host, require_loaded=True
            )
            transcription = stt.transcribe(result.audio)
            if not transcription.text:
                raise RuntimeError("Voicebox STT returned empty text")
            return {
                "duration": result.duration_seconds,
                "text_present": True,
                "scope": "synthetic WAV round trip; human listening required",
            }

        record("voicebox_tts_stt_roundtrip", voice)
    local.close()
    tags = metadata_probe(config.engine.ollama.host, "/api/tags")
    metadata = []
    for model in tags.get("models", [])[:12]:
        info = metadata_probe(
            config.engine.ollama.host, "/api/show", {"name": model["name"]}
        )
        metadata.append(
            {
                "id": model["name"],
                "digest": model.get("digest", ""),
                "capabilities": info.get("capabilities", []),
            }
        )
    return catalog_context_sha256(config, metadata)
