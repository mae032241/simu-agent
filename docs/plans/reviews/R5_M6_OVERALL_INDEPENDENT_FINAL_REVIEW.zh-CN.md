# R5-M6 重复治理合同整体独立终审

- 日期：2026-09-02
- 审查对象：当前工作树组合字节；基准提交 `404aeb14c6ebc4b08bac599db91eaee54c103f48` 仅用于定位，M6 基线数取自冻结的 R5-M0/M2 证据
- 审查身份：未参与 M6 实现、M6-A—D 局部审查或返工的全新普通代码审查者
- 最终结论：**FAIL**
- 放行判断：**不放行 M7；不宣称 M7 或 R5-M 完成**
- 缺陷计数：**2 项阻断，0 项新增非阻断缺陷**

## 1. 结论先行

M6-A—D 的局部 PASS 不能组合成整体 PASS。当前组合字节存在两个完成门级阻断：

1. Effect 的 `ExecutionService.create()` 提交与 Execution 语义绑定之间仍有崩溃窗口。相同完整
   `operation_invoke` 每次重试都可创建一个新的随机 Execution 和 ExecutionRequest Artifact，形成无界、
   无语义 binding 的权威孤儿状态；M6-D 修复的是后一个 Approval 创建/绑定窗口，没有覆盖前一个
   Execution 创建/绑定窗口。
2. `approval_status`、审批列表/loopback dashboard GET 和 `execution_status` 仍会写数据库、轮换访问令牌
   或发布结果 binding。它们直接违反 M6-D 的“查询不推进审批或执行状态”和 `CQRS-001` 的明文合同。

两项都是可独立复现的当前代码事实，不是文档瑕疵、测试覆盖建议或 M7 才需验证的远端能力，因此按 M6
自动停止规则必须 FAIL。现有 `R5_M6_OVERALL_CLOSURE_EVIDENCE.zh-CN.md` 的复杂度数字可复算且正确，
但其“各一个权威”“查询仍不写状态”两个结论候选不成立。

## 2. 阻断发现

### B1 — Effect 的 Execution 创建/绑定窗口会为同一请求累积权威孤儿

**严重性：阻断。** 影响 `AUTH-001`、`IMM-002`、`CQRS-002`、`RES-002`，并使 M6 的
Execution 单一权威、完整请求幂等和故障恢复完成门失败。

当前调用顺序是：

1. `mcp_root_execution_routes.py:147-164` 计算完整指纹并发现语义名尚无 binding；
2. `mcp_root_execution_routes.py:165-173` 先调用 `ExecutionService.create()`，再调用
   `_bind_target("execution", ...)`；
3. `executions.py:84-133` 的 `create()` 每次生成随机 `exe_<uuid>`，先登记新的 ExecutionRequest
   Artifact，再提交新的 `executions` 行；API 不接收语义指纹或稳定 execution id；
4. 若第 2 步的 binding 抛错，已提交的 Execution 不会回滚，下一次相同 invoke 因仍无 binding 而再次
   进入随机创建路径。

本审查在真实 Root facade、当前编译 architecture fixture Effect 上，将 Execution namespace 的
`_bind_target` 连续三次注入失败，再以完全相同的语义名、Operation 和输入重试。结果为：

```text
{'faults': 3,
 'execution_rows_after_faults': 3,
 'execution_rows_after_recovery': 4,
 'distinct_execution_ids': 4,
 'bound_execution_is_new_fourth': True,
 'orphan_created_rows': 3,
 'approval_rows': 1,
 'returned_state': 'created'}
```

前三个 Execution 均保留为 `created`，没有 Execution binding；第四个才被绑定并建立一个 Approval。
每多失败一次即可再增加一个 Execution 行和 ExecutionRequest Artifact，数量没有固定上限。锁只能避免
进程内并发，不能消除已提交后的进程崩溃或异常窗口。

现有 `test_effect_approval_recovers_one_request_after_binding_failure` 只在 Execution 已成功绑定后注入
Approval binding 失败；稳定的 `apr_<execution_id>` 正确关闭了该较晚窗口，却没有覆盖本项较早窗口。
因此把 M6-D 的局部恢复 PASS 外推为整条 Effect 创建链幂等是不成立的。

**最小关闭条件：**

- 让同一完整 Effect 请求在 Execution 创建提交后、语义绑定前重放时取回同一个 Execution；稳定身份或
  幂等键必须由现有完整请求指纹/不可变调用身份推出，不能再由随机 UUID 决定；
- 不增加恢复表、outbox、第二 registry、公共补偿工具或后台清理状态机；
- 增加精确回归：在 Execution 行和 request Artifact 已提交、Execution binding 尚未提交处连续多次
  失败，重试后断言始终只有一个 Execution、一个 ExecutionRequest、一个最终 Approval、同一个对象
  被绑定且 adapter submit 次数为零；
- 若该代码曾对持久状态开放，还需给出存量无 binding Execution 的有界审计与 fail-closed 处置证据，
  不能靠查询时静默收养任意孤儿。

### B2 — status/list/页面 GET 仍在推进审批、令牌和结果发布状态

**严重性：阻断。** 直接违反 `CQRS-001`；其中审批过期和结果发布还破坏 `CQRS-002` 的显式命令边界。
该项有三个同根表现：

1. `ApprovalService.status()` 在 `approvals.py:283-298` 先调用 `_expire_if_needed()`；后者在
   `approvals.py:961-981` 执行 `BEGIN IMMEDIATE` 并把 `pending` 写成 `expired`。Root
   `approval_status` 在 `mcp_root_approval_routes.py:10-36` 直接走该路径。
2. `ApprovalService.list_requests()` 在 `approvals.py:368-431` 对 pending 项调用
   `_refresh_expired_access()`；`approvals.py:476-512` 会轮换 access token、CSRF token 和访问过期时间。
   loopback dashboard 的 `GET /` 在 `approval_ui/app.py:139-152` 调用这个列表。
3. Root `execution_status()` 在 `mcp_root_execution_routes.py:436-449` 看到 `result_ref` 后调用 `_bind()`
   创建 `<execution>.result` Artifact binding；`execution_list()` 又逐项调用 `execution_status()`。

独立数据库前后摘要探针得到：

```text
{'approval_status_before_query': 'pending',
 'approval_status_after_query': 'expired',
 'approval_root_result': 'expired',
 'result_bindings_before_execution_status': 0,
 'result_bindings_after_execution_status': 1,
 'execution_result_artifact_name': 'query_execution.result'}
```

真实 loopback dashboard GET 的令牌探针得到：

```text
{'status_unchanged': True,
 'access_token_rotated_by_get': True,
 'csrf_rotated_by_get': True,
 'access_expiry_changed_by_get': True}
```

M6-D 的自动 execution approval 默认不设业务 expiry，只能说明该单一路径不会触发第一种写入，不能
证明整个 Approval/Root 查询边界纯读。当前 33 项约束的 `CQRS-001` 明确禁止“查询写数据库、轮换令牌、
发布输出，或因时间经过在读路径落库状态”，上述三个行为逐字命中禁止项。

**最小关闭条件：**

- `status`、`list`、`readiness` 与所有页面 GET 对持久库摘要纯读；过期可作为读视图计算，但持久化过期
  必须由显式、幂等、CAS 命令或 reconcile 完成；
- 访问令牌刷新改成显式且受 CSRF/能力约束的命令，不得由 dashboard GET 或 list 隐式执行；
- Execution 结果 binding 在 `execution_sync`/collect 的显式幂等命令边界完成，`execution_status/list`
  只投影已经存在的事实；
- 增加查询前后数据库摘要回归，至少覆盖过期 Approval、过期 UI 访问令牌、已收集但尚无语义结果 binding
  的 Execution，以及 Root list/status 和 loopback GET；不得只断言返回 JSON。

## 3. M6 组合完成门

| 完成门 | 独立终审事实 | 判定 |
|---|---|---|
| Artifact、Run、current、Approval、Execution 各一个权威 | Artifact、Run、current 和 Approval 的结构 owner 未见第二 registry；但 B1 使同一完整请求产生多个权威 Execution/Request 且留下隐藏孤儿 | **FAIL** |
| 普通探索零 cohort/approval/execution 成本 | 无 `input_admission` 的普通 Agent/Transform 不查询资格、不建 Approval/Execution；explore/internal 标签仍不能充当 claim | PASS |
| 未绑定实例只能经精确显式用户入口创建/选择 | `instance_current` 未绑定时只发短期 AEAD loopback capability；创建/选择只由 loopback POST 进入单事务 session binding；Root、聊天、Agent、Worker 无创建/选择工具 | PASS |
| `InputAdmissionSpec` 是唯一 all-or-none/资格合同 | `preflight_operation` 在 guard 前按 `member_ports` 拒绝部分组；Root 只查询同一合同；`allowed_port_sets`、`_PARAMETER_COHORT_PORTS` 和端口资格四字段均不在生产路径 | PASS |
| producer 未来用途字段/图消失，consumer-only 扩展闭合 | `allowed_input_usages` 与替代全局用途图均无生产命中；精确 producer/reviewer/revision/change-request 与下游 usage 规则仍闭合 | PASS |
| Effect 自动建立单一稳定审批、固定 subjects、人工决定与 start/sync 分离 | `apr_<execution_id>`、固定 request→payload subjects、无自动决定/submit、显式 start/sync 均成立；但 B1 表明它依赖的 Execution 身份本身不稳定 | **FAIL** |
| 科学资格与执行授权是两个决定 | qualification Approval 与 `execution_authorization` 的 kind、subjects、合同和决定均分离 | PASS |
| readiness 与 invoke 使用同一绑定；查询不推进命令状态 | readiness/invoke 都从同一 `_prepare_operation_call`/`BoundOperationCall` 出发；但 B2 的查询纯度失败 | **FAIL** |
| Root 工具、通用表和 Operation 字段净减少 | 独立复算与归因均正确，见第 4 节 | PASS |
| 单插件入口、单 `CompiledCatalog`，无第二 registry/兼容路由/领域特判 | 所有声明入口仍为 `scidiscovery.plugins`；生产 AST 只有一个 `CompiledCatalog(...)` 构造点；关键核心路径领域 token 扫描为 0 | PASS |
| TCAD、普通 Agent、Local/Hardened、部署与 33 项约束无组合退化 | 串行聚焦、组合和全量测试均绿，结构扫描未见新分叉；但 B1/B2 位于 Local/Hardened 共用 Root/service，且实际违反 33 项约束，不能据绿测判 PASS | **FAIL** |
| 奥卡姆：本阶段无必须再删的重复治理 | 未见需新增抽象；但 B1 应折回现有请求幂等身份，B2 应删除查询内隐藏命令。二者正是本阶段必须关闭的重复/隐藏治理 | **FAIL** |

## 4. 独立复杂度复算

### 4.1 Root 工具

冻结的 R5-M0 清单为 30 个；当前 `ROOT_TOOLS` 为 26 个，Local/Hardened 投影也各为 26 个。M6 没有
新增工具，恰好删除：

```text
M6-A  instance_prepare
M6-A  instance_status
M6-A  instance_select
M6-D  execution_approval_request_create
```

因此 `30 → 26`、M6 净删 4 及 A/D 归因正确。部署脚本对退役名称的负断言不计作可调用兼容路径。

### 4.2 fresh 通用数据库

独立新建默认 Local runtime，按五个通用 owner 复算为 15 表：

```text
Artifact   3  artifact_envelopes, artifact_links, idempotency_records
Scheduler  5  scheduler_bindings, scheduler_instances, scheduler_observations,
              scheduler_scientific_selections, scheduler_sessions
Run        2  run_activity, runs
Approval   4  approval_decisions, approval_requests, decision_attempts, used_nonces
Execution  1  executions
```

冻结 M0 为 20；M1 删除 `artifact_events`、`approval_events` 两张事件表；M6-A 删除
`scheduler_instance_proposals`、`scheduler_session_binding_requests`、
`scheduler_session_binding_candidates` 三张伪审批表；M6-B/C/D 新增 0。故 `20 → 15` 中 M1 `-2`、
M6-A `-3` 的归因正确。Hardened 的 backend-private `active_transport` 不属于五个通用事实 owner，排除
口径一致。

### 4.3 Operation 合同

| 合同 | 冻结 M6 前 | 当前 | 归因 |
|---|---:|---:|---|
| `InputPortSpec` | 16 | 12 | M6-B 删除 cohort、approval kind/options/providers 四字段 |
| `OutputPortSpec` | 18 | 17 | M6-C 删除 `allowed_input_usages` |
| `OperationSpec` | 11 | 12 | M6-B 只增加一个可选 `input_admission` |

三类合计 `45 → 41`，净减 4；ABI 从冻结 M2 的 9 经 M6-B 的 10 到当前 11。生产代码无旧字段双读。

### 4.4 当前规模与目录

`scripts/r5_current_metrics.py` 和独立字段/文件计数一致：

| 指标 | 冻结/门槛 | 当前 | 判定 |
|---|---:|---:|---|
| 生产 Python | M0 146 文件 / 50,023 行 | **141 / 46,717** | 净减 5 / 3,306，正确 |
| `src/scidiscovery/operations` | 门 8 / 2,103 | **8 / 2,100** | 通过 |
| `catalog.py` | 门 738 | **734** | 通过 |
| 默认五插件 | M0 220 components / 46 Operations | **186 / 43** | 归因与证据一致 |

生产 AST 只有 `src/scidiscovery/operations/catalog.py:708` 一个 `CompiledCatalog(...)` 构造点；根包与
各插件 `pyproject.toml` 只声明 `scidiscovery.plugins` 入口组。关键核心扫描的领域 token 命中数为 0。
这些数字支持结构净简化，但不能抵消 B1/B2 的语义失败。

## 5. 33 项约束与架构边界

约束账本可解析为 **33 项且 id 全部唯一**；当前 assessment 统计为 `conformant=7`、
`pending_review=25`、`known_issue=1`。终审没有把历史 pending 自动升级。

- B1 违反 `AUTH-001` 的控制面唯一事实、`IMM-002` 的完整请求幂等、`CQRS-002` 的显式幂等状态推进
  和 `RES-002` 的有界恢复。`AUTH-001` 当前账本虽标为 `conformant`，其 evidence 只证明 H3-A 删除
  YAML current；B1 是新的全域反例，故该标签不能作为 M6 放行证据。修复后应按决策语料规则另行
  对账，不得覆写本报告或历史 FAIL。
- B2 直接违反 `CQRS-001` 的 requirement/prohibited；审批过期与结果发布还违反 `CQRS-002` 的命令
  边界。
- `HIL-002` 仍成立：科学资格与执行授权没有合并。`EFF-001/002` 的 submit/domain/collect 和未知提交
  查回结构未见由 M6 合并。Artifact/Run/current、精确 reviewer/revision、TCAD Operation、普通 Agent、
  Local/Hardened 配置与部署安装没有发现 B1/B2 之外的新退化。
- `SEC-002` 的 Local 原生工具隔离仍是账本中唯一 `known_issue`，是计划已显式保留的既知限制，不是
  本审查新增非阻断缺陷，也未被本报告宣称关闭。

## 6. 串行验证记录

所有 pytest 均单进程串行运行，设置 `ulimit -Sv 7340032`（7 GiB）、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1`，并禁用 pytest cache provider；未使用 `xdist` 或任何并行命令。

### 6.1 M6 聚焦组合集

```bash
pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_m6a_direct_instance_management.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_artifact_audit.py
```

结果：`52 passed in 55.88s`。

### 6.2 跨边界扩展集

```bash
pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l5_hardened_run_backend.py \
  tests/operations/test_l6_runtime_capabilities.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m3_transform_equivalence.py \
  tests/operations/test_l2_local_run.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/artifact_agent/test_deploy_scripts.py
```

结果：`116 passed in 76.13s`。

### 6.3 当前完整回归

```bash
pytest -q -p no:cacheprovider --tb=short
```

结果：`257 passed in 113.08s`。

### 6.4 结构、度量和独立反例

| 命令/探针 | 结果 |
|---|---|
| `python scripts/r5_current_metrics.py` | exit 0；生产 `141/46717`、operations `8/2100`、catalog `734`、核心领域 token `0` |
| `PYTHONPATH=src:tests/fixtures python - <<'PY'` fresh runtime/字段/约束探针 | Root Local/Hardened `26/26/26`；fresh 表 15；字段 `12/17/12`，ABI 11；约束 `33/33` |
| 同类 inline Execution 创建/绑定故障注入 | exit 0；三次故障后 3 行，恢复后 4 行、3 个孤儿，仅第 4 个绑定，见 B1 |
| inline Root approval/execution 查询前后摘要探针 | exit 0；status 令审批落库过期，execution status 新增结果 binding，见 B2 |
| inline loopback dashboard HTTP GET 前后摘要探针 | HTTP 200；GET 轮换 access/CSRF token 和 expiry，见 B2 |
| 旧工具/字段/隐藏集合/入口组/`CompiledCatalog` AST 扫描 | 生产旧面 0；唯一入口组与唯一构造点成立 |
| `git diff --check HEAD` | exit 0，无 whitespace error |

第一次独立 schema 探针直接从 source checkout 启动时因未设置 `PYTHONPATH` 得到
`ModuleNotFoundError: scidiscovery`；补上 `PYTHONPATH=src:tests/fixtures` 后上述探针通过。这是审查命令
环境修正，不是产品测试失败，也没有修改工作树。

测试全绿只证明现有断言通过。B1 的注入点早于现有 Approval binding 恢复测试，B2 则需要数据库前后
摘要而非返回值断言；因此这两个反例与 `257 passed` 不矛盾。

## 7. 审查对象与语料处理

本工作树包含自基准提交以来尚未拆成单一 M6 commit 的完整 R5 变更，不能把 `git diff HEAD` 冒充精确
M6 diff。本审查按要求以当前组合字节为对象，并用冻结实施证据、首次 FAIL、复审 PASS、架构章程和
33 项约束复核归因。关键当前字节指纹为：

```text
38258de31e9aa75555d4e9902eb81377c945225e341e252aee52e95f9fd71913  mcp_root_execution_routes.py
d5cdbfc0bcb3999dbcbcd5026e66fdf91e694041dcfc68c4b59fd684d02d6fcc  executions.py
414b27002ad0fb47948bfe954dc4b03248ec358474f3e0d17d90bc46ca2b9bab  approvals.py
3612c797d16a7e6f4e41ee5a49731367883ce2e037ac542487d5941764cbb872  approval_ui/app.py
ae7838bf9c9927535094dbc6c126ee88266e1b273c11ba57ddd8a6f1fd72396d  operations/spec.py
a1e12de19b607278c8317916c247e91a5543327cfd7bd6115522fc878b7afc11  operations/catalog.py
53a498e7c416a70da6e0bf8dc92a465d2ccf6979d1c39906efc1609d07509ad4  operations/invoke.py
```

历史首次 FAIL 与局部复审报告均保持原结论；本报告不覆盖或改写旧 verdict。计划、README 和总体证据
当前都仍写明“只有 M6 整体终审 PASS 才可进入 M7”，因此本 FAIL 是当前唯一有效放行判断。

## 8. 唯一放行判断

**M6 整体终审 FAIL。M7 不放行。**

只有 B1、B2 按上述最小关闭条件修复、加入精确负例，并由未参与返工者重新审查当时的当前组合字节为
PASS，才可重新考虑放行 M7。不得以四个旧局部 PASS、现有 `257 passed` 或正确的净复杂度数字代替该
整体复审；本报告也不授权把修复扩张成新的 registry、恢复状态机或兼容路径。
