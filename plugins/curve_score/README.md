# Curve science plugin

Operation names below are reusable plugin library declarations. They do not
provide an application scheduler or Run service; see the
[Plugin API](../../docs/PLUGIN_RUNTIME_API.md).

`science.result.diagnose.v1` owns a complete analysis task: inspect exact observations,
compute metrics, draw figures, diagnose material numerical limitations and write one
scientific report. Plans and independent reviews are optional context. Scoring and
localization are internal tools; they do not require separate contract, review or
transform Runs. Curve comparison methods and conclusions remain scientific choices.

The consuming host owns retention of task workspaces and originals after failure.
The provided checkpoint tools can reuse exact numerical work when retrying the same
originals. Scientific files contain observations and results; control retains original
identities and receipts.
TCAD analysis reuses this workspace and supplies its own native-output parser.

Curve parsing, scoring, coverage and residual algorithms remain reusable Python
capabilities. The former curve-contract design/review and score/coverage/error-analysis
scheduling chain is retired. The optional `curve_figure_evidence` plugin owns paper
figure extraction and its deterministic curve-bundle adapter.

The scorer consumes canonical curves and explicit comparison choices. It never guesses
units, series identities, missing values or crossing selections. Insufficient support
remains unavailable or inconclusive.
