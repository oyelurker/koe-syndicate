"""Phase C dispatch, cancellation, approvals, quotas and provider-boundary proofs."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from common.security import Execution, SecurityError, ServiceAuth, execution, verify_request
from common.execution_store import WorkStore, PolicyDenied, enqueue, normalize_phone
from ui_client import db,main
from ui_client.store import Store, SCHEMA_VERSION as StoreVersion

OWNER='owner@example.test'
PHONE='+15555550100'
EMAIL='fixture@example.test'


@pytest.fixture
def adapters(settings,offline_network):
    phone=importlib.import_module('sdr.sdr.tools.phone_call')
    email=importlib.import_module('sdr.sdr.sub_agents.outreach_email_agent.tools.gmail_service_account_tool')
    calendar=importlib.import_module('ui_client.calendar_routes')
    return phone,email,calendar


@pytest.fixture
def ready(adapters,monkeypatch):
    monkeypatch.setenv('KOE_MODE','live')
    for action in ('CALLS','EMAIL','CALENDAR'):
        monkeypatch.setenv('ENABLE_LIVE_'+action,'true')
    monkeypatch.setenv('TWILIO_ACCOUNT_SID','AC'+'a'*32)
    monkeypatch.setenv('TWILIO_AUTH_TOKEN','t'*32)
    monkeypatch.setenv('MAX_CALL_SECONDS','120')
    store=Store(db.DB_PATH); store.initialize(); store.heartbeat('fixture-worker')
    snapshot=main.empty_pipeline_state(); snapshot.pop('websocket_connections')
    snapshot.update(session_id='campaign',current_city='Fixture')
    store.save(OWNER,snapshot,dispatch={'kind':'sdr','payload':{},'mode':'live'})
    ledger=WorkStore(); claimed=ledger.claim(OWNER,'fixture-worker','live')
    context=Execution(OWNER,'live','campaign',claimed['id'],claimed['claim_token'])
    token=execution.set(context)
    policy={'hourly_limit':10,'daily_limit':20,'concurrency':3,'daily_units':100,
        'timezone':'UTC','start_hour':0,'end_hour':24,'weekdays':list(range(7)),
        'recipients':[PHONE,EMAIL,'friend@example.test'],'unit_costs':{'calls':5,'email':1,'calendar':1}}
    ledger.configure(policy)
    yield ledger,store,context,policy,adapters
    execution.reset(token)


def proposed(ledger,kind='email',payload=None,recipients=None,approved=True):
    payload=payload or {'from':'sender@example.test','to':EMAIL,'subject':'Fixture','body':'Fixture','attachment_sha256':None,'attachment_name':None}
    key=ledger.propose(kind,recipients or [EMAIL],payload)
    if approved:
        ledger.approve(key)
    return key


def call_proposal(ledger):
    return proposed(ledger,'calls',{'number':PHONE,'system_prompt':'fixture','first_message':'hello','max_duration_seconds':120,'agent_id':'fixture-agent','phone_number_id':'fixture-phone'},[PHONE])


def fake_phone(monkeypatch,phone):
    api=SimpleNamespace(twilio=SimpleNamespace(outbound_call=AsyncMock(return_value=SimpleNamespace(success=True,
        conversation_id='conv-fixture',call_sid='CA'+'b'*32))),conversations=SimpleNamespace(get=AsyncMock(
        return_value=SimpleNamespace(status='done',transcript=[SimpleNamespace(role='agent',message='Fixture')]))))
    monkeypatch.setattr(phone,'_init_elevenlabs_client',lambda transport:(Mock(),api))
    monkeypatch.setattr(phone,'_stop_call',AsyncMock(return_value=True))
    return api


def test_missing_policy_and_exact_approval_are_denied_and_audited(ready):
    ledger,store,context,policy,_=ready
    key=proposed(ledger,approved=False)
    with pytest.raises(PolicyDenied,match='approval'):
        ledger.reserve(key)
    ledger.approve(key)
    with ledger.connection() as connection:
        connection.execute('DELETE FROM outreach_policies')
    with pytest.raises(PolicyDenied,match='policy'):
        ledger.reserve(key)
    assert len([r for r in ledger.audit() if r['decision']=='denied'])==2
    assert ledger.action(key) is None


def test_model_payload_recipient_changes_cannot_reuse_approval(ready):
    ledger,*_=ready
    approved=proposed(ledger)
    changed=proposed(ledger,payload={'body':'Changed'},recipients=['friend@example.test'],approved=False)
    assert changed!=approved
    with pytest.raises(PolicyDenied,match='approval'):
        ledger.reserve(changed)


@pytest.mark.parametrize('stage',['reserve','dispatch'])
def test_opt_out_blocks_even_previously_approved_actions(ready,stage):
    ledger,*_=ready; key=proposed(ledger)
    if stage=='dispatch':
        ledger.reserve(key)
    ledger.suppress(EMAIL)
    with pytest.raises(SecurityError,match='suppressed'):
        ledger.reserve(key) if stage=='reserve' else ledger.begin(key)
    assert not ledger.action(key) or ledger.action(key)['state']=='reserved'


def test_contact_window_budget_and_allowlist_are_enforced(ready):
    ledger,_,_,policy,_=ready; key=proposed(ledger)
    policy['recipients']=[PHONE]; ledger.configure(policy)
    with pytest.raises(PolicyDenied,match='allowlist'):
        ledger.reserve(key)
    policy['recipients']=[EMAIL]; policy['daily_units']=0; ledger.configure(policy)
    with pytest.raises(PolicyDenied,match='limit'):
        ledger.reserve(key)
    policy['daily_units']=10
    from datetime import datetime,timezone
    hour=datetime.now(timezone.utc).hour
    policy['start_hour'],policy['end_hour']=(1,2) if hour!=1 else (2,3)
    ledger.configure(policy)
    with pytest.raises(PolicyDenied,match='window'):
        ledger.reserve(key)


def test_quota_reservation_is_atomic_across_two_processes(ready,tmp_path):
    ledger,store,context,policy,_=ready
    policy.update(hourly_limit=1,concurrency=1); ledger.configure(policy)
    keys=[proposed(ledger,payload={'subject':label}) for label in ('one','two')]
    script=tmp_path/'reserve.py'
    script.write_text('''import json,sys
from common.security import Execution,execution
from common.execution_store import WorkStore,PolicyDenied
v=json.loads(sys.stdin.read()); execution.set(Execution(**v['context']))
try:
 WorkStore().reserve(v['key']); print('reserved')
except PolicyDenied:
 print('denied')
''',encoding='utf-8')
    env=dict(os.environ,PYTHONPATH=str(Path.cwd()))
    def reserve(key):
        result=subprocess.run([sys.executable,str(script)],input=json.dumps({'context':context.__dict__,'key':key}),
            env=env,capture_output=True,text=True,timeout=25)
        assert result.returncode==0,result.stderr
        return result.stdout.strip()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve,keys))==['denied','reserved']
    with ledger.connection() as connection:
        assert connection.execute('SELECT COUNT(*),SUM(units) FROM provider_actions').fetchone()[0]==1


def test_reset_cancels_job_reservations_and_approvals_atomically(ready):
    ledger,store,context,_,_=ready; key=proposed(ledger); ledger.reserve(key)
    snapshot=store.read_view(OWNER)
    reset={**snapshot['snapshot'],'session_id':None,'businesses':{}}
    store.save(OWNER,reset,{'type':'state_reset'},expected_revision=snapshot['revision'])
    assert ledger.jobs(OWNER)[0]['state']=='cancelled'
    assert ledger.action(key)['state']=='cancelled'
    with pytest.raises(SecurityError):
        ledger.begin(key)
    assert ledger.proposals()[0]['approved_until']==0


def test_job_cancel_fences_callback_and_signed_job_fields_cannot_be_changed(ready):
    ledger,_,context,_,_=ready
    request=httpx.Request('POST','http://localhost:8000/agent_callback',json={'agent_type':'sdr',
        'business_id':'late','status':'engaged','message':'Late','data':{'name':'Late','city':'Fixture'}})
    request=next(ServiceAuth('sdr','ui-client',context).auth_flow(request))
    with pytest.raises(SecurityError):
        verify_request({**dict(request.headers),'x-koe-job-token':'f'*48},'POST','/agent_callback',request.content,'ui-client',{'sdr'})
    ledger.cancel_job(context.job_id)
    with TestClient(main.app,base_url='http://localhost:8000') as client:
        assert client.post('/agent_callback',content=request.content,headers=dict(request.headers)).status_code==409
    assert not Store(db.DB_PATH).load(OWNER)['businesses']


def test_expired_claim_recovers_reads_but_quarantines_provider_work(ready):
    ledger,store,context,_,_=ready
    with ledger.connection() as connection:
        connection.execute('UPDATE dispatch_jobs SET lease_until=0')
    # Outreach job is not replayed after loss of its worker response.
    assert ledger.claim(OWNER,'fixture-worker','live') is None
    assert ledger.jobs(OWNER)[0]['state']=='uncertain'
    with ledger.connection() as connection:
        read_job=enqueue(connection,OWNER,'campaign','discovery',{'city':'Fixture'},'live')
    first=ledger.claim(OWNER,'fixture-worker','live')
    assert first['id']==read_job and first['attempts']==1
    with ledger.connection() as connection:
        connection.execute('UPDATE dispatch_jobs SET lease_until=0 WHERE id=?',(read_job,))
    recovered=WorkStore().claim(OWNER,'fixture-worker','live')
    assert recovered['id']==read_job and recovered['attempts']==2
    assert recovered['claim_token']!=first['claim_token']


def test_completed_action_is_not_dispatched_twice_and_unknown_is_not_retried(ready):
    ledger,*_=ready; key=proposed(ledger)
    ledger.reserve(key); ledger.begin(key)
    with pytest.raises(SecurityError):
        ledger.begin(key)
    ledger.record(key,'unknown',{'status':'unknown'})
    assert ledger.reserve(key)['state']=='unknown'
    with pytest.raises(SecurityError):
        ledger.begin(key)


@pytest.mark.parametrize('number,expected',[
    ('+1 (555) 555-0100',PHONE),('0091 98765 43210','+919876543210'),
    ('5555550100',None),('+44 20 1234 5678',None),('+15555550100 ext 1',None),
    ('+0001234567890',None),('+911234567890',None),('++15555550100',None)])
def test_supported_phone_normalization(number,expected,monkeypatch):
    monkeypatch.delenv('PHONE_DEFAULT_COUNTRY',raising=False)
    if expected is None:
        with pytest.raises(SecurityError):
            normalize_phone(number)
    else:
        assert normalize_phone(number)==expected


@pytest.mark.asyncio
async def test_phone_uses_async_provider_no_retries_and_replays_durable_receipt(ready,monkeypatch):
    ledger,_,_,_,(phone,_,_)=ready
    api=fake_phone(monkeypatch,phone); key=call_proposal(ledger)
    first=await phone._make_call(PHONE,'fixture','hello',total_timeout=1)
    second=await phone._make_call(PHONE,'fixture','hello',total_timeout=1)
    assert first['status']==second['status']=='done'
    assert api.twilio.outbound_call.await_count==1
    kwargs=api.twilio.outbound_call.call_args.kwargs
    assert kwargs['request_options']['max_retries']==0
    assert kwargs['conversation_initiation_client_data']['conversation_config_override']['conversation']['max_duration_seconds']==120
    assert ledger.action(key)['provider_id']=='conv-fixture'


@pytest.mark.asyncio
async def test_stalled_phone_deadline_does_not_freeze_loop_or_place_duplicate(ready,monkeypatch):
    ledger,_,_,_,(phone,_,_)=ready
    api=fake_phone(monkeypatch,phone); key=call_proposal(ledger)
    async def stalled(**kwargs):
        await asyncio.Event().wait()
    api.twilio.outbound_call.side_effect=stalled
    ticks=0
    async def tick():
        nonlocal ticks
        for _ in range(8):
            ticks+=1; await asyncio.sleep(0.005)
    result,_=await asyncio.gather(phone._make_call(PHONE,'fixture','hello',total_timeout=0.06),tick())
    assert ticks==8 and result['error_category']=='timeout'
    assert ledger.action(key)['state']=='unknown'
    await phone._make_call(PHONE,'fixture','hello',total_timeout=0.06)
    assert api.twilio.outbound_call.await_count==1


@pytest.mark.asyncio
async def test_phone_cancellation_hangs_up_known_call_and_preserves_uncertainty(ready,monkeypatch):
    ledger,_,_,_,(phone,_,_)=ready
    api=fake_phone(monkeypatch,phone); key=call_proposal(ledger)
    started=asyncio.Event()
    async def stall(*args,**kwargs):
        started.set(); await asyncio.Event().wait()
    api.conversations.get.side_effect=stall
    task=asyncio.create_task(phone._make_call(PHONE,'fixture','hello',total_timeout=2))
    await started.wait(); task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    phone._stop_call.assert_awaited_once_with('CA'+'b'*32)
    assert ledger.action(key)['provider_id']=='conv-fixture'
    assert ledger.action(key)['state']=='unknown'
    api.conversations.get.side_effect=None
    assert (await phone.reconcile_call(key))['status']=='done'
    assert api.twilio.outbound_call.await_count==1


def test_email_timeout_reconciles_sent_header_without_resending(ready,monkeypatch):
    ledger,_,_,_,(_,email,_)=ready; key=proposed(ledger)
    service=Mock(); monkeypatch.setattr(email,'create_service_account_credentials',Mock(return_value=Mock()))
    monkeypatch.setattr(email,'build',Mock(return_value=service))
    service.users().messages().send().execute.side_effect=TimeoutError()
    assert email.send_email(EMAIL,'Fixture','Fixture')['status']=='unknown'
    service.users().messages().list().execute.return_value={'messages':[{'id':'m1'}]}
    service.users().messages().get().execute.return_value={'id':'m1','labelIds':['SENT'],'payload':{'headers':[
        {'name':'Message-ID','value':'<'+key+'@koe-syndicate.invalid>'}]}}
    assert email.send_email(EMAIL,'Fixture','Fixture')['status']=='success'
    assert service.users().messages().send.call_count==2  # one fixture setup call, one actual provider attempt
    assert ledger.action(key)['provider_id']=='m1'


def test_arbitrary_attachment_paths_are_rejected_before_provider(ready,monkeypatch,tmp_path):
    _,_,_,_,(_,email,_)=ready
    secret=tmp_path/'private.txt'; secret.write_text('fixture private data')
    provider=Mock(); monkeypatch.setattr(email,'build',provider)
    result=email.send_email(EMAIL,'Fixture','Fixture',str(secret))
    assert result['status']=='failed' and 'outside' in result['error']
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_calendar_timeout_reconciles_deterministic_event_without_second_insert(ready,monkeypatch):
    ledger,_,_,_,(_,_,calendar)=ready
    req=calendar.Meeting(lead_name='Fixture',lead_email=EMAIL,preferred_date='2100-01-04',preferred_time='09:00')
    key=proposed(ledger,'calendar',req.model_dump(mode='json'),[EMAIL])
    service=Mock(); monkeypatch.setattr(calendar,'owner_service',AsyncMock(return_value=service))
    monkeypatch.setattr(calendar,'free_slots',Mock(return_value={'timezone':'UTC','available_slots':[]}))
    service.freebusy().query().execute.return_value={'calendars':{'primary':{'busy':[]}}}
    service.events().insert().execute.side_effect=TimeoutError()
    first=await calendar.meeting(req)
    assert first.status_code==502
    assert service.events().insert.call_count==2
    service.events().get().execute.return_value={'id':key,'extendedProperties':{'private':{'koe_action_key':key}},
        'start':{'dateTime':'2100-01-04T09:00:00+00:00'},'end':{'dateTime':'2100-01-04T10:00:00+00:00'}}
    second=await calendar.meeting(req)
    assert second['success'] is True and second['meeting_id']==key
    assert service.events().insert.call_count==2
    assert ledger.action(key)['state']=='succeeded'


def test_model_claim_of_sent_email_cannot_notify_contacted(ready,monkeypatch):
    from sdr.sdr import callbacks
    provider=Mock(); monkeypatch.setattr(httpx,'Client',provider)
    assert not callbacks.send_sdr_update_to_ui({'id':'fixture','name':'Fixture','city':'Test'},
        {'status':'success','message_id':'invented','crafted_email':{'to':EMAIL}})
    provider.assert_not_called()



def test_outreach_queue_is_json_durable_and_repeated_submit_does_not_duplicate(ready):
    from tests.security.test_durable_dispatch import login
    ledger,store,_,_,_=ready
    with TestClient(main.app,base_url='http://localhost:8000') as client:
        login(client)
        main.app_state['businesses']['fixture-lead']=main.Business(id='fixture-lead',name='Fixture',city='Test',phone=PHONE,email=EMAIL)
        store.save(OWNER,main.pipeline_snapshot(),expected_revision=store.read_view(OWNER)['revision'])
        first=client.post('/send_to_sdr',data={'business_id':'fixture-lead'})
        second=client.post('/send_to_sdr',data={'business_id':'fixture-lead'})
        assert first.status_code==second.status_code==202
        assert first.json()['job_id']==second.json()['job_id']
        with ledger.connection() as connection:
            rows=connection.execute('SELECT payload FROM dispatch_jobs WHERE id=?',(first.json()['job_id'],)).fetchall()
            assert len(rows)==1
            assert isinstance(json.loads(rows[0][0])['business']['created_at'],str)


def test_artifact_bytes_are_owner_scoped_and_bound_to_exact_hash(ready,monkeypatch):
    from common.execution_store import artifact_directory
    ledger,*_=ready
    directory=artifact_directory()
    directory.mkdir(parents=True)
    artifact=directory/'offer.pdf'; artifact.write_bytes(b'fixture PDF bytes')
    digest=ledger.put_artifact(artifact.read_bytes(),'offer.pdf')
    assert ledger.artifact(digest)==('offer.pdf',b'fixture PDF bytes')
    other='second@example.test'; monkeypatch.setenv('KOE_OWNER_EMAIL',other)
    token=execution.set(Execution(other,'live','campaign'))
    try:
        with pytest.raises(SecurityError,match='not found'):
            ledger.artifact(digest)
    finally:
        execution.reset(token)



def test_service_signature_cannot_grant_browser_owner_approval(ready):
    ledger,_,context,_,_=ready
    key=proposed(ledger,approved=False)
    request=httpx.Request('POST','http://localhost:8000/api/outreach/approvals',json={'action_key':key})
    request=next(ServiceAuth('sdr','ui-client',context).auth_flow(request))
    with TestClient(main.app,base_url='http://localhost:8000') as client:
        assert client.post(request.url.path,content=request.content,headers=dict(request.headers)).status_code==401
    assert ledger.proposal(key)['approved_until']==0


def test_owner_policy_and_approval_api_require_csrf_and_never_enable_flags(ready):
    from tests.security.test_durable_dispatch import login
    ledger,_,_,policy,_=ready
    key=proposed(ledger,approved=False)
    with TestClient(main.app,base_url='http://localhost:8000') as client:
        login(client)
        assert client.put('/api/outreach/policy',json={**policy,'enable_live_calls':True}).status_code==422
        assert client.put('/api/outreach/policy',json=policy).status_code==200
        assert client.post('/api/outreach/approvals',json={'action_key':key}).status_code==200
        assert ledger.proposal(key)['approved_until']>0
        assert client.post('/api/outreach/suppressions',json={'recipient':EMAIL}).status_code==200
        assert ledger.audit()[0]['decision']=='suppressed'
        denied=client.post('/api/outreach/approvals',json={'action_key':key},headers={'X-Koe-CSRF':'wrong'})
        assert denied.status_code==403



def test_dispatch_rechecks_budget_after_policy_and_time_window_changes(ready):
    ledger,_,_,policy,_=ready
    policy['daily_limit']=1; ledger.configure(policy)
    old=proposed(ledger,payload={'subject':'Old reservation'})
    ledger.reserve(old)
    with ledger.connection() as connection:
        connection.execute('UPDATE provider_actions SET created_at=0 WHERE id=?',(old,))
    today=proposed(ledger,payload={'subject':'Current reservation'})
    ledger.reserve(today)
    with pytest.raises(SecurityError,match='limit'):
        ledger.begin(old)
    assert ledger.action(old)['state']=='reserved'
    policy['daily_limit']=20; policy['unit_costs']['email']=101
    ledger.configure(policy)
    with pytest.raises(SecurityError,match='limit'):
        ledger.begin(today)


@pytest.mark.asyncio
async def test_approved_action_executes_exact_payload_through_signed_sdr_route(ready,monkeypatch):
    ledger,_,context,_,(phone,_,_)=ready
    server=importlib.import_module('sdr.__main__')
    api=fake_phone(monkeypatch,phone)
    key=call_proposal(ledger)
    ledger.finish_job(context,{'success':True})
    identity=ledger.queue_approved(key)
    claimed=ledger.claim(OWNER,'fixture-worker','live')
    assert claimed['id']==identity and claimed['kind']=='action'
    action_context=Execution(OWNER,'live','campaign',identity,claimed['claim_token'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://localhost:8084',
            auth=ServiceAuth('ui-client','sdr',action_context)) as client:
        first=await client.post('/internal/actions/'+key+'/execute',json={})
        second=await client.post('/internal/actions/'+key+'/execute',json={})
        assert first.status_code==second.status_code==200
        assert first.json()['status']==second.json()['status']=='done'
        assert api.twilio.outbound_call.await_count==1
        assert (await client.post('/internal/actions/'+'f'*64+'/execute',json={})).status_code==403
    assert ledger.finish_job(action_context,{'success':True})=='completed'
    assert ledger.jobs(OWNER)[0]['state']=='completed'



def test_job_cancel_does_not_cancel_unrelated_job_in_same_campaign(ready):
    ledger,_,context,_,_=ready
    with ledger.connection() as connection:
        other=enqueue(connection,OWNER,'campaign','lead_manager',{'query':'Fixture'},'live')
    assert ledger.cancel_job(context.job_id)
    rows={r['id']:r for r in ledger.jobs(OWNER)}
    assert rows[context.job_id]['state']=='cancelled'
    assert rows[other]['state']=='queued'


def test_schema_two_upgrade_is_atomic_and_preserves_encrypted_auth(monkeypatch):
    from tests.offline.test_storage import prepare
    from common import execution_store
    prepare()
    store=Store(db.DB_PATH)
    with store.connection() as connection:
        before=tuple(connection.execute('SELECT access_token,refresh_token,client_secret FROM users').fetchone())
        for table in ('dispatch_jobs','outreach_policies','suppressions','action_proposals','provider_actions','action_artifacts','action_audit'):
            connection.execute('DROP TABLE '+table)
        connection.execute('PRAGMA user_version=2')
    original=execution_store.create_schema
    def fail(connection):
        original(connection)
        raise ValueError('Injected execution migration failure')
    monkeypatch.setattr(execution_store,'create_schema',fail)
    with pytest.raises(ValueError,match='Injected execution'):
        store.initialize()
    with store.connection() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0]==2
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='provider_actions'").fetchone() is None
        assert tuple(connection.execute('SELECT access_token,refresh_token,client_secret FROM users').fetchone())==before
    monkeypatch.setattr(execution_store,'create_schema',original)
    store.initialize()
    with store.connection() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0]==StoreVersion
        assert tuple(connection.execute('SELECT access_token,refresh_token,client_secret FROM users').fetchone())==before



def test_approved_attachment_uses_frozen_bytes_after_source_file_changes(ready,monkeypatch):
    from common.execution_store import artifact_directory
    from email import policy as mail_policy
    from email.parser import BytesParser
    import base64
    ledger,_,_,_,(_,email,_)=ready
    root=artifact_directory(); root.mkdir(parents=True,exist_ok=True)
    path=root/'offer.pdf'; path.write_bytes(b'original fixture artifact')
    service=Mock(); service.users().messages().send().execute.return_value={'id':'attachment-message'}
    monkeypatch.setattr(email,'build',Mock(return_value=service))
    monkeypatch.setattr(email,'create_service_account_credentials',Mock(return_value=Mock()))
    first=email.send_email(EMAIL,'Fixture','Fixture',str(path))
    assert first['status']=='failed'
    key=first['action_key']; ledger.approve(key)
    path.write_bytes(b'changed after approval')
    changed=email.send_email(EMAIL,'Fixture','Fixture',str(path))
    assert changed['status']=='failed' and changed['action_key']!=key
    email.build.assert_not_called()
    payload=json.loads(ledger.proposal(key)['payload'])
    name,content=ledger.artifact(payload['attachment_sha256'])
    result=email.send_email(EMAIL,'Fixture','Fixture',_attachment=content,_attachment_name=name)
    assert result['status']=='success'
    raw=service.users().messages().send.call_args.kwargs['body']['raw']
    message=BytesParser(policy=mail_policy.default).parsebytes(base64.urlsafe_b64decode(raw))
    attachment=next(part for part in message.walk() if part.get_filename()==name)
    assert attachment.get_payload(decode=True)==b'original fixture artifact'



def test_lost_action_job_recovers_committed_receipt_without_provider_replay(ready):
    ledger,_,context,_,_=ready
    key=proposed(ledger)
    ledger.finish_job(context,{'success':True})
    identity=ledger.queue_approved(key)
    job=ledger.claim(OWNER,'fixture-worker','live')
    token=execution.set(Execution(OWNER,'live','campaign',identity,job['claim_token']))
    try:
        ledger.reserve(key); ledger.begin(key)
        ledger.record(key,'succeeded',{'status':'success','message_id':'recorded-message'},'recorded-message')
    finally:
        execution.reset(token)
    with ledger.connection() as connection:
        connection.execute('UPDATE dispatch_jobs SET lease_until=0 WHERE id=?',(identity,))
    assert WorkStore().claim(OWNER,'fixture-worker','live') is None
    recovered=next(row for row in ledger.jobs(OWNER) if row['id']==identity)
    assert recovered['state']=='completed' and recovered['attempts']==1
    assert json.loads(recovered['result'])['provider_result']['message_id']=='recorded-message'



@pytest.mark.asyncio
@pytest.mark.parametrize('state,target',[('ringing','canceled'),('in-progress','completed'),('completed',None)])
async def test_phone_hangup_uses_provider_call_state(ready,monkeypatch,state,target):
    phone=ready[-1][0]
    client=SimpleNamespace(get=AsyncMock(return_value=httpx.Response(200,json={'status':state})),
        post=AsyncMock(return_value=httpx.Response(200,json={'status':target})))
    manager=Mock(); manager.__aenter__=AsyncMock(return_value=client); manager.__aexit__=AsyncMock(return_value=False)
    monkeypatch.setattr(phone.httpx,'AsyncClient',Mock(return_value=manager))
    assert await phone._stop_call('CA'+'b'*32)
    if target:
        assert client.post.call_args.kwargs['data']=={'Status':target}
    else:
        client.post.assert_not_awaited()
