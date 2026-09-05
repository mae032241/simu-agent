# PASS — R5-M1 返工后实现独立复审

日期：2026-09-01

结论：**PASS。首轮阻断 B-1 已关闭，M1 通过并放行 M2；M2—M7 均未完成，R5-M 也未完成。**

本复审者未参与 M1 实现和首轮评审。复审绑定到分支 `baseline/8765-codex`、
`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48` 以及复审时完整 dirty worktree。首轮 FAIL 只作为
待关闭问题的定位，不继承其通过项，也不改写其历史结论。除本报告外，复审者未修改生产代码、测试、
计划、证据或其他文档，未运行实时外部 Agent。

## 1. Findings

### 阻断项

无。

### 改进项

无必须在 M1 内返工的改进项。

## 2. B-1 独立复现与关闭判断

### 2.1 新库不再建立事件权威

当前 `storage/migrations/0001_artifacts.sql:3-74` 只建立：

- `artifact_envelopes`；
- `artifact_links`；
- `idempotency_records`；
- 两个当前索引和三张表各自的 update/delete 只追加触发器。

独立初始化临时 Local 运行时实际枚举到 Artifact 库只有上述三表；Approval 库只有
`approval_requests`、`approval_decisions`、`decision_attempts`、`used_nonces`。新库没有
`artifact_events` 或 `approval_events`，Local 通用数据库总表数为 18，与 M1 减二表目标一致。

生产源码中没有 `ArtifactEvent` 类型或事件读写。`SQLiteArtifactRegistry.register()` 在
`storage/sqlite.py:133-270` 只写 Envelope、父链接和幂等记录；原始读取与 audit snapshot 在
`:329-399` 也只读取这三类当前事实。全生产树对 `approval_events` 为零命中。

### 2.2 旧 v1 事件对象只是精确惰性 allowlist

`storage/sqlite.py:30-49` 冻结了旧 v1 `artifact_events` 表和两条只追加触发器的精确形状；它仅在
`:639-649` 的内存期望合同中组成第二个**允许的输入形状**，不会在目标库创建、读取、写入或删除事件。
`:465-475` 只接受当前合同或“当前合同 + 精确旧事件对象”两个值。

这不是第二 schema 运行权威：当前 migration、登记路径、读取路径和 audit 都不消费事件，旧对象也不
参加任何 current、Run、审批或执行判断。生产中没有在线 migration、删表状态机、兼容服务、双写或
事件 DTO。

### 2.3 真实旧 migration 重启探针

复审者直接从 `git show HEAD:src/scidiscovery/artifact_agent/storage/migrations/0001_artifacts.sql` 取得
首轮所指的旧 v1 migration，在独立临时目录执行，而不是以当前新库替代旧库。随后构造旧 Artifact 和
旧事件行，并用当前 `ArtifactService` 重启。结果：

```text
old_v1_restart=PASS
old_read_audit=PASS
new_register=PASS
event_rows_unchanged=PASS
fresh_tables=artifact_envelopes,artifact_links,idempotency_records
```

旧 Artifact 可精确读取，`verify_artifacts()` 通过；同一旧库可登记并读取新 Artifact；登记和 audit
前后旧事件行完全不变。现有回归 `test_artifact_audit.py:183-230` 也覆盖旧行惰性保留、旧对象读取/
审计、新对象登记、未知表和当前触发器缺失。

### 2.4 漂移继续失败关闭

`_schema_contract()` 在 `storage/sqlite.py:654-718` 同时绑定：

- `sqlite_master` 中所有非内部表、索引、视图和触发器的名称、归属和规范化 SQL；
- 每张表的 `table_xinfo`；
- 每张表的 `foreign_key_list`；
- 每个索引的唯一性、来源、partial 标志和 `index_xinfo`；
- `user_version`。

初始化还执行 `foreign_key_check`。独立探针逐项制造下列漂移，全部得到
`RegistryConfigurationError`：

```text
current_table
current_index
current_foreign_key
current_trigger
unknown_table
retired_table
retired_index
retired_trigger
```

因此容忍范围没有从“精确旧对象”扩大成“任意旧表”，当前三张权威表、索引、外键和触发器仍精确
失败关闭。B-1 的可达重启故障已消失，最小返工边界得到遵守。

## 3. M1-01—M1-05 重新核查

| 候选 | 独立结果 | 判定 |
|---|---|---|
| M1-01 死 Schema/周期状态 | 四个 Schema 文件、`ScientificReadiness`、`ScientificObjectStatus`、`ScientificClosureStatus` 均不在生产树；没有替代固定阶段或科学状态 | 通过 |
| M1-02 僵尸 web/analysis 工具 | `worker_run_analysis`、`worker_fetch_web_evidence`、相关组件常量和 `web_fetch.py` 在生产零命中；当前说明明确旧通用工具已退出，插件专用图证据能力没有被冒充为核心别名 | 通过 |
| M1-03 第二运行投影 | `RuntimeOperationProjection`、`runtime_operation_projection()`、`CompiledCatalog.runtime_projection()` 均消失；`CompiledCatalog.__slots__` 只有唯一 operation/runtime-plugin 编译事实，调度器只保留 `SchedulerOperationView` | 通过 |
| M1-04 在线清除 | `purge_registrations`、`delete_artifacts`、`delete_requests`、`delete_executions` 及针对权威表的在线 DELETE/临时拆触发器路径均为零命中；未出现离线清理器、别名或转发器 | 通过 |
| M1-05 事件与 audit | 新库不建/不写两事件表；旧 Artifact 事件对象精确惰性保留；`audit.py:57-273` 仍检查 CAS、Envelope、父链、幂等绑定、缺失内容和孤儿布局；旧库重启缺陷已关闭 | 通过 |

人工损坏回归继续覆盖：缺失 CAS、孤儿 CAS、Envelope 列损坏、父链接位置损坏和幂等请求哈希损坏。
孤儿只报告、不自动删除；已登记对象的缺失或损坏使报告失败关闭。

## 4. 目录、复杂度与承重边界

独立复算结果：

| 指标 | 当前结果 |
|---|---:|
| `src/scidiscovery` Python | 96 文件 / 26,116 行 |
| `plugins` Python | 45 文件 / 22,763 行 |
| 生产 Python 合计 | 141 文件 / 48,879 行 |
| 生产树摘要 | `f9ee0531df21ff96712dca0ab956e2f18461aa4ef667698d83c3105f3ccd24c7` |
| 插件/组件/Operation | 5 / 220 / 46 |
| public/support | 26 / 20 |
| Agent/Transform/Approval/Effect | 22 / 20 / 3 / 1 |
| 完整目录摘要 | `4c17c856ba4249d400d8d1455139b2e39588759e16ee1c31e5122b4e97dbb57e` |
| Root 公共工具 | Local 30 / Hardened 30 |
| Local 新建通用表 | 18 |

目录摘要与 M0 一致，M1 没有改变 Operation 集合或编译身份。Local 公开 Agent 仍为 19/22 可运行，
三项仍只因 `agent_collection_outputs` 在 Run 前拒绝；这是 M2 的公开能力问题，不能在 M1 伪装成完成。
Hardened 公开 Agent 仍为 0/22，可选后端边界没有被 M1 重写。

承重边界的重新核查结果：

- Root 仍只有同一 `ROOT_TOOLS` 30 项，Local/Hardened 返回同一集合；
- Run 数据库仍只允许 `queued/running/completed/failed` 四态；
- ResearchInstance、会话绑定、递归 current 和 compare-and-set 仍由控制面唯一持久化；
- 审批仍绑定精确 subject/nonce/HumanDecision，聊天不构成决定，科学资格与执行授权仍分离；
- Execution 的 create/authorize/submit/domain status/collect 和 unknown 查回边界没有变化；
- Worker 内建只有生命周期工具，其他 PDF/文件工具仍须由精确 `OperationSpec` 组件显式授权；assignment
  不暴露 Run、Artifact、Approval、session、token、数据库或 current 控制身份；
- 仍只有 `scidiscovery.plugins` 入口组、一个 `CompiledCatalog`、一个 preflight 和一个 invoke；
  core 没有恢复 TCAD、曲线、Schema、角色或插件名分支。

没有发现新增 Registry、运行状态、表、Root 工具、守护进程、兼容 adapter、第二 preflight/invoke 或
领域运行实体。精确旧事件 allowlist 只保护已有 v1 库重启，不恢复事件责任，符合 M1 的奥卡姆门。

## 5. 33 项约束

独立解析 `SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 得到 33 个唯一 id；结构测试通过。逐组复核
AUTH、IMM、LIN、EVD、UNC、TOP、ROLE、DET、HIL、CQRS、EFF、PLG、SEC、RES、UI、MIG 后，没有
发现 M1 删除或 B-1 返工使现有证据降级，也没有发现状态被无证据晋级。

特别地：

- B-1 关闭了旧 v1 库重启的 MIG-002 阶段阻断，但 `MIG-002` 仍保持 `pending_review`，没有被本报告
  提升为全面发布资格；
- `SEC-002` 仍为 `known_issue`，Local `spawn_agent` 的原生工具隔离仍只是提示约束；
- 其余 `pending_review` 也继续保持，工程测试数量不等于科学资格或最终架构总审查。

## 6. 独立执行证据

所有 pytest 均串行执行，设置 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2`，未使用 pytest 并行。

1. `python -m pytest -q tests/artifact_agent/test_artifact_audit.py`：**8 passed in 0.67s**。
2. 真实 `HEAD` 旧 v1 migration 探针：旧库重启、旧读取/audit、新登记、事件不变和八类 schema
   漂移正反例全部通过。
3. 69 函数跨边界集合：**69 passed in 51.92s**。集合覆盖 33 项结构、唯一目录/安装 entry point、
   Local Run/current、崩溃与恢复、独立审查/人工决定、Effect 与执行审批身份、TCAD 本地闭环、
   Hardened 围栏、平台最小 Worker 上下文和插件领域边界。
4. 生产规模、五插件目录摘要、Root 工具、Local 表清单、Local/Hardened 能力和 33 项状态均用独立
   临时进程复算。
5. `git diff --check`：通过。
6. `bash -n deploy/install.sh deploy/reinstall.sh deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh`：通过。

实现证据记录的全量结果为 `208 passed in 63.48s`；本复审不把该供应记录冒充独立观测，也没有重复
全量集合。独立 PASS 建立在上述 B-1 真实旧库探针、8 项直接 audit 回归、69 项跨边界集合和源码/
目录/表面逐项核查上。

主要输入与返工对象的复审时 SHA-256：

```text
da5d131c7cc57bcd0d82cfd8a6a040eab595dc7941076f9c1733c81286ed9ecd  R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md
7ce1d20f9533180eff076ce41bdb8915a1a47ed01170e805961254d00bfad5ac  R5_M0_BASELINE_AND_CANDIDATE_LEDGER.zh-CN.md
07387fd18d2751c53cec9b21a59da9ef56f08cb84436e28db03b5d285025378f  R5_M1_IMPLEMENTATION_EVIDENCE.zh-CN.md
434443630fc31bef112dd887f5acdb537c0a941c020806ddaec64739b2a93979  R5_M0_BASELINE_AND_CANDIDATE_LEDGER_INDEPENDENT_REVIEW.zh-CN.md
a6dcefa9d61a6d0f495796f88f72d5b15eae3ebdb9f0c72119b39d299dfcc55a  R5_M1_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md
e9553531915216b4f679bcd3cd98aa8073e20b5f498e580e883b4388004179ed  storage/sqlite.py
23c5f300a8702598415dd68178daddfdd09e87ac1f5b80096fc28a310857c286  storage/migrations/0001_artifacts.sql
e24df400283ea0594a59b4f7037b48e6c1e1aaa1356603c9a2945671a595a196  test_artifact_audit.py
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
```

## 7. 未验证范围

- 按 M1 要求未运行实时外部 Agent；没有运行真实浏览器、远程 SSH/VM 或 Sentaurus solver。
- 没有宣称论文图数字化、参数来源或曲线诊断的科学准确率资格。
- 三个公开 Agent 集合输出、旧 TransformAdapter、科学语义桥、插件归位/可选化和治理合同分别属于
  M2—M6，仍须后续实现与独立审查。
- 真实机器发布升级仍是 MIG-002 的后续门；本次只证明精确旧 v1 Artifact 库在当前代码下可重启和
  继续登记，不将其扩大为所有历史/未来数据库形状兼容承诺。

## 8. 最终判定

**PASS：B-1 已按首轮要求最小关闭，M1-01—M1-05 全部通过，M1 放行 M2。**

本结论仅表示 M1 阶段门通过。**M2—M7 均未完成，R5-M 未完成。**
