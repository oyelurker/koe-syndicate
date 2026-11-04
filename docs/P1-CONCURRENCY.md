# Campaign concurrency and shared local workers — 4 November 2026

This completes item 15's source/local verification for the supported topology: one configured owner, one active campaign per owner, UI workers sharing the same SQLite database on one host, and one process per agent service. Authentication remains restricted to the configured Google account. Independent Cloud Run replicas with separate files are not supported; deployment/shared cloud storage validation remains item 22. No billing change or cloud deployment was performed.

## Authoritative state and conflicting writes

Each authenticated HTTP operation and discovery task loads its own owner-scoped snapshot and revision from SQLite. Context-local views prevent concurrent requests from mutating each other's working state. The process cache is used for initialization/diagnostics; requests do not trust it. A successful HTTP response flushes any remaining changes before response headers are sent.

Schema version 2 adds snapshot revisions, job worker IDs and worker leases. A write takes SQLite's writer lock, compares the caller's expected revision, then commits the snapshot, campaigns, lead changes, job changes and event together. The default revision is zero, which permits creation only. An existing snapshot cannot be silently overwritten without the correct revision. Serialization failures, constraint failures and revision conflicts leave no partial commit or event.

A competing write returns HTTP 409 with `code: pipeline_conflict`. Reload before deciding whether to retry. There is no automatic provider retry or speculative merge. A background task that loses a revision race discards its state and cannot run its completion finalizer against the newer campaign. This protects reset/new campaigns even when the late task lives in another UI process. It does not recall a provider request already sent; cancellation and external-action idempotency remain item 16.

## Durable owner event delivery

Production updates are committed to the owner-scoped event table rather than broadcast only within the receiving process. Each connected socket reads a bounded batch of up to 200 committed events every 0.5 seconds, filters obsolete campaigns, advances its own event cursor, and receives a current snapshot when caught up. A callback handled by a different UI worker therefore reaches the connection. Snapshot, revision and outbox cursor are read in one consistent database transaction. Socket messages include campaign/revision metadata, and committed event messages include an event ID.

Cookie/Origin authentication remains in place, including session revalidation before sends and during quiet periods. Wrong-owner sessions cannot subscribe. This is server-side delivery for connected clients; durable browser acknowledgements, reconnect/history recovery and dashboard stale-event handling remain item 23. The current dashboard's existing snapshot/reset rendering limitations are not claimed fixed here.

## Worker lifecycle

Workers renew a 90-second lease every 20 seconds. Startup and periodic maintenance mark discovery work interrupted only when its worker lease is missing or expired. A second healthy worker no longer interrupts the first worker's active job. Graceful shutdown releases its lease; after an unclean exit, interruption may take the lease period plus the next maintenance pass. An expired worker cannot renew its old lease or commit further pipeline writes; restart gives it a new identity. Failed renewal is logged and expires closed. No provider work is replayed automatically.

These leases track in-process discovery work. They are not a durable dispatch/retry queue. Agent A2A task stores and pending SDR approvals remain process-local; keep those agent services single-process until their durable execution work is implemented. A request reaching an agent without the matching pending approval fails rather than selecting another request.

## Approval provenance

SDR pending requests and duplicate-session keys are scoped by verified owner and campaign. Request IDs use full UUIDs; prompt session hashes are stable and scoped. The UI records campaign identity from the verified signer. An approval response must contain `request_id`, `campaign_id` and `response`; the path ID, stored request campaign and active campaign must match before forwarding. Missing campaign returns 422; stale/mismatched identity returns 409. Legacy pending requests without verified campaign identity are excluded from the active view.

Failed agent delivery returns 503 and retains the pending request. Only a successful response from the matching agent removes it and records submission. The human-approval UI and durable acknowledgement/reconciliation remain items 24 and 16.

## Operating and upgrading

Before upgrading, stop services and create a backup with `python scripts/backup_local_data.py`. Preserve the existing `TOKEN_ENCRYPTION_KEY`. Restart every local service on the same code revision. Migration preserves existing snapshots, encrypted OAuth values and credentials. Older schema-1 application code refuses a schema-2 database; restoring an older code revision requires a compatible backup.

All local UI workers must use the same persistent absolute `DB_PATH` and `SECURITY_DB_PATH`, the same owner and signing/session/encryption configuration, and consistently configured browser origins/service URLs. Separate database files do not form a replicated store. Keep live-action flags disabled until the remaining policy/execution gates pass.

## Verification

Regression evidence covers revision rollback, competing OS processes with the same/different owners, independent concurrent HTTP views with one success and one 409, fresh reads despite stale caches, stale discovery after another worker's reset, bounded/campaign-filtered owner outboxes, worker expiry, schema-1 migration and encrypted credential preservation.

A real two-process Uvicorn test verifies authenticated reads, wrong-owner read/reset/execution/socket denial, a callback on worker 2 reaching a socket on worker 1, a reset becoming visible on worker 1, stale callback rejection and preservation of the other owner's records. Approval tests cover owner/campaign ID collisions, missing context, signed SDR rejection/duplicate responses, stale browser responses and truthful failed delivery. All test databases, credentials and ports are temporary; providers remain disabled.

Validation result: **132 tests passed** in the combined offline suite, with four existing upstream SDK warnings. The final expired-worker lease-renewal/write-fencing regression also passes. Whitespace validation and tracked-file secret scanning pass. Hosted Linux/Windows PR checks remain pending publication; no live provider or cloud deployment claim is made.

## Phase C follow-up — 4 November 2026

Item 16 is now complete for the same local shared-database topology. Durable claims and signed job tokens fence execution and callbacks; provider receipts recover confirmed outcomes and quarantine ambiguous writes. Items 17–18 add policy enforcement and bounded asynchronous phone execution. See `P1-PHASE-C.md` for upgrade requirements and verification limits.
