# 当前 Operation 校验处置清单

本清单覆盖本仓库五个生产插件入口编译出的全部 50 个 Operation。83 是具名 validator／guard 组件数，不是规则条数；模型验证、工具算法、审批 projector 和执行 adapter 的约束另按其所有者审查。完整声明见 INVENTORY_BEFORE.json 与 INVENTORY_AFTER.json。未把“删掉所有校验器”作为目标。

## 逐 Operation

| Operation | 执行种类 | 具名检查组件 | 处置 |
| --- | --- | --- | --- |
| scidiscovery.curve-bundle.figure-evidence.v2 | transform | curve_figure_evidence:figure_parentage<br>curve_score:audit_validator<br>curve_score:curve_bundle_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| scidiscovery.curve-reference-coverage.v1 | transform | curve_score:reference_coverage_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| scidiscovery.curve-score.v1 | transform | curve_score:audit_validator<br>curve_score:curve_bundle_validator<br>curve_score:metric_report_validator<br>curve_score:plot_validator<br>curve_score:score_parentage | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| scidiscovery.objective-coverage.v1 | transform | curve_score:objective_coverage_validator<br>curve_score:objective_parentage | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.curve.contract.design.v1 | agent | curve_score:curve_contract_context<br>curve_score:curve_contract_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.curve.contract.review.v1 | agent | curve_score:curve_contract_review_context<br>curve_score:scientific_review_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.curve.error.analyze.v1 | transform | curve_score:curve_analysis_package_validator<br>curve_score:nonempty_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.evidence.audit.intake.v1 | agent | general_science:audit_validator<br>general_science:evidence_audit_context | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.evidence.audit.v1 | agent | general_science:audit_validator<br>general_science:evidence_audit_context | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.evidence.extract.figure.v2 | agent | curve_figure_evidence:figure_revision_parentage<br>general_science:intake_source_context<br>general_science:intake_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.evidence.extract.v1 | agent | general_science:intake_source_context<br>general_science:intake_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.evidence.qualify.v1 | approval |  | 审批 projector 保留精确来源、完整生产集合、独立审查和人工决定；不读取分析 claim_allowed 作为授权。 |
| science.evidence.revise-from-critic.v1 | agent | general_science:evidence_revision_cohort<br>general_science:intake_source_context<br>general_science:intake_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.experiment.design.v1 | agent | general_science:experiment_context<br>general_science:experiment_inputs<br>general_science:experiment_science_cohort<br>general_science:experiment_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.experiment.materialize.v1 | transform | general_science:experiment_lineage<br>general_science:experiment_portfolio_validator<br>general_science:materialization_report_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.experiment.revise.v1 | agent | general_science:experiment_portfolio_validator<br>general_science:experiment_revision_context<br>general_science:experiment_revision_inputs | 随共享组件删减，必要结构／身份校验保留。 |
| science.figure.evidence.audit.v1 | agent | general_science:audit_validator<br>general_science:evidence_audit_context | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.figure.evidence.materialize.v1 | transform | curve_figure_evidence:figure_manifest_validator<br>curve_figure_evidence:figure_png_validator<br>curve_figure_evidence:figure_report_validator<br>curve_figure_evidence:nonempty_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.figure.request.prepare.v1 | agent | curve_figure_evidence:figure_request_context<br>curve_figure_evidence:figure_request_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.hypothesis.criticize.v1 | agent | general_science:critic_inputs<br>general_science:critic_portfolio_context<br>general_science:critic_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.hypothesis.propose.v1 | agent | general_science:hypothesis_inputs<br>general_science:hypothesis_objective_context<br>general_science:hypothesis_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.hypothesis.revise.v1 | agent | general_science:hypothesis_inputs<br>general_science:hypothesis_objective_context<br>general_science:hypothesis_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.intake.revise.v1 | agent | general_science:intake_source_context<br>general_science:intake_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.intake.split.v1 | transform | general_science:foundation_validator<br>general_science:problem_frame_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.object.review.v1 | agent | general_science:object_review_context<br>general_science:object_review_inputs<br>general_science:review_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.objective.project.v1 | transform | general_science:objective_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.parameter.coverage.v1 | transform | tcad_artifact:parameter_coverage_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.parameter.uncertainty.v1 | transform | tcad_artifact:parameter_uncertainty_lineage<br>tcad_artifact:parameter_uncertainty_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| science.parameters.qualify.exception.v1 | approval |  | 审批 projector 保留精确对象、显式例外理由与人工决定。 |
| science.parameters.qualify.pass.v1 | approval |  | 审批 projector 保留精确参数家族、独立审计与正常资格条件。 |
| science.result.diagnose.curve-error.v1 | agent | curve_score:curve_diagnosis_context<br>curve_score:curve_diagnosis_inputs<br>curve_score:diagnosis_validator | 随共享组件删减，必要结构／身份校验保留。 |
| science.result.diagnose.v1 | agent | curve_score:diagnosis_context<br>curve_score:diagnosis_identity<br>curve_score:diagnosis_inputs<br>curve_score:diagnosis_validator | 随共享组件删减，必要结构／身份校验保留。 |
| tcad.control-equivalence.v1 | transform |  | 确定性组件比较已声明控制项与实际实现；不是科学总体结论。 |
| tcad.curve-bundle.sprocess-log.v1 | transform | curve_score:curve_bundle_validator<br>tcad_artifact:curve_log_parentage<br>tcad_artifact:curve_normalization_audit_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.curve-bundle.sprocess-plx.v1 | transform | curve_score:curve_bundle_validator<br>tcad_artifact:curve_normalization_audit_validator<br>tcad_artifact:curve_plx_parentage | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.deck-project-compare.v1 | transform |  | 确定性组件比较项目和计划中的实际字段。 |
| tcad.deck-review-validate.v1 | transform |  | 确定性组件确认当前项目及精确独立审查可打包，保留执行准入。 |
| tcad.deck.author.initial.v1 | agent | tcad_artifact:author_context<br>tcad_artifact:parameter_cohort_guard<br>tcad_artifact:parameter_inputs<br>tcad_artifact:project_validator | 随共享组件删减，必要结构／身份校验保留。 |
| tcad.deck.author.revise.v1 | agent | tcad_artifact:author_context<br>tcad_artifact:parameter_cohort_guard<br>tcad_artifact:parameter_inputs<br>tcad_artifact:project_validator | 随共享组件删减，必要结构／身份校验保留。 |
| tcad.deck.author.runtime-failure.v1 | agent | tcad_artifact:parameter_cohort_guard<br>tcad_artifact:project_validator<br>tcad_artifact:runtime_author_context<br>tcad_artifact:runtime_author_inputs | 随共享组件删减，必要结构／身份校验保留。 |
| tcad.deck.review.v1 | agent | tcad_artifact:parameter_cohort_guard<br>tcad_artifact:parameter_inputs<br>tcad_artifact:review_context<br>tcad_artifact:review_validator | 随共享组件删减，必要结构／身份校验保留。 |
| tcad.execution-context.project.v1 | transform |  | 确定性投影实际后端能力，不赋予执行权限。 |
| tcad.parameter.evidence.audit.v1 | agent | tcad_artifact:audit_validator<br>tcad_artifact:evidence_audit_context<br>tcad_artifact:parameter_audit_inputs | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.parameter.evidence.expand.v1 | transform | tcad_artifact:device_parameters_validator<br>tcad_artifact:intake_validator<br>tcad_artifact:parameter_requirements_validator<br>tcad_artifact:source_catalog_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.parameter.evidence.extract.v1 | agent | tcad_artifact:parameter_extract_context<br>tcad_artifact:parameter_package_validator | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.realization-snapshot-materialize.v1 | transform |  | 控制工具从已有项目和计划产生实现快照，避免作者重复填派生字段。 |
| tcad.result.analyze.v1 | agent | tcad_artifact:result_analysis_context<br>tcad_artifact:result_analysis_input<br>tcad_artifact:result_analysis_parentage<br>tcad_artifact:result_analysis_validator | 随共享组件删减，必要结构／身份校验保留。 |
| tcad.reviewed-deck-package.v2 | transform | tcad_artifact:package_parentage | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.runtime-attestation.v1 | transform | tcad_artifact:runtime_parentage | 保留所列组件的实际格式、身份、来源或确定性数据约束。 |
| tcad.study.execute | effect |  | Effect 保留精确已审项目与执行请求的审批、预算及执行权限。 |

## 逐组件

| 组件 | 处置 | 保留理由／删除内容 | 实现 |
| --- | --- | --- | --- |
| curve_figure_evidence:figure_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/curve_figure_evidence/curve_figure_evidence/operation_transforms.py:114` |
| curve_score:audit_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:68` |
| curve_score:curve_bundle_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_score:reference_coverage_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_score:metric_report_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_score:plot_validator | 保留 | 确定性输出文件的非空／可读媒体格式边界，避免把错误页面或空文件登记为实际产物。 | `plugins/curve_score/curve_score/operation_transforms.py:74` |
| curve_score:score_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/curve_score/curve_score/operation_transforms.py:142` |
| curve_score:objective_coverage_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_score:objective_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/curve_score/curve_score/operation_transforms.py:152` |
| curve_score:curve_contract_context | 保留 | 保留：控制工具生成的机械合同须与精确意图、计划和参考数据一致；不要求 Agent 手填，亦不运行评分。 | `plugins/curve_score/curve_score/science_operations.py:119` |
| curve_score:curve_contract_validator | 删减 | 共享 CurveComparisonSpec 允许全部比较为可选，不从用途固定 required；既有专用合同仍须兑现其已声明计划。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_score:curve_contract_review_context | 保留 | 保留：确为领域合同审查且交接忠实于审查 verdict；不把合同 review 当执行授权。 | `plugins/curve_score/curve_score/science_operations.py:137` |
| curve_score:scientific_review_validator | 删减 | 复用科学审查模型的同一删改，不保留领域内规则副本。 | `src/scidiscovery/operation_declaration.py:85` |
| curve_score:curve_analysis_package_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/science_operations.py:849` |
| curve_score:nonempty_validator | 保留 | 确定性输出文件的非空／可读媒体格式边界，避免把错误页面或空文件登记为实际产物。 | `plugins/curve_score/curve_score/science_operations.py:150` |
| general_science:audit_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:evidence_audit_context | 保留 | 保留：证据审计检查必须有依据，审计失败／未知不能通过交接变成有资格的 PASS；忠实报告来源局限可获审计通过。 | `src/scidiscovery/general_science_components.py:174` |
| curve_figure_evidence:figure_revision_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py:190` |
| general_science:intake_source_context | 保留 | 保留：引用须来自本轮实际绑定来源；不判断其科学结论。 | `src/scidiscovery/general_science_components.py:85` |
| general_science:intake_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:evidence_revision_cohort | 保留 | 保留：精确来源、前轮稿、审查、基础和假设的父链，防止修订偷偷更换证据。 | `src/scidiscovery/general_science_components.py:99` |
| general_science:experiment_context | 删减 | 随共享意图／实验模型取消固定实验形状；物化程序生成案例数等机械字段，核验所选目标与假设确有绑定。 | `src/scidiscovery/general_science_experiment_components.py:184` |
| general_science:experiment_inputs | 保留 | 保留在 preflight：目标／假设配对和输入结构、精确 critic 的可设计处置；提交不重做该准入。 | `src/scidiscovery/general_science_experiment_components.py:167` |
| general_science:experiment_science_cohort | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `scidiscovery.general_science_experiment_components:ExperimentComponents.experiment_science_cohort` |
| general_science:experiment_validator | 删减 | 删除科学必须对照／至少两案例／完整预测模板、工程只能单案例模板；保留原目标身份及物化所需结构。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:experiment_lineage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `src/scidiscovery/general_science_experiment_components.py:151` |
| general_science:experiment_portfolio_validator | 删减 | 同共享实验模型删减；可选识别性主张不要求覆盖所有假设，但引用必须存在。 | `src/scidiscovery/general_science_experiment_components.py:159` |
| general_science:materialization_report_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/general_science_experiment_components.py:131` |
| general_science:experiment_revision_context | 删减 | 解析采用放宽的共享模型；保留修订对象的研究身份，改变身份应创建新的设计。 | `src/scidiscovery/general_science_experiment_components.py:196` |
| general_science:experiment_revision_inputs | 保留 | 保留在 preflight：变更请求实际审查的对象类型须为实验计划。 | `src/scidiscovery/general_science_experiment_components.py:190` |
| curve_figure_evidence:figure_manifest_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_figure_evidence:figure_png_validator | 保留 | 确定性输出文件的非空／可读媒体格式边界，避免把错误页面或空文件登记为实际产物。 | `plugins/curve_score/curve_score/operation_transforms.py:74` |
| curve_figure_evidence:figure_report_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/operation_transforms.py:59` |
| curve_figure_evidence:nonempty_validator | 保留 | 确定性输出文件的非空／可读媒体格式边界，避免把错误页面或空文件登记为实际产物。 | `plugins/curve_score/curve_score/science_operations.py:150` |
| curve_figure_evidence:figure_request_context | 保留 | 保留：恢复的原图须对应精确论文页／图像和哈希；不是重算科学结论或要求重新提取曲线。 | `plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py:159` |
| curve_figure_evidence:figure_request_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:critic_inputs | 保留 | 保留在 preflight：被批评的假设集合非空。 | `src/scidiscovery/general_science_components.py:48` |
| general_science:critic_portfolio_context | 保留 | 保留：本操作承诺逐个审查精确假设集合，不能漏审而交付整组 PASS；交接忠实投影 critic 自己选择的 disposition。 | `src/scidiscovery/general_science_components.py:62` |
| general_science:critic_validator | 删减 | 删除各维度到 disposition 的固定公式，以及未知问题必须提出解决办法的要求；保留键与引用。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:hypothesis_inputs | 保留 | 保留在 preflight：明确原始研究目标，避免静默创造研究任务。 | `src/scidiscovery/general_science_components.py:55` |
| general_science:hypothesis_objective_context | 保留 | 保留：输出引用原始目标、修订保持既定假设身份；不按文字长度判定科学进展。 | `src/scidiscovery/general_science_components.py:130` |
| general_science:hypothesis_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:foundation_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/general_science_components.py:186` |
| general_science:problem_frame_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/general_science_components.py:186` |
| general_science:object_review_context | 保留 | 保留：审查对象身份、实际来源、载荷 verdict 与将用于资格的交接值一致；不推导科学 verdict。 | `src/scidiscovery/general_science_experiment_components.py:234` |
| general_science:object_review_inputs | 保留 | 保留在 preflight：绑定目标与被审计划一致、可选执行上下文可解析；不因计划科学 blocked 禁止审查。 | `src/scidiscovery/general_science_experiment_components.py:218` |
| general_science:review_validator | 删减 | 删除维度状态到科学 verdict 的固定公式；保留报告结构和引用。 | `src/scidiscovery/operation_declaration.py:85` |
| general_science:objective_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `src/scidiscovery/general_science_experiment_components.py:131` |
| tcad_artifact:parameter_coverage_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:183` |
| tcad_artifact:parameter_uncertainty_lineage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:307` |
| tcad_artifact:parameter_uncertainty_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:183` |
| curve_score:curve_diagnosis_context | 删减 | 删除预计算报告强制目标评估及覆盖／结论公式；保留精确包内引用，当前角色未获评分工具所以不得伪造新计算。 | `plugins/curve_score/curve_score/science_operations.py:643` |
| curve_score:curve_diagnosis_inputs | 保留 | 保留在 preflight：专用已计算诊断包必须是所声明合同的完整确定性包；通用／TCAD 分析不要求此包或前置评分。 | `plugins/curve_score/curve_score/science_operations.py:626` |
| curve_score:diagnosis_validator | 删减 | 共享分析模型删除科学／工程标签、六门状态和总体结论的固定联动；保留结构、边界和引用。 | `src/scidiscovery/operation_declaration.py:85` |
| curve_score:diagnosis_context | 删减 | 删除提交评分重放、必填目标评估、必需检查覆盖和阈值推导总体结论；保留精确计划、引用、收据。 | `plugins/curve_score/curve_score/science_operations.py:573` |
| curve_score:diagnosis_identity | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/curve_score/curve_score/science_operations.py:254` |
| curve_score:diagnosis_inputs | 保留 | 保留在 preflight：显式绑定计划、结果、可选度量的结构与身份；失败执行仍可分析。 | `plugins/curve_score/curve_score/science_operations.py:269` |
| tcad_artifact:curve_log_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/curve_operations.py:250` |
| tcad_artifact:curve_normalization_audit_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/curve_operations.py:259` |
| tcad_artifact:curve_plx_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/curve_operations.py:233` |
| tcad_artifact:author_context | 删减 | 删除提交时重查参数 uncertainty.ready；缺口只在载荷填一次；保留实际项目与绑定计划、参数值及单位一致。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:94` |
| tcad_artifact:parameter_cohort_guard | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:147` |
| tcad_artifact:parameter_inputs | 保留 | 保留在 preflight：参数集与覆盖报告成对且同一集合；不是按覆盖不足拒绝所有下游。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:100` |
| tcad_artifact:project_validator | 保留 | 项目／审查数据结构及执行就绪声明一致性；真实实现、初始化、独立审查与授权仍为执行条件。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:82` |
| tcad_artifact:runtime_author_context | 删减 | 与初始作者共用删减；不对已绑定参数重做就绪判断，保留输出实现与既有任务身份。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:121` |
| tcad_artifact:runtime_author_inputs | 保留 | 保留在 preflight：故障修订绑定既定参数集合；与新输出实现校验分离。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:113` |
| tcad_artifact:review_context | 删减 | 删除提交时参数就绪复查；允许缺口审查给出具体失败，允许附加已物化要求的审查；保留实际执行所需项目／审查条件。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:127` |
| tcad_artifact:review_validator | 保留 | 项目／审查数据结构及执行就绪声明一致性；真实实现、初始化、独立审查与授权仍为执行条件。 | `plugins/tcad_artifact/tcad_artifact/plugin.py:82` |
| tcad_artifact:audit_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:195` |
| tcad_artifact:evidence_audit_context | 保留 | 保留：来源审计的精确引用及明确审计状态到资格交接的忠实映射；不是假设／结果的科学结论公式。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:229` |
| tcad_artifact:parameter_audit_inputs | 保留 | 保留在 preflight：审计包与其确定性展开完全相同，不能拼接另一包的数据。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:207` |
| tcad_artifact:device_parameters_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:183` |
| tcad_artifact:intake_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:195` |
| tcad_artifact:parameter_requirements_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:183` |
| tcad_artifact:source_catalog_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:183` |
| tcad_artifact:parameter_extract_context | 保留 | 保留：提取包使用实际来源别名，并忠实于绑定的参数清单，不改变任务要求。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:382` |
| tcad_artifact:parameter_package_validator | 保留 | 输出模型的结构、资源边界、唯一键／引用及确定性产物内部一致性；不增加科学结论准入。 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:183` |
| tcad_artifact:result_analysis_context | 删减 | 删除提交评分重放、重复案例映射和说明逐字比对、执行状态推导科学结论；保留精确计划、引用和控制收据完整性。 | `plugins/tcad_artifact/tcad_artifact/result_analysis.py:353` |
| tcad_artifact:result_analysis_input | 保留 | 保留在 preflight：分析输入对应同一计划、项目、终态执行和产物；允许失败／缺少产物的分析。 | `plugins/tcad_artifact/tcad_artifact/result_analysis.py:271` |
| tcad_artifact:result_analysis_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/result_analysis.py:79` |
| tcad_artifact:result_analysis_validator | 删减 | 同通用分析共享模型；不按执行状态或预设门状态替分析者决定结论。 | `src/scidiscovery/operation_declaration.py:85` |
| tcad_artifact:package_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/operation_transforms.py:171` |
| tcad_artifact:runtime_parentage | 保留 | 精确父链、生产者／审查组合与同一执行身份；不允许同字节的另一执行替代本次证据。 | `plugins/tcad_artifact/tcad_artifact/operation_transforms.py:183` |

## 共享模型及工具边界

- 实验意图由 Agent 选择；物化程序继续生成案例数、总体目标展开和比较字段，Agent 无需重填这些机械字段。既有比较合同一旦声明，其案例、变量值、单位和引用仍必须自洽。
- 分析、critic 和科学审查不再把维度状态组合成固定科学结论。保留现有报告结构以读取历史载荷；这次没有重做所有科学表单。
- 曲线评分工具仍检查实际可计算条件：有限数、轴、单位、引用、采样边界及准确来源。工具返回记录由控制层收据证明；不让提交重新评分。
- TCAD 案例在项目中已声明时，工具复用该身份；尚未声明的科学对应关系由 Agent 给依据一次，不能覆盖已声明案例或换成另一执行的同字节产物。
- 证据审计与执行审查的资格交接保持明确：来源审计失败不能变成已核准证据，无实现的缺口不能声称 execution_ready。分析的科学 claim_allowed 不授予控制权。
- 旧 ValidationReport 的未挂载入口不纳入本次活跃 Operation 删改；没有批量删除历史兼容类型。
- 所有授权、不可变记录、预算、独立审查边和历史可读性仍由原控制机制处理，没有新增 Operation、状态机或规则注册表。
