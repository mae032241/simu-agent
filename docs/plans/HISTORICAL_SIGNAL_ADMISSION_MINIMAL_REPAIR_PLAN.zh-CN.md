# 历史判定与分析准入最小修订计划 R2

2026-09-10。状态：按跨模块审查完成计划修订；未实施，未测试，未取得本版复审结论。

本版替代聊天中“只对齐 Root 的历史 handoff 读取”方案，承接 [R4 安装后真实记录验证](evidence/input-validation-boundary/LIVE_VALIDATION.zh-CN.md)。审查意见保留在 [历史判定计划审查](evidence/input-validation-boundary/HISTORICAL_SIGNAL_PLAN_REVIEW.zh-CN.md)，其 REVISE 不改写为 PASS。原 R4 计划、实现记录和本地通过证据保留，本计划只处理升级后真实分析路径暴露的遗漏。

## 1. 目标与责任边界

原版本已经封存的审查判定是历史事实；版本更新不能使它在输入投影中变成空值。读取该事实不授予当前审查、资格或执行权限。

验收目标：旧版本正式产生计划、通过审查及执行记录，升级后仍能用精确旧记录创建新分析并封存有限结论；需要当前独立审查、资格或执行批准的其他动作保持原要求。

输入结构、来源、历史用途及资格在创建前处理。提交/预览不重跑输入准入。历史分析不自动证明计划仍适用于新实验，也不把一次历史 pass 当作总体目标完成。

## 2. 冻结最小生产改动范围

限定三个生产文件。不是把审查中读过的所有文件都纳入修改。

| 文件 | 必要修改 | 解决的已发生/可达问题 |
| --- | --- | --- |
| src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py | 输入事实显式读取封存 handoff；审批材料保留原当前判定语义 | Root 与 schedule 的输入投影不一致；通用修改误影响资格审批 |
| plugins/tcad_artifact/tcad_artifact/result_analysis.py | 仅分析的 plan/review 端口用途调整；补齐对应输入结构与来源校验及组件身份 | 历史审查先被 parentage guard 拒绝，之后又被通用当前 review 门禁拒绝 |
| plugins/curve_score/curve_score/science_operations.py | 仅 science.result.diagnose.v1 的同类 plan/review 用途及输入检查 | 通用结果分析存在相同升级接缝 |

不改 signal_for_output 默认参数、_scheduler_signal_for_output 公共 helper、is_exact_reviewer_output 的当前合同要求、review_input_mode、RunService.schedule、current 策略或 claim_admissible 规则。它们作为对照检查，不因本修复全局放宽。

不修改设计/作者/修订/物化的 prior_signal 用途，不变更专门的 curve-error 分析包 Operation。不增加端口类别、注册表、状态机、数据库列、MCP 工具或全局 ABI。VM runner、执行协议和安装脚本不在范围内。

## 3. P1：Root 输入事实与审批条件分别取值

### 3.1 构造输入

在 _prepare_operation_call 构造 InvocationArtifact 的实际位置，显式调用已有 runs.signal_for_output(envelope.ref, require_current=False)，与 schedule 的权威重建一致。一次取值后使用，不复制查询实现。

只从精确 output_ref 对应的 completed Run 取得原 signal。没有完成 Run、没有 signal 的对象仍为 None；不得从 payload.verdict、标签或指令推定 pass。原 historical/current、schema、媒体、大小、父链及标签按原来源传递。

### 3.2 准备资格审批材料

_prepare_approval_projection 不能继续把上述历史 handoff 无条件复制为原审批 projector 的当前条件。构造 ApprovalSubjectSnapshot 时，通过现有 _scheduler_signal_for_output(item.artifact.ref) 取得原来 require_current=True 的值，使审批准备保留修改前的判定语义；不回写或覆盖已构造的输入历史事实。

这是保留原审批请求条件，不是新增“所有历史材料都不能审批”的规则：历史提取成果配合当前有效独立 audit 申请新资格仍按现有路径处理；旧 audit 是否满足 projector 条件按原当前检查处理。证据资格与参数资格均做前后对照。

外部执行审批使用 mcp_root_execution_routes 中现有 helper，其行为不改；批准 provider/contract/subject 身份核验以及用户 UI 决策仍由原实现负责。

## 4. P2：分析明确消费历史计划与审查，不重新授予实施资格

### 4.1 只调整两个分析入口的两个端口

对 tcad.result.analyze.v1 和 science.result.diagnose.v1 的 experiment_plan、experiment_review，将 usage 从 prior_signal 改为既有 evidence_inventory。这样它们不再以“启动新的实施任务的审查见证”进入通用 producer-review 资格路径。

保留具体 schema、JSON codec/schema resource、媒体、数量、预算与 exposure。不要直接使用把资源换成 wildcard 的通用 inventory helper；可在具体端口构造后窄 model_copy 修改 usage。不要全局修改 TCAD _input 或 curve 的 _review_input 默认值。

分析 guard 继续验证历史计划与审查的精确关系，TCAD 同时核对 package/manifest/产品/diagnostics 的实际执行父链。改用途不意味着来源可任意匹配。

### 4.2 补上原 prior_signal 路径承担的检查

evidence_inventory 会跳过部分通用 producer 检查及历史 prior_signal 结构验证，因此必须把本分析实际依赖的最小检查放入其已有 guard/input_validation，而非丢掉保护或推到输出阶段：

- plan 使用 ExperimentPortfolio 解析；review 使用 ScientificReview 解析，目标必须是 experiment_portfolio，payload 与封存 handoff 的通过判定一致。只检查结构、身份和已有审查事实，不重新评价计划的科学合理性。
- review 必须是实际 completed Run 提供的 handoff，并匹配独立计划审查生产者及其输出端口、精确 plan 父引用；不能仅凭 JSON 中的 pass 或一个同 schema 的其他领域审查通过。预期生产者与现有计划独立审查合同保持一致，在领域声明/guard 中表达，不在 Root 添加 Operation 名字白名单，不要求历史 producer digest 等于当前 digest。
- 原分析关联规则不削弱：错误计划、错误 review target、无完成记录的伪审查、另一执行的同字节日志均拒绝；科学输入参数值和总体目标覆盖交给 Agent/审查，不追加硬门槛。

TCAD 复用 validate_analysis_inputs，补 review 解析和对应静态错误位置。通用分析在本文件中增加一个最小组合 input_validation 组件，解析其 plan/review；复用现有 InputValidationSpec、parse_bound_json、OperationInvocationError，不另建框架。相对候选输出的引用和计算校验仍留在输出路径。

所有新前提经 input_validation.description 或相应 guard 的既有声明说明暴露，字段错误给稳定端口/字段。模型可见规则不得与实现分叉。

### 4.3 非通过历史记录的用途

历史 blocked/revise 原样保留。它们可以经已有 current_progress/evidence_inventory 作为诊断、设计背景；不能冒充分析入口要求的通过计划审查，也不能经 claim_evidence 当作可用成功主张。

恢复历史值后 claim_admissible 对某些输入会更严格，这是原非通过规则重新生效。不得为维持错误放行而把历史非通过改回 None；也不得把同一限制施加到背景材料端口。

## 5. P3：先建立升级回归，再实现，最后验证相邻边界

扩展现存测试，避免建立平行 fixture 工厂或全量运行。每个用例必须证明行为，不能只断言新增字段存在。

| 用例组 | 设置与必须成立的结果 | 优先复用文件 |
| --- | --- | --- |
| 真正跨版本分析 | 正式产生带 producer 元数据的计划（含确定性 materialize 父链）、独立 review 及执行产物；随后更换 review 的生产合同。旧 review 状态为 historical，但 Root preflight/invoke、schedule、Worker submit 全链通过 | test_collector_analysis_handoff.py、test_historical_compatibility_paths.py、test_result_analysis_tool.py |
| 来源与结构负例 | 错 plan、错误审查生产者/target、只有标签的伪 pass、畸形历史 plan/review、跨执行相同日志均在创建前拒绝，零新 Run；正常当前记录仍通过 | 上述升级用例参数化；test_tcad_result_analysis.py |
| 当前审查不继承 | 同一旧 review 不能满足明确要求当前审查的 author；改过的计划不能继承旧 pass；现有物化、修订的审查门禁回归保持 | test_historical_compatibility_paths.py、test_review_admission_integration.py |
| 资格申请无扩权 | 证据资格、参数资格分别覆盖：当前 audit 的原合法申请仍合法；换成升级后历史 audit 不会因恢复 pass 就新增审批准入；历史 extraction 配当前 audit 仍按原规则处理；无需提交任何真实 UI 决策 | test_historical_compatibility_paths.py、test_m2_parameter_package.py、test_l3_review_and_human_policy.py |
| 非通过记录 | 同一历史 blocked/revise 作为背景可交付有限分析，作为 claim_evidence 被原规则拒绝；无 completed Run 不产生 handoff | test_historical_compatibility_paths.py 或既有角色合同集成测试 |
| 输出职责 | preflight/创建执行输入 checker，preview/submit 零输入 checker 调用；错误候选仍可定位修正 | test_tcad_result_analysis.py 的现有观测用例 |
| 安装一致性 | 精确候选 wheel 中两个分析 Operation 的端口用途、输入规则及 Root 投影一致；升级交接至少一次经过 installed Root/Worker，而非仅源码 PYTHONPATH | test_catalog_installed_entrypoint.py 的既有安装 fixture |

重点防止再次使用只通过同一版本新 review 的 fixture：测试必须先断言旧 review 的封存 pass 可读且当前精确资格检查不通过，再验证新分析完成。通用分析与 TCAD 各覆盖一条；不能仅用 payload 标签模拟升级。

单进程串行运行，复用 bounded_check.py，总测试树预算 min(512 MiB, MemAvailable/4)，含子进程，超限停止。先运行能复现本缺陷的用例，再分批检查相邻路径；不运行全量、压力测试或真实求解器。成功批次不无理由重复，保留失败日志与峰值。

## 6. P4：身份、部署与线上完成条件

端口 usage 和 input_validation/guard 的改变必须正常进入组件与 Operation 摘要。只更新本次修改组件的 configuration_identity；不伪造旧摘要、不提升全局 ABI。比较前后完整目录，若出现无关 Operation 摘要变化，应先定位，不以“只是元数据”忽略。

core 与两个受影响插件作为匹配安装集合发布。数据库、VM runner 和执行协议不变，不要求重跑求解器。现有旧失败分析保留 failed/recovery_pending，未经完整受控保全不传 draft_from，也不修改旧 Run。

安装后从管理绑定恢复原实例，使用原 plan_3、review_6、reviewed_package_2、execution_1 的精确产物和原目标。先调用 operation_preflight；通过后才 invoke 新分析并派发控制返回的角色。不得为了过门禁替换旧 plan/review、删去诊断证据或要求人重新审查原计划。

只有新 Run 在控制层 completed、封存有限分析可读取，且上述资格/来源负例保持，才算本缺陷闭合。preflight 通过、Worker 自称完成或静态审查 PASS 均不能单独作为线上完成依据。若仍拒绝，保留具体原因定位，不原样重试。

## 7. 审查意见闭合与范围约束

| 意见 | 本版具体处置 |
| --- | --- |
| HSP-1 下一道当前审查门禁 | 两个分析的 plan/review 使用历史材料用途；补原结构与精确独立审查身份检查，贯通至 submit |
| HSP-2 审批受到历史 pass 影响 | 输入事实与 ApprovalSubjectSnapshot 当前条件分别取值，保留原资格 projector 行为并作两类申请对照 |
| HSP-3 非通过历史记录收紧 | 明确 claim 与背景的不同结果，复用原规则，不增加科学禁令 |
| HSP-4 公共 helper 扩散 | 不改公共默认值、执行审批或全局 prior_signal，仅修改实际输入构造和必要消费者 |

范围上限为三个生产文件及其必要测试/身份/证据文档。本版不因发现相邻问题而顺手重构。若实施证明无法在既有机制内维持以上边界，先记录具体缺口再修订计划，不能偷偷添加新规则体系或缩减验收。
