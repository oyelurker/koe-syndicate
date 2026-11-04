# Phase D: integration checkpoint — 4 November 2026

Items 19–21 are implemented and verified in the offline local topology. Item 22 remains open. P0's restricted local source scope is already complete; cloud reactivation was explicitly deferred while billing is unavailable. P2/P3 product work also remains in FIX-CHECKLIST.md.

## Upgrade and supported topology

Stop every service and back up DB_PATH plus its encryption key before starting this checkpoint. Schema 4 atomically adds Gmail cursors, accepted messages, confirmed meeting records and Calendar interval claims. Existing encrypted credentials and Phase C jobs/receipts are preserved. Restart all services with the same version; roll back code and the matching database backup together.

Only one configured owner and one host with shared SQLite files are supported. Set the same absolute DB_PATH and SECURITY_DB_PATH for every service. Agents and the Gmail listener remain single-process. Production rejects relative storage paths, unsupported cloud topology and unencrypted non-loopback service URLs. The local launchers resolve shared paths before startup; the Windows launcher forwards security/integration settings and no longer kills unrelated processes on occupied ports.

## 19: durable Gmail ingestion

The listener uses SubscriberClient.subscribe with bounded flow control. Startup/terminal stream failures propagate to durable polling. Neither polling nor Pub/Sub calls a nonexistent agent endpoint. The shared database atomically accepts the full incoming message and a real Lead Manager dispatch job containing its stable message ID. The existing signed A2A consumer carries the claimed job; the email tool reads only that accepted message for ingestion jobs.

Acknowledgement follows durable acceptance, not an attempted HTTP send. Failed API reads, queue/storage failures and incomplete pages retain the old cursor and nack notifications. Duplicate delivery does not create another job. Saved history cursors drive all history pages; notification history IDs never become the start cursor. An expired history cursor triggers a paginated INBOX rescan with the replacement cursor captured before listing. Deleted/non-inbox/sent/draft/spam/trash messages do not trigger work. Accepted messages stay deduplicated across campaign resets; cancelled jobs require explicit operator review rather than automatic paid replay.

The configured SALES_EMAIL must match the delegated Gmail profile. The current provider authentication uses a service account with Google Workspace domain-wide delegation; it does not automatically support a personal Gmail inbox. Validate account authorization, watch/subscription provisioning and provider consent in staging before enabling the listener. Polling uses Gmail without depending on Pub/Sub availability; it does not bypass provider permissions. No delegated mailbox or real notifications were contacted in these checks.

## 20: Calendar correctness

Availability is owner-scoped, bounded to the requested future interval and checked against every returned free/busy interval; per-calendar errors fail closed. Calculations compare actual UTC instants across timezone changes. Nonexistent and ambiguous local booking times are rejected explicitly instead of choosing an offset silently. Duration is elapsed time.

Every approved booking rechecks provider availability immediately before dispatch. A transactionally claimed owner interval prevents competing application jobs from booking overlapping or unresolved intervals. Deterministic provider IDs and private action-key evidence reconcile uncertain writes without reinsertion. Missing or cancelled provider evidence remains unresolved. External clients can still modify a calendar after a free/busy read; Google Calendar does not make that read and insertion atomic, so provider staging remains required.

## 21: truthful durable meeting storage

SQLite is the designated meeting store for this topology. A confirmed Calendar receipt and its meeting record commit in one transaction. Storage failure cannot commit a successful receipt; reconciliation can recover known provider evidence and persist it without another booking. A failed/unknown booking or model-generated success cannot create a meeting record.

The post-action tool uses the immutable provider receipt rather than arbitrary model fields. It reports storage=local_sqlite and never claims a BigQuery upload. GET /api/meetings retrieves only the authenticated owner's persisted records. Success means the record is retrievable from this shared local database, not that data was uploaded to the cloud.

## 22: deployment still open

The UI image now includes scoring code/sample assets and the listener uses a package module entry point. Runtime preflight validates the supported topology, explicit production storage, owner, service key and service URL settings. The Cloud Run scripts refuse to build/deploy the incompatible independent-service SQLite topology. Live flags, IAM containment and billing were not changed.

Docker is installed, but the Docker Desktop Linux engine is unavailable (missing named pipe), so clean Linux container builds were not performed. Cloud Run staging is also unavailable while billing is disabled. Before closing item 22: choose a shared-database cloud design, implement/verify cloud identity transport, validate all service URLs/OAuth callbacks/browser origin/WSS, build every service and frontend, provision delegated Gmail/watch/subscription access, then run authenticated staging contracts and backup/rollback checks. Do not remove deployment guards merely to make a deployment command proceed.

## Verification

The final complete offline suite result is recorded in P1-VERIFICATION.md. New tests cover cursor pagination/expiration, atomic queue acceptance, nack on failures, duplicate delivery, polling fallback, actual job-scoped email-tool handoff, DST gaps/overlaps, bounded availability, simultaneous interval claims, atomic meeting storage/rollback and deployment-preflight rejection. All providers are mocked; no live calls, emails, bookings, billing changes or deployment occurred. Hosted CI remains to be run after publication.

Provider contracts were checked against the official [Gmail history reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list), [Gmail synchronization guide](https://developers.google.com/workspace/gmail/api/guides/sync), [Pub/Sub subscriber reference](https://docs.cloud.google.com/python/docs/reference/pubsub/latest/google.cloud.pubsub_v1.subscriber.client.Client) and [Calendar free/busy reference](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query).
