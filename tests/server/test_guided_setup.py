from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.core.config import JarvisConfig
from openjarvis.server import setup_router
from openjarvis.server.control_router import initialize_control


@pytest.fixture
def setup(tmp_path, monkeypatch):
    cfg = JarvisConfig()
    cfg.security.private_operations = True
    (tmp_path / "config.toml").write_text("[server]\nport=18080\n")
    monkeypatch.setattr(setup_router, "get_config_dir", lambda: tmp_path)
    store = MagicMock()
    store.status.return_value = {"telegram": False, "nararouter": False}
    store.get.return_value = "123456:abcdefghijklmnopqrstuvwxyz1234567890"
    monkeypatch.setattr(setup_router, "_store", lambda: store)
    app = FastAPI()
    app.state.config = cfg
    initialize_control(app)
    client = TestClient(
        app, base_url="http://127.0.0.1:18080", headers={"X-Jarvis-Control": "1"}
    )
    return client, cfg, store, tmp_path


def test_secret_save_does_not_echo_or_validate_with_pydantic_input(setup):
    client, _, store, _ = setup
    token = "123456:abcdefghijklmnopqrstuvwxyz1234567890"
    result = client.post(
        "/v1/control/setup/credentials/telegram", json={"value": token}
    )
    assert result.status_code == 200
    assert token not in result.text
    assert store.save.call_args.args == ("telegram", token)
    bad = client.post(
        "/v1/control/setup/credentials/telegram", json={"value": {"secret": token}}
    )
    assert bad.status_code == 400 and token not in bad.text


def test_foreign_origin_cannot_save_a_secret(setup):
    client, _, store, _ = setup
    response = client.post(
        "/v1/control/setup/credentials/telegram",
        json={"value": "secret"},
        headers={"Origin": "https://other.invalid"},
    )
    assert response.status_code == 403
    store.save.assert_not_called()


def test_empty_chat_allowlist_refuses_enable_and_discovery_refuses_duplicate_poller(
    setup, monkeypatch
):
    client, cfg, _, _ = setup
    assert client.post("/v1/control/setup/telegram/state/enable").status_code == 409
    cfg.channel.enabled = True
    remote = MagicMock()
    monkeypatch.setattr(setup_router, "_telegram", remote)
    assert client.post("/v1/control/setup/telegram/discover-chats").status_code == 409
    remote.assert_not_called()


def test_allowed_chats_merge_preserves_existing_config_without_token(setup):
    client, cfg, _, root = setup
    assert (
        client.post(
            "/v1/control/setup/telegram/chats", json={"chat_ids": "123, -456, 123"}
        ).status_code
        == 200
    )
    assert cfg.channel.telegram.allowed_chat_ids == "123,-456"
    text = (root / "config.toml").read_text()
    assert "port=18080" in text and "123,-456" in text
    assert "BOT_TOKEN" not in text


def test_bot_check_sanitizes_token_bearing_network_error(monkeypatch):
    token = "123456:abcdefghijklmnopqrstuvwxyz1234567890"
    monkeypatch.setattr(
        setup_router.httpx, "Client", MagicMock(side_effect=RuntimeError(token))
    )
    with pytest.raises(Exception) as error:
        setup_router._telegram("getMe", token)
    assert token not in str(error.value)
