# TCAD Artifact Plugin

[简体中文](README.zh-CN.md) | English

`tcad_control` is the execution adapter for prepared TCAD jobs. It exposes
five operations: capability discovery, submit, status, cancel, and collect.

It owns only operational run directories and detached process state. Artifact
identity, task identity, approval, execution identity, and result registration
remain in SciDiscovery.

The accepted payload is a canonical JSON `TCADJobSpec` containing a local
archive descriptor, an archive member manifest, one deployment-owned tool
profile, a required trusted execution purpose, resource limits, and expected
output paths. Current reviewed/package flows always set `production`; schema
v1 jobs without a purpose are rejected. The dispatcher does not generate or
assess scientific models or decks.

The reviewed-package transform also requires the exact `experiment_plan`.
Before producing an executable package it verifies that every case-varying
scientific comparison control is source-bound for every case; a frozen control
may instead use one matching global binding. Missing realization coverage is a
pre-execution error, not a post-run Control Equivalence surprise.

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

The plugin also supplies one TCAD deck author role for initial authoring and
bounded revision, plus an independent code reviewer. Deterministic project
comparison, exact review validation, reviewed packaging, runtime attestation,
and legacy patch compatibility remain control-owned. These components do
not distribute or replace Synopsys software or licensing.

The new direct-solver author flow uses a solver-neutral declaration materializer.
A worker writes the complete solver project plus explicit case anchors and raw
solver-output paths; it does not fill capability identity, resource policy,
case-binding tables, realization rows, runtime assertions, or project diffs.
Control validates paths, exact case coverage, immutable plan values/units,
source hashes, and collection bounds. It contains no material names, state
variables, equations, boundaries, or solver-command grammar, and never
generates a `.cmd` scaffold. The independent reviewer reads the complete source
and judges physical fidelity, numerical reasoning, case isolation, declared raw
outputs, and explicit code defects as one holistic review; it does not restate
per-requirement rows. Packaging re-materializes the exact source declarations
and requires a passing source-bound preflight and review.

Direct solver projects are deliberately narrow: they contain physical solver
code, inputs, parameters, and raw TDR/PLX/PLT/log output declarations. Curve
resampling, masks, derived metrics, observed-data eligibility, thresholds, and
scientific verdicts must be implemented by a separately versioned domain
transform/scorer after execution; they are never deck responsibilities.
