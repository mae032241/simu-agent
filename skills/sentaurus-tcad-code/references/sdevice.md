# SDevice Guide

## Minimal source shape

```text
File {
  Grid="device.tdr"
  Parameter="device.par"
  Plot="results/device.tdrdat"
  Current="results/device.plt"
  Output="results/device.log"
}
Electrode { ... }
Physics { ... }
Plot { ... }
Math { ... }
Solve {
  Poisson
  Coupled { Poisson Electron Hole }
  Quasistationary(...) { Coupled { Poisson Electron Hole } }
}
```

Use the exact R-2020.09 manual for model keywords and option nesting. Do not
infer SDevice syntax from SProcess or another simulator.

## Authoring checks

- Every electrode name matches a contact in the input TDR.
- Regions, materials, alloy fractions, doping fields, and units match the TDR.
- Every enabled physical model has an explicit scope and parameter source.
- Equilibrium precedes coupled carrier solves. Sweep direction, start state,
  goal, and step controls are explicit.
- Workbench tokens are resolved unless a preprocessing execution unit is
  declared.
- Raw outputs include the log, terminal current/voltage PLT, and the TDR/field
  states required downstream.

Reject hidden fitted current scales, artificial current floors, undeclared
sample-specific lifetimes, stitched branches, and conclusions based on
nonconverged points. Deterministic postprocessing must check accepted bias
points, duplicates, nonfinite values, KCL, and branch identity outside the
deck.

## Development modes

R-2020.09 documents `sdevice -P <commandfile>` for parameter extraction and
`sdevice -i <commandfile>` for the initial solution only. These are provisional
preflight/smoke diagnostics and do not qualify the full solve or outputs.

Manual basis: *Sentaurus Device User Guide*, R-2020.09, PDF pages 1477–1478,
SHA-256 `dae2c94b29c92705d3b8d6124c2f0ab595541ed48e4b220a425f72fac42794ce`.
