"""Shared isolated configuration for the offline suite; never use real providers."""
import base64
import json
import socket

import pytest


@pytest.fixture(autouse=True)
def settings(monkeypatch, tmp_path):
    from ui_client import db
    values = {"APP_ENV": "development", "SESSION_SECRET": "s" * 48,
              "TOKEN_ENCRYPTION_KEY": base64.urlsafe_b64encode(b"t" * 32).decode(),
              "KOE_OWNER_EMAIL": "owner@example.test", "KOE_MODE": "demo",
              "MOCK_SDR": "false", "MOCK_LEAD_FINDER": "false",
              "SECURITY_DB_PATH": str(tmp_path / "nonces.db"),
              "GOOGLE_OAUTH_CLIENT_ID": "test-client", "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
              "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8000/auth/google/callback",
              "NEXT_PUBLIC_FRONTEND_URL": "http://localhost:3000",
              "UI_CLIENT_SERVICE_URL": "http://localhost:8000", "SDR_SERVICE_URL": "http://localhost:8084",
              "LEAD_FINDER_SERVICE_URL": "http://localhost:8081", "LEAD_MANAGER_SERVICE_URL": "http://localhost:8082",
              "GOOGLE_API_KEY": "offline-test-key", "GOOGLE_MAPS_API_KEY": "AIza" + "t" * 35,
              "ELEVENLABS_API_KEY": "offline-test-key",
              "SERVICE_AUTH_KEYS": json.dumps({key: key + "k" * 48 for key in
                  ["ui-client", "sdr", "lead-manager", "lead-finder", "gmail-listener"]})}
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    for name in ["CALLS", "EMAIL", "CALENDAR"]:
        monkeypatch.setenv("ENABLE_LIVE_" + name, "false")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tokens.db")


@pytest.fixture(autouse=True)
def offline_network(monkeypatch):
    original = socket.socket.connect
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in {"localhost", "127.0.0.1", "::1"}:
            pytest.fail("External network access attempted in offline test; mock the provider", pytrace=False)
        return original(sock, address)
    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture(autouse=True)
def reset_app_state(settings, monkeypatch):
    from ui_client import main
    from common.security import Execution, execution
    token = execution.set(Execution("owner@example.test", "demo"))
    monkeypatch.setattr(main, "RAPIDS_SCORING_AVAILABLE", False)
    main.app_state.clear_all()
    main.manager.active_connections.clear()
    try:
        yield
    finally:
        main.app_state.clear_all()
        main.manager.active_connections.clear()
        execution.reset(token)
