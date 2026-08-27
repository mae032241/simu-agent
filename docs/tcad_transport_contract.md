# TCAD Transport Contract

The interactive Agent never receives machine credentials or a solver-side
control socket. `CommandTCADExecutorAdapter` invokes one administrator-owned,
short-lived executable for each operation. The executable reads one canonical
JSON object from standard input and writes one bounded JSON response to standard
output.

Request envelope:

```json
{
  "schema_version": 1,
  "operation": "capabilities|prepare|submit|status|cancel|collect",
  "payload": {}
}
```

Successful response:

```json
{
  "schema_version": 1,
  "operation": "status",
  "ok": true,
  "payload": {}
}
```

The operations are deliberately small:

- `capabilities` accepts no payload and returns the currently active immutable
  public solver snapshots. This reads configured release evidence; it does not
  run or invent a solver version probe.
- `prepare` receives local descriptors for `job.json` and `project.tar` and
  returns the descriptor that the solver-side user runner can read.
- `submit` returns immediately with `run_id` and `state`.
- `status` performs one short state query and returns one state.
- `cancel` requests cancellation and returns immediately with the observed state.
- `collect` runs only after terminal state, materializes verified outputs under
  the supplied local result root, and returns their descriptors.

The transport must not wait for a solver job, repeatedly poll, generate a deck,
change the package, approve a request, or write SciDiscovery state. Credentials,
connectivity, and the production tool policy stay in administrator-owned
configuration outside the Agent boundary.

Each public `tcad.solver-capability.v2` snapshot is an allowlist projection. It
contains an explicit `solver_kind`, launch basename, administrator-opted-in
`public_arguments`, a constrained `public_release_label`, counts/digests for
the complete private fixed arguments and release evidence, and the unchanged
digest of the complete private tool profile. It never projects private fixed
arguments, full release evidence, the full executable path, environment
variables, SSH configuration, or license values. `public_arguments` default to
empty and must be an ordered exact subset of configured fixed arguments. The
label defaults from a safe profile name and permits no path, URI, or credential
syntax. Version 1 snapshots fail closed. Root MCP lists only the public v2
summary; an explicit
`execution_capability_bind` freezes the selected snapshot under a semantic
artifact name for task-local use as `execution_capability`.

Production preparation accepts only `tcad.reviewed-deck-package.v2`. The deck
author copies the selected profile, solver kind, and capability digest into the
project; the independent reviewer copies and verifies the same digest. The
reviewed package embeds the public snapshot, and the generated JobSpec binds
its opaque private-profile digest. The adapter rediscovers the active snapshot
during request validation and again immediately before authorization and
submission. Local and remote runners finally recompute the complete configured
profile digest and reject executable, fixed-argument, environment, solver-kind,
or release-evidence drift before launch.

Prepared jobs use `TCADJobSpec` wire schema v2 and require a trusted
`execution_purpose` of either `production` or `development_debug`. Every
existing reviewed-package and project-packaging path hard-codes `production`;
worker or reviewed payload content cannot select or downgrade this field. The
task-bound development controller constructs `development_debug` only within
its trusted adapter boundary. Purpose is part of canonical job bytes, so an
otherwise identical debug submission cannot deduplicate to, or be reused as,
an approved production run. Legacy v1 jobs without the field fail closed in
both local and remote runners.

## Task-bound development debugging

The worker surface exposes one operation,
`worker_tcad_debug_run(run_name, mode)`, only to a claimed `tcad_deck_author`
attempt that has exactly one task-local v2 solver capability. `mode` is required
and limited to `preflight|smoke`; a run name is permanently bound to its first
mode. The trusted adapter, not the worker, injects the exact release-matched
arguments: SProcess R-2020.09 uses `-s` or `-f`, while SDevice uses `-P` or
`-i`. It also clears all scientific expected outputs. Preflight is capped at
60 seconds, smoke at 180 seconds, and the fixed task/attempt/session/capability
lease permits no more than six runs, 360 aggregate solver-seconds, and 900
wall-clock seconds. A new name validates and freezes the current staged project
and exact task inputs, while repeating the same name and mode only polls or
collects; adapter run identifiers never cross the worker boundary. The worker
cannot supply a full-study mode, shell, command, arguments, environment,
credentials, network target, or path outside its frozen project and declared
input slots.

Collected logs are sanitized and reduced to the earliest parser,
initialization, numerical, output-contract, resource, or runtime layer. Files
are name-, count-, per-file-, and aggregate-size bounded before registration.
Candidate snapshots, diagnostics, and outputs enter only task-private
provisional CAS with `development_only=true` and
`scientific_claim_admissible=false`. They never create an `ExecutionRequest`,
approval, production execution result, task output attachment, or readiness
object. A retry may inspect the frozen prior-attempt context, but the final
project still requires ordinary independent deck review and the separate
approved production execution path. Only that production path may execute and
qualify the complete planned case portfolio.

Expiry does not erase an external run binding. A token-independent bounded
reconciler cancels runs whose task/attempt/session lease is no longer active,
polls terminal state, collects bounded diagnostics into provisional CAS, and
then removes the private exchange directory. Task/orphan/instance cleanup must
remain blocked while a debug row is prepared, submitted, running, cancelling,
or terminal-but-uncollected.

For the supported VMware deployment, each transport call invokes the existing
Windows OpenSSH client and a dependency-free Python 3.6 runner in the VM
user's project directory. No VM-side SciDiscovery service, new SSH key, sudo,
or port proxy is required.

The worker broker must receive the same administrator-selected
`--tcad-socket` or `--tcad-command-config` as the control daemon. Real debug
runs additionally require an installed `sprocess` or `sdevice` profile, valid
license/runtime configuration in the private runner policy, and reachable
local or SSH transport. Deterministic test executables validate only the
control and transport boundary; they do not establish real Sentaurus success
or scientific correctness.
