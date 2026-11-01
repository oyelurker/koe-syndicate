# P0 security configuration and verification

This release is restricted to one explicitly configured Google account. It is not a multi-tenant release. The allowed owner's address belongs in environment configuration, not source code. Local `.env` has been configured from the owner's answer in chat; no secrets are committed.

## Operating modes

- `KOE_MODE=demo` is the default. Either legacy mock flag also forces demo policy.
- All of `ENABLE_LIVE_CALLS`, `ENABLE_LIVE_EMAIL`, and `ENABLE_LIVE_CALENDAR` default to false. A provider write requires live mode, the matching flag, and a verified execution owner.
- Simulated frontend workflows never create Calendar events. The legacy demo booking endpoint returns 410.
- Internal agents use signed requests with a caller identity, destination, timestamp, nonce, body hash, owner and execution mode. An identity authorized for one route cannot masquerade as another agent on callbacks.
- Browser data/action routes require a signed, unexpired session belonging to `KOE_OWNER_EMAIL`. Mutations additionally require an allowed Origin and a session-bound CSRF token. WebSockets require both the session and allowed Origin.

## Required configuration

| Variable | Requirement |
| --- | --- |
| `KOE_OWNER_EMAIL` | Exactly one verified Google email; all others rejected |
| `SESSION_SECRET` | Random secret, at least 32 characters; no development fallback |
| `TOKEN_ENCRYPTION_KEY` | Stable Fernet key kept outside the database; protect and back it up securely |
| `SERVICE_AUTH_KEYS` | JSON mapping service identities to independent random secrets of at least 32 characters |
| `APP_ENV` | Defaults to production; development HTTP is permitted only on loopback URLs |
| `NEXT_PUBLIC_FRONTEND_URL` | Exact frontend origin, HTTPS in production |
| `UI_CLIENT_SERVICE_URL` | Backend service URL; also used for the legacy same-origin UI |
| `GOOGLE_OAUTH_REDIRECT_URI` | Registered callback URL, HTTPS in production |
| `SECURITY_DB_PATH` | Writable, persistent replay-nonce database shared by workers on the same host |
| `DB_PATH` | Persistent OAuth/session SQLite database; protect filesystem access |

Also configure every actual `*_SERVICE_URL` consistently on callers. Signing refuses an unexpected destination or non-loopback plain HTTP. Do not put any signing key in `NEXT_PUBLIC_*` variables or frontend files.

Generate fresh values with Python's `secrets.token_urlsafe(48)` and `Fernet.generate_key()`. Existing session cookies are invalidated by the new signing salt. OAuth state expires after ten minutes, is browser-bound and consumed once; authorization codes use PKCE. Google provider consent still requires an interactive test with the configured account before production enablement.

## Credential storage and disconnect

UI database initialization transactionally encrypts legacy plaintext access tokens, refresh tokens and client secrets. Preserve `TOKEN_ENCRYPTION_KEY`; changing it without re-encrypting rows makes existing connections unreadable. Back up database and key separately before deployment. Disconnect deletes this owner's tokens and all local sessions. It does not claim to revoke the application's grant at Google; the account owner can revoke that separately through Google account permissions.

Calendar agents call authenticated `/internal/calendar/availability` and `/internal/calendar/meeting` operations. They never obtain raw OAuth tokens, choose an owner from model output, fall back to the latest user, or silently use a service-account Calendar.

## Deployment limits

On 1 November 2026, public IAM grants were removed from the four existing Cloud Run services and invoker IAM enforcement was verified. Anonymous HTTP probes returned 403 for every service. See `p0-cloud-containment.json`. The old code revisions remain deployed; this containment is not a deployment of the new source.

Cloud Run rejected ingress updates with `BILLING_DISABLED`. The owner requested that billing remain unchanged and cloud work be deferred. Ingress remains `all`, with IAM authentication required. Do not re-add public grants. The supported P0 configuration is local, single-owner operation with persistent SQLite files; current local settings use demo mode and disable every live action. Cloud redeployment is not part of the completed local verification.

The deploy scripts target the actual existing service names, default to internal ingress and private IAM, limit instances to one, force demo mode and disabled live actions, and preserve other existing environment settings. The old bulk-public-access script refuses to run. These scripts are preparation for a later rollout and have not been executed to deploy this source.

Use a single restricted host until durable job and tenant work is complete. SQLite replay storage must survive restarts and be shared by all workers. A multi-replica/cloud deployment without shared durable nonce storage is not supported by this P0 implementation. Cloud Run IAM also requires the caller's Google identity token and invoker permission in addition to application request signing; configure that transport before attempting a private Cloud Run rollout. These requirements remain tracked in checklist item 22.

Do not expose agent services publicly to work around a configuration error. Validate real service URLs, ingress, IAM, secret mounting, persistent storage and the deployed revision as a separate rollout gate. No deployment is implied by local test results.

## Commit and verification boundaries

1. Frontend security dependency update: `frontend/package.json` and `frontend/package-lock.json`, after the production build and fresh audit pass.
2. P0 application boundaries: shared security, UI authentication/OAuth/Calendar gateway, callers and provider guards, frontend API/demo changes, regression tests, environment/deployment documentation. These files must travel together; partial authentication changes would break internal requests.
3. Python dependency locks and container installation changes: direct `.in` manifests, compiled runtime requirements and test dependencies; validate service imports and audits before committing.
4. Data/build hygiene: ignore rules, sanitized tracked debug fixture, reduced sensitive logging, history-scan report.

No commit is created automatically. See `FIX-CHECKLIST.md` for item status and remaining rollout work.

## Verified checkpoint — 1 November 2026

See `P0-VERIFICATION.md` for test results and limits. The frontend dependency checkpoint was committed by the owner as `e4486eb`. The remaining P0 source, manifests, tests, scripts and documentation form one coordinated security change. `P0-COMMIT-FILES.txt` lists only that change's files; it excludes the owner's unrelated pitch/deck documents and every local secret or runtime artifact.
