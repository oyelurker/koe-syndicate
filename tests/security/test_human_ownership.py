"""Approval identifiers must never cross verified owners or campaigns."""
import asyncio
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from google.oauth2.credentials import Credentials

from common.security import Execution, SecurityError, ServiceAuth, execution
from ui_client import db, main, security

A,B='owner@example.test','second@example.test'


@pytest.fixture
def human(settings,offline_network):
    from sdr.sdr.sub_agents.outreach_email_agent.sub_agents.website_creator.tools import human_creation_tool as human
    manager=human.HumanInteractionManager()
    manager._pending_requests.clear(); manager._active_sessions.clear()
    yield human
    manager._pending_requests.clear(); manager._active_sessions.clear()


@pytest.mark.parametrize('context',[None,Execution(A,'demo')])
def test_human_manager_requires_verified_campaign(context,human):
    token=execution.set(context)
    try:
        with pytest.raises(SecurityError,match='owner and campaign'):
            human.HumanInteractionManager().create_request('Private prompt')
    finally:
        execution.reset(token)


def test_same_approval_and_session_ids_are_owner_and_campaign_scoped(monkeypatch,human):
    monkeypatch.setattr(human.uuid,'uuid4',lambda:'same-request')
    manager=human.HumanInteractionManager()
    token=execution.set(Execution(A,'demo','one'))
    try:
        first=manager.create_request('Private A one')
        manager.mark_session_active('same-session')
        execution.set(Execution(A,'demo','two'))
        assert manager.get_request(first) is None
        assert not manager.is_session_active('same-session')
        manager.cancel_request(first)
        second=manager.create_request('Private A two')
        assert second==first
        # A separate configured owner cannot select the first owner's request.
        monkeypatch.setenv('KOE_OWNER_EMAIL',B)
        execution.set(Execution(B,'demo','one'))
        assert manager.get_request(first) is None
        manager.create_request('Private B one')
        manager.update_request(first,'https://fixture.test/b')
        monkeypatch.setenv('KOE_OWNER_EMAIL',A)
        execution.set(Execution(A,'demo','one'))
        assert manager.get_request(first).prompt=='Private A one'
        assert manager.get_request(first).status==human.RequestStatus.PENDING
        assert manager.get_request(first).url_response is None
        assert manager.is_session_active('same-session')
        manager.cleanup_request(first)
        execution.set(Execution(A,'demo','two'))
        assert manager.get_request(second).prompt=='Private A two'
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_real_signed_sdr_approval_rejects_wrong_campaign_and_duplicate(human):
    from sdr import __main__ as server
    manager=human.HumanInteractionManager()
    token=execution.set(Execution(A,'demo','one'))
    try:
        request_id=manager.create_request('Private prompt')
    finally:
        execution.reset(token)
    for campaign,status in [('two',404),('one',200),('one',404)]:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://localhost:8084',
                auth=ServiceAuth('ui-client','sdr',Execution(A,'demo',campaign))) as client:
            response=await client.post('/api/human-input/'+request_id,json={'url':'https://fixture.test/approved'})
            assert response.status_code==status
    token=execution.set(Execution(A,'demo','one'))
    try:
        assert manager.get_request(request_id).url_response=='https://fixture.test/approved'
    finally:
        execution.reset(token)


def test_browser_approval_requires_current_campaign_and_truthful_agent_delivery(monkeypatch,human):
    with TestClient(main.app,base_url='http://localhost:8000') as client:
        async def login():
            uid=await db.upsert_user({'id':A,'email':A},Credentials(token='fixture',refresh_token='fixture',
                token_uri='https://oauth2.googleapis.com/token',client_id='fixture',client_secret='fixture',scopes=[]))
            await db.create_session('approval-session',uid)
        asyncio.run(login())
        client.cookies.set('koe_session',security.signer().dumps('approval-session'))
        headers={'Origin':'http://localhost:3000','X-Koe-CSRF':security.csrf_token('approval-session')}
        main.app_state['session_id']='new'
        main.app_state['human_input_requests']['reused-id']=main.HumanInputRequest(campaign_id='new',
            request_id='reused-id',prompt='New request',type='website',timestamp='fixture')
        store=main.pipeline_store
        store.save(A,main.pipeline_snapshot())
        provider=AsyncMock()
        provider_class=Mock()
        provider_class.return_value.__aenter__=AsyncMock(return_value=provider)
        provider_class.return_value.__aexit__=AsyncMock(return_value=False)
        monkeypatch.setattr(main.httpx,'AsyncClient',provider_class)
        valid={'request_id':'reused-id','campaign_id':'new','response':'https://fixture.test/approved'}
        for body,status in [({**valid,'campaign_id':'old'},409),({**valid,'request_id':'other'},409),
                            ({k:v for k,v in valid.items() if k!='campaign_id'},422)]:
            assert client.post('/api/human-input/reused-id',json=body,headers=headers).status_code==status
        provider_class.assert_not_called()
        provider.post.return_value=httpx.Response(404,json={'error':'wrong replica'})
        response=client.post('/api/human-input/reused-id',json=valid,headers=headers)
        assert response.status_code==503
        assert 'reused-id' in store.load(A)['human_input_requests']
        assert not any(e['kind']=='human_input_response_submitted' for e in store.events(A))
        provider.post.return_value=httpx.Response(200,json={'status':'success'})
        assert client.post('/api/human-input/reused-id',json=valid,headers=headers).status_code==200
        assert 'reused-id' not in store.load(A)['human_input_requests']
        assert store.events(A)[-1]['kind']=='human_input_response_submitted'
