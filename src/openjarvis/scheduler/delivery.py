"""Derived notification receipts; the existing scheduler owns retries."""

import hashlib
import json
import threading
import time
from pathlib import Path

from openjarvis.security.file_utils import secure_write_json


class NotificationOutbox:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.delivery_lock = threading.Lock()

    def records(self):
        if not self.path.exists():
            return []
        if self.path.is_symlink() or self.path.stat().st_size > 2_000_000:
            raise ValueError("Invalid delivery receipt file")
        data = json.loads(self.path.read_text())
        if not isinstance(data, list):
            raise ValueError("Invalid delivery receipts")
        return data

    def enqueue(self, run_id, channel, chat_id, message):
        key = hashlib.sha256(f"{run_id}|{channel}|{chat_id}".encode()).hexdigest()
        with self.lock:
            rows = self.records()
            if any(row["id"] == key for row in rows):
                return
            if len([r for r in rows if r["status"] == "pending"]) >= 200:
                raise RuntimeError("Notification queue needs review")
            rows.append(
                {
                    "id": key,
                    "run_id": run_id,
                    "channel": channel,
                    "chat_id": chat_id,
                    "message": message[:3500],
                    "status": "pending",
                    "attempts": 0,
                    "next_retry": 0,
                }
            )
            secure_write_json(self.path, rows[-500:])

    def drain(self, send, now=None):
        if not self.delivery_lock.acquire(blocking=False):
            return
        try:
            now = time.time() if now is None else now
            with self.lock:
                due = [
                    dict(r)
                    for r in self.records()
                    if r["status"] == "pending" and r["next_retry"] <= now
                ][:20]
            for row in due:
                try:
                    success = bool(send(row["channel"], row["chat_id"], row["message"]))
                except Exception:
                    success = False
                with self.lock:
                    rows = self.records()
                    current = next(r for r in rows if r["id"] == row["id"])
                    current["attempts"] += 1
                    current["status"] = (
                        "delivered"
                        if success
                        else "failed"
                        if current["attempts"] >= 6
                        else "pending"
                    )
                    current["next_retry"] = now + min(300, 5 * 2 ** current["attempts"])
                    if success:
                        current["delivered_at"] = now
                    secure_write_json(self.path, rows)
        finally:
            self.delivery_lock.release()
