# Plugin runtime boundary

This reference owns the supported plugin runtime boundary. `scidiscovery.operations`
continues to own stable declarations. There is one compiler/catalog and no runtime
API registry. Catalog ABI/digests, configuration identity, public/support/internal
visibility and versioned schema IDs remain necessary platform contracts.

## Implemented public modules

| Module | Contract | Authority retained by control |
| --- | --- | --- |
| `scidiscovery.operations.transforms` | Pure `object_schema`, `single_input`, `group_inputs`, `transform_output`, `transform_operation`; explicit component/codec references and scientific descriptions | Compilation, registration, identity, admission and side effects |
| `scidiscovery.plugin_runtime.evidence` | `read_evidence_records(raw)` validates the manifest wire shape and returns detached records with `alias`, `artifact_ref`, `source_ref`, `media_type`, `size_bytes`, `metadata`, `tool_name` | Authenticity, exact input binding, attempt/recovery proof, immutable registration and qualification |
| `scidiscovery.plugin_runtime.workspace` | Symlink-resistant task-root file IO, media typing, publication content validation, atomic bounded JSON records on supplied paths | Workspace allocation, roots, immutable sealing, Artifact registration and qualification |
| `scidiscovery.plugin_runtime.calculations` | `CalculationResult`, scientific citation resolution; structural `CalculationTools`/`CalculationEvidence` protocols implemented by the actual tool/validation contexts | Actual attempt, receipt, exact read-source identity, registration and recovery verification |
| `scidiscovery.plugin_runtime.experiment` | Per-Run `ExperimentTools`: methods, sealed implementation bytes, task diagnostic context/cancel and declared execution commands | Coordinator, Run/Execution/Artifact services, lineage, budget origin and task admission |
| `scidiscovery.plugin_runtime.collection` | Supplied `CollectionContext` deadlines/cancellation/progress, bounded streaming `run_bounded`, owned-child parent watch | Execution supervisor, grants, cancellation decisions, Run lifecycle, DB and leases |
| `scidiscovery.plugin_runtime.diagnostics` | Redacted bounded exception facts and declared failure value types | Diagnostic storage, host traceback capture, qualification and retry decisions |
| `scidiscovery.plugin_runtime.results` | Mechanical draft copies and handoff projections on the supplied workspace request | Final output validation, sealing and lifecycle |
| `scidiscovery.plugin_runtime.transport` | Generic `MCPRouter`, JSON-RPC parsing/error values, bounded Unix socket client/daemon | Root/Worker routers, tools/registration, authentication and compiled action authority |
| `scidiscovery.plugin_runtime.observation` | `RECORD_DIR`, `normalize_log`, `materialize_launcher` for the optional Worker-executed stdlib launcher | Launch/stop authorization, Run lifecycle and interpretation of observations; other module functions are implementation details |
| `scidiscovery.plugin_runtime.presentation` | Pure JSON field/section/gap/source/parameter/citation constructors, bounded row windows and ancestry within the supplied cohort | Authorized input cohort, provider discovery, output/source validation, aggregate bounds and rendering |

The runtime package performs no imports of service, interfaces or approval UI modules.
Figure, curve and TCAD are migrated consumers. All three production plugin packages
and plugin_runtime have no imports of service, interfaces or approval UI. Domain
SSH/solver, packager and numerical behavior remain in their plugins.
The full tool manifest models live in the core schema layer for control use, **not**
in the public API. Moving them does not make attempts, recovery state or private
calculation records public plugin contracts. Reserved `calculation_proof` and
`checkpoint_proof` metadata is excluded from both manifest record views and the
tool context's `evidence()` view. Control reads the original records for verification;
scientific/domain metadata remains available.

Evidence records are callback data for trusted domain tools/validators. They are not
Agent-visible output: source identities and domain restoration metadata may be private.
Parsing does not prove authenticity or authorize access. Obtain the exact bytes from
compiled inputs or the existing tool context; retain domain source/hash/membership
checks. Mutating the detached result changes no stored record. Registration and
adoption still go through the task's existing controlled tool context.

Presentation helpers accept only the already authorized records supplied by the UI.
They cannot load artifacts, expand a cohort, grant qualification or return executable
HTML. The UI still validates every source and caps the combined response. Domain
providers retain interpretation and layout of their own scientific fields.

## Calculations and checkpoints

Algorithms return `CalculationResult`: scientific request/result/status, exact numerical
input hashes and bounded safe diagnostics. Existing hashes support numerical replay;
they are not Agent fields or private receipts. `complete_calculation` on the supplied
tool context creates the actual attempt result and seals the private record. Control
checks those hashes against sources actually read. `verified_calculations(report)` on
the validation sources verifies receipts/origins before returning result values; it
never returns attempts or recovery state. Both contexts implement the public structural
protocols without a second service registry.

`publish_analysis_file` registers immutable bytes and a task-local preview.
`publish_calculation_checkpoint` accepts checkpoint bytes, algorithm/record identity,
source aliases and numerical identity values. Control derives exact source references
and hashes. `read_calculation_checkpoint` checks the registered producer, bytes and
source cohort, returning only saved bytes and numerical identity values. Curve retains
request equality, numerical reconstruction and mathematical consistency checks. No
plugin constructs `ControlledCalculationRecord` to complete these paths.

## Ownership and extension

TCAD socket transport remains a supported runtime configuration and CLI; its generic
transport implementation is shared with core. It does not expose Root/Worker service
routers. Collection utilities preserve streaming, total/per-file/idle deadlines and
owned-process cancellation; a utility import grants no execution permission. Workspace
and atomic-record helpers require control-supplied roots/paths.

`prior_analysis_sources` supplies paired historical source-port facts along with exact
source mappings, so TCAD need not parse private manifest bindings. Scientific case
correspondence remains a domain check. Process supervisors, task lifecycle, leases,
execution DB, host traceback storage and retry authority remain internal.

A new facade must not simply re-export `RunService`, private proof models or UI
implementation functions. Pure values/functions can move to their owning public
module; stateful powers use a narrow injected capability with one control-side owner.
No plugin acquires lifecycle or approval authority by importing this API. Experiment
services expose a per-Run adapter, never the coordinator. Shared startup bindings are
scoped by the real local/hardened tool host without changing cached Run identity;
TCAD receives exact implementation values and a derived diagnostic workspace.

## Root consumer boundary

Normal Root calls use the research surface. Standalone Effect plugins and historical
execution recovery select `surface="execution"` on all three gateway methods
(`scid_catalog` also needs `kind="interfaces"`). Interface declarations own this
projection; it does not authorize internal Operations or task-managed execution.
Execution services, exact approval, budgets and idempotency remain control-owned.

`run_status` uses `intent="decision"` by default; `status` waits or pages safe saved
diagnostics, `navigation` discovers exact scientific fields/input names, and `full`
explicitly reads complete completed science. The old profile/view/mode/full-output
flags are removed. `output_fields` and exact `output_paths` remain mutually exclusive;
index/stage pagination and explicit omission markers retain their bounds. UI and
control retain private recovery and engineering records.

## Validation status

These migrations have only source/AST/import-graph review. No tests, import execution,
catalog compilation, installation, build, model call or solver run was performed.
The [R4 plan](plans/RESEARCH_TASK_REFACTOR_R4.zh-CN.md) owns rollout and acceptance status.
