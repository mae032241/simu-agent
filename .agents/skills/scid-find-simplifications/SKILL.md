---
name: scid-find-simplifications
description: Find evidence-backed simplifications in SciDiscovery's control plane, scientific contracts, plugin seams, tests, and documentation. Use for explicit complexity-reduction, architecture-simplification, dead-surface, duplicate-state, or overengineering audits; do not invoke for an ordinary bug fix or style cleanup.
---

# Find SciDiscovery Simplifications

Identify a small set of changes that remove real maintenance cost while preserving the scientific-control guarantees that justify this framework. Default to a read-only audit unless the user asks for implementation.

## Preserve the load-bearing invariants

Do not propose weakening these merely to reduce code:

- immutable, content-bound Artifacts and explicit lineage;
- one authoritative currentness and qualification decision;
- scientific judgment separated from deterministic transforms and side effects;
- identity-free, bounded Worker assignments;
- exact human review for claim qualification and execution authorization;
- idempotent lifecycle transitions and reconciliation of uncertain external effects;
- core/domain plugin separation and fail-closed admission.

Read the current architecture sources before judging a candidate: `docs/ARCHITECTURE.md` or its Chinese counterpart, the scientific design charter, the constraint registry and current audit ledger, and the relevant package or plugin documentation. Treat plans, old audits, tests, and comments as evidence, not automatic authority.

## Find strong candidates

Start with the largest production modules and the boundaries most changed by the current work. A strong candidate has call-site evidence for one or more of these conditions:

- two registries, projections, records, or validators represent the same authoritative fact;
- readiness and mutation admission independently encode the same rule;
- a public method, operation, configuration field, event, compatibility path, or schema variant has no production consumer;
- only tests or documentation consume a surface that is not a supported contract;
- a domain-specific rule leaked into the generic core or a generic extension point has only one private consumer;
- multiple flags, receipts, or reconciliation paths mirror one lifecycle transition;
- a hand-written parser, diff, retry, packaging, or discovery mechanism can be replaced with a smaller proven dependency without relocating the same complexity;
- prompt instructions compensate for a rule that code already enforces, or code duplicates a rule that should have one runtime authority;
- historical plans or audits remain on the active reading path after their decisions have been superseded.

File size, age, test count, or conceptual dislike is not sufficient evidence.

## Prove each candidate

Use `rg` and the runtime registration/loading paths, not symbol search alone. Classify every consumer as production, dynamic/plugin-loaded, test-only, documentation-only, generated, or historical. Trace both the producer and consumer, including entry points, installed-wheel behavior, MCP facades, subprocesses, and deployment scripts.

For lifecycle machinery, draw the smallest ownership and state-transition map that explains the duplication. Name the exact invariant each mechanism protects. Reject the candidate when deletion would make a product decision, break persisted compatibility, or discard a defensive rule without stronger evidence.

## Report

For each retained candidate provide:

1. exact files and symbols;
2. duplicated or unused responsibility;
3. production-consumer evidence;
4. invariant that remains protected;
5. proposed deletion, folding, demotion, or rehoming;
6. behavior or compatibility intentionally given up;
7. focused regression tests and observable acceptance criteria;
8. risk and rollback boundary.

Prefer a few high-confidence candidates over a long speculative list. If implementation is requested, handle one independently verifiable candidate at a time and compare focused tests before and after.
