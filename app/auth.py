"""Signed HttpOnly cookies for anonymous sessions and the store admin."""

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request, Response

from . import config

ANON_COOKIE = "bf_session"
ADMIN_COOKIE = "bf_admin"


def _sign(value: str) -> str:
    return hmac.new(
        config.SESSION_SECRET.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _new_token(kind: str, ttl_seconds: int) -> str:
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{kind}:{expires_at}:{secrets.token_urlsafe(32)}"
    return f"{payload}.{_sign(payload)}"


def _verify(token: str | None, kind: str) -> bool:
    if not token:
        return False
    try:
        payload, signature = token.rsplit(".", 1)
        token_kind, expires_at, _nonce = payload.split(":", 2)
        expected = _sign(payload)
    except (ValueError, TypeError):
        return False
    if not hmac.compare_digest(signature, expected):
        return False
    return token_kind == kind and int(expires_at) > int(time.time())


def _set_cookie(response: Response, name: str, token: str, max_age: int) -> None:
    response.set_cookie(
        key=name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def create_anonymous_session(response: Response) -> str:
    token = _new_token("anonymous", config.SESSION_TTL_SECONDS)
    _set_cookie(response, ANON_COOKIE, token, config.SESSION_TTL_SECONDS)
    return token


def create_admin_session(response: Response) -> None:
    token = _new_token("admin", config.SESSION_TTL_SECONDS)
    _set_cookie(response, ADMIN_COOKIE, token, config.SESSION_TTL_SECONDS)


def clear_sessions(response: Response) -> None:
    response.delete_cookie(ANON_COOKIE, path="/")
    response.delete_cookie(ADMIN_COOKIE, path="/")


def anonymous_session(request: Request) -> str | None:
    token = request.cookies.get(ANON_COOKIE)
    return token if _verify(token, "anonymous") else None


def is_admin(request: Request) -> bool:
    return _verify(request.cookies.get(ADMIN_COOKIE), "admin")


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(401, "Admin login required")


def check_admin_password(password: str) -> bool:
    return hmac.compare_digest(password, config.ADMIN_TOKEN)


def request_identity(request: Request) -> str:
    """Use a signed session when available, otherwise the direct client address."""
    session = anonymous_session(request) or request.cookies.get(ADMIN_COOKIE)
    if session:
        return session
    return request.client.host if request.client else "unknown"
