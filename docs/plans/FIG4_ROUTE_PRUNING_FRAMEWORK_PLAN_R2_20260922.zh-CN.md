# Fig.4 路线剪枝框架计划 R2

状态：**[Sol R2 独立审查 PASS（计划级）](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_SOL_REVIEW_20260922.zh-CN.md)；[WP0—WP3 本地工程候选已实施](evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md)。多轮实现审查最终由[R3 GPT-6 独立复审 REVISE](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R3_20260922.zh-CN.md)定位 `preserve-sqlite` 的三个 P2；用户否决继续兼容 state 嵌入回滚树，[结构性分离修复候选](evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R3_STATE_ROOT_SEPARATION_ROOT_20260922.zh-CN.md)已删除该机制并在生产安装前拒绝 state root 与所有受管树重叠，待独立复审。未部署、未启动 Fig.4 科研 Run，计划列明的 live/科学/token 证据仍待完成。**

本文件独立核对当前工作树与规范，只提出后续实现方案，不改写 R0/R1 或历史审查。代码基线为 `943c4626f8490530e9318eb9fbb409d2670908b9` 及 2026-09-22 已存在的未提交修改；实际事实以本文引用的当前文件为准。

## R0/R1 问题处置矩阵

本次核查完整阅读 [R0](FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_20260922.zh-CN.md)、[R0 审查](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R0_REVIEW_20260922.zh-CN.md)、[R1](FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R1_20260922.zh-CN.md) 和已完成的 [R1 审查](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R1_REVIEW_20260922.zh-CN.md)。审查意见是问题线索，不是机制选择的依据；下表是 R2 的独立设计处置，不宣称问题已经在实现中关闭。

| 问题 | 独立核查与 R2 处置 | 验收落点 |
|---|---|---|
| R0 P1-1：Worker `prune` 获得硬路由权 | R5-N 明确科学建议无准入权。保留 R1 删除硬门的结论，并进一步删除 `prune/required_change` 持久枚举；scheduler 自己决定暂不继续某项工作。（E1、E4） | 建议或总体 verdict 的变化不能引入新的 Operation allow/deny；原审查、审批门继续生效。 |
| R0 P1-2：跨计划路线身份无唯一 owner | 不实现 branch/strategy key、route fingerprint、改名放行、新证据重开机制。当前报告只针对现有 Run 的精确计划或 package；跨实验综合仍由科学 Agent 判断。（E2、E5） | 同 key 不同 Artifact 不混同；不产生路线索引或第二生命周期。 |
| R0 P1-3、R1 P1-3：v2 及 prior 双读扩散 | **不采用 v2**。v1 已有目标评估、逐假设 assessment、限制和矛盾。只加强三个新版本 producer 的一个输入条件约束，保持共享 reader、端口和历史字节不变。（E2、E6） | 缺目标评估的旧 v1 仍可读、可按原合同作 prior；新输出的条件规则可见且被验证。 |
| R1 P1-1：统一 stop pointer 无统一 plan input | 独立确认 curve-error 只有 package/plots 及通用 user_context；其 plan 在 package 内。三个 producer 均无直接 `research_objective` 端口。删除新 stop pointer；按各自实际 scope 读取原有停止条件。（E5） | 三条 producer 路径各有 scope fixture，不新增伪端口，不猜 objective Artifact。 |
| R1 P1-2：prior-v2 有效性例外遗漏 scope 与递归证据 | 删除此例外及 `validity_scope`。历史计算复用沿既有 manifest/receipt 路径；引用旧结论不自动成为本次物理结论，不恢复资格。（E6、E7） | 无效执行与历史有效观察可并列阅读，control 不计算跨研究科学有效性。 |
| R0 P2：无效研究被当成物理失败 | 不以 `invalid_study` 或 gate enum 自动导出“物理路线失败/必须数值修复”。Worker 说明实际证据界限，scheduler 可以因用户成本约束停止调查，同时保留机制未判定。（E1、E2、E5） | 数值失败不产生机制反证；有效历史反证不因当前失败被抹去；两者不合成为自动资格。 |
| R0/R1 UI 与包组合遗漏 | 现有 provider 已展示目标评估，R2 仅补有用的原字段展示并检查三入口。完整核查 core/curve-score/TCAD wheel、PluginDefinition 和安装投影；采用一个精确发布 cohort。（E8、E9） | installed entrypoints、真实 HTTP、旧结果展示与整组回滚。 |
| Fig.4 迎合验收 | 确定性夹具验证表达、绑定、读取、权限及“不调用下一动作”的可行性，不给真实 Worker 预置剪枝答案。模型是否作出有价值选择另列行为证据。 | §7 明确工程 PASS 的能力边界。 |
| token telemetry | Root 原生事件和生产 Worker 原生 trace 均有条件可观测；collaboration 工具本身不提供 token。现有 native parser 锁定 Sol/medium，不能直接验证其他模型。（E10） | §9 分来源报告，不用代理替代生产，不估算不可观测值。 |

对 R1 审查文字作一处精确澄清：`analysis_artifacts.py` 实际直接导入的是 v1 模块中的 **`CalculationRecord`**，不是 `LayeredDiagnosisReport`；完整 report 的旧类型解析在 `tool_evidence.py`。遗漏 `analysis_artifacts.py` 与 TCAD `analysis_bindings.py` 这两条消费者仍是成立的问题。R2 保留审查原件，不修改其历史表述。（E6）

## 首选方案 vs 被拒方案

**首选：v1 科学报告 + 一个有条件的目标评估提交规则 + scheduler 的明确价值判断。** 科学 Agent 报告“已观察到什么、当前目标达到什么程度、哪些解释被支持或削弱、仍不知道什么”；scheduler 结合这些封存事实、总体目标和用户约束决定下一项工作值不值得做。停止安排同一路径不需要证明该机制为假，也不需要新建“已剪枝”状态。（E1、E2）

| 候选 | R2 选择与理由 |
|---|---|
| 仅更新 scheduler/Worker 提示 | 必须做，但单独不够：当前有目标 key 的新分析仍可合法完全省略目标评估。增加已有字段的输入条件约束，使该缺项有明确诊断。 |
| v1 全局收紧或新 writer Schema 无条件必填目标评估 | 拒绝。`ExperimentPortfolio.objective_key` 可以为 null，历史 scientific 计划也未由基础 reader 强制非空；无条件必填会逼造身份。全局收紧还会破坏历史读取及 prior 端口。（E2、E3） |
| v1 不变，三个 producer 的 context 合同要求：scope plan 的 objective_key 非空时必须有 objective_assessment | **采用。** 是可机械验证的输入条件，已有 `validate_analysis_report` 被三条真实输出路径共用。JSON Schema 无法单独表示“精确输入字段非空”的条件，故应公开在现有 context semantic contract，而非藏进 reader。（E3、E5、E11） |
| `layered-diagnosis.v2 + continuation_assessment` | 拒绝。现有字段足以提供科学事实；新增的“值得/剪枝/所需变化”主要是对下一步工作的价值选择，会复制 scheduler 的判断。当前任务没有足以支付全链 reader/manifest/包迁移的需求。 |
| Worker 持久输出 route disposition，但不设硬门 | 本轮也不采用。即使无控制权，仍会混淆测试假设结论、成本判断与用户意愿，并诱发按 enum 选路。Worker 可在既有 `next_action` 提建议，缺失或不采纳都不阻断提交。 |
| stop pointer、prior-v2 继承有效性例外 | 拒绝。没有需执行停止条件的机器消费者；现有原计划文本及 exact 引用已足够供人和 scheduler 阅读。历史有效结论与当前执行有效性各自保留，不新增跨研究证明协议。 |
| 全局 continuation guard、路线 fingerprint、永久墓碑、自动重开 | 拒绝。会增加路线同一性和权限语义，违反本轮最小范围；本轮没有业务需求要求 control 阻止一个科学上不划算的动作。 |

R2 的代价是：它不能保证模型永远选择最经济的下一步，也不能机械阻止用户或 scheduler 再次尝试。若真正需要全局硬预算或永久禁止某项执行，应另由已有预算/权限 owner 设计；不能把这项需求伪装成分析报告字段。

## 当前合同与权威证据

### 1. 证据索引与文档 owner

以下路径均相对仓库根。行号只作本次工作树定位；实施前冻结 exact 文件摘要和编译摘要。

| 编号 | 当前文件/合同证据 | 本次可确认事实 |
|---|---|---|
| E1 | [Architecture 中文](../ARCHITECTURE.zh-CN.md) §1–4、§9；[英文](../ARCHITECTURE.md)；[R5-N](R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md)；[scheduler](../../roles/scheduler.md)、[research](../../roles/scheduler/research.md)、[results](../../roles/scheduler/results.md) | Worker 科学结果与 scheduler 行动权分离；compiled catalog 唯一行动权威；已有指南要求将总体目标、矛盾与局部任务关联，并允许停止。 |
| E2 | [layered_diagnosis.py](../../src/scidiscovery/artifact_agent/schema/layered_diagnosis.py) L17–87、163–213；[validation.py](../../src/scidiscovery/artifact_agent/schema/validation.py) L16–43 | 目标、gate、逐假设结论已存在。`gates/objective_assessment/remaining_contradiction/next_action` 可省略；目标 pass/fail 须有 evidence_keys；基础 consistency 不判定科学真伪。 |
| E3 | [experiment.py](../../src/scidiscovery/artifact_agent/schema/experiment.py) L203–244、387–429；[experiment_intent.py](../../src/scidiscovery/artifact_agent/schema/experiment_intent.py) L45–63、165–188 | 停止条件已有文本 owner；plan 的 objective_key 可为 null。科学骨架、设计意图和计划已有当前目标、限制、价值理由，不需新建路线身份。 |
| E4 | [role_result.py](../../src/scidiscovery/artifact_agent/schema/role_result.py)、[run_signal.py](../../src/scidiscovery/artifact_agent/schema/run_signal.py)；[result_materialization.py](../../src/scidiscovery/artifact_agent/service/result_materialization.py) L46–56；[run_outputs.py](../../src/scidiscovery/artifact_agent/service/run_outputs.py) L261–270；[claim.py](../../src/scidiscovery/artifact_agent/schema/claim.py) | finalizer 机械映射 verdict，并给出正文位置；signal 复制 handoff，不包含目标处置。claim projection 不根据目标 fail 改写科学 verdict。 |
| E5 | [science_operations.py](../../plugins/curve_score/curve_score/science_operations.py) L275–387、579–715、782–839；[result_analysis.py](../../plugins/tcad_artifact/tcad_artifact/result_analysis.py) L355–381、453–548、584–645；[analysis_workspace.py](../../plugins/curve_score/curve_score/analysis_workspace.py) L26–35、109–127 | 三个 producer 的真实输入、scope 与共用输出 validator；工作区明确额外 assessment 可选，且已有计划停止条件的原文导航。 |
| E6 | [input_validation.py](../../src/scidiscovery/operations/input_validation.py) L148–211；[analysis_artifacts.py](../../src/scidiscovery/artifact_agent/service/analysis_artifacts.py) L56–99、135–197；[tool_evidence.py](../../src/scidiscovery/artifact_agent/service/tool_evidence.py) L80–145；[analysis_bindings.py](../../plugins/tcad_artifact/tcad_artifact/analysis_bindings.py) L19–89 | prior pair、source rebinding、计算收据及 TCAD 条件案例映射各有真实消费者；不能只搜索 report 类名找迁移面。 |
| E7 | [reference_tools.py](../../src/scidiscovery/reference_tools.py) `ReferencePolicy`；[reference_access.py](../../src/scidiscovery/artifact_agent/service/reference_access.py) `_reference_edges`；[general_science_agent_operations.py](../../src/scidiscovery/general_science_agent_operations.py) `_HYPOTHESIS_FEEDBACK`；[general_science_experiment_operations.py](../../src/scidiscovery/general_science_experiment_operations.py) `_FEEDBACK_INPUTS` | v1 的 objective/hypothesis/gate evidence 已有 exact 原件访问规则；六个命名下游通过 wildcard inventory 接受 sealed analysis。 |
| E8 | [general_science_views.py](../../src/scidiscovery/general_science_views.py) `_ROOTS`；[read_model.py](../../src/scidiscovery/artifact_agent/approval_ui/read_model.py) L228–265、306–325、395–405；[presentation.py](../../src/scidiscovery/artifact_agent/approval_ui/presentation.py)、[presentation_render.py](../../src/scidiscovery/artifact_agent/approval_ui/presentation_render.py)、[workbench_render.py](../../src/scidiscovery/artifact_agent/approval_ui/workbench_render.py)、[render.py](../../src/scidiscovery/artifact_agent/approval_ui/render.py)、[app.py](../../src/scidiscovery/artifact_agent/approval_ui/app.py) L507–622 | 原有目标评估与分层结论已经展示；Run、Artifact、Approval 沿真实 provider/HTTP 链消费同一科学原件；不需要新四轴 UI 数据模型。 |
| E9 | [core pyproject](../../pyproject.toml)、[curve-score pyproject](../../plugins/curve_score/pyproject.toml)、[TCAD pyproject](../../plugins/tcad_artifact/pyproject.toml)；[catalog.py](../../src/scidiscovery/operations/catalog.py) L745–810、845；[install.sh](../../deploy/install.sh) L510–602、1213；[scheduler_prompt.py](../../src/scidiscovery/platforms/scheduler_prompt.py)、[codex.py](../../src/scidiscovery/platforms/codex.py) | Python distribution、PluginDefinition.version 与 Operation.version 是不同身份；实际入口来自 entrypoints；安装以阶段 site 构建并可整组回滚；guides 随 wheel 生成。 |
| E10 | [probe_request_usage.py](evidence/mcp-response-levels/probe_request_usage.py) `RequestMeter`、`native_trace_metrics`；[native usage tests](../../tests/artifact_agent/test_native_worker_usage.py)；[compiled worker probe](../../scripts/run_compiled_codex_worker.py) L1–5、149–152；[local_process_observation.py](../../src/scidiscovery/artifact_agent/service/local_process_observation.py) | Root 有原生逐请求 usage 探针；native trace 可解析 response_id 去重的 token_usage_record；旧 CLI probe 非生产派发且拒绝统一入口角色；进程 RSS/时间不是模型 token。 |
| E11 | [operation_declaration.py](../../src/scidiscovery/operation_declaration.py) L159–213；[invoke.py](../../src/scidiscovery/operations/invoke.py) L134–244；[mcp_root_operation_routes.py](../../src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py) L188–242；[mcp_root_run_routes.py](../../src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py) L128–198、283–300 | 通用注入 user_context/reference 能力；preflight/invoke 共用准备与 input validation；completed decision read 已支持按正文 pointer 读取并同时返回 signal。 |

文档所有权：Architecture、R5-N 与仓库 `AGENTS.md` 保持当前规范；R0/R1 与两份审查保留原角色和原文，R2 不自动取代它们，也不修改索引。实施获审后，Architecture 中“所有额外 assessment 均可省略”的段落需**部分修订**为 §4 的新生产条件；历史可读、gate 可选、建议非权威等规则继续保留。规则唯一实施 owner 是三个 Operation 的声明/共同 context validator，指南说明如何使用，UI 只展示。不得把本提案中的未来规则提前写成已上线事实。

### 2. 精确 producer/consumer 清单

本次只读导入实际 Operation 对象并编译 `builtin + general_science + curve_score + tcad_artifact` 成功；这证明当前源声明可组合，**不证明安装态、runtime availability 或实例资格**。下面版本为 `OperationSpec.version`，不是 ID 的 `.v1` 后缀。

| Producer（当前 → 提案版本） | 必需科学输入与 scope owner | 相关可选输入 | R2 的具体约束 |
|---|---|---|---|
| `science.result.diagnose.v1`，`3 → 4` | `experiment_plan`、`experiment_review`、`experiment_results`。scope 是 exact plan Artifact 中与报告 experiment_key/plan_key 匹配的唯一 validation plan；结果须有该 plan 的直接父链。 | reference_material、current_progress、prior_analysis、prior_analysis_manifest、metric_report、curve_bundle、user_context。 | 使用这个 `ExperimentPortfolio.objective_key` 判断是否要求目标 assessment；沿现有 metric comparison/alias 校验。 |
| `science.result.diagnose.curve-error.v1`，`1 → 2` | `curve_analysis_package`。scope 是 exact package 的 `/experiment_plan` 子树及 curve_contract 的 experiment_key；**没有独立 plan/review/prior/objective 端口**。 | curve_analysis_plots、user_context。 | 从 package 内既有 portfolio 校验同一条件。保留“不能作者新 calculation_records”约束，不新增 prior/replay 端口。 |
| `tcad.result.analyze.v1`，`1 → 2` | `experiment_plan`、`reviewed_package`、`runtime_manifest`。scope 是包对应的原执行计划；现代 skeleton 分支条件必需 scientific_skeleton + execution_review，legacy 分支条件必需 experiment_review。 | execution_result、recovery_manifest、prior_analysis、prior_analysis_manifest、runtime_attestation、solver_outputs、diagnostics、reference_material、current_progress、user_context。 | 按原执行 portfolio 校验；回顾性分析计划仍放 current_progress，不替换执行身份。失败/缺产物仍可给受限分析。 |

三者均输出 `layered_diagnosis: scidiscovery.layered-diagnosis.v1`，并有 `recovery_manifest_output: scidiscovery.tool-evidence-manifest.v1`；其中 curve-error 的 manifest 来自通用 `with_reference_access` 注入。generic/TCAD 还声明 tool_evidence。三者都没有直接 `research_objective` 输入；总体目标只能由 scheduler 沿精确父链恢复，再按选定行动的实际端口传递。不能将 payload 的 objective_key 等同于已经绑定一个完整 objective Artifact。（E5、E11）

下游 Operation：

- typed prior consumer 仅 `science.result.diagnose.v1@3` 与 `tcad.result.analyze.v1@1`，现有 `prior_analysis` 精确接受 v1。提案升级后名称、schema、manifest 配对规则均不变。
- 命名 `result_analysis` inventory consumer 是 `science.hypothesis.propose.v1@1`、`science.hypothesis.criticize.v1@1`、`science.hypothesis.revise.v1@1`、`science.experiment.design.v1@1`、`science.object.review.v1@1`、`science.experiment.skeleton.v1@1`。它们的 `result_analysis` 是 `*`、`on_demand/evidence_inventory`，本轮不改合同。
- 其他允许 wildcard `current_progress/reference_material` 的 Operation 可以接收这种 Artifact 作为库存；它们不是新 route assessment 消费者，不能由此推断需要独立 review、具备 prior replay 或可自动继续。目录中的 wildcard 是开放能力，以上“命名消费者”清单不宣称穷举所有可能绑定。（E7）

非 Operation 消费路径也必须列入回归面：

| 路径 | 现状/本轮处置 |
|---|---|
| `analysis_workspace._excerpts/_start_file`、TCAD `analysis_bindings.source_bindings/workspace_sources` | v1 摘录、原文指针、old→current alias/案例条件映射；不改历史 schema，工作区 guidance 只同步新生产条件。 |
| `input_validation.prior_analysis_sources` | 验证 direct parent/same producer/manifest 输出端口；现代 source_bindings 来自 bindings，只有 legacy 无 bindings 时才从 records 补来源。保持原用途，不把它扩成科学有效性证明。 |
| `analysis_artifacts.calculation_reference_aliases/analysis_calculations` | 接受 inline、当前/历史已保存计算引用，单独消费 manifest.records/recovery；历史 calculation 的来源重绑规则不变。 |
| `tool_evidence.calculation_sources` | 解析旧 report、重建计算 namespace 与收据核验；仍使用 v1 reader，不能调用新输出规则重验历史报告。 |
| `reference_tools.ReferencePolicy`、`reference_access._reference_edges` | exact objective/hypothesis/gate/evidence 引用解析保持不变，普通历史读取不续资格。 |
| `result_materialization → run_outputs → SchedulerSignal`、`claim.project_claim_decision` | 不添加字段，不修改 verdict/claim 规则，不从目标 fail 推导科学 fail 或下一 Operation。 |
| Root `run_status`、general_science provider、Approval/Workbench 三入口 | 直接读取已完成正文；显示原状态、缺失与来源。既有 schema-specific v1 分支无需双读迁移。 |

### 3. Fig.4 为何没有剪枝：能证明什么

本次**没有**重新访问实例、读取 CAS 或启动研究 Run。父调度器给出的下列名称只用于导航；对应 run_status 原 JSON 和任务原文没有仓库副本，本提案没有独立复核其封存字节：

- `fig4_deployed_acceptance_plot_20260922_r2` / 同名 `.output`；上游 `fig4_retardation_frozen_metrics_20260921_1.output`。
- 用户原文 `fig4_user_route_failure_judgment_20260922_1`、`fig4_user_route_pruning_20260922_1`、`fig4_user_gap_too_large_20260922_1`。

现场转述称：最新 Run 只用冻结 M0 轨迹绘制叠加/残差 PNG，禁止 refit、新 solver、新证据，并要求保留原结论；报告为 inconclusive、claim_allowed=false，objective_assessment 缺失，同时保留执行失败、未做收敛与无稳健参数区等限制。此处不把转述的拟合数值重印成科学证据。WP0 必须导出上述 exact 原件和绑定，才能声称完成 Fig.4 历史归因或构造其回归夹具。

| 因素 | 当前可下的判断 | 不能据此断言 |
|---|---|---|
| 任务 scope | **现场导航信息，待原件复核**：若是纯绘图并冻结原结论，Worker 未重新裁决路线符合任务范围。不能以该 Run 没有推翻结论证明框架不能剪枝。 | 图链验收成功等于研究成功；要求不改结论后又以未改判作为 Worker 失败。 |
| Schema/生产合同 | **代码已证实**：v1 已能分别表达目标失败与总体 inconclusive，但新生产可以省略目标评估。缺的是条件性完整交代目标，不是必须新增 prune enum。 | 当前误差必然触发物理否定；字段存在就能保证判断质量。 |
| scheduler 指南/读取 | **当前代码已证实**：research 已禁止把每个结果送去调参，results 已有读取 objective/hypothesis 的示例，AGENTS 已要求动作价值。应核验当时安装版本和实际读取；不能把现有修复后文字追溯成历史已执行。 | 没有任何停止指南；只要再复制一句提示即可保证停止。 |
| 总体目标/停止条件 | **代码已证实已有承载位置；现场内容未复核**：plan/skeleton 有文本停止条件，缺的是是否与总体目标、实际任务和用户成本约束一起使用。需要读取 exact 条件，不能从缺一个 enum 推定未注册停止规则。 | 创造 Fig.4 通用阈值、把当前用户意见追溯成原实验停止判据。 |
| 科学不确定性与调度价值混同 | **框架判断**：未严格证伪不推出值得继续；数值有效性未闭合不推出必须花钱闭合。若修复也不会改变当前决策，scheduler 可以停下，保留科学未知。（E1） | 停止就等于物理机制已失败；用户不想继续可写成反证。 |

因而当前最有力的解释是一个待 exact 原件核证的组合：**局部绘图任务没有获得路线裁决 scope，目标评估可以省略，scheduler 没有把已有受限结论与用户价值约束合成明确的下一步决策。** 不能给四项贡献编造百分比，也不能把 R2 的实施当作 Fig.4 科学结论已经改变。

## 最小框架与实施工作包

### 4. 唯一 owner、持久边界与最小科学合同

| 问题 | 唯一内容 owner | 数据源与既有承载 | 是否新增持久 Schema |
|---|---|---|---|
| 本次科学结论与可声明范围 | 当前 Analysis Worker | exact 计划/结果/证据；`summary/overall_verdict/claim_allowed/limitations` | 否。沿用 v1；control 不从阈值或 gate 重新计算科学结论。 |
| 本次目标达成度 | 当前 Analysis Worker；总体目标内容仍归原目标作者 | scope portfolio 的 objective_key、当前 objectives、已完成观测；`objective_assessment` | 否。仅增加下面的输入条件规则；不把一次局部 pass 当作所有总体目标完成。 |
| tested-hypothesis disposition | 当前 Analysis Worker；新假设集合归 hypothesis 作者并由独立 critic 审查 | `hypothesis_assessments` 的 supports/contradicts/inconclusive/invalid_study/not_tested、证据与 rationale | 否。它评估已测试假设，不代表永久剪枝，不授权修改假设集合。 |
| 下一项工作的价值与选择 | Scheduler | 上述 sealed result + 原总体目标 + 当前任务 scope + 用户约束；判断“新增信息能改变什么决定” | 否。保留有界决策说明和实际调用记录，不建立科学 Artifact、route state 或可执行 enum。 |
| 用户目标、成本容忍度、偏好与停止意愿 | 用户 | 已有原文 Artifact、来源标签和 `user_context`；数值预算仍按现有授权/Run budget 执行 | 否。用户的“差得太远/不值得”影响工作优先级，不自动写成物理反证或审批。 |
| 原计划的判据与停止条件 | 对应 plan/skeleton 科学作者及其现有审查路径 | `stop_conditions`、判据、current objectives；exact 原件及原字段 | 否。后见之明不改写预注册条件；需要改科学任务时新建正式对象并重新审查。 |

**新生产的唯一新增提交约束**，由三个新版本 producer 的现有 context checker 共用：

```text
scope = generic/TCAD 的 exact experiment_plan，或 curve-error exact package.experiment_plan
先按既有规则核验 report.experiment_key / plan_key / study_kind
若 scope.objective_key 非 null：report.objective_assessment 必须非 null
若存在 assessment：其 objective_key 必须等于 scope.objective_key（既有规则）
assessment 的类型、status、pass/fail 证据及 comparison 引用沿用既有规则
```

这个条件是对 exact 输入身份的机械检查，不是“目标应通过/失败”的判定。`not_evaluable` 和 `inconclusive` 都是合法答案；其 summary 由 Worker 说明证据或任务范围限制。对于无 objective_key 的历史/工程计划，允许 assessment 缺失，Worker 在现有 summary/limitations 中交代目标范围；禁止发明 key，禁止 control 从目标文本 hash 出一个科学身份。不得另加 summary 关键词/模板校验。（E2、E3、E5）

保持 v1 Pydantic reader、共享 `diagnosis_schema` 和已有 `PrecomputedDiagnosisReport` 不变。尤其不能把 `diagnosis_schema` 原位收紧：它同时用于 prior 输入。条件应在 `science_operations.validate_analysis_report` 一处实现，generic、package 和 TCAD 的既有调用自然共享；report 专属 semantic contract 与 TCAD contract 公开相同规则，分别说明 scope 的真实来源。诊断定位 `$.payload.objective_assessment`，保持现有 `curve.diagnosis.input_binding` / `tcad.result_analysis.context_binding` 规则归属。（E5、E11）

还需一个窄的声明隔离：现有 `diagnosis_semantic_contract` 同时被 support Transform `science.curve.error.analyze.v1@1` 的 package/plot 输出和其 validator 引用（`science_operations.py` L939–1014、1050–1077、1123–1129）。不能把新 report 条件原位加给它。新增同文件内的 `diagnosis_report_semantic_contract` resource，仅供两个 diagnosis 主输出及 `diagnosis_validator/diagnosis_context/curve_diagnosis_context` 引用；保留旧 resource、package/nonempty validator 的引用。它仍是现有 ComponentSpec 声明的一项静态文本资源，不是新 Schema、全局规则表或路由器；TCAD 使用自身 `result_analysis_semantic`。编译对比须证明该 support Transform 的 version/digest 和其输出合同不因新 report 条件漂移。

`gates` 保持可选，避免把有限分析强迫展开成六层表格；缺失不代表 pass。`hypothesis_assessments` 按实际科学任务需要填写，不强迫绘图/实现分析评价全部假设；只有输入可支持时才声明 predictions/falsifiers。`remaining_contradiction` 与 `next_action` 继续可选。特别是 `next_action/recommended_task_mode/handoff.next_actions` 不得成为 required 内容门、路由枚举或提交成败原因；这延续 R5-N，不引入方向相反的“建议完整性”要求。（E1、E2、E5）

纯绘图/部署验收任务不因新字段获得重新拟合、求解或裁决科学机制的授权。若确切 prior 已评估同 scope 目标，可在现有字段引用其封存判断并说明本次未新增分析；否则给出 `not_evaluable` 及任务范围限制。这个科学选择由 Worker 作出，control 不自动复制旧判断，不检查“是否足够同路线”。若任务无需新科学报告，scheduler 应首先复用已有结果或选择现有合适工具；本轮不为绘图另建一个 Operation。

### 5. Scheduler 如何剪枝，以及 control 不做什么

“剪枝”在本提案中只表示 **scheduler 明确选择不再安排当前局部工作**。它不改变历史科学内容、qualification、Run state，也不永久删除一个科学假设。

1. 先确认当前要改变的决定：例如总体目标能否达到、某机制能否区分，或某项数值有效性是否会影响当前结论。检查刚完成 Run 的实际 scope；plot-only 任务不能承担新路线裁决。
2. 在同一个 completed `run_status(response_profile="decision")` 中读取结论及 signal。沿用现有八字段选择：`/summary`、`/overall_verdict`、`/claim_allowed`、`/objective_assessment`、`/hypothesis_assessments`、`/limitations`、`/remaining_contradiction`、`/next_action`。不增加固定全报告读取；有具体有效性疑问时再定向读 gates/证据。missing/null/omitted/historical 分别处理，不把摘要当全文。（E11）
3. 对当前候选工作写一句可审查的理由：**“它可能产生的哪种结果，会如何改变当前决定，并为何符合用户投入约束。”** 依据必须来自已绑定原件；scheduler 可以判断边际价值，但不能替 Worker 填科学 verdict、编造预计改善幅度或某个缺失参数。
4. 若已有结果足够作当前决定，停止细分和重复检查，带着限制报告结果。若需要新科学设计，用目录中实际可用的 public Operation，并绑定原目标、相关结果/analysis 和用户原文。Worker 建议的动作名不充当命令；依赖关系不是必须依次执行的流程。（E1、E7）
5. 若继续仅能减小一个不影响当前选择的局部误差，可以停止，**即使总体 verdict 仍为 inconclusive、甚至执行仍无效**。若数值修复可能改变当前选择且用户允许投入，才选择有界数值工作；不存在 invalid_study 必须修复的规则。

决策理由保存在现有 orchestration 记录、面向用户的说明以及实际下一 Run 的 instruction/绑定中；没有下一动作时无需制造“stop Run”。后续 scheduler 从确切总体目标、原文约束、sealed 报告和真实活动恢复上下文，不能把前一线程的摘要或子 Agent 聊天重新登记成科学事实。改变用户预算/方向需使用原用户指令，不从科学报告推导。（E1、E11）

control 可以验证类型、显式条件、精确 key/Artifact/父链、引用 alias、manifest 配对、计算收据、合同/Run 身份、预算、独立审查与人工决定；**不能**验证“这个误差大不大”“局部改进是否值得”“两个模型是不是同一路线”“历史反证是否仍适用”。例如“只凭不收敛声称机制失败”是科学审查问题，不能伪装成一个 deterministic validator 能识别的字符串负例。

### 6. 最小工作包与精确文件面

仅规划；本次不执行这些实现/部署动作，不启动研究 Run、不重跑 TCAD、不授予审批。WP 顺序是实现依赖，不是科研工作流。

**WP0：冻结可证基线与验收题。** 从本提案记录的 exact Run/Artifact 名导出封存 payload、任务原文、绑定、manifest、用户原文及父链，保存字节摘要、Operation identity 和完整性标记。若暂时拿不到原件，先完成明确标为 synthetic 的通用夹具；不得把它改名成 Fig.4 科学证据。保留当前工作树差异快照，不把 HEAD 单独当 baseline。冻结三个 producer 的 version/digest/完整端口与 output contract、reader resource 摘要、core/插件 wheel hash、模型/effort/工具权限、安装指南 hash。审查关注点是 §4 条件是否确实解决可证明缺项，不是证明 Fig.4 必须 prune。

**WP1：科学报告条件与 Worker 说明。** 实现面限于：

- [science_operations.py](../../plugins/curve_score/curve_score/science_operations.py)：共同 `validate_analysis_report` 条件；generic/curve-error 版本 `4/2`；§4 的 report 专属 semantic resource 及精确引用；generic 与 curve-error 的 role/semantic 提示准确说明 scope。普通建议继续可省略。
- [result_analysis.py](../../plugins/tcad_artifact/tcad_artifact/result_analysis.py)：版本 `2`、TCAD prompt/semantic contract；继续调用共同 helper，不复制判定算法。
- [analysis_workspace.py](../../plugins/curve_score/curve_score/analysis_workspace.py)：`REPORT_GUIDANCE` 从“目标 assessment 一概可选”改为上述条件，不扩大 excerpts、表格或手工 handoff。
- 对应 [analysis handoff tests](../../tests/operations/test_analysis_handoff_report.py)、[curve boundary tests](../../tests/operations/test_m2_curve_analysis_boundary.py)、[TCAD analysis tests](../../tests/operations/test_tcad_result_analysis.py)、[result analysis tool tests](../../tests/operations/test_result_analysis_tool.py) 与 [contract alignment tests](../../tests/operations/test_agent_contract_alignment.py)。只修正有真实契约影响的 fixture，不批量伪造 objective key。

明确不修改 `schema/layered_diagnosis.py`、`role_result.py`、`run_signal.py`、hypothesis/plan identity schema、prior ports、manifest schema、input_validation、receipt replay 或新建 rule registry。若实施遇到共同 helper 被额外生产者引用，应先更新 producer 清单，不能让隐式新消费者获得未版本化的要求。

**WP2：读取、决策说明和最小展示。** 源文件面：

- [research.md](../../roles/scheduler/research.md)、[results.md](../../roles/scheduler/results.md)：补清 scope/事实/成本的区分；现有八字段读取不增通用 required list。`roles/scheduler.md` 已有动作价值总原则，仅在消除歧义必要时微调，不重复长指南。
- [general_science_views.py](../../src/scidiscovery/general_science_views.py)：已有 objective/gates 显示保留，只把 `hypothesis_assessments` 和 `next_action` 纳入相同原字段投影；建议标注为原报告建议，不能显示推导出来的 prune badge。新旧 v1 共用同一 provider。
- 当前 [read_model.py](../../src/scidiscovery/artifact_agent/approval_ui/read_model.py)、[presentation.py](../../src/scidiscovery/artifact_agent/approval_ui/presentation.py)、[presentation_render.py](../../src/scidiscovery/artifact_agent/approval_ui/presentation_render.py)、[workbench_render.py](../../src/scidiscovery/artifact_agent/approval_ui/workbench_render.py)、[render.py](../../src/scidiscovery/artifact_agent/approval_ui/render.py)、[app.py](../../src/scidiscovery/artifact_agent/approval_ui/app.py) 与 CSS 是**核查面，不预授权全量修改**；只有确定的投影/显示缺口才修改相应窄位置。
- [Architecture 中文](../ARCHITECTURE.zh-CN.md)、[英文](../ARCHITECTURE.md) 只同步新增生产条件与职责边界；经审查确认后才更新计划索引。本次不修改任何这些文件。
- tests：`tests/artifact_agent/test_scheduler_guides.py`、`tests/operations/test_run_status_output_selection.py`、`test_instance_presentations.py`、`test_instance_presentation_render.py`、`test_instance_approval_presentation.py`、`test_instance_workbench_render.py`。断言实际字段和值、来源 pointer 和安全输出，不只搜索 prompt 关键词。

**WP3：端到端边界、安装、回滚与测量。** 复用现有 tests 的运行时与 installed fixtures，新增一个 `tests/operations/test_analysis_decision_contract.py` 负责 §7 的跨边界夹具；不要建立测试之外的 route policy 引擎。受影响 prior alternate callers 用 `test_prior_analysis_sources.py`、`test_analysis_artifact_references.py`、`test_analysis_continuation.py`、`test_reference_access.py`、`test_tcad_gap_continuation.py`、`test_historical_compatibility_paths.py` 做精确回归。`test_catalog_installed_entrypoint.py` 验证真实 wheel/entrypoint；真实 HTTP 检查复用 `test_instance_browser_http.py`。

发布文件面包括三个 `pyproject.toml`、现有 installer/package projection tests 及生成检查；测试核对 `PluginDefinition` 声明而不是盲目同步其版本。`deploy/install.sh`、`platforms/scheduler_prompt.py`、`platforms/codex.py` 按当前真实安装流程验证，若流程已能完成则不修改。性能证据复用 E10，必要时仅给 native parser 增加 expected model/effort 参数和相应测试；不改生产 token 协议。

## 验收、兼容与未决事项

### 7. 确定性正负边界与 installed/live acceptance

工程 PASS 依次证明 **能表达、能读到、能保留来源、能选择不调用、不会越权**。确定性 fixture 不证明模型善于科研，也不证明某路线物理失败。

| 夹具/检查 | 确定性预期 |
|---|---|
| generic、TCAD、curve-error：有效 scope key，合法 `inconclusive + objective fail + claim_allowed=false` | 三条真实提交路径均可封存，Root 同一次 decision read 和 UI 显示原值；不存在科学矛盾组合硬门。 |
| 同样 scope key，objective assessment 缺失或 null | 新 producer 在共同 context 规则拒绝；错误路径、消息、rule_id 与 Worker 可见合同一致。不是 input admission 拒绝，不是 Schema 版本迁移。 |
| key 存在，status=not_evaluable，执行失败/无 score/绘图 scope | 可封存，保留理由与限制；不强制 scoring、gates、next_action、修复 Run 或 TCAD 执行。 |
| scope key=null，包括合法工程计划及历史 scientific 计划 | 缺 assessment 合法；不生成 key。作者凭空填写不同 key 仍由既有 exact-key 检查拒绝。 |
| curve-error package 的 experiment/plan 不匹配、未知 comparison/evidence alias、试图生成新 calculation_records | 按现有对应路径拒绝；不要求不存在的 experiment_plan/prior 端口。 |
| 旧 v1 缺 assessment 作为 prior；manifest 正确/错配；inline/保存文件/recovery 计算；TCAD prior 条件 mapping | 正例经过真实 admission、workspace、replay、context；负例保留原诊断。证明共享 reader 未被新生产规则污染。 |
| current invalid + exact historical 有限观察 | 两者可读取且科学内容不被自动合并；无 prior-v2 继承分支。若报告有语义过度推论，标为科学审查问题，不能宣称此机械测试已识别。 |
| 修改普通 next_action、deprecated recommended_task_mode、handoff hint 为未知/空值 | 不影响 admission 或封存合法性；无新的字符串匹配、allowed-operation 表或命令解释。 |
| 未改的 `science.curve.error.analyze.v1@1` package/plot 输出 | 不消费 report 专属条件；其 version/digest/Schema 不漂移，不要求不存在的 objective_assessment。 |
| 相同已注册下一 Operation 调用，变换分析中的非权威建议 | 原 preflight/invoke 同因通过或拒绝；必须控制其他输入相同，以排除既有父链/审查门造成的差异。 |
| 明确停止的测试 client：读取 completed 报告后结束，不发 invoke | Run/Execution 数量和副作用调用计数不变；fixture 证明流程允许停止，**不声称该 client 证明真实 scheduler 会自主停止**。 |
| running/failed Run、selected missing/null/omitted、旧 compiled digest、signal 不可解析 | 保持当前读取语义，不偷读草稿；原正文可读性与 signal 可用性分开。缺值不补造目标 fail 或路线状态。 |
| Run/Artifact/Approval 三入口 | 相同原字段、pointer 与限制；历史无 assessment 只显示缺项/未记录；HTML 转义；页面失败不改变审批对象或科学字节。 |

源代码单元测试之外，安装验收必须在隔离 site 中安装实际 core/curve-score/TCAD wheels，清除源码 PYTHONPATH 影响，通过 `scidiscovery.plugins` / `scidiscovery.instance_views` 入口编译目录与渲染页面；沿真实 stdio unified MCP 检查 `scid_describe(view="invoke")`、Run assignment/output contract、提交/decision read 和原 preflight/invoke。invoke view 不包含完整 Worker 输出合同，不能以它替代 assignment/schema/context contract 验收。（E9、E11）

生产部署后的 acceptance 只复核已授权安装状态和 exact 报告的读取/展示；不因本计划自动建立研究 Run。若另行授权一次真实分析，使用已有冻结证据、正确 producer 与当前用户原文，不执行 TCAD、不提示“请给出 prune”。Worker 得出任何证据支持的结论均可；工程 PASS 不依赖其迎合用户。

真实 scheduler 的行为质量另列：用同一 sealed fixture、不同明确用户目标/投入约束做受控 Root replay，独立审查其是否把“机制未知”“目标未达”“不再投入”区分，是否说清下一动作能改变什么决定；允许有证据的继续、停止或重新设计。不得在 production 增加一个测试用规则表来制造确定性 PASS；无法观察的行为保持未验证。

遵守现有 R5-N 受限内存纪律：相关 pytest 分批串行，不并行叠加安装矩阵与 Agent 审查；安装态矩阵合并一个批次。实现完成后才使用 change-scope checks 选择最小可信集合，并安排独立实现审查。本次计划阶段不运行全量测试，不把源声明编译成功称为部署 PASS。

### 8. 兼容、发布和回滚

**无数据迁移。** v1 reader/schema resource、Artifact 字节、prior port 名称、manifest、计算与 reference 规则不变；不增加 legacy 双端口、90 天期限或数据转换。仅新 producer 的 `OperationSpec.version` 从 `3/1/1` 提升到 `4/2/2`，新的 context semantic 文本进入相应 digest。其他 Operation 的 digest 是否不变必须用编译结果核对，不能仅靠“没改代码”推断。（E5、E9）

注意 R5-N 历史文件的“合同退休即不返回旧载荷”表述已被当前 Architecture §3 与 `mcp_root_run_routes._sealed_output` 的实现演进取代：**当前 completed 旧版本报告标记 historical，仍返回封存正文及可解析 signal；这不续期资格。** R2 延续该当前行为，而不是恢复旧的 `contract_retired` 读取阻断。Run 续接、独立审查、审批和外部执行仍按各自现有身份规则；不能重开旧 Run 使用新 context checker。相应证据还见 `test_run_status_output_selection.py` 与 `test_historical_compatibility_paths.py`。

当前 Python distribution 为 core `scidiscovery==0.1.0`、curve `scidiscovery-curve-score==0.2.1`、TCAD `tcad-artifact==0.1.0`；对应 PluginDefinition 是 builtin/general_science `0.1.0`、curve_score `0.2.1`、tcad_artifact `0.2.0`。不得混淆这三组版本。R2 发布提议将 distribution 分别增至 `0.1.1/0.2.2/0.1.1`，curve 声明 `scidiscovery>=0.1.1`，TCAD 声明 `scidiscovery>=0.1.1`、`scidiscovery-curve-score>=0.2.2`。最终部署同时锁定三个 wheel hash，不以最低版本代替候选身份。若这些版本已被其他工作占用，在 WP0 选择未占用的后继 release 并更新整组清单，不能覆盖同版本包。

本轮没有新增 plugin ABI 或跨插件符号，PluginDefinition.version 及其 exact PluginDependency 保持既有值；科学合同变化由 Operation version 和可达 resource digest 标识。盲目提升 plugin version 会进入所有可达 component 的 digest 并扩大退休范围（`catalog.py` L755–779），不属于最小改动。发布包版本与声明版本差异写入 release manifest，并以编译对比确认范围。

| 安装组合 | 支持边界 |
|---|---|
| C0/K0/T0：当前精确 cohort | 回滚目标；已有 v1 科学字节可读。 |
| C1/K0/T0：新 core 指南/UI + 旧 producer | 允许安装态验证；writer 条件尚未启用，不能宣称功能全通过。 |
| C1/K1/T1：三个新包、精确 hash | 完整功能验收与生产目标。 |
| K1/T1 配旧 C0，或 T1 配旧 K0 | 新依赖 minimum 应拒绝，不用 `--no-deps` 绕过后声称可部署。 |
| 其他半升级组合 | 不列为生产 release；必须先经单独矩阵证实才增加支持面。本计划不要求发布多阶段 v2 reader。 |

利用现有 installer 将完整验证后的 site 和生成配置成组切换，保持新旧 cohort 清单与服务重启顺序。回滚首先停止新建工作、确认活动 Worker 的冻结合同不会混用，再恢复 C0/K0/T0 与对应受管指南/配置；不删除新结果，不回写旧 report，不借回滚恢复任何审查/审批资格。新结果本来仍是 v1，旧 reader 可解析；恢复后的旧 writer 规则只适用于之后新 Run，不能倒改已封存对象。不要单独回滚 TCAD wheel 后保留不一致的 curve/component cohort。

### 9. Root 与 compiled Worker token telemetry

| 测量对象 | 可接受来源和归属条件 | 能报告 / 不能报告 |
|---|---|---|
| Root | E10 App Server `thread/tokenUsage/updated` 的 total/last 原事件；每个请求边界可验证；或能唯一归属于该 Root 的 native trace | 原生逐请求 input/cached/output、请求数、首次/峰值/末次、净增长；usage 聚合/丢失则 pair 无效。 |
| 生产 compiled Worker | 真正经 spawn_agent + worker_attach 的 exact Run/attempt/session 可关联的 native trace；`token_usage_record` 有唯一 response_id，profile 与冻结模型/effort 一致 | 条件可观测，不是假定均不可观测。若拿不到精确 trace/归属或仅有 aggregate token_count，填写“不可观测”。 |
| collaboration Planner/Reviewer | 本会话工具没有 token usage 接口；无合法外部精确归属证据 | 本轮用量不可观测，不估算。 |
| 独立 App Server/CLI 代理 | 自己的原生 usage，清楚标明受控代理 | 可研究提示成本；不能冒充生产 compiled Worker。旧 run_compiled_codex_worker.py 已拒绝统一 MCP 角色，不是替代生产路径。 |
| 进程/传输辅助量 | 现有 native_execution/RSS/耗时、UTF-8 工具结果/schema/prompt 字节、截断标记 | 分栏报告；不能转换成模型 token、科学正确性或隐藏上下文占比。 |

现有 `native_trace_metrics` 确实解析原生逐 response usage、去重 response_id、不导出正文，但末尾 **hardcode `gpt-5.6-sol/medium`**。直接拿它检查本次 Astra 或其他 profile 必须报测量无效；如改为参数，expected profile 只能来自冻结执行配置，不能放宽匹配来让数据通过。原始 trace 可能含隐私或科学正文，只保存受控位置，报告仅导出元数据与摘要。（E10）

A/B 在实现授权后做：至少两对交替、全新 Root/Worker 线程、串行、同模型/effort、同任务、same exact 输入、同工具权限/响应 profile/预算；分别记录 Root 决策阶段和真实 Worker 阶段。先确认结果事实与限制、引用完整性和操作合法性可比，再比较 token。不保证不同模型选择完全相同行动；调用序列或完成范围不同时只能分场景报告，不能把少做任务当收益。

每侧报告首次/峰值/末次 input、峰值相对首次增长、净增长、逐请求及累计 cached/output、请求数、重读与已识别 compaction/truncation 事件。累计 input/cached 不是上下文窗口；无 compaction 事件也不证明从未裁剪。新增一项 assessment 可能增加 Worker 输出，scheduler 是否减少无价值工作和重复读取必须由观测说明，不承诺未经测量的节约比例。缺任何必要事件不插值，不用 tokenizer 估算填 native token 栏。

### 10. 尚未完成的证据与实施前决定

1. Fig.4 exact 原件、任务 scope 和用户原文只给出了现场导航，尚未导出到本次计划证据；WP0 之前不能把上面的历史归因称为已完成科学审计。
2. 条件目标 assessment 的价值与额外输出成本需要独立计划审查确认；如果 exact 原件显示目标判断早已充分存在于上游，仍应先改 scheduler 消费，不能为了产新字段重做已足够的科学工作。
3. 源声明导入/编译已核查，实际 installed/live cohort、端到端提交、UI 浏览器和 token A/B 尚未执行；本文没有任何部署或资格 PASS。
4. 没有 objective_key 的合法计划仍缺结构化目标 assessment，这是明确保留的兼容限制；先读原目标文本并保持范围说明。只有实际多次因此无法决策，才另提目标身份/Schema 变更，不在本轮悄悄扩展。
5. R2 不承诺硬剪枝。是否重新进入一个先前暂不投入的方向，由新的用户约束和科学证据驱动的 scheduler 决定；科学作者/critic、独立 review、审批和执行门各守原权限。

本次交付仅新增此 R2 文件。计划级自检结果：71 个相对文件链接全部存在；未发现 TODO/TBD 或待填正文；全工作树 `git diff --check` 无错误，并以相对 `/dev/null` 的 no-index check 单独检查这个未跟踪新文件，无空白错误。只读导入与四插件源目录编译完成；未运行实现测试、部署、模型试验或研究任务。这些检查验证文档完整性，不替代独立审查、实现、部署或科学验收。
