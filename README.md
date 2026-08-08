# SciDiscovery Agent

[简体中文](README.zh-CN.md) | English

SciDiscovery is a scientific-discovery orchestration service for Codex and
Claude Code. It separates scientific reasoning, immutable evidence, human
approval, deterministic transformations, and external simulator execution.
The included TCAD plugin supports reviewed Synopsys Sentaurus projects without
placing VM, SSH, license, or job-lifecycle concerns inside scientific Agents.

This repository is an engineering prototype. A successful run establishes only
the claims explicitly registered by its experiment and validation contracts.

## Why It Exists

Long scientific tasks fail when one conversational Agent must remember every
paper fact, invent hypotheses, write simulator code, manage jobs, and judge its
own results. SciDiscovery divides those responsibilities:

1. **Evidence intake** extracts a bounded, source-backed scientific foundation.
2. **Scientific roles** propose, criticize, audit, design, and diagnose.
3. **Domain authors and reviewers** produce and independently inspect executable
   projects.
4. **Deterministic code** validates schemas, applies patches, compares projects,
   packages reviewed inputs, and registers outputs.
5. **The control plane** isolates contexts, preserves immutable records, owns
   task state, and presents exact human approvals.
6. **Execution adapters** perform only approved side effects.

The root Agent remains a scheduler. Scientific content comes from bounded role
workers; identities and lifecycle state remain in the control plane.

## Components

| Component | Responsibility |
| --- | --- |
| `src/scidiscovery/` | Generic Artifact store, scheduler, approvals, MCP servers, worker protocol, schemas, platform generators, and execution bridge |
| `roles/` | Generic scientific role definitions |
| `plugins/tcad_artifact/` | TCAD project schemas, author/reviewer roles, deterministic packager, execution policy, SSH transport, and detached VM runner |
| `skills/sentaurus-tcad-code/` | Solver-code-only guidance and static validation for SProcess/SDevice |
| `plugins/ingaas_fig4/` | Optional domain example; not required by the generic control plane |
| `deploy/` | Linux/WSL systemd installation and remote-runner deployment |
| `tests/` | Unit, fault-injection, concurrency, platform, MCP, and closed-loop tests |

Generated `.codex`, `.claude`, `.mcp.json`, sockets, databases, approvals,
research data, solver outputs, and credentials are runtime state and are not
source artifacts.

## Architecture

```text
User
  |  local approval UI
  v
Codex / Claude root scheduler
  |  Root MCP (semantic names only)
  v
SciDiscovery control plane
  |-- immutable Artifacts and provenance
  |-- ResearchInstance bindings
  |-- task leases and bounded worker contexts
  |-- approval and execution lifecycle
  |
  +--> role worker MCP --> scientific role Agent --> validated JSON payload
  |
  +--> deterministic transform --> reviewed package / diff / score
  |
  +--> execution bridge --> TCAD adapter --> local or remote simulator
                                      |
                                      +--> terminal records and outputs
```

Dependencies describe readiness, not a fixed workflow graph. The scheduler
selects the shortest defensible role topology for the current contradiction.

See [Architecture](docs/ARCHITECTURE.md) for ownership and data-flow details.

## Quick Start

Supported hosts are Linux and WSL2 with systemd and Python 3.10 or newer.

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip poppler-utils bubblewrap curl openssh-client

git clone <your-repository-url> scidiscovery-agent
cd scidiscovery-agent

# Preview. On a fresh Python installation, run the full install directly.
SCID_PYTHON="$(command -v python3)" deploy/install.sh --dry-run

# Codex is the default platform.
sudo SCID_PYTHON="$(command -v python3)" \
  SCID_SERVICE_USER="$USER" \
  SCID_PLATFORM=codex \
  deploy/install.sh install
```

The installer creates three SciDiscovery services and a loopback-only approval
UI at <http://127.0.0.1:8765>. Without a TCAD command-adapter configuration it
installs a local `/bin/true` deployment-smoke profile only.

For Claude Code, use `SCID_PLATFORM=claude`; use `both` to generate both
platform configurations. Restart the selected client after installation.

Full instructions:

- [Installation](docs/INSTALL.md)
- [安装教程](docs/INSTALL.zh-CN.md)

## TCAD Boundary

SciDiscovery does not distribute Sentaurus, a license, proprietary manuals, or
a virtual machine. The TCAD plugin accepts a reviewed `DeckProject`, prepares a
bounded package, and invokes an allow-listed tool profile. For a remote VM, SSH
is used only for short upload, submit, status, cancel, and collect operations;
the VM runner owns detached jobs and durable terminal markers.

Machine-specific paths belong in copies of the JSON examples under
`plugins/tcad_artifact/config/`, normally installed under `/etc/scidiscovery`.
Never commit private keys, license files, live IP addresses, or generated
service secrets.

## Development

```bash
python3 -m pip install -e '.[test]'
python3 -m pip install -e plugins/tcad_artifact
python3 -m pip install -e plugins/ingaas_fig4  # optional example
pytest -q
```

Run the hermetic suite before publishing. Live platform and real solver tests
require explicit external configuration and are not implied by unit-test
success.

## Build a Clean Git Repository

The release builder copies only the source boundary, removes caches and build
outputs, scans for machine-specific data, writes a SHA-256 manifest, and can
initialize a new Git repository:

```bash
python3 scripts/build_git_release.py \
  --output dist/scidiscovery-agent \
  --init-git
```

Review the generated repository before adding a remote. The builder excludes
research databases, simulation results, paper PDFs, VM data, generated platform
configuration, and credentials.

## Current Limitations

- Human approval UI and production TCAD qualification still require deployment
  tests on the target machine.
- The framework validates evidence and implementation contracts; it cannot make
  an unsupported physical model scientifically correct.
- Claude Code configuration generation is implemented and tested
  hermetically, but every target Claude release must be smoke-tested.
- No software license is selected in this source tree. Choose and add a license
  before publishing the repository publicly.
