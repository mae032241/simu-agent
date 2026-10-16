# Generic inverse tools fixture

Read [objective.md](objective.md) for the scientific task, available information,
constraints, deliverables, and stopping rule. This directory is separate from cov
and imports no cov code, task model, hidden scorer, or external dependency.

Prepare a disposable experiment directory with copies of `run.py` and `objective.md`,
then run `python generate.py /absolute/experiment/dataset.json`. From that directory,
`python run.py --method source_linear` or `python run.py --method operator_ridge`
produces the existing local execution result format. `--fail` is an explicit
acceptance injection and exits before writing a result.

The regression in `tests/research_loop/test_generic_inverse_tools.py` uses the real
research CLI and managed experiment CLI with scripted H/W/A transport roles. It
asserts the default local mode, three real subprocess executions, retained originals,
metric and output handoff, failure and read-only recovery, and byte reproduction from the same instance's retained archive after export-only.
The roles are deterministic test programs, not models; they do not implement a
candidate selector. Search is disabled explicitly to isolate this execution test.

These are repository acceptance materials. They are included by the existing release builder through its
`tests/` tree; they are not packaged inside the core wheel.

This initial engineering acceptance runs two successful experiments and one explicit
failure injection. It uses no models or network and has no model budget. Passing
the tool test does not complete the scientific task's selected-solution delivery: the
generic candidate, shortlist, and external audit interfaces remain a recorded gap.
