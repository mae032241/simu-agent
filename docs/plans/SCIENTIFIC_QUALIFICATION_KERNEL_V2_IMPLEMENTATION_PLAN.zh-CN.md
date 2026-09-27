# 科学资格内核 v2 重构实施计划与进度记录

更新日期：2026-08-22

状态：代码实施与本地验证完成；等待用户明确授权后部署。未执行重启、外部执行或历史数据迁移。

## 1. 计划地位

本计划取代“继续在 Root 中增加局部门禁”的修补路线，并补充
`SCIENTIFIC_OPERATION_CONTRACT_AND_KNOWLEDGE_CLOSURE_HANDOFF.zh-CN.md`
未覆盖的生产回执、实例级审批回执、精确 current、操作终态和外部提交不确定态。
旧 handoff 保留为 v1 实施历史，不修改其既有完成记录。

本计划不引入 LangGraph，不重写 Artifact CAS、TaskService、审批 UI 或领域科学 Schema。
重构对象仅限科学资格、current 和外部副作用提交边界。

## 2. 问题来源与根因

当前系统分别拥有不可变 Artifact、任务生命周期、context policy、确定性 transform、人工审批
和 selection generation，但仍把以下互不等价的事实混在 Root 的特例判断中：

1. 内容存在且完整；
2. 内容由某个合法操作产生；
3. 人工允许精确对象集合用于某种用途；
4. 对象是实例当前使用的精确版本；
5. 对象对眼前这个消费操作可采纳；
6. 外部副作用已经或可能已经发生。

结果是 labels、`parent_refs`、逻辑名、最新 revision、全局审批成员关系和角色/profile 组合
承担了本不属于它们的控制权威。长任务、审批晚到、合同升级和外部提交崩溃会进一步放大这些
混淆。

## 3. 冻结设计决策

### 3.1 五类权威事实

| 问题 | 唯一权威事实 |
|---|---|
| 精确内容 | `ArtifactEnvelope` / `ArtifactRef` |
| 合法生产 | `OperationReceiptRecord` |
| 人工资格 | 实例级 `QualificationReceiptRecord` |
| 当前状态 | 精确 `ActiveHeadTarget` 与单调 version |
| 外部副作用 | `EffectIntentRecord` / outbox 状态 |

Artifact labels、任务依赖、`parent_refs`、scheduler 逻辑名和 latest revision 仅作审计或展示，
不得建立上述事实。

### 3.2 双阶段门禁

```text
exact inputs
  -> admission preflight
  -> immutable OperationIntent
  -> worker / transform / control operation
  -> immutable OperationReceipt or OperationTerminalRecord
  -> optional human QualificationReceipt
  -> optional ActiveHead CAS
  -> downstream admission revalidates exact consumer inputs
```

任务在 current 改变后仍可完成并保留为历史候选，但不得自动激活或被不匹配的下游操作消费。

### 3.3 同库事务边界

实例状态、OperationIntent、ReviewIntent、ActiveHead 和 Effect outbox 使用现有
`scheduler-bindings.sqlite3` 的同一 SQLite 事务。Artifact、Task 和 Approval 仍保留各自数据库；
跨库采用 fail-closed 顺序和幂等 reconciliation，不伪造分布式事务。

### 3.4 协议版本

- 新实例在最终切换后使用 control protocol v2；
- 历史 v1 实例只读，显示 `legacy_requalification_required`；
- 不按 labels 或历史父链自动升级资格；
- 原始来源可通过显式 intake 在新实例中复用；
- 派生科学对象只有通过 operation-specific requalification 或重新执行才能进入 v2。

## 4. 正式数据模型

新增 `schema/scientific_control.py`，定义：

- `OperationInputBinding`：task-local source alias、精确 ArtifactRef、usage；
- `RequiredHeadSnapshot`：head key、精确 target、version；
- `OperationIntentRecord`：实例、原始目标摘要、合同版本/指纹、精确有序输入、依赖、指令摘要、
  预算、required-head snapshot 和请求指纹；
- `OperationOutputBinding`：受合同拥有的 output slot、精确 ArtifactRef、collection/item；
- `OperationReceiptRecord`：Intent、成功 producer/attempt、主输出、全部附件、冻结 web/PDF 证据、
  scheduler signal 和完成时间；
- `OperationTerminalRecord`：cancelled、failed、timed_out、contract_runtime_unavailable；
- `ScientificReviewIntent`：实例、目标摘要、合同、精确 subject bundle、选项和展示清单摘要；
- `ScientificReviewOutcome`：accepted、rejected、expired、cancelled；
- `QualificationReceiptRecord`：仅从 accepted outcome 产生，声明允许用途和例外；
- `QualificationWithdrawalRecord`：撤销旧资格但不改写旧回执；
- `ActiveHeadTarget`、`ActiveHeadTransition`；
- `EffectIntentRecord`：外部副作用 payload、资格回执、current snapshot 和稳定 idempotency key；
- `PreflightDecision`：允许/拒绝、稳定 reason code、精确 facts 摘要。

所有不可变记录使用 canonical JSON 和 SHA-256。内部 ID 不进入 worker assignment，也不暴露给
scheduler；scheduler 只使用稳定语义名。

## 5. 控制数据库

由一个统一 migration owner 在 `scheduler-bindings.sqlite3` 中创建：

### 5.1 不可变表

- `scientific_operation_intents`
- `scientific_operation_bindings`
- `scientific_operation_receipts`
- `scientific_operation_terminals`
- `scientific_review_intents`
- `scientific_review_outcomes`
- `scientific_qualification_receipts`
- `scientific_qualification_withdrawals`
- `scientific_head_events`

### 5.2 可变索引/生命周期表

- `scientific_active_heads`
- `scientific_effect_outbox`
- `scheduler_binding_reservations`
- `control_schema_versions`

同一实例和请求指纹重复调用返回同一个 Intent；完整请求不同必须显式创建 revision。
generation/version 只作 CAS precondition，不作为科学请求身份。

## 6. OperationSpec

扩展 `scientific_operation_contracts.py`：

```text
operation_key
contract_version
contract_fingerprint
effect
executor_kind
role / context_profile / output_profile
input_slots
output_slots
required_heads
accepted_producer_contracts
parameter_policy
activation_policy
evidence_collection_policy
budget_ceiling
semantic_validator_id
implementation_version
```

OperationSpec 负责科学资格；TaskContextPolicy 继续负责 exposure、数量和字节限制；role output
contract 继续负责 worker 文件格式。启动时交叉验证三者，拒绝不一致、重复或未注册的 effectful
操作。首版只使用普通 dataclass 和操作专用 validator，不实现 policy DSL 或递归证明引擎。

## 7. 必须补齐的八个边界

1. **操作终态与重试**：同一 Task 的 attempt 共享 Intent；仅最终成功 attempt 生成唯一 Receipt；
   重试耗尽或显式放弃写 TerminalRecord；迟到失败不能覆盖成功。
2. **实例归属**：Intent 事务内确认实例 active；输入必须属于当前实例，或有显式 raw-source
   import receipt；不同实例不能共享审批或生产资格。
3. **dependency 与 lineage 分离**：task dependency 只决定运行顺序；科学 lineage 只来自 Intent
   的精确 Artifact 输入。改变 dependency 会改变请求指纹。
4. **ActiveHead 权限矩阵**：objective/foundation/parameters/uncertainty/plan/knowledge 各有固定
   修改者；新 revision 永不自动 current；knowledge 禁止人工回退。
5. **审批拒绝终态**：accepted/rejected/expired/cancelled 都生成实例级 ReviewOutcome；只有
   accepted 可产生 QualificationReceipt。
6. **合同运行时缺失**：注册表自身不一致阻止启动；历史合同缺失仍允许只读；未完成 Intent
   标记 `contract_runtime_unavailable`，不得换角色、profile 或 adapter。
7. **唯一 migration owner**：统一 schema version 和 `BEGIN IMMEDIATE` migration，禁止两个
   service 并行独立迁移同一数据库。
8. **外部不确定态**：execution start/cancel/collect 和 TCAD debug submit/recovery 都必须使用
   outbox/idempotency；无法按 key 查询时进入 `submission_unknown`，禁止自动重提。

## 8. ActiveHead 权限矩阵

| Head | 唯一合法更新来源 |
|---|---|
| `research_objective_contract` | 通过 scope-alignment 审核的显式选择 |
| `scientific_foundation` | accepted foundation QualificationReceipt |
| `device_parameter_group` | accepted 完整参数组 QualificationReceipt |
| `parameter_uncertainty` | 精确 parameter-group 的 deterministic projection |
| `experiment_plan` | scheduler 显式选择的已资格化 plan |
| `knowledge_state` | strict knowledge-transition CAS |

审批晚到可以形成历史 receipt，但 automatic activation 必须使用原 head snapshot 做 CAS。

## 9. 参数状态机

OperationSpec 的 parameter policy 只能是：

- `none`：禁止消费参数组；
- `resolve`：提取、审核或修订参数阻断；
- `if_active`：存在参数组时必须绑定完整组及 uncertainty；
- `required`：必须存在完整参数组及 uncertainty。

| 状态 | 行为 |
|---|---|
| 无已审核参数集 | 非参数操作可继续 |
| 已审核参数组、无 uncertainty | `parameter_projection_required` |
| required + unbounded | 阻断消费操作，保留证据修订能力 |
| fixed / bounded tunable / deferred unused | 绑定完整组和 uncertainty 后继续 |

未知值只有结构化 `tuning` 声明才能成为调参项。ExperimentDesignIntent 必须将每个 tunable
映射到完整获批候选集或显式 frozen baseline。

## 10. 可靠提交和 reconciliation

### 10.1 Worker

Intent -> Task schedule -> worker finalize -> Task completed -> OperationReceipt。
Task completed 与 Receipt 之间崩溃时，任务保留但不可科学消费；`task_status`、`task_outputs`、
readiness 和启动恢复器幂等补建 Receipt。

### 10.2 Transform

Intent -> adapter bytes -> contract-owned output validation/registration -> Receipt -> semantic binding ->
optional head CAS。adapter 不能在运行时决定输出 kind/schema。

### 10.3 Review

ReviewIntent -> ApprovalRequest -> HumanDecision -> ReviewOutcome -> optional QualificationReceipt ->
optional head CAS。所有资格消费入口在 preflight 前执行有界 reconciliation。

### 10.4 External effect

同库 preflight + outbox commit -> adapter submit(idempotency key) -> lookup/reconcile -> external id。
没有幂等能力且结果不明时永久停在 `submission_unknown`，直到人工管理恢复。

## 11. 科学操作覆盖

### 11.1 证据

- text/no-paper intake；
- device parameter intake；
- figure extraction；
- foundation/device/figure/revision audit；
- bounded scientific revision；
- unchanged-evidence receipt；
- final scientific-foundation review。

### 11.2 假设与实验

- ideation；
- portfolio critic；
- hypothesis-bound evidence audit；
- candidate eligibility；
- scientific/engineering experiment design；
- design revision；
- plan materialization；
- curve-reference coverage。

### 11.3 TCAD 与闭环

- author/revision/reviewer；
- project materialization/package；
- execution approval/start/cancel/collect；
- runtime attestation/control equivalence/curve score；
- strict diagnosis/curve-error analysis/baseline provenance diagnosis；
- knowledge transition。

no-paper、baseline replay、baseline provenance、deck revision、engineering-only 和 result diagnosis
使用独立 OperationSpec，不依赖“缺少部分输入”的默认路径。Advisory output 只能进入
`prior_signal`、`revision_base`、`change_request` 或 `evidence_inventory`。

## 12. Readiness

readiness 不再按 Artifact kind presence 推断能力，而是：

1. 展示 inventory；
2. 展示 ActiveHead；
3. 从 OperationReceipt 索引构造精确合法 join；
4. 对每个候选调用与正式 authorize 相同的 kernel preflight；
5. 多个科学候选返回 `choice_required`，不自动选择 latest。

强性质：状态不变时，readiness 宣称 ready 的 exact bundle 必须能被 authorize 接受。

## 13. 实施阶段与验收门

### P0：基线和失败矩阵

- 保存当前 dirty worktree，不 reset、不覆盖用户修改；
- 记录聚焦与全量测试基线；
- 枚举 Root/Worker mutating tools 和 adapter effects；
- 为 new revision current、伪造 producer、跨实例 approval、参数无 projection、长任务陈旧、
  review 晚到、合同不兼容、external unknown 和 readiness parity 建立负例。

验收：每个缺陷有直接测试，失败原因落在目标边界。

### P1：Schema、统一 migration 和控制存储

- 新增控制 Schema；
- 增加 control schema migration；
- 实现 Intent/Terminal/ReviewOutcome/Receipt/Head/outbox 的最小 store；
- 增加多进程 reservation 和 ActiveHead CAS 测试；
- 暂不接管 live Root 行为。

验收：不可变记录幂等、不同请求冲突、head CAS、关闭实例拒写、同库恢复测试通过。

### P2：OperationSpec 与纯 Kernel

- 扩展完整合同；
- 合并 core/plugin specs；
- 实现稳定 reason code；
- 增加 Root/Worker effect-entry coverage 静态测试。

验收：缺输入、输出、validator、profile 或 effect registration 时启动失败。

### P3：Producer receipt

- task schedule 接入 operation key 和 Intent；
- TaskService 内部记录 intent，不传 worker；
- completed->receipt reconciler；
- transform output semantics 归合同所有；
- SecureIntake 产生 raw-source receipt；
- dependency 与 lineage 分离。

验收：labels、parent_refs、task dependency 和手工同形 payload 都不能伪造 producer。

### P4：Review、current 和参数纵向切片

打通 device extraction -> coverage -> audit -> review -> QualificationReceipt -> uncertainty ->
parameter-aware role。审批 UI 保留折叠参数矩阵、直接来源链接和科学计数法。

验收：跨实例、部分审批、缺 projection、未声明 tuning、撤销 receipt 全部 fail closed。

### P5：idea/critic/evidence/experiment/revision

迁移 new-mechanism 路径和实验物化；critic/auditor/reviewer 的额外检索最多六个新冻结来源，
全部进入 Receipt evidence closure。

验收：同一 portfolio 的 critic+audit join、完整 tunable 映射、受控 revision 和 plan materialize
纵向测试通过。

### P6：TCAD project 与外部 effect

- author/reviewer/package；
- execution start/cancel/collect outbox；
- adapter idempotency capability；
- debug submit/recovery 不确定态；
- execution result mechanical receipt。

验收：每个故障注入点只产生安全候选或 `submission_unknown`，不重复提交。

### P7：diagnosis 与 knowledge

- scorer/control-equivalence producer receipts；
- strict/advisory diagnosis 分离；
- curve-error analysis；
- knowledge state exact-head CAS。

验收：validation report、advisory diagnosis、历史 knowledge head 不能推进知识。

### P8：readiness、维护、迁移和删除旧权威

- readiness 使用 preflight；
- orphan cleanup 使用 Intent/Receipt/Review/Head/outbox 可达性；
- instance deletion 纳入新表；
- v1 只读、v2 切换；
- 删除 latest-current、全局 approval、label/parent producer、legacy knowledge/experiment 路径；
- 更新 scheduler、roles、docs。

验收：不存在同一实例的双权威路径；完整 E2E、并发、fault injection 与全量测试通过。

## 14. 故障注入矩阵

必须覆盖：

1. Intent 已写、Task 未创建；
2. Task completed、Receipt 未写；
3. transform outputs 已登记、名称未绑定；
4. HumanDecision 已写、ReviewOutcome/QualificationReceipt 未发；
5. Receipt 已写、ActiveHead CAS 失败；
6. outbox 已写、submit 未发生；
7. submit 成功、external id 未落库；
8. adapter 无 lookup-by-key；
9. 在途任务跨合同版本部署；
10. reconciliation 前执行 orphan cleanup；
11. 同一 Intent 多 attempt 的迟到完成/失败竞态；
12. 实例关闭与 Intent 创建并发。

每个场景必须证明：不产生错误资格、不自动 current、不重复外部副作用、重试幂等且状态可恢复。

## 15. 完成标准

- 每个 scientific mutation 有 OperationIntent；
- 每个可消费产物有 OperationReceipt；
- 每个人工资格是实例级 QualificationReceipt；
- 每个 current 是精确 ActiveHead；
- 每个永久失败/取消操作有 TerminalRecord；
- readiness 与 authorize 共用 preflight；
- 参数审批和 uncertainty 之间没有零输入绕过；
-所有 submit/cancel/debug 使用 outbox 或进入 unknown；
-不兼容合同必须 requalification；
- orphan cleanup 不删除权威记录可达对象；
- no-paper、参数感知新机制、论文曲线复现、baseline provenance、engineering-only 五条 E2E 通过；
-完整现有测试、并发测试、故障注入、compileall 和 `git diff --check` 通过；
-用户明确授权前不部署、不重启、不执行真实外部求解。

## 16. 开发进度记录

### 当前摘要

- 当前阶段：P8 完成
- 当前动作：资格内核 v2 的代码、角色协议、维护边界、迁移隔离和文档已收口；本地最终
  全量回归通过，下一动作仅能在用户明确授权后执行部署与运行态 smoke test。
- 部署状态：未部署、未重启。
- 数据迁移状态：未迁移历史实例。

### 完成记录

- 2026-08-21：完成架构逆向审查；确认双阶段资格、实例级 review receipt、精确 ActiveHead、
  合同指纹、outbox 和 fail-closed reconciliation 为必需边界。
- 2026-08-21：补入 OperationTerminal、ReviewOutcome、实例归属、dependency/lineage 分离、
  ActiveHead 权限矩阵、旧合同运行时缺失、唯一 migration owner 和 debug/execution unknown 八项闭环。
- 2026-08-21：P0 完成。聚焦基线 75 项全部通过；完成 Root/Worker/adapter effect-entry
  inventory，并确认 TCAD debug 的 `submitting` 恢复路径存在直接重提风险，留待 P6 通过 outbox
  和 `submission_unknown` 关闭。
- 2026-08-21：P1-A 完成。新增严格 scientific-control Schema 及 10 项 Schema 测试。
- 2026-08-21：P1-B/C 完成主体。由 `SchedulerBindingService` 唯一初始化同库控制表；新增
  Intent、Terminal、Receipt、binding reservation 和 ActiveHead CAS 服务。13 项存储测试通过，
  包含多进程 revision 分配唯一性和 ActiveHead CAS 单一胜者。
- 2026-08-21：P1-D/E 完成。新增 ReviewIntent/Outcome、accepted-only QualificationReceipt、
  append-only Withdrawal，以及 EffectIntent/outbox CAS 状态机；`submission_unknown` 不能回到
  `ready/submitting` 自动重提。Schema/Service 28 项、阶段聚焦回归 111 项、compileall 与
  `git diff --check` 全部通过。
- 2026-08-21：P2-A 完成。新增向后兼容的 v2 `OperationSpec`、输入/输出槽、required-head、
  parameter/activation/evidence policy、预算上限和 canonical contract fingerprint；启动时已交叉
  验证 worker context profile 与 role output contract，core/plugin 同名 spec 拒绝覆盖。
- 2026-08-21：P2-B 完成。新增无 I/O 的 facts -> `PreflightDecision` 内核；覆盖 producer receipt、
  实例归属、schema/kind、qualification exact bundle/use/withdrawal、ActiveHead、参数 group/
  projection/unbounded 和额外冻结证据。P2 扩大聚焦回归 121 项通过。
- 2026-08-22：P2-C 完成。36 个 Root 和 31 个 Worker/兼容入口具有精确 authority inventory；
  generic transform/task/review 使用 operation-key allowlist，外部入口只能绑定静态 execution
  spec。Root/Worker router 启动时验证完整登记，缺入口、缺 spec、错误 executor/effect 均 fail
  closed。
- 2026-08-22：P2 并发复核发现旧 ActiveHead 实现仍是“事务内读取 + 无条件 UPSERT”，压力下
  不能以数据库条件证明单一胜者；已改为 SQL 条件 INSERT/UPDATE CAS，并让返回值绑定本次
  transition 而非提交后的可变 current。多进程测试改用独立 `spawn` 语义，避免 fork 继承
  SQLite/WAL 状态。连续 CAS 压测与 P2 阶段 234 项回归通过。
- 2026-08-22：P3-A/B 完成最小 source-intake 纵向链。`artifact_ingest_file` 的 v2 路径先原子
  reservation、再写 Intent；Artifact 成功后写控制面 producer Receipt，最后绑定语义名称。
  Artifact/Receipt、Receipt/名称两个崩溃窗口均可通过相同不可变请求恢复，且不会复制 Artifact；
  精确 Artifact producer 增加实例级唯一索引，跨实例查询不继承生产者。
- 2026-08-22：P3-C 完成受治理 transform 纵向链。`artifact_transform` 的 v2 路径要求显式
  operation key，输入必须具有同实例且受当前合同支持的 producer Receipt；executor label 到
  contract output name 的映射、kind、schema 和输出预算均由 `OperationSpec` 所有。所有输出登记
  后先原子写一个完整 Receipt，再绑定主输出和派生输出名称；覆盖 outputs/Receipt 与
  Receipt/binding 两个故障注入窗口。顺带修复 experiment-plan 与 knowledge-update Spec 的真实
  输入/输出形状、source-intake kind，以及“初始 head 缺失不能作为精确 CAS 前置条件”的 Schema
  缺口。
- 2026-08-22：P3-D 完成。`task_schedule` 使用 operation reservation/Intent 后创建确定性 Task，
  Task 仅内部保存 Intent 关联，worker assignment 不泄露控制 ID。成功 finalize 后 reconciler 按
  当前精确合同收集 primary、全部 collection attachments、scheduler signal 和已冻结 web evidence，
  原子生成一个 Receipt；失败/超时且 attempt 耗尽生成 Terminal 而不生成 Receipt。
- 2026-08-22：补齐 `device_parameter_evidence_extraction` 的真实集合合同，证明主
  `scientific_intake` 与 requirements/parameters/source_catalog 三个附件共同进入同一 Receipt；
  task outputs 只能在 Receipt 完整后绑定。覆盖 Intent/Task、Task/Binding、completed/Receipt、
  并发同请求、失败和 dispatch timeout 恢复窗口，P3 聚焦 41 项通过。
- 2026-08-22：P4 完成。新增 intake projection、parameter coverage、device-parameter audit、
  foundation review 和 uncertainty projection 合同；UI 决策现在 reconciles 为实例级
  ReviewOutcome/QualificationReceipt，拒绝/过期/取消不发资格。一次参数审批以同事务 CAS 原子
  激活 foundation 与完整 parameter group；晚到审批仅保留历史资格。uncertainty 投影使用带
  read-only head guards 的 CAS，参数组在投影期间改变时不激活结果。
- 2026-08-22：ideator 默认 context 可接收且在 active parameter group 存在时必须接收完整获批
  foundation/requirements/values/catalog/coverage/audit 与精确 current uncertainty。无 projection、
  blocking-unbounded、部分组或撤销资格均 fail closed；结构化 engineering-prior tuning 被投影为
  bounded tunable 后可进入 idea 层。P4 聚焦回归 123 项通过。
- 2026-08-22：P5 完成。新增无论文 text evidence intake、foundation audit、portfolio-bound
  critic/auditor、candidate eligibility、objective projection、scientific experiment design、
  structured revision/apply、unchanged-evidence receipt、delta critic/audit 和 plan materialization
  的 v2 合同。冻结证据 closure 可接收由同实例 Receipt 持有的动态来源，而非要求把来源别名硬编码
  到合同。
- 2026-08-22：两条纵向链通过：其一为 no-paper objective -> review -> idea -> 两个独立 review ->
  eligibility -> design -> bounded intent revision -> complete plan；其二为 assumed parameter ->
  approve-with-exception -> uncertainty -> parameter-aware idea/reviews -> eligibility -> design，证明
  tunable 必须映射完整候选集和独立 contrast 后才能物化。portfolio revision 的旧 review 不能与新
  revision join；同证据 delta receipt 可走独立 delta review，证据声明变化仍由 receipt transform
  fail closed 并回退 full audit。
- 2026-08-22：P6 完成。TCAD 插件通过独立 entry point 注册 initial/revision author、reviewer、
  project diff、review validation 和 reviewed package 七个 OperationSpec；运行时合并 core/plugin
  合同并拒绝同名覆盖。reviewed package 绑定精确 current experiment plan，并携带完整获批参数组与
  uncertainty lineage。
- 2026-08-22：execution request、独立 UI authorization、start、cancel、terminal collect 和 logical
  output registration 全部进入 v2 Intent/Qualification/Effect/Receipt 链。提交、取消和收集采用 durable
  outbox claim；远端调用后本地状态不明时停在相应 unknown 状态。TCAD development debug 同样删除
  `submitting` 自动重提，并为 submit/collect/cancel 三个响应丢失窗口增加不重复调用测试。
- 2026-08-22：P7 完成。runtime-attestation、control-equivalence 和两个 versioned curve scorer
  通过插件 OperationSpec 产生精确 Receipt；动态输入/输出集合也进入同一不可变 Receipt。
  strict、curve-error、advisory 和 baseline-provenance diagnosis 已分离，TaskService 按实际 Intent
  合同而非 role/profile 猜测 claim 权限。knowledge update 只接受通过 scheduler signal 的严格
  diagnosis Receipt，校验 exact plan/runtime/package/metric/hypothesis 闭包与 current plan，并通过
  exact knowledge-head CAS 拒绝 validation report、advisory、迟到计划、历史 head 和重复诊断迁移；
  同一语义请求重放仍幂等。P7 跨模块聚焦回归 168 项通过。
- 2026-08-22：P8 完成。`scientific_readiness` 现在从精确 ActiveHead、同实例 producer Receipt、
  Qualification、scheduler signal 和共用 operation preflight 生成；strict diagnosis 必须绑定当前
  plan 的完整 runtime/control/metric/hypothesis 闭包，历史诊断不再触发 claim 或 knowledge。
- 2026-08-22：orphan cleanup 与 instance deletion 的可达根纳入 Intent、Receipt、Terminal、
  Review、Qualification、ActiveHead、reservation 和 effect outbox；v2 实例关闭在同一
  `BEGIN IMMEDIATE` 事务中拒绝未完成操作、待解释 review、accepted-but-unqualified review、
  未收集 effect 和未绑定 reservation。
- 2026-08-22：新实例显式使用 protocol v2；无 v2 控制事实的历史实例保留为 v1 只读，生产 Root
  阻止新的科学 mutation，也不再让 `task_status` 隐式发布旧任务输出。生产 MCP/CLI 已注入同一
  `ScientificControlService`，插件 OperationSpec 可从源码树可靠发现。
- 2026-08-22：`task_evidence_sources` 从伪只读接口改为 task-operation publication；只有任务成功
  finalization 且完整 producer Receipt 存在后，才发布当前 attempt 中精确列入 Receipt 的 web
  snapshot/PDF excerpt。角色与中英文架构文档同步完成。

### 待办队列

1. 用户授权后执行安装/重启；部署前保留运行态数据备份并使用现有事务化安装入口。
2. 部署后只做本地控制面 smoke test：实例绑定、readiness、审批展示和维护预览；真实 TCAD
   执行仍需独立 execution approval。
3. 历史 v1 实例保持只读；如需继续其研究目标，在新 v2 实例显式重新 intake/requalification，
   不执行自动资格迁移。

### 验证日志

- 2026-08-21：重构前聚焦基线：75 passed。
- 2026-08-21：scientific-control Schema：10 passed。
- 2026-08-21：scientific-control Service：13 passed。
- 2026-08-21：Schema/Service/Scheduler 组合：34 passed（补并发 CAS 前）。
- 2026-08-21：Schema/Service/Scheduler/Runtime 配置组合：42 passed（补并发 CAS 前）。
- 2026-08-21：`python -m compileall -q src/scidiscovery/artifact_agent tests/artifact_agent`：通过。
- 2026-08-21：P1 Schema/Service 最终组合：28 passed（10 Schema + 18 Service）。
- 2026-08-21：P1 阶段聚焦回归：111 passed。
- 2026-08-21：P1 阶段 `compileall`、`git diff --check`：通过。
- 2026-08-21：P2 OperationSpec/Kernel/扩大聚焦回归：121 passed。
- 2026-08-21：P2-A/B 全量回归：870 passed，6 个既有 `datetime.utcnow()` deprecation
  warnings；无失败。
- 2026-08-22：P2 effect-entry/并发/Router 阶段回归：234 passed。
- 2026-08-22：ActiveHead CAS 独立进程连续压测：10/10 passed；Service：18 passed。
- 2026-08-22：P3 source-intake Receipt/恢复与 control store 组合：23 passed。
- 2026-08-22：P3 transform Receipt/合同/恢复聚焦组合：45 passed；producer 合同负例增补后
  16 passed；`compileall` 与 `git diff --check` 通过。
- 2026-08-22：P3 task/collection/terminal 与 source/transform/control 组合：41 passed；
  `compileall` 与 `git diff --check` 通过。
- 2026-08-22：P4 parameter review/current/uncertainty/ideator 与扩大回归：123 passed；
  `compileall` 与 `git diff --check` 通过。
- 2026-08-22：P5 跨模块聚焦回归：138 passed；修订/任务/实验子集 60 passed；两条新增纵向
  E2E 单独通过；`compileall` 与 `git diff --check` 通过。
- 2026-08-22：P6 TCAD/project/execution/debug/contract 聚焦回归：159 passed；TCAD debug 独立
  35 passed，execution/contract/outbox 子集 32 passed；`git diff --check` 通过。
- 2026-08-22：P7 diagnosis/curve/knowledge 跨模块聚焦回归：168 passed；新增严格知识纵向链
  4 项负例/恢复测试通过。
- 2026-08-22：P8 maintenance/readiness/protocol/Receipt 收口聚焦回归：45 passed；实例关闭五类
  未完成控制记录、v2 evidence publication 和 v1 status 真只读负例均单独通过。
- 2026-08-22：第一次 P8 全量回归：929 passed，6 个 Python `datetime.utcnow()` deprecation
  warnings；随后将 Python 3.6 remote runner 改为 timezone-aware UTC 取时并保持原有 `Z` wire format。
- 2026-08-22：最终代码树全量回归：930 passed；SSH transport/remote-runner 19 项通过且不再产生
  上述 warning；`compileall` 与 `git diff --check` 通过。

### 已知实施约束

- 当前 worktree 包含大量既有未提交修改；不得 reset、checkout 或覆盖无关文件。
- `mcp_root.py` 和 `tasks.py` 已较大；新资格逻辑优先进入职责单一的新模块，Root 仅保留适配。
- P1 新代码不改变现有 live 行为，降低与既有修改的冲突；权威切换从 P3/P4 的纵向切片开始。
