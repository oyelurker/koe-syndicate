"""Migration, restart, ownership, backup and integration-revocation contracts."""
import asyncio
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials

from common.security import Execution, ServiceAuth
from ui_client import db, security
from ui_client.store import Store, tenant_id

OWNER = "owner@example.test"


def snapshot(campaign="campaign", name="Fixture", running=False):
    return {"session_id": campaign, "current_city": "Test City", "is_running": running,
            "businesses": {"same-id": {"id": "same-id", "name": name, "city": "Test City"}},
            "agent_updates": [], "human_input_requests": {}, "lead_scores": {}}


def prepare():
    async def seed():
        await db.init_db()
        return await db.upsert_user({"id": "owner-id", "email": OWNER}, Credentials(
            token="fixture-access", refresh_token="fixture-refresh", token_uri="https://oauth2.googleapis.com/token",
            client_id="fixture-client", client_secret="fixture-secret", scopes=[]))
    return asyncio.run(seed())


def test_store_requires_explicit_owner(tmp_path):
    store = Store(tmp_path / "store.db")
    store.initialize()
    for owner in (None, "", "not-an-owner"):
        with pytest.raises(ValueError, match="explicit verified owner"):
            store.save(owner, snapshot())


def test_tenant_records_and_same_ids_cannot_cross_owners(tmp_path):
    store = Store(tmp_path / "store.db")
    store.initialize()
    other = "other@example.test"
    store.save(OWNER, snapshot(name="Owner lead"), {"type": "process_started"})
    store.save(other, snapshot(name="Other lead"), {"type": "process_started"})
    reopened = Store(store.path)
    assert reopened.load(OWNER)["businesses"]["same-id"]["name"] == "Owner lead"
    assert reopened.load(other)["businesses"]["same-id"]["name"] == "Other lead"
    assert reopened.leads(OWNER)[0]["name"] == "Owner lead"
    assert reopened.leads(other)[0]["name"] == "Other lead"
    assert reopened.events(OWNER)[0]["id"] != reopened.events(other)[0]["id"]
    assert reopened.job(OWNER, "discovery:campaign")["tenant_id"] == tenant_id(OWNER)
    assert reopened.job("missing@example.test", "discovery:campaign") is None


def test_foreign_campaign_job_is_rejected_transactionally(tmp_path):
    store = Store(tmp_path / "store.db")
    store.initialize()
    store.save(OWNER, snapshot())
    with pytest.raises(sqlite3.IntegrityError):
        store.create_job("other@example.test", "work", {}, campaign_id="campaign")
    with store.connection() as connection:
        assert connection.execute("SELECT count(*) FROM tenants").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0


def test_invalid_snapshot_does_not_replace_durable_state(tmp_path):
    store = Store(tmp_path / "store.db")
    store.initialize()
    store.save(OWNER, snapshot())
    bad = snapshot(name="Should not persist")
    bad["lead_scores"] = {"bad": float("nan")}
    with pytest.raises(ValueError):
        store.save(OWNER, bad)
    assert store.load(OWNER) == snapshot()


def test_legacy_oauth_database_migrates_without_losing_encrypted_tokens():
    prepare()
    with sqlite3.connect(db.DB_PATH) as connection:
        before = connection.execute("SELECT access_token,refresh_token,client_secret FROM users").fetchone()
        for table in ("events", "jobs", "leads", "campaigns", "pipeline_snapshots", "integration_connections", "tenants"):
            connection.execute(f"DROP TABLE {table}")
        connection.execute("PRAGMA user_version=0")
    asyncio.run(db.init_db())
    asyncio.run(db.init_db())
    with sqlite3.connect(db.DB_PATH) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT access_token,refresh_token,client_secret FROM users").fetchone() == before
        assert connection.execute("SELECT connected FROM integration_connections WHERE tenant_id=?", (tenant_id(OWNER),)).fetchone()[0] == 1
    assert asyncio.run(db.credentials_for_owner(OWNER)).refresh_token == "fixture-refresh"


def test_future_schema_is_rejected_before_auth_data_is_touched(monkeypatch, tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=999")
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('preserve')")
    monkeypatch.setattr(db, "DB_PATH", path)
    with pytest.raises(ValueError, match="newer"):
        asyncio.run(db.init_db())
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM sentinel").fetchone()[0] == "preserve"
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='users'").fetchone() is None


def test_failed_schema_migration_rolls_back_without_losing_profile(monkeypatch):
    prepare()
    with sqlite3.connect(db.DB_PATH) as connection:
        for table in ("events", "jobs", "leads", "campaigns", "pipeline_snapshots", "integration_connections", "tenants"):
            connection.execute(f"DROP TABLE {table}")
        connection.execute("PRAGMA user_version=0")
        connection.execute("UPDATE users SET email='Owner@Example.Test'")
    monkeypatch.setattr(Store, "_tenant", Mock(side_effect=ValueError("Simulated migration failure")))
    with pytest.raises(ValueError, match="Simulated migration failure"):
        asyncio.run(db.init_db())
    with sqlite3.connect(db.DB_PATH) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='tenants'").fetchone() is None
        assert connection.execute("SELECT email FROM users").fetchone()[0] == "Owner@Example.Test"
    assert asyncio.run(db.credentials_for_owner(OWNER)).token == "fixture-access"


def test_disconnect_cancels_connection_jobs_and_reconnect_does_not_reauthorize_them():
    uid = prepare()
    store = Store(db.DB_PATH)
    old_job = store.create_job(OWNER, "calendar", {}, provider="google")
    assert store.job_connection_valid(OWNER, old_job)
    asyncio.run(db.disconnect_user(uid))
    assert not store.job_connection_valid(OWNER, old_job)
    assert store.job(OWNER, old_job)["state"] == "cancelled"
    assert asyncio.run(db.credentials_for_owner(OWNER)) is None
    prepare()
    assert not store.job_connection_valid(OWNER, old_job)
    fresh = store.create_job(OWNER, "calendar", {}, provider="google")
    assert store.job_connection_valid(OWNER, fresh)


def test_backup_restore_includes_records_and_encrypted_credentials(monkeypatch, tmp_path):
    prepare()
    store = Store(db.DB_PATH)
    store.save(OWNER, snapshot(), {"type": "business_updated"})
    destination = tmp_path / "backup.db"
    store.backup(destination)
    with pytest.raises(ValueError, match="overwrite"):
        store.backup(destination)
    restored = Store(destination)
    restored.initialize()
    assert restored.load(OWNER) == snapshot()
    assert restored.leads(OWNER) == store.leads(OWNER)
    assert restored.events(OWNER) == store.events(OWNER)
    monkeypatch.setattr(db, "DB_PATH", destination)
    assert asyncio.run(db.credentials_for_owner(OWNER)).token == "fixture-access"
    assert b"fixture-access" not in destination.read_bytes()


def test_missing_source_cannot_create_a_misleading_empty_backup(tmp_path):
    source, target = tmp_path / "missing.db", tmp_path / "backup.db"
    with pytest.raises(ValueError, match="Source database"):
        Store(source).backup(target)
    assert not source.exists() and not target.exists()


def test_backup_cli_copies_to_a_new_path_and_refuses_overwrite(tmp_path):
    prepare()
    Store(db.DB_PATH).save(OWNER, snapshot())
    destination = tmp_path / "cli-copy.db"
    script = Path(__file__).resolve().parents[2] / "scripts/backup_local_data.py"
    command = [sys.executable, str(script), "--source", str(db.DB_PATH), "--output", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert Store(destination).load(OWNER) == snapshot()
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode != 0
    assert "refusing to overwrite" in again.stderr


def test_real_app_restores_callback_state_after_restart():
    import ui_client.main as main
    with TestClient(main.app, base_url="http://localhost:8000") as client:
        prepare()
        payload = {"agent_type": "sdr", "business_id": "saved-lead", "status": "engaged", "message": "Fixture update",
                   "data": {"name": "Persisted Business", "city": "Test City"}}
        main.app_state["session_id"] = "fixture-campaign"
        request = httpx.Request("POST", "http://localhost:8000/agent_callback", json=payload)
        signed = next(ServiceAuth("sdr", "ui-client", Execution(OWNER, "demo", "fixture-campaign")).auth_flow(request))
        assert client.post(request.url.path, content=request.content, headers=dict(signed.headers)).status_code == 200
        expected = main.app_state["businesses"]["saved-lead"].model_dump(mode="json")
    main.app_state["businesses"].clear()
    with TestClient(main.app, base_url="http://localhost:8000") as client:
        asyncio.run(db.create_session("restored-session", "owner-id"))
        client.cookies.set("koe_session", security.signer().dumps("restored-session"))
        response = client.get("/api/businesses")
        assert response.status_code == 200
        assert response.json()["businesses"][0]["name"] == "Persisted Business"
        assert main.app_state["businesses"]["saved-lead"].model_dump(mode="json") == expected
        assert main.app_state["agent_updates"][0].message == "Fixture update"


def test_restart_marks_interrupted_work_without_replaying_it(monkeypatch):
    import ui_client.main as main
    prepare()
    store = Store(db.DB_PATH)
    store.save(OWNER, snapshot(running=True), {"type": "process_started"})
    process = AsyncMock()
    monkeypatch.setattr(main, "run_lead_finding_process", process)
    with TestClient(main.app):
        assert main.app_state["is_running"] is False
        assert store.job(OWNER, "discovery:campaign")["state"] == "interrupted"
        assert main.app_state["businesses"]["same-id"].name == "Fixture"
    process.assert_not_called()


def test_changing_configured_owner_does_not_reuse_previous_owner_cache(monkeypatch):
    import ui_client.main as main
    prepare()
    Store(db.DB_PATH).save(OWNER, snapshot(name="Private owner lead"))
    with TestClient(main.app):
        assert main.app_state["businesses"]["same-id"].name == "Private owner lead"
    monkeypatch.setenv("KOE_OWNER_EMAIL", "other@example.test")
    with TestClient(main.app):
        assert main.app_state["businesses"] == {}
        assert main.app_state["session_id"] is None
    assert Store(db.DB_PATH).leads(OWNER)[0]["name"] == "Private owner lead"
