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

Operation ABI 17 requires every Agent output to reference a structured semantic
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

Experiment proposals retain an ordered `objectives` list and a nonempty exact
`current_objectives` subset. Materialization includes the original overall
objective in each proposal and expands only the declared current cases. Existing
rationale fields preserve the selection reasons, remaining goals, and future
conditions. Designers and independent reviewers assess whether omitted targets
prevent the current experiment, including targets sharing an observable. Curve
contracts use explicit target bindings when requested; local success does not close
uncovered overall targets. Curve scoring is an optional tool of result analysis,
not a prerequisite for authoring or execution. Generic and TCAD result analysis
are alternative Operations. The TCAD analysis tool parses bound raw outputs and
scores in the same Run; unsupported scoring limits a quantitative conclusion but
does not prevent a partial analysis. Exact plan, review, execution, file, and case
identity checks apply even when no scoring tool is called.

Observable descriptions are scientific prose, not a second identity registry.
Design, materialization, review, and curve compilation do not require repeating
them verbatim. An explicit comparison baseline key identifies the baseline
without a duplicate case-role label. Compact intent can omit that key when
exactly one declared baseline/control supplies it; ambiguity remains a located
missing input. Unknown cases and contradictory variable values remain errors.

Legacy detailed experiment-design output contracts require `validation_intent`; the obsolete
`validation_plan` branch and its exclusive definitions are not shown to authors.
Historical intents use a dedicated input reader at the existing materialization
boundary, preserving the original exclusive-choice and experiment-identity checks.
Reading compatibility neither rewrites old artifacts nor renews qualification.
Reader and writer share the current scientific fields and constraints; the output
Schema and submission model come from the same definition.
The precomputed curve-diagnosis writer declares an empty calculation-record tuple;
its Schema therefore omits unreachable calculation-record definitions. General
analysis and historical readers retain their existing record support.

## 2. Registration, compilation, and catalog views

Scientific actions have one entry-point group, `scidiscovery.plugins`. Each entry returns
one `PluginDefinition`; one distribution may currently publish more than one
plugin definition. A plugin declares one frozen component tuple and the
Operations composed from those components. Components have no separate entry
points, and Root or Worker code cannot rediscover private implementations by
Python path. The optional browser-only `scidiscovery.instance_views` group loads
pure presentation mappings; it registers no actions, tools, or scientific admission rules.

At startup, `compile_installed_catalog()` validates plugin identity,
dependencies, component closure and protocols, resource digests, Operation
ports and limits, structured semantic rules, permission templates,
review/provider edges, and approval contracts. It creates the single
`CompiledCatalog` containing frozen
implementations plus operation id, version, and digest.

The existing declarations also compile the static Worker tool schemas and output
contracts once. Catalog, assignment, MCP and submission reuse these projections;
Run aliases are added to detached copies. Static material excludes its own digest
before the existing identity envelope is computed. Root and lifecycle tools retain
their own declarations and share strict JSON argument parsing and diagnostics.
Preflight/invoke own input admission. Submission checks outputs and their claims
against frozen evidence; it does not repeat input eligibility checks.

Source references resolve against exact control-owned input aliases and tool records; they
need no second registration in an output evidence table. Optional citation tables add
locators and scientific source descriptions. Repeated citations, multiple locators and
unused bound sources do not block a whole result. Qualification verifies complete frozen
subjects and independent review lineage, rather than copied citation ledgers. Analysis can
cite saved calculation files directly; receipt and execution/case identity checks still apply.
Declared model and semantic rejections retain bounded specific reasons without echoing
whole inputs, exception chains or tracebacks. Unknown engineering failures remain separate.

Public errors carry bounded code, phase, path, message, repairability and affected
action. Immediate replies and durable activity use the same safe details. Unknown
checker exceptions are engineering failures. Opted-in scoring tools record attempts
before parsing, including rejected and interrupted calls, in the existing Run
activity and sealed evidence manifest. A failed calculation can explain a limit;
it cannot establish a successful quantitative check. Scientific Agents and independent
reviewers judge claim scope, necessary checks and the impact of missing evidence.
Validators do not derive scientific verdicts from a fixed checklist or prescribe case
counts from scientific/engineering labels. Historical calculations use paired manifests
and full Artifact identities to verify provenance. Evidence collection receipts and
scientific case-mapping claims stay distinct. New computed records require controlled
receipts; submission does not rerun scoring.

`public`, `support`, `internal`, and diagnostic `all` are projections of that
one catalog, not separate registries:

- `public`: scientific actions selectable by the scheduler;
- `support`: deterministic helpers used by public actions;
- `internal`: framework tests and self-checks only;
- `all`: a diagnostic union.

Domain artifact kinds are format-constrained plugin identifiers, not core-owned
domain enums. Structured Worker findings and suggested next actions are sealed
scientific results, not scheduling commands. The scheduler selects an exact
Operation from the compiled catalog; invoke checks admission before creation.
Preflight is an optional check without creation, not an authorization or reservation.

## 3. Scheduler and Operations

The interactive Root Agent reads immutable scientific inputs, the compiled
catalog, and bounded readiness advice. It selects the shortest defensible
public Operation from the current contradiction. Dependencies express
admission requirements, not a fixed stage DAG. Root binds instance-scoped
semantic Artifact names and calls `operation_invoke` directly. Control enforces
identity, qualification, review, budget, and side-effect gates before creation;
`operation_preflight` remains an optional read-only check of the same request.

A Worker does not emit an authoritative successor Operation name. The scheduler
may reason over sealed verdicts, domain dispositions, missing inputs, and
suggestions, but independently chooses the catalog Operation. `change_request`
and `review_signal` prove exact review and provenance relationships; they do not
declare a fixed stage or successor.
Legacy `next_action_kind`, `accepts_actions`, and `recommended_task_mode` fields
remain parseable compatibility data, but every control path ignores their
values. They are neither a second action catalog nor an admission condition.
A TCAD implementation gap may include control-captured bounded
source, declarations, attempt notes and diagnostic files. These remain negative
development records, not an executable project. Review and revision both accept
this result; revision restores diagnostics under `reports/history` and requires
fresh completion proofs. Legacy gaps with no captured files remain readable but
cannot reconstruct an earlier failed source. Diagnostic excerpts retain their
existing truncation bounds; the gap still obeys the Operation output byte limit.
The trusted-local Worker router can claim a new queued Run of the same compiled
Operation after its previous Run terminates, clearing all per-Run tool state.
Codex may reuse an idle matching Agent; different Operation IDs or compiled digests, catalog
generations and independent review of its own work require a fresh Agent.
Agent memory grants no permission to access old workspaces or use unbound facts.

Framework-owned diagnostic logs follow one rule: retain bounded original files,
derive display excerpts separately, and locate errors before display truncation.
TCAD runners keep merged stdout/stderr in `worker.log`; a separate diagnostic
file includes bounded solver `.log` and `.err` files for development and production.
Capture limits report incomplete coverage instead of silently deleting log content.
Development Workers receive a full bounded redacted file path and may read line
ranges; captured logs travel with implementation gaps. Replies remain short and
debug time budgets are unchanged. Launcher, transport and PDF failure diagnostics
are retained in their existing run/result directories. This is file-based reading,
not a new logging service or a grant to read unbound historical workspaces.
A completed Run's default `run_status` provides a bounded summary excerpt;
`view=detail` with omitted `output_paths` returns the complete sealed original. `output_paths=[]` returns status, exact bindings, signal and output metadata
without reading the payload. This default `compat` profile preserves existing clients.
An explicit request-time profile avoids assembling unrelated context: `poll` requires
an empty values selection, `navigation` returns a bounded index without signal text,
and `decision` returns requested exact values and the signal only after completion.
Compact failed responses retain exact safe diagnostics and a mechanical recovery-gate
projection; full bindings, native/tool records and recovery detail remain available
through the compatibility detail path. Explicit payload JSON Pointers return exact values in
`selected_output`, never a partial `sealed_output`: up to 8 paths and 32 KiB of values.
Pointers start inside the payload: `/summary`, not `/payload/summary`. An empty
pointer selects the whole payload; `/` selects an empty key. A `selected` value
is exact and can be used directly, including when it is the whole payload; only
unread information needed for a decision requires another fetch.
Oversized subtrees have bounded direct-child navigation (32 entries, 8 KiB total);
missing, null and omitted values remain distinct. Full reading is always available
by omitting the parameter. Signal availability is independent of payload delivery.
Running Runs and bulk `run_list` do not expose payloads. Review
sources used for change accept only non-passing verdicts, never `pass`. If the
Run's saved Operation version or digest no longer matches the compiled catalog,
status reports `historical` and returns the sealed payload and parseable handoff
without renewing qualification. Missing producer installations also leave completed
records readable; an unavailable handoff does not hide an independently verified
payload. `scheduler_signal_status` reports that limitation separately. Inventory
and Worker input descriptions explicitly mark historical context.
`evidence_inventory` permits historical reading. `prior_signal` and `revision_base`
may cross producer versions when the current port can consume the same type;
structured historical JSON is validated against the consumer input Schema before
creating a Run. These rules apply to input usage, not executor kind. Exact
independent review and revision subjects remain mandatory, and cross-version
revision history does not reset revision limits. Sealed scientific records and
reviews remain consumable when their Operation id/version and output port type
(schema, kind, media) are compatible; runtime digest drift alone does not revoke
the original object's proof. Scientifically incompatible changes must advance the
existing Operation version or schema. A new object cannot inherit an old review,
and an incompatible reviewer requires a new review of the exact old subject.
Historical producer families preserve their original identity and must
still prove all sources, members and unambiguous port bindings when requesting a
new human decision. Historical blocked/revise signals retain nonclaiming labels
through deterministic transforms. Research input qualification may reuse a sealed
human decision for its original subjects when provider id/version and the existing
approval contract digest match. This does not create a decision or renew a Run.
Run continuation and external execution/approval retain full compiled identity
checks; the provider matching service is strict by default and never relaxes
execution authorization. History flags and original provenance digests are retained.
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

Design and plan review can bind optional `current_progress`, `experiment_results`,
and `result_analysis` originals: zero to four Artifacts per group, up to 8 MiB
each, within the original 32 MiB input allowance plus the user-text allowance below. These are `on_demand` read-only
`evidence_inventory` files. Only Agent inventory inputs skip producer-output
qualification admission; instance, size, current, family, cohort, claim, revision,
and effect gates remain in their existing paths. Wildcard schema/media pairs are
limited to inventory with `handoff_only` or `on_demand` exposure. Reading history
does not restore retired qualification. Deck review treats its exact project as
`prior_signal`: incomplete implementation may receive a negative review, while
passing review, packaging, and execution retain their implementation requirements.

Root's `artifact_ingest_text(name, text, on_conflict)` registers 1–8,192 valid
Unicode code points as exact UTF-8 bytes, including whitespace and line endings.
The immutable `opaque` text records `source_origin=user_via_scheduler` separately
from its content and retains the actual caller as creator. Registration uses the
existing instance name, fingerprint and revision mechanisms; it creates no Run.
All public scientific Agents declare an optional `user_context` port for up to
four originals, each at most 32,768 bytes. Its `prior_signal`/`on_demand` usage
does not create evidence qualification or consume `current_progress` slots;
131,072 bytes are added to each Agent's original aggregate input allowance.
Assignment and analysis navigation expose the original path and recorded origin.
The Agent judges the text's scientific meaning; control requires no adoption form.

All inputs remain in output provenance. Exact saved producer input ports distinguish
formal sources from background for evidence revision and parameter qualification;
Root and scheduling's authoritative reconstruction project the same stored bindings.
The projection is neither a second persistent record nor a new scientific claim.
Continuing a completed node creates a new Run with explicit original inputs. Failed
work with changed inputs uses `draft_from`; `resume_from` retains exact input and
contract identity. User text cannot replace an independent review or UI approval.

Analysis Workers start with `analysis-start.json`: an input size/purpose index,
verbatim excerpts and exact original field pointers. TCAD adds a bounded project
and scientific case matrix in `analysis-bindings.json`. Control-generated case
binding ledgers remain in immutable originals and server-side tool inputs; they
are not default reading or reporting tasks. The combined TCAD display budget is
32 KiB, with original pointers and omission counts when details do not fit.
Views do not become scientific evidence or change source identity, qualification,
or native filesystem permissions. Reused Agents verify the new bindings and read
relevant current originals; they need not reread every complete input file. The full
continuation guidance lives in `analysis-start.json`, and report instructions in the
workspace `patch_contract`; analysis role prompts provide short navigation.

Local Worker open returns the frozen assignment tool-contract path and pointer
independently of analysis navigation. Workers read the selected tool contract before
use, including its complete Schema and local definitions. Old assignments without
contracts retain their frozen fallback; Hardened retains inline contracts. Corrupt
assignments are engineering errors, never permission to substitute newer contracts.
TCAD authors put initialization coverage and untested reset paths in source comments
before their final source-bound diagnostics, so the reviewer receives and independently
checks those statements with the sealed project. Comments are not execution proof.

`LayeredDiagnosisReport` concentrates conclusions in `summary` and `overall_verdict`,
with evidence and optional `limitations`. Its complete legacy `gates` object,
remaining contradiction, next action and hypothesis assessments are optional. For
new outputs of the supported generic, fixed curve-error and TCAD analysis producer
versions, an exact scoped plan with a non-null `objective_key` requires the existing
`objective_assessment`; a null key keeps it optional and does not authorize inventing
one. This is a producer context rule, not a v1 reader or prior-admission migration.
`claim_allowed` remains an explicit scientific judgment; absent numerical gates
project to `not_evaluable`. For these analysis reports, the existing finalizer
creates handoff verdict and a short reference to the formal summary before sealing.
The workspace `patch_contract` declares draft omissions; Root reads the sealed
payload and scheduler signal together. TCAD, generic and fixed curve-error analysis
share this behavior on their supported local backend. Old Artifact bytes remain
unchanged; these reading and delivery changes do not add a scoring prerequisite.
The scheduler distinguishes the completed Run's scope and sealed facts from its own
value judgment under user cost constraints. Reported next actions remain advice, not
catalog authority; stopping further work does not rewrite an inconclusive or invalid
study into physical refutation and requires no persistent route state.

ScientificReview, DeckReviewReport and ImplementationGap also author their formal
summary once. Their finalizers fill omitted handoff verdict/summary, retaining explicit
legacy notes; the sealed envelope Schema stays strict. Generic review Schema descriptions
and TCAD workspace patch contracts explain draft omissions. New author templates omit
mechanical placeholders; gaps may omit the handoff file, while complete projects still
require their authored handoff. An impossible projection reports its formal source field,
so an invalid verdict or summary can be corrected in the same Run. CriticReview and
EvidenceAudit still require their own handoff summary; old sealed records are unchanged.

`artifact_catalog(name=...)` returns ordered `parent_artifact_names` for the exact
Artifact: `[]` without parents and `null` for a parent without a current-instance
binding. Names resolve the stored parent identity, never the latest revision;
aliases use the existing first-created/name order. More than 4096 direct parents
causes an explicit error. The query neither writes state nor recursively searches
history. A new scheduler follows plan revisions to the materialized plan's typed
parents to recover its original objective, then explicitly binds relevant context
to the next Worker. This continuation path adds no progress object or stage machine.
The `producer_inputs` view first projects one immediate producer's frozen port/item
mapping and exact refs from the same producer-family record used by admission. It
does not recurse or select replacements. Historical, cross-instance, unavailable
and ambiguous producers remain explicit and carry a `parents` fallback; frozen names
outside the current instance are not exposed.

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

`execution_sync` refreshes solver state and bounded logs, including terminal
executions. `execution_status` reads saved observations without contacting the
adapter. Artifact transfer starts only with explicit `execution_collect`;
`execution_outputs` publishes names after collection. One daemon-owned collection
slot consumes a frozen total budget (600 seconds by default), with cleanup
reserved inside it. A private control guard holds the locks until its single work
process group has stopped, including after daemon exit; transport programs do not
own those locks. Duplicate active requests retain that budget; another
execution receives busy without being queued. Complete files and a stable output
manifest survive interrupted collection and registration. Adapters implement
transport only, optionally consuming the common `CollectionContext`; they do not
own another scheduler. Query, file and idle defaults are 5, 120 and 30 seconds.

Engineering failures use one bounded, redacted diagnostic projection. Root reads
details by an instance/session-scoped `diagnostic_read` reference; Workers retain
their own readable workspace reports. Existing Run activity also supplies MCP
timing. Local trusted workspaces share an optional process-observation launcher:
analysis retains its existing execution policy, other roles inherit their prior
environment and limits. Missing or damaged observation is reported explicitly
and never adds a scientific submission requirement.

Error observations append to existing Run activity even after the deadline or
terminal state; they do not renew a budget, reopen a Run, or accept a result.
Each MCP call's start and finish belong to the same Run, including when an idle
Worker opens its next assignment. An open failure after selection belongs to
that selected Run, preserves its cause,
and cannot return the previous Run's completion as the new call's outcome.
`run_status` retains a compact default summary; `diagnostic_after=0` requests
the first saved error page, with `next_after` as the
continuation cursor and `diagnostic_limit` bounded to 100. `run_list` returns
`next_before` for its optional semantic-name `before` cursor. Both queries stay
instance-scoped. Historical events without details remain explicitly incomplete;
pagination does not reconstruct information that was never recorded.

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

Local analysis workspaces preserve a versioned, bounded subset of `output/` and
`scratch/` on failure. The immutable recovery copy and pending original-directory
cleanup are distinct: failure does not prove native writers stopped. Unconfirmed
writers, unsupported files and original logs keep the directory retained. Ordinary
tracebacks can be delivered as normalized copies; bytecode caches are excluded.
Recovery remains provisional and never inherits scientific qualification.

An optional stdlib launcher is materialized from the installed core package into
the analysis workspace. The Worker executes it locally; it is not a server tool.
It bounds logs and numerical-process resources and clips each requested timeout
to the absolute Run deadline minus an adjustable submission reserve. Root reads
only bounded timing/status metadata. Unobserved execution remains unknown and
does not block submission. Analysts save complete numerical units atomically and
retry plotting from saved data; optional rendering failure cannot erase numbers.
`run_status.bound_inputs` and ordered `artifact_catalog.parents` project exact
bindings without selecting replacements. TCAD plan/review ports retain original
execution identity; newer analysis plans and reviews use `current_progress`.

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

Codex registers one `scidiscovery` MCP exposing `scid_catalog`, `scid_describe`
and `scid_call`. Discovery returns names and purposes; selected contracts are
read on demand and calls delegate to the existing Root/Worker handlers. Operation
describe defaults to the compatible full contract and also exposes an `invoke` view
projected from that same compiled item. It retains digest, complete input/admission,
review, revision, attempts and runtime applicability while omitting executor details
that cannot change a legal call. Interface describe remains full-only.
After spawning, Root uses `worker_attach` to bind the returned child thread ID
to the exact queued Run, then asks the child to begin. Server routing consumes
platform session/thread metadata, not a caller-selected role or Run.
Bindings live in the Run database and follow instance archival. Thread reuse
requires the same compiled Operation, model and reasoning effort for the new Run.
Native files, shell and Skills retain their existing soft-isolation limits;
this is not a security boundary against a hostile user sharing the OS account.
The only connected dispatch path is currently `spawn_agent`.
The legacy `run_compiled_codex_worker.py` direct-CLI probe explicitly rejects
new unified profiles; it is not a production dispatch path.
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
curves, scoring, and diagnosis. TCAD result analysis composes its own raw-output
parsers with the curve plugin's deterministic scoring functions without a reverse
dependency. Final analysis validation verifies tool receipts, calculation records and
exact source references without rerunning scoring. Raw evidence cites bound aliases;
calculation evidence cites returned records without repeating their case mappings.
Read-only binding descriptors distinguish same-content output files by their registered
identity. The optional curve-figure-evidence plugin
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
OperationSpec to verify output references and record integrity. They neither recheck
input readiness nor decide scientific conclusions.
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
- The approval UI now provides structured parameters, evidence and original-file
  links. Post-deployment Fig4 reading still requires separate acceptance; synthetic
  page checks do not substitute for it.
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

TCAD analysis may optionally inspect files from its bound terminal execution and accept explicit output mappings. Registered tools preserve the original bytes and durable receipts in Run-owned Artifact collections; frozen inputs remain unchanged. The report and exact evidence snapshot complete together. Root exposes ancillary semantic names only after completion; a later Run binds the recovery manifest and raw files explicitly and can replay original calculation aliases. Missing inspection services or old runners allow limited analysis. Solver exit status and collection errors remain separate; recovery never rewrites the old execution or grants scientific success.

## 9. Instance browsing, trajectory and storage maintenance

The existing approval UI serves instance overviews, nodes, source figures and
management. `InstanceReadModel` follows exact instance bindings and frozen parent
references. General and TCAD presentation providers map existing values into
source-linked text, parameter tables and safe figures. Unknown fields, missing
sources or presentation failures remain display gaps, never Worker rejections.
Browser read access, maintenance access and original approval tokens have separate
scopes; pages do not change approval subjects, deadlines or decision authority.

One bounded UI observer polls node metadata while subscribed and sends SSE
locations and cursors. Results load on demand. The UI-owned
`state_root/ui/workbench.sqlite3` stores rebuildable views and actual observations;
source timestamps remain separate from observation timestamps. Missing telemetry
is never invented. Browsing and caches neither start scientific Runs/executions/
collection nor add Agent handoff fields.

User-confirmed archive maintenance moves exactly owned instance data into the
workspace's `.scidiscovery-archive/instances`. Shared active copies and files with
unknown ownership remain in place and are reported. Read-only archives retain
original identities and bytes. Restore does not rebind old sessions, restart
processes, promote qualification or extend approvals. Permanent deletion is not
provided. A durable maintenance gate covers Root, Worker, approval writes and the
full collection writer lifecycle; unknown native quiescence preserves the files
and prevents migration.

A global `run_activity_sequence` allocator in the Run database preserves activity
rowids across archive/restore. Normal activity writes allocate inside their
original transaction. This counter stays outside instance snapshots so another
instance cannot reuse archived event IDs. Scientific schemas, Operations and tool
contracts remain unchanged. Directed archive transactions restore original
append-only triggers; the maintenance journal is not disposable UI cache. See the
[implementation record](plans/evidence/instance-workbench/IMPLEMENTATION.zh-CN.md)
for scope, failure evidence and deployment limits.

## Native capability profiles and external evidence

Root startup instructions come from `roles/scheduler.md`: core authority, approval,
binding and bounded-reading rules plus a conditional reading index. Detailed guides
in `roles/scheduler/` ship in the wheel and install under `.codex/scidiscovery-guides/`;
the generated prompt records their absolute directory. Root reads the relevant guide
before its action and refreshes after deployment. Guides are not additional roles,
tools or routing authority, and are not appended to catalog/describe responses.
They do not change Worker instructions or scientific admission. Installation preserves
unmanaged project prose and verifies guide availability in each generated profile.

Local workspaces include the read-only `tools/read_tool_contract.py`. It reads only
the frozen assignment's tool contracts. The reader owns a disposable scratch receipt
of its last complete response; callers supply only the tool name. Related reads can
return a lossless JSON Patch against that full response, never another patch.
Changed assignment/workspace/contracts, missing or stale receipts and larger patches
fall back to full text. Use `--full` after context loss: a delivery receipt cannot
prove the model still retains the base. Receipt failures do not reject scientific work.
This adds no MCP capability, contract registry, scientific state or authority, and
changes no executable schema or scientific output. Old workspaces retain direct
reading; Hardened permissions do not gain native execution.

Local workspaces also provide `tools/read_output_schema.py`, a read-only view of
`schema/result.schema.json`. It retains envelope/payload structure and all shared
rules, expands required references and selected `--field` closures, and lists exact
pointers for unexpanded definitions. `--definitions-only` supplements a retained
current overview; `--full` returns the original. This view is not a validation schema.
Nested resource IDs and recursive local references are resolved against that same
file; unsupported/dynamic/external references fall back to full reading, with an
explicit reason. The CLI keeps disposable schema-reading metadata under `.read-input/` to avoid
repeating the overview and shared definitions; repeated `--field` options are merged.
Later reads supplement retained sections, while `--full` restores originals after a
lost reply or context loss. Missing/corrupt/unwritable caches fall back to a complete
required view. The cache is not scientific state or proof of memory. Schema refreshes
are read on every call. Unsupported envelope shapes and old workspaces retain full reading.
The submit validator and all scientific fields remain unchanged.

Local workspaces also install `tools/read_input.py` for exact text/JSON-pointer
reading with a 4 KiB default and 8 KiB maximum complete reply. Callers select a
bound source alias or unique input port, optionally repeated `--pointer` fields;
`--file` selects explicit task-local files such as assignment or schema. Replies
contain exact text and short end/continuation markers, not escaped fragment wrappers,
paths, hashes or offsets. Numeric lexemes remain exact; fragments are not complete JSON.
Installed input/schema readers alone maintain disposable reading metadata under `.read-input/`,
outside output/scratch recovery scanning; other helper caches remain in scratch.
After specifying a selection, bare `--next`, `--repeat` and `--restart` reuse its
file/alias mode, pointers and budget. Explicit reads switch the current selection;
failed reads do not. Use `--repeat` for an uncertain latest reply or `--restart`
when earlier material is missing; missing navigation requires an explicit selection. Locks protect cache
updates, not delivery order or proof of reading. The cache does not cross Runs or
become scientific state. It detects changes since that selection's first read,
not mismatches against a sealed-input hash; control retains input binding/initialization.
Old workspaces receive a targeted direct-reading hint without rewriting frozen helpers.
This helper neither limits arbitrary native shell output nor adds submission gates.
Analysis launchers default to a short observation with retained log paths; explicit
`--display raw` preserves stdout data consumers, and native inherit policy keeps
its raw default. Capture remains bounded separately from display. Recovery status
summarizes coverage and omission counts; `run_status(view="detail", output_paths=[])`
retains the original omission list.

Codex platform roles group identical declared `NativeToolPolicy` values (shell,
image viewing, web search). Scientific Operations retain their identities and
contracts. The generated role is a lifecycle bootstrap; each assignment provides
its compiled `role_instructions`, including on Agent reuse. Control checks matching
Operation/compiled digest/frozen profile at attachment and actual model/effort at
the Worker gateway; the Agent does not compare role hashes. Local open derives
`reading_guidance` from the preceding thread binding and actual old/new role, schema
and tool-contract bytes, without a new registry. It identifies unchanged contracts
for reuse only while retained; unavailable originals require reading. Dynamic schema
changes are compared separately from compiled identity. Control-admitted reuse
also receives input equivalence derived from persisted immutable bindings and usage
descriptors: unchanged, changed, new or unknown, with aliases only. This is navigation,
not a reading ledger or memory claim; incomplete history falls back to unknown.
Reassessment may reuse retained originals, with targeted rereading for missing context
or scientific verification. Exact originals and the overall objective remain available.
No submission gate depends on these hints. Control-admitted reuse
permits skipping reprinting only while complete instructions remain in context;
first use, uncertain continuity or context loss requires reading. Each new task, objective/input binding,
language and budget must still be read. Worker MCP capabilities
still come only from the attached Operation. A shared platform role does not permit
cross-Operation reuse or independent review of that Agent's own work. Installation
removes obsolete managed role files without rewriting historical Runs or Artifacts.

`science.evidence.extract.v1` declares live native web discovery and the optional
`worker_capture_source` capability. Captured public HTTPS originals enter the existing
tool-evidence store with automatic aliases, URL and retrieval time. They are external
sources, not derived simulation results. The source manifest and exact originals may
be bound to intake audit and bounded revision. Discovery snippets are not preserved
scientific evidence; unavailable sources limit the claim. Existing fixed-source
extraction and review Operations do not gain search permission implicitly.

Capture limits are eight originals, 16 MiB per original, and 24 HTTP requests per Run
including redirects. Transfers, DNS and redirects are bounded; failed attempts retain
engineering diagnostics. Native web discovery remains governed by the Run budget and
platform policy, not this HTTP counter. Trusted-local filesystem restrictions remain
prompt boundaries; native profiles do not create an additional OS sandbox.

## Execution preferences and scientific contracts

Global defaults are loaded once at service startup; sparse instance overrides live on scheduler instance rows. One resolver merges instance Operation overrides, instance defaults, global Operation overrides, global defaults, then Operation compatibility defaults. Narrative language is instance-wide. There is no second model registry or automatic model fallback.

Invoke resolves and freezes configuration during creation. Optional preflight produces a complete `normalized_request` that callers can reuse unchanged; it does not reserve dynamic admission conditions. Each new Run freezes model, reasoning effort and narrative language; behavior values participate in request identity while source annotations do not. Scheduler dispatch, Worker assignment and UI project that snapshot. Submission never rereads current preferences. Language affects newly authored prose only, preserving identifiers, code, units, quotations and required exact copies; output validation does not enforce language. Existing recovery policy remains the attempt authority: explicit values win, recovery inherits its saved scheduler budget, and new instance defaults do not extend a chain automatically.

`ExecutorRef.model` and permission model retain their legacy compiled-digest role as compatibility defaults. Runtime overrides never recompile scientific Operations. Generated Codex roles omit fixed model/effort; dispatch supplies both explicitly. Agent reuse requires the same Operation ID and compiled digest, compatible native profile, and known matching actual model/effort, while preserving independent-review rules. New assignments supply language. Unknown configuration is not a match; interruption is not closure.

Only four additive columns are introduced: `scheduler_instances.agent_settings_json`, `agent_settings_revision`, `agent_settings_updated_at`, and `runs.execution_profile_json`. Historical NULL means unrecorded. Legacy archive bytes remain immutable. Restore projects exactly these installation ALTER definitions, using fixed NULL/0 for absent values, through preview, transactional import and interrupted completion. Unrelated schema/index/trigger or record conflicts remain rejected. Cache cleanup does not remove execution settings. No new scientific artifact, state machine, translation role or model-specific role pool is introduced.

For new supported SProcess studies, `science.experiment.skeleton.v1` delivers scientific
comparisons, criteria and frozen conditions without mandatory engineering cases. The
author writes a concrete `ExperimentPortfolio` inside the sole project output and
performs authorized development validation. `tcad.execution-plan.project.v1` extracts
that same plan unchanged for downstream ports; it grants no qualification. An optional
early skeleton review does not replace the independent comprehensive project review.
Packaging and TCAD analysis bind the exact project, projected plan, skeleton and
comprehensive review. Legacy detailed plans retain their separate scientific review
witness; legacy SDevice and other plugins keep their existing contracts. Production
approval and execution permissions are unchanged. Scientific semantic conflicts are
resolved before repeated implementation searches; equivalent local engineering choices
remain with the author. Fixture checks do not establish model behavior or token savings.
