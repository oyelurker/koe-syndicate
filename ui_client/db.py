import aiosqlite
import asyncio
import json
import os
from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials
from .token_crypto import encrypt, decrypt, cipher, PREFIX
from .store import Store, tenant_id, now

DB_PATH = Path(os.getenv("DB_PATH", "tokens.db"))

async def init_db():
    """Initializes the database schema."""
    cipher()  # Fail before touching stored credentials if key configuration is invalid.
    await asyncio.to_thread(Store(DB_PATH).check_version)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                name TEXT,
                picture_url TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                expires_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        # Encrypt existing plaintext rows transactionally. Keep this key stable;
        # deleting or changing it makes previously encrypted credentials unreadable.
        async with db.execute("SELECT id, access_token, refresh_token, client_secret FROM users") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            values = [v if v is None or v.startswith(PREFIX) else encrypt(v) for v in row[1:]]
            await db.execute("UPDATE users SET access_token=?, refresh_token=?, client_secret=? WHERE id=?", (*values, row[0]))
        await db.commit()
    await asyncio.to_thread(Store(DB_PATH).initialize)

async def upsert_user(user_info, credentials) -> str:
    """Inserts or updates a user and returns their ID."""
    email = (user_info.get("email") or "").strip().lower()
    identity = tenant_id(email)
    user_id = user_info.get("id") or "local-" + identity
    name = user_info.get("name")
    picture = user_info.get("picture")
    
    scopes_json = json.dumps(credentials.scopes) if credentials.scopes else "[]"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (
                id, email, name, picture_url, 
                access_token, refresh_token, token_uri, client_id, client_secret, scopes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name,
                picture_url=excluded.picture_url,
                access_token=excluded.access_token,
                refresh_token=COALESCE(excluded.refresh_token, users.refresh_token),
                token_uri=excluded.token_uri,
                client_id=excluded.client_id,
                client_secret=excluded.client_secret,
                scopes=excluded.scopes,
                updated_at=CURRENT_TIMESTAMP
        """, (
            user_id, email, name, picture,
            encrypt(credentials.token), encrypt(credentials.refresh_token), credentials.token_uri,
            credentials.client_id, encrypt(credentials.client_secret), scopes_json
        ))
        
        # Get the ID (might be different if we matched on email)
        async with db.execute("SELECT id FROM users WHERE email = ?", (email,)) as cursor:
            row = await cursor.fetchone()
            actual_user_id = row[0]
        await db.execute("INSERT OR IGNORE INTO tenants VALUES (?,?,?)", (identity, email, now()))
        await db.execute("""INSERT INTO integration_connections VALUES (?, 'google', ?, 1, 1, ?)
            ON CONFLICT(tenant_id,provider) DO UPDATE SET user_id=excluded.user_id,connected=1,
            generation=integration_connections.generation + CASE WHEN integration_connections.connected=0 THEN 1 ELSE 0 END,
            updated_at=excluded.updated_at""", (identity, actual_user_id, now()))
        await db.commit()
        return actual_user_id

async def create_session(session_id: str, user_id: str, expires_in_days: int = 30):
    """Creates a new session."""
    import datetime
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=expires_in_days)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO sessions (session_id, user_id, expires_at) VALUES (?, ?, ?)", 
                         (session_id, user_id, expires_at.isoformat()))
        await db.commit()

async def get_user_by_session(session_id: str):
    """Gets user info and credentials from a session ID. Returns None if invalid or expired."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Also clean up expired sessions
        await db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        await db.commit()
        
        async with db.execute("""
            SELECT u.id, u.email, u.name, u.picture_url, 
                   u.access_token, u.refresh_token, u.token_uri, 
                   u.client_id, u.client_secret, u.scopes
            FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.session_id = ? AND s.expires_at > ?
        """, (session_id, now)) as cursor:
            row = await cursor.fetchone()
            
            if row:
                scopes = json.loads(row[9]) if row[9] else []
                return {
                    "id": row[0],
                    "email": row[1],
                    "name": row[2],
                    "picture": row[3],
                    "credentials": {
                        "token": decrypt(row[4]),
                        "refresh_token": decrypt(row[5]),
                        "token_uri": row[6],
                        "client_id": row[7],
                        "client_secret": decrypt(row[8]),
                        "scopes": scopes
                    }
                }
            return None

async def get_credentials_for_user(session_id: str) -> Optional[Credentials]:
    user = await get_user_by_session(session_id)
    if not user:
        return None
    
    creds = user["credentials"]
    return Credentials(
        token=creds["token"],
        refresh_token=creds["refresh_token"],
        token_uri=creds["token_uri"],
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        scopes=creds["scopes"]
    )

async def delete_session(session_id: str):
    """Deletes a session."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()

async def disconnect_user(user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT email FROM users WHERE id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            identity = tenant_id(row[0])
            await db.execute("UPDATE integration_connections SET connected=0,user_id=NULL,generation=generation+1,updated_at=? WHERE tenant_id=? AND provider='google'", (now(), identity))
            await db.execute("UPDATE jobs SET state='cancelled',updated_at=? WHERE tenant_id=? AND provider='google' AND state IN ('queued','running')", (now(), identity))
        await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()

async def credentials_for_owner(email: str):
    from common.security import require_owner
    require_owner(email)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT access_token, refresh_token, token_uri, client_id, client_secret, scopes FROM users WHERE lower(email) = ?", (email.lower(),)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return Credentials(token=decrypt(row[0]), refresh_token=decrypt(row[1]), token_uri=row[2], client_id=row[3], client_secret=decrypt(row[4]), scopes=json.loads(row[5]))
