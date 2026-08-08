# Direct Solver Execution Contract

## Contents

- Execution unit
- Entrypoint compatibility
- Multiple cases
- Parameter injection
- Output contract
- Review checklist

## Execution Unit

Model one execution unit as:

```text
solver + solver-language entrypoint + solver arguments -> declared outputs
```

Packaging may copy files and construct this invocation, but does not run it.
For a project object with `tool_profile`, `entrypoint`, and `arguments`, first
obtain the capability that maps `tool_profile` to a solver. Then reconstruct
the exact argv before reviewing any file content.

Direct SProcess shape:

```text
sprocess process_case.cmd
```

Direct SDevice shape:

```text
sdevice device_case.cmd
```

Flags and argument ordering are release-specific. Use only supplied capability
data, the matching release manual, or a previously executed example.

## Entrypoint Compatibility

| Solver kind | Valid direct entrypoint | Invalid direct entrypoint |
| --- | --- | --- |
| SProcess | SProcess/Tcl `.cmd` consumed by `sprocess` | Bash, Python, SDevice deck |
| SDevice | SDevice `.cmd` consumed by `sdevice` | Bash, Python, SProcess deck |

A shebang, `set -e`, shell functions, `nohup`, `&`, `wait`, or nested
`sprocess`/`sdevice` invocation indicates a shell runner, not a direct solver
deck. Do not approve it under a solver executable.

## Multiple Cases

Prefer one execution unit per independent solver case. For a paired process
study, create two direct SProcess projects or two native `.cmd` entrypoints.
Keep the shared deck frozen and express the declared case difference in a small
native-language launcher or generated parameter include.

Do not hide multiple external solver launches inside a direct solver
entrypoint. Native loops are acceptable only when the solver language supports
full state reinitialization and the study explicitly requires a single process;
otherwise split the cases.

## Parameter Injection

Every parameter must be available when the solver reads the entrypoint.

- Prefer explicit values or solver-native includes in standalone projects.
- Environment variables are valid only when the execution capability declares
  how the job supplies them.
- Workbench macros are valid only with a declared Workbench preprocessing step.
- Never assume a shell wrapper will populate variables for a direct solver job.

For paired cases, compare the resolved solver inputs. Output names and case
labels may differ; all scientific invariants must remain identical outside the
declared changed variable.

## Output Contract

Declare outputs that the solver-facing code actually writes. Required outputs
must be sufficient to distinguish:

1. executable reached;
2. deck parsed;
3. equilibrium or process initialization completed;
4. requested solve completed;
5. expected fields and observables exist.

Do not manufacture a success marker in a wrapper that can outlive or mask the
solver exit code. Treat missing, stale, empty, or unparseable required output
as failure. Record actual output filenames from a validated release rather
than guessing suffixes.

## Review Checklist

- Reconstruct exact argv.
- Match solver kind to entrypoint language.
- Confirm the entrypoint exists in the project.
- Confirm all includes and referenced grids are present.
- Reject unresolved preprocessing tokens.
- Confirm parameter injection is available without an undeclared wrapper.
- Trace expected outputs to exact deck statements.
- Confirm a nonzero solver exit cannot become success.
- Confirm multi-case topology matches the solver's actual invocation model.
