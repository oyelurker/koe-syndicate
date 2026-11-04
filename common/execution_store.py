"""Shared local dispatch, approvals and at-most-once provider dispatch.

All participating services must share DB_PATH. No implicit provider retries.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .security import Execution, SecurityError, execution, require_action, require_owner


class PolicyDenied(SecurityError):
    pass


class ActionPending(SecurityError):
    pass


def create_schema(db):
    schema='''
    CREATE TABLE IF NOT EXISTS dispatch_jobs (
      owner TEXT NOT NULL,id TEXT NOT NULL,campaign TEXT NOT NULL,kind TEXT NOT NULL,
      payload TEXT NOT NULL,mode TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
      max_attempts INTEGER NOT NULL,ready_at REAL NOT NULL,lease_until REAL NOT NULL DEFAULT 0,
      claim_token TEXT,worker_id TEXT,error TEXT,result TEXT,created_at REAL NOT NULL,
      PRIMARY KEY(owner,id));
    CREATE INDEX IF NOT EXISTS dispatch_ready ON dispatch_jobs(owner,state,ready_at);
    CREATE TABLE IF NOT EXISTS outreach_policies (owner TEXT PRIMARY KEY,data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS suppressions (owner TEXT,recipient TEXT,reason TEXT,PRIMARY KEY(owner,recipient));
    CREATE TABLE IF NOT EXISTS action_proposals (
      owner TEXT,id TEXT,campaign TEXT,kind TEXT,recipients TEXT,payload TEXT,approved_until REAL NOT NULL DEFAULT 0,
      PRIMARY KEY(owner,id));
    CREATE TABLE IF NOT EXISTS provider_actions (
      owner TEXT,id TEXT,campaign TEXT,job_id TEXT,kind TEXT,recipients TEXT,payload TEXT,
      state TEXT,units INTEGER,quantity INTEGER NOT NULL DEFAULT 1,created_at REAL,provider_id TEXT,result TEXT,cancel_requested INTEGER DEFAULT 0,
      PRIMARY KEY(owner,id));
    CREATE TABLE IF NOT EXISTS action_artifacts (owner TEXT,digest TEXT,name TEXT,data BLOB,PRIMARY KEY(owner,digest));
    CREATE TABLE IF NOT EXISTS action_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,owner TEXT,action_id TEXT,decision TEXT,reason TEXT,created_at REAL);
    '''
    for statement in schema.split(';'):
        if statement.strip():
            db.execute(statement)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def normalize_email(value):
    if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}",value):
        raise PolicyDenied('A single valid recipient email is required')
    local,domain=value.rsplit('@',1)
    return local+'@'+domain.lower()


def normalize_phone(value):
    if not isinstance(value,str) or not re.fullmatch(r'[+0-9 ()\.\-]{7,30}',value):
        raise PolicyDenied('Unsupported phone format; use an explicit +1 or +91 country code')
    number=re.sub(r'[ ()\.\-]','',value)
    if number.startswith('00'):
        number='+'+number[2:]
    if not number.startswith('+'):
        country=os.getenv('PHONE_DEFAULT_COUNTRY','')
        if country not in {'1','91'} or len(number)!=10:
            raise PolicyDenied('An explicit supported country code is required')
        number='+'+country+number
    if not (re.fullmatch(r'\+1[2-9]\d{2}[2-9]\d{6}',number) or re.fullmatch(r'\+91[6-9]\d{9}',number)):
        raise PolicyDenied('Unsupported or invalid destination; supported countries are +1 and +91')
    return number


def owner_context(campaign=True):
    context=execution.get()
    if context is None:
        raise PolicyDenied('Verified execution context is required')
    require_owner(context.owner)
    if campaign and not context.campaign_id:
        raise PolicyDenied('A verified campaign is required')
    return context


def job_id(owner,campaign,kind,payload):
    return kind+':'+hashlib.sha256(canonical([owner.lower(),campaign,kind,payload]).encode()).hexdigest()


def enqueue(db,owner,campaign,kind,payload,mode):
    if kind not in {'discovery','sdr','lead_manager','action'} or mode not in {'demo','live'}:
        raise ValueError('Unsupported durable job')
    identity=job_id(owner,campaign,kind,payload)
    db.execute('INSERT OR IGNORE INTO dispatch_jobs(owner,id,campaign,kind,payload,mode,state,max_attempts,ready_at,created_at) VALUES (?,?,?,?,?,?,\'queued\',?,?,?)',
        (owner.lower(),identity,campaign,kind,canonical(payload),mode,3 if kind=='discovery' else 1,time.time(),time.time()))
    if kind=='discovery':
        tenant=hashlib.sha256(owner.strip().lower().encode()).hexdigest()
        db.execute("UPDATE jobs SET state='queued' WHERE tenant_id=? AND id=?",(tenant,'discovery:'+campaign))
    return identity


def cancel_in_transaction(db,owner,campaign):
    tenant=hashlib.sha256(owner.strip().lower().encode()).hexdigest()
    db.execute("UPDATE jobs SET state='cancelled' WHERE tenant_id=? AND campaign_id=? AND state IN ('queued','running')",(tenant,campaign))
    db.execute("UPDATE dispatch_jobs SET state='cancelled',lease_until=0,error='Campaign cancelled' WHERE owner=? AND campaign=? AND state IN ('queued','running','uncertain')",(owner.lower(),campaign))
    db.execute("UPDATE provider_actions SET cancel_requested=1,state=CASE WHEN state='reserved' THEN 'cancelled' ELSE state END WHERE owner=? AND campaign=? AND state NOT IN ('succeeded','failed','cancelled')",(owner.lower(),campaign))
    db.execute('UPDATE action_proposals SET approved_until=0 WHERE owner=? AND campaign=?',(owner.lower(),campaign))


class WorkStore:
    def __init__(self,path=None):
        self.path=Path(path or os.getenv('DB_PATH','tokens.db')).resolve()

    @contextmanager
    def connection(self):
        # A wrong/missing shared path must fail, never create a separate empty ledger.
        with closing(sqlite3.connect(self.path.as_uri()+'?mode=rw',uri=True,timeout=5)) as db,db:
            db.row_factory=sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            yield db

    def _active(self,db,context):
        tenant=hashlib.sha256(context.owner.strip().lower().encode()).hexdigest()
        row=db.execute('SELECT data FROM pipeline_snapshots WHERE tenant_id=?',(tenant,)).fetchone()
        if not row or json.loads(row[0]).get('session_id')!=context.campaign_id:
            raise PolicyDenied('Campaign cancelled, missing or superseded')

    def _job(self,db,context):
        self._active(db,context)
        row=db.execute('SELECT * FROM dispatch_jobs WHERE owner=? AND id=?',(context.owner.lower(),context.job_id)).fetchone()
        if (not row or row['campaign']!=context.campaign_id or row['mode']!=context.mode or row['state']!='running'
                or row['claim_token']!=context.job_token or row['lease_until']<=time.time()):
            raise PolicyDenied('Durable job is cancelled, expired or not owned by this execution')
        worker=db.execute('SELECT expires_at FROM runtime_workers WHERE id=?',(row['worker_id'],)).fetchone()
        if not worker or worker[0]<=time.time():
            raise PolicyDenied('Worker lease expired')
        return row

    def require_job(self):
        context=owner_context()
        with self.connection() as db:
            return dict(self._job(db,context))

    def jobs(self,owner):
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT id,campaign,kind,mode,state,attempts,max_attempts,error,result,created_at FROM dispatch_jobs WHERE owner=? ORDER BY created_at DESC LIMIT 100',(owner.lower(),))]

    def claim(self,owner,worker,mode):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            lease=db.execute('SELECT expires_at FROM runtime_workers WHERE id=?',(worker,)).fetchone()
            if not lease or lease[0]<=time.time():
                return None
            stale=db.execute("SELECT * FROM dispatch_jobs WHERE owner=? AND state='running' AND (lease_until<=? OR NOT EXISTS (SELECT 1 FROM runtime_workers WHERE id=dispatch_jobs.worker_id AND expires_at>?))",(owner.lower(),time.time(),time.time())).fetchall()
            for row in stale:
                state='queued' if row['kind']=='discovery' and row['attempts']<row['max_attempts'] else ('failed' if row['kind']=='discovery' else 'uncertain')
                receipt=None
                if row['kind']=='action':
                    key=json.loads(row['payload'])['action_key']
                    action=db.execute('SELECT state,result FROM provider_actions WHERE owner=? AND id=?',(owner.lower(),key)).fetchone()
                    if action and action['state'] in {'succeeded','failed'}:
                        state='completed' if action['state']=='succeeded' else 'failed'
                        receipt=canonical({'success':action['state']=='succeeded','provider_result':json.loads(action['result']) if action['result'] else None})
                db.execute('UPDATE dispatch_jobs SET state=?,lease_until=0,error=?,result=COALESCE(?,result) WHERE owner=? AND id=?',
                    (state,None if receipt else 'Previous worker lost; provider writes are never replayed',receipt,owner.lower(),row['id']))
                if row['kind']=='discovery':
                    self._mirror_discovery(db,owner,row['campaign'],state)
                if state in {'failed','uncertain'}:
                    self._terminal_view(db,owner,row['campaign'],state)
            if db.execute("SELECT 1 FROM dispatch_jobs WHERE owner=? AND state='running'",(owner.lower(),)).fetchone():
                return None
            row=db.execute("SELECT * FROM dispatch_jobs WHERE owner=? AND mode=? AND state='queued' AND ready_at<=? ORDER BY created_at LIMIT 1",(owner.lower(),mode,time.time())).fetchone()
            if row is None:
                return None
            context=Execution(owner,mode,row['campaign'])
            try:
                self._active(db,context)
            except PolicyDenied:
                db.execute("UPDATE dispatch_jobs SET state='cancelled' WHERE owner=? AND id=?",(owner.lower(),row['id']))
                return None
            token=secrets.token_hex(24)
            db.execute("UPDATE dispatch_jobs SET state='running',attempts=attempts+1,claim_token=?,worker_id=?,lease_until=? WHERE owner=? AND id=?",(token,worker,time.time()+45,owner.lower(),row['id']))
            if row['kind']=='discovery':
                self._mirror_discovery(db,owner,row['campaign'],'running',worker)
                self._running_view(db,owner,row['campaign'])
            result=dict(row); result.update(state='running',attempts=row['attempts']+1,claim_token=token,worker_id=worker)
            result['payload']=json.loads(result['payload'])
            return result

    def _mirror_discovery(self,db,owner,campaign,state,worker=None):
        tenant=hashlib.sha256(owner.strip().lower().encode()).hexdigest()
        db.execute('UPDATE jobs SET state=?,worker_id=?,updated_at=? WHERE tenant_id=? AND id=?',
            (state,worker,datetime.now(timezone.utc).isoformat(),tenant,'discovery:'+campaign))

    def _running_view(self,db,owner,campaign):
        tenant=hashlib.sha256(owner.strip().lower().encode()).hexdigest()
        row=db.execute('SELECT data,revision FROM pipeline_snapshots WHERE tenant_id=?',(tenant,)).fetchone()
        if row:
            snapshot=json.loads(row[0])
            if snapshot.get('session_id')==campaign and not snapshot.get('is_running'):
                snapshot['is_running']=True; revision=row[1]+1
                db.execute('UPDATE pipeline_snapshots SET data=?,revision=?,updated_at=? WHERE tenant_id=?',
                    (canonical(snapshot),revision,datetime.now(timezone.utc).isoformat(),tenant))
                event={'type':'process_started','city':snapshot.get('current_city'),'campaign_id':campaign,'revision':revision}
                db.execute('INSERT INTO events(tenant_id,campaign_id,kind,payload,created_at) VALUES (?,?,?,?,?)',
                    (tenant,campaign,'process_started',canonical(event),datetime.now(timezone.utc).isoformat()))

    def _terminal_view(self,db,owner,campaign,state):
        tenant=hashlib.sha256(owner.strip().lower().encode()).hexdigest()
        row=db.execute('SELECT data,revision FROM pipeline_snapshots WHERE tenant_id=?',(tenant,)).fetchone()
        if row:
            snapshot=json.loads(row[0])
            if snapshot.get('session_id')==campaign and snapshot.get('is_running'):
                snapshot['is_running']=False
                revision=row[1]+1
                db.execute('UPDATE pipeline_snapshots SET data=?,revision=?,updated_at=? WHERE tenant_id=?',(canonical(snapshot),revision,datetime.now(timezone.utc).isoformat(),tenant))
                event={'type':'process_finished','status':state,'campaign_id':campaign,'revision':revision}
                db.execute('INSERT INTO events(tenant_id,campaign_id,kind,payload,created_at) VALUES (?,?,?,?,?)',
                    (tenant,campaign,'process_finished',canonical(event),datetime.now().isoformat()))

    def renew(self,context):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self._job(db,context)
            db.execute('UPDATE dispatch_jobs SET lease_until=? WHERE owner=? AND id=?',(time.time()+45,context.owner.lower(),context.job_id))

    def finish_job(self,context,result=None,error=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=self._job(db,context)
            if error:
                state='queued' if row['kind']=='discovery' and row['attempts']<row['max_attempts'] else ('failed' if row['kind']=='discovery' else 'uncertain')
            else:
                state='completed'
            if row['kind']=='action':
                key=json.loads(row['payload'])['action_key']
                action=db.execute('SELECT state,result FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
                if action and action['state']=='succeeded':
                    state='completed'; error=None
                    result={'success':True,'provider_result':json.loads(action['result'])}
                elif error and (action is None or action['state'] in {'reserved','failed','cancelled'}):
                    state='failed'
            db.execute('UPDATE dispatch_jobs SET state=?,result=?,error=?,ready_at=?,lease_until=0 WHERE owner=? AND id=?',
                (state,canonical(result) if result is not None else None,error,time.time()+min(30,2**row['attempts']),context.owner.lower(),context.job_id))
            if row['kind']=='discovery':
                self._mirror_discovery(db,context.owner,context.campaign_id,state)
            if state in {'failed','uncertain'}:
                self._terminal_view(db,context.owner,context.campaign_id,state)
            return state

    def cancel_job(self,identity):
        context=owner_context(False)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM dispatch_jobs WHERE owner=? AND id=?',(context.owner.lower(),identity)).fetchone()
            if row is None or row['state'] in {'completed','failed'}:
                return False
            db.execute("UPDATE dispatch_jobs SET state='cancelled',lease_until=0,error='Owner cancelled job' WHERE owner=? AND id=?",(context.owner.lower(),identity))
            db.execute("UPDATE provider_actions SET cancel_requested=1,state=CASE WHEN state='reserved' THEN 'cancelled' ELSE state END WHERE owner=? AND job_id=? AND state NOT IN ('succeeded','failed','cancelled')",(context.owner.lower(),identity))
            db.execute('UPDATE action_proposals SET approved_until=0 WHERE owner=? AND id IN (SELECT id FROM provider_actions WHERE owner=? AND job_id=?)',
                (context.owner.lower(),context.owner.lower(),identity))
            if row['kind']=='action':
                key=json.loads(row['payload'])['action_key']
                db.execute('UPDATE action_proposals SET approved_until=0 WHERE owner=? AND id=?',(context.owner.lower(),key))
            if row['kind']=='discovery':
                self._mirror_discovery(db,context.owner,row['campaign'],'cancelled')
                self._terminal_view(db,context.owner,row['campaign'],'cancelled')
            return True

    def policy(self):
        context=owner_context(False)
        with self.connection() as db:
            row=db.execute('SELECT data FROM outreach_policies WHERE owner=?',(context.owner.lower(),)).fetchone()
            return json.loads(row[0]) if row else None

    def actions(self):
        context=owner_context(False)
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT id,campaign,job_id,kind,recipients,state,units,quantity,created_at,provider_id,result,cancel_requested FROM provider_actions WHERE owner=? ORDER BY CASE WHEN state IN ('unknown','dispatching','initiated','reserved') THEN 0 ELSE 1 END,created_at DESC LIMIT 100",(context.owner.lower(),))]

    def configure(self,policy):
        context=owner_context(False)
        required={'hourly_limit','daily_limit','concurrency','daily_units','timezone','start_hour','end_hour','weekdays','recipients','unit_costs'}
        if set(policy)!=required:
            raise PolicyDenied('Complete explicit outreach policy is required')
        for field in ('hourly_limit','daily_limit','concurrency','daily_units'):
            if type(policy[field]) is not int or not 0<=policy[field]<=100000:
                raise PolicyDenied('Invalid policy limits')
        if not (type(policy['start_hour']) is int and type(policy['end_hour']) is int and 0<=policy['start_hour']<policy['end_hour']<=24):
            raise PolicyDenied('Invalid contact window')
        ZoneInfo(policy['timezone'])
        if not policy['weekdays'] or any(type(d) is not int or d not in range(7) for d in policy['weekdays']):
            raise PolicyDenied('Explicit contact weekdays are required')
        if set(policy['unit_costs'])!={'calls','email','calendar'} or any(type(v) is not int or not 1<=v<=100000 for v in policy['unit_costs'].values()):
            raise PolicyDenied('Positive per-action reservation ceilings are required')
        if not isinstance(policy['recipients'],list) or not all(isinstance(r,str) for r in policy['recipients']):
            raise PolicyDenied('Explicit recipient allowlist is required')
        policy={**policy,'recipients':[normalize_phone(r) if r.startswith('+') else normalize_email(r) for r in policy['recipients']]}
        with self.connection() as db:
            db.execute('INSERT INTO outreach_policies VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET data=excluded.data',(context.owner.lower(),canonical(policy)))
            self._audit(db,context.owner,None,'policy_updated','Owner configuration')

    def suppress(self,recipient,reason='Owner opt-out'):
        context=owner_context(False)
        recipient=normalize_phone(recipient) if recipient.startswith('+') else normalize_email(recipient)
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO suppressions VALUES (?,?,?)',(context.owner.lower(),recipient,reason[:200]))
            self._audit(db,context.owner,None,'suppressed','Recipient opted out')

    def _audit(self,db,owner,key,decision,reason):
        db.execute('INSERT INTO action_audit(owner,action_id,decision,reason,created_at) VALUES (?,?,?,?,?)',(owner.lower(),key,decision,reason,time.time()))

    def propose(self,kind,recipients,payload):
        context=owner_context()
        if kind not in {'calls','email','calendar'} or not recipients:
            raise PolicyDenied('Unsupported action')
        recipients=sorted(set(normalize_phone(r) if kind=='calls' else normalize_email(r) for r in recipients))
        key=hashlib.sha256(canonical([context.owner.lower(),context.campaign_id,context.mode,kind,recipients,payload]).encode()).hexdigest()
        with self.connection() as db:
            self._active(db,context)
            db.execute('INSERT OR IGNORE INTO action_proposals(owner,id,campaign,kind,recipients,payload) VALUES (?,?,?,?,?,?)',
                (context.owner.lower(),key,context.campaign_id,kind,canonical(recipients),canonical(payload)))
        return key

    def owner_action(self,key):
        context=owner_context(False)
        with self.connection() as db:
            row=db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            return dict(row) if row else None

    def queue_approved(self,key):
        context=owner_context(False)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            proposal=db.execute('SELECT * FROM action_proposals WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            if proposal is None or proposal['approved_until']<=time.time():
                raise PolicyDenied('Exact action must be approved first')
            require_action(proposal['kind'])
            self._active(db,Execution(context.owner,context.mode,proposal['campaign']))
            identity=enqueue(db,context.owner,proposal['campaign'],'action',{'action_key':key},context.mode)
            # Explicit retry is allowed only when the provider gate proves nothing was dispatched.
            action=db.execute('SELECT state FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            if action is None or action[0]=='reserved':
                db.execute("UPDATE dispatch_jobs SET state='queued',ready_at=?,error=NULL,claim_token=NULL WHERE owner=? AND id=? AND state IN ('failed','uncertain')",(time.time(),context.owner.lower(),identity))
            return identity

    def proposal(self,key):
        context=owner_context(False)
        with self.connection() as db:
            row=db.execute('SELECT * FROM action_proposals WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            return dict(row) if row else None

    def workflow_preflight(self):
        context=owner_context()
        with self.connection() as db:
            self._job(db,context)
            row=db.execute('SELECT data FROM outreach_policies WHERE owner=?',(context.owner.lower(),)).fetchone()
            if not row:
                raise PolicyDenied('Outreach policy is required before invoking a live agent')
            policy=json.loads(row[0])
            if not all(policy[k]>0 for k in ('hourly_limit','daily_limit','concurrency','daily_units')):
                raise PolicyDenied('Outreach is paused by owner policy')

    def confirmed(self,key,kind,provider_id):
        try:
            row=self.action(key)
            return bool(row and row['kind']==kind and row['state']=='succeeded' and row['provider_id']==provider_id)
        except (SecurityError,sqlite3.Error):
            return False

    def put_artifact(self,data,name):
        context=owner_context()
        if not isinstance(data,bytes) or len(data)>10*1024*1024 or not isinstance(name,str) or len(name)>200 or any(c in name for c in "\r\n/\\"):
            raise PolicyDenied('Invalid approved artifact')
        digest=hashlib.sha256(data).hexdigest()
        with self.connection() as db:
            self._job(db,context)
            db.execute('INSERT OR IGNORE INTO action_artifacts VALUES (?,?,?,?)',(context.owner.lower(),digest,name,data))
        return digest

    def artifact(self,digest):
        context=owner_context()
        with self.connection() as db:
            row=db.execute('SELECT name,data FROM action_artifacts WHERE owner=? AND digest=?',(context.owner.lower(),digest)).fetchone()
            if not row:
                raise PolicyDenied('Approved artifact not found')
            return row[0],bytes(row[1])

    def proposals(self):
        context=owner_context(False)
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM action_proposals WHERE owner=? ORDER BY rowid DESC LIMIT 100',(context.owner.lower(),))]

    def approve(self,key,seconds=900):
        context=owner_context(False)
        if type(seconds) is not int or not 1<=seconds<=3600:
            raise PolicyDenied('Approval expiry must be 1 to 3600 seconds')
        with self.connection() as db:
            row=db.execute('SELECT campaign FROM action_proposals WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            if not row:
                raise PolicyDenied('Action proposal not found')
            self._active(db,Execution(context.owner,context.mode,row[0]))
            db.execute('UPDATE action_proposals SET approved_until=? WHERE owner=? AND id=?',(time.time()+seconds,context.owner.lower(),key))
            self._audit(db,context.owner,key,'approved','Exact payload approved by owner')

    def _checks(self,db,context,proposal):
        self._job(db,context)
        policy=db.execute('SELECT data FROM outreach_policies WHERE owner=?',(context.owner.lower(),)).fetchone()
        if not policy:
            raise PolicyDenied('No owner outreach policy configured')
        policy=json.loads(policy[0]); recipients=json.loads(proposal['recipients'])
        if proposal['approved_until']<=time.time():
            raise PolicyDenied('Exact action approval is missing or expired')
        if not set(recipients)<=set(policy['recipients']):
            raise PolicyDenied('Recipient is not on the owner allowlist')
        if any(db.execute('SELECT 1 FROM suppressions WHERE owner=? AND recipient=?',(context.owner.lower(),r)).fetchone() for r in recipients):
            raise PolicyDenied('Recipient is suppressed or opted out')
        now=datetime.fromtimestamp(time.time(),ZoneInfo(policy['timezone']))
        if now.weekday() not in policy['weekdays'] or not policy['start_hour']<=now.hour<policy['end_hour']:
            raise PolicyDenied('Outside approved contact window')
        return policy,now

    def action(self,key):
        context=owner_context()
        with self.connection() as db:
            row=db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=? AND campaign=?',(context.owner.lower(),key,context.campaign_id)).fetchone()
            return dict(row) if row else None

    def reserve(self,key,quantity=1):
        context=owner_context()
        error=None; result=None
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                proposal=db.execute('SELECT * FROM action_proposals WHERE owner=? AND id=? AND campaign=?',(context.owner.lower(),key,context.campaign_id)).fetchone()
                if proposal is None:
                    raise PolicyDenied('Action proposal missing')
                require_action(proposal['kind'])
                self._job(db,context)
                existing=db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
                if existing:
                    result=dict(existing)
                else:
                    policy,now=self._checks(db,context,proposal)
                    if type(quantity) is not int or not 1<=quantity<=100:
                        raise PolicyDenied('Invalid action quantity')
                    start=now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
                    day=db.execute('SELECT COUNT(*),COALESCE(SUM(units),0) FROM provider_actions WHERE owner=? AND created_at>=?',(context.owner.lower(),start)).fetchone()
                    hour=db.execute('SELECT COUNT(*) FROM provider_actions WHERE owner=? AND created_at>=?',(context.owner.lower(),time.time()-3600)).fetchone()[0]
                    active=db.execute("SELECT COUNT(*) FROM provider_actions WHERE owner=? AND state IN ('reserved','dispatching','initiated','unknown')",(context.owner.lower(),)).fetchone()[0]
                    units=policy['unit_costs'][proposal['kind']]*quantity
                    if hour>=policy['hourly_limit'] or day[0]>=policy['daily_limit'] or day[1]+units>policy['daily_units'] or active>=policy['concurrency']:
                        raise PolicyDenied('Owner rate, budget or concurrency limit reached')
                    db.execute('INSERT INTO provider_actions(owner,id,campaign,job_id,kind,recipients,payload,state,units,quantity,created_at) VALUES (?,?,?,?,?,?,?,\'reserved\',?,?,?)',
                        (context.owner.lower(),key,context.campaign_id,context.job_id,proposal['kind'],proposal['recipients'],proposal['payload'],units,quantity,time.time()))
                    self._audit(db,context.owner,key,'reserved','Budget reserved atomically')
                    result=dict(db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone())
            except SecurityError as exc:
                error=str(exc); self._audit(db,context.owner,key,'denied',error)
        if error:
            raise PolicyDenied(error)
        return result

    def _dispatch_limits(self,db,context,key,policy,now,units):
        start=now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        day=db.execute('SELECT COUNT(*),COALESCE(SUM(units),0) FROM provider_actions WHERE owner=? AND id!=? AND created_at>=?',(context.owner.lower(),key,start)).fetchone()
        hour=db.execute('SELECT COUNT(*) FROM provider_actions WHERE owner=? AND id!=? AND created_at>=?',(context.owner.lower(),key,time.time()-3600)).fetchone()[0]
        active=db.execute("SELECT COUNT(*) FROM provider_actions WHERE owner=? AND id!=? AND state IN ('reserved','dispatching','initiated','unknown')",(context.owner.lower(),key)).fetchone()[0]
        if hour>=policy['hourly_limit'] or day[0]>=policy['daily_limit'] or day[1]+units>policy['daily_units'] or active>=policy['concurrency']:
            raise PolicyDenied('Owner rate, budget or concurrency limit reached at dispatch')

    def begin(self,key):
        context=owner_context()
        error=None
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                proposal=db.execute('SELECT * FROM action_proposals WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
                if proposal is None:
                    raise PolicyDenied('Action proposal missing')
                require_action(proposal['kind'])
                policy,now=self._checks(db,context,proposal)
                row=db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
                if not row or row['state']!='reserved' or row['cancel_requested']:
                    raise ActionPending('Action already dispatched, cancelled or awaiting reconciliation')
                units=policy['unit_costs'][row['kind']]*row['quantity']
                self._dispatch_limits(db,context,key,policy,now,units)
                db.execute("UPDATE provider_actions SET state='dispatching',created_at=?,units=? WHERE owner=? AND id=?",(time.time(),units,context.owner.lower(),key))
                self._audit(db,context.owner,key,'dispatching','Provider request may now be sent once')
            except SecurityError as exc:
                error=str(exc); self._audit(db,context.owner,key,'denied',error)
        if error:
            raise ActionPending(error)

    def check(self,key):
        context=owner_context()
        with self.connection() as db:
            self._job(db,context)
            row=db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            if not row or row['cancel_requested']:
                raise PolicyDenied('Action cancelled')
            proposal=db.execute('SELECT * FROM action_proposals WHERE owner=? AND id=?',(context.owner.lower(),key)).fetchone()
            require_action(row['kind'])
            self._checks(db,context,proposal)

    def fail_reserved(self,key,error):
        context=owner_context()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute("UPDATE provider_actions SET state='failed',result=? WHERE owner=? AND id=? AND campaign=? AND job_id=? AND state='reserved'",
                (canonical({'success':False,'action_key':key,'error':error}),context.owner.lower(),key,context.campaign_id,context.job_id))
            return changed.rowcount == 1

    def record(self,key,state,result=None,provider_id=None):
        context=owner_context()
        if state not in {'initiated','succeeded','failed','unknown'}:
            raise ValueError('Invalid provider action state')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM provider_actions WHERE owner=? AND id=? AND campaign=?',(context.owner.lower(),key,context.campaign_id)).fetchone()
            if row is None or row['state'] in {'reserved','cancelled'}:
                raise PolicyDenied('No dispatched action to record')
            if row['state'] in {'succeeded','failed'}:
                return
            if row['provider_id'] and provider_id and row['provider_id']!=provider_id:
                raise PolicyDenied('Provider identity cannot be replaced')
            db.execute('UPDATE provider_actions SET state=?,provider_id=COALESCE(provider_id,?),result=? WHERE owner=? AND id=?',
                (state,provider_id,canonical(result) if result is not None else row['result'],context.owner.lower(),key))
            if state=='succeeded' and row['kind']=='calendar':
                if not (provider_id or row['provider_id']) or not isinstance(result,dict) or not result.get('success'):
                    raise PolicyDenied('Confirmed Calendar result required')
                db.execute('INSERT OR IGNORE INTO meeting_records VALUES (?,?,?,?,?,?)',
                    (context.owner.lower(),key,row['campaign'],provider_id or row['provider_id'],
                     canonical({'request':json.loads(row['payload']),'receipt':result}),time.time()))
            self._audit(db,context.owner,key,state,'Provider evidence recorded; no resend')
            if state in {'succeeded','failed'}:
                final='completed' if state=='succeeded' else 'failed'
                db.execute("UPDATE dispatch_jobs SET state=?,result=?,error=NULL,lease_until=0 WHERE owner=? AND id=? AND kind='action' AND state='uncertain'",
                    (final,canonical({'success':state=='succeeded','provider_result':result}),context.owner.lower(),row['job_id']))


    def audit(self):
        context=owner_context(False)
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM action_audit WHERE owner=? ORDER BY id DESC LIMIT 200',(context.owner.lower(),))]


def cached_result(row):
    if row['state']=='cancelled':
        return {'status':'cancelled','success':False,'action_key':row['id']}
    if row['result'] and row['state'] in {'succeeded','failed'}:
        return json.loads(row['result'])
    return {'status':'pending_reconciliation','success':False,'action_key':row['id'],
            'provider_id':row['provider_id'],'error':'Provider outcome is unresolved; this action will not be resent'}


def artifact_directory():
    context=owner_context()
    base=Path(os.getenv('OUTREACH_ATTACHMENT_DIR','.runtime/outreach-attachments')).resolve()
    owner=hashlib.sha256(context.owner.lower().encode()).hexdigest()
    campaign=hashlib.sha256(context.campaign_id.encode()).hexdigest()
    path=base/owner/campaign
    if not path.resolve().is_relative_to(base/owner):
        raise PolicyDenied('Artifact directory crosses owner boundary')
    return path
