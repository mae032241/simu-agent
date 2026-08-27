# Architecture

[简体中文](ARCHITECTURE.zh-CN.md) | English

## Design Rule

SciDiscovery separates scientific creativity from state authority and external
side effects. The root Agent chooses work; it does not manufacture the output
of a configured role. Workers own scientific content. Deterministic code owns
mechanical transformations. The control plane owns identity and lifecycle.

## Layers

### 1. Interactive scheduler

The Codex root process interprets the user's objective, reads bounded
readiness signals, chooses the shortest defensible role topology, and dispatches
ready work. It uses semantic names and never handles internal Artifact, task,
approval, session, execution, or external-run identifiers.

### 2. SciDiscovery control plane

The control service owns:

- immutable content-addressed Artifacts and provenance;
- ResearchInstance-scoped semantic bindings;
- task creation, assignment instances, attempts, leases, and terminal state;
- context profiles and input exposure (`full`, `on_demand`, `handoff_only`);
- exact human approvals and process-to-instance binding;
- execution requests and returned-output registration.

It does not decide scientific truth or write simulator decks.

#### Scientific qualification kernel v2

New ResearchInstances use one fail-closed authority model:

- `OperationIntent` admits an exact immutable request before work starts;
  `OperationReceipt` publishes the complete usable result, while
  `OperationTerminalRecord` closes a permanently failed or cancelled request.
- `ScientificReviewIntent` freezes one exact visible subject set. The local UI
  decision is interpreted as a `ScientificReviewOutcome`; only an accepted
  outcome can issue an instance-scoped `QualificationReceipt`, and withdrawal
  is append-only.
- `ActiveHead` is the sole current-object authority. Revision order, completion
  time, labels, parent links, and historical approval do not implicitly make an
  object current.
- External execution uses a durable effect outbox and explicit unknown states;
  an uncertain submission is reconciled instead of resubmitted.
- Readiness and authorization call the same contract preflight over exact
  receipts, qualifications, head snapshots, parameter uncertainty, and adapter
  availability.

Every semantic publication is recoverable from the immutable request
fingerprint. Maintenance reachability includes intents, receipts, reviews,
qualifications, heads, reservations, and effect-outbox records. Closing a v2
instance is rejected in the same database transaction while any of those
recoverable operations remains unfinished.

The protocol version belongs to each ResearchInstance. Migrated v1 instances
remain readable but reject new scientific mutations; requalification happens
in a newly created v2 instance rather than by silently inheriting legacy
authority.

### 3. Scientific workers

Each role receives one identity-free assignment with task-local input aliases,
a bounded resource contract, and an exact JSON Schema. A worker may read only
the assigned files and tools. It returns a universal `RoleResultEnvelope`:

```json
{
  "schema_version": 1,
  "handoff": {
    "verdict": "pass",
    "summary": "Bounded scheduler signal",
    "assumptions": [],
    "missing_inputs": [],
    "next_actions": []
  },
  "payload": {}
}
```

The payload Schema is role-specific. The control plane validates and registers
only the payload, then derives a bounded scheduler signal from `handoff`. For a
scientific-paper-evidence bundle, the handoff must bind the deterministic
fingerprint of the exact staged collection bytes. The control plane projects
the final figure summary, manifest ambiguities, and required audit action from
the validated manifest/report instead of trusting mutable extraction prose.

`worker_materialize_assignment` returns exact local paths for native read-only
inspection. Worker mutations never use broad filesystem write grants: a
session-bound MCP file service applies context-checked unified diffs or bounded
chunked file creation only within the role's declared task-relative paths.
Validation and finalization freeze the resulting controlled tree.

Generic roles include evidence extraction, ideation, criticism, evidence audit,
experiment design, and diagnosis. The TCAD plugin adds one deck author role for
both initial authoring and bounded revision, plus an independent code reviewer.

For new tasks bound to an exact SProcess capability and experiment plan, the
author may edit only `deck/files/**` and the bounded handoff. `project.json`,
case/global bindings, units, source locators, the realization manifest, raw
output contract, capability identity, arguments, and resource policy are
control-owned read-only projections. A versioned TCAD materializer derives the
canonical project from the exact plan, capability, and current source before
validation or debug, returning reason-coded findings with case, variable,
file, and line. Comments cannot stand in for executable bindings, and
scorer/diagnosis controls never enter the deck contract.

### 4. Deterministic transforms

Transforms perform operations that should not depend on Agent judgment:

- split reviewed intake objects;
- derive eligibility and knowledge-update records;
- expand a worker-authored `ExperimentDesignIntent` from sparse baseline values
  and case overrides into the complete strict `ExperimentPortfolio`, including
  exact case settings, comparison expectations, factor inventories, case
  counts, and a source-bound materialization report;
- freeze the author's controlled project tree and compare complete revisions;
- materialize TCAD case bindings, units, manifest, locators, raw-output
  contracts, and a source digest from exact source;
- compare complete projects and emit immutable diffs;
- validate an exact review against an exact project;
- record a source-bound bounded preflight attestation; reviewers neither copy
  capability digests nor restate manifest rows or self-assert syntax passage;
- create `tcad.reviewed-deck-package.v2` objects bound to a solver-capability
  and the exact experiment plan, rejecting missing scientific case-control
  bindings before execution;
- materialize trusted realization snapshots and compare control equivalence;
- validate case coverage and SProcess-to-SDevice dependencies in typed
  `StudyExecutionPlan` DAGs;
- stage content-addressed binary inputs and create layered runtime
  attestations;
- run domain scorers.

Transforms cannot invoke a simulator or invent physical parameters.
The intent remains a provisional scientific object and cannot be selected as
the current experiment plan. Only the materialized full portfolio may enter
deck authoring, scoring, packaging, or diagnosis. Legacy complete portfolios
remain readable and selectable; new experiment-design tasks use the compact
contract by default.

Direct SProcess/SDevice decks stop at solver code and raw TDR/PLX/PLT/log
outputs. They do not resample curves, apply evidence masks, calculate derived
metrics, evaluate thresholds, or emit scientific verdicts. The execution
bridge checks lifecycle and immutable raw-output integrity; a versioned domain
scorer computes deterministic post-execution values; diagnosis interprets
those values. Contextual finalization validators compare deck-author and
deck-review outputs with their exact project inputs so an unsupported or
post-execution deck duty cannot receive a formal passing review and fail only
later during packaging. Packaging re-materializes the exact source against the
exact plan and capability, then requires a passing preflight for that source
digest and an independent code/physics review.

### 5. Execution bridge and domain adapters

An exact reviewed payload becomes one `ExecutionRequest`. Human authorization
is bound to that request. The bridge invokes a configured adapter and maps its
states into the control-plane lifecycle. A TCAD adapter may run locally or use
the SSH transport, but it cannot change scientific objects or approvals.

The remote runner is dependency-free Python and implements only bounded file
transfer, detached submit, short status/cancel, and terminal collection. SSH is
never used as a long-lived scheduler connection.

Production TCAD adapters accept only reviewed-package v2. The package, JobSpec,
and runner policy bind the same capability digest. A change to the executable,
fixed arguments, environment, solver kind, or release evidence fails before a
solver starts. Binary inputs such as SDevice TDR files are staged only through
content-addressed ArtifactRefs and exact project slots; workers never embed
them in JSON.

## Human Interaction

The loopback approval UI displays the exact frozen subject. Decisions are
written directly to the control service; the conversational Agent cannot forge
or translate a chat message into an approval. Current review types include
instance binding, scientific foundation approval, and execution authorization.

The page is not generated by AI. Agents and workers produce schema-validated
structured Artifacts; fixed Python renderers in `approval_ui/render.py` select
allow-listed views, escape content, and assemble HTML. Unknown structures fall
back to bounded generic tree/download views and cannot provide HTML, JavaScript,
or template code.

Quantitative evidence extraction, revision, and independent audit form one
provisional chain. Intermediate versions are not separately approved. One
final scientific-evidence review covers the accepted ScientificFoundation,
extraction result, all attachments, and final audit report. Execution
authorization remains separate because it permits an external side effect.

The dashboard also provides ResearchInstance management and per-instance
approval history, including the selected option, rationale, and decision time.
Deletion requires an impact preview, the exact instance name, and a one-time
token; active tasks or executions block it. Exclusive task, approval, execution,
and Artifact registrations are removed, while cross-instance objects remain.
Artifact registration and deletion share a cross-process file lock. Exclusive
CAS bytes are unlinked only when no retained registration uses the same digest;
an offline orphan scan still reports bytes left by interrupted operations.

## Generic and Domain-Specific Boundaries

| Generic core | Domain-specific extension |
| --- | --- |
| Artifact, approval, task, instance, and execution services | Simulator project Schema |
| Root and worker MCP protocols | Unified deck author/revision and reviewer prompts |
| Role envelope and common scientific Schemas | Solver project and reviewed-package validation |
| Platform configuration generation | Tool allow-list and transport |
| Context isolation and web-evidence freezing | Domain scorer or baseline transform |

No domain plugin may duplicate control-plane identity or lifecycle state.

## Persistence

Runtime data lives outside the source tree, normally under
`/var/lib/scidiscovery`. SQLite stores registries and lifecycle state; a CAS
stores immutable payloads. Service secrets live under `/etc/scidiscovery`.
Generated platform configuration contains absolute local paths and must be
regenerated on each machine.

Source migration and research-state migration are independent. The optional
ActiveResearchBundle exporter moves explicitly selected, identity-neutral
scientific Artifacts; it does not restore tasks, approvals, sessions, or
executions.

## Trust Boundary

- Worker prompts and JSON validation improve correctness but are not the
  security boundary.
- The control plane binds identity, immutable inputs, and state transitions.
- The local approval UI binds human decisions to exact subjects.
- The domain execution policy allow-lists executables, arguments, environment,
  resource limits, and input roots.
- Scientific acceptance still requires evidence, preregistered checks, and an
  independent result diagnosis.
