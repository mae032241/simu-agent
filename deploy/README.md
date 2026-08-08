# Deployment Entry Points

[简体中文](README.zh-CN.md) | English

- `install.sh`: installs, verifies, reports, or removes the Linux/WSL services.
- `install_ssh_tcad_runner.sh`: validates or installs the dependency-free
  runner through an existing SSH connection.
- `systemd/*.service.in`: rendered service templates; do not edit generated
  units under `/etc/systemd/system` directly.

The installer infers the repository root from its own location. Machine values
are supplied through `SCID_*` environment variables and private copies of the
JSON examples. See [the complete installation guide](../docs/INSTALL.md).

No deployment command installs Sentaurus, a license, a VM, or an SSH key.
