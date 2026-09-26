# Release Procedure

[简体中文](RELEASE.zh-CN.md) | English

## 2026-09-24 breaking update (working tree)

Operation ABI is now 19. The UI no longer reads Task-era databases or old Artifact
envelopes containing `task_ref`. Removed formats include experiment-intent `validation_plan`,
`next_action_kind` / `recommended_task_mode` / `accepts_actions`, the
`scid_describe.representation` parameter, and the five-column SProcess CSV fallback.
Use Runs, strict Artifact envelopes, `validation_intent`, compact invoke contracts,
and `SCID_CURVE_V1` logs. Original data is retained; recreate current-format inputs
without inheriting old approvals or scientific qualification. Keep the old installation
for reading old data, and retain environment/data copies before updating.
This working tree is not deployed. Only static checks were performed; no tests,
collection, installation, or builds were executed during this cleanup.

The TCAD job payload is now v4 (policy digest, cumulative resource enforcement and file-reference transport). Removed compatibility includes the unused
`max_processes` hint, automatic smoke-policy migration, historical serialization,
and sprocess v1 repackaging. Update control and remote runners together.
Use declared-source v2 projects with complete case anchors and exact rematerialization.

## Release steps

1. Run `pytest -q` in the source workspace.
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
