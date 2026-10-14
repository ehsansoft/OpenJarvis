"""Tests for RosterStore — named-agent registry (T1)."""

from __future__ import annotations

import pytest

from openjarvis.team.roster import RosterStore


@pytest.fixture()
def store(tmp_path):
    s = RosterStore(tmp_path / "team_test.db")
    yield s
    s.close()


class TestRosterCRUD:
    def test_add_and_get(self, store):
        entry = store.add("researcher", "Reads sources and writes notes")
        assert entry["name"] == "researcher"
        assert entry["model_alias"] == "local/fast"
        assert entry["privacy_label"] == "private"
        assert entry["status"] == "active"
        got = store.get("researcher")
        assert got is not None
        assert got["role_description"] == "Reads sources and writes notes"

    def test_name_is_normalized(self, store):
        entry = store.add("Coder-1", "Writes code")
        assert entry["name"] == "coder-1"

    def test_invalid_name_rejected(self, store):
        with pytest.raises(ValueError):
            store.add("Bad Name!", "x")

    def test_duplicate_rejected(self, store):
        store.add("researcher")
        with pytest.raises(ValueError):
            store.add("researcher")

    def test_get_missing_returns_none(self, store):
        assert store.get("nobody") is None

    def test_update_role_and_model(self, store):
        store.add("coder", "Old role")
        updated = store.update(
            "coder", role_description="New role", model_alias="free/code"
        )
        assert updated["role_description"] == "New role"
        assert updated["model_alias"] == "free/code"

    def test_update_missing_raises(self, store):
        with pytest.raises(KeyError):
            store.update("ghost", role_description="x")

    def test_invalid_model_alias_rejected(self, store):
        with pytest.raises(ValueError):
            store.add("coder", model_alias="gpt-4")
        with pytest.raises(ValueError):
            store.add("coder", model_alias="local/")

    def test_invalid_privacy_rejected(self, store):
        with pytest.raises(ValueError):
            store.add("coder", privacy_label="secret")

    def test_list_filters_by_status(self, store):
        store.add("a")
        store.add("b")
        store.update("b", status="paused")
        active = store.list(status="active")
        assert [e["name"] for e in active] == ["a"]
        assert len(store.list()) == 2


class TestRoutingDescription:
    def test_describe_routing_only_active(self, store):
        store.add("researcher", "Researches sources")
        store.add("coder", "Writes code")
        store.update("coder", status="archived")
        text = store.describe_routing()
        assert "researcher: Researches sources" in text
        assert "coder" not in text

    def test_describe_routing_empty(self, store):
        assert store.describe_routing() == "No active agents registered."
