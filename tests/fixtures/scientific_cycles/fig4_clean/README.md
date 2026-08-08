# Fig.4 Clean Fixture Namespace

This directory is the only test-visible namespace for new Fig.4 layered tests.
It intentionally starts with no accepted scientific data files.

Historical Fig.4 resources under `results/`, `agent/runtime/`, and the research
ledgers are evidence archives. Tests must not discover or select them with a
glob. A historical resource may enter this directory only after provenance,
realization, and scope review, and only by adding its relative path and SHA-256
to `manifest.json`.

Synthetic values constructed inside unit tests exercise Schema and control
logic only. They are not paper evidence, TCAD evidence, or accepted scientific
results.
