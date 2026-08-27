---
name: sentaurus-tcad-code
description: Author, revise, review, or diagnose standalone Synopsys Sentaurus Process (SProcess) and Sentaurus Device (SDevice) solver code. Use for .cmd/.par source, physical-model realization, geometry/material/contact definitions, numerical solve sequences, raw TDR/PLX/PLT/log outputs, and parser/initialization/convergence failures. Do not use for project scheduling, approvals, SSH/VM/license setup, deterministic postprocessing, scoring, or scientific verdicts.
---

# Sentaurus TCAD Code

Use this Skill to make solver code clearer and faster to produce. Do not turn
solver authoring into control-plane form filling.

## Route by task

Read only the references needed for the current task:

| Task | Read | Deliver |
| --- | --- | --- |
| New SProcess source | [execution-contract.md](references/execution-contract.md), then the matching recipe in [sprocess-r2020.09-recipes.md](references/sprocess-r2020.09-recipes.md) | Smallest complete solver source and raw-output declarations |
| New SDevice source | [execution-contract.md](references/execution-contract.md), then [sdevice.md](references/sdevice.md) | Smallest complete solver source, parameters, and raw outputs |
| Bounded revision or failed run | Current source and exact change request/log, then [diagnostics.md](references/diagnostics.md) | One diagnostic-backed code correction |
| Independent deck review | Plan, effective source, and [review.md](references/review.md) | Code/physics fidelity verdict; no edits or execution |
| Controlled workspace mechanics | [control-materialization.md](references/control-materialization.md) | Source and declarations through the supplied file lifecycle |

Do not read every reference by default. Do not search a manual merely to prove
that familiar, release-indexed syntax exists.

## Authoring loop

1. Reconstruct the direct invocation: `solver entrypoint arguments...`. Match
   `sprocess` to an SProcess `.cmd` and `sdevice` to an SDevice `.cmd`.
2. Freeze the supplied physics, cases, units, changed variables, and raw output
   needs. Name an unresolved physical choice instead of inventing it.
3. Write and reread the smallest complete source before broad documentation
   work. For a normal recipe-covered SProcess task, make the first source write
   within two minutes.
4. Choose the shallowest bounded development mode that reaches the changed
   layer. Use `preflight` only for parser or source-contract changes. A change
   to structure, material/state initialization, boundaries, model callbacks,
   case reset, or the first solve requires `initialization`; author and declare
   a smallest separate initialization entrypoint if none exists. Do not use a
   successful syntax preflight as a substitute for an unavailable deeper check.
   On failure, classify the earliest layer and change only its source locator.
5. Repeat only within the task's explicit debug budget. A nonterminal run or a
   later warning does not justify another code change.
6. Declare only raw solver-native TDR, PLX, PLT, and log products. Leave
   resampling, metrics, thresholds, curve comparison, and interpretation to
   deterministic postprocessing and diagnosis.

Prefer a small executable deck over a large self-checking Tcl program. Split
independent cases into separate entrypoints unless one native procedure can
recreate the complete structure and state for every direct case call. Never
hide external solver launches, workers, or scheduling inside a deck.

## Manual lookup policy

Use the supplied execution capability to select the exact solver and release.
For R-2020.09 SProcess, start from the reviewed recipe. If one construct is
still missing, run:

Resolve `<skill-dir>` to the directory containing this `SKILL.md`, then run:

```bash
python <skill-dir>/scripts/manual_search.py --release R-2020.09 --solver-kind sprocess \
  --topic custom_conservative_state
python <skill-dir>/scripts/manual_extract.py --release R-2020.09 --solver-kind sprocess \
  --start-page 632 --end-page 633
```

Use `--query` only for an exact command or diagnostic token not covered by a
topic. Before the first source write, allow at most one targeted lookup. An
empty literal search means only “that spelling was not found”; it is not proof
that the construct is unsupported. Never substitute another release or syntax
remembered from a different TCAD tool.

## Hard boundaries

- Own physical realization and solver implementation: geometry, material and
  composition, transported states, equations, initial/boundary conditions,
  contacts, meshes, solve sequencing, and raw output statements.
- Do not own approval, task identity, immutable-record metadata, execution
  scheduling, remote transport, licenses, or services.
- Do not embed curve scoring, masks, crossings, CSV/JSON reports, output
  self-verifiers, observed-data gates, or scientific pass/fail logic.
- Do not use Workbench placeholders in a standalone direct-solver project
  unless an explicit preprocessing execution unit is supplied.
- Do not tune scientific parameters to conceal parser, initialization,
  convergence, or output-contract failures.
- Development preflight/smoke/initialization results are provisional code
  diagnostics, never scientific evidence.

## Completion gates

An authored deck is ready for independent review only when its invocation is
explicit, source is complete, cases are traceable, required inputs exist, raw
outputs map to actual solver statements, and the latest permitted diagnostic
reaches the deepest changed implementation layer or its absence is reported
fail-closed. Syntax success does not prove initialization, convergence, or
physical fidelity.

A review may pass only when the effective code implements the supplied
physical hypothesis and case comparison without an explicit logic bug. The
reviewer must not require postprocessing, control metadata, or scientific
thresholds inside solver code.

A diagnosis stops at the earliest failed layer, records the first actionable
message and source locator, and proposes at most one smallest next correction.
