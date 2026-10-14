from unittest.mock import MagicMock

import numpy as np
import pytest

from openjarvis.memory.scoped_index import ScopedIndex
from openjarvis.tools.storage.sqlite import SQLiteMemory


def test_preview_hash_prevents_stale_approval_and_secret_ingestion(
    tmp_path, monkeypatch
):
    source = tmp_path / "approved.md"
    source.write_text("Approved public fixture")
    index = ScopedIndex(tmp_path, {"notes": source}, MagicMock())
    preview = index.preview(["notes"])
    source.write_text("Changed after preview")
    with pytest.raises(ValueError, match="Sources changed"):
        index.index(["notes"], preview["preview_sha256"], MagicMock())
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "long-synthetic-secret")
    source.write_text("long-synthetic-secret")
    with pytest.raises(ValueError, match="secret"):
        index.preview(["notes"])


def test_existing_fts_is_reused_vectors_rebuild_and_offline_falls_back(tmp_path):
    source = tmp_path / "approved.md"
    source.write_text("Documented apples and oranges")
    embedder = MagicMock()
    embedder.embed_documents.return_value = np.ones(
        (1, 768), dtype=np.float32
    ) / np.sqrt(768)
    embedder.embed_queries.return_value = np.ones((1, 768), dtype=np.float32) / np.sqrt(
        768
    )
    memory = SQLiteMemory(tmp_path / "memory.db")
    index = ScopedIndex(tmp_path, {"notes": source}, embedder)
    preview = index.preview(["notes"])
    assert index.index(["notes"], preview["preview_sha256"], memory)["chunks"] == 1
    assert index.retrieve("fruit", memory)[0].source == str(source)
    index.index(["notes"], preview["preview_sha256"], memory)
    assert len(memory.retrieve("apples")) == 1
    embedder.embed_queries.side_effect = RuntimeError("offline")
    assert index.retrieve("apples", memory)
    source.write_text("Revised source")
    assert index.status()["fresh"] is False
    memory.close()
