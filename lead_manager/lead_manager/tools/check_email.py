"""
Gmail Email Checking Tool for Lead Manager.
"""

import asyncio
import base64
import logging
from typing import Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp
import httplib2
from google.adk.tools import FunctionTool
from ..config import SERVICE_ACCOUNT_FILE, SALES_EMAIL, GMAIL_SCOPES
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

def extract_message_body(message):
    """Extract text body from Gmail message"""
    body = ""

    def extract_text_from_part(part):
        if part.get('mimeType') == 'text/plain':
            data = part.get('body', {}).get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
        elif part.get('mimeType') == 'text/html':
            data = part.get('body', {}).get('data')
            if data:
                html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                # Simple HTML to text conversion (remove basic tags)
                import re
                text_content = re.sub('<[^<]+?>', '', html_content)
                return text_content
        return ""

    payload = message.get('payload', {})

    # Single part message
    if payload.get('body', {}).get('data'):
        body = extract_text_from_part(payload)

    # Multi-part message
    elif payload.get('parts'):
        for part in payload['parts']:
            if part.get('parts'):  # Nested parts
                for nested_part in part['parts']:
                    text = extract_text_from_part(nested_part)
                    if text:
                        body += text + "\n"
            else:
                text = extract_text_from_part(part)
                if text:
                    body += text + "\n"

    return body.strip()

def extract_email_address(email_string):
    """Extract email address from 'Name <email@domain.com>' format"""
    if '<' in email_string and '>' in email_string:
        return email_string.split('<')[1].split('>')[0]
    return email_string.strip()

def get_thread_details(service, thread_id):
    """Get detailed information about an email thread"""
    try:
        thread = service.users().threads().get(
            userId='me',
            id=thread_id
        ).execute(num_retries=0)

        messages = thread.get('messages', [])
        participants = set()

        for msg in messages:
            headers = msg['payload'].get('headers', [])
            from_header = next((h['value'] for h in headers if h['name'] == 'From'), '')
            to_header = next((h['value'] for h in headers if h['name'] == 'To'), '')

            # Extract email addresses
            if from_header:
                participants.add(extract_email_address(from_header))
            if to_header:
                for email in to_header.split(','):
                    participants.add(extract_email_address(email.strip()))

        return {
            'message_count': len(messages),
            'participants': list(participants)
        }

    except Exception as e:
        logger.warning(f"Error getting thread details: {e}")
        return {'message_count': 1, 'participants': ['Unknown']}

async def check_unread_emails() -> Dict[str, Any]:
    """
    Check unread emails and return structured data.

    Returns:
        Dictionary containing unread emails data
    """
    from common.integration_store import IntegrationStore
    from common.execution_store import WorkStore
    WorkStore().require_job()
    accepted = await asyncio.to_thread(IntegrationStore().job_message)
    if accepted is not None:
        headers = {h['name'].lower(): h['value'] for h in accepted.get('payload', {}).get('headers', [])}
        sender = headers.get('from', '')
        item = {'message_id': accepted['id'], 'thread_id': accepted.get('threadId'),
                'sender': sender, 'sender_email': extract_email_address(sender),
                'subject': headers.get('subject', ''), 'date_received': headers.get('date', ''),
                'body': extract_message_body(accepted)}
        return {'success': True, 'count': 1, 'emails': [item], 'source': 'durable_inbox'}
    return await asyncio.to_thread(_scan_unread_emails)


def _scan_unread_emails():
    try:
        logger.info("🔍 Checking unread emails...")

        # Create credentials with delegation
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=GMAIL_SCOPES
        )
        delegated_creds = credentials.with_subject(SALES_EMAIL)

        # Create Gmail service
        service = build('gmail', 'v1', http=AuthorizedHttp(delegated_creds, http=httplib2.Http(timeout=10)), cache_discovery=False)

        # Get unread messages
        results = service.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=50
        ).execute(num_retries=0)

        messages = results.get('messages', [])

        if not messages:
            logger.info("✅ No unread emails found!")
            return {
                "success": True,
                "count": 0,
                "emails": [],
                "message": "No unread emails found"
            }

        logger.info(f"📧 Found {len(messages)} unread email(s)")

        unread_emails = []

        for i, message in enumerate(messages, 1):
            message_id = message['id']

            # Get detailed message info
            msg = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute(num_retries=0)

            # Extract headers
            headers = msg['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date_hdr = next((h['value'] for h in headers if h['name'] == 'Date'), 'No Date')
            thread_id = msg.get('threadId')

            # Get message body
            body = extract_message_body(msg)

            # Get thread details
            thread_info = get_thread_details(service, thread_id)

            # Convert header date to ISO format for JSON serialization
            try:
                dt = parsedate_to_datetime(date_hdr)
                # isoformat will include timezone offset
                date_received = dt.isoformat()
            except Exception:
                date_received = date_hdr
            # Extract sender email address
            sender_email = extract_email_address(sender)
            email_data = {
                'message_id': message_id,
                'thread_id': thread_id,
                'subject': subject,
                'sender': sender,
                'sender_email': sender_email,
                'date_received': date_received,
                'body': body,
                'preview': body[:200] + '...' if len(body) > 200 else body,
                'thread_message_count': thread_info['message_count'],
                'thread_participants': thread_info['participants']
            }

            unread_emails.append(email_data)

            logger.info(f"📧 Email #{i}: {sender_email} - {subject}")

        return {
            "success": True,
            "count": len(unread_emails),
            "emails": unread_emails,
            "message": f"Successfully retrieved {len(unread_emails)} unread emails"
        }

    except Exception as e:
        logger.error(f"❌ Error checking emails: {e}")
        return {
            "success": False,
            "count": 0,
            "emails": [],
            "error": str(e),
            "message": f"Error checking emails: {str(e)}"
        }

async def mark_email_as_read(email_message_id: str) -> Dict[str, Any]:
    """
    Mark a specific email as read.

    Args:
        email_message_id: The Gmail message ID to mark as read

    Returns:
        Dictionary containing operation result
    """
    from common.security import require_action
    from common.integration_store import IntegrationStore
    try:
        require_action('email')
        accepted = await asyncio.to_thread(IntegrationStore().job_message)
        if accepted is None or accepted['id'] != email_message_id:
            return {'success': False, 'error': 'Message is not bound to this accepted job'}
        return await asyncio.to_thread(_mark_email_as_read, email_message_id)
    except Exception:
        return {'success': False, 'error': 'Email mutation is not authorized'}


def _mark_email_as_read(email_message_id):
    try:
        logger.info(f"📝 Marking email as read: {email_message_id}")

        # Create credentials with delegation
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=GMAIL_SCOPES
        )
        delegated_creds = credentials.with_subject(SALES_EMAIL)

        # Create Gmail service
        service = build('gmail', 'v1', http=AuthorizedHttp(delegated_creds, http=httplib2.Http(timeout=10)), cache_discovery=False)

        # Mark as read by removing UNREAD label
        service.users().messages().modify(
            userId='me',
            id=email_message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute(num_retries=0)

        logger.info(f"✅ Email marked as read: {email_message_id}")
        return {
            "success": True,
            "message_id": email_message_id,
            "message": "Email successfully marked as read"
        }

    except Exception as e:
        logger.error(f"❌ Error marking email as read: {e}")
        return {
            "success": False,
            "message_id": email_message_id,
            "error": str(e),
            "message": f"Error marking email as read: {str(e)}"
        }

# Create the tools
check_email_tool = FunctionTool(func=check_unread_emails)

mark_email_read_tool = FunctionTool(func=mark_email_as_read)
