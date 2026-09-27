# Release Procedure

[简体中文](RELEASE.zh-CN.md) | English

<a id="current-status"></a>
## Current implementation and validation status

The current platform exposes the generic plugin runtime API, explicit Root reading
intents, and LocalTrusted execution. See [Architecture](ARCHITECTURE.md),
[Plugin runtime API](PLUGIN_RUNTIME_API.md), and [Security](../SECURITY.md).
LocalTrusted assumes cooperative local Agents and the host user; it does not isolate
hostile processes sharing the control user's OS identity.

The internal R4 document remains the single implementation and acceptance plan.
Its research history is not shipped. The previous source node `6adf018` has recorded
bounded evidence for 1386 source, 16 installed and 54 process cases. Later fixes
require their own receipts; these historical counts do not qualify newer bytes.
Source release collection and isolated wheel checks do not establish live model,
solver, deployment, or Python sdist acceptance. Run the relevant checks below for
each release candidate and retain the emitted `result.json` and logs.

<a id="publication-scope"></a>
## Source publication scope

`scripts/build_git_release.py` uses explicit source/document/tool allowlists. It
includes the current hermetic test tree, fixture packages, serial resource runner,
CI configurations, and scripts imported or launched by those tests. The retired
`test_native_worker_usage.py` tested only a private historical measurement script;
it was removed after confirming no production consumer. No test is silently
excluded to hide a missing private dependency.

All `docs/plans/` history, including raw research evidence and the private R4 plan,
is excluded. Original research documents are not edited. In the generated copies
only, the English/Chinese Architecture introductions and archive implementation
links point to these public status/scope sections, with explicit public labels.
The Plugin runtime API validation paragraph links here and identifies omitted
private receipts. These are publication projections, not a replacement plan or
new acceptance evidence. `MANIFEST.sha256` hashes the projected release bytes.
Other historical citations in shipped audit documents describe archived material;
they do not make that private archive part of this delivery.

## 2026-09-24 breaking update (working tree)

Operation ABI is now 19. The UI no longer reads Task-era databases or old Artifact
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
