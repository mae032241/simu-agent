# Release Procedure

[简体中文](RELEASE.zh-CN.md) | English

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
   local deployment-smoke mode. Real TCAD qualification is a separate release
   gate.

The sibling `scidiscovery-agent.tar.gz` is a normalized source archive. It does
not include `.git`.
