# 发布流程

简体中文 | [English](RELEASE.md)

## 2026-09-24 破坏兼容更新（工作树）

本轮 Operation ABI 为 19。旧 Task 数据库及带 `task_ref` 的旧 Artifact envelope 不再由 UI 读取；
旧实验意图 `validation_plan`、弃用路由字段 `next_action_kind` / `recommended_task_mode` /
`accepts_actions`、`scid_describe.representation` 参数和旧五列 SProcess 曲线 CSV 回退均已删除。
当前使用 Run、严格 Artifact envelope、`validation_intent`、compact invoke 合同及 `SCID_CURVE_V1` 日志。
旧数据原件保留；需要续接时从原输入重新生成当前格式，不自动继承旧审批或科学资格。
旧安装保留用于查看原版本数据。更新前由操作者保留旧环境与数据副本，不直接覆盖唯一原件。
此工作树尚未部署；本轮仅做静态检查，未执行测试、测试收集、安装或构建。

TCAD 任务载荷已升级至 v4（policy digest、累计资源约束与文件引用传输），移除未执行的 `max_processes`、旧 smoke 配置自动迁移、
旧序列化字节保持及 sprocess v1 重新打包分支。控制端和远端 runner 需同时更新；
使用 declared-source v2 项目及完整 case anchors，重新物化必须与已审原件一致。

## 发布步骤

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
   检查安装事务证据和回滚故障矩阵。真实 TCAD 资格是独立发布门禁，当前状态见
   [TCAD_QUALIFICATION_STATUS.zh-CN.md](TCAD_QUALIFICATION_STATUS.zh-CN.md)。

同目录的 `scidiscovery-agent.tar.gz` 是规范化源码包，不包含 `.git`。
