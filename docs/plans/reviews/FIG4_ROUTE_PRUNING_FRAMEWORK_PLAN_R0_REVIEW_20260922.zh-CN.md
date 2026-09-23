# Fig.4 路线剪枝框架计划独立审查 R0

范围：只读审查 `FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_20260922.zh-CN.md`，并核对当前 Architecture、R5-N 调度权威、分析 Schema/validator、Operation admission、假设/实验身份、UI 安装入口及现有 token 测量能力。未修改计划或实现。

结论：**REVISE（仅限计划级）**。存在 3 项 P1 阻断。

## P1 阻断

### 1. `prune` 被提升为硬准入权威，但权威迁移与边界未闭合

位置：计划 §2、§3、§4、WP3；当前 R5-N 调度权威规范及 Architecture 的科学/控制职责边界。

可达场景：单个未独立审查的 Analysis Worker 输出 `prune` 后，所谓“同路线 continuation Operation”被 control 拒绝；但该 Operation 集合、数值修复、补证据和重新分析例外均未机械定义。错误科学判断可锁死路线，新增 Operation 又可能漏挂门禁，形成第二路由表。

影响：Analysis Worker 间接选择允许的后继行为，control 从身份准入扩张为科学路由权威，可能绕过 scheduler 或造成死锁。

修订要求：

- 明确该提案是否部分取代 R5-N；
- 不得建立全局“动作类别 → required_change”表；
- 每个受约束 Operation 必须在自身编译合同中显式声明所消费的 assessment、原策略输入和允许的机械关系；
- preflight/invoke 必须复用同一 input validator；
- 若 `prune` 具有硬阻断力，必须增加对该处置的独立科学复核及明确的重新开放路径；否则它只能作为 scheduler 决策输入。

### 2. branch/strategy、停止条件和“新证据”无法按当前对象机械判定

位置：计划 §4、§6、§9；当前 `cognitive.py` 的 hypothesis 对象、`experiment.py` 与 `experiment_intent.py`。

证据：现有计划的 `stop_conditions` 是字符串数组，没有 `stop_condition_key`；`evidence_keys` 是 Run 内 alias，不是 Artifact ref；`objective identity` 未定义；`strategy_key` 被安排在 skeleton、intent、portfolio 多个作者对象中。新 `strategy_key` 又自动放行，因此同一路线改 key 即可绕过剪枝。

影响：guard 既可能误拒合法重设计，也不能阻止改名绕过；control 若判断语义等价就会发明科学身份。

修订要求：

- 冻结唯一 owner，例如 branch 只由 hypothesis proposal 首次作者，strategy 只由独立审查后的 scientific skeleton 首次作者，下游只能机械复制；
- 新 key 本身不得放行，必须绑定精确旧对象和通过的独立审查；
- route fingerprint 使用精确 objective Artifact 身份；
- 停止条件升级为版本化 keyed 对象，或引用“计划 Artifact ref + JSON Pointer”；
- 新证据集合由冻结 Run 绑定/manifest 机械解析为 Artifact ref/digest，不能从 alias 猜测。

### 3. 新旧 Schema 与共享 handoff 迁移方案不成立

位置：计划 §3、WP1、§6、§9；当前 `layered_diagnosis.py`、`role_result.py`、`run_signal.py` 与两类 analysis 输出声明。

可达场景：当前生产者和消费者都精确使用 `scidiscovery.layered-diagnosis.v1`。在同一模型中把新字段设为必填会使旧 Artifact 不可解析；设为可选又不能保证新生产必填。若向共享 `RoleHandoff` 添加投影字段，其严格 Schema 会变化，并使所有 Agent 的输出合同与 Operation digest 扩散变化，而计划只讨论 analysis。

影响：历史读取、`prior_analysis` admission、资格和 installed catalog 可能集体漂移。

修订要求：

- 实施前冻结唯一迁移路线：新 schema id/version，或“共享读模型可选 + 新 Operation 专属 validator 必填”；
- 列出所有 producer/consumer 端口及并行读取期限；
- 不要把分析专属字段塞入全局 `RoleHandoff`；
- 优先直接从 sealed payload 的 `/continuation_assessment` 读取；若确需 signal 投影，应按 schema id 机械派生且不成为第二真相。

## P2 重要问题

- `invalid_study` 规则只禁止“因数值失败自动 prune”，尚未规定物理剪枝证据必须来自通过前置有效性门的当前证据，或明确独立有效的历史证据。需增加正反例，防止无效求解被包装成路线失败。
- UI 文件面不完整。`approval_ui/read_model.py` 目前多处精确匹配 v1，Run/Artifact/Approval 又经过 `workbench_render.py`、`render.py` 和 installed `scidiscovery.instance_views` 入口。WP4/WP5 应纳入这些入口、CSS、wheel 安装与真实浏览器负例。
- Fig.4 live 验收仍有迎合风险。“能够表达并执行 prune”应由确定性 fixture 验证；真实 Worker 对 Fig.4 返回 `continue/prune/defer` 均不得决定框架 PASS，只检查字段合法、证据绑定和调度边界。
- token A/B 尚不可按原文直接完成。Root 可用现有 App Server 原生逐请求 usage 探针测量；平台 `spawn_agent` / collaboration subagent token 当前不可观测。若 compiled Worker 使用独立探针，只能标为受控代理测量，不能冒充生产子 Agent。必须预先指定 telemetry 来源；不可观测项记录为“不可观测”，不得估算。

## 已核查路径

- R5-N / Architecture 调度与科学权威；
- `LayeredDiagnosis → finalizer → RoleHandoff → SchedulerSignal`；
- 通用/TCAD analysis validator；
- `preflight → guard/input validation → invoke`；
- hypothesis critic/revision；
- experiment/skeleton identity；
- instance view → read model → Run/Artifact/Approval UI；
- installed plugin entrypoint；
- 现有 Root token 探针。

## 残余风险

未执行测试、未验证部署实例；本 verdict 不评价任何未来实现。

独立 Reviewer token 用量：平台不可观测，未估算。
