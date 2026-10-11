# Frozen offline candidate-pool evaluation

No LLM calls, training, budget amendment or source-instance modification. Hidden outcomes are post-hoc diagnostics only; they must not be supplied to a scientific role or used for new model selection in the original task.

Both instances use identical train/val/meta/runner/exp_cli hashes, and public scoring conditions match the official hidden verifier metadata. Each saved candidate is evaluated in the previously validated bwrap/official-verifier boundary; both datasets, environment versions, model pickles, ledger, audit sources and verifier hashes are frozen in manifest.json.

## Coverage and rank diagnostics

| Pool | Candidates/scored | Completed recorded audits | Missing audits | Failures | Spearman val/hidden | Spearman val/conditional reward |
|---|---:|---:|---:|---:|---:|---:|
| n5 | 50/50 | 20 | 30 | 0 | 0.608717 (n=50) | 0.600707 (n=50) |
| live02 | 42/42 | 42 | 0 | 0 | 0.290925 (n=42) | 0.285019 (n=42) |

Spearman uses exact average ranks for ties; public validation scores remain the original rounded ledger values. Hidden recovery is captured at full precision; rewards retain the official four-decimal rounding. Separate audited and pooled denominators and tie counts are in final-summary.json.

## Selection differences within each frozen pool

| Pool / choice | Run | Val | Hidden recovery | Conditional reward | Audited verifier reward | Loss vs pool best conditional | Loss vs audited-pool best |
|---|---:|---:|---:|---:|---:|---:|---:|
| n5: Pool best conditional | 19 | 0.852800 | 0.677530 | 0.724800 | unavailable | 0.000000 | unavailable |
| n5: Audited-pool best | 17 | 0.907300 | 0.489721 | 0.217200 | 0.217200 | 0.507600 | 0.000000 |
| n5: Actual submission | 17 | 0.907300 | 0.489721 | 0.217200 | 0.217200 | 0.507600 | 0.000000 |
| n5: Latest historical non-null A recommendation | 34 | 0.926200 | 0.473814 | 0.187900 | 0.187900 | 0.536900 | 0.029300 |
| n5: Val highest | 32 | 0.926500 | 0.452567 | 0.152000 | 0.152000 | 0.572800 | 0.065200 |
| live02: Pool best conditional | 30 | 0.857900 | 0.609285 | 0.506000 | 0.506000 | 0.000000 | 0.000000 |
| live02: Audited-pool best | 30 | 0.857900 | 0.609285 | 0.506000 | 0.506000 | 0.000000 | 0.000000 |
| live02: Actual submission | 42 | 0.894600 | 0.578637 | 0.420500 | 0.420500 | 0.085500 | 0.085500 |
| live02: Latest A explicit prose retention | 42 | 0.894600 | 0.578637 | 0.420500 | 0.420500 | 0.085500 | 0.085500 |
| live02: Val highest | 15 | 0.906600 | 0.302665 | 0.006800 | 0.006800 | 0.499200 | 0.499200 |

**n5 recommendation scope:** Latest non-null structured recommendation is historical A013 run34; latest A016 recommendation is null and prose retains actual run17. Do not manufacture a current A016 recommendation.


**live02 recommendation scope:** Published older protocol has no structured candidate recommendation; A006 explicitly retains audited run42 in its summary. This prose retention is shown separately, not encoded as a fabricated structured recommendation.

## Qualification limits

- Missing audit metadata uses leakage_flag=null, never false. Its prediction-based reward is conditional; its audited/official reward stays unavailable. Known leakage is forced to zero under the official rule, with prediction shown only as diagnosis. No known-leakage record was found in these two pools.
- Recorded completed honesty audits are frozen existing source evidence, not new independent audits. Apart from the actual submitted model/receipt pair, these historical receipts do not contain a cryptographic hash linking their separately fitted audit model to the current saved candidate pickle. The table explicitly reports this scope; it does not elevate missing or skipped audit evidence.
- An ordinary verifier band assertion is retained as a diagnostic; a score below the pass band is still a successfully evaluated candidate, with its prescribed reward. Runtime or missing-file failures are separate.
- Actual submitted-model SHA matches its selected candidate pickle in each frozen instance. Hashes of all source-instance files match before and after evaluation.

## Reproduce

The original command was `python .trial/n5-live02-pool-eval-20261011/evaluate.py`, holding scripts/run_tests.py serial_lock for the complete pool. The script refuses to overwrite an existing manifest. To repeat, copy evaluate.py into a fresh sibling output directory and run it there; then copy/run report.py to summarize. Per-candidate snapshot/, verifier/hidden.json, resource.json and pytest.log preserve all inputs, exact outcomes and failures.

The output directory is operator-owned post-hoc evidence; none of it is written into either original instance.

## Independent review

2026-10-12: independent reviewer recomputed average tied ranks and checked all 92 source/snapshot model hashes, hidden outputs, return codes, frozen verifier/runtime hashes and unchanged instance manifests. PASS for post-hoc diagnostic evidence only; this does not qualify missing audits or establish new independent model audits.

[Independent review record](ROOTLESS_N5_LIVE02_POOL_REVIEW_20261012.md)
