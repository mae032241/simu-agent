# F2 修复：按原实例归属处理 TCAD 诊断归档

日期：2026-10-16。基线 `dev@727f5372549148fa2c0f40c51c5bd74692478954`。本记录仅覆盖 F2；同时工作树的非本地执行终态 F1 由另一执行者负责，不在本记录的提交文件清单中。未提交或推送 Git。

## 1. 结果与最小设计

原行为是任何非空 `local-tcad-debug` 都让任意实例归档 `ready=false`。现在由已有 runtime factory 的可选只读 `archive_storage` builder 提供领域状态归属；核心复用 `Files.add`、快照指纹、既有 maintenance gate、复制/清理和 restore，不引入新注册表、预算账本或科学字段。

TCAD 的只读 reader 验证预算文件的现行 schema、record key、Run 的实际 instance、实例预算 key、原 submission 和已收集 receipt。目标实例的预算、锁、准备目录和 receipt 作为完整原件选入既有 inventory。其他实例的状态保留原位，并明确报告 `unselected_plugin_state_retained`；已知其他实例正在运行的诊断也不获得目标实例所有权。

目标调用必须已经 `collected`，且 submission 内容摘要、receipt 的 Run/name/submission/response 和保留文件内容一致。活动、未知、未收集终态、缺锁、锁被写者占用、混合归属、坏原件、未知残留或歧义均保守拒绝。不会调用 solver、查询外部状态或用新提交替代恢复。

归档 provider 的装配只读配置，既不实例化 executor/Worker service，也不创建调试目录。未安装/未配置 provider 但存在历史 TCAD 调试残留时，原来的 explicit unsupported 守卫仍保留。旧 archive 没有新增 plugin roots 仍可用原基线 roots 验证；含 plugin root 的新 archive 恢复时必须有同一个 provider/root，缺 provider 不会静默跳过原件。

## 2. 写者与锁边界

既有 MCP Local Worker 的 `_maintenance_call` 在 tool 期间持有 global 与目标 instance guard；archive freeze/switch 使用同一维护互斥与持久 marker。reader 非阻塞取得原 budget lock 进行读取，且要求目标诊断已收集完成，避免把 tool 返回/锁释放误当成后台任务结束。快照后的控制记录/原文件变化仍使原 preview 失效或阻断切换。

原有框架关于 shared 锁文件的策略没有更改。新增 provider 明确选中的目标 budget lock 是实例独占原件，随 ledger 一起迁移，避免留下没有 ledger 的孤立锁重新阻断其他实例。其他实例的锁与字节原位保留。

这依赖受控 MCP writer 的 guard 和持久维护 marker，不宣称证明绕过该协议的任意原生写者已经静止。原生产 `backend_writer_guards` 对 native writer 的保守限制完整保留。格式/迁移正控使用既有 `SynchronousFixtureArchive` 的同步 fixture 约定；没有把它当作真实 native Worker 归档资格。

## 3. 无模型受管验证

所有测试都由 `scripts/run_tests.py` 的 `serial_lock/run_one` 监督，无模型、无 solver、无全量回归。`git diff --check` 通过。

| 批次 | 结果与证据 |
| --- | --- |
| `/tmp/scid-debug-archive-f2-01` | 初版夹具 Run ID 含额外下划线，13 failed/5 passed；后端在构造阶段拒绝非法 ID。只修夹具为合法 Run ID。 |
| `/tmp/scid-debug-archive-f2-02` | 新增首批18项全部通过，8.30秒；监督8.756秒，采样 tree RSS高水位123,830,272 bytes，cleanup完成。 |
| `/tmp/scid-debug-archive-f2-final-source` | 新增21项、现有 archive、runtime plugin configuration、debug task identity 四文件：96 passed/5 failed/3 deselected，49.09秒；采样RSS153,935,872 bytes，cleanup完成。5个失败是下节列出的已有夹具前提失配。 |
| `/tmp/scid-debug-archive-f2-final-recheck` | 新增21项及修正后的原失败5项：26 passed，12.44秒；监督12.869秒，采样RSS131,858,432 bytes，cleanup完成。 |

每批 `batch-001/pytest.log` 与 `resource.json` 保留完整输出/资源证据。最终 production 改动与上一批相同；最终复核只额外修正原归档测试的两处夹具前提。因此该定向集合总计101个唯一用例最终通过，不能把两批通过数直接相加当作127个唯一用例。

新增21项覆盖：B已完成/已知运行中诊断不被A迁移；A自身状态归档/恢复的预算和receipt字节不变；A归档后B仍可归档；目标accepted/running/failed/succeeded但未收集时拒绝；目标budget锁占用时preview和archive均拒绝；preview后预算变化失效；扫描后受控writer guard使freeze拒绝；坏归属/坏receipt/未知旧目录/符号链接/缺锁拒绝；无provider残留拒绝；restore缺provider拒绝；核心拒绝越界路径、链接和重叠root；生产 `LocalTCADDebugService` 在无solver adapter fixture下生成的原ledger/receipt适配reader，读取不改字节。

未运行 installed wheel、真实 daemon/browser、跨主机重启、真实 TCAD 或 native Worker 场。这些结果证明边界行为和同步原件迁移，不构成其生产资格。

## 4. 旧失败与当前入口覆盖映射

为了不把新回归误归为旧问题，核对了精确 HEAD `727f537` 的源码：

- 原 `test_instance_archive.py:128` 在四种 client presence 情况调用 scheduler `run_status(output_paths=[])`。HEAD 的 `interfaces/mcp_root.py:266` 定义的 `SchedulerRunStatusInput` 已没有 `output_paths`，字段只属于紧邻上方的另一种 RunStatusInput。删除该不合法参数，保留同一 facade、同一 queued/running 状态断言以及归档 `run_nonterminal` 拒绝断言；最终四种 presence 均通过。
- 原 `test_instance_archive.py:347` 在 `backend.prepare` 后再次无条件创建 scratch。HEAD 的 `local_workspace.py:165`–`:178` 已读取 capture roots并建立目录；`:27`–`:41` 默认 root 是 `scratch/artifacts`，所以 prepare已建立 scratch。改为 `mkdir(exist_ok=True)`，保留写入原草稿、隔离workspace、shared recovery保留、归档恢复后原字节和activity/预算事实不变的所有后续断言；最终该恢复用例通过。

这两处只修现行测试输入，没有放宽生产 Schema、归档检查或 writer quiescence。

## 5. F2 专属文件与冻结摘要

以下7个生产文件、2个测试文件及本报告属于F2。其他 execution/history/worker_delivery/contracts 改动属于F1，不应混入F2提交。

| 文件 | SHA-256 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/debug_archive.py`（新增） | `6cde5f5c1d1fb2d8e07ca769e17d4a752c6979d8db133b9c458d083da51d7f8c` |
| `plugins/tcad_artifact/tcad_artifact/plugin.py` | `a088e6e2eafba5488a1152186a7d8221c8799bc636b6f974f787b9a8db67267d` |
| `plugins/tcad_artifact/tcad_artifact/runtime_plugin.py` | `41c99f596fac69c05dbd9f87113e0b411f6e78a659a3e1b3ae1c2f9b6c3ecd9d` |
| `src/scidiscovery/artifact_agent/runtime_plugin_bindings.py` | `0303d024ed2218ac18728cdb7bd9b7fb33e6eff6f8b67ff760627c475fa14ac9` |
| `src/scidiscovery/artifact_agent/service/instance_archive.py` | `8768cb8c48164c3e9ba42ac41769df1559bbd10040d7afb2ec9900971853281e` |
| `src/scidiscovery/artifact_agent/service/instance_archive_files.py` | `9c18cf233c9a5ac7426cc1fce47f71804727fa9da935f81e12f6353748928bba` |
| `src/scidiscovery/operations/runtime_plugins.py` | `44c109354bf5723b22380d52b6e5049454d91e802b8b7abf802d3755c29071eb` |
| `tests/operations/test_instance_archive.py` | `7420b77a1346542f9ffc7cab9f644d922bdf05c12cec6fe759a3d42733a85c7b` |
| `tests/operations/test_instance_archive_debug_storage.py`（新增） | `003bff3da62de50f64853fad526275300ff7c550f5eaed9c50e55287dae4bfc7` |

runtime factory 的声明 identity 升为 `tcad.runtime-factory.v4:scoped-debug-archive`。历史已封存结果仍是原件；不自动重写旧 ledger 或重置额度。未知旧数据需要有证据的恢复/维护，本修复不猜归属、不按mtime选取、不删除残留来制造ready。

状态：实现与定向验证完成，等待独立审查；未声称独审通过。
