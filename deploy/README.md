# Deployment Entry Points

[简体中文](README.zh-CN.md) | English

- `install.sh`: installs, verifies, reports, or removes the Linux/WSL services.
- `reinstall.sh`: generic, transactional, maintained reinstall entrypoint.
- `install_ssh_tcad_runner.sh`: installs the dependency-free runner through an
  existing SSH connection; it can also reuse the active transport for a full
  runner/config update or a current-schema code-only upgrade.
- `init_workspace.sh`: initializes a source-separated research workspace with
  `0750` permissions.
- `install_transaction.py`: snapshots and rolls back the site, units, config,
  skills, launchers, and SQLite state as one install transaction.
- `systemd/*.service.in`: rendered service templates; do not edit generated
  units under `/etc/systemd/system` directly.

The installer builds and validates the release site offline before stopping
services, then activates it transactionally. A failed health check restores the
previous files, databases, and service state. The installer infers the
repository root from its own location. Machine values
are supplied through `SCID_*` environment variables and private copies of the
JSON examples. See [the complete installation guide](../docs/INSTALL.md).

For automatic figures, explicitly select `tcad_artifact,curve_score,curve_figure_evidence`
and supply the offline tool/model contract described in that guide. Both dry-run
and installation validate it under the service identity before any transaction.
No paper-specific installation wrapper or manual geometry skill is installed.

No deployment command installs Sentaurus, a license, a VM, or an SSH key.
The installer passes the same selected TCAD socket or command-adapter
configuration to both control and worker daemons. This enables bounded
development debug without exposing the private solver profile to a worker;
actual `sprocess`/`sdevice` runs still require the administrator-provided
solver, license, and transport configuration.
