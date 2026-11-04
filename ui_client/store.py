"""Versioned, tenant-owned local records. Execution/retry scheduling is separate."""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

SCHEMA_VERSION = 4


class StoreConflict(ValueError):
    """The caller must reload; a newer committed view must never be overwritten."""
    pass


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
            connection.execute("BEGIN IMMEDIATE")
            # Re-read after acquiring the writer lock: another process may migrate.
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == SCHEMA_VERSION:
                return
            if version == 3:
                self._migrate_v4(connection)
                return
            if version == 1:
                self._migrate_v2(connection)
                self._migrate_v3(connection)
                return
            if version == 2:
                self._migrate_v3(connection)
                return
            schema = """
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
            """
            for statement in schema.split(";"):
                if statement.strip():
                    connection.execute(statement)
            # Existing users retain their encrypted credentials and gain a tenant.
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
                # Case-colliding legacy profiles require review; never merge them silently.
                connection.execute("UPDATE users SET email=lower(trim(email))")
                for user in connection.execute("SELECT id,email FROM users"):
                    identity = self._tenant(connection, user["email"])
                    connection.execute("INSERT OR IGNORE INTO integration_connections VALUES (?, 'google', ?, 1, 1, ?)",
                                       (identity, user["id"], now()))
            self._migrate_v2(connection)
            self._migrate_v3(connection)

    def _migrate_v3(self, connection):
        from common.execution_store import create_schema
        create_schema(connection)
        connection.execute("PRAGMA user_version=3")
        self._migrate_v4(connection)

    def _migrate_v4(self, connection):
        from common.integration_store import create_schema
        create_schema(connection)
        connection.execute("PRAGMA user_version=4")

    def _migrate_v2(self, connection):
        connection.execute("ALTER TABLE pipeline_snapshots ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        connection.execute("ALTER TABLE jobs ADD COLUMN worker_id TEXT")
        connection.execute("CREATE TABLE IF NOT EXISTS runtime_workers (id TEXT PRIMARY KEY, expires_at REAL NOT NULL)")
        connection.execute("PRAGMA user_version=2")

    def heartbeat(self, worker_id):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT expires_at FROM runtime_workers WHERE id=?", (worker_id,)).fetchone()
            if existing and existing[0] <= time.time():
                raise StoreConflict("Worker lease expired; restart this worker before renewing")
            connection.execute("INSERT INTO runtime_workers VALUES (?,?) ON CONFLICT(id) DO UPDATE SET expires_at=excluded.expires_at",
                               (worker_id, time.time() + 90))

    def release_worker(self, worker_id):
        with self.connection() as connection:
            connection.execute("UPDATE runtime_workers SET expires_at=0 WHERE id=?", (worker_id,))

    def read_view(self, owner, after=None, limit=200):
        """Read a consistent owner snapshot, revision and bounded committed outbox."""
        identity = tenant_id(owner)
        if not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("Invalid event batch size")
        with self.connection() as connection:
            connection.execute("BEGIN")
            row = connection.execute("SELECT data,revision FROM pipeline_snapshots WHERE tenant_id=?", (identity,)).fetchone()
            cursor = connection.execute("SELECT COALESCE(MAX(id),0) FROM events WHERE tenant_id=?", (identity,)).fetchone()[0]
            events = []
            if after is not None:
                events = [{"id": r[0], "campaign_id": r[1], "payload": json.loads(r[2])} for r in connection.execute(
                    "SELECT id,campaign_id,payload FROM events WHERE tenant_id=? AND id>? AND id<=? ORDER BY id LIMIT ?",
                    (identity, after, cursor, limit))]
        return {"snapshot": json.loads(row[0]) if row else None, "revision": row[1] if row else 0,
                "cursor": cursor, "events": events}

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

    def save(self, owner, snapshot, event=None, *, expected_revision=0, worker_id=None, dispatch=None):
        # Serialize before beginning a transaction; invalid payloads change nothing.
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("An explicit nonnegative revision is required")
        encoded = json.dumps(snapshot, allow_nan=False)
        event_json = json.dumps(event, allow_nan=False) if event else None
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            identity = tenant_id(owner)
            row = connection.execute("SELECT revision,data FROM pipeline_snapshots WHERE tenant_id=?", (identity,)).fetchone()
            if worker_id and not connection.execute("SELECT 1 FROM runtime_workers WHERE id=? AND expires_at>?", (worker_id, time.time())).fetchone():
                raise StoreConflict("Worker lease expired; restart this worker before writing")
            actual_revision = row[0] if row else 0
            if actual_revision != expected_revision:
                raise StoreConflict("Pipeline changed; reload and retry the operation")
            identity = self._tenant(connection, owner)
            revision = actual_revision + 1
            campaign = snapshot.get("session_id")
            old_campaign = json.loads(row[1]).get("session_id") if row else None
            if old_campaign and old_campaign != campaign:
                from common.execution_store import cancel_in_transaction
                cancel_in_transaction(connection, owner, old_campaign)
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
            connection.execute("""INSERT INTO pipeline_snapshots(tenant_id,data,updated_at,revision) VALUES (?,?,?,?)
                ON CONFLICT(tenant_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at,revision=excluded.revision""",
                (identity, encoded, timestamp, revision))
            event_id = None
            if event:
                kind = event.get("type", "update")
                event_json = json.dumps({**event, "campaign_id": campaign, "revision": revision}, allow_nan=False)
                connection.execute("INSERT INTO events(tenant_id,campaign_id,kind,payload,created_at) VALUES (?,?,?,?,?)",
                                   (identity, campaign, kind, event_json, timestamp))
                event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                if campaign and kind == "process_started":
                    connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (identity, "discovery:" + campaign, campaign, "lead_discovery", "running", event_json, None, None, timestamp, timestamp, worker_id))
                if campaign and kind in {"lead_finding_completed", "lead_finding_failed"}:
                    state = "completed" if kind == "lead_finding_completed" else "failed"
                    connection.execute("UPDATE jobs SET state=?,updated_at=? WHERE tenant_id=? AND id=?",
                                       (state, timestamp, identity, "discovery:" + campaign))

            queued_job = None
            if dispatch is not None:
                from common.execution_store import enqueue
                if not campaign:
                    raise ValueError("A durable job requires an active campaign")
                queued_job = enqueue(connection,owner,campaign,dispatch['kind'],dispatch['payload'],dispatch['mode'])
        return {"revision": revision, "event_id": event_id, "job_id": queued_job}

    def interrupt_incomplete(self, owner):
        """Mark lost in-process work accurately; never replay provider actions on restart."""
        identity = tenant_id(owner)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE jobs SET state='interrupted',updated_at=? WHERE tenant_id=? AND state IN ('queued','running') AND NOT EXISTS (SELECT 1 FROM dispatch_jobs WHERE owner=? AND campaign=jobs.campaign_id) AND (worker_id IS NULL OR NOT EXISTS (SELECT 1 FROM runtime_workers WHERE id=jobs.worker_id AND expires_at>?))",
                               (now(), identity, owner.lower(), time.time()))
            row = connection.execute("SELECT data,revision FROM pipeline_snapshots WHERE tenant_id=?", (identity,)).fetchone()
            if row:
                snapshot = json.loads(row[0])
                campaign = snapshot.get("session_id")
                interrupted = connection.execute("SELECT 1 FROM jobs WHERE tenant_id=? AND id=? AND state='interrupted'",
                    (identity, "discovery:" + str(campaign))).fetchone()
                if snapshot.get("is_running") and interrupted:
                    snapshot["is_running"] = False
                    revision = row[1] + 1
                    connection.execute("UPDATE pipeline_snapshots SET data=?,updated_at=?,revision=? WHERE tenant_id=?",
                                       (json.dumps(snapshot), now(), revision, identity))
                    payload = {"type": "process_finished", "status": "interrupted", "campaign_id": campaign, "revision": revision}
                    connection.execute("INSERT INTO events(tenant_id,campaign_id,kind,payload,created_at) VALUES (?,?,?,?,?)",
                        (identity, campaign, "process_finished", json.dumps(payload), now()))
            connection.execute("UPDATE campaigns SET state='interrupted',updated_at=? WHERE tenant_id=? AND state='running' AND EXISTS (SELECT 1 FROM jobs WHERE jobs.tenant_id=campaigns.tenant_id AND jobs.campaign_id=campaigns.id AND jobs.state='interrupted')", (now(), identity))

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
            connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (identity, job_id, campaign_id, kind, "queued", encoded, provider, generation, timestamp, timestamp, None))
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
