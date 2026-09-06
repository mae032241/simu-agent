# Installation

[简体中文](INSTALL.zh-CN.md) | English

## 1. Supported Environment

- Linux or WSL2 with systemd
- Python 3.10 or newer with `pip`, `setuptools>=68`, `packaging`,
  `pydantic>=2,<3`, and `jsonschema>=4,<5`
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
  'pydantic>=2,<3' 'jsonschema>=4,<5' 'setuptools>=68' packaging pip
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

`reinstall.sh` installs no domain plugin by default. Select
`tcad_artifact,curve_score` or other plugins explicitly with `SCID_PLUGINS`, and an external adapter with
`SCID_TCAD_COMMAND_CONFIG`. `install` and `reinstall` use the same
transactional flow; no argument is equivalent to `install`.

Automatic figure extraction uses the three generic domain plugins. Supply
Pillow **12.1.1**, Poppler **22.02.0** (`pdfinfo`, `pdfimages`, `pdftoppm`),
Tesseract and an existing, readable `eng.traineddata` model offline. Tesseract's
exact supplied executable version and the model's verified SHA-256 are explicit
installation inputs; no executable or model version is guessed. Replace the two
placeholders below with values verified against your offline supply:

```bash
export SCID_PYTHON=/absolute/path/to/service/python
"$SCID_PYTHON" -m pip install --no-index --find-links /srv/scid-offline/wheels 'Pillow==12.1.1'
export SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence
export SCID_PLATFORM=codex SCID_WORKER_BACKEND=local
export SCID_WORKSPACE=/srv/scid-project
export SCID_CODEX_LAUNCH_ROOT=/srv/scid-codex
export SCID_SERVICE_USER="$(id -un)" SCID_SERVICE_GROUP="$(id -gn)"
export SCID_FIGURE_TESSERACT_VERSION='<exact supplied version>'
export SCID_FIGURE_OCR_MODEL_PATH=/srv/scid-offline/tessdata/eng.traineddata
export SCID_FIGURE_OCR_MODEL_SHA256='<verified 64-character SHA-256>'
deploy/reinstall.sh --dry-run
# After the installation/review gates have passed:
deploy/reinstall.sh reinstall
```

The workspace and launch directories must already exist and be separate from
the checkout. Run the generic wrapper as the service user; it forwards these
three supply variables through `sudo`. The installer executes real Python
imports, version calls, PDF extraction/rendering and OCR under that service
identity and systemd's effective default PATH before creating the installation
transaction. The operator's shell PATH is not the dependency check.

The verified binding is written once to
`site/curve_figure_evidence/figure_dependencies.json` in the staged installation,
then checked again with the selected service Python before switching and after
installation. The existing detector resource includes these bytes in the
request/materialize Operation digests. Activation makes the installation prefix
read-only. The separate Python runtime identity check does not hash application files.
Runtime uses the recorded absolute executable/model paths and rechecks model
bytes and versions. Changing an environment variable does not change this
installed contract: supply a new installation for a new model. The model itself
is not copied or downloaded. An ordinary wheel without this supplied record can
compile but is unavailable for verified OCR and cannot pass figure installation.

The current trusted Local backend provides soft isolation, not an OS sandbox.
The production package, runtime resources, default configuration and explicit
Worker context must not include case geometry, historical answers or paths that
act as answer-discovery inputs. Historical audit documents may retain locators,
but the runtime must not consume them. Record readable host probes honestly and
claim only that those files were not supplied or observed in use; `SEC-002`
remains a known issue. Check for queued or running old-contract Runs before any
approved switch; cross-digest recovery is not promised. The automatic Operation
does not bind the manual `scientific-paper-evidence` skill.

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
  SCID_WORKER_BACKEND=local \
  deploy/install.sh install
```

The installation creates:

- `/opt/scidiscovery/site`: immutable installed Python packages;
- `/var/lib/scidiscovery`: control-plane state;
- `/var/lib/scidiscovery-tcad`: local execution state when used;
- `/etc/scidiscovery`: generated secrets and execution policy;
- `/run/scidiscovery/control.sock`: Root MCP socket;
- `scidiscovery-control.service`;
- `scidiscovery-approval-ui.service`;
- per-Operation local stdio MCP profiles for supported Agent Operations; no central worker service;
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

When Codex is actually launched outside both the source root and workspace, set
that existing absolute directory as `SCID_CODEX_LAUNCH_ROOT`. The installer
generates, backs up, and verifies its `.codex` and `AGENTS.md` in the same
transaction so the launch directory cannot retain stale MCP definitions. When
`SCID_WORKSPACE` points outside the source tree, the installer emits an
equivalent project-local runtime profile there because it cannot inherit the
framework root. This does not duplicate research data or control-plane state.

```bash
export SCID_CODEX_LAUNCH_ROOT=/absolute/directory/where/codex/is/started
```

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
| `SCID_CODEX_LAUNCH_ROOT` | unset | Optional actual Codex launch directory; receives the same-generation project profile when distinct from source and workspace |
| `SCID_PYTHON` | first `python3` on `PATH` | Base interpreter |
| `SCID_SERVICE_USER` | `SUDO_USER` or current user | Service account |
| `SCID_SERVICE_GROUP` | primary group of service user | Socket/file group |
| `SCID_PLATFORM` | `codex` | Codex platform selector; other values are rejected |
| `SCID_WORKER_BACKEND` | `local` | `local` is the trusted native-tool path; `hardened` is the MCP-only file backend, and the value drives daemon, systemd, Codex profiles, and install verification together |
| `SCID_PLUGINS` | empty | Comma-separated local plugin directory names, for example `tcad_artifact,curve_score,curve_figure_evidence` |
| `SCID_FIGURE_TESSERACT_VERSION` | unset | Required exact offline executable version when figure is selected |
| `SCID_FIGURE_OCR_MODEL_PATH` | unset | Required existing absolute `eng.traineddata` path, readable by the service |
| `SCID_FIGURE_OCR_MODEL_SHA256` | unset | Required verified SHA-256 of the supplied model; frozen into the installed detector resource |
| `SCID_INSTALL_ROOT` | `/opt/scidiscovery` | Installed package root |
| `SCID_STATE_ROOT` | `/var/lib/scidiscovery` | Control-plane state |
| `SCID_CONFIG_ROOT` | `/etc/scidiscovery` | Secrets and policy |
| `SCID_APPROVAL_PORT` | `8765` | Loopback approval UI port |
| `SCID_TCAD_COMMAND_CONFIG` | unset | External command adapter configuration |

`hardened` currently rejects Operations requiring shell, code, or `view_image`,
so TCAD Deck authoring v1 uses `local`. Effect approval and adapter boundaries
remain independent of that choice.

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

## 9. Troubleshooting

- **A base Python dependency is missing**: install the reported dependency in
  the selected Conda or system Python environment, then rerun the installer.
  Deployment itself is offline and does not resolve third-party packages.
- **MCP socket missing**: inspect
  `journalctl -u scidiscovery-control.service -n 100`.
- **Agent Run timeouts**: inspect `run_status`; create a new Run after failure
  rather than overwriting the old result or current binding.
- **Approval returns 403**: open the exact URL on the same host and verify the
  process is bound to the intended ResearchInstance.
- **VM address changed**: use a resolver or update only the private transport
  configuration; never hard-code a discovered address in source.
- **TCAD job appears stuck**: use short status calls. Never hold SSH open while
  the solver runs.
