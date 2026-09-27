# SProcess Guide

For R-2020.09 authoring, use
[sprocess-r2020.09-recipes.md](sprocess-r2020.09-recipes.md). This file records
the model-level checks that remain after syntax is chosen.

## Physical realization

- Define one coordinate convention and depth direction.
- Bind every region to its material and composition before the process step.
- Verify the alloy endpoint convention; a chemical formula does not determine
  the simulator's mole-fraction field convention.
- Treat support layers and unreported substrate properties as explicit
  assumptions.
- Use built-in diffusion/defect models only when their state semantics match
  the hypothesis. Give a phenomenological custom inventory a fresh solution
  name so built-in dopant callbacks are not activated accidentally.
- For a custom PDE, verify units, sign, outer-divergence convention, initial
  condition, boundary conditions, and limiting cases.

## Cases and numerics

- Make all case-varying values visible at unique direct call sites.
- Recreate the full structure and state for each independent case; variable
  reassignment alone is not a reset.
- Use the smallest mesh that resolves interfaces and expected gradients. Add
  refinement only when the plan declares a numerical tier or convergence gate.
- Keep temperature, duration, and step units explicit.

## Raw outputs

Retain the solver log plus the TDR/PLX fields needed by deterministic
postprocessing. State whether a field is chemical, active, charged, or custom.
Do not calculate curve metrics or scientific decisions in Tcl.

## Development modes

R-2020.09 documents `sprocess -s <commandfile>` and fast mode `-f`. Treat `-s`
as a bounded syntax-development mode, not a side-effect-free parser: Tcl
control flow can still be traversed. Fast mode omits physical work and cannot
qualify a study. If initialization needs diagnosis, author a separate minimal
entrypoint; never ask control to truncate production source.
