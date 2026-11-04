"""Real competing-process CAS, authoritative views, leases and committed outbox."""
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI, WebSocket

from common.security import Execution, execution
from ui_client import db, main
from ui_client.runtime import PipelineRuntimeMiddleware
from ui_client.store import SCHEMA_VERSION, Store, StoreConflict

A, B = 'owner@example.test', 'second@example.test'


def state(campaign='campaign', label='Fixture', running=False):
    return {**main.empty_pipeline_state(), 'websocket_connections':None, 'session_id':campaign,
            'current_city':label, 'is_running':running,
            'businesses':{'same-id':{'id':'same-id','name':label,'city':label}}}


def disk_state(campaign='campaign', label='Fixture', running=False):
    result = state(campaign,label,running)
    result.pop('websocket_connections')
    return result


@pytest.fixture
def store(tmp_path, monkeypatch):
    result = Store(tmp_path/'shared.db')
    result.initialize()
    monkeypatch.setattr(main,'pipeline_store',result)
    return result


def test_revision_rejects_stale_writer_without_partial_records_or_events(store):
    first = store.save(A,disk_state(),{'type':'seed'})
    assert first['revision'] == 1
    before = store.read_view(A,after=0)
    store.save(A,disk_state(None,'Reset'),{'type':'state_reset'},expected_revision=1)
    with pytest.raises(StoreConflict):
        store.save(A,disk_state(label='Stale callback'),{'type':'business_updated'},expected_revision=1)
    assert store.read_view(A)['revision'] == 2
    assert store.load(A)['session_id'] is None
    assert 'Stale callback' not in str(store.leads(A)) + str(store.events(A))
    assert len(store.events(A)) == len(before['events']) + 1
    # Omitting a revision is create-only, never an unguarded overwrite.
    with pytest.raises(StoreConflict):
        store.save(A,disk_state())


def test_failed_event_transaction_rolls_back_revision_snapshot_and_outbox(store):
    store.save(A,disk_state(running=True),{'type':'process_started'})
    before = store.read_view(A,after=0)
    with pytest.raises(sqlite3.IntegrityError):
        store.save(A,disk_state(label='Must roll back'),{'type':'process_started'},expected_revision=1)
    assert store.read_view(A,after=0) == before
    assert store.leads(A)[0]['name'] == 'Fixture'


@pytest.mark.parametrize('separate_owners',[False,True])
def test_two_os_processes_share_revision_and_owner_boundaries(store,tmp_path,separate_owners):
    script = tmp_path/'writer.py'
    script.write_text('''import json,sys
from ui_client.store import Store,StoreConflict
s=Store(sys.argv[1]); owner=sys.argv[2]; label=sys.argv[3]
v=s.read_view(owner)
print('READY',flush=True)
sys.stdin.readline()
snapshot=v['snapshot'] or {'session_id':'same-campaign','is_running':False,'businesses':{}}
snapshot['current_city']=label
snapshot['businesses']={'same-id':{'id':'same-id','name':label,'city':label}}
try:
 r=s.save(owner,snapshot,{'type':'worker_event','label':label},expected_revision=v['revision'])
 print(json.dumps({'status':'committed','revision':r['revision']}),flush=True)
except StoreConflict:
 print(json.dumps({'status':'conflict'}),flush=True)
''',encoding='utf-8')
    env=dict(os.environ,PYTHONPATH=str(Path.cwd()))
    owners=(A,B if separate_owners else A)
    workers=[subprocess.Popen([sys.executable,'-u',str(script),str(store.path),owner,label],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        for owner,label in zip(owners,('Worker A','Worker B'))]
    try:
        for worker in workers:
            assert worker.stdout.readline().strip() == 'READY'
        for worker in workers:
            worker.stdin.write('go\n'); worker.stdin.flush()
        results=[]
        for worker in workers:
            stdout,stderr=worker.communicate(timeout=25)
            assert worker.returncode == 0,stderr
            results.append(json.loads(stdout))
        statuses=sorted(r['status'] for r in results)
        assert statuses == (['committed','committed'] if separate_owners else ['committed','conflict'])
        if separate_owners:
            assert store.load(A)['current_city'] == 'Worker A'
            assert store.load(B)['current_city'] == 'Worker B'
            assert 'Worker B' not in str(store.read_view(A,after=0))
            assert 'Worker A' not in str(store.read_view(B,after=0))
        else:
            assert store.read_view(A)['revision'] == 1
            assert len(store.events(A)) == 1
            assert len(store.leads(A)) == 1
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill(); worker.communicate(timeout=10)


@pytest.mark.asyncio
async def test_concurrent_http_mutations_get_one_success_one_409_and_fresh_reads(store):
    app=FastAPI()
    app.add_middleware(PipelineRuntimeMiddleware,scope_factory=main.pipeline_scope,flush=main.flush_pipeline)
    entered=0
    both=asyncio.Event()
    @app.post('/replace/{campaign}')
    async def replace(campaign:str):
        nonlocal entered
        main.app_state['session_id']=campaign
        main.app_state['current_city']=campaign
        entered+=1
        if entered==2:
            both.set()
        await both.wait()
        await main.manager.send_update({'type':'replacement'})
        return {'campaign':campaign}
    @app.get('/read')
    async def read():
        return await main.get_status()
    async def trusted(scope,receive,send):
        token=execution.set(Execution(A,'demo'))
        try:
            await app(scope,receive,send)
        finally:
            execution.reset(token)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=trusted),base_url='http://fixture') as client:
        results=await asyncio.gather(client.post('/replace/one'),client.post('/replace/two'))
        assert sorted(r.status_code for r in results)==[200,409]
        assert next(r for r in results if r.status_code==409).json()['code']=='pipeline_conflict'
        main.app_state['session_id']='Uncommitted cache poison'
        response=await client.get('/read')
        assert response.json()['session_id']==store.load(A)['session_id']
        assert response.json()['session_id'] in {'one','two'}
        assert store.read_view(A)['revision']==1
        assert len(store.events(A))==1


@pytest.mark.asyncio
async def test_dirty_response_is_committed_before_200_and_other_operations_reload(store):
    app=FastAPI()
    app.add_middleware(PipelineRuntimeMiddleware,scope_factory=main.pipeline_scope,flush=main.flush_pipeline)
    @app.post('/change')
    async def change():
        main.app_state['current_city']='Committed before response'
        return {'ok':True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        response=await client.post('/change')
    assert response.status_code==200
    assert store.load(A)['current_city']=='Committed before response'
    assert store.read_view(A)['revision']==1
    assert store.events(A)[0]['kind']=='state_changed'


@pytest.mark.asyncio
async def test_reset_committed_by_other_worker_fences_late_discovery(store,monkeypatch):
    store.save(A,disk_state(running=True),{'type':'process_started'})
    started,release=asyncio.Event(),asyncio.Event()
    async def provider(*args,**kwargs):
        started.set(); await release.wait()
        return {'success':True,'businesses':[{'id':'late','name':'Late lead'}]}
    monkeypatch.setattr(main,'call_lead_finder_agent',provider)
    task=asyncio.create_task(main.run_lead_finding_process('Test','campaign'))
    await started.wait()
    other=Store(store.path)
    other.save(A,disk_state(None,'Reset'),{'type':'state_reset'},expected_revision=1)
    release.set()
    await task
    assert store.load(A)['session_id'] is None
    assert store.read_view(A)['revision']==2
    assert 'Late lead' not in str(store.events(A))+str(store.leads(A))


@pytest.mark.asyncio
async def test_socket_reads_other_process_events_without_private_owner_leaks(store,tmp_path):
    script=tmp_path/'remote.py'
    script.write_text('''import sys
from ui_client.store import Store
s=Store(sys.argv[1])
for owner,name in [('second@example.test','Other private lead'),('owner@example.test','Owner lead')]:
 s.save(owner,{'session_id':'same-campaign','businesses':{'same-id':{'id':'same-id','name':name,'city':'Test'}},'is_running':False}, {'type':'business_updated','message':name})
''',encoding='utf-8')
    result=subprocess.run([sys.executable,str(script),str(store.path)],env=dict(os.environ,PYTHONPATH=str(Path.cwd())),capture_output=True,text=True,timeout=25)
    assert result.returncode==0,result.stderr
    ws=Mock(spec=WebSocket); ws.send_text=AsyncMock()
    cursor,revision=await main.deliver_socket_events(ws,0,0)
    messages=[json.loads(c.args[0]) for c in ws.send_text.call_args_list]
    assert revision==1 and cursor==store.read_view(A)['cursor']
    assert any(m.get('message')=='Owner lead' for m in messages)
    assert messages[-1]['businesses'][0]['name']=='Owner lead'
    assert 'Other private lead' not in str(messages)
    ws.send_text.reset_mock()
    assert await main.deliver_socket_events(ws,cursor,revision)==(cursor,revision)
    ws.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_socket_drops_obsolete_campaign_and_drains_bounded_outbox(store):
    store.save(A,disk_state('old','Old'),{'type':'old_event'})
    for revision in range(1,205):
        store.save(A,disk_state('new','New'),{'type':'current_event','number':revision},expected_revision=revision)
    ws=Mock(spec=WebSocket); ws.send_text=AsyncMock()
    cursor,revision=await main.deliver_socket_events(ws,0,0)
    assert cursor < store.read_view(A)['cursor']
    assert revision==0
    cursor,revision=await main.deliver_socket_events(ws,cursor,revision)
    messages=[json.loads(c.args[0]) for c in ws.send_text.call_args_list]
    assert len([m for m in messages if m['type']=='current_event'])==204
    assert not any(m['type']=='old_event' for m in messages)
    assert messages[-1]['type']=='initial_state'
    assert revision==205


def test_live_worker_is_not_interrupted_and_expired_worker_is_fenced(store):
    store.heartbeat('worker-a')
    store.save(A,disk_state(running=True),{'type':'process_started'},worker_id='worker-a')
    other=Store(store.path)
    other.heartbeat('worker-b')
    other.interrupt_incomplete(A)
    assert store.job(A,'discovery:campaign')['state']=='running'
    assert store.load(A)['is_running'] is True
    with store.connection() as connection:
        connection.execute('UPDATE runtime_workers SET expires_at=0 WHERE id=?',('worker-a',))
    with pytest.raises(StoreConflict,match='lease expired'):
        store.heartbeat('worker-a')
    with pytest.raises(StoreConflict,match='lease expired'):
        store.save(A,disk_state(),expected_revision=1,worker_id='worker-a')
    other.interrupt_incomplete(A)
    assert store.job(A,'discovery:campaign')['state']=='interrupted'
    assert store.load(A)['is_running'] is False
    assert store.read_view(A)['revision']==2


def test_v1_migration_preserves_snapshot_and_encrypted_credentials(monkeypatch):
    from tests.offline.test_storage import prepare
    prepare()
    original=Store(db.DB_PATH)
    original.save(A,disk_state())
    with original.connection() as connection:
        tokens=tuple(connection.execute('SELECT access_token,refresh_token,client_secret FROM users').fetchone())
        connection.execute('ALTER TABLE pipeline_snapshots DROP COLUMN revision')
        connection.execute('ALTER TABLE jobs DROP COLUMN worker_id')
        connection.execute('DROP TABLE runtime_workers')
        connection.execute('PRAGMA user_version=1')
    asyncio.run(db.init_db())
    asyncio.run(db.init_db())
    assert original.load(A)==disk_state()
    assert original.read_view(A)['revision']==1
    with original.connection() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0]==SCHEMA_VERSION
        assert tuple(connection.execute('SELECT access_token,refresh_token,client_secret FROM users').fetchone())==tokens
