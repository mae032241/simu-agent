# Optional paper-figure evidence plugin

This plugin registers paper-figure extraction and independent review through
the single `scidiscovery.plugins` entry point. It owns deterministic
digitization, calibration, validation, and curve normalization; the default TCAD
installation does not include it. A typed
request Agent selects one exact source image, a deterministic Transform
materializes the attachment family, and separate single-output Agents author
and independently audit the ScientificIntake. The authoring Operation creates
an Intake when only the complete family is bound and performs a bounded,
copy-on-write complete revision when its optional prior Intake and exact
non-passing audit are both bound. Agent collection submission is not used.
The request Agent supplies visible plot geometry, tick calibration, and series
identity, then inspects both a source-pixel overlay and a CSV-only numeric redraw.
The deterministic path owns pixel extraction, calibrated values, statistics, and
shared-pixel labels; it performs no OCR, automatic axis detection, or scientific
identity inference.

The Agent selects a PDF page and document image index, or the bound raster.
Preview and submission materialize recovered hashes, dimensions and tool metadata
from that original source. An unresolved request retains the original source identity,
known partial fields and explicit gaps without inventing recovery metadata. Only
quantitative extraction admission requires a ready request with complete metadata.
