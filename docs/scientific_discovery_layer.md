# Scientific Discovery Layer

Date: 2026-08-04
Status: P0-P5 source implementation complete; production deployment pending

## Purpose

The production SciDiscovery/TCAD path already owns immutable storage, exact
approval, identity-free worker dispatch, deterministic packaging, detached
execution, result collection, and terminal diagnosis. The discovery layer adds
scientific meaning without moving scientific decisions into that control plane.

```text
ScientificFoundation
        -> HypothesisState
        -> ExperimentProposal + ValidationPlan
        -> reviewed implementation and execution
        -> ValidationReport
        -> KnowledgeUpdate
```

These are immutable scientific Artifacts. The root scheduler chooses the next
task dynamically; the sequence above is not a fixed workflow graph.

## Ownership

- Scientific workers author scientific content and expose assumptions.
- Deterministic validators check schemas, references, units, declared
  applicability, metrics, and state-projection consistency.
- SciDiscovery assigns identity, freezes content, isolates task context,
  records approvals, and owns task/execution lifecycle.
- Domain adapters prepare, submit, inspect, cancel, and collect solver jobs.
- Humans approve the exact scientific foundation, execution request, or claim
  promotion when the scheduler identifies that gate.

## Implemented Scientific Objects

### P1 ScientificFoundation

`ScientificFoundation` is the human-reviewable input to downstream hypothesis
work. Each `EvidenceItem` declares:

- a local semantic key and item type;
- epistemic status;
- statement, value, and unit where applicable;
- scientific scope and applicability conditions;
- uncertainty when available;
- exact local evidence keys or an explicit non-factual rationale.

The object also declares sources, conflicts, missing inputs, and open
questions. Deterministic validation rejects:

- a parameter without a value or unit;
- a source-backed fact without evidence;
- an inference, assumption, or speculation without rationale;
- duplicate or unknown item/source references;
- inconsistent conflict resolution state;
- a web citation without a task-local frozen web snapshot.

The evidence extractor returns this specialized schema directly. The
existing approval UI renders its objective, grouped items, values, conditions,
scope, uncertainty, sources, conflicts, and unresolved questions in Chinese.
The generic raw tree remains available for complete inspection.

### P2 HypothesisPortfolio

The ideator returns a bounded portfolio rather than free-form prose. Each
hypothesis declares its mechanism, prerequisites, parameters, observable
predictions, explicit falsifiers, competitors, evidence impact, current status,
and support level. Deterministic validation closes all local references and
requires calibratable parameters to have a declared range. It does not assign
confidence or rank ideas on the worker's behalf.

### P3 ExperimentPortfolio

The experiment designer returns controlled cases, frozen invariants,
hypothesis-linked prediction tests, resource estimates, stop conditions, and a
pre-registered three-dimensional validation plan. A deterministic ordinal
score checks the declared priority ordering using evidence support,
discrimination power, information gain, cost, and added parameters. At least
one baseline or control is mandatory.

### P4 ValidationReport

The diagnostician reports numerical, physical, and experimental validation
separately. Threshold checks are evaluated by deterministic code; qualitative
checks remain explicit reviewed judgments. Reports bind the exact experiment
and plan, cite task inputs or frozen web evidence, cover every required check,
and cannot claim success when an active dimension fails.

### P5 KnowledgeUpdate

The diagnostician records evidence-bound judgments for the hypotheses actually
tested. Deterministic control code consumes that validation report and the
frozen hypothesis portfolio, then emits explicit transitions and the remaining
contradiction as `KnowledgeUpdate`. No extra Agent interprets the result a
second time. The object distinguishes five outcomes:

- supporting evidence from a numerically valid passing study;
- contradicting evidence from a numerically valid failed prediction;
- a valid but inconclusive study;
- an invalid numerical study;
- a hypothesis not tested by the study.

Rejection requires a pre-registered falsifier. Numerical failure cannot count
as physical contradiction. Support or rejection marks the exact update for
human review. `project_knowledge_state` replays an ordered chain and rejects
unknown hypotheses, broken update chains, and stale prior states. Both
deterministic operations preserve the diagnostician's judgment and add none of
their own.

## Source Acceptance

- P5 focused schema, cross-input, projection, and platform tests: 20 passed.
- Full source regression, including cross-object discovery-chain checks: 156 passed.
- Existing root and worker lifecycle interfaces are unchanged.
- No TCAD execution was submitted and no scientific model was accepted.

## Next Gate

P6 deploys these role definitions and exercises one bounded Fig.4 SProcess
loop from frozen foundation through hypothesis, experiment, reviewed deck,
real execution, validation, and knowledge update. A separate full five-layer
Device realization remains mandatory before any dark-current production run.
