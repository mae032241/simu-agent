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
