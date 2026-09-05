# Optional paper-figure evidence plugin

This plugin registers paper-figure extraction and independent review through
the single `scidiscovery.plugins` entry point. It reuses deterministic
digitization, calibration, validation, and curve-normalization algorithms from
`curve_score`; the default TCAD installation does not include it. A typed
request Agent selects one exact source image, a deterministic Transform
materializes the attachment family, and separate single-output Agents author
and independently audit the ScientificIntake. The authoring Operation creates
an Intake when only the complete family is bound and performs a bounded,
copy-on-write complete revision when its optional prior Intake and exact
non-passing audit are both bound. Agent collection submission is not used.
