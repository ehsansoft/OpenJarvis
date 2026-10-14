import json
import logging
import os

import pytest

from openjarvis.core import integration_secrets as module


def test_encrypted_store_keeps_values_out_of_json_and_preserves_other_keys(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("NARAROUTER_API_KEY", "")
    monkeypatch.setattr(module, "_crypt", lambda data, decrypt=False: data[::-1])
    store = module.IntegrationSecretStore(tmp_path)
    store.save("telegram", "a synthetic secret value")
    store.save("nararouter", "another synthetic secret")
    assert "synthetic secret" not in store.path.read_text()
    assert store.get("telegram") == "a synthetic secret value"
    assert store.status()["telegram"] is True
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    store.inject()
    assert os.environ["TELEGRAM_BOT_TOKEN"] == "a synthetic secret value"


def test_corrupt_secret_store_is_not_moved_or_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_crypt", lambda data, decrypt=False: data[::-1])
    store = module.IntegrationSecretStore(tmp_path)
    store.path.write_text("invalid")
    with pytest.raises(ValueError):
        store.save("telegram", "some valid value")
    assert store.path.read_text() == "invalid"
    assert list(tmp_path.iterdir()) == [store.path]


def test_saved_tokens_are_redacted_in_client_logs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-secret-log-test")
    monkeypatch.setattr(logging, "_logRecordFactory", logging.getLogRecordFactory())
    module.install_secret_log_redaction()
    record = logging.getLogRecordFactory()(
        "httpx",
        logging.WARNING,
        "",
        1,
        "URL %s",
        ("https://host/synthetic-secret-log-test",),
        None,
    )
    assert "synthetic-secret-log-test" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI")
def test_real_windows_user_bound_dpapi_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    store = module.IntegrationSecretStore(tmp_path)
    store.save("telegram", "synthetic-only-credential-for-dpapi")
    data = json.loads(store.path.read_text())
    assert "synthetic-only" not in json.dumps(data)
    assert store.get("telegram") == "synthetic-only-credential-for-dpapi"
