# SProcess Code Guide

## Contents

- Direct deck structure
- Structure and materials
- Process physics and parameters
- Paired cases
- Outputs and qualification
- Review checklist

## Direct Deck Structure

An SProcess entrypoint is a solver-consumable command file. A typical standalone
ordering is:

```tcl
math coord.ucs
AdvancedCalibration Off

set diffusionTimeMin 7.5

# Declare material/process parameters before use.
# Define mesh lines and tagged boundaries.
# Create regions and initialize composition/doping fields.
# Apply deposit, diffuse, etch, or other process steps.
# Select output fields.

SetPlxList { Zinc ZincActiveConcentration }
WritePlx results/case.plx
struct tdr=results/case
exit
```

The exact command spelling and generated filename suffixes are release-specific.
Copy them from a validated deck or the matching SProcess manual. Never invent
an etch, interface, alloy, or defect-equation syntax from analogy.

## Structure and Materials

- Define one coordinate convention and state which direction is depth.
- Tag every scientific interface explicitly.
- Bind each region to its material and composition before diffusion.
- For alloys, distinguish the physical mole fraction from the simulator's
  endpoint convention.
- Preserve remote layers when they are part of the device structure, even when
  they are not expected to affect shallow diffusion.
- Treat numerical support layers and unreported substrate properties as
  assumptions, not paper facts.
- Verify the final post-process structure after deposit or etch operations;
  do not infer coordinates from the pre-process grid.

## Process Physics and Parameters

- Use built-in diffusion/defect models when they express the intended physics.
- Treat custom Alagator/PDB equations as explicit model implementations that
  require units, signs, boundary conditions, activation law, and limiting-case
  tests.
- Separate calibrated simulator mappings from measured material constants.
- Bind diffusion coefficients, time, temperature, source concentration,
  interface transfer, and activation parameters to exact locators.
- Do not hand-edit the final dopant profile to satisfy an electrical target.
- Output chemical, active, charged, and auxiliary defect fields separately
  whenever later interpretation depends on their distinction.

## Paired Cases

For two devices that differ only by diffusion time, prefer two direct decks or
two small native launchers that set only the time and output prefix before
loading the same frozen implementation. Compare the resolved input texts and
declare the permitted differences.

Do not use a shell `submit/worker` runner as the SProcess entrypoint. External
orchestration belongs outside a direct `sprocess` execution unit.

## Outputs and Qualification

At minimum retain:

- complete SProcess log;
- PLX profile with every required chemical/active/defect field;
- TDR structure used downstream;
- layer/material readback when geometry changes;
- exact input deck and parameter digest.

Qualification checks should establish:

- the deck parser and process solve completed;
- every expected field is present and numeric;
- output depth coordinates and units are understood;
- deposited source layers were removed when the downstream DeviceView excludes
  them;
- final interfaces, materials, and total depth match the intended structure;
- paired cases differ only by the declared variable.

Profile agreement with a paper is a later scientific gate. A successful
SProcess run proves execution, not physical correctness.

## Review Checklist

- Entrypoint is SProcess code, not shell.
- All `env(...)` reads have a declared injection mechanism.
- All region/material names used by model or interface settings exist.
- Mesh resolves every interface and expected sharp profile feature.
- Process operations preserve the intended final DeviceView.
- Output statements cover every downstream field.
- Custom equations have source, units, signs, and limiting tests.
- No target-informed profile stitching or hidden sample-specific parameter.
