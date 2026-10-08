"""OS-held scheduler ownership; the lock file remains after shutdown."""

import os
from pathlib import Path


class SchedulerOwnership:
    def __init__(self, db_path):
        self.path = (
            None if db_path == ":memory:" else Path(str(db_path) + ".owner.lock")
        )
        self.file = None

    def acquire(self):
        if self.path is None or self.file is not None:
            return
        handle = self.path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RuntimeError("Another runtime owns this scheduler database") from exc
        self.file = handle

    def release(self):
        if self.file is not None:
            self.file.close()
            self.file = None
