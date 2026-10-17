# SciDiscovery Agent

[简体中文](README.zh-CN.md) | English

SciDiscovery is a scientific research framework for Codex. It runs native H/W/A/E
threads against an explicit objective and frozen inputs, with finite shared budgets,
sealed scientific results and recovery of known calls. Scientific Workers own model
choices and conclusions; deterministic control owns identities, input bindings,
qualification checks, budgets and execution permissions.

This is an engineering prototype. A successful command or solver run supports only
the claims established by its exact inputs, experiment and validation contract.

## What you can do

| Entrance | Purpose |
| --- | --- |
| `scid-research` | Prepare an instance; run, inspect, pause and continue research; close out results. |
| `scid-research serve-ui` | Serve one explicitly selected instance, its controls and paginated sealed results. |
| `scid-research archive-*` / `checkpoint-*` | Export and inspect originals, restore selected material, or perform a bounded same-host cold transfer. |
| `scid-experiment` | Use managed local experiments or a declared domain execution interface. |

The optional TCAD adapter provides detached solver execution through bounded
transport. Curve plugins provide deterministic scoring and paper-figure evidence
capabilities. Installing a plugin registers its declared capabilities; it does not
supply a solver, license or scientific qualification. Plugin declarations also
remain available as libraries through the [Plugin API](docs/PLUGIN_RUNTIME_API.md).

## Install and start

Provide Python 3.10+ and the runtime/build dependencies declared in
[pyproject.toml](pyproject.toml), then install the application offline:

```sh
SCID_PYTHON=/absolute/python deploy/install.sh --dry-run
sudo SCID_PYTHON=/absolute/python deploy/install.sh install
scid-research --help
```

Installation publishes `scid-research` and `scid-experiment` and requires a fresh
installation prefix. Choose optional plugins explicitly with `SCID_PLUGINS`;
see [installation](docs/INSTALL.md) for dependencies, settings and removal.

To start research, prepare a new instance with an objective file, public inputs,
an explicit native launcher and finite token, time and step ceilings. Then run
and inspect that exact instance. The [CLI guide](docs/ROOTLESS_CLI.zh-CN.md)
contains commands, policy examples, result retrieval and recovery rules.
Execution requires its own frozen configuration and authorization. Research
budgets, independent review and user statements do not grant execution permission.

## Documentation and development

[Documentation index](docs/README.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Release scope](docs/RELEASE.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

The active controller lives in `src/scidiscovery/research_loop/`; domain algorithms,
contracts and adapters live in `plugins/`. Use the [test lanes](tests/README.md)
with supervised, serial, exact targets. Functional tests do not build or install
packages. `scripts/build_git_release.py` creates a source distribution with a
per-file SHA256 manifest from explicitly selected source, current references,
tools and functional fixtures.

Development plans, audits, handoffs and trial outputs are local working records.
They are excluded from long-term source tracking and source publication. Current
usage and behavior are defined by the code and current reference documents.

## Boundaries

Workers and same-user host processes are trusted: control provides a soft boundary.
Browser behavior, real native continuation, TCAD solvers and power-loss recovery
need evidence for the exact candidate and environment. Source tests do not establish
that qualification. Full cross-host disaster recovery is outside current support.
Frozen instances retain their implementation identity. Unknown external submissions
must be reconciled by their original identity before further action.

The supported application entrances are the two commands above. The old `scid`,
Root/MCP application, generated platform roles and legacy systemd application
installation are unavailable. See the [distribution notice](NOTICE.md) for software
licensing and bundled-reference restrictions before sharing a source release.
