# Installation

[简体中文](INSTALL.zh-CN.md) | English

## 1. Supported Environment

- Linux or WSL2 with systemd
- Python 3.10 or newer with `pip`, `setuptools>=68`, `packaging`,
  `pydantic>=2,<3`, and `PyYAML>=6,<7`
- Codex CLI
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

The installer uses the selected base Python executable and installs only the
repository's application packages into `/opt/scidiscovery/site`. It does not
create a virtual environment, download dependencies, or modify the selected
Python environment. Provide third-party dependencies before deployment. For a
Conda base environment:

```bash
conda install -n base -c conda-forge \
  'pydantic>=2,<3' 'pyyaml>=6,<7' 'setuptools>=68' packaging pip
```

The install prints each phase and performs the local package build before it
stops an existing service deployment. Activation is transactional: exact
release/configuration targets and SQLite databases are snapshotted, and a
failed service or MCP health check restores the previous files and service
state. Successful transaction evidence is retained under
`/var/backups/scidiscovery/transactions/`.

The generic transactional reinstall entrypoint is:

```bash
SCID_WORKSPACE="$PWD/workspace/<project-name>" \
  deploy/reinstall.sh --dry-run
SCID_WORKSPACE="$PWD/workspace/<project-name>" \
  deploy/reinstall.sh reinstall
```

`reinstall.sh` defaults to the generic `tcad_artifact,curve_score` plugins.
Select additions with `SCID_PLUGINS` and an external adapter with
`SCID_TCAD_COMMAND_CONFIG`. `install` and `reinstall` use the same
transactional flow; no argument is equivalent to `install`.

For the bundled InGaAs/Fig.4 configuration, the project profile supplies only
the workspace, `ingaas_fig4` plugin, and command-adapter defaults before it
delegates to the generic entrypoint:

```bash
deploy/apply_ingaas_fig4_profile.sh --dry-run
deploy/apply_ingaas_fig4_profile.sh reinstall
deploy/apply_ingaas_fig4_profile.sh status
```

Run both entrypoints as the normal service user; the generic wrapper invokes
`sudo`. Maintain common installation behavior only in `reinstall.sh`, and keep
paper/project differences in their profile scripts and plugins.

## 2. Obtain the Source

```bash
git clone <repository-url> scidiscovery-agent
cd scidiscovery-agent

deploy/init_workspace.sh ingaas-paper
export SCID_WORKSPACE="$PWD/workspace/ingaas-paper"
```

The Git repository contains framework source only. Every research project must
live under the Git-ignored `workspace/<project-name>/` tree; papers, parameters,
research ledgers, simulator projects, logs, and results belong in that project's
subdirectories.

Do not run the services from `/mnt/c` under WSL. Use the WSL filesystem, for
example `~/src/scidiscovery-agent`.

## 3. Select the AI Platform

`SCID_PLATFORM` accepts only `codex`. It generates `.codex/config.toml`, role
TOMLs, and the managed generic scheduler block at the framework source root;
nested workspaces inherit that configuration.

Generated files contain absolute local paths. Regenerate them on every machine
and do not commit them. A workspace `AGENTS.md` contains project-specific
constraints only; installation migrates the old layout by removing its
duplicate managed scheduler block.

## 4. Local Deployment Smoke

This mode validates the services and MCP surfaces without running a scientific
solver. The internal TCAD controller allow-lists `/bin/true` only.

```bash
PYTHON="$(command -v python3)"

# Optional source preview. It requires the dependencies to be importable by
# the selected base Python.
SCID_WORKSPACE="$SCID_WORKSPACE" \
  SCID_PYTHON="$PYTHON" deploy/install.sh --dry-run

sudo SCID_PYTHON="$PYTHON" \
  SCID_WORKSPACE="$SCID_WORKSPACE" \
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

Restart Codex after installation. Start it directly from the framework root:

```bash
codex -C "$PWD"
```

You may also start it in the default nested workspace, which inherits the root
MCP and Subagent configuration:

```bash
codex -C "$SCID_WORKSPACE"
```

When `SCID_WORKSPACE` points outside the source tree, the installer emits an
equivalent project-local runtime profile there because it cannot inherit the
framework root. This does not duplicate research data or control-plane state.

Do not rerun the installer for every Codex session. Reinstall only for the
initial deployment, an installation-configuration change, or an installed-code
update.

## 5. Remote TCAD VM

### 5.1 Configure the VM runner

Create a private local copy of the example; do not edit the tracked example with
real license or host data:

```bash
mkdir -p config/local
cp plugins/tcad_artifact/config/remote-runner.example.json \
  config/local/remote-runner.json
chmod 600 config/local/remote-runner.json
```

Edit the copied file:

- set the real `sprocess`/`sdevice` executable paths;
- set `STROOT`, `PATH`, and license environment variables;
- add one unique `profile_id` for each allowed solver profile;
- set VM-user-owned state and exchange roots.

The example explicitly contains one `sprocess` and one `sdevice` profile. Keep
`solver_kind` and non-empty `release_evidence` on both profiles, and point each
at an administrator-confirmed executable. Do not infer these values from an
executable name or from the other profile's environment.
Copying the file and changing only its permissions is not configuration; the
installer rejects a byte-for-byte copy of the tracked example.

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

After an active transport exists, use it for a standard full install whenever
the runner code or private profiles change. This is also the migration path
from an older single-profile config to the current dual-profile config:

```bash
SCID_PYTHON="$(command -v python3)" \
SCID_REMOTE_RUNNER_CONFIG="$PWD/config/local/remote-runner.json" \
deploy/install_ssh_tcad_runner.sh install-from-transport --dry-run

SCID_PYTHON="$(command -v python3)" \
SCID_REMOTE_RUNNER_CONFIG="$PWD/config/local/remote-runner.json" \
deploy/install_ssh_tcad_runner.sh install-from-transport
```

`install-from-transport` reads `/etc/scidiscovery/tcad-transport.json` by
default; set `SCID_TCAD_TRANSPORT_CONFIG` to select another absolute path. It
reuses the configured SSH executable, identity, destination resolver,
known-hosts, and exact remote paths. It runs `tcad_capabilities` against the
candidate runner and config in a temporary directory before replacing both;
a failed post-commit probe restores the previous files.
Every install mode that writes the VM requires an explicit
`SCID_REMOTE_RUNNER_CONFIG` and refuses to deploy the tracked example as the
private configuration.

Use `upgrade-code` only when the remote `runner.json` already conforms to the
current schema and only code must change. It neither uploads nor migrates the
configuration and fails closed against an old schema:

```bash
SCID_PYTHON="$(command -v python3)" \
deploy/install_ssh_tcad_runner.sh upgrade-code --dry-run

SCID_PYTHON="$(command -v python3)" \
deploy/install_ssh_tcad_runner.sh upgrade-code
```

For Windows OpenSSH from WSL, a typical executable is
`/mnt/c/Windows/System32/OpenSSH/ssh.exe`; identity and known-hosts values use
the syntax expected by that executable.

Install the services with the external adapter selected:

```bash
PYTHON="$(command -v python3)"
sudo SCID_PYTHON="$PYTHON" \
  SCID_WORKSPACE="$SCID_WORKSPACE" \
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
| `SCID_WORKSPACE` | `<source-root>/workspace/default` | Existing project workspace; must differ from the source root |
| `SCID_PYTHON` | first `python3` on `PATH` | Base interpreter |
| `SCID_SERVICE_USER` | `SUDO_USER` or current user | Service account |
| `SCID_SERVICE_GROUP` | primary group of service user | Socket/file group |
| `SCID_PLATFORM` | `codex` | Codex platform selector; other values are rejected |
| `SCID_PLUGINS` | `tcad_artifact,curve_score` | Comma-separated local plugin directory names, for example `tcad_artifact,curve_score,ingaas_fig4` |
| `SCID_INSTALL_ROOT` | `/opt/scidiscovery` | Installed package root |
| `SCID_STATE_ROOT` | `/var/lib/scidiscovery` | Control-plane state |
| `SCID_CONFIG_ROOT` | `/etc/scidiscovery` | Secrets and policy |
| `SCID_APPROVAL_PORT` | `8765` | Loopback approval UI port |
| `SCID_WEB_FETCH_ALLOW_FAKE_IP` | `0` | Set to `1` to let the worker accept `198.18.0.0/15` as a trusted TUN/Fake-IP mapping; other non-public addresses remain blocked |
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

After migrating from the retired `artifact-agent-vnext` or early
`tcad-control` deployments, audit their exact service roots and duplicate
user-local packages with:

```bash
deploy/cleanup_legacy_services.sh --dry-run
```

If the audit shows the current services are active and no current configuration
references those roots, remove them and retain the newest three SciDiscovery
installation backups with:

```bash
sudo deploy/cleanup_legacy_services.sh clean
```

The cleanup script never removes `/opt/scidiscovery`, `/etc/scidiscovery`,
`/var/lib/scidiscovery`, or `/var/lib/scidiscovery-tcad`.

### Clean control state without instance ownership

After an upgrade or old-instance deletion, run the administrative CLI as the
service account to preview tasks, approvals, executions, Artifact registrations,
and terminal runtime directories that no instance owns. Project workspace files
are outside this command's scope:

```bash
scid \
  --project-root "$SCID_WORKSPACE" \
  --state-root /var/lib/scidiscovery \
  --task-secret-file /etc/scidiscovery/task-token.key \
  --approval-secret-file /etc/scidiscovery/approval-receipt.key \
  --shared-group \
  state-orphans-cleanup
```

Before deletion, stop the control, worker, approval UI, and TCAD control
services and back up the state root. If the preview has no blockers, run one
explicit confirmation as the same service account:

```bash
scid \
  --project-root "$SCID_WORKSPACE" \
  --state-root /var/lib/scidiscovery \
  --task-secret-file /etc/scidiscovery/task-token.key \
  --approval-secret-file /etc/scidiscovery/approval-receipt.key \
  --shared-group \
  state-orphans-cleanup --confirm delete-orphan-state
```

The command preserves instance-bound objects and their provenance, blocks on
active work or unrecognized runtime entries, and reports SQLite and Artifact/CAS
integrity after deletion. Do not substitute manual SQL or recursive removal.

The same capability is available in the loopback dashboard's **System
maintenance** section. It shows aggregate counts without internal identities,
requires one `delete-orphan-state` confirmation, and displays the integrity
receipt. Web cleanup and instance deletion take the exclusive maintenance lock;
Root, Worker, and ordinary approval writes take the shared lock. An in-flight
operation therefore returns a conflict instead of permitting a partial cleanup.
The CLI remains available for offline recovery.

## 9. Troubleshooting

- **A base Python dependency is missing**: install the reported dependency in
  the selected Conda or system Python environment, then rerun the installer.
  Deployment itself is offline and does not resolve third-party packages.
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
