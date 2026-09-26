# Root 上下文边界修复计划独立 SOL 审查（2026-09-21）

结论：**需修订（NEEDS REVISION）**。

审查对象为 `docs/plans/ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_20260921.zh-CN.md`，审查时 SHA-256 为
`c7c1205e52b591cf6e4c5ba677a475938c8ed2c63e9e1c1eddf87247def1639c`；与任务指定哈希一致。规划基线
`docs/plans/evidence/root-context-boundary-remediation-20260921/plan-baseline.json` 的 SHA-256 为
`3147c025834afccff67949df29587af22b67f481cee6292927ef6365ccc2d1f0`。该 manifest 所列生产源码、指南和架构文件的当前哈希均与其中记录一致，审查期间未发现基线漂移。

本轮只做静态、只读跨边界审查，没有运行模型、solver、科学 Operation、Fig4 流程、部署或测试，也没有修改计划或生产代码。唯一新增文件是本报告。

## 1. 已成立的设计方向

计划的总体切分是正确的：`CompiledCatalog` 继续作为唯一调用权威；Run/Artifact/Approval/Execution 状态机和准入逻辑不变；控制层只投影机械事实，Root 保留动作选择和科学判断；完整合同、原始 payload、父链、诊断和恢复入口继续存在。`run_status` 的 poll/navigation/decision 分流、即时 producer inputs、同一编译合同的 invoke 视图以及最后才更新安装指南，均能复用现有边界，不需要新摘要 Agent、第二合同表或 lineage 状态机。

计划也正确区分了确定性字符重放和真实模型行为验收。真实 A/B 明确要求同模型、同推理档、同初始历史、同输入和同阶段终点，并分别报告逐请求 input、峰值、净增长、请求数、output/reasoning、cache 累计与 compaction；没有用 cached input 累计值冒充上下文改善，也没有预先承诺降幅。

以下缺口会使实施者无法同时满足计划自身的不变量，须在实施前修订。没有 P0 级发现；有三项 P1 阻断和两项 P2 补强。

## 2. P1 阻断项

### P1-1：`run_status` 精简路径没有闭合失败诊断与 `view` 组合语义

计划第 63–77 行定义 profile，但没有规定非 compat profile 与 `view="detail"`、`diagnostic_after`/`diagnostic_limit` 的合法组合和最终响应语义。当前调用链中，`RootMCPRouter._call_tool` 在进入 route 前移除 `view`，而 `root_response` 对 detail 直接返回 route 结果；如果实现者分别理解“detail 总是 full”和“profile 先延迟组装”，同一请求会得到相反行为。计划第 75、83 行的“detail/full 保持”只能明确适用于 `response_profile="compat"`，否则 compact profile 可能静默退化为全量响应。

更关键的是，“exact failure reason，以及诊断目录或恢复可用性的短状态”没有可执行字段定义。现有 `RunService.diagnostic_summary` 保存 `failure`、`latest_rejection`、`latest_tool_error`、`recent_errors` 和 `rejection_count`；显式 `diagnostic_after` 才返回带 `next_after` 的 durable events，其中可能带 `engineering.reference`，再由 `diagnostic_read` 精确读取。只保留 `reason` 或一个未定义的“诊断目录”不足以解释 output rejection、tool failure、framework failure 和恢复失败。

最小修订：

1. 增加一张规范字段矩阵，并声明只有 `compat + detail` 保留现有 full 行为；`poll/navigation/decision` 要么禁止 `view="detail"` 并给精确校验错误，要么明确 detail 不扩展 profile。两种做法择一。
2. `poll` 和未完成/失败的 `decision` 至少保留 Run 的 operation id/version/digest、state、deadline/completed、exact `reason`、`recovery_available`、`sealed_output_status`、`scheduler_signal_status`，以及当前 `diagnostic_summary` 中能够定位失败的安全字段。
3. 明确 `diagnostic_after` 在 compact profile 中仍合法，返回原有 `events/next_after`；保留事件内现有 `engineering.reference` 和 `diagnostic_read` 原访问方式。不要把 native/tool/recovery 全详情重新放回常规 poll。
4. 对 queued/running/completed/failed/timed-out、output rejection、tool failure、framework failure、带/不带 diagnostic page 建 golden 响应；验证精确诊断不丢、科学 payload 未完成时仍不可见。

对应现状：`mcp_root.py::RunStatusInput`，`mcp_root.py::RootMCPRouter._call_tool`，`mcp_root_run_routes.py::RootRunRoutes.run_status/_run_status_value`，`mcp_response_views.py::run_summary/root_response`，`runs.py::RunService.diagnostic_events/diagnostic_summary`。

### P1-2：producer 投影指定的数据结构无法承载计划要求，历史和实例边界也未闭合

计划要求输出冻结的 Run `artifact_name/source_name`，同时指定 `ProducerOutputFamily.producer_inputs` 为“唯一端口映射结构”。当前该字段的类型仅为 `tuple[tuple[str, ArtifactRef], ...] | None`，只能保存 port 和 ref，不能保存 item index、`artifact_name` 或 `source_name`。若 `artifact_catalog` 再单独拼一次 `RunStatus.inputs`，就形成计划禁止的第二套映射；若不拼，则无法满足响应合同。

当前 `_run_output_family` 还有两条与计划历史语义冲突的路径：Operation id 在当前 catalog 缺失时立即返回 `None`；当前 catalog 有同名 Operation 时没有先比较 version/digest，就用当前 spec 解释历史输出。后者不仅是“合同缺失”，同名新 digest 也可能误解释旧端口。`RunService.completed_for_output` 本身按 exact ref 全库查找且不按 instance 过滤，因此在当前 instance 绑定了另一 instance 产生的相同 Artifact 时，还必须定义冻结 semantic name 的可见边界。

最小修订：

1. 明确提取一个共用内部 producer 投影记录（或扩展 `ProducerOutputFamily` 的输入成员），单项至少包含 `port_name`、稳定 item index、exact ref、可选 frozen `artifact_name/source_name`。approval family 与 `artifact_catalog` 都从该记录派生，不再各自 join/猜测。
2. Run 分支先以 `completed_for_output(ref)` 和 `status.output_ref == ref` 证明 exact producer，再直接从冻结 `RunStatus.inputs` 形成端口记录。只有 current compiled Operation 的 id/version/digest 全部匹配时，才用当前 spec 补充/验证合同信息；缺失或 digest/version 不同一律标 historical/unavailable，仍返回冻结 port/ref，不借同名新合同解释。
3. 明确 instance policy：只用当前 instance 的 bindings 计算 `current_access_name`。若 producer Run 属于另一 instance，至少不能暴露该 instance 的 semantic `artifact_name`；计划应选择将 frozen names 置 null 或把 producer 标为 cross-instance unavailable。不可把另一 instance 的名字当成本实例可访问入口。
4. transform 分支必须把 `_transform_input_groups` 的唯一解实际写入同一个 producer-input 记录；合同缺失、digest/version 不同或多解时返回计划所列 unavailable reason，并保留 parents fallback。
5. 测试同时覆盖“同 id 新 digest”的历史 Run，而不只覆盖 catalog 中完全无 id 的历史 Run；验证 read path 零写入、分页稳定和 cross-instance 名称不泄漏。

对应现状：`operations/invoke.py::ProducerOutputFamily`，`mcp_root_operation_routes.py::_run_output_family/_transform_output_family/_transform_input_groups`，`mcp_root_instance_routes.py::artifact_catalog`，`runs.py::RunService.completed_for_output`，`run_records.py::RunInputBinding/RunStatus`。

### P1-3：invoke 视图仍遗漏真实准入规则，且 digest 与 full 字节兼容要求互相矛盾

计划第 112、116 行要求所有会改变合法调用的字段和 review/revision 一致性都可由 invoke 视图解释，但当前保留字段清单没有 revision policy。`SchedulerOperationView` 也没有 `ReviewSpec.max_revisions` 或“新 change request 必须产生 progress”的机械声明。实际 `_validate_revision_policy` 会据此拒绝 `revision_limit_reached`、`revision_progress_unavailable` 和 `revision_no_progress`。只投影 `review_edge`、`requires_independent_review` 和 `requires_human_approval` 仍会留下计划试图消除的隐藏拒绝要求。

此外，当前 `SchedulerOperationView` 没有 Operation digest。计划一方面要求把 digest 加入当前 catalog item，另一方面要求 `full/default` 字节兼容；新增 digest 必然改变 full/default 响应字节。第 162 行允许“明确新增 additive Schema”，与第 114 行的字节兼容表述冲突，实施者无法同时满足。

最小修订：

1. invoke 视图增加同源的 `revision_policy`，至少暴露 `max_revisions`、是否要求相邻 change request 有可验证 progress，以及适用的 revision-base/change-request 端口。组件实现标识和 fingerprint 结果无需暴露，但对应拒绝必须能映射回这个规则。
2. 明确 digest 方案二选一：推荐从同一 `CompiledOperation.digest` 向 scheduler catalog/full 增加 `operation_digest`，把兼容条件改为“除该明确 additive 字段外语义兼容”；或者让 invoke projector 接收 full item 与同一 compiled digest 的内部二元输入，同时 full 保持原字节。不得在 MCP 层重算 digest。
3. 全 catalog 一致性检查不仅比较 ports/input admission，还要枚举真实 `_prepare_operation_call` 准入来源，证明 currentness、cohort/approval、complete producer family、review、revision policy、attempt/runtime applicability 的每个可修复拒绝都能定位到 invoke 视图或统一 `operation_invoke` 接口 Schema。generic 请求字段（`on_conflict`、`execution_profile`、`max_attempts`、`resume_from`、`draft_from`）继续由已描述的 interface contract 承担，不复制进每份 Operation。
4. 正向 invoke 验证限于无外部 side effect 的代表性 fixture；所有 public Operation 用纯编译一致性检查覆盖。Effect/approval 的 gate 用 preflight/拒绝 fixture 证明，不能为了合同测试提交外部执行或代替 UI 审批。

对应现状：`spec.py::SchedulerOperationView/scheduler_operation_view/ReviewSpec`，`mcp_root_operation_routes.py::_operation_catalog_item/_validate_revision_policy/_prepare_operation_call`，`mcp_response_views.py::operation_detail`，`mcp_gateway.py::UnifiedMCPRouter.describe`。

## 3. P2 补强项

### P2-1：确定性 replay 需要先冻结可执行输入，而不只是分类统计

计划第 50、158 行称使用“已保存的请求/响应元数据”和“同一份保存输入”运行旧/新投影。现有 `root-context-independent-sol.json` 保存的是 usage、字符分类、字段字符数、16 个 run-status 元数据和 20 个最大增长步；它没有保存可传给新 projector 的完整结构值。原生 trace 有完整响应，但文件在会话目录中继续增长，plan-baseline 也没有绑定目标窗口的 byte/response identity 哈希。因此当前证据足以复算旧统计，不足以单独执行 old/new projector 语义重放。

最小补足：P0 明确先从指定时间边界流式提取仅 P1-P3 所需的结构化响应 fixture，按 response id 去重，逐项保存 canonical SHA-256、来源时间和字段保留/脱敏清单；科学 selected values 可置于受限临时证据文件，仓库只保存哈希和机械投影，不能导出完整 transcript、隐藏思维或凭据。若不用真实值而改用合成 fixture，则只能声称结构/golden 兼容，不能声称“同一保存输入”的样本字符收益。重放报告必须同时绑定脚本哈希和 fixture manifest 哈希。

### P2-2：默认 compat 下，实际采用新路径要成为显式行为验收

P5 已列出 `roles/scheduler*.md`、`src/scidiscovery/platforms/codex.py`、安装指南和实际 runner 探针，方向足够；但“指南文件已安装”不能证明 Root 实际选择了非默认的新参数。真实 A/B 中应额外报告调用采用率：所选 Operation 的 describe 是否为 `view="invoke"`，必要 polling 是否为 `response_profile="poll"`，未知结构才用 navigation，完成决策是否一次使用 decision。每次退回 compat/full 都记录触发原因和正文字符。若新路径没有被实际调用，不能把字符或模型差异归因于本计划。

安装测试还应断言实际生成的 `AGENTS.md` 已把“selected complete contract”改为 invoke-first，并且 `.codex/scidiscovery-guides` 的 results/inputs/domain-analysis 与运行入口返回的新 Schema 同一版本；隔离 wheel 通过仍不能代替常驻 runner 的只读 contract probe。计划已有相应文件和部署顺序，只需把这些判定写进 P5/6.2 的通过条件。

## 4. 最小一次修订清单

planner 无需重写整体方案。一次修订补齐以下五点即可重新送审：

1. 为 run-status profiles 增加 profile × view × diagnostics 的合法组合和字段矩阵，明确 exact diagnostic event/reference 的保留方式。
2. 把 producer input 共用内部记录写实，补上 source/artifact name 的承载方式、同 id 异 digest 的历史规则及 cross-instance 名称策略。
3. 在 invoke 视图中加入 revision policy；解决 operation digest 与 full/default 字节兼容的二选一矛盾。
4. P0 先生成绑定 response identity/hash 的可执行 replay fixture manifest，区分真实样本重放与合成 golden 测试。
5. 将新 profile/view 的实际调用采用率加入安装后行为验收和真实 A/B 报告。

这些修订不要求新增状态机、改变 Operation/Artifact/Run Schema、递归 lineage、弱化独立 review/approval/recovery/currentness，也不要求在计划审查阶段运行真实模型。修订后若上述字段和边界闭合，当前分批顺序和最小源码范围可继续使用。
