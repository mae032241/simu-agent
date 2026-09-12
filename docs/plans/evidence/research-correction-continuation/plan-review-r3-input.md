# 校验纠错与跨轮续研最小实施计划

状态：**2026-09-08 计划 R3 增量待审；R2 计划已通过，P1 正常包装正控发现初始化证明丢失，拟增加一个现有包装文件后复审；未部署。** 本文从两条路径细化升级为唯一实施入口，明确修改决定、文件责任、执行步骤、验证和发布边界。源码根为 `123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`，核查 HEAD 为 `2edac5d317a74056869a567bd0daa7f556ecbc85`；实施基线包含当前已修改、已删除及未跟踪文件，不等于干净 HEAD。

## 1. 文档所有权与完成范围

| 文档 | 拥有的内容及处置 |
| --- | --- |
| 本文 | 完整实施步骤、目标与反馈合同、审查修复、发布及验收的唯一当前拟议规则 |
| [目标列表与反馈原方案](EXPERIMENT_DESIGN_GOALS_AND_FEEDBACK_MINIMAL_PLAN.zh-CN.md) | 已被本文承接的设计来源；原文保留供精确审查追溯，不作为另一个并行实施入口 |
| [原方案独立审查](reviews/EXPERIMENT_DESIGN_GOALS_AND_FEEDBACK_FEASIBILITY_REVIEW.zh-CN.md) | 保留对 SHA256 `bd8ae03c1fe4347c270fa820709b2551b882596a0967d635a408e0188122a644` 的 REVISE 结论；本文第 3 节落实其 R1/R2/N1/N2/N3，尚不代表新计划获得审查通过 |
| [完整计划独立审查](reviews/RESEARCH_CORRECTION_CONTINUATION_IMPLEMENTABILITY_AND_GOAL_FIT_REVIEW.zh-CN.md) | 保留对 SHA256 `182fc74bdf66248df9b5e4802785fba61538f49e4cf81326921bcc9767cfe9f3` 的 REVISE 结论；父链查询提案由第 3.4.1 节承接，不改写历史报告 |
| [最小范围独立审查 R1](reviews/RESEARCH_CORRECTION_MINIMAL_PLAN_REVIEW_R1.zh-CN.md) | 保留对 SHA256 `4e4b0c1d6ee6342b48a8519527d26e22f383dedf8e69683b7b0ecaddaaa4126b` 的 REVISE 结论；唯一阻断为查询合同缺失，本次增加一个现有查询文件及其验收，待独立复审 |
| [独立复审 R2](reviews/RESEARCH_CORRECTION_MINIMAL_PLAN_REVIEW_R2.zh-CN.md) | 对冻结 R2 计划 SHA256 `acc011a04ff2b6b0d7b7b2383f921c56faafe1e360cc53fdbe13f9bc1f01c93c` 的 PASS；输入副本和原报告保留，P1 新发现按本版第 2.3.1 节修订，不能继承 R2 对新范围的 verdict |
| [author 修复记录](TCAD_AUTHOR_FAILURE_MINIMAL_REPAIR_PLAN.zh-CN.md) | 保留原工程修复和 R4/R5 历史；不因新提案改写 blocked 或预检拒绝 |

本轮固定现有 Fig.4 研究案例。科学目标、实验参数和研究结论仍由编译目录中的科学 Agent 根据确切封存输入决定；本文不代写实验，不规定必须走某个科学阶段。下面的次序是工程验收次序，不是新增科研 DAG。

完成标准是：新设计者根据既往记录选出可执行的本轮实验；author 完成；独立审查能评价成果和缺口；经过原审批与执行路径取得结果并分析；新会话中不继承聊天的设计者据此调整目标；下一轮经审查和 author 后实际开展。第一轮结果进入第二轮设计是最小里程碑；第二轮真正开展才完成本轮路径验收。若研究判断认为应停止，则保存有据的停止结论，不为验收制造实验，也不声称“两轮执行”已完成。

### 1.1 直接修改哪些 Operation

2026-09-08 已通过 Root `operation_catalog(scope="all")` 核对当前安装目录的 49 个 Operation。以下名称、执行种类、端口和 review edge 来自该目录，usage、校验器及资源绑定对照当前源码。新增端口尚未注册；本节是具体变更合同，不能把拟议端口当成已可调用能力。部署后仍以重新查询的编译目录为行动权威。

| 现有 Operation | 声明/输入的具体变化 | 输出、校验与后续绑定 |
| --- | --- | --- |
| `science.experiment.design.v1`（public Agent） | 保留 foundation/objective/hypothesis/critic/execution_context；增加 current_progress、experiment_results、result_analysis 三组可见只读端口；在 outputs[experiment_design_intent].context_sources 纳入三组，输入总上限 32 MiB | 输出仍是 ExperimentDesignIntent，但 payload.proposals[*] 增加 objectives/current_objectives；同源 Schema、experiment_context 和提示同步。当前可确定错误仍在同 Run 修正；本轮选择和后续条件由 Agent 写入正式意图 |
| `science.experiment.materialize.v1`（support Transform） | 输入形状、cohort 和 experiment_lineage 不改；科学意图仍绑定同一 foundation/objective/hypothesis/critic，工程意图仍只绑定 intent；不新增反馈端口 | 在 materialize_experiment_design_intent 中复制完整目标和 current 子集，补精确总目标；只物化意图已声明的本轮 case。experiment_plan 输出仍通过 review edge 指向 science.object.review.v1 的 experiment_plan |
| `science.object.review.v1`（public Agent） | 保留 experiment_plan:prior_signal；增加 research_objective、execution_context 两个可选 typed prior_signal 和三组 feedback；全部可见来源加入 scientific_review.context_sources；输入总上限 32 MiB | 仍输出 ScientificReview。object_review_prompt/context/语义合同增加对原目标、当前选择和反馈的审查；evidence_paths=()，本 Operation 的 context validator 检查实际输入别名。报告可非通过封存，不把缺少可选输入变成异常 |
| `science.experiment.revise.v1`（public Agent） | 保留 prior_draft:revision_base 和 change_request:change_request 两个输入，不加续研端口 | 仍输出完整 ExperimentPortfolio，使用新目标模型并保留后续目标；同步 experiment_prompt 和 revision 语义说明。输入 change_request 必须是该计划的 ScientificReview；新输出仍走同一个计划 review edge |
| `science.curve.contract.design.v1`（public Agent） | 端口和输出类型不变；更新现有提示、可见语义及确定性编译器 | 复用现有 target_bindings 精确选择本轮目标；取消按 observable 强制覆盖全部同类目标的要求，保留所选目标、参考曲线、case 和本轮验证要求的一致性检查 |
| `science.curve.contract.review.v1`（public Agent） | 端口和输出类型不变；更新现有审查提示与可见语义，使用同一修订后的编译校验 | 独立判断未覆盖目标是否影响本轮实验成立及结论边界；科学理由写入正式 ScientificReview，不将总体覆盖不足机械判为拒绝或通过 |
| `tcad.deck.review.v1`（public Agent） | 仅将 project 输入由默认 claim_evidence 改成显式 prior_signal；保留其他原输入、参数 cohort/guard、工具、预算及 scientific consequence | 输出仍是 DeckReviewReport；修改 review_context/validate_deck_review_task_output 与 reviewer prompt：输入身份和报告一致性始终检查，项目实现完整性是 pass 条件，允许有据的 revise/blocked 且 execution_ready=false |
| `tcad.reviewed-deck-package.v2`（support Transform） | 端口和输出类型不变；仅修复既有包装组件重建 declared-source.v2 项目时丢失初始化证明 | 从精确被审项目保留 initialization_attestation，严格核对重建后的项目绑定并保持整对象一致性比较；不生成新证明、不放宽审查或执行资格 |

TCAD 三个 author Operation 的端口、工具和预算不扩展。initial 接收新计划，author.revise 仍接收确切 prior_project 和 DeckReviewReport，runtime-failure 仍处理同一任务的运行失败。shared schema 会改变它们的编译身份，但不增加“阶段”参数或目标筛选逻辑。

### 1.2 在 Operation 机制的哪两处改核心

反馈端口直接复用当前 `_agent_input`，它已支持 `schema="*"` 对应的 opaque codec 和 wildcard_schema；在 general_science_experiment_operations.py 中定义一组本地共享端口，供 design/review 引用。每个端口的具体参数是：

```python
_agent_input(
    port_name,  # current_progress / experiment_results / result_analysis
    port_description,
    "*",
    media_types=("*/*",),
    min_items=0,
    max_items=4,
    max_item_bytes=8 * 1024 * 1024,
    exposure="on_demand",
    usage="evidence_inventory",
)
```

这只是声明片段，不新增公共 helper。要让它真正可用，必须同时完成：

1. `InputPortSpec.issue`：现有 wildcard 判定中的 exposure 条件从仅 handoff_only 改成允许 handoff_only/on_demand，仍要求 schema/media 通配成对且 usage=evidence_inventory。其他通配用途继续拒绝。
2. `Root._validate_producer_output_admission`：在每个 bound input 的 `_operation_output_contract` 调用前，仅对 executor.kind=agent 且 usage=evidence_inventory 跳过该项 producer 资格检查。实例、数量/字节、显式 current、完整 family、cohort、revision 和 claim 检查仍由原路径执行。对 review 的 project:prior_signal 不适用这个例外，仍须匹配当前 producer 合同和确切 review edge。

之后继续使用现有冻结输入→Run→只读 Local 文件→Worker assignment→submit→Artifact 父链，不增加读取历史的工具或进度服务。所有依赖该行为的共享编译身份由 ABI 16→17 更新。review project 的用途纠正与 inventory 的只读例外是两项独立修改，不能只做其中一项就声称两条路径都已修复。

### 1.3 一次本轮设计应如何绑定

以下是实施后的绑定表；尖括号表示必须从实例中解析的确切 artifact_name，不是可直接发送的名称，也不意味着现在已有这些输出。

| design 的输入端口 | 本次绑定的原件 |
| --- | --- |
| scientific_foundation | `<当前合格科学基础>` |
| research_objective | `<该基础的精确原始目标合同>` |
| hypothesis_portfolio | `<当前合格假设集合>` |
| critic_review | `<该集合的精确批评结果>` |
| execution_context | `<相关能力背景>`，可不绑定 |
| current_progress | `<前轮计划>`、`<前轮计划审查>`、`<前轮项目>`、`<项目审查>`中至多四项相关原件；没有的不能编造 |
| experiment_results | `<前轮 metric_report>`、`<相关 curve_bundle 或原始输出>`中至多四项；可为空 |
| result_analysis | `<前轮 layered_diagnosis>`及其他相关分析中至多四项；可为空 |

输出 intent 完成后，Root 为所选计划审查行动调用目录声明的 materialize helper。科学输入绑定为该 intent 和设计时同一 foundation/objective/hypothesis/critic；得到新的 experiment_plan，再将它与原目标、必要能力和相关 feedback 绑定给 object review。不能假设 reviewer 会自动读到 intent 的父链内容，必须显式绑定文件。

当前 Run 文件交付的是 Artifact 的科学 payload 原字节，不会自动附带生产者完整 RoleResultEnvelope 或 scheduler_signal。Root 读完成状态中的 handoff 判断下一行动；下一 Worker 靠显式文件理解科学内容。因此完整目标、选择理由和后续条件必须存在 plan 的正式 payload，缺口依据保存在审查/诊断的正式 payload；不能只写 handoff。历史记录若只在 handoff 中说明某事，不能宣称绑定 project 就已把该说明交给新 Agent，也不能复制聊天冒充原件；该上下文缺席须如实说明。

### 1.4 计划到结果的具体端口连接

这里给出当前案例所需的可用连接，供 Root 根据科学结果和目录选择；support 项只在所选 public 行动需要时调用，不构造另一套固定调度表。

| 需要完成的事情 | 当前目录中的 Operation 与输入输出连接 |
| --- | --- |
| 给新计划建立曲线合同 | science.curve.contract.design.v1：research_objective、**新 experiment_plan**、**新 experiment_review**、reference_bundle → curve_contract；其 review edge 指向 science.curve.contract.review.v1，绑定同一组原件并增加 curve_contract → scientific_review |
| 实现本轮 | tcad.deck.author.initial.v1：execution_capability、**新 experiment_plan**，以及本案例所需的新 curve_contract、experiment_review、curve_contract_review 和既有声明的合格参数组 → project |
| 审查实现 | 读取 author 条目的 review edge；tcad.deck.review.v1 绑定 project 及 author 使用的同一 INITIAL_INPUTS → review。参数组有则完整绑定，不能只传 project 丢掉声明的基础输入 |
| 准备执行 | 已选 tcad.study.execute 后，使用其所需 tcad.reviewed-deck-package.v2 helper：project、review、capability、experiment_plan → reviewed_package。包装仍按计划重物化并校验 case，非通过项目不能包装 |
| 执行 | tcad.study.execute：reviewed_package → execution_request 与精确审批 URL；只在 UI 决定被控制确认后 execution_start，随后 bounded execution_sync 收集已登记 runtime_manifest/原始输出；不把 execution_request 当成结果 |
| 将运行事实转成曲线 | tcad.runtime-attestation.v1：reviewed_package、runtime_manifest、runtime_outputs → runtime_attestation。PLX 路径 tcad.curve-bundle.sprocess-plx.v1 绑定 manifest、attestation、计划/审查、曲线合同/审查、solver_outputs → curve_bundle；日志路径则按 tcad.curve-bundle.sprocess-log.v1 的 solver_output、attestation、同一组科学输入和可选 source_spec 声明绑定 |
| 计算本轮指标 | 为所选结果诊断调用 scidiscovery.curve-score.v1：curve_bundle、experiment_plan、experiment_review、curve_contract、curve_contract_review、所需 reference_bundles → metric_report、merged_curve_bundle、score_audit、comparison_plot |
| 解释本轮结果 | science.result.diagnose.v1：experiment_plan、experiment_review、curve_contract、curve_contract_review、metric_report 和可选 curve_bundle → layered_diagnosis。若问题是有界曲线误差，可选 science.result.diagnose.curve-error.v1，并先用其所需 science.curve.error.analyze.v1 产生 curve_analysis_package |
| 进入下一轮 | 再调用 science.experiment.design.v1，current_progress 绑定本轮计划及相关审查/项目，experiment_results 绑定本轮 metric_report/相关曲线或输出，result_analysis 绑定 layered_diagnosis；保留同一总体目标及仍合格的必要基础，产生新 intent 和新计划 |

新计划不能只替换 author 的 experiment_plan 却沿用旧计划的 curve_contract/review；须按新计划建立相匹配的曲线合同和审查。原 reference bundle、capability 和科学基础能否复用，以其当前资格和精确绑定为准。

curve contract 的目标选择编译规则及 design/review 提示按第 3.2.1 节调整；其余 curve/执行 Operation 只重新绑定和调用，不修改数值算法、端口或总体评分。diagnose 的 complete_plan 指当前绑定计划的完整验证要求；未来目标仅为目标文字时不自动成为其中的 check。metric_report 中数值比较 fail 不等于对象来源不可信；但若 Artifact 本身因准入或传播规则不合格，仍须尊重精确预检，不能靠改 payload 掩盖。

### 1.5 拒绝后具体走哪一个现有入口

| 已封存判断或确定性错误 | 可使用的入口及绑定 | 不允许的替代 |
| --- | --- | --- |
| 当前 Worker 草稿违反可修正输出规则 | 同一 Run 内改本地输出，再 worker_submit_result；Root 不为每次格式错误创建新 Run | 修改冻结输入、把 checker failure 当输出错误 |
| 计划审查要求局部修正 | science.experiment.revise.v1：prior_draft=被审计划，change_request=其 ScientificReview；新完整计划重新 object review | 把 TCAD 的 DeckReviewReport 塞进这个 change_request |
| TCAD 审查认为计划合理、实现有缺陷 | tcad.deck.author.revise.v1：prior_project=被审项目，change_request=其 DeckReviewReport，继续绑定同一 INITIAL_INPUTS；新项目重新 deck review | reviewer 修改源码，或 author 自行改研究目标 |
| TCAD 审查指出任务依赖未知结果或当前输入不足 | science.experiment.design.v1：原必需科学上下文 + current_progress 中的计划/项目/DeckReviewReport；设计者重定本轮目标，再 materialize 和审查 | 反复要求 author.revise 实现尚不存在的参数；把 TCAD 报告冒充计划审查 |
| 分析产生新信息，需要下一项实验 | 同一个 science.experiment.design.v1，绑定 results/analysis 和前计划 | 新增 continue-stage Operation，或把续研伪装成独立审查要求的 revise |
| checker 故障、无适用能力、无进展或精确门禁未满足 | 记录当前失败/未决，按问题补工程或输入；Root 仍从目录判断下一动作 | 自动按错误字符串硬编码下个 Operation，或改名绕过门禁 |

表中科学分支由 Root 读取 completed 的 sealed_output 与 scheduler_signal 后判断，不把 Worker 的 next_actions 当操作指令。负面 DeckReviewReport 可直接作为 design feedback，不要求先经过 review-validate 或 package 把它变成“通过”产物。

### 1.6 每项修改对应的 Operation 入口验收

1. deck.review 的同一当前合同项目：blocked handoff 不再挡住审查；真实 review workspace 可打开；非通过报告完成，假 pass 和后续 package 失败。
2. design 的反馈矩阵：无反馈、单组、三组、多项、超限/重复各走 preflight→invoke→Worker 文件；错误 current 引用经 submit 拒绝，在原 Run 修正后完成。
3. materialize→object.review：完整目标/本轮子集不丢失；review 能引用 plan/objective/feedback；可选原件缺席不引发隐藏 required input。
4. experiment.revise 与 author.revise：各自只接收对应精确报告类型，新对象不继承审查；错误报告类型或错误 subject 在预期入口拒绝。
5. 新计划→curve contract/review→author→package：全部引用同一新计划，旧合同混入被拒绝；同一 observable 下的部分目标可进入合同和独立审查，不能因为还有未覆盖目标就机械拒绝；当前 case 严格、未来 case 不强加。
6. score→diagnose→新 design：真实指标/诊断被绑定成下一轮原件；新 Worker 不继承父聊天即可对照完整目标选择本轮。总体未闭合仍按现有总体评价处理，不能从局部 diagnosis 推断研究整体完成。

第 4 节的 P0—P6 只安排上述具体修改及验收顺序，不替代这份 Operation 合同清单。

## 2. 路径一：校验发现问题后，正确修正或退出当前任务

### 2.1 按操作用途限定影响

| 触发问题 | 当前操作如何处理 | 谁负责后续处理 | 必须保留的边界 |
| --- | --- | --- | --- |
| 输入归属、原件完整性、精确审查绑定或授权不成立 | 拒绝涉及该问题的调用，给出原因和输入端口 | Root 根据受控记录修正绑定；所需人类决定走原 UI | 不能靠修改科学文本、重命名或读背景绕过 |
| Agent 输出格式、缺字段、可确定的输出一致性错误 | 拒绝本次提交，Run 保持 running，当前 Agent 在剩余预算内修改 | 当前 Worker | 未封存草稿可改；不能修改冻结输入 |
| 被审项目实现不完整，但原件可解析、来源和审查绑定成立 | 允许进入审查；有据的 revise/blocked 报告可封存 | 独立 reviewer 判断影响，Root 再选择适合的已编译行动 | 允许负面审查不使项目获得 pass、包装或执行资格 |
| 当前任务本身缺必要条件或要求实现未知结果 | 保存当前合同能表达的有界缺口，停止要求 author 猜参或无限补写 | 设计者判断是否缩小本轮目标或改变任务；证据缺口由相应 Agent 处理 | reviewer 不修改项目，author 不擅自改研究目标 |
| 只有后续目标缺参数 | 本轮可执行部分不受此项阻断，后续条件保留在正式计划 | 设计者保留并在后续重新判断 | 本轮自身仍须满足执行条件 |
| 总体目标或同一 observable 下的目标未全部覆盖 | 保留未覆盖项，允许提交局部方案并进入科学审查；不按覆盖率自动决定能否执行 | 设计者判断本轮能否成立，独立 reviewer 复核遗漏的影响；必要时缩小或修订计划 | 不自动批准执行，不将局部结果宣称为总体完成，不删除缺口来制造覆盖 |
| 科学解释或目标选择有争议 | 报告受影响的判断和依据，提交独立审查 | 科学 Agent | 程序不把争议推断成统一的全局禁令 |
| 校验器异常、输入解码契约故障 | 记录工程失败并终止该 Run | 工程修复后按现有生命周期重新运行 | 不伪装成可修正输出错误，不让 Worker 重写输入去适配 bug |

现有依据：`service/runs.py:454` 的提交路径区分 RunOutputError 与 RunCheckerError；`test_agent_contract_alignment.py:323` 覆盖同 Run 拒绝后修正完成，邻接测试覆盖系统故障终止。复用这条路径，不增加错误状态、重试服务或通用修复 Agent。

### 2.2 每次拒绝应传达什么

复用提交诊断的 `rule_id/path/message/type` 和 preflight 的 `reason_code/port`。当前这些字段并不意味着每条诊断已经足够精确；只补本案例实际遇到的不足。

- 程序报告已确定的事实：哪条规则、哪个输出字段或输入、预期条件、观察到的差异。字段路径无法由现有异常精确携带时，先在 message 指明输入别名和 case/字段位置，不新增统一错误对象。
- 当前调用及编译合同说明该拒绝影响的是提交、审查、资格消费还是执行。不得从一个拒绝外推“整个研究不能继续”。
- 已绑定科学对象中的 `findings/missing_inputs/rationale/next_actions` 等既有字段说明科学影响和待解决问题。处理建议是科学意见，不是给 Root 的操作路由命令。
- 当前 Worker 可改的草稿错误留在本 Run；冻结输入或任务定义有问题时，交回 Root 选择后续行动。已封存对象修订产生新版本和新审查。
- 同一诊断反复出现、没有新信息或可行修改时停止无效改写；沿用既有时间/资源预算和适用的审查次数、无进展约束，不新增计数状态机。

### 2.3 首个修复：让已封存的缺陷项目可被审查

已确认的两处落点是 `tcad_artifact/plugin.py:455` 的 REVIEW_INPUTS 和 `project_packager.py:1218` 的 `validate_deck_review_task_output`。

1. 将审查主体明确声明为被检查的原对象，采用现有 `prior_signal` 用途，保持强类型、原字节、当前 producer 合同和精确 review edge；不能把主体改成 inventory 以同时绕开身份检查。不放宽其他 claim 输入。
2. 把“项目是否完整、是否实现所需 case”与“审查报告自身是否合法”分开。先解析确切输入和报告，始终检查冻结输入的类型、参数集合/coverage 对应关系、报告主体和 handoff 一致性。项目 case 覆盖、项目参数值/单位实现以及执行准备条件作为 pass 的严格条件；非通过报告可记载这些项目缺陷。不得用捕获全部异常的方式放行。
3. 对已识别的项目完整性缺口，pass 仍须拒绝；`execution_ready=false`、未解决发现和缺失输入沿现有 DeckReviewReport 表达。包装和执行路径的原门禁保持。
4. 同步 reviewer 可见说明和同源语义规则。审查者只评价和提出有界修改要求，不能为了提交报告去改被审输入。
5. 在同一文件中拆清 `_validate_approved_parameter_bindings` 的输入一致性与项目实现检查；author 仍执行原完整检查，review 的任何 verdict 均检查冻结参数上下文，只有 pass 要求项目实现合格。`plugin.py` 的 `_review_context` 同步处理参数 uncertainty：原件严格解析，未 ready 可以说明为负面审查依据，但不能通过；参数 cohort/审批 guard 不变。新增私有辅助只服务这两个原调用者，不建立通用校验框架。

负面报告仍由 reviewer 撰写事实、影响和修改建议，不增加“必须逐字复述所有错误消息”校验。`validate_deck_review_against_project` 的主体/要求键/能力对应、report/handoff 一致性和 pass 条件保留。声明为 blocked 的旧项目不会因读取或新报告自动改标签、改 handoff 或获执行资格。

已追踪的 review workspace 只解析并只读展开项目、生成现有报告模板；它不运行 author 的确定性物化分支。本轮默认不改 `operation_workspace.py`。现有 ReviewedDeckPackage 要求通过且 execution_ready 的审查及精确项目/能力绑定；除第 2.3.1 节保留初始化证明外，不改包装的 case 物化或执行算法，必须由真实包装入口负控确认审查放宽没有传入执行路径。

这里承诺的是当前合同下结构可读的封存项目可审查，不是任意损坏文件或退休合同都能作为当前正式审查主体。退休项目的只读背景路径由第 3 节处理。若现有 author 合同根本无法封存某类失败，应记录这一精确阻断，不能假装已有可绑定产物；先修正不合理的实验任务，避免默认引入通用“半成品项目”Schema。

### 2.3.1 P1 正控发现的必要包装修正

P1 新增的完整科学两 case 正控具有每 case 的 deck-scoped binding；当前 author 和 reviewer 均完成，但 Root package invoke 报 `reviewed project differs from deterministic rematerialization`。冻结基线复现相同失败，逐字段比较确认唯一差异是原项目的 `initialization_attestation` 在重物化后变为 None。依据：[科学包装失败](evidence/research-correction-continuation/p1-scientific-package-pytest.txt)、[冻结基线及字段差异](evidence/research-correction-continuation/p1-package-baseline-differences-pytest.txt)。这是 P1 正常包装和后续执行的必要阻断，不能通过删除初始化证明或关闭对象比较解决。

唯一新增生产落点为 `plugins/tcad_artifact/tcad_artifact/transform_adapter.py:package_reviewed_project`：在既有 declared-source.v2 重建后、整对象比较前，从精确输入项目保留已经封存的 `initialization_attestation`；使用现有 DeckProjectDraft 严格校验，继续核对 source/project digest，再执行原整对象一致性比较及既有受限日志迁移判断。证明为 None 时仍为 None，不合成或重新授予 qualified。原 preflight、case controls、review pass/execution_ready、精确 review 绑定和 Effect 授权门均不改。不扩展 materializer 签名、不新增证明格式或包装器。

验收保留当前 declared-source.v2 完整科学 case 的 Root author→review→package 成功用例，包装输出中的初始化证明与被审输入逐字一致；替换证明对应的 source/project、改变项目声明或其他重建字段仍在原入口拒绝。P1 已有负面报告、假 pass、包装及执行拒绝负控继续通过。

额外发现的“无 comparison binding 的工程单 case 丢失 case anchor”是另一项基线缺陷，本次不修；其失败证据保留在 [P1 包装范围审查](reviews/RESEARCH_CORRECTION_P1_PACKAGE_SCOPE_REVIEW.zh-CN.md)。Fig.4 采用的本轮计划必须实际通过完整 binding 的包装正控，不能只因 case 数多就宣称不受影响。若真实必要范围仍需无 binding case，先据那个具体反例修订范围；不在本项预建 source anchor 存储。

### 2.4 本路径最小验收

| 场景 | 必须同时成立的结果 |
| --- | --- |
| 草稿有一个可确定错误 | 返回可定位诊断；同 Run 改正后可完成；冻结输入不变 |
| 注入校验器异常 | Run 明确 failed；不返回要求科学改写的可修正诊断 |
| 有 blocked handoff 的合法封存项目作为确切审查主体 | 审查 preflight/invoke 可进入，负面报告能完成封存 |
| 被审项目缺少已声明实现 | reviewer 可报告该缺口；不能以 pass 或 execution_ready=true 提交 |
| 同一缺陷项目尝试包装、取得执行资格或执行 | 相关原门禁仍拒绝；审查可读没有产生执行授权 |
| 输入对象、来源、review subject 或批准上下文被替换 | 精确身份/父链/审批负控仍在预期入口拒绝 |
| 任务要求依赖尚未知的选择结果 | 不继续靠 author 猜参；设计者依据原记录重新限定任务，旧失败仍保留 |

## 3. 路径二：研究记录支持新 Agent 选择下一轮实验

### 3.1 每轮给什么、由谁选择

Root 从当前目录和受控封存记录中选取确切输入，设计者负责科学判断。研究进展、结果与分析直接绑定原 Artifact，不另建进度对象。

| 材料 | 所需作用 | 缺席时的行为 |
| --- | --- | --- |
| 原始总体目标、现有合格科学基础/假设/批评 | 明确总体义务和可使用的前提；总体目标继续进入每个实验 | 保持原声明的必需输入和资格检查 |
| 前一份相关计划 | 提供完整目标清单、当时本轮选择、后续条件及选择理由 | 首轮可无；续研缺席明确“未提供”，不推断没有历史 |
| 相关审查、实现或失败记录 | 解释哪些实现或判断被否定、哪些问题未解决 | 不从子 Agent 聊天补写科学历史 |
| 本轮执行原始输出或确定性指标 | 提供实际观察，保留数据与计划的来源关系 | 未执行、执行失败、结果缺失分别如实说明 |
| 结果分析 | 说明观察支持、否定或尚不能决定什么 | 可选；没有分析不等于没有结果，也不自动阻断设计 |
| 执行能力背景 | 约束本轮真正可开展的任务 | 保持可选；缺少关键能力信息时说明具体影响 |

design 与 object review 均增加 `current_progress`、`experiment_results`、`result_analysis` 三组端口。每组 0—4 项，每项最多 8 MiB；`schema="*"`、`media_types=("*/*",)`、现有 opaque codec/wildcard schema resource、`usage="evidence_inventory"`、`exposure="on_demand"`。只在两个 Operation 的已有声明文件组装端口，不改公共 `_input` helper 或新增 schema 包装器。

两者总输入上限均为 32 MiB，包含原必需输入、计划和可选背景；数量上限不承诺所有大文件能同时放满。design 保留 900 秒、review 保留 600 秒，均保留 64 KiB 主输出限制。同一 Artifact 不跨端口重复绑定；三组独立可选，不加入 foundation 审批 cohort，不产生全有或全无要求。超限重新选择原记录，不截断或复制为假原件。

design 保留现有 execution_context 端口；object review 增加同类型、同单项上限的可选 execution_context 和不超过 512 KiB 的可选 research_objective，二者用途为 prior_signal。有输入才解析；没有关键原件时说明科学判断限制，不以隐藏必需条件拒绝输出。所有新增可见输入纳入相应 context_sources，语义规则的 required_inputs 不把可选项写成必需。

默认先读前轮计划及相关审查/分析中的简要说明，必要时读取已绑定原件的细节。原件按任务声明只读提供；摘要不能替代支持关键判断的证据，也不授予 Worker 任意浏览全部历史或他人工作区的权限。新发现需要未绑定原件时，说明缺少什么，由 Root 组织后续确切绑定；不能在运行中偷偷替换输入。

### 3.2 设计者必须完成的判断

1. 对照前轮完整目标清单，说明已获得哪些结果、哪些结论仍不确定、哪些目标继续保留；每项完成、调整或放弃都给出对应原记录依据。
2. 保留完整 `objectives`，选择非空 `current_objectives` 子集。只把本轮目标展开为 cases、变量、输出、预算和验证；未来选择结果不能以占位参数进入本轮执行字段。
3. 在现有 rationale 中解释本轮为什么足够小而仍有研究价值、当前条件是否足够、结果可能改变什么后续判断。对未覆盖目标明确说明它是否是本轮的必要前提、缺失会限制哪些结论，以及能继续、需调整还是应停止的理由。目标选择和缺口的科学影响由 Agent 判断，程序只核对可确定的一致性。
4. 输出正式意图并物化为新不可变计划。总体目标、当前子集及仍相关的后续目标均保留；旧计划和结果不覆盖，不自动继承旧资格。

模型改动确定如下：ExperimentProposalIntent 增加必填 objectives（1—16 项）与 current_objectives（1—16 项）；每项非空且不超过 8192 字符，两列表内部均唯一，current 必须逐字属于完整列表。ExperimentProposal 将 objective 单字符串改为 objectives（1—17 项），增加同样的 current_objectives；JSON 使用数组、Python 沿用严格不可变 tuple。物化把精确总体目标放在每个 proposal 的完整列表首位，重复的总体文本只保留一次，其余目标不重写、不丢弃，本轮子集逐字复制。

保留 ResearchObjectiveContract 的 statement/key/mandatory_targets/closure_requirements 和 ExperimentPortfolio.objective。Portfolio/Proposal 的共同校验要求每个 proposal 含精确总体目标并满足 current 子集约束，首次物化、完整对象提交和 revise 都执行，不能只在 materializer 插入时保证。设计者解释目标变化，程序不把整份目标集合永久冻结。

删除 `validate_experiment_design_task_output` 中每轮覆盖全部 mandatory_targets 的 blanket 循环；其他目标身份、假设、case/变量、验证计划、单位和来源检查保留。cases、observables、输出、预算和验证只服务本轮。既有 `proposals[*].value_assessment.rationale` 记录覆盖、暂缓、最小性与后续条件，`priority_rationale` 说明本轮选择次序；二者均已由物化逐字保留，验收核对原文，不新增 rationale 字段。handoff 仅作摘要。

materialize 不绑定三组反馈，沿 plan → intent → feedback 父链保存来源；不改变 Transform 的非合格来源传播。下一轮新设计仍用现有 design；revise 仍接收精确前稿和独立修改要求并输出完整对象，不承接“继续下一阶段”的通用职责。

这四项是设计和独立审查的职责，不新增“每个目标完成状态”的数据库，也不要求用字符串差异自动推断目标是否完成。

### 3.2.1 未覆盖目标不自动阻断，由 Agent 判断本轮能否成立

总体目标保留完整义务，但不要求每轮覆盖全部目标，也不要求选中一个 observable 就覆盖它下面的所有目标。不为绕过这一限制改写 observable 的科学含义或新增阶段实体。

1. **设计者决定科学范围。** 将本轮目标、未覆盖项、缺口对本轮可执行性和结论的影响写入既有正式目标列表及 rationale。未覆盖项可以暂缓，也可能意味着本轮任务需要缩小、补证或停止；不能仅从“未覆盖”推导任何一种结论。
2. **曲线设计者实现已选范围。** 复用现有 `CurveContractCompileInput.target_bindings` 和 `target_key`，根据计划及其审查选择本轮精确目标，不新增目标 ID 或另一套目标清单。若领域实现发现计划本轮目标仍缺必要条件，应报告具体不一致并回到设计，不能静默删掉本轮承诺。
3. **编译器只检查确定性约束。** 在 `curve_contract_compiler.py:compile_curve_contract` 中取消 bindings 与“required_observables 对应的全部 mandatory_targets”集合相等的要求。按 Agent 提供的 bindings 选择目标，仍要求键非空、唯一、属于原目标合同，所选目标的 observable 属于本轮计划，参考 series/case/check 存在且关系一致。编译与 `validate_compiled_curve_contract` 重算使用同一规则；不自动补入未选目标，不取消当前验证计划的检查覆盖、单位、阈值和机械字段一致性约束。
4. **独立审查判断是否可以继续。** 通用计划审查和曲线合同审查对照原目标、本轮范围及可见证据，检查遗漏是否破坏本轮科学意义、必要对照或可执行条件，并在既有正式审查字段中给出理由和结论。`science_operations.py` 的设计/审查提示及同源语义说明同步，不新增审查 Operation 或由程序模拟科学 verdict。允许继续仍经过既有计划、合同、实现审查及精确执行授权。
5. **结果只支持实际完成的范围。** 未覆盖目标继续保留；原总体覆盖 evaluator 仍报告缺项，局部通过不等于总体完成。author 若不能完成已审定的本轮范围，报告真实缺口，由相关科学 Agent 判断修订或重新设计；不能把改变计划的决定隐藏在实现中。

这里保留的是本轮已经明确声明的确定性合同，不预先断言所有目标科学上都可拆开。合理的局部实验和因关键依赖而不能成立的局部实验都必须能被审查；科学判定分别通过真实 Agent 证据验收，测试只验证所需机制和门禁。

### 3.3 审查者获得独立判断依据

落实原方案审查 R1：计划审查增加精确类型的可选 `research_objective` 原件；当评价科学计划的总体覆盖和暂缓安排时，Root 绑定与设计同一份原目标合同。工程审查仍可不绑定，不能把可选端口缺席变成隐藏的提交异常。

审查同时获得支撑目标选择的确切反馈；相关材料缺席时限制相应结论，不能宣称已独立核实。execution_context 仅在判断依赖它时绑定。将这些端口加入实际 context_sources，确保声明、Worker 文件、引用规则和提交校验一致。

落实引用投影注意项：在该 review 输出声明中明确 `evidence_paths=()`，在 `_object_review_context` 及同源可见语义规则中校验每条 evidence.source_key 属于本次实际可见 inputs 别名，含 collection 的实际别名。引用项仍使用既有 EvidenceCitation，finding 到 evidence 的关系仍由原模型校验。这样允许引用计划、原目标和反馈，不改通用投影算法，不靠把审查主体改成 inventory 修引用。无反馈时可引用 experiment_plan；引用未绑定原件必须得到可修正诊断。

Root 按第 3.4.1 节通过现有 artifact_catalog 查询精确父名称，从物化计划直接父项找原目标；经 revise 的计划先沿唯一 ExperimentPortfolio 父项回到物化计划，再找原目标。不能只凭同 key 猜测是同一个原件，也不能从 design intent 的同型反馈中猜原目标。组件核对所绑定目标与计划的 key/statement，并将 mandatory_targets/closure 交给独立科学审查；不把直接父引用检查冒充任意深度父链检查。原目标替换必须改变审查指纹，新的科学输入组合不能继承旧 verdict。

### 3.4 历史只读与当前资格分别处理

在 InputPortSpec.issue 中仅增加 evidence_inventory/on_demand 的合法 wildcard 组合，保留原 handoff_only 组合。Root 的 `_validate_producer_output_admission` 在解析旧 producer contract 之前，仅对 executor=agent 且 usage=evidence_inventory 的已绑定项跳过 producer 资格消费检查；其他项走原分支。不得提前返回整个 admission，也不得添加操作名白名单。

历史、未审查或 blocked 原件可作为背景，不因此变成可信资格输入。wildcard/on_demand 必须实际交付原字节；外层实例、完整 family、大小、数量、指纹和显式 current 检查仍有效。Transform、claim、revision、审查主体和 Effect 的资格规则不随之放宽。已知九个 Agent inventory 消费者须重新枚举，逐一确认其主审对象、family、确定性消费和审批门仍有效；发现用途承担资格义务的反例时停止本项，提交最小范围修订。

共享 producer admission 变化须落实审查 R2：在本次 ABI 16 基线上将 Operation ABI 提升为 17，并比较完整目录身份，不只看实验 Schema 的自然传播。若实施前基线已合法升级，重新冻结并确定新值，不覆盖他人 ABI 改动。所有 Operation digest 因 ABI 更新而变化，生成 profile/Worker 配置须重建；不改插件版本、Operation ID，不增加旧摘要白名单或旧目标 schema 的静默兼容默认值。

旧资格不能自动继承；部署恢复与同版本会话续研分开验收。必要基础退休时，依据新目录从可接纳来源重建相关资格，不把旧记录重摄入为“新原始来源”。旧 R4 只能作为背景，不能在新目录下强行重放旧 R5 请求。

### 3.4.1 复用现有查询定位精确历史原件

只修改 `mcp_root_instance_routes.py:artifact_catalog(name=...)` 的现有响应，增加 `parent_artifact_names`。按 `envelope.parent_refs` 的顺序，使用既有 `bindings.find_name(instance=当前实例, namespace="artifact", object_id=父引用的 artifact_id)` 返回名称；不增加工具、数据库字段或 Operation。

- 无父项返回 `[]`；某父项没有当前实例绑定时，该位置返回 `null`，不把缺项混同于没有历史。相同精确原件若有多个语义名，使用 find_name 的既有稳定选择，不另存别名。
- 只映射确切对象，不回退 latest；已退休对象仍可定位名称，能否作为当前资格输入继续由原 admission 判断。不得查询另一实例来补名字，也不返回内部 ID/ref、摘要、令牌或 Worker 路径。
- 直接父项数量上限为 4096，与既有来源遍历尺度一致；超限在该查询明确报错，不截断，不新增分页或递归服务。查询不得更新任何逻辑状态。
- Root 对返回的父名称继续调用同一 artifact_catalog 读取 Schema：物化计划的直接父项中原目标是单项且有独立类型，同时可定位 intent 和原科学上下文；revise 的父项为旧 ExperimentPortfolio 与 ScientificReview，先沿旧计划继续查询。随后可沿 intent 找相关反馈，再显式绑定到新 design/review。Worker 仍只接收声明的科学文件，不接收这个控制查询响应。
- 必需父项无法定位时如实记录缺口；不读数据库、不扫描旧 Worker 目录，也不让用户重述内容来冒充精确来源恢复。本次限定的两条计划来源链无需额外输入别名投影。

工程验收通过真实 Root MCP 查询入口，从一个计划名恢复原目标：同时存在相同 key/statement、不同 mandatory_targets/closure 的新目标时，仍找回原先精确目标；至少一次 revise 后同样成立。覆盖旧版本、跨实例未映射 null、无父项空列表、4096 上限及查询前后逻辑状态不变。找到的原件还须进入新 design/review 的实际 Worker 文件，替换输入改变请求指纹；仅检查内部 parent_refs 不算完成。固定版本的真实无聊天恢复仍在 L4 验收。

### 3.5 本路径最小验收

| 场景 | 必须观察的行为 |
| --- | --- |
| 没有历史反馈的首轮 | 正常设计，未绑定的可选组不产生隐藏必需输入 |
| 仅结果、仅分析、仅进展及组合 | 对应原字节到达 Worker；输入变化改变指纹；缺席语义明确 |
| 历史或 blocked 记录进入反馈 | 可以阅读；同一原件作为当前资格输入仍受原门禁约束 |
| 局部实验计划 | 当前目标可实现，后续条件保留；本轮未覆盖的总体目标没有被标为整体通过 |
| 同一 observable 下有未覆盖目标 | Agent 能明确选择子集，合同可编译并接受独立审查；是否继续由缺口影响决定，非由同 observable 归组决定 |
| 未覆盖项是本轮必要前提 | 设计/审查 Agent 给出有据的调整或停止判断；不自动批准局部执行，也不要求 author 猜测缺失条件 |
| 结果不支持原假设或暂时不确定 | 下一轮依据真实结果调整、补充验证或停止，不为续研编造肯定结论 |
| 新会话、无父聊天的新设计者 | 从绑定记录说明研究位置、选择理由和未完成目标；不要求用户重新讲述科学背景 |
| 下一轮计划 | 能选择原后续目标或有据的新目标，保留仍相关项；接受新审查并具备真正开展的条件 |

新会话验收在版本固定后进行，并由用户明确继续原实例；正常 UI 选择和必要审批与“因为记录不足而要求用户重述研究”分开计数。总体评价仍遵守原始目标合同；现有 evaluator 不因两轮各自通过就自动累计出总体 PASS。

## 4. 实施次序与范围

### 4.1 文件责任

限定为以下 **14 个已有生产文件**：在 R2 审定的十三文件范围上，仅为 P1 必要正控增加一个现有包装文件，修复初始化证明在重建时丢失。第 2.3.1 节增量通过独立复审后才修改该文件；其余范围不变。工程实现者负责源码和测试，独立工程审查者负责实现复核；科学设计、author、审查与诊断仍归各自编译 Agent。

| 文件（相对源码根） | 唯一必要修改 | 步骤 |
| --- | --- | --- |
| `plugins/tcad_artifact/tcad_artifact/plugin.py` | project 审查用途、适用条件及可见语义；review uncertainty 与 author 的严格条件分开 | P1 |
| `plugins/tcad_artifact/tcad_artifact/project_packager.py` | 审查报告有效性与项目实现完整性分开；原输入一致性和 pass 条件严格 | P1 |
| `plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_reviewer.md` | 明确缺陷项目的负面审查可交付，不要求 reviewer 修改输入 | P1 |
| `plugins/tcad_artifact/tcad_artifact/transform_adapter.py` | declared-source.v2 包装重建保留精确输入的初始化证明并严格校验；原一致性和执行门保留 | P1 |
| `src/scidiscovery/artifact_agent/schema/experiment_intent.py` | 两个必填目标列表及物化逐字保留；本轮意图仍满足原机械一致性 | P2 |
| `src/scidiscovery/artifact_agent/schema/experiment.py` | 正式计划列表/子集/总体目标约束；移除单轮全集覆盖循环 | P2 |
| `src/scidiscovery/general_science_experiment_operations.py` | design/review 反馈、review 原目标和能力端口、context_sources、预算及引用声明 | P2/P3 |
| `src/scidiscovery/general_science_experiment_components.py` | 设计/修订/审查可见职责；目标对照、引用别名校验和同源语义规则 | P2/P3 |
| `plugins/curve_score/curve_score/curve_contract_compiler.py` | 按既有 target_bindings 编译本轮目标子集；取消同 observable 全目标集合相等要求，保留所选范围的机械校验和重算一致性 | P2 |
| `plugins/curve_score/curve_score/science_operations.py` | 曲线设计/审查提示及同源语义明确局部范围、未覆盖目标影响和科学判断职责；端口不变 | P2 |
| `src/scidiscovery/operations/spec.py` | wildcard 只读组合；ABI 16→17 | P3 |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | 仅 Agent inventory 的 producer 只读例外，外层门禁保留 | P3 |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py` | 现有 artifact_catalog 投影当前实例精确 parent_artifact_names，未映射 null、空列表及 4096 上限；复用 find_name，不写状态 | P3 |
| `roles/scheduler.md` | 确切记录选择、原目标/反馈复用、任务错误与对象错误分工、续研与停止 | P2/P3 |

默认不改 Run 生命周期、通用错误模型、TCAD 工作区机制、solver 源码、服务、部署脚本、curve/TCAD 数值算法和总体评分。curve 的变动限定为上述目标选择编译规则与 Agent 说明。测试 fixture、本文/索引、受影响的中英文架构条目及安装生成 profile 属于验证和文档范围，不手改生成的 AGENTS/profile。新增目标 ID、状态机、公共 Operation、进展包装对象或核心对领域模型的依赖不在本计划内。

### 4.2 P0：冻结与复现

**工作：** 保存当前完整源码基线（含未跟踪生产文件）、最终审定文件清单及摘要、已安装版本和完整 catalog。对运行状态只用受控查询；不快照活动数据库文件来冒充一致备份，不读取失败 Worker 草稿作科学证据。证据集中在仓库 `docs/plans/evidence/research-correction-continuation/`，运行日志和命令结果保存于此，不仅放 `/tmp`，排除凭证。

**最小反例：** 当前合同下 blocked 项目的审查预检拒绝；结构合法但 case 实现有缺口时负面报告被 context validator 拒绝；局部观测目标被 design 全集覆盖校验拒绝；handoff_only 无 Worker 文件及历史 inventory 被 producer gate 拒绝。测试构造与真实 R4/R5 分开记录，不能把 fixture 注册成实例内的新科学事实。

新增目标覆盖反例：同一 observable 下两个目标，仅选一个时被 curve compiler 拒绝；同时保留不同 observable 的局部目标对照。该工程反例不预先决定真实科学任务是否适合拆分。

**交付：** 基线清单、上述反例及第 3.4.1 节冷启动反例的预期入口/诊断/责任人，以及修订计划的独立工程审查报告。既有 REVISE 报告是修订输入，不是本计划的 PASS；R1 查询合同与十三文件范围须经复审。新审查发现范围缺口时先修订本文；不通过就不开始生产修改。

### 4.3 P1：恢复负面审查的可交付性

**工作：** 按第 2.3 节修改原三个 TCAD 文件，并在第 2.3.1 节增量复审通过后修正包装的初始化证明保留。保留当前 Worker 纠错生命周期；补充本案例诊断中的输入/字段位置和已确定差异，不新增统一诊断服务。

**验收：** 经 Root preflight/invoke、真实 Local review workspace 和 Run submit 路径验证 blocked 项目可被确切 reviewer 打开，负面报告可完成；同一缺陷的假 pass 仍被拒绝。确认报告/输入/参数身份错配、非法主体替换仍拒绝；对包装和 Effect 路径执行负控。无须为这些控制用例运行 solver。

**退出条件：** 第 2.4 节相关正反例通过，且当前 declared-source.v2 完整科学 case 的 author→review→package 实际完成并保留精确初始化证明。若还需修改未列出的 workspace/资格实现，记录具体调用链并修订范围，不靠换 verdict 或删除负控继续。

### 4.4 P2：让实验设计承担本轮目标选择

**工作：** 实现第 3.2 节模型、物化和 validator 调整及第 3.2.1 节曲线目标选择规则；同步设计、完整对象 revise 和曲线设计/审查的提示及可见语义。为计划 review 绑定原目标和可选 execution_context，核对 key/statement 并独立判断覆盖与暂缓；不要求 reviewer 从计划自述推测原 mandatory_targets。

**验收：** intent→materialize→Portfolio→revise round-trip 保留总体、本轮、后续目标；空/重复/超限/不存在的 current 引用拒绝。不同及相同 observable 的目标子集均能编译、重算并进入审查；未知目标、计划外 observable、错误参考曲线和漏掉本轮已声明 check 仍在对应入口拒绝。局部计划通过机械验证，未来目标不生成 case；总体覆盖仍不返回完整 PASS。TCAD materializer/case-control checker 仍严格核对本轮 case。测试中的审查 verdict 只验证门禁行为，缺口是否科学上允许继续留给 P6 的真实 Agent 与独立审查。

**退出条件：** 模型、提示、物化与下游 fixture 一致；原目标替换会改变审查指纹；工程 review 不绑定科学目标仍可提交。此时不部署，不宣称已能使用历史反馈。

### 4.5 P3：交付原始反馈并保持资格边界

**工作：** 按第 3.1、3.3、3.4 节实现两处准入接口修改、三组输入、引用约束及 ABI 更新，并按第 3.4.1 节扩展现有 artifact_catalog 的只读响应和 scheduler 的逐层查询说明。完整枚举当前 Agent inventory 消费者，确认其只读例外没有替代主审对象或资格端口。materialize 不重复绑定反馈，不新增状态或跨 Run 隐式上下文。

**验收：** 无反馈、每组单独、三组组合、集合多项均经 Root→Run→Local 打开；实际字节、0400 权限、别名、大小/数量/重复绑定和指纹符合声明。过期/blocked/未审查原件可读，外层 source/family/current/claim/revision/Effect 负控仍成立。审查可引用 plan/objective/feedback；未绑定 source_key 可纠正，校验器异常仍终止。真实 Root 查询入口满足第 3.4.1 节首轮及 revise、多版本原目标、跨实例、空/未映射/超限和纯读负控，恢复的原件确切交付给新 Worker。

**退出条件：** 第 3.5 节中可由工程用例证明的条件通过；完整 catalog 的身份变化得到解释，包含不依赖实验 Schema 的旧 inventory 操作。真实无聊天续研留给 P6，不用测试模板代替。

### 4.6 P4：完整验证与独立实现审查

聚焦检查通过后，对最终合并差异完成第 6 节检查；pytest、wheel 和进程测试串行，不与真实 Agent/solver 并发。安装态测试使用隔离环境验证 wheel、loader、生成 profile 和声明内容；源码导入通过不算安装通过。

独立工程审查至少追踪 review admission→workspace→submit→package/Effect，以及 feedback→设计→物化→审查→后续绑定两条链。报告绑定最终源码/计划摘要、实际测试命令及未验证项。只有最终候选通过才进入部署，不能继承旧实现或原七文件提案的 verdict。

### 4.7 P5：一次部署与资格恢复

**部署前：** 冻结候选完整目录，列出当前案例的必需科学基础、生产者/审查/审批身份及升级后处置：可读背景、需要重新产生或审查的资格输入、仍可作为确切来源的原件。对必要资格逐项确认新目录下可接纳的建立路径；不能假设旧产物直接重审就足够。若没有可行来源或已注册能力，记录为发布/真实验收阻断，不部署后再靠改用途绕过。

**部署：** 沿当前安装/新会话流程一次交付 P1—P3，重建生成配置；不引入新服务、目录配置或部署命令变体。核对安装资源和候选目录一致，观察旧合同 Run 的退休结果，不能恢复成新合同草稿。人类资格和执行决定仍使用现有精确 UI 合同。

**退出条件：** 新会话工具与 Worker 配置一致，历史背景可读，新的必需资格链有效。保留旧 R4/R5 有界记录，不声称旧 blocked 被修成 pass。冻结这个版本进入真实研究，只有实际新阻断才启动下一次有界修复。

### 4.8 P6：固定案例完成两轮真实推进

由 Root 查询当前实例及已编译目录选择适用 public Operation，逐次绑定、preflight、invoke；按控制返回的 agent_type 启动无父历史 Worker，只接受 completed 的 sealed_output 与 scheduler_signal。本文步骤不是操作名来源或绕过预检的授权。

| 里程碑 | 实际动作与证据 | 不计作通过的情况 |
| --- | --- | --- |
| L1 本轮设计成立 | 新设计依据原目标和相关历史自主选定 current，解释未覆盖目标为何允许继续或需要调整，完整目标与后续条件保留，取得新计划的独立审查 | 仅字段齐全；Root 代写实验目标；无依据忽略本轮关键依赖；仍含未来结果占位 case |
| L2 首轮获得结果 | author 完成当前计划，独立 reviewer 能审成果/缺口；符合条件后经原审批执行并收回计划要求的输出 | 仅 author 调试证明或包装成功；solver 启动即失败；审批请求尚未决定 |
| L3 结果得到分析 | 确定性指标及相应科学分析封存，说明已知结果与未决判断 | 拿历史样例冒充新结果；把总体未闭合错误当成不能读取局部结果 |
| L4 无聊天续研 | 用户明确续研后，新 Root 从已有计划名经 artifact_catalog 逐层恢复精确原目标及相关记录；新设计 Worker 从显式文件解释进展并调整目标，接受新审查。工程入口负控另覆盖同文本异约束目标和至少一次 revise | 用户重讲整段科学背景；父会话记住原件名代替查询；仅靠 key/statement 选目标；未完成目标无说明消失；沿用旧审查 |
| L5 下一轮真正开展 | 新 author 实现下一轮当前计划，经独立审查和精确授权，取得对应有界实验的实际输出 | 只有第二轮计划、排队、启动回执或立即失败，没有对应实验输出 |

当前实验失败或结论不确定时，记录真实原因，由科学 Agent 判断修订、追加证据或停止；若有据停止，则标注已完成里程碑和停止原因，不为完成 L5 强造实验。正向两轮推进验收未完成时不得标注整条路径 PASS。

P1—P3 按步骤串行形成可验证小变更，P4 后合并一次发布。P0 基线及探针已记录；P1 原三个文件已形成候选，必要包装正控未通过，新增一文件修正待增量审查。后续状态由对应执行证据登记，不修改冻结审查输入来继承 verdict。

## 5. 如何记录效果

复用现有受控运行记录和仓库 evidence 记录，不新建指标服务。对固定案例记录实际发生的：遗漏总体/后续目标或冻结约束、错引结果/版本、同一诊断无新增信息的重复提交、无进展的新 Run，以及因记录不足要求用户补述科学背景的次数。必要审批次数单独列出，不作为减少人工风险决定的目标。

最小通过条件是：负面审查可封存且缺陷项目未被执行；首轮当前任务完整而后续目标未丢失；结果与分析能供新 Agent 定位并使用；会话重启不靠重讲聊天恢复；下一轮发生了有依据的目标调整并真正开展。未取得结果、缺少独立审查或只停在第二轮文本设计时，分别标注已到达的里程碑，不宣称整条路径完成。

## 6. 检查清单与证据要求

在以下已有测试文件中补充拥有该行为的回归，优先运行新增/受影响 nodeid，再按涉及的共享边界扩大。测试用例和对应实际入口必须明确，不写与实现逐行同构的检查。

| 检查组 | 已有文件（位于 tests/operations） | 需要证明 |
| --- | --- | --- |
| TCAD 审查 | `test_l4_local_tcad.py`、`test_m6c_producer_topology_removal.py` | blocked subject 精确审查、负面提交完成、假 pass/包装/执行拒绝、未改正常路径 |
| 输出纠错和目标 | `test_agent_contract_alignment.py`、`test_general_transform_operations.py` | 同 Run 纠错与 checker failure 分开；目标列表物化/修订一致；局部设计有意义且可交付 |
| 可读反馈与准入 | `test_general_transform_operations.py`、`test_catalog_negative_cases.py`、`test_m6c_producer_topology_removal.py` | Root→Local 原字节及限制；当前/历史读用途与资格用途分开；引用别名严格 |
| 精确历史查询 | `test_general_transform_operations.py`、`test_m6a_direct_instance_management.py` | Root artifact_catalog 找回旧目标及 revise 父链；同文本异约束负控；当前实例名称、null/空/上限、纯读和恢复后实际文件绑定 |
| 领域联通 | `test_l4_local_tcad.py`、`test_m2_curve_analysis_boundary.py` | 同/不同 observable 下的目标子集可编译并可审查；所选目标、case、check 及参考绑定错误仍拒绝；未覆盖总体目标不变成整体 PASS |
| 编译、安装与兼容 | `test_catalog_installed_entrypoint.py`、`test_skill_policy_producer_compatibility.py` | 完整 catalog 身份变化、旧资格不自动复用、wheel/loader/profile 与源码一致 |
| 架构登记 | `test_architecture_constraint_matrix.py` | 现有约束登记结构完整；行为符合性仍由独立跨边界审查判定 |

命令以源码根为工作目录，使用该环境已配置的 Python/pytest。例如 P1 检查文件为：

```bash
python -m pytest -q tests/operations/test_l4_local_tcad.py
python -m pytest -q tests/operations/test_m6c_producer_topology_removal.py
```

P4 必须覆盖完整 pytest 收集清单。先保存收集结果，再按文件用独立进程串行运行，逐文件记录退出码、通过/失败/跳过及耗时；聚焦已通过用例若未再改且环境相同，可记入同一候选证据，不为仪式重复。安装/wheel 测试只执行一批；任何失败都调查，不能省略后写“全套通过”。需要真实平台/solver 的用例缺席时明确列为 P5/P6 待验证，不与离线 pytest 混算。

本发布副本实际存在的架构检查入口是上述矩阵测试；不照抄本仓库不存在的架构或 benchmark 脚本名，也不为满足命令名新增脚本。最终检查 `git diff --check`、计划及受影响文档链接，核对中英文架构改动含义一致。未改架构规范的纯计划编写阶段只做文档检查，不跑 solver 或全套测试。

证据由 P0 建立的同一目录承接：基线和最终文件摘要、catalog 前后清单、逐项反例与回归日志、独立审查、安装核对、资格恢复清单、L1—L5 受控记录引用。测试结果只证明相应工程行为；科学结论只报告 completed Run 的 sealed_output 和配套 scheduler_signal。

## 7. 风险、停止与回退

| 触发情况 | 必须采取的动作 |
| --- | --- |
| 已有 inventory 消费者实际依赖 producer gate 承担资格义务 | 停止共享例外修改，记录具体消费者和反例，修订最小声明/边界并重新审查 |
| 修复需增加生产文件或修改列外领域/生命周期代码 | 先更新第 4.1 节文件清单、调用链依据及验证范围，并复审该增量后再继续；不得默默扩大 |
| 缺陷项目可审后能取得虚假 pass、包装或执行资格 | 停止发布，保留负控与失败证据；收回导致扩权的最小改动 |
| 目标字符串子集看似合法，但未来依赖仍进入本轮 case | 科学验收不通过；由设计者根据原记录修订本轮范围，不靠增加 author 预算补救 |
| ABI 退休使必要基础无可接纳来源或建立路径 | 标注 P5 阻断，不把旧记录换 schema 重摄入、不伪造资格或历史 |
| 发生重复诊断、工程异常或未知外部执行状态 | 停止无进展改写；工程问题由工程处理，外部执行用既有受控查询/同步确认，不能盲目再次提交 |

部署前保留可重建的原代码/安装配置和一致的状态恢复依据。需要回退时暂停新 Run，使用既有安装回退流程恢复相应代码/配置并核对其目录；不手工改 Artifact、Run、审批或执行历史，不删除新版本产物。旧新合同的资格分别重新核对，回滚代码不等于新旧证明可以互用。已有外部执行保持原身份进行有界同步，不因回退而重复提交。

R2 计划已通过，P1 因真实包装正控发现既有初始化证明丢失而提出 R3 一文件增量，尚未据此修改包装源码。P1 退出条件未满足，P2—P6 未执行。没有新的科学资格、部署或真实研究完成主张。
