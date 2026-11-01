"""Owner-scoped Calendar gateway. OAuth tokens never leave the UI service."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from pydantic import BaseModel, Field, ConfigDict

from common.security import execution, require_owner, require_action, SecurityError
from . import db

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
    return await asyncio.to_thread(build, "calendar", "v3", credentials=creds, cache_discovery=False)


def free_slots(service, days, duration=60):
    info = service.calendars().get(calendarId="primary").execute()
    tz = ZoneInfo(info.get("timeZone", "UTC"))
    now = datetime.now(tz)
    end = now + timedelta(days=days)
    result = service.freebusy().query(body={"timeMin": now.isoformat(), "timeMax": end.isoformat(),
                                           "items": [{"id": "primary"}]}).execute()
    calendar = result["calendars"]["primary"]
    if calendar.get("errors"):
        raise ValueError("Calendar availability unavailable")
    busy = [(datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
             datetime.fromisoformat(b["end"].replace("Z", "+00:00"))) for b in calendar.get("busy", [])]
    slots = []
    for day in range(days + 1):
        start = (now + timedelta(days=day)).replace(hour=9, minute=0, second=0, microsecond=0)
        if start.weekday() >= 5:
            continue
        close = start.replace(hour=18)
        while start + timedelta(minutes=duration) <= min(close, end):
            finish = start + timedelta(minutes=duration)
            if start >= now and not any(start < b and finish > a for a, b in busy):
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


@router.post("/meeting")
async def meeting(req: Meeting):
    try:
        require_action("calendar")
        service = await owner_service()
        slots = await asyncio.to_thread(free_slots, service, 30, req.duration_minutes)
        if bool(req.preferred_date) != bool(req.preferred_time):
            raise ValueError("Provide both preferred date and time")
        if req.preferred_date:
            start = datetime.strptime(req.preferred_date + " " + req.preferred_time, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(slots["timezone"]))
        elif slots["available_slots"]:
            start = datetime.fromisoformat(slots["available_slots"][0]["start"])
        else:
            raise ValueError("No available appointment slots")
        end = start + timedelta(minutes=req.duration_minutes)
        if start <= datetime.now(start.tzinfo):
            raise ValueError("Meeting must be in the future")
        def insert():
            # Check just before insertion. Strong scheduling concurrency is P1.
            result = service.freebusy().query(body={"timeMin": start.isoformat(), "timeMax": end.isoformat(), "items": [{"id": "primary"}]}).execute()
            cal = result["calendars"]["primary"]
            if cal.get("errors") or cal.get("busy"):
                raise ValueError("Calendar slot unavailable")
            emails = list(dict.fromkeys([req.lead_email] + req.attendees))
            if any("@" not in email or any(c in email for c in "\r\n") for email in emails):
                raise ValueError("Invalid attendee email")
            require_action("calendar")
            return service.events().insert(calendarId="primary", sendUpdates="all", body={
                "summary": req.meeting_subject or "Sales Discussion - " + req.lead_name,
                "description": req.description or "", "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()}, "attendees": [{"email": email} for email in emails]}).execute()
        event = await asyncio.to_thread(insert)
        return {"success": True, "meeting_id": event["id"], "calendar_link": event.get("htmlLink"),
                "title": event.get("summary"), "start_time": start.isoformat(), "end_time": end.isoformat(),
                "lead_name": req.lead_name, "lead_email": req.lead_email, "attendees": [req.lead_email] + req.attendees}
    except SecurityError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, 403)
    except ValueError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, 400)
    except Exception:
        return JSONResponse({"success": False, "error": "Calendar booking failed"}, 502)
