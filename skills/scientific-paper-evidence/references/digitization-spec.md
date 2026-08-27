# Digitization Spec

Use schema version `scidiscovery.plot-digitization-spec.v1`. All pixel
coordinates are absolute image coordinates. Bounding boxes are
`[left, top, right, bottom]` with exclusive right and bottom edges.

## Minimal shape

```json
{
  "schema_version": "scidiscovery.plot-digitization-spec.v1",
  "figure_key": "paper-doi-fig7",
  "source": {
    "source_name": "paper_source",
    "page": 7,
    "figure": "Fig. 7",
    "image": {
      "path": "fig7.png",
      "sha256": "<lowercase SHA-256>",
      "width": 1200,
      "height": 800
    },
    "pdf": {
      "path": "paper.pdf",
      "sha256": "<lowercase SHA-256 of PDF>",
      "page": 7,
      "object_id": "42"
    }
  },
  "panels": [
    {
      "panel_key": "a",
      "citation": "Fig. 7(a)",
      "plot_bbox": [100, 80, 560, 700],
      "axis_calibration": {
        "x": {
          "scale": "linear",
          "unit": "V",
          "pixel_min": 100,
          "pixel_max": 559,
          "value_min": 0.0,
          "value_max": 1.0,
          "reprojection_error_px": 0.5
        },
        "y": {
          "scale": "log10",
          "unit": "A",
          "pixel_min": 699,
          "pixel_max": 80,
          "value_min": 1e-9,
          "value_max": 1e-3,
          "reprojection_error_px": 0.75
        }
      },
      "exclusion_regions": [[100, 80, 160, 120]],
      "series": [
        {
          "series_key": "measured",
          "label": "Measured",
          "primitive_kind": "line",
          "descriptor": {
            "color": "#d62728",
            "color_tolerance": 30,
            "line_style": "dashed"
          },
          "seeds": [[120, 500], [530, 240]],
          "binding": {
            "source": "legend",
            "visible_label": "Measured",
            "bbox": [410, 95, 545, 125],
            "alternatives": []
          },
          "tracking": {
            "max_vertical_step_px": 12,
            "max_gap_px": 24,
            "min_visible_fraction": 0.2,
            "max_ambiguous_fraction": 0.1
          },
          "eligibility": {
            "default_eligible": true,
            "ineligible_pixel_ranges": [],
            "below_detection_limit_pixel_ranges": []
          }
        }
      ]
    }
  ]
}
```

`source.pdf` is optional. When present, the script hash-binds the PDF and
recovered image bytes and records the declared page/object provenance.

## Recover an embedded PDF image

Prefer embedded object recovery over page rendering. Run `pdfimages -list` to
identify the page/object and then extract only the selected page to a fresh
directory, for example:

```text
pdfimages -list paper.pdf
pdfimages -f 7 -l 7 -png paper.pdf recovered/fig7-object
```

Select the output corresponding to the recorded object identifier, compute the
PDF and image SHA-256 digests, inspect the image dimensions, and put all values
in `source.pdf` and `source.image`. Preserve the relevant `pdfimages -list`
record as review evidence. `digitize_plot.py` verifies the PDF/image hashes,
image dimensions, and agreement of the declared page fields; `object_id` is an
operator provenance assertion that the script records but cannot independently
derive from PDF internals. The script never invokes `pdfimages` and never falls
back to rasterizing the whole page. If object recovery is impossible, keep that
provenance distinction explicit outside this embedded-image workflow.

`scale` is `linear` or `log10`; log endpoints must be positive. Pixel/value
endpoint pairs may run in either direction. `primitive_kind` is `line`,
`marker`, or `fit_segment`. Any series may add the half-open
`pixel_range: [left, right]` when the scientific trace is defined or visible
over only part of the panel. The range must lie inside `plot_bbox`. Search,
visibility, and gap metrics use that declared domain; excluded leading or
trailing panel regions are not evidence of a curve gap. For markers, the range
restricts component search while point-count visibility remains the configured
identity check.

## Identity and tracing

Every series must provide a `legend` or `annotation` binding. Its `bbox` must
contain at least one descriptor-colored glyph; use `min_color_pixels` to raise
the threshold. Add `verify_style: false` only when the binding glyph has no
representative line sample and record why outside this machine spec.

Seeds are `[x, y]` pixels or `{ "pixel": [x, y] }`. Supply two or more for
same-color traces and curved/near-overlapping paths. The tracker interpolates
between configured seeds and follows matching pixels under the declared
continuity limits. It never discovers semantic identity.

Use `tracking.max_guide_distance_px` to define a bounded corridor around the
piecewise-linear seed guide independently of `max_vertical_step_px`. This is
important when a steep physical front needs a large vertical step allowance
but same-color axes, annotations, or another trace lie elsewhere in the panel.
A candidate outside the corridor is missing support, not permission to jump to
the unrelated object.

Optional `descriptor.style_signature` keys are `min_runs`, `min_run_px`,
`max_run_px`, and `min_gap_px`. Use them to calibrate dotted/dashed checks for
the exact rasterization. Optional marker tracking keys are
`min_component_pixels`, `max_component_pixels`, and `max_seed_distance_px`.

Place plot-obscuring rectangles in panel or series `exclusion_regions`.
Exclusions affect tracing only; binding boxes remain independently validated.

When a same-color label, arrow, SEM annotation, or other glyph overlaps an
otherwise tracked curve, color matching cannot establish curve ownership in
that local interval. Preserve the observed descriptor pixels for review but
mask them quantitatively with a reasoned eligibility region:

```json
"eligibility": {
  "default_eligible": true,
  "ineligible_pixel_regions": [{
    "pixel_range": [420, 447],
    "reason": "same_color_annotation_overlap"
  }]
}
```

Regions are half-open, must lie inside the series trace domain, and may not
overlap one another. The CSV records the reason in `eligibility_reason`.
Eligible rows have an empty reason; every ineligible row emitted by the
digitizer has an explicit reason. The support renderer shows same-color
annotation masks as purple squares, so the suspect pixels remain visible
without being presented as quantitative curve support. Use ordinary
`exclusion_regions` instead when the glyph should not be traced at all.

Use `declared_gap_ranges: [[left, right], ...]` only for a visibly verified
half-open x-pixel interval where the source trace is interrupted or occluded.
The interval must lie inside the series trace domain. `tracking.max_gap_px` is
the allowed raster-dropout tolerance for every gap not fully covered by one of
these declarations; a larger undeclared gap makes the series unresolved. This
separates honest source occlusion from a tracker that lost a continuous curve.

Line tracking excludes the outer four plot pixels by default so a horizontal
axis stroke cannot become a same-color curve branch. Override
`tracking.plot_border_exclusion_px` only when a genuine trace is visibly bound
to the plot border. Axes and frames that extend farther into the panel still
belong in `exclusion_regions`.
Across a skipped-column run, vertical reacquisition is capped by
`tracking.max_gap_vertical_displacement_px` (default: one normal vertical step
plus the guide distance), rather than multiplying the normal step by the gap
length. This prevents a short dropout from jumping to distant same-color text
or noise.

## Multicolor overdraw and shared support

The tracker reports a possible multicolor overdraw when a series has an
internal source-column gap, a differently colored series has direct pixels
through that interval, and the covered series converges to that visible series
at both endpoints. This is only a candidate because pixels cannot establish the
identity of a fully hidden line.

After inspecting the source and identity overlay, confirm a defensible
candidate with a panel-level declaration:

```json
"shared_support": [{
  "group_key": "measured-overdraw-01",
  "visible_series": "measured_red",
  "covered_series": ["measured_black"],
  "pixel_ranges": [[190, 204]],
  "mode": "overdraw",
  "covered_eligible": false,
  "max_endpoint_distance_px": 4
}]
```

Ranges are half-open and require direct covered-series support on both sides.
The visible series must contain a direct descriptor pixel in every declared
column. Endpoint distance must not exceed the declared bound. Overlapping
groups, missing donor pixels, and undeclared shared rows fail validation.
`covered_eligible` is fail-closed by default and must be set deliberately from
the scientific identity evidence.

## Outputs

The command creates a new output directory atomically and refuses an existing
path. It writes:

```text
figure_manifest/evidence.json
source_panels/source_image.<ext>
source_panels/<panel_key>.png
audit_overlays/fidelity_overlay.png
audit_overlays/identity_overlay.png
audit_overlays/observed_support.png  # when rendered for quantitative review
curve_tables/<panel_key>--<series_key>.csv
```

Each CSV includes integer raw pixels, subpixel coordinates, calibrated values,
pixel/value uncertainty, an observed flag, and an explicit quantitative
eligibility flag and reason. Eligibility is fail-closed by default. Set
`series.eligibility.default_eligible` only from visible/scientific identity
evidence; optionally provide half-open `ineligible_pixel_ranges` and
`below_detection_limit_pixel_ranges` inside the series trace domain. A
below-limit row is always ineligible. `evidence.json` uses
`scidiscovery.figure-evidence-manifest.v1` and has a fail-closed `qualified` or
`unresolved` status. Its `provenance` section binds the canonicalized spec and
every non-manifest output by SHA-256 and byte count. Emit exactly one
`figure_manifest` artifact; the surrounding worker bundle supplies the outer
artifact manifest.

After generation, run `scripts/validate_evidence_bundle.py` against the package.
The validator accepts both this canonical CSV shape and extended curve tables
that retain the identity/pixel columns while adding explicit fields such as
`quantitative_measurement_claim_eligible`, `below_sims_detection_limit`,
`scientific_role`, `support_kind`, `support_source_series`,
`coordinate_ownership`, and `shared_group`. Shared rows must use one non-empty,
consistent group; exclusive rows must leave the group empty.
Extra CSVs named in provenance but not referenced by a manifest series are
treated as supporting tables and are syntax/row-count checked without being
included in curve totals.

The worker-side report is diagnostic only. During finalization the control
plane reruns the same deterministic implementation against the staged bytes and
registers `validation_reports/validation_report.json` as a control-generated
derived artifact. Its totals, not manually authored prose, are the canonical
source for curve-row, eligibility, detection-limit, and shared-pixel counts.

Manifest `status` summarizes the whole figure. `qualified_series_count` counts
unambiguous identity bindings; it is not a quantitative row count.
Quantitative eligibility is
series-local: an ambiguity record disqualifies only the named
`(panel_key, series_key)`, and an explicit row eligibility flag applies only to
that table row. A package may therefore be globally `unresolved` while a
separately bound measured series remains eligible. Do not set unrelated tables
to zero eligibility to mirror the global status. Preserve occluded/gap rows and
exclude their declared intervals downstream instead of connecting them.

For line and fit-segment CSVs, `point_index` preserves source-column position
inside the declared pixel domain. Missing source columns therefore create an
index discontinuity instead of being renumbered into a false continuous run.
For canonical tables a validator cross-checks every `point_index` delta against
the corresponding `pixel_x_raw` delta. Historical extended tables may already
carry conservative extra index gaps, but a multi-column `pixel_x` jump must
still have a non-adjacent index. Thus a distant pair of source pixels cannot be
made adjacent by rewriting indices. Marker tables retain ordinary strictly
increasing point order because their points are not sampled column-by-column.
A local maximum trace gap is recorded in `max_gap_px`; it does not by itself
create a series identity ambiguity.

Gap classification is a visual evidence decision, not a way to excuse a
tracker failure. Compare the fidelity overlay with the source panel. When a
solid source trace is visibly continuous, a CSV gap means the spec or tracking
parameters are inadequate and the extraction must be rerun. Only a visible
source interruption, occlusion, or explicitly excluded region may remain as a
declared evidence gap. Do not convert a tracker dropout into two adjacent
ineligible rows.

Use `scripts/render_curve_support.py` after adding any extended eligibility or
detection-limit fields. Select explicit `PANEL/SERIES` keys. The output shows
all observed rows in a subdued style, eligible contiguous runs prominently,
singleton eligible points as markers, below-limit masks as crosses, and other
masks as open circles. Direct eligible support is solid and declared shared
overdraw support is dashed. The renderer never creates full-height mask bands,
and it rejects invocations without explicit series selections. It never
connects across a point-index discontinuity or a raw
pixel-column discontinuity. When its output is below the package's
`audit_overlays/` directory, it deterministically updates that artifact's
bytes/SHA-256 provenance entry before bundle validation.
