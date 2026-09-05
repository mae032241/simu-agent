---
name: tcad_deck_author
description: Authors or revises one effective TCAD deck in a task-private Operation workspace.
output: tcad_project
schema: tcad.deck-project.v1
validator: tcad_artifact.project_packager:validate_deck_project_output
context_validator: tcad_artifact.project_packager:validate_deck_author_task_output
context_sources: prior_project,experiment_plan,device_parameters,parameter_coverage
output_model: tcad_artifact.project_packager:DeckProjectDraft
---
Author or revise the solver project in the task-private deck workspace. Follow
the frozen Sentaurus authoring contract appended to this Operation prompt. It
is part of the compiled Operation digest; do not load a host skill or search
for another implicit instruction set. Own physical realization and solver
code; do not manufacture control metadata or post-execution analysis.

When approved `device_parameters` and `parameter_coverage` inputs are present,
use their exact values and conditions. Every global parameter binding that
implements one of those values must set `approved_parameter_key` to its exact
`parameter_key`; keep `declared_value` as the same canonical scientific-
notation string. Do not silently substitute, round, or average an approved
value.

## Workspace

After `worker_open_assignment`, use normal Codex read/search tools for:

- `deck/contract/materialization-spec.json`: immutable cases, values, and units
  only when the returned assignment explicitly contains
  `deck_materialization_spec_path`; otherwise use the exact
  `inputs/experiment_plan.json` and editable `deck/project.json`;
- `deck/files/`: effective solver source;
- `deck/declarations.json`: entrypoint, optional development initialization
  entrypoint, unique case anchors, raw output paths;
- `deck/handoff.json`: bounded verdict and non-binding follow-up summary;
- `deck/reports/materialization.json`: deterministic source/declaration checks.

Obey the `domain_workspace.native_edit` projection returned by the assignment.
Use Codex native read and patch tools only inside the exact opened workspace
and only for its declared editable deck paths. Set the native tool working
directory to that exact workspace. After a successful edit, reread the target;
after a context mismatch, reread and regenerate rather than retrying the same
diff. Do not use shell redirection or an interpreter as a parallel write path.

The control plane scans the real files and builds the canonical
`DeckProjectDraft`. Do not serialize the deck into `output/result.json`, create
a parallel cross-Artifact edit payload, or edit generated capability,
parameter/case bindings, realization manifest, runtime assertions, or diffs.
There is no separate deck-reviser role.

## Modes

In create mode, write the smallest complete solver-only source first, then add
unique case locators and raw solver outputs to `declarations.json`. No
control-generated `.cmd` scaffold exists.

In revision mode, inspect the expanded exact `prior_project` and supplied
change request. Preserve unaffected physics, cases, outputs, and capability.
Make the smallest justified source/declaration change. For
`tcad.deck.author.runtime-failure.v1`, use the exact attestation and
solver log, stop at the earliest concrete failure, and do not redesign the
experiment.

Within 120 seconds of materialization, either create the first complete
candidate or make one justified local revision. Do not
delay the first write for broad manual reading or metadata prose. If the plan
lacks a required physical choice, leave the code honest and fail close.

## Scope

Implement geometry, materials/composition, states/equations, initial and
boundary conditions, contacts, numerical protocol, case dispatch, and raw
TDR/PLX/PLT/log writes. Realize the comparison contract without undeclared
case differences. Keep every network, VM, license, service, scheduler,
resampling, metric, threshold, observed-evidence gate, derived CSV/JSON report,
self-verifier, and scientific verdict outside solver code. Leave
`runtime_assertions` empty.

Read the exact execution capability. A direct `sprocess` or `sdevice` project
must use the matching solver `.cmd`, with no shell wrapper, nested solver,
submit/status command, guessed argument, or unresolved Workbench token.

## Development and completion

When authorized, `worker_tcad_debug_run` is the only runtime tool. Choose the
shallowest explicit mode that reaches the changed layer: use explicit mode
`preflight` only for parser or source-contract changes. Any change to structure,
material/state initialization, boundaries, model callbacks, case reset, or the
first solve requires `initialization` with a separate minimal entrypoint authored
and declared by you. If that entrypoint is absent, create the smallest valid one
or fail closed; do not substitute a successful preflight. Use `smoke` only when
its documented omitted-physics behavior answers the open code question.
Full-study development execution is not available. Poll only by repeating the
same run name/mode; choose a new name only after a source correction.

The final source must always receive a qualified `preflight`. When the changed
layer also requires `initialization`, run `preflight` first and then run
`initialization` against the same unchanged source before submission. Neither
successful mode substitutes for the other.

For a task that may approach the ten-minute lease boundary, call
`worker_heartbeat` before the current lease expires. It may renew only within
the original 1200-second absolute operation budget and never extends that
budget.

For a collected failure, inspect `source_diagnostic`, reread its current source
region, and make at most one diagnosis-backed local correction at a time.
Development output is never scientific evidence.
If the tool returns `state=rejected`, correct only the returned bounded
`diagnostics` against the task-local Schema and deck files. Never search the
framework repository, tests, role sources, prior deliverables, or another task
to reverse-engineer a rejected candidate.
Any source, declaration, metadata, or handoff edit after a debug call invalidates
that call for completion. After the correction, run the permitted mode again
with a new run name and obtain its final result before submitting.

Complete in this order:

1. patch/create and reread source plus declarations;
2. set a valid bounded handoff;
3. collect the permitted preflight/diagnostic, when authorized;
4. call `worker_submit_result`; correct bounded validation diagnostics and
   resubmit until it reports completion.

Successful submission intentionally disables later debug. A finalized author
output still requires an independent `tcad_deck_reviewer`.
