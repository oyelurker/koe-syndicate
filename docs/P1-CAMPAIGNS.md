# Campaign provenance checkpoint — 4 November 2026

This is the first commit checkpoint within checklist item 15. The item remains open: shared UI runtime state, full owner/campaign socket routing and cross-replica consistency still need implementation and two-owner/replica tests. Keep the configured single-owner restriction and all live-action switches disabled.

## Changes

- `Execution` carries an optional campaign ID. Internal HMAC signatures cover `X-Koe-Campaign` along with the existing owner, mode, destination, method, body, time and nonce. Changing/removing the campaign invalidates the signature. Campaign identifiers are bounded and validated.
- The six UI workflow transports bind their request to the selected campaign. Agent callbacks and human-input requests require a signed campaign matching the active local campaign; missing, reset and superseded campaigns return 409 before mutation or persistence. Calendar callbacks use the same boundary.
- Lead Finder, SDR and Lead Manager reject A2A context/campaign mismatches before executing a task. ADK user IDs derive from verified owners; ADK sessions derive from campaign/task identity. Model-supplied data cannot choose these identities. This separates SDR sessions for different lead tasks within one campaign.
- Discovery captures its campaign before scheduling and checks it after the provider returns and before processing each lead. Old success/failure results cannot populate, finish or publish into a reset or newer local campaign. In-flight SDR, Lead Manager and human-response results also check the campaign before publishing.
- Reset and new discovery clear pending human-input requests and scores from the previous view. Durable history is retained.

## Compatibility and limits

Restart all local services together: the signed protocol changed. Older requests fail signature verification; campaign-less callbacks are deliberately rejected. Old in-memory ADK sessions are not migrated. The Gmail listener still needs explicit durable campaign association as part of item 19; it must not attach incoming messages to whichever campaign happens to be visible.

This checkpoint rejects obsolete results in the local process. It does not cancel provider work already sent, implement a durable dispatcher, prevent duplicate provider actions, or provide transactional cross-replica ordering. Those remain items 15–16. No claim of multi-user or cloud readiness is made.

## Verification

The new offline regressions exercise signed-header tampering, real signed HTTP propagation, current callback persistence, missing/old campaign rejection without state/events, stale human requests, delayed discovery success/failure after reset/replacement, normal discovery completion/context cleanup, and owner/task identity separation. Existing callback contract tests now supply an explicit active campaign. The maintained P0 authentication/replay assertions remain in place.

Validation: the full offline suite passes **107 tests** (94 existing plus 13 campaign regressions), with four existing upstream SDK warnings. All five service import checks and `git diff --check` pass. Hosted PR validation remains pending publication.

Follow-up: the owner runtime/socket checkpoint in `P1-OWNER-RUNTIME.md` replaces the shared UI cache and shared socket broadcast described as pending above. Cross-replica ordering and durable execution remain open.
