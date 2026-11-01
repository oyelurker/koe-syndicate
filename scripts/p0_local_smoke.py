"""Start the real UI process in demo mode and probe it over loopback HTTP."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import httpx

root = Path(__file__).resolve().parents[1]
with socket.socket() as reservation:
    reservation.bind(("127.0.0.1", 0))
    port = reservation.getsockname()[1]
base = f"http://127.0.0.1:{port}"
with tempfile.TemporaryDirectory(prefix="koe-p0-") as temporary:
    env = dict(os.environ, APP_ENV="development", KOE_MODE="demo",
               ENABLE_LIVE_CALLS="false", ENABLE_LIVE_EMAIL="false", ENABLE_LIVE_CALENDAR="false",
               DB_PATH=str(Path(temporary) / "tokens.db"), SECURITY_DB_PATH=str(Path(temporary) / "nonces.db"),
               UI_CLIENT_SERVICE_URL=base, NEXT_PUBLIC_FRONTEND_URL="http://localhost:3000")
    with (root / ".runtime/p0-local-smoke.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "ui_client.main:app", "--host", "127.0.0.1", "--port", str(port)],
                                   cwd=root, env=env, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 45
            with httpx.Client(base_url=base, timeout=2, follow_redirects=False, trust_env=False) as client:
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("UI startup failed; see .runtime/p0-local-smoke.log")
                    try:
                        response = client.get("/health")
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("UI startup timed out")
                    time.sleep(0.2)
                assert client.get("/api/businesses").status_code == 401
                assert client.post("/send_to_sdr", data={"business_id": "fake"}).status_code == 401
                assert client.post("/agent_callback", json={}).status_code == 401
                assert client.get("/debug/static").status_code == 404
                assert client.get("/auth/status").json() == {"connected": False}
                login = client.get("/auth/google")
                assert login.status_code == 307
                assert login.headers["location"].startswith("https://accounts.google.com/")
                assert "koe_oauth_browser" in client.cookies
                print("PASS real UI startup, anonymous route denial, callback denial, debug removal, OAuth initiation")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
