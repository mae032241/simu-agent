# Frozen Sentaurus independent-review contract

Reconstruct the direct solver invocation and match the solver to its entrypoint
language. Resolve every native include/input, trace every case-varying value to
effective source, and trace every declared raw output to a solver statement.

Review physical fidelity: geometry, materials and composition convention,
states/equations, initial/boundary/contact conditions, units, numerical
sequence, case changes and frozen controls must match the supplied plan and
approved parameters. Undeclared simulator defaults are not scientific
assumptions.

Review executable logic: definitions precede use; every procedure, loop and
branch has complete reset/initialization; the direct entrypoint contains no
shell, nested solver, scheduler or unresolved preprocessing; raw outputs are
distinct and traceable. Solver source must contain no scorer, observed-data
gate, threshold verdict, self-verifier or derived report.

Return `revise` only for a concrete contradiction, omitted required
realization, or explicit code/physics defect, citing the smallest source
locator and violated plan requirement. Return `pass` when no explicit blocker
remains. A pass means ready for controlled execution, never that the scientific
hypothesis is accepted. Do not edit files, run the solver, redesign the study,
or require the author to restate deterministic bindings.
