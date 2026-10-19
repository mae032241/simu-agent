# SciDiscovery Agent

[简体中文](README.zh-CN.md) | English

SciDiscovery is a scientific research framework for Codex. It runs native H/W/A/E
threads against an explicit objective and frozen inputs, with finite shared budgets,
sealed scientific results and recovery of known calls. Scientific Workers own model
choices and conclusions; deterministic control owns identities, input bindings,
qualification checks, budgets and execution permissions.

Candidate metrics, audit receipts and availability are evidence for the scientific
author. Control preserves observed order and every candidate; A explicitly names
its delivery choice and explains it with bound evidence. Control supplies no
scientific ranking or default choice.

Local result `candidates` lists every retained model available to A; each member
requires a distinct exact retained artifact. Identity follows the original call and
artifact path, independently of list order. Measurements and scientific metadata may
be absent. Optional descriptions and comparison tables do not grant
or gate delivery. Invalid individual declarations retain their originals and
receive local diagnostics; previews link full retained content.

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
A single `codex` launcher defaults to local experiments: the native host handles
ordinary-file submissions during W and returns responses automatically. Managed
local commands require a supported native permission projection; see the
[CLI guide](docs/ROOTLESS_CLI.zh-CN.md) for prerequisites and explicit unsupported
cases. External execution remains owned by its declared launcher.
Execution requires its own frozen configuration and authorization. Research
budgets, independent review and user statements do not grant execution permission.

All H/W/A/E node token budgets and W stage targets are advisory: reaching a target requests a bounded conclusion without rejecting new managed experiments or forcing A review. Actual input plus output is fully accounted; no whole-node token allocation is prepaid. Current protocol 23 accepts only soft node settings; older instances remain read-only without rewriting their frozen settings. Shared budget checks for new nodes, finite execution time, permissions and cleanup limits remain enforced.

New instances freeze a final-A completion policy with one A per FINAL cycle: insufficient, zero or
exceeded shared token, time or step budgets do not deny the final A's admission,
completion or its own authorized delivery. Missing or unreconciled billing alone
also cannot block its verified terminal return or that delivery: unknown usage stays
unknown and is never replaced with a zero meter. A completed native event, zero exit
and confirmed cleanup remain required. Observed usage remains accounted without
raising the shared ceilings; original finite per-call time, permissions and other
execution limits still apply. After an explicit threshold increase, the next run may resume the saved pending normal route when its full admission is affordable and original effects are known and quiescent. New physical IDs preserve prior final outputs, submissions and all consumption; a later budget denial begins another FINAL cycle. See the [architecture](docs/ARCHITECTURE.md).

A candidate choice requires `selection_explanation`: its comparison criteria and
whether they changed. Revised criteria explicitly acknowledge the prior rule,
changes, locatable evidence explaining why, and accepted tradeoffs. Missing details
use the frozen same-session output repair, including FINAL with its original
completion protection and cumulative usage. Control checks completeness; A owns
scientific sufficiency. Planning without a candidate choice needs no explanation.
Standard `codex` CLI preparation defaults to at most two output-only repairs in
the original native home, preserving configuration, permissions and authentication.
Explicit policies take precedence; custom launchers and direct controller API
calls require an explicit repair policy. This default grants no failed-task or
scientific-work continuation.

Workers write ordinary scientific files and use the thin experiment submission and
wait interface. Their instructions add no hash calculation, comparison, verification
or hash inventories. Control performs those checks automatically and retains
the mechanical bindings privately on the host.

The operator evidence exporter keeps default omission metadata within 8 KiB and
links to complete scientific details in pages of at most 16 KiB. This limit applies
to omissions, not the entire evidence index. Details describe missing materials;
`not_available_in_this_view` does not provide the omitted originals. See the
[architecture](docs/ARCHITECTURE.md) for the reading entry points.

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
The default managed local subprocess and an explicit science launcher provide
their declared file views; generic native execution has no blanket physical-isolation
guarantee. Network access follows the selected frozen native permissions.
Browser behavior, real native continuation, TCAD solvers and power-loss recovery
need evidence for the exact candidate and environment. Source tests do not establish
that qualification. Full cross-host disaster recovery is outside current support.
Frozen instances retain their implementation identity. Unknown external submissions
must be reconciled by their original identity before further action.

The supported application entrances are the two commands above. The old `scid`,
Root/MCP application, generated platform roles and legacy systemd application
installation are unavailable. See the [distribution notice](NOTICE.md) for software
licensing and bundled-reference restrictions before sharing a source release.
