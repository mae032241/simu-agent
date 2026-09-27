# 校验职责清理：逐 Operation 审计

2026-09-13。本表来自源码实际编译的五个插件目录，共50项（25项 public Agent）。不是角色名称表，也不是只搜索报错文字。`CATALOG_BEFORE.json`/`CATALOG_AFTER.json`保存逐项输入、输出、上下文规则；后者另含287条组件实现定位。基线为清理开始时的脏工作树，保留前轮历史兼容修复。

## 本轮判定原则

- 删除：要求 Agent 把已绑定来源再次登记到输出表，然后以漏抄/重复为由拒绝成果；明确 input_alias 后仍要求 locator 再抄 alias；未使用输入必须被输出完整覆盖。
- 移位：输入之间的有效性/一致性仅在预检判断；控制工作区或已准入绑定故障归工程故障。实际引用由绑定/收据解析，Agent 不建立第二份来源注册表。
- 保留：输入与对象身份、确切独立审查/审批、输出实际作出的引用和案例对应、科学证据定位、有限数值/单位/算法定义域、受控预算与文件完整性。重复的科学引用不等于冲突的来源映射。

## 逐项覆盖

所有 Agent 共享的文件/JSON/字节预算、阶段隔离及错误诊断也纳入检查。下表“保留”不代表每条路径已经有真实外部平台验收；测试范围与限制见 COMPLETION。

| Operation | 执行者 | 处理与保留依据 |
| --- | --- | --- |
| `scidiscovery.curve-bundle.figure-evidence.v2` | transform | 保留确定性归一化的源文件/序列/列/坐标与有效采样条件；无 Agent 重复填表。 |
| `scidiscovery.curve-reference-coverage.v1` | transform | 保留确定性数值/真实序列与算子要求及计算输出一致性；评分不作为 author/execution 前提；不把工程计算状态当科学裁决。 |
| `scidiscovery.curve-score.v1` | transform | 保留确定性数值/真实序列与算子要求及计算输出一致性；评分不作为 author/execution 前提；不把工程计算状态当科学裁决。 |
| `scidiscovery.objective-coverage.v1` | transform | 保留确定性数值/真实序列与算子要求及计算输出一致性；评分不作为 author/execution 前提；不把工程计算状态当科学裁决。 |
| `science.curve.contract.design.v1` | agent | 机械合同由已注册编译工具生成；保留真实目标/曲线/算子绑定、可计算条件；不新增全目标覆盖要求。 |
| `science.curve.contract.review.v1` | agent | 删除 finding→自建 evidence 表闭包；合法输入直接可引；保留 review_target 与对象身份。 |
| `science.curve.error.analyze.v1` | transform | 保留确定性数值/真实序列与算子要求及计算输出一致性；评分不作为 author/execution 前提；不把工程计算状态当科学裁决。 |
| `science.evidence.audit.intake.v1` | agent | 删除检查→自建 evidence 表闭包；直接核对绑定来源；保留独立审查对象与明确检查结果。 |
| `science.evidence.audit.v1` | agent | 删除检查→自建 evidence 表闭包；直接核对绑定来源；保留独立审查对象与明确检查结果。 |
| `science.evidence.extract.figure.v2` | agent | 删除 Foundation 自登记闭包；引用核对本轮绑定来源；保留事实引用、条目与目标身份。 |
| `science.evidence.extract.v1` | agent | 删除 Foundation 自登记闭包；引用核对本轮绑定来源；保留事实引用、条目与目标身份。 |
| `science.evidence.qualify.v1` | approval | 删除审查 evidence 表必须抄齐来源；参数 catalog 允许未使用来源缺席；保留冻结对象完整集合、独立审查父链、确定性参数状态与 UI 决定。 |
| `science.evidence.revise-from-critic.v1` | agent | 删除 Foundation 自登记闭包；引用核对本轮绑定来源；保留事实引用、条目与目标身份。 |
| `science.experiment.design.v1` | agent | 保留可实现的案例设置、单位、比较对象、目标与修订身份；case_count 等镜像已有 materializer/finalizer 生成；不要求覆盖所有总体目标。 |
| `science.experiment.materialize.v1` | transform | 保留可实现的案例设置、单位、比较对象、目标与修订身份；case_count 等镜像已有 materializer/finalizer 生成；不要求覆盖所有总体目标。 |
| `science.experiment.revise.v1` | agent | 保留可实现的案例设置、单位、比较对象、目标与修订身份；case_count 等镜像已有 materializer/finalizer 生成；不要求覆盖所有总体目标。 |
| `science.figure.evidence.audit.v1` | agent | 删除检查→自建 evidence 表闭包；直接核对绑定来源；保留独立审查对象与明确检查结果。 |
| `science.figure.evidence.materialize.v1` | transform | 保留图像身份、坐标域/对数轴、可执行条件；未解决 request 仍可交付；确定性图像像素/来源核对属于 materialize。 |
| `science.figure.request.prepare.v1` | agent | 保留图像身份、坐标域/对数轴、可执行条件；未解决 request 仍可交付；确定性图像像素/来源核对属于 materialize。 |
| `science.hypothesis.criticize.v1` | agent | 保留确切假设对应与完整审查；科学 disposition 由角色决定；handoff 镜像已有 finalizer 生成。 |
| `science.hypothesis.propose.v1` | agent | 删除假设→自建 evidence 表闭包；允许绑定输入及冻结 Foundation 已有来源；保留假设主键、竞争关系和修订目标身份。 |
| `science.hypothesis.revise.v1` | agent | 删除假设→自建 evidence 表闭包；允许绑定输入及冻结 Foundation 已有来源；保留假设主键、竞争关系和修订目标身份。 |
| `science.intake.revise.v1` | agent | 删除 Foundation 自登记闭包；引用核对本轮绑定来源；保留事实引用、条目与目标身份。 |
| `science.intake.split.v1` | transform | 沿用放宽后的共享科学模型；保留确定性拆分/投影内容与父链；不增加来源登记。 |
| `science.object.review.v1` | agent | 删除 finding→自建 evidence 表闭包；合法输入直接可引；保留 review_target 与对象身份。 |
| `science.objective.project.v1` | transform | 沿用放宽后的共享科学模型；保留确定性拆分/投影内容与父链；不增加来源登记。 |
| `science.parameter.coverage.v1` | transform | 保留数值有限、单位/条件/来源独立性、观察对应和有限候选；输出状态由确定性工具生成。 |
| `science.parameter.uncertainty.v1` | transform | 保留数值有限、单位/条件/来源独立性、观察对应和有限候选；输出状态由确定性工具生成。 |
| `science.parameters.qualify.exception.v1` | approval | 删除审查 evidence 表必须抄齐来源；参数 catalog 允许未使用来源缺席；保留冻结对象完整集合、独立审查父链、确定性参数状态与 UI 决定。 |
| `science.parameters.qualify.pass.v1` | approval | 删除审查 evidence 表必须抄齐来源；参数 catalog 允许未使用来源缺席；保留冻结对象完整集合、独立审查父链、确定性参数状态与 UI 决定。 |
| `science.result.diagnose.curve-error.v1` | agent | 删除内部证据登记/唯一性及 locator 重抄；包的完整性留在输入准入；允许引用已绑定诊断图；保留输出对确切包/实验的引用、真实 JSON pointer；不得伪造新计算。 |
| `science.result.diagnose.v1` | agent | 删除内部证据登记/唯一性、未使用映射拒绝和 locator 重抄；直接消费工具记录，兼容内联记录直接引用；metric 输入相符检查移至 preflight。保留实际引用、计算收据及结论对象对应。 |
| `tcad.control-equivalence.v1` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.curve-bundle.sprocess-log.v1` | transform | 保留确定性归一化的源文件/序列/列/坐标与有效采样条件；无 Agent 重复填表。 |
| `tcad.curve-bundle.sprocess-plx.v1` | transform | 保留确定性归一化的源文件/序列/列/坐标与有效采样条件；无 Agent 重复填表。 |
| `tcad.deck-project-compare.v1` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.deck-review-validate.v1` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.deck.author.initial.v1` | agent | 无同类 ledger 阻断；保留真实源文件/入口/输出/实现条件/案例映射和修改范围；已有缺口成果可提交。作者与审查输出不重判输入资格；冻结输入文件缺失/损坏与已准入能力格式故障归工程问题，不能要求改输出。 |
| `tcad.deck.author.revise.v1` | agent | 无同类 ledger 阻断；保留真实源文件/入口/输出/实现条件/案例映射和修改范围；已有缺口成果可提交。作者与审查输出不重判输入资格；冻结输入文件缺失/损坏与已准入能力格式故障归工程问题，不能要求改输出。 |
| `tcad.deck.author.runtime-failure.v1` | agent | 无同类 ledger 阻断；保留真实源文件/入口/输出/实现条件/案例映射和修改范围；已有缺口成果可提交。作者与审查输出不重判输入资格；冻结输入文件缺失/损坏与已准入能力格式故障归工程问题，不能要求改输出。 |
| `tcad.deck.review.v1` | agent | 无同类 ledger 阻断；保留真实源文件/入口/输出/实现条件/案例映射和修改范围；已有缺口成果可提交。作者与审查输出不重判输入资格；冻结输入文件缺失/损坏与已准入能力格式故障归工程问题，不能要求改输出。 |
| `tcad.execution-context.project.v1` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.parameter.evidence.audit.v1` | agent | 删除检查→自建 evidence 表闭包；直接核对绑定来源；保留独立审查对象与明确检查结果。 |
| `tcad.parameter.evidence.expand.v1` | transform | 沿用放宽后的共享科学模型；保留确定性拆分/投影内容与父链；不增加来源登记。 |
| `tcad.parameter.evidence.extract.v1` | agent | 删除 catalog→Foundation 再登记、全部绑定来源必须抄入 catalog；实际参数观察仍须可定位来源、单位和条件。 |
| `tcad.realization-snapshot-materialize.v1` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.result.analyze.v1` | agent | 删除内部证据登记/唯一性和 locator 重抄；相同映射重复可接受；保留冲突映射拒绝、确切执行/输出/案例、收据与计算来源。 |
| `tcad.reviewed-deck-package.v2` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.runtime-attestation.v1` | transform | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |
| `tcad.study.execute` | effect | 保留确定性实现/运行证据、不可变身份与精确审批/执行权限；均非 Agent 自登记来源规则；运行成功须有实际步骤证据。 |

## 共享模型与边界遗漏的处理

1. 原6次拒绝共同命中 ScientificReview 的 finding→evidence 自登记，已删除。ScientificFoundation、HypothesisProposal、EvidenceAudit、LayeredDiagnosisReport 的同类规则一起删除。ScientificRoleOutput/ValidationReport 当前不属于注册 Agent 主输出；仍在兼容模型中删除同类闭包，但不将它们算作当前生产阻断。
2. 不是只让模型通过：通用/TCAD分析均可直接引用已绑定的工具计算文件，analysis_calculations 消费原始收据，提交不重算。传统 evidence/locator 与 inline record 仍可读。相同 source_reference 重复允许；同一键指向不同来源仍拒绝。
3. 不是把错误拖到审批：通用证据、参数正常资格及例外资格审批不再要求审核表抄齐来源。被冻结、受审查和受批准的完整对象集合仍由控制记录核验。
4. 诊断按所有权修复：Pydantic 已分类的模型 ValueError 保留512字符以内原因；明确 SemanticRuleViolation 保留自身原因，优先嵌套的结构化字段错误；control 产生的文件诊断与 workspace finalizer 的明确协议错误均保持具体原因。任意外来 diagnostic dict 不被自动信任，未知运行异常不被改成“请科学 Agent 修正文案”。JSON 编码错误保留原因与行列/字节位置，不回显内容。
5. 删掉误导性的 experiment.review.verdict_consistency 名称，合同与实际绑定一并改为 experiment.review.structure；角色提示同步取消“再次登记所有来源”的义务。
6. 另发现 generic 分析输出校验比较两个既有输入（metric_report与plan）。该前提移至预检；提交只使用属于当前所分析计划的比较记录，不再因未使用的既有输入拒绝输出。

## 没有删除的检查为什么有用

模型中采样点/字节上限、坐标单调性/正值/区间、交点层级、真实病例或假设主键、文件不覆盖输入等均有可确定的消费后果。确定性 Transform 所生成的状态、摘要、像素计数和覆盖报告不是 Agent 的机械填表义务。来源覆盖/完整集合必须区分：输入冻结集合和审批对象保持完整，Agent 的引用表不承担证明该集合的职责。科学支撑性与缺口对结论的影响仍由科学角色和独立审查决定。

静态基线扫描记录的413个普通异常位置覆盖125个模型/27个文件；该计数包含控制配置和确定性模型，不能称为413个无用校验。此次没有新增状态机、Operation、审批类别或来源注册表。没有声称用有限工程回归证明未来绝无拒绝。
