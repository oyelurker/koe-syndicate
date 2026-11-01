"""Versioned, tenant-owned local records. Execution/retry scheduling is separate."""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

SCHEMA_VERSION = 1


def tenant_id(owner):
    if not isinstance(owner, str) or "@" not in owner or not owner.strip():
        raise ValueError("An explicit verified owner is required")
    return hashlib.sha256(owner.strip().lower().encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("Database schema is newer than this application; migration refused")
            if version == SCHEMA_VERSION:
                return
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY, owner_email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS campaigns (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id), id TEXT NOT NULL,
                    city TEXT, state TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS leads (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id), id TEXT NOT NULL,
                    campaign_id TEXT, data TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,id),
                    FOREIGN KEY(tenant_id,campaign_id) REFERENCES campaigns(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id), id TEXT NOT NULL,
                    campaign_id TEXT, kind TEXT NOT NULL, state TEXT NOT NULL,
                    payload TEXT NOT NULL, provider TEXT, connection_generation INTEGER,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,id),
                    FOREIGN KEY(tenant_id,campaign_id) REFERENCES campaigns(tenant_id,id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL REFERENCES tenants(id), campaign_id TEXT,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(tenant_id,campaign_id) REFERENCES campaigns(tenant_id,id)
                );
                CREATE INDEX IF NOT EXISTS tenant_events ON events(tenant_id,id);
                CREATE TABLE IF NOT EXISTS integration_connections (
                    tenant_id TEXT NOT NULL REFERENCES tenants(id), provider TEXT NOT NULL,
                    user_id TEXT, connected INTEGER NOT NULL CHECK(connected IN (0,1)),
                    generation INTEGER NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,provider)
                );
                CREATE TABLE IF NOT EXISTS pipeline_snapshots (
                    tenant_id TEXT PRIMARY KEY REFERENCES tenants(id),
                    data TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)
            # Existing users retain their encrypted credentials and gain a tenant.
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
                # Case-colliding legacy profiles require review; never merge them silently.
                connection.execute("UPDATE users SET email=lower(trim(email))")
                for user in connection.execute("SELECT id,email FROM users"):
                    identity = self._tenant(connection, user["email"])
                    connection.execute("INSERT OR IGNORE INTO integration_connections VALUES (?, 'google', ?, 1, 1, ?)",
                                       (identity, user["id"], now()))
            connection.execute("PRAGMA user_version=1")

    def check_version(self):
        if self.path.exists():
            with self.connection() as connection:
                if connection.execute("PRAGMA user_version").fetchone()[0] > SCHEMA_VERSION:
                    raise ValueError("Database schema is newer than this application; migration refused")

    def _tenant(self, connection, owner):
        identity = tenant_id(owner)
        connection.execute("INSERT OR IGNORE INTO tenants VALUES (?,?,?)", (identity, owner.strip().lower(), now()))
        return identity

    def load(self, owner):
        identity = tenant_id(owner)
        with self.connection() as connection:
            row = connection.execute("SELECT data FROM pipeline_snapshots WHERE tenant_id=?", (identity,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, owner, snapshot, event=None):
        # Serialize before beginning a transaction; invalid payloads change nothing.
        encoded = json.dumps(snapshot, allow_nan=False)
        event_json = json.dumps(event, allow_nan=False) if event else None
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            identity = self._tenant(connection, owner)
            campaign = snapshot.get("session_id")
            timestamp = now()
            if campaign:
                state = "running" if snapshot.get("is_running") else "idle"
                connection.execute("""INSERT INTO campaigns VALUES (?,?,?,?,?)
                    ON CONFLICT(tenant_id,id) DO UPDATE SET city=excluded.city,state=excluded.state,updated_at=excluded.updated_at""",
                    (identity, campaign, snapshot.get("current_city"), state, timestamp))
            for lead_id, data in snapshot.get("businesses", {}).items():
                connection.execute("""INSERT INTO leads VALUES (?,?,?,?,?)
                    ON CONFLICT(tenant_id,id) DO UPDATE SET campaign_id=excluded.campaign_id,data=excluded.data,updated_at=excluded.updated_at""",
                    (identity, lead_id, campaign, json.dumps(data, allow_nan=False), timestamp))
            connection.execute("""INSERT INTO pipeline_snapshots VALUES (?,?,?)
                ON CONFLICT(tenant_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at""", (identity, encoded, timestamp))
            if event:
                kind = event.get("type", "update")
                connection.execute("INSERT INTO events(tenant_id,campaign_id,kind,payload,created_at) VALUES (?,?,?,?,?)",
                                   (identity, campaign, kind, event_json, timestamp))
                if campaign and kind == "process_started":
                    connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (identity, "discovery:" + campaign, campaign, "lead_discovery", "running", event_json, None, None, timestamp, timestamp))
                if campaign and kind in {"lead_finding_completed", "lead_finding_failed"}:
                    state = "completed" if kind == "lead_finding_completed" else "failed"
                    connection.execute("UPDATE jobs SET state=?,updated_at=? WHERE tenant_id=? AND id=?",
                                       (state, timestamp, identity, "discovery:" + campaign))

    def interrupt_incomplete(self, owner):
        """Mark lost in-process work accurately; never replay provider actions on restart."""
        identity = tenant_id(owner)
        with self.connection() as connection:
            connection.execute("UPDATE jobs SET state='interrupted',updated_at=? WHERE tenant_id=? AND state IN ('queued','running')",
                               (now(), identity))
            row = connection.execute("SELECT data FROM pipeline_snapshots WHERE tenant_id=?", (identity,)).fetchone()
            if row:
                snapshot = json.loads(row[0])
                snapshot["is_running"] = False
                connection.execute("UPDATE pipeline_snapshots SET data=?,updated_at=? WHERE tenant_id=?",
                                   (json.dumps(snapshot), now(), identity))
            connection.execute("UPDATE campaigns SET state='interrupted',updated_at=? WHERE tenant_id=? AND state='running'", (now(), identity))

    def leads(self, owner):
        with self.connection() as connection:
            rows = connection.execute("SELECT data FROM leads WHERE tenant_id=? ORDER BY id", (tenant_id(owner),)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def events(self, owner):
        with self.connection() as connection:
            rows = connection.execute("SELECT id,kind,payload FROM events WHERE tenant_id=? ORDER BY id", (tenant_id(owner),)).fetchall()
        return [{"id": row[0], "kind": row[1], "payload": json.loads(row[2])} for row in rows]

    def job(self, owner, job_id):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE tenant_id=? AND id=?", (tenant_id(owner), job_id)).fetchone()
        return dict(row) if row else None

    def create_job(self, owner, kind, payload, campaign_id=None, provider=None):
        job_id, encoded = str(uuid.uuid4()), json.dumps(payload, allow_nan=False)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            identity = self._tenant(connection, owner)
            generation = None
            if provider:
                row = connection.execute("SELECT generation FROM integration_connections WHERE tenant_id=? AND provider=? AND connected=1", (identity, provider)).fetchone()
                if row is None:
                    raise ValueError("Integration is disconnected")
                generation = row[0]
            timestamp = now()
            connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (identity, job_id, campaign_id, kind, "queued", encoded, provider, generation, timestamp, timestamp))
        return job_id

    def job_connection_valid(self, owner, job_id):
        job = self.job(owner, job_id)
        if not job:
            return False
        if not job["provider"]:
            return True
        with self.connection() as connection:
            return connection.execute("SELECT 1 FROM integration_connections WHERE tenant_id=? AND provider=? AND connected=1 AND generation=?",
                (tenant_id(owner), job["provider"], job["connection_generation"])).fetchone() is not None

    def backup(self, destination):
        destination = Path(destination)
        if not self.path.is_file():
            raise ValueError("Source database does not exist")
        if destination.exists():
            raise ValueError("Backup destination already exists; refusing to overwrite")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb"):
            pass  # Reserve the name atomically before opening SQLite.
        with self.connection() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity verification failed")
