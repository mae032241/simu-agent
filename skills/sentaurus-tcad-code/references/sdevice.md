# SDevice Code Guide

## Contents

- Direct command structure
- Grid, contacts, and materials
- Physics and parameters
- Solve sequencing
- Outputs
- Review checklist

## Direct Command Structure

An SDevice entrypoint is a solver-consumable command file. A conventional
standalone organization is:

```text
File {
  Grid    = "device.tdr"
  Plot    = "device.tdrdat"
  Current = "device.plt"
  Output  = "device.log"
  Parameter = "device.par"
}

Electrode {
  { Name="anode"   Voltage=0.0 }
  { Name="cathode" Voltage=0.0 }
}

Physics {
  Fermi
  Mobility(...)
  Recombination(...)
}

Plot { ... }
Math { ... }

Solve {
  Poisson
  Coupled { Poisson Electron Hole }
  Quasistationary(
    InitialStep=...
    Increment=...
    Decrement=...
    MinStep=...
    MaxStep=...
    Goal { Name="cathode" Voltage=... }
  ) { Coupled { Poisson Electron Hole } }
}
```

Use the matching release manual for every model keyword and option. Do not
infer capitalization, nesting, or parameter names from another TCAD tool.

## Grid, Contacts, and Materials

- Verify that every `Electrode` name exactly matches a contact in the input
  grid.
- Verify region names, materials, alloy fractions, doping fields, and units
  from the TDR before enabling transport models.
- Record every material parameter override in a `.par` file or explicit
  region/material block with provenance.
- Do not silently accept default binary material values for a ternary alloy.
- Distinguish numerical support/substrate assumptions from active device
  layers.

## Physics and Parameters

Start from the smallest model set required by the hypothesis. Add mobility,
SRH, radiative, Auger, bandgap narrowing, incomplete ionization, avalanche,
Hurkx/TAT, optical generation, or interface terms only when their role and
parameters are explicit.

For every model, record:

- activation scope: global, material, region, interface, or contact;
- parameters and temperature law;
- source or assumption class;
- expected observable and falsifier;
- whether it affects equilibrium, dark current, optical generation, or
  collection.

Do not use a fitted current scale, artificial current floor, or sample-specific
hidden lifetime as accepted physics.

## Solve Sequencing

- Establish Poisson equilibrium before coupled carrier solves.
- State the carrier-equation order and damping strategy.
- Treat point-DC and quasistationary sweeps as different numerical protocols.
- Make sweep direction, start state, target voltage, step controls, and saved
  bias points explicit.
- Do not compare branches without checking continuation dependence, KCL, and
  convergence at every accepted point.
- Separate a runtime qualification solve from a full scientific voltage sweep.

Unresolved Workbench tokens such as `@tdr@`, `@plot@`, or `@node@` are invalid
in a direct standalone job unless preprocessing is declared and executed.

## Outputs

Retain enough information to audit both convergence and physics:

- solver log;
- terminal current/voltage PLT;
- requested TDR states or field plots;
- convergence and accepted-step records;
- electron, hole, displacement, and total current components when relevant;
- generation/recombination components for mechanism studies;
- optical generation and terminal response for optical studies.

An output parser must reject missing bias points, duplicate branches, nonfinite
values, failed KCL, and stale files. A completed process is not automatically a
valid electrical curve.

## Review Checklist

- Entrypoint is an SDevice command file, not shell or SProcess code.
- Grid and parameter files exist in the project.
- Contact, region, and material names match the TDR.
- Every enabled physical model has a declared scope and parameter source.
- Initialization and sweep path are explicit.
- Expected outputs are written by the deck and cover the acceptance metrics.
- Workbench placeholders are resolved or preprocessing is declared.
- No scientific claim depends on a nonconverged, nonunique, or stitched branch.
