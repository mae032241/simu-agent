# Current Architecture

[简体中文](ARCHITECTURE.zh-CN.md) | English

This document describes the current generic plugin platform and complete research
tasks. See the [public implementation and validation status](RELEASE.md#current-status).
Historical plans and audits describe their recorded candidates; they do not override
current contracts. Static implementation does not establish runtime acceptance.

## 1. Design rule

The behavioral atom is an immutable, compilable `OperationSpec`. It is a
declaration of a behavior closure, not a giant class containing every
implementation. It declares ports, executor kind, component references,
limits, workspace, tools, network, review, approval, and effect requirements.
Narrow plugin components implement codecs, validators, guards, projectors,
workspace hooks, worker tools, and runtime factories.

Operation ABI 23 requires every Agent output to reference a structured semantic
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

Root chooses complete evidence, hypothesis, experiment or analysis tasks according
to the research question. These are responsibility categories, not a fixed pipeline
or four resident Agents. `science.experiment.v1` owns design, implementation, local
debugging, execution, collection, validity and delivery in one Run. TCAD is a domain
capability of that task. Normal stages require no independent review or approval;
applicable qualification and execution authorization remain explicit contracts.

An experiment invocation may explicitly set `require_execution_review=true` when
its task requires independent implementation review before formal execution. New
tasks default to false; recovery inherits a true requirement and cannot remove it.
Control resolves the latest completed independent review of the exact sealed
implementation and requires `pass` under a compatible review contract. Diagnostic
runs remain available. Workers neither enter review IDs nor receive a new global
review gate. Revised implementations require their own review.

Public tool evidence receives its exact artifact name atomically with its sealing
receipt, before the owner Run finishes. Final submission reuses that same binding;
failed owners do not erase sealed material or confer a passing qualification.
Stage queries expose these names without writing bindings. `run_status(intent="navigation")`
also returns a bounded evidence page for active and failed Runs; continue with
`evidence_outputs_next_offset` as `index_offset`. Status polling returns no evidence list.
Private control packages
and manifests are not published by this path. Preparation returns a review request
when required; `worker_experiment_execute(action="review", implementation=...)`
also supplies the exact subject and a scheduler invocation, including for older
sealed receipts. It dispatches no reviewer and creates no execution. A formal
reviewer must still differ from all authors, including authors of running tasks.

Queued Worker attachments may be corrected by calling `worker_attach` again before
the assignment opens. Opening verifies the current native thread binding within
the state transition transaction; a running assignment cannot be rebound.

Bound experiment reports expose their adopted stages through the existing paginated
reference tool. A collected execution stage resolves named original files from its
exact sealed result manifest, including media type and size. Reading these files
does not take over the execution or grant access to other runs.

Execution budget responses explain allowance shared by the research instance.
Abandonment refunds an unused reservation only after confirming no external
submission exists; uncertain submission lookup preserves the reservation. Reservation
history remains recorded. Diagnostic failures distinguish exhausted budgets,
preparation failure, unknown submission, status failure and collection failure,
without returning private backend exception text.

A task seals scientific stage conclusions and material references as work proceeds.
The UI reads the same stage projection, without dispatching work. A stage preview is
not final completion: the final report identifies adopted stage versions and their
remaining limitations. Control verifies exact scientific sources, actual collected
execution and adopted implementation; it does not impose a fixed scientific checklist.

The experiment owner may use an optional native helper for a meaningful bounded
subproblem. It starts with fresh context and the owner's native permissions, Skill
access and task workspace. Worker tools admit only the prepared child of that owner;
helpers cannot select instances, dispatch Root tasks, seal owner stages, submit the
parent result, or supply a formal independent review. The owner waits and integrates
findings/files before releasing helper access. Default admission is one active helper
and one layer, with a cumulative call allowance across recovery. Releasing Run tool
access does not stop native tools or prove thread exit; native wait/stop/close and
model usage remain platform responsibilities. The framework does not claim a hard
aggregate memory or token cap for those native threads.

Result analysis may invoke domain scoring and parsing in the same task. Calculations
retain exact input and tool-evidence identity; unavailable scoring limits the
quantitative conclusion rather than forcing an author/reviewer dispatch chain.

Scientific progress uses the same terminal-consumption ledger. Optional compiled
Operation declarations project source-bound Worker judgments into a common
contract, preserving stage report types and exact original inputs. A generic
research cycle counts its interpreted exact experiment once; completed hypotheses
and experiments await interpretation, and waiting creates no attempt. Missing
assessment, repeated interpretation and explicit no progress remain distinct.
First scientific dimension changes can advance the observation window without
claiming independent scientific verification; deterministic/review test proofs
remain stronger evidence. New files, report identities and changed thresholds
alone cannot reset it. The automatic confirmation pause, immutable trigger history,
user continuation and exact accepted-work/review authority retain their budgets.
Experiments own one answerable question and a bounded comparison protocol, with
scope and stopping reasons in existing task/stage narratives. The experiment owner
designs and declares the protocol before execution, preserving supplied constraints;
criteria and condition range need not be pre-existing admission inputs. Related
trials, repetitions and candidate contrasts, including baselines across sealed
hypotheses, can continue within that protocol and its original criterion/range. Keep each
attempt's results/limits and the best eligible candidate under the original
selection criterion. Seal for independent analysis when sufficient, without further
scientific progress, or at budget/permission boundaries; changed mechanisms, criteria
or scope need a new scientific decision. Cheap computation does not authorize wider
search. Preserve unmet overall requirements. Reuse an unchanged portfolio and exact
engineering materials; check a minimal saved-model/code loading chain early when
delivery needs it. These instructions add no fields, gates or budget extensions;
their throughput benefit requires live qualification.

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

Residual diagnostics now save a controlled numerical checkpoint before rendering.
The same Worker tool accepts `checkpoint_alias` for a plot-only retry: request,
algorithm and complete input Artifact identities must match, and the checkpoint
must be current or control-adopted evidence. It never reads an editable workspace
copy as a checkpoint. Rendering failure preserves computed metrics, saved residuals
and specific diagnostics; a computed status does not claim that plots were produced.
Failure continuation reuses the existing receipt adoption path. Changed scientific
inputs/methods require new computation; report corrections remain inside the current
Run until sealing. Previously sealed reports remain immutable.

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
The deprecated `next_action_kind`, `accepts_actions`, and `recommended_task_mode` fields
and their forwarding paths have been removed; strict models reject these extra fields.
Scientific suggestions use `next_actions`; the compiled catalog owns action authority.
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
`run_status` has one `intent`: `decision` (default), `status`, `navigation`, or
`full`. Decision returns bounded declared conclusions, limitations, remaining
questions and scheduler signal after completion. Choose top-level `output_fields`
or exact non-root `output_paths`, never both; omission or `[]` selects declared
fields. Status reads no scientific payload; `diagnostic_after=0` explicitly starts
safe terminal diagnostics. Navigation lists bounded exact output paths and the
frozen visible scientific input names. Full explicitly returns complete sealed
science only after completion, with no output selection or private control records.
Active Runs stay short; explicitly requested sealed stage previews retain their
own pagination and never establish final completion.

Root interface declarations also own their surface: ordinary `research` omits the
10 standalone execution interfaces. Select `surface="execution"` consistently in
`scid_catalog(kind="interfaces")`, `scid_describe`, and `scid_call` for independent
Effect execution or historical recovery. This is one declaration projection, not
another Operation registry or authorization. Task-managed execution stays with
`worker_experiment_execute` while its owner or any recovery descendant is active.
When every owner has failed or sealed a limited experiment conclusion, the execution surface and lifecycle events
expose the original execution for status, sync, logs, collect and outputs, plus
state-appropriate explicit start, abandon or cancel. Starting reuses the exact request,
implementation and approval; it checks the frozen task contract, required independent
review and current execution policy. Uncertain submissions use authoritative lookup.
This creates no new Run or retry and never marks the failed scientific Run successful.
Internal Operations remain inaccessible. UI reads execution/collection state directly.

Selected JSON Pointer values appear in `selected_output`, never a partial
`sealed_output`: at most 8 paths and 32 KiB. Paths start inside the payload, for
example `/summary`, not `/payload/summary`. The empty root pointer is forbidden in
decision intent; `/` denotes an empty member key. Exact selected values need no redundant
fetch. Oversized subtrees provide bounded direct-child navigation (32 entries,
8 KiB); missing, null and omitted values stay distinct. Whole-output reading always
requires the explicit full-output flag. Signal availability is separate from payload
expansion. Compact failures retain safe diagnostics and recovery information; a
failed Run does not become completed scientific evidence through a larger view.
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

Scientific tasks bind relevant original evidence and prior results through their
compiled scientific input ports. Inventory is read-only context; reading historical
material does not renew its qualification. Mechanically derived ports remain hidden
from Agent contracts, assignments and input files; control resolves their exact
origins from the declared scientific anchors. Missing or ambiguous origins produce
located repair diagnostics, not additional identity forms for the Agent.

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

Every local owner Worker starts with `worker-start.json`, derived from its frozen
assignment and the domain workspace manifest. It supplies the complete task/role,
input index, language, budget, revision/recovery instructions, authoring-form
navigation and domain read/edit rules in one entry. It does not preload tool
contracts or scientific originals. Long entries can use the existing paginated
input reader; instructions are never silently truncated. The entry is a disposable
projection, not another task record, permission source or submission gate.

When visible input aliases bind the same exact immutable ArtifactRef, later entries
carry `same_source_as` pointing to a safely shared readable representative. The
default startup index expands shared paths, types and sizes only on that entry,
retaining each alias's purpose, provenance and citation permissions. The reader
shares pagination for the same field selection; selecting another alias returns
a short notice and remaining character count without advancing the page. Cache
does not prove that the Agent read the material: `--repeat` restores the last page
and `--restart` rereads from the beginning. Different fields stay independent;
explicit restart recovers damaged navigation. Equal names or hashes do not
establish equivalence. Hidden, handoff-only, metadata-only and file_reference
inputs cannot become shared reading bridges; file_reference still uses controlled
streaming tools. Without a safe representative, reads stay independent. This
navigation projection merges no bindings, qualification or source identity and
does not truncate scientific originals.

`analysis-start.json` is optional navigation for input size/purpose, original field
pointers, verbatim excerpts and recovery coverage. It no longer repeats task,
output, tool-contract or continuation instructions. TCAD additionally provides
`analysis-bindings.json` for the project and scientific case matrix. Their combined
navigation budget is 32 KiB, with original pointers and omission counts. Internal
case binding ledgers remain in originals and control tools. These views do not
change source identity, scientific qualification or filesystem permissions.

Local open retains the frozen tool-contract path for on-demand reading; selected tools also use
`scid_describe`. Helpers retain their separate subtask and selected inputs, without
owner instructions or the owner's form unless their task needs it. Corrupt
assignments are engineering errors, never permission to substitute newer contracts.
TCAD authors put initialization coverage and untested reset paths in source comments
before their final source-bound diagnostics, so the reviewer receives and independently
checks those statements with the sealed project. Comments are not execution proof.
The TCAD implementation form excludes `expected_outputs` and `collect_generated_outputs`.
Control captures process logs and discovers solver-generated files within the declared
resource budget, producing their paths, sizes, hashes and references from actual files.
Authors do not repeat PLX/TDR output paths in a separate table; analysts select collected
materials and explain their scientific meaning. Log aliases in existing sealed declarations
are mapped only at the transport boundary, preserving the original, review subject and
authorization. Collection alone does not establish scientific success; analysis must
still report missing target observations.

Execution receipts distinguish direct control parents from inherited scientific
inputs in the private evidence manifest. Result lookup uses that exact link; older
receipts may exclude inputs proven by their original frozen manifest, but ambiguity
is never resolved by recency. Asynchronous collection is explicitly reported as
pending delivery. Subsequent task status and pre-finalization reconciliation create
the same idempotent execution receipt once results have been collected, including
collected results from cancelled or failed executions. A terminal state alone does
not create a receipt or trigger collection.
Final delivery refreshes solver status before reconciling collected receipts. A
successful execution without collected results, or a terminal execution with an
active/uncertain collector, blocks finalization. A definitively failed, timed-out or
interrupted collector with no active recovery permits a blocked/inconclusive report
with nonempty limitations, never completed or a fabricated collection receipt.
A stopped failed/cancelled execution can still support a limited report. A collector finishing during refresh is reconciled
in that same submission attempt. Status observation never implicitly starts collection.
When every owner has failed or sealed a limited experiment conclusion, Root may
recover the original execution's status/results. Later collection cannot rewrite
the sealed report; new conclusions need a new delivery based on those results.
Any queued or running owner still prevents takeover. Limited completed owners permit
result recovery only; starting an unsubmitted request still requires an entirely failed
owner lineage, the original review and execution authorization.
Read/export accept exact output identifiers or verified solver-relative filenames.
Finalization identifies missing chain edges and lists bounded available aliases,
without selecting scientific validity on the Worker's behalf.
Initialization diagnostics automatically publish their verified native files through
streamed attachments; no output path declarations are needed. These remain diagnostic
materials, not formal execution receipts. A missing expected output does not prevent
retention of other generated files; collection errors and terminal failure remain explicit.

Reading and replaying a sealed calculation use the same exact producer receipt and
parent bindings, independent of whether its owner is running, failed or completed.
Publication freezes one private reference proof per material; later reads reuse it
even if the owner adds evidence. Historical materials create this proof once on first
access. Parent derivation filters against the declared schema, media and size contract
before checking cardinality. For historical implementations without `control_parents`,
only the original producer's exact frozen inputs may be excluded to resolve a package;
unresolved ambiguity remains an error.

Evidence admission builds its proof from the receipt transaction's captured records
before committing the receipt and public binding. Proof failure rolls back admission;
an identical retry also repairs a historical receipt missing its proof. A CAS proof
left by an interrupted transaction is reused only if its exact subject receipt still
matches, so a later alias allocation cannot adopt an orphan's binding.
Current attempts are read through that same SQLite connection, and immutable recovery
origins are verified before taking the write lock; no second Run-database reader waits
on the receipt transaction. Per-material proofs retain the declared dependency closure
and matching calculation attempts, including exact recovery namespaces, rather than
unrelated later receipts. Existing proofs retain their original bytes. Legacy missing
proofs can be repaired even when the whole Run exceeds snapshot limits; a genuinely
oversized dependency closure returns `reference_proof_limit` without truncation.
The aggregate input/receipt/access binding map has no additional 128-entry gate.
Per-collection and per-attempt limits remain; all writers and recovery/finalization
use the same 1 MiB encoded-manifest budget. New receipts check the complete snapshot
before committing, while identical receipt retries reuse their fixed proof. Oversize
legacy data receives an explicit diagnostic to preserve materials and continue from
selected exact sources, not an opaque runtime error or a silently truncated proof.
Reference proof failures still settle the response/time reservation; an assignment
proof failure terminates the Run while retaining originals. Explicit adoption and
recovery copying validate the complete combined proof before committing. Final
submission uses one error policy from reconciliation through finalization, proof
construction, checking, candidate acceptance, Artifact registration and completion.
Temporary storage/connection failures preserve the Run and allow unchanged retry;
correctable output errors remain declared rejections. Irreparable proof limits and
verified integrity failures terminate the task with retained evidence, drafts and
explicit Root recovery instructions. Unknown exceptions retain engineering traces
and require intervention, without classifying them as scientific failure or advising
automatic retry. A draft may be preserved without a publishable proof; its
`evidence_proof_unavailable` marker never grants scientific validity. Idempotent
publication keys and accepted candidate identity survive interruptions. A committed
completion is never reversed by an optional post-commit failure. Attachment
streaming and Artifact registration finish before taking the Run write lock; the
transaction rechecks state, quotas and the complete proof. Unbound immutable objects
left by rejection are reused by publication key, never treated as accepted evidence.

Within the v5 storage generation and current ABI25 declarations, the binding-limit
revision retains one explicit predecessor contract: the catalog
recompiles the original 128-binding schema and complete output contracts, accepting
an in-flight identity only when its old digest matches exactly. Old output remains
subject to that old contract. Failed predecessors may explicitly recover to the
current widened contract without rewriting original task, draft or proof identities.
Catalog `recorded_operation` resolves exact ID/version/digest for Run producer families,
derived inputs, historical Transform interpretation and approval UI review relationships.
Root reports `current`, `supported_historical` or `unavailable` separately from output
availability. New invocations and current scientific qualification retain current-policy
checks; historical availability grants no authorization. These readers share the resolver,
so a supported predecessor can complete and supply downstream inputs after upgrade.
Tests exercise exact predecessor reads, old-contract completion, and both draft and
resume recovery. The actual 964713f ABI23 golden digests remain preserved, but that
deployment's unmarked/older state and archives are rejected by the existing breaking
upgrade policy; this is not an ABI23 migration or recovery path. Original bytes remain
readable when explicitly supplied as materials, without current qualification or an
invented historical review edge. Other contract differences are not ignored; unknown
digests remain unavailable.
Budget-extension accounting maps known record/integrity failures to a repairable UI
conflict; unexpected technical errors retain their traceback in server logs and return
the ordinary service-unavailable response without sealing a decision.
Grant validation and projection resolve one frozen budget owner from exact policy
history, even when its current pointer is missing; conflicting history is rejected.
Reauthorization also checks that history, so losing a pointer cannot change the pool.
Approval forms use 400 for malformed fields, 403 for access denial, and 409 for
known execution/record conflicts. New zero-extension decisions omit the optional
field; already sealed explicit-zero decisions preserve their bytes. Nonzero grants
still require a grant-aware reader when downgrading.
Parent derivation uses original control receipt edges when present, verifying their
membership in the immutable envelope. Without those edges, only exact producer input
parents can resolve historical ambiguity; no unadvertised kind constraint is invented.
UI presentation accumulates direct parents only until its byte budget is reached,
retaining an explicit omission marker instead of building the entire list first.
New receipts also retain exact derived_from parent references. Historical empty
control_parents can recover those edges from the original producer's exact sources;
empty must not silently mean no ancestry. An execution without a wall-time allowance
is reported as ineligible for time extension, rather than as corrupt control state.

New curve scores identify the support-aware algorithm as `curve-operators.v2` or
`analysis-curve-operators.v2`. Historical v1 calculations still require exact source
bytes and full numeric replay. Compatibility accepts the pre-shared-support bundle
digest only when no shared support is declared; it never accepts changed metrics or
rewrites the sealed record. Changed historical metrics require a new calculation.

`LayeredDiagnosisReport` concentrates conclusions in `summary` and `overall_verdict`,
with evidence and optional `limitations`. Its complete legacy `gates` object,
remaining contradiction, next action and hypothesis assessments are optional. For
new outputs of the supported generic, fixed curve-error and TCAD analysis producer
versions, `objective_assessment` is optional. When supplied, it must use the exact
scoped plan’s non-null `objective_key`; a missing key never authorizes inventing one.
`claim_allowed` remains an explicit scientific judgment; absent numerical gates
project to `not_evaluable`. For these analysis reports, the existing finalizer
copies the formal summary and derives the handoff verdict before sealing.
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

For an Effect, `operation_invoke` creates an immutable execution request. A compiled
contract may explicitly allow administrator policy authorization. TCAD requests
within both configured storage and wall-time limits are authorized without a human
approval record; other requests require the configured human decision or are denied.
Execution policy separates the per-request wall-time threshold (`max_wall_time_seconds`,
3600 in the example config) from the cumulative research-instance threshold
(`max_total_wall_time_seconds`, 21600). Both are administrator configuration. Queued
or uncertain work reserves its requested limit; terminal runner observations settle
actual elapsed time, rounded up to seconds, independently of storage observations.
At terminal state, missing observations are charged at reserved limits as explicit
estimates, not claimed actual use; later measured values replace those estimates.
Terminal jobs awaiting accounting remain in bounded background synchronization, including
collected jobs. Preparation failure before a saved submission releases its reservation;
an uncertain submission retains it. Repeated settlement never refunds recorded usage.
A current policy increase changes the ceiling without resetting historical consumption.
Execution approval pages can optionally append a human-chosen cumulative wall-time
extension when authorizing the exact request. The signed decision binds the increment;
an idempotent durable ledger applies it to this executor/scientific-subject pool across
revisions and restarts. Per-request thresholds, storage limits and usage are unchanged.
Reject/cancel decisions cannot extend budgets. Archive/restore retains these grants,
and interrupted projection is repaired by an identical UI retry or execution authorization.
Installation agent settings bound new extensions with
`budget_extensions.max_seconds_per_decision` (default 21600 seconds) and
`budget_extensions.max_total_seconds_per_pool` (default 86400 seconds of additional
grants). Zero disables new grants. Validation counts both projected grants and sealed
decisions awaiting projection; a short control-side lock serializes validation,
decision sealing and projection. Lowering these settings does not invalidate an
already sealed grant. Historical decisions preserve their original canonical bytes,
including both omitted and explicit-zero extension fields. These administrative
limits are shown in the approval UI, not added to Worker forms.
Grant accounting selects exact requests from the pool's durable policy history and
reservation records before loading unprojected decisions. Missing current policy
pointers do not erase sealed grants; an unreadable decision blocks only its relevant
pool with an explicit UI conflict. Projected grants use their retained ledger rows.
Approval UI separates the requested increment, per-request threshold, cumulative balance
and overage; a negative balance is never presented as this request's available time.
The install transaction fills a missing cumulative threshold from the bundled config
and preserves explicit administrator settings, including on the remote runner.

Development diagnostics use `debug.budget_scope` (`task` in the example configuration).
Task accounting includes the complete control-bound recovery family.
`scientific_subject` explicitly shares diagnostic usage across the research instance;
neither setting changes the formal execution instance pool.
Both modes keep immutable submission records and separate actual terminal time from
outstanding reservations. Before new admission, known submitted jobs are refreshed to
settle completed usage. Limits still come from `debug.total_wall_seconds` and
`debug.max_runs`; errors identify their scope and the administrator setting needed for
recovery. A missing exact lookup does not prove that an earlier submit has stopped:
socket timeout leaves server processing alive, and the remote job directory may not
exist yet. Diagnostics report `submission_unknown`; cancel and formal abandon reject
unconfirmed retirement and retain the exact identity and reservation. Retry the same
diagnostic status or recover the same formal execution, then cancel the confirmed job.
Even a genuinely absent request stays reserved until permanent retirement can be proven;
formal execution cancel/abandon uses the atomic retirement protocol described below;
diagnostic recovery still requires a confirmed job. Approval expiry releases only
never-prepared requests. Renaming or recovery never resets
the current task's usage; changing scope does not delete historical accounting.
Validated retained receipts reconcile the original diagnostic to `collected` and settle
their trusted elapsed time idempotently, including after a crash between receipt and
budget commits. This recovery needs no solver submission, collection or remote lookup;
damaged receipts leave the reservation outstanding.
Task identity comes from the sealed recovery origin even when `draft_from` changes the
objective or resumes an earlier branch. A versioned instance ledger stores each job
under its exact `(run_id, run_name)` identity and updates elapsed charges in place.
The current owner takes precedence; otherwise a named recovery requires exactly one
control-authorized ancestor. Other tasks with the same implementation or name grant
no access. The full recovery family counts toward task limits, including sibling
branches, without granting access to those siblings' named jobs. Multiple authorized
ancestors with the requested name require explicit repair. Shared accounting retains
all instance charges across goal carriers, revisions and objective keys.
Each preflight or initialization report has an immutable attempt path; the mode report
is only the current selection. Receipts and finalization proofs bind the attempt path.
Old receipts retain their original bytes and hashes and restore their mode-report bytes
to that attempt path. Conflicting attempt bytes still reject recovery.

An active experiment can call `worker_experiment_execute(action="review")` again to
obtain the latest completed review of its exact implementation in the same instance.
Control delivers the unchanged review body through the existing sealed material channel,
with the original review as an immutable parent and an explicit `worker_reference_read`
request. Negative findings are readable as well. Repeated delivery is idempotent and old
delivered versions remain readable; execution admission always checks the original latest
exact review, never the delivered copy or an old pass.

Exact request identity and any explicitly applicable review policy still apply. Explicit
`execution_start` rechecks the current policy before submission. An unknown submission
is looked up using its frozen descriptor before any new side effect; a renamed request
cannot claim the same semantic project's budget again. Status and the instance UI show
`authorization.source` (`policy`, `human`, or `none`) and the frozen policy digest/budget.

Root and Worker submission calls hand remote admission, preparation and submission to
one control-owned background writer. The bounded reply reports `submission.state=pending`;
it does not claim solver success. The writer retains an independent maintenance lease
and durable per-execution lock/record. Duplicate calls cannot launch another submission.
After a lost response or daemon restart, status reconciles the exact descriptor by lookup
only; an absent lookup is still unknown, never permission to resubmit or release budget.
Background failures expose a bounded diagnostic reference; required approvals remain
available through status. Operational submission progress is excluded from sealed receipts.
Control admits one background submission per registered execution backend at a time;
independent backends do not share the slot. A busy backend rejects before accepting
another submission; there is no unbounded queue.

An explicit abandon/cancel can retire a new-protocol uncertain submission. The backend
atomically returns an existing job or installs a permanent tombstone under its submit
lock; a negative lookup alone is never enough. Old in-flight submissions without recorded
retirement support, unavailable backends and failed retirement retain their reservations.
Retirement requires the matching control adapter and runner; it cannot certify that an
old runner process loaded before upgrade will honor a newly installed tombstone.
TCAD protocol discovery is required before new admission/reservation and diagnostic
preparation. Deployment probes verify the submission/retirement protocol as well as
capabilities and policy. For legacy requests, the administrator recovery command in
[INSTALL.md](INSTALL.md#legacy-uncertain-submissions) records quiescence attestation;
budget remains reserved until the normal bridge obtains remote retirement proof.
Submission progress rewrites preserve the private `administrator_recovery` audit
record verbatim; it is never included in the model-facing submission summary.

Known terminal executions finalize missing resource measurements at their reserved
limits in a separate estimate ledger. Responses/UI distinguish `actual` from `estimated`;
estimates do not refund capacity and stop endless automatic polling. Later exact
observations replace estimates without overwriting earlier measured dimensions. Both
the actual and estimate ledgers survive instance archive/restore.
If the terminal query itself fails, control retains the reservation and retries until
`lifecycle.terminal_observation_failure_limit` consecutive failures (default 3).
The counter is transactionally stored in the execution database, survives archive/restore
and observation-cache corruption, and resets after a successful query. Readable legacy
cache counts seed the database once. A successful
terminal response lacking measurements still finalizes those missing dimensions.

The control daemon reconciles expired Runs and polls already submitted executions
serially, independently of Worker calls. Global `lifecycle.interval_seconds` (30)
and `lifecycle.batch_size` (32) configure bounded, rotating passes. Worker timeout
records a failed Run and preserves its recovery draft and external execution;
it does not cancel the solver or imply a solver outcome. Observation failures
retain the last confirmed execution state and record a refresh diagnostic. The
reconciler never submits or collects work. Resuming the failed Run retains the
original execution identity and removes it from Root recovery while the new owner
is active. A terminal solver outcome does not complete the scientific Run.

A task's human execution-approval wait is recorded by the background approval creator
once in its activity ledger, starting at approval creation rather than a Worker poll.
Effective deadlines add the union of these intervals, ending at decision, cancellation
or expiry; simultaneous waits count once. Total credit is capped by the Run's frozen
`execution_io.approval_wait_budget_seconds` (default 86400, zero disables credit),
including historical pending approvals without expiry. The original deadline stays unchanged, and
repeated reads or daemon restarts cannot accumulate extra work time. Worker calls,
Root status and timeout reconciliation use the same projection. An approval created
while work is active returns the current deadline and remaining task time in
`task_budget`; the initial assignment deadline must not be reused as a live clock.
An approval created
after expiry cannot revive a task. Existing failed tasks remain failed and can only
use explicit recovery of their original execution as described above.
Batch status reads load wait events and approval records once per batch. The local Worker
receives the approval database path independently of Operation capability.

Complete experiments use `worker_experiment_execute(action="status")` to refresh
remote state and progress of submitted work without starting, cancelling or
collecting it. `advance` can continue authorized work; `collect` transfers outputs. Both return
elapsed time and log metadata only, with distinct status
and progress observation times. A refresh failure retains the previous snapshot
and is explicitly marked; a running state or quiet log alone proves neither
continued solver progress nor a stall. UI metadata includes these observations so
progress updates notify subscribers even when the state remains `running`. UI
reads do not poll the solver. Without a solver-provided completion ratio, the UI
uses an indeterminate indicator and measured elapsed time/log activity, never elapsed
budget as a completion percentage. File transfer percentages use observed byte totals
and remain distinct from solver progress. Mutable progress is excluded from sealed execution
evidence. Diagnostic status also returns compact progress without submitting or
collecting; full diagnostic tails remain available through its saved detail file.

Status refreshes save a bounded log-tail snapshot under the exact immutable execution
ID. Worker `action="logs"` and Root `execution_logs` explicitly page that cache
without remote access. Neither default nor detailed status includes log text; the
UI may show a bounded last-line preview. Log reads default to the newest page,
with text in chronological order. `direction="before"` plus the returned `before`
cursor reads older cached text; `direction="after"` plus `after` reads new text,
returning empty text when unchanged. Cursors are scoped to the execution/log.
Incremental continuity requires a stable source window and an exact text prefix.
Rotation, a sliding/replaced window, or an older adapter without source identity
returns `gap="snapshot_replaced"` and a fresh newest page instead of guessing overlap.
Pages report observation time and truncation; these diagnostics are not sealed
evidence. The experiment owner chooses when to inspect logs or use an optional
native helper to summarize a bounded diagnostic question. Status never invokes a
model; helper summaries retain evidence locations and do not establish solver state.
Collection retains declared log outputs (TCAD includes `tcad_log`). Cached bodies
are discarded only after all outputs and the result manifest are durably registered
and state is `collected`; failed/interrupted collection retains them. Cleanup and
late refreshes affect only that execution. Recovering its owning task keeps the
original execution identity and cache. After collection, read retained output files.

`execution_sync` refreshes solver state and bounded logs, including terminal
executions. `execution_status` queries the adapter for submitted, running or
cancelling executions; unsubmitted and confirmed terminal executions use control
state. A query failure explicitly returns the error and last observation time.
Inventory and UI reads remain cached, updated by daemon observations. Artifact transfer starts only with explicit `execution_collect`;
`execution_outputs` publishes names after collection. One daemon-owned collection
slot consumes a frozen total budget (600 seconds by default), with cleanup
reserved inside it. A private control guard holds the locks until its single work
process group has stopped, including after daemon exit; transport programs do not
own those locks. Duplicate active requests retain that budget; another
execution receives busy without being queued. Complete files and a stable output
manifest survive interrupted collection and registration. Adapters implement
transport only, optionally consuming the common `CollectionContext`; they do not
own another scheduler. Query, file and idle defaults are 5, 120 and 30 seconds.

SSH result collection freezes a file list and transfers a standard uncompressed tar
stream in one connection per bounded manifest batch. The remote does not retain an
extra archive. A fixed SHA-256 trailer verifies archive transport; local extraction
checks the exact manifest, member type, size and per-file digest before replacing a
cache file. Temporary local archives are removed on success or handled failure;
verified files remain reusable after interruption. A forced process kill may leave
an unaccepted temporary archive, removed by the next collection for that execution.
No archive or full result file is buffered in memory. The local disk temporarily
holds both the archive and extracted files. Archive transfer uses the collection
and idle budgets; per-file budget applies during extraction. UI shows archive bytes
received separately from files verified. Upgrading uses the existing joint local
and remote runner install transaction; old runners fail with an upgrade diagnostic.

Execution requests retain the exact scientific implementation receipt separately from
its private executable package. Several scientific descriptions may share a package;
review/start use the selected receipt, and collection/recovery/final reconciliation
use the frozen receipt. Historical requests without that identity require a unique
match; ambiguity is never evidence of integrity corruption. Once execution and
collection are idle, a missing/ambiguous exact receipt permits only a blocked or
inconclusive report with limitations; control never invents a receipt. Completed
delivery stays rejected. Root sees binding ambiguity in normal status and can inspect
retained results without rerunning the solver. Mechanical collection remains available
under the frozen execution identity even before receipt binding is repaired; it
withholds scientific output projection and receipt publication until binding is exact. Selecting a new description does not
inherit an earlier description's independent review.

Submission retry classification follows explicit causes across wrappers; implicit
exception context remains diagnostic evidence only. A declared integrity/admission
failure cannot be overridden by an earlier lock/connection error. `repairable` alone
does not identify who can repair a problem: submission correction is declared by
RunOutputError/WorkspaceOutputError; other DiagnosticErrors require Root intervention.
Submission errors follow their explicit cause across wrappers. Declared finalizer/checker
budget exhaustion stops the task; a connection interruption or SQLite busy may be
retried only within the task deadline. An unclassified timeout requires investigation,
not automatic retry or an assumed exhausted budget. Storage exhaustion stops the
Run when the failure can be persisted. If control storage cannot confirm state, the
caller gets `submission_state_unavailable`; it must query the same task after repair,
not assume termination or start another solver. Running tasks that need investigation
expose a short `attention_required` field through normal Root status polling.
Attention is a durable control-issue projection, independent of the last tool error.
Submission issue codes coexist; implementation issues bind one exact execution.
Ordinary rejections and successful unrelated tools cannot erase either. A missing
historical implementation receipt requires intervention; a bad caller alias, an
expected not-created object or a transient transport failure does not. Successful
submission resolves its submission issues. A verified exact receipt lookup resolves
only that execution's binding issues, including its earlier recovery owners. A
limited report can close its Run without pretending that an unresolved execution
binding has been repaired; its attention remains visible after completion.

Ordinary Root tool responses automatically include bounded `attention_notifications`
on first observation, changed issues or recurrence. Repeated identical observations
update last-seen time but do not notify again; reading a notice never resolves it.
`lifecycle_events` has an independent durable notification cursor. Notices contain
semantic task names and safe codes, not private execution bindings or trace bodies.
This is delivery on the next Root tool response, not unsolicited process wake-up:
a disconnected/idle Root must reconnect or call a tool. Notification failure does
not turn a committed operation into a failed tool call; durable status remains
available for retry. Issue transitions live in the Run activity store; mutable notification snapshots
live in `run_attention_notices` in the same database. Both share instance archive/restore.
Legacy notice rows remain untouched, and migration preserves their cursor versions.

Successful `resume_from` completion marks the ancestor's submission issues as
`superseded`; it does not erase diagnostics or clear execution-binding issues.
`draft_from` may change scientific inputs and cannot establish that repair.
Legacy requests without an exact receipt resolve uniquely against the sealed package
author's complete receipts, then map that exact receipt to a consumer alias. Request
`experiment_run` denotes the recovery root, which may differ from the package author.
Packages without author metadata require uniqueness across the original task family;
a narrowed successor input set is never proof that a historical ambiguity is repaired.

Notification reads use one compact transition snapshot per task and indexed joins,
not historical issue scans or an inventory of all Run bindings. Closed snapshots
are sent only to observers that have an outstanding notice; an acknowledged closed
snapshot is excluded. Unchanged notification/lifecycle reads take no write lock.
Acknowledgement atomically claims each version per observer; concurrent replies
include only notices they successfully claimed. Claims advance monotonically and
only cover notices that fit the final reply. This does not guarantee network delivery
after a response is lost. `mcp_read` byte budgets include list entries, cursors and appended notices;
when a notice cannot fit it remains pending. Codes are capped by the eight-issue
projection; `issues_truncated` marks omissions while `total` counts all open issues.

Expected output corrections store structured diagnostics without traceback files.
Engineering traces are deduplicated by exact failure and scope; collection enforces
bounded storage, and serial lifecycle maintenance applies the global agent-settings
`diagnostics` policy (defaults: 1024 records, 67108864 bytes, 604800 seconds).
Only the control lifecycle daemon publishes the derived retention policy cache;
capture/prune callers read it without overwriting it with local settings. If that cache
is damaged, recording and cleanup use bounded fallback settings, and the daemon
restores it from authoritative configuration without requiring a readable old cache.
Log bodies use atomic replacement. Live reads share the retention lock with writers
and cleanup; historical read-only archives need no new lock file.
Expiry removes diagnostic JSON/stdout/stderr only, never CAS or sealed evidence.
References in Root records do not pin traces: the count/byte budget can evict them
before seven days. Durable Run error summaries remain; the full trace is expendable.
A retained locator may expire; diagnostic reads report this explicitly. Old settings
without this optional section use defaults; remove it before rolling back to a
program version that does not recognize it.

Engineering failures use one bounded, redacted diagnostic projection. Root reads
details by an instance/session-scoped `diagnostic_read` reference. Worker runtime errors
and explicit Root diagnostic pages carry only a locator and section names, never inline
tracebacks or logs; private diagnostics are not copied into scientific workspaces.
Argument corrections still return their actionable instructions directly. Run activity supplies MCP
timing. Local trusted workspaces share an optional process-observation launcher:
analysis retains its existing execution policy, other roles inherit their prior
environment and limits. Missing or damaged observation is reported explicitly
and never adds a scientific submission requirement.

Runtime assembly supplies the experiment coordinator once when constructing
RunService, including its operation-service loader. Root facades and gateways
only consume it; creating another view cannot replace cancellation/finalization
authority. Daemon startup reconciliation and standalone Worker assembly include
the same dependencies. `ExecutionBridge.cancel_or_abandon` owns authoritative
prepared-submission lookup before abandoning or cancelling; uncertain lookup
preserves the existing identity and does not submit.

Operation ABI 24 replaces implicit infinite byte sentinels with `None` only for
wildcard material/file inputs and control attachments. Existing frozen settings
own those budgets. Root/Worker views retain effective limits or an explicit
settings source; ordinary scientific ports still require positive static limits.
Historical archives and scheduler fingerprints retain their original encodings.

Known failure boundaries add safe recovery facts: configuration repair belongs to
the administrator; a failed connection is retryable only when no bytes were sent;
policy rejection requires repair; an uncertain submission requires lookup of the
exact prepared identity through `execution_start`. None starts an automatic retry.
`ExecutionBridge.health` reuses declared capability reads, caches observations for
a configurable minimum interval (default 5 seconds), and never submits, collects,
cancels or recovers jobs. TCAD capability/policy queries share the configured total
query timeout. An available probe proves capability access, not solver success.

`platforms.codex_usage.observe_usage` reduces Codex `thread/tokenUsage/updated`
cumulative snapshots for the host's existing observation storage. The host owns
exact thread/turn bindings and Root/Worker/helper attribution; missing bindings
remain unattributed. Repeated counters contribute zero; counter regression retains
the high water and marks a gap. A resumed thread requires an initial baseline.
`usage_summary` reads one latest record per thread, includes failed-thread usage,
and preserves gaps. Cached input is part of input, and response bytes/time are
separate optional observations. Individual model-request usage remains unavailable.
This interface creates no database or host loop; automatic collection by a live
host and its persistence remain integration/acceptance work, not an Agent form.

Error observations append to existing Run activity even after the deadline or
terminal state; they do not renew a budget, reopen a Run, or accept a result.
Each MCP call's start and finish belong to the same Run, including when an idle
Worker opens its next assignment. An open failure after selection belongs to
that selected Run, preserves its cause,
and cannot return the previous Run's completion as the new call's outcome.
`run_status(intent="status", diagnostic_after=0)` requests
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

`worker-start.json` points the Worker to the authoring form in
`schema/result.schema.json`, including its structural and scientific rules. JSON Schema owns required fields,
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
`run_status(intent="navigation").bound_inputs` and ordered `artifact_catalog.parents` project exact
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
control metadata. `LocalTrustedBackend` is the only execution backend and owns its workspace.
The retired hardened execution, upload, patch and Worker MCP entry points are removed.
Historical Run backend labels, Artifact bytes, workspace layouts and dispatch records
remain readable through archive readers; they never enable the retired executor.
Old `worker_backend=hardened` configuration is rejected before runtime/deployment changes.
Migration requires explicitly selecting `local` and regenerating profiles after
finishing or archiving old work on the prior release; native permissions remain declared.
This retirement does not resolve `SEC-002`.

## 6. Generic and domain boundaries

The hypothesis task accepts exact original user text without mandatory intake,
retrieval or scientific-foundation qualification. Its Worker owns scientific
understanding and testable hypotheses, preserving unsupported claims and missing
information. Control freezes the original goal identity and creates no foundation
or objective key. The alternative structured frame/foundation branch retains
existing qualification and requires its exact objective key. Optional hypothesis
review inherits the original goal and source materials, with large files streamed.

Experiment tasks require an exact sealed nonempty hypothesis portfolio, selected
directly or inherited from an exact prior experiment. Control follows immutable
producer inputs to bind that hypothesis and its original global goal; original
text, intake, foundation or a goal alone cannot start an experiment. Evidence
preparation may be omitted when existing materials suffice. Hypothesis formulation,
bounded experiment and result analysis retain their scientific responsibilities;
new research routes return to hypothesis formulation. The generic result-analysis
Operation is available without domain plugins and binds the exact experiment,
its original hypotheses, goal and scientific materials. No new stage approval or
mandatory independent review is introduced. New remote execution requires the
task hypothesis; status, collection and cancellation retain existing recovery
semantics. Native shell remains a soft permission boundary, permits role-appropriate
analysis calculations, and does not technically prevent arbitrary native programs.
Original-goal readability, immutable identity and instance budget ownership remain
control responsibilities; raw text never receives a fabricated objective key.
Missing information and unavailable execution remain explicit in blocked/inconclusive
delivery; completed reports adopt exact implementation, execution and validity materials.

| Generic core | Plugin |
| --- | --- |
| OperationSpec ABI and one-shot compiler | Operations and narrow components |
| Artifact, Run, Approval, Execution lifecycles | Domain Schemas, validators, guards, projectors |
| Root MCP, Run lifecycle, workspace backends | Expert prompts, workspace hooks, domain tools |
| Fixed safe review document and UI | Review projection, never HTML or scripts |
| Generic preflight/invoke | Transforms, runtime factory, effect adapter |

The TCAD plugin supplies an `ExperimentCapability`: solver project declarations,
implementation preparation, debugging, raw-output analysis and an internal execution
Effect. It does not register a separate public author/revision/reviewer pipeline.
Control creates `ExecutionPackage` (`tcad.execution-package.v2`) with exact source,
file and capability identity; its optional review is an independent fact and grants
no authorization by being embedded. SProcess and SDevice share the generic task.

Curve-score supplies deterministic scoring/diagnosis tools for complete analysis
tasks. Curve-figure-evidence supplies scientific figure extraction and independent
evidence review with the required algorithms. The InGaAs Fig.4 plugin supplies its
project scorer. Core owns lifecycle, bindings and qualification; plugins own domain
algorithms and declared components. Component configuration identity, catalog ABI and
digests, public/support/internal visibility and versioned schema IDs remain platform
contracts. The public runtime boundary is documented in [Plugin runtime API](PLUGIN_RUNTIME_API.md).
Figure consumes its records/presentation API and shared deterministic declarations.
The remaining plugin dependency boundary still requires focused review;
these declarations do not claim that every plugin already avoids core internals.

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
- Hardened execution is retired. Production Local history with unconfirmed native
  writers still blocks destructive archival, even for terminal Runs. Synchronous
  archive fixtures prove format and transaction behavior only; native writer
  quiescence and deployed upgrade acceptance remain separate release work.
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

`LocalTrustedBackend` assumes cooperative local Agents and a trusted host user.
The Root/Worker route consumes client-supplied platform metadata; a native shell
with socket access can forge Root metadata. The default installer runs control,
UI and local TCAD services under the same service UID, normally the installing
user's UID. A Worker with that UID and filesystem access can read or modify
control databases, CAS and the approval receipt secret. Separate daemon processes,
same-UID peer credentials and same-UID-readable `0600` tokens do not isolate roles.
`SEC-002` remains open. Strong isolation needs a trusted launcher identity binding
and an OS/sandbox boundary denying Workers access to control sockets, state and
secrets; native sandbox restrictions alone are not a framework guarantee.

Worker prompts, task directories, and JSON validation provide context-level
soft isolation. Normal interfaces enforce exact input binding, output sealing and
validation, Artifact registration, independent review, human approval and effect
authorization. Those gates do not contain a hostile same-UID shell. Effect policy limits executable,
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
Completed outputs prioritize their exact same-producer file manifest and published
attachments ahead of wide input histories, including general Experiment reports.
Agents do not supply an additional evidence field to display published attachments.
Manifest display keeps file records, plugin metadata and original array positions,
while omitting nonvisual calculation bodies; exact original manifests stay readable.
PNG/JPEG previews serve the complete registered bytes; SVG remains downloadable.
Presentation grants no review verdict or qualification and never reads draft paths.
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
append-only triggers; the maintenance journal is not disposable UI cache. See [release scope and omitted historical records](RELEASE.md#publication-scope).

## Native capability profiles and external evidence

Root startup instructions come from `roles/scheduler.md`, installed as managed
top-level `developer_instructions` in the project Codex configuration. Interactive
CLI and background hosts share that source. Project `AGENTS.md` contains the
managed `roles/common.md` rules and preserved user prose; controlled Worker/helper
role files replace the Root developer field through the existing capability seam.
Frozen assignments still own scientific roles. Ordinary user developer settings
whose scope is unknown cause an installation conflict before migration. Existing
thread history is retained; disk updates cannot retract it. Normal operation uses the self-contained catalog and
selected callable contract; it requires no guide files. Guides under
`roles/scheduler/` are installed for exceptional maintenance, not as a normal reading
gate or a second routing authority. Installation preserves unmanaged project prose.

Local workspaces include the read-only `tools/read_tool_contract.py`. It reads only
the frozen assignment's tool contracts. The reader owns a disposable scratch receipt
of its last complete response; callers supply only the tool name. Related reads can
return a lossless JSON Patch against that full response, never another patch.
Changed assignment/workspace/contracts, missing or stale receipts and larger patches
fall back to full text. Use `--full` after context loss: a delivery receipt cannot
prove the model still retains the base. Receipt failures do not reject scientific work.
This adds no MCP capability, contract registry, scientific state or authority, and
changes no executable schema or scientific output. Old workspaces retain direct
reading; historical workspace files grant no execution permission.

Local workspaces also provide `tools/read_output_schema.py`, a read-only view of
`schema/result.schema.json`, the Agent authoring form projected by the actual
paired finalizer. Mechanical fields, internal port/checker wiring, Operation digest
and input admission metadata stay with control. Scientific rules, limits and
source aliases remain visible. It retains envelope/payload structure and all shared
rules, expands required references and selected `--field` closures, and lists exact
pointers for unexpanded definitions. `--definitions-only` supplements a retained
current overview; `--full` returns the complete authoring form, including any
required scientific handoff, never the sealed artifact contract. `--field` selects
a payload member, not the payload wrapper. This view is not a validation schema.
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
its raw default. Capture remains bounded separately from display. The control UI retains recovery coverage and exact omission records. Root status
exposes recovery availability and explicitly requested safe diagnostics.

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

New experiment tasks select scientific materials and optional scientific files.
Control prepares the exact execution package and resolves private execution bindings;
the owner is not required to fill capability IDs, review witnesses or routing fields.
Optional Effect preparation remains part of the compiled ABI: transform, output schema
and validator enter identity. Applicable policy or UI authorization, exact submission
lookup and cumulative execution budgets govern external side effects. Changed content
creates a new object and never silently inherits review qualification.

`agent-settings.json` also configures `helpers` and `execution_io`. Global values are
merged with explicit instance fields and frozen when a Run is created; recovery keeps
the source snapshot. Explicit values equal to package defaults still override global
values. These control settings are not scientific input ports or Agent forms.
`execution_io` defaults are `max_export_bytes=2000000000`, `read_page_bytes=16384`,
`collection_timeout_seconds=600`, `file_timeout_seconds=120` and
`idle_timeout_seconds=30` and `submission_response_wait_seconds=0.25` (0–2 seconds).
The last setting bounds the initial wait for background submission, not solver runtime.
`approval_wait_budget_seconds=86400` separately bounds cumulative human-wait credit.
Capacity is bytes, time is seconds. The experiment's text
read, streamed export and collection consume those frozen values; export/collection
are additionally bounded by remaining Run time. They are separate from the plugin's
configured solver storage/wall-time authorization and from RAM limits. Changing them
neither authorizes a solver run nor expands a running task's deadline.

Scientific semantic conflicts are resolved before repeated implementation searches;
equivalent local engineering choices remain with the author. Four modules define
complete task responsibilities, not a fixed DAG. Static implementation review does
not establish production behavior, token savings or a deployed runtime.

### Two profiles for general internal helpers

`worker_helper` accepts `profile="inherit"` or `profile="lightweight"`; omission uses
`helpers.default_profile` (inherit by default). Inherit uses the parent's frozen
model and reasoning effort. Lightweight uses `helpers.profiles.lightweight`, shipped
as gpt-6-luna / low, with the model name declared only in configuration. Both retain
existing native permissions, workspace and allowed tools; neither is limited to
summarization. Missing lightweight configuration is rejected without model fallback
or automatic escalation. Fresh-context helpers receive their subtask and selected
materials, without a new Root task, approval or delivery form.

Explicit instance profile fields override global fields; an explicit empty profiles
map disables separate profiles. Run creation freezes helper settings; recovery retains
the original settings and cumulative allowances. Prepare freezes the selected profile
and actual model in the existing participant record; dispatch and gateway use that same
record. A mismatched model is rejected before child binding without failing the owner.
Historical records without a helper profile use their parent's frozen profile only.
Global max_calls/max_input_bytes remain aggregate limits, with optional smaller
lightweight max_calls/max_input_bytes; max_active defaults to one. These are not hard
native token or memory limits, and call counts do not establish actual token cost.

The owner chooses direct diagnosis or delegation. Log access uses the control cache
for its own execution; status never calls a model. Helpers return findings, evidence
locations and uncertainty for owner integration, without mandatory per-poll summaries.
