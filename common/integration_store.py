"""Durable inbox acceptance and confirmed meeting records on the shared host."""
import hashlib
import json
import time

from .execution_store import WorkStore, canonical, enqueue, owner_context
from .security import SecurityError


def create_schema(db):
    for statement in '''
      CREATE TABLE IF NOT EXISTS gmail_cursors (
        owner TEXT,mailbox TEXT,history_id TEXT NOT NULL,PRIMARY KEY(owner,mailbox));
      CREATE TABLE IF NOT EXISTS gmail_messages (
        owner TEXT,mailbox TEXT,message_id TEXT,job_id TEXT NOT NULL,data TEXT NOT NULL,
        accepted_at REAL NOT NULL,PRIMARY KEY(owner,mailbox,message_id));
      CREATE TABLE IF NOT EXISTS meeting_records (
        owner TEXT,action_id TEXT,campaign TEXT,provider_id TEXT NOT NULL,
        data TEXT NOT NULL,created_at REAL NOT NULL,PRIMARY KEY(owner,action_id));
      CREATE TABLE IF NOT EXISTS calendar_intervals (
        owner TEXT,action_id TEXT,start REAL NOT NULL,end REAL NOT NULL,
        PRIMARY KEY(owner,action_id));
    '''.split(';'):
        if statement.strip():
            db.execute(statement)


class IntegrationStore(WorkStore):
    def claim_calendar(self, key, start, end):
        context = owner_context()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._job(db, context)
            action = db.execute("SELECT 1 FROM provider_actions WHERE owner=? AND id=? AND campaign=? AND job_id=? AND kind='calendar' AND state='reserved'",
                                (context.owner.lower(), key, context.campaign_id, context.job_id)).fetchone()
            if not action:
                raise SecurityError('Calendar reservation is not owned by the active job')
            conflict = db.execute("SELECT i.action_id FROM calendar_intervals i JOIN provider_actions a ON a.owner=i.owner AND a.id=i.action_id WHERE i.owner=? AND i.action_id!=? AND i.start<? AND i.end>? AND a.state NOT IN ('failed','cancelled')",
                                  (context.owner.lower(), key, end.timestamp(), start.timestamp())).fetchone()
            if conflict:
                raise SecurityError('Calendar interval already reserved or awaiting reconciliation')
            db.execute('INSERT OR IGNORE INTO calendar_intervals VALUES (?,?,?,?)',
                       (context.owner.lower(), key, start.timestamp(), end.timestamp()))

    def cursor(self, mailbox):
        context = owner_context(False)
        with self.connection() as db:
            row = db.execute('SELECT history_id FROM gmail_cursors WHERE owner=? AND mailbox=?',
                             (context.owner.lower(), mailbox.lower())).fetchone()
            return row[0] if row else None

    def advance(self, mailbox, history_id):
        context = owner_context(False)
        if not str(history_id).isdigit():
            raise ValueError('Invalid Gmail history cursor')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT history_id FROM gmail_cursors WHERE owner=? AND mailbox=?',
                             (context.owner.lower(), mailbox.lower())).fetchone()
            if not row or int(history_id) > int(row[0]):
                db.execute('INSERT OR REPLACE INTO gmail_cursors VALUES (?,?,?)',
                           (context.owner.lower(), mailbox.lower(), str(history_id)))

    def accept(self, mailbox, message):
        """Acknowledgeable only after message and its real A2A job commit together."""
        context = owner_context(False)
        message_id = message.get('id')
        if not isinstance(message_id, str) or not message_id or len(message_id) > 200:
            raise ValueError('Invalid Gmail message identity')
        data = canonical(message)
        if len(data.encode()) > 1024 * 1024:
            raise ValueError('Gmail message exceeds durable ingestion limit')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT job_id FROM gmail_messages WHERE owner=? AND mailbox=? AND message_id=?',
                                  (context.owner.lower(), mailbox.lower(), message_id)).fetchone()
            if previous:
                return previous[0]
            tenant = hashlib.sha256(context.owner.lower().encode()).hexdigest()
            row = db.execute('SELECT data FROM pipeline_snapshots WHERE tenant_id=?', (tenant,)).fetchone()
            campaign = json.loads(row[0]).get('session_id') if row else None
            if not campaign:
                raise SecurityError('Start a campaign before accepting mailbox work')
            identity = enqueue(db, context.owner, campaign, 'lead_manager',
                               {'query': 'check_lead_emails', 'gmail_message_id': message_id,
                                'mailbox': mailbox.lower()}, context.mode)
            db.execute('INSERT INTO gmail_messages VALUES (?,?,?,?,?,?)',
                       (context.owner.lower(), mailbox.lower(), message_id, identity, data, time.time()))
            return identity

    def job_message(self):
        job = self.require_job()
        payload = json.loads(job['payload']) if isinstance(job['payload'], str) else job['payload']
        if not payload.get('gmail_message_id'):
            return None
        context = owner_context()
        with self.connection() as db:
            row = db.execute('SELECT data FROM gmail_messages WHERE owner=? AND mailbox=? AND message_id=? AND job_id=?',
                             (context.owner.lower(), payload['mailbox'], payload['gmail_message_id'], job['id'])).fetchone()
            if not row:
                raise SecurityError('Accepted email is missing from this job')
            return json.loads(row[0])

    def save_meeting(self, key):
        """Use provider proof, never caller/model-supplied success or meeting fields."""
        context = owner_context()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM provider_actions WHERE owner=? AND id=? AND campaign=? AND kind='calendar' AND state='succeeded'",
                             (context.owner.lower(), key, context.campaign_id)).fetchone()
            if not row or not row['provider_id']:
                raise SecurityError('Confirmed Calendar receipt required for meeting persistence')
            data = {'request': json.loads(row['payload']), 'receipt': json.loads(row['result'])}
            db.execute('INSERT OR IGNORE INTO meeting_records VALUES (?,?,?,?,?,?)',
                       (context.owner.lower(), key, row['campaign'], row['provider_id'], canonical(data), time.time()))
        return {'success': True, 'persisted': True, 'storage': 'local_sqlite',
                'meeting_id': row['provider_id'], 'action_key': key}

    def meetings(self):
        context = owner_context(False)
        with self.connection() as db:
            return [dict(row) | {'data': json.loads(row['data'])} for row in db.execute(
                'SELECT * FROM meeting_records WHERE owner=? ORDER BY created_at DESC LIMIT 200', (context.owner.lower(),))]
