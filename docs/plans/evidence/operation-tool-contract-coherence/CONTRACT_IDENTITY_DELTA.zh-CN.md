# 编译身份变化

对照修改前实际目录与最终源码目录；隔离安装 wheel 的完整结果另存 INSTALLED_DEFAULT_CATALOG.json、INSTALLED_FIGURE_CATALOG.json，逐项身份与当前源码一致。此表仅是审计产物，不是运行时注册表。

| 组合 | 原/新 Operation 数 | 摘要变化 | Agent 类型变化 |
|---|---:|---:|---:|
| default | 45/45 | 45 | 22 |
| figure | 50/50 | 50 | 25 |

完整旧/新 digest 与 agent_type 见 CONTRACT_IDENTITY_DELTA.json。公共编译材料与组件变化会传播到依赖身份；不得继续使用旧生成的 Worker 类型，也不因身份变化重做无关科学实验。

| Operation（figure 为全集） | 新 agent_type，非 Agent 为 — |
|---|---|
| scidiscovery.curve-bundle.figure-evidence.v2 | — |
| scidiscovery.curve-reference-coverage.v1 | — |
| scidiscovery.curve-score.v1 | — |
| scidiscovery.objective-coverage.v1 | — |
| science.curve.contract.design.v1 | op_science_curve_contract_design_v1_1213b2d3818c |
| science.curve.contract.review.v1 | op_science_curve_contract_review_v1_5c1dd225eeb9 |
| science.curve.error.analyze.v1 | — |
| science.evidence.audit.intake.v1 | op_science_evidence_audit_intake_v1_946952bdf698 |
| science.evidence.audit.v1 | op_science_evidence_audit_v1_e1e9c7e4dd94 |
| science.evidence.extract.figure.v2 | op_science_evidence_extract_figure_v2_41989135f268 |
| science.evidence.extract.v1 | op_science_evidence_extract_v1_4f46fcb94eeb |
| science.evidence.qualify.v1 | — |
| science.evidence.revise-from-critic.v1 | op_science_evidence_revise_from_critic_v1_09e04777ec33 |
| science.experiment.design.v1 | op_science_experiment_design_v1_18d4022b8c4e |
| science.experiment.materialize.v1 | — |
| science.experiment.revise.v1 | op_science_experiment_revise_v1_b58f7f3eee3d |
| science.figure.evidence.audit.v1 | op_science_figure_evidence_audit_v1_039cc500e6e0 |
| science.figure.evidence.materialize.v1 | — |
| science.figure.request.prepare.v1 | op_science_figure_request_prepare_v1_05dfddfcc686 |
| science.hypothesis.criticize.v1 | op_science_hypothesis_criticize_v1_d890f89a1fa3 |
| science.hypothesis.propose.v1 | op_science_hypothesis_propose_v1_15900df6f117 |
| science.hypothesis.revise.v1 | op_science_hypothesis_revise_v1_830099cac9b4 |
| science.intake.revise.v1 | op_science_intake_revise_v1_b61613cfc9fb |
| science.intake.split.v1 | — |
| science.object.review.v1 | op_science_object_review_v1_f33dca64232d |
| science.objective.project.v1 | — |
| science.parameter.coverage.v1 | — |
| science.parameter.uncertainty.v1 | — |
| science.parameters.qualify.exception.v1 | — |
| science.parameters.qualify.pass.v1 | — |
| science.result.diagnose.curve-error.v1 | op_science_result_diagnose_curve_error_v1_1dba5986dcf4 |
| science.result.diagnose.v1 | op_science_result_diagnose_v1_fba7f76437b6 |
| tcad.control-equivalence.v1 | — |
| tcad.curve-bundle.sprocess-log.v1 | — |
| tcad.curve-bundle.sprocess-plx.v1 | — |
| tcad.deck-project-compare.v1 | — |
| tcad.deck-review-validate.v1 | — |
| tcad.deck.author.initial.v1 | op_tcad_deck_author_initial_v1_185cf8db98a7 |
| tcad.deck.author.revise.v1 | op_tcad_deck_author_revise_v1_53f870221d60 |
| tcad.deck.author.runtime-failure.v1 | op_tcad_deck_author_runtime_failure_v1_9d52d0bc37a6 |
| tcad.deck.review.v1 | op_tcad_deck_review_v1_7324bdfb74d5 |
| tcad.execution-context.project.v1 | — |
| tcad.parameter.evidence.audit.v1 | op_tcad_parameter_evidence_audit_v1_5c53ae4b6d54 |
| tcad.parameter.evidence.expand.v1 | — |
| tcad.parameter.evidence.extract.v1 | op_tcad_parameter_evidence_extract_v1_dc906d1e9792 |
| tcad.realization-snapshot-materialize.v1 | — |
| tcad.result.analyze.v1 | op_tcad_result_analyze_v1_71074c580caa |
| tcad.reviewed-deck-package.v2 | — |
| tcad.runtime-attestation.v1 | — |
| tcad.study.execute | — |

Root 工具声明 26→26，Schema 变化项：[]。Lifecycle 声明 3→3，Schema 变化项：[]。共享参数解析与诊断实现变化由边界测试覆盖，未新增第二套声明。
