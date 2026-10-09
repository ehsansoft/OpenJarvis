"""Reuse an already loaded Voicebox Kokoro engine; never load or download models."""

import io
import time
import wave

import httpx

from openjarvis.core.http import trust_environment_for_url
from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult


@TTSRegistry.register("voicebox")
class VoiceboxTTSBackend(TTSBackend):
    backend_id = "voicebox"

    def __init__(self, *, host=None, client=None, timeout=120):
        if host is None:
            from openjarvis.core.config import load_config

            host = load_config().projects.voicebox_host
        self._client = client or httpx.Client(
            base_url=host.rstrip("/"),
            timeout=10,
            trust_env=trust_environment_for_url(host),
        )
        self._owns_client = client is None
        self._timeout = timeout

    def _profiles(self):
        response = self._client.get("/profiles")
        response.raise_for_status()
        return [
            p
            for p in response.json()
            if p.get("preset_engine") == "kokoro" and p.get("voice_type") == "preset"
        ]

    def available_voices(self):
        return [p["id"] for p in self._profiles()]

    def health(self):
        try:
            response = self._client.get("/health")
            return response.is_success
        except httpx.HTTPError:
            return False

    def synthesize(self, text, *, voice_id="", speed=1.0, output_format="wav"):
        if speed != 1.0 or output_format != "wav":
            raise ValueError("Voicebox supports WAV at the configured profile speed")
        status = self._client.get("/models/status")
        status.raise_for_status()
        models = status.json().get("models", [])
        if not any(m.get("model_name") == "kokoro" and m.get("loaded") for m in models):
            raise RuntimeError(
                "Load installed Kokoro in Voicebox first; no automatic downloads"
            )
        profiles = self._profiles()
        profile = (
            next(
                (
                    p
                    for p in profiles
                    if voice_id in (p["id"], p.get("name"), p.get("preset_voice_id"))
                ),
                None,
            )
            if voice_id
            else next(iter(profiles), None)
        )
        if profile is None:
            raise RuntimeError("Choose an existing Voicebox Kokoro preset profile")
        response = self._client.post(
            "/generate",
            json={
                "profile_id": profile["id"],
                "text": text,
                "engine": "kokoro",
                "language": profile.get("language", "en"),
                "personality": False,
            },
        )
        response.raise_for_status()
        generation = response.json()
        generation_id = generation["id"]
        deadline = time.monotonic() + self._timeout
        while generation.get("status") not in {"completed", "failed", "cancelled"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Voicebox generation is still running; inspect it before retrying"
                )
            time.sleep(0.25)
            # /generate/{id}/status is an SSE stream in Voicebox 0.5.
            # History exposes the same persisted state as bounded JSON.
            response = self._client.get(f"/history/{generation_id}")
            response.raise_for_status()
            generation = response.json()
        if generation.get("status") != "completed":
            raise RuntimeError("Voicebox generation failed; inspect Voicebox history")
        audio = self._client.get(f"/audio/{generation_id}")
        audio.raise_for_status()
        with wave.open(io.BytesIO(audio.content)) as wav:
            rate = wav.getframerate()
            duration = wav.getnframes() / rate
        return TTSResult(
            audio.content,
            "wav",
            duration,
            profile["id"],
            rate,
            {"generation_id": generation_id},
        )

    def close(self):
        if self._owns_client:
            self._client.close()
