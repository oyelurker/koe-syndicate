"""Two real local UI processes sharing SQLite; no external providers or cloud."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from websockets.exceptions import InvalidStatus
from google.oauth2.credentials import Credentials
from websockets.sync.client import connect

from common.security import Execution, ServiceAuth
from ui_client import db, main, security
from ui_client.store import Store

OWNER='owner@example.test'
OTHER='second@example.test'


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        return listener.getsockname()[1]


def test_two_real_ui_workers_share_fresh_state_events_and_reset(tmp_path,monkeypatch):
    async def seed():
        await db.init_db()
        for owner,session in ((OWNER,'worker-session'),(OTHER,'other-session')):
            uid=await db.upsert_user({'id':owner,'email':owner},Credentials(token='fixture-token',
                refresh_token='fixture-refresh',token_uri='https://oauth2.googleapis.com/token',
                client_id='fixture-client',client_secret='fixture-secret',scopes=[]))
            await db.create_session(session,uid)
    asyncio.run(seed())
    store=Store(db.DB_PATH)
    for owner,name in ((OWNER,'Owner private lead'),(OTHER,'Other private lead')):
        snapshot=main.empty_pipeline_state(); snapshot.pop('websocket_connections')
        snapshot.update(session_id='shared-id',current_city='Fixture',businesses={
            'same-id':{'id':'same-id','name':name,'city':'Fixture'}})
        store.save(owner,snapshot)
    ports=[free_port(),free_port()]
    while ports[1]==ports[0]:
        ports[1]=free_port()
    bases=[f'http://127.0.0.1:{port}' for port in ports]
    processes=[]; logs=[]
    try:
        for index,base in enumerate(bases):
            log=(tmp_path/f'worker-{index}.log').open('w',encoding='utf-8'); logs.append(log)
            env=dict(os.environ,DB_PATH=str(db.DB_PATH),KOE_OWNER_EMAIL=OWNER,KOE_MODE='demo',
                ENABLE_LIVE_CALLS='false',ENABLE_LIVE_EMAIL='false',ENABLE_LIVE_CALENDAR='false',
                UI_CLIENT_SERVICE_URL=base)
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','ui_client.main:app',
                '--host','127.0.0.1','--port',str(ports[index]),'--log-level','warning'],
                cwd=Path.cwd(),env=env,stdout=log,stderr=subprocess.STDOUT))
        with httpx.Client(timeout=5,trust_env=False) as client:
            deadline=time.monotonic()+60
            for index,base in enumerate(bases):
                while True:
                    assert processes[index].poll() is None,(tmp_path/f'worker-{index}.log').read_text(encoding='utf-8')[-2500:]
                    try:
                        if client.get(base+'/health').status_code==200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic()<deadline,'UI worker did not become healthy'
                    time.sleep(0.1)
            cookie='koe_session='+security.signer().dumps('worker-session')
            auth={'Cookie':cookie,'Origin':'http://localhost:3000','X-Koe-CSRF':security.csrf_token('worker-session')}
            other_cookie='koe_session='+security.signer().dumps('other-session')
            for base in bases:
                response=client.get(base+'/api/businesses',headers=auth)
                assert response.status_code==200
                assert response.json()['businesses'][0]['name']=='Owner private lead'
                assert 'Other private lead' not in response.text
                assert client.get(base+'/api/businesses',headers={'Cookie':other_cookie}).status_code==401
                assert client.post(base+'/reset',headers={'Cookie':other_cookie}).status_code==401
                assert client.post(base+'/start_lead_finding',headers={'Cookie':other_cookie},data={'city':'Denied'}).status_code==401
            with pytest.raises(InvalidStatus):
                with connect(f'ws://127.0.0.1:{ports[0]}/ws',origin='http://localhost:3000',
                             additional_headers={'Cookie':other_cookie},proxy=None,open_timeout=5):
                    pass
            with connect(f'ws://127.0.0.1:{ports[0]}/ws',origin='http://localhost:3000',
                         additional_headers={'Cookie':cookie},proxy=None,open_timeout=5,close_timeout=2) as ws:
                initial=json.loads(ws.recv(timeout=5))
                assert initial['type']=='initial_state' and initial['campaign_id']=='shared-id'
                # A callback handled by worker 2 must reach a socket on worker 1.
                monkeypatch.setenv('UI_CLIENT_SERVICE_URL',bases[1])
                payload={'agent_type':'sdr','business_id':'remote-lead','status':'engaged','message':'Remote update',
                         'data':{'name':'Cross-worker lead','city':'Fixture'}}
                request=httpx.Request('POST',bases[1]+'/agent_callback',json=payload)
                signed=next(ServiceAuth('sdr','ui-client',Execution(OWNER,'demo','shared-id')).auth_flow(request))
                assert client.post(request.url,content=request.content,headers=dict(signed.headers)).status_code==200
                for _ in range(8):
                    event=json.loads(ws.recv(timeout=5))
                    assert 'Other private lead' not in str(event)
                    if event.get('type')=='business_updated' and event.get('business',{}).get('id')=='remote-lead':
                        break
                else:
                    raise AssertionError('Remote committed callback was not delivered')
                assert client.post(bases[1]+'/reset',headers=auth).status_code==303
                # Worker 1 must read reset state from disk, regardless of its cache.
                assert client.get(bases[0]+'/api/businesses',headers=auth).json()['total']==0
                for _ in range(8):
                    event=json.loads(ws.recv(timeout=5))
                    if event.get('type')=='initial_state' and event.get('campaign_id') is None:
                        assert event['businesses']==[]
                        break
                else:
                    raise AssertionError('Remote reset did not reach the socket')
                before=store.read_view(OWNER)['revision']
                stale=httpx.Request('POST',bases[1]+'/agent_callback',json=payload)
                stale=next(ServiceAuth('sdr','ui-client',Execution(OWNER,'demo','shared-id')).auth_flow(stale))
                assert client.post(stale.url,content=stale.content,headers=dict(stale.headers)).status_code==409
                assert store.read_view(OWNER)['revision']==before
            assert store.load(OTHER)['businesses']['same-id']['name']=='Other private lead'
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=10)
        for log in logs:
            log.close()
