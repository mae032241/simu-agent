# Fig.4 迭代优化调度记录

2026-09-12。用户授权继续多轮测试：获得有依据的良好结果对齐，或在已检验范围内确认不能对齐的原因。掺杂深度、曲线形状及前尾平台是对齐重点。科学方法、参数、反事实及判定由受控角色选择，调度者不制造科学结论。

## 验收和边界

每轮读取已封存进展，选择能减少当前不确定性的最小动作；改计划须匹配独立科学审查，改实现须匹配领域审查，新外部执行仍须精确UI审批。复用已完成数字，计算串行、低资源、及时落盘，不因局部绘图或交付故障重算整批。恢复验收的成功不是本轮科学优化的完成条件。

允许多轮并不保证唯一物理原因一定可识别。最终必须分别说明已对齐的部分、已证实的模型局限、已排除原因、仍不可区分项及最小缺失证据；不得将无解释的inconclusive或未完成执行冒充闭环结论。

## 当前进展

恢复验收已完成，完整成果仍为原封存60单元。本轮首先从原物化计划父链恢复精确foundation/objective/hypothesis/critic cohort；没有以同schema最新记录替代原目标。

1. 新设计预检被 `input_independent_review_missing` 拒绝，未创建Run。旧critic确为completed且审查同一假设组合，但其Operation digest与当前版本不同。`RunService.is_exact_reviewer_output`调用`_compiled`后不再接受旧证明。
2. 对相同假设和基础申请新独立假设审查，预检被 `input_producer_contract_changed` 拒绝，位置为scientific_foundation，未创建Run。该端口为claim_evidence，不能将旧生产合同当作当前证据资格。
3. 当前任务是对已有实验作基于结果的下一轮修订。选择public目录的独立物化计划审查，绑定原目标、已有计划和作者成果、原始参考表、实际结果与四份封存分析。历史假设只作evidence_inventory背景，不更新资格。该精确请求preflight通过，并创建`fig4_iterative_alignment_scope_review_1`。后续是否需要有界修订，由其封存判断决定。

上述是不同公开操作的权限和用途，前两份拒绝请求未被invoke、未修改输入身份或科学资格。现有计划审查路径不授权新的假设或基础证据，也不授权执行。

完整请求、拒绝、诊断依据与当前Run创建记录见 [首轮审查起点](iteration-1-scope-review-start.json)。未为处理上述准入问题修改源码或部署。合同资格与提示问题保留为本轮框架故障账本；不以科研重算消除版本问题。

## 独立审查完成与当前停点

`fig4_iterative_alignment_scope_review_1`已completed，封存verdict为revise。其认为原回顾性计划的历史效力有效，但已经完成；作为下一轮重复执行不会增加证据。它请求有限的逐材料D/Cs候选包络，分开参数选择观测与独立过渡/尾段验证，结果仅对所测常数D范围作结论。若仍有结构失配，保留后续改变曲线族/假设的目标；有效联合不确定度仍是更强对齐结论的条件。这是封存审查的转述，数值候选尚未由设计者确定。

该审查同Run发生两次可修正输出拒绝，均显示`experiment.review.verdict_consistency`、位置`$.payload`，之后成功封存。Root诊断未指出精确冲突字段和值，不能假称已定位到具体候选错误；不把它记作输入重新准入或工具超时。[完成返回](iteration-1-scope-review-completed.json)保留原始证据。

按此review准备的`fig4_iterative_alignment_plan_revision_1`预检通过，但尚未invoke、没有新Agent或新求解。用户随后询问合同完整性、旧资格及应先修兼容还是继续实验；调度者建议先修兼容性，以免后续科学需要修订假设时再次受版本限制。精确待执行请求见 [修订预检](iteration-1-revision-preflight.json)。

在线目录另确认：假设提案、critic及假设修订没有可选结果/分析/当前进度端口；计划设计和计划审查有对应反馈端口。故“有限分析链已可用”不能外推为“结果驱动假设变化的完整迭代链已可用”。该不足未在本轮改源码，后续修复须保留旧记录身份、科学资格作用域及新执行审批。

## 兼容性源码修复

随后用户授权先保存 Git 检查点，再制定最小计划、独立审查通过后执行。检查点为 `be5da77`；[兼容修复](COMPATIBILITY_IMPLEMENTATION.zh-CN.md)已按计划完成，并通过独立实现复核。三个生产文件、82 项不同定向用例通过，串行峰值约 184 MiB，未部署。原科研记录及待执行计划修订没有改变，安装后必须重新验证原绑定；假设反馈入口仍单独待办。

## 安装后原请求预检与恢复迭代

2026-09-12：三个修复文件安装摘要均匹配，服务 active，用户重新绑定 M7-test0。此前因旧 reviewer digest 和旧 foundation producer digest 分别拒绝的两份原请求，现均 admissible=true；没有修改其绑定或请求内容，也没有额外发起假设审查。按已完成的独立范围审查，重新预检待执行计划修订后创建 fig4_iterative_alignment_plan_revision_1，预算链2次中的第1次，并分派全新受控修订 Agent。未执行新仿真。完整控制响应见 compatibility-postinstall-preflight-and-iteration.json。

## 计划修订首轮超时与有界续接

首轮在 900 秒预算内未完成封存：16:02:10Z 和 16:02:54Z 两次输出拒绝均定位 experiment.revision.case_and_validation_closure、payload.proposals[0]，同时有 proposals 最小长度错误。诊断没有指出具体关系，不能判断其科学合理性或把它归因于历史输入重新准入。控制于 16:03:40Z 记录 run_timeout；delivery_preserved/draft_available/resume_available 为 true，recovery_pending=false。全程 native_coverage=unobserved，中途读取/编辑与原生命令错误不可据此还原。

据实际保存草稿，创建 fig4_iterative_alignment_plan_revision_completion_1，resume_from 指向首轮；同一组冻结输入、只针对草稿与输出合同纠错的新受控说明，preflight 与 invoke 均通过。累计预算2次，当前第2次；原同 Operation Agent 空闲后重新打开新任务，复用记忆不代替新绑定和恢复记录。未启动仿真，也未自动扩展尝试预算。见 iteration-1-plan-revision-timeout-and-continuation.json。

续接首次提交于16:06:32Z再次遭遇同一输出拒绝。只读源码定位诊断信息损失：schema/experiment.py 的 ExperimentProposal._proposal_is_bounded 包含多个 case/factor/数量/comparison 引用关系检查，大多抛普通 ValueError；operation_contract.py:validation_diagnostics 对普通 value_error 统一使用泛化消息，仅显式 SemanticRuleViolation 的 DeclaredDiagnostic 才保留具体诊断。当前返回不足以确定实际触发条件，不能把任选一个候选规则认定为本次根因，也不能凭位置断定 proposals 本来为空。未读取失败科学草稿或更改生产校验，受控角色继续使用可见合同纠错。

## 修订封存与新计划独立审查

续接 Run 于16:09:53Z完成，从创建到完成319.44秒。其7次拒绝依次包含3次 proposal 输出字段检查及4次 experiment.revision.review_target 输出上下文检查，最后成功封存；加上首轮2次，本次修订链共9次提交拒绝和1次超时。后者源码 general_science_experiment_components.py 的修订检查比较 study_kind、objective_key、objective、selected_hypothesis_keys 及 experiment_key 集合，但返回未指出哪项改变，实际触发字段仍未知。此处不能把规则定位冒充完整个案根因定位。没有在科研测试中更改校验器。

封存修订提出两材料各3×3主网格及一个收紧数值对照，共20个串行案例；用前部浓度和位置选择参数，保留过渡宽度、前部对齐残差及尾部浓度/斜率作验证，明确有限常数D族与相对改善的结论范围。此为设计者提案，尚非独立认可或实验结论。16:15:02Z 创建 fig4_iterative_alignment_plan_review_1，绑定新计划、原始目标、原执行上下文与相关封存进展、结果和参考表，预检通过并分派全新独立审查者。新求解仍未启动。完整受控响应见 iteration-1-plan-revision-completed-and-review.json。

## 新计划审查输出拒绝、超时和停止执行

fig4_iterative_alignment_plan_review_1 从16:15:02Z创建，16:22:00Z出现首次输出拒绝，至16:24:21Z累计6次；均为 output_payload 的 experiment.review.verdict_consistency、位置 $.payload、普通 value_error 泛化消息。600秒截止16:25:02Z后仍无封存审查，Root于16:25:42Z按精确状态与 last_activity 比较记录 run_timeout。没有产出有效科学审查，不能将其理解为科学上的 reject/revise，也不能据此授权新计划执行。

首次失败收尾显示 recovery_pending=true；Agent退出后重复同一幂等失败收尾，控制确认 delivery_preserved=true、recovery_pending=false。当前尝试预算 used=1/limit=1，draft_available/resume_available=false；交付已保存不等于当前预算可继续调用，也不等于已有科学成果。未自动增加次数或创建同内容新审查。旧计划结果和本轮已封存修订均保留，新TCAD作者与求解均未启动。完整返回见 iteration-1-plan-review-failure.json。

只读源码核查定位到 ScientificReview._review_is_coherent（schema/research_cycle.py），模型层普通 ValueError 的候选包括重复 hypothesis_key、finding.evidence_keys 未包含在 evidence.source_key 集合中、hypothesis_portfolio 目标缺少 hypothesis_reviews。这些与统一命名 verdict_consistency 不完全对应；operation_contract.py 将具体错误信息抹为泛化提示。上述三个相关源码文件与安装文件摘要完全一致，排除这些文件漏装；见 iteration-1-review-validator-installed-check.json。Root没有读取未封存的审查候选，不能据此判断本次触发哪项或宣称某个科学 verdict 已知。

本轮已验证历史资格兼容修复生效，但完整迭代尚未完成。目前合理停点是保留成果，先让这项输出错误可精确定位、可有界纠正，再续接独立审查。不能以无限重试替代纠错反馈，也不能绕过必需的独立科学审查启动20案例。到此，自安装后修订开始共15次提交拒绝、2次超时；再计入安装前范围审查的2次拒绝，该科学迭代阶段累计17次拒绝。均不包含2份安装前准入拒绝。未运行工程测试或更改生产源码。


## 2026-09-13：审查六次拒绝的精确根因与源码清理

通过平台工具调用中的文件 patch 顺序在内存还原6份失败提交；不执行历史命令，不读取或转述 Agent 推理，不把未封存审查当科学结果。6份均在 `payload.findings[5].evidence_keys[1]` 引用 `current_progress_002`；它真实绑定原 Run 的 `fig4_morphology_objective_revision_4.output`。旧 ScientificReview 却要求再在本输出 evidence 表登记它，抛出 `scientific review finding references undeclared evidence`；诊断转换又抹成泛化 value_error，并冠以误导性的 verdict_consistency 规则名。

此为嵌套模型职责错误和诊断丢失，不是新旧安装文件错配。超时后才写入的最后恢复 payload 可通过旧模型，不能用它解释之前6次拒绝。最终静态重建与已保存副本一致；原记录及失败状态保持不变。另有3次原生 apply_patch 失败仅在平台工具记录可见，Root native_coverage=unobserved；本轮没有将未观测误报成无错误。

用户随后明确要求全面删除同类校验。对实际50项 Operation 从模型、上下文、审批与消费路径作清理，见[逐项审计](../operation-validation-ownership-cleanup/AUDIT.zh-CN.md)。保留真实来源/执行/案例/收据和审批身份，删除来源二次登记与无用完整抄表义务。新源码逐份重放原6份失败提交，全部通过模型及原14项真实绑定别名检查；见 `../operation-validation-ownership-cleanup/FIG4_REPLAY_AFTER.json`。这是工程回归，不是审查通过或科学完成。源码安装后仍须创建新受控审查 Run，原失效 Run 不重开。
