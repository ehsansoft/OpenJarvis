"""Named agent roster registry — T1 of the team-operations plan (2026-10-14).

The roster is the routing surface: named agents with role descriptions,
model aliases, tool policies and privacy labels. Nothing here executes
work or sends messages; assignment and dispatch stay with the caller.

SQLite table ``agent_roster`` (own file ``team.db`` next to the other
per-domain stores). Names are unique, lowercase handles; model aliases
follow the ``local/*`` / ``free/*`` scheme so routing stays explicit.
"""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODEL_ALIAS_RE = re.compile(r"^(local|free)/[a-z]+$")
PRIVACY_LABELS = {"private", "public", "mixed"}
STATUSES = {"active", "paused", "archived"}

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS agent_roster (
    name             TEXT PRIMARY KEY,
    role_description TEXT NOT NULL DEFAULT '',
    model_alias      TEXT NOT NULL DEFAULT 'local/fast',
    tool_policy      TEXT NOT NULL DEFAULT '',
    memory_scope     TEXT NOT NULL DEFAULT 'isolated',
    privacy_label    TEXT NOT NULL DEFAULT 'private',
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       REAL NOT NULL,
    updated_at       REAL NOT NULL
);
"""


class RosterStore:
    """SQLite CRUD store for the named-agent roster."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    # -- Validation -----------------------------------------------------------

    @staticmethod
    def validate_name(name: str) -> str:
        """Return the normalized name, or raise on invalid input."""
        normalized = (name or "").strip().lower()
        if not _NAME_RE.match(normalized):
            raise ValueError(
                "Roster name must be a lowercase handle: letters, digits, "
                "'.', '_', '-' (max 64 chars)"
            )
        return normalized

    @staticmethod
    def validate_model_alias(alias: str) -> str:
        """Model aliases must be explicit ``local/*`` or ``free/*`` routes."""
        normalized = (alias or "").strip().lower()
        if not _MODEL_ALIAS_RE.match(normalized):
            raise ValueError(
                "Model alias must be an explicit route like 'local/fast' "
                "or 'free/research'"
            )
        return normalized

    # -- CRUD -----------------------------------------------------------------

    def add(
        self,
        name: str,
        role_description: str = "",
        model_alias: str = "local/fast",
        *,
        tool_policy: str = "",
        memory_scope: str = "isolated",
        privacy_label: str = "private",
        status: str = "active",
    ) -> Dict[str, Any]:
        """Register a roster entry. Raises ``ValueError`` on duplicates."""
        name = self.validate_name(name)
        model_alias = self.validate_model_alias(model_alias)
        if privacy_label not in PRIVACY_LABELS:
            raise ValueError(f"privacy_label must be one of {sorted(PRIVACY_LABELS)}")
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        now = time.time()
        try:
            self._conn.execute(
                "INSERT INTO agent_roster (name, role_description, model_alias,"
                " tool_policy, memory_scope, privacy_label, status,"
                " created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    role_description,
                    model_alias,
                    tool_policy,
                    memory_scope,
                    privacy_label,
                    status,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Roster name already exists: {name}") from exc
        self._conn.commit()
        return self.get(name)  # type: ignore[return-value]

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Return one roster entry by name, or ``None``."""
        row = self._conn.execute(
            "SELECT * FROM agent_roster WHERE name = ?", (name.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def list(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return roster entries, optionally filtered by status."""
        if status is not None:
            rows = self._conn.execute(
                "SELECT * FROM agent_roster WHERE status = ? ORDER BY name",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM agent_roster ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    def update(self, name: str, **fields: Any) -> Dict[str, Any]:
        """Update whitelisted fields of an existing entry."""
        entry = self.get(name)
        if entry is None:
            raise KeyError(f"Roster entry not found: {name}")
        allowed = {
            "role_description",
            "model_alias",
            "tool_policy",
            "memory_scope",
            "privacy_label",
            "status",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if "model_alias" in updates:
            updates["model_alias"] = self.validate_model_alias(updates["model_alias"])
        if (
            "privacy_label" in updates
            and updates["privacy_label"] not in PRIVACY_LABELS
        ):
            raise ValueError(f"privacy_label must be one of {sorted(PRIVACY_LABELS)}")
        if "status" in updates and updates["status"] not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        if not updates:
            return entry
        sets = ", ".join(f"{k} = ?" for k in updates)
        self._conn.execute(
            f"UPDATE agent_roster SET {sets}, updated_at = ? WHERE name = ?",
            (*updates.values(), time.time(), entry["name"]),
        )
        self._conn.commit()
        return self.get(entry["name"])  # type: ignore[return-value]

    def describe_routing(self) -> str:
        """Render active roster names and roles as a routing prompt block.

        This is the "roster in the system prompt" pattern: concise, factual,
        and limited to active entries so no archived or paused agent is
        addressed by accident.
        """
        entries = self.list(status="active")
        if not entries:
            return "No active agents registered."
        lines = [
            f"- {e['name']}: {e['role_description'] or 'no description'}"
            for e in entries
        ]
        return "Active agent roster:\n" + "\n".join(lines)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()


__all__ = ["RosterStore", "PRIVACY_LABELS", "STATUSES"]
