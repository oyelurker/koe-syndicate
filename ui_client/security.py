"""Session authentication, CSRF protection and restricted internal routes."""
import hashlib
import hmac
import os
from urllib.parse import urlsplit

from itsdangerous import URLSafeSerializer
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from common.security import (Execution, SecurityError, ServiceMiddleware, execution,
                             mode, require_owner, secret)
from . import db


def signer():
    return URLSafeSerializer(secret("SESSION_SECRET"), salt="koe-session-v1")


def csrf_token(session_id):
    return hmac.new(secret("SESSION_SECRET").encode(), ("csrf:" + session_id).encode(), hashlib.sha256).hexdigest()


def secure_cookies():
    return os.getenv("APP_ENV", "production") != "development"


def allowed_origins():
    return {os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000").rstrip("/"),
            os.getenv("UI_CLIENT_SERVICE_URL", "http://localhost:8000").rstrip("/")}


def validate_config():
    secret("SESSION_SECRET")
    require_owner(os.getenv("KOE_OWNER_EMAIL", ""))
    mode()
    if secure_cookies():
        redirect = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")
        if not redirect.startswith("https://") or any(not url.startswith("https://") for url in allowed_origins()):
            raise SecurityError("Production OAuth and browser origins require HTTPS")
    else:
        urls = allowed_origins() | {os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")}
        if any(urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"} for url in urls):
            raise SecurityError("Development HTTP is limited to loopback origins")


async def session_user(scope):
    cookie = HTTPConnection(scope).cookies.get("koe_session")
    if not cookie:
        return None, None
    try:
        session_id = signer().loads(cookie)
        user = await db.get_user_by_session(session_id)
        if user:
            require_owner(user["email"])
            return session_id, user
    except (ValueError, SecurityError):
        pass
    except Exception:
        # Invalid signatures or unavailable session storage must fail closed.
        pass
    return None, None


class BrowserSecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        path = scope["path"]
        internal = {
            "/agent_callback": {"lead-finder", "sdr", "lead-manager"},
            "/api/human-input": {"sdr"},
            "/internal/calendar/availability": {"lead-manager"},
            "/internal/calendar/meeting": {"lead-manager"},
        }
        if path in internal and scope.get("method") == "POST":
            return await ServiceMiddleware(self.app, "ui-client", internal[path])(scope, receive, send)
        if path.startswith(("/debug", "/test", "/docs", "/redoc", "/openapi", "/auth/credentials")):
            return await JSONResponse({"error": "Not found"}, 404)(scope, receive, send)
        public = {"/health", "/auth/google", "/auth/google/callback", "/auth/status"}
        if scope["type"] == "http" and scope["method"] == "GET" and (path in public or path.startswith("/static/")):
            return await self.app(scope, receive, send)
        session_id, user = await session_user(scope)
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        if scope["type"] == "websocket":
            if not user or headers.get("origin") not in allowed_origins():
                return await send({"type": "websocket.close", "code": 1008})
        elif not user:
            return await JSONResponse({"error": "Authentication required"}, 401)(scope, receive, send)
        elif scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            if headers.get("origin") not in allowed_origins() or not hmac.compare_digest(
                    headers.get("x-koe-csrf", ""), csrf_token(session_id)):
                return await JSONResponse({"error": "CSRF validation failed"}, 403)(scope, receive, send)
        scope.setdefault("state", {}).update(user=user, session_id=session_id)
        token = execution.set(Execution(user["email"].lower(), mode()))
        async def authorized_send(message):
            if scope["type"] == "websocket" and message["type"] == "websocket.send":
                _, current = await session_user(scope)
                if not current:
                    await send({"type": "websocket.close", "code": 1008})
                    raise WebSocketDisconnect(code=1008)
            await send(message)
        try:
            await self.app(scope, receive, authorized_send)
        finally:
            execution.reset(token)
