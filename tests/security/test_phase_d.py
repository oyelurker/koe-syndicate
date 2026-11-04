"""Offline acceptance, timezone, booking and persistence recovery regressions."""
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from common.integration_store import IntegrationStore
from common.security import Execution, execution, SecurityError
from ui_client import db, main
from ui_client.store import Store, SCHEMA_VERSION
from ui_client.calendar_routes import free_slots, local_time

OWNER = 'owner@example.test'
MAILBOX = 'sender@example.test'


@pytest.fixture
def inbox():
    store = Store(db.DB_PATH)
    store.initialize()
    snapshot = main.empty_pipeline_state()
    snapshot.pop('websocket_connections')
    snapshot['session_id'] = 'campaign'
    store.save(OWNER, snapshot)
    from gmail_pubsub_listener.gmail_listener_service import GmailPubSubListener
    service = Mock()
    service.users().getProfile().execute.return_value = {'emailAddress': MAILBOX, 'historyId': '10'}
    service.users().messages().list().execute.return_value = {'messages': [{'id': 'm1'}]}
    service.users().history().list().execute.return_value = {'historyId': '20', 'history': []}
    service.users().messages().get().execute.return_value = {
        'id': 'm1', 'threadId': 't1', 'labelIds': ['INBOX'],
        'payload': {'headers': [{'name': 'From', 'value': 'lead@example.test'}]}}
    listener = GmailPubSubListener(service, Mock(), IntegrationStore())
    return listener, service, store


def notification(history='20', mailbox=MAILBOX):
    return json.dumps({'emailAddress': mailbox, 'historyId': history}).encode()


def test_inbox_acceptance_is_atomic_deduplicated_and_restart_safe(inbox):
    listener, service, store = inbox
    assert listener.process_gmail_notification(notification())
    assert IntegrationStore().cursor(MAILBOX) == '10'
    assert listener.process_gmail_notification(notification())
    with store.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM gmail_messages').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM dispatch_jobs').fetchone()[0] == 1
    assert IntegrationStore(db.DB_PATH).cursor(MAILBOX) == '20'
    job = IntegrationStore().jobs(OWNER)[0]
    assert job['kind'] == 'lead_manager'


def test_failed_queue_acceptance_nacks_and_does_not_advance_cursor(inbox, monkeypatch):
    listener, service, store = inbox
    monkeypatch.setattr(listener.store, 'accept', Mock(side_effect=sqlite3.OperationalError('disk full')))
    message = Mock(data=notification())
    listener.message_callback(message)
    message.nack.assert_called_once()
    message.ack.assert_not_called()
    assert listener.store.cursor(MAILBOX) is None
    assert listener.store.jobs(OWNER) == []


def test_failed_enqueue_rolls_back_message_too(inbox, monkeypatch):
    listener, service, store = inbox
    import common.integration_store as module
    monkeypatch.setattr(module, 'enqueue', Mock(side_effect=ValueError('failed enqueue')))
    assert not listener.check_recent_messages()
    with store.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM gmail_messages').fetchone()[0] == 0


def test_full_sync_paginates_and_captures_cursor_before_scan(inbox):
    listener, service, _ = inbox
    service.users().messages().list().execute.side_effect = [
        {'messages': [{'id': 'm1'}], 'nextPageToken': 'next'}, {'messages': [{'id': 'm2'}]}]
    service.users().messages().get().execute.side_effect = [
        {'id': identity, 'labelIds': ['INBOX']} for identity in ['m1', 'm2']]
    assert listener.check_recent_messages()
    assert len(listener.store.jobs(OWNER)) == 2
    calls = service.mock_calls
    profile_index = next(i for i,c in enumerate(calls) if 'getProfile().execute' in str(c))
    list_indices = [i for i,c in enumerate(calls) if 'messages().list().execute' in str(c)]
    assert any(i > profile_index for i in list_indices)


def test_history_uses_saved_cursor_paginates_and_never_uses_notification_as_start(inbox):
    listener, service, _ = inbox
    listener.store.advance(MAILBOX, '10')
    service.users().history().list().execute.side_effect = [
        {'history': [{'messagesAdded': [{'message': {'id': 'm1'}}]}], 'nextPageToken': 'p2', 'historyId': '19'},
        {'history': [{'messagesAdded': [{'message': {'id': 'm1'}}]}], 'historyId': '20'}]
    assert listener.process_gmail_notification(notification())
    assert listener.store.cursor(MAILBOX) == '20'
    actual = [c for c in service.users().history().list.call_args_list if c.kwargs]
    assert all(c.kwargs['startHistoryId'] == '10' for c in actual)
    assert actual[-1].kwargs['pageToken'] == 'p2'
    assert len(listener.store.jobs(OWNER)) == 1


def test_history_failure_does_not_fallback_or_advance(inbox):
    listener, service, _ = inbox
    listener.store.advance(MAILBOX, '10')
    service.users().history().list().execute.side_effect = TimeoutError()
    service.users().getProfile.reset_mock()
    assert not listener.process_gmail_notification(notification())
    service.users().getProfile.assert_not_called()
    assert listener.store.cursor(MAILBOX) == '10'


def test_expired_history_resyncs_and_old_notification_is_ignored(inbox):
    listener, service, _ = inbox
    listener.store.advance(MAILBOX, '5')
    class Expired(Exception):
        resp = SimpleNamespace(status=404)
    service.users().history().list().execute.side_effect = Expired()
    assert listener.process_gmail_notification(notification())
    assert listener.store.cursor(MAILBOX) == '10'
    service.reset_mock()
    assert listener.process_gmail_notification(notification('9'))
    service.users.assert_not_called()


def test_wrong_mailbox_and_noninbox_are_not_dispatched(inbox):
    listener, service, _ = inbox
    assert not listener.process_gmail_notification(notification(mailbox='other@example.test'))
    service.users().messages().get().execute.return_value = {'id': 'm1', 'labelIds': ['SENT']}
    assert listener.check_recent_messages()
    assert listener.store.jobs(OWNER) == []


def test_subscribe_api_and_terminal_failure_propagate(inbox):
    listener, _, _ = inbox
    future = listener.subscriber.subscribe.return_value
    future.result.side_effect = RuntimeError('terminal stream failure')
    with pytest.raises(RuntimeError, match='terminal'):
        listener.start_listening()
    listener.subscriber.subscribe.assert_called_once()
    listener.subscriber.pull.assert_not_called()
    future.cancel.assert_called_once()
    listener.subscriber.close.assert_called_once()


def test_pubsub_start_failure_activates_polling(monkeypatch, inbox):
    import gmail_pubsub_listener.gmail_listener_service as module
    listener, _, _ = inbox
    listener.start_listening = Mock(side_effect=RuntimeError('startup'))
    listener.start_cron_job = Mock()
    listener.stop_cron = Mock()
    listener.stop_cron.wait.return_value = True
    monkeypatch.setattr(module, 'GmailPubSubListener', lambda: listener)
    module.main()
    listener.start_cron_job.assert_called_once()


@pytest.mark.parametrize('value,reason', [
    ('2027-03-14 02:30', 'does not exist'), ('2027-11-07 01:30', 'ambiguous')])
def test_dst_gap_and_overlap_are_rejected(value, reason):
    with pytest.raises(ValueError, match=reason):
        local_time(value, ZoneInfo('America/New_York'))


def test_availability_is_clipped_and_uses_all_busy_intervals():
    service = Mock()
    service.calendars().get().execute.return_value = {'timeZone': 'Asia/Kolkata'}
    service.freebusy().query().execute.return_value = {'calendars': {'primary': {'busy': [
        {'start': '2026-11-04T05:00:00Z', 'end': '2026-11-04T08:00:00Z'},
        {'start': '2026-11-05T03:30:00Z', 'end': '2026-11-05T06:00:00Z'}]}}}
    now = datetime(2026,11,4,10,15,tzinfo=ZoneInfo('Asia/Kolkata'))
    result = free_slots(service, 1, 60, now)
    assert result['available_slots']
    for slot in result['available_slots']:
        start, end = datetime.fromisoformat(slot['start']), datetime.fromisoformat(slot['end'])
        assert now <= start < end <= now.replace(day=5)
        assert not (start.day == 4 and start.hour < 13)


def test_partial_freebusy_error_is_not_reported_available():
    service = Mock()
    service.calendars().get().execute.return_value = {'timeZone': 'UTC'}
    service.freebusy().query().execute.return_value = {'calendars': {'primary': {'errors': [{'reason': 'internalError'}]}}}
    with pytest.raises(ValueError, match='unavailable'):
        free_slots(service, 7)


def test_schema3_upgrade_and_failure_rollback(inbox, monkeypatch):
    _, _, store = inbox
    with store.connection() as connection:
        for table in ('gmail_cursors','gmail_messages','meeting_records','calendar_intervals'):
            connection.execute('DROP TABLE '+table)
        connection.execute('PRAGMA user_version=3')
    import common.integration_store as module
    original = module.create_schema
    def fail(connection):
        original(connection)
        raise ValueError('migration interrupted')
    monkeypatch.setattr(module, 'create_schema', fail)
    with pytest.raises(ValueError, match='interrupted'):
        store.initialize()
    with store.connection() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 3
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='gmail_cursors'").fetchone() is None
    monkeypatch.setattr(module, 'create_schema', original)
    store.initialize()
    with store.connection() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION


def test_unconfirmed_meeting_cannot_be_persisted(inbox):
    token = execution.set(Execution(OWNER, 'demo', 'campaign'))
    try:
        with pytest.raises(SecurityError, match='receipt'):
            IntegrationStore().save_meeting('invented')
        assert IntegrationStore().meetings() == []
    finally:
        execution.reset(token)


@pytest.mark.asyncio
async def test_accepted_message_reaches_actual_job_scoped_email_tool(inbox, monkeypatch):
    listener, service, store = inbox
    assert listener.check_recent_messages()
    store.heartbeat('inbox-worker')
    job = listener.store.claim(OWNER, 'inbox-worker', 'demo')
    token = execution.set(Execution(OWNER, 'demo', 'campaign', job['id'], job['claim_token']))
    try:
        from lead_manager.lead_manager.tools import check_email
        provider = Mock(side_effect=AssertionError('must use accepted message'))
        monkeypatch.setattr(check_email, 'build', provider)
        result = await check_email.check_unread_emails()
        assert result['source'] == 'durable_inbox'
        assert result['emails'][0]['message_id'] == 'm1'
        provider.assert_not_called()
        mutation = await check_email.mark_email_as_read('m1')
        assert mutation['success'] is False  # Demo cannot mutate Gmail labels.
    finally:
        execution.reset(token)


@pytest.fixture
def calendar_job(inbox, monkeypatch):
    listener, _, store = inbox
    listener.check_recent_messages()
    store.heartbeat('calendar-worker')
    job = listener.store.claim(OWNER, 'calendar-worker', 'demo')
    token = execution.set(Execution(OWNER, 'demo', 'campaign', job['id'], job['claim_token']))
    yield listener.store, store, job
    execution.reset(token)


def test_calendar_interval_conflicts_include_unresolved_writes(calendar_job):
    ledger, store, job = calendar_job
    start = datetime(2100,1,1,9,tzinfo=timezone.utc)
    end = datetime(2100,1,1,10,tzinfo=timezone.utc)
    with store.connection() as connection:
        for key in ('a','b'):
            connection.execute("INSERT INTO provider_actions(owner,id,campaign,job_id,kind,payload,state) VALUES (?,?,?,?,?,?,?)",
                               (OWNER,key,'campaign',job['id'],'calendar','{}','reserved'))
    ledger.claim_calendar('a', start, end)
    with store.connection() as connection:
        connection.execute("UPDATE provider_actions SET state='unknown' WHERE id='a'")
    with pytest.raises(SecurityError, match='reserved'):
        ledger.claim_calendar('b', start, end)
    with store.connection() as connection:
        connection.execute("UPDATE provider_actions SET state='failed' WHERE id='a'")
    ledger.claim_calendar('b', start, end)


def test_confirmed_receipt_and_meeting_record_commit_together(calendar_job):
    ledger, store, job = calendar_job
    with store.connection() as connection:
        connection.execute("INSERT INTO provider_actions(owner,id,campaign,job_id,kind,payload,state) VALUES (?,?,?,?,?,?,?)",
                           (OWNER,'confirmed','campaign',job['id'],'calendar','{}','dispatching'))
    ledger.record('confirmed','succeeded',{'success':True,'meeting_id':'event1'},'event1')
    records = IntegrationStore(db.DB_PATH).meetings()
    assert len(records) == 1 and records[0]['provider_id'] == 'event1'
    ledger.save_meeting('confirmed')
    assert len(ledger.meetings()) == 1
    token = execution.set(Execution('other@example.test','demo','campaign'))
    try:
        # Single-owner authentication also protects direct store use.
        with pytest.raises(SecurityError):
            ledger.meetings()
    finally:
        execution.reset(token)


def test_meeting_storage_failure_does_not_commit_success(calendar_job):
    ledger, store, job = calendar_job
    with store.connection() as connection:
        connection.execute("INSERT INTO provider_actions(owner,id,campaign,job_id,kind,payload,state) VALUES (?,?,?,?,?,?,?)",
                           (OWNER,'failing','campaign',job['id'],'calendar','{}','dispatching'))
        connection.execute("CREATE TRIGGER reject_meeting BEFORE INSERT ON meeting_records BEGIN SELECT RAISE(ABORT,'storage unavailable'); END")
    with pytest.raises(sqlite3.IntegrityError):
        ledger.record('failing','succeeded',{'success':True},'event1')
    assert ledger.action('failing')['state'] == 'dispatching'
    with store.connection() as connection:
        connection.execute('DROP TRIGGER reject_meeting')
    ledger.record('failing','succeeded',{'success':True},'event1')
    assert ledger.action('failing')['state'] == 'succeeded'
    assert len(ledger.meetings()) == 1


@pytest.mark.parametrize('variable,value,reason', [
    ('KOE_TOPOLOGY','cloud','one-host'), ('K_SERVICE','fixture-cloud-service','one-host'),
    ('DB_PATH','relative.db','absolute'),
    ('SDR_SERVICE_URL','http://external.example.test','HTTPS'),
    ('SDR_SERVICE_URL','https://user:password@example.test','Invalid')])
def test_unsupported_deployment_configuration_is_rejected(monkeypatch, variable, value, reason):
    from common.preflight import validate_runtime
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv(variable,value)
    with pytest.raises(SecurityError, match=reason):
        validate_runtime()


def test_concurrent_calendar_claims_allow_only_one_interval(calendar_job):
    from concurrent.futures import ThreadPoolExecutor
    ledger, store, job = calendar_job
    context = execution.get()
    start = datetime(2100,1,1,9,tzinfo=timezone.utc)
    end = datetime(2100,1,1,10,tzinfo=timezone.utc)
    with store.connection() as connection:
        for key in ('race-a','race-b'):
            connection.execute("INSERT INTO provider_actions(owner,id,campaign,job_id,kind,payload,state) VALUES (?,?,?,?,?,?,?)",
                               (OWNER,key,'campaign',job['id'],'calendar','{}','reserved'))
    def claim(key):
        token = execution.set(context)
        try:
            IntegrationStore().claim_calendar(key,start,end)
            return True
        except SecurityError:
            return False
        finally:
            execution.reset(token)
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(claim,['race-a','race-b'])) == [False,True]
