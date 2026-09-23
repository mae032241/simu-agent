# Fig.4 路线剪枝框架计划 R2 独立审查

- 审查对象：[FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md](../FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md)
- 审查类型：计划级、独立跨边界审查
- 审查基线：`943c4626f8490530e9318eb9fbb409d2670908b9` 及审查时可见的未提交实现/文档；工作树已有大量其他作者的 dirty changes，本审查未整理、还原或归因这些变更
- 审查边界：只新增本报告；未修改 R2、R0/R1、计划索引、Architecture、README 或实现
- Reviewer：GPT-5.6 Sol / xhigh

## 结论

**PASS（计划级）。** 未发现 P1 或 P2 阻断。

R2 没有通过增加 `prune` 枚举、路线身份、第二状态机或硬 admission 来修复调度问题，而是保留 `scidiscovery.layered-diagnosis.v1`，把新增要求收敛为三个新 producer 版本上的一个 exact-scope 条件：scope plan 的 `objective_key` 非空时，当前 Worker 必须提交 `objective_assessment`。随后仍由 scheduler 将封存科学事实、总体目标、任务 scope 和用户投入约束组合成下一动作价值判断。这与 [R5-N](../R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md) 及当前 [Architecture 中文](../../ARCHITECTURE.zh-CN.md) / [英文](../../ARCHITECTURE.md) 的权威边界一致，也不会让 Worker 建议变成控制命令。

计划同时准确保留了重要的非保证：它不能机械保证 scheduler 永远作出最经济选择，不能把当前数值失败自动变成物理反证，也不宣称尚未导出的 Fig.4 原件已经完成科学审计。该边界是正确的职责收敛，不是遗漏。

## Findings

### P1

无。

### P2

无。

## 逐项核查结果

### 1. v1 条件规则覆盖三个真实 producer，且不逼造历史身份

R2 §2、§4、WP1 的 producer/scope 表与当前实现一致：

- generic `science.result.diagnose.v1` 当前 `OperationSpec.version=3`，输出 context 从 exact `experiment_plan` 解析 `ExperimentPortfolio`，经 `_diagnosis_context → validate_analysis_report` 校验；计划升级为 4。
- curve-error `science.result.diagnose.curve-error.v1` 当前版本 1，只有 `curve_analysis_package`/plots；`_curve_diagnosis_context` 实际解析 package，随后把 `package.experiment_plan` 传入 `_validate_diagnosis_against → validate_analysis_report`。因此 R2 指定从 exact package 内 `/experiment_plan` 读取条件是现有可达路径，不需要伪造一个独立 plan port；计划升级为 2。
- TCAD `tcad.result.analyze.v1` 当前版本 1，`analysis_context` 使用 original execution `experiment_plan`，最后调用同一 `validate_analysis_report`；计划升级为 2。回顾性分析计划仍只能作为 `current_progress`，不会替换执行身份。

代码证据见 [curve science operations](../../../plugins/curve_score/curve_score/science_operations.py) 的 `_diagnosis_context`、`_curve_diagnosis_context`、`_validate_diagnosis_against` 与 `validate_analysis_report`，以及 [TCAD result analysis](../../../plugins/tcad_artifact/tcad_artifact/result_analysis.py) 的 `analysis_context`。生产调用点恰为上述三条；其他直接调用是测试，不是隐藏 producer。

`ExperimentPortfolio.objective_key` 当前确实允许 `None`；scientific portfolio 的基础模型只要求非空 selected hypotheses，并不把 key 设为必填。R2 的条件规则仅在 key 非空时要求 assessment，明确允许 engineering plan 和历史 scientific null-key plan 省略它，并禁止 control 从目标文本生成 key。因此历史可读性不会迫使作者制造科学身份。证据见 [experiment schema](../../../src/scidiscovery/artifact_agent/schema/experiment.py) 与 [experiment intent](../../../src/scidiscovery/artifact_agent/schema/experiment_intent.py)。

### 2. 共享 validator 与 semantic resource 的隔离方案机械可实现

当前 `validate_analysis_report` 已由三条生产 context 路径共享；`LayeredDiagnosisReport` payload validator/Schema 还被 prior reader 使用。R2 把“非空 objective key 必须有 assessment”放在新 producer 的 context checker，而不原位收紧 Pydantic v1 reader/`diagnosis_schema`，所以旧 v1 prior 不会被新 writer 规则重验。

R2 也正确识别了一个不直观的 alternate caller：现有 `diagnosis_semantic_contract` 不只服务 diagnosis report，还被 support Transform `science.curve.error.analyze.v1@1` 的 package output、package validator和 plot `nonempty_validator` 间接引用。新增 report 专属静态 resource，并只让两个 curve diagnosis 主输出及 `diagnosis_validator`、`diagnosis_context`、`curve_diagnosis_context` 可达，能把新规则从 package/plot Transform 隔离。TCAD 继续使用自己的 `result_analysis_semantic`。

当前 compiler 只把每个 Operation 的可达 component specs/resource digests 和插件/Operation identity 纳入 digest；新增一个不可达 resource 不会自动污染 Transform。R2 又明确要求编译前后比较 support Transform 的 version/digest/output contract，足以发现引用接错。证据见 [catalog compiler](../../../src/scidiscovery/operations/catalog.py) 的 component/resource resolution 与 digest envelope，以及 [curve component declarations](../../../plugins/curve_score/curve_score/science_operations.py) 的 `component_specs()`。

### 3. 目标、证据和执行身份闭合；invalid study 不被 control 改写为物理结论

现有 `ObjectiveDiagnosisAssessment` 对 `pass/fail` 要求非空 `evidence_keys`；三个 analysis context 最终都递归调用 `validate_evidence_source_aliases`，因此 objective assessment 的 key 必须解析到本 Run 的 bound/tool evidence alias。`validate_analysis_report` 还校验：

- report 的 `experiment_key/plan_key` 在 exact scope portfolio 中唯一匹配；
- `study_kind` 与 scope plan 相同；
- assessment 的 `objective_key` 与 scope plan exact 相同；
- `comparison_keys` 只能来自当前合法 metric report 或已核验 calculation records。

相关证据见 [layered diagnosis schema](../../../src/scidiscovery/artifact_agent/schema/layered_diagnosis.py)、[operation contract evidence validator](../../../src/scidiscovery/operation_contract.py) 与上述三个 context checker。

R2 没有把这些机械身份检查扩大成科学真伪判断。当前 v1 本来允许 `overall_verdict`、`claim_allowed`、optional gates 与 objective status 分别表达不同层次；[claim projection](../../../src/scidiscovery/artifact_agent/schema/claim.py) 只投影原值，[result materialization](../../../src/scidiscovery/artifact_agent/service/result_materialization.py) 只机械映射 handoff verdict。计划明确要求 failed/missing execution 可提交受限的 `not_evaluable`/`inconclusive`，禁止因 `invalid_study` 自动推导物理路线失败，也禁止 control 根据 summary 关键词做门禁。当前无效执行和 exact historical 有限观察可并列读取，但不能由 manifest/replay 自动合成为本次物理资格；这个边界与 R5-N 一致。

### 4. producer/consumer、prior/replay/reference/claim/UI 面完整

源码搜索与声明核对确认，强类型 `scidiscovery.layered-diagnosis.v1` prior 输入只存在于 generic diagnosis 与 TCAD analysis；curve-error producer 没有 prior port。R2 没有新增 v2/双端口，因此 R1 遗漏 consumer 的风险被删除，而不是转移。

R2 仍把真实 alternate consumers 纳入回归面：

- [input validation](../../../src/scidiscovery/operations/input_validation.py) 的 prior report/manifest direct-parent、same-producer 和 source rebinding；
- [analysis artifacts](../../../src/scidiscovery/artifact_agent/service/analysis_artifacts.py) 的 inline/current/historical calculation alias 与 replay；
- [tool evidence](../../../src/scidiscovery/artifact_agent/service/tool_evidence.py) 的旧 report/receipt namespace；
- [TCAD analysis bindings](../../../plugins/tcad_artifact/tcad_artifact/analysis_bindings.py) 的 source/case conditional mapping；
- [reference policy](../../../src/scidiscovery/reference_tools.py) 与 [reference access](../../../src/scidiscovery/artifact_agent/service/reference_access.py) 的 objective/hypothesis/gate evidence 原件读取；
- `result_materialization → run_outputs → SchedulerSignal` 与 claim projection，不新增 route field 或第二真相。

R2 列出的六个命名 `result_analysis` wildcard consumer 与当前 general-science declarations 相符；它也正确说明其他 wildcard `current_progress/reference_material` 只是开放库存能力，不能据此推导 prior replay、自动 continuation 或穷举清单。

UI 方面，当前 [general science views](../../../src/scidiscovery/general_science_views.py) 已展示 summary/verdict/claim/objective/gates/limitations/remaining contradiction；R2 只计划补 `hypothesis_assessments` 与 `next_action` 的原字段投影，并把 [read model](../../../src/scidiscovery/artifact_agent/approval_ui/read_model.py)、presentation/render/workbench、真实 HTTP 与 installed `scidiscovery.instance_views` 全链列为核查面，而不是预授权重写。历史缺 assessment 只显示缺失/未记录，UI 不推导 prune badge，也不改变审批 subject 或科学字节。

### 5. scheduler 职责修复足够且未重建路由权威

当前 [scheduler root prompt](../../../roles/scheduler.md) 已要求每项动作关联总体/当前目标，先说明下一局部工作能改变什么决定，在细节不再影响决定时停止；[research guide](../../../roles/scheduler/research.md) 已明确数值/实现失败不是物理反证、不得把每个结果送回调参；[results guide](../../../roles/scheduler/results.md) 已提供一次 decision read 的八字段路径，并区分 missing/null/omitted/historical。

R2 WP2 的增量只需补清“当前 Run scope、封存事实、边际价值/用户成本”的区分，不要求 scheduler 改写 Worker 科学事实，也不把 `next_action`/handoff hint 当命令。实际下一 Operation 仍只能来自 compiled public catalog，preflight/invoke、独立审查、审批、预算及副作用门完全保留。因而本计划足以修复可证明的职责缺口，同时诚实保留模型行为质量不能由 prompt 或 deterministic fixture 保证的限制。

### 6. Fig.4 WP0 与反迎合边界正确

R2 §3 明确说明本次没有重新访问实例、CAS 或 Run，父调度器提供的名称仅用于导航；转述的任务 scope、报告内容和用户意见不能成为科学证据。WP0 要求从 exact Run/Artifact 导出 sealed payload、任务原文、bindings、manifest、用户原文和父链，保存摘要、Operation identity 与完整性标记；拿不到时只能使用明确标为 synthetic 的通用 fixture，不能冒充 Fig.4 科学证据。

确定性验收只证明表达、绑定、读取、来源保存、可以不调用下一动作和权限边界；真实 Worker 不会被提示“应 prune”，其任何有证据支持的继续、停止或重设计都不决定工程 PASS。真实 scheduler 行为另列受控 replay 与独立审查。这一划分关闭了 R0/R1 指出的迎合风险。

### 7. installed cohort、PluginDefinition 与回滚计划闭合

当前 distribution 版本、PluginDefinition 版本和 Operation 版本确实是三套身份：core `0.1.0`，curve distribution/plugin `0.2.1`，TCAD distribution `0.1.0` 但 plugin `0.2.0`；三个 producer 为 `3/1/1`。R2 分别处理它们，没有把 Python package version 当作 plugin/Operation identity。

计划提出 core/curve/TCAD distribution cohort `0.1.1/0.2.2/0.1.1`，同步 curve/TCAD Python minimum dependency，但保持 PluginDefinition exact versions，避免无关可达组件因 plugin version 扩大退休范围。当前插件 compiler 对 PluginDependency 使用 exact PluginDefinition version，而 Python installer 负责 distribution dependency；两层安排相容。R2 还要求冻结三个 wheel hash、从隔离 site 的真实 entrypoints 编译、走 stdio unified MCP/HTTP，并把 C0/K0/T0、C1/K0/T0、C1/K1/T1 与拒绝组合写清。

回滚恢复整组旧 site/受管指南/配置，不删除新 v1 报告、不回写历史、不恢复旧资格；切换前停止新建并处理仍持有冻结合同的活动 Worker。这与 [installer](../../../deploy/install.sh) 的阶段 site、事务切换和回滚模型相符。版本若已被其他 dirty work 占用，WP0 重新选择未占用 cohort，也避免覆盖同版本包。

### 8. token 与 native telemetry 声明真实且有归属限制

R2 没有把 collaboration token、RSS/耗时或字符数冒充模型 token：

- Root 可由 App Server `thread/tokenUsage/updated` 在请求边界报告原生 usage；
- production compiled Worker 只有在 native trace 能与 `spawn_agent → worker_identity/worker_attach` 的 exact Run/attempt/thread/profile 唯一关联时才可报告；拿不到即记“不可观测”；
- collaboration Planner/Reviewer 当前没有 token usage 接口，不估算；
- 独立 CLI/App Server 代理只能标作代理测量，不能冒充 production Worker。

现有 [native parser](../evidence/mcp-response-levels/probe_request_usage.py) 确实按 `response_id` 去重 `token_usage_record`、只导出元数据，并硬编码要求 `gpt-5.6-sol/medium`；[native usage tests](../../../tests/artifact_agent/test_native_worker_usage.py) 也只覆盖该 profile。R2 因而正确要求 Astra/其他模型先把 expected profile 参数化并从冻结 execution profile 取得，否则测量无效。[legacy compiled worker script](../../../scripts/run_compiled_codex_worker.py) 明确拒绝统一 MCP 角色，计划没有把它误称为 production dispatch。

本 Reviewer 的 token 用量：**不可观测，未估算。**

## 文档所有权与 supersession

Architecture、R5-N、仓库 [AGENTS.md](../../../AGENTS.md) 和 scheduler prompt/guides 仍是当前规范；R2 是活动提案，不提前把未来条件写成已部署事实。R0/R1 及其 review 是历史问题与被拒方案的证据，不应被改写。R2 已要求审查通过后才更新计划索引，并只部分修订 Architecture 中“额外 assessment 均可省略”的现行表述；历史可读、建议非权威、gate 可选等规则继续由现有规范拥有。这个处置符合 decision-corpus 的当前规范/活动提案/历史审查分工。

## 核查路径与残余风险

实际核查了：

- R2 全文、R0/R1 两份审查、R5-N、双语 Architecture、根与仓库 AGENTS；
- 三个 producer 的声明、输入/输出、版本、context validator 和共享 helper 全部 production 调用点；
- layered diagnosis/objective/evidence consistency 与 exact plan/package/TCAD execution identity；
- prior manifest、calculation replay、reference、claim、handoff/signal 和历史 output read；
- general-science provider、read model、presentation/render/workbench/HTTP 与 installed instance-view entrypoint；
- core/curve/TCAD pyproject、PluginDefinition/dependencies、catalog reachable-resource digest、installer transaction/rollback；
- Root App Server usage probe、native trace parser/tests、compiled Worker attachment边界与 legacy probe 限制。

本次是计划审查，以下风险按 R2 自身要求留待实施/验收，不改变 PASS：

1. Fig.4 exact sealed originals 尚未导出；在 WP0 完成前，历史归因和 Fig.4-specific fixture 都不能称为科学审计证据。
2. source import/compile 不等于 installed/live cohort；三个真实提交路径、prior/replay、三类 UI 入口、entrypoint 和回滚必须由实施证据闭合。
3. 条件 assessment 能强制“交代目标”，不能保证交代质量；真实 Worker 与 scheduler 的非迎合行为仍需独立行为审查，且结果不预设必须停止。
4. scientific null-key 历史计划继续没有结构化 objective assessment；这是明确保留的兼容限制，不能在本轮通过生成 key 隐式修复。
5. token A/B 只有在 exact thread/profile/input/tool/请求边界可归属时有效；缺 trace、混合 profile、聚合 token_count 或不同比较范围都必须报告不可比/不可观测。

这些均已在 R2 §7–§10 被列为未完成证据或验收条件，没有被用来提前宣称实现、部署或科学资格 PASS。
