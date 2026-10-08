"""Tests for the Voicebox speech-to-text adapter."""

from __future__ import annotations

import json

import httpx

from openjarvis.speech.voicebox_stt import VoiceboxSpeechBackend


def test_voicebox_stt_health_and_transcription() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        if request.url.path == "/transcribe":
            return httpx.Response(
                200,
                json={
                    "text": "hello world",
                    "duration": 2.5,
                },
            )
        return httpx.Response(404)

    client = httpx.Client(
        base_url="http://127.0.0.1:17493",
        transport=httpx.MockTransport(handler),
    )
    backend = VoiceboxSpeechBackend(
        client=client,
        model_size="base",
    )

    assert backend.health() is True
    result = backend.transcribe(
        b"RIFF....",
        format="wav",
        language="en",
    )

    assert result.text == "hello world"
    assert result.duration_seconds == 2.5
    assert result.language == "en"
    transcribe = next(
        request for request in requests if request.url.path == "/transcribe"
    )
    assert "multipart/form-data" in transcribe.headers["content-type"]


def test_voicebox_stt_unhealthy_is_nonfatal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "starting"})

    client = httpx.Client(
        base_url="http://127.0.0.1:17493",
        transport=httpx.MockTransport(handler),
    )
    backend = VoiceboxSpeechBackend(client=client)

    assert backend.health() is False
    assert backend.last_error()
