"""Guided setup: encrypted secrets and explicit channel activation on loopback."""

from __future__ import annotations

import os
import re

import httpx
import tomlkit
from fastapi import APIRouter, Depends, HTTPException, Request

from openjarvis.core.integration_secrets import SECRET_KEYS, IntegrationSecretStore
from openjarvis.core.paths import get_config_dir
from openjarvis.security.file_utils import secure_write_text
from openjarvis.server.control_router import local_browser

router = APIRouter(prefix="/v1/control/setup", dependencies=[Depends(local_browser)])


def _store():
    return IntegrationSecretStore(get_config_dir())


def _token():
    return _store().get("telegram") or os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _telegram(method, token, **data):
    if not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{20,100}", token):
        raise HTTPException(400, "Enter a valid BotFather token in Setup first")
    try:
        with httpx.Client(timeout=12, follow_redirects=False) as client:
            response = client.post(
                f"https://api.telegram.org/bot{token}/{method}", json=data
            )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise ValueError("Telegram rejected request")
        return payload["result"]
    except Exception:
        # Never expose the request URL, token, upstream body or raw exception.
        raise HTTPException(
            502, "Telegram did not accept the request; check token or network privately"
        ) from None


def _merge_config(sections):
    path = get_config_dir() / "config.toml"
    if path.is_symlink():
        raise HTTPException(409, "Configuration must be a regular local file")
    document = tomlkit.parse(path.read_text(encoding="utf-8-sig"))
    for parts, values in sections:
        table = document
        for part in parts:
            if part not in table:
                table[part] = tomlkit.table()
            table = table[part]
        table.update(values)
    secure_write_text(path, tomlkit.dumps(document))


@router.get("")
def setup_status(request: Request):
    cfg = request.app.state.config
    try:
        credentials = _store().status()
    except (ValueError, RuntimeError):
        raise HTTPException(
            409, "Stored integration credentials need local recovery"
        ) from None
    return {
        "credentials": credentials,
        "storage": "Windows user-bound DPAPI",
        "allowed_chat_ids": cfg.channel.telegram.allowed_chat_ids,
        "telegram_enabled": cfg.channel.enabled
        and cfg.channel.default_channel == "telegram",
        "private_operations": cfg.security.private_operations,
        "instructions": (
            "Save token, verify bot, save allowed chat IDs, then enable a"
            "nd restart. Telegram carries messages through its cloud."
        ),
    }


@router.post("/credentials/{provider}")
async def save_secret(provider: str, request: Request):
    if provider not in SECRET_KEYS:
        raise HTTPException(404, "Unknown integration")
    try:
        body = await request.json()
        value = body.get("value")
        if (
            not isinstance(value, str)
            or not 8 <= len(value.strip()) <= 512
            or any(ord(x) < 32 for x in value)
        ):
            raise ValueError("Invalid credential")
        if provider == "telegram" and not re.fullmatch(
            r"\d{5,15}:[A-Za-z0-9_-]{20,100}", value.strip()
        ):
            raise ValueError("Invalid token")
        with request.app.state._control_lock:
            _store().save(provider, value)
    except Exception:
        raise HTTPException(
            400,
            (
                "Credential could not be saved; check its format and Windows "
                "storage access"
            ),
        ) from None
    return {"saved": True, "restart_required": True, "provider": provider}


@router.post("/telegram/verify")
def verify_bot():
    bot = _telegram("getMe", _token())
    return {
        "verified": True,
        "username": bot.get("username", ""),
        "bot_id": bot.get("id"),
    }


@router.post("/telegram/discover-chats")
def discover_chats(request: Request):
    cfg = request.app.state.config
    if cfg.channel.enabled:
        raise HTTPException(
            409, "Disable the owned channel and restart before the one-time chat lookup"
        )
    webhook = _telegram("getWebhookInfo", _token())
    if webhook.get("url"):
        raise HTTPException(
            409,
            "This bot has a webhook; review it privately before switching to polling",
        )
    updates = _telegram("getUpdates", _token(), timeout=0, limit=100)
    chats = {}
    for item in updates:
        chat = item.get("message", {}).get("chat", {})
        if chat.get("id") is not None:
            chats[str(chat["id"])] = {
                "id": str(chat["id"]),
                "type": chat.get("type", ""),
            }
    return {
        "chats": list(chats.values()),
        "note": "Select your own chat; discovery does not allow it automatically",
    }


@router.post("/telegram/chats")
async def save_chats(request: Request):
    body = await request.json()
    value = body.get("chat_ids", "")
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"-?\d+(?:\s*,\s*-?\d+)*", value.strip())
        or len(value) > 300
    ):
        raise HTTPException(400, "Enter numeric chat IDs separated by commas")
    value = ",".join(dict.fromkeys(x.strip() for x in value.split(",")))
    with request.app.state._control_lock:
        if request.app.state.config.channel.enabled:
            raise HTTPException(
                409, "Disable and restart the channel before changing its allow-list"
            )
        _merge_config([(("channel", "telegram"), {"allowed_chat_ids": value})])
        request.app.state.config.channel.telegram.allowed_chat_ids = value
    return {"saved": True, "allowed_chat_ids": value}


@router.post("/telegram/state/{action}")
def channel_state(action: str, request: Request):
    if action not in {"enable", "disable"}:
        raise HTTPException(404, "Unknown channel action")
    cfg = request.app.state.config
    if action == "enable":
        if (
            not cfg.security.private_operations
            or not cfg.channel.telegram.allowed_chat_ids
            or not _token()
        ):
            raise HTTPException(
                409, "Private permissions, saved token and allowed chats are required"
            )
        _telegram("getMe", _token())
        system = getattr(request.app.state, "runtime_system", None)
        if system is None or system.capability_policy is None:
            raise HTTPException(
                409,
                (
                    "Restart Jarvis with enforced private permissions before enab"
                    "ling the bot"
                ),
            )
    with request.app.state._control_lock:
        _merge_config(
            [
                (
                    ("channel",),
                    {
                        "enabled": action == "enable",
                        "default_channel": "telegram",
                        "default_agent": "orchestrator",
                    },
                ),
                (("channel", "telegram"), {"drop_pending_updates": False}),
            ]
        )
    return {"saved": True, "restart_required": True, "action": action}


@router.post("/telegram/test-notification")
def send_test(request: Request):
    bridge = getattr(request.app.state, "channel_bridge", None)
    cfg = request.app.state.config
    if bridge is None or not cfg.channel.enabled:
        raise HTTPException(409, "Enable the owned bot and restart first")
    chat = cfg.channel.telegram.allowed_chat_ids.split(",")[0].strip()
    adapter = bridge._channels.get("telegram")
    if adapter is None:
        raise HTTPException(409, "Owned Telegram adapter is unavailable")
    sent = adapter.send(chat, "Jarvis connection test. Your local dashboard is ready.")
    return {
        "sent": bool(sent),
        "note": (
            "Confirm receipt in Telegram; this does not opt you into recu"
            "rring reminders"
        ),
    }


def initialize_setup(app):
    app.include_router(router)
