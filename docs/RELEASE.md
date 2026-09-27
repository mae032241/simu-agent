# Release Procedure

[简体中文](RELEASE.zh-CN.md) | English

<a id="current-status"></a>
## Current implementation and validation status

The current platform exposes the generic plugin runtime API, explicit Root reading
intents, and LocalTrusted execution. See [Architecture](ARCHITECTURE.md),
[Plugin runtime API](PLUGIN_RUNTIME_API.md), and [Security](../SECURITY.md).
LocalTrusted assumes cooperative local Agents and the host user; it does not isolate
hostile processes sharing the control user's OS identity.

Current Operation ABI is 23. Source node `775b3e8` and merge node `5a90f3f`
have identical trees. The recorded approval-fix verification for that source was
1593 source cases passed (70 cases in other lanes deselected), with a 2,000,000,000
byte address-space cap and an observed process-tree RSS peak of 304,713,728 bytes.
Focused checks covered 49 cases, including actual local HTTP approval routes with
a test execution adapter and an isolated replay of the original approval receipt.
These are prior candidate results, not tests rerun by this documentation cleanup.
Raw receipts remain outside the source release; this summary is not a replacement
for those receipts or proof that the current installation contains the fix.

Open limits:

- SEC-002 remains open: LocalTrusted does not isolate processes sharing its UID.
- Earlier live figure and short SProcess initialization checks do not establish a
  complete Fig.4 research result, H0/H1 verdict, or full SDevice realization.
- Root/Worker/helper token savings have not been established by a controlled
  comparison. Helper use alone is not evidence of lower total cost.
- Source checks do not qualify installed/process/live lanes for newer bytes.
  Instance archive/restore requires verified writer quiescence; real deployment,
  systemd and scientific continuation checks remain candidate-specific.
- Pending and known-issue entries in the architecture constraint registry remain
  open for reassessment. Removing historical reports does not close them.

Run the relevant checks below for each release candidate and retain its emitted
`result.json`, logs and source identity outside the source tree.

<a id="publication-scope"></a>
## Source publication scope

`scripts/build_git_release.py` uses explicit source/document/tool allowlists. It
includes the current hermetic test tree, fixture packages, serial resource runner,
CI configurations, and scripts imported or launched by those tests. The retired
`test_native_worker_usage.py` tested only a private historical measurement script;
it was removed after confirming no production consumer. No test is silently
excluded to hide a missing private dependency.

Process documents, raw acceptance output, duplicate reviews and source backups
have been removed from the current tree. Their original content remains in Git at
`5a90f3fa33135c8b151a547e2eceed0d102eea95`; for example, use
`git show 5a90f3f:docs/plans/HISTORY.md` to locate old records. This does not rewrite
Git history or erase unresolved findings. The retained Fig.4 discussion and its two
direct source snapshots are research references, excluded from the release.

Published architecture, installation and plugin documents link directly to these
status/scope sections. The builder copies the maintained text without a second set
of editorial replacements. `MANIFEST.sha256` hashes the generated release bytes.

## Historical compatibility break: 2026-09-24

That revision introduced Operation ABI 19 (the current ABI is 23). The UI no longer reads Task-era databases or old Artifact
envelopes containing `task_ref`. Removed formats include experiment-intent `validation_plan`,
`next_action_kind` / `recommended_task_mode` / `accepts_actions`, the
`scid_describe.representation` parameter, and the five-column SProcess CSV fallback.
Use Runs, strict Artifact envelopes, `validation_intent`, compact invoke contracts,
and `SCID_CURVE_V1` logs. Original data is retained; recreate current-format inputs
without inheriting old approvals or scientific qualification. Keep the old installation
for reading old data, and retain environment/data copies before updating.
That cleanup was checked statically at the time. Later validation is described
in the current status above; no existing deployment is updated by this procedure.

The TCAD job payload is now v4 (policy digest, cumulative resource enforcement and file-reference transport). Removed compatibility includes the unused
`max_processes` hint, automatic smoke-policy migration, historical serialization,
and sprocess v1 repackaging. Update control and remote runners together.
Use declared-source v2 projects with complete case anchors and exact rematerialization.

## Release steps

1. Run bounded tests serially from the source workspace:

   ```bash
   python scripts/run_tests.py --lane source --per-file --output /tmp/scid-source
   python scripts/run_tests.py --lane installed --output /tmp/scid-installed
   python scripts/run_tests.py --lane process --per-file --output /tmp/scid-process
   ```

   See [test lanes and limits](../tests/README.md). Output directories must be new.
2. Build a clean repository:

   ```bash
   python3 scripts/build_git_release.py \
     --output git_release/scidiscovery-agent \
     --force \
     --init-git
   ```

3. Verify `MANIFEST.sha256` from the generated directory:

   ```bash
   cd git_release/scidiscovery-agent
   sha256sum --check MANIFEST.sha256
   git status --short
   ```

4. Review the staged file list. Confirm there are no research inputs, outputs,
   databases, generated platform files, host paths, credentials, licenses, or
   proprietary documents.
5. Add a software license before a public release.
6. Create the initial commit using the repository owner's identity:

   ```bash
   git commit -m "Initial SciDiscovery Agent release"
   git remote add origin <repository-url>
   git push -u origin main
   ```

7. On a clean Linux/WSL target, follow `docs/INSTALL.md` and verify at least the
   local deployment-smoke mode, install transaction evidence, and rollback
   fault matrix. Real TCAD qualification is a separate release gate; see
   [TCAD_QUALIFICATION_STATUS.md](TCAD_QUALIFICATION_STATUS.md).

The sibling `scidiscovery-agent.tar.gz` is a normalized source archive. It does
not include `.git`.
