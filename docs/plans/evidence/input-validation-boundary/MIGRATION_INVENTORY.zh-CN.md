# R4 输入／输出校验职责迁移盘点

状态：已完成本轮静态迁移及真实 5 插件 `all` 目录中 50 个 Operation 的输出绑定核对；最终目录、独立静态审查及定向测试已完成，汇总见 REPORT.zh-CN.md。禁止将静态搜索或测试收集成功等同于全部已注册组件的语义证明。

## 入口及动态注册边界

| 注册／入口 | 可达实现及依赖 | 当前／正确阶段 | 处置与验收 |
| --- | --- | --- | --- |
| `operations/catalog.py::compile_catalog` | 每个 PluginDefinition 的 OperationSpec；OutputPortSpec.validator/context_validator/collection.bundle_validator；validator 的 resource 边；executor/workspace hooks | 启动编译 | 同注册表新增 input_validation.validator 的 validator-kind 和资源可达身份检查；非法引用拒绝。`test_invoke_preflight::test_input_checker_reference_is_compiled_and_default_digest_is_compatible` |
| `operations/invoke.py::preflight_operation` | 显式 BoundInput 元数据、受控 reader、InputValidationSpec | 创建前准入 | 总预算先于 reader；真实 sha256/size 验证；一个组合 checker；输入异常 code/port/field。`test_declared_input_checker_gets_exact_bounded_sources_before_run_creation` |
| Root `_prepare_operation_call`；RunService.schedule | Root 资格/批准/审查政策；服务权威 Artifact 注册记录 | 创建前准入 | Root 不复制政策；直接 schedule 重建权威输入并通过共享 preflight。由生命周期实施测试覆盖零 Run/工作区拒绝 |
| `run_outputs.validate_run_output`／RunService.validate_candidate／submit | 候选 envelope/schema/payload/context；冻结输入 bytes | 输出／控制完整性 | 不调用 input checker；解析暴露既有输入缺陷由 RunCheckerError 保存成果。Root 负责零调用与恢复测试 |
| `operation_contract.operation_port_json_schema`／scheduler_operation_view | 唯一 input_validation_projection | 模型可见合同 | catalog.input_validation 与 Worker `x-scidiscovery-input-validation-contract` 同源；原 input_admission 不变 |
| `execute_compiled_transform`／确定性支持 Operations | OutputPortSpec.validator 及 transform 返回集合 | 输出结构；transform 自身输入算子前提 | 保留正确输出格式检查；不把支持算子的计算前提变成 Agent 交付前提 |
| qualification/approval projector 及 guards | 当前资格、精确父链、批准对象、完整 producer family | 资格／批准／准入 | 保留现有时机；不迁入科学输出；读取历史不授予新资格 |

## 科学 checker 迁移表

规则编号是新 input_validation 的稳定 rule_id；未迁移输出规则保留原输出合同编号。

| Operation / 族 | 实现符号、冻结依赖 | 规则／模型可见条款 | 原阶段 → 正确归属／处理 | 定向验收位置 |
| --- | --- | --- | --- | --- |
| `science.hypothesis.criticize.v1` | general_science_components._critic_portfolio_context；hypothesis_portfolio | `science.hypothesis.criticize.v1.inputs`：输入 portfolio 非空 | 输出 → _critic_inputs 准入；候选 reviews 覆盖每个 hypothesis 一次、handoff 与 disposition 一致仍输出 | test_hypothesis_review_routing、test_agent_contract_alignment |
| `science.hypothesis.propose.v1` / revise | 同文件 _hypothesis_objective_context；scientific_foundation | 各 Operation `.inputs`：foundation 有原始 objective | 输出 → _hypothesis_inputs 准入；候选 objective 身份及修订 key 集不变仍输出 | test_hypothesis_objective_boundary |
| `science.experiment.design.v1` | general_science_experiment_components._experiment_context；critic_review、execution_context | `science.experiment.design.v1.inputs`：critic 支持设计；hypothesis/objective 身份一致；可选能力结构合法 | 输出 → _experiment_inputs（含深层 schema.experiment 的输入身份规则；确定性 materialization 复用该纯输入 helper）；候选目标选择、比较合同、有限覆盖说明仍科学输出／审查 | test_hypothesis_objective_boundary、test_agent_contract_alignment |
| `science.experiment.revise.v1` | 同文件 _experiment_revision_context；change_request | `science.experiment.revise.v1.inputs`：审查对象类型 experiment_portfolio | 输出 → _experiment_revision_inputs；候选不可改既定实验身份仍输出 | test_incremental_revision_runtime |
| `science.object.review.v1` | 同文件 _object_review_context；plan、可选原 objective/execution_context | `science.object.review.v1.inputs`：绑定 objective key/statement 一致 | 输出 → _object_review_inputs；候选 review_target、handoff、证据引用仍输出 | test_agent_contract_alignment |
| evidence extract/revise/audit，包括 figure evidence 复用的 general 组件 | general_science_components._intake_source_context/_evidence_audit_context | intake 引用绑定源；audit exact checks/evidence/handoff | 候选依赖，保留输出；没有要求 evidence 全部通过 | test_minimal_figure_extraction、test_figure_semantic_compilation |
| TCAD parameter evidence audit | parameter_operations._audit_context；package 与 expanded scientific_intake/requirements/parameters/source_catalog | `tcad.parameter.audit.inputs`：展开成员必须等于绑定 package | 输出 → _audit_inputs；候选 checks/source keys/判定仍输出 | test_m2_parameter_package |
| TCAD parameter extract | parameter_operations.validate_extract_context；候选 package 与 sources/checklist | `parameter.source_binding` | 候选 catalog keys、参数 requirement fields 与绑定证据比较，保留输出 | test_m2_parameter_package |
| TCAD result analysis | result_analysis._identity_context/analysis_context；package、manifest、raw products、diagnostics | `tcad.result_analysis.input_binding` | manifest/父链/执行关系准入；候选 plan/case/source 引用与计算重放仍输出；失败与缺产物允许有限报告 | test_tcad_result_analysis、test_analysis_input_descriptors |
| TCAD author/review | plugin._author_context/_review_context/_validate_parameter_uncertainty；project_packager._validate_approved_parameter_bindings | 原 author/review context rules | parameter set/coverage 成对及 key 一致迁到 _parameter_inputs；coverage fail 仅阻止成功实现或 passing review，非pass审查可交付；`require_ready` 依赖候选 result_kind/verdict，保留输出，implementation_gap 可交付 | test_l4_local_tcad、test_tcad_gap_continuation |
| TCAD runtime-failure revision | plugin._runtime_author_context；runtime_attestation.verdict | `tcad.author.runtime_failure.inputs` | `verdict == fail` → _runtime_author_inputs 准入；其余候选实现验收保留 | test_l4_local_tcad |
| curve result diagnosis | curve_score.science_operations._diagnosis_context/_validate_diagnosis | exact selected plan、objective、候选 calculations | 候选引用/计算结果/方法变更/成功声明，保留输出；评分可选 | test_m2_curve_analysis_boundary |
| curve-error diagnosis | 同文件 _curve_diagnosis_context/_validate_diagnosis_against；curve_analysis_package | `curve.diagnosis.inputs`：curve contract、complete-plan metric 覆盖 | package 合同与 coverage → _curve_diagnosis_inputs；候选选定 plan digest、objective assessment、未覆盖检查不能 pass 仍输出 | test_m2_curve_analysis_boundary |
| curve contract design | _curve_contract_context；候选 curve contract 与 plan/objective/reference | 原 contract context rule | 候选机械字段与编译结果一致，保留输出 | test_m2_curve_analysis_boundary |
| curve contract review | _curve_contract_review_context；被审 curve contract 与 plan/objective/reference | 原 review context rule | 删除“被审合同必须先通过机械校验”硬条件，让 reviewer 能交付 revise/reject；候选 review_target/handoff 保留 | test_m2_curve_analysis_boundary |
| figure request prepare | figure_science_operations._validate_request_context；paper_source 与候选 request | 原 curve.figure.request.source_binding | recover_requested_image 依赖候选请求，保留；源集合基数由 PortSpec 保证（已移除冗余源集合检查） | test_figure_semantic_compilation |
| 所有 payload validators / schema resources | 各组件工厂 payload_validator/_strict_validator、model_validate_json、curve/figure/TCAD 输出 models | 每 OutputPortSpec 的 validator_rule_id、semantic_contract | 仅候选内部结构／一致性，保留。schema 自身引用输入仅在 context 层检查 | test_catalog_compile、test_catalog_installed_entrypoint |
| collection validators | curve error plots／TCAD project snapshot family／一般 transform output | 每 CollectionSpec 的 bundle_validator | 同一候选输出集合内部完整性，保留；Run 冻结字节身份归控制层 | test_result_analysis_tool、test_l4_local_tcad |

## 可达性核对要求

默认 builtin + general_science + curve_score + tcad_artifact 与受支持可选 curve_figure_evidence 的真实目录 `all` 投影都必须导出。逐 Operation 展开 `component_ids` 和 `component_specs` 中 validator、resource、workspace_* hook，并将每个实际绑定的输出 validator/context_validator/bundle_validator 对应到上表。无输出 validator 的资源／工具／guard 不冒充输出校验面；动态工厂生成的 spec 不能只凭源码中的字面 ComponentSpec 次数计数。

最终 catalog-source.json 已在全部源码收尾后刷新，包含默认 45 项、可选 figure 组合 50 项及完整 component_specs/resource/hook 闭包；catalog-installed.json 为已部署版本对照，digest-impact.json 记录 20 项变化、30 项不变。早期 catalog-after.json 仅保留盘点过程，最终身份以 catalog-source.json 为准。

## 当前真实目录逐输出绑定核对

来源：`catalog-after.json` 的初始输出枚举，最终以 `catalog-source.json` 复核的 50 个 Operation（不是源码字面注册推测）。下表展开全部输出；`payload` 表示仅候选结构／内部一致性检查，context 对应上表的逐符号语义分类。无输出项为批准等不使用科学输出 validator 的 Operation。

| Operation | 输出 | payload validator | context validator／处置映射 |
| --- | --- | --- | --- |
| `scidiscovery.curve-bundle.figure-evidence.v2` | `curve_bundle` | `component_id='curve_bundle_validator' plugin_id='curve_score'` | `None` |
| `scidiscovery.curve-bundle.figure-evidence.v2` | `normalization_audit` | `component_id='audit_validator' plugin_id='curve_score'` | `None` |
| `scidiscovery.curve-reference-coverage.v1` | `coverage_report` | `component_id='reference_coverage_validator' plugin_id=None` | `None` |
| `scidiscovery.curve-score.v1` | `metric_report` | `component_id='metric_report_validator' plugin_id=None` | `None` |
| `scidiscovery.curve-score.v1` | `merged_curve_bundle` | `component_id='curve_bundle_validator' plugin_id=None` | `None` |
| `scidiscovery.curve-score.v1` | `score_audit` | `component_id='audit_validator' plugin_id=None` | `None` |
| `scidiscovery.curve-score.v1` | `comparison_plot` | `component_id='plot_validator' plugin_id=None` | `None` |
| `scidiscovery.objective-coverage.v1` | `coverage_report` | `component_id='objective_coverage_validator' plugin_id=None` | `None` |
| `science.curve.contract.design.v1` | `curve_contract` | `component_id='curve_contract_validator' plugin_id=None` | `component_id='curve_contract_context' plugin_id=None` |
| `science.curve.contract.review.v1` | `scientific_review` | `component_id='scientific_review_validator' plugin_id=None` | `component_id='curve_contract_review_context' plugin_id=None` |
| `science.curve.error.analyze.v1` | `curve_analysis_package` | `component_id='curve_analysis_package_validator' plugin_id=None` | `None` |
| `science.curve.error.analyze.v1` | `curve_analysis_plots` | `component_id='nonempty_validator' plugin_id=None` | `None` |
| `science.evidence.audit.intake.v1` | `evidence_audit` | `component_id='audit_validator' plugin_id=None` | `component_id='evidence_audit_context' plugin_id=None` |
| `science.evidence.audit.v1` | `evidence_audit` | `component_id='audit_validator' plugin_id=None` | `component_id='evidence_audit_context' plugin_id=None` |
| `science.evidence.extract.figure.v2` | `scientific_intake` | `component_id='intake_validator' plugin_id='general_science'` | `component_id='intake_source_context' plugin_id='general_science'` |
| `science.evidence.extract.v1` | `scientific_intake` | `component_id='intake_validator' plugin_id=None` | `component_id='intake_source_context' plugin_id=None` |
| `science.evidence.qualify.v1` | 无科学输出 | — | 既有批准/控制边界 |
| `science.evidence.revise-from-critic.v1` | `scientific_intake` | `component_id='intake_validator' plugin_id=None` | `component_id='intake_source_context' plugin_id=None` |
| `science.experiment.design.v1` | `experiment_design_intent` | `component_id='experiment_validator' plugin_id=None` | `component_id='experiment_context' plugin_id=None` |
| `science.experiment.materialize.v1` | `experiment_plan` | `component_id='experiment_portfolio_validator' plugin_id=None` | `None` |
| `science.experiment.materialize.v1` | `materialization_report` | `component_id='materialization_report_validator' plugin_id=None` | `None` |
| `science.experiment.revise.v1` | `experiment_plan` | `component_id='experiment_portfolio_validator' plugin_id=None` | `component_id='experiment_revision_context' plugin_id=None` |
| `science.figure.evidence.audit.v1` | `evidence_audit` | `component_id='audit_validator' plugin_id='general_science'` | `component_id='evidence_audit_context' plugin_id='general_science'` |
| `science.figure.evidence.materialize.v1` | `figure_manifest` | `component_id='figure_manifest_validator' plugin_id=None` | `None` |
| `science.figure.evidence.materialize.v1` | `source_panels` | `component_id='figure_png_validator' plugin_id=None` | `None` |
| `science.figure.evidence.materialize.v1` | `audit_overlays` | `component_id='figure_png_validator' plugin_id=None` | `None` |
| `science.figure.evidence.materialize.v1` | `curve_tables` | `component_id='nonempty_validator' plugin_id=None` | `None` |
| `science.figure.evidence.materialize.v1` | `validation_report` | `component_id='figure_report_validator' plugin_id=None` | `None` |
| `science.figure.request.prepare.v1` | `figure_request` | `component_id='figure_request_validator' plugin_id=None` | `component_id='figure_request_context' plugin_id=None` |
| `science.hypothesis.criticize.v1` | `scientific_review` | `component_id='critic_validator' plugin_id=None` | `component_id='critic_portfolio_context' plugin_id=None` |
| `science.hypothesis.propose.v1` | `hypothesis_portfolio` | `component_id='hypothesis_validator' plugin_id=None` | `component_id='hypothesis_objective_context' plugin_id=None` |
| `science.hypothesis.revise.v1` | `hypothesis_portfolio` | `component_id='hypothesis_validator' plugin_id=None` | `component_id='hypothesis_objective_context' plugin_id=None` |
| `science.intake.revise.v1` | `scientific_intake` | `component_id='intake_validator' plugin_id=None` | `component_id='intake_source_context' plugin_id=None` |
| `science.intake.split.v1` | `problem_frame` | `component_id='problem_frame_validator' plugin_id=None` | `None` |
| `science.intake.split.v1` | `scientific_foundation` | `component_id='foundation_validator' plugin_id=None` | `None` |
| `science.object.review.v1` | `scientific_review` | `component_id='review_validator' plugin_id=None` | `component_id='object_review_context' plugin_id=None` |
| `science.objective.project.v1` | `research_objective` | `component_id='objective_validator' plugin_id=None` | `None` |
| `science.parameter.coverage.v1` | `parameter_coverage` | `component_id='parameter_coverage_validator' plugin_id=None` | `None` |
| `science.parameter.uncertainty.v1` | `parameter_uncertainty` | `component_id='parameter_uncertainty_validator' plugin_id=None` | `None` |
| `science.parameters.qualify.exception.v1` | 无科学输出 | — | 既有批准/控制边界 |
| `science.parameters.qualify.pass.v1` | 无科学输出 | — | 既有批准/控制边界 |
| `science.result.diagnose.curve-error.v1` | `layered_diagnosis` | `component_id='diagnosis_validator' plugin_id=None` | `component_id='curve_diagnosis_context' plugin_id=None` |
| `science.result.diagnose.v1` | `layered_diagnosis` | `component_id='diagnosis_validator' plugin_id=None` | `component_id='diagnosis_context' plugin_id=None` |
| `tcad.control-equivalence.v1` | `control_equivalence` | `None` | `None` |
| `tcad.control-equivalence.v1` | `realization_snapshots` | `None` | `None` |
| `tcad.control-equivalence.v1` | `control_audit` | `None` | `None` |
| `tcad.curve-bundle.sprocess-log.v1` | `curve_bundle` | `component_id='curve_bundle_validator' plugin_id='curve_score'` | `None` |
| `tcad.curve-bundle.sprocess-log.v1` | `normalization_audit` | `component_id='curve_normalization_audit_validator' plugin_id=None` | `None` |
| `tcad.curve-bundle.sprocess-plx.v1` | `curve_bundle` | `component_id='curve_bundle_validator' plugin_id='curve_score'` | `None` |
| `tcad.curve-bundle.sprocess-plx.v1` | `normalization_audit` | `component_id='curve_normalization_audit_validator' plugin_id=None` | `None` |
| `tcad.deck-project-compare.v1` | `project_diff` | `None` | `None` |
| `tcad.deck-review-validate.v1` | `review_attestation` | `None` | `None` |
| `tcad.deck.author.initial.v1` | `project` | `component_id='project_validator' plugin_id=None` | `component_id='author_context' plugin_id=None` |
| `tcad.deck.author.revise.v1` | `project` | `component_id='project_validator' plugin_id=None` | `component_id='author_context' plugin_id=None` |
| `tcad.deck.author.runtime-failure.v1` | `project` | `component_id='project_validator' plugin_id=None` | `component_id='runtime_author_context' plugin_id=None` |
| `tcad.deck.review.v1` | `review` | `component_id='review_validator' plugin_id=None` | `component_id='review_context' plugin_id=None` |
| `tcad.execution-context.project.v1` | `execution_context` | `None` | `None` |
| `tcad.parameter.evidence.audit.v1` | `evidence_audit` | `component_id='audit_validator' plugin_id=None` | `component_id='evidence_audit_context' plugin_id=None` |
| `tcad.parameter.evidence.expand.v1` | `scientific_intake` | `component_id='intake_validator' plugin_id=None` | `None` |
| `tcad.parameter.evidence.expand.v1` | `parameter_requirements` | `component_id='parameter_requirements_validator' plugin_id=None` | `None` |
| `tcad.parameter.evidence.expand.v1` | `device_parameters` | `component_id='device_parameters_validator' plugin_id=None` | `None` |
| `tcad.parameter.evidence.expand.v1` | `source_catalog` | `component_id='source_catalog_validator' plugin_id=None` | `None` |
| `tcad.parameter.evidence.extract.v1` | `parameter_evidence_package` | `component_id='parameter_package_validator' plugin_id=None` | `component_id='parameter_extract_context' plugin_id=None` |
| `tcad.realization-snapshot-materialize.v1` | `realization_snapshot` | `None` | `None` |
| `tcad.result.analyze.v1` | `layered_diagnosis` | `component_id='result_analysis_validator' plugin_id=None` | `component_id='result_analysis_context' plugin_id=None` |
| `tcad.reviewed-deck-package.v2` | `reviewed_package` | `None` | `None` |
| `tcad.runtime-attestation.v1` | `runtime_attestation` | `None` | `None` |
| `tcad.study.execute` | `execution_request` | `None` | `None` |
