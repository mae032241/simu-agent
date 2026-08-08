# Architecture

[简体中文](ARCHITECTURE.zh-CN.md) | English

## Design Rule

SciDiscovery separates scientific creativity from state authority and external
side effects. The root Agent chooses work; it does not manufacture the output
of a configured role. Workers own scientific content. Deterministic code owns
mechanical transformations. The control plane owns identity and lifecycle.

## Layers

### 1. Interactive scheduler

The Codex or Claude root process interprets the user's objective, reads bounded
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
only the payload, then derives a bounded scheduler signal from `handoff`.

Generic roles include evidence extraction, ideation, criticism, evidence audit,
experiment design, and diagnosis. The TCAD plugin adds deck author, reviewer,
and reviser roles.

### 4. Deterministic transforms

Transforms perform operations that should not depend on Agent judgment:

- split reviewed intake objects;
- derive eligibility and knowledge-update records;
- apply bounded deck patches;
- compare complete projects and emit immutable diffs;
- validate an exact review against an exact project;
- create reviewed packages and runtime attestations;
- run domain scorers.

Transforms cannot invoke a simulator or invent physical parameters.

### 5. Execution bridge and domain adapters

An exact reviewed payload becomes one `ExecutionRequest`. Human authorization
is bound to that request. The bridge invokes a configured adapter and maps its
states into the control-plane lifecycle. A TCAD adapter may run locally or use
the SSH transport, but it cannot change scientific objects or approvals.

The remote runner is dependency-free Python and implements only bounded file
transfer, detached submit, short status/cancel, and terminal collection. SSH is
never used as a long-lived scheduler connection.

## Human Interaction

The loopback approval UI displays the exact frozen subject. Decisions are
written directly to the control service; the conversational Agent cannot forge
or translate a chat message into an approval. Current review types include
instance binding, scientific foundation approval, and execution authorization.

## Generic and Domain-Specific Boundaries

| Generic core | Domain-specific extension |
| --- | --- |
| Artifact, approval, task, instance, and execution services | Simulator project Schema |
| Root and worker MCP protocols | Deck author/reviewer/reviser prompts |
| Role envelope and common scientific Schemas | Packager and runtime assertions |
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
