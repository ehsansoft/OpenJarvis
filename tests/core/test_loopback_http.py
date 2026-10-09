"""Local model and speech calls must stay local despite workstation proxies."""

import asyncio
import importlib.util
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from openjarvis.connectors.embeddings import OllamaEmbedder as ConnectorEmbedder
from openjarvis.core.http import trust_environment_for_url
from openjarvis.engine.ollama import OllamaEngine
from openjarvis.mcp.transport import StreamableHTTPTransport
from openjarvis.speech.voicebox_stt import VoiceboxSpeechBackend
from openjarvis.speech.voicebox_tts import VoiceboxTTSBackend
from openjarvis.tools.storage.embeddings import OllamaEmbedder


@pytest.fixture
def local_service(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"healthy","models":[]}')

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"embeddings":[[1.0,0.0]],"embedding":[1.0,0.0]}')

        def log_message(self, *args):
            pass

    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
        # Lowercase remains effective in CGI environments, which deliberately
        # ignore uppercase HTTP_PROXY when REQUEST_METHOD is present.
        monkeypatch.setenv(name.lower(), "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.delenv("no_proxy", raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    worker.join()


@pytest.mark.parametrize(
    "factory", [OllamaEngine, VoiceboxSpeechBackend, VoiceboxTTSBackend]
)
def test_loopback_client_ignores_broken_environment_proxy(local_service, factory):
    backend = factory(host=local_service)
    try:
        response = backend._client.get("/health", timeout=2)
        response.raise_for_status()
        assert response.json()["status"] == "healthy"
    finally:
        backend.close()


def test_ollama_async_stream_transport_also_stays_local(local_service):
    engine = OllamaEngine(host=local_service, timeout=2)

    async def check():
        async with engine._make_async_client() as client:
            response = await client.get("/health")
            response.raise_for_status()
            assert response.json()["status"] == "healthy"

    try:
        asyncio.run(check())
    finally:
        engine.close()


def test_local_embeddings_ignore_environment_proxy(local_service):
    embedder = OllamaEmbedder(base_url=local_service, timeout_s=2)
    assert embedder._embed_batch(["synthetic acceptance"]) == [[1.0, 0.0]]


def test_connector_embeddings_also_stay_local(local_service):
    embedder = ConnectorEmbedder(host=local_service, timeout=2)
    assert embedder.embed("synthetic acceptance") is not None


def test_local_mcp_transport_ignores_environment_proxy(local_service):
    transport = StreamableHTTPTransport(local_service + "/mcp", request_timeout=2)
    try:
        response = transport._client.get(local_service + "/health")
        response.raise_for_status()
        assert response.json()["status"] == "healthy"
    finally:
        transport.close()


def test_finalizer_health_probe_ignores_environment_proxy(local_service, tmp_path):
    path = (
        Path(__file__).resolve().parents[2] / "scripts/install/Finalize-Ehsan-Setup.py"
    )
    spec = importlib.util.spec_from_file_location("proxy_finalizer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    finalizer = module.Finalizer(tmp_path, tmp_path / "state", tmp_path / "projects")
    ok, payload = finalizer._http_get_json(local_service + "/health", timeout=2)
    assert ok is True
    assert payload["status"] == "healthy"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:17493",
        "http://LOCALHOST.:17493",
        "http://127.0.0.2:11434",
        "http://[::1]:17493",
        "http://[::ffff:127.0.0.1]:17493",
    ],
)
def test_loopback_addresses_never_use_environment_proxy(url):
    assert trust_environment_for_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://provider.example",
        "http://192.168.1.2:11434",
        "https://localhost.provider.example",
        "https://localhost@provider.example",
    ],
)
def test_remote_and_lan_services_keep_environment_proxy(url):
    assert trust_environment_for_url(url) is True
