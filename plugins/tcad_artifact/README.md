# TCAD Artifact Plugin

[简体中文](README.zh-CN.md) | English

`tcad_control` is the execution adapter for prepared TCAD jobs. It exposes
exactly four operations: submit, status, cancel, and collect.

It owns only operational run directories and detached process state. Artifact
identity, task identity, approval, execution identity, and result registration
remain in SciDiscovery.

The accepted payload is a canonical JSON `TCADJobSpec` containing a local
archive descriptor, an archive member manifest, one deployment-owned tool
profile, resource limits, and expected output paths. The dispatcher does not
generate or assess scientific models or decks.

Deployment files:

- `deploy/systemd/tcad-control.service.in`
- `config/execution-policy.example.json`

The socket is internal to `ExecutionBridge`; it is not registered as a Codex or
Claude MCP. Interactive clients receive only the SciDiscovery root tools.
Cross-machine deployment uses the bounded command contract documented in
`docs/tcad_transport_contract.md`. The optional SSH transport invokes the
dependency-free `remote_runner_py36.py` through an existing user-authorized
OpenSSH connection; it does not install a Python package or system service
inside the simulator host.

The plugin also supplies TCAD deck author, reviewer, and reviser roles plus
deterministic transforms for patching, project comparison, exact review
validation, reviewed packaging, and runtime attestation. These components do
not distribute or replace Synopsys software or licensing.
