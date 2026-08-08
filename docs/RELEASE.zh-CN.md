# 发布流程

简体中文 | [English](RELEASE.md)

1. 在源码工程中运行 `pytest -q`。
2. 生成干净仓库：

   ```bash
   python3 scripts/build_git_release.py \
     --output git_release/scidiscovery-agent \
     --force \
     --init-git
   ```

3. 在生成目录校验 `MANIFEST.sha256`：

   ```bash
   cd git_release/scidiscovery-agent
   sha256sum --check MANIFEST.sha256
   git status --short
   ```

4. 人工检查暂存文件，确认不含研究输入/结果、数据库、生成的平台配置、主机路径、
   凭据、许可证或专有文档。
5. 公开发布前加入由项目所有者选择的软件许可证。
6. 使用仓库所有者身份创建首次提交并推送：

   ```bash
   git commit -m "Initial SciDiscovery Agent release"
   git remote add origin <仓库地址>
   git push -u origin main
   ```

7. 在干净 Linux/WSL 目标机按 `docs/INSTALL.zh-CN.md` 至少完成本地部署冒烟。
   真实 TCAD 资格是独立发布门禁。

同目录的 `scidiscovery-agent.tar.gz` 是规范化源码包，不包含 `.git`。
