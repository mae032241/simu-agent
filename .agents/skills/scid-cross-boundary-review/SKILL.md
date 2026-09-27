---
name: scid-cross-boundary-review
description: Review SciDiscovery changes across MCP, operation, task, Artifact, Worker, qualification, plugin, UI, execution, and recovery boundaries. Use for PR, diff, architecture, lifecycle, or production-path reviews where local unit correctness is insufficient; not for style-only review.
---

# Review SciDiscovery Across Boundaries

Review for defects that appear only when separately valid components compose. Default to read-only findings; do not implement fixes unless the user requests them.

## Establish the exact change

Identify the repository root, worktree state, review base, and exact head or uncommitted diff. Never guess a remote base. Preserve unrelated user changes. Read enough surrounding code and current architecture documentation to understand the intended ownership boundary.

## Trace the affected path

Follow every touched contract through the applicable real path:

```text
Scheduler / Root MCP
  -> operation entrypoint and admission
  -> service mutation and durable state
  -> task dispatch and identity-free assignment
  -> Worker validation and finalization
  -> receipt / terminal reconciliation
  -> downstream input admission
  -> active head and qualification
  -> approval UI or external execution
  -> deterministic scoring and diagnosis
```

Include plugin discovery, installed package entry points, generated platform configuration, and deployment paths when the change can reach them. Do not assume a hand-assembled test runtime represents the shipped entry path.

## Review lenses

- **Authority:** one source owns each fact; queries do not mutate; derived views cannot become alternate truth.
- **Identity and lineage:** immutable fingerprints include every behavior-changing input; revisions cannot overwrite or silently inherit qualification.
- **Admission consistency:** readiness advice and the command preflight accept and reject the same exact invocation; producer output families compose without core plugin-name allowlists.
- **Scientific ownership:** Workers decide scientific content, deterministic code owns mechanical fields and metrics, adapters own side effects, and the scheduler does not manufacture role output.
- **Model-visible contract:** inspect the exact assignment, prompt, JSON Schema, tool surface, diagnostics, and bounds seen by the model; runtime validators must not hide undiscoverable semantic rules.
- **Lifecycle and recovery:** test cancellation, timeout, retry, late activity, restart, finalization, compare-and-set failure, unknown submission, and idempotent reconciliation.
- **Plugin lifecycle:** installation, disablement, failed upgrade, rollback, duplicate registration, disposal, and capability disappearance leave no stale authority.
- **Bounds:** limits cover complete primary outputs, generated collections, wrappers, multibyte text, retries, and the final commit operation.
- **Human boundary:** chat cannot become approval; UI decisions bind the exact visible cohort; rendering cannot alter scientific bytes.
- **Real entry path:** exercise the packaged wheel, loader, MCP proxy, daemon, subprocess, or browser route that production uses.

## Demand meaningful evidence

Trace both sides of changed interfaces and every alternate caller that could bypass a facade, Schema, policy, or listener order. Require a negative control that fails through the intended real entry point. A green unit test, coverage percentage, or self-reported Agent result does not prove the scenario.

## Report findings

Lead with findings ordered by impact. Each finding must state the defect, tightest location, reachable scenario, scientific or operational impact, and concrete evidence. Separate blockers from improvements. Omit style issues already enforced by tooling.

If no defect is found, say so and identify the important paths actually inspected, tests observed or run, and remaining unverified production risks.
