# Curve science plugin

`scidiscovery-curve-score` owns only curve-domain semantics: reviewed curve contracts, canonical curves, deterministic metrics, coverage checks, and curve diagnosis. It does not parse TCAD-native output or know SProcess, PLX, solver attestations, or execution protocols. `tcad_artifact` owns adapters from TCAD output to canonical curves.

Public scientific Operations:

- `science.curve.contract.design.v1`
- `science.curve.contract.review.v1`
- `science.result.diagnose.v1`
- `science.result.diagnose.curve-error.v1` (interprets one closed deterministic
  curve-error analysis package and emits one scientific diagnosis)


Deterministic support Operations:

- `science.curve.error.analyze.v1`
- `scidiscovery.curve-bundle.figure-evidence.v2`
- `scidiscovery.curve-score.v1`
- `scidiscovery.curve-reference-coverage.v1`
- `scidiscovery.objective-coverage.v1`

Paper-figure evidence Agents are not part of the default TCAD loop and are
registered by the separate optional `curve_figure_evidence` plugin. This
package retains the deterministic figure-evidence, calibration, validation,
and canonical-curve algorithms reused by that plugin. Installing only this
package or TCAD does not expose paper-figure extraction/review Agents.

`CurveExperimentContract` is a separately reviewed domain artifact, not a field of the generic `ExperimentPortfolio`. It binds one generic experiment to exact series identities, axes, units, comparison domains, operators, thresholds, and one-to-one deterministic validation checks. Reference series must be explicitly compared or excluded with rationale.

The scorer consumes only canonical `CurveBundle` values. It never guesses a solver, file format, unit, series identity, missing value, or crossing selection. Insufficient or ambiguous support remains `unavailable` or `inconclusive`.

TCAD may depend on this plugin's public curve contract and canonical curve schema and may publish adapters such as `tcad.curve-bundle.sprocess-plx.v1` and `tcad.curve-bundle.sprocess-log.v1`. The dependency direction is strictly `tcad_artifact -> curve_score`; this plugin must never import TCAD implementation code.
