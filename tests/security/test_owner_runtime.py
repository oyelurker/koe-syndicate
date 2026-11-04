"""Isolation below the verified-auth boundary; production stays single-owner."""
import asyncio
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI, WebSocket

from common.security import Execution, SecurityError, execution
from ui_client import main
from ui_client.store import Store

A, B = 'owner@example.test', 'second@example.test'


def enter(owner, campaign=None):
    return execution.set(Execution(owner, 'demo', campaign))


def socket():
    result = Mock(spec=WebSocket)
    result.accept = AsyncMock()
    result.send_text = AsyncMock()
    return result


def test_state_has_no_implicit_owner_or_default_user():
    token = execution.set(None)
    try:
        for operation in (lambda: main.app_state['businesses'], lambda: main.app_state.clear(),
                          lambda: main.app_state.update(session_id='injected'), main.pipeline_snapshot):
            with pytest.raises(SecurityError, match='owner context'):
                operation()
    finally:
        execution.reset(token)


def test_invalid_context_owner_is_rejected():
    token = enter('invalid')
    try:
        with pytest.raises(SecurityError, match='runtime owner'):
            main.app_state['businesses']
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_concurrent_tasks_keep_every_pipeline_field_owned():
    async def owner_work(owner, label):
        token = enter(owner)
        try:
            main.app_state.update(session_id='same-campaign', current_city=label, is_running=True,
                businesses={'same-id':main.Business(id='same-id', name=label, city=label)},
                human_input_requests={'same-request':main.HumanInputRequest(request_id='same-request', prompt=label,
                    type='website', timestamp='fixture')}, lead_scores={'same-id':{'score':label}})
            await asyncio.sleep(0)
            assert main.app_state['current_city'] == label
            assert main.app_state['businesses']['same-id'].name == label
            assert main.app_state['human_input_requests']['same-request'].prompt == label
            assert main.app_state['lead_scores']['same-id']['score'] == label
            return main.pipeline_snapshot()
        finally:
            execution.reset(token)
    first, second = await asyncio.gather(owner_work(A,'Private A'), owner_work(B,'Private B'))
    assert first['businesses']['same-id']['name'] != second['businesses']['same-id']['name']


@pytest.mark.asyncio
async def test_owned_http_views_callbacks_reset_and_persistence(monkeypatch, tmp_path):
    store = Store(tmp_path/'owners.db')
    store.initialize()
    monkeypatch.setattr(main, 'pipeline_store', store)
    # This harness establishes already-verified identities beneath browser/service
    # authentication. Existing P0 tests retain the actual single-owner policy.
    test_app = FastAPI()
    test_app.router.routes.extend(main.app.router.routes)
    async def verified_app(scope, receive, send):
        headers = dict(scope['headers'])
        owner = headers[b'x-test-owner'].decode()
        assert owner in {A, B}
        token = enter(owner, headers.get(b'x-test-campaign',b'').decode() or None)
        try:
            async with main.pipeline_scope():
                await test_app(scope, receive, send)
        finally:
            execution.reset(token)
    for owner, name in ((A,'Private A'),(B,'Private B')):
        token = enter(owner)
        try:
            main.app_state.update(session_id='same-campaign', current_city=name,
                businesses={'same-id':main.Business(id='same-id',name=name,city=name)})
            store.save(owner, main.pipeline_snapshot())
        finally:
            execution.reset(token)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=verified_app),base_url='http://test') as client:
        for owner, name in ((A,'Private A'),(B,'Private B')):
            result = await client.get('/api/businesses', headers={'x-test-owner':owner})
            assert result.json()['businesses'][0]['name'] == name
            payload = {'agent_type':'sdr','business_id':'same-id','status':'engaged','message':name}
            response = await client.post('/agent_callback',json=payload,
                headers={'x-test-owner':owner,'x-test-campaign':'same-campaign'})
            assert response.status_code == 200
            assert store.load(owner)['businesses']['same-id']['notes'] == ['AgentType.SDR: '+name]
        reset = await client.post('/reset', headers={'x-test-owner':A})
        assert reset.status_code == 303
        assert (await client.get('/api/businesses',headers={'x-test-owner':A})).json()['total'] == 0
        assert (await client.get('/api/businesses',headers={'x-test-owner':B})).json()['businesses'][0]['name'] == 'Private B'
        assert store.load(A)['session_id'] is None
        assert store.load(B)['session_id'] == 'same-campaign'
        # Both tenants chose the same IDs, yet neither sees the other's event data.
        assert 'Private B' not in str(store.events(A))
        assert 'Private A' not in str(store.events(B))


@pytest.mark.asyncio
async def test_websocket_broadcast_uses_owner_not_campaign_collision():
    manager = main.ConnectionManager()
    first, second = socket(), socket()
    for owner, ws in ((A, first),(B,second)):
        token = enter(owner)
        try:
            main.app_state['session_id'] = 'same-campaign'
            await manager.connect(ws)
        finally:
            execution.reset(token)
    token = enter(A,'same-campaign')
    try:
        await manager.send_update({'type':'private','message':'Only A'})
        first.send_text.assert_awaited_once()
        assert 'Only A' in first.send_text.call_args.args[0]
        second.send_text.assert_not_awaited()
    finally:
        execution.reset(token)
    token = enter(B,'same-campaign')
    try:
        await manager.send_update({'type':'private','message':'Only B'})
        second.send_text.assert_awaited_once()
        assert 'Only B' in second.send_text.call_args.args[0]
        assert first.send_text.await_count == 1
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_missing_owner_cannot_connect_or_publish():
    persist = AsyncMock()
    manager, ws = main.ConnectionManager(persist=persist), socket()
    token = execution.set(None)
    try:
        with pytest.raises(SecurityError):
            await manager.connect(ws)
        with pytest.raises(SecurityError):
            await manager.send_update({'type':'private'})
        ws.accept.assert_not_awaited()
        persist.assert_not_awaited()
        assert not manager.active_connections
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_reset_while_persisting_drops_old_socket_event():
    started, release = asyncio.Event(), asyncio.Event()
    async def persist(event):
        started.set()
        await release.wait()
    manager = main.ConnectionManager(persist=persist)
    ws = socket()
    token = enter(A,'old')
    try:
        main.app_state['session_id'] = 'old'
        await manager.connect(ws)
        pending = asyncio.create_task(manager.send_update({'type':'old-event'}))
        await started.wait()
        main.app_state['session_id'] = 'new'
        release.set()
        await pending
        ws.send_text.assert_not_awaited()
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_disconnect_during_persistence_does_not_receive_event():
    manager = None
    ws = socket()
    async def persist(event):
        manager.disconnect(ws)
    manager = main.ConnectionManager(persist=persist)
    token = enter(A)
    try:
        await manager.connect(ws)
        await manager.send_update({'type':'event'})
        ws.send_text.assert_not_awaited()
    finally:
        execution.reset(token)
