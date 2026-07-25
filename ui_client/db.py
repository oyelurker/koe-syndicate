import aiosqlite
import json
import os
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "tokens.db"))

async def init_db():
    """Initializes the database schema."""
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
        await db.commit()

async def upsert_user(user_info, credentials) -> str:
    """Inserts or updates a user and returns their ID."""
    user_id = user_info.get("id") or str(hash(user_info.get("email")))
    email = user_info.get("email")
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
                refresh_token=excluded.refresh_token,
                token_uri=excluded.token_uri,
                client_id=excluded.client_id,
                client_secret=excluded.client_secret,
                scopes=excluded.scopes,
                updated_at=CURRENT_TIMESTAMP
        """, (
            user_id, email, name, picture,
            credentials.token, credentials.refresh_token, credentials.token_uri,
            credentials.client_id, credentials.client_secret, scopes_json
        ))
        
        # Get the ID (might be different if we matched on email)
        async with db.execute("SELECT id FROM users WHERE email = ?", (email,)) as cursor:
            row = await cursor.fetchone()
            actual_user_id = row[0]
            
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
                        "token": row[4],
                        "refresh_token": row[5],
                        "token_uri": row[6],
                        "client_id": row[7],
                        "client_secret": row[8],
                        "scopes": scopes
                    }
                }
            return None

async def delete_session(session_id: str):
    """Deletes a session."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()

async def get_default_user_credentials():
    """
    Fallback for A2A communication where no session is passed. 
    Returns the most recently updated user's credentials.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # check if table exists first just in case
        try:
            async with db.execute("""
                SELECT email, access_token, refresh_token, token_uri, client_id, client_secret, scopes
                FROM users
                ORDER BY updated_at DESC LIMIT 1
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    scopes = json.loads(row[6]) if row[6] else []
                    return {
                        "email": row[0],
                        "credentials": {
                            "token": row[1],
                            "refresh_token": row[2],
                            "token_uri": row[3],
                            "client_id": row[4],
                            "client_secret": row[5],
                            "scopes": scopes
                        }
                    }
        except aiosqlite.OperationalError:
            pass # tables might not be created yet
        return None
