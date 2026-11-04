# Owner runtime and socket isolation — 4 November 2026

This is the second commit checkpoint within checklist item 15. Browser and service authentication still restrict the instance to its configured owner. The runtime now separates data and socket delivery by explicit verified owner, but it remains process-local. Item 15 is not complete until cross-replica consistency and applicable deployment checks are implemented.

## Behavior

`ui_client/runtime.py` supplies an owner-scoped mapping for the pipeline. Every lookup, mutation, snapshot and reset resolves the current `Execution` owner. There is no configured-owner or latest-user fallback. Missing/invalid owner context fails closed. Separate owners receive fresh dictionaries, including nested lead, score, update and human-input collections. Existing route code uses this mapping, so reads, callbacks, discovery, scores, human input and resets share the same ownership boundary.

Startup explicitly binds the configured owner while restoring that owner's durable snapshot and calculating startup scores, then restores the previous context before serving. Shutdown clears process caches and socket registrations. Startup restoration still loads only the configured account: this does not enable multi-user login or lazy restoration of other accounts.

Each WebSocket registration records its authenticated owner. Publishing requires an owner even with no clients, persists under that owner and sends only to that owner's registered connections. Identical campaign IDs do not join different owners' streams. Initial snapshots and updates include `campaign_id`. Connections follow their owner's active dashboard campaign. Delivery rechecks the current campaign and connection membership after persistence and between awaited sends; disconnected clients and obsolete events are dropped. An already-started network send cannot be recalled.

## Verification

Eight new offline tests cover missing/invalid context, concurrent owner contexts with identical IDs, actual API reads/callbacks/resets and durable events under two verified identities, bidirectional socket separation, denied ownerless socket/publish operations, reset during persistence and disconnect during persistence. The API test harness supplies trusted identities below the auth boundary; it does not modify production auth. Existing P0 tests retain real session/signature/CSRF checks and single-owner denial, including revoking an already-connected socket.

Validation: the combined offline suite passes **115 tests** (107 existing plus eight new isolation regressions), with the same four upstream SDK warnings. Tracked-file secret scanning reports zero matching locations; whitespace checks pass. Hosted PR checks remain pending publication.

## Remaining work

- Transactional revisions/ordering for competing writes and campaign replacement, including across processes/replicas.
- Shared durable state/event delivery and applicable multi-replica isolation tests before replica enablement.
- Durable job dispatch, cancellation and provider idempotency (item 16).
- Frontend event recovery/reconnect and campaign-aware stale-event handling (item 23).

Keep single-owner access and live actions disabled. No cloud revision or provider action was executed for this checkpoint.
