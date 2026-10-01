# Optional paper-figure evidence plugin

The optional plugin exposes one complete author task, independent audit, and a
normalization consumer. It is not part of the default TCAD installation.

- `science.evidence.extract.figure.v3`: one author inspects the exact raster or
  PDF, describes visible geometry/calibration/identity, previews extraction,
  explicitly saves the selected family, checks its files and authors ScientificIntake.
- `science.figure.evidence.audit.v2`: another Agent reviews that Intake against
  `paper_source`, its exact `figure_provenance` control manifest and every
  `figure_family` attachment.
- `scidiscovery.curve-bundle.figure-evidence.v3`: normalize that complete family
  only with its exact passing independent audit. The internal numerical
  normalization profile remains v2; it is not a callable legacy Operation.

The author uses `worker_curve_figure_inspect_source`,
`worker_curve_figure_preview` and `worker_curve_figure_save` in one workspace.
A ready save requires a completed controlled preview receipt for the exact
materialized request. Saving explicitly selects one request and publishes all
files plus a selected-family manifest to immutable Artifact storage. It returns
local read-only files and exact evidence aliases for composing Intake. Retrying
an unchanged save is idempotent; a different selection needs a new Run.
Partial saves reuse exact adopted receipts by source/request/data item/bytes, even
when a recovery uses different input aliases; only missing members are registered.
Failed calls remain in the control recovery manifest. Finalization rejects an
incomplete selection, substituted source or extra/unselected member.

The Intake's immutable parent is the control manifest, which in turn binds the
selected request, algorithm identity, source, files and attempts. Consumers must
bind every saved member, including the selection record, by exact Artifact
identity. Omission, tampering, another family's manifest and reuse of an old
Intake audit are rejected. Neither tool save nor faithful audit grants quantitative
qualification. A revision must bind the prior Intake, its non-passing audit, exact prior
`figure_provenance` and complete `figure_family`. For wording-only changes,
`worker_curve_figure_reuse` adopts those original receipts and Artifact identities
without running the digitizer. Input aliases must not shadow the retained original
tool evidence aliases. The new Intake receives a new control manifest and requires
a fresh independent audit; the prior verdict is never inherited. When the review
requires extraction changes, explicitly preview/save a new family instead of reuse;
a Run cannot mix the two selections.

PDF page/text and embedded-image recovery remain available. The author locates
its page/index and views originals; deterministic code supplies hashes,
dimensions, pixel extraction, CSV values, reports, overlays and numeric redraws.
There is no OCR, automatic plot detection or inferred series identity. An
unresolved source selection saves its request and explicit limits without
claiming extracted tables; it can be faithfully audited but cannot produce a
quantitative curve bundle. The former request-author, materialization and second
Intake-author Operations are removed, without compatibility aliases.

The v2 digitizer selects connected paths through two-dimensional pixel support
with forward/backward costs. Guide-supported components retain natural starts,
ends and gaps, including observations beyond the seed endpoints. Each component
grows in both directions from supported interior identity anchors with the same
natural-end rule; horizontal reflection cannot authorize an unrelated prefix.
Equivalent anchors retain competing evidence. A longer unrelated
stroke cannot overwrite the selected path or fill its missing ends. Reacquisition
uses anchor residuals and pixel tolerances; unresolved merged branches retain ambiguity.
Ambiguity compares cost differences over the alternative path's actual differing
columns; extending a common prefix or tail does not change the local decision.
Guide anchors select a path; coordinates come
from image centers and local normal sections. Sharp image caps are retained.
Solid, dashed and dotted styles survive the request,
manifest and redraw. Empty source columns remain gaps. A thick or steep column is
not evidence of physical multivalued behavior. Width alone never disables
interpolation. Competing continuous paths retain their bands and identity ambiguity;
disconnected support and stated scientific limits prevent interpolation.
Disconnected adjacent strokes split interpolation and redraw runs using their
recorded pixel support ranges; both endpoint observations remain eligible within
their own segments. Missing support ranges preserve legacy table semantics.
CSV localization geometry separates the measured normal line width, extracted
trajectory slope and one-pixel resolution from the full candidate support envelope.
The conservative bounds are `dx=0.5` and
`dy=max(0,(normal_width-1)/2)*sqrt(1+slope²)+0.5*(1+abs(slope))` pixels;
they are propagated separately through each calibrated axis, not statistical errors.
CSV `observed`, `identity_resolved`, quantitative eligibility and
`interpolation_eligible` describe different facts; the manifest/report counts and
overlays use these same rows. Numeric redraws and curve consumers do not connect
across excluded interpolation intervals. Crossing consumers reject unavailable
curves even when their endpoint observations remain readable as raw data.

Authors may supply series `use_limits` with `pixel_bbox`, a scientific `reason`
and `applies_to` (`quantitative_measurement`, `interpolation`, or `all`). These retain
source observations and restrict their use; `exclusion_regions` remove non-data
pixels. The program derives all row flags, candidate ranges, gaps and shared groups.
CSV `use_limit_indices` refer to the complete reasons in manifest `use_limits`.
Manifest series record effective global and recipient `exclusion_regions`.
Shared allocation and CSV validation reject excluded raw or subpixel observation
coordinates. Selected v2/v7 families also verify these restrictions and `use_limits`
against the exact frozen request; a manifest cannot silently omit them.

Shared groups preserve each direct owner's coordinates. An owner whose color is
covered may retain a `shared_pixel` observation linked to its visible source.
Shared observations are not automatically ineligible, and nearby coordinates are
not forced equal. The main CurveBundle and normalization audit preserve shared
dependency; independent evidence weights remain a scoring-contract decision.
Legacy overdraw copies retain their original semantics. New families use algorithm
`curve-figure-digitizer.v2` and validator v7; existing v1/v6 selections replay their
original report version and bytes. Extraction changes require a new complete family.

Input diagnostics identify the scientific field to correct. A generated family
that fails its own integrity checks returns `figure_generation_inconsistent` as a
program defect, without asking the author to invent mechanical shared fields.
Mechanical integrity and faithful audit do not grant a scientific conclusion.
