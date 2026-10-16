"""Guarded uvicorn logging for the OpenJarvis daemon.

Background loggers (python-telegram-bot, MCP loaders, schedulers) can bubble
records into the ``uvicorn.access`` handler whose ``record.args`` is not the
5-tuple uvicorn's stock ``AccessFormatter`` expects. That raises
``ValueError: not enough values to unpack (expected 5, got 0)`` in the log
flush path. ``GuardedAccessFormatter`` keeps real access lines untouched and
renders foreign records without crashing.
"""

from __future__ import annotations

from typing import Any

from uvicorn.logging import AccessFormatter


class GuardedAccessFormatter(AccessFormatter):
    """AccessFormatter that never explodes on non-access records."""

    def format(self, record: Any) -> str:  # type: ignore[override]
        try:
            if record.args:
                return super().format(record)
        except ValueError:
            pass
        return f"{record.name}: {record.getMessage()}"

    # Mirror of the guard for records with *malformed* tuples (len != 5).
    def formatMessage(self, record: Any) -> str:
        try:
            return super().formatMessage(record)
        except ValueError:
            return f"{record.name}: {record.getMessage()}"


def daemon_log_config() -> dict[str, Any]:
    """uvicorn ``log_config`` dict with guarded access formatting."""

    formatter_access = {
        "()": "openjarvis.server.log_guard.GuardedAccessFormatter",
        "fmt": '%(client_addr)s - "%(request_line)s" %(status_code)s',
    }
    formatter_default = {
        "()": "uvicorn.logging.DefaultFormatter",
        "fmt": "%(levelprefix)s %(message)s",
        "use_colors": None,
    }
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": formatter_default,
            "access": formatter_access,
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        },
    }
