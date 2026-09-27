# 发布流程

简体中文 | [English](RELEASE.md)

<a id="current-status"></a>
## 当前实现与验证状态

当前平台提供通用插件运行时 API、明确的 Root 读取意图与 LocalTrusted 执行。
合同见[当前架构](ARCHITECTURE.zh-CN.md)、[插件 API](PLUGIN_RUNTIME_API.md)和[安全说明](../SECURITY.md)。
LocalTrusted 信任协作式本地 Agent 和宿主用户，不隔离共享控制用户 OS 身份的恶意进程。

当前 Operation ABI 为 23。源码节点 `775b3e8` 与合并节点 `5a90f3f` 的文件树一致。
该源码的审批修复验证记录为：1593 项源码测试通过、70 项其他通道用例排除；地址空间
硬限制 2,000,000,000 字节，进程树观测 RSS 峰值 304,713,728 字节。49 项定向检查
包含真实本地 HTTP 审批路由配合测试执行适配器，以及原故障审批回执的隔离回放。
这些是此前候选的验证事实，本轮文档清理没有重跑它们。原始凭据在源码发布包之外；
本摘要不代替原始凭据，也不证明当前安装已包含该修复。

保留的边界：

- SEC-002 未关闭：LocalTrusted 不隔离共享 UID 的进程。
- 前序真实图证据子链和短 SProcess 初始化不证明完整 Fig.4 研究结果、H0/H1 判定或完整 SDevice 实现有效。
- Root、负责人及助手的 Token 收益没有受控对照证明；助手确实使用不等于总成本下降。
- 源码检查不能替新版本完成安装、进程或真实运行验收。实例归档/恢复须确认写入者停止；真实部署、systemd 和科学接续仍需绑定具体候选验收。
- 架构约束登记中的待复核及已知问题继续保留；删除历史报告不表示关闭这些事项。

每个发布候选按下文选择相关检查，在源码树之外保存 `result.json`、日志及源码身份。

<a id="publication-scope"></a>
## 源码发布范围

`scripts/build_git_release.py` 使用明确的源码、文档和工具 allowlist，包含当前
hermetic 测试树、fixture 包、串行资源运行器、CI 配置及测试导入或启动的脚本。
旧 `test_native_worker_usage.py` 只测试私人历史测量脚本，确认无生产消费者后删除；
没有为隐藏私人依赖而静默排除测试。

过程文档、原始验收输出、重复审查和源码备份已从当前树移除，原文仍保存在 Git 节点
`5a90f3fa33135c8b151a547e2eceed0d102eea95`；可用
`git show 5a90f3f:docs/plans/HISTORY.md` 定位旧记录。此次不改写 Git 历史，也不抹去
未关闭问题。保留的 Fig.4 讨论及其直接引用的两份快照属于研究参考，不随源码发布。

架构、安装和插件文档直接引用本页的状态/范围；发布器复制维护中的正文，删除另一套
文案替换规则。`MANIFEST.sha256` 对生成的发布字节计算哈希。

## 历史兼容断点：2026-09-24

当时引入 Operation ABI 19，当前 ABI 为 23。旧 Task 数据库及带 `task_ref` 的旧 Artifact envelope 不再由 UI 读取；
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
