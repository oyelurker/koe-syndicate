# P1 verification checkpoint — 4 November 2026

Items 11–18 are complete for the restricted local/shared-database scope. See `P1-CONCURRENCY.md` for item 15, its multi-process evidence and its deployment limits. The durable-storage foundation was merged through PR #20; see `P1-STORAGE.md`. Hosted CI and main's merge protection are verified, including the deliberate failure and recovery proof recorded below. Phase C execution safeguards are documented in `P1-PHASE-C.md`. Integrations and cloud deployment remain pending in items 19–22. Cloud services stay IAM-contained and live actions stay disabled.

## Backend baseline — item 11 complete

- Before: 13 failures and 63 passes across the UI and P0 suites.
- At the baseline checkpoint, `python -m pytest -q` passed **80 tests**, including all 56 P0 cases. The merged storage suite now has **94 passing tests**. Four upstream Google SDK deprecation warnings remain; the application's deprecated Pydantic serialization was corrected.
- The legacy UI tests now authenticate with real signed sessions, CSRF tokens and signed service requests. Redirect assertions explicitly disable following. Health assertions reflect the intentional removal of public pipeline state. Typed SDK responses distinguish successful empty results, failed tasks and JSON-RPC errors.
- Shared fixtures use temporary databases, deterministic test identities and isolated pipeline state. External socket connections fail tests instead of reaching a provider. A regression test proves the network guard rejects a connection before opening it.
- Twenty-eight historical provider/debug probes were moved to `scripts/manual_checks/`; several execute real work while being imported and are not automated tests. They remain available as historical references with an explicit README. The minimal test-container copy path was updated. No failing maintained test was skipped or suppressed.
- Pytest now declares test roots, import mode, required async plugin, strict configuration and strict markers. Run with a fresh Python 3.12 environment and `requirements.txt` plus `requirements-dev.txt`; an outdated plugin fails with an actionable requirement error.

## Frontend — item 12 complete

- Before: four lint errors and 30 warnings.
- After: lint passes with **zero errors and zero warnings**; standalone TypeScript checking and the production build pass. Local Node version: 26.3.0. Hosted CI also passes on Node 24.
- The phone modal initializes its editable state in a keyed form, so switching prospects or reopening the modal resets the draft without an effect-driven render loop. Internal navigation uses Next Link. External OAuth navigation remains a full browser navigation to the backend.
- Removed unused values and duplicate component font links. Fonts are supplied by the root layout through Next's font loader. Existing external images use explicit dimensions or bounded fill; they remain unoptimized to retain direct external delivery, including SVG logos.
- Lint now treats warnings as failures by default. There are no new blanket rule suppressions.

## CI — hosted success and merge protection verified

`.github/workflows/ci.yml` runs offline backend tests on Linux and Windows, frontend lint/type checking/build, dependency audits and a tracked-file credential-pattern check. It uses read-only permissions, no provider secrets, pinned official action commits, timeouts, cancellation of superseded runs and an aggregate `required-checks` job that fails unless every prerequisite succeeds. Dependabot is configured for frontend, Python and Actions updates.

Local evidence:

- The workflow passes actionlint 1.7.12, downloaded from its official release with the published archive checksum verified.
- Fresh Python advisory checks report no known vulnerabilities in all runtime locks. Fresh npm checking passes the high/critical threshold; the existing 16 moderate lint-toolchain findings remain a documented limitation. These tools should run only on trusted project input; no advisory findings were hidden with an ignore list.
- The tracked-file secret check reports no matches in the working tree. Its test injects a fake credential into a disposable repository, proves a nonzero exit, confirms the secret itself is not printed, then proves ordinary content passes. It is a bounded pattern check of tracked files up to 1 MiB, skips symlinks and is not a replacement for provider revocation or a comprehensive entropy/history scanner. The separate P0 history scan remains available.
- Commit `844bce6` passed every hosted job, including both Linux and Windows backends and the aggregate `required-checks`: [verified CI run](https://github.com/oyelurker/koe-syndicate/actions/runs/41275060918). `p1-hosted-ci.json` records the results and policy.
- GitHub's API confirms main now requires an up-to-date `required-checks` result from the GitHub Actions app, PRs, admin enforcement and no force-push/deletion. No second reviewer is required. Future work belongs on feature branches and PRs.

On 4 November 2026, the manual-only `exercise_failure_gate` input was exercised against merged main commit `77879b37fc462d19a5a7a86e4e91d5d9d52bc2a9`:

- [Intentional failure run](https://github.com/oyelurker/koe-syndicate/actions/runs/41778811893): the maintained Linux suite passed, then the opt-in test failed. The Linux job and aggregate `required-checks` failed; Windows, frontend, audits and secrets passed. This proves failure propagates to the required check. No failing project code was committed and no merge was attempted.
- [Normal recovery run](https://github.com/oyelurker/koe-syndicate/actions/runs/41779206213): the same commit, with the probe disabled, passed all six jobs. Ordinary pushes and PRs never execute the intentional-failure step.
- Main's protection was re-read from GitHub: strict/up-to-date `required-checks`, bound to GitHub Actions app 15368, PR requirement and admin enforcement remain enabled. Force pushes and deletion remain disabled.

Item 13 is complete. `p1-hosted-ci.json` contains the run/job evidence and policy. Dependabot PRs remain open and unmerged. No cloud deployment or provider action was performed.

## Commit and next step

The owner retains control of commits. This branch changes only verification documentation and evidence; the two earlier commit-file manifests are historical and should not be reused. The next implementation is item 16: durable dispatch, cancellation, bounded retries, idempotency and reconciliation. Keep the existing single-owner restriction and disabled live actions until all applicable execution and deployment gates are satisfied.

The configuration follows the official [GitHub Actions Python guide](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) and [Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference). Frontend changes follow the installed Next.js 16.4.3 documentation for client components, Link, Image and fonts.

## Phase C final checkpoint — 4 November 2026

Items 16–18 pass the complete offline suite: **172 passed**, with four existing upstream SDK deprecation warnings, in 84.21 seconds. This includes local process restart/claim recovery, independent-process quota races, signed exact-action dispatch, migration rollback, cancellation, provider timeout/reconciliation and policy enforcement. Frontend lint (zero warnings), TypeScript and production build pass. Whitespace validation and the tracked-file secret check pass (zero matches). Providers were mocked; no live writes or cloud deployment were performed. See `P1-PHASE-C.md` and the explicit 29-file commit manifest `P1-PHASE-C-COMMIT-FILES.txt`. Hosted CI awaits publication.
