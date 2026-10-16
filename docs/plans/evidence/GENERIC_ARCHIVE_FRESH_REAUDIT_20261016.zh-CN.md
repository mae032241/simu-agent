# 通用平台归档新审查者复审（2026-10-16）

结论：**发现剩余功能缺陷，不能延用原 F2 PASS 作为实际实验入口已通过的证据。** 已证明的缺陷不涉及越权或原件丢失，按 P2 记录。审查者未参与被审实现，未修改生产代码、未提交，也未启动模型或 solver。

## 范围与基线

仓库为 `123/scidiscovery-e5.2`，分支 `dev`，精确 HEAD 为 `53798e9798f6634bd2b62ecedb2bc03e742a7411`。重点审查 `da7d891848bcc0d4a0617095600c36380bebfa8a`，对照其前置 `727f5372549148fa2c0f40c51c5bd74692478954` 的通用候选/目录交付，以及 HEAD 非 local 执行观察原件变化。保留原有未跟踪证据目录，唯一仓库写入是本报告。

使用 `scid-cross-boundary-review`、`scid-change-scope-checks` 与 `karpathy-guidelines`。先读适用 AGENTS，再读实际 producer、runtime factory、归档 provider、核心迁移与恢复代码；原实现和复审报告用于定位已有主张，没有把它们的 PASS 当作独立验证。

## F2-R1 / P2：正常实验调试私有工作目录再次全局阻断归档

**最小位置：** `plugins/tcad_artifact/tcad_artifact/debug_archive.py:148`。该处要求调试根下除 `budgets` 外的每个顶层目录，均是从 reservation submission 推导出的 32 位 hex exchange 目录；真实实验工具生成的 `experiment-workspaces` 永远不在这个集合中。

**可达路径：** TCAD `experiment_capability.debug()` 在行 125 无条件调用 `execution.diagnostic_context()`；后者在 `src/scidiscovery/artifact_agent/service/experiment_execution.py:953`—959 把工作目录放在 `service.exchange_root / "experiment-workspaces" / task_origin`，并立即创建它。随后 `LocalTCADDebugService.run()` 在同一根下生成预算 ledger、提交 exchange 和收集 receipt。这是当前正常的实验调试路径，成功完成也不会删除该私有工作目录。

reader 没有解释该正常 producer 产物的归属，而是抛出 `debug_unowned_exchange`，再统一转换为 `debug_ownership_or_writer_unconfirmed`。`Files.collect()` 在每个实例的预览中调用这个 reader，因此 B 已正常收集完成的调试也阻断没有 Run 的 A。影响包含使用其他插件的无关实例；不是仅有未知、损坏或活动 writer 才触发。

**独立行为证据：** 使用生产 `_TaskExperimentTools.diagnostic_context()` 和真实 `LocalTCADDebugService`，复用已有无 solver adapter fixture，执行一次提交、一次收集。B ledger 最终确为 `collected`；B 的控制 Run 为终态，A 没有任何 Run。预览 A 使用未替换的生产 `InstanceArchive`，不使用 `SynchronousFixtureArchive`，结果为：

```json
{
  "a_ready": false,
  "a_unsupported": [{
    "code": "plugin_storage_unavailable",
    "provider": "tcad_artifact:debug",
    "reason": "debug_ownership_or_writer_unconfirmed"
  }],
  "ledger_state": "collected",
  "submits": 1,
  "collections": 1,
  "preview_preserved_bytes": true
}
```

对照操作仅把 `experiment-workspaces` 移到调试根外，预算、receipt、exchange 原字节完全不变；A 的生产预览立即 `ready=true`，B 自身 reader 也从 unsupported 变为正常返回四个原件路径。因此拒绝由正常工作目录形状触发，不能归因于损坏 receipt、目标 native writer、没有完成收集或目录归属混合。

此 probe 没有启动完整 MCP Worker/真实 TCAD adapter。handler 到该目录创建的连接由源码证明；目录创建、实际诊断收集、provider 拒绝及生产预览拒绝由行为证明。B 的终态控制行由现有测试辅助函数构造，未将它解释为真实 native Worker 静止证明。

**现有测试缺口：** `tests/operations/test_instance_archive_debug_storage.py:163`—186 的“真实 debug service”用例直接调用 `debugger.run()`，用 fixture 自己的工作目录，绕过 `experiment_capability.debug()` 和 `diagnostic_context()`。其他归档正控多数使用同步归档 fixture。101 个最终通过用例因此没有覆盖这个必经 producer 目录。

**最小建议：** 为 `experiment-workspaces/<task_origin>` 建立控制事实支持的 Run/instance 归属投影，将当前实例确切拥有的完整私有目录纳入迁移，保留其他实例目录；未知身份继续拒绝。不能仅忽略整个目录，否则目标私有原件会漏档。增加包含真实 `diagnostic_context()` 的跨实例正控：B 调试 collected 后 A 可归档；同步可验证的 B 自身归档/恢复还要保留该目录，重新归档时不产生孤儿目录。

## F2-R2 / P2：零原件 provider 根造成无关插件恢复依赖

**最小位置：** `src/scidiscovery/artifact_agent/service/instance_archive.py:622`—629，结合 `instance_archive_files.py:77`—96、329。`roots()` 把所有已配置 provider 根加入快照；无论该 provider 是否贡献文件，`_restore_validation()` 都要求每个归档 root 在当前 provider 配置中存在并相同。

这样，配置 TCAD 时归档的纯通用实例，即便没有任何 TCAD Run、Execution、plugin-owned 文件，甚至 TCAD 调试根从未存在，关闭 TCAD provider 配置也会收到 `restore requires the original configured roots and backend`。在恢复复制和数据库 switch 中，该 provider 不拥有任何待恢复对象；必要的基础根、后端、schema、CAS 与记录验证本可独立完成。这个要求扩大了可选插件的恢复权限范围。

**独立行为证据：** 第二个 probe 全程使用生产 `InstanceArchive`，实例只绑定普通 CAS artifact，`run_ids=[]`、`execution_ids=[]`、`plugin_files=[]`，debug 根始终未创建。启用 TCAD provider 配置完成归档后，仅清空 `archive.plugin_configs`，恢复预览即拒绝；重新提供相同配置便可恢复。随后保持 provider 关闭再次归档、恢复，两次恢复读出的 CAS 字节均为原文 `generic original, no TCAD input or execution`。除 provider 声明外，没有改变根、后端、schema、数据或待恢复对象。这个反例证明此依赖来自空 root 声明，而不是恢复实际领域原件所必需。

这与确有 plugin-owned 原件时拒绝缺失 provider 是两种情形；后者应保留。最小修复应依据归档中实际 plugin-owned 文件及明确的 provider 元数据确定所需 provider，继续对实际恢复对象检查原 root，不能整体删除根身份验证。

## 已追踪的边界与限制

| 边界 | 本次证据与判断 |
| --- | --- |
| runtime 装配和部署入口 | `runtime_plugin.py` 的 builder 声明固定 debug 根；`load_archive_storage()` 不执行 runtime build；CLI `serve-approval-ui` 将 plugin configs 传入生产归档服务；安装脚本配置相同参数。未做新 wheel 安装或真实 UI 会话。 |
| 预算和实例所有权 | 正常调试预算由控制实例身份计算，reader 要求 ledger key 与其所有 Run 的真实 instance 一致。不同实例不共享同一正常调试预算文件；同实例多个任务复用同一额度，整份 ledger 迁移不拆分、不重置。 |
| ledger / receipt | reader 验证现行 schema、record identity、reservation、submission、collected state、receipt 身份和文件摘要。坏/旧 ledger、未知 Run、混合归属、缺锁和未知残留均保守拒绝。没有重复运行原来的参数化测试。 |
| 活动 writer / lock inode | reader 在原预算锁上取非阻塞 SH；真实 Local Worker 工具调用整个期间持 global/instance maintenance guard；freeze/switch 取同一 instance EX 并保留 durable marker。归档副本与恢复后的锁是新 inode，但正常同实例 writer 被 marker 阻断，未证明该正常入口存在 inode 绕过。绕过平台协议的任意 native 写者不在保证内。 |
| freeze → copy → switch → cleanup | 源文件 stat 和目录 inventory 在关键 switch 前再验，复制验证摘要；控制库 ReadTicket 防止扫描期间提交改变选择；清理不递归删除未枚举内容。plugin 路径仍经过公共规范路径、root 不重叠、symlink 和文件类型检查。未发现额外可达数据损失或越权。 |
| restore → 再归档 | 真实有文件 provider 的缺失/root 改变会拒绝；原控制记录和预算原字节作为快照恢复。R1 阻止真实调试入口走到该阶段，不能把同步形状正控当作真实入口已通过。R2 的生产无 Run/通用 CAS 路径另行验证。 |
| native Worker 静止 | `instance_maintenance.backend_writer_guards()` 行 306—325 对现有终态 Run 仍要求 native writer/backend quiescence，当前实现没有通过分支；这是已有保守拒绝，未由本改动放宽。同步 fixture 的归档/恢复不能证明生产 native Worker 可归档。 |
| 缺失整个 debug 根 | provider 对不存在的根返回空选择；若历史 ledger/receipt 已被外部删除，本接口没有持久的预期 inventory 可判定曾经存在。不能把这种 empty selection 当作历史预算/原件完整性证明；本次未把任意外部删根演示为新增缺陷。 |
| 非 local 原件 / 通用目录交付 | `record_observation()` 将非 local adapter proofs/outputs 留存到调用目录的 observed-originals；通用交付使用已封存 history 原件，将 bundle 写入显式目标目录。该研究循环根及交付目标不是本次 instance archive 新增的插件根；不能宣称 instance archive 会搬运所有外部目标/remote VM 原字节。未扩展到尚未支持的 rootless-MCP 融合，也未重做另一审查者的执行/交付审查。 |
| 查询副作用 | factory archive builder 仅验证配置、构造声明；budget/receipt reader 不启动适配器、不查询 solver、不调 reconciliation。R1 probe 对预览前后所有 debug 文件内容摘要核对相同；没有将只读宣称扩大到文件系统 atime 或任意第三方 provider。 |

## 实际运行证据

所有 probe 使用仓库 `scripts.run_tests.serial_lock()` 与 `run_one()`、默认资源阈值；与其他审查者协调串行，不并发测试。

| 验证 | 结果 |
| --- | --- |
| `git diff --check 727f537..HEAD` | 通过。 |
| `/tmp/scid-archive-fresh-supervise-20261016.py` 首次输入 | 退出 1，2.091 秒，cleanup=true。审查脚本误用含额外下划线的 Run ID，后端在测试行构造时拒绝；没有得出产品结论。保留 `/tmp/scid-archive-fresh-probe-20261016/pytest.log`。 |
| 同脚本修正合法 Run ID，R1 精确 probe | 退出 0，1.786 秒，tree RSS 高水位 114565120 bytes，cleanup=true，无资源触发。原件见 `/tmp/scid-archive-fresh-probe2-20261016/{result.json,pytest.log,resource.json}`。 |
| `/tmp/scid-archive-empty-provider-supervise-20261016.py`，R2 与再次归档/恢复对照 | 退出 0，2.627 秒，tree RSS 高水位 117157888 bytes，cleanup=true，无资源触发。原件见 `/tmp/scid-archive-empty-provider-probe-20261016/{result.json,pytest.log,resource.json}`。 |

可重放脚本为 `/tmp/scid-archive-fresh-repro-20261016.py` 与 `/tmp/scid-archive-empty-provider-repro-20261016.py`；前者调用生产目录创建/诊断服务/预览，并将 handler 未识别目录移出根作因果对照，后者执行完整真实 archive/restore/再 archive/restore。未运行全套回归、模型、solver、真实 daemon/browser、独立 wheel、跨主机恢复或任意原生写者压力测试。原 101 个用例只是历史证据，本报告没有重新运行或另计为本次通过数。

收尾再次确认 HEAD 未变，`git diff --check` 通过。未修改任何生产或测试文件，未删除或回退他人改动。
