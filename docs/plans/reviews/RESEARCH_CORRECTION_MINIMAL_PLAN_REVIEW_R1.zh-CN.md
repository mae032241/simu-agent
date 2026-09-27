# 校验纠错与跨轮续研最小计划独立审查 R1

日期：2026-09-08。结论：**REVISE**。本次发现 **1 项计划阻断**：精确父链查询仍未写成可实施合同。最小修订是在已有 `artifact_catalog` 增加有界父名称投影，将生产文件清单从 12 个补为 13 个，并补冷启动验收；无需新增公共 Operation、工具、来源别名存储、递归服务、进度对象或状态机。

新增两个 curve 文件足以承接“同一 observable 的目标也可选择子集”的本次修改。未发现必须再修改评分算法、TCAD 工作区或生命周期的源码依据。允许未覆盖目标进入科学审查、由 Agent 判断缺口是否影响继续的方向成立；这不等于任何局部实验必然获得通过。

## 1. 冻结身份与审查边界

- 仓库：`123/scidiscovery-e5.2`；分支 `refactor/m7-pre-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。
- 审查计划：[RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md](../RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md)，SHA256：`4e4b0c1d6ee6342b48a8519527d26e22f383dedf8e69683b7b0ecaddaaa4126b`。相同字节已冻结于 [plan-review-r1-input.md](../evidence/research-correction-continuation/plan-review-r1-input.md)。本结论不自动适用于后续修订。
- 完整基线：[source-baseline-2026-09-08.json](../evidence/research-correction-continuation/source-baseline-2026-09-08.json)，699 个文件记录，清单文件 SHA256：`50574bfe11f1fe1caa7649e89d887e44fa0a816cb654c8656ba0f713f760e438`。本审查独立逐项复算其中 `src/`、`plugins/`、`roles/`、`skills/`、`deploy/` 文件摘要，**未发现不一致**。大量既有修改、删除及未跟踪文件是基线；不能用干净 HEAD 代替。
- 安装目录记录：[installed-catalog-before.json](../evidence/research-correction-continuation/installed-catalog-before.json)，SHA256：`79c75f6ff04f958160dd748a3050609581b448e698b108b4ea456524b8bc4a94`。此文件由父工程任务冻结，本审查未自行调用科学控制 MCP。
- 已读工作区根和发布副本的 AGENTS、工作区三个 `scid-cross-boundary-review`、`scid-find-simplifications`、`scid-change-scope-checks` 技能及 Karpathy 准则；对照当前架构、科学设计宪章、约束登记、当前评估及 curve/TCAD 插件文档。评估和旧报告作为证据，不作为当前实现已经通过的证明。
- 本次只审计划，不实施；只写本报告。未调用 instance、Worker、审批或执行工具，未读取失败 Worker 草稿；未运行 pytest、wheel、平台或 solver，也未另行运行内存模型探针。

关键源码摘要如下，其余按上述完整清单复核：

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py` | `89d87b1c1292f0fe40dfbaa215e72690a02cec763c6ed2fa2c3808753d00b421` |
| `src/scidiscovery/artifact_agent/service/scheduler_bindings.py` | `6b277453266aa79478860166a0a72ba620c371810109e31ea7a1afe863a6229c` |
| `plugins/curve_score/curve_score/curve_contract_compiler.py` | `ba400470457f307f1b21209fde78eb7db8656a2a973c867930adbf95c943be6b` |
| `plugins/curve_score/curve_score/science_operations.py` | `8da75c40fc46fb222f3673f32fa1e18d71f279f42caf0e0df447dc550b63bda7` |
| `src/scidiscovery/operations/spec.py` | `acc76c1627604c9e8885d4e18273fea2c1a65f4ff13b3787c5e30ea84bc5453d` |

## 2. R1：精确父链恢复缺少实际查询合同（阻断）

**计划位置：** 72—74、214、238 行要求从计划及其父链找回设计时的精确原目标和反馈，包括 revise 的计划；271 行仍把查询文件写为“预计还需”，没有响应字段、边界与实际验收。计划自身已明确未补齐不得实施，因此不能给予 PASS。

**源码证据：**

1. `mcp_root_instance_routes.py:246` 的 `artifact_catalog` 只返回名称、Schema、尺寸、时间及清理后的 labels，至 263 行均无父名称。`:134` 的 inventory 只选每个 logical_name 的最新 revision，无法恢复旧绑定。
2. `mcp_root.py:140` 的完整工具面没有另一项输入/父链查询；`mcp_root_run_routes.py:10`、`:58` 的 Run 列表/状态不投影原输入。科学 payload 也不能代替控制绑定。
3. 父引用已持久化：`service/runs.py:848` 保存 Run 的全部输入父引用；`mcp_root_operation_routes.py:880`、`:900` 保存 Transform 输入父引用。无需新增存储。
4. `service/scheduler_bindings.py:516` 的 `find_name(instance, namespace, object_id)` 已按当前实例和精确对象 ID 查询语义名；`:533` 稳定选择已存在绑定，**不替换成 latest**。这正是所需读能力。

**可达反例：** 物化计划 P 使用目标 O1；同实例随后存在相同 key/statement、不同 mandatory_targets/closure 的 O2。新会话仅知道 P，最新 inventory 展示 O2，现有公开查询不能指出 P 的 O1。只检查 key/statement 会把错误来源当作已恢复。P 再经过一次 `experiment.revise` 后，其父项只有旧计划及确切 ScientificReview，问题仍在；让用户重述原目标、读取数据库或旧工作区均不满足 L4。

**最小闭合修订：**

- 第 4.1 节明确加入唯一新增生产文件 `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py`，清单为 **13 个已有生产文件**。在现有 `artifact_catalog(name=...)` 的响应增加 `parent_artifact_names`，逐项按已有 `envelope.parent_refs` 的顺序，以当前实例调用 `bindings.find_name(namespace="artifact", object_id=parent.artifact_id)`。
- 没有当前实例语义绑定的项返回 `null`；无父项返回空列表。不能换成其他实例名称、latest、内部 ref/ID、摘要或 Worker 路径。相同精确原件已有多个语义绑定时，采用既有 `find_name` 的稳定选择即可；它们绑定同一对象，不需要引入别名权威。
- 规定明确响应上限，超限显式报错而非截断。例如沿用现有来源遍历数量尺度 4096（`mcp_root_operation_routes.py:1109`），在查询函数内检查直接父项数量；不新增分页或递归接口。查询不更新 Run、current、绑定、审批或资格。
- 调度说明写明：对物化计划逐项查询父对象 Schema，找到其直接的 research_objective、intent 和既有科学上下文；对 revise 计划先找到唯一 ExperimentPortfolio 父项并继续查询。之后再沿 intent 找相关反馈，并在下次行动中显式绑定选定原件。
- 将本合同和下述入口验收加入 P3、第 6 节及 L4；前文“不增加读取历史的工具”可保留，但应明确是扩展现有元数据响应。

**为什么不用新增来源别名：** `general_science_experiment_operations.py:223` 的 materialize 没有 feedback 端口，直接输入中的 research_objective 是单项、独立类型；`:149` 的 revise 只含单项 prior_draft 与 ScientificReview。两条限定链都可由精确父名称加已有 Schema 元数据辨认。design 的 wildcard 反馈确实可能另含一个同型目标，所以恢复原目标应从物化计划的直接父项进行，不能从 intent 的同型父项中猜选。若将来出现另一种生产者的实际歧义，再依据那个具体合同处理；本次无须预建通用来源别名机制。

**验收必须覆盖：**

1. 固定安装版本、无父聊天，只从 P 的名称经真实 Root `artifact_catalog` 入口恢复 O1；同时存在 O2 时仍为 O1。
2. P 至少经一次 revise 后重复恢复；回到旧物化计划，不能把相同目标 key 当作同一原件。
3. parent 列表中包含已退休版本时仍能定位其名称；另实例专有父项为 `null`，不泄露名称；空列表与未映射项可区分。
4. 查询前后逻辑状态不变；超限在该入口明确失败。找不到必需父项时记录缺口，不让 Root 补造来源。
5. 找回原件并实际绑定到新 design/review 的 Worker 文件；输入替换改变请求指纹，新输出重新审查。不能只对 Python 内部 parent_refs 做断言就宣称冷启动恢复通过。

## 3. 已核实可在原范围完成的部分

| 路径 | 源码依据、结论及保留的验证条件 |
| --- | --- |
| 同 Run 输出纠错 | `service/runs.py:453` 在 RunOutputError/WorkspaceError 时拒绝该次提交，RunCheckerError 时失败终止，成功后登记并完成。计划复用此生命周期成立；不应增加错误状态或新的纠错 Agent。 |
| blocked 项目进入精确审查 | `mcp_root_operation_routes.py:1329` 先核对 producer 合同，`:1357` 放行精确 reviewer 主体；`:1119` 的 claim gate 只针对 claim_evidence。project 改为 prior_signal 可以解决被审对象不能进入审查的语义错误，同时保持 producer/review 身份。 |
| 审查工作区及负面报告 | `operation_workspace.py:320` 只对 author 做确定性物化，`:347` 解析 review project，`:426` 生成只读模板。`project_packager.py:1233` 的 case 实现校验、`:1249` 的参数检查及 `plugin.py:108`、`:129` 的 uncertainty 检查均位于计划列出的三个文件。拆清输入一致性与 pass 的实现条件足够具体；不需要扩大 workspace 范围。 |
| 假 pass、包装与执行 | `project_packager.py:710` 的报告规则、`:785` 的 ReviewedDeckPackage 条件、`:1429` 的项目/报告/执行准备校验仍承重；`operation_transforms.py:171` 要求 review 精确绑定 project/capability/plan。允许负面封存不赋予执行资格。必须保留 P1 的假 pass、package、Effect 负控。 |
| 正式目标 payload 的传承 | `experiment_intent.py:136`、`experiment.py:206` 是两个目标列表的直接模型落点；`experiment_intent.py:405` 是 materializer；`:422` 已逐字携带 value_assessment，`:434` 携带 priority_rationale。`experiment.py:424` 的 Portfolio 校验同时覆盖物化和完整对象提交；`general_science_experiment_components.py:141` 覆盖完整 revise。没有发现生产调用者必须读取旧 proposal.objective，字段替换无需再改数值下游。 |
| 原目标与引用 | review 增加可选原目标、能力和 feedback 并在 `_object_review_context` 校验可见别名可实施。`operation_contract.py:293` 只把可见 inventory 加入 evidence 枚举，所以计划为本 review 设置 evidence_paths=()、改由其 context validator 检查 plan/objective/feedback 别名是必要且有限的改法。必须包括 collection 的实际别名；可选原件不进入 required_inputs。 |
| 三组可选原件交付 | `spec.py:114` 是 wildcard exposure 限制；`runs.py:235` 只排除 handoff_only，on_demand 会交付 Artifact payload 原字节；`local_workspace.py:150` 写 0400 输入。计划同时覆盖逐项 producer 例外、context_sources、总预算与指纹，能够贯通 Root→Run→Local→submit，而不仅是提示词增加背景。 |
| 结果供下一轮设计 | `transform_adapter.py:62` 形成指标，`science_operations.py:664` 只要求当前 validation plan 的完整检查；总体未来目标文字不会自动变成当前 check。新 design 显式绑定 metric/diagnosis 原件可成立；未来目标未闭合仍不能宣称整体完成。 |

## 4. 两个 curve 文件是否充分

**对本次改变，充分；没有证据要求第三个 curve 生产文件。**

当前 `curve_contract_compiler.py:115` 先按 observable 求全部目标，`:121` 要求与 Agent 的 target_bindings 集合完全相等，`:149` 再遍历那个全集。这确实会把同 observable 的未覆盖目标机械阻断。计划第 3.2.1 节要求依据显式 bindings 选择原合同中的目标、只验证选中范围，已覆盖需要同时改变“选目标”与“展开目标”的实际落点，不能只删除报错条件。

`validate_compiled_curve_contract` 在 `:287` 从已提交合同重建选择，`:304` 调用同一 compiler 重算，`:310` 比较完整机械结果。`science_operations.py:128`、`:151` 的设计和审查入口均复用它；对应提示及同源语义位于同一 science_operations.py。保留未知目标、计划外 observable、参考 series/case/check、单位/阈值和全部当前 curve-score check 的校验，是本计划已经承诺的实现要求。

下游也没有要求把目标全集放回合同：`transform_adapter.py:94`、`:445` 根据合同声明从完整参考库选择所需序列；其后的严格系列一致性检查作用于所选序列。`objective.py:160` 单独逐项评价总体目标，缺少 binding 会报告缺项。独立 reference-coverage helper 可能报告未处置的其他参考曲线，但它不是本计划 score→diagnose 的强制准入门；无需为了追求它的 PASS 扩大目标选择或改评分算法。

父任务保存的 [baseline-probes.json](../evidence/research-correction-continuation/baseline-probes.json)（SHA256 `df45bdd0660d01a40be7c6fb5c4eb1081debbd3a36a9d962737d7f8cba2bb6be`）与源码一致：当前同 observable 子集拒绝，不同 observable 子集可编译而总体覆盖 fail。本审查只核对该记录及对应源码，没有把该工程 fixture 当作 Fig.4 科学结果。

## 5. 全局 Agent inventory 例外、ABI 与真实验收

**未发现共享例外过宽而必须再改核心合同的具体消费者反例。** 源码及父任务目录探针给出的九个现有消费者一致：两项通用 evidence audit、两项 curve contract、两项 parameter evidence，以及 figure request、figure extract、figure audit。

- 通用 evidence audit 的被审 foundation/intake 保留 prior_signal（`general_science_agent_operations.py:283`、`:326`）；读 source_material 不替换被审对象。
- Curve 的原目标/计划/审查/合同继续为严格 typed 信号；只有 reference_bundle 是 inventory（`science_operations.py:422`、`:485`）。后续 Transform 使用原资格规则。
- 参数审查的 package、intake、coverage 保留 prior_signal（`parameter_operations.py:1038`）；参数审批投影另外核对完整 family 和来源（`:477` 起），它是 approval executor，不适用新增 Agent 例外。
- Figure extract/audit 保留 `CompleteTransformFamilySpec`（`figure_science_operations.py:425`、`:614`、`:637`）；Root 在逐项 producer admission 后仍执行 family、cohort、claim 与 revision gate（`mcp_root_operation_routes.py:1114`）。

实现必须只在逐项 `_operation_output_contract` 之前跳过 Agent inventory 的该项检查，不能提前返回整个 admission。现有九项加新 design/review 的共享负控仍须实施验证；本审查不把源码推理称为已通过运行验证。

ABI 16→17 与共享 producer admission 的行为变更一致：当前值在 `spec.py:10`，编译身份使用 ABI（`operations/catalog.py:725`）。只改实验 Schema 不能覆盖所有九个既有消费者。`deploy/install.sh:930` 附近的 profile 校验及 `:964` 的 launch-root 生成、`:1113` 起的既有安装事务可承接重建，暂无新增部署脚本的依据。

P5 在部署前逐项确认必需资格的可接纳重建路径是必要条件；它仍需真实完成。旧 producer 摘要将被 `mcp_root_operation_routes.py:1461` 拒绝，不能假定旧 foundation 或旧曲线重新审查就会自动恢复资格。计划已明确无可接纳来源时阻断发布、旧 R4 只作背景、不改用途绕门，未把部署成功当作科研已恢复。

L1—L5 要求真实设计与独立审查、首轮实际输出与分析、新会话目标调整和第二轮实际输出，且有据停止不冒充两轮完成，验收标准合理。R1 冷启动反例补入后，未发现必须增加公共 Operation 或阶段状态才能实施这些路径。真实 Agent、审批及 solver 尚未运行，不能承诺科学上一定达到 L5。

## 6. 非阻断建议与验证记录

只有一项可选文字精化：把计划中的“既有 rationale”直接指为 `proposals[*].value_assessment.rationale` 和 `priority_rationale`，并在对应 round-trip 验收核对原文保留。现有物化代码已经携带这两个正式字段，不需要新增 rationale 字段或状态对象；此建议不构成第二项阻断。

本次执行了 `rg`/带行号源码读取、Git HEAD/status 查询、计划与证据 SHA256 复算、基线生产文件摘要逐项对照，以及报告文档检查。`git diff --check`、报告空白检查及全部报告链接检查通过，计划 SHA256 未改变。未运行 pytest/wheel/平台/solver；当前任务只审未实施计划，且父任务要求避免与其他工作并发测试。父任务的内存探针仅作为已标明来源的补充证据。

下一版计划只需闭合第 2 节 R1，并复审该具体增量。实施阶段保留原 P1—P6 的聚焦负控、完整候选检查、安装态与资格恢复、真实双轮验收；尤其不能用目标数组非空、compiler 单测或第二轮排队代替真实结果。**本 REVISE 是计划结论，不是实施、部署或科学执行授权。**
