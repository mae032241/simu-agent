# R5-M6 整体第二次返工第二名全新独立复审

- 日期：2026-09-02
- 审查对象：当前工作树组合字节；基准提交
  `404aeb14c6ebc4b08bac599db91eaee54c103f48` 只用于定位，不能冒充精确 M6 diff
- 审查身份：未参与 M6 实现、首次整体终审、第一次返工复审或 B3 修复的第二名全新普通代码审查者
- 复审结论：**FAIL**
- 缺陷计数：**1 项阻断，0 项新增非阻断缺陷**
- 唯一放行判断：**不放行 M7；不宣称 M6、M7 或 R5-M 完成**

## 1. 结论先行

第二次返工正确关闭了第一次返工复审的 B3 主反例。在真实 Root Effect 路径连续三次于
`execution_request` Artifact 已提交、`executions` 行尚未插入处中断，每轮均稳定保持
`0 Execution / 1 request / 0 Approval / null binding / 0 submit`；第四次相同调用恢复为
`1 / 1 / 1 / 同一稳定对象 / 0`。无 Execution 行时，稳定 request Artifact 的内容、Operation 身份和
全部指定 Envelope 元数据任一漂移均失败关闭；原幂等记录缺失或指向不同 registration 也失败关闭，
随机相似 orphan 不会被扫描或收养。首次整体终审的 B1/B2 正常反例、显式维护命令和受控并发也转绿。

但完成门要求的是恢复只能依赖“稳定 request Artifact id + 原 idempotency record”。当前
`ExecutionService.create()` 只在 `executions` 行不存在时重放 Artifact registration；行已存在的分支
验证 request Artifact 后直接返回，完全不读取或重放原幂等记录。因此，在首次 B1 的
“Execution 行已提交、语义 binding 未提交”窗口中，原幂等记录被删除或损坏后，相同真实 Root Effect
重试仍被接受，并进一步创建 binding 和 Approval。

这个反例命中本次任务明文要求的“缺失/错误 idempotency record 均 fail-closed”，也表明 B3 的新验证
没有覆盖整条恢复入口。现有 `261 passed` 没有该负例，不能覆盖控制事实缺失后的 fail-open。故 M6
portfolio 仍为 **FAIL**。

## 2. 阻断发现 B4：已有 Execution 行的恢复绕过原幂等记录

**严重性：阻断。** 影响 `AUTH-001`、`IMM-002`、`CQRS-002` 和 `RES-002`。

### 2.1 当前代码路径

真实 Effect 路径在 `mcp_root_execution_routes.py:147-180` 计算完整调用指纹和稳定
`execution_id`，并在语义 binding 缺失时调用 `ExecutionService.create()`。该 service 的两条恢复分支
并不等价：

1. `executions.py:102-123` 查询到已有 Execution 行后，只检查行内 executor/payload，并调用
   `_validate_request_artifact()` 校验 request 内容及所列 Envelope 字段，随后直接返回；
2. 只有行不存在时，`executions.py:124-178` 才派生稳定 request Artifact id，取回冻结 request，并以
   `execution:<execution_id>:request` 再次调用 `ArtifactService.register()`；注册表由此核对原
   idempotency record；
3. Root 随后在 `mcp_root_execution_routes.py:181-184` 建立 execution binding 和 Approval。

所以第二次返工完整保护了 B3 的“Artifact 有、Execution 行无”状态，却没有保护 B1 的“Artifact 和
Execution 行均有、binding 无”状态。`_validate_request_artifact()` 不是幂等记录验证器；它不读取
`idempotency_records`。

### 2.2 独立真实 Root 反例

复审先在真实 Root facade 注入一次 Execution 行提交后的 binding 失败，得到：

```text
1 Execution / 1 execution_request / 0 Approval / null binding / 0 submit
```

随后只在一次性临时 state 中分别模拟两类控制存储损坏：删除原
`execution:<stable execution id>:request` 记录；或破坏该记录的 request bytes/hash。为构造明确要求的
缺失/错误记录负例，探针直接操作临时 SQLite 并先移除对应 append-only trigger；这不是产品写入口，
而是离线损坏/不完整恢复场景。两种情况下，相同 `operation_invoke` 都得到 `ACCEPTED`，并推进为：

```text
1 Execution / 1 execution_request / 1 Approval / stable execution binding / 0 submit
```

缺失记录与错误记录的返回状态均为 `created`。稳定 Execution 和 request Artifact 内容没有变化，但
Root 在不能由原幂等收据证明其 registration 的情况下仍把对象绑定到科学语义名，并建立人工执行授权
请求。这正是应失败关闭却继续推进的行为。

正常 `ArtifactService.register()` 会在一个 Artifact SQLite 事务内同时写 Envelope 和幂等记录，因此
普通 B1/B3 崩溃不会自然制造这个损坏；但本轮验收明确要求缺失/错误 record 也必须失败关闭，且
`AUTH-001`/恢复完整性不能把 append-only 声明当作“无需核对”的理由。离线损坏、错误恢复或部分数据库
替换后，当前 Root 路径不会调用 Artifact audit，也不会以其他方式发现该事实缺口。

### 2.3 当前回归为何没有发现

- `test_effect_execution_identity_is_stable_across_binding_failures` 只保留完整正确的幂等记录；
- `test_effect_recovers_request_artifact_committed_before_execution_row` 只走“行不存在”分支，因而会重新
  调用 `ArtifactService.register()`；
- 当前测试没有在“行存在、binding 不存在”状态下删除或置错原 idempotency record。

### 2.4 最小关闭动作

不需要新增表、Root 工具、registry、reconciler 或后台状态机。最小修复是让已有 Execution 行分支在
返回前也用冻结 request bytes、稳定 Artifact registration 和原稳定 idempotency key 重放现有
`ArtifactService.register()`，并核对返回 ref 与行内 `request_ref` 完全相同。这样：

- 正常完整重放仍返回同一个对象；
- record 缺失时因稳定 Artifact id 已占用而失败关闭；
- record 错误时由现有 idempotency/registry integrity 检查失败关闭；
- 无需扫描孤儿，也不产生新恢复事实。

应增加两个精确回归：已有 Execution 行且 binding 未建立时，原 record 缺失和错误分别不得建立
binding/Approval，adapter submit 必须保持 0。修复还应复用一条 registration 重放路径，避免“有行”和
“无行”再次形成两份恢复合同。

## 3. 第二次 B3 修复的独立复验

### 3.1 三轮 request-commit 故障：通过

复审没有只接受新增测试，而是另写内联探针，从真实 `RootMCPRouter.operation_invoke` 进入当前编译的
architecture Effect，在 `ArtifactService.register()` 真正返回后连续三次抛错：

| 轮次 | Execution | request Artifact | Approval | execution binding | submit |
|---:|---:|---:|---:|---|---:|
| 故障 1 | 0 | 1 | 0 | null | 0 |
| 故障 2 | 0 | 1 | 0 | null | 0 |
| 故障 3 | 0 | 1 | 0 | null | 0 |
| 恢复 | 1 | 1 | 1 | 同一稳定 Execution | 0 |

三轮观察到的 request Artifact id 完全相同：

```text
execution_request_720d0087c32097c66c8b83f472713aa0cacda9ba6d87419217030d946b1dfecc
```

三轮幂等键也完全相同，并包含同一稳定 Execution id。恢复返回 `state=created`，Execution 行引用的仍是
上述 Artifact。这一精确主反例通过。

### 3.2 无行恢复的身份与元数据负例：通过

复审先在 request 提交前截获当前 Root 将要登记的精确内容、Artifact id、registration 和幂等键，再在
fresh state 中分别预置单一漂移候选。以下每项均被拒绝，且保持 `0 Execution / 0 Approval /
null binding / 0 submit`：

| 漂移维度 | 结果 |
|---|---|
| request 内 `execution_id` | `ExecutionServiceError` |
| executor | `ExecutionServiceError` |
| preparation profile | `ExecutionServiceError` |
| payload ref | `ExecutionServiceError` |
| compiled operation/approval identity | `ExecutionServiceError` |
| labels | `ExecutionServiceError` |
| Artifact kind / Schema id / schema version | `ExecutionServiceError` |
| media type | `ExecutionServiceError` |
| creator | `ExecutionServiceError` |
| parent refs | `ExecutionServiceError` |
| confidentiality | `ExecutionServiceError` |
| 精确 Artifact 存在但原 key 无 record | `ArtifactIdentityConflictError` |
| 原 key 指向不同 registration | `IdempotencyConflictError` |

kind 漂移的候选不再计入 `kind=execution_request` 的列表，但其单一 Artifact 确实已持久化；判定依据是
Root 没有创建 Execution、Approval、binding 或 submit，而不是列表过滤造成的假零。

### 3.3 随机相似 orphan：通过

复审预置一个 payload 与预期 request 完全相同、但 Artifact id 为
`execution_request_ffff...ffff` 的随机相似 orphan。正常 Root 调用没有扫描或收养它，而是创建由稳定
Execution id 精确派生的另一个 request Artifact；最终数据库为 1 Execution、2 request Artifact、
1 Approval、submit 0，Execution 行引用稳定 id 对象而非随机 orphan。

## 4. 首次 B1/B2 与并发重放抽查

### 4.1 Execution 行提交后 binding 失败：正常记录下通过

在原幂等记录完整时，复审独立连续三次注入 Execution binding 失败。每轮均为
`1 Execution / 1 request / 0 Approval / null binding / 0 submit`，三轮 execution id 与 request id
分别稳定一致；第四次恢复为 `1 / 1 / 1 / 同一 Execution / 0`。因此首次 B1 的随机孤儿问题已关闭；
B4 是更窄但强制要求覆盖的收据完整性缺口，不能把 B1 的正常正例重新写成失败。

### 4.2 Approval、Root、UI GET 和 Execution 查询纯读：通过

复审对 temporary state 下所有 SQLite 文件、所有非内部表和全部行生成排序逻辑摘要，覆盖：

- 业务已过期但持久行仍 pending 的 Approval；
- access token 已过期但业务仍 pending 的 Approval；
- Root `approval_status` 与 pending/expired `approval_list`；
- loopback dashboard GET、业务过期 review GET 和过期 access-token review GET；
- 已 collected、已有 result Artifact 但尚无结果语义 binding 的 Execution；
- Root `execution_status` 与 `execution_list(collected)`。

查询前后所有数据库摘要完全一致。HTTP 结果为 dashboard `200`、业务过期 review `200`、过期 access
review `403`；Root 返回有效业务状态 `expired`。错误 Origin 和错误 CSRF 的 refresh POST 均为 `403`
且全库摘要不变。

正确同源/CSRF 的显式 refresh POST 返回 `303`，只改变 `approvals.sqlite3`；刷新后的 GET 为 `200` 且
再次不改库。显式 `execution_outputs` 才发布结果 binding，只改变
`scheduler-bindings.sqlite3`。这关闭首次 B2 的三类隐藏写入反例。

### 4.3 并发与 `INSERT OR IGNORE`：通过

复审在单个串行探针内使用有界两线程屏障专门制造竞争；这不是并行 pytest 或 `xdist`：

- 对同一 execution id，分别让 executor、profile、payload、compiled identity 或 labels 不同，每类
  连续 5 轮；每轮严格只有一个请求成功，另一个均以 `ExecutionServiceError` 拒绝，存储的 request
  与胜者逐项一致；
- 对两个完全相同的请求，在 Artifact registration 后设置屏障，使二者同时竞争
  `INSERT OR IGNORE`；两次调用均返回同一 id，最终只有 1 Execution 行和 1 request Artifact；
- 26 个受控并发场景最终为 26 Execution/26 request、0 Approval、0 submit，没有不同请求被
  `INSERT OR IGNORE` 静默接受。

## 5. M6 组合完成门

| 完成门 | 第二次独立复审事实 | 判定 |
|---|---|---|
| Artifact、Run、current、Approval、Execution 各一个权威 | 表、service 和 registry 数量仍唯一；但 B4 在原 Artifact 幂等事实缺失/错误时仍建立 Execution 语义 binding/Approval | **FAIL** |
| 普通探索零 cohort/approval/execution 成本 | M6-B 组合回归与代码路径保持无 admission 即不查询资格、不建副作用状态 | PASS |
| 实例创建/选择只经精确显式用户入口 | M6-A 直接 loopback capability、原子 session binding 和退役审批只读回归通过 | PASS |
| Operation 级 all-or-none/资格合同唯一 | `InputAdmissionSpec`、preflight-before-guard 和同一 Root 资格查询保持唯一 | PASS |
| producer 未来用途预测消失 | 无 `allowed_input_usages` 或替代全局用途图；consumer/reviewer/revision 规则回归通过 | PASS |
| Effect 自动建立稳定精确 Approval，不自动决定/start/submit | 正常记录、B1/B3 和随机 orphan 均通过；但 B4 允许收据不完整对象进入 binding/Approval | **FAIL** |
| 科学资格与执行授权分离 | 两个 kind、subjects、决定和合同仍分离 | PASS |
| readiness 与 invoke 同源；查询纯读 | 同一 `_prepare_operation_call`；B2 全库摘要通过 | PASS |
| Root 工具、表和 Operation 字段净减少 | 独立复算 26 工具、15 表、41 字段，见第 6 节 | PASS |
| 单目录、单 registry、无领域特判 | 唯一 `CompiledCatalog` 构造点、单入口组、核心领域 token 0 | PASS |
| TCAD、普通 Agent、Local/Hardened 和组合回归不退化 | 组合、跨边界和完整回归全绿；但绿测缺少 B4，不能覆盖强制恢复负例 | **FAIL** |
| 奥卡姆：不以新治理修复旧治理 | 当前结构净减成立；B4 只需复用既有 registration replay，尚未闭合 | **FAIL** |

Portfolio 只要一个完成维度失败就不能通过，所以局部 PASS 不形成 M6 PASS。

## 6. 结构、规模与奥卡姆复算

独立 Python/AST/SQLite 探针未调用实施证据中的预计算结果；其结果与
`scripts/r5_current_metrics.py` 一致：

| 指标 | 当前独立结果 | 判断 |
|---|---:|---|
| Root / Local / Hardened 工具 | **26 / 26 / 26** | 相对 M0 30 净删 4 |
| fresh 五类通用事实表 | **15** | Artifact 3、Scheduler 5、Run 2、Approval 4、Execution 1 |
| `InputPortSpec` / `OutputPortSpec` / `OperationSpec` | **12 / 17 / 12** | 合计 41；相对 M6 前 45 净减 4 |
| Operation ABI | **11** | 无旧字段双读 |
| 生产 Python | **141 文件 / 46,959 行** | 相对 M0 146 / 50,023 净减 5 / 3,064 |
| `src/scidiscovery/operations` | **8 文件 / 2,100 行** | 未超过 8 / 2,103 门 |
| `catalog.py` | **734 行** | 未超过 738 门 |
| 默认五插件 | **186 components / 43 Operations** | 与当前证据一致 |

生产 AST 只有 `src/scidiscovery/operations/catalog.py:708` 一个 `CompiledCatalog(...)` 构造点；根包和
四个领域插件的 `pyproject.toml` 只声明 `scidiscovery.plugins` 同一个 entry-point group。按既有通用
核心扫描口径，`src/scidiscovery` 中 TCAD、device parameter、curve score、InGaAs、Fig.4 领域 token
命中为 0。未发现第二 registry、第二 current、兼容路由、Operation 字段或领域专用恢复分支。

第二次返工从第一次返工的 46,845 行增至 46,959 行，共增加 114 行且没有增加生产文件。稳定 Artifact
id、精确恢复和负例的方向符合奥卡姆；B4 也不需要新抽象。现有两条分支的 recovery validation 不同，
恰是应以一次既有幂等重放收敛的最小重复治理。

## 7. 33 项约束复核

当前 YAML 精确为 33 个唯一 id，assessment 分布仍是 `conformant=7`、`pending_review=25`、
`known_issue=1`。本复审不因 261 项绿测把 pending 自动晋级。

- **FAIL：`AUTH-001`**。Artifact idempotency record 是控制面不可变事实；B4 在它缺失或错误时仍建立
  语义 binding/Approval，未坚持完整控制事实权威。
- **FAIL：`IMM-002`**。行为重放只验证 request Artifact，没有证明它来自原完整 registration 请求；
  “只有完整指纹相同才幂等”的恢复证据链不完整。
- **FAIL：`CQRS-002`**。同一显式命令在部分后果恢复时绕过原幂等 consequence record，仍推进新的
  binding/Approval 后果。
- **FAIL：`RES-002`**。损坏/不完整恢复后的状态没有有界失败关闭，而是继续扩展权威语义状态。
- **PASS（本阶段相关）：`CQRS-001`**。Approval/Execution status/list 和 UI GET 全库摘要均纯读；
  refresh/result publish 只由显式命令写入。
- `HIL-001/002`、`EFF-001/002`、`PLG-001/002`、`MIG-001`、`ROLE-001/002`、`TOP-002` 的当前 M6
  相关路径未发现 B4 之外的新退化；人工决定仍只来自精确 UI，科学资格与执行授权分离，未知 submit
  不盲目重发，插件和合同入口保持唯一。
- `SEC-002` 的 Local 原生工具隔离仍是唯一 `known_issue`，原样保留，不被本报告升级或伪装关闭。

因此 33 项登记结构正确，但当前工作树存在明确行为反例，不能宣称 33 项不退化完成门通过。

## 8. 串行验证记录

所有 pytest 命令均单进程串行，设置：

```bash
ulimit -Sv 7340032
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q -p no:cacheprovider --tb=short ...
```

未使用 `xdist` 或并行测试命令。仅第 4.3 节单个内联并发不变量探针按其测试目的使用两个有界线程。

### 8.1 精确审批/执行集合

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_m6a_direct_instance_management.py
```

结果：`19 passed in 13.08s`；外层 elapsed `13.45s`；MAXRSS `98,828 KiB`；exit 0。

### 8.2 M6 组合与 UI 扩展

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

结果：`60 passed in 55.50s`；外层 elapsed `55.84s`；MAXRSS `105,928 KiB`；exit 0。

### 8.3 跨边界扩展

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

结果：`116 passed in 74.84s`；外层 elapsed `73.77s`；MAXRSS `124,996 KiB`；exit 0。

### 8.4 完整回归

```bash
python -m pytest -q -p no:cacheprovider --tb=short
```

结果：`261 passed in 115.22s`；外层 elapsed `113.50s`；MAXRSS `139,332 KiB`；exit 0。

### 8.5 独立探针与静态命令

| 命令/探针 | 结果 |
|---|---|
| 真实 Root B3 三轮 request-commit 故障 | 三轮 `0/1/0/null/0`；恢复 `1/1/1/同一对象/0` |
| request/Envelope/record 负面矩阵 | 13 个字段/元数据漂移及 2 个无行 record 负例全部拒绝；随机 orphan 未收养 |
| 真实 Root B1 三轮 execution-binding 故障 | 三轮 `1/1/0/null/0`；恢复 `1/1/1/同一对象/0` |
| **已有行 + record 缺失/错误反例** | **两者均 `ACCEPTED` 并建立 binding/Approval；B4 成立** |
| Approval/Execution/loopback 全库逻辑摘要 | 所有 GET/status/list 纯读；显式 refresh 只改 Approval DB，显式 publish 只改 binding DB |
| 有界并发/`INSERT OR IGNORE` | 不同请求每轮只接受一个；相同请求只留一行/一 Artifact |
| `python scripts/r5_current_metrics.py` | exit 0；141/46,959、operations 8/2,100、catalog 734、领域 token 0 |
| 独立 fresh runtime/AST/字段/插件/约束探针 | 26/26/26 工具、15 表、12/17/12、ABI 11、186/43、单 catalog、33/33 |
| `git diff --check HEAD` | exit 0，无 whitespace error |

第一次全库 Execution 探针误用了 `round2-run`，而 fixture adapter 已提交
`external_run_id=unexpected-run`，在查询断言前得到 `ExecutionStateConflict`；改用真实提交 id 后上述
探针通过。第一次独立结构探针误假定 `CompiledCatalog.all_operations` 存在，在指标输出前得到
`AttributeError`；改用公开 `operation_ids()` 后通过。这两项都是审查 harness 前置假设修正，没有进入
产品断言或修改仓库字节，不计为产品失败。

## 9. 审查对象、历史 FAIL 与剩余边界

当前分支为 `baseline/8765-codex`，`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`，其上叠加完整
R5 大型未提交工作树；不存在可从 Git 独立还原的精确 B3 修复 commit。本报告以当前字节、真实入口
和独立反例冻结审查对象。关键 SHA-256 为：

```text
a56230852d372a7ee266fcf892a8b4b3b7299da6768b42cbb6ea75b430daee5b  executions.py
388e2b9f678f9f1ecb3ffa8ec5bf691df60eb2cb3ef45e336ef03846c8280c1d  mcp_root_execution_routes.py
5784566f48352df57df602044009773069bd517a1890d6e29fb83e90483cd39a  approvals.py
6b64c67de10c194036833f8289e39dfcf70b9ee75dbb1c474950bc9aa4262572  approval_ui/app.py
5bb9341bbf91cec8aa4aec33d79b5efd5676bbaeb1f21ac0e505484a60e24c66  test_r4_execution_approval_identity.py
b0ede8c692a3c35ae985bc2439e382ba4bcd496a0e1f6481a2d5c14f1e92af05  test_m6a_direct_instance_management.py
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
```

两份历史 FAIL 原样保留：首次整体终审的 B1/B2 是当时字节的有效事实；第一次返工复审的 B3 是当时
字节的有效事实。本报告确认当前字节关闭那些精确主反例，但不覆盖、删除或回写旧 verdict。

没有运行真实远端 solver、真实生产升级或长时失联外部执行；它们属于 M7 和 `MIG-002` 等仍保留的
后续资格，不能由本地 261 项测试外推。当前 FAIL 已由本地真实 Root 的强制恢复负例充分成立，不依赖
这些尚未运行的后续门。

## 10. 唯一放行结论

**R5-M6 整体第二次返工第二名独立复审 FAIL；M7 不放行。**

只有 B4 以第 2.4 节的最小方式关闭，新增“已有 Execution 行 + binding 缺失 + 原 idempotency record
缺失/错误”的精确负例，并由未参与该修复者重新审查当时当前组合字节为 PASS，才可重新考虑**仅放行
M7**。即使未来 M6 复审 PASS，也不得由该报告宣称 M7 或 R5-M 已完成。
