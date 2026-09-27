# TCAD Artifact Plugin

[简体中文](README.zh-CN.md) | English

The bundled SSH command transport is validated locally during installation, including
its referenced configuration, without contacting the remote solver. The optional
`transfer_chunk_bytes` setting defaults to 1 MiB and can be overridden; transfer
quotas and execution authorization remain explicit. Invalid transport configuration
produces `tcad_transport_configuration_invalid`: an administrator must repair it
before retrying the same scientific action. Private diagnostics stay in control storage.

`tcad_control` is the execution adapter for prepared TCAD jobs. It exposes
capability and administrator-policy discovery, authoritative submission lookup, submit,
status, cancel, inspection, and collection. Submission is idempotent for an exact frozen
descriptor; an unavailable lookup fails before any retry side effect.

It owns only operational run directories and detached process state. Artifact
identity, Run identity, approval, execution identity, and result registration
remain in SciDiscovery.

The accepted payload is a canonical JSON `TCADJobSpec` containing a local
archive descriptor, an archive member manifest, one deployment-owned tool
profile, a required trusted execution purpose, resource limits, and expected
output paths. Current execution-package flows always set `production`; schema
v1 jobs without a purpose are rejected. The dispatcher does not generate or
assess scientific models or decks.

The current job protocol is `TCADJobSpec.schema_version=4`. It includes an explicit
`collect_generated_outputs` flag and enforced wall/CPU/memory/output limits plus required total `max_storage_bytes`; the
unused `max_processes` hint is removed. Update control and remote runners together.
Policies are validated strictly, without old smoke-policy migration. Project and
execution serialization retains default fields. Packaging uses declared-source v2
with complete case anchors and exact source materialization. The owner supplies
scientific design and solver source; control resolves capability, file bindings,
resource policy and execution identity. `ExecutionPackage` uses
`tcad.execution-package.v2`; an optional review does not make the package approved.

Capability discovery emits only `tcad.solver-capability.v2`. Private fixed
arguments, executable paths, environments, and full release evidence never
enter the snapshot. Administrators may opt specific fixed arguments into
`public_arguments` and set a constrained `public_release_label`; defaults
publish no arguments and derive a safe label from the profile name. Digests
and counts bind the undisclosed private values. Version 1 snapshots are not
accepted.

Deployment files:

- `deploy/systemd/tcad-control.service.in`
- `config/execution-policy.example.json`

The socket is internal to `ExecutionBridge`; it is not registered as a Codex
MCP. Interactive clients receive only the SciDiscovery root tools.
Cross-machine deployment uses the bounded command contract documented in
`docs/tcad_transport_contract.md`. The optional SSH transport invokes the
dependency-free `remote_runner_py36.py` through an existing user-authorized
OpenSSH connection; it does not install a Python package or system service
inside the simulator host.

## Complete experiment task

`science.experiment.v1` is the public generic experiment task. One owner handles
design, solver code, local debugging, execution, collection, validity and delivery.
The plugin contributes `ExperimentCapability` tools and an internal solver Effect;
it does not register a separate author/revision/reviewer dispatch chain. SProcess
and SDevice use this same task. The owner seals actual stage conclusions for the UI;
normal stages require no independent review or approval. Independent review is
optional unless an applicable contract explicitly requires it. Execution authorization
is governed by the configured policy below.

The owner writes the full solver project, scientific execution plan, case anchors
and raw-output declarations. Control resolves exact capability, source/file identities
and resource settings. The declaration materializer does not invent physical models
or generate a `.cmd` scaffold. Local refinements remain in the same task. Native
helpers may read task files, use Skills and tools, and perform authorized local work;
the owner waits and integrates their findings. A helper does not become an approver
or receive Root control rights. See the [core architecture](../../docs/ARCHITECTURE.md)
for participation, permission and native lifecycle boundaries.

Solver projects declare physical code, inputs, parameters and raw TDR/PLX/PLT/log
outputs. Deterministic parsing/scoring tools own derived curves and metrics;
scientific conclusions remain with the task owner. These components do not distribute
or replace Synopsys software or licensing.

## Configured autonomous execution

The administrator must supply the complete `agent_execution_policy`, `runner`, and
`debug` sections illustrated in `config/execution-policy.example.json` and
`config/remote-runner.example.json`. Missing/invalid policy is rejected; deployment
no longer manufactures a smoke policy. The example permits **2,000,000,000 bytes**
and **3600 seconds**, inclusive, with both conditions required. These are editable
configuration values, independent of RAM. Outside the allowance or when disabled,
`outside_limits` selects `require_human_approval` or `deny`.

The core stores policy authorization separately from HumanDecision, bound to the
request, execution package, compiled identity, budget and policy digest. The runner
rechecks that projection at submission, then freezes its resource settings. One
job process tree shares a wall deadline across cases. A persistent semantic-project
budget owner and exact submission lookup prevent renamed/recovered work from receiving
a fresh allowance. Debug modes, attempts, total reservations and diagnostic bounds
also come from config; reservations are saved before submission against the immutable
scientific subject, including failed/unknown submissions.

The domain execution policy also constrains allowed executables, hosts, inputs,
environment and runner limits. Core control owns exact authorization bindings,
budgets and lifecycle; the TCAD adapter owns enforcement at the side-effect
boundary. Socket and command transports, including the stdio installation probe,
retain these distinct responsibilities. The default local daemon runs under the
same service UID as core control and usually the local Worker: it separates
processes and faults, but provides no credential isolation from that UID. A native
shell with access can reach sockets and control state or read the approval secret;
the trusted-local assumption and open `SEC-002` limitation apply (see
[Security](../../SECURITY.md)).

Storage counts logical inputs, intermediates, outputs and logs. Inputs remain charged
even if deleted. Every solver file is counted; retained stdout mirrors are conservatively included in the terminal observation. Local and remote runners
sample directory sizes and terminate the process group on excess. The manifest reports
**observed high water**, sample interval and overshoot, not an instantaneous peak or a
filesystem hard quota. Scientific input staging, archives, SSH transfers and final CAS
ingestion stream files; small JSON and diagnostic views retain separate limits.

Transfer settings are separate from solver authorization and RAM. In core
`agent-settings.json`, `execution_io` configures `max_export_bytes` (default
2,000,000,000), `read_page_bytes` (16,384), `collection_timeout_seconds` (600),
`file_timeout_seconds` (120) and `idle_timeout_seconds` (30). Bytes and seconds are
explicit units. Global settings merge with explicit instance fields when a Run is
created; recovery retains its snapshot. Export and collection also respect remaining
Run time. Raising a transfer limit does not authorize a larger solver job.

Current implementation and unverified acceptance items are recorded in the single
[R4 plan](../../docs/plans/RESEARCH_TASK_REFACTOR_R4.zh-CN.md). Historical solver or
helper transport probes are not full scientific-chain acceptance.

### Revision budgets, file bindings and diagnostic recovery

Control derives the budget owner from the exact research objective, following sealed parents. Implementation revisions keep independent identities while sharing a durable allowance pool. Before submit, the full request is reserved atomically; terminal runner observations settle elapsed wall time and retained storage high water. Missing observations and unknown submissions retain their reservation. Policy tightening reduces the remaining pool and never erases consumed usage.

SDevice grid files are declared through the experiment's `scientific_files` and
mapped to implementation input slots by scientific name. File references are streamed
from exact CAS originals; the control package retains exact slot and parent identity.
They do not enter the model as inline text, but runner total storage still applies.
Changing a scientific input creates a new implementation; applicable qualification
must be re-established rather than inherited by a name.

Debug receipts live in control storage separately from the budget ledger. Recovery verifies exact submission and file hashes, permits only the same Run or a control-recorded recovery lineage, restores all relevant modes and reruns candidate finalization. Cached responses alone never establish trusted records. Each attempt carries its actual mode/selection collection limits through child collection and finalization. Stdout uses `.scid-capture/solver_stdout.log`; existing solver logs remain original files.

Unsubmitted requests retain immutable authorization history plus one current policy decision. Reauthorization of the same request/owner/budget retains one reservation; a human/deny reassessment atomically releases it only before any prepared submission exists. Prepared or unknown submissions require exact lookup and keep their original
reservation. Repairs retain exact prior scientific inputs unless the task intentionally
changes them; optional review does not replace source or execution identity checks.
