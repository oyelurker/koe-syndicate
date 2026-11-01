"""Offline security regressions. Never contact live providers."""
import asyncio
import hashlib
import json
import time
import base64
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials

from common.security import (Execution, ServiceAuth, ServiceMiddleware, SecurityError,
                             execution, require_action, verify_request)
from ui_client import db, oauth, security


@pytest.fixture
def client(monkeypatch):
    import ui_client.main as main
    monkeypatch.setattr(main, "RAPIDS_SCORING_AVAILABLE", False)
    main.app_state["businesses"] = {}
    main.app_state["is_running"] = False
    with TestClient(main.app, base_url="http://localhost:8000", follow_redirects=False) as c:
        yield c
    main.app_state["businesses"] = {}
    main.manager.active_connections.clear()


def login(client, email="owner@example.test", session="test-session"):
    async def seed():
        creds = Credentials(token="fake-token", refresh_token="fake-refresh", token_uri="https://oauth2.googleapis.com/token",
                            client_id="test", client_secret="test", scopes=[])
        uid = await db.upsert_user({"id": email, "email": email}, creds)
        await db.create_session(session, uid)
    asyncio.run(seed())
    client.cookies.set("koe_session", security.signer().dumps(session))
    return {"Origin": "http://localhost:3000", "X-Koe-CSRF": security.csrf_token(session)}


@pytest.mark.parametrize("action", ["calls", "email", "calendar"])
def test_action_requires_mode_flag_and_owner(monkeypatch, action):
    token = execution.set(Execution("owner@example.test", "demo"))
    try:
        monkeypatch.setenv("ENABLE_LIVE_" + action.upper(), "true")
        monkeypatch.setenv("KOE_MODE", "live")
        with pytest.raises(SecurityError):
            require_action(action)
        execution.set(Execution("other@example.test", "live"))
        with pytest.raises(SecurityError):
            require_action(action)
        execution.set(Execution("owner@example.test", "live"))
        require_action(action)
        monkeypatch.setenv("ENABLE_LIVE_" + action.upper(), "false")
        with pytest.raises(SecurityError):
            require_action(action)
        execution.set(None)
        with pytest.raises(SecurityError):
            require_action(action)
    finally:
        execution.reset(token)


def test_mock_flags_cannot_enable_live_action(monkeypatch):
    monkeypatch.setenv("KOE_MODE", "live")
    monkeypatch.setenv("ENABLE_LIVE_CALLS", "true")
    monkeypatch.setenv("MOCK_SDR", "true")
    token = execution.set(Execution("owner@example.test", "live"))
    try:
        with pytest.raises(SecurityError):
            require_action("calls")
    finally:
        execution.reset(token)


@pytest.mark.parametrize("path,method", [("/api/businesses", "get"), ("/start_lead_finding", "post"),
    ("/send_to_sdr", "post"), ("/reset", "post"), ("/trigger_lead_manager", "post"),
    ("/api/human-input", "get"), ("/api/rescore", "post")])
def test_browser_routes_reject_anonymous(client, path, method):
    assert getattr(client, method)(path).status_code == 401


def test_callbacks_reject_anonymous_and_browser_session(client):
    assert client.post("/agent_callback", json={}).status_code == 401
    headers = login(client)
    assert client.post("/agent_callback", json={}, headers=headers).status_code == 401


def test_owner_restriction(client):
    login(client, "other@example.test")
    assert client.get("/api/businesses").status_code == 401
    assert client.get("/auth/status").json() == {"connected": False}


def test_csrf_required_and_owner_can_read(client):
    headers = login(client)
    assert client.get("/api/businesses").status_code == 200
    assert client.post("/reset").status_code == 403
    assert client.post("/reset", headers={**headers, "Origin": "https://attacker.test"}).status_code == 403
    assert client.post("/reset", headers=headers).status_code == 303


def test_demo_outreach_never_dispatches(client, monkeypatch):
    import ui_client.main as main
    dispatch = AsyncMock()
    monkeypatch.setattr(main, "call_sdr_agent", dispatch)
    headers = login(client)
    assert client.post("/send_to_sdr", data={"business_id": "any"}, headers=headers).status_code == 403
    assert client.post("/auth/schedule-meeting", json={"lead_name": "Fake lead"}, headers=headers).status_code == 410
    dispatch.assert_not_awaited()


@pytest.mark.parametrize("path", ["/auth/credentials", "/debug/static", "/docs", "/openapi.json"])
def test_sensitive_routes_removed(client, path):
    assert client.get(path).status_code == 404


def test_disconnect_removes_credentials_and_all_sessions(client):
    headers = login(client)
    assert client.post("/auth/disconnect", headers=headers).status_code == 200
    assert asyncio.run(db.credentials_for_owner("owner@example.test")) is None
    assert client.get("/api/businesses").status_code == 401


def test_oauth_state_browser_binding_and_replay():
    state, cookie, challenge = oauth.start_state("A&B", "x=y")
    with pytest.raises(SecurityError):
        oauth.consume_state(state, "wrong-browser")
    data = oauth.consume_state(state, cookie)
    assert data["city"] == "A&B" and data["niche"] == "x=y"
    import base64
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(data["verifier"].encode()).digest()).rstrip(b"=").decode()
    with pytest.raises(SecurityError):
        oauth.consume_state(state, cookie)


def test_expired_oauth_state(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr("itsdangerous.timed.TimestampSigner.get_timestamp", lambda self: int(time.time()) - 601)
        state, cookie, _ = oauth.start_state("", "")
    with pytest.raises(SecurityError):
        oauth.consume_state(state, cookie)


@pytest.mark.parametrize("state", ["", "forged", "eyJjaXR5IjoiTG9uZG9uIn0="])
def test_invalid_oauth_callback_rejected_before_provider(client, state):
    assert client.get("/auth/google/callback", params={"code": "not-a-real-code", "state": state}).status_code == 400


def test_production_config_rejects_defaults(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "koe-syndicate-secret-dev-key")
    with pytest.raises(SecurityError):
        security.validate_config()
    monkeypatch.setenv("SESSION_SECRET", "s" * 48)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(SecurityError):
        security.validate_config()


def signed_request(path="/agent_callback", body=None, caller="sdr", audience="ui-client"):
    request = httpx.Request("POST", "http://localhost:8000" + path, json=body or {})
    return next(ServiceAuth(caller, audience, Execution("owner@example.test", "demo")).auth_flow(request))


def test_service_signature_body_audience_expiry_and_replay(monkeypatch):
    req = signed_request()
    headers = dict(req.headers)
    with pytest.raises(SecurityError):
        verify_request(headers, "POST", "/agent_callback", b'changed', "ui-client", {"sdr"})
    with pytest.raises(SecurityError):
        verify_request(headers, "POST", "/agent_callback", req.content, "sdr", {"sdr"})
    with pytest.raises(SecurityError):
        verify_request({**headers, "x-koe-time": str(int(time.time()) - 121)}, "POST", "/agent_callback", req.content, "ui-client", {"sdr"})
    assert verify_request(headers, "POST", "/agent_callback", req.content, "ui-client", {"sdr"}).owner == "owner@example.test"
    with pytest.raises(SecurityError):
        verify_request(headers, "POST", "/agent_callback", req.content, "ui-client", {"sdr"})


def test_signed_callback_works_once_and_cannot_spoof_agent(client):
    payload = {"agent_type": "sdr", "business_id": "test-lead", "status": "found", "message": "fixture",
               "data": {"name": "Fixture", "city": "Test"}}
    req = signed_request(body=payload)
    assert client.post("/agent_callback", content=req.content, headers=dict(req.headers)).status_code == 200
    assert client.post("/agent_callback", content=req.content, headers=dict(req.headers)).status_code == 401
    req = signed_request(body={**payload, "agent_type": "calendar"})
    assert client.post("/agent_callback", content=req.content, headers=dict(req.headers)).status_code == 401


def test_service_transport_integration():
    app = FastAPI()
    @app.post("/work")
    async def work(request: Request):
        return {"owner": execution.get().owner, "mode": execution.get().mode, "body": await request.json()}
    wrapped = ServiceMiddleware(app, "sdr", {"ui-client"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wrapped),
            auth=ServiceAuth("ui-client", "sdr", Execution("owner@example.test", "demo"))) as c:
            response = await c.post("http://localhost:8084/work", json={"hello": "world"})
            assert response.status_code == 200
            assert response.json() == {"owner": "owner@example.test", "mode": "demo", "body": {"hello": "world"}}
    asyncio.run(run())


def test_websocket_owner_and_origin(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}):
            pass
    login(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"Origin": "https://attacker.test"}):
            pass
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as socket:
        assert socket.receive_json()["type"] == "initial_state"


def test_disconnect_revokes_existing_websocket(client):
    from starlette.websockets import WebSocketDisconnect
    import ui_client.main as main
    headers = login(client)
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:3000"}) as socket:
        socket.receive_json()
        assert client.post("/auth/disconnect", headers=headers).status_code == 200
        async def publish_as_service():
            token = execution.set(Execution("owner@example.test", "demo"))
            try:
                await main.manager.send_update({"type": "private_update"})
            finally:
                execution.reset(token)
        client.portal.call(publish_as_service)
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_calendar_gateway_demo_does_not_build_provider(client, monkeypatch):
    from ui_client import calendar_routes
    provider = Mock(side_effect=AssertionError("Provider must not be touched"))
    monkeypatch.setattr(calendar_routes, "build", provider)
    req = signed_request("/internal/calendar/meeting", {"lead_name": "Test", "lead_email": "lead@example.test"}, "lead-manager")
    assert client.post(req.url.path, content=req.content, headers=dict(req.headers)).status_code == 403
    provider.assert_not_called()


def test_signer_refuses_untrusted_destination():
    request = httpx.Request("POST", "http://169.254.169.254/work", json={})
    with pytest.raises(SecurityError):
        next(ServiceAuth("ui-client", "sdr", Execution("owner@example.test", "demo")).auth_flow(request))


def test_health_does_not_disclose_pipeline_state(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert not {"current_city", "business_count", "is_running", "active_connections"} & response.json().keys()


def test_credentials_encrypted_at_rest_and_refresh_preserved(client):
    import sqlite3
    login(client)
    with sqlite3.connect(db.DB_PATH) as connection:
        stored = connection.execute("SELECT access_token, refresh_token, client_secret FROM users").fetchone()
    assert all(value.startswith("enc:v1:") for value in stored)
    assert "fake-token" not in db.DB_PATH.read_bytes().decode(errors="ignore")

    async def refresh():
        creds = Credentials(token="new-token", client_id="test", client_secret="test")
        await db.upsert_user({"id": "owner@example.test", "email": "owner@example.test"}, creds)
        restored = await db.credentials_for_owner("owner@example.test")
        assert restored.token == "new-token"
        assert restored.refresh_token == "fake-refresh"
    asyncio.run(refresh())


def test_plaintext_migration_is_repeatable_and_wrong_key_fails(client, monkeypatch):
    import sqlite3
    from cryptography.fernet import InvalidToken
    login(client)
    with sqlite3.connect(db.DB_PATH) as connection:
        connection.execute("UPDATE users SET access_token='legacy-token', refresh_token='legacy-refresh', client_secret='legacy-secret'")
    asyncio.run(db.init_db())
    asyncio.run(db.init_db())
    assert asyncio.run(db.credentials_for_owner("owner@example.test")).token == "legacy-token"
    with sqlite3.connect(db.DB_PATH) as connection:
        assert connection.execute("SELECT access_token FROM users").fetchone()[0].startswith("enc:v1:")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"x" * 32).decode())
    with pytest.raises(InvalidToken):
        asyncio.run(db.credentials_for_owner("owner@example.test"))


def test_expired_session_cannot_read_pipeline(client):
    import sqlite3
    login(client)
    with sqlite3.connect(db.DB_PATH) as connection:
        connection.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    assert client.get("/api/businesses").status_code == 401


def test_legacy_dashboard_redirects_to_csrf_aware_frontend(client):
    login(client)
    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:3000/dashboard"


def test_demo_readiness_never_probes_providers(client, monkeypatch):
    login(client)
    provider = Mock(side_effect=AssertionError("No provider probe in demo"))
    monkeypatch.setattr(httpx, "AsyncClient", provider)
    response = client.get("/api/system-status")
    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["mode"] == "demo"
    provider.assert_not_called()


def test_bigquery_hostile_filters_remain_parameters(monkeypatch):
    from lead_finder.lead_finder.tools import bigquery_utils as module
    provider = Mock()
    provider.client.query.return_value = []
    monkeypatch.setattr(module, "BigQueryClient", Mock(return_value=provider))
    monkeypatch.setattr(module, "ensure_no_website_table_exists", Mock())
    hostile = "x' OR 1=1 --"
    result = asyncio.run(module.bigquery_query_no_website_leads(city=hostile, category="O'Reilly", limit=7))
    assert result["status"] == "success"
    args, kwargs = provider.client.query.call_args
    assert hostile not in args[0] and "O'Reilly" not in args[0]
    values = {p.name: p.value for p in kwargs["job_config"].query_parameters}
    assert values == {"city": hostile, "category": "O'Reilly", "limit": 7}


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 1001}, {"limit": True}, {"min_rating": -1}, {"min_rating": 6}])
def test_bigquery_invalid_bounds_rejected_before_provider(monkeypatch, kwargs):
    from lead_finder.lead_finder.tools import bigquery_utils as module
    provider = Mock(side_effect=AssertionError("Invalid input must not reach provider"))
    monkeypatch.setattr(module, "BigQueryClient", provider)
    with pytest.raises(ValueError):
        asyncio.run(module.bigquery_query_no_website_leads(**kwargs))
    provider.assert_not_called()


@pytest.mark.parametrize("email,verified,expected", [
    ("owner@example.test", True, 307),
    ("other@example.test", True, 403),
    ("owner@example.test", False, 403),
])
def test_oauth_exchange_requires_verified_owner(client, monkeypatch, email, verified, expected):
    from urllib.parse import parse_qs, urlsplit
    response = client.get("/auth/google", params={"city": "A&B", "niche": "test"})
    state = parse_qs(urlsplit(response.headers["location"]).query)["state"][0]
    fake = AsyncMock()
    fake.post.return_value = httpx.Response(200, json={"access_token": "fake-access", "refresh_token": "fake-refresh"},
                                            request=httpx.Request("POST", "https://oauth2.googleapis.com/token"))
    fake.get.return_value = httpx.Response(200, json={"id": "123", "email": email, "verified_email": verified},
                                           request=httpx.Request("GET", "https://www.googleapis.com/oauth2/v2/userinfo"))
    context = AsyncMock()
    context.__aenter__.return_value = fake
    monkeypatch.setattr(httpx, "AsyncClient", Mock(return_value=context))
    response = client.get("/auth/google/callback", params={"code": "fake-code", "state": state})
    assert response.status_code == expected
    assert fake.post.call_args.kwargs["data"]["code_verifier"]
    status = client.get("/auth/status").json()
    assert status["connected"] is (expected == 307)
    if expected == 307:
        assert parse_qs(urlsplit(response.headers["location"]).query)["city"] == ["A&B"]
        assert status["csrf_token"]
    # Even a rejected identity cannot reuse an already exchanged state.
    assert client.get("/auth/google/callback", params={"code": "fake-code", "state": state}).status_code == 400


def test_all_bigquery_paths_parameterize_untrusted_values():
    from lead_finder.lead_finder.tools import bigquery_utils as module
    client = object.__new__(module.BigQueryClient)
    client.client = Mock()
    client.client.query.return_value = []
    hostile = "x'); DROP TABLE leads; --"
    result = asyncio.run(client.query_businesses(city=hostile, lead_status=hostile, min_rating=0, limit=10))
    assert result["status"] == "success"
    args, kwargs = client.client.query.call_args
    assert hostile not in args[0]
    values = {p.name: p.value for p in kwargs["job_config"].query_parameters}
    assert values == {"limit": 10, "city": hostile, "lead_status": hostile, "min_rating": 0}
    asyncio.run(client._get_existing_place_ids([hostile]))
    args, kwargs = client.client.query.call_args
    assert hostile not in args[0] and "UNNEST(@place_ids)" in args[0]
    assert kwargs["job_config"].query_parameters[0].values == [hostile]


@pytest.mark.parametrize("meeting", [{}, {"success": False, "meeting_id": "bad"}, {"success": True}])
def test_unconfirmed_meeting_cannot_notify_success(monkeypatch, meeting):
    from lead_manager.lead_manager import callbacks
    from lead_manager.lead_manager.tools import ui_notification
    provider = Mock(side_effect=AssertionError("No notification for an unconfirmed booking"))
    monkeypatch.setattr(httpx, "Client", provider)
    monkeypatch.setattr(httpx, "AsyncClient", provider)
    callbacks.send_calendar_notification_to_ui(meeting)
    result = asyncio.run(ui_notification.notify_meeting_arranged(meeting, {}, {}))
    assert result["success"] is False
    provider.assert_not_called()


def test_demo_direct_call_and_email_tools_never_initialize_provider(monkeypatch):
    import importlib
    phone = importlib.import_module("sdr.sdr.tools.phone_call")
    email = importlib.import_module("sdr.sdr.sub_agents.outreach_email_agent.tools.gmail_service_account_tool")
    provider = Mock(side_effect=AssertionError("No external provider in demo"))
    monkeypatch.setattr(phone, "_init_elevenlabs_client", provider)
    monkeypatch.setattr(email, "build", provider)
    token = execution.set(Execution("owner@example.test", "demo"))
    try:
        with pytest.raises(SecurityError):
            asyncio.run(phone._make_call("+15555550100", "test", "test"))
        with pytest.raises(SecurityError):
            asyncio.run(phone.phone_call({"phone": "+15555550100"}, "test"))
        with pytest.raises(SecurityError):
            email.send_email("test@example.test", "test", "test")
    finally:
        execution.reset(token)
    provider.assert_not_called()


@pytest.mark.parametrize("service,entrypoint,port", [
    ("lead-finder", "lead_finder.__main__", 8081),
    ("lead-manager", "lead_manager.adk_main", 8082),
    ("sdr", "sdr.__main__", 8084),
])
def test_real_agent_discovery_requires_signed_identity(monkeypatch, service, entrypoint, port):
    import importlib
    import uvicorn
    monkeypatch.setenv(service.upper().replace("-", "_") + "_SERVICE_URL", f"http://127.0.0.1:{port}")
    capture = Mock()
    monkeypatch.setattr(uvicorn, "run", capture)
    module = importlib.import_module(entrypoint)
    if service == "sdr":
        app = module.app
        assert module.ADK_AVAILABLE
    else:
        module.main.callback(host="127.0.0.1", port=port)
        app = capture.call_args.args[0]
    url = f"http://127.0.0.1:{port}/.well-known/agent.json"
    with TestClient(app) as caller:
        assert caller.get(url).status_code == 401
        req = httpx.Request("GET", url)
        signed = next(ServiceAuth("ui-client", service, Execution("owner@example.test", "demo")).auth_flow(req))
        response = caller.get(url, headers=dict(signed.headers))
        assert response.status_code == 200
        assert response.json()["name"]
