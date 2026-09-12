# Operation 职责与输入交接修复计划：独立工程审查 R1

日期：2026-09-09。审查对象：`docs/plans/OPERATION_RESPONSIBILITY_HANDOFF_REPAIR_PLAN.zh-CN.md`，SHA256：`3185e004903dbfbd89b3102a3097dcad03ed2e39b5d872cba6cac6f19d8ca8a2`。

仓库：`123/scidiscovery-e5.2`。HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`，但审查基线是有大量既有修改和未跟踪文件的当前工作树，不能以 HEAD 代替该基线。按用户授权进行工程静态审查，采用 `scid-cross-boundary-review` 方法；未调用科研控制面或 Worker 工具，未运行测试、构建、安装或求解，未修改计划或源码。仅新增本报告。行号均指本次静态阅读时的工作树。

## 总体判定

**REVISE：不能把 R1 当作已经冻结、可直接实施完毕的规格；可以立即开展其有界合同核定及 A 项。** 方向正确，删去通用扩展后未发现必须靠新 Operation、新状态机或新增 revise 反馈端口才能接通的路径。B 的合同决策可以在首步静态核定中完成；C 的证据来源及读取能力必须在 C 的生产实现前定案。以下问题不要求停止所有工作，也不要求先完成科学实验才允许修改代码。

| 维度 | 结论 | 理由 |
| --- | --- | --- |
| 1. 目标定位准确性 | PASS | 任务交付、无项目负结果、实际初始化证明分别对应三个具体问题；未把独立 review 的正确阻断当作错误，也未把评分条件重新前移给 author。 |
| 2. 工程实施完备性 | REVISE | 主要消费者已列齐，但初始化证据实际生产链尚未闭合；gap 的具体互斥形状、版本及恢复载体未冻结；返回 design 的验收未写出完整必要 cohort。 |
| 3. 修改后系统逻辑及有效科研闭环 | PASS_WITH_GAPS | 绑定记录→设计→独立审查→实现/执行→有限分析→再设计在现有机制下可行；负记录可合法进入 design 反馈。当前只得到静态机制可行判断，尚无真实跨轮验收，C 不解决前不能宣称本案例执行就绪。 |
| 4. 最小改动原则 | PASS_WITH_GAPS | A/B/C 均有生产依据；保持四态、独立审查、不可变身份和审批是合适边界。C 如选择原生文件证据，可能需要有证据的少量 debug 输出收集修改；应明确列入具体增量，不能暗中发展成跨求解器框架。 |

## 决定能否实施的最少事项

仅 F2 是需要补入计划的接线验收遗漏；F1、F3 是 R1 已明确承认的待决项，本审查为其补充代码证据和接受标准，不将现有代码尚未实现计划重复认定为新缺陷。

### F1 — P1，已知实施阻断：C 尚无可实现的证据生产与读取闭环

**计划位置：** 第 86–94、109、112、123–124、148 行。

**已证实代码事实：**

- `debug_adapter.py:prepare` 第 270–275 行把开发 job 的 `expected_outputs` 清空；`prepare_submission` 第 356–368 行明确拒绝非空 `job.expected_outputs`。
- `debug_adapter.py:_earliest_diagnostic` 第 508–515 行以 succeeded + exit 0 直接返回 complete；`local_debug_service.py:_finish` 第 200–225 行据此形成 qualified 收据。
- `project_packager.py:ProjectPreflightAttestation._qualification_matches_result` 第 329–337 行把 qualified 与这三个形式条件等价绑定；`ProjectInitializationAttestation` 第 341 行继承该校验。
- `project_packager.py:_evaluate_runtime_assertion` 第 1664–1669 行的 `tdr_metadata` 固定失败，理由是没有合格的 TDR metadata provider。`attest_runtime_contract` 的名称不能作为已有初始化读取器的证明。

**可达场景及影响：** 若实现者选计划所列结构/网格输出作为证据，只添加收据字段和消费者校验，则开发提交仍不接受声明输出，而且现有 TDR 分支不能证明任何结构。系统可能只完成“全部拒绝”，真实工程也无法推进；或为做出正例退回非空文件/日志标记，重现原缺陷。计划已承认问题未决，这不是发现了其承诺之外的新要求。

**最小修正：** 在 C 前给出一份窄决策：精确 SProcess capability/release 适用条件、一个可信样本来源、所证明的实际步骤、现有或最小新增读取函数、证据从 debug prepare/transport/collect 到受控收据的路径及字节/时间上限。若选择日志，说明为什么原生内容能区别跳过、作者 puts 和真正初始化；若选择文件，明确处理当前 expected_outputs 禁止规则及格式读取缺口。维持一个领域证据校验，历史解析与执行准入分开。不要求通用检测平台。

**必要验收：** 可信正例必须走与实际开发初始化一致的生成/收集入口；skipped + exit 0、伪完成标记、错误/陈旧证据、源码或声明变化均失败；正例可通过 author→独立 review→package，旧 package 直接执行准备失败而其历史结果仍可分析。不能仅向模型手工填一个 qualified=true 的新收据作为正例。

**待决分类：** C 的生产实现和本案例执行就绪验收的阻断；可以在有界首步核定。核定失败只暂停 C，A/B 可继续；不得将此状态报告为整轮完成。

### F2 — P2，返回 design 的恢复验收缺少完整科学 cohort 和一次真实准入接线检查

**计划位置：** 第 64、82、122、134–138 行。

**已证实代码事实：** `general_science_experiment_operations.py` 第 63–100 行的 design 除可选反馈外，还要求 exact scientific_foundation、research_objective、hypothesis_portfolio、critic_review；第 126–127 行挂有 foundation admission 和 science cohort guard。`general_science_experiment_components.py:experiment_science_cohort` 第 393–401 行要求 objective/portfolio/critic 与 foundation，以及 critic 与 portfolio 的确切父链。`operations/invoke.py` 第 181–197 行检查 cohort 完整性并运行 guard。

**可达场景及影响：** 按第 134 行字面只恢复“目标、计划、参考、author/review 缺口”并绑定 feedback，不能直接 invoke design：还缺必选 portfolio/critic/foundation 或对应资格。计划不是声称放宽这些门禁，但其真实恢复步骤未把该事实写清，可能将首次不可达错误误判成又需要扩展接口。

**最小修正：** 补一段确切绑定表或恢复步骤：从计划/意图父链找回原始 objective 及其匹配 foundation/portfolio/critic；原计划与 gap/领域 review 放入现有 current_progress，结果/分析放入各自端口；依据 catalog 保留既有 admission/审批。原 cohort 不可用时明确封存有界缺口，不猜同 schema 替代品。无需新端口、自动路由或放松资格。

**必要验收：** 在现有少量接线路径中增加一次 author gap 封存→独立 deck review→以真实输出名绑定 design→preflight→新设计输入可读的检查，使用完整正确 cohort；另以错误 cohort 或把负记录当 claim_evidence 的负例确认门禁保留。不需运行求解器，也不需新建全套回归。真实恢复再由 Worker 证明其只凭绑定记录能理解缺口并改变任务。

**范围判断：** 这是恢复步骤和验收精度缺口，不是已证实的生产断路。现有反馈机制本身可承载这条路径，见下节。

### F3 — 首步定案任务，非新增缺陷：B 的候选合同与兼容策略

**计划位置：** 第 74–80、100–103、109、122、148 行。

**已证实代码事实：** `project_packager.py:DeckProjectDraft` 第 432–462 行强制 files/entrypoint 等工程字段；`plugin.py:_author_operation` 第 371–377 行绑定单一 `tcad.deck-project.v1` schema，`PROJECT_SCHEMA` 第 669 行由 DeckProjectDraft 生成。`operation_workspace.py:_restore_retry` 第 156–183 行按完整工程恢复，`_restore_retry_tree` 第 202–211 行先要求 files 目录，`materialize_workspace` 第 328–350 行优先尝试该路径并把 review project 按完整模型读取；`finalize_workspace` 第 531–557 行先读源码并物化，之后才构造 envelope。现有 handoff 无法免除这些要求。

**可达场景及影响：** 若实现时不同层自行理解候选 union，可出现模型接受 gap 但模板/恢复优先走残留工程，或 Worker 可见 schema 仍要求 files。反过来放宽共享 DeckProjectDraft 则会让原本只应读取工程的消费者接受不完整内容。R1 正确提出贯穿修改，但具体分支、工作区载体和版本尚未选择。

**最小修正：** 首步冻结一个严格互斥负分支、其现有工作区文件载体、有限字段及 handoff 一致性规则；明确 raw-tree 与已封存 gap 恢复的选择优先级。列明 author 输出/reviewer 输入使用 union，revision/runtime-failure/compare/package/realization 使用完整工程入口。决定逻辑 schema ID 是否复用以及 Operation 版本增量，不能以“后向兼容”替代实际编译 schema 核对。不需要第二套提交协议。

**必要验收：** 无 files/入口/诊断可封存负结果，pass handoff + gap 拒绝；带残留 files/declarations 的 gap 经重试仍为 gap；独立 review 可读取 payload 缺口且不能 execution_ready；完整旧项目解析不变；工程消费者明确拒绝 gap；修改后的 schema/角色资源进入 catalog 摘要。

**待决分类：** 可在有界静态首步完成的任务，不是必须另开架构设计的阻断。接受标准为上述分支/载体/版本决策一页可审查，B 各消费者用同一决定实施；在冻结前不能称 B 可直接严格实施。

## 已核对成立的边界

**设计交付与物化。** `experiment_intent.py:materialize_experiment_design_intent` 第 332–429 行从 intent 展开 variables、case settings、validation，并保留 frozen_invariants；现有科学字段可交付小型数值、单位和推导条件。必要值是否科学合理是绑定证据和独立 Worker 的问题，静态审查不能选择 x_max。现有 design/review 的反馈输入与 revise 的 prior_draft/change_request 差异真实存在（`general_science_experiment_operations.py:35–51,140–164,194–208`）；回到 design 是合理替代，不需要给 revise 批量加端口。review 必须绑定相关目标/反馈，不能靠设计者聊天补交上下文。

**负记录可合法返回现有设计。** design 的反馈是 wildcard、on_demand、evidence_inventory（同文件第 35–45 行）。Root `_validate_operation_input_admission` 仅对 claim_evidence 阻断不具 claim admissibility 的记录（`mcp_root_operation_routes.py:1114–1128`）；producer review admission 对 Agent 的 evidence_inventory 跳过要求先 PASS 的规则（第 1326–1331 行），对精确独立 reviewer 也有专用分支（第 1361–1366 行）。`run_current.py:79–87` 仅在 require_current 时强制当前头，读取历史不等于恢复资格。因此不应新增通用 claim 绕过。仍须保留 design 原 cohort 和其批准条件，不能把“允许读 gap”误读为“随意接受任何科学前提”。

**payload 与 handoff。** `runs.py:_register_output` 第 877–884 行登记的是 validated.content 及确切输入父链；生产结果的 handoff 不是新 Agent 任意可读附件。把缺口的科学事实保存在领域 payload 是必要改动。新的科学 Agent 可据负反馈重新作出有理由的正设计，并重新独立审查；不得只通过 transform 把旧负结果升级成资格，Root transform 对 nonqualifying 来源仍传播该限制（`mcp_root_operation_routes.py:834–844,910–913`）。

**独立审查与工程消费者。** `DeckReviewReport` 支持 blocked/revise、unknown fidelity、missing_inputs（`project_packager.py:690–711`），无需新 review 状态。工程检查和无项目缺口检查需在领域解析处区分，不能删除 `validate_deck_review_against_project` 的源码、能力及 requirement 一致性。计划保留 package 父链和精确审批，方向正确。

**执行准入与历史分析。** `validate_reviewed_deck_json` 当前只做模型与 canonical JSON 检查（`project_packager.py:1107–1117`）；执行/命令适配器分别在第 57、79 行调用它，Root effect 准备也会调用 execution bridge 的 validate_request（`mcp_root_operation_routes.py:788–799`）。`runtime_plugin.py:execution_projector` 第 117–125 行直接解析 package 并校验 compiled identity。R1 覆盖旧 package 执行准备入口是必要的，不能只改初次 author。历史分析 `result_analysis.py:_identity_context` 第 158–168 行直接解析旧 package 并检查输入字节身份，因此证据准入应置于执行用途检查，不能把新要求塞入使所有历史 JSON 失效的共同基础模型。

**合同漂移及部署。** `runs.py` 第 993–994 行拒绝 Run 的 Operation version/digest 漂移；`plugin.py` 第 358 行已有明确 Operation version，schema 是资源。TCAD wheel 已声明 `roles/*.md` 包数据（`plugins/tcad_artifact/pyproject.toml:27–28`），没有证据要求修改安装脚本。计划提出核对摘要资源闭包、冻结旧 active Run、只做一次有界安装入口验证是足够的计划要求；本次未生成新 catalog/wheel，因此不能提前证明新摘要正确。旧 Run 要在旧合同下结束或显式失败后重新创建，不能靠部署兼容放行跨版本提交。

## 闭环有效性与最小范围

这份计划可支持有边界的真实 AI 科研助手：新设计 Agent 通过明确的父链、目标、反馈 payload 理解当前进展；可行目标进入计划及独立审查；author 交付真实工程或可审查缺口；执行保持精确授权；分析可报告局部、不确定或负结果；下一轮再设计保留总体目标和未覆盖部分。当前必要阻断回到负责环节，未受影响目标能否继续由设计/独立审查说明，而非控制面自动推断。

该判断是机制可行，不是本案例完成证明。初始化原生证据未核定，真实参数能否从绑定证据交付未由新 Worker 验证，真实执行/分析/下一轮尚无本次验收记录。不得以独立审查报告、绿色测试、completed 或一个 package 存在替代这些事实。也不应因原型没有预先覆盖所有异常就否定其有效性。

R1 的总改动集没有已证实的无关扩张；保留不新增状态机/自动路由/通用端口/科学语义 validator 的限制。若 F1 最终需要 debug 的有限输出收集，按具体证据补明确切文件即可，不据此要求新跨求解器框架。A 的提示改进应有实际 Worker 交付验证，不能仅依赖关键词回归或不断给 reviewer 增加前置义务。

## 修改后复审最小清单

1. 新计划 SHA256；补完整恢复 cohort 与 gap→review→design 接线验收，无需增设端口。
2. B 的冻结合同：互斥 schema、工作区/恢复分支、完整工程消费者清单、版本策略。
3. C 的窄证据决策：可信正样本、实际步骤、适用 capability/release、生产/收集/读取入口及边界；若无法确定，明确 C 暂停。
4. 实施后只提交本轮精确增量和上述少量正负例结果；覆盖旧 package 执行拒绝/历史分析可读、旧 Run 合同漂移拒绝、schema/角色摘要及一次安装入口验证。
5. 部署和真实跨轮研究单独记证据；未完成时维持“机制已验证、真实跨轮未验收”或具体阻断，不以本报告作为科学或执行批准。
