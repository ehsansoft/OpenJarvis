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

    def _loaded_engines(self):
        try:
            status = self._client.get("/models/status")
            status.raise_for_status()
            models = status.json().get("models", [])
            return {
                m.get("model_name")
                for m in models
                if m.get("loaded") or m.get("downloaded") and m.get("loaded")
            }
        except httpx.HTTPError:
            return set()

    def synthesize(self, text, *, voice_id="", speed=1.0, output_format="wav"):
        if speed != 1.0 or output_format != "wav":
            raise ValueError("Voicebox supports WAV at the configured profile speed")
        # Prefer kokoro, but fall over to ANY engine Voicebox has loaded so a
        # stale app state can't mute the chat. Profiles carry their engine.
        loaded = self._loaded_engines()
        if "kokoro" not in loaded:
            if not loaded:
                raise RuntimeError(
                    "No TTS engine is loaded in Voicebox (open it once to load kokoro);"
                    " no automatic downloads"
                )
        profiles = self._profiles()
        candidates = [
            p for p in profiles if p.get("preset_engine") in loaded
        ] or profiles
        profile = (
            next(
                (
                    p
                    for p in candidates
                    if voice_id in (p["id"], p.get("name"), p.get("preset_voice_id"))
                ),
                None,
            )
            if voice_id
            else next(iter(candidates), None)
        )
        if profile is None:
            raise RuntimeError("Choose an existing Voicebox Kokoro preset profile")
        response = self._client.post(
            "/generate",
            json={
                "profile_id": profile["id"],
                "text": text,
                "engine": profile.get("preset_engine", "kokoro"),
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
            {
                "generation_id": generation_id,
                # The Voicebox desktop app plays completed generations itself;
                # the chat must not replay the same audio locally.
                "server_played": True,
            },
        )

    def close(self):
        if self._owns_client:
            self._client.close()
