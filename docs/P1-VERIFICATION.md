# P1 verification checkpoint — 1 November 2026

The first checkpoint implements items 11–12. Its hosted CI now passes, and main's merge protection is enabled. The next feature branch implements the local durable-storage foundation in item 14; see `P1-STORAGE.md`. The opt-in hosted failure probe for item 13 still needs the updated workflow published and exercised. Isolation, job execution, outreach policies and integrations remain pending in items 15–22. Cloud services stay IAM-contained and live actions stay disabled.

## Backend baseline — item 11 complete

- Before: 13 failures and 63 passes across the UI and P0 suites.
- After: `python -m pytest -q` passes **80 tests**, including all 56 P0 cases. Four upstream Google SDK deprecation warnings remain; the application's deprecated Pydantic serialization was corrected.
- The legacy UI tests now authenticate with real signed sessions, CSRF tokens and signed service requests. Redirect assertions explicitly disable following. Health assertions reflect the intentional removal of public pipeline state. Typed SDK responses distinguish successful empty results, failed tasks and JSON-RPC errors.
- Shared fixtures use temporary databases, deterministic test identities and isolated pipeline state. External socket connections fail tests instead of reaching a provider. A regression test proves the network guard rejects a connection before opening it.
- Twenty-eight historical provider/debug probes were moved to `scripts/manual_checks/`; several execute real work while being imported and are not automated tests. They remain available as historical references with an explicit README. The minimal test-container copy path was updated. No failing maintained test was skipped or suppressed.
- Pytest now declares test roots, import mode, required async plugin, strict configuration and strict markers. Run with a fresh Python 3.12 environment and `requirements.txt` plus `requirements-dev.txt`; an outdated plugin fails with an actionable requirement error.

## Frontend — item 12 complete

- Before: four lint errors and 30 warnings.
- After: lint passes with **zero errors and zero warnings**; standalone TypeScript checking and the production build pass. Local Node version: 26.3.0. The CI configuration selects Node 24; the hosted run remains pending.
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

The remaining item 13 proof is an intentionally failed hosted test followed by a successful normal run. The updated workflow adds a manual-only `exercise_failure_gate` boolean, false by default. Locally executing its exact shell step creates a temporary failing pytest case and returns exit 1 as intended. After this workflow update is published, exercise that input once, verify the Linux test job and aggregate required check fail, then run normally and verify the gate returns green. Ordinary pushes/PRs never execute the intentional-failure step.

## Commit and next step

The owner retains control of commits. `P1-COMMIT-FILES.txt` is the historical first-checkpoint manifest, already committed as `844bce6`. Use `P1-STORAGE-COMMIT-FILES.txt` for the new storage/CI-evidence feature branch. It excludes unrelated pitch/deck files and runtime artifacts. Push the feature branch and use a PR; main now rejects direct pushes.

The configuration follows the official [GitHub Actions Python guide](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) and [Dependabot options reference](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference). Frontend changes follow the installed Next.js 16.4.3 documentation for client components, Link, Image and fonts.
