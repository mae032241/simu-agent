# Failure Diagnosis

## Earliest-layer order

1. Project contract: wrong solver/entrypoint, missing input, unresolved token.
2. Capability: executable or exact release unavailable.
3. Parser: the command file is rejected.
4. Structure/material/state initialization.
5. Initial numerical solve.
6. Continuation or process step.
7. Raw output contract.
8. Scientific comparison.

Never use a failure at layers 1–7 as evidence against a physical hypothesis.

## Bounded correction loop

1. Preserve the exact invocation, terminal state, first error, file, line, and
   command/procedure excerpt.
2. Reread the current source around that locator. A generated line number is a
   hint, not permission to patch unread source.
3. Decide whether the message identifies one code defect. If not, stop and
   report the missing diagnostic.
4. Change one construct. Preserve physics, cases, values, outputs, and
   unrelated formatting.
5. Use a new run name only after a source change; otherwise poll the same run.
6. If the correction advances the first error, diagnose the new earliest
   layer. If it repeats unchanged, revert unsupported speculation.

For a parser error, search the exact command or option token in the matching
release manual. For initialization, inspect material, state, region/interface,
initial condition, and callback registration before changing numerics. For
convergence, reduce to the smallest failing solve before adjusting damping or
steps. For missing outputs, distinguish solver failure from a wrong filename.

## Minimum report

- exact invocation and release;
- earliest failed layer and first actionable message;
- whether parsing, initialization, and requested operation were reached;
- valid raw outputs, if any;
- one smallest supported correction or next diagnostic;
- explicit statement that scientific interpretation is unavailable when
  layers 1–7 are open.
