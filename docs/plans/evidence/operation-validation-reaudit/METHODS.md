# 可达模型校验方法逐项判断

索引对应 METHODS.json；包含继承/别名，不是原子规则总数。异常表达式在 JSON 附件，不伪造推导其路径分支条件。

| 索引 | 符号 | 位置 | 判断 |
| --- | --- | --- | --- |
| 0 | `SchemaModel._freeze_nested_values` | `src/scidiscovery/artifact_agent/schema/common.py:66` | 冻结嵌套值，无科学门槛。 |
| 1 | `ParameterForm._calibratable_parameter_is_bounded` | `src/scidiscovery/artifact_agent/schema/cognitive.py:50` | 声明可校准参数必须有范围描述；这不是强迫当前实现尚缺的参数。 |
| 2 | `HypothesisForm._local_keys_are_unique` | `src/scidiscovery/artifact_agent/schema/cognitive.py:84` | 预测/证伪等局部实体键防歧义；保留。 |
| 3 | `HypothesisProposal._portfolio_is_coherent` | `src/scidiscovery/artifact_agent/schema/cognitive.py:106` | 目标身份、hypothesis 实体键和引用闭合；保留，目标镜像见 F04。 |
| 4 | `CriticReview._keys_are_unique` | `src/scidiscovery/artifact_agent/schema/cognitive.py:146` | 每条 hypothesis 一份批评是该完整评审任务的明确范围；保留。 |
| 5 | `EvidenceCheckForm._references_are_unique` | `src/scidiscovery/artifact_agent/schema/cognitive.py:193` | 区分主键与引用列表；引用去重见 F02。 |
| 6 | `EvidenceAudit._audit_is_coherent` | `src/scidiscovery/artifact_agent/schema/cognitive.py:206` | 检查项实体键、已有证据引用可解析；保留。 |
| 7 | `ObjectiveTarget._evidence_is_unique` | `src/scidiscovery/artifact_agent/schema/research_objective.py:37` | 纯引用去重，见 F02。 |
| 8 | `ObjectiveClosureRequirement._subjects_match_type` | `src/scidiscovery/artifact_agent/schema/research_objective.py:126` | 不同 closure 类型参数配对有用；纯列表去重见 F02。 |
| 9 | `ResearchObjectiveContract._objective_is_complete` | `src/scidiscovery/artifact_agent/schema/research_objective.py:170` | 目标主键唯一、closure 引用存在；external_reproduction 要有外部目标是对象的用途定义，保留。 |
| 10 | `EvidenceUncertainty._numeric_value_has_unit` | `src/scidiscovery/artifact_agent/schema/scientific_foundation.py:42` | 数值不确定度与单位配对；保留。 |
| 11 | `EvidenceItem._scientific_basis_is_explicit` | `src/scidiscovery/artifact_agent/schema/scientific_foundation.py:82` | 事实有来源、推断有理由有用；标签/重复引用见 F02。 |
| 12 | `EvidenceConflict._resolution_matches_status` | `src/scidiscovery/artifact_agent/schema/scientific_foundation.py:122` | 解决/未解决冲突不能同时声称无处置；保留。 |
| 13 | `ScientificFoundation._references_are_local_and_complete` | `src/scidiscovery/artifact_agent/schema/scientific_foundation.py:148` | 实体引用闭合有用；同源多定位、重复目标见 F03/F04。 |
| 14 | `ResearchObservable._references_are_unique` | `src/scidiscovery/artifact_agent/schema/research_cycle.py:28` | 引用列表去重见 F02。 |
| 15 | `ProblemFrame._frame_is_closed` | `src/scidiscovery/artifact_agent/schema/research_cycle.py:64` | observable 实体键及引用存在；保留。 |
| 16 | `ScientificReview._review_is_coherent` | `src/scidiscovery/artifact_agent/schema/research_cycle.py:121` | 主体评审键和引用存在保留；纯引用去重/同源多位置见 F02/F03。 |
| 17 | `ScientificIntake._frame_uses_the_supplied_foundation` | `src/scidiscovery/artifact_agent/schema/research_cycle.py:150` | frame 与 foundation 的实际引用一致保留；目标原文复制见 F04。 |
| 18 | `MetricThreshold._range_matches_operator` | `src/scidiscovery/artifact_agent/schema/experiment.py:43` | between 与上下限配对保证可计算；保留。 |
| 19 | `MetricThreshold._unit_is_supported` | `src/scidiscovery/artifact_agent/schema/experiment.py:37` | 数值阈值单位可解释；保留。 |
| 20 | `ExperimentFactor._values_are_unique` | `src/scidiscovery/artifact_agent/schema/experiment.py:60` | 因子候选值重复可导致重复展开案例；当前保留，未来若规范化必须同时验证展开数。 |
| 21 | `ExperimentCase._setting_names_are_unique` | `src/scidiscovery/artifact_agent/schema/experiment.py:85` | 同一案例参数不能有冲突赋值；保留。 |
| 22 | `ComparisonVariable._comparison_semantics_are_explicit` | `src/scidiscovery/artifact_agent/schema/experiment.py:121` | intended_change/frozen、容差与值类型是已经选定比较的定义；保留。 |
| 23 | `ComparisonContract._contract_keys_are_unique` | `src/scidiscovery/artifact_agent/schema/experiment.py:168` | 比较本身的角色/变量/案例引用完整性有用；不是要求整个总体目标全覆盖。 |
| 24 | `ExperimentProposal._proposal_is_bounded` | `src/scidiscovery/artifact_agent/schema/experiment.py:233` | 混合：选中比较引用/值/单位保留；case_count 派生、全案例及 observable 等式见 F04/F05。 |
| 25 | `ValidationCheck._threshold_matches_evaluation` | `src/scidiscovery/artifact_agent/schema/experiment.py:352` | 已经选 deterministic_threshold 才要求阈值，qualitative 可不填；保留。 |
| 26 | `ValidationDimensionPlan._applicability_matches_checks` | `src/scidiscovery/artifact_agent/schema/experiment.py:375` | not_applicable 与实际检查的定义一致性；保留。 |
| 27 | `ValidationPlan._check_keys_are_globally_unique` | `src/scidiscovery/artifact_agent/schema/experiment.py:395` | 计划 check_key 主键全局可解析；保留。 |
| 28 | `ExperimentPortfolio._portfolio_is_complete_and_ranked` | `src/scidiscovery/artifact_agent/schema/experiment.py:425` | proposal 主键和已选验证计划对应保留；目标字符串、priority_order 的机械完整投影见 F04（排序选择本身归 Agent）。 |
| 29 | `IntentComparisonVariable._override_and_tolerance_contract` | `src/scidiscovery/artifact_agent/schema/experiment_intent.py:72` | 精简意图的 override/tolerance 定义；保留。 |
| 30 | `IntentValidationDimension._deterministic_keys_are_unique` | `src/scidiscovery/artifact_agent/schema/experiment_intent.py:122` | 选中 validation 的实体键不冲突；保留。 |
| 31 | `ExperimentProposalIntent._intent_is_bounded` | `src/scidiscovery/artifact_agent/schema/experiment_intent.py:170` | 意图中的已选变量/案例引用和 intended/frozen 检查有用；不推导必须覆盖所有总体目标。 |
| 32 | `ExperimentDesignIntent._portfolio_intent_is_complete` | `src/scidiscovery/artifact_agent/schema/experiment_intent.py:248` | 区分科学研究与 engineering_qualification 的身份要求；目前保留，缺假设可另走工程实验。 |
| 33 | `ExperimentPlanMaterializationReport._source_hashes_are_all_present_or_absent` | `src/scidiscovery/artifact_agent/schema/experiment_intent.py:293` | 控制生成 materialization 记录的来源摘要应完整成组；保留。 |
| 34 | `CurveInterval._ordered` | `plugins/curve_score/curve_score/schema.py:76` | 区间必须有正长度；保留。 |
| 35 | `CurveAvailability._reason_matches_status` | `plugins/curve_score/curve_score/schema.py:88` | available/unavailable 原因字段一致；保留。 |
| 36 | `CurveSeries._points_and_intervals_are_coherent` | `plugins/curve_score/curve_score/schema.py:114` | 曲线点、轴域和区间支撑是数学输入条件；保留。 |
| 37 | `CurveSeriesDeclaration._point_bounds_are_ordered` | `plugins/curve_score/curve_score/schema.py:150` | 点数支持上下界有序；保留。 |
| 38 | `CurveBundle._series_are_unique` | `plugins/curve_score/curve_score/schema.py:164` | 序列身份唯一防止错误配对；保留。 |
| 39 | `CurveDomain._ordered` | `plugins/curve_score/curve_score/schema.py:183` | 计算区间有序；保留。 |
| 40 | `CurveThreshold._absolute_limit_is_nonnegative` | `plugins/curve_score/curve_score/schema.py:195` | 绝对误差阈值不能为负；保留。 |
| 41 | `CurveOperatorSpec._parameters_match_operator` | `plugins/curve_score/curve_score/schema.py:227` | 算子所需参数不可缺或互相矛盾；保留。 |
| 42 | `CurveComparison._operators_are_unique` | `plugins/curve_score/curve_score/schema.py:264` | 算子 key 主键保留；用途/标签限定算法见 F06。 |
| 43 | `CurveComparisonSpec._comparisons_are_unique` | `plugins/curve_score/curve_score/schema.py:342` | 实际引用存在保留；用途角色硬矩阵/全部参考使用见 F06/F07。 |
| 44 | `CurveObjectiveTargetBinding._domains_are_unique` | `plugins/curve_score/curve_score/schema.py:482` | 重复域可确定性去重；次要简化候选，不改变真实区间支撑。 |
| 45 | `CurveExperimentContract._objective_bindings_are_unique` | `plugins/curve_score/curve_score/schema.py:502` | 目标绑定身份及引用存在；保留。 |
| 46 | `CurveReferenceOperatorSupport._status_matches_counts` | `plugins/curve_score/curve_score/schema.py:744` | 程序生成 reference support 的计数与状态一致；保留。 |
| 47 | `CurveReferenceComparisonSupport._status_matches_support` | `plugins/curve_score/curve_score/schema.py:781` | 程序生成 comparison support 聚合；保留。 |
| 48 | `CurveReferenceCoverageReport._status_matches_coverage` | `plugins/curve_score/curve_score/schema.py:824` | 程序生成 coverage 聚合及引用；保留；不自动成为 author/执行前置。 |
| 49 | `CurveMetricCrossingSupport._locations_are_finite` | `plugins/curve_score/curve_score/schema.py:857` | 输出 crossing 数值有限与支撑一致；保留。 |
| 50 | `CurveMetricResult._value_matches_status` | `plugins/curve_score/curve_score/schema.py:884` | 计算结果 available/value 配对；保留。 |
| 51 | `CurveThresholdResult._observed_matches_status` | `plugins/curve_score/curve_score/schema.py:902` | 数值阈值的程序结果自洽；保留。 |
| 52 | `CurveComparisonResult._status_is_derived` | `plugins/curve_score/curve_score/schema.py:925` | 计算器对自己产出的比较状态聚合；保留，不代替整体科学结论。 |
| 53 | `CurveConsistencyReport._aggregate_is_derived` | `plugins/curve_score/curve_score/schema.py:970` | 计算器报告计数/聚合；保留，不把局部分数当总目标完成。 |
| 54 | `ObjectiveTargetCoverage._status_matches_reasons` | `plugins/curve_score/curve_score/objective.py:57` | 程序生成目标覆盖报告原因与状态；保留。 |
| 55 | `ObjectiveRequirementCoverage._status_matches_reasons` | `plugins/curve_score/curve_score/objective.py:75` | 程序生成 closure 覆盖报告原因与状态；保留。 |
| 56 | `ObjectiveCoverageReport._aggregate_is_derived` | `plugins/curve_score/curve_score/objective.py:105` | 覆盖器的机械聚合；保留；具体是否阻止当前实验仍由实际 Operation 准入决定。 |
| 57 | `CurveErrorSegment._range_and_metrics_are_coherent` | `plugins/curve_score/curve_score/analysis.py:76` | 残差片段范围与数值有限；保留。 |
| 58 | `CurveErrorGlobalScore._availability_is_coherent` | `plugins/curve_score/curve_score/analysis.py:100` | 计算结果有值/无值状态配对；保留。 |
| 59 | `CurveErrorAnalysisReport._analyses_are_unique` | `plugins/curve_score/curve_score/analysis.py:156` | 诊断序列/比较实体键唯一；保留。 |
| 60 | `CurveDiagnosticAnalysisPackage._analysis_reproduces_from_exact_inputs` | `plugins/curve_score/curve_score/analysis.py:314` | 在 model_validator 重算输入包，见 F10。 |
| 61 | `HypothesisAssessment._references_are_unique` | `src/scidiscovery/artifact_agent/schema/validation.py:38` | 引用去重见 F02；证伪项强制总判断见 F09。 |
| 62 | `ScientificGateResult._decisive_gate_has_evidence` | `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:28` | 决定性 gate 有证据引用有用；保留，不从六 gate 自动算总 verdict。 |
| 63 | `ObjectiveDiagnosisAssessment._references_are_unique` | `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:83` | 决定性目标判断有证据有用；纯引用去重见 F02。 |
| 64 | `CalculationRecord._bounded_status` | `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:122` | 记录有限大小/时间/状态和 request 摘要；保留。新详情已外置，不强迫复制旧 inline record。 |
| 65 | `AnalysisSourceReference._case_identity_is_paired` | `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:159` | experiment_key 与 case_key 是一对身份，防跨案例误认；保留。 |
| 66 | `LayeredDiagnosisReport._references_and_bounds_are_consistent` | `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:190` | 当前仅证据/计算实体键与实际引用存在/预算，无旧六门总判定公式；保留。 |
| 67 | `ExpectedOutput._case_identity_is_paired` | `plugins/tcad_artifact/tcad_artifact/execution_control.py:105` | 文件的实验/案例身份成对出现；保留。 |
| 68 | `_validate_relative_path` | `plugins/tcad_artifact/tcad_artifact/execution_control.py:26` | 禁止绝对路径与路径穿越；保留。 |
| 69 | `_safe_public_profile_id` | `plugins/tcad_artifact/tcad_artifact/execution_control.py:59` | 公开能力标识防内部敏感路径/控制内容泄露；保留。 |
| 70 | `SolverCapabilitySnapshot._public_launch_name` | `plugins/tcad_artifact/tcad_artifact/execution_control.py:234` | 运行能力声明为公开 launch，而非隐藏路径；保留。 |
| 71 | `_safe_public_release_label` | `plugins/tcad_artifact/tcad_artifact/execution_control.py:48` | 公开 release label 范围；保留。 |
| 72 | `ParameterCondition._numeric_condition_uses_scientific_notation` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:96` | 单位与数值可解析；保留（函数名虽写 scientific_notation，实际此函数只要求有限 Decimal）。 |
| 73 | `ParameterAgreementRule._tolerance_matches_rule` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:108` | exact/容差的数学定义；保留。 |
| 74 | `DeviceParameterRequirement._requirement_is_valid` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:137` | 单位可解析保留；纯 required_condition_names 去重可规范化。 |
| 75 | `DeviceParameterRequirementSet._parameter_keys_are_unique` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:156` | parameter requirement 实体主键唯一；保留。 |
| 76 | `EvidenceSourceCatalogEntry._source_identity_is_consistent` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:185` | URL/来源元数据有用；DOI 派生 work_key 与作者去重属于可机械化细节。 |
| 77 | `EvidenceSourceCatalog._source_keys_are_unique` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:226` | source_catalog 实体主键防歧义；保留。 |
| 78 | `DeviceParameterObservation._observation_is_valid` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:247` | 单位可解析及同一条件不能多值；保留。 |
| 79 | `DeviceParameterTuningSpec._candidate_values_are_numerically_unique` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:266` | 数值候选重复会重复实验，当前保留或在生成案例前规范化。 |
| 80 | `DeviceParameterClaim._claim_is_valid` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:291` | 事实有观测、工程先验标 assumption、bounded candidates 有基线；保留；conflicting_sources 只代表原文离散值不是所有可能设计。 |
| 81 | `DeviceParameterSet._claim_keys_are_unique` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:336` | 参数 claim 实体键唯一；保留。 |
| 82 | `ParameterSourceComparison._agreement_requires_comparability` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:353` | 不可比较时不应给已同意的布尔结论；保留。 |
| 83 | `ParameterUncertaintyItem._classification_has_exact_values` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:400` | 这是控制生成 uncertainty projection，bounded_tunable 必须有基线和候选；保留。 |
| 84 | `ParameterUncertaintyProjection._projection_is_consistent` | `plugins/tcad_artifact/tcad_artifact/device_parameters.py:422` | 控制生成 uncertainty 的状态与明细一致；保留。 |
| 85 | `_safe_relative_path` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:56` | 文件路径安全；保留。 |
| 86 | `_safe_relative_path` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:56` | 文件路径安全（另一注册名）；保留。 |
| 87 | `ParameterBinding._complete_evidence` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:139` | parameter binding 的文件/定位/声明成组有用；镜像字段应控制生成，不能据文字出现证明物理实现。 |
| 88 | `CaseParameterBinding._requirements_are_unique` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:216` | requirement_keys 纯引用去重可由控制生成；真实控制身份保留。 |
| 89 | `ProjectMaterializationReport._status_matches_findings` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:294` | 控制生成 materialization 证明状态与 findings；保留。 |
| 90 | `ProjectPreflightAttestation._qualification_matches_result` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:331` | debug 证明只能表示实际模式和结果；保留。 |
| 91 | `RuntimeAssertion._parser_requirements_are_consistent` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:363` | 明确声明的 runtime assertion 参数可解析；保留；direct-solver author 不负责后处理。 |
| 92 | `RealizationRequirement._implementation_is_explicit` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:408` | implemented 声称需要代码定位，unsupported/missing 可以诚实表达；保留。 |
| 93 | `RealizationRequirement._safe_optional_path` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:403` | 可选实现路径不能逃逸；保留。 |
| 94 | `DeckProjectDraft._consistent_project` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:471` | 真实文件、entrypoint、input/output 不冲突、source digest 和代码控制定位；保留。字符串出现只是实现线索，不替代独立科学审查。 |
| 95 | `_safe_relative_path` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:56` | 文件路径安全（另一注册名）；保留。 |
| 96 | `_safe_optional_relative_path` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:64` | 可选文件路径安全；保留。 |
| 97 | `DeckReviewFinding._safe_optional_path` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:686` | review 指向文件的路径安全；保留。 |
| 98 | `ImplementationGap._attempt_paths` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:708` | gap 保存的尝试路径有界；保留。 |
| 99 | `DeckReviewReport._verdict_matches_review` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:774` | pass 表示可授予实现执行资格时不能同时有 blocker/缺必要输入；保留此资格定义；不要据此强迫科学总体目标全完成。 |
| 100 | `ReviewedDeckPackage._review_qualifies_project` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:822` | 打包只消费确切通过审查的项目与能力；保留。 |
| 101 | `RuntimeAttestation._verdict_matches_checks` | `plugins/tcad_artifact/tcad_artifact/project_packager.py:915` | runtime attestation 对它实际完成的检查聚合；保留，不等于物理真相已证实。 |
| 102 | `RealizationSnapshot._values_are_unambiguous` | `src/scidiscovery/artifact_agent/schema/comparison.py:33` | 同一科学控制不能多个实现值；保留。 |
| 103 | `ControlEquivalenceReport._status_is_derived` | `src/scidiscovery/artifact_agent/schema/comparison.py:85` | 程序比较 intended/frozen 的聚合；保留；physical_claim_evaluable 名称过强且无独立生产消费，列观察项。 |
| 104 | `ExperimentControlEquivalenceReport._snapshot_digests_are_unique` | `src/scidiscovery/artifact_agent/schema/comparison.py:103` | 快照 digest 唯一防混入/重复控制；保留。 |
| 105 | `StudyControlEquivalenceReport._status_is_derived` | `src/scidiscovery/artifact_agent/schema/comparison.py:136` | 程序生成 study control 对比聚合；保留，不作为分析结论公式。 |
| 106 | `ParameterEvidencePackage._family_is_closed` | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py:166` | parameter family 科学来源闭合保留；同一目标多处手抄见 F04。 |
| 107 | `SProcessSeriesSpec._point_bounds_are_ordered` | `plugins/tcad_artifact/tcad_artifact/curve_normalizer.py:43` | 解析器期待点数边界有序；保留。 |
| 108 | `SProcessLogSourceSpec._expected_series_are_unique` | `plugins/tcad_artifact/tcad_artifact/curve_normalizer.py:59` | 日志预期序列身份不能混淆；保留。 |
| 109 | `FigureEvidenceSource._pdf_provenance_is_complete` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:57` | PDF 与已恢复图像的出处字段成组；保留。 |
| 110 | `FigureAxisCalibration._endpoints_define_a_transform` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:79` | 两点定义非退化线性/log 标定；保留。 |
| 111 | `FigureEvidenceSeries._primitive_has_a_compatible_style` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:126` | 点/线/拟合片段风格符合既有 digitizer 能力；保留。 |
| 112 | `FigureOverdrawSupport._ranges_and_members_are_valid` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:151` | 共享遮挡支撑区间和成员明确；保留。 |
| 113 | `FigureCoincidentOverlapSupport._ranges_and_members_are_valid` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:174` | 重合曲线支撑成员/区间明确；保留。 |
| 114 | `FigureEvidencePanel._series_keys_are_unique` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:203` | 面板系列主键、标定、遮挡引用与像素占用防重复计证；保留。 |
| 115 | `FigureEvidenceArtifact._collection_matches_path` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:276` | 确定性产物集合与相对路径一致；保留。 |
| 116 | `FigureEvidenceProvenance._recovery_identity_is_complete` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:291` | 恢复 provenance 与原图出处一致；保留。 |
| 117 | `FigureEvidenceProvenance._artifact_items_are_unique` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:297` | 产物路径身份唯一；保留。 |
| 118 | `FigureEvidenceManifest._manifest_is_internally_consistent` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:319` | 程序生成 manifest 的计数/来源/qualified 身份；保留（unresolved 请求是另一模型）。 |
| 119 | `FigureEvidenceValidationSeries._counts_are_consistent` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:421` | 生成表的有效/共享/检测限行数自洽；保留。 |
| 120 | `FigureEvidenceValidationReport._derived_counts_are_consistent` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_evidence.py:521` | 科学 role 聚合条目唯一，不是禁止多个系列具有相同科学角色；保留。 |
| 121 | `FigureAxisRequest._ticks_define_an_axis` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py:57` | axis tick 定义可计算标定；保留。 |
| 122 | `FigureDigitizationSeries._anchors_are_ordered` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py:100` | trace anchor 有序是 digitizer 当前算法所需；保留。 |
| 123 | `FigureDigitizationRequest._request_is_bounded_and_self_consistent` | `plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py:165` | ready 几何支撑保留；unresolved 禁止保留部分信息见 F08。 |
| 124 | `TCADRuntimeConfig._one_transport` | `plugins/tcad_artifact/tcad_artifact/runtime_plugin.py:56` | runtime config 必须明确一种 transport，属于部署配置而非科学输出；保留。 |
