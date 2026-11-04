"""Signed campaign provenance and late-result regressions; no provider calls."""
import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from common.security import (Execution, SecurityError, ServiceAuth, ServiceMiddleware,
                             agent_session_identity, execution, verify_request)
from ui_client import main

OWNER = "owner@example.test"


def signed(path, campaign, body, owner=OWNER, caller="sdr"):
    request = httpx.Request("POST", "http://localhost:8000" + path, json=body)
    return next(ServiceAuth(caller, "ui-client", Execution(owner, "demo", campaign)).auth_flow(request))


def test_campaign_header_cannot_be_changed_or_removed():
    request = signed('/agent_callback', 'campaign-a', {})
    for value in ('campaign-b', ''):
        with pytest.raises(SecurityError, match='signature'):
            verify_request({**dict(request.headers), 'x-koe-campaign': value}, 'POST',
                           '/agent_callback', request.content, 'ui-client', {'sdr'})
    verified = verify_request(dict(request.headers), 'POST', '/agent_callback', request.content, 'ui-client', {'sdr'})
    assert verified.campaign_id == 'campaign-a'


@pytest.mark.parametrize('campaign', [None, 'old-campaign', 'different-campaign'])
def test_callback_without_current_signed_campaign_changes_nothing(campaign):
    with TestClient(main.app, base_url='http://localhost:8000') as client:
        main.app_state['session_id'] = 'current-campaign'
        main.pipeline_store.save(OWNER, main.pipeline_snapshot())
        payload = {'agent_type':'sdr', 'business_id':'late', 'status':'engaged', 'message':'Late update',
                   'data':{'name':'Wrong campaign lead', 'city':'Test'}}
        request = signed('/agent_callback', campaign, payload)
        before = main.pipeline_snapshot()
        response = client.post(request.url.path, content=request.content, headers=dict(request.headers))
        assert response.status_code == 409
        assert main.pipeline_snapshot() == before
        assert main.pipeline_store.events(OWNER) == []


def test_current_callback_then_reset_rejects_freshly_signed_old_work():
    with TestClient(main.app, base_url='http://localhost:8000') as client:
        main.app_state['session_id'] = 'campaign-a'
        main.pipeline_store.save(OWNER, main.pipeline_snapshot())
        payload = {'agent_type':'sdr', 'business_id':'lead', 'status':'engaged', 'message':'Current',
                   'data':{'name':'Fixture', 'city':'Test'}}
        first = signed('/agent_callback', 'campaign-a', payload)
        assert client.post(first.url.path, content=first.content, headers=dict(first.headers)).status_code == 200
        assert main.pipeline_store.load(OWNER)['businesses']['lead']['name'] == 'Fixture'
        main.app_state.update(main.empty_pipeline_state())
        main.pipeline_store.save(OWNER, main.pipeline_snapshot(), expected_revision=main.pipeline_store.read_view(OWNER)["revision"])
        late = signed('/agent_callback', 'campaign-a', payload)
        assert client.post(late.url.path, content=late.content, headers=dict(late.headers)).status_code == 409
        assert main.app_state['businesses'] == {}


def test_stale_human_request_is_not_persisted():
    with TestClient(main.app, base_url='http://localhost:8000') as client:
        main.app_state['session_id'] = 'new-campaign'
        main.pipeline_store.save(OWNER, main.pipeline_snapshot())
        body = {'request_id':'old-request', 'prompt':'Fixture', 'type':'website', 'timestamp':'fixture'}
        request = signed('/api/human-input', 'old-campaign', body)
        assert client.post(request.url.path, content=request.content, headers=dict(request.headers)).status_code == 409
        assert main.app_state['human_input_requests'] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize('replacement', [None, 'new-campaign'])
@pytest.mark.parametrize('result', [{'success':True, 'businesses':[{'id':'late','name':'Late'}]},
                                    {'success':False, 'error':'Late failure'}])
async def test_late_discovery_does_not_modify_or_finish_replacement(monkeypatch, replacement, result):
    started, release = asyncio.Event(), asyncio.Event()
    async def provider(*args, **kwargs):
        started.set()
        await release.wait()
        return result
    publish = AsyncMock()
    monkeypatch.setattr(main, 'call_lead_finder_agent', provider)
    monkeypatch.setattr(main.manager, 'send_update', publish)
    main.app_state.update(session_id='old-campaign', is_running=True)
    token = execution.set(Execution(OWNER, 'demo'))
    try:
        task = asyncio.create_task(main.run_lead_finding_process('Test', 'old-campaign'))
        await started.wait()
        main.app_state.update(main.empty_pipeline_state())
        main.app_state.update(session_id=replacement, is_running=bool(replacement))
        before = main.pipeline_snapshot()
        release.set()
        await task
        assert main.pipeline_snapshot() == before
        publish.assert_not_called()
    finally:
        execution.reset(token)


def test_agent_identity_is_scoped_and_requires_matching_signed_campaign(monkeypatch):
    token = execution.set(Execution(OWNER, 'demo', 'campaign-a'))
    try:
        owner_id, session_a = agent_session_identity('campaign-a', 'task-a')
        assert (owner_id, session_a) == agent_session_identity('campaign-a', 'task-a')
        assert session_a != agent_session_identity('campaign-a', 'task-b')[1]
        with pytest.raises(SecurityError, match='mismatch'):
            agent_session_identity('campaign-b', 'task-a')
        execution.set(Execution(OWNER, 'demo'))
        with pytest.raises(SecurityError, match='signed campaign'):
            agent_session_identity('campaign-a', 'task-a')
        # Configure a separate restricted owner, without opening access to two owners.
        monkeypatch.setenv('KOE_OWNER_EMAIL', 'second@example.test')
        execution.set(Execution('second@example.test', 'demo', 'campaign-a'))
        assert owner_id != agent_session_identity('campaign-a', 'task-a')[0]
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_campaign_survives_real_signed_service_hop():
    app = FastAPI()
    @app.post('/work')
    async def work(request: Request):
        return {'owner':execution.get().owner, 'campaign':execution.get().campaign_id}
    wrapped = ServiceMiddleware(app, 'sdr', {'ui-client'})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wrapped),
          auth=ServiceAuth('ui-client','sdr',Execution(OWNER,'demo','campaign-a'))) as client:
        response = await client.post('http://localhost:8084/work', json={})
    assert response.status_code == 200
    assert response.json() == {'owner':OWNER, 'campaign':'campaign-a'}


@pytest.mark.asyncio
async def test_current_discovery_keeps_campaign_context_and_completes(monkeypatch):
    contexts = []
    async def provider(*args, **kwargs):
        contexts.append(execution.get())
        return {'success':True, 'businesses':[{'id':'current','name':'Current lead'}]}
    async def publish(event):
        contexts.append(execution.get())
    monkeypatch.setattr(main, 'call_lead_finder_agent', provider)
    monkeypatch.setattr(main.manager, 'send_update', publish)
    main.app_state.update(session_id='campaign-a', is_running=True)
    context = Execution(OWNER, 'demo')
    token = execution.set(context)
    try:
        await main.run_lead_finding_process('Test', 'campaign-a')
        assert main.app_state['businesses']['current'].name == 'Current lead'
        assert main.app_state['is_running'] is False
        assert all(c.campaign_id == 'campaign-a' and c.owner == OWNER for c in contexts)
        assert execution.get() == context
    finally:
        execution.reset(token)
