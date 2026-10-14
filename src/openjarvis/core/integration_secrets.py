"""Windows user-bound encrypted integration secrets, separate from Git/config."""

from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import threading
import traceback
from pathlib import Path

from openjarvis.core.paths import get_config_dir
from openjarvis.security.file_utils import secure_write_json

SECRET_KEYS = {
    "telegram": "TELEGRAM_BOT_TOKEN",
    "nararouter": "NARAROUTER_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "youcom": "YOUDOTCOM_API_KEY",
    "serply": "SERPLY_API_KEY",
}
_lock = threading.RLock()


def install_secret_log_redaction():
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_jarvis_secret_redaction", False):
        return

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        values = [
            value
            for key in SECRET_KEYS.values()
            if (value := os.environ.get(key)) and len(value) >= 8
        ]
        message = record.getMessage()
        for value in values:
            message = message.replace(value, "[REDACTED]")
        record.msg, record.args = message, ()
        if record.exc_info:
            exception = "".join(traceback.format_exception(*record.exc_info))
            for value in values:
                exception = exception.replace(value, "[REDACTED]")
            record.exc_text, record.exc_info = exception, None
        return record

    factory._jarvis_secret_redaction = True
    logging.setLogRecordFactory(factory)


def _crypt(data: bytes, *, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("Encrypted dashboard credentials require Windows DPAPI")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    incoming = Blob(len(data), buffer)
    outgoing = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if decrypt:
        function = crypt32.CryptUnprotectData
        description = None
    else:
        function = crypt32.CryptProtectData
        description = ctypes.c_wchar_p("OpenJarvis integration credentials")
    function.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not function(
        ctypes.byref(incoming), description, None, None, None, 1, ctypes.byref(outgoing)
    ):
        raise RuntimeError("Windows could not protect integration credentials")
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel32.LocalFree(outgoing.data)


class IntegrationSecretStore:
    def __init__(self, root: Path | None = None):
        self.path = (root or get_config_dir()) / "integration-secrets.json"

    def _read(self):
        if not self.path.exists():
            return {}
        if self.path.is_symlink() or self.path.stat().st_size > 65536:
            raise ValueError("Invalid integration credential store")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("encrypted"), dict)
        ):
            raise ValueError("Invalid integration credential store")
        return data["encrypted"]

    def get(self, provider):
        if provider not in SECRET_KEYS:
            raise ValueError("Unknown integration")
        with _lock:
            encoded = self._read().get(provider)
            if encoded is None:
                return None
            return _crypt(
                base64.b64decode(encoded, validate=True), decrypt=True
            ).decode()

    def save(self, provider, value):
        if (
            provider not in SECRET_KEYS
            or not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError("Invalid integration credential")
        with _lock:
            encrypted = self._read()
            encrypted[provider] = base64.b64encode(
                _crypt(value.strip().encode())
            ).decode()
            secure_write_json(self.path, {"version": 1, "encrypted": encrypted})
        os.environ[SECRET_KEYS[provider]] = value.strip()
        install_secret_log_redaction()

    def status(self):
        encrypted = self._read()
        return {
            name: name in encrypted or bool(os.environ.get(key))
            for name, key in SECRET_KEYS.items()
        }

    def inject(self):
        for name, key in SECRET_KEYS.items():
            value = self.get(name)
            if value:
                os.environ[key] = value
        install_secret_log_redaction()
