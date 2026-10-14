"""Durable task board for agent collaboration — T2 of the team plan.

Design constraints from the project rules:
- No second scheduler loop: the board is a store plus explicit state
  transitions. Dispatch is driven by the existing scheduler tick or by a
  caller; nothing here polls or spawns workers.
- Atomic claims: a task moves ``ready -> running`` through a single
  conditional UPDATE so two workers can never claim the same task.
- Dependency gating: a task with unfinished dependencies cannot be
  claimed; claiming checks every dependency in one transaction.
- Review is a real state: work does not go straight to ``done``; an
  explicit ``approve`` decision completes it (one reviewer per task).

Tables (created on demand in the same SQLite file the caller passes):
``board_tasks``, ``board_task_links`` (dependency edges),
``board_comments`` (inter-agent protocol).
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Task lifecycle. ``triage`` -> ``ready`` -> ``running`` -> ``review``
# -> ``done``. ``blocked`` can be entered from any live state and
# returns to ``triage`` or ``ready``. ``archived`` is terminal.
STATES = {"triage", "ready", "running", "blocked", "review", "done", "archived"}
LIVE_STATES = STATES - {"done", "archived"}

_TRANSITIONS = {
    "triage": {"ready", "blocked", "archived"},
    "ready": {"running", "triage", "blocked", "archived"},
    "running": {"review", "blocked", "ready"},  # ready = stale reclaim
    "review": {"done", "running", "blocked"},  # done only via approve()
    "blocked": {"triage", "ready", "archived"},
    "done": {"archived"},
    "archived": set(),
}

# Claimed tasks whose heartbeat is older than this are reclaimed to
# ``ready`` by maintain(). Bounded default: 15 minutes.
DEFAULT_CLAIM_TTL_SECONDS = 900

_CREATE_TASKS = """\
CREATE TABLE IF NOT EXISTS board_tasks (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT    NOT NULL DEFAULT '',
    state        TEXT    NOT NULL DEFAULT 'triage',
    assignee     TEXT    NOT NULL DEFAULT '',
    claim_owner  TEXT    NOT NULL DEFAULT '',
    claim_expires REAL,
    created_by   TEXT    NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    metadata     TEXT NOT NULL DEFAULT '{}'
);
"""

_CREATE_LINKS = """\
CREATE TABLE IF NOT EXISTS board_task_links (
    task_id    TEXT NOT NULL,
    depends_on TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on)
);
"""

_CREATE_COMMENTS = """\
CREATE TABLE IF NOT EXISTS board_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT NOT NULL,
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class BoardStore:
    """SQLite store for the durable task board."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
    ) -> None:
        if claim_ttl_seconds <= 0:
            raise ValueError("claim_ttl_seconds must be positive")
        self._db_path = str(db_path)
        self._claim_ttl = claim_ttl_seconds
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TASKS)
        self._conn.execute(_CREATE_LINKS)
        self._conn.execute(_CREATE_COMMENTS)
        self._conn.commit()

    # -- Task CRUD -----------------------------------------------------------

    def create(
        self,
        title: str,
        body: str = "",
        *,
        assignee: str = "",
        depends_on: Optional[List[str]] = None,
        created_by: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a task in ``triage`` with optional dependencies."""
        if not title.strip():
            raise ValueError("Task title must not be empty")
        task_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._conn:
            self._conn.execute(
                "INSERT INTO board_tasks (id, title, body, state, assignee,"
                " claim_owner, claim_expires, created_by, created_at, updated_at,"
                " metadata) VALUES (?, ?, ?, 'triage', ?, '', NULL, ?, ?, ?, ?)",
                (
                    task_id,
                    title.strip(),
                    body,
                    assignee.strip(),
                    created_by.strip(),
                    now,
                    now,
                    json.dumps(metadata or {}),
                ),
            )
            for dep in depends_on or []:
                dep = dep.strip()
                if not dep:
                    continue
                if dep == task_id:
                    raise ValueError("A task cannot depend on itself")
                exists = self._conn.execute(
                    "SELECT 1 FROM board_tasks WHERE id = ?", (dep,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"Unknown dependency task: {dep}")
                self._conn.execute(
                    "INSERT OR IGNORE INTO board_task_links (task_id, depends_on)"
                    " VALUES (?, ?)",
                    (task_id, dep),
                )
        return self.get(task_id)  # type: ignore[return-value]

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return one task with dependencies and comments attached."""
        row = self._conn.execute(
            "SELECT * FROM board_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        task = dict(row)
        try:
            task["metadata"] = json.loads(task.get("metadata") or "{}")
        except (json.JSONDecodeError, TypeError):
            task["metadata"] = {}
        task["depends_on"] = [
            r["depends_on"]
            for r in self._conn.execute(
                "SELECT depends_on FROM board_task_links WHERE task_id = ?"
                " ORDER BY depends_on",
                (task_id,),
            )
        ]
        task["comments"] = [
            dict(r)
            for r in self._conn.execute(
                "SELECT id, author, body, created_at FROM board_comments"
                " WHERE task_id = ? ORDER BY id",
                (task_id,),
            )
        ]
        return task

    def list(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return task summaries, optionally filtered by state."""
        if state is not None:
            if state not in STATES:
                raise ValueError(f"Unknown state: {state}")
            rows = self._conn.execute(
                "SELECT * FROM board_tasks WHERE state = ? ORDER BY created_at",
                (state,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM board_tasks ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    # -- State machine -------------------------------------------------------

    @staticmethod
    def _check_transition(current: str, target: str) -> None:
        if target not in _TRANSITIONS[current]:
            raise ValueError(
                f"Illegal transition {current} -> {target}; allowed:"
                f" {sorted(_TRANSITIONS[current]) or 'none'}"
            )

    def set_state(
        self, task_id: str, target: str, *, actor: str = ""
    ) -> Dict[str, Any]:
        """Move a task to *target* through the validated state machine.

        ``done`` is only reachable via :meth:`approve`; direct moves to it
        are rejected even though ``review -> done`` exists on the graph.
        """
        if target not in STATES:
            raise ValueError(f"Unknown state: {target}")
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if target == "done":
            raise ValueError("Use approve() to complete a reviewed task")
        self._check_transition(task["state"], target)
        if target == "review":
            # Keep the claimant attached while work is under review; the
            # claim is frozen (no heartbeat in review), and the reviewer
            # decides done vs. sending it back to the same claimant.
            self._conn.execute(
                "UPDATE board_tasks SET state = 'review', claim_expires = NULL,"
                " updated_at = ? WHERE id = ?",
                (time.time(), task_id),
            )
        else:
            self._conn.execute(
                "UPDATE board_tasks SET state = ?, claim_owner = '',"
                " claim_expires = NULL, updated_at = ? WHERE id = ?",
                (target, time.time(), task_id),
            )
        if actor:
            self._comment(task_id, actor, f"state -> {target}")
        self._conn.commit()
        return self.get(task_id)  # type: ignore[return-value]

    def assign(self, task_id: str, assignee: str) -> Dict[str, Any]:
        """Set the assignee on a live task."""
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task["state"] in {"done", "archived"}:
            raise ValueError("Cannot assign a completed or archived task")
        self._conn.execute(
            "UPDATE board_tasks SET assignee = ?, updated_at = ? WHERE id = ?",
            (assignee.strip(), time.time(), task_id),
        )
        self._conn.commit()
        return self.get(task_id)  # type: ignore[return-value]

    def ready(self, task_id: str, *, actor: str = "") -> Dict[str, Any]:
        """Promote triage/blocked work to ``ready`` (dependency-aware)."""
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task["state"] == "ready":
            return task
        unfinished = self._unfinished_dependencies(task_id)
        if unfinished:
            raise ValueError(f"Dependencies not done: {', '.join(unfinished)}")
        return self.set_state(task_id, "ready", actor=actor)

    def block(
        self, task_id: str, *, reason: str = "", actor: str = ""
    ) -> Dict[str, Any]:
        """Block a live task with an explanatory comment."""
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        result = self.set_state(task_id, "blocked", actor=actor)
        if reason:
            self._comment(task_id, actor or "system", f"blocked: {reason}")
            self._conn.commit()
        return result

    # -- Claims --------------------------------------------------------------

    def claim(self, task_id: str, *, owner: str) -> Dict[str, Any]:
        """Atomically claim a ``ready`` task for *owner*.

        Fails (returns ``None``) when the task is not ready, was claimed by
        someone else, or still has unfinished dependencies. The single
        conditional UPDATE makes concurrent claims safe.
        """
        if not owner.strip():
            raise ValueError("Claim owner must not be empty")
        now = time.time()
        with self._conn:
            row = self._conn.execute(
                "SELECT state FROM board_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Task not found: {task_id}")
            if row["state"] != "ready":
                return None
            if self._unfinished_dependencies(task_id):
                return None
            cur = self._conn.execute(
                "UPDATE board_tasks SET state = 'running', claim_owner = ?,"
                " claim_expires = ?, updated_at = ?"
                " WHERE id = ? AND state = 'ready'",
                (owner.strip(), now + self._claim_ttl, now, task_id),
            )
            if cur.rowcount != 1:
                return None
        return self.get(task_id)

    def heartbeat(self, task_id: str, *, owner: str) -> bool:
        """Extend a claim. Returns False when the claim was lost/reclaimed."""
        cur = self._conn.execute(
            "UPDATE board_tasks SET claim_expires = ?, updated_at = ?"
            " WHERE id = ? AND state = 'running' AND claim_owner = ?",
            (time.time() + self._claim_ttl, time.time(), task_id, owner.strip()),
        )
        self._conn.commit()
        return cur.rowcount == 1

    def maintain(self, *, now: Optional[float] = None) -> int:
        """Reclaim expired claims back to ``ready``. Returns count."""
        now = time.time() if now is None else now
        with self._conn:
            cur = self._conn.execute(
                "UPDATE board_tasks SET state = 'ready', claim_owner = '',"
                " claim_expires = NULL, updated_at = ?"
                " WHERE state = 'running' AND claim_expires IS NOT NULL"
                " AND claim_expires < ?",
                (now, now),
            )
        return cur.rowcount

    # -- Review --------------------------------------------------------------

    def request_review(
        self, task_id: str, *, owner: str, summary: str = ""
    ) -> Dict[str, Any]:
        """Claimant submits work for review with an optional summary."""
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task["state"] != "running" or task["claim_owner"] != owner.strip():
            raise ValueError("Only the current claimant can request review")
        result = self.set_state(task_id, "review", actor=owner)
        if summary:
            self._comment(task_id, owner, f"review requested: {summary}")
            self._conn.commit()
        return result

    def approve(self, task_id: str, *, reviewer: str, note: str = "") -> Dict[str, Any]:
        """One reviewer approves work in ``review``; this is the only
        path to ``done``."""
        if not reviewer.strip():
            raise ValueError("Reviewer must not be empty")
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task["state"] != "review":
            raise ValueError("Only tasks in review can be approved")
        self._conn.execute(
            "UPDATE board_tasks SET state = 'done', claim_owner = '',"
            " claim_expires = NULL, updated_at = ? WHERE id = ?",
            (time.time(), task_id),
        )
        self._comment(task_id, reviewer, f"approved{': ' + note if note else ''}")
        self._conn.commit()
        return self.get(task_id)  # type: ignore[return-value]

    def request_changes(
        self, task_id: str, *, reviewer: str, note: str
    ) -> Dict[str, Any]:
        """Reviewer sends running work back to its claimant."""
        if not note.strip():
            raise ValueError("A change request must include a note")
        task = self.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task["state"] != "review":
            raise ValueError("Only tasks in review can be sent back")
        self._conn.execute(
            "UPDATE board_tasks SET state = 'running', claim_expires = ?,"
            " updated_at = ? WHERE id = ?",
            (time.time() + self._claim_ttl, time.time(), task_id),
        )
        self._comment(task_id, reviewer, f"changes requested: {note.strip()}")
        self._conn.commit()
        return self.get(task_id)  # type: ignore[return-value]

    # -- Comments ------------------------------------------------------------

    def comment(self, task_id: str, *, author: str, body: str) -> None:
        """Public comment API for the inter-agent protocol."""
        if self.get(task_id) is None:
            raise KeyError(f"Task not found: {task_id}")
        self._comment(task_id, author, body)
        self._conn.commit()

    def _comment(self, task_id: str, author: str, body: str) -> None:
        self._conn.execute(
            "INSERT INTO board_comments (task_id, author, body, created_at)"
            " VALUES (?, ?, ?, ?)",
            (task_id, author.strip() or "system", body, time.time()),
        )

    # -- Dependencies --------------------------------------------------------

    def _unfinished_dependencies(self, task_id: str) -> List[str]:
        rows = self._conn.execute(
            "SELECT l.depends_on FROM board_task_links l"
            " JOIN board_tasks t ON t.id = l.depends_on"
            " WHERE l.task_id = ? AND t.state != 'done'",
            (task_id,),
        ).fetchall()
        return [r["depends_on"] for r in rows]

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()


__all__ = ["BoardStore", "STATES", "LIVE_STATES", "DEFAULT_CLAIM_TTL_SECONDS"]
