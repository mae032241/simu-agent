# 校验纠错与跨轮续研执行记录

本记录跟踪本次工程候选，不替代实施计划、独立审查或科学控制记录。日期：2026-09-08。

## 当前状态

- P0：已冻结完整脏工作树基线和已安装的 49 项 Operation 目录。计划 R1 为 REVISE，修订后 [R2](../../reviews/RESEARCH_CORRECTION_MINIMAL_PLAN_REVIEW_R2.zh-CN.md) 及必要包装增量 [R3](../../reviews/RESEARCH_CORRECTION_MINIMAL_PLAN_REVIEW_R3.zh-CN.md) 均 PASS；当前审定计划 SHA256 为 `9e9ca01559d712b69a7d48d3f58797174e9dcb546dd5bc1e1d344a15ba6e43a8`，历次输入原文保留。
- P1：工程正负验收通过，四个已审定 TCAD 文件完成，两个相关测试文件最终 94 passed。真实完整科学 case author→review→package 成功并保留初始化证明；篡改和负面包装/Effect 拒绝保留。详见 [p1-results.md](p1-results.md)。最终合并候选的独立实现复核仍归 P4。
- P2：通用目标/评审聚焦 107 passed，必要 fixture 回归 91 passed，曲线目标子集所属文件 24 passed；详见 [通用证据](p2-goals-evidence.json) 和 [曲线日志](p2-curve-pytest.log)。额外 M3 检查暴露既有 corpus 缺少 execution-context Operation，未扩大生产范围。
- P3：可选原件/准入四文件聚焦 212 passed；精确父件查询和冷 Root 最终 13 passed，历史合同退役 5 passed。冷 Root 工程正控经真实 design→materialize→review/revise 后，从计划名找回原始目标并交付新 review Worker；同文本异约束反馈不替代原目标。4096/4097 上限夹具首轮未登记父件，被存储层正确拒绝；登记真实原件后复跑通过。详见 [反馈证据](p3-feedback-evidence.json)、[父查询最终日志](p3-parent-query-final.log)、[历史合同及初轮日志](p3-parent-query-and-retirement.log)。
- P4：独立[实现 R1](../../reviews/RESEARCH_CORRECTION_IMPLEMENTATION_REVIEW_R1.zh-CN.md) 为 REVISE，唯一生产缺口是无适用曲线检查时丢弃显式坏键；原编译器内移动早返回后，负控由 2 failed/1 passed 变为整文件 27 passed。[最终候选](p4-candidate-final.json) digest=`27da282cee930c816f32a0f070153de8516cd8f2b3179429f73bb433984d3bc9`，仍为 14 生产文件，另有 17 验证 fixture 和 2 双语架构文件。独立[实现 R2](../../reviews/RESEARCH_CORRECTION_IMPLEMENTATION_REVIEW_R2.zh-CN.md) 已 **PASS，仅限冻结的 Local 工程候选**；不替代 P5/P6。
- P4 验证：[完整清单](p4-collection.log) 686 项/52 文件全部覆盖，[逐批结果](p4-checks.json) 为 **676 passed、10 failed、0 skipped**，不能称全套通过；一次 [wheel 批](p4-installed-wheel-batch-1.log) 为 35 passed/1 failed，Local 安装正控通过，[49 项安装目录](p4-installed-catalog.json) 与源码精确一致。7 项失败属于既有可选 Hardened reviewer 无读取能力/运行时不支持（含 wheel 1 项），详见[基线比对](p4-hardened-baseline-analysis.json)；3 项属于[过期结构快照](p4-structure-baseline-analysis.json)，复杂度上限在基线已超 35 行，本轮审定声明/语义另增 118 行，没有提高阈值或压缩格式掩盖增长。必要 fixture 迁移保留全部原门禁断言；M3 增补既有 execution-context 场景后通过。独立实现 R2 已确认这些范围处置并放行该 Local 工程候选；十项失败继续保留。
- P4 新独立结果审查：[R3](../../reviews/RESEARCH_CORRECTION_RESULT_CORRECTNESS_REVIEW_R3.zh-CN.md)为 **PASS，仅限冻结的 Local 首版工程候选**。本轮独立复验 36 项通过，另外实际对照冻结基线/候选确认 Hardened 归因；不与原 676 项累加。已复现同 key/statement、不同约束的替代目标可通过 review 和下游预检；这符合审定计划将精确原件选择交给 Root 的条款，按首版范围记录为非阻断边界，不增加生产代码或新门禁。九份原始探针/日志已[归档](independent-result-r3/evidence-manifest.json)。本轮只追加审查证据并更新本记录/索引；原 33 文件候选、旧审查和 P5 目录快照不改写。
- P5：用户安装、重启并在 UI 绑定 M7-test0 后，已实际核验 ABI 17、49 项 Operation 及运行中目录与审定候选逐项一致，framework/external workspace/launch profile 一致；见[安装核验](p5-installed-after-restart.json)。沿 revision_5 的五次修订查询找回 materialized plan 的确切原目标；旧 author 的 status 为 completed/contract_retired，旧基础的新设计 preflight 为 input_producer_contract_changed。已按目录从原 PDF 启动新的图证请求；见[受控接续记录](p5-resume-controlled-records.json)。部署完成，新的必需科学资格恢复进行中，P5 尚未满足全部退出条件。此前预部署记录及交接作为当时快照保留。
- P5 图证进展：新 figure request 已 completed，materializer 已登记完整七件 family；[封存请求与文件登记](p5-figure-materialization-and-intake-start.json)保留。第一轮 intake 在 deadline 前未接纳任何候选，已通过控制端记录 timed-out failed 并中断对应 Agent；复用同一原件新建一次范围更明确的提取 Run，未恢复旧隐藏会话。见[超时与重试](p5-intake-timeout-and-retry.json)。目前不能推断首轮超时的内部原因。第二个 intake Run 已在预算内 completed，按编译 review edge 启动了绑定同一完整 family 的独立图证审查；见[完成与审查派发](p5-intake-completed-and-audit-start.json)。提取结果明确保留曲线缺口和检出限标记冲突；这是提取者的封存结论，尚非独立审查或资格通过。
- P5 接续检查：独立图证审查已 completed/pass，确认准确表述图证及限制，未授予量化资格、未解决曲线缺口或检出限标记冲突。确定性 split 已登记 frame/foundation；目标投影的确切 preflight 因缺少 `objective_contract` 返回 `input_required_field_missing`。已通过同一编译审查 Operation 新建一次针对目标结构完整性的补充审查，不改写原 PASS、不由 Root 补写科学合同。见[审查完成与目标缺项](p5-audit-completed-and-objective-gap.json)。人类资格审批尚未创建。
- P5 有界纠错：补充审查 completed/blocked，明确已有证据忠实性仍成立，唯一失败检查为缺少 `scientific_foundation.objective_contract`；要求仅补齐已陈述目的的正式合同。完整原件、确切 prior_draft 及这份非通过审查绑定到既有 figure extraction 的修订模式，preflight 通过，已派发新 Worker。见[补充审查与修订派发](p5-objective-audit-and-revision-start.json)。未新增 Operation、门禁或生产修改，原 PASS 及旧版 Intake 保留。
- P5 修订完成：修订 Run 已 completed；比较旧、新封存 payload，去掉新增 `objective_contract` 后其余结构和值完全相同。已按同一编译 review edge 为新版本派发独立审查，尚不继承旧 PASS。见[修订结果与新审查](p5-objective-revision-completed-and-review-start.json)。
- P5 9 月 8 日状态：修订版独立图证审查已 completed/pass，17 项检查包括目标用途、覆盖及范围控制；split 已登记新 frame/foundation。目标投影预检已从 `input_required_field_missing` 变为 `input_cohort_approval_missing`，字段阻断消除，等待现有精确资格门。完整新证据组的资格预检通过，已创建 `fig4_continuation_evidence_qualification_1`，最后一次 `approval_status` 为 pending；人类尚未决定。见[新审查通过与待资格审批](p5-revised-intake-pass-and-qualification-pending.json)。上述提取/审查/修订条目保留发生时状态，最新接续状态见后续日期条目。仓库记录省略本地审查 URL 的 capability token，续接时按确切审批名调用 `approval_status`。
- P5/P6 9 月 9 日接续：通过 `approval_status` 确认新证据资格为 decided/approve；从当前目录选择假设提案 Operation，确切新 frame/foundation 的预检通过，已派发提案 Worker。见[批准与提案派发](p5-approved-and-hypothesis-start-2026-09-09.json)。新基础已获资格；假设审查、下一轮实验设计和外部执行仍待完成，两轮真实推进未完成。P5/P6 不继承工程 PASS。

- 9 月 9 日假设进展：四候选提案已 completed，精确独立审查 completed/revise；连续响应和证据表象两项通过，双机制和边界两项存在主张强于其拒绝条件的问题。已按确切 review 进入既有 hypothesis revision，范围仅收窄这两处主张，不扩大证据。见[提案封存](hypothesis-completed-and-critic-start-2026-09-09.json)和[审查与修订派发](hypothesis-critic-and-revision-start-2026-09-09.json)。尚无新实验计划或外部执行。

- 9 月 9 日设计启动：修订假设经新独立 critic 全部通过；目标投影成功，当前 SProcess 能力已投影为执行上下文。新设计明确绑定新目标/基础、精确假设/critic，以及旧 plan、原目标、intent、author 四件历史进展；旧资格未恢复，inventory 准入通过。设计 Run 已派发，仍须以封存结果证明实际读取、合理子集及后续目标保留。见[假设通过与设计派发](hypothesis-pass-and-design-start-2026-09-09.json)。尚无新的物化实验计划、实现或求解器输出。

- 9 月 9 日计划审查与修订：新意图和完整计划已生成；封存设计明确引用旧项目进展但不继承资格，本轮选择边界/证据支持两项假设并保留后续机制比较。独立计划审查认可范围与优先顺序，要求补齐八次执行的逐案绑定、唯一统计与掩码定义、正式判定检查；原物理范围不增加。确切修订 Run `fig4_continuation_experiment_plan_revision_1` 已启动。见[设计封存与审查派发](design-completed-and-plan-review-start-2026-09-09.json)、[计划审查与修订派发](plan-review-and-revision-start-2026-09-09.json)。上述条目按发生顺序记录，以最后条目为当前进展；当前尚无新领域合同、author 或外部执行。

- 9 月 9 日修订封存与复审：计划修订已 completed，显式八个 case、统计/掩码规则与正式判定检查已写入；仍保留同一总体目标、两项当前假设与条件性后续目标。复审 `fig4_continuation_experiment_review_2` 已派发，除同一目标、上下文和历史进展外，直接绑定已批准图证的两份 CSV，以及确切图证审查/验证报告；这些是论文参考输入，非新仿真结果。见[修订封存与复审派发](plan-revision-completed-and-review2-start-2026-09-09.json)。当前仍无新领域合同、author 或外部执行。

- 9 月 9 日逐行数据复审与有界重设计：复审 completed/revise，直接数据证明两种材料的 5.4e16 cm^-3 交点均跨缺失 point_index，原计划禁止跨缺口，因此 F 及依赖统计量在执行前已不可用；另指出 CSV 字段映射缺项与适合度失败结论冲突。已按既有 design Operation 重选可支持的当前观测量：绑定前轮计划、确切审查、两份逐行参考表和图证分析，并维持同一已批准原目标及假设组合。普通 plan-revise 只有 prior_draft/change_request，不能读取这组新增行数据；本次选择是因当前科学任务前提不可用而重新设计，不绕过任何 revision_no_progress/revision_limit_reached 拒绝。见[复审结论与有界重设计](plan-review2-and-supported-observable-redesign-2026-09-09.json)。当前无外部执行。

- 9 月 9 日重设计封存：新意图 completed，将缺口交点及其依赖量暂缓，改为已有行上的剖面误差与连续低浓度支持长度；保留两项当前假设及后续机制目标。已物化为 `fig4_continuation_experiment_plan_2`，并将同一目标、进展、逐行参考表及图证分析绑定给独立审查 `fig4_continuation_experiment_review_3`。设计者的 pass 不替代独立审查；当前仍无新领域合同、author 或求解器执行。见[重设计封存与独立审查派发](supported-redesign-and-review3-start-2026-09-09.json)。

- 9 月 9 日重设计独立审查 completed/revise：审查认可替代端点、物理范围与后续目标保留；但 M0 有 14 个 Al 行无法计算已规定的双侧对数不确定度，其他掩码也有受影响行，且数字化误差不足以支持 1.96 倍合成量的 95% 概率解释。已用确切计划与审查进入现有 plan-revise，限定修正不确定度与判断规则，维持八工况；仍未开始实现或执行。见[独立审查与不确定度修订派发](review3-and-uncertainty-revision-start-2026-09-09.json)。

- 9 月 9 日不确定度修订 completed：修订计划加入有限不确定度筛选，改为非概率确定性敏感性规则，并明确逐行清单尚待参考表核验。已将确切修订计划、新原目标、前轮审查、两份参考表及图证分析绑定给独立复审 `fig4_continuation_experiment_review_4`。见[修订封存与复审派发](uncertainty-revision-and-review4-start-2026-09-09.json)。当前无外部执行。

- 9 月 9 日逐行复审 completed/revise：已独立复现所有有限掩码、宽掩码及排除行数量，确认邻接规则可执行；剩余一项是逐组名义敏感性之和不足以界定多组同时扰动。已预检通过并派发确切 plan-revise，限于使敏感性计算与结论范围相符，优先考虑审查允许的有限测试范围收窄，不增加工况。见[复审与敏感性范围修订](review4-and-sensitivity-scope-revision-start-2026-09-09.json)。当前无外部执行。

- 9 月 9 日测试范围修订 completed：采用逐组四角点与单独数值对照的明确有限集合，报告实际最小/最大值，撤除对多组同时扰动的覆盖主张。工况、掩码及目标条件保留；确切完整修订进入独立审查 `fig4_continuation_experiment_review_5`。见[测试范围修订与复审](tested-scope-revision-and-review5-start-2026-09-09.json)。当前无外部执行。

- 9 月 9 日独立计划复审 completed/pass：确认有限测试集合、判断规则与结论范围一致，八工况和后续目标保持合理。通过当前目录的必需 support 操作规范化确切图证族，得到新 reference bundle；已派发曲线合同设计，首先核验参考库信息及合同能力能否落实计划，缺项不得猜测。见[计划通过与领域合同派发](plan-pass-and-curve-contract-start-2026-09-09.json)。通用科学计划 PASS 不等于领域实现、初始化或执行通过，当前无新 solver 结果。

- 9 月 9 日当前有界终点：领域合同子任务已返回，但受控状态仍 running、candidate_accepted=false、无 sealed_output，现已由控制端正式记为 failed（非超时）。没有可交给独立领域审查或 author 的合同，也没有封存科学诊断可用于下一次科学修订；不采信或转述子任务聊天中的内容作为原因证据。当前目录中的相关修订/诊断入口均要求其声明的确切封存对象，本次未产生这些对象，因此暂停该科学推进路径，保留独立计划 PASS；下一步应诊断领域合同的受控提交失败。见[受控提交失败记录](curve-contract-controlled-submission-failed-2026-09-09.json)。本轮未新增应用代码改动、author、初始化或求解器执行，P6 两轮真实研究闭环未完成。

## 基线证据

| 文件 | 能证明什么 |
| --- | --- |
| [source-baseline-2026-09-08.json](source-baseline-2026-09-08.json) | 既有修改、删除和未跟踪文件的确切基线；后续按此计算工程增量 |
| [installed-catalog-before.json](installed-catalog-before.json) | 修改前安装目录的受控只读投影，共 49 项 Operation |
| [baseline-probes.json](baseline-probes.json) | 内存 fixture 复现同 observable 子集被拒绝、不同 observable 子集可编译但总体覆盖未完成；枚举 9 个现有 Agent inventory 消费者 |
| [baseline-local-goal-rejection.json](baseline-local-goal-rejection.json) | 从冻结源码副本运行纯模型 fixture，复现局部设计被总体 mandatory_targets 循环拒绝 |
| [baseline-history-admission.json](baseline-history-admission.json) | 冻结源码副本中，on_demand wildcard 返回 input_wildcard_invalid，Agent inventory 的历史 producer 返回 input_producer_contract_changed；尚非修复后的 Root→Worker 验证 |
| [baseline-focused-tests.json](baseline-focused-tests.json)、[日志](baseline-focused-tests.log) | 四个既有 pytest nodeid，参数展开后 6 passed；覆盖同 Run 纠错、checker failure、原 wildcard 约束和机械曲线编译，不代表新功能通过 |
| [计划审查 R1 输入](plan-review-r1-input.md)、[R2 输入](plan-review-r2-input.md) | 历次独立审查所对应的冻结文本；当前拟议规则仍由主计划拥有 |
| [R3 输入](plan-review-r3-input.md)、[完整科学包装失败](p1-scientific-package-pytest.txt)、[冻结基线字段差异](p1-package-baseline-differences-pytest.txt) | 完整 case binding 仍无法包装，初始化证明在重建后丢失；支持一文件必要增量，不能记为 P1 已通过 |

## 待修复的有界反例与责任

| 反例 | 修改前依据、预期入口及诊断 | 实施责任 |
| --- | --- | --- |
| blocked 项目不能进入自己的审查 | 历史受控 [R4/R5 记录](../TCAD_AUTHOR_R4_R5_2026-09-08.json)，Root preflight 的 project:input_scientific_claim_forbidden | P1：审查端口用途；保留精确 producer/review 身份 |
| 项目 case/参数实现有缺口，合法负面报告仍被拒绝 | 独立审查 R1 已定位 validate_deck_review_task_output 和参数 uncertainty；实现前补对应入口失败复现 | P1：分开输入一致性、报告有效性与 pass 条件 |
| 局部设计被总体 mandatory_targets 覆盖要求拒绝 | baseline-local-goal-rejection.json 已复现 SemanticRuleViolation；完整提交路径在 P2 验证 | P2：由设计/审查判断局部目标，机械校验保留本轮合同 |
| 同一 observable 的目标子集被编译器拒绝 | baseline-probes.json 已复现 SemanticRuleViolation | P2：按既有 target_bindings 选择目标及同一规则重算 |
| 历史 inventory 无文件或被 producer 资格门拒绝 | handoff_only 被 Run 文件交付排除；InputPortSpec.issue 和 Root producer admission 是已定位门槛 | P3：只读声明、逐项例外和真实 Worker 文件正负控 |
| 新 Root 不能恢复计划的确切旧原目标 | artifact_catalog 无父名称响应；同文本异约束目标和 revise 链已由独立审查定位 | P3：现有查询的父名称投影及真实入口恢复测试 |

上述工程 fixture、源码核查和历史记录不构成新的 Fig.4 科学结论，也不表示资格恢复或两轮真实研究已经完成。
