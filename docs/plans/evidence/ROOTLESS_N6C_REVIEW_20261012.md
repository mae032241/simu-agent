# N6c independent final review — 2026-10-12

**PASS: frozen source / zero-model fake and installed qualification scope.** No remaining blocking defect found in the reviewed implementation. Review base `a5f4bb7afd8d172c952f8ef23cc937de564a8c9a`; current uncommitted N6c diff. Reviewer edited only this `/tmp` report, performed read-only source/artifact checks, did not run tests/models, did not edit production/tests, and did not commit. `git diff --check` passed.

## Resolved findings

1. **Success before seal / accepted intent drift:** `execution.record` now checks the successful continuation's runner/native process receipt hashes, exact current intent digest, receipt shape and accepted boot, and rederives the cumulative budget report from the full prior chain before allowing raw/seal readers. The root failed record is not overwritten. The two terminal-success-before-seal negative controls mutate the current intent or report, then require seal and ordinary run to reject, without a new attempt or root seal. Previously sealed execution_ref drift remains rejected.
2. **Frozen task and schema at actual launch:** `continuation.validate_task` verifies root result schema against the job's exact role/protocol and reuses `_validate_inputs` at initial admission and the real Popen boundary. **Correction to the preliminary report:** `_validate_inputs` already checked science-task.json == science_view at its first line; initial task-view admission was not missing. The gap was schema revalidation and late task/input validation at resume dispatch. Late schema/task mutation now leaves an accepted attempt with no native-process receipt and no resume request; original published schema/view bytes are unchanged.

## Reviewed complete paths

- `execution`: append-only ordinal attempt chain; job/root/previous proofs; selected successful raw; root seal/result/schema remain root metadata, native files stay per attempt. No mutable current status or successful raw copied over failed initial raw.
- `continuation` and CLI/controller: explicit max 1..2 new attempts on newly frozen resume-enabled instances; exact executable/config files, thread event and unique bounded session metadata, same home/workspace; no --last/fork/PATH selection. Valid success is collected/sealed before considering retry; known local nonzero/no-stop/clean/observed-meter failure only. Existing accepted work is collected before cap/pause checks; unknown work is not reissued. Rejection restores inactive clock only when execution is genuinely inactive.
- `native/runtime`: each runner/watchdog is bound to a fixed attempt and exact intent identity; lease, process cleanup, output and logs are scoped to that attempt. Resume preserves frozen raw-Codex global configuration/permissions and shows remaining original-node allocation. Arbitrary shell side-effect idempotence is not claimed.
- `budget`: input+output meters accumulated once per turn/attempt; cached is not added twice. Current prior counters must equal original chain consumption, with finite/nonnegative checks and matching report role/limits/dispatch/usage. Node/W caps and cumulative seconds are not reset. A legitimate shared amendment supplies the new attempt's current shared overlay, while retaining prior consumed node allocation. Continuations consume original max_steps, later fresh nodes check total used slots, prepared current slot is not double charged, and N6b reserve/pause/closeout are preserved.
- All raw/outcome consumers inspected: contracts validate/seal/parent copy/selected originals; history observer/_source/direct_sources; search W meter; correction and semantic roots; native usage/runtime/budget; controller/CLI; delivery binding/invoke. Root metadata and attempt native data are distinguished. Ordinary run still cannot turn a failed node into a fresh replay, or skip an unknown node.
- Compatibility: published scientific protocols 1..8 get no new unconditional schema/view fields; original jobs/settings/failed artifacts are preserved. No silent old-instance resume-policy migration, budget expansion, model Root, generic checkpoint engine, second balance or parallel current-state authority.

## Evidence personally inspected (parent executed through shared serial runner)

- Full rootless baseline before final narrow fixes: `.trial/n6c-checks-20261012/rootless/batch-001/pytest.log`: **360 passed in 170.29s**.
- Final exact focused set: worker_resume, node_budget, runtime, closeout, delivery; `.trial/n6c-checks-20261012/final/result.json` and `batch-001/pytest.log`: **106 passed in 56.03s, no skips**. Includes the actual public-harness bwrap delivery lane, W continuation → A sealing/search/history consumption, shared amendment without node refund, steps/reserve/cap2, malformed prior counter, missing meter/report, unknown accepted attempt, pause/tamper, and the two final integrity windows.
- Fresh installed CLI `.trial/n6c-installed-final-20261012/result/result.json`: **seven checks passed, model_requests=0**. Explicit same node/session, retained checkpoint and initial files, cumulative 14+22=36 observed tokens with cached not double charged, ordinary-run no replay, and successful node not resumed again. Commands/exit codes inspected.
- Read-only byte comparison independently verified **all 15 source / wheel / installed modules** against module-bindings.json. Wheel SHA: `e94ff461a186eb5146447cc7d522cdc9f7c77ea405a74c7a84f11a1ef7721fcc`.

## Qualification boundary

**Actual native same-thread continuation, actual incremental usage semantics and actual permission behavior remain unqualified.** Fake UUID/session fixtures and a policy declaration/script hash cannot prove those properties. A future authorized native qualification remains separate. No real scientific model calls, original N5 mutation or budget enlargement was performed by this review or claimed by these gates.

## Final reviewed hashes

```json
{
  "src/scidiscovery/research_loop/__init__.py": "84f6b87da02cfd9d0386b077b72267d2cdfc8e603036cb03f42874f9795f6f54",
  "src/scidiscovery/research_loop/budget.py": "120747acb8babd47c36d5d609acfdd3b0ca3c93d8720075e01b45f417a37dd99",
  "src/scidiscovery/research_loop/cli.py": "e8fe7f80ab72b33f784e006d6eaaca219850a691c7739ccd0193347f31e787d9",
  "src/scidiscovery/research_loop/continuation.py": "dfb9c746c175892eb1cd35e3b17b75f63636b1ffa2011cd64c990fce8840d365",
  "src/scidiscovery/research_loop/contracts.py": "caf71aa0a88a99be853ec55c134338d9e80dd60e138a71378b3fec1f272575b0",
  "src/scidiscovery/research_loop/controller.py": "95e0d3b329370366d4910a282f3178d9770b33faf0e2fe19f209c0136e80bb66",
  "src/scidiscovery/research_loop/correction.py": "05c272d262315e6cbf23688465b0ee5e839e09d3a961addf19396c8bf756b296",
  "src/scidiscovery/research_loop/cov_delivery.py": "eac83d833adb9e3eb26c7494db4327134bd0909bf49a8422cefb604c6ebf2023",
  "src/scidiscovery/research_loop/delivery.py": "d98761850816e726c0d35aecaa0f495fced6178db38d38ca92c7b45c6aafcb07",
  "src/scidiscovery/research_loop/execution.py": "4169c3122210d14c63a949c945e5f0ae197afa249fd29fb660eeacebf77a24e0",
  "src/scidiscovery/research_loop/history.py": "80ffd74d4999947ee7afce29f03bca920a536078871725b97eebbdc449b994dd",
  "src/scidiscovery/research_loop/native.py": "3493bdad7c7a309d3fe301c49b96c01139aa2706bef16cf2c7bc4e87000ee63a",
  "src/scidiscovery/research_loop/runtime.py": "13a9a819da04c2010c2404ca059c7dd3c7ccad30d983cc56a448f8aecd3f45fb",
  "src/scidiscovery/research_loop/search.py": "7c59984e2237dd7cb925609e7f3c5f22350d89c147764ff76e0fff75b0279b3b",
  "src/scidiscovery/research_loop/semantic.py": "43e6b873cd9ce447f9abed02c787992f8b326c278ddeae5b3add9e7dfe318a64",
  "tests/research_loop/test_worker_resume.py": "019cc7a0f686aafa8f14da3b4271cc668088d573bb7e33f0bde96afddb9967a0",
  "docs/ROOTLESS_CLI.zh-CN.md": "3dd76cf9fb82d9b1d50d1bbc44c4b6d49620949b1584039b359eeb68c48d3e73"
}
```
