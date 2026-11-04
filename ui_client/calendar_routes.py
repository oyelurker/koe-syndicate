"""Owner-scoped Calendar gateway. OAuth tokens never leave the UI service."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from google_auth_httplib2 import AuthorizedHttp
import httplib2
from pydantic import BaseModel, Field, ConfigDict

from common.security import execution, require_owner, require_action, SecurityError
from . import db
from common.execution_store import WorkStore, normalize_email, cached_result

router = APIRouter(prefix="/internal/calendar")


class Availability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days_ahead: int = Field(7, ge=1, le=30)


class Meeting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_name: str = Field(min_length=1, max_length=200)
    lead_email: str = Field(min_length=3, max_length=254)
    meeting_subject: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=10000)
    duration_minutes: int = Field(60, ge=15, le=240)
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    attendees: list[str] = Field(default_factory=list, max_length=20)


async def owner_service():
    context = execution.get()
    if context is None:
        raise SecurityError("Missing Calendar owner")
    require_owner(context.owner)
    creds = await db.credentials_for_owner(context.owner)
    if creds is None:
        raise SecurityError("Calendar owner is not connected")
    return await asyncio.to_thread(build, "calendar", "v3", http=AuthorizedHttp(creds, http=httplib2.Http(timeout=10)), cache_discovery=False)


def local_time(value, tz):
    naive = datetime.strptime(value, "%Y-%m-%d %H:%M")
    candidates = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=tz, fold=fold)
        if aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == naive:
            candidates.append(aware)
    if not candidates:
        raise ValueError("Meeting time does not exist in the Calendar timezone")
    if len({c.utcoffset() for c in candidates}) > 1:
        raise ValueError("Meeting time is ambiguous in the Calendar timezone; choose another time")
    return candidates[0]


def free_slots(service, days, duration=60, now=None):
    info = service.calendars().get(calendarId="primary").execute(num_retries=0)
    tz = ZoneInfo(info.get("timeZone", "UTC"))
    now = now.astimezone(tz) if now is not None else datetime.now(tz)
    end = now + timedelta(days=days)
    result = service.freebusy().query(body={"timeMin": now.isoformat(), "timeMax": end.isoformat(),
                                           "items": [{"id": "primary"}]}).execute(num_retries=0)
    calendar = result["calendars"]["primary"]
    if calendar.get("errors"):
        raise ValueError("Calendar availability unavailable")
    busy = [(datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
             datetime.fromisoformat(b["end"].replace("Z", "+00:00"))) for b in calendar.get("busy", [])]
    busy = [(a.astimezone(timezone.utc), b.astimezone(timezone.utc)) for a,b in busy]
    slots = []
    for day in range(days + 1):
        start = (now + timedelta(days=day)).replace(hour=9, minute=0, second=0, microsecond=0)
        if start.weekday() >= 5:
            continue
        close = start.replace(hour=18)
        while start + timedelta(minutes=duration) <= min(close, end):
            try:
                local_time(start.strftime('%Y-%m-%d %H:%M'), tz)
            except ValueError:
                start += timedelta(minutes=30)
                continue
            finish = (start.astimezone(timezone.utc) + timedelta(minutes=duration)).astimezone(tz)
            if start.timestamp() >= now.timestamp() and finish.timestamp() <= end.timestamp() and finish.timestamp() <= close.timestamp() and not any(start.astimezone(timezone.utc) < b and finish.astimezone(timezone.utc) > a for a, b in busy):
                slots.append({"start": start.isoformat(), "end": finish.isoformat()})
            start += timedelta(minutes=30)
    return {"success": True, "timezone": str(tz), "available_slots": slots[:20]}


@router.post("/availability")
async def availability(req: Availability):
    try:
        service = await owner_service()
        return await asyncio.to_thread(free_slots, service, req.days_ahead)
    except SecurityError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, 403)
    except Exception:
        return JSONResponse({"success": False, "error": "Calendar availability failed"}, 502)


def confirmed_meeting(event, req, key):
    return {"success":True,"meeting_id":event["id"],"calendar_link":event.get("htmlLink"),
        "title":event.get("summary"),"start_time":event.get("start",{}).get("dateTime"),
        "end_time":event.get("end",{}).get("dateTime"),"lead_name":req.lead_name,
        "lead_email":req.lead_email,"attendees":[req.lead_email]+req.attendees,"action_key":key}


async def reconcile_meeting(key):
    ledger=WorkStore(); row=await asyncio.to_thread(ledger.action,key)
    if not row or row["kind"]!="calendar":
        return {"success":False,"error":"Calendar action not found"}
    if row["state"] in {"succeeded","failed"}:
        if row["state"] == "succeeded":
            from common.integration_store import IntegrationStore
            await asyncio.to_thread(IntegrationStore().save_meeting, key)
        return cached_result(row)
    try:
        service=await owner_service()
        event=await asyncio.wait_for(asyncio.to_thread(lambda: service.events().get(calendarId="primary",eventId=key).execute(num_retries=0)),15)
        if event.get("status") == "cancelled" or event.get("extendedProperties",{}).get("private",{}).get("koe_action_key")!=key:
            return {"success":False,"error":"Provider evidence does not match this action"}
        req=Meeting.model_validate(json.loads(row["payload"]))
        result=confirmed_meeting(event,req,key)
        await asyncio.to_thread(ledger.record,key,"succeeded",result,event["id"])
        return result
    except Exception:
        return cached_result(row)


@router.post("/meeting")
async def meeting(req: Meeting):
    key=None; dispatched=False; ledger=WorkStore()
    try:
        require_action("calendar")
        emails=sorted(set(normalize_email(email) for email in [req.lead_email]+req.attendees))
        req=req.model_copy(update={"lead_email":normalize_email(req.lead_email),"attendees":sorted(set(normalize_email(e) for e in req.attendees))})
        if not req.preferred_date or not req.preferred_time:
            raise ValueError("An explicit approved meeting date and time are required")
        key=await asyncio.to_thread(ledger.propose,"calendar",emails,req.model_dump(mode="json"))
        row=await asyncio.to_thread(ledger.reserve,key,len(emails))
        if row["state"]!="reserved":
            return await reconcile_meeting(key)
        service=await owner_service()
        slots=await asyncio.to_thread(free_slots,service,30,req.duration_minutes)
        start=local_time(req.preferred_date+" "+req.preferred_time,ZoneInfo(slots["timezone"]))
        end=(start.astimezone(timezone.utc)+timedelta(minutes=req.duration_minutes)).astimezone(start.tzinfo)
        if start<=datetime.now(start.tzinfo):
            raise ValueError("Meeting must be in the future")
        def insert():
            nonlocal dispatched
            busy=service.freebusy().query(body={"timeMin":start.isoformat(),"timeMax":end.isoformat(),"items":[{"id":"primary"}]}).execute(num_retries=0)["calendars"]["primary"]
            if busy.get("errors") or busy.get("busy"):
                raise ValueError("Calendar slot unavailable")
            from common.integration_store import IntegrationStore
            IntegrationStore().claim_calendar(key,start,end)
            ledger.begin(key)
            dispatched=True
            event=service.events().insert(calendarId="primary",sendUpdates="all",body={
                "id":key,"summary":req.meeting_subject or "Sales Discussion - "+req.lead_name,
                "description":req.description or "","start":{"dateTime":start.isoformat()},
                "end":{"dateTime":end.isoformat()},"attendees":[{"email":email} for email in emails],
                "extendedProperties":{"private":{"koe_action_key":key}}}).execute(num_retries=0)
            result=confirmed_meeting(event,req,key)
            ledger.record(key,"succeeded",result,event["id"])
            return result
        return await asyncio.wait_for(asyncio.to_thread(insert),20)
    except SecurityError as exc:
        if key and not dispatched:
            await asyncio.to_thread(ledger.fail_reserved,key,str(exc))
        return JSONResponse({"success":False,"error":str(exc),"action_key":key},403)
    except ValueError as exc:
        if key and not dispatched:
            await asyncio.to_thread(ledger.fail_reserved,key,str(exc))
        return JSONResponse({"success":False,"error":str(exc),"action_key":key},400)
    except Exception:
        if key:
            stopped=await asyncio.to_thread(ledger.fail_reserved,key,'Calendar preflight failed; no event was sent')
            if stopped:
                return JSONResponse({'success':False,'action_key':key,'error':'Calendar preflight failed; no event was sent'},502)
            row=await asyncio.to_thread(ledger.action,key)
            if row and row['state'] in {'succeeded','failed'}:
                return cached_result(row)
        result={"success":False,"error":"Calendar outcome is uncertain; reconcile before retrying","action_key":key}
        if key:
            await asyncio.to_thread(ledger.record,key,"unknown",result)
        return JSONResponse(result,502)
