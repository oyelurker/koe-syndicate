from common.security import require_action, SecurityError
"""
Gmail Service Account Tool - No manual authentication required.
Uses service account with domain-wide delegation to send emails.
Based on working example with attachment support.
"""

import os
import asyncio
import base64
import mimetypes
import logging
from typing import Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.adk.tools import FunctionTool

from sdr.sdr.config import SERVICE_ACCOUNT_FILE, SALES_EMAIL, GMAIL_SCOPES

# Setup logger for this module
logger = logging.getLogger(__name__)

def create_service_account_credentials():
    """
    Creates service account credentials with domain-wide delegation.
    Handles both local development (JSON file) and cloud deployment scenarios.
    
    Returns:
        google.oauth2.service_account.Credentials: Delegated credentials for the sales email
    """
    try:
        logger.info(f"🔑 Setting up service account authentication for {SALES_EMAIL}...")
        logger.info(f"Setting up service account authentication for {SALES_EMAIL}")
        
        # Try to use environment variable for cloud deployment first
        credentials = None
        
        # Check if SERVICE_ACCOUNT_FILE is set (cloud deployment)
        if os.getenv('SERVICE_ACCOUNT_FILE'):
            logger.info("📁 Using SERVICE_ACCOUNT_FILE environment variable...")
            logger.info(f"Using SERVICE_ACCOUNT_FILE: {os.getenv('SERVICE_ACCOUNT_FILE')}")
            credentials = service_account.Credentials.from_service_account_file(
                os.getenv('SERVICE_ACCOUNT_FILE'), scopes=GMAIL_SCOPES
            )
        # Check if service account file exists locally
        elif os.path.exists(SERVICE_ACCOUNT_FILE):
            logger.info(f"📁 Using local service account file: {SERVICE_ACCOUNT_FILE}")
            logger.info(f"Using local service account file: {SERVICE_ACCOUNT_FILE}")
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=GMAIL_SCOPES
            )
        else:
            # Try default cloud credentials (for Cloud Run with service account attached)
            try:
                logger.info("☁️ Attempting to use default Cloud credentials...")
                logger.info("Attempting to use default Cloud credentials")
                from google.auth import default
                credentials, _ = default(scopes=GMAIL_SCOPES)
            except Exception as default_error:
                logger.error(f"Default credentials failed: {default_error}")
                raise FileNotFoundError(
                    f"No service account credentials found. Tried:\n"
                    f"1. SERVICE_ACCOUNT_FILE env var\n"
                    f"2. Local file: {SERVICE_ACCOUNT_FILE}\n"
                    f"3. Default cloud credentials\n"
                    f"Default credentials error: {default_error}"
                )
        
        # Create delegated credentials for the sales email
        if hasattr(credentials, 'with_subject'):
            delegated_credentials = credentials.with_subject(SALES_EMAIL)
            logger.info(f"Created delegated credentials for {SALES_EMAIL}")
        else:
            # For some credential types, we might not need delegation
            delegated_credentials = credentials
            logger.info("Using non-delegated credentials")
        
        logger.info(f"✅ Service account authentication successful for {SALES_EMAIL}")
        logger.info(f"Service account authentication successful for {SALES_EMAIL}")
        return delegated_credentials
        
    except Exception as e:
        logger.error(f"❌ Service account setup failed: {e}")
        logger.error(f"Service account setup failed: {e}", exc_info=True)
        raise

def send_email(to_email: str, subject: str, body: str, attachment_path: Optional[str] = None, *, _attachment=None, _attachment_name=None) -> dict[str, Any]:
    """Exactly approved payload; ambiguous Gmail sends are never replayed."""
    require_action("email")
    from common.execution_store import WorkStore, normalize_email, cached_result, artifact_directory
    import hashlib
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    ledger = WorkStore()
    key = None
    dispatched = False
    try:
        recipient = normalize_email(to_email)
        ledger.require_job()
        if not isinstance(subject,str) or any(c in subject for c in "\r\n") or not isinstance(body,str):
            raise ValueError("Invalid email headers or body")
        attachment = _attachment
        attachment_name = _attachment_name
        if attachment_path:
            from pathlib import Path
            artifact_root=artifact_directory().resolve()
            artifact=Path(attachment_path).resolve()
            if not artifact.is_relative_to(artifact_root):
                raise ValueError("Attachment is outside the approved artifact directory")
            if os.path.getsize(artifact) > 10 * 1024 * 1024:
                raise ValueError("Attachment exceeds the 10 MiB limit")
            with open(artifact,'rb') as source:
                attachment = source.read(10 * 1024 * 1024 + 1)
            attachment_name=os.path.basename(attachment_path)
            if len(attachment)>10 * 1024 * 1024:
                raise ValueError("Attachment exceeds the 10 MiB limit")
        if attachment is not None:
            ledger.put_artifact(attachment,attachment_name)
        sender = normalize_email(SALES_EMAIL)
        payload = {"from":sender,"to":recipient,"subject":subject,"body":body,
            "attachment_sha256":hashlib.sha256(attachment).hexdigest() if attachment is not None else None,
            "attachment_name":attachment_name}
        key = ledger.propose("email",[recipient],payload)
        row = ledger.reserve(key)
        if row["state"] != "reserved":
            return cached_result(row) if row["state"] in {"succeeded","failed"} else reconcile_email(key)
        message = MIMEMultipart() if attachment is not None else MIMEText(body,'plain')
        if attachment is not None:
            message.attach(MIMEText(body,'plain'))
            part = MIMEBase('application','octet-stream')
            part.set_payload(attachment); encoders.encode_base64(part)
            part.add_header('Content-Disposition','attachment',filename=attachment_name)
            message.attach(part)
        message['To'],message['From'],message['Subject'] = recipient,sender,subject
        message['Message-ID'] = '<'+key+'@koe-syndicate.invalid>'
        credentials = create_service_account_credentials()
        service = build('gmail','v1',http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=10)),cache_discovery=False)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')
        ledger.begin(key)
        dispatched = True
        response = service.users().messages().send(userId='me',body={'raw':raw}).execute(num_retries=0)
        if not response.get('id'):
            raise ValueError("Gmail did not confirm a message ID")
        result = {"status":"success","message_id":response['id'],"thread_id":response.get('threadId'),
            "action_key":key,"attachment_included":attachment is not None}
        ledger.record(key,'succeeded',result,response['id'])
        return result
    except Exception as exc:
        result = {"status":"unknown" if dispatched else "failed","action_key":key,
            "error":str(exc) if isinstance(exc,(SecurityError,ValueError)) else "Email provider request failed"}
        if dispatched:
            ledger.record(key,'unknown',result)
        return result


async def send_email_with_attachment(crafted_email: dict[str, Any], attachment_path: Optional[str] = None, tool_context=None) -> dict[str, Any]:
    require_action("email")
    if not isinstance(crafted_email,dict):
        return {"status":"failed","error":"Email payload must contain to, subject and body"}
    # Session-local success flags cannot substitute for the exact durable action key.
    return await asyncio.to_thread(send_email,crafted_email.get('to'),crafted_email.get('subject',''),crafted_email.get('body',''),attachment_path)

send_email_with_attachment_tool = FunctionTool(func=send_email_with_attachment)


def reconcile_email(key):
    from common.execution_store import WorkStore, cached_result
    from google_auth_httplib2 import AuthorizedHttp
    import httplib2
    ledger=WorkStore(); row=ledger.action(key)
    if not row or row['kind']!='email':
        return {'status':'failed','error':'Email action not found'}
    if row['state'] in {'succeeded','failed'}:
        return cached_result(row)
    try:
        service=build('gmail','v1',http=AuthorizedHttp(create_service_account_credentials(),http=httplib2.Http(timeout=10)),cache_discovery=False)
        matches=service.users().messages().list(userId='me',q='in:sent rfc822msgid:'+key+'@koe-syndicate.invalid',maxResults=2).execute(num_retries=0).get('messages',[])
        if len(matches)==1:
            message=service.users().messages().get(userId='me',id=matches[0]['id'],format='metadata',metadataHeaders=['Message-ID']).execute(num_retries=0)
            headers={h['name'].lower():h['value'] for h in message.get('payload',{}).get('headers',[])}
            if 'SENT' in message.get('labelIds',[]) and headers.get('message-id')=='<'+key+'@koe-syndicate.invalid>':
                result={'status':'success','message_id':message['id'],'thread_id':message.get('threadId'),'action_key':key}
                ledger.record(key,'succeeded',result,message['id'])
                return result
    except Exception:
        pass
    return cached_result(row)
