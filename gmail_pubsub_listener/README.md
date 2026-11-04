# Gmail listener

This single-process listener shares the UI service's absolute DB_PATH and SECURITY_DB_PATH on one host. Start the updated UI first so schema 4 exists, then run:

```sh
python -m gmail_pubsub_listener.gmail_listener_service
```

Configure KOE_OWNER_EMAIL, KOE_MODE, SERVICE_AUTH_KEYS, SALES_EMAIL, SERVICE_ACCOUNT_FILE and optionally PROJECT_ID/SUBSCRIPTION_NAME. Google Workspace domain-wide delegation must authorize the service account for the configured SALES_EMAIL and Gmail readonly access. A personal Gmail account is not automatically supported by service-account delegation. Keep populated credentials outside source control.

Pub/Sub uses streaming subscribe; startup/terminal failure switches to polling. Provider operations have transport timeouts and no implicit request retries. Both paths persist history cursors, paginate results and atomically accept messages with durable Lead Manager jobs before acknowledgement. Failed acceptance is retried. No direct agent execution endpoint is used.

Start a campaign before accepting mailbox work. Wrong mailbox notifications are rejected. Only incoming INBOX messages are accepted; duplicate message IDs do not create new work. Accepted jobs cancelled by a reset require operator review. All downstream actions still require Phase C's live flags, policies and exact approvals. Gmail label mutations require live email permission and the accepted job's exact message ID.

See ../docs/P1-PHASE-D.md for migration, provider setup limits, verification and deployment blockers. No cloud staging or live Gmail validation has been completed.
