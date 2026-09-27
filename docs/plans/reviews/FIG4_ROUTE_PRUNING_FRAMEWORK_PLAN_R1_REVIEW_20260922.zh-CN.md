# Fig.4 路线剪枝框架计划 R1 独立审查

范围：只读审查 `FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R1_20260922.zh-CN.md`，逐项核对 R0 review 的 3 个 P1、4 个 P2，并以当前代码、架构、插件包与 installed entry point 为事实基线。未修改 R1、R0、计划索引或实现。

结论：**REVISE（仅限计划级）**。R1 已关闭“`prune` 成为 command/全局 admission/第二状态机”这一最重要的权威问题，也正确选择了独立 v2 Schema；但 assessment scope、`validated_prior_analysis` 的机械关系和全部实际 consumer 的迁移仍未闭合。存在 3 项 P1 阻断、1 项 P2。

## P1 阻断

### 1. stop pointer 与 assessment scope 被写成统一的“本 Run 绑定 plan”，但第三个 producer 没有该绑定

位置：R1 §2 第 54、58 行，§4.1 第 74—82 行，WP1/WP2；当前 `plugins/curve_score/curve_score/science_operations.py:348-380,666-704`。

可达场景：R1 要求三个 producer 都产必填 v2，并允许 `stop_basis=pre_registered` 引用“本 Run 绑定的 `experiment_plan`”。`science.result.diagnose.v1` 与 `tcad.result.analyze.v1` 确实有 `experiment_plan` 输入；但 `science.result.diagnose.curve-error.v1` 只有 `curve_analysis_package` 和 `curve_analysis_plots`，其 plan 是 package 内嵌字段，不是该 Run 的 `experiment_plan` Artifact 绑定。三个 analysis Operation 也都没有直接 `research_objective` 输入，R1 所称 exact research-objective binding 并非实际共同合同。

影响：同一个 v2 validator 无法按 R1 文字机械执行。实现若只查 `experiment_plan` 会拒绝合法 curve-error 输出；若自行改查 package 内嵌 plan，control 就在计划未声明的情况下发明了另一种 scope；若放松 pointer，则可能把其他 proposal 或非 stop-condition 文本伪称为预注册停止条件。

代码证据：generic 输入在 `science_operations.py:320-335`；curve-error 输入和 context sources 在 `:360-380`；curve-error 当前只以 `package.experiment_plan` 验证 payload，在 `:691-704`。当前 Operation 只读导入核对得到版本 `3/1/1`，与 R1 表格一致，但端口形状不一致。

具体修订要求：逐 Operation 冻结 scope owner 和允许的 pointer 根：generic/TCAD 使用 exact `experiment_plan` input Artifact；curve-error 要么明确使用 exact `curve_analysis_package` 的 `/experiment_plan` 子树并将其纳入 v2 mechanical helper，要么新增真实 plan port 并相应升级合同。objective 范围应改成实际可证的 plan/package `objective_key`，或显式新增 objective port；不得继续声称三个 producer 都有 research-objective Artifact 绑定。为每个 producer 增加跨 proposal、越界、非 stop-condition 和 package/plan 不一致负例。

### 2. `validated_prior_analysis` 尚不能证明“同一精确评估范围”，并可能把跨修订历史判断包装为当前处置

位置：R1 §3 第 62—68 行、§2 第 53—58 行、§4.2；当前 `src/scidiscovery/operations/input_validation.py:148-211`、`src/scidiscovery/artifact_agent/service/analysis_artifacts.py:102-112,165-196`。

可达场景：当前研究 invalid 时，R1 允许 prior v2 支撑当前 `prune`，但没有要求 prior 的 exact plan/package Artifact 与当前 scope owner 相同，也没有要求 prior 的 `experiment_key/plan_key/objective_key`、原 `continuation_assessment` disposition 和当前转载值机械一致。所谓“相应 evidence locator 指向 prior 正式字段”没有冻结 locator 语法、允许 pointer 或递归解析算法。只要绑定一个 gates 为 pass 的 v2 prior，并重绑一部分来源，当前 Worker 就可能把另一次 plan 修订或另一个实验的 `prune` 写进当前 report。

另一个确定性缺口是：现代 tool-evidence manifest 同时有 `bindings` 与 `records`；当前 `prior_analysis_sources` 只在缺少 `bindings` 字段的 legacy manifest 中才把 `records` 纳入 identities（`input_validation.py:185-199`）。因此 prior disposition 若引用 prior 的工具产物，R1 所要求“全部原始来源经 manifest 映射并在本 Run 重绑”无法沿当前 helper 完成；实现者只能漏验、错误排除合法证据或另造未定义规则。

影响：这会重新引入 R0 P1-2 所警告的跨修订路线同一性问题，并违反“历史可读性不续期资格”。control 不能靠文本相似度判断两份 plan 是否同一路线，也不能把 prior 自报 gates 当成 current qualification。

具体修订要求：冻结完整的机械关系：

- prior report 必须是 exact v2，并与唯一 same-producer direct manifest 配对；
- 按 P1-1 的 producer-specific scope owner，要求 prior 与 current 的 exact plan/package 身份及 `experiment_key/plan_key/objective_key` 关系；若不要求 exact identity，就只能 `defer`，不得暗称跨修订同一路线；
- 定义 evidence row 到 prior `/continuation_assessment`、其 `evidence_basis`、再到 prior evidence/source reference 的唯一 RFC 6901 路径及允许字段；当前 disposition/required_change 不得与被引用 prior 字段冲突；
- 同时处理 manifest `bindings`、`records`、recovery origins，并要求每个实际被 prior disposition 引用的 Artifact 在当前 Run 精确重绑；不要求未引用来源；
- 明确这只允许新 Worker 引用旧结论，不恢复 prior 的 current-head、review 或 qualification 状态。

还需补齐跨 experiment、同 key 不同 plan Artifact、tool record 未重绑、prior disposition 不一致、只重绑 report 未重绑其依据等负例。curve-error 若仍无 prior ports，应明确不支持该例外，不能由通用文字暗示支持。

### 3. v1/v2 双读遗漏实际 production consumer，R0 P1-3 未关闭

位置：R1 §4.2、WP2 第 112—123 行；当前 `src/scidiscovery/artifact_agent/service/analysis_artifacts.py`、`plugins/tcad_artifact/tcad_artifact/analysis_bindings.py`、`src/scidiscovery/operations/input_validation.py`。

可达场景：R1 的预计文件面没有列出 `service/analysis_artifacts.py`。该模块直接导入 v1 `LayeredDiagnosisReport`，在 calculation replay 中调用单一 `prior_analysis_sources`，并只认识旧 manifest alias。TCAD 的 `analysis_bindings.py` 也未列入：其 `JSON_PORTS` 只包含旧 `prior_analysis/prior_analysis_manifest`，随后读取 prior source mappings 和历史 `source_references`。按 R1 增加 `prior_analysis_v1*` 并把原端口切到 v2 后，这两条真实路径会漏读 legacy port、用 v1 类解析 v2、或丢失 prior conditional source mapping。

影响：admission 可能接受、finalization/output validation 却失败；更坏时是 calculation replay 与 TCAD case mapping 对相同 invocation 得到不同 prior cohort。仅修改已列出的 `input_validation.py`、`tool_evidence.py` 和 `result_materialization.py` 不能闭合这两个 alternate caller。

代码证据：`analysis_artifacts.py:67,75-79,167,180-189` 固定调用现有 helper/alias 和 `CalculationRecord` 路径；`analysis_bindings.py:19-20,46-56` 固定旧 port 集并直接读取 historical JSON。当前 curve-error Operation 本来没有任何 prior port，R1 也未逐 producer 说明它是否新增这些端口。

具体修订要求：补全 producer/consumer/port 矩阵，至少纳入上述两个文件，明确每个 Operation 是否支持 prior、其 v1/v2 四端口及互斥规则；由一个返回 schema discriminator 与精确 alias 集的 helper 同时供 admission、calculation replay、TCAD materializer/context validator、tool evidence 与 output validation 使用。测试必须走真实 generic/TCAD alternate callers，并证明 v1 legacy、v2、错配、双绑定得到一致结果；不能只测端口 helper。

## P2 重要问题

### 4. 两阶段部署缺少插件包依赖/version 矩阵，不能保证 installed rollback 可执行

位置：R1 §6、WP4；当前 `pyproject.toml:28-33`、`plugins/curve_score/pyproject.toml:5-13`、`plugins/tcad_artifact/pyproject.toml:5-24`。

可达场景：v2 Schema/readers 位于 core，两个 generic producer 位于 `scidiscovery-curve-score`，TCAD producer 又引用 curve-score 的 schema/component。当前 curve-score 仅依赖 `scidiscovery>=0.1.0`，TCAD 仅依赖 `scidiscovery>=0.1.0` 与 `scidiscovery-curve-score>=0.2.1`。若只按“先 core/UI、后 producer catalog”发布，新 TCAD wheel 可与旧 curve-score/core 组合安装，entry point 加载时缺 v2 resource/parser；回滚某一个 wheel 也可能留下不能编译的 catalog。

影响：source 测试可绿而 shipped entry path 启动失败，或者 deployed catalog/readers 组合与验收身份不同。

具体修订要求：把 root、curve-score、tcad-artifact 三个 package manifest/version/dependency minimum 纳入 WP 与回滚清单；冻结允许的 N/N+1 组合和安装/回滚顺序；用隔离环境分别验证 reader-only 阶段、完整 v2 阶段、旧 producer+新 reader、回滚 producer 后的 entry-point catalog。`test_catalog_installed_entrypoint.py` 必须安装实际三个 wheel，而不是只验证 source import。

## R0 findings closure matrix

| R0 项 | R1 状态 | 本轮判定 |
|---|---|---|
| P1-1：`prune` 成为硬路由权威 | R1 §1 明确它不是 command/admission/qualification，验收要求任意 Operation preflight/invoke 不因 disposition 改变，并禁止 route action table | **关闭**。R5-N 权威未被侵蚀；没有第二状态或隐藏 command。 |
| P1-2：route identity、stop/new evidence 无法机械判定 | 删除 branch/strategy/fingerprint 和“新证据放行”是正确收敛 | **部分关闭**。route identity 问题被删除，但 producer-specific stop scope 和 prior 跨修订 scope 未闭合，见 P1-1/P1-2。 |
| P1-3：Schema/Operation/shared handoff 迁移不成立 | 独立 v2、保留 v1、不改 `RoleHandoff/SchedulerSignal` 的方向正确 | **未关闭**。真实 consumer 和 alternate caller 缺失，见 P1-3。 |
| P2-1：invalid-study 历史证据有效性 | 增加 gates 与 prior v2 例外 | **未关闭**。同 scope、引用递归、manifest records/rebinding 和资格边界仍不足，见 P1-2。 |
| P2-2：UI/installed 文件面 | 已覆盖 provider、read model、presentation、两类 renderer、HTTP、CSS、entry point 与三入口负控 | **计划级关闭**；package 组合风险另见 P2。 |
| P2-3：真实 Worker 迎合风险 | deterministic fixture 决定框架 PASS，真实 Worker 任一合法 enum 都可 PASS，prompt 禁止提示期望答案 | **关闭**。 |
| P2-4：token telemetry 来源 | Root、production Worker、controlled proxy、collaboration 分表；不可观测不估算 | **关闭**。 |

## 已核查路径

- R5-N 与 `ARCHITECTURE*.md` 的 scheduler/catalog/Worker 权威边界；
- R1 与 R0 review 全文、计划索引的 active-proposal/历史角色；
- 三个 producer 的实际 Operation ID、版本、输入/输出端口和 context validator；
- v1 `LayeredDiagnosisReport`、claim projection、finalizer、`RoleHandoff`、`SchedulerSignal`；
- prior admission、manifest bindings/records、calculation replay、TCAD source-binding alternate caller；
- reference rules、general-science/Approval/Workbench display 与 installed `scidiscovery.instance_views` entry point；
- root、curve-score、tcad-artifact 三个 package dependency 表；
- deterministic fixture、真实 Worker 反迎合与 Root/Worker/subagent token telemetry 设计。

只读导入核对确认三个当前 Operation 版本为 `3/1/1`，与 R1 基线一致。未运行完整测试或部署实例；本 verdict 不评价未来实现质量。

## 残余风险

R1 没有建立硬剪枝门，因此上述缺口当前不会改变已有 Operation admission；风险发生在按此计划实施 v2 后。UI 的具体四轴布局和浏览器字节级渲染仍需实现审查与 installed/live 验收。即使修订后计划 PASS，真实 Fig.4 的 `prune` 仍只是 Worker 科学判断和 scheduler 输入，不是框架资格或普适机制证伪。

独立 Reviewer token 用量：平台不可观测，未估算。
