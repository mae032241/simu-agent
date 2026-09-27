# 发布流程

简体中文 | [English](RELEASE.md)

<a id="current-status"></a>
## 当前实现与验证状态

当前平台提供通用插件运行时 API、明确的 Root 读取意图与 LocalTrusted 执行。
合同见[当前架构](ARCHITECTURE.zh-CN.md)、[插件 API](PLUGIN_RUNTIME_API.md)和[安全说明](../SECURITY.md)。
LocalTrusted 信任协作式本地 Agent 和宿主用户，不隔离共享控制用户 OS 身份的恶意进程。

内部 R4 文档仍是唯一实施与验收主计划，其研究历史不随源码发布。
前一源码节点 `6adf018` 留有受限验证记录：源码 1386、安装 16、进程 54 项。
后续改动需要各自的运行凭据；历史计数不自动证明新字节通过。
源码发布收集和隔离 wheel 检查不代表真实模型、求解器、部署或 Python sdist 验收。
每个发布候选均应按下文运行相关检查，保存输出的 `result.json` 和日志。

<a id="publication-scope"></a>
## 源码发布范围

`scripts/build_git_release.py` 使用明确的源码、文档和工具 allowlist，包含当前
hermetic 测试树、fixture 包、串行资源运行器、CI 配置及测试导入或启动的脚本。
旧 `test_native_worker_usage.py` 只测试私人历史测量脚本，确认无生产消费者后删除；
没有为隐藏私人依赖而静默排除测试。

整个 `docs/plans/` 历史（包括原始研究证据和私人 R4 主计划）均排除。
原始研究文档保持不变。仅在生成副本中，双语架构开头和归档实施链接改指向本页的
公开状态/范围，并明确标注公开说明；插件 API 验证段落改指向本页并说明私人凭据未附。
这只是发布投影，不是第二计划，也不是新增验收证据。`MANIFEST.sha256` 对投影后的
发布字节计算哈希。其他已发布审计文档中的历史引用只描述归档材料，不把私人归档纳入交付。

## 2026-09-24 破坏兼容更新（工作树）

本轮 Operation ABI 为 19。旧 Task 数据库及带 `task_ref` 的旧 Artifact envelope 不再由 UI 读取；
旧实验意图 `validation_plan`、弃用路由字段 `next_action_kind` / `recommended_task_mode` /
`accepts_actions`、`scid_describe.representation` 参数和旧五列 SProcess 曲线 CSV 回退均已删除。
当前使用 Run、严格 Artifact envelope、`validation_intent`、compact invoke 合同及 `SCID_CURVE_V1` 日志。
旧数据原件保留；需要续接时从原输入重新生成当前格式，不自动继承旧审批或科学资格。
旧安装保留用于查看原版本数据。更新前由操作者保留旧环境与数据副本，不直接覆盖唯一原件。
该次清理当时仅做静态检查；后续验证范围见上方当前状态，本流程不会更新已有部署。

TCAD 任务载荷已升级至 v4（policy digest、累计资源约束与文件引用传输），移除未执行的 `max_processes`、旧 smoke 配置自动迁移、
旧序列化字节保持及 sprocess v1 重新打包分支。控制端和远端 runner 需同时更新；
使用 declared-source v2 项目及完整 case anchors，重新物化必须与已审原件一致。

## 发布步骤

1. 在源码工程中串行运行受限测试：

   ```bash
   python scripts/run_tests.py --lane source --per-file --output /tmp/scid-source
   python scripts/run_tests.py --lane installed --output /tmp/scid-installed
   python scripts/run_tests.py --lane process --per-file --output /tmp/scid-process
   ```

   详见[测试分层与限额](../tests/README.md)，输出目录必须不存在。
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
