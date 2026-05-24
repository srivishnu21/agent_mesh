"""Lightweight HMAC-signed token auth.

Single static user defined via env (AUTH_USERNAME, AUTH_PASSWORD, AUTH_SECRET).
Empty AUTH_USERNAME disables auth entirely — local dev works without configuring anything.

Token format: ``base64url(payload).base64url(hmac_sha256(secret, payload))``
where payload is JSON ``{"sub": "<user>", "exp": <unix>}``. Stateless; no DB.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import Header, HTTPException, Query, status

from app.config import settings

TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).digest()
    return _b64encode(digest)


def auth_enabled() -> bool:
    return bool(settings.AUTH_USERNAME and settings.AUTH_PASSWORD and settings.AUTH_SECRET)


def verify_credentials(username: str, password: str) -> bool:
    if not auth_enabled():
        return False
    return hmac.compare_digest(username, settings.AUTH_USERNAME) and hmac.compare_digest(
        password, settings.AUTH_PASSWORD
    )


def create_token(username: str) -> str:
    payload = {"sub": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_b64, settings.AUTH_SECRET)
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[str]:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = _sign(payload_b64, settings.AUTH_SECRET)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


async def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """HTTP dependency. 401 if auth enabled and bearer missing/invalid."""
    if not auth_enabled():
        return "anonymous"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    user = verify_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_ws(token: str | None = Query(default=None)) -> str:
    """WebSocket dependency. WS spec sends close code 4401 on auth failure."""
    if not auth_enabled():
        return "anonymous"
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token query parameter")
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user
