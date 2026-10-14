"""Tests for BoardStore — durable task board (T2).

Covers the acceptance points from the team plan: atomic claims, dependency
gating, review as a real state, stale-claim reclaim and restart survival.
"""

from __future__ import annotations

import pytest

from openjarvis.team.board import BoardStore


@pytest.fixture()
def store(tmp_path):
    s = BoardStore(tmp_path / "board_test.db")
    yield s
    s.close()


class TestTaskLifecycle:
    def test_create_starts_in_triage(self, store):
        task = store.create("Write report", "body")
        assert task["state"] == "triage"
        assert task["depends_on"] == []
        assert task["comments"] == []

    def test_full_happy_path(self, store):
        task = store.create("Ship feature")
        tid = task["id"]
        assert store.ready(tid)["state"] == "ready"
        claimed = store.claim(tid, owner="coder")
        assert claimed is not None
        assert claimed["state"] == "running"
        assert claimed["claim_owner"] == "coder"
        assert store.request_review(tid, owner="coder")["state"] == "review"
        done = store.approve(tid, reviewer="reviewer")
        assert done["state"] == "done"
        assert done["claim_owner"] == ""

    def test_done_only_via_approve(self, store):
        task = store.create("Ship")
        with pytest.raises(ValueError, match="approve"):
            store.set_state(task["id"], "done")

    def test_illegal_transition_rejected(self, store):
        task = store.create("Ship")
        # triage -> running skips ready; review requires a claim first.
        with pytest.raises(ValueError, match="Illegal transition"):
            store.set_state(task["id"], "running")
        with pytest.raises(ValueError, match="Illegal transition"):
            store.set_state(task["id"], "review")

    def test_unknown_state_rejected(self, store):
        task = store.create("Ship")
        with pytest.raises(ValueError, match="Unknown state"):
            store.set_state(task["id"], "teleported")


class TestAtomicClaims:
    def test_claim_only_ready_task(self, store):
        task = store.create("Ship")
        assert store.claim(task["id"], owner="coder") is None

    def test_second_claim_fails(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        assert store.claim(task["id"], owner="coder") is not None
        assert store.claim(task["id"], owner="other") is None

    def test_empty_owner_rejected(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        with pytest.raises(ValueError):
            store.claim(task["id"], owner="  ")

    def test_heartbeat_extends_claim(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        assert store.heartbeat(task["id"], owner="coder") is True
        assert store.heartbeat(task["id"], owner="impostor") is False

    def test_stale_claim_reclaimed(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        reclaimed = store.maintain(now=task["created_at"] + 10_000)
        assert reclaimed == 1
        got = store.get(task["id"])
        assert got["state"] == "ready"
        assert got["claim_owner"] == ""


class TestDependencies:
    def test_dependency_gates_promotion(self, store):
        first = store.create("Design")
        second = store.create("Build", depends_on=[first["id"]])
        with pytest.raises(ValueError, match="Dependencies not done"):
            store.ready(second["id"])

    def test_dependency_gates_claim(self, store):
        first = store.create("Design")
        second = store.create("Build", depends_on=[first["id"]])
        # Force second into ready to prove the claim itself still checks deps.
        store._conn.execute(
            "UPDATE board_tasks SET state = 'ready' WHERE id = ?", (second["id"],)
        )
        store._conn.commit()
        assert store.claim(second["id"], owner="coder") is None

    def test_ready_after_dependency_done(self, store):
        first = store.create("Design")
        second = store.create("Build", depends_on=[first["id"]])
        store.ready(first["id"])
        store.claim(first["id"], owner="coder")
        store.request_review(first["id"], owner="coder")
        store.approve(first["id"], reviewer="reviewer")
        assert store.ready(second["id"])["state"] == "ready"

    def test_unknown_dependency_rejected(self, store):
        with pytest.raises(ValueError, match="Unknown dependency"):
            store.create("Weird", depends_on=["doesnotexist"])

    def test_empty_dependency_ignored(self, store):
        store.create("Ship")
        task = store.create("Build", depends_on=[""])
        assert task["depends_on"] == []


class TestReview:
    def test_only_claimant_requests_review(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        with pytest.raises(ValueError, match="claimant"):
            store.request_review(task["id"], owner="stranger")

    def test_approve_requires_review_state(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        with pytest.raises(ValueError, match="review"):
            store.approve(task["id"], reviewer="reviewer")

    def test_request_changes_returns_to_running(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        store.request_review(task["id"], owner="coder")
        sent_back = store.request_changes(
            task["id"], reviewer="reviewer", note="add tests"
        )
        assert sent_back["state"] == "running"
        assert sent_back["claim_owner"] == "coder"

    def test_change_request_needs_note(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        store.request_review(task["id"], owner="coder")
        with pytest.raises(ValueError, match="note"):
            store.request_changes(task["id"], reviewer="reviewer", note=" ")

    def test_approve_needs_reviewer(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        store.claim(task["id"], owner="coder")
        store.request_review(task["id"], owner="coder")
        with pytest.raises(ValueError):
            store.approve(task["id"], reviewer=" ")


class TestBlocking:
    def test_block_and_unblock(self, store):
        task = store.create("Ship")
        store.ready(task["id"])
        blocked = store.block(task["id"], reason="needs API key", actor="operator")
        assert blocked["state"] == "blocked"
        got = store.get(task["id"])
        assert any("needs API key" in c["body"] for c in got["comments"])
        assert store.ready(task["id"])["state"] == "ready"


class TestComments:
    def test_comments_recorded_in_order(self, store):
        task = store.create("Ship")
        store.comment(task["id"], author="a", body="first")
        store.comment(task["id"], author="b", body="second")
        got = store.get(task["id"])
        assert [c["body"] for c in got["comments"]][-2:] == ["first", "second"]

    def test_comment_unknown_task_raises(self, store):
        with pytest.raises(KeyError):
            store.comment("missing", author="a", body="x")


class TestPersistence:
    def test_rows_survive_restart(self, tmp_path):
        db = tmp_path / "board_restart.db"
        s1 = BoardStore(db)
        task = s1.create("Persist me", assignee="coder")
        s1.ready(task["id"])
        s1.claim(task["id"], owner="coder")
        s1.close()

        s2 = BoardStore(db)
        got = s2.get(task["id"])
        assert got is not None
        assert got["state"] == "running"
        assert got["claim_owner"] == "coder"
        assert got["assignee"] == "coder"
        s2.close()
