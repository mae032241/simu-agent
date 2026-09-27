---
name: scid-change-scope-checks
description: Select and run the smallest credible SciDiscovery checks for an exact working-tree, commit, or PR diff. Use before push or review, after rebasing, when verifying a fix, or when deciding whether focused tests or the full suite are warranted; do not use as a substitute for semantic review.
---

# Select SciDiscovery Change-Scope Checks

Produce truthful local evidence for the exact outgoing change. Focused regression evidence comes first; CI owns the exhaustive platform matrix. Do not push, commit, rewrite history, or modify external state unless separately requested.

## Establish scope

Confirm the repository root and `git status --short --branch`. Use the user-specified base/head when provided. For uncommitted work with no external base, inspect the diff against `HEAD` and say so; never guess a remote branch. Include staged, unstaged, untracked, generated, and deleted files in the scope assessment.

Classify affected surfaces before choosing commands:

- Schema, semantic validators, operation contracts, qualification, and readiness;
- task, Artifact, approval, execution, storage, recovery, or MCP services;
- plugin entry points, runtime factories, transforms, scorers, or domain adapters;
- Worker prompts, role definitions, skills, or generated platform configuration;
- deployment, installation, release manifest, packaging, or migrations;
- approval UI, rendering, JavaScript, or browser behavior;
- documentation, constraint registry, audit ledger, or bilingual pairs.

## Select evidence

Always consider `git diff --check`. Then choose the narrowest test that would fail for the intended regression and expand only for shared contracts:

- run the owning test function or file for a local behavior change;
- add contract, context-policy, readiness, and task-operation tests when a scientific Schema or operation changes;
- add real MCP/proxy/daemon or process E2E coverage when transport, session, timeout, or recovery changes;
- run plugin boundary, entry-point, clean-install, and deployment-probe tests for plugin registration changes;
- build and test installed artifacts for package metadata, exports, release builders, or runtime discovery changes;
- run approval renderer/UI tests and a real browser flow for user-visible review changes;
- run `scripts/validate_architecture_constraints.py` when the charter, registry, coverage matrix, current audit ledger, or architecture-enforced behavior changes;
- run `scripts/run_science_control_bench.py` for cross-cutting protocol, recovery, scientific-quality, or plugin-compatibility claims.

Run the full `pytest -q` suite when the change crosses several ownership boundaries, changes shared lifecycle or admission code, affects global plugin/runtime assembly, or no focused set credibly covers the impact. Do not use the full suite as a replacement for a focused regression that demonstrates the defect.

Tests that import source through repository `pythonpath` do not prove wheel packaging or installed entry-point behavior. Tests using fixtures or mock adapters do not prove a live Worker, browser, or solver lane.

## Handle results

Stop on a relevant failure and report the exact command and failing behavior. Investigate before labeling a failure environmental. Do not rerun unchanged passing commands for ceremony, lower thresholds, hide missing tests, or claim that local evidence equals CI or production qualification.

Report:

- the exact diff/base examined;
- affected surfaces;
- commands run with pass/fail status and duration when available;
- important checks not run and why;
- whether a full suite, installed-package smoke, live platform, browser, or real solver gate remains required.
