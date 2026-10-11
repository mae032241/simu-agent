# Independent review of the thin filesystem live H/W/A run

Reviewed source revision: `ff165dc` in `123/scidiscovery-e5.2`.
Reviewed live evidence: this directory's `instance/native-evidence/{001,002,003}/native.jsonl`, terminal outcomes, original scientific responses, host seals, scientific work files, selected artifacts, and downstream input copies. Review used the `scid-cross-boundary-review` skill. The reviewer did not implement the change, rerun tests, launch models, or modify the live instance. This review file is the sole reviewer-authored output.

## Verdict

No blocking defect was found for the evaluated objective: scientific roles perform scientific work while the host owns collection, exact byte identities, envelopes, and sealing. The complete live H→W→A path was observed. Every recorded role command and file-change event was inspected through each terminal event, including the contents and generation logic of potentially ambiguous JSON files, comparison drivers, serialization checks, reproduction code, and reports. The conclusion is based on semantic inspection rather than keyword counts.

No scientific-role attachment manifest, file inventory for handoff, hash list, host schema validator, envelope builder, receipt builder, or mechanical packaging script was observed. Directory discovery with `rg --files`, scientific score tables, model configurations, numerical diagnostics, and comparison reproduction code were inspected and classified by their actual function.

| Role/node | Completed commands | File-change events | Selected artifacts | Selected bytes | Scientific conclusion bytes | Navigation bytes |
|---|---:|---:|---:|---:|---:|---:|
| H / 001 | 19 | 4 | 3 | 28,221 | 1,198 | 559 |
| W / 002 | 43 | 8 | 7 | 295,114 | 1,245 | 1,267 |
| A / 003 | 26 | 3 | 4 | 45,019 | 1,277 | 1,738 |

All three native outcomes report return code 0, no stop reason, known usage, and a terminal scientific-output digest. All three host seals exist. The final controller result is `bounded_steps_exhausted`, with three completed nodes, A's `revise_h` route, and `goal_completion: not_asserted`. The next H was not launched. This establishes successful execution and handoff of the bounded H/W/A round; it does not establish completion or hidden-test quality of the scientific objective.

## Role work and ambiguous cases

H's scripts estimate the forward operator, inspect sparsity and residuals, compare sparse recovery under hypothetical shifts, and check solver stability and validation-label invariance. `work/data_diagnostics.json` contains scientific measurements such as rank, norms, support counts, and residual estimates. Its final artifact-table row/method count checks the scientific comparison. H delivered a scientific direction document, comparison CSV, and candidate source.

W's formal comparison driver generates candidate training code, executes finite scientific experiments, preserves failures and reported scores, and invokes the benchmark's submit-time scientific honesty audit. Its progress JSONL and formal comparison CSV record experiment configurations and observations; they are not attachment inventories. Its stress and bootstrap drivers evaluate declared perturbations, training-only selection, and conditional uncertainty. The selected-candidate JSON is a model configuration. Shape, finite-value, poisoned-validation, and tightened-solver checks concern scientific/model correctness.

W's cloudpickle roundtrip checks whether a scientific model preserves predictions after serialization and agrees with the submitted model. The resulting local pickle remains scratch. Its `reproduce_comparison.py` combines recovery methods, scenario experiments, and bootstrap analysis into a runnable scientific deliverable. The code was read; it contains neither collection/sealing logic nor an attachment package. The later comparison of reproduced numerical tables and score arrays checks scientific reproducibility. W moved redundant comparison intermediates to scratch and handed off selected source, results, report, reproduction code, and row-level numerical evidence.

A directly checks reported experiments and candidate/submitted-model predictions, then performs independent scenario-weight sensitivity and new structured-shift counterexamples. Its assertions check perturbation magnitude and numerical predictions. They do not inspect host envelopes, validate host schemas, or construct provenance inventories. A's JSON diagnostics contain scientific configurations, warnings, and weighting thresholds. Its report carries limitations and requests a scientific mechanism revision.

## Host collection and downstream access

H's concise scientific response contains three relative Markdown links. The host mapped them to the actual W input paths for the direction document, comparison, and candidate. W read all three mapped paths. W's response contains four selected links to its report, comparison, formal results, and candidate. A's 1,738-byte navigation document includes H's three and W's four mapped entries; it does not enumerate every artifact or expose per-file hashes, the host schema, or envelopes. A read the mapped parent conclusions, direction, report, candidate, formal results, and comparison, then accessed further paired/reproduction evidence when scientifically needed.

Every visible H/W entry copy in A was compared with its source bytes and matched. Each node's `conclusion.json` matches its original native scientific response byte for byte and contains only the scientific fields. Host envelope and schema files are absent from all three scientific node roots; they reside in host evidence storage.

Scratch was excluded from the seals: H retained 14 scratch files totaling 2,227,180 bytes; W retained 200 totaling 3,531,942 bytes; A retained four totaling 332,289 bytes. No sealed material source is under `work/`. Parent inputs and historical scratch were not recursively collected as new node artifacts. The benchmark's own shared run/model/submission storage is separate from the host's selected handoff artifacts.

## Limits of this evidence

This is one observed bounded round with the configured external launcher. It does not guarantee future model compliance, arbitrary native-tool output, every launcher, scientific optimality, or hidden-test reward. The live round did not create `experiments/<id>` child trees, use E, exercise supplementary user statements, or encounter successful-output resealing. Those paths have source/test evidence but no live qualification from this run. Supplements are currently frozen at preparation; no runtime update API is established. Historical scratch retrieval remains unimplemented.

The earlier live01 run used the old workspace layout and lacks the new terminal raw-output digest; this review does not claim it was automatically recovered. For new-format successful-output resealing, the scientific response remains fixed, and repair must preserve any deliverable explicitly linked by that response. Artifact membership and bytes become frozen at successful sealing.

No scientific scoring verdict is provided here. The bounded verdict concerns removal of mechanical handoff work and the observed scientific filesystem handoff.
