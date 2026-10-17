# Current architecture: thin H/W/A/E control

[简体中文](ARCHITECTURE.zh-CN.md) | English

`scid-research` owns explicit research instances; `scid-experiment` records managed experiments.
There is no LLM Root, MCP scheduling service or background Root daemon.
The core exposes the thin CLI and instance UI; the old CLI/MCP/UI, Root host,
platform-profile generator and legacy systemd deployment are retired.

## Ownership and flow

```text
Operator objective + inputs + configuration + finite budgets
  -> CLI prepare: freeze instance settings
  -> controller: instance writer lock, budget, pause and role routing
  -> native: fresh H / W / A / E threads
  -> sealed scientific JSON and exact materials
  -> A scientific direction -> controller

W -> scid-experiment -> frozen interface -> local / domain adapter
                                    -> original-call query / cancel / collect
CLI serve-ui -> same instance read views and control commands
CLI archive / checkpoint -> original verification and bounded restoration
```

H owns hypotheses and mechanisms; W owns bounded experimental design, implementation
and observations; A owns contribution, evidence gaps, direction and delivery selection;
E owns requested evidence work. Control owns immutable bindings, budgets, qualification,
authorization and mechanical publication. It does not manufacture science or ask models
to compute hashes and references.

## Implementation owners

All listed files are in `src/scidiscovery/research_loop/` unless stated otherwise.

| Responsibility | Owner |
| --- | --- |
| Preparation, routing, pause | `controller.py`, `runtime.py`, `instance_control.py` |
| Native work, continuation, usage | `native.py`, `execution.py`, `continuation.py` |
| Scientific contracts and originals | `contracts.py`, `semantic.py`, `instance_science.py` |
| Candidates and delivery | `selection.py`, `delivery.py`, `worker_delivery.py` |
| Execution and original-call recovery | `experiments.py`, `managed_wait.py`, `local_experiments.py`; domain adapters |
| Provenance, independent review, approval | `qualification.py`, `formal_review.py`, `execution_inputs.py`, `execution_authority.py` |
| Budget and execution resources | Original control ledger in `budget.py` |
| Instance UI | `instance_ui.py`, `instance_render.py`; no second state authority |
| Archive and same-host cold restore | `instance_archive.py`, `instance_owner.py`, shared `archive_io.py` |

`scidiscovery.execution_interfaces` discovers execution implementations; instances freeze
the exact selected implementation. Retained Operation/compiler declarations and shared
`artifact_agent` schemas/storage primitives and the extracted Operation callbacks are
independent libraries. The old `artifact_agent/service` Run/SQL host and its runtime
helpers are deleted; the thin loop does not require that storage library as its host.
Keep adapter, provenance and storage validation dependencies regardless of directory age.
Operation ABI is defined by `operations/spec.py` (currently 26); see the [plugin API](PLUGIN_RUNTIME_API.md).

## Invariants

- One advancing writer per instance; read views neither call models nor own scientific/budget state.
- Exact immutable originals, configuration and calls; revisions inherit no prior qualification or approval.
- Unknown provenance stays unknown. Formal review excludes all known subject authors/participants;
  ordinary A analysis is not automatically formal review.
- Scientific judgments, qualification and execution permission are distinct. Chat and handwritten
  decision files cannot become human authorization.
- Reconcile uncertain external submissions by original identity; no replay, refund, budget reset or new owner.
- Escape author text and read exact sealed attachment members; HTML/SVG remain downloads.
- Workers and same-user host processes are trusted. This is a soft boundary, not hostile-process isolation.

## Declared sources and review

Qualification consumes exact frozen originals, not names, equal bytes or the most
recent object. Managed execution may declare input sources through its frozen
capability; self-contained TCAD V2 packages must match the prepared archive and the
original reviewed producer, while compiled V3 inputs retain their compiler chain.
An explicitly incomplete declaration cannot fall back to a broader source claim.
Optional observers need a separately enabled frozen source contract and a source
view bound to the exact observation. Display coverage alone grants no qualification.
Known producer contributions enter authorship even when not selected as an
implementation. Ordinary parent links do not manufacture authorship.

Ordinary exploration has no mandatory formal-review stage. When requested, review
binds the exact subject and verified contributors; ordinary A interpretation does
not qualify as independent review. Source restrictions propagate through frozen
inputs, and unknown origins remain unknown. These checks cover declared framework
surfaces, not arbitrary native reads or scientific correctness.

## Extension rules

Domain algorithms, scientific schemas and execution adapters belong to plugins.
Core routes frozen declared capabilities without branching on a domain or plugin
name to decide scientific behavior. Schema shape, declared scientific semantics
and validation must agree; engineering failures must not be disguised as scientific
rejection or an invitation to retry. Bounds and failure evidence survive recovery.
Read views and UI render the same sealed scientific bytes without rewriting them.

## Support and qualification

Managed local experiments, candidate delivery, UI, declared provenance, execution gates,
original-call maintenance and same-host original-path cold checkpoints are implemented.
`/results?after=N` lists sealed nodes; `/results/<step>` shows an exact result. Rankings
are frozen at that node's input boundary, not a current global ranking.
Ordinary read-only archives grant no advancing restore permission. Cross-host recovery,
lost anchors and arbitrary native external reads remain outside support.
Source/HTTP/synthetic-process checks do not qualify real browsers, native Codex continuation,
TCAD solvers or power-loss recovery. Retirement grants none of these qualifications and does
not operate existing host services, databases or external jobs.

TCAD-specific promotion evidence is defined in the [qualification status](TCAD_QUALIFICATION_STATUS.md).

See the [CLI guide](ROOTLESS_CLI.zh-CN.md), [installation](INSTALL.md) and [release scope](RELEASE.md).
