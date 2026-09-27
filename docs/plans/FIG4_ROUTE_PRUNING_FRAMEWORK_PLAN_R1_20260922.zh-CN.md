# Fig.4 路线剪枝框架实施计划 R1

状态：**历史 R1 修订提案；[R1 独立审查 REVISE](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R1_REVIEW_20260922.zh-CN.md)，由 [GPT-6 R2 活动提案](FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md)接管；未实施、未部署**。
日期：2026-09-22。
来源：修订 [R0 计划](FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_20260922.zh-CN.md)，逐项回应 [R0 独立审查](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R0_REVIEW_20260922.zh-CN.md)。本文不覆盖 R0 的历史状态，未获授权成为当前架构规范。

## R0 P1/P2 closure matrix

| 审查项 | R1 关闭方式 | 验收锚点 |
|---|---|---|
| P1-1：Worker `prune` 变成全局硬路由权威 | 删除 R0 的 continuation guard、全局动作分类和硬拒绝。本轮 `continuation_assessment` 只是封存科学内容及 scheduler 输入；scheduler 仍依 R5-N 从唯一 compiled catalog 自主选 public Operation，control 不按 `prune` 接受或拒绝调用。任何未来硬门必须另立提案，并由具体 Operation 自身声明机械合同及精确独立科学复核。 | 同一 `prune` 报告不能使任意 Operation 的 preflight/invoke 结果变化；不存在 route action table；废弃建议仍无路由权。 |
| P1-2：branch/strategy/stop/new-evidence 无机械身份 | 从本轮合同删除 `branch_key`、`strategy_key`、`route_fingerprint` 和“新证据放行”。当前判断范围只由 exact objective/plan Artifact 绑定及报告内 `experiment_key/plan_key` 锚定。停止条件仅允许用绑定 `experiment_plan` 内的精确 JSON Pointer 引用；control 不判断语义等价。 | Schema 中不存在 route identity；合法 stop pointer 可解析，越界/指向非 stop-condition 路径失败；改名不会产生任何机械放行。 |
| P1-3：Schema、Operation、共享 handoff 迁移不闭合 | 新建 `scidiscovery.layered-diagnosis.v2`；v1 类和字节不改。三个当前 producer 切换到 v2 并提升 Operation version；明确 v1/v2 双读端口、期限和退役门。`RoleHandoff`、通用 `SchedulerSignal` 均不加字段；Root/UI 直接读 sealed v2 payload，必要导航只是 schema-specific projection。 | v1 历史可读；新 producer 缺 assessment 必须失败；v1/v2 prior 互斥且各自与精确 manifest 配对；所有非 analysis RoleResult digest 不因共享 handoff 漂移。 |
| P2-1：`invalid_study` 证据有效性边界缺失 | v2 强制 `gates`；无效当前研究不得以本次失败证据输出 `continue/prune`。仅当处置证据全部来自精确绑定、可复核且前置有效性为 pass 的 prior v2 analysis 时，当前 `invalid_study` 才可保留一个历史路线判断；否则只能 `defer + numerical_repair/new_evidence`。 | 无效求解包装成物理 `prune` 失败；数值无效但绑定合格 prior v2 的正例通过；v1 prior 不冒充有效性证明。 |
| P2-2：UI/installed 真实入口不完整 | 文件面覆盖 read model、provider、presentation、两类 renderer、Workbench/Approval HTTP 路由、CSS 以及 installed `scidiscovery.instance_views` entry point；Run/Artifact/Approval 三入口显示相同四轴原值。 | source 与隔离 wheel 各验证三入口；缺字段的 v1 显示 legacy，不推导、不报错；浏览器 HTML 负控无伪造状态。 |
| P2-3：Fig.4 live 验收有迎合风险 | 框架 PASS 只由确定性 Fig.4 fixture 和机械正反例决定。真实 Worker 结果无论 `continue/prune/defer` 均不作为框架成败标准；提示中不得写入用户期望 enum 或预期答案。 | 固定 fixture 覆盖 `inconclusive + objective fail + prune`；真实 Worker 仅检查合同合法、证据绑定和无控制越权。 |
| P2-4：Root/Worker token telemetry 来源不清 | Root 仅采用 App Server 原生 `thread/tokenUsage/updated` 逐请求 usage；compiled Worker 仅在其实际 transport 暴露同类原生事件时计量。受控代理测量单列，collaboration/subagent 与不可见生产 Worker 标为“不可观测”，绝不估算。 | A/B 报告逐项标明来源、可观测性和不可比项；字符/tokenizer 估算不得进入 native token 栏。 |

## 1. 提案边界、语料角色与 R5-N 关系

本提案只解决一个缺口：分析报告没有稳定表达“目标是否达到”和“继续当前局部微调是否仍有科学价值”。它不判定 Fig.4 的普适科学阈值，不改写任何既有结果，也不自动淘汰任何假设或阻止任何 Operation。

- [R5-N 调度行动权威简化](R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md) 与 `ARCHITECTURE*.md` 继续是当前规范；R1 **不取代、也不部分取代 R5-N**。
- R0 与其 R0 review 保留为历史修订证据；R1 经独立审查通过并由索引登记前，不取得当前规范地位。
- Analysis Worker 作者科学判断；control 只核验 Schema、精确绑定、引用和组合一致性；scheduler 把封存判断作为一个输入，自主选择 compiled catalog 中的 public Operation；critic 继续独立审查新假设集合；UI 只展示原值。

`prune` 不是 command、approval、qualification、current-head 状态或永久分支墓碑。本轮不实现任何基于处置值的 admission。若未来确有硬阻断需要，必须另行设计，且同时满足：由每个受影响 Operation 在自身编译合同中声明所消费的 exact assessment、exact subject 和机械关系；preflight/invoke 共用同一 validator；`prune` 已有精确独立科学复核；有显式重新开放路径；不存在核心全局“动作类型→允许变化”表。上述未来条件不预授权本轮代码。

## 2. 最小科学合同

新增 schema id `scidiscovery.layered-diagnosis.v2`，v1 模型和 codec 保持不变。v2 保留现有报告的科学字段，但要求 `gates`、`objective_assessment`、`remaining_contradiction` 与下列 `continuation_assessment`；删除 v2 中已废弃的 `recommended_task_mode`。自由文本 `next_action` 可保留为非约束建议。

```json
{
  "continuation_assessment": {
    "local_refinement_value": "justified|not_justified|unknown",
    "tested_route_disposition": "continue|prune|defer",
    "required_change": "none|new_hypothesis|model_redesign|new_evidence|numerical_repair|stop",
    "stop_basis": "pre_registered|post_hoc|not_applicable",
    "plan_stop_condition_refs": ["/proposals/0/stop_conditions/1"],
    "evidence_basis": [{
      "evidence_key": "exact_local_key",
      "validity_scope": "current_valid_study|validated_prior_analysis"
    }],
    "rationale": "evidence-bound scientific judgment"
  }
}
```

机械约束仅限可从 exact payload/bindings 判定的事实：

- `continue = justified + none`；`prune = not_justified + new_hypothesis/model_redesign/stop`；`defer = unknown + new_evidence/numerical_repair`。
- `evidence_basis` 至少一项，键必须唯一并解析到本报告 `evidence` 的唯一项；validator 只核验引用与有效性来源，不从误差大小派生处置。
- `pre_registered` 必须给出至少一个 stop pointer；`post_hoc/not_applicable` 必须为空。pointer 必须精确指向本 Run 绑定的 `experiment_plan` 中、当前 `experiment_key` 所属 proposal 的一个 `stop_conditions` 字符串。计划生产者是该文本的唯一 owner；analysis 只引用，control 不比较同义文本。
- `objective_assessment.status=fail` 与 `overall_verdict=inconclusive`、`tested_route_disposition=prune` 是合法组合。`inconclusive` 表示没有严格证明完整机制真伪；`prune` 表示 Worker 判断当前已测试的局部微调不值得继续，二者不是同一轴。
- 不定义通用误差阈值，不把 Fig.4 用户判断写成 validator。`rationale` 是科学内容，control 不做关键词、量级或语义等价判断。

不新增 `branch_key`、`strategy_key` 或 route fingerprint。报告范围以 Run 的 exact research-objective/experiment-plan 绑定及 payload 的 `experiment_key/plan_key` 表示；它足以说明“本报告评估了什么”，但不试图给跨修订路线建立全局机械同一性。新 hypothesis、skeleton 或 experiment 仍沿用现有对象身份、revision 与 review edge，不因某个新 key 自动放行。

## 3. `invalid_study` 与证据有效性

1. `gates.evidence_identity/implementation_fidelity/numerical_validity/control_equivalence` 全部为 `pass/not_applicable` 时，`current_valid_study` 可以支撑三种处置；其 evidence key 仍须通过现有领域 context validator 解析到精确输入或 tool evidence。
2. 任一前置 gate 非上述状态，当前证据不得支撑 `continue` 或 `prune`。默认合法结果是 `overall_verdict=invalid_study`、`defer + numerical_repair/new_evidence`。
3. 例外仅是 `validated_prior_analysis`：必须绑定 exact v2 prior report 及其 same-producer direct manifest；prior v2 的前置 gates 必须有效，引用的原始来源必须经 manifest 映射并在本 Run 重绑。当前 assessment 的相应 evidence locator 必须明确指向该 prior report 的正式字段。control 只验证这些机械事实，不重新判断旧科学结论。
4. v1 prior 因 `gates` 和 continuation 字段可缺，不能作为这项例外的有效性证明；它仍可按既有合同作历史背景或计算记录复用。
5. `invalid_study + prune` 仅在全部处置依据均为上述合格 prior v2 时可封存，并必须在 limitation 中明确“本次执行未新增有效物理证据”。混入当前无效证据即拒绝。

正例包括“当前求解失败，但 exact prior v2 已在有效研究上判定本路线不值得继续”；反例包括“仅凭不收敛、缺失输出或错误映射声称物理路线失败”。

## 4. 唯一 Schema 与 Operation 迁移路径

### 4.1 Producer

只有三个当前分析 producer 切换为 v2：

| Operation | 当前→目标 version | 目标输出 |
|---|---:|---|
| `science.result.diagnose.v1` | `3 → 4` | `layered_diagnosis: scidiscovery.layered-diagnosis.v2` |
| `science.result.diagnose.curve-error.v1` | `1 → 2` | 同上 |
| `tcad.result.analyze.v1` | `1 → 2` | 同上 |

切换是 producer-only cutover：新 Run 只产 v2，不双写 v1，不原地改历史 Artifact，不让旧 verdict/review 自动继承到新对象。Operation digest、schema resource、prompt、semantic/context validator 和 workspace patch contract 必须共同变化。

### 4.2 Consumer 双读边界

- 新报告复用端口保持 `prior_analysis` + `prior_analysis_manifest`，只接受 v2。
- 增加成对且互斥的 `prior_analysis_v1` + `prior_analysis_v1_manifest`，只接受 v1。显式 manifest 不再与 TCAD 的执行恢复 `recovery_manifest` 兼任，避免一件两义；四个 prior 端口最多选择一组。
- `prior_analysis_sources` 返回所选 schema/version 与精确 source mapping；calculation replay 按该 discriminator 使用 v1 或 v2 parser。错误配对、两个版本同时绑定、manifest 非直接同生产者父件均在 admission 与 output validation 用同一 helper 失败。
- reference access、claim projection、general-science display、Approval/Workbench read model 对 v1/v2 双读；v1 显示 `legacy/no continuation assessment`，绝不补造字段。v2 的 reference rules 增加 continuation evidence keys 和 stop pointer 所需的声明路径。
- `RoleHandoff` 与 `SchedulerSignal` 不变。analysis finalizer 仍只从正式 summary/verdict 生成通用 handoff；Root 通过 `run_status(response_profile="decision", output_paths=[...])` 直接选择 v2 的 `/objective_assessment`、`/continuation_assessment`、`/limitations`、`/remaining_contradiction`。若产品确需有界导航，只在 v2 schema 的 response/read-model projection 中投影原字段和原 JSON Pointer，不进入共享 handoff，也不成为第二真相。

迁移时限：部署版本 N 开始生产 v2，所有 reader 与 prior ports 双读；N+1 继续双读。最早在 **N+2 且首次 v2 生产部署满 90 天** 后，只有在实例清单证明没有 current workflow 依赖 legacy prior ports，并通过独立迁移审查，才可在新的 Operation version 删除 v1 prior 输入端口。v1 历史 Artifact、codec、UI/read-only reference access 不设删除期限。

## 5. 工作包与精确文件面

### WP0：冻结合同、fixture 与语料状态

- 冻结 R0 review 三个 P1/四个 P2、R5-N 不变式、三个 producer 的当前 version/digest，以及 before/after 测量提交。
- 新建最小 `tests/fixtures/fig4_route_pruning/`：exact objective、plan、有效 evidence、无效 execution、v1 prior、v2 prior 和期望 Schema 结果。fixture 记录 Fig.4 的“总体 inconclusive、目标 fail、局部路线 prune”组合，但不成为通用阈值或真实科学再判定。
- R1 经审查通过后才由计划索引标为活动 owner；R0 保留链接与历史审查结论，不改写。

### WP1：v2 Schema 与纯机械 validator

预计修改：

- `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py`：保留 v1；新增 v2、continuation 子模型与 v2 consistency helper。
- `src/scidiscovery/artifact_agent/schema/claim.py`：v1/v2 claim projection。
- `src/scidiscovery/reference_tools.py`、`src/scidiscovery/artifact_agent/service/reference_access.py`：v2 声明式引用解析。

明确不修改 `schema/role_result.py`、`schema/run_signal.py`、`schema/cognitive.py`、`schema/experiment.py` 或 `schema/experiment_intent.py`。stop condition 继续由现有 plan 作者拥有，本轮只增加对精确 pointer 的消费校验。

### WP2：三个 producer 与 prior 双读

预计修改：

- `plugins/curve_score/curve_score/science_operations.py`
- `plugins/curve_score/curve_score/analysis_workspace.py`
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py`
- `src/scidiscovery/operations/input_validation.py`
- `src/scidiscovery/artifact_agent/service/tool_evidence.py`
- `src/scidiscovery/artifact_agent/service/result_materialization.py`

prompt 要求 Worker 分开回答 scientific verdict、objective status、local refinement value 与 disposition；不得告诉 Worker Fig.4“应该 prune”，不得让它命名后继 Operation。generic/TCAD context validator 复用同一 v2 mechanical helper，再分别验证领域 source binding。v1 calculation replay 兼容路径用显式 legacy port，不猜 schema。

### WP3：Scheduler 读取与 UI

Scheduler 只更新源指南 `roles/scheduler.md`、`roles/scheduler/results.md` 及其安装投影源：读取四轴原值，结合目标和矛盾自主选择行动；不把 disposition 当命令，不无条件把 inconclusive 送去调参。`.codex` 安装产物由既有生成/安装流程产生，不直接手改。

UI 预计修改/核查：

- `src/scidiscovery/general_science_views.py`：v2 provider 和四轴字段源。
- `src/scidiscovery/artifact_agent/approval_ui/read_model.py`
- `src/scidiscovery/artifact_agent/approval_ui/presentation.py`
- `src/scidiscovery/artifact_agent/approval_ui/presentation_render.py`
- `src/scidiscovery/artifact_agent/approval_ui/workbench_render.py`
- `src/scidiscovery/artifact_agent/approval_ui/render.py`
- `src/scidiscovery/artifact_agent/approval_ui/app.py`（真实 Run/Artifact/Approval HTTP 入口核查；无路由改动需要时不改）。
- `pyproject.toml` 的 installed `scidiscovery.instance_views` entry point 与 wheel 内容核查。

展示为四个并列、带原字段链接的值：科学可信度、目标符合度、当前路线评估、所需变化。v1 显示 legacy；缺失/截断/解析失败显示 gap，不从 summary 推导。UI 不提供“执行 prune”按钮，不改变 Artifact 字节或 approval subject。

### WP4：测试、隔离安装与 live 验收

测试文件面至少覆盖：

- schema/context：`test_analysis_handoff_report.py`、`test_tcad_result_analysis.py`、`test_m2_curve_analysis_boundary.py`；
- prior/reference：`test_prior_analysis_sources.py`、`test_reference_access.py`、`test_reference_access_installed.py`；
- UI：`test_instance_presentations.py`、`test_instance_approval_presentation.py`、`test_instance_presentation_render.py`、`test_instance_workbench_render.py`、`test_instance_trajectory_read.py`；
- installed：`test_catalog_installed_entrypoint.py`，使用隔离 wheel 的真实 plugin 与 `scidiscovery.instance_views` entry points。

真实浏览器负控必须确认 Run/Artifact/Approval 三入口一致、legacy 不伪造、HTML 转义和缺字段 fail-closed。live 科学检查在已绑定实例中新建一次 analysis 时不得重跑 TCAD，也不得以 Worker 是否同意用户为工程 PASS 条件。

## 6. 迁移、部署与回滚

部署顺序固定：先发布具备 v1/v2 reader 的核心与 UI，再发布 v2 producer catalog；不得反序让新 Artifact 无 reader。部署前保存三个 Operation 的 compiled identity 和 installed entry-point 清单，部署后从真实 MCP `describe(view="invoke")`、隔离 wheel 和浏览器入口核对。

回滚时：停止创建 v2 Run，恢复上一套 compiled catalog/wheel；保留 v2 schema reader、历史 Artifact 和 UI legacy/v2 展示。不得删除 v2 数据、把 v2 转写成 v1、恢复旧资格或复用旧 review verdict。若 producer 已切换但 UI 失败，只回滚展示/包，不改科学字节。若 v2 validator 有误，创建新 Operation version 修复，不原地接受已拒绝或篡改已封存结果。

## 7. 验收矩阵

| 场景 | 预期 |
|---|---|
| v2 `inconclusive + objective fail + prune + model_redesign`，当前 gates 有效、证据完整 | producer 接受；四轴原值展示；不自动触发或阻止 Operation |
| v2 `inconclusive + continue` 且 Worker 给出 evidence-bound justified 判断 | 接受，证明框架不预设剪枝答案 |
| v2 `defer + numerical_repair`、当前 invalid | 接受 |
| 当前 invalid，仅凭失败 solver evidence 输出 `prune` | 精确拒绝到 continuation evidence validity |
| 当前 invalid，全部处置依据来自 exact 合格 prior v2 与重绑来源 | 接受；limitation 明确本次无新有效物理证据 |
| v1 prior 冒充 validated prior | 拒绝；仍允许其合法 legacy calculation/background 用途 |
| stop pointer 越界、跨 experiment、指向非 stop condition | 精确拒绝；control 不做文本相似判断 |
| `prune` 后调用任意原 public Operation | disposition 本身不改变 preflight/invoke；其他现有门照常工作 |
| v1 历史报告 | 字节不变、可读、UI 显示 legacy、无 continuation 硬门 |
| v1/v2 prior 同时绑定或 manifest 错配 | preflight/invoke 同 helper、同原因拒绝 |
| 非 analysis RoleResult | RoleHandoff/SchedulerSignal schema 与 digest 无无关漂移 |
| source 与隔离 wheel 的 Run/Artifact/Approval | 四轴一致，字段源可追溯，installed entry point 生效 |
| deterministic Fig.4 fixture | 无模型参与即可完整通过正例和所有负例 |
| 真实 Fig.4 Worker 输出 `continue/prune/defer` 任一值 | 只要 schema、证据、有效性和边界合法，框架检查均可 PASS；不做迎合评分 |

验收还必须证明 `rg`/AST 检查不存在按 disposition 的 Operation allow/deny 分支、不存在全局 route action table，preflight/invoke 原有一致性未退化。分批测试按仓库受限内存纪律串行运行；安装态矩阵只执行一次。

## 8. Token 与上下文 telemetry

测量不是功能 gate 的替代。WP0 固定 before/after commit、任务文本、输入 Artifact、模型、effort、工具、响应 profile 与运行顺序；至少两对 A/B 交替、全新线程、串行执行，先证明科学输出和调用序列可比。

| 对象 | 唯一可接受来源 | 报告字段 | 不可观测时 |
|---|---|---|---|
| Root | App Server 原生 `thread/tokenUsage/updated`，沿用 `docs/plans/evidence/mcp-response-levels/probe_request_usage.py` 的逐请求边界与原事件保存 | 首次/峰值/末次 input、cached input、output、请求数、net input growth、工具结果字节、compaction/异常 | 记“不可观测/测量无效”，不从上下文百分比反推 |
| production compiled Worker | 仅其实际 Worker transport 暴露的原生逐请求 usage，且能绑定 exact Run/attempt | 与 Root 分表；额外记录 Run、attempt、模型/effort 和工具调用数 | 记“不可观测”，不拿 Root 或 collaboration 代替 |
| 受控 Worker 代理 | 独立 App Server probe，可用于 before/after 工程代理趋势 | 明标 `controlled proxy`，不声称是 production child | 与生产结果不合并 |
| collaboration/subagent | 当前平台无 token telemetry | 只记录 agent/task 与“不可观测” | 禁止估算 |

UTF-8 字节、字符数或 `o200k_base` 只能作为 transport/schema 体积辅助指标，不能写入 native token 栏。累计 cached tokens 不能冒充上下文窗口。若任一 A/B 请求 usage 合并、缺事件、模型不一致或调用序列漂移，该 pair 作废而不是插值。

## 9. 本轮明确不做

- 不实现 continuation admission guard、全局路线索引、route fingerprint、branch/strategy key 或自动“新证据”判定。
- 不让 control 识别科学路线的语义等价，不建立 `required_change → Operation` 映射。
- 不修改共享 `RoleHandoff`/`SchedulerSignal`，不改所有 Agent 的通用合同。
- 不引入 Fig.4 专用阈值，不把用户意见伪装成实验事实，不重新执行 solver。
- 不把 `prune` 变成人工审批、qualification 或永久删除；hypothesis/skeleton/design 的既有独立 review 与 revision 规则保持。
- 不在本计划阶段修改实现、生成安装产物、部署或声称 qualification 通过。

## 10. 未决项

1. 首次实施前须由独立 reviewer 确认 v2 的 `validated_prior_analysis` 机械规则没有错误排除合法历史证据，也没有把 v1 宽松读提升为当前科学资格。
2. exact compiled catalog 必须确认三个 producer 的基线 version 与本文一致；若工作树/部署已变化，先更新 WP0 基线和迁移表，不能静默沿用数字。
3. legacy prior ports 的 N+2/90 天退出需要实例级只读 inventory 证据和单独迁移审查；当前没有授权其删除。
4. 若未来确需硬剪枝，必须另立经独立审查的设计；R1 既不定义被阻断 Operation 集合，也不为该设计预留隐式控制状态。
