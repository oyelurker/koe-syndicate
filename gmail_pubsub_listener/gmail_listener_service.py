"""Single-host Gmail ingestion: durable acceptance before Pub/Sub acknowledgement."""
import json
import logging
import os
import threading
from contextlib import contextmanager

from dotenv import load_dotenv
from google.cloud import pubsub_v1
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp
import httplib2

from common.integration_store import IntegrationStore
from common.security import Execution, execution, mode, owner_email

load_dotenv()
logger = logging.getLogger(__name__)
CRON_INTERVAL = 30


class GmailPubSubListener:
    def __init__(self, gmail_service=None, subscriber=None, store=None):
        from common.preflight import validate_runtime
        validate_runtime('gmail-listener')
        self.sales_email = os.environ['SALES_EMAIL'].strip().lower()
        self.project_id = os.getenv('PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
        self.subscription_name = os.getenv('SUBSCRIPTION_NAME', 'gmail-notifications-pull')
        self.subscriber = subscriber
        self.store = store or IntegrationStore()
        self.gmail_service = gmail_service or self._init_gmail_service()
        self.lock = threading.Lock()
        self.stop_cron = threading.Event()
        self.cron_thread = None

    def _init_gmail_service(self):
        creds = service_account.Credentials.from_service_account_file(
            os.getenv('SERVICE_ACCOUNT_FILE', '.secrets/koe-syndicate-service.json'),
            scopes=['https://www.googleapis.com/auth/gmail.readonly']).with_subject(self.sales_email)
        return build('gmail', 'v1', http=AuthorizedHttp(creds, http=httplib2.Http(timeout=10)), cache_discovery=False)

    @contextmanager
    def owner(self):
        token = execution.set(Execution(owner_email(), mode()))
        try:
            yield
        finally:
            execution.reset(token)

    def process_new_message(self, message_id):
        try:
            message = self.gmail_service.users().messages().get(
                userId='me', id=message_id, format='full').execute(num_retries=0)
        except Exception as exc:
            if getattr(getattr(exc, 'resp', None), 'status', None) == 404:
                return True  # Deleted before retrieval; no work remains.
            raise
        labels = set(message.get('labelIds', []))
        if 'INBOX' not in labels or labels.intersection({'SENT', 'DRAFT', 'SPAM', 'TRASH'}):
            return True
        self.store.accept(self.sales_email, message)
        return True

    def _full_sync(self):
        # Capture BEFORE listing: arrivals during the scan are covered by the next history scan.
        profile = self.gmail_service.users().getProfile(userId='me').execute(num_retries=0)
        if profile.get('emailAddress', '').lower() != self.sales_email:
            raise ValueError('Configured Gmail mailbox does not match delegated identity')
        history_id = profile['historyId']
        page = None
        while True:
            result = self.gmail_service.users().messages().list(
                userId='me', labelIds=['INBOX'], maxResults=100, pageToken=page).execute(num_retries=0)
            for message in result.get('messages', []):
                self.process_new_message(message['id'])
            page = result.get('nextPageToken')
            if not page:
                break
        self.store.advance(self.sales_email, history_id)

    def _sync(self):
        cursor = self.store.cursor(self.sales_email)
        if not cursor:
            return self._full_sync()
        page = None
        latest = cursor
        while True:
            try:
                result = self.gmail_service.users().history().list(
                    userId='me', startHistoryId=cursor, historyTypes=['messageAdded'],
                    labelId='INBOX', maxResults=100, pageToken=page).execute(num_retries=0)
            except Exception as exc:
                if getattr(getattr(exc, 'resp', None), 'status', None) == 404:
                    return self._full_sync()
                raise
            for change in result.get('history', []):
                for addition in change.get('messagesAdded', []):
                    self.process_new_message(addition['message']['id'])
            latest = result.get('historyId', latest)
            page = result.get('nextPageToken')
            if not page:
                break
        self.store.advance(self.sales_email, latest)

    def check_recent_messages(self):
        try:
            with self.lock, self.owner():
                self._sync()
            return True
        except Exception:
            logger.exception('Mailbox scan failed; cursor retained for retry')
            return False

    def process_gmail_notification(self, notification_data):
        try:
            notification = json.loads(notification_data)
            if notification.get('emailAddress', '').lower() != self.sales_email:
                return False
            incoming = str(notification['historyId'])
            if not incoming.isdigit():
                return False
            with self.lock, self.owner():
                cursor = self.store.cursor(self.sales_email)
                if cursor and int(incoming) <= int(cursor):
                    return True
                self._sync()
            return True
        except Exception:
            logger.exception('Notification acceptance failed; message will be retried')
            return False

    def message_callback(self, message):
        if self.process_gmail_notification(message.data):
            message.ack()
        else:
            message.nack()

    def start_listening(self):
        # Startup and terminal stream failures propagate to the polling fallback.
        subscriber = self.subscriber or pubsub_v1.SubscriberClient()
        self.subscriber = subscriber
        future = None
        try:
            path = subscriber.subscription_path(self.project_id, self.subscription_name)
            future = subscriber.subscribe(path, callback=self.message_callback,
                flow_control=pubsub_v1.types.FlowControl(max_messages=1), await_callbacks_on_shutdown=True)
            future.result()
            raise RuntimeError("Pub/Sub stream ended; polling is required")
        finally:
            if future is not None:
                future.cancel()
            subscriber.close()

    def start_cron_job(self):
        if self.cron_thread and self.cron_thread.is_alive():
            return
        self.stop_cron.clear()
        def poll():
            while not self.stop_cron.is_set():
                self.check_recent_messages()
                self.stop_cron.wait(CRON_INTERVAL)
        self.cron_thread = threading.Thread(target=poll, daemon=True)
        self.cron_thread.start()

    def stop_cron_job(self):
        self.stop_cron.set()
        if self.cron_thread:
            self.cron_thread.join(timeout=15)


def main():
    logging.basicConfig(level=logging.INFO)
    listener = GmailPubSubListener()
    try:
        listener.start_listening()
    except KeyboardInterrupt:
        return
    except Exception:
        logger.exception('Pub/Sub unavailable; switching to durable polling')
        listener.start_cron_job()
        try:
            while not listener.stop_cron.wait(1):
                pass
        except KeyboardInterrupt:
            listener.stop_cron_job()


if __name__ == '__main__':
    main()
