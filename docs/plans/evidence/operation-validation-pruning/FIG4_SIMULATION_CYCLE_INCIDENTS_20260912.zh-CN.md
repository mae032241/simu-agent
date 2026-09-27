# Fig.4 本轮仿真流程错误与来源记录

日期：2026-09-12。实例：M7-test0。状态：形貌目标修订第三 Run 已封存；最终独立审查因用户要求暂停而终止，未产生审查结论。当前工作为全部 Operation 的工程校验审计。

## 范围与证据规则

本记录覆盖 `fig4_continuation_execution_1`、其恢复与分析，以及用户将本轮目标改为掺杂深度、曲线形状、前后平台一致性的续接过程。不是所有历史开发问题的重新审计，不替代封存科学结果。

工程事实来自 Root `run_status`、`run_list`、`execution_status`、公开准入回复、既有工程复现记录及只读源码检查。科学内容仅引用 completed Run 的 sealed_output 与 scheduler_signal。不读取未提交草稿，不将子 Agent 聊天视为科学证据。此次没有改生产源码、运行 pytest 或新启求解器；后续完成了有资源上限的串行安装包微型探针，记录如下。

本次相关 Run 的终态、计数与具体公开诊断保存在[诊断快照](FIG4_SIMULATION_CYCLE_DIAGNOSTICS_20260912.json)。该快照不包含草稿、子 Agent 科学聊天或凭据。

源码检查基线 HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`；工作区已有大量未提交修改，因此 HEAD 不能代表所有正在运行的代码。后续先核对 8 个关键文件，再比对审计定位到的 38 个组件/模型/工具实现文件，安装包与工作树均逐字节相同；这不是全仓库版本一致性证明。

## 已发生的问题

| 编号 | 现象与影响 | 来源与证据 | 当前处置及未解项 |
| --- | --- | --- | --- |
| E1 | 原执行因必需 TDR 收集失败而为 failed/97。 | completed `fig4_continuation_execution_analysis_recovery_complete_1` 明确记录：声明 `*.tdr`，实际为 `*_fps.tdr`；日志有六案例写出与 END_CASE。缺陷在输出声明与收集路径的交接。 | 13 个必需产物已通过受控恢复绑定，当前分析无需为补证据重跑。原 failed/97 不改写；任何未来执行前仍须修正并审查输出声明。`execution_status=collected` 只表示结果已收集，不是求解成功。 |
| E2 | 评分请求的轴结构和比较结构错误，被归为 PLX 格式不支持。 | [analysis 3 根因核查](../../reviews/TCAD_ANALYSIS_3_BLOCKER_ROOT_CAUSE.zh-CN.md)保留实际调用及安装包合成复现：字符串轴在解析前失败，正确轴对象使同一合成 PLX 可解析；外层把参数错误变成 `tcad_layout_unsupported`。 | 历史已证实的错误分类与纠错问题。不能据失败请求证明真实 PLX 不受支持，也不能由 Root 代选科学算子。后续生产验证成功不追改旧报告。 |
| E3 | 输入允许历史案例身份缺失，工具、恢复、报告却要求另一套显式映射；固定状态关系又造成连续返工。 | 同一根因核查列明 analysis 3 的六次拒绝及源码。`fig4_continuation_execution_analysis_1` 终止原因是绑定清单与实际输入身份不一致，累计 8 次拒绝。 | 存在接口表达及职责边界问题，不能全部归为 Agent 格式错误。后续修复/恢复有效范围以各自验收为准，不声称所有类似规则已清除。 |
| E4 | 分析过程中出现计算预算耗尽、超时或 Agent 返回但未封存。 | Root 记录：analysis 4、6 及 independent 1 有 `calculation_work_limit`，最终 failed；独立分析 1 未形成受控结果。 | 无封存就是未完成，不能接受聊天结论。应保留尝试和新 Run 的独立身份；本次未重新判定每次耗时究竟来自计算、模型生成还是重放。 |
| E5 | 完整残差诊断超过单条 CalculationRecord 的 32 KiB，先前只能用 129 点完成。 | `fig4_continuation_residual_diagnosis_retest_1` completed，但保存了两条 `diagnostic_unavailable` / `calculation record exceeds 32 KiB`。 | [产物引用修复](ANALYSIS_ARTIFACT_REFERENCES_COMPLETION.zh-CN.md)把详情与短记录分开。安装后 `fig4_continuation_analysis_artifact_retest_1` completed，0 工具错误、0 拒绝，保留 257 点详情和 PNG；该 live Run 未调用原生脚本发布工具，不能声称这一支路也已实测。 |
| E6 | 0.15 decade 被继承成充分性门，但缺少为何取该数值的证据，且不符合用户当前强调的形貌优先级。 | 已读绑定谱系中最早见 `fig4_e55_experiment_intent_1`：只说明避免相对优胜者冒充复现，没有数值推导。completed `fig4_morphology_objective_change_review_2` 要求三项目标分开，整体误差降为辅助。 | 属于目标、指标和科学审查的选择问题，不是计算程序算错。正在修订完整计划；原阈值及旧结论保持历史身份。不由 Root 发明新容差。 |
| E7 | 首次形貌变更审查连续 5 次因 `experiment.review.verdict_consistency` 被拒，只有 `$.payload` 和泛化原因。此前 completion_review_1 已发生 10 次类似拒绝。 | Root `fig4_morphology_objective_change_review_1` 的 diagnostic_summary。工作树 `ScientificReview._review_is_coherent` 检查键唯一性和引用闭合，不从各维状态推导 verdict；`operation_contract.validation_diagnostics` 把普通 ValueError 转成泛化提示。 | 首 Run 已 failed；第二个新 Run 在不可变指令中补明现有结构规则后 completed，0 拒绝。未读被拒草稿，不能断言具体是哪个字段或唯一性分支；第二次成功只是规避成功，不是框架缺陷已修复。停止原因文本写“四次”，最终计数因停止前又到达一次而为 5，以控制计数为准。 |
| E8 | 直接走新设计的 preflight 因 `input_independent_review_missing` 拒绝绑定的 hypothesis_portfolio。 | 本轮 `science.experiment.design.v1` 的公开准入返回；未创建 Run。 | 该返回对当次绑定有效，未绕过。目标调整随后走目录已有的“完整旧计划审查 → 根据确切审查修订”路径。缺少进一步资格谱系核查，不能称该拒绝本身就是 bug。 |
| E9 | 首次完整目标修订超过 900 秒截止时间仍无封存，也无工具错误或提交拒绝。 | `fig4_morphology_objective_revision_1` 创建于 01:00:49 UTC，截止 01:15:49，01:17:33 由 Root 终止并记录 `run_timeout`；最后公开活动为打开任务。 | 失败后控制报告草稿与续接材料可用。第二 Run 以 `draft_from` 受控绑定原草稿，缩窄为最小字段更新，复用同一编译角色但使用新 workspace/输入/预算。不读取草稿判断科学内容，也不把原因猜成 OOM、工具失败或校验失败。具体耗时来源未证实；截止时间到达后 `run_status` 仍显示 running 的终止机制需另行核查。 |
| E10 | 第二目标修订连续 3 次拒绝，`proposals[0]` 的 value_error 没有具体关系原因，同时出现 proposals 的 too_short。 | `fig4_morphology_objective_revision_2` 的 Root 诊断，01:26:54 UTC 停止并记 failed。工作树 `ExperimentProposal._proposal_is_bounded` 仍有多个普通 ValueError 分支，包括案例计数、因素/设置、comparison.required_observables 以及 claim 引用等关系。 | 停止盲试；第三新 Run 在不可变任务中列明已有关系，从封存旧计划做最小更新。没有读取被拒草稿，不能断言是 case_count、某处引用或空 proposals，尤其不能把可能的级联 too_short 当成真实草稿数组为空的证明。 |
| E11 | 草稿可用性与后续准入出现变化，第二 Run 保留 delivery 但没有 draft/resume；再绑定第一 Run 草稿被拒。 | 第一 Run 失败时 recovery 为 draft_available=true，第二 Run 用该 draft_from 准入成功；第二 Run 失败后第一、第二 Run 均 draft_available=false。安装编译确认修订 Operation 的 max_attempts=2；`runs.py:_check_recovery_attempts` 对起始 Run 加 draft/resume 后代计数，达到 2 即拒绝。 | 恢复次数预算已耗尽能解释此次变化，不是字节必然丢失。Root 路由仍将不同异常泛化为 `draft_source_unavailable`，造成诊断损失。第三 Run 不带 draft，绑定原完整封存计划后成功交付；没有读取旧目录绕过准入。 |

## 可量化的重复工作

2026-09-12 本次读取最新 50 个 Run 的快照中，按名称限定为 execution_analysis 系列及两个 diagnosis/artifact retest，共 13 个分析 Run：9 completed、4 failed，累计 34 次输出拒绝。该数字是这组明确名称的子集统计，不是全部历史错误数；completed 也可能包含多次拒绝。两次首次审查失败（completion_review_1 的 10 次、morphology change review_1 的 5 次）不计入这 34 次。

## 来源分析与证据强度

1. **可见合同与实际要求之间的信息丢失。** 参数结构、历史身份表达和错误原因在跨边界传递时发生损失，造成 Agent 无法据当前回复有效纠错。E2、E3 有既有工程复现；E7 本轮仍能观察到泛化诊断。不能因此推论所有校验无效，也不能把键引用一致性误称为科学结论公式。
2. **将机械记录塞回 Agent 输出。** 重复案例映射及计算记录搬运带来返工和体积问题。E5 已用独立产物保留在真实案例证明改善；历史报告的科学结论不会因封存结构改进自动变得更强。
3. **完成证据的层次混用。** 文件收集失败、求解步骤已发生、证据恢复完整、科学目标是否满足是不同事实。E1 允许恢复后继续有限分析，但不能把原外部执行改为成功。
4. **指标选择偏离研究重点。** E6 表明“数值计算可以正确完成”与“指标足以评价用户目标”是不同问题。将单一整体误差作为总门会掩盖深度、形状和平台各自的判断；更细结论由修订及独立审查的封存结果决定。
5. **有限证据本身不等于工程错误。** 检测状态、不确定度或用于机制区分的反事实不足，是 completed 分析明确保留的科学限制。工程链跑通不能自动补齐这些信息；局部不可判不应伪装成系统故障。

E7 的最紧源码边界是 `src/scidiscovery/artifact_agent/schema/research_cycle.py:122` → `src/scidiscovery/operation_contract.py:85`。前者使用普通 ValueError 报告结构关系；后者只有显式 SemanticRuleViolation / DeclaredDiagnostic 才保留具名原因和字段位置，普通 value_error 走通用文本。`src/scidiscovery/general_science_experiment_components.py:381` 仍用 `experiment.review.verdict_consistency` 标记整个 payload 校验，名称也不足以区分这些关系。已有明确诊断通道可用；是否只需迁移这些具体规则，应在后续最小修复中验证。本次没有改这些实现，且没有证据指出被拒草稿究竟违反其中哪一条。

E10 暴露相同诊断路径在另一个角色中的可达性：`src/scidiscovery/artifact_agent/schema/experiment.py:233` 仍要求若干机械关系在 proposal、cases、comparison_contract 和 resource_estimate 重复吻合。源码确认这些要求存在，公开拒绝却不能定位具体一项；根因分析应同时审视重复填写成本与错误信息投影，不能仅让模型无限修改科学文本，也不能在没有草稿证据时把所有结构检查一并判为无意义。

## 当前续接与完成后补记

### 安装版本、校验层与实例隔离核查

用户要求先排除版本更新问题，必要时用新实例测试。本次只读比对确认以下 8 个文件在 `/opt/scidiscovery-m7/site` 与工作区逐字节相同：`schema/experiment.py`、`schema/research_cycle.py`、`operation_contract.py`、`general_science_experiment_components.py`、`general_science_agent_operations.py`、`interfaces/mcp_root_operation_routes.py`、`service/runs.py`、`operations/spec.py`（前两项位于 scidiscovery/artifact_agent，interfaces/service 同属该目录）。

安装文件时间为 2026-09-12 00:24:50 UTC，control 与 approval-ui 的启动时间均为 00:24:57 UTC；二者 active，PYTHONPATH 均为 `/opt/scidiscovery-m7/site`，PYTHONNOUSERSITE=1。运行摘要 catalog_digest 为 `b0b541582179374a5e562465492615390f19cdbbe2edf69adb797beccc5cfbcc`。当前生成的修订/审查 Agent 配置指向同一安装目录，Operation 摘要分别与控制端派发的 `d46cc12241b5…` / `f6fdf24c8242…` 一致。没有以版本号或 HEAD 单独替代这些核对。

使用安装包做了一个不访问实例、数据库或科学草稿的微型合成复现：合法 ScientificReview 先通过 JSON 校验；随后只重复 `evidence_item_keys`，原始错误为 `scientific review evidence_item_keys must be unique`，`validation_diagnostics` 输出却变成 `path=$`、`Value violates the declared type, bounds, or field relationship.`。这证明该诊断丢失可以独立于旧实例发生；不证明真实被拒草稿恰好也是重复证据键。首次探针误用严格 Python 模式传 list，被 tuple_type 拒绝；改用实际 JSON 输入模式后上述正负对照成立，该夹具错误不计为生产事故。最终探针 0.20 秒、峰值 RSS 38,460 KiB，地址空间上限 512 MiB；未运行 pytest 或求解器。

结论：本次已确认的泛化诊断属于现有校验/诊断层缺陷，不是这 8 个文件未安装、服务未重启或旧实例独有的问题。无需为验证这一缺陷新建实例；换实例不会改变同一模型与诊断函数。具体 proposal 拒绝分支仍未由公开诊断确定。E11 的 recovery 检查另含身份、保全内容、完整性与恢复次数上限等分支，Root 路由又把所有异常统一成 `draft_source_unavailable`；不能仅从该码认定材料丢失或版本错误。

- 新目标修订首 Run `fig4_morphology_objective_revision_1` 已超时失败，第二 Run `fig4_morphology_objective_revision_2` 因连续 3 次泛化拒绝停止；第三 Run `fig4_morphology_objective_revision_3` 于 01:34:58 UTC completed，0 拒绝、0 工具错误，成果为 `fig4_morphology_objective_revision_3.output`。这是修订成果封存，不是独立审查通过。
- `fig4_morphology_objective_revision_review_1` 于 01:36:40 UTC 启动，因用户要求先暂停科学审查，于 01:37:50 终止，0 拒绝/0 工具错误、无封存成果。状态 failed 的控制记录不代表计划被科学否决。
- E9 的后续源码核查：`run_status` 为纯查询，不负责超时转移；调度者在截止后 104 秒记录终止是本次实际延迟，不把这一事实描述成查询接口必须写状态。具体生成耗时仍未知。
- 本次全目录审计确认 14 项需要删除硬拒绝、机械化、移位或修复诊断的候选；逐一列明实际消费者、保留不变量、兼容风险与证据强度，见[全部 50 个 Operation 校验复扫](../operation-validation-reaudit/REPORT.zh-CN.md)。未修改这些生产校验实现。
- 如后续按新目标分析，再追加逐目标的分析交付与局限；本次仅调整目标，不自动重跑求解器。

本记录是错误和证据的汇总，不是新修复计划。后续若修代码，应针对已触发且原因明确的缺陷另定最小范围，避免把一次泛化诊断扩成全系统重构。
