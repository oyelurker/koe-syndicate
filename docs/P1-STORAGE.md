# Durable local data — P1 item 14

The application now uses the existing `DB_PATH` SQLite database for both encrypted OAuth credentials and versioned application records. The database must be on a persistent local disk. No external service or cloud billing is required. The supported runtime remains one configured owner. The item 15 follow-up in `P1-CONCURRENCY.md` supports UI workers sharing this file on one host; agent services remain single-process. This does not enable multi-user login or independent cloud replicas.

## Stored records and migration

Schema version 1 introduced tenants, campaigns, leads, jobs, events, integration connections and pipeline snapshots. Schema version 2 adds compare-and-swap snapshot revisions, job worker identity and worker leases; existing records and encrypted credentials are retained. Every application record carries an explicit tenant derived from the canonical owner email. Queries bind owner/record parameters; campaign references are constrained by composite tenant foreign keys. Existing Google profiles gain tenant/connection records without replacing their encrypted credentials or sessions. The fallback profile identifier is deterministic across process restarts.

Migration is automatic at startup. Application-schema changes, owner-email normalization and connection backfill share a transaction. Failed migration rolls back those changes; a database from a newer schema version is rejected before auth data is modified. Case-colliding legacy email records require manual review and are not silently merged. Preserve a backup and the existing `TOKEN_ENCRYPTION_KEY` before starting the updated application.

State updates are persisted before broadcasting, even when no browser is connected. Startup restores the configured owner's leads, original model fields/timestamps, agent updates, scores and pending human-input records. It starts with an empty cache when that owner has no snapshot. Socket objects themselves are never persisted. The production broadcaster refuses updates if storage startup did not finish or the execution owner is missing.

Discovery job records track running/completed/failed work. Startup and maintenance mark work interrupted when its owning worker lease is missing or expired; healthy workers are left alone. An unclean exit waits for lease expiry before interruption. No provider calls are replayed. This is durable recording, not the durable scheduler/retry/idempotency implementation required by item 16.

## Disconnect and retention

Disconnect deletes the owner's OAuth credentials and sessions, marks the Google connection disconnected, increments its connection generation and cancels queued/running Google-bound job records. Reconnection gets a new generation; it does not make an old connection-bound job eligible again. New connection-bound job creation requires a connected integration. Runtime Calendar operations continue to retrieve credentials from the authenticated owner rather than a default/latest profile.

Campaign, lead, event and job history is retained locally after disconnect or a dashboard reset. There is no automatic retention purge in this checkpoint. Reset clears the current view; full in-flight cancellation remains item 16. Owner-requested record deletion/export UI is not included. Keep live-action flags disabled until the remaining execution-policy gates pass. The database and its backups contain business/contact data; OAuth token fields remain encrypted, while application records are not claimed to be encrypted at rest.

## Backup and restore

Use Python 3.12 with the committed requirements installed. Before starting the new revision, create a consistent database backup:

```powershell
python scripts/backup_local_data.py
```

The default destination is a timestamped `.runtime/backups/*.db` file. An explicit destination is supported with `--output`. The command uses SQLite's backup API, includes the WAL-consistent database contents, verifies integrity and refuses to overwrite an existing file. Missing sources fail instead of producing an empty backup. The encryption key is not copied; preserve it securely and separately.

To restore, stop the UI and copy a backup into a **new** database path:

```powershell
python scripts/backup_local_data.py --source .runtime/backups/YOUR-BACKUP.db --output .runtime/restored.db
```

Set `DB_PATH` to that restored file and retain the original token encryption key before restarting the UI. This preserves the backup and avoids overwriting the current database. `.db`, `.sqlite`, `.sqlite3` and their sidecar files are excluded from Git/build uploads.

## Verification and remaining gates

Local validation: **94 tests pass**, with four upstream Google SDK deprecation warnings. The real-process startup smoke check, actionlint and the locally exercised manual CI failure probe also pass their expected checks. This feature branch has not yet been published or verified by hosted CI.

Offline tests cover existing-data migration, idempotent initialization, rollback on failure, future-schema rejection, owner-scoped same-ID records, foreign-campaign rejection, transactional failure, disconnect/reconnect generations, encrypted backup/restore, the actual backup CLI, exact model preservation across a real app lifecycle, interrupted work without replay and cache isolation when the configured owner changes.

The browser/API runtime still uses a single-owner memory cache. Simultaneous-user isolation is item 15. Durable dispatch, cancellation, retries and external-action idempotency are item 16; rate/spend/recipient policies are item 17. Shared cloud storage and rollout remain item 22. Keep the existing Cloud Run services IAM-contained while those gates are incomplete.
