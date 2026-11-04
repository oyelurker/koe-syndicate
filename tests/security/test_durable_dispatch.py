"""Restart recovery and bounded retries through the actual lifespan consumer."""
import asyncio
import threading
import time
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials
from common.security import Execution,ServiceAuth,execution
from common.execution_store import WorkStore,enqueue
from ui_client import db,main,security
from ui_client.store import Store

OWNER='owner@example.test'


def login(client):
    async def seed():
        uid=await db.upsert_user({'id':OWNER,'email':OWNER},Credentials(token='fixture',refresh_token='fixture',
            token_uri='https://oauth2.googleapis.com/token',client_id='fixture',client_secret='fixture',scopes=[]))
        await db.create_session('durable-session',uid)
    asyncio.run(seed())
    client.cookies.set('koe_session',security.signer().dumps('durable-session'))
    client.headers.update({'Origin':'http://localhost:3000','X-Koe-CSRF':security.csrf_token('durable-session')})


def test_discovery_recovers_same_job_after_lifespan_restart_without_duplicate_leads(monkeypatch):
    started=threading.Event()
    attempts=0
    async def provider(*args,**kwargs):
        nonlocal attempts
        attempts+=1
        if attempts==1:
            started.set()
            await asyncio.Event().wait()
        return {'success':True,'businesses':[{'id':'stable-id','name':'Recovered lead'}]}
    monkeypatch.setattr(main,'call_lead_finder_agent',provider)
    with TestClient(main.app,base_url='http://localhost:8000',follow_redirects=False) as client:
        login(client)
        assert client.post('/start_lead_finding',data={'city':'Fixture'}).status_code==303
        assert started.wait(5),'Durable consumer did not claim the queued job'
        ledger=WorkStore()
        identity=ledger.jobs(OWNER)[0]['id']
        with ledger.connection() as connection:
            row=connection.execute('SELECT * FROM dispatch_jobs WHERE owner=? AND id=?',(OWNER,identity)).fetchone()
            old_context=Execution(OWNER,'demo',row['campaign'],identity,row['claim_token'])
    assert WorkStore().jobs(OWNER)[0]['state']=='queued'
    with TestClient(main.app,base_url='http://localhost:8000') as client:
        client.cookies.set('koe_session',security.signer().dumps('durable-session'))
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            job=client.get('/api/jobs').json()['jobs'][0]
            if job['state']=='completed':
                break
            time.sleep(0.05)
        assert job['id']==identity and job['state']=='completed' and job['attempts']==2
        assert 'claim_token' not in client.get('/api/jobs').text
        businesses=client.get('/api/businesses').json()['businesses']
        assert len(businesses)==1 and businesses[0]['id']=='stable-id'
        request=httpx.Request('POST','http://localhost:8000/agent_callback',json={'agent_type':'sdr',
            'business_id':'stable-id','status':'engaged','message':'Stale task completion'})
        request=next(ServiceAuth('sdr','ui-client',old_context).auth_flow(request))
        assert client.post('/agent_callback',content=request.content,headers=dict(request.headers)).status_code==409
    assert attempts==2


def test_retry_exhaustion_is_bounded_and_releases_running_view():
    store=Store(db.DB_PATH); store.initialize(); store.heartbeat('worker')
    snapshot=main.empty_pipeline_state(); snapshot.pop('websocket_connections')
    snapshot.update(session_id='retry',is_running=True)
    store.save(OWNER,snapshot,dispatch={'kind':'discovery','payload':{'city':'Fixture'},'mode':'demo'})
    ledger=WorkStore()
    for attempt in range(1,4):
        job=ledger.claim(OWNER,'worker','demo')
        assert job and job['attempts']==attempt
        context=Execution(OWNER,'demo','retry',job['id'],job['claim_token'])
        result=ledger.finish_job(context,error='Fixture provider unavailable')
        assert result==('queued' if attempt<3 else 'failed')
        with ledger.connection() as connection:
            connection.execute('UPDATE dispatch_jobs SET ready_at=0')
    assert ledger.claim(OWNER,'worker','demo') is None
    assert ledger.jobs(OWNER)[0]['attempts']==3
    assert store.load(OWNER)['is_running'] is False
