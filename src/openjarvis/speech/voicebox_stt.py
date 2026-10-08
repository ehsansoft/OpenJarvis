"""Voicebox speech-to-text backend using the local REST API."""

from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from openjarvis.core.registry import SpeechRegistry
from openjarvis.speech._stubs import Segment, SpeechBackend, TranscriptionResult

logger = logging.getLogger(__name__)


def _normalize_host(host: str) -> str:
    return (host or "http://127.0.0.1:17493").rstrip("/")


_MIME_BY_FORMAT = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "webm": "audio/webm",
}


@SpeechRegistry.register("voicebox")
class VoiceboxSpeechBackend(SpeechBackend):
    """Reuse Voicebox's local Whisper service instead of loading a second copy."""

    backend_id = "voicebox"

    def __init__(
        self,
        *,
        host: str = "http://127.0.0.1:17493",
        model_size: str = "base",
        timeout: float = 180.0,
        client: httpx.Client | None = None,
        require_loaded: bool = False,
    ) -> None:
        self._host = _normalize_host(host)
        self._model_size = model_size or "base"
        self._timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._host,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )
        self._last_error: Optional[str] = None
        self._require_loaded = require_loaded

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        fmt = format.lstrip(".").lower() or "wav"
        filename = f"audio.{fmt}"
        content_type = _MIME_BY_FORMAT.get(
            fmt,
            "application/octet-stream",
        )
        data = {"model_size": self._model_size}
        if language:
            data["language"] = language

        try:
            if self._require_loaded:
                status = self._client.get("/models/status")
                status.raise_for_status()
                if not any(
                    m.get("model_name") == f"whisper-{self._model_size}"
                    and m.get("loaded")
                    for m in status.json().get("models", [])
                ):
                    raise RuntimeError("Load cached Whisper in Voicebox first")
            response = self._client.post(
                "/transcribe",
                files={"file": (filename, audio, content_type)},
                data=data,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            self._last_error = str(exc)
            raise RuntimeError(f"Voicebox transcription failed: {exc}") from exc

        text = str(payload.get("text") or "").strip()
        duration = float(payload.get("duration") or 0.0)
        resolved_language = payload.get("language") or language or None
        self._last_error = None

        segments = []
        if text:
            segments.append(
                Segment(
                    text=text,
                    start=0.0,
                    end=duration,
                    confidence=None,
                )
            )

        return TranscriptionResult(
            text=text,
            language=resolved_language,
            confidence=None,
            duration_seconds=duration,
            segments=segments,
        )

    def health(self) -> bool:
        try:
            response = self._client.get("/health", timeout=5.0)
            response.raise_for_status()
            payload = response.json()
            status = str(payload.get("status") or "").lower()
            healthy = status in {"healthy", "ok", "ready"} or not status
            if healthy:
                self._last_error = None
            else:
                self._last_error = f"Voicebox health status: {status}"
            return healthy
        except Exception as exc:
            self._last_error = str(exc)
            logger.debug("Voicebox STT health check failed: %s", exc)
            return False

    def last_error(self) -> Optional[str]:
        return self._last_error

    def supported_formats(self) -> List[str]:
        return ["wav", "mp3", "m4a", "ogg", "flac", "webm"]

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


__all__ = ["VoiceboxSpeechBackend"]
