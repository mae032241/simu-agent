# Installation

[简体中文](INSTALL.zh-CN.md) | English

## 1. Supported Environment

- Linux or WSL2 with systemd
- Python 3.10 or newer with `pip`
- Codex CLI, Claude Code, or both
- `poppler-utils` for bounded PDF extraction
- `bubblewrap` for isolated worker analysis
- `curl` for service health checks
- OpenSSH client for remote TCAD execution

Sentaurus, its license, and any VM are external prerequisites.

On Debian, Ubuntu, or WSL:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip poppler-utils bubblewrap curl openssh-client
```

The installer uses the selected base Python executable but installs application
packages and their dependencies into `/opt/scidiscovery/site`. It does not
create a virtual environment and does not modify Conda base packages.

## 2. Obtain the Source

```bash
git clone <repository-url> scidiscovery-agent
cd scidiscovery-agent
```

Do not run the services from `/mnt/c` under WSL. Use the WSL filesystem, for
example `~/src/scidiscovery-agent`.

## 3. Select the AI Platform

`SCID_PLATFORM` accepts:

- `codex` (default): generates `.codex/config.toml`, role TOMLs, and the managed
  scheduler block in `AGENTS.md`;
- `claude`: generates `.mcp.json`, `.claude/agents/*.md`, and the managed block
  in `CLAUDE.md`;
- `both`: generates both configurations.

Generated files contain absolute local paths. Regenerate them on every machine
and do not commit them.

## 4. Local Deployment Smoke

This mode validates the services and MCP surfaces without running a scientific
solver. The internal TCAD controller allow-lists `/bin/true` only.

```bash
PYTHON="$(command -v python3)"

# Optional source preview. It requires the dependencies to be importable by
# the selected base Python.
SCID_PYTHON="$PYTHON" deploy/install.sh --dry-run

sudo SCID_PYTHON="$PYTHON" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  deploy/install.sh install
```

The installation creates:

- `/opt/scidiscovery/site`: immutable installed Python packages;
- `/var/lib/scidiscovery`: control-plane state;
- `/var/lib/scidiscovery-tcad`: local execution state when used;
- `/etc/scidiscovery`: generated secrets and execution policy;
- `/run/scidiscovery/control.sock`: Root MCP socket;
- `/run/scidiscovery-worker/worker.sock`: worker MCP socket;
- `scidiscovery-control.service`;
- `scidiscovery-worker.service`;
- `scidiscovery-approval-ui.service`;
- `tcad-control.service` only for local-adapter mode.

The approval UI listens only on <http://127.0.0.1:8765>.

Restart Codex or Claude Code after installation.

## 5. Remote TCAD VM

### 5.1 Configure the VM runner

Create a private local copy of the example; do not edit the tracked example with
real license or host data:

```bash
mkdir -p config/local
cp plugins/tcad_artifact/config/remote-runner.example.json \
  config/local/remote-runner.json
```

Edit the copied file:

- set the real `sprocess`/`sdevice` executable paths;
- set `STROOT`, `PATH`, and license environment variables;
- add one unique `profile_id` for each allowed solver profile;
- set VM-user-owned state and exchange roots.

Install the dependency-free runner through an existing passwordless SSH path:

```bash
SCID_SSH_DESTINATION='tcad@vm-host-or-ip' \
SCID_SSH_IDENTITY="$HOME/.ssh/id_ed25519" \
SCID_REMOTE_RUNNER_ROOT='/home/tcad/scidiscovery-tcad' \
SCID_REMOTE_RUNNER_CONFIG="$PWD/config/local/remote-runner.json" \
deploy/install_ssh_tcad_runner.sh install
```

The script does not create an SSH key and does not install a VM system service.
It uploads a Python 3.6-compatible runner under the VM user account.

For VMware DHCP discovery, set all of the following instead of a fixed
`SCID_SSH_DESTINATION`:

```bash
export SCID_SSH_DESTINATION_FALLBACK='tcad@192.0.2.10'
export SCID_VMRUN_EXE='/path/to/vmrun'
export SCID_VMX_PATH='/path/to/guest.vmx'
```

### 5.2 Configure the WSL/Linux transport

```bash
sudo install -d -o root -g "$(id -gn)" -m 0750 /etc/scidiscovery

sudo install -o root -g "$(id -gn)" -m 0640 \
  plugins/tcad_artifact/config/ssh-transport.example.json \
  /etc/scidiscovery/tcad-transport.json

sudo install -o root -g "$(id -gn)" -m 0640 \
  plugins/tcad_artifact/config/command-adapter.example.json \
  /etc/scidiscovery/command-adapter.json
```

Edit `/etc/scidiscovery/tcad-transport.json` and set:

- SSH executable and optional identity;
- destination or VMware resolver;
- known-hosts file and stable host-key alias;
- remote runner, config, and exchange paths.

For Windows OpenSSH from WSL, a typical executable is
`/mnt/c/Windows/System32/OpenSSH/ssh.exe`; identity and known-hosts values use
the syntax expected by that executable.

Install the services with the external adapter selected:

```bash
PYTHON="$(command -v python3)"
sudo SCID_PYTHON="$PYTHON" \
  SCID_SERVICE_USER="$USER" \
  SCID_SERVICE_GROUP="$(id -gn)" \
  SCID_PLATFORM=codex \
  SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
  deploy/install.sh install
```

The external adapter replaces the local `tcad-control.service`. SSH operations
are bounded and return immediately; the VM runner owns detached execution and
durable `running`, `status`, and `done` records.

## 6. Verify

```bash
deploy/install.sh status

systemctl is-active \
  scidiscovery-control.service \
  scidiscovery-worker.service \
  scidiscovery-approval-ui.service

curl -fsS http://127.0.0.1:8765/ >/dev/null
pytest -q
```

For an external TCAD setup, first verify SSH and the configured runner with a
deployment-smoke tool profile. A service health check does not qualify a
scientific model or a Sentaurus license.

## 7. Configuration Reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `SCID_WORKSPACE` | repository root inferred from the script | Source/project root |
| `SCID_PYTHON` | first `python3` on `PATH` | Base interpreter |
| `SCID_SERVICE_USER` | `SUDO_USER` or current user | Service account |
| `SCID_SERVICE_GROUP` | primary group of service user | Socket/file group |
| `SCID_PLATFORM` | `codex` | `codex`, `claude`, or `both` |
| `SCID_ENABLE_INGAAS_FIG4` | `0` | Install the optional domain example when set to `1` |
| `SCID_INSTALL_ROOT` | `/opt/scidiscovery` | Installed package root |
| `SCID_STATE_ROOT` | `/var/lib/scidiscovery` | Control-plane state |
| `SCID_CONFIG_ROOT` | `/etc/scidiscovery` | Secrets and policy |
| `SCID_APPROVAL_PORT` | `8765` | Loopback approval UI port |
| `SCID_TCAD_COMMAND_CONFIG` | unset | External command adapter configuration |

The remote-runner script documents additional `SCID_SSH_*`, `SCID_VMRUN_*`,
and `SCID_REMOTE_*` variables through `--dry-run` output and its source header.

## 8. Upgrade and Uninstall

Re-run `install`; packages and generated platform configuration are replaced
atomically and the previous configuration is backed up under
`/var/backups/scidiscovery`.

```bash
sudo deploy/install.sh uninstall
```

Uninstall removes services but preserves state, configuration, and backups.
Delete those directories only after an explicit archival decision.

## 9. Troubleshooting

- **`pydantic` or `pydantic-core` cannot be installed**: verify Python is 3.10+
  on a supported Linux architecture and that `pip` can access wheels or a local
  wheelhouse.
- **MCP socket missing**: inspect
  `journalctl -u scidiscovery-control.service -n 100`.
- **Worker timeouts**: inspect `task_status` phase timestamps before retrying;
  do not overwrite an active worker attempt.
- **Approval returns 403**: open the exact URL on the same host and verify the
  process is bound to the intended ResearchInstance.
- **VM address changed**: use a resolver or update only the private transport
  configuration; never hard-code a discovered address in source.
- **TCAD job appears stuck**: use short status calls. Never hold SSH open while
  the solver runs.
