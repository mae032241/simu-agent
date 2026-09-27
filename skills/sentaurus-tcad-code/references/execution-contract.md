# Direct Solver Contract

Model one execution unit as:

```text
solver + solver-language entrypoint + arguments -> raw solver outputs
```

## Direct invocations

| Solver | Valid entrypoint | Invalid entrypoint |
| --- | --- | --- |
| SProcess | SProcess/Tcl `.cmd` | shell, Python, SDevice source |
| SDevice | SDevice `.cmd` plus declared `.par`/TDR inputs | shell, Python, SProcess source |

A shebang, `set -e`, `nohup`, nested `sprocess`/`sdevice`, submit/status
commands, or detached processes belong to a runner, not a direct solver deck.
Packaging copies files and freezes argv; it does not execute the solver.

## Cases and inputs

- Make every case-varying value visible in solver source or a declared native
  include.
- Prefer one execution unit per independent case. A native multi-case
  procedure is acceptable only when it recreates the complete structure,
  fields, model state, and history for each case.
- Use environment variables or Workbench tokens only when the supplied
  execution unit explicitly provides that preprocessing mechanism.
- Keep upstream binary inputs at declared project-relative paths; do not embed
  or reconstruct their bytes.

## Outputs

Declare paths actually written by solver statements: TDR, PLX, PLT, and solver
logs. Missing, stale, empty, or unparseable required output is an execution or
output-contract failure.

The deck does not compute residual scores, masks, crossings, thresholds,
scientific status, or JSON/CSV reports. Those are deterministic scorer duties.

## Quick audit

1. Reconstruct exact argv.
2. Match solver to entrypoint language.
3. Resolve every include and binary input.
4. Trace case-varying values to executable source.
5. Trace every declared raw output to a solver statement.
6. Confirm a nonzero solver exit cannot become success.
