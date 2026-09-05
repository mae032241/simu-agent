# Current Architecture

[简体中文](ARCHITECTURE.zh-CN.md) | English

This document describes the current R5-L Run-v1 architecture after the R5-M
simplification and R5-N scheduler-authority correction. Historical designs and
failed reviews remain under `docs/plans/`; the active implementation authority
is `docs/plans/R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md`, while
the R5-L and R5-M plans remain reviewed historical baselines.
The current charter and 33-constraint matrix live under `docs/architecture/`.

## 1. Design rule

The behavioral atom is an immutable, compilable `OperationSpec`. It is a
declaration of a behavior closure, not a giant class containing every
implementation. It declares ports, executor kind, component references,
limits, workspace, tools, network, review, approval, and effect requirements.
Narrow plugin components implement codecs, validators, guards, projectors,
workspace hooks, worker tools, and runtime factories.

Operation ABI 15 requires every Agent output to reference a structured semantic
contract. Each rule that is not expressible in JSON Schema has a stable
`rule_id`, description, output paths, and required inputs. Compilation rejects
unknown inputs and rules that silently make an optional port required. The
compiler embeds those rules and the mechanically derived schema, payload,
context, and revision validation contract in the same `result.schema.json` used
by submission. Every Python payload or context checker binds one declared
`rule_id`; submission executes that exact JSON Schema first and may then report
only a Worker-visible rule identifier and field path. There is no prompt-only
or submit-only second rule set.

The scheduler and expert Workers own scientific judgment. The control plane
owns identity, immutable records, least-context projection, lifecycle,
qualification, and effect gates. Deterministic code owns replayable mechanical
work. Domain adapters own side effects only.

## 2. Registration, compilation, and catalog views

The system has one entry-point group, `scidiscovery.plugins`. Each entry returns
one `PluginDefinition`; one distribution may currently publish more than one
plugin definition. A plugin declares one frozen component tuple and the
Operations composed from those components. Components have no separate entry
points, and Root or Worker code cannot rediscover private implementations by
Python path.

At startup, `compile_installed_catalog()` validates plugin identity,
dependencies, component closure and protocols, resource digests, Operation
ports and limits, structured semantic rules, permission templates,
review/provider edges, and approval contracts. It creates the single
`CompiledCatalog` containing frozen
implementations plus operation id, version, and digest.

`public`, `support`, `internal`, and diagnostic `all` are projections of that
one catalog, not separate registries:

- `public`: scientific actions selectable by the scheduler;
- `support`: deterministic helpers used by public actions;
- `internal`: framework tests and self-checks only;
- `all`: a diagnostic union.

Domain artifact kinds are format-constrained plugin identifiers, not core-owned
domain enums. Structured Worker findings and suggested next actions are sealed
scientific results, not scheduling commands. The scheduler selects an exact
Operation from the compiled catalog and unified preflight decides executability.

## 3. Scheduler and Operations

The interactive Root Agent reads immutable scientific inputs, the compiled
catalog, and bounded readiness advice. It selects the shortest defensible
public Operation from the current contradiction. Dependencies express
admission requirements, not a fixed stage DAG. Root binds instance-scoped
semantic Artifact names and calls the same `operation_preflight` used for
identity, qualification, review, budget, and side-effect gates.

A Worker does not emit an authoritative successor Operation name. The scheduler
may reason over sealed verdicts, domain dispositions, missing inputs, and
suggestions, but independently chooses the catalog Operation. `change_request`
and `review_signal` prove exact review and provenance relationships; they do not
declare a fixed stage or successor.
Legacy `next_action_kind`, `accepts_actions`, and `recommended_task_mode` fields
remain parseable compatibility data, but every control path ignores their
values. They are neither a second action catalog nor an admission condition.
A completed Run's `run_status` includes its validated sealed scientific payload
for this decision; running Runs and bulk `run_list` do not expose payloads. Review
sources used for change accept only non-passing verdicts, never `pass`. If the
Run's saved Operation version or digest no longer matches the compiled catalog,
status reports `contract_retired` without exposing the old payload or handoff.
The structured object is in `sealed_output`; bounded verdict, missing inputs,
and suggestions are in the same response's `scheduler_signal`. Every review
signal must bind an exact reviewed subject in the same call.
The producer's public catalog entry also exposes a minimal `review_edge`: the
review Operation, its subject input port, reviewed output ports, and accepted
verdicts. Independent review is therefore scheduled from the same compiled
catalog rather than a role table or second routing configuration.
Public producers may reference only public reviewers. If a reviewer is not
currently runnable, its producer is also absent from the available public view
and fails preflight. Root rejects internal Operations; support remains limited
to deterministic helpers for a selected public action.

Behavior is created through `operation_invoke`. The TCAD plugin
registers the device-parameter schemas, extraction/audit Agents, deterministic
coverage/uncertainty transforms, and qualification approvals as one vertical
slice; generic core neither imports that schema nor compiles parameter
Operations. The old role/transform entry points and direct task, transform,
approval, and execution creation tools are no longer product authorities.

For an Effect, the same `operation_invoke` creates the immutable execution
request and its exact pending loopback review from the compiled approval
contract. It returns the request-specific review URL but neither decides nor
starts the side effect. Only a sealed UI decision followed by explicit
`execution_start` and bounded `execution_sync` advances execution.

## 4. Four executor closures

### Agent Operations

The compiler projects an Agent Operation into a Run output contract, input
exposure, workspace, tools, limits, and review requirement. The parent uses
Codex `spawn_agent` without parent history. The child uses native capabilities
inside its task workspace together with the domain Worker MCP and expert
resources compiled for that Operation, then submits through the unified
lifecycle. A chat completion is an untrusted
transport signal; the sealed Run output is the scientific result.

`assignment.json` points the Worker to the structural, semantic, and validation
contracts embedded in `result.schema.json`. JSON Schema owns required fields,
types, enums, ranges, and basic nesting. The semantic contract only adds
cross-field or input-binding rules that Schema cannot express. A context
validator may consume only declared sources and cannot reinterpret an omitted
optional port as a Worker output error; doing so is a plugin contract failure.
Only an explicit `SemanticRuleViolation` from a payload or context checker may
report a Worker-correctable failure under the output port's bound `rule_id`;
the exception carries no independent rule identity. Every other checker
exception is a plugin contract failure.
File shape, size, paths, immutable parentage, and
authority remain sealing checks; scientific quality belongs to the declared
independent review Operation rather than hidden control-plane content rules.

The default Local path uses soft isolation. Control materializes the assignment,
output schema, explicit inputs, optional recovery draft, and domain working files
inside one Run workspace. The Agent may use native Codex file and code capabilities
for ordinary task-local work. Per-file reads and writes are not separately
registered Operation capabilities; OperationSpec declares extra domain tools,
network, or external effects. Editing a workspace copy cannot change its source
Artifact, and only a complete declared output that passes schema, parentage, and
submission validation can become a formal Artifact. This boundary controls
scientific context and formal publication, not host-level file visibility.
Deployment keeps formal Artifacts and control databases under the state root,
while the trusted-local Run workspace uses a separate Codex-writable project
path compiled identically into control and Worker processes. That workspace is
not a second state authority.

A direct revision is an ordinary Agent Operation with one `revision_base` input
and one complete output using the same schema, media type, codec, and schema
resource, plus an independent review contract. The base may be required, or it
may form one approval-free all-or-none optional group with the unique
`change_request`. The optional form lets the same Operation create an object
without that group and revise it when the group is bound, without a mode field
or a parallel revision Operation. Compilation identifies static revision
capability; runtime derives whether this exact call activates revision only from
its frozen inputs. Runtime uses
copy-on-write: ordinary JSON objects initialize `output/result.json` with the
exact base payload, while a declared domain workspace materializer (currently
the TCAD project path) is used only when paired with a finalizer that assembles
the result. The Worker edits only the reviewed fields, but submission still validates and publishes one complete
immutable snapshot; an unchanged payload is rejected. This reuses the
producer's Agent, workspace, tools, and validation instead of creating a
universal revision manager or patch-shaped scientific entity. The old object
remains immutable, and the new object inherits neither review nor
qualification. Optional revision must declare a bounded revision count and a
progress fingerprint. Catalog compilation rejects malformed `revision_base`
declarations. The former structured-patch Artifact, patch-application
Operation, diff receipt, retired Task projection, and recursive Root family
remain deleted.

There is one explicit prototype limitation. Codex may expose parent-visible
Worker MCP servers to spawned Agents. The compiled prompt names allowed and
forbidden domain tools and server-side handlers reject undeclared domain tools,
but native file capabilities follow the soft-isolation contract rather than a
platform-enforced isolation guarantee.
Documentation and qualification reports must not overstate this prompt
constraint as a sandbox fact.
The only connected dispatch path is currently `spawn_agent`.
The dormant process-isolation base and its focused tests now live under
`experiments/worker_process_v2/` and are not packaged as product code. Their
results are not production-isolation proof.

### Transform Operations

Transforms are deterministic and replayable: intake splitting, experiment
materialization, TCAD packaging, runtime attestation, curve-bundle construction,
and scoring. They consume exact Artifacts, emit content-addressed Artifacts, and
preserve parentage. A Transform cannot invoke a solver or invent a scientific
verdict.

A normal consumer may read one Transform output. A consumer that genuinely
needs every result of one invocation declares one optional
`complete_transform_family` in its own OperationSpec, naming producer-aligned
output and input ports. Root reconstructs and compares the family only from
frozen operation digests, invocation fingerprints, instance bindings, and
parentage; it does not read domain payloads. The declaration currently covers
one family and creates neither a family registry nor downstream knowledge in
the producer.

### Approval Operations

A plugin projector maps exact subjects into the core fixed `ReviewDocument`.
Root should not interpret a domain Schema. The UI renders fixed safe nodes,
escapes text, and offers bounded raw-attachment views. A human decision is
written only through the loopback UI and binds exact subjects, operation
identity, and contract digest. Producer families are derived from compiled
ports, invocation fingerprints, completed Run contracts, and exact parentage.
Direct revisions are reviewed as complete new output families; approval does
not recursively reconstruct a patch chain.

### Effect Operations

An Effect creates an exact side-effect request and separate UI authorization.
A domain adapter supplied by the compiled runtime factory then executes it.
The sole Execution lifecycle owns idempotency, state mapping, uncertain-submit
recovery, and raw-output registration. An adapter cannot mutate scientific
objects or approve itself.

## 5. Control and data planes

The default control plane has four independent kinds of facts:

- Artifact/CAS: immutable bytes, content digests, parentage, and instance names;
- Run: exact Operation, inputs, backend, `queued/running/completed/failed`, and receipt;
- Approval: exact subjects, options, and a human decision only when declared;
- Execution: effect request, authorization, submit, synchronize, collect, and recovery.

Run, Artifact, Approval, and Execution objects created through Operations carry
the compiled operation id, version, and digest. Ordinary user-ingested source
Artifacts may have no producer Operation. A Worker receives Run-local aliases
rather than internal Artifact, Approval, current-write, or external-execution
identities. Root does not manufacture Worker science, and Workers do not write
control metadata. The default `LocalTrustedBackend` owns only its workspace. The
existing `HardenedWorkerBackend` remains a non-default experimental/optional
implementation, but strong isolation is not a current product completion gate
and must not add protocol cost to default Operations, plugins, or Workers. It
currently has no controlled reader for a preinitialized result, so it rejects
direct revision Operations instead of advertising an unusable capability.

## 6. Generic and domain boundaries

| Generic core | Plugin |
| --- | --- |
| OperationSpec ABI and one-shot compiler | Operations and narrow components |
| Artifact, Run, Approval, Execution lifecycles | Domain Schemas, validators, guards, projectors |
| Root MCP, Run lifecycle, workspace backends | Expert prompts, workspace hooks, domain tools |
| Fixed safe review document and UI | Review projection, never HTML or scripts |
| Generic preflight/invoke | Transforms, runtime factory, effect adapter |

The TCAD plugin registers deck author/reviewer Agents, project workspace and
debug tools, packaging/attestation/control-equivalence Transforms, and the
solver Effect. The curve-score plugin registers curve contracts, canonical
curves, scoring, and diagnosis. The optional curve-figure-evidence plugin
registers paper-figure extraction, independent review, and their tools while
reusing the curve plugin's deterministic algorithms. Core does not recognize curve
manifests, fixed script names, or figure collections; native and domain tools
are projected from the compiled Operation.
The InGaAs Fig.4 project plugin registers only its frozen project scorer. No
plugin may duplicate control-plane identity or lifecycle state.

Each deterministic Transform component consumes exact bytes grouped by input
port and produces its complete output family atomically. Relations among
multiple outputs are closed inside the trusted plugin component that owns the
algorithm. The generic invoker enforces compiled schema, media type,
cardinality, and per-item validators before registering immutable Artifacts
with the same input parentage; it does not interpret domain bytes or branch by
plugin, Operation, or Schema. Agent primary-output context validators instead
receive only the input sources and tool receipts explicitly declared by their
OperationSpec and may replay deterministic algorithms at submit time.
This is not a second registry, state object, or scientific decision hook.
Agent collection declarations compile, but Run v1 does not invoke them as
formal submissions. Optional capabilities requiring collection submission are
omitted from the current backend's `public` scheduling view and remain visible
with a reason in the diagnostic `all` view.

## 7. Explicit current limitations

- The default Local backend deliberately uses soft isolation. Native Codex file
  visibility is not a technical sandbox; `SEC-002` remains a known issue but
  does not block the trusted-local prototype milestone.
- Run v1 accepts one Agent primary result. Agent Operations declaring collection
  outputs are uniformly unavailable and fail preflight closed; Transform
  multi-output remains supported.
- The historical Hardened-v1 implementation supports MCP-only Operations. The
  current milestone neither extends nor completes it and does not require it to
  pass.
- The approval UI safety contract is covered, but its information hierarchy and
  visual readability still need product work.
- Current tests establish engineering boundaries and one TCAD vertical slice,
  not paper-digitization accuracy, solver scientific validity, three-domain
  universality, or statistical superiority to a single Agent.

R5-L adds no scientific graph, plugin lifecycle system, second registry, second
current, or fixed scientific workflow.

## 8. Persistence and trust

Runtime state lives outside source and temporary directories. SQLite stores
control lifecycle, CAS stores immutable payloads, and service secrets remain
separate. ResearchInstance and semantic bindings are the sole runtime current;
the installer does not read a standalone YAML current. Generated platform
configuration contains machine-specific absolute paths and must be regenerated
per machine.

Orphaned historical binding rows are not synthesized into `legacy.*`
ResearchInstances and cannot enter instance listings, session current, or
session-binding candidates. No online migration or compatibility entry is
added for them.

Worker prompts, task directories, and JSON validation provide context-level
soft isolation, not a complete system sandbox. Enforced boundaries are exact
input binding, output sealing and validation, Artifact registration,
independent review, human approval, and effect authorization—not a control-plane
record for every task-local read. Effect policy still limits executable,
arguments, environment, resources, and inputs. Scientific acceptance still
depends on provenance, independent review, deterministic reports, and result
diagnosis.
