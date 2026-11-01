import asyncio
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google.oauth2.credentials import Credentials

from common.security import SecurityError, mode, require_owner
from . import db, oauth, security

router = APIRouter(prefix="/auth", tags=["Auth"])
SCOPES = ["https://www.googleapis.com/auth/calendar.events",
          "https://www.googleapis.com/auth/calendar.readonly",
          "https://www.googleapis.com/auth/userinfo.email", "openid"]


@router.get("/google")
async def login_google(city: str = "", niche: str = ""):
    try:
        security.validate_config()
        client_id = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
        if not os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"):
            raise SecurityError("OAuth unavailable")
        state, browser, challenge = oauth.start_state(city, niche)
    except (SecurityError, KeyError):
        return JSONResponse({"error": "Secure OAuth configuration is incomplete"}, 503)
    params = {"client_id": client_id, "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"],
              "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
              "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
    response = RedirectResponse("https://accounts.google.com/o/oauth2/auth?" + urlencode(params))
    response.set_cookie("koe_oauth_browser", browser, max_age=600, httponly=True,
                        secure=security.secure_cookies(), samesite="lax", path="/auth")
    return response


@router.get("/google/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    try:
        data = await asyncio.to_thread(oauth.consume_state, state, request.cookies.get("koe_oauth_browser", ""))
        if not code or error:
            raise SecurityError("OAuth authorization was not completed")
    except SecurityError:
        return JSONResponse({"error": "Invalid, expired or already used OAuth request"}, 400)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            result = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
                "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"],
                "grant_type": "authorization_code", "code_verifier": data["verifier"]})
            result.raise_for_status()
            tokens = result.json()
            profile = await client.get("https://www.googleapis.com/oauth2/v2/userinfo",
                                       headers={"Authorization": "Bearer " + tokens["access_token"]})
            profile.raise_for_status()
            user = profile.json()
        if user.get("verified_email") is not True:
            raise SecurityError("Verified email required")
        require_owner(user.get("email", ""))
        creds = Credentials(token=tokens["access_token"], refresh_token=tokens.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token", client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"], scopes=SCOPES)
        user_id = await db.upsert_user(user, creds)
        session = secrets.token_urlsafe(32)
        await db.create_session(session, user_id)
        query = urlencode({"auth": "success", "city": data["city"], "niche": data["niche"]})
        response = RedirectResponse(os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000").rstrip("/") + "/dashboard?" + query)
        response.set_cookie("koe_session", security.signer().dumps(session), httponly=True,
            secure=security.secure_cookies(), samesite="none" if security.secure_cookies() else "lax",
            max_age=30 * 86400)
    except SecurityError:
        response = JSONResponse({"error": "This account is not permitted on this instance"}, 403)
    except Exception:
        response = JSONResponse({"error": "Google connection failed; please start again"}, 502)
    response.delete_cookie("koe_oauth_browser", path="/auth", secure=security.secure_cookies(), samesite="lax")
    return response


@router.get("/status")
async def status(request: Request):
    session_id, user = await security.session_user(request.scope)
    if not user:
        return {"connected": False}
    return JSONResponse({"connected": True, "email": user["email"], "name": user["name"],
        "picture": user["picture"], "csrf_token": security.csrf_token(session_id), "mode": mode()},
        headers={"Cache-Control": "no-store"})


@router.post("/schedule-meeting")
async def legacy_demo_booking():
    # This endpoint only supported synthetic leads. Live booking goes through
    # the owner-scoped Calendar workflow, never through a frontend demo runner.
    return JSONResponse({"error": "Demo Calendar writes have been removed"}, 410)


@router.post("/disconnect")
async def disconnect(request: Request):
    await db.disconnect_user(request.state.user["id"])
    response = JSONResponse({"status": "disconnected"})
    response.delete_cookie("koe_session", secure=security.secure_cookies(),
                           samesite="none" if security.secure_cookies() else "lax")
    return response
