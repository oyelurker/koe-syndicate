"""Calendar tools use authenticated owner-scoped operations, never raw tokens."""
from typing import Optional, List
import httpx
from google.adk.tools import FunctionTool
from common.security import ServiceAuth, service_url, require_action, SecurityError

async def _operation(path, payload):
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("lead-manager", "ui-client"), timeout=30) as client:
            response = await client.post(service_url("ui-client") + "/internal/calendar/" + path, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception:
        return {"success": False, "error": "Owner-scoped Calendar operation failed"}

async def check_calendar_availability(days_ahead: int = 7):
    return await _operation("availability", {"days_ahead": days_ahead})

async def create_meeting_with_lead(
    lead_name: str, lead_email: str, meeting_subject: Optional[str] = None,
    description: Optional[str] = None, duration_minutes: int = 60,
    preferred_date: Optional[str] = None, preferred_time: Optional[str] = None,
    attendees: Optional[List[str]] = None,
):
    try:
        require_action("calendar")
    except SecurityError as exc:
        return {"success": False, "error": str(exc)}
    return await _operation("meeting", {
        "lead_name": lead_name, "lead_email": lead_email, "meeting_subject": meeting_subject,
        "description": description, "duration_minutes": duration_minutes,
        "preferred_date": preferred_date, "preferred_time": preferred_time, "attendees": attendees or [],
    })

check_availability_tool = FunctionTool(func=check_calendar_availability)
create_meeting_tool = FunctionTool(func=create_meeting_with_lead)
