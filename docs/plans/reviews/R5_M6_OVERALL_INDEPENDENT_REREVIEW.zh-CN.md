# R5-M6 整体返工全新独立复审

- 日期：2026-09-02
- 审查对象：当前工作树组合字节；基准提交
  `404aeb14c6ebc4b08bac599db91eaee54c103f48` 只用于定位，不能冒充精确 M6 返工 diff
- 审查身份：未参与 M6 实现、首次整体终审或本次返工的全新普通代码审查者
- 复审结论：**FAIL**
- 放行判断：**不放行 M7；不宣称 M7、R5-M 或 M6 整体完成**
- 缺陷计数：**1 项阻断，0 项新增非阻断缺陷**

## 1. 结论先行

首次整体终审的两个指定反例已经在当前字节上实质关闭：

1. 同一完整 Effect 调用在 Execution 行和 request Artifact 已提交、Execution binding 连续三次失败后，
   始终只有一个 Execution 和一个 request Artifact；恢复后同一 Execution 被绑定，只建立一个 Approval，
   adapter submit 为零。
2. 业务过期审批、过期访问 token、Root approval status/list、loopback dashboard/review GET，以及已
   collected 但尚无 result binding 的 Execution status/list，前后全部持久库逻辑摘要不变；显式同源、
   CSRF 保护的 POST 续期和 `execution_outputs` 发布均可用。

稳定 execution id 的既有对象也会对 executor、preparation profile、payload、compiled identity 和 labels
任一变化失败关闭，当前实现不扫描或静默收养任意旧孤儿。首次整体终审的 B1、B2 因而不能原样继续
作为当前阻断；其历史 FAIL 报告仍须原样保留。

但是，稳定 identity 返工在相邻、更早的跨库提交窗口留下了新的阻断：
`ExecutionService.create()` 先提交含动态 `created_at` 的 `execution_request` Artifact，再插入
`executions` 行。若进程或调用恰在 Artifact 已提交、Execution 行尚未插入时中断，同一完整
`operation_invoke` 重试会使用同一稳定 idempotency key，却产生不同的 request bytes，永久得到
`IdempotencyConflictError`。此时数据库保持 0 个 Execution、1 个不可达 request Artifact、0 个
Approval、0 个 binding，后续同一调用无法自行恢复。

这不是测试建议或 M7 才验证的远端能力，而是当前本地生产 service 的确定性故障窗口，违反
`IMM-002`、`CQRS-002` 和 `RES-002`。所以尽管 59 项组合、116 项跨边界和 260 项完整回归全部通过，
R5-M6 整体仍必须 **FAIL**。

## 2. 审查对象与当前字节

工作树包含从单一 baseline commit 起尚未拆分提交的完整 R5 变更，无法从 `git diff HEAD` 还原精确的
“首次整体 FAIL 后返工 diff”。本复审以当前组合字节为对象，以首次 FAIL 报告中的冻结观察作为前态，
并独立读取当前实现、测试、M6 计划完成门、设计宪章和 33 项约束。关键当前字节为：

```text
388e2b9f678f9f1ecb3ffa8ec5bf691df60eb2cb3ef45e336ef03846c8280c1d  mcp_root_execution_routes.py
652d742667144f58d00d167ea0f22bba87350f11c3d173d2953059d984b9913c  executions.py
5784566f48352df57df602044009773069bd517a1890d6e29fb83e90483cd39a  approvals.py
6b64c67de10c194036833f8289e39dfcf70b9ee75dbb1c474950bc9aa4262572  approval_ui/app.py
abccdb2231bf485f98f261cd0723d71fa8109d5c30473eb06aa06ad39ac51ee7  mcp_root_approval_routes.py
44683db2bbdf64d188fbe918c048cbb4bb42ae1480654cd3b04db034dab8a8d5  test_r4_execution_approval_identity.py
b0ede8c692a3c35ae985bc2439e382ba4bcd496a0e1f6481a2d5c14f1e92af05  test_m6a_direct_instance_management.py
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
```

## 3. 首次 B1/B2 的独立复验

### 3.1 Execution 行已提交、binding 未提交：通过

当前 Root 在 `mcp_root_execution_routes.py:147-181` 先计算包含 Operation id/version/digest、审批合同
digest、executor、preparation profile 和 payload ref 的完整调用指纹，再以实例、最终语义名和该指纹
派生稳定 `execution_id`。`ExecutionService.create()` 在 `executions.py:97-118` 对同 id 的既有行、
stored request、payload、compiled identity 和 labels 做完整复核。

我在真实 Root facade 和当前 architecture Effect fixture 上，让 `_bind_target("execution", ...)` 在
Execution 行与 request Artifact 已提交后连续三次抛错。每次故障后的
`Execution/request Artifact/Approval/submit` 数量均为：

```text
第一次  1 / 1 / 0 / 0
第二次  1 / 1 / 0 / 0
第三次  1 / 1 / 0 / 0
```

三次观察到的 id 完全相同：

```text
exe_0865e5bb843f0b5d09cceebc81ac0ba9e5f8fc95d4461d9a351c233d6b667211
```

第四次不再注入故障后，数量为 `1 / 1 / 1 / 0`，最终 binding 指向上述同一对象，返回状态为
`created`。该结果关闭首次整体终审 B1 明确要求复验的窗口。

### 3.2 稳定 id 的请求冲突与孤儿边界：通过

对上述稳定 id 做 exact replay 成功；分别改变 executor、preparation profile、payload ref、compiled
identity 和 labels，五类重放全部得到“execution identity is already bound to a different request”，
Execution 和 `execution_request` 数量不增加。

我另预先创建一个没有语义 binding、但 request 内容相同的随机
`exe_ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff`，再发起一个正常 Effect 调用。
Root 绑定的是由当前实例、语义名和指纹派生的
`exe_3b5733bba262bdc21d6dcca59afd6d7395649d9957b4ae34f39daa8597a3958e`，没有扫描或收养随机对象。
这正是 fail-closed 边界：无绑定旧对象可留给离线审计，但查询或新调用不得猜测其语义归属。

### 3.3 Approval 查询与页面 GET：通过

独立探针在同一个 fresh state 中同时构造：

- 一个持久行仍为 pending、但业务 `expires_at` 已过期的审批；
- 一个业务仍 pending、但 access token 已过期的审批；
- Root 对二者的语义 binding；
- 真实 loopback `ApprovalUI`。

随后对 state 下所有 SQLite 库、所有非内部表和全部行做排序逻辑摘要。Root
`approval_status` 返回业务审批的有效状态 `expired`；`approval_list(pending)` 只返回过期访问链接项，
`approval_list(expired)` 只返回业务过期项；dashboard GET 为 200，业务过期 review GET 为 200 的只读
历史视图，过期 access token 的 review GET 为 403。全部读取前后五个持久库摘要完全一致。

错误 Origin 和错误 CSRF 的续期 POST 均为 403 且摘要不变。正确同源、正确 CSRF 的显式 POST 返回
303，只改变 `database/approvals.sqlite3`；新 review URL 随后 GET 200，且该 GET 再次不改库。
`approvals.py:284-301,371-476,533-573,990-997` 的有效状态投影与只读 review 路径、以及
`approval_ui/app.py:295-296,424-464` 的显式续期命令，与实测一致。

### 3.4 collected Execution 查询与显式发布：通过

我建立一个已授权、已提交、随后由 service 直接记录为 succeeded 并 ingest 成 collected、但尚无
`<execution>.result` binding 的 Execution。对全部持久库取摘要后调用 Root `execution_status` 和
`execution_list(collected)`：返回 `state=collected`、`result_artifact_name=null`，前后摘要完全一致。

随后显式调用 `execution_outputs`，`<execution>.result` 才被绑定到已有 result Artifact，持久库摘要按
预期改变。代码边界位于 `mcp_root_execution_routes.py:444-491,510-524`：status/list 只验证已有
binding，`execution_sync`/`execution_outputs` 才调用 `_publish_execution_result()`。首次整体终审 B2
的 Execution 分支已关闭。

## 4. 新阻断 B3：request Artifact 已提交、Execution 行未提交时不可恢复

**严重性：阻断。** 影响完整请求幂等、显式命令恢复和进程故障有界性。

当前实际顺序是：

1. `mcp_root_execution_routes.py:166-180` 派生稳定 `execution_id` 并调用
   `ExecutionService.create()`；
2. `executions.py:97-101` 只从 `executions` 表查既有 id；
3. 若行不存在，`executions.py:119-126` 以每次调用的新 `_timestamp()` 构造 `ExecutionRequest`；
4. `executions.py:127-140` 先把 request bytes 以稳定键
   `execution:<stable execution_id>:request` 登记并提交到 Artifact 数据库；
5. `executions.py:141-157` 随后才在另一个 SQLite 库插入 `executions` 行。

第 4、5 步不在同一事务。进程退出、数据库打开失败、SQLite 插入失败或其他异常都可在 Artifact 已
提交但 Execution 行未提交时发生。下一次相同调用仍得到相同 execution id 和 idempotency key，但第
3 步的 `created_at` 已变化，从而改变 request payload SHA。Artifact registry 在
`storage/sqlite.py:168-180` 正确地把同键异字节拒绝为 `IdempotencyConflictError`；问题在于
Execution 创建端没有取回并验证已提交 request Artifact 的恢复路径。

独立故障注入在 `ArtifactService.register()` 已真实提交 `execution_request` 后抛错，原始结果是：

```text
first_error = RuntimeError: injected after request Artifact commit
after_first = executions 0, requests 1, approvals 0, binding null, submit 0

retry_error = IdempotencyConflictError:
              idempotency key is already bound to a different request
after_retry = executions 0, requests 1, approvals 0, binding null, submit 0
```

这与 3.1 并不矛盾：3.1 注入在 Execution 行已经存在之后，当前既有行校验能够恢复；B3 注入在该行
之前，重试永远到不了既有行分支。仓库中也没有按此稳定 key 恢复 request Artifact 并补建精确
Execution 行的命令或 reconcile；任意孤儿收养又被正确禁止。因此该 request Artifact 对正常 Effect
语义入口不可达，同一完整调用也无法继续建立 binding 或 Approval。

约束影响：

- `IMM-002`：行为完全未变却不能幂等重放；冲突来自非行为字段 `created_at`，不是合法修订；
- `CQRS-002`：显式创建命令在一次已提交后果后不能幂等完成剩余后果；
- `RES-002`：一次常规进程/数据库故障把同一 Run 前 Effect 请求留在永久不可恢复状态。

**最小关闭条件：** 不增加表、Root 工具、后台清理状态机或任意孤儿扫描。应在现有稳定
`execution_id`/idempotency key 下使第 4、5 步可恢复：要么原子提交，要么在 Execution 行缺失但 exact
idempotency record 已存在时，只取回该 key 对应的冻结 request Artifact，逐项验证
execution id、executor、preparation profile、payload ref、compiled identity 和 labels 后补建同一
Execution 行。不能按 kind、payload 或相似 labels 收养其他 Artifact。必须增加精确回归：在 request
Artifact 已提交、Execution INSERT 前连续故障，随后同一完整 `operation_invoke` 恢复为一个
Execution、一个 request Artifact、一个 binding、一个 Approval、submit 0；任一请求字段改变仍
fail-closed。

## 5. 奥卡姆剃刀与复杂度复算

返工的结构方向本身保持克制：稳定 id 折回现有完整指纹；业务过期改为读时有效投影；token 续期和
result 发布移到既有 UI/Root 的显式命令；没有增加领域状态机。当前独立复算为：

| 指标 | 冻结/前态 | 当前 | 判断 |
|---|---:|---:|---|
| Root 工具（Root/Local/Hardened） | M0 30 | **26/26/26** | M6 净删 4，无新 Root 工具 |
| fresh 五类通用事实表 | M0 20 | **15** | M1 -2、M6-A -3；返工新增 0 |
| `InputPortSpec` 字段 | M6 前 16 | **12** | 删除四个端口重复资格字段 |
| `OutputPortSpec` 字段 | M6 前 18 | **17** | 删除未来用途字段 |
| `OperationSpec` 字段 | M6 前 11 | **12** | 只增加现有 `input_admission`；返工新增 0 |
| 三类合同合计 | 45 | **41** | 净减 4，ABI **11** |
| 生产 Python | M0 146 / 50,023 | **141 / 46,845** | 净减 5 / 3,178 |
| `operations` 包 | 门 8 / 2,103 | **8 / 2,100** | 通过 |
| `catalog.py` | 门 738 | **734** | 通过 |
| 默认五插件 | M0 220 components / 46 Operations | **186 / 43** | 收敛 |

fresh 表逐库为 Artifact 3、Scheduler 5、Run 2、Approval 4、Execution 1。生产 AST 只有
`src/scidiscovery/operations/catalog.py:708` 一个 `CompiledCatalog(...)` 构造点；所有声明入口仍只有
`scidiscovery.plugins`；度量脚本在关键通用核心中的领域 token 命中为 0。未发现新增表、第二
registry、第二 current、Operation 字段、兼容路由、插件名分支或 TCAD/曲线领域特判。

首次 FAIL 报告记录的生产规模是 141/46,717；当前为 141/46,845，增加 128 行但没有增加生产文件。
结合当前 UI 显式续期、query 投影和结果发布代码，此增量没有形成需删除的新抽象。B3 也不要求新
恢复系统：最小修复应复用现有稳定 key、Artifact 幂等记录和 Execution 行。故奥卡姆的**结构门通过**，
但生命周期闭合门因 B3 **失败**，结构净减不能抵消语义不可恢复。

## 6. 33 项约束逐项复核

注册表保持 33 个唯一 id，assessment 仍为 `conformant=7`、`pending_review=25`、`known_issue=1`；本复审
不把测试通过自动改写成 33/33 conformant。

| ID | 当前返工相关判断 |
|---|---|
| AUTH-001 | 无第二 Execution/Approval/current 权威；指定随机孤儿不被收养。B3 留下不完整 request Artifact，但不是第二权威。 |
| AUTH-002 | Worker assignment 与控制身份面未由返工改动；无新增暴露。 |
| AUTH-003 | Effect identity、审批合同、start 授权仍消费同一 compiled Operation；无隐藏能力表。 |
| IMM-001 | 已登记 request/result/decision Artifact 仍不可变；查询不覆盖字节。 |
| IMM-002 | **FAIL：B3 中相同完整请求因新的 `created_at` 字节而冲突，不能幂等重放。** |
| LIN-001 | 原始目标绑定路径未改；无新增科学目标解释。 |
| LIN-002 | current、cohort 与 revision 规则未改；M6-B/C 精确回归通过。 |
| EVD-001 | 外部来源冻结/locator 路径未改；返工不制造来源。 |
| EVD-002 | 来源独立性和冲突保留未改；控制层无新聚合判断。 |
| UNC-001 | 未增加默认参数、范围或可调性。 |
| UNC-002 | 未改变机制/nuisance 对照所有权。 |
| TOP-001 | 无阶段 DAG 或自动调度步骤回流。 |
| TOP-002 | readiness/invoke 仍共用 `_prepare_operation_call`；相关组合回归通过。 |
| ROLE-001 | token/result 修复只处理机械控制事实，不补科学内容。 |
| ROLE-002 | compiled identity、projector subject 和 authorize 合同仍闭合；漂移/卸载负例通过。 |
| DET-001 | 稳定 execution id 由 canonical SHA-256 确定；Transform 重放面未改。 |
| DET-002 | 无 Metric/控制层科研选择新增。 |
| HIL-001 | 决定仍只来自 exact loopback UI；显式 refresh POST 只续期访问能力，不写决定。 |
| HIL-002 | 科学资格与 `execution_authorization` 保持两个合同和决定。 |
| CQRS-001 | **PASS：Approval/Execution status/list 及 dashboard/review GET 的全库摘要反例通过。** |
| CQRS-002 | **FAIL：B3 的同一显式创建命令不能在部分提交后幂等完成。** |
| EFF-001 | create/authorize/submit/domain status/collect/result publish 仍分离。 |
| EFF-002 | 未知提交查回路径未改；本返工没有自动 submit、cancel 或 collect。 |
| PLG-001 | 关键核心领域 token 0；无插件名、Schema 名或领域分支。 |
| PLG-002 | 单 entry-point group、单 catalog；默认五插件仍可编译，跨边界集通过。 |
| SEC-001 | 同源和 CSRF 负例均 403；查询不能借来源内容扩权。 |
| SEC-002 | 既有 Local 原生工具隔离 `known_issue` 原样保留，未被本报告升级。 |
| RES-001 | 输入/输出大对象边界未由返工改变。 |
| RES-002 | **FAIL：B3 在普通进程/数据库中断后永久卡住相同 Effect 调用。** |
| UI-001 | dashboard 对过期访问链接显示显式续期动作；renderer 回归通过。 |
| UI-002 | status、过期和显式维护结果仍可审计；无隐式成功写入。 |
| MIG-001 | 无旧 binding/approval 自动升级；随机无 binding Execution 不被收养。 |
| MIG-002 | 安装/回滚代码未由返工新增分支；真实机器发布仍按账本保持 pending。 |

因此 33 项结构登记正确、绝大多数边界未退化，但只要 `IMM-002`、`CQRS-002`、`RES-002` 中任一存在
当前反例，M6 portfolio 就不能通过。

## 7. 串行验证记录

所有 pytest 与内联探针均为单进程串行，使用：

```bash
ulimit -Sv 7340032
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q -p no:cacheprovider --tb=short ...
```

未使用 `xdist` 或任何并行测试。

### 7.1 审批/执行精确集合

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_m6a_direct_instance_management.py
```

结果：`18 passed in 13.08s`；外层 elapsed `13.42s`；MAXRSS `99,924 KiB`；exit 0。

### 7.2 M6 组合与 UI 扩展

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_m6a_direct_instance_management.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_artifact_audit.py
```

结果：`59 passed in 54.75s`；外层 elapsed `55.12s`；MAXRSS `106,664 KiB`；exit 0。

不含四项 renderer 的原首次终审组合选择另跑为 `55 passed in 55.06s`、MAXRSS `106,300 KiB`。

### 7.3 跨边界扩展

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
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

结果：`116 passed in 75.37s`；外层 elapsed `74.32s`；MAXRSS `124,044 KiB`；exit 0。

### 7.4 当前完整回归

```bash
python -m pytest -q -p no:cacheprovider --tb=short
```

结果：`260 passed in 114.38s`；外层 elapsed `113.25s`；MAXRSS `139,480 KiB`；exit 0。

### 7.5 独立探针与结构命令

| 命令/探针 | 精确结果 |
|---|---|
| `PYTHONPATH=src:tests/fixtures/plugins/architecture_operation_plugin:tests/operations python - <<'PY'`，连续三次 Execution binding 故障、稳定 id 冲突、随机孤儿、collected query/publish 探针 | 三次均 `1/1/0/0` 且同 id；恢复 `1/1/1/0`；五类冲突拒绝；随机孤儿未收养；status/list 全库摘要不变；`execution_outputs` 显式发布 |
| `PYTHONPATH=src:tests/operations python - <<'PY'`，Approval 全库摘要与真实 HTTP 探针 | Root 有效状态 `expired`；dashboard/business/stale GET 为 `200/200/403`；全查询摘要不变；坏 Origin/CSRF 为 `403/403`；正确 POST `303` 且只改 approvals 库；刷新后 GET 200 且纯读 |
| `PYTHONPATH=src:tests/fixtures/plugins/architecture_operation_plugin:tests/operations python - <<'PY'`，request Artifact 提交后、Execution INSERT 前故障注入 | 首次 `0 Execution/1 request/0 Approval/null binding/0 submit`；同一调用重试 `IdempotencyConflictError`，状态不变，见 B3 |
| `PYTHONPATH=src:plugins/...:scripts python - <<'PY'`，fresh runtime/字段/插件/AST/约束复算 | Root `26/26/26`；15 表；字段 `12/17/12`、ABI 11；141/46,845；operations 8/2,100；catalog 734；五插件 186/43；唯一 catalog 构造；领域 token 0；约束 33/33 |
| `git diff --check HEAD` | exit 0，无 whitespace error |

最初内联 Execution 探针误把 fixture 根写成 `tests/fixtures`，在产品调用前得到
`ModuleNotFoundError: architecture_operation_test_plugin`；改为 pytest 配置声明的精确 fixture 目录后通过。
首次度量筛选尝试发现环境没有 `jq`，上游打印得到 `BrokenPipeError`；改用同一 Python 采集函数直接
选择字段后通过。另一次 fresh 表探针错误假定 `ArtifactService.database_path` 是公开属性，得到
`AttributeError`；改为枚举临时 state 下的实际 SQLite 文件后通过。三者都是审查 harness 环境修正，
均未进入产品断言、未修改仓库字节，也没有被计作产品失败。

完整回归全绿并不覆盖 B3：当前新增测试只在 Execution 行已经存在后注入 binding 故障；没有在
`ArtifactService.register()` 已提交、`executions` INSERT 尚未发生处注入。B3 的原始状态和确定性重试
冲突因此与 `260 passed` 不矛盾。

## 8. 阻断与非阻断汇总

- 阻断：B3，request Artifact→Execution 行跨库提交窗口使相同完整 Effect 调用永久不可恢复。
- 新增非阻断缺陷：无。
- 明确保留但非本轮新增：`SEC-002` Local 原生工具隔离 known issue、真实远端/TCAD 科学与发布资格门。

## 9. 唯一放行结论

**R5-M6 整体返工复审 FAIL；M7 不放行。**

首次整体终审报告继续保留其当时 B1/B2 的 FAIL 事实；本报告只说明当前字节已关闭那两个精确反例，
不覆盖旧 verdict。只有 B3 以不增加表、Root 工具、第二 registry 或任意孤儿收养的最小方式关闭，加入
request Artifact 已提交而 Execution 行未提交的精确崩溃回归，并由未参与修复者对新的当前组合字节
独立复审为 PASS，才可重新考虑**仅放行 M7**。即使届时 PASS，也不得宣称 M7 或 R5-M 已完成。
