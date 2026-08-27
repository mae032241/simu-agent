---
name: scientific-paper-evidence
description: Digitize curves, markers, and fitted segments from supplied scientific-paper figure images into traceable CSV evidence with calibrated linear or log axes, explicit legend or annotation identity bindings, uncertainty, overlays, and a fail-closed manifest. Use for evidence extraction from PNG/JPEG raster plots when the user can provide panel geometry, axis calibration, series colors/styles, and identity anchors. Do not use as OCR, to infer missing labels or units, or to qualify a curve whose visual identity remains ambiguous.
---

# Scientific Paper Evidence

Convert a paper figure into reviewable numerical evidence without pretending
that pixels alone establish series identity. Require a configuration that binds
the exact source bytes and records every scientific interpretation.

## Workflow

1. Preserve the original figure image. Record its SHA-256 digest and pixel
   dimensions before interpreting it.
2. Read [digitization-spec.md](references/digitization-spec.md). Build one JSON
   spec with explicit panel, axis, exclusion-region, series-descriptor, seed,
   and legend/annotation binding information.
3. Obtain labels, units, citations, and identity mappings from visible paper
   evidence or supplied metadata. Never infer them from curve color alone.
4. Run:

   ```text
   python scripts/digitize_plot.py SPEC.json --output-dir OUTPUT
   ```

   Pillow is required by this script. Do not add it to an unrelated project's
   dependency manifest; install it in the execution environment when absent.
   In a collection-enabled SciDiscovery worker analysis sandbox, the same
   packaged script is mounted read-only at `/tools/digitize_plot.py`. Run it
   against staged `/inputs` and write the atomic package first under `/tmp`.
5. Validate the exact generated package before copying any evidence into the
   worker output directory:

   ```text
   python scripts/validate_evidence_bundle.py OUTPUT \
     --report /tmp/validation_report.json
   ```

   The sandbox mounts this tool at `/tools/validate_evidence_bundle.py`. It
   opens every series CSV and deterministically checks row identity, strictly
   ordered indices, exact preservation of line source-column gaps, finite
   values, source-pixel bounds, calibrated values and
   uncertainty, manifest point counts, mandatory explicit quantitative
   eligibility and optional detection-limit
   flags, shared-coordinate ownership, sibling hashes, and provenance. Exit
   code `1` is a hard integrity failure: do not copy or finalize the package.
   Never transcribe its counts into worker-authored prose as authoritative data.
6. For any quantitative curve that will be reviewed or scored, render its
   complete observed support before registration:

   ```text
   python scripts/render_curve_support.py OUTPUT \
     --series PANEL/SERIES --series PANEL/OTHER_SERIES \
     --output OUTPUT/audit_overlays/observed_support.png
   ```

   In the worker sandbox use `/tools/render_curve_support.py`. The renderer
   draws every observed row without crossing either a `point_index` gap or a
   raw pixel-column gap, emphasizes eligible runs, keeps singleton eligible
   points visible, and distinguishes below-limit rows from other masks. Inspect
   this PNG beside the source panel. Never substitute an eligible-only plot for
   the complete observed-support view. Always pass explicit `--series`
   selections; never mix measured and fitted roles merely because they share a
   manifest. When the output is written below the package's
   `audit_overlays/` directory, the renderer deterministically updates that
   file's bytes and SHA-256 entry in manifest provenance; do not transcribe it
   manually.
7. After a successful integrity check, copy only the completed
   `figure_manifest`, `source_panels`, `audit_overlays`, and `curve_tables`
   directories into `/outputs/collections`, then write `bundle.json`. Rerun the
   validator against the exact staged `/outputs/collections` tree and save its
   report under `/tmp`. Write `result.json` last and copy the report's exact
   `bundle_fingerprint_sha256` into
   `handoff.evidence_bundle_fingerprint_sha256`. Never reuse a report or
   handoff from an earlier output directory. The control plane checks this
   binding, reruns the same validator before registration, and creates the
   immutable `validation_reports/validation_report.json` artifact itself. The
   figure handoff leaves `assumptions`, `missing_inputs`, and `next_actions`
   empty because scientific assumptions stay in the payload/manifest and the
   control plane projects routing facts from the exact manifest and required audit.
   The analysis sandbox exposes no control-plane identifiers or schema
   internals.
8. Treat the manifest `status` as a figure-level summary, not an all-series
   eligibility switch. Exit code `2` and status `unresolved` require review of
   the named ambiguities. Keep only the affected series unavailable; a
   different series may remain quantitatively eligible when its own binding is
   matched, it has no ambiguity record, and its validated rows are eligible.
   Never set every CSV row ineligible merely because another trace is
   unresolved. Downstream normalization must preserve the unresolved series
   and its reason while selecting only independently qualified series or
   continuous intervals for comparison.
9. Inspect both overlays. The fidelity overlay checks pixel following; the
   identity overlay checks which explicit binding and seed own each trace.
10. Register the original/crops as `source_panels`, overlays as
   `audit_overlays`, CSV files as `curve_tables`, and canonical JSON files as
   the single `figure_manifest` artifact. Use the control-generated validation
   report for every row count, eligibility total, and duplicate/shared-pixel
   metric cited downstream.

## Guardrails

- Use panel-local calibration, including for multi-panel figures.
- Declare `pixel_range` when a line or marker has a scientifically intentional
  partial x domain; do not count out-of-domain panel pixels as missing evidence.
- Declare `declared_gap_ranges` only for source-visible interruption or
  occlusion. `tracking.max_gap_px` is only the bounded raster-dropout tolerance;
  a larger undeclared gap must leave the series unresolved.
- Use seeds to distinguish same-color or near-overlapping traces. A seed is an
  identity assertion from the operator, not evidence discovered by the script.
- Declare solid, dashed, or dotted line style in addition to color. Configure
  a style signature when rasterization makes the default checks unsuitable.
- Exclude legends, annotations, axes, and occlusions from trace searches.
- A same-color annotation that overlaps a trace is not direct curve evidence.
  After inspecting the source and overlay, declare its half-open x support with
  `eligibility.ineligible_pixel_regions` and reason
  `same_color_annotation_overlap`. Keep those observed pixels visible and
  explicitly masked; never count them as eligible merely because their color
  matches the series descriptor.
- Increase tolerances only through a new spec. Keep the source binding fixed.
- Never overwrite a prior output directory. Compare revisions as separate
  evidence packages.
- Keep `unresolved` when a binding fails, descriptors collide without seeds,
  candidate paths are tied, or no usable quantitative interval remains. A
  local trace gap alone is not an identity ambiguity: preserve it through a
  discontinuous `point_index` or explicit ineligible rows and split intervals.
- Distinguish a visible source gap from a tracker dropout. If a solid source
  curve is visibly continuous but the CSV has a gap, the extraction is
  defective: adjust seeds, continuity limits, exclusions, or color tolerance
  and rerun. Never relabel only the two gap endpoints as ineligible, never
  renumber them into adjacent `point_index` values, and never call that a source
  occlusion.
- Scope every ambiguity to its exact `(panel_key, series_key)`. Do not spread a
  fitted-branch identity ambiguity to a separately matched measured curve.
- Mark genuine visible gaps and occlusions on the affected series or interval
  and preserve their source-column discontinuity; never join them visually or
  numerically to manufacture continuous support.
- Show observed-but-ineligible rows in the support PNG. Masking controls
  scoring eligibility, not whether a human reviewer can see the source data.
- Treat multicolor overdraw as shared support, not interpolation. First extract
  every color directly. If one series disappears exactly where another color
  remains continuous and the covered series rejoins it at both ends, review the
  emitted candidate and add an explicit panel-level `shared_support`
  declaration. Never assign a candidate automatically.
- Render shared support as a distinct dashed segment. Never paint one series'
  masked or fitted interval as a full-height background band over other series.
- Declare `series.eligibility.default_eligible` explicitly for every series
  that may support a quantitative measurement claim. The fail-closed default is
  `false`. Use half-open `ineligible_pixel_ranges` and
  `below_detection_limit_pixel_ranges` for local masks. The digitizer writes
  explicit row flags, and validation rejects every curve table that omits the
  eligibility column; manifest identity qualification is not a substitute for
  quantitative row eligibility.

## Scope

The bundled script performs deterministic, configuration-calibrated raster
sampling with Pillow only. It does not perform OCR, semantic segmentation,
caption recovery, source-paper retrieval, or automatic scientific validation.
For a PDF source, recover an embedded image object as described in the spec
reference before running the Pillow-only digitizer; never silently substitute a
rendered PDF page.
