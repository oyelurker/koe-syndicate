# Historical manual checks

These are development probes moved out of pytest discovery. Many execute code during import, contact real providers or assume a developer-specific path. They are retained as historical debugging references, not as supported automated tests. Review and adapt an individual script before running it; running one can incur provider usage. Do not import this directory from the offline suite or CI.

Run the maintained offline suite from the repository root with `python -m pytest`. The pytest configuration selects `tests/` and `ui_client/test/`, requires the async plugin and rejects external socket connections during tests. Shared fixtures provide temporary databases and test identities. Provider integration checks should be added as explicit, opt-in commands with documented prerequisites rather than import-time scripts.
