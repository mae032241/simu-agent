# Curve Score transform plugin

`scidiscovery-curve-score` normalizes declared native solver outputs into
canonical curves and evaluates a pre-registered, domain-neutral comparison. It
performs deterministic parsing and arithmetic only; it does not interpret
physics or change a TCAD project.

## Profiles

- `scidiscovery.curve-normalize.sprocess-log.v1`: `source_spec` +
  `solver_output` -> `CurveBundle` + parser audit.
- `scidiscovery.curve-normalize.sprocess-plx.v1`: `source_spec` + one native
  ASCII PLX -> one-series `CurveBundle` + parser audit.
- `scidiscovery.curve-bundle.sprocess-plx.v1`: passing runtime attestation +
  experiment plan + one `solver_output__<series_key>` PLX per solver series ->
  a traceable multi-series `CurveBundle` + parser audit.
- `scidiscovery.curve-bundle.figure-evidence.v1`: legacy figure-global qualification;
  retained read-only so old artifacts are never reinterpreted.
- `scidiscovery.curve-bundle.figure-evidence.v2`: exact figure manifest +
  control-generated validation report + one
  `curve_table__<panel_key>__<series_key>` CSV per manifest series -> a
  complete canonical evidence `CurveBundle` + normalization audit. This bridge
  is independent of any experiment plan. Qualified rows are calibrated from
  pixels; unresolved identity or zero eligible rows remain value-free
  `unavailable` series.
- `scidiscovery.curve-reference-coverage.v1`: experiment plan + one or more
  complete `reference_curve__*` libraries -> a deterministic pre-execution
  coverage report. The agent-authored plan must mark every library series as
  `compare` or `exclude`; the transform validates that mapping, exact comparison
  domains, and unique reference-side crossing support, but never chooses an
  operator, level, or target.
- `scidiscovery.curve-consistency.v1`: `curve_bundle` + `comparison_spec` ->
  standalone `CurveConsistencyReport` (not a study `metric_report`).
- `scidiscovery.curve-score.v1`: canonical curve bundle + passing runtime
  attestation + experiment plan, with optional `reference_curve__*` inputs ->
  complete-plan metric report, merged bundle, audit, and a deterministic
  reference/candidate comparison PNG. This scorer is solver- and
  file-format-neutral.
- `scidiscovery.curve-score.sprocess-log.v1`: `solver_output` + passing
  `runtime_attestation` + `experiment_plan`, with optional `source_spec` ->
  legacy complete-plan metric report, canonical bundle, and audit.

The composite profile requires exactly one proposal to contain a
`curve_comparison_spec`. Every thresholded operator names one
`validation_check_key`; these bindings must exactly cover all
`deterministic_threshold` checks in that proposal's `ValidationPlan`, and the
operator thresholds must match the plan. Each covered check also fixes the
curve-score evaluator profile and exact operator kind, so a check key cannot be
reused for a different metric. Partial or ad-hoc specifications are rejected
before normalization and cannot produce a scientific `metric_report`.

The figure-evidence bridge requires the control-generated validation report to
be a direct child of the exact manifest and every manifest curve table. It
preserves the complete evidence inventory and does not infer identity from
labels, filenames, colors, or column names. The scorer later selects only the
series explicitly mapped by `CurveComparisonSpec`; unused evidence remains in
the source library and is not merged into the scored bundle. A reviewed TCAD
package with external references requires a passing exact-plan coverage report.

## SProcess log grammar

The v1 normalizer recognizes only these UTF-8 records and ignores other solver
log lines:

```text
SCID_CURVE_V1|POINT|<case_key>|<series_key>|<zero_based_index>|<x>|<y>
SCID_CURVE_V1|END|<case_key>|<series_key>|<point_count>
```

To reuse earlier solver-only executions already registered by control, the same
profile also admits one strict compatibility grammar:
`<fixed uppercase profile tag>,<case_key>,<zero_based_index>,<x>,<y>`, paired
with `SOLVE_COMPLETED,<case_key>,<finite_summary_1>,<finite_summary_2>`. Point
count is computed independently from contiguous indexes and checked against the
source spec after scanning the complete log; completion summaries and their
ordering relative to profile export are never guessed as counts. This branch is used only when no `SCID_CURVE_V1` record is
present. It requires one declared series per case, one stable tag, contiguous
indexes, finite values, and source-spec bounds; it never guesses units, sorts,
or fills points.

Every expected series, axis name/unit/scale, and point bound must be declared
in the comparison or source specification. Unknown, truncated, non-finite, or
undeclared data fail closed. Source row order is preserved; a declared `y(x)`
operator builds a non-mutating x index for interpolation. Repeated-x interface observations
are preserved in source order and are masked from ambiguous numerical samples;
they are never sorted, deduplicated, averaged, or treated as a failed metric.
The parser does not infer units, extrapolate, or fill missing values.

## SProcess ASCII PLX grammar

The PLX normalizer accepts one or more quoted dataset headers, each followed by
exactly two finite numeric columns (`x y`). A multi-dataset PLX requires an
explicit `dataset_name`; silently selecting the first dataset is forbidden.
Blank lines are ignored and point counts must satisfy declared bounds. Original
row order is retained, with x-order reversals reported in the normalization
audit. Repeated x values are retained as
interface/seam evidence and reported by the normalization audit;
downstream comparison masks the ambiguous coordinate while keeping it visible
for diagnosis. Additional columns, duplicate/missing dataset names, invalid
UTF-8, and non-finite values fail closed. Axes, units, case identity,
and series identity come from the experiment plan; they are never inferred
from a file name, header, or log.

## Interpretation boundary

The report may contain `pass`, `fail`, `unavailable`, or `inconclusive`
deterministic checks. A diagnostician may interpret those checks together with
runtime and control-equivalence reports, but must not recompute or overwrite
their values. For log-value metrics, exact-zero support is retained and shown
but excluded from the numeric metric without epsilon substitution. Repeated-x
seams follow the same visible-but-masked rule. Either condition can make a
metric unavailable when too little eligible support remains, but cannot by
itself make the metric fail.

Crossing discovery returns every ordered crossing location. Zero crossings are
represented by an empty list; multiple crossings remain a list and are not a
parser failure. A scalar `crossing_shift` or `width_shift` is unavailable when
its declared contract has no explicit pairing rule and either side does not
contain exactly one required crossing. The metric report preserves the complete
crossing-location inventory for downstream diagnosis.
