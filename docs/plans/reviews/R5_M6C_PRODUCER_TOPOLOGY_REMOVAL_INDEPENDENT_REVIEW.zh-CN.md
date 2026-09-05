# R5-M6C“删除生产者下游拓扑预测”独立审查

日期：2026-09-02

审查者身份：未参与实现的普通代码独立审查者；本次不作为科学 Operation Worker，也未调用
instance/control/worker 工具。

## 1. 结论

**PASS。** 当前工作树中的 R5-M6-C 实现正确删除了生产者对未来下游用途的预测，没有建立替代的
全局用途图、注册表、兼容双路径或领域专用放行规则；精确 producer 身份、独立 reviewer、直接修订、
change request、Operation 级资格准入以及 explore/internal 不可 claim 边界均继续失败关闭。

- 阻断项：**无**。
- 非阻断项：**无代码缺陷**；有两项审计边界说明，见第 8 节。
- 33 项约束：本阶段未发现退化；不因本次测试通过擅自把 `pending_review` 晋级为 `conformant`，
  `SEC-002` 继续保持既有 `known_issue`。
- **唯一阶段放行判断：放行 M6-D；不提前放行 M7。**

任何实质缺陷都会使本报告结论为 FAIL；本次没有发现此类缺陷。

## 2. 审查基线与方法

审查仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`

- 分支：`baseline/8765-codex`
- `HEAD`：`404aeb14c6ebc4b08bac599db91eaee54c103f48`
- 工作树：包含 R5 前序阶段的大量已修改、删除和未跟踪文件；M6-C 的主要生产文件本身未被
  `HEAD` 单独跟踪，因而不能把 `git diff HEAD` 的 131 个文件总差异冒充 M6-C 专属补丁。
- 实际审查对象：当前文件字节、冻结 M2 ABI9 oracle、M6-C 新增/受影响测试，以及从 Root preflight
  到 Run/Transform 登记和下游 admission 的真实调用路径。

规范依据：

1. `docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 的 M6-C、33 项阶段门和自动停止条件；
2. `docs/plans/evidence/R5_M6C_PRODUCER_TOPOLOGY_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`；
3. `docs/ARCHITECTURE.zh-CN.md`；
4. `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
5. `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
6. 当前生产源码、插件声明、测试插件和测试。

审查遵循 `scid-cross-boundary-review`、`scid-find-simplifications`、
`scid-change-scope-checks` 和 `karpathy-guidelines`：先锁定权威和受影响路径，再寻找替代权威、
旁路、兼容层和不必要复杂度，最后从最小可信回归扩展到完整串行回归。

受审关键文件摘要：

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/operations/spec.py` | `ae7838bf9c9927535094dbc6c126ee88266e1b273c11ba57ddd8a6f1fd72396d` |
| `src/scidiscovery/operations/catalog.py` | `587beb27915359fd1d5898f775b46543b405fbb97c0398a2788a24bfbeaed9ed` |
| `src/scidiscovery/operations/invoke.py` | `53a498e7c416a70da6e0bf8dc92a465d2ccf6979d1c39906efc1609d07509ad4` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | `be4376ba3eb8edea929611e05d519eaf5f41bb5c6c38581428ac5f68c231c6ba` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_shared.py` | `6f574df7bf4d7effb7f96f6485cc4d48b46c5d2021eb52980542698386959de2` |
| `src/scidiscovery/artifact_agent/service/runs.py` | `2ee4253ccbee65358b2a063f688c7d2cd3408e0a5b28292f20b79c09339e3aba` |
| `tests/operations/test_m6c_producer_topology_removal.py` | `85c3b57cba071fe4692464f2bdecf060956ec103ee5a8583415f2a52a05b902a` |
| `tests/operations/test_l3_review_and_human_policy.py` | `bb79b6e6b2b05128a7d6c69e6ff8e0aaf7586cdc25baa56f2d4adf42e2a7e4a8` |

## 3. 九项重点独立核验

### 3.1 旧生产者用途权威已真实删除

PASS。

- `OutputPortSpec` 当前只声明输出自身的 kind、Schema、媒体类型、基数、大小、validator、
  semantic contract、collection、context 和 evidence path；不存在 `allowed_input_usages`。
- `FrozenSpec` 保持 `extra="forbid"`。独立探针把旧字段放回 `OutputPortSpec` 的序列化 payload，
  `model_validate(..., strict=True)` 抛出 `ValidationError`，不存在静默兼容读取。
- 冻结 M2 源的 `src/`、`plugins/` Python 中有 55 个 `allowed_input_usages` 命中；当前 `src/`、
  `plugins/`、`tests/fixtures/`、`scripts/`、`deploy/` 为零命中。
- 旧 `_operation_output_policy`、`producer_usage`、`output_usage_invalid` 等生产名称为零命中。
- `invoke.py` 的 `_AGENT_INPUT_USAGES` 只是消费者 Agent 输入语义的有界词汇校验，不包含
  producer→consumer 映射，不是被删权威的替身。
- `catalog.py` 顶层没有可变 dict/list/set；`CompiledCatalog` 仍只有一个。Root、Operation 和 Run
  路径中未发现用途图、跨插件依赖表或第二 preflight。

历史快照 `123/current-worktree-snapshot/` 和封存 deliverable 中仍可找到旧字段；它们不在当前
`src/`、插件入口或发布包的生产路径，不能构成兼容双路径。

### 3.2 Root 仍精确绑定 producer id/version/digest/output port

PASS。

`_operation_output_contract` 对带 Operation 来源标签的 Artifact 依次要求：

1. `operation_id` 必须在当前唯一 `CompiledCatalog` 中存在；
2. 当前 `spec.version` 必须等于冻结 `operation_version`；
3. 当前 compiled digest 必须等于冻结 `operation_digest`；
4. `operation_output_port` 必须是该精确 Operation 的已编译输出端口。

Agent 登记路径 `RunService._register_candidate` 和 Transform 登记路径
`_invoke_compiled_transform` 都写入这些冻结标签；Run 完成还消费同一 compiled Operation。
独立探针分别漂移 id、version、digest、port，得到：

| 漂移 | 结果 |
|---|---|
| operation id | `input_producer_contract_unavailable` |
| version | `input_producer_contract_changed` |
| digest | `input_producer_contract_changed` |
| output port | `input_producer_port_unknown` |

用户直接摄入、没有任何 Operation 来源标签的原始 Artifact 仍按原始输入处理；部分伪造来源标签不会
降级为原始 Artifact，而会失败关闭。

### 3.3 未审查 subject 只能进入精确 reviewer

PASS。

- 目录编译器要求 reviewer Operation 存在、executor 为独立 Agent、不能与 producer 复用 Agent
  component，并验证精确 reviewer input port 的 Schema、媒体、codec、Schema resource digest 和
  聚合 cardinality。
- Root 只在“当前 consumer Operation id 等于冻结 reviewer id，且当前绑定 port 等于冻结 reviewer
  input port”时允许未审查 subject 进入 reviewer。
- 其他消费者必须同时绑定一个已完成的精确 reviewer Run 输出；该 Run 必须在精确 reviewer input
  port 消费同一个 subject ref，且 handoff verdict 位于 producer 冻结的 accepted verdicts 中。
- 真实 Root/Local 路径的盲 CSV 用例验证：缺审查拒绝、精确审查通过、subject revision 后旧审查
  拒绝、新 revision 精确审查后重新通过。

未发现按 Schema 名、角色名、插件名或相似 parent 猜测 reviewer 的旁路。

### 3.4 revision 不继承旧审查，direct revision 与 change request 失败关闭

PASS。

- `direct_revision_ports` 只承认一个完整对象修订形状：一个必需 `revision_base`、一个非 collection
  主输出、相同 Schema/媒体/codec/Schema resource，以及一个精确独立 reviewer 合同。
- 目录在编译末端对所有声明 `revision_base` 的 Operation 重新调用该识别器；畸形修订合同不能进入
  compiled catalog。
- Root 对 base 的冻结 reviewer tuple 与 revision Operation 的 reviewer tuple 做精确相等比较；
  不同 reviewer 合同返回 `input_revision_review_contract_mismatch`。
- 若声明了 change request，它必须是冻结 reviewer Operation 在冻结 reviewer input port 对 exact
  base ref 产生的真实完成 Run 输出；否则返回 `input_change_request_mismatch`。
- revision 是新的 Artifact ref。`is_exact_reviewer_output` 按 exact subject ref 查询，因此旧对象的
  review 不会覆盖新 revision。盲 CSV 真实路径已验证这一点。

### 3.5 新 downstream usage 无需反向修改 producer

PASS。

独立探针分别编译原始 blind CSV 插件和只新增 `blind.csv.consume.v1` 的扩展目录：

- producer `blind.csv.observe.v1` 对象未修改；
- 新 consumer 自己把 `csv_observation` 声明为 `evidence_inventory`；
- 扩展前后 producer compiled digest 完全相同；
- 真实 Root preflight 在缺审查时拒绝，在绑定 exact review 时通过。

这不是仅凭“字段不存在”推断可扩展性，而是 consumer-only 扩展的真实目录和 Root 正负例。

### 3.6 explore/internal Agent 与 Transform 固有不可 claim，普通插件无额外状态

PASS。

- Agent 输出：`RunService._register_candidate` 在 `consequence == "explore"` 或
  `catalog_scope == "internal"` 时写入 `scientific_claim_admissible=false`。
- Transform 输出：统一 `_operation_artifact_labels` 使用相同条件；确定性 Transform 若从已标记的
  nonqualifying 输入派生，还会继续传播 false，防止机械洗白。
- Root 对非 explore consumer 的 `claim_evidence` 输入统一调用 `_claim_admissible`，false 标签和
  blocked/revise handoff 都会返回 `input_scientific_claim_forbidden`。
- 这一属性来自 Operation 固有 consequence/scope 和 Artifact 标签，不要求插件增加字段、表、
  qualification、approval 或 execution 状态。
- 数据库迁移和普通插件中未发现 M6-C 新增状态或持久化用途事实。

### 3.7 ABI11、旧 ABI9 oracle、目录摘要/行数门和完整回归

PASS。

- 当前 `OPERATION_ABI_VERSION = "11"`。
- 冻结 M2 tar SHA-256 为
  `bd8f548312cdf4eebcc4d3be9f261fb1640a94e9d0b42bf9b784c137706f6002`；其 `spec.py` 明确为 ABI9。
- M3 双进程 oracle 对当前源和冻结 M2 源分别启动隔离 subprocess，没有在生产源码增加 ABI9
  兼容字段；oracle 回归通过。
- core/general 当前 Operation digest summary 金丝雀通过。
- `scripts/r5_current_metrics.py` 实测 `catalog.py` 为 734 行；operations 包为 8 文件、2100 行，均在
  既有 738 行和 2103 行门内，唯一 successor path 仍是 `catalog.py` 自身。
- 完整串行回归：`255 passed in 112.80s`。

### 3.8 删除目录重复审批校验没有漏掉 approval executor 负例

PASS。

删除的是 `_validate_review_graph` 中已被覆盖的后置重复块，不是唯一保护：

- `_validate_operation_contracts` 在解析端口和 component 前就要求 approval executor 为 public、
  non-external、零输出、有 review、有 approval contract、executor component 精确等于 projector、
  且 `subject_ports` 精确等于全部 input ports；
- `ApprovalContract.issue()` 继续拥有 subjects、options、question、projector、kind、decision、
  reason 和长度/数量校验；
- `_validate_review_graph` 继续拥有 subject cardinality、Effect 精确合同、projector component 和
  provider edge 校验。

独立内联探针构造七个畸形 approval executor：non-public、external、带输出、缺 review、缺 approval
contract、executor/projector 不同、遗漏一个 input subject。七个均在目录编译期以
`approval_operation_invalid` 失败关闭。因而本次四行净删除没有丢失 approval executor 负例。

### 3.9 无定向补丁、兼容双路径或隐藏领域硬编码

PASS。

- 当前生产/插件/测试插件/脚本/部署路径中，旧字段和旧 output policy 名称零命中。
- Root admission、Operation compiler 和 Run 登记路径中对 `tcad`、`curve`、`figure`、`ingaas`、
  `blind_csv` 零命中。
- reviewer、revision、claim admissibility 和资格准入只按 compiled contracts、端口和 Artifact ref
  工作，没有按测试名、插件名、Schema 名或领域标签放行。
- 没有新增 adapter、alias、双写、fallback Registry、数据库表、Run 状态或第二目录。
- 保留的 `input_output_usage_forbidden` reason code 只用于“直接修订 base 没有可验证 producer
  contract”的既有失败关闭语义；它不读取旧 allowed-usage 数据，也不是兼容路径。

## 4. 跨边界路径复核

| 边界 | 当前唯一权威 | 复核结果 |
|---|---|---|
| 插件声明 → 编译 | `OutputPortSpec` 输出自身合同；`ReviewSpec` reviewer edge；`InputAdmissionSpec` 资格组 | PASS；无 producer 下游图 |
| Scheduler/Root → preflight | `_prepare_operation_call` 同时服务 readiness/preflight/invoke | PASS；无第二准入 |
| producer 身份 | Artifact 冻结 labels + 当前 `CompiledCatalog` | PASS；id/version/digest/port 精确 |
| 未审查 subject → reviewer | 编译 reviewer edge + exact operation/input port | PASS；其他 consumer 拒绝 |
| reviewer 输出 → consumer | 完成 Run + exact subject ref + accepted verdict | PASS；revision 不继承 |
| direct revision | complete-object shape + frozen reviewer tuple + exact change request | PASS；漂移失败关闭 |
| Agent 输出登记 | `RunService` + compiled Operation | PASS；explore/internal false |
| Transform 输出登记 | 通用 Transform 路径 + compiled Operation | PASS；false 固有/传播 |
| 资格与审批 | Operation 级 `InputAdmissionSpec` / 既有 ApprovalService | PASS；M6-C 未新增状态 |
| 插件与领域 | 单一 catalog、通用 core admission | PASS；无领域分支 |

## 5. 33 项架构约束复核

本次不是对所有历史 `pending_review` 项做全系统晋级，而是判断 M6-C 是否使任一项退化。

- `AUTH-001/AUTH-003`、`ROLE-002`：能力和 producer/reviewer/admission 身份仍来自同一个 compiled
  Operation；无第二权威。
- `IMM-001/IMM-002`、`LIN-002`：Artifact/ref 不变；revision 建新对象，旧 review 不继承。
- `TOP-001/TOP-002`：未增加阶段 DAG；readiness 和 invoke 继续共用 `_prepare_operation_call`。
- `DET-001/DET-002`：Transform 仍只做编译后的确定性输出，且 nonqualifying 机械传播未削弱。
- `HIL-001/HIL-002`：独立 review、科学资格和执行授权未合并；聊天仍不能成为决定。
- `CQRS-001/CQRS-002`：M6-C 只改声明和 admission，不在查询路径增加写状态。
- `PLG-001/PLG-002`：core 无领域名称分支；新 consumer 不要求反改 producer 或 core。
- `SEC-001/SEC-002`：未扩 Worker 工具、文件或来源权限；`SEC-002 known_issue` 保持原状。
- `RES-001/RES-002`：端口/Run 资源界限未删除；全部测试严格串行并限制 7 GiB 虚拟内存。
- `MIG-001/MIG-002`：ABI 提升没有在生产路径自动升级旧字段、旧 review 或旧资格；旧 ABI9 仅在
  封存 oracle subprocess 中运行。
- `EVD/UNC/EFF/UI` 组：本阶段没有修改其科学内容、Effect 生命周期或 UI 权威；完整回归未见退化。

`tests/operations/test_architecture_constraint_matrix.py` 独立确认 registry 仍恰有 33 个唯一、稳定顺序
的 id，且每项具备 requirement/prohibited/assessment/evidence。

## 6. 独立命令与结果

除只读 `git`/`rg`/`tar`/metrics 命令外，所有 Python/pytest 均设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

没有使用 xdist 或其他并行 pytest。

### 6.1 最小可信回归

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_l3_review_and_human_policy.py
```

结果：`36 passed in 2.44s`。

### 6.2 独立内联反例探针

使用当前源码和测试插件直接调用 `compile_catalog`、`_operation_output_contract`，并比较扩展前后
blind producer digest。探针包含：

- 7 个 approval executor 负例；
- 4 个 producer identity 漂移负例；
- consumer-only 新 `evidence_inventory` usage 的 producer digest 不变断言；
- 旧 `allowed_input_usages` 反序列化拒绝断言。

结果：

```text
7 approval-executor negatives closed; 4 producer identity negatives closed;
consumer-only extension preserves producer digest; legacy field rejected
```

### 6.3 扩展跨边界与冻结 oracle 回归

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_m3_transform_equivalence.py \
  tests/operations/test_m2_parameter_package.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_h2b_domain_boundaries.py \
  tests/operations/test_general_transform_operations.py
```

结果：`27 passed in 30.27s`。

### 6.4 33 项矩阵

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_architecture_constraint_matrix.py
```

结果：`1 passed in 0.04s`。

### 6.5 完整回归

```bash
pytest -q -p no:cacheprovider
```

结果：`255 passed in 112.80s (0:01:52)`。

### 6.6 静态、ABI 和规模检查

```bash
git diff --check HEAD
rg -n 'allowed_input_usages|producer_usage|operation_output_policy|output_usage_invalid' \
  src plugins tests/fixtures scripts deploy
rg -n 'tcad|curve|figure|ingaas|blind_csv' \
  src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py \
  src/scidiscovery/operations \
  src/scidiscovery/artifact_agent/service/runs.py
python scripts/r5_current_metrics.py
sha256sum archive/r5-m2-transform-oracle/m2-production-source.tar.gz
tar -xOf archive/r5-m2-transform-oracle/m2-production-source.tar.gz \
  src/scidiscovery/operations/spec.py | rg -m1 OPERATION_ABI_VERSION
rg -n OPERATION_ABI_VERSION src/scidiscovery/operations/spec.py
```

结果：

- `git diff --check HEAD`：通过；
- 旧权威和领域硬编码扫描：当前生产范围零命中；
- `catalog.py`：734 行；operations 包：8 文件/2100 行；
- 冻结 tar 摘要匹配；冻结 ABI9、当前 ABI11。

## 7. 未发现的简化反模式

本次应用奥卡姆审计后，没有保留新的删除候选：

- `_AGENT_INPUT_USAGES` 保护 Agent 输入语义边界，删除它会放宽模型可见合同，不应因名称相似而删；
- reviewer graph、exact reviewer Run 查询、direct revision contract 和 claim-admissible 标签各保护不同
  不变量，不是 `allowed_input_usages` 的重复替身；
- Agent 与 Transform 各自登记 false 标签位于两个真实提交边界。可以抽象成共享 predicate，但为一次
  两行条件创建跨 service/interface 依赖不会减少净复杂度，因此不建议在 M6-C 追加重构；
- approval executor 前置检查与 `ApprovalContract.issue()`、review graph 校验分工不同；当前只删除了
  完全覆盖的后置重复条件，没有继续误删承重检查。

## 8. 非阻断审计边界

1. 当前是跨多个 R5 阶段的大型未提交工作树，不存在可独立复现的 M6-B→M6-C Git commit diff。
   本报告用当前关键文件 SHA-256、冻结 ABI9 oracle、生产路径追踪和独立探针固定了实际受审字节。
   这是变更审计边界，不是当前 M6-C 代码缺陷。
2. 技能建议的 `scripts/validate_architecture_constraints.py` 在当前仓库不存在；直接运行得到文件不存在。
   历史独立审查也记录了这一仓库事实。本次没有误称该脚本通过，而是执行仓库实际拥有的
   `test_architecture_constraint_matrix.py`、逐项语义复核及完整回归。

未运行真实浏览器、远端 solver 或长时外部执行：M6-C 未修改 UI、Effect adapter 或远端恢复路径；
本阶段最小可信证据是目录/Root/Run/Transform/插件/installed-entry 测试和完整回归。M7 仍负责发布与
真实纵向总门，本报告不提前替代 M7。

## 9. 最终放行

R5-M6-C **PASS**。没有阻断项，没有需要条件修复的实质缺陷。

**唯一下一阶段判断：放行 M6-D；M7 继续未放行。**
