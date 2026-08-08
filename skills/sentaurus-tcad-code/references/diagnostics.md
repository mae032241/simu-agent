# Sentaurus Failure Diagnosis

## Contents

- Causal order
- Failure classes
- Minimum diagnosis output

## Causal Order

Stop at the first failed layer:

1. **Project contract**: wrong solver, entrypoint language, missing include, or
   unresolved preprocessing token.
2. **Executable capability**: solver unavailable or supplied capability does
   not support the requested syntax/version.
3. **Parser**: command file rejected before structure or equations initialize.
4. **Structure/material initialization**: region, material, composition,
   contact, mesh, or field missing.
5. **Initial numerical state**: equilibrium or initial coupled solve fails.
6. **Continuation**: voltage/process step fails, takes the wrong branch, or
   violates KCL/convergence gates.
7. **Output contract**: required TDR/PLX/PLT/log missing, stale, empty, or
   unparseable.
8. **Scientific comparison**: only after layers 1-7 pass may residuals test a
   physical hypothesis.

Never interpret a failure at layers 1-7 as evidence against a physical model.

## Failure Classes

### Entrypoint mismatch

Example: a direct SProcess profile receives `run.sh`. Reconstruct the actual
argv and classify as an implementation-contract failure. Do not debug shell
statements or process physics until the entrypoint is corrected.

### Parser failure

Report the first parser diagnostic, file, and line. Compare syntax against the
matching release or a validated deck. Change one construct at a time.

### Material or structure failure

Audit the TDR/layer readback, region names, material aliases, mole fractions,
contacts, and required fields before changing solver controls.

### Numerical failure

Record the last converged state, failed equation set, residual trend, damping,
step size, and branch history. First reduce the test to the smallest solve that
reproduces the failure. Do not tune physical parameters to conceal it.

### Output failure

Distinguish solver failure from a wrong expected filename or parser assumption.
Check solver exit, log terminus, file freshness, size, fields, and numeric rows.

## Minimum Diagnosis Output

- exact reconstructed solver invocation;
- earliest failed layer and first error;
- whether parser, initialization, and requested solver operation were reached;
- which expected outputs are valid;
- whether any physical conclusion is evaluable;
- one smallest next repair or discriminating run.
