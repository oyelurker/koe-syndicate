"""One-time browser-bound OAuth state with PKCE. No provider secrets in cookies."""
import base64
import hashlib
import hmac
import secrets
import time

from itsdangerous import URLSafeTimedSerializer, BadSignature
from common.security import SecurityError, consume_once, secret


def state_signer():
    return URLSafeTimedSerializer(secret("SESSION_SECRET"), salt="oauth-state-v1")


def start_state(city, niche):
    browser = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    # Derive verifier from a server secret and nonce so it is not exposed in state.
    verifier = hmac.new(secret("SESSION_SECRET").encode(), ("pkce:" + nonce).encode(), hashlib.sha256).hexdigest()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = state_signer().dumps({"nonce": nonce, "browser": hashlib.sha256(browser.encode()).hexdigest(),
                                  "city": city[:100], "niche": niche[:200]})
    return state, browser, challenge


def consume_state(state, browser):
    try:
        data = state_signer().loads(state, max_age=600)
        digest = hashlib.sha256(browser.encode()).hexdigest()
        if not browser or not hmac.compare_digest(data["browser"], digest):
            raise SecurityError("OAuth browser mismatch")
        consume_once("oauth", data["nonce"], time.time() + 600)
        data["verifier"] = hmac.new(secret("SESSION_SECRET").encode(),
                                   ("pkce:" + data["nonce"]).encode(), hashlib.sha256).hexdigest()
        return data
    except (BadSignature, KeyError, TypeError, AttributeError) as exc:
        raise SecurityError("Invalid or expired OAuth state") from exc
