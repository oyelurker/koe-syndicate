"""Fail-closed execution policy and signed internal HTTP requests.

P0 supports one configured owner only. This is deliberately not tenant isolation.
Use a shared SECURITY_DB_PATH across workers; separate replicas require shared
replay storage before enabling them (see docs/P0-SECURITY.md).
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from starlette.responses import JSONResponse


class SecurityError(ValueError):
    pass


@dataclass(frozen=True)
class Execution:
    owner: str
    mode: str


execution: ContextVar[Execution | None] = ContextVar("koe_execution", default=None)


def owner_email():
    return os.getenv("KOE_OWNER_EMAIL", "").strip().lower()


def require_owner(email):
    if not owner_email() or not email or email.lower() != owner_email():
        raise SecurityError("This instance is restricted to its configured owner")


def mode():
    value = os.getenv("KOE_MODE", "demo").lower()
    if value not in {"live", "demo"}:
        raise SecurityError("KOE_MODE must be demo or live")
    if any(os.getenv(k, "").lower() == "true" for k in ("MOCK_SDR", "MOCK_LEAD_FINDER")):
        return "demo"
    return value


def require_action(action):
    context = execution.get()
    if context is None:
        raise SecurityError("Missing verified execution owner")
    require_owner(context.owner)
    if mode() != "live" or context.mode != "live":
        raise SecurityError("External actions are disabled in demo mode")
    if action not in {"calls", "email", "calendar"}:
        raise SecurityError("Unknown action")
    if os.getenv(f"ENABLE_LIVE_{action.upper()}", "false").lower() != "true":
        raise SecurityError(f"Live {action} is disabled")


def secret(name):
    value = os.getenv(name, "")
    if len(value) < 32 or value.startswith(("your_", "replace", "change")) or value == "koe-syndicate-secret-dev-key":
        raise SecurityError(f"{name} must be a randomly generated secret of at least 32 characters")
    return value


def consume_once(namespace, nonce, expires):
    """Atomically consume a nonce, including across worker restarts."""
    path = Path(os.getenv("SECURITY_DB_PATH", ".runtime/security.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=5) as db:
        db.execute("CREATE TABLE IF NOT EXISTS nonces (namespace TEXT, nonce TEXT, expires REAL, PRIMARY KEY(namespace, nonce))")
        db.execute("DELETE FROM nonces WHERE expires < ?", (time.time(),))
        try:
            db.execute("INSERT INTO nonces VALUES (?, ?, ?)", (namespace, nonce, expires))
        except sqlite3.IntegrityError as exc:
            raise SecurityError("Request already consumed") from exc


def service_key(caller):
    # Each signer has its own key. Receivers configure only trusted callers.
    keys = json.loads(os.getenv("SERVICE_AUTH_KEYS", "{}"))
    value = keys.get(caller, "")
    if not isinstance(value, str) or len(value) < 32:
        raise SecurityError("Service identity is not configured")
    return value


def service_url(audience):
    from common import config
    defaults = {"ui-client": config.DEFAULT_UI_CLIENT_URL, "sdr": config.DEFAULT_SDR_URL,
                "lead-finder": config.DEFAULT_LEAD_FINDER_URL, "lead-manager": config.DEFAULT_LEAD_MANAGER_URL}
    key = audience.upper().replace("-", "_") + "_SERVICE_URL"
    return os.getenv(key, defaults[audience]).rstrip("/")


def canonical(caller, audience, owner, run_mode, timestamp, nonce, method, target, body):
    return "\n".join((caller, audience, owner, run_mode, timestamp, nonce, method.upper(), target,
                      hashlib.sha256(body).hexdigest())).encode()


class ServiceAuth(httpx.Auth):
    requires_request_body = True

    def __init__(self, caller, audience, context=None):
        self.caller, self.audience, self.context = caller, audience, context

    def auth_flow(self, request):
        context = self.context or execution.get()
        if context is None:
            raise SecurityError("Missing execution context for internal request")
        require_owner(context.owner)
        expected = urlsplit(service_url(self.audience))
        actual = urlsplit(str(request.url))
        if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
            raise SecurityError("Internal request destination mismatch")
        if actual.scheme != "https" and actual.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise SecurityError("Internal requests require HTTPS outside loopback")
        timestamp, nonce = str(int(time.time())), secrets.token_hex(24)
        run_mode = "demo" if mode() == "demo" else context.mode
        target = request.url.raw_path.decode("ascii")
        signature = hmac.new(service_key(self.caller).encode(), canonical(
            self.caller, self.audience, context.owner, run_mode, timestamp, nonce,
            request.method, target, request.content), hashlib.sha256).hexdigest()
        request.headers.update({"X-Koe-Caller": self.caller, "X-Koe-Audience": self.audience,
            "X-Koe-Owner": context.owner, "X-Koe-Mode": run_mode, "X-Koe-Time": timestamp,
            "X-Koe-Nonce": nonce, "X-Koe-Signature": signature})
        yield request


def verify_request(headers, method, target, body, audience, allowed_callers):
    caller = headers.get("x-koe-caller", "")
    owner = headers.get("x-koe-owner", "")
    run_mode = headers.get("x-koe-mode", "")
    timestamp = headers.get("x-koe-time", "")
    nonce = headers.get("x-koe-nonce", "")
    if caller not in allowed_callers or headers.get("x-koe-audience") != audience:
        raise SecurityError("Invalid service identity or audience")
    require_owner(owner)
    if run_mode not in {"live", "demo"} or len(nonce) != 48:
        raise SecurityError("Invalid execution context")
    try:
        issued = int(timestamp)
    except ValueError as exc:
        raise SecurityError("Invalid timestamp") from exc
    if abs(time.time() - issued) > 60:
        raise SecurityError("Expired request")
    expected = hmac.new(service_key(caller).encode(), canonical(caller, audience, owner,
        run_mode, timestamp, nonce, method, target, body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, headers.get("x-koe-signature", "")):
        raise SecurityError("Invalid signature")
    consume_once(audience + ":" + caller, nonce, issued + 120)
    return Execution(owner, "demo" if mode() == "demo" else run_mode)


class ServiceMiddleware:
    """Protect all internal routes except non-sensitive liveness."""
    def __init__(self, app, audience, callers):
        self.app, self.audience, self.callers = app, audience, callers

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        if scope["path"] == "/health" and scope["method"] == "GET":
            return await JSONResponse({"status": "alive"})(scope, receive, send)
        if scope["path"].startswith(("/test", "/debug", "/authenticate")):
            return await JSONResponse({"error": "Not found"}, 404)(scope, receive, send)
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if len(body) > 1_048_576:
                return await JSONResponse({"error": "Request too large"}, 413)(scope, receive, send)
            if not message.get("more_body"):
                break
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        target = scope.get("raw_path", scope["path"].encode()).decode("ascii")
        if scope.get("query_string"):
            target += "?" + scope["query_string"].decode("ascii")
        try:
            context = verify_request(headers, scope["method"], target, body, self.audience, self.callers)
            if self.audience == "ui-client" and scope["path"] == "/agent_callback":
                expected_agents = {"lead-finder": {"lead_finder"}, "sdr": {"sdr"},
                                   "lead-manager": {"lead_manager", "calendar"}}
                if json.loads(body).get("agent_type") not in expected_agents.get(headers["x-koe-caller"], set()):
                    raise SecurityError("Callback agent does not match signer")
        except (SecurityError, ValueError, sqlite3.Error):
            return await JSONResponse({"error": "Service authentication failed"}, 401)(scope, receive, send)
        token = execution.set(context)
        scope.setdefault("state", {})["service_caller"] = headers["x-koe-caller"]
        consumed = False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        try:
            await self.app(scope, replay, send)
        finally:
            execution.reset(token)
