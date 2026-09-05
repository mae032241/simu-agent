# R5-G：直接完整对象修订简化计划

状态：方案第二轮独立复审已通过；D0 实现已通过独立审查；D1 经三轮独立实现审查后通过；D2
最后实际消费者迁移已经独立审查通过，只放行 D3。首轮方案审查提出的 F1—F5 阻断已全部写回并
闭合。未经审查的“非通过评审放行结构化补丁”半修复已经撤销，旧失败已由特征测试冻结。D3 经
两次实质打回和一次机械冻结修正后已通过独立审查，只放行 D4。D4 runner 与一次性 ABI 8
状态代际转换与 D4-Q 已真实完成并通过后置独立审查。D4-H 首轮与独立诊断只放行的唯一一次
D4-H2 均已完成，两个新 critic 都判定 `blocked`；第三轮修订与实验设计已按停止门关闭。最终后置
独立复核确认实现与停止门通过、科学结果未通过；全仓回归与发布清单已闭合。R5 发布冻结仍未放行。

上位约束：

- [OperationSpec 中心的最小重构计划](OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md)；
- [R5 控制重量删除计划](R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md)；
- [当前架构](../ARCHITECTURE.zh-CN.md)。

## 0. 开发和测试问题处理原则

D0—D4 的任何开发或测试问题都必须先归入以下一种主要原因，并把判断写入阶段记录：

1. 架构所有权或抽象错误；
2. OperationSpec/端口/评审合同错误；
3. 普通局部实现缺陷；
4. 测试或冻结夹具错误；
5. 外部环境问题。

只有第 3 类且修复完全落在既有唯一所有者和已审查合同内，才允许直接做局部修复。出现以下任一
迹象必须立即停止编码，回到本计划并重新独立审查，不能为了测试变绿继续缝补：

- 需要按 operation id、Schema、插件名、角色名或端口名增加核心特判；
- 需要新增第二个资格、来源、current、修订或 readiness 权威；
- 同一失败在相邻层分别增加准入例外；
- 新增的状态、收据、实体或 guard 只是为了补偿不自然的数据流；
- 测试只能通过降低门槛、伪造科学对象、跳过真实入口或继承旧 verdict；
- 修复代码明显大于被删除的旧责任，且不能指出新的必要不变量。

每个独立审查报告除正确性外，必须回答“本阶段是在消除根因，还是把断裂移到下一层”。出现新的
架构问题时，允许修改本计划甚至打回当前方案；既有测试和已投入工作量不能成为保留不合理设计的
理由。

## 1. 问题与结论

R5-G 的真实假设批评以 `blocked` 结束后，系统暴露出“对象必须修订，但未通过评审的对象又不能
进入修订”的死锁。最初的局部修复尝试为结构化补丁生产和补丁应用分别增加特殊准入，独立审查
随即发现两段链路仍会互相阻断。

这不是缺少一个准入条件，而是修订抽象过重：

```text
旧对象
  → 修订 Agent 只输出 StructuredRevision
  → 确定性 Apply 生成完整对象和 RevisionDiff
  → UnchangedEvidenceReceipt 证明证据未变
  → 特殊生产者族递归恢复原来源
  → 新的独立审查
```

该设计把不可变版本控制、科学内容修改、界面差异展示和证据复核绑成一条强制控制链。修订对象
越多，核心越需要识别补丁、应用器、差异、收据和原生产者族，最终形成当前的行为断裂。

本计划改为：

```text
精确旧对象 + 本次修订指令 + 必要科学上下文 + 可选精确评审意见
  → 原对象所属的专业 Agent 输出完整新对象
  → 控制层按原输出 Schema 校验并封存不可变父链
  → 原类型的独立审查者重新审查新对象
  → 只有新评审通过，普通下游才可消费
```

旧对象保持不可变。所谓“直接修订”是产生完整的新版本，不是覆盖旧字节。

## 2. 权限边界

“修订 Agent 可以修正任何实体内容”在本框架中的准确含义是：

1. 调度器为一次调用绑定一个精确的旧实体；Agent 不获得全库写权限；
2. Agent 可以修改该实体输出 Schema 内的任何科学内容，不受通用控制层的字段白名单约束；
3. Artifact 标识、摘要、版本、父链、任务身份和评审资格由控制层生成，Agent 不可写；
4. 新对象必须满足该 OperationSpec 的完整输出 Schema、语义校验和资源上限；
5. 新对象不继承旧对象的通过资格，仍由原类型声明的独立评审 Operation 重新判断；
6. 旧对象作为 `revision_base` 只提供待修改内容，不自动成为证据；事实性内容仍需由该修订
   Operation 明确绑定的科学基础或冻结来源支持；
7. 修订只改变科学 Artifact，不得绕过人工审批或外部执行授权。

不建立一个可以处理所有 Schema 的“万能修订 Agent”。每个插件使用原生产者的专业 Agent、工具、
工作区、输出 Schema 和审查者声明一个修订 Operation；通用的是调用协议，不是专业判断者。

## 3. OperationSpec 形态

首版不增加 `supports_revision`、动态输出 Schema、修订注册表或编译器自动生成系统。现有
OperationSpec 已足以表达直接修订：

```text
operation_id: science.hypothesis.revise.v1
executor: 与假设提出 Operation 相同的 ideator Agent、工具和提示资源
inputs:
  prior_object        usage=revision_base       必需
  scientific_context usage=claim_evidence       必需
  change_request      usage=change_request      可选或按该行为必需
outputs:
  hypothesis_portfolio                         完整对象
review:
  science.hypothesis.criticize.v1
```

初次生产和修订的输入集合不同，因此仍是两个 public Operation；它们复用同一 Agent 组件、Schema、
validator、工具和工作区，不新增角色类。新领域只在自己的单一插件入口声明相同模式，不修改核心、
Root、通用调度器或界面。

### 3.1 直接完整修订的结构总函数

不增加新字段，但最终 catalog 必须从现有 executor、consequence、输入、输出和 review 声明判定
一种唯一合法的普通直接修订形态。旧 apply/receipt 声明在迁移期间可以短暂保留，但不获得
`revision_base` 免审资格且不得再作为新链消费者；最后一个消费者迁走后，catalog 才把以下规则
提升为编译硬门。最终任何 Operation 使用 `revision_base` 时必须同时满足：

1. executor 是 Agent，consequence 是 `scientific`；Transform、Effect 和 Approval 禁止使用该
   用途；
2. 恰有一个 `revision_base` 输入，且它必需、单值、非集合；
3. 恰有一个非集合主输出，不允许附带输出集合；主输出的 Schema、媒体类型和已编译 codec 与
   base 端口完全一致；
4. OperationSpec 的 ReviewSpec 必须把该主输出声明为独立 reviewer 的精确 subject；没有
   ReviewSpec 的 Agent 不能编译为直接修订；
5. 其他科学上下文、来源和可选 change request 仍由显式端口声明，不从角色名、Operation 名或
   Schema 名推断。

调用期再把结构合同与精确旧对象的冻结生产合同组合验证：

1. 旧对象输出必须明确允许 `revision_base` 用途；
2. 若旧对象有冻结 review 合同，新输出的 reviewer Operation、reviewer input port 和 accepted
   verdicts 必须与旧合同完全一致，不允许删除、替换或弱化；
3. 若调用提供 `change_request`，它必须是旧合同指定的 reviewer Operation 对该精确旧对象产生的
   completed 输出；旧对象没有 review 合同时，任何 change request 均失败；
4. blocked、revise、inconclusive 或 pass 只说明修改请求，不授予新输出资格；
5. 无 change request 只有在端口基数允许时成立，新输出仍必须重新审查。

迁移期 preflight 只为满足上述完整结构的 Agent 调用提供免审；旧 Transform 声明仍按旧普通资格门
处理，不能借 `revision_base` 获得放行。D3 删除最后的旧声明后，catalog 同时拒绝所有不满足结构
的声明。未知插件把 blocked 对象改绑到 Transform、Effect、无 ReviewSpec Agent、不同 Schema/codec
输出、不同 reviewer、另一对象或另一实例时必须失败关闭。不得增加 RevisionPolicy、兼容 facade
或领域白名单。

### 3.2 通用准入语义

- `revision_base` 表示显式待修草稿，只检查实例、Schema、用途、大小和权限，不要求旧评审已经
  `pass`；
- 普通 `claim_evidence`、`prior_signal` 和外部执行输入继续遵守原独立评审通过门；
- 一个调用若绑定 `change_request`，控制层按第 3.1 节验证旧对象冻结 review 合同和精确
  subject-review 关系；评审结论只解释修改请求，不授予新对象资格；
- 修订 Operation 没有 `change_request` 时，可由调用指令说明用户或调度器要求的修改；是否允许
  这种调用由该 OperationSpec 的端口基数决定，不由核心建立新的修订政策；
- 一个修订调用只有一个普通 `revision_base`。确需多对象联合重写的领域行为由插件显式声明
  guard，不在首版增加通用多基线协议。

### 3.3 差异展示

差异不是科学对象生产的前置门。首版不产生 `RevisionDiff` Artifact，也不建立 diff Operation。
后续审批界面若需要差异，只能在旧对象和新对象已经精确绑定后进行无状态、确定性展示投影；该
投影不能授予资格、改变字节或成为科学证据。没有真实界面需求前，不预先建设新的差异协议。

## 4. 删除和迁移清单

### 4.1 通用规范和任务合同

删除：

- `OutputPortSpec.revision_base_port`；
- `OutputPortSpec.allowed_revision_paths`；
- 输入用途 `unchanged_set_receipt`；
- `TaskRevisionSpec` 及 Task 输出中的 `revision` 分支；
- Worker assignment 中的结构化补丁合同；
- `roles/common.md` 中“只允许输出 StructuredRevision”的通用提示；
- Worker finalize 对 JSON Pointer 范围和补丁应用的专用校验；
- catalog、invoke 中由上述字段产生的编译和任务投影逻辑。

保留：

- 输入用途 `revision_base` 和 `change_request`；
- 完整输出的原 Schema、validator、semantic contract 和 context validator；
- 任务指令、输入、工具、权限和输出进入原有不可变调用指纹；
- Task/Artifact 的直接父链和新输出的独立评审合同。

### 4.2 通用科学插件

将以下 Agent Operation 改为输出完整对象：

- `science.intake.revise.v1` → 完整 `ScientificIntake`；
- `science.hypothesis.revise.v1` → 完整 `HypothesisProposal`。

修订 Operation 必须绑定足以重新支持完整科学内容的上下文：

- intake 修订同时绑定全部冻结来源，不能把旧 intake 当作证据；
- hypothesis 修订同时绑定已批准 scientific foundation；
- `change_request` 可精确绑定原 evidence audit 或 critic review；
- 使用与初次生产相同的完整对象提示、validator 和语义合同，不保留通用补丁提示。

删除：

- `science.revision.apply.intake.v1`；
- `science.revision.apply.hypothesis-proposal.v1`；
- `science.evidence.receipt.intake.v1`；
- `science.evidence.receipt.hypothesis-proposal.v1`；
- `structured_revision_apply`、`unchanged_evidence_receipt`、补丁/差异/收据 validator 和资源；
- `StructuredRevision`、`StructuredRevisionOperation`、`StructuredRevisionDiff`、
  `UnchangedEvidenceReceipt` 在无剩余生产消费者后对应的 Schema 文件和导出。

### 4.3 实验计划插件

将 `science.experiment.revise.v1` 改为由 experiment designer 直接输出完整
`ExperimentPortfolio`，并绑定原实验计划、精确对象审查、已批准科学基础、目标、假设组合和批评
中该计划生成所必需的最小集合。

删除：

- `science.revision.apply.experiment.v1`；
- `science.evidence.receipt.experiment.v1`；
- curve-score 插件中复制的补丁应用、收据、Schema、validator 和组件声明。

### 4.4 TCAD

`tcad.deck.author.revise.v1` 和 `tcad.deck.author.runtime-failure.v1` 已经采用“读取旧工程、输出完整
新工程”的正确模式，不改为通用补丁。只需验证新的 `revision_base` 准入规则允许被 reviewer 打回
的旧工程进入 author revision，同时普通打包和执行仍要求新工程重新 review 通过。

TCAD 文件工作区内部可以继续使用 Agent 的原生文本编辑工具；这是任务私有工作副本的编辑方式，
不是跨 Artifact 的结构化补丁协议。

### 4.5 生产者族和资格审批

删除 Root 中对 `structured_revision_apply` 的识别和递归族重建：

- `_revision_transform_family`；
- `_is_exact_review_bound_applied_revision`；
- `ProducerOutputFamily` 中只服务补丁链的 base、patch、diff 字段；
- 当前未通过的 `_revision_admission_subject_refs` 半修复。

直接修订 Agent 必须把完整科学来源或 foundation 作为本次直接输入，因此新对象的 Task 父链和
producer family 已经完整，不再递归借用旧生产者的来源。证据 intake 修订后执行一次新的完整
evidence audit，再创建新的科学基础资格审批；不生成“证据未变化收据”，不继承旧 audit 或旧
人工资格。

完整父链和科学证据源必须分开投影：

- Task/Artifact 父链继续包含本次全部直接输入，包括旧草稿、change request、prior signal、来源和
  foundation；删掉任一已绑定父对象都应破坏精确调用或谱系；
- `ProducerOutputFamily.evidence_sources` 只从已编译输入用途中的 `claim_evidence`、
  `evidence_inventory`、`cached_excerpt`，以及受控登记的 web snapshot/PDF excerpt 投影；
- `revision_base`、`change_request` 和 `prior_signal` 不得成为可支持事实主张的 evidence source；
- 该过滤直接读取现有 TaskInput usage，不新增来源表、收据或证据注册表。

正负例必须同时证明：删除真实冻结来源会使 audit/qualification 失败；旧 draft/review 仍在完整
父链中；但它们不出现在 qualification 的 frozen source set 中。

科学资格 projector 移除 `revision_diff` 和 `unchanged_evidence_receipt` 可选端口与修订特判。
初次 intake 和直接修订 intake 使用相同的“完整生产者族 + 完整冻结来源 + 全新 audit”审批规则。

### 4.6 历史通用 Transform 实现

`src/scidiscovery/artifact_agent/transforms.py` 中仍被 curve-score 插件复用的补丁/收据 profile、
函数和导出随插件迁移一并删除；文件中与其他确定性科学变换有关的实现保持不动。不得借本次机会
重写无关 Transform。

### 4.7 消费者迁移矩阵

| 类别 | 当前消费者 | 处置 |
| --- | --- | --- |
| 规范与调用 | `operations/spec.py`、`catalog.py`、`invoke.py`、`builtin_plugin.py` | 先让全部直接修订消费者迁移，再删除 patch 字段、Schema 投影和测试 revision 资源 |
| 修订 Schema | `artifact_agent/schema/structured_revision.py`、`artifact_agent/schema/evidence_receipt.py` 及公共导出 | 最后一个生产消费者迁走后删除，不迁成新的直接修订实体 |
| Task/Worker | `schema/task.py`、`service/task_outputs.py`、`service/task_worker_files.py`、`roles/common.md` | 删除 TaskRevisionSpec、范围校验、assignment revision 和 Worker 补丁提示；保留完整对象文件生命周期 |
| Root/生产者族 | `mcp_root_operation_routes.py` | 增加第 3.1 节结构总函数和按 usage 的证据源投影；随后删除 apply 识别、递归 revision family 和补丁字段 |
| 通用科学插件 | `general_science_agent_operations.py`、`general_science_resources.py`、`general_science_components.py`、`general_science_control_operations.py` | intake/hypothesis 改完整输出；同阶段改直接 intake 资格 projector；迁移后删除 apply/receipt 组件和端口 |
| 实验插件 | `plugins/curve_score/curve_score/science_operations.py` | experiment 改完整输出后，删除复制的 patch/apply/receipt 实现、资源和 Operation |
| 历史 Transform | `artifact_agent/transforms.py` | 最后一个 curve 消费者迁出后，只删两个 patch/receipt profile、函数、validator 和导出 |
| TCAD | `plugins/tcad_artifact/tcad_artifact/plugin.py` | 保持完整工程输出；在 D1 先让 project 输出允许 revision_base，再重放 review-request/runtime-failure |
| 实际评估与生成 | `scripts/r5_g_science_chain.py`、`tests/fixtures/r5_e2e_tcad/manifest.json`、生成的调度提示和 `MANIFEST.sha256` | 移除 diff/receipt 端口和旧目录项；生成结果必须从唯一 catalog 重建 |
| 当前架构文档 | `docs/ARCHITECTURE.md`、`docs/ARCHITECTURE.zh-CN.md` | 草案和 D0—D2 不改写当前事实；D3 候选实现完成后双语同步，作为 D3 独立审查对象 |
| 安装态 | `test_catalog_installed_entrypoint.py`、`test_operation_invoke_installed.py`、四类 clean-wheel | 先迁目录期望，再证明源码态和安装态一致 |
| 通用性夹具 | `tests/fixtures/plugins/producer_family_operation_plugin/`、`test_r5_blind_producer_family.py` | 改成未知插件“旧对象→完整新对象→新 review”正负例，不直接删除通用性证明 |
| 结构/专项测试 | `test_r3_agent_contract.py`、`test_catalog_negative_cases.py`、`test_general_transform_operations.py`、`test_general_science_plugin.py`、`test_curve_score_operation_plugin.py`、`test_r4_approval_operation.py`、`r5_structure_inventory.json` | 删除旧补丁断言，增加结构总函数、父链/证据源分离及重新审查门 |
| 冻结历史 | `scripts/r5_baseline_metrics.py`、历史报告、旧持久 Artifact | 只读保留；旧 revision 正则和历史字节不为零命中统计而改写 |

最终 `rg` 零命中门只针对发布生产路径和当前生成资源；历史文档、冻结基线、旧 Artifact 和独立审查
报告允许保留旧术语，以免篡改历史证据。

## 5. 实施阶段与检查点

### 阶段 D0：冻结缺陷并撤销半修复

1. 保留当前真实 `blocked` hypothesis critic 和独立审查报告，不修改其科学结论；
2. 增加最小失败测试，证明旧设计在“非通过评审→修订→新评审”处断裂；
3. 撤销 `_REVISION_REQUEST_VERDICTS`、`_revision_admission_subject_refs` 及为两段补丁链新增的
   临时测试和文档结论；
4. 不删除旧补丁协议，先恢复到可比较的已知基线。

完成门：工作树不再包含未审查的准入例外；旧失败由测试精确复现。

#### D0 实现记录（独立审查通过）

- 原因分类：旧对象被非通过评审打回后，同时又被普通 producer-output admission 禁止作为
  `revision_base`，属于架构/合同冲突，不是局部实现缺陷；D0 不尝试修复该冲突；
- 已从 Root 路由撤销 `_REVISION_REQUEST_VERDICTS`、
  `_revision_admission_subject_refs`、`revision_subject_refs` 及其
  `revision_base` 跳过分支，控制层不再理解补丁作者或补丁应用器；
- 已撤销为半修复增加的真实 `blocked → StructuredRevision → Apply` 临时正例，恢复既有通过
  评审下的旧补丁链基线；
- 已增加最小特征断言：同一精确审查输出被投影为 `revise` 时，普通下游与旧
  `science.intake.revise.v1` 均以 `input_independent_review_missing` 失败。该断言只记录旧设计
  死锁，不把失败解释为正确目标行为；
- 未实现直接完整对象修订，未删除旧协议，未创建或修改任何科研 Artifact、私有运行或审批状态；
- 冻结指标按候选源码重新计算：生产 Python 为 143 个文件、60254 行；通用科学声明责任为
  941 行，声明与确定性组件合计 2065 行；
- 7 GiB 虚拟内存上限下，聚焦回归 36 项通过；全量 `tests/operations` 首轮暴露一项已过期的
  机械行数夹具（归类为测试冻结错误），同步实测值后完整重跑为 269 项通过；
- 独立实现审查报告为
  `reviews/R5_G_DIRECT_OBJECT_REVISION_D0_INDEPENDENT_REVIEW.zh-CN.md`，结论“通过，仅放行
  D1”；独立复跑 36 项聚焦和 269 项全 Operation 测试均通过；
- 下一步只执行 D1 的直接完整对象准入、通用 intake/hypothesis 迁移、来源投影和 TCAD
  `revision_base` 用途；不得提前删除旧协议或迁移 D2 消费者。

### 阶段 D1：直接完整修订准入和 Worker 合同

1. 在 preflight 落实第 3.1 节的直接修订结构分类与调用总函数；旧 apply/receipt 不获得免审；
2. 将合法直接修订的 `revision_base` 从普通下游资格输入中分离，同时保持 output usage 检查；
3. 对可选 `change_request` 实现领域无关的精确 subject-review 绑定；
4. 把 intake 与 hypothesis 修订 Operation 改为完整对象输出；
5. 同步直接 intake 的 producer family、按 usage 的 evidence source、完整 audit 和科学资格 projector；
6. 让 TCAD project 输出显式允许 `revision_base`，但不改变普通打包/执行用途；
7. 真实 Worker 文件生命周期验证完整对象可写入、校验、封存；
8. 验证旧对象、评审意见、科学基础或来源均成为新对象的直接父输入，新对象没有新评审通过前不能
   进入普通下游；
9. 完成一次直接 intake→全新 audit→全新人工资格的正负例。

D1 的目录解释发生兼容性变化，因此在本阶段把 `OPERATION_ABI_VERSION` 提升为 7。由 ABI、通用
修订 Spec 和 TCAD project 输出用途直接派生的摘要、安装态 fixture 摘要及机械行数冻结必须在 D1
同步，否则测试验证的是不存在的旧目录；这不等于提前迁移 D2 的评估拓扑、脚本行为或 experiment
消费者。D1 同时保留旧 Task revision 投影供 D2 迁移，允许 `operations` 包相对 R5-0 冻结值最多
增加 40 行；这是显式的迁移重叠预算，不是新的长期复杂度基线。D3 删除旧投影时必须同时撤销这
40 行余量，并以净删除证明收口。

完成门：免审分类不识别具体 operation id、Schema、插件名、角色名或 `structured_revision_apply`；
未知插件的非法声明/调用负例和聚焦科学正负例通过；独立跨边界审查通过后才进入 D2。

#### D1 候选实现记录（待独立审查）

实现事实：

- `operations.invoke.direct_revision_ports` 只从现有 executor、consequence、单一
  `revision_base`、单一完整主输出、Schema/媒体/codec/resource 和 ReviewSpec 结构识别直接修订；
  不读取 operation id、Schema 名、插件名、角色名、端口名或领域类；旧 Transform apply 返回
  非直接修订；
- Root 的既有 producer-output admission 仍是唯一输入准入路径。只有结构识别成功且旧输出明确
  允许 `revision_base`、旧/新 reviewer 合同完全一致时才跳过旧对象的通过门；可选
  `change_request` 复用 TaskService 的同一个精确 reviewer 查询，并以 `accepted_verdicts=None`
  表示“只证明审查关系、不授予资格”，没有新增查询方法、状态或 verdict 白名单；
- intake 与 hypothesis 修订复用原 evidence/ideator Agent、完整输出 Schema、validator、语义合同、
  工具和提示资源，直接输出完整 `ScientificIntake`/`HypothesisProposal`；通用补丁 Agent 提示、
  validator、context validator 和四个无消费者组件已删除；旧 apply/receipt Transform 仍按 D1
  回退边界保留，未获直接修订免审；
- 完整 Artifact 父链保留旧稿、审查、来源和任务指令。`ProducerOutputFamily.evidence_sources` 只投影
  `claim_evidence`、`evidence_inventory`、`cached_excerpt` 以及受控 web/PDF 来源；
  `revision_base`、`change_request`、`prior_signal` 不再被提升为事实来源；
- intake 资格 projector 已接受直接 `science.intake.revise.v1` 生产者族，并移除 diff/receipt 输入和
  特判。真实测试闭合“完整修订→旧审查不能复用→新 audit→缺来源失败→新 UI 资格→下游放行”；
- TCAD author project 输出显式允许 `revision_base`；TCAD reviewer 输出显式允许
  `change_request`/`prior_signal`。真实 TCAD 生命周期证明非通过 reviewer 信号可以进入
  `tcad.deck.author.revise.v1`，但同一信号不能进入普通 reviewed-package；Root 无 TCAD 分支；
- ABI 提升为 7。由 D1 合同直接派生的 clean-wheel 摘要、R5 fixture operation digest、资格端口和
  机械指标已同步；curve experiment、盲插件完整对象迁移和实际评估脚本行为仍未进入 D2。

开发/测试问题分类：

1. 系统 Python 未设置源码路径：外部环境问题，只调整探针环境，未改代码；
2. 新对象父链多出任务指令：测试夹具错误；保留既有可追溯性，将断言改为必需科学输入子集；
3. 首轮全 Operation 的摘要、行数和安装态 fixture 失败：D1 ABI/Spec 的派生冻结变化；计划先明确
   ABI7、D1/D2 边界和 40 行迁移重叠预算，再同步实测值；
4. TaskService 一度新增第二个 reviewer 查询方法：不符合奥卡姆门，撤销新方法并合并到原查询，
   方法数保持 40；
5. TCAD reviewer 输出未声明实际 change-request/prior-signal 用途：插件 OperationSpec 合同缺陷；
   在 TCAD 插件端修正声明并增加真实重放，没有在 Root 增加领域例外。

冻结验证：

- 生产 Python：143 个文件、60308 行；`operations` 包 2097 行，在已声明的 D1 临时余量内；
- 通用科学声明 959 行、确定性组件 1036 行，合计 1995 行，较 D0 的 2065 行下降 70 行；
- Root 责任聚合 3146 行；TaskService 责任聚合 6221 行且仍只有 40 个自身方法；
- 首轮候选的 `python -m py_compile` 通过；全 `tests/operations` 为 269 项通过；全仓含 clean-wheel
  安装态为 306 项通过；该证据随后被独立审查判定不足，不能作为 D1 放行依据；
- 未运行真实科研 Agent、外部 solver 或用户审批；D1 只验证通用合同和测试态 Worker/UI 生命周期。

下一步只允许独立审查 D1 的结构总函数、精确审查绑定、父链/证据源分离、TCAD 复用、迁移余量
和阶段边界；审查通过前不得修改 curve experiment、盲插件或删除旧协议。

#### D1 首轮实现审查打回与架构复查

独立报告：
[D1 独立实现审查](reviews/R5_G_DIRECT_OBJECT_REVISION_D1_INDEPENDENT_REVIEW.zh-CN.md)。
首轮结论为打回：未知插件非法结构/真实 Root 调用负例不足；TCAD 只到修订预检，尚未真实完成
修订 Worker、领域工具和完整工程封存。

补真实 TCAD 生命周期后，测试首先暴露的不是断言缺口，而是工作区所有权错误：已完成调试的旧
`DeckProjectDraft` 带有控制生成的 `preflight_attestation`；修订工作区原样继承该字段后，一方面
旧证明已因源码变化而失效，另一方面输出校验会正确拒绝 Worker 重新提交控制字段。D1 据此冻结
以下领域工作区不变量：

1. 完整对象修订继承的是旧对象中的 Worker 科学/工程内容，不继承对旧字节成立的控制证明；
2. TCAD 修订物化时必须对所有 solver 类型移除旧 `preflight_attestation` 和
   `materialization_report`，不得只在 SProcess 确定性分支移除；
3. 新源码只能通过注册的领域调试工具重新生成新预检证明，最终封存仍由同一输出 validator
   fail-closed；
4. 修复只能落在 TCAD workspace materializer 这个现有唯一所有者，不得放宽校验器、伪造证明、
   在 Root 增加 TCAD 特判或在测试中跳过工具。

该问题分类为“架构所有权或抽象错误”，不是普通局部实现缺陷。完成上述唯一所有者修正和 F1/F2
真实测试后，D1 必须重新独立审查，仍不得提前进入 D2。

返工闭合事实：

- F1：增加仅测试态、未安装的 `unknown_revision_*` 插件。一个合法未知插件直接修订结构被识别；
  Transform/Effect/Approval、非 scientific、无评审、评审 subject 不符、零/多/集合 base、零/多/
  集合输出以及 Schema、媒体、codec、schema resource 不同的矩阵均返回非直接修订。无评审、零
  base、多 base 三种可编译未知插件还携带精确 `revise` 审查信号经过真实 Root preflight，均以
  普通独立评审门失败关闭；核心没有新增未知插件特判；
- F2：现有 TCAD 生命周期现已真实调用 `tcad.deck.author.revise.v1`，完成 Operation invoke、Task
  dispatch/claim、`deck_mode=revise` 工作区物化、注册工具可见性、`worker_file_apply_patch`、
  `worker_tcad_debug_run`、完整 project 校验和 finalize。修订输出父链包含全部精确输入；旧 review
  与新 project 组合被通用谱系 guard 拒绝，不能进入 reviewed package；
- 真实测试发现并修正 TCAD workspace 唯一所有者缺陷：所有 TCAD 修订不再继承旧字节对应的
  `preflight_attestation`/`materialization_report`；新预检证明只能由注册领域工具重新产生。未放宽
  validator，未修改 Root、TaskService 或 OperationSpec；
- 该生产修复净增 5 行，生产 Python 实测为 143 文件、60308 行；`operations` 包、Root、TaskService
  与通用科学责任指标不变；
- 返工后聚焦 3 项、全 `tests/operations` 270 项、全仓含 clean-wheel 307 项通过；复审前再次执行
  语法编译与 `git diff --check`。D1 仍须独立复审通过后才能进入 D2。

第二轮独立复审报告：
[D1 独立实现审查第二轮](reviews/R5_G_DIRECT_OBJECT_REVISION_D1_INDEPENDENT_REVIEW_ROUND2.zh-CN.md)。
结论仍为打回。审查独立证明 `consequence=explore` 与 `revision_base.max_items=2` 两种畸形结构可
通过目录编译，但候选只在已编译对象的结构矩阵中断言非直接修订，未把它们送入真实 Root 与
`revise` 信号验证普通评审门失败关闭。该项分类为测试证据缺口；只允许把两种声明加入现有
`unknown_variants` Root 循环并同步记录，不得修改生产代码或提前进入 D2。

第二轮返工闭合：`unknown_variants` 已加入可编译的 `consequence=explore` 与
`revision_base.max_items=2` 两种声明；它们与原三种畸形声明使用同一未知插件编译入口、同一精确
`revise` 审查信号和同一 Root preflight，均未获得直接修订免审并以
`input_independent_review_missing` 失败关闭。此次只改测试和本记录，生产代码、目录、ABI 与机械
指标均未变化。聚焦 2 项、全 Operation 270 项、全仓/clean-wheel 307 项再次通过，等待第三轮
独立复审；通过前仍不得进入 D2。

第三轮独立复审报告：
[D1 独立实现审查第三轮](reviews/R5_G_DIRECT_OBJECT_REVISION_D1_INDEPENDENT_REVIEW_ROUND3.zh-CN.md)。
结论为通过，只放行 D2。独立复跑证明新增两种 variant 均真实完成“完整目录编译→
`direct_revision_ports=None`→真实 Root+`revise` 失败关闭”；TCAD 完整修订链继续通过，生产/ABI/
目录和 60308/2097/3146/6221 指标未变化。D1 自此冻结，D2 只迁移 curve experiment、盲插件夹具
和实际评估脚本，不得修改已通过的核心免审规则。

### 阶段 D2：迁移最后生产消费者

1. 将 curve-score 插件的 experiment revision 改为完整对象输出；
2. 将盲插件 fixture 改为完整对象修订和新 review；
3. 迁移实际评估脚本、fixture manifest、生成提示、安装态目录期望及全部当前消费者；
4. 用 `rg` 证明发布生产路径已经没有旧协议消费者；旧类型和实现此阶段可以暂时保留，但必须零
   生产引用；
5. 运行 core-only 干净安装态、同一 `CORE_PLUGIN + general_science` 组合的源码编译、full、
   full+InGaAs 的目录与聚焦调用检查。`CORE_PLUGIN` 是零 Operation 的共享组件包，不是一个可独立
   部署的“纯 builtin”目录；不得为使这种不存在的组合可编译而放宽未使用组件门。

完成门：全部生产消费者先迁完，四种目录均可编译；独立审查通过后才允许删除旧协议。

#### D2 冻结实现合同

曲线实验修订：

- `science.experiment.revise.v1` 继续复用 `experiment_agent`、通用 Worker 文件工具、workspace 和
  `experiment_prompt`，不创建 `experiment_reviser` 角色；
- 当输入含 `prior_draft`/`change_request` 时，提示资源要求输出完整 `ExperimentPortfolio`；初次
  `science.experiment.design.v1` 仍输出紧凑 `ExperimentDesignIntent`，两种行为以各自
  `output.schema.json` 为唯一格式合同；
- 修订输入固定为旧计划、精确 `ScientificReview`，以及一个可选但全有或全无的科学上下文 cohort：
  已批准 `scientific_foundation`、`research_objective`、`hypothesis_portfolio`、`critic_review`。
  科学计划缺该组时由完整计划 context validator 拒绝，工程计划允许不绑定该组；
- 输出为单一完整 `experiment_plan`，复用 `ExperimentPortfolio` Schema/validator/semantic contract，
  并声明原 `science.object.review.v1` 为新对象 reviewer。不得保留 Agent patch prompt、patch validator
  或 patch context validator；旧 apply/receipt Transform 只为 D3 删除前的零消费者重叠保留。

盲插件夹具：

- 初始 Transform 仍产生一个主对象和两个同 Schema 附件，以继续验证未知插件 producer family；
- 插件自己声明 `blind.domain.review.v1`，并把初始主对象与直接修订主对象都绑定到这一 reviewer
  合同；review 输出可作为精确 `change_request`，但其 verdict 不授予新对象资格；
- `blind.domain.revision.propose.v1` 改为 Agent 直接输出完整 `blind.object.v1`，删除夹具自己的
  revision apply、delta、change log 和对应 Schema/组件；
- 初始对象的审批仍必须绑定完整 sibling family 与精确新 review；直接修订对象没有伪造 sibling，
  审批投影以其实际 producer family 为准。用同 Schema 附件作 base 时，因为附件不是初始 review
  subject，必须在真实 Root 准入处失败，不能晋升为主对象；
- clean-wheel 只证明未知插件目录、初始生产和直接修订/reviewer 声明可发现；真实 Worker 修订与
  新评审由源码态跨边界测试闭合，不为安装探针复制第二套生命周期。

D2 出现任何需要 Root 按 experiment/blind id 或 Schema 分派、需要新 revision 状态/注册表、或必须
借旧 diff/receipt 恢复来源的情况，均判为直接修订抽象失败并退回架构审查，不允许继续补丁迁移。

#### D2 当前实现与问题分类

- curve-score 的实验修订已改为复用原实验设计 Agent、工具、工作区和提示资源，直接输出完整
  `ExperimentPortfolio`；真实工程计划生命周期证明旧计划和精确返修意见进入新对象父链、旧评审
  不能作用于新版本、新版本可被原 reviewer 重新审查；
- 未知盲插件已删除自身 patch/apply/change-log 链，真实 Root 与 Worker 文件生命周期、同 Schema
  附件不可提升、旧评审不可继承及 clean-wheel 发现共 10 项通过；
- 实际 R5-G 科学链已删除资格调用中的旧 `revision_diff` 和 `unchanged_evidence_receipt` 空端口；
- 中断后出现的运行实现/测试仍使用旧链，归为第 4 类冻结夹具迁移不完整，一次性替换且未保留
  双路径；两次辅助变量错位和一次分类器参数错误均为第 4 类测试编辑错误；
- 首次四目录探针把 `core-only` 误解为单独编译零 Operation 的 `CORE_PLUGIN`，触发
  `component_unused`。历史安装测试和 R3 决策证明 core-only 的产品定义始终是
  `builtin + general_science`。该问题归为验收定义用词错误，已在本阶段完成门中澄清；没有给 catalog
  增加例外，也没有创造纯 builtin 部署形态。
- 首轮完整 Operation 回归为 271 通过、1 失败；唯一失败是 D1 冻结的生产 Python 行数仍为
  `60308`，而 D2 将曲线实验修订改成完整对象后实测为 143 文件、`60313` 行。该净增 5 行处于
  D1 已批准的 40 行迁移重叠预算内，分类为第 4 类冻结指标同步；测试已更新为实测值，D3 必须随
  旧协议删除撤销临时余量并证明总体净删除。
- 指标同步后，`tests/operations` 为 272/272 通过，全仓为 309/309 通过；core-only 源码组合、full、
  full+InGaAs 分别编译出 15/49/50 项，core-only 干净安装态包含在全仓 installed-entrypoint 回归；
  `git diff --check` 通过，`operations` 包仍为 7 文件、2097 行，Root/TaskService 仍为 3146/6221 行。
  D2 候选实现现提交独立跨边界审查；通过前不得进入 D3。

[D2 独立实现审查](reviews/R5_G_DIRECT_OBJECT_REVISION_D2_INDEPENDENT_REVIEW.zh-CN.md)结论为通过，
只放行 D3。独立复测同样得到聚焦 5 项、Operation 272 项、全仓 309 项通过，并确认无核心领域
分派、第二注册表、状态或资格权威。D3 额外冻结两项收口检查：删除未被运行时消费但会误导读者的
旧 experiment designer 补丁提示；增加 scientific experiment revision 缺完整 cohort 的精确集成
负例。

### 阶段 D3：删除补丁协议并完成发布回归

1. 删除通用与 curve-score 插件的六个 apply/receipt support Operation 及旧组件；
2. 删除结构化补丁、差异、未变证据收据 Schema；
3. 删除 spec/catalog/invoke/Task/Worker 中 patch 专用字段和分支；
4. 把第 3.1 节结构形态提升为 catalog 编译硬门，删除迁移期旧声明的可能性；
5. 删除 Root 的 apply 识别、递归 revision family 和补丁字段；
6. 删除历史 Transform 中已经零生产引用的 patch/receipt profile 和实现；
7. 更新当前生成资源、结构清单和安装态摘要；冻结历史保持不动；
8. 重放 TCAD review-request revision 和 runtime-failure revision，验证 author 工具、任务私有工作区
   和新 reviewer 门；
9. 运行四种 clean-wheel、全 Operation 回归和全仓回归。
10. 候选实现闭合后同步中英文当前架构文档，再提交 D3 独立审查；两份文档不得提前把草案写成
    既成事实。

完成门：新领域 fixture 只声明“旧对象输入→完整新对象输出→独立 reviewer”即可运行；删除行数
大于新增行数；零新表、注册表、状态机和入口；独立审查通过后才恢复 R5-G 实际科学链。

#### D3 候选实现记录（待独立审查）

实现事实：

- Operation ABI 提升为 8；catalog 以 `direct_revision_ports` 的领域无关结构判定作为编译硬门，
  任何声明 `revision_base` 却不满足单一必需 base、单一同合同完整输出、科学 Agent 和独立
  ReviewSpec 的 Operation 均以 `direct_revision_contract_invalid` 失败关闭；
- 通用科学插件和 curve-score 插件的六个 apply/receipt support Operation、对应组件与资源已删除；
  `structured_revision.py`、`evidence_receipt.py` 及其公共导出已删除，不保留兼容 facade；
- `OperationSpec`、调用投影、Task/Worker 合同、Root 生产者族和历史 Transform 中的 patch、diff、
  receipt 专用字段、递归和实现已删除。Root 只读取完整新对象的普通直接父输入；
- 实验修订缺少全有或全无科学上下文 cohort 的真实 Root 负例以 `guard_rejected` 失败关闭；TCAD
  review-request 与 runtime-failure 两条修订链均完成 author Task、私有工作区、领域调试工具、完整
  工程封存和新 reviewer 门，旧 review 不能用于新工程；
- 当前 core-only/full/full+InGaAs 目录分别为 11/43/44 项；通用科学插件为 11 项 Operation，其中
  public/support=10/1，Agent/Transform/Approval=9/1/1；
- 生产 Python 为 141 文件、59061 行；`operations` 包 2062 行，Root/TaskService 责任聚合为
  2949/6170 行，通用科学声明与确定性组件合计 1754 行。相对 D2 的 60313 行净删 1252 行，没有
  新表、注册表、状态机或入口；
- 串行内存受限回归得到 `tests/operations` 271/271 通过、全仓 308/308 通过；全仓包含
  core-only、full、full+InGaAs 和 R5-G 安装态/clean-wheel 路径。

问题分类：删除旧收据后残留的无消费者 curve wildcard 组件属于第 3 类局部实现孤儿，已随唯一
所有者删除，未放宽目录闭包；旧递归测试和 ABI 派生摘要属于第 4 类冻结夹具更新，按当前唯一目录
重建。独立审查首次发现根发布清单仍指向已删除文件，第二次发现 TCAD wheel 仍发布一套未注册的
`DeckProjectPatch` 兼容分支；二者均归为第 4 类删除/发布清单遗漏。返工使用唯一发布生成器重建
清单，并从 TCAD packager、adapter、公共导出、README 和 Agent 提示中删除跨 Artifact 补丁类型、
应用器与 profile，同时增加生产插件零命中结构门。任务私有 `worker_file_*` 编辑和仍注册使用的
完整工程比较/diff 保持不变。返工后生产 Python 为 59061 行，相对 D2 净删 1252 行。未出现需要
领域 id 特判、第二资格/来源/current 权威或新修订实体的架构性失败。

D3 最终独立审查报告：
[R5-G D3 直接完整对象修订独立审查](reviews/R5_G_DIRECT_OBJECT_REVISION_D3_INDEPENDENT_REVIEW.zh-CN.md)。
结论为通过，只放行 D4；不放行实验设计或 R5 发布冻结。

### 阶段 D4：真实假设修订和科学复审

1. 使用现有持久 R5-G run root、原 approved foundation、原 portfolio 和原 `blocked` critic；
2. 真实启动 hypothesis revision Agent，只修正已指出的两个可识别性问题，输出完整新 portfolio；
3. 真实启动新的独立 critic；旧 critic 不继承、不转换为通过；
4. 阶段报告同时记录任务完成态、critic verdict 和 `stage_admissible`，不能再用
   `status=completed` 冒充科学通过；
5. 独立科学审查者读取封存的新 portfolio、critic 和精确父链。只有 verdict=`pass` 且独立科学
   审查通过，才进入实验设计。

完成门：真实科学闭环证明直接修订不是仅在测试夹具中成立。

#### D4 真实运行前候选实现记录

首次使用当前 ABI 8 对持久 R5-G 状态做只读预检时，严格任务解码在旧任务描述的
`output.revision: null` 处失败。问题分类为第 5 类外部运行代际边界，同时暴露一项实施前提：D3
明确不保留历史兼容面，但 D4 又必须复用 ABI 6 已封存的科学对象和审批。不得把字段加回运行时
Schema、改成忽略未知字段或用旧 ABI 继续创建科学任务。

候选方案采用一次性前向代际转换，而不是运行时兼容：

1. 原 `state/`、旧 portfolio、旧 critic、科学输出、审批和阶段报告保持原位且不改写；
2. 在同一持久 run root 下复制出 `state-d4-abi8/`，只把 12 个不可变 task descriptor 中恒为
   `null` 的退役 `output.revision` 删除；每个 ABI 8 task descriptor 以旧 descriptor 为直接父项
   和 supersedes 项，转换前后摘要写入单一迁移报告；
3. 转换器遇到非空 revision、其他 Schema 差异、活跃 WAL、身份变化或不满足 ABI 8 的 payload
   一律失败关闭；不改写科学 Artifact、输入绑定、任务状态、scheduler signal 或 Approval；
4. D4 只在该新代际状态和重新安装、重新编译的 ABI 8 单一 Operation catalog 中运行。旧
   `runtime-venv` 的 ABI 6 目录与陈旧 8765 服务均不参与；
5. runner 精确验证旧 blocked critic 审查旧 portfolio，随后调用
   `science.hypothesis.revise.v1` 输出完整替代对象，再调用新的
   `science.hypothesis.criticize.v1`；
6. 即使新 critic 精确给出 `pass`，runner 也只写 `awaiting_independent_review`，保持
   `stage_admissible=false` 和 `experiment_design_released=false`。最终阶段准入只能由新的独立
   科学复审记录形成；若 critic 非 pass，则写 `blocked` 并停止。

首轮真实运行前独立审查结论为**不通过**：旧资格决定的 compiled provider identity 不属于 ABI 8，
且首版代际报告没有闭合旧 output `task_ref` 与新 task descriptor 的精确关系。报告见
[D4 首轮真实运行前独立审查](reviews/R5_G_D4_PRERUN_INDEPENDENT_REVIEW.zh-CN.md)。返工没有放宽核心
provider/producer 检查，而是把 D4 拆成两个受审门：

1. **D4-Q（当前资格重新封存）**：一次性状态转换报告升级为 schema 2，逐项记录完整 old/new
   `ArtifactRef`、唯一删除字段、新 descriptor 的 parent/supersedes、旧 output/scheduler signal 的
   task edge 和未变化的 task state/output/signal；runner 会机器复核内外报告、SQLite、CAS 和旧输出
   关系。安全 staging 可在原状态独占锁内丢弃重建，非终态源任务禁止转换；
2. 可丢弃真实状态副本证明 12 项任务转换可重复验证，旧资格请求的 compiled identity 与 ABI 8
   不同，旧生产者对象被当前门以 `input_producer_contract_changed` 拒绝；即使先用 ABI 8 重建四个
   **确定性**投影，旧 Agent 生产者仍被同一门拒绝。新 profile、metric、metric source 和 curve
   source 与旧对象逐字节相同；
3. 资格 projector 还要求 extraction primary 属于当前编译 Agent producer family，因此不能只重签旧
   审批，也不能给旧 task authority 换 digest。D4-Q 必须用相同六源真实运行当前
   `science.evidence.extract.v1` 和新的独立 `science.evidence.audit.intake.v1`，再执行当前
   `science.intake.split.v1`，最后由当前 `science.evidence.qualify.v1` 生成新的本地 UI 决定；
4. 旧 evidence、audit、foundation、Approval 和全部科学字节保持不变；新链是新的不可变当前代际
   对象，不冒充旧对象。若新 audit 非 `pass` 或用户不批准，D4 假设修订停止；
5. **D4-H（假设完整对象修订）**：只有 D4-Q 的新 provider、完整九对象 subject family、当前
   foundation 和代际报告再次独立核验通过后，才启动 hypothesis revision 与新 critic。即使 critic
   `pass`，仍保持 `stage_admissible=false`，等待最终独立科学复审。

当前聚焦/Approval/目录测试为 68/68 通过，单独 runner 集为 17/17；当前实现生成的持久可丢弃
probe 保存于 `.scidiscovery/r5-e2e-private/d4-prerun-probe-20260830-04/`，迁移报告 SHA-256 为
`667d080ee0adf53c90c80c84c27b7d444f1fc05461c40b86df5cf083387dc5c0`。其 12 项映射均冻结有/无
scheduler signal 的旧 task edge，当前 ABI 8 校验器初始及允许后继两种模式均通过；真实状态树
前后 SHA-256 均为 `129059c89f87c892743d63efb8b6167e7b6d5408100996f9e9203276b77918ca`。返工将先送第二轮独立审查，第二轮最多
只可放行 D4-Q，不得直接放行 D4-H、实验设计或发布冻结。

D4-Q 真实运行记录：schema 2 代际报告内外 SHA-256 均为
`257a2b9f613e7004786c49d587e7144d2b959ec29d2ff0e54f67abb1f1619939`；当前 extract 与独立 audit
任务均一次完成；用户只在本地 UI 对 `r5g_evidence_qualification_abi8` revision 1 作出
`approve` 决定；资格报告 SHA-256 为
`85a2e257233843192ddc472fc435b66786043ea6c20811460969ad4f39cebccc`，并明确
`old_decision_inherited=false`。该事实只表示 D4-Q 执行完成，D4-H 仍等待后置独立审查放行。

D4-Q 后置独立审查结论为“通过（只放行 D4-H）”，报告见
[D4-Q 后置独立审查](reviews/R5_G_D4Q_POSTRUN_INDEPENDENT_REVIEW.zh-CN.md)。D4-H 随后真实执行：
`science.hypothesis.revise.v1` 输出完整新对象，新的 `science.hypothesis.criticize.v1` 精确审查该
对象；两个 Task 均为 `completed`，但 sealed critic verdict 为 `blocked`。阶段报告 SHA-256 为
`4d6e64e89db11ef23a16c214b9fdba44e6a72f7b376b42402e654b5c1d101444`，状态保持 `blocked`、
`stage_admissible=false`、`experiment_design_released=false`。这属于科学质量门阻断，不按运行错误
处理；在独立诊断区分 Agent 科学判断、上下文合同和批评合理性以前，不自动开始第二次修订。

D4-H blocked 独立诊断结论为“实现通过但科学结果阻断，可进行一次有界 D4-H2 修订”，报告见
[D4-H blocked 独立诊断](reviews/R5_G_D4H_BLOCKED_INDEPENDENT_DIAGNOSIS.zh-CN.md)。诊断确认现有
OperationSpec 的 `prior_draft`、`change_request`、`scientific_foundation` 三端口已足够，无需新增
Operation、Schema、Validator 或核心特判。D4-H2 因此只复用同一 revise/critic，运行前审查见
[D4-H2 运行前独立审查](reviews/R5_G_D4H2_PRERUN_INDEPENDENT_REVIEW.zh-CN.md)。

D4-H2 的完整修订与全新 critic 均一次完成，但 sealed verdict 再次为 `blocked`。阶段报告 SHA-256
为 `3cd745b2d996428496ec4b77be317e9c77e1e87d290ac57fc8fe667c1f888d8f`，并明确
`stage_admissible=false`、`experiment_design_released=false`、`further_revision_released=false`。
因此 D4 不再启动第三轮科学修订，也不进入实验设计；当前只允许最终独立复核实现、科学阻断和
停止门是否诚实生效。

最终后置独立复核结论为“实现与停止门通过，科学结果未通过，R5-G 停止于假设阶段”，报告见
[D4-H2 后置独立复核](reviews/R5_G_D4H2_POSTRUN_INDEPENDENT_REVIEW.zh-CN.md)。独立机器断言通过，
最小回归 17/17；审批 UI 可用性继续判为未通过。工程收口随后在 7 GiB 限制下运行全仓测试，结果
`323 passed in 98.80s`。清理的 9 个目录均为未跟踪、Git 忽略、可再生的 `build`/`*.egg-info`
构建元数据，未删除源码或用户文件；清理后测试没有重新污染源码树，生产复杂度仍冻结为 141 个
Python 文件、59061 行。

最终工程结论由
[R5-G 最终工程收口独立审查](reviews/R5_G_FINAL_ENGINEERING_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md)
再次独立确认：工程实现通过，科学验收未通过，R5-G 关闭但 R5 发布不放行；其独立全仓结果为
`323 passed in 99.86s`，最大 RSS `128580 KiB`。

唯一发布生成器输出的当前清洁候选共 374 个文件，`MANIFEST.sha256` 为 373 条记录；在候选根执行
`sha256sum --check --strict --quiet` 通过，生成时根清单与候选清单逐字节一致。清单包含本计划，
因此不得在本计划中冻结其自身间接依赖的摘要；最终独立报告写入后必须再执行一次机械重建和严格
校验，以最后生成的根文件为权威。该清单只证明工程发布集合闭合，不改变 R5-G 科学结果未通过和
R5 发布冻结未放行的结论。

## 6. 必须覆盖的测试

### 正例

1. `blocked/revise/inconclusive` 的精确 reviewer 输出可以作为可选 change request；
2. 原专业 Agent 读取旧对象和科学上下文，输出完整新对象；
3. 新对象通过原 Schema、语义校验、文件生命周期和资源上限；
4. 新对象父链精确包含旧对象及本次直接科学输入；
5. 新对象经过全新独立 reviewer `pass` 后可以进入普通下游；
6. TCAD author revision 继续使用注册的领域工具并输出完整工程。

### 负例

1. 无关 reviewer、审查另一对象的结果或另一实例对象不能作为 change request；
2. Transform、Effect、Approval、无 ReviewSpec Agent、不同 Schema/codec 输出或 reviewer 合同漂移
   均不能声明/调用为直接修订；
3. 不完整的新对象、错误 Schema、越界文件或未声明工具调用失败；
4. 旧对象的 `pass` 资格不能自动赋予新对象；
5. `blocked` 旧对象可以进入合法 `revision_base`，但仍不能进入实验设计、打包或执行；
6. 修订 Operation 未绑定必需 scientific context 时失败；
7. 新插件不能通过 raw Python 路径、第二入口或核心白名单注册修订；
8. 删除任一新对象的直接来源或 foundation 后，审查/资格失败关闭；
9. draft/review 缺失会破坏父链，但二者不得出现在 evidence source set。

### 结构和发布检查

- `rg` 在生产代码中找不到 `structured_revision_apply`、`revision_base_port`、
  `allowed_revision_paths`、`unchanged_evidence_receipt` 及 apply/receipt operation id；
- `src/scidiscovery` 不出现领域 operation id、领域 Schema 或插件名分派；
- 单一 `scidiscovery.plugins` 入口和单一 CompiledCatalog 不变；
- 无新增表、持久化实体、状态机、注册表或审批事实；
- 聚焦测试、全 Operation 测试、全仓回归和 clean-wheel 安装态回归均通过；
- 所有测试和真实 Agent 命令保持 7 GiB 虚拟内存上限，串行执行。

## 7. 复杂度预算与奥卡姆门

本次允许新增的生产概念只有“`revision_base` 不等同普通合格下游输入”这一条既有用途语义的明确
实现，不新增类型。必须净删除：

- 6 个 apply/receipt support Operation；
- 3 套补丁 Agent 输出合同；
- 结构化补丁、差异和未变证据收据实体；
- Root 的修订 Transform 递归和补丁识别；
- Task/Worker 的补丁范围合同；
- 通用与 curve-score 插件中的重复应用/收据实现。

若实现需要新增通用 RevisionManager、RevisionSession、RevisionPolicy、动态 Schema 注册表、差异
状态机或新的数据库表，立即打回方案。若删除后生产代码没有净下降，独立审查必须逐行解释；不能
用测试数量或文件拆分冒充简化。

## 8. 回退边界

- D0 只撤销未通过的半修复和增加失败证据；
- D1 只改变通用直接修订、intake 资格和 TCAD revision 用途，不删除旧 apply/receipt，失败可整体
  回退；
- D2 只迁 curve-score、盲插件和安装/生成消费者，旧协议仍暂留，失败分别按插件/fixture 回退；
- D3 在零生产消费者后原子删除旧协议，不保留兼容 facade；TCAD 重放和 clean-wheel 是同阶段门；
- D4 只产生新的不可变 R5-G 对象，不修改或删除旧 portfolio、critic、evidence 或审批记录。

## 9. 完成定义

只有同时满足以下条件，本问题才算解决：

1. 被打回对象可以由原专业 Agent 直接产生完整新版本；
2. 控制层不限制科学字段修改，只验证精确授权、完整 Schema、父链和重新评审；
3. 普通下游与外部执行的通过门没有放宽；
4. 补丁、应用、差异收据和修订生产者族特判从发布生产路径删除；
5. 完整父链与 evidence source 按输入用途分离，旧草稿/评审不被提升为科学来源；
6. 一个未知领域插件可只用现有 OperationSpec 声明直接完整修订，不修改核心；
7. TCAD 完整工程修订、工具权限和独立 reviewer 不退化；
8. R5-G 的真实 hypothesis revision 和新 critic 获得独立科学审查结论；
9. 每个关键阶段均由未参与实现的独立审查者书面通过。

成功信号不是“补丁终于可以应用”，而是：

> 修订重新成为专业 Agent 的普通内容生产行为，控制层只保留不可变版本、最小授权、精确谱系和
> 新版本重新审查。
