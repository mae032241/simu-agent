# R5-M6D“Effect 自动建立审批请求”独立复审

日期：2026-09-02

审查者身份：未参与实现、首次审查或返工的普通代码独立复审者；本次不是科学 Operation Worker，
未调用 instance/control/worker 工具，也未修改生产代码、测试、计划、实施证据或首次审查报告。

## 1. 结论与唯一放行判断

**PASS。** 本复审不继承首次报告的 FAIL verdict，而是对当前文件字节重新追踪生产路径、独立重做
原 B1/B2 反例并重新运行风险相称的串行测试。首次审查的两个阻断均已关闭：

1. `ApprovalService.create_request()` 已提交而 approval semantic bind 失败后，相同
   `operation_invoke` 复用由不可变 `execution_id` 派生的同一 approval id 和同一幂等键；连续五次
   注入同一故障时，审批表、真实 loopback dashboard 和 exact 可授权候选始终各恰好一个，恢复后
   补齐同一 binding；
2. 即使提供真正理解反向 subjects 的 projector，反向 Effect `subject_ports` 仍在目录编译期以
   `effect_approval_contract_mismatch` 拒绝；projector 未被调用，Execution/Approval 记录增量均为零。

- 阻断项：**0 项**；
- 非阻断缺陷：**0 项**；
- 审计边界：2 项，见第 9 节，不改变本阶段结论；
- 33 项约束：未擅自晋级 registry 中的 `pending_review`，`SEC-002` 继续如实保持
  `known_issue`；没有发现 M6-D 导致的阶段退化；
- **唯一放行判断：只放行“M6 整体回归与独立终审”；M7 仍不放行。**

本报告不把完整测试数量替代语义审查，也不把首次报告或实施证据中的结论当作当前 verdict。

## 2. 审查基线、范围与方法

审查仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`

- 分支：`baseline/8765-codex`；
- `HEAD`：`404aeb14c6ebc4b08bac599db91eaee54c103f48`；
- 工作树：包含多个 R5 阶段的大量既有修改、删除和未跟踪文件，M6-D 不是独立 Git commit；因此本
  复审没有把整个 `git diff HEAD` 冒充 M6-D 专属补丁；
- 实际对象：首次 FAIL 报告、修订实施证据所指当前文件字节，以及
  `compile_catalog → operation_preflight/invoke → ExecutionService → ApprovalService → semantic
  binding → loopback UI → execution_start/sync` 的真实组合边界；
- 只写本报告；所有探针状态均位于自动清理的 `/tmp` 临时目录。

规范依据：

1. `docs/ARCHITECTURE.zh-CN.md`；
2. `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
3. `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 33 项当前约束；
4. `docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 的 M6-D、M6 完成门、M7 边界和自动
   停止条件；
5. `docs/plans/README.md` 的当前决策语料索引；
6. 当前生产代码、测试插件、平台生成器、部署入口和自动化测试。

本复审完整遵循 `scid-cross-boundary-review`、`scid-find-simplifications`、
`scid-change-scope-checks` 和 `karpathy-guidelines`：固定当前字节和真实入口，检查唯一权威、恢复、
插件合同、Worker/Root 隔离及净复杂度，再从目标反例扩展到完整回归。

关键当前字节：

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_execution_routes.py` | `38258de31e9aa75555d4e9902eb81377c945225e341e252aee52e95f9fd71913` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_approval_routes.py` | `abccdb2231bf485f98f261cd0723d71fa8109d5c30473eb06aa06ad39ac51ee7` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` | `e2d8876bde41af24f6dd302da106a3ae9a229a67eca51d6491af57168b88b81a` |
| `src/scidiscovery/artifact_agent/service/approvals.py` | `414b27002ad0fb47948bfe954dc4b03248ec358474f3e0d17d90bc46ca2b9bab` |
| `src/scidiscovery/artifact_agent/service/executions.py` | `d5cdbfc0bcb3999dbcbcd5026e66fdf91e694041dcfc68c4b59fd684d02d6fcc` |
| `src/scidiscovery/operations/catalog.py` | `a1e12de19b607278c8317916c247e91a5543327cfd7bd6115522fc878b7afc11` |
| `src/scidiscovery/operations/spec.py` | `ae7838bf9c9927535094dbc6c126ee88266e1b273c11ba57ddd8a6f1fd72396d` |
| `src/scidiscovery/platforms/codex.py` | `f5737759e490c963737ecd14abf4cc1a26befde9d04892c989c3242b44c76c9c` |
| `deploy/install.sh` | `8475b5a5a4b816b07c7e34ce1f89b9a09731e365ae721cf44a47f0ebe5a43d03` |
| `tests/operations/test_r4_execution_approval_identity.py` | `33179c894f3fe243c5d23a1409871954ff7a7f408cb35c9de685d2e002eb4a89` |
| `tests/operations/test_baseline_effect_lifecycle.py` | `a800f44971982a7b7a6db3894f506b516da9f5c190e74e0e7a2cfd7b1eb4dbd9` |
| `tests/operations/test_catalog_negative_cases.py` | `f2fe180cd68520ed5af0c8becf3ed0a34bd1be59eb242785d1171b3a6f78cb1b` |
| `tests/operations/test_catalog_compile.py` | `cf8a823e7b2d0d6c4b290cf904518f7a5041b085aeb9b7f46c50cd5b9e8f3fcb` |

## 3. 首次 B1 反例独立重做：PASS

### 3.1 故障位置与探针

独立探针没有调用现有测试函数。它建立全新 runtime、真实 `ApprovalUI` loopback server、当前
architecture fixture Effect 和无副作用 adapter，然后在 `RootExecutionRoutes._bind()` 的
`namespace="approval"` 分支连续五次抛错。

每次抛错前，探针直接查询 `approval_requests`，确认 `ApprovalService.create_request()` 的事务已经
提交且表中已有目标行。因此故障位置精确落在首次 B1 所要求的“审批已提交、semantic bind 尚未完成”
窗口，而不是在 create 之前伪造失败。

五次失败都重放完全相同的 `operation_invoke`。每轮分别检查：

- Execution semantic binding 已存在且解析到同一 `execution_id`；
- approval semantic binding 仍不存在；
- 审批表只有一行；
- approval id 恒为 `apr_<execution_id>`；
- 幂等键恒为 `execution-approval:<execution_id>`；
- approval id、幂等键、request ref 和 access token 的四元快照五次完全相同；
- `ApprovalService.list_requests(status="pending")` 只有该请求；
- 真实 `GET /` dashboard 只有一个 `approval-item` 和一个该 request-specific review link；
- Execution 保持 `created`，adapter submit 次数为 0。

恢复 `_bind()` 后再次调用同一请求，Root 补齐 `<execution-name>.approval` 到同一稳定 id；数据库和
dashboard 仍各只有一个请求。探针再按 kind、精确 `(request_ref, payload_ref)` 和 compiled identity
遍历全部审批，exact 可授权候选也恰好一个。最后只决定该请求并显式调用 `execution_start`，Execution
进入 `submitted`、adapter submit 恰好一次，审批表仍只有一行。

最终输出：

```text
B1_PASS faults=5 rows=1 dashboard_rows=1 exact_authorizable_candidates=1
approval_id=apr_<same-execution-id>
idempotency_key=execution-approval:<same-execution-id>
binding_recovered=yes unbounded_growth=no
```

### 3.2 根因关闭判断

当前 `_ensure_execution_approval()` 先解析已有不可变 Execution，再以该 Execution 的稳定身份生成
approval id 和幂等键。`ApprovalService.create_request()` 对相同幂等键和相同 canonical request bytes
返回已提交 launch；Root 随后只补做同一 semantic binding。恢复不需要新表、outbox、清理器、第二
registry 或公开二步工具。

因此首次 B1 的两个随机量（随机 approval id 及由其派生的随机幂等键）已经退出该路径；反复同一故障
不能使审批数无界增长，也没有遗留第二个可决定、可授权权威。

## 4. 首次 B2 反例独立重做：PASS

独立探针把 fixture Effect 的 `subject_ports` 改为
`("effect_input", "effect_request")`，并把实际加载的 projector component 替换为反向感知实现。该
实现明确要求反向端口顺序，若被调用则把 snapshots 重排后生成合法 `ReviewDocument`；因此候选不是
“声明反向但 projector 仍只理解 request-first”的无效反例。

对该插件直接调用当前 `compile_catalog()` 得到：

```text
B2_PASS reason=effect_approval_contract_mismatch
reverse_aware_projector_loaded=yes projector_called=0
execution_delta=0 approval_delta=0
```

异常还精确绑定 `operation_id="builtin.test.effect"`、`field="review"`。编译器要求 external Effect：

```text
subject_ports == (operation.outputs[0].name, operation.inputs[0].name)
```

并同时要求单输入、单 ExecutionRequest 输出及其 kind/Schema。检查发生在目录构建阶段；projector
虽已通过组件协议加载，但未执行，既有临时 runtime 的 Execution/Approval 行数前后无变化。首次 B2
所述“合法编译后直到人工决定完成才失败”的死路已经消失。

## 5. 其余要求逐项复核

### 5.1 自动创建、正常幂等与明确副作用边界：PASS

- `operation_invoke` 创建或找到 Execution 后只走私有 `_ensure_execution_approval()`；正常重放返回
  同一 Execution、同一 Approval 和同一 request-specific URL；
- 自动调用结束时 Approval=`pending`、Execution=`created`；
- Root 没有调用 `record_ui_decision`、`execution_start` 或 `execution_sync`；
- 人工决定前重复状态查询不推进本路径逻辑状态，adapter submit 始终为 0；
- 只有 loopback UI 决定后，显式 `execution_start` 才授权并提交；`execution_sync` 仍是后续显式命令。

### 5.2 旧公开工具在全部生产面不可达：PASS

- `ROOT_TOOLS` 当前 26 个且名称唯一，旧
  `execution_approval_request_create` 不在其中；`RootMCPRouter` 对该名称返回 `unknown root tool`；
- `SCHEDULER_TOOLS` 是当前 Root tools 的精确 26 项投影；
- `src/`、`plugins/` 和 `pyproject.toml` 对旧名零命中；不存在生产方法、RootTool、路由、别名、
  facade 或转发器；
- `deploy/install.sh` 中两处旧名只用于退役负集合和安装探针；测试中的命中也只用于不可达负例；
- 平台生成器和部署测试通过，没有第二生产入口。

### 5.3 exact request-specific loopback URL 只到 Root：PASS

- Root 的 `approval_status()` 仅在 pending 时返回
  `<loopback-base>/review/<approval_id>?token=<request-token>`，不是 dashboard 首页；
- B1 探针启动真实 loopback `ApprovalUI`，逐字确认 Root 返回值等于 UI base URL 加该请求保存的
  `review_path`；
- production systemd control unit 固定传入 `http://127.0.0.1:@APPROVAL_PORT@`，UI unit 固定绑定
  `127.0.0.1`；ApprovalUI 本身拒绝非字面 loopback 绑定；
- Run assignment、Local/Hardened Worker MCP、Worker 协议和 Codex Operation profile 对
  `review_url`、approval/execution id、access token 均无投影；Root scheduler prompt 只要求把 Root
  返回的 URL 提供给用户，聊天不能写决定。

### 5.4 labels、subjects、question、options、document、identity 精确：PASS

独立字段探针解析实际持久化的 `ApprovalRequest` 和 `ExecutionRequest` Artifact，确认：

- kind 精确为 `execution_authorization`；
- ExecutionRequest Artifact 的 operation id/version/digest 和 approval-contract digest 四项 labels
  与当前 compiled identity 精确一致；
- subjects 精确且有序为 `(ExecutionRequest ref, payload ref)`；
- question 精确来自当前 `ApprovalContract.question`；
- option id、label、reason requirement 和固定核心 description 逐项一致；
- `ReviewDocument` 等于当前 compiled projector 对精确 snapshots 的投影；
- ApprovalRequest 与 ExecutionRequest 的 compiled identity 完全一致。

探针随后分别构造错误 labels、subjects、question、options、document 和 identity。六类均失败关闭；
错误已有 binding 不增加新审批、不改变 binding、不提交 adapter。反向 subjects 携带原 request-first
文档时还会被 ApprovalService 的 JSON Pointer 校验更早拒绝；为单独到达 Root 比较，最终探针改用
无文档错误请求，Root 仍按 stored-contract 比较拒绝。

### 5.5 漂移、卸载、历史对象和 revision：PASS

- 人工决定后切换到合同漂移目录，`execution_start` 以 operation contract changed 拒绝；
- 当前 Operation 插件卸载后，历史 Execution 不回退到旧实现，start 拒绝；
- 错误 Approval compiled identity 无法授权；错误 subjects 由独立字段探针拒绝；
- 无 compiled identity 的历史 ExecutionRequest 即使存在人工决定也不能授权；
- 新 payload 使用 `on_conflict="create_revision"` 得到新 Execution 和新的 pending Approval；旧 revision
  决定不继承，未决定的新 revision 不能 start，adapter submit 保持 0。

### 5.6 Root 净减、表/状态/registry/ABI 与规模：PASS

- M6-C 的 Root 工具数为 27；当前为 26，净减 1；
- `OPERATION_ABI_VERSION="11"`，`OperationSpec` 仍为 12 个字段；`spec.py` SHA 与已审 M6-C 字节相同；
- 全新 runtime 独立枚举五个既有 SQLite owner，共 15 张表：Artifact 3、Run 2、Approval 4、Execution
  1、Scheduler 5；没有 M6-D 恢复表、状态机、outbox、第二 binding registry 或第二目录；
- `scripts/r5_current_metrics.py`：生产 Python `141 files / 46,717 lines`；operations 包
  `8 files / 2,100 lines`；`catalog.py` 734 行，保持既有门内；
- 当前修复只复用现有 Execution 身份和目录编译校验，不新增 Operation 字段或持久化事实。

### 5.7 TCAD、普通 Agent、资格和部署防退化：PASS

- 58 项非重叠风险扩展覆盖最小运行投影、Local/Hardened 能力、运行时插件配置、真实 Local TCAD、
  Codex 平台配置和部署入口；
- 14 项覆盖普通 Local Agent Run、独立 review/人工资格、M6-B Operation input admission 和 33 项
  约束注册表结构；
- 完整串行 257 项又覆盖 installed wheel/UI 生命周期、插件组合、Approval/Execution 恢复、
  qualification、Worker 边界及其余既有回归；
- 没有发现 M6-D 把执行身份或 URL 投影给 Worker，也没有合并科学资格与执行授权。

### 5.8 无测试/领域特判与奥卡姆检查：PASS

对 M6-D 关键 Root 路由和目录编译器扫描 TCAD、curve、InGaAs、fixture、pytest 和测试 Operation
名称均零命中。修复规则只读取通用 `OperationSpec` 端口、ExecutionRequest kind/Schema、不可变
Execution identity 和现有 ApprovalService 幂等合同。

没有保留需要本阶段追加的简化候选：

1. 恢复公开二步工具会重新引入遗漏步骤和重复合同组装，不是简化；
2. 新事务协调器、恢复表或清理任务会增加第二状态权威，稳定派生 identity 已以更小方式闭合故障；
3. `ExecutionService.authorize()` 的 exact ordered subjects 校验是承重安全边界，不能删除；目录编译期
   固定唯一合法顺序使 producer、projector、UI 决定和 authorize 消费同一合同；
4. `_ensure_execution_approval()` 对已有 binding 的逐字段比较继续保护漂移和篡改，不能为恢复重放而
   放宽。

## 6. 跨边界权威图

| 边界 | 唯一权威 | 复审结果 |
|---|---|---|
| Operation 声明 → catalog | `ApprovalContract` + compiled identity | PASS；反向顺序编译期拒绝 |
| preflight → invoke | 同一 compiled `BoundOperationCall` | PASS |
| Execution 创建/重放 | `ExecutionService` + execution semantic binding | PASS |
| Execution → Approval | 稳定 `apr_<execution_id>` + exact contract | PASS；五次故障仍一项 |
| Approval 展示 | compiled projector → 固定 `ReviewDocument` | PASS |
| 人工决定 | request-specific loopback UI | PASS；无聊天/Root 代写 |
| 决定 → start | exact identity + ordered request/payload subjects | PASS |
| start → sync/collect | 唯一 Execution lifecycle + adapter | PASS |
| Worker | 无 Approval/Execution/token 身份 | PASS |
| 平台/安装 | 当前 26 项 Root tool 投影 | PASS；旧工具不可达 |

## 7. 33 项约束复核

本复审只判断 M6-D 当前字节是否满足阶段门，不把 `pending_review` 批量改为 `conformant`。

- 首次 B1 涉及的 `AUTH-001/IMM-002/HIL-001/CQRS-002/RES-002`：当前稳定 request identity、单行
  重放、单 dashboard 项、单 exact 可授权候选和五次故障有界恢复均通过；
- 首次 B2 涉及的 `AUTH-003/ROLE-002/PLG-002`：畸形顺序在 catalog 编译期拒绝，正常 Effect 从声明、
  projector、ApprovalRequest、HumanDecision 到 authorize 只消费一个有序合同；
- `HIL-002`：科学资格与外部执行授权仍为两个独立 ApprovalContract 和两个决定；
- `CQRS-001`：本路径的 pending execution approval 不设置 expiry，status/list/readiness 不推进其逻辑
  决定或 Execution 状态；
- `EFF-001/EFF-002`：创建审批不等于 submit、领域完成或结果收集，未知提交规则未改变；
- `PLG-001`：核心无领域或测试特判；
- `MIG-001/MIG-002`：历史无 identity 不升级，当前平台/部署/installed 路径通过；
- `SEC-002`：Local `spawn_agent` 原生工具隔离仍是既有 `known_issue`，本阶段没有扩大，也没有虚假
  宣称关闭。

`tests/operations/test_architecture_constraint_matrix.py` 只证明 33 个稳定 id 和字段结构；本结论还依赖
B1/B2 独立生命周期反例、字段篡改探针和跨边界测试，不以结构测试代替语义证据。

## 8. 独立命令与结果

所有 Python/pytest 命令均使用：

```bash
ulimit -Sv 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

pytest 未使用 xdist 或任何并行选项。

### 8.1 独立内联探针

1. B1/B2 最终探针：**PASS**，输出见第 3、4 节；B1 连续 5 次故障，B2 的记录增量为 0；
2. exact contract/tamper 最终探针：**PASS**，正常七类字段精确，六类篡改失败关闭，自动
   decision/start/sync 均为否，adapter submit=0；
3. 结构探针：**PASS**，`root_tools=26`、`scheduler_tools=26`、ABI=11、OperationSpec=12 字段、
   5 个 SQLite owner/15 表。

审查过程中有三类探针夹具错误，均从全新临时状态修正后重跑，未计入产品失败或 PASS 证据：

- B1 第一稿的临时 adapter 漏实现既有 `prepare()`，只在人工决定后的显式 start 处触发
  `AttributeError`；补齐协议后完整重跑通过；
- 字段篡改第一稿把 request-first ReviewDocument 原样用于反向 subjects，被 ApprovalService 的
  JSON Pointer 校验更早拒绝；改用可创建的错误 subjects 请求后，Root 精确比较仍拒绝；
- 结构探针第一稿未设置 `PYTHONPATH=src`，第二稿错误假设五个服务共用一个 SQLite 文件；按当前
  runtime 的五个数据库 owner 重新枚举后通过。

### 8.2 最小聚焦回归

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_catalog_compile.py
```

结果：`51 passed in 40.48s`。

### 8.3 非重叠跨边界扩展

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l6_runtime_capabilities.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_l4_local_tcad.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/artifact_agent/test_deploy_scripts.py
```

结果：`58 passed in 44.96s`。

### 8.4 普通 Agent、资格与约束

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_l2_local_run.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_architecture_constraint_matrix.py
```

结果：`14 passed in 2.21s`。

### 8.5 完整串行回归

```bash
pytest -q -p no:cacheprovider
```

结果：`257 passed in 113.22s`。

### 8.6 静态与规模检查

- `git diff --check HEAD`：通过；
- `scripts/r5_current_metrics.py`：生产 Python `141/46,717`，operations `8/2,100`，catalog 734 行，
  generic-core domain token count=0；
- 旧工具名在生产源码/插件/包声明零命中；部署命中仅为退役负集合；
- M6-D Root/compiler 关键文件对领域和测试名称零命中；
- Root/Scheduler tool 投影、ABI、OperationSpec 字段和全新 SQLite 表面均由独立 Python 探针复算；
- 仓库不存在技能建议的 `scripts/validate_architecture_constraints.py` 或
  `scripts/run_science_control_bench.py`，因此没有虚构这两项命令结果；现有 33 项矩阵测试、目标反例和
  完整回归承担本阶段验证。

## 9. 剩余风险与不构成缺陷的边界

1. 当前是跨多个 R5 阶段的大型未提交工作树，不存在可单独复现的 M6-C→M6-D commit diff。本复审用
   当前关键 SHA、首次失败根因、修订证据指向的文件、生产路径和独立反例固定字节。这是可追溯边界，
   不是 M6-D 代码缺陷。
2. 本复审运行了真实 loopback dashboard、installed wheel/UI 生命周期和 Local TCAD 回归，但没有
   运行真实远端 solver、长时失联恢复或真实模型 Agent/TCAD 的 M7 纵向矩阵。这些仍属于 M6 整体终审
   与 M7 明确保留的发布门；当前 M6-D 没有修改远端 adapter 算法或模型行为，缺少这些昂贵门不否定
   已独立闭合的两个局部阻断。

## 10. 最终放行

R5-M6D 当前字节 **PASS**。

首次 FAIL 的随机审批身份恢复缺陷和 subject 顺序合同缺陷均已由独立反例证明关闭；没有发现新的
阻断或非阻断实质缺陷。

**唯一下一步判断：只放行“M6 整体回归与独立终审”。M7 继续不放行，本报告也不宣称 R5-M 完成。**
