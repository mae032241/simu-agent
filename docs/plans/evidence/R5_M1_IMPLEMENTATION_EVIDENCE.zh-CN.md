# R5-M1 实现证据

日期：2026-09-01

状态：首轮 FAIL 的 B-1 已返工并通过全新独立复审；M1 完成，仅放行 M2

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

基线账本：`R5_M0_BASELINE_AND_CANDIDATE_LEDGER.zh-CN.md`

## 1. 实现边界

M1 只删除零消费者和重复事实，没有改写默认运行主干，没有增加兼容层、状态、表、Root 工具、
注册表、预检入口或调用入口。

### M1-01：死 Schema 与伪科学状态

已删除：

- `schema/discovery.py`；
- `schema/decision.py`；
- `schema/pdf_excerpt.py`；
- `schema/web_evidence.py`；
- `ScientificReadiness`、`ScientificObjectStatus`、`ScientificClosureStatus` 及其三个内部状态类型。

领域中性测试改为验证仍有真实消费者的开放标识类型，没有建立替代科学状态或固定阶段。

### M1-02：未注册、不可执行的 Worker 工具

已删除：

- `worker_run_analysis` 及输入/组件常量；
- `worker_fetch_web_evidence` 及输入/组件常量；
- `artifact_agent/web_fetch.py`。

网络策略编译负例改用测试插件私有的 `NETWORK_TOOL`，没有给生产包保留别名。当前论文证据资格文档
也已改为说明图证据由插件专用能力拥有，不再声称核心注入任意分析工具。

### M1-03：第二运行投影

已删除：

- `RuntimeOperationProjection`；
- `runtime_operation_projection()`；
- `CompiledCatalog.runtime_projection()`；
- 公共导出。

运行策略测试直接读取唯一 `CompiledOperation.spec`、摘要、权限模板、审查边和审批合同，没有建立
替代投影。

### M1-04：无消费者在线清除

已删除：

- `ArtifactService.purge_registrations()`；
- `SQLiteArtifactRegistry.delete_artifacts()`；
- `ApprovalService.delete_requests()`；
- `ExecutionService.delete_executions()`；
- 仅为这些在线删除存在的临时拆除/恢复只追加触发器辅助函数。

没有预建离线清理器；Artifact、审批和执行默认事实继续只追加。

### M1-05：重复事件与核心审计

按独立 M0 审查要求分三步完成：

1. 先将 `audit.py` 收敛为 CAS、Envelope、父链、幂等绑定和孤儿检测，并增加人工破坏负例；
2. 再删除 `ArtifactEvent`、`artifact_events`、写入、原始 snapshot 和触发器；
3. 最后删除只写不读的 `approval_events`、写入和触发器。

保留事实包括：Artifact Envelope、`artifact_links`、`idempotency_records`、审批请求、
`approval_decisions`、`decision_attempts`、`used_nonces` 和 HumanDecision Artifact。

首轮独立审查发现旧 v1 Artifact 库保留惰性 `artifact_events` 时会被完整 Schema 等值校验拒绝。
返工没有恢复事件责任或增加迁移器：Registry 现在只额外接受形状精确等于旧 v1 的事件表和两条只追加
触发器；该表不读、不写、不删。未知额外表、被删除的当前触发器或其他权威结构漂移继续失败关闭。

## 2. 负向审计证据

新增 `tests/artifact_agent/test_artifact_audit.py`，用独立临时数据库验证：

- 正常 CAS、Envelope、父链和幂等绑定全部通过；
- 删除已登记 CAS 对象同时产生 `payload_integrity` 与 `payload_missing`；
- 额外 CAS 对象出现在 `orphan_digests`，不被静默忽略或删除；
- Envelope 摘要列被篡改产生 `envelope_integrity`；
- 父链接位置被篡改产生 `provenance_journal`；
- 幂等请求摘要被篡改产生 `idempotency_integrity`。
- 带精确旧事件表的 v1 库可以重启，旧 Artifact 可读/可审计，新 Artifact 可登记且旧事件行不变；
- 除精确旧事件对象外的额外表，以及当前权威触发器缺失，仍被拒绝。

孤儿对象本身不证明已登记科学事实损坏，因此进入显式孤儿报告而不自动删除；缺失或错误的已登记
对象使报告失败关闭。

## 3. 净复杂度

| 指标 | M0 | M1 | 变化 |
|---|---:|---:|---:|
| `src/scidiscovery` Python 文件 | 101 | 96 | -5 |
| `src/scidiscovery` 物理行 | 27,260 | 26,116 | -1,144 |
| 插件 Python 文件 | 45 | 45 | 0 |
| 插件物理行 | 22,763 | 22,763 | 0 |
| 生产 Python 合计 | 50,023 | 48,879 | -1,144 |
| Local 新建运行时表 | 20 | 18 | -2 |
| 显式 Hardened 比 Local 额外表 | 1 | 1 | 0 |
| Root 公共工具 | 30 | 30 | 0 |
| 插件定义/组件/Operation | 5/220/46 | 5/220/46 | 0 |
| public/support Operation | 26/20 | 26/20 | 0 |

M1 生产 Python 树摘要为：

```text
f9ee0531df21ff96712dca0ab956e2f18461aa4ef667698d83c3105f3ccd24c7
```

完整五插件编译目录摘要仍为：

```text
4c17c856ba4249d400d8d1455139b2e39588759e16ee1c31e5122b4e97dbb57e
```

这证明删除项没有改变当前可运行 Operation 集合和编译身份。

## 4. 验证结果

在 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2`、串行 pytest 下执行：

```text
pytest -q
208 passed in 63.48s
```

其中包含 8 项新增审计用例。另有：

```text
git diff --check
bash -n deploy/install.sh deploy/reinstall.sh \
  deploy/cleanup_legacy_services.sh deploy/install_ssh_tcad_runner.sh
```

均通过。完整测试覆盖 clean-wheel 插件入口、目录编译、Local/Hardened、Run/current、审批防重放、
Effect、部署和 TCAD 本地闭环；本阶段没有运行实时外部 Agent，也没有声称科学准确率资格。

## 5. 明确未完成

- 三个公开 Agent 集合输出在默认 Local 的不可运行问题仍属于 M2；
- 旧 TransformAdapter 双层、科学语义桥、插件公共组件、可选 transport 和重复治理合同均未修改；
- M1 只有独立实现审查 PASS 后才能放行 M2；该审查不得继承 M0 或 R5-L 的结论。

首轮 FAIL 报告：`../reviews/R5_M1_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`。B-1 返工必须由新的
独立复审者确认关闭，不能由实现者自行改写首轮结论。复审 PASS 报告：
`../reviews/R5_M1_IMPLEMENTATION_INDEPENDENT_REREVIEW.zh-CN.md`。
