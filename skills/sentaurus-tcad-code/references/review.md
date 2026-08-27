# Independent Deck Review

Review effective solver code against the supplied hypothesis, experiment plan,
and author declarations. Do not edit files, run the solver, redesign the study,
or complete control-plane metadata.

## Review dimensions

### Physical fidelity

- Geometry, materials, alloy convention, transported states, equations,
  initial/boundary/contact conditions, and parameter units match the plan.
- Each case changes only its declared variables; frozen controls remain equal.
- Built-in models and custom equations have semantics compatible with the
  stated hypothesis. Undeclared simulator defaults are not used as scientific
  assumptions.

### Executable logic

- Direct argv and entrypoint language match.
- Values are defined before use; loops and procedures have complete reset and
  initialization paths; branches cannot consume missing/stale values.
- Mesh and solve sequencing can realize the intended state without an obvious
  parser, initialization, or control-flow defect.
- Raw output statements cover the downstream observables and use distinct,
  traceable paths.

### Scope

- Solver source contains no scheduler, scorer, observed-evidence gate,
  threshold verdict, self-verifier, or derived report.
- Control-generated bindings are traceability aids, not proof of physics.

## Verdict rule

Use `revise` only for a concrete contradiction, omitted required realization,
or explicit code/physics bug. Cite the smallest source locator and the plan
requirement it violates. Do not demand that the author restate deterministic
bindings, add postprocessing, or run a full study.

Use `pass` when no explicit blocker remains. A pass means “ready for controlled
execution,” not “the hypothesis is scientifically accepted.” Keep the report
bounded; do not reproduce every generated manifest row.
