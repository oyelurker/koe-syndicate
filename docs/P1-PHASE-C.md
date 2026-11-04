# Phase C: durable execution and outreach safeguards

Source checkpoint: 4 November 2026. Items 14–18 are complete for the restricted local topology. Live provider actions remain disabled. Cloud services remain IAM-contained; deployment validation is item 22.

## Supported operation and upgrade

One configured owner is supported. UI and agent services must use the same absolute DB_PATH on one host and the same absolute SECURITY_DB_PATH for signature replay protection. Agents remain single-process. Independent cloud replicas require a supported shared-storage design and deployment verification.

Stop all services, back up the SQLite database and preserve TOKEN_ENCRYPTION_KEY before upgrading. Startup atomically migrates application schema 2 to 3 without replacing encrypted OAuth data. Restart every service with the same code: signed requests now bind job identity and claim tokens. Older code rejects a newer database. Restore the matching database backup and code together for rollback.

## Item 16: durable jobs and provider receipts

Campaign state and dispatch acceptance commit atomically. A tracked consumer claims work with expiring leases and signed job provenance. Discovery retries at most three times; deterministic lead IDs prevent duplicate results. Only the current campaign and active claim may publish callbacks. Reset and cancellation fence future work and approvals.

Calls, emails and bookings have immutable action keys and durable provider receipts. A dispatch marker commits before the network write. Unknown outcomes are quarantined rather than resent. Confirmed receipts can recover a job after worker loss without issuing another write. Reconciliation reads known provider identifiers; absence of proof does not authorize replay. Cancellation cannot undo an already accepted provider operation.

## Item 17: enforceable owner policy

Provider tools independently require live mode and the relevant server flag, an active job, explicit recipient allowlisting, an exact owner-approved payload, a valid contact window, and available quota. Policies specify owner timezone, weekdays/hours, hourly/daily action counts, concurrency and daily action budget units. Approval expires and binds recipients, content, sender/provider identity, attachment digest and campaign/mode. Suppressions apply across the owner's campaigns. Decisions and receipts are durable and owner-scoped.

Budget units are conservative owner-configured action costs, not measured provider billing. Cancelled and ambiguous reservations remain charged. LLM workflows have bounded calls; provider account spending caps and staging checks remain deployment work. This checkpoint does not guarantee a dollar billing ceiling.

Authenticated browser APIs provide jobs/cancellation, policy, proposals, approvals, suppressions, audit, receipts, exact approved dispatch and read-only reconciliation under /api/jobs and /api/outreach. Mutations require the existing session and CSRF protection. Agent signatures cannot grant owner approval. The visual approval interface remains item 24.

Email attachments are frozen in the owner ledger by digest, limited to 10 MiB and sourced from the owner's campaign directory. Arbitrary local files are rejected. Success notifications require confirmed provider receipts rather than model claims.

## Item 18: phone execution

The asynchronous provider client uses bounded requests, no automatic SDK retries and a total deadline. MAX_CALL_SECONDS defaults to 120 and accepts 60–600; the provider receives the same conversation duration limit and a ringing timeout. Cancellation attempts a bounded Twilio state-aware hangup and records whether stopping was confirmed. Missing stop credentials fail before placing live calls. Unknown provider outcomes stay quarantined.

Only explicit supported +1 NANP and +91 Indian formats are accepted. PHONE_DEFAULT_COUNTRY may explicitly select 1 or 91; an unset value never guesses a country for a bare national number. Authentication, quota, validation, timeout and provider failures are distinguished.

## Verification and remaining work

Offline regressions cover migration rollback, real local restart/claim recovery, process races, signed dispatch, cancellation, stale callbacks, exact approvals, quota windows, suppressions, immutable artifacts, stalled providers and reconciliation without duplicate writes. Provider transports are mocked and external sockets are blocked. Frontend lint, TypeScript and production build pass. The final backend result is recorded in P1-VERIFICATION.md.

No real call, email, booking, billing change or cloud deployment was performed. Hosted CI must run after publication. Phase D remains: Gmail durable ingestion (19), complete Calendar availability/DST/conflict handling (20), truthful meeting persistence (21), deployment (22). Legacy Gmail direct execution must be replaced with durable enqueueing; it now fails closed without a valid job. Dashboard reconnect recovery (23) and approval UI (24) remain separate work.
