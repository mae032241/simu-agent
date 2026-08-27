# TCAD Qualification Status

English | [简体中文](TCAD_QUALIFICATION_STATUS.zh-CN.md)

Recorded on 2026-08-08.

## Completed engineering qualification

- Hermetic suite: `322 passed`.
- Unit conversion, unified claim projection, reviewed-package v2, and solver
  capability drift rejection.
- Case realization/execution DAGs, control-owned snapshot materialization, and
  control-equivalence comparison.
- Digest-, size-, media-type-, target-path-, and byte-exact validation for
  ArtifactRef-bound binary inputs.
- Column, row-count, and finite-value gates for synthetic PLX/PLT text fixtures;
  empty, truncated, non-finite, and descriptor-substituted inputs fail closed.
- Install transaction rollback coverage for the site, launchers, systemd units,
  configuration, platform skills, and SQLite state.

These results qualify schemas, deterministic transforms, state machines, and
license-free fixtures. They do not qualify Synopsys Sentaurus or a physical
model.

## Outstanding live qualification

This host exposes neither an `sprocess` nor an `sdevice` executable. No license,
administrator-qualified release capability, or external real PLX/PLT/TDR/log
qualification bundle was supplied. Consequently:

- the approved real SProcess execution/collection/parser loop is
  `unqualified / capability unavailable`;
- real SDevice and a TDR metadata provider are
  `unqualified / capability unavailable`;
- no Fig.4 or other scientific claim may be accepted from mock/fixture tests.

The release gate must bind an exact `SolverCapability` on a controlled runner,
complete one human-approved real SProcess smoke, and retain input/output
digests, release evidence, and parser results. SDevice may be promoted only
when a license, a real TDR fixture, and a qualified metadata provider are all
available.
