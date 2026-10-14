"""OpenCode free-tier relay engine — the official OpenCode CLI as a relay.

OpenCode's free tier is explicitly restricted to requests made "from within
OpenCode": direct HTTP calls without the client get HTTP 403
``FreeTierError`` ("OpenCode's free tier can only be used from within
OpenCode"). The sanctioned programmatic interface is therefore the CLI itself
— ``opencode run --format json`` accepts prompts on stdin and streams NDJSON
parts back (verified live: verbatim completion in ~4-8s).

Safety properties of the relay:

* ``--agent plan`` — OpenCode's built-in read-only agent: no edits, no shell.
* temp working directory — even an errant tool call touches an empty dir.
* prompt travels on stdin — never through argv, so no quoting/injection path.
* roster TTL-cached — ``opencode models`` runs at most once per refresh window.

Model ids are advertised with the ``opencode/`` prefix (matching the editors'
``opencode/<id>`` convention) and stripped again when building CLI arguments.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Sequence
from typing import Any, Dict, List

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message
from openjarvis.engine._base import (
    EngineConnectionError,
    estimate_prompt_tokens,
    messages_to_dicts,
)
from openjarvis.engine._stubs import InferenceEngine

logger = logging.getLogger(__name__)

#: Advertised prefix for every model this engine owns.
MODEL_PREFIX = "opencode/"

#: Read-only built-in agent: relayed prompts can never edit or run anything.
_RELAY_AGENT = "plan"

#: Fallback roster when ``opencode models`` cannot run (mirrors the CLI's
#: free-tier list at the time of writing; live discovery supersedes it).
_DEFAULT_ROSTER = (
    "big-pickle",
    "cat-jam-free",
    "longcat-2.5-preview-free",
    "mimo-v2.6-flash-free",
    "muse-spark-1.3-contributor-free",
    "nemotron-3-ultra-free",
    "nemotron-3.5-lightning-free",
    "space-bunny-free",
    "step-5-preview-free",
)

_ROSTER_TTL_SECONDS = 300.0


def _parse_relay_output(stdout: str) -> str:
    """Concatenate ``text`` parts from the CLI's NDJSON event stream."""
    pieces: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        part = event.get("part") or {}
        text = part.get("text")
        if isinstance(text, str) and text:
            pieces.append(text)
    if pieces:
        return "".join(pieces)
    # Older/plain output: fall back to the raw stdout minus blank lines.
    return stdout.strip()


@EngineRegistry.register("opencode")
class OpenCodeEngine(InferenceEngine):
    """Chat completions relayed through the local OpenCode CLI."""

    engine_id = "opencode"
    # The relay process runs locally; the *inference* is remote — classify as
    # cloud so free-pool privacy checks never mistake it for zero-API-local.
    is_cloud = True

    def __init__(
        self,
        path: str | None = None,
        *,
        timeout: float = 300.0,
        refresh_seconds: float = _ROSTER_TTL_SECONDS,
    ) -> None:
        self._configured = path or None
        self._timeout = timeout
        self._refresh = max(30.0, refresh_seconds)
        self._binary: str | None = None
        self._roster: list[str] | None = None
        self._roster_at = 0.0

    # -- binary / roster ----------------------------------------------------

    def _resolve_binary(self) -> str | None:
        if self._binary:
            return self._binary
        candidates: list[str] = []
        if self._configured:
            candidates.append(self._configured)
        which = shutil.which("opencode")
        if which:
            candidates.append(which)
        for candidate in candidates:
            if os.path.isfile(candidate):
                self._binary = candidate
                return candidate
            resolved = shutil.which(candidate)
            if resolved:
                self._binary = resolved
                return resolved
        return None

    def _load_roster(self, *, force: bool = False) -> list[str]:
        now = time.monotonic()
        if (
            not force
            and self._roster is not None
            and now - self._roster_at < self._refresh
        ):
            return self._roster
        roster: list[str] = []
        binary = self._resolve_binary()
        if binary:
            try:
                proc = self._run_cli(
                    [binary, "models"],
                    input_text="",
                    cwd=None,
                    timeout=60.0,
                )
                for line in (proc.stdout or "").splitlines():
                    line = line.strip()
                    if line.startswith(MODEL_PREFIX):
                        model_id = line[len(MODEL_PREFIX) :]
                        if model_id and " " not in model_id:
                            roster.append(model_id)
            except (OSError, subprocess.SubprocessError) as exc:
                logger.debug("opencode roster refresh failed: %s", exc)
        if not roster:
            roster = list(_DEFAULT_ROSTER)
        self._roster = roster
        self._roster_at = now
        return roster

    def _run_cli(
        self,
        args: list[str],
        *,
        input_text: str,
        cwd: str | None,
        timeout: float,
    ) -> subprocess.CompletedProcess:
        """Spawn the CLI (single seam so tests can fake completions)."""
        env = dict(os.environ)
        env.setdefault("NO_COLOR", "1")
        return subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=env,
            shell=False,
        )

    # -- prompt rendering ---------------------------------------------------

    @staticmethod
    def _render_prompt(messages: Sequence[Message]) -> str:
        """Render the conversation as a role-tagged transcript.

        The trailing ``[assistant]`` marker makes the relayed model answer as
        the assistant instead of continuing the user's turn.
        """
        blocks: list[str] = []
        for message in messages_to_dicts(messages):
            role = message.get("role") or "user"
            content = message.get("content") or ""
            blocks.append(f"[{role}]\n{content}")
        blocks.append("[assistant]")
        return "\n\n".join(blocks)

    # -- InferenceEngine interface -----------------------------------------

    def health(self) -> bool:
        return self._resolve_binary() is not None

    def list_models(self) -> List[str]:
        return [f"{MODEL_PREFIX}{model_id}" for model_id in self._load_roster()]

    def list_free_model_ids(self) -> list[str]:
        # Everything the CLI advertises under ``opencode/`` is free-tier.
        return self.list_models()

    def list_model_metadata(self) -> list[dict[str, Any]]:
        return [
            {"id": f"{MODEL_PREFIX}{model_id}", "free": True}
            for model_id in self._load_roster()
        ]

    def can_serve(self, model: str) -> bool:
        if not model.startswith(MODEL_PREFIX):
            return False
        return model[len(MODEL_PREFIX) :] in self._load_roster()

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        binary = self._resolve_binary()
        if not binary:
            raise EngineConnectionError(
                "OpenCode CLI not found; install OpenCode or set "
                "engine.opencode.path in config.toml"
            )
        model_id = model
        if model_id.startswith(MODEL_PREFIX):
            model_id = model_id[len(MODEL_PREFIX) :]
        if model_id not in self._load_roster():
            raise EngineConnectionError(
                f"OpenCode relay has no model {model!r} in its free roster"
            )
        prompt = self._render_prompt(messages)
        try:
            with tempfile.TemporaryDirectory(prefix="oj-opencode-relay-") as tmp:
                proc = self._run_cli(
                    [
                        binary,
                        "run",
                        "--agent",
                        _RELAY_AGENT,
                        "--format",
                        "json",
                        "-m",
                        f"{MODEL_PREFIX}{model_id}",
                    ],
                    input_text=prompt,
                    cwd=tmp,
                    timeout=self._timeout,
                )
        except subprocess.TimeoutExpired as exc:
            raise EngineConnectionError(
                f"OpenCode relay timed out after {self._timeout:.0f}s"
            ) from exc
        except OSError as exc:
            raise EngineConnectionError(
                f"OpenCode relay failed to start: {exc}"
            ) from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-400:]
            raise EngineConnectionError(
                f"OpenCode relay exited with {proc.returncode}: {detail}"
            )
        content = _parse_relay_output(proc.stdout or "")
        prompt_tokens = estimate_prompt_tokens(messages)
        completion_tokens = max(1, len(content) // 4)
        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "prompt_tokens_evaluated": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "model": model,
            "finish_reason": "stop" if content else "error",
        }

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ):
        """Relay one completion, then emit it in coarse chunks.

        The CLI itself has no token stream, so consumers see progressive
        output only after the relay returns; ``stream_full``'s default wraps
        this path automatically.
        """
        result = await asyncio.to_thread(
            self.generate,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        content = result.get("content") or ""
        step = 48
        for start in range(0, len(content), step):
            yield content[start : start + step]
            await asyncio.sleep(0)

    def close(self) -> None:
        return None


__all__ = ["OpenCodeEngine", "MODEL_PREFIX"]
