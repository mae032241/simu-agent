---
name: sentaurus-tcad-code
description: Author, revise, review, and diagnose standalone Synopsys Sentaurus Process (SProcess) and Sentaurus Device (SDevice) code and project bundles. Use for .cmd/.par decks, solver entrypoints, geometry/material/doping definitions, physical models, numerical solve sequences, parameterization, expected TDR/PLX/PLT/log outputs, and TCAD parser or convergence failures. Do not use for SSH, VMware, IP addresses, license installation, remote scheduling, service deployment, or control-plane identity and approval handling.
---

# Sentaurus TCAD Code

## Purpose

Produce solver-facing SProcess and SDevice code whose physical meaning,
invocation, inputs, and outputs are explicit. Treat packaging and execution as
different operations. Never infer how an external scheduler or remote machine
works.

## Required Workflow

1. Classify each execution unit as `sprocess` or `sdevice`.
2. Read [execution-contract.md](references/execution-contract.md) before writing
   or reviewing any project entrypoint.
3. Read [sprocess.md](references/sprocess.md) for process simulation or
   [sdevice.md](references/sdevice.md) for electrical/optical device simulation.
4. Define one direct solver invocation for each execution unit. Split cases
   when one solver invocation cannot natively and safely express the study.
5. Keep validated upstream decks byte-identical. Create a derived deck or a
   small native-language launcher for declared changes; do not reconstruct a
   known-good deck from memory.
6. Bind every numerical value to its source, unit, and exact code locator.
7. Declare every expected TDR, PLX, PLT, log, and current output using the path
   actually written by the deck.
8. Run `scripts/validate_deck_project.py <project.json>` for a DeckProject JSON
   before review or execution.
9. Read [diagnostics.md](references/diagnostics.md) when a run fails. Stop at
   the earliest failed layer before interpreting physics.

## Nonnegotiable Execution Rules

- A solver profile selects a solver executable; it is not merely an environment
  selector.
- An SProcess execution unit must give `sprocess` an SProcess command file.
- An SDevice execution unit must give `sdevice` an SDevice command file.
- Never place a shell script at the entrypoint of a direct `sprocess` or
  `sdevice` invocation.
- Never assume `prepare`, packaging, signing, or staging executes a solver.
- Never start a second solver, detach a worker, or implement job scheduling
  inside a solver deck.
- Use a shell runner only when the declared executable is a shell runner. That
  is a separate execution type outside this Skill's direct-solver contract.
- Do not assume version flags such as `-V` or `--version`. Version and
  capability checks must come from a supplied capability description or a
  previously validated local example.
- Do not emit Workbench placeholders such as `@tdr@` in a standalone project
  unless an explicit preprocessing step is part of the same declared execution
  unit.

## Review Boundary

Review both physics and executable semantics. A syntactically valid JSON
project is not executable evidence. Before passing a deck, reconstruct the
exact direct command:

```text
<solver executable> <entrypoint> <arguments...>
```

Reject the project when the entrypoint language does not match the solver,
when a case depends on undeclared preprocessing or environment injection, or
when required outputs cannot be traced to deck statements.

## Scope Boundary

This Skill contains no instructions for networks, virtual machines, remote
transports, credentials, license servers, service managers, approval systems,
or job schedulers. Receive tool availability and execution capabilities as
inputs. If they are absent, report the missing capability instead of inventing
deployment behavior.
