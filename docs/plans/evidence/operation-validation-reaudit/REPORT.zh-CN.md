# 当前 50 个 Operation 校验复扫（2026-09-12）

后续实施状态见[删除阶段完成记录](REMOVAL_COMPLETION.zh-CN.md)。以下保留删除前的审计事实，不把后续修复倒写为原始状态。

结论：**校验层仍有实质过度约束和职责越界。应保留真实身份、授权、资源、计算必要条件和程序产物完整性；删掉机械重复填写形成的拒绝、全覆盖要求及科学结论公式。** 上一轮将较多规则统一归入“结构一致性保留”，粒度过粗，遗漏了这些叶规则。

本次只做工程诊断和清单，没有修改生产源码、启动科学审查或求解器，没有跑 pytest 全量测试。用户此前要求暂停的科学审查保持暂停。

## 范围、依据和证据强度

- 从 Root 当前 `operation_catalog(scope=all)` 的 50 项出发，覆盖 25 Agent、21 transform、3 approval、1 effect，含 public/support。
- 对照当前安装包编译的 111 个 validator/guard/transform/projector/effect 组件，其中 83 个 validator/guard；追踪 184 个 Schema 可达模型、252 个校验绑定，归并为 125 个具名方法条目（包含继承/别名，不是 125 条原子规则）。另核对 19 个注册 Worker 工具的模型和边界。
- 已比对 38 个定位到的安装文件与工作树，全部逐字节相同。工作区很脏，HEAD 不能代表当前部署；不能仅用旧 PASS 文档认定现况正确。
- 源码/消费者证据与实际 Run 分开。14 项发现中，F01 有本轮真实拒绝证据；数项通过无实例微型输入对照复现；其余为源码与调用链确定的限制，不冒称都造成了本轮事故。
- 不读取被拒科学草稿。当前 proposal 的真实失败分支仍未知，不能把通用 value_error 断言成 case_count 错、案例错或空数组。
- 低资源串行检查：编译清单峰值约 87 MiB RSS、最终微型探针约 74 MiB RSS，地址空间上限 512 MiB。完整原始计数见 [SCOPE.json](SCOPE.json)。首次小探针的夹具错误（缺 schema 参数、fixture 多 title/少 domain.unit）已纠正，不计作生产事故。

## 判断尺子

| 判断 | 判定依据 | 正确落点 |
| --- | --- | --- |
| 保留 | 违反后真的会错用来源、串案例、越权执行、损坏文件、无法计算或伪称程序完成 | 准入/工具调用/副作用边界；输出只核对输出事实与引用 |
| 修复或移位 | 事实有用，但重复填写、重复准入、报错丢失或工程失败归错责任 | 控制层派生、一次准入、可定位错误、工程故障记录 |
| 删除硬拒绝 | 只因多写一次引用、局部任务未覆盖全部、研究标签不合模板或不符合固定科学 verdict 公式 | 规范化或作为审查材料，不阻止有效局部成果封存 |
| 暂不删 | 当前是明确资格/操作用途边界，或未证实生产消费者与删除后果 | 保留并注明限制，不把怀疑当已确认缺陷 |

**读取冻结输入以解析输出引用是合理的；在提交输出时重新决定这个输入有没有资格、是否满足科学前提，或重跑其计算，不合理。** 来源身份检查不是“输入再准入”，两者必须分开。

## 14 项具体发现

### F01 — 具体关系错误被抹成通用 value_error（修复）

位置：`src/scidiscovery/operation_contract.py:83 validation_diagnostics；src/scidiscovery/operation_declaration.py:85 payload_validator；service/runs.py:780 _sanitize_diagnostic`。

事实：普通 Pydantic ValueError 的具体原因被替换为 Value violates the declared type, bounds, or field relationship；模型根级错误退化到 $/$.payload。真实审查 5 次、修订 3 次拒绝均未指出具体关系。

判断：这是已发生的纠错链缺陷；不能从通用码猜测 Agent 究竟写错了哪个分支。

- 保留：保留错误分类、边界和敏感信息过滤。
- 最小处理：保留可信具名规则的具体字段/原因/动作；已有 DeclaredDiagnostic 通道可复用，不新增状态机。不要直接回显任意异常字符串。
- 定向验收：同一确定字段错误在原始模型、Worker 拒绝和 Root 摘要中保持规则与位置；校验器异常不标为 Agent 可修复输出。
- 风险/兼容边界：低至中：限定可信诊断白名单；旧错误码保持可读。
- 证据强度：真实 Run 诊断 + 安装包独立微型复现。

### F02 — 重复引用、标签、作者名等被当成致命错误（删除硬拒绝/控制层去重）

位置：`schema/scientific_foundation.py:82 EvidenceItem；schema/research_objective.py:37 ObjectiveTarget；schema/research_cycle.py:121 ScientificReview；device_parameters.py:185 EvidenceSourceCatalogEntry`。

事实：evidence_item_keys、evidence_keys、tags、authors 等重复项会使整个对象提交失败；不少消费者只把它们转成 set。

判断：引用列表里同一项出现两次不等于引用对象身份冲突；拒绝整份科学成果没有对应收益。

- 保留：保留实体主键唯一性、真实参数名唯一性、引用必须存在；不能按同一规则删除这些检查。
- 最小处理：纯集合语义列表在封存前由控制层稳定去重或按集合读取；不修改历史不可变版本。作者姓名可能同名，不能以姓名字符串推断两个人重复。
- 定向验收：重复引用仍可封存且引用集合不变；不存在的引用、两个不同实体同一主键仍拒绝。
- 风险/兼容边界：低：去重不能用于顺序有意义或加权采样的列表。
- 证据强度：源码 + duplicate_reference_only 复现。

### F03 — 同一文件引用两个位置也被 source_key 唯一性拒绝（调整引用模型）

位置：`src/scidiscovery/artifact_agent/schema/research_cycle.py:121 ScientificReview._review_is_coherent`。

事实：同一 plan source_key、两个不同 locator 的合法引用被拒；输入上下文又要求 source_key 是绑定源别名，Agent 不能随意伪造新别名。

判断：把源身份与一条引用的身份混成同一个主键，妨碍精确举证。

- 保留：源必须真实绑定，finding 的 evidence_keys 必须能解析。
- 最小处理：允许同一源的多个定位，或由控制层合并源下定位；如消费者必须一对一，则明确分开引用键与源别名，范围限于受影响模型。
- 定向验收：同一源两处定位可审查；不存在的源仍拒绝；旧单定位引用可读。
- 风险/兼容边界：中：必须检查 evidence_keys 的解析消费者，不能只删 unique 后让 dict 静默覆盖。
- 证据强度：源码 + same_source_two_locators 复现。

### F04 — 派生字段和总体目标重复搬运（交给控制层生成）

位置：`schema/experiment.py:233,425；schema/experiment_intent.py:405；schema/scientific_foundation.py:148；schema/research_cycle.py:150；general_science_*components.py handoff verdict checks`。

事实：case_count 必须等于 len(cases)，目标原文在多个子对象完全相同；报告 verdict 又需复制到 handoff。materialize 已生成 case_count，但 revise 仍直接交完整 Portfolio。

判断：一致性事实有用，要求 Agent 重抄再靠拒绝纠正没有用；尤其修订链尚未复用已有机械生成能力。

- 保留：保留总体研究目标及当前子集，绑定原始目标身份，保留真实独立审查结论。
- 最小处理：新对象封存前计算 count、投影同一目标/同一正式 verdict；不要求 Agent 为一个值填写多份；科学范围变化仍需新版本与匹配审查。
- 定向验收：只改科学目标或案例一次即可生成一致成果；有意换目标/误绑定旧计划仍拒绝。
- 风险/兼容边界：中：只派生单一权威来源能决定的字段；不能替 Agent 决定目标子集、实验因子或 verdict。
- 证据强度：源码与生产调用链。

### F05 — 一个比较合同必须覆盖实验全部案例和全部 observable（删除全覆盖硬要求）

位置：`src/scidiscovery/artifact_agent/schema/experiment.py:274,285,321 ExperimentProposal._proposal_is_bounded`。

事实：compared cases 集合必须等于所有 cases；comparison_contract.required_observables 必须等于 proposal.required_observables。

判断：阻止一个实验中有附加案例、局部比较或不同观测任务；不是保证当前比较可计算所必需。字段布局还限制一个 proposal 只有一个比较合同，因此不能仅靠提示修复表达范围。

- 保留：保留所引用案例/观测存在、选中变量的值/单位明确、比较自身的 baseline/control 和 intended/frozen 语义。
- 最小处理：对实际比较引用做子集和局部充分性检查；未覆盖案例/目标留给设计者与审查者说明，不自动阻断整实验。先不新增多合同状态机。
- 定向验收：三个案例只比较其中两个可通过；不存在案例或缺所选比较必要变量仍拒绝。
- 风险/兼容边界：中：下游 validate_project_case_controls 与 control_equivalence 必须按合同实际子集消费；不能同时宣称整个实验已比较完成。
- 证据强度：源码与生产调用链。

### F06 — 研究用途/曲线标签决定哪些算子准用（删除科学方法硬编码）

位置：`plugins/curve_score/curve_score/schema.py:264 CurveComparison；:342 CurveComparisonSpec；analysis_tool.py:89 AnalysisCurveComparison 继承这些规则`。

事实：smooth_curve 只能用残差算子；sharp_front 必须 crossing/width，某些用途必须阈值；purpose 还绑定 gate_scope 与固定 scientific_role 配对。

判断：同一数学上有效 crossing 加 smooth_curve 标签就失败。用途说明不应成为通用计算器的方法许可表。

- 保留：保留算子真正所需的 level、second_level、x、单位、点支持与来源身份；保持原始来源与派生数据区分。
- 最小处理：移除按科学用途/形状标签限制算法和强制阈值；标签作为解释信息，方法合理性交给分析/独立审查。不要放宽 source 是真实实验还是仿真数据的身份事实。
- 定向验收：相同算子加不同描述标签仍可计算；缺 crossing level、错误单位、不可用支撑仍给受限结果或明确拒绝。
- 风险/兼容边界：中：旧 purpose/gate_scope 仍可读；计算选择不能悄悄改变旧已封存合同的宣称。
- 证据强度：源码 + crossing_without_profile/same_crossing_labeled_smooth 对照。

### F07 — 声明过的参考序列全部被要求使用（删除全使用硬要求）

位置：`plugins/curve_score/curve_score/schema.py:342 CurveComparisonSpec._comparisons_are_unique`。

事实：所有 reference_input 声明必须进入比较；一旦填写非空 compare dispositions，其集合又必须恰好等于全部已声明参考。

判断：提供背景参考不等于每次分析都必须使用；有效局部分析不应先为全部资料填 compare/exclude。

- 保留：保留实际选中比较的序列存在、原始数据身份和明确的排除说明（若 Agent 主动给出）。
- 最小处理：验证实际引用子集；未用参考由程序列出，不强迫科学 Agent 搬运。
- 定向验收：绑定三个参考仅分析一个可完成；引用不存在的第四个仍拒绝。
- 风险/兼容边界：中：完整目标覆盖报告仍须忠实标出未覆盖，不能把子集分数叫完整复现。
- 证据强度：源码与生产调用链。

### F08 — 未完成的图像请求不允许保留已知部分字段（删除状态越界限制）

位置：`plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py:165 FigureDigitizationRequest`。

事实：request_status=unresolved 时 plot_bbox、axis_calibration、exclusion_regions、series 任何一项存在都被拒绝。

判断：为表达缺口必须抹掉已经完成的工作，直接损伤跨轮续接。

- 保留：ready 才可实际 digitize；已填写几何/标定字段仍必须局部有效。
- 最小处理：允许 unresolved 保存可校验的已知字段；执行准入只检查当前 digitizer 的必要条件。
- 定向验收：已知 bbox、未知轴单位可封存并交接；缺轴不能执行定量提取。
- 风险/兼容边界：低至中：原有 unresolved 空字段继续可读；消费者不得把字段非空自动当 ready。
- 证据强度：源码 + unresolved 两请求对照。

### F09 — 触发证伪项就必须给出 contradicts（删除结论公式）

位置：`src/scidiscovery/artifact_agent/schema/validation.py:38 HypothesisAssessment._references_are_unique`。

事实：falsifiers_triggered 非空时 outcome 必须为 contradicts；invalid_study 和 inconclusive 都被拒绝。三个现役分析 Operation 共享此模型。

判断：这是仍在运行的科学结论公式；观测到触发模式不等于有充分有效证据下机制被否证。

- 保留：保留证据键可解析、声明未测试不能同时声称已测试等真正语义定义。
- 最小处理：保留触发记录及解释，结论由分析者结合有效性判断；独立审查检查理由。
- 定向验收：有触发项且数值研究无效可交 invalid_study；伪造不存在的证据引用仍拒绝。
- 风险/兼容边界：低：消费者必须读取正式 outcome 与理由，不自行把 trigger 列表投影成总 verdict。
- 证据强度：源码 + falsifier_with_invalid_study 复现。

### F10 — 读取冻结曲线分析包会重算并复查输入合同（移出输出校验）

位置：`curve_score/analysis.py:314 CurveDiagnosticAnalysisPackage；science_operations.py:634,651；scidiscovery/operations/input_validation.py:196 parse_bound_json`。

事实：model_validator 调 analyze_curve_error 并逐字节比对；preflight 解析一次，诊断输出 context 再解析时会再次调用，且 package validator 也可触发。

判断：模型读取携带计算和输入准入副作用；输出能否封存取决于已接受输入再次过关。此分支是 science.result.diagnose.curve-error.v1，不是当前 tcad.result.analyze.v1 的提交重算。

- 保留：包的原始完整性、生成出处和精确引用；实际构建该包时可以验证程序产物。
- 最小处理：构建/准入时完成输入验证；输出 context 只读已验证结构并核对新输出引用；不把昂贵重算塞在通用 model_validator。
- 定向验收：同一冻结包 preflight 后提交不再次调用分析算法；错包/错引用仍能在相应边界拒绝。
- 风险/兼容边界：中：不要用 model_construct 无条件接纳任意外部 JSON；必须有实际输入准入事实。
- 证据强度：源码与生产调用链。

### F11 — author 输出校验再次按整份参数覆盖状态拒绝（移位/去重复）

位置：`tcad_artifact/plugin.py:100 _parameter_inputs；project_packager.py:1331 _validate_approved_parameter_bindings；parameter_operations.py:623,812`。

事实：输入 helper 允许成对同集 fail coverage；输出 helper 在看实际 binding 前按 coverage.status==fail 拒绝。完整生产审批目前仅允许 pass/review_required，因此微型复现不等于完整 preflight 可通过。

判断：确认存在重复的输入资格职责和不按实际使用项限定的规则；在正确新审批链中 fail 分支被更早挡住，不把它算成本轮已触发事故。

- 保留：保留批准 cohort、被实际使用的参数身份/数值/单位与审批一致；不得把未批准缺失值变成代码事实。
- 最小处理：资格由现有准入权威决定，输出仅检查实现确实消费的 approved binding；按当前目标选择参数的科学任务另由设计者完成。
- 定向验收：测试完整审批链仍拒绝未授权参数；已准入任务的输出不会因重复资格判定被否定；部分目标不使用缺参数时可以诚实交付或报告缺口。
- 风险/兼容边界：中：不能为让单独 helper 通过而删除完整批准链。
- 证据强度：安装包 helper 对照 + 完整审批调用链限制。

### F12 — TCAD 分析只准裸别名，不能精确定位（统一引用语法）

位置：`tcad_artifact/result_analysis.py:376 analysis_context；curve_score/science_operations.py:592 _validate_analysis_evidence`。

事实：TCAD raw evidence.locator 必须等于 input alias；通用分析已允许 alias:locator。限制同时写在 TCAD prompt 中，因此不是隐藏 Schema 缺项，而是公开合同本身过窄。

判断：同类分析角色使用不同引用语言；迫使 Agent 放弃日志行/JSON 子项的精确定位。

- 保留：绑定源身份、execution/case 一致性、真实计算收据与源文件不可变性。
- 最小处理：复用同一 alias + 可选局部定位解析，仍精确验证 alias；需要真实指针时验证指针，而非把整段 locator 当别名。
- 定向验收：TCAD 的 solver_log:line-range 等合理局部定位能保存；跨执行或未知源仍拒绝。
- 风险/兼容边界：低至中：旧裸别名继续有效；局部定位语法必须一致公开。
- 证据强度：源码与生产调用链。

### F13 — 精确数值被强制使用一种字符串拼法（确定性规范化）

位置：`plugins/tcad_artifact/tcad_artifact/device_parameters.py:19,45,50 ScientificDecimal`。

事实：Decimal 解析器能无损读取普通十进制，Schema 却只允许特定 e+/- 科学计数法；1.0 被拒，1e+0 接受。

判断：精度保护有用，强迫 Agent 手工格式化没有科学收益；严格拼写可以由既有 canonical_scientific_decimal 完成。

- 保留：不允许 NaN/Infinity；保留十进制精度、单位一致性和原始报告值。
- 最小处理：输入接受可无损解析的十进制字符串，在新对象确定性规范化；不要先转 float。
- 定向验收：普通小数/科学计数法同值可用；极高精度不截断，非有限值仍拒绝。
- 风险/兼容边界：中：规范化会改变新对象字节，历史 hash/签名不得追改；数值不同不能归一为相同。
- 证据强度：源码 + decimal spelling 对照。

### F14 — 参数审查禁止引用自己正在审查的对象（修复范围）

位置：`plugins/tcad_artifact/tcad_artifact/parameter_operations.py:229 _audit_context`。

事实：已绑定 parameter_evidence_package、scientific_intake、parameter_requirements、device_parameters、source_catalog 被从可引用 sources 集合中减去。

判断：源文献是证明参数事实的依据；被审对象本身也是证明其遗漏/自相矛盾的依据，不能禁止审查者引用。

- 保留：不能把待审对象冒充独立外部依据；批准时要求原始来源和审查完整性仍保留。
- 最小处理：允许引用待审对象以指出问题，同时保留来源类型/用途；不要把“可引用”直接投影成“已证实”。
- 定向验收：以 requirements/package 的具体位置报告缺项可封存 fail/unknown；不能凭该引用授予参数科学资格。
- 风险/兼容边界：低至中：检查已有 EvidenceAudit 引用类型，不新建一套资格系统。
- 证据强度：源码与生产调用链。

## 明确保留的有用检查

1. **不可变来源、execution/package/manifest、实验/案例身份和引用存在。** 这些防止把 A 的文件用于 B 的结论。只重复别名/标签与实体身份冲突不是一回事。
2. **确切独立审查、当前性和人类批准。** 作用限于声明的 claim/execution 边界；历史读取、负面审查与有限分析不能继承执行资格要求。`evidence_inventory` / `prior_signal` 的区别必须保留。
3. **路径、symlink、文件摘要、字节数、运行预算、幂等外部执行。** 微型负对照 `../outside.cmd` 被拒有实质意义；预算超限要记录真实原因，不能假装科学命题被否定。
4. **真实计算条件。** crossing 缺 level、width 缺第二 level、非法单位/域、非有限数值、没有足够支持点。这些决定算法是否有定义；可以阻止这个计算，但不必阻止封存有限分析。
5. **程序所生成结果的内部正确性。** 文件数、表格行数、像素支撑、hash、阈值计算状态聚合、runtime attestation 检查清单。程序自己生成错了应记工程故障，不让 Agent 反复改科学文字。
6. **诚实状态的定义。** 没测试不能声称已测试；实现缺口不能取得可执行资格；已宣称事实要有来源。与“观测某触发项就自动否定机制”不同，后者越过了科学判断边界。

这些检查保护的多是错误执行/错证据，而不是“科学一定正确”。单位是否合法并不能证明机理正确；代码中出现某参数字面值也不能证明物理初始化发生；正确的公式分数不能证明用户关心的形貌已经复现。后者需要实际过程证据及科学审查，当前测试通过数不能替代它们。

## 暂不作为删除依据的几项

- `ValidationReport._verdict_is_derived_from_dimensions` 等旧三维公式仍存在于仓库，但没有进入这 50 项的可达输出 Schema；不把死/兼容代码计成本次现役阻断。现役 `HypothesisAssessment` 的公式则明确在 F09。
- `FigureEvidenceValidationReport` 要求 scientific_role_counts 的 role 唯一，是聚合桶唯一，不是禁止多个曲线同一角色；保留。
- `science.hypothesis.revise.v1` 冻结假设 key 集合是有界修订职责，替代的 propose 已存在；直接删会改变操作用途和审查含义。
- `science.result.diagnose.curve-error.v1` 入口要求 complete_plan，是这项预计算包专用操作的现行范围；通用/TCAD 分析允许可选评分。先修 F10，不另造一条强制评分阶段。
- 共享 preflight 的跨端口相同 Artifact 禁重、helper 的相同内容 bundle 禁重可能过宽；要先证明控制 alias/lineage 对同一源多用途的消费者再改。当前列后续候选，不把完整性保护整段删除。
- 参数审批里重新计算 coverage、强制审计覆盖所有 frozen source，及各层重复完整目录，有机械化空间；但资格阶段完整性和“本轮只做目标子集”不同，不能只删要求就授予缺证据参数资格。
- `physical_claim_evaluable` 是 control-equivalence 程序聚合的过强命名，未查到独立生产消费者；当前不靠改名/删布尔值解决实际拒绝。

## 全部 Operation 的逐项结论

以下每行均核对注册组件和可达模型。标出的发现可能来自输入 Schema 或共享工具，不代表该 Operation 已实测触发；完整分层入口、方法索引和精确摘要在 [OPERATIONS.json](OPERATIONS.json)。

| Operation | 类型 / 范围 | 具体判断 | 相关发现 |
| --- | --- | --- | --- |
| `scidiscovery.curve-bundle.figure-evidence.v2` | transform / support | 保留图像/表格身份、来源谱系与真实数值支撑；生成 bundle 的结构断言有用。 | F02, F03, F04, F08 |
| `scidiscovery.curve-reference-coverage.v1` | transform / support | 覆盖计算自身正确性有用；关联曲线合同的全使用/方法限制应删。该 support 结果不是自动执行前置。 | F02, F03, F04, F05, F06, F07 |
| `scidiscovery.curve-score.v1` | transform / support | 算子计算条件、精确输入和程序结果聚合有用；科学标签许可表与全参考使用无用。 | F02, F03, F04, F05, F06, F07 |
| `scidiscovery.objective-coverage.v1` | transform / support | 客观报告覆盖/未覆盖有用；不得从未覆盖直接推导本轮不能做。 | F02, F03, F04, F05, F06, F07 |
| `science.curve.contract.design.v1` | agent / public | 保留选中目标/序列真实身份；编译器已代填轴、单位和 ID；移除标签控制方法及强制全覆盖。 | F01, F02, F03, F04, F05, F06, F07 |
| `science.curve.contract.review.v1` | agent / public | 保留被审对象/证据身份；修复通用 review 引用过严、诊断丢失、handoff 镜像。 | F01, F02, F03, F04, F05, F06, F07 |
| `science.curve.error.analyze.v1` | transform / support | 构建包时验证算法产出可以保留；把 model_validator 内的输入重算移出通用读取。 | F02, F03, F04, F05, F06, F07, F10 |
| `science.evidence.audit.intake.v1` | agent / public | 保留原始来源和检查实际对象；决定性来源审查需要证据；handoff 聚合由程序派生。 | F01, F02, F03, F04 |
| `science.evidence.audit.v1` | agent / public | 同上；完整 foundation 审计不是要求当前科学目标全部可执行。 | F01, F02, F03, F04 |
| `science.evidence.extract.figure.v2` | agent / public | 保留完整确定性 family 谱系；提取应允许忠实有限结论；纯引用/目标镜像应机械化。 | F01, F02, F03, F04, F08 |
| `science.evidence.extract.v1` | agent / public | 保留事实/推断区分、来源存在；删除标签/重复引用拒绝，目标镜像机械化。 | F01, F02, F03, F04 |
| `science.evidence.qualify.v1` | approval / public | 确切独立审查、来源、UI 决定与主题不可变必须保留；不把历史可读等同重新获得资格。 | F02, F03, F04 |
| `science.evidence.revise-from-critic.v1` | agent / public | 保留原基础/假设/批评 cohort 与精确 frozen sources；修订仅限已绑定批评问题；同源引用与镜像需修。 | F01, F02, F03, F04 |
| `science.experiment.design.v1` | agent / public | 保留原目标/假设审查 cohort 和所选实验实际条件；设计 intent 已比完整输出轻；相关冗余字段继续控制生成。 | F01, F02, F03, F04 |
| `science.experiment.materialize.v1` | transform / support | 应承担 case_count、重复目标和机械映射；程序产物不自洽是工程故障，不让设计者重填。 | F02, F03, F04, F05 |
| `science.experiment.revise.v1` | agent / public | 最直接承担完整 Portfolio 表单负担；全案例比较与 observable 等式优先删，派生数据控制生成，修复具体诊断。 | F01, F02, F03, F04, F05 |
| `science.figure.evidence.audit.v1` | agent / public | 保留 exact family 与来源/共享像素等真实质量证据；不把有限图证直接当伪造。 | F01, F02, F03, F04, F08 |
| `science.figure.evidence.materialize.v1` | transform / support | 保留 ready 的真实标定/图像来源和产物计数；程序失败归工程；未就绪请求可保存但不能定量提取。 | F08 |
| `science.figure.request.prepare.v1` | agent / public | 删除 unresolved 不许保存部分成果；保留图像来源、已填几何合法性和 ready 所需完整条件。 | F01, F02, F08 |
| `science.hypothesis.criticize.v1` | agent / public | 保留每个绑定假设均受评、引用原假设；批评结论归 Agent，handoff 不让 Agent 重抄。 | F01, F02, F03, F04 |
| `science.hypothesis.propose.v1` | agent / public | 保留目标身份、假设/预测实体键；对 calibratable 明确范围有用途；不从 schema 判科学真假。 | F01, F02, F03, F04 |
| `science.hypothesis.revise.v1` | agent / public | 冻结原 portfolio 的假设身份是本 Operation 的有界修订职责；新建不同组合应走 propose；不能误删 revision scope。 | F01, F02, F03, F04 |
| `science.intake.revise.v1` | agent / public | 保留 exact prior/review 来源；允许修正对象事实；同源多定位/机械目标镜像需修。 | F01, F02, F03, F04 |
| `science.intake.split.v1` | transform / support | 确定性投影及真实独立 audit 有用；对象内容一致由程序保证。 | F02, F03, F04 |
| `science.object.review.v1` | agent / public | 实际待审计划必须可读；不能因它待修就拒绝审查。当前 review 模型无旧 verdict 公式，但引用/诊断问题仍在。 | F01, F02, F03, F04, F05 |
| `science.objective.project.v1` | transform / support | 目标从原 foundation 确定性投影有用；目标副本与原文的同步由程序完成。 | F02, F03, F04 |
| `science.parameter.coverage.v1` | transform / support | 单位/条件比较、独立源去重有科学记录价值；程序报告 status/count 可校验，局部设计不自动承受整套总门。 | F02, F13 |
| `science.parameter.uncertainty.v1` | transform / support | 保留 exact requirements/parameters/coverage 父系；bounded/缺口投影供设计选择，不代替设计可行性判断。 | F02 |
| `science.parameters.qualify.exception.v1` | approval / public | 保留精确产物族/审查/UI 理由；只接受 review_required 是当前例外资格定义；重算 coverage 为可优化观察项。 | F02, F03, F04 |
| `science.parameters.qualify.pass.v1` | approval / public | 保留原始来源、完整独立 audit、数值 coverage 与 exact subject；重复源/目标目录字段应控制生成。 | F02, F03, F04 |
| `science.result.diagnose.curve-error.v1` | agent / public | 保留引用包与现有计划/分数身份；删除科学结论公式，输出提交不再重算冻结输入。其 complete_plan 入口较窄，通用/TCAD 分析已是可选替代。 | F01, F02, F04, F05, F06, F07, F09, F10 |
| `science.result.diagnose.v1` | agent / public | 保留真实结果与计划谱系、计算收据；删除 triggered=>contradicts、纯去重和工具用途限制。 | F01, F02, F03, F04, F05, F06, F07, F09 |
| `tcad.control-equivalence.v1` | transform / support | 真实 planned/intended/frozen 与代码快照对比有用；程序计数/聚合有用；不能替代机制判断。 | F04, F05 |
| `tcad.curve-bundle.sprocess-log.v1` | transform / support | 日志解析列、单位、案例来源和数据边界有用；不把解析成功叫科学成功。 | F02, F03, F04, F05, F06, F07 |
| `tcad.curve-bundle.sprocess-plx.v1` | transform / support | PLX 格式/来源/案例身份有用；不要重复要求 Agent 描述控制已知的身份。 | F02, F03, F04, F05, F06, F07 |
| `tcad.deck-project-compare.v1` | transform / support | 源码路径与结构有效、机械 diff 有用；无科学总门。 | 保留；没有确认需要删除的本地规则 |
| `tcad.deck-review-validate.v1` | transform / support | 将 review 对确切项目的实现覆盖变成程序证明有用；不能据 exit=0 代替实质初始化。 | 保留；没有确认需要删除的本地规则 |
| `tcad.deck.author.initial.v1` | agent / public | 保留代码/entrypoint/参数值/文件范围和批准身份；gap 可交付；整份 coverage 的输出资格再判应移除。 | F01, F02, F03, F04, F05, F06, F07, F11 |
| `tcad.deck.author.revise.v1` | agent / public | 保留 exact prior/review、scope 和真实代码修订；消除重复资格与机械填写，不让作者接后处理职责。 | F01, F02, F03, F04, F05, F06, F07, F11 |
| `tcad.deck.author.runtime-failure.v1` | agent / public | 输入必须是对应运行失败/attestation，防对错项目修复；保留代码边界；重复资格同初始 author。 | F01, F02, F03, F04, F05, F06, F07, F11 |
| `tcad.deck.review.v1` | agent / public | 可审 implementation_gap/历史项目；pass 授予实现资格需干净覆盖；同一 handoff verdict 应程序投影。 | F01, F02, F03, F04, F05, F06, F07, F11 |
| `tcad.execution-context.project.v1` | transform / support | 实际安装能力投影、公开参数和路径信息边界有用；无科学表单。 | 保留；没有确认需要删除的本地规则 |
| `tcad.parameter.evidence.audit.v1` | agent / public | 保留 exact expansion 与原始源独立性；允许引用待审对象指出错误；不强迫重复完整目录。 | F01, F02, F03, F04, F14 |
| `tcad.parameter.evidence.expand.v1` | transform / support | 应承担完整 package 的机械拆分与派生字段；独立 lineage 有用。 | F02, F03, F04, F13 |
| `tcad.parameter.evidence.extract.v1` | agent / public | 事实依据/单位条件/真实引用有用；科学记数法格式与重复目标、来源目录应由控制层规范化。 | F01, F02, F03, F04, F13 |
| `tcad.realization-snapshot-materialize.v1` | transform / support | 真实源代码中控制值与合同身份匹配有用；程序生成快照，不让 Agent 搬运。 | 保留；没有确认需要删除的本地规则 |
| `tcad.result.analyze.v1` | agent / public | 保留 execution/package/manifest/case 与计算证据；修复精确 locator、科学结论公式与工具用途限制；当前无需评分即可部分结论封存。 | F01, F02, F03, F04, F05, F06, F07, F09, F12 |
| `tcad.reviewed-deck-package.v2` | transform / support | 保留通过的确切实现审查、能力、源码与输入文件完整性；这里有执行前实际保护意义。 | F02, F03, F04, F05 |
| `tcad.runtime-attestation.v1` | transform / support | 实际输出与运行 manifest 对齐、防缺文件冒充完成有用；失败 attestation 仍是可读可分析结果。 | 保留；没有确认需要删除的本地规则 |
| `tcad.study.execute` | effect / public | 保留 exact 审批/编译身份、payload、幂等启动、资源/路径/产物边界；无权根据科学分数决定运行成功。 | 保留；没有确认需要删除的本地规则 |

## 优先顺序与当前科研状态

1. 优先处理真实造成盲重试的 F01；同时删清楚的机械引用拒绝（F02）并处理同源多定位（F03），不能仅改提示词。
2. 对正在修订和分析的路径处理 F04/F05/F06/F07/F09/F12：派生事实交控制层，局部实验/分析由 Agent 选择，计算器不作方法审判。
3. F08/F10/F11/F13/F14 按各自可达路径做定向修改，保留上面的负对照；不合并成架构重构或全量测试工程。

这是审计处置顺序，**不是已经执行的源码修复，也不是用户已批准的下一轮实施计划**。若实施，每次必须同时证明有意义的错误仍被拒、有效局部任务能交付，不能把旧“所有结构关系都保留”的列表照搬回来。

当前 `fig4_morphology_objective_revision_3` 已 completed，0 拒绝/0 工具错误；其 `fig4_morphology_objective_revision_review_1` 因用户要求暂停而终止，未生成独立审查成果。不能说计划已审查通过，不能由此启动新仿真。完整本轮事故状态见[错误记录](../operation-validation-pruning/FIG4_SIMULATION_CYCLE_INCIDENTS_20260912.zh-CN.md)。

## 可追溯附件

- [FINDINGS.json](FINDINGS.json)：14 项证据、建议、保留不变量、风险和定向验收。
- [METHODS.md](METHODS.md) / [METHODS.json](METHODS.json)：125 个具名校验方法逐项判断、实际 raise 位置及生产可达 Operation。
- [COMPONENTS.json](COMPONENTS.json)：111 个注册边界组件的实现位置及挂接 Operation；共享包装器不能当单一规则。
- [TOOLS.json](TOOLS.json)：19 个注册 Worker 工具的输入模型/实现边界。
- [PROBES.json](PROBES.json) / [microprobes.py](microprobes.py)：14 个串行安装包微型正负输入；不接触实例/数据库/求解器。参数 helper 对照明确不等于完整批准准入。
- [VERSION_FILES.json](VERSION_FILES.json)：38 个源码/安装文件逐字节比对与摘要。

本报告不是穷尽所有异常分支执行，也没有声称所有 JSON Schema 关键字逐项动态验收。它完成了 50 项的注册校验入口扫描、共享具名规则归并、实际消费者核查与高价值问题复现；未确认的分支已单列，避免把猜测当事实。
