"""Voicebox WAV synthesis reuses loaded models and never requests downloads."""

import io
import wave

import httpx
import pytest

from openjarvis.speech.voicebox_tts import VoiceboxTTSBackend


def fixture_client(*, loaded=True):
    calls = []
    wav_bytes = io.BytesIO()
    with wave.open(wav_bytes, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * 2400)

    def handler(request):
        calls.append(request.url.path)
        path = request.url.path
        if path == "/models/status":
            return httpx.Response(
                200, json={"models": [{"model_name": "kokoro", "loaded": loaded}]}
            )
        if path == "/profiles":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "preset",
                        "voice_type": "preset",
                        "preset_engine": "kokoro",
                        "language": "en",
                    }
                ],
            )
        if path == "/generate":
            return httpx.Response(200, json={"id": "generation", "status": "completed"})
        if path == "/audio/generation":
            return httpx.Response(200, content=wav_bytes.getvalue())
        return httpx.Response(200, json={"status": "healthy"})

    return httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(handler)
    ), calls


def test_loaded_voicebox_returns_playable_wav():
    client, calls = fixture_client()
    backend = VoiceboxTTSBackend(client=client)
    result = backend.synthesize("Acceptance", output_format="wav")
    assert result.audio.startswith(b"RIFF")
    assert result.sample_rate == 24000
    assert result.duration_seconds == 0.1
    assert not any("load" in path or "download" in path for path in calls)
    client.close()


def test_unloaded_voicebox_never_loads_or_downloads():
    client, calls = fixture_client(loaded=False)
    with pytest.raises(RuntimeError, match="no automatic downloads"):
        VoiceboxTTSBackend(client=client).synthesize("Acceptance")
    assert calls == ["/models/status"]
    client.close()


def test_generation_polls_json_history_instead_of_sse_status():
    """Voicebox 0.5 returns SSE at /generate/{id}/status, not JSON."""
    client, _ = fixture_client()
    original = client._transport.handler
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/generate":
            return httpx.Response(
                200, json={"id": "generation", "status": "generating"}
            )
        if request.url.path == "/generate/generation/status":
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text='data: {"status": "completed"}\n\n',
            )
        if request.url.path == "/history/generation":
            return httpx.Response(200, json={"id": "generation", "status": "completed"})
        return original(request)

    client._transport.handler = handler
    result = VoiceboxTTSBackend(client=client).synthesize("Acceptance")
    assert result.audio.startswith(b"RIFF")
    assert "/history/generation" in calls
    assert "/generate/generation/status" not in calls
    assert calls.count("/generate") == 1
    client.close()
