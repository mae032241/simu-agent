# Root 上下文边界修复计划（2026-09-21）

状态：**R2，待独立复审的主动计划**。R1 已回应 `ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_SOL_REVIEW_20260921.zh-CN.md` 的五项最小修订；R2 仅回应 `ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_R1_SOL_REVIEW_20260921.zh-CN.md` 剩余的 compact recovery P1，尚未获得复审通过。本文不是实施记录、独立复审结论或收益验收报告；本轮没有改生产源码、安装、部署，也没有运行模型、solver 或任何 A/B。

## 1. 决策与证据边界

本计划针对长科研链中 Root 请求上下文持续增长。独立记录显示同一轮共有 150 个请求，输入 token 从 59,357 增至 138,089，净增 78,732；前 149 个响应自身输出合计 21,909 token，其中 reasoning 2,718。剩余 56,823 是工具正文、child/user 消息和平台序列化等合并边界，不能归因成单一“工具 token”。可见工具正文中，`run_status` 为 48,094 字符，9 份不同合同为 44,363 字符，6 份指南为 22,931 字符，11 次父链导航为 19,591 字符；44 次 `wait` 仅 2,139 字符。没有重复 describe 同一合同，也没有 preflight 后又 invoke 的重复准入。

因此修复对象是**合法调用所需信息的确定性读投影**，不是削弱科学合同。先缩减重复状态、过宽合同和多跳父链，再用同边界测量判断是否需要更深的 Schema 改动。既往短路径验收没有覆盖这条长链，本问题不定性为既有功能回归。

证据优先级如下：

1. 原始 trace 派生的 `root-context-independent-sol.json` 及可复现脚本；
2. 独立分析 `ROOT_CONTEXT_INDEPENDENT_SOL_ANALYSIS_20260921.zh-CN.md`；
3. `ROOT_CONTEXT_FINDINGS.zh-CN.md` 与 `OBSERVATIONS.zh-CN.md` 作为同轮观察记录；
4. 源码、编译声明、安装入口与指南只解释机制，不反推未测的模型收益。

规划时基线记录在 `docs/plans/evidence/root-context-boundary-remediation-20260921/plan-baseline.json`：分支 `refactor/m7-pre-e5.2`、HEAD `943c4626f8490530e9318eb9fbb409d2670908b9`、dirty 条目 365。该 manifest 只标识本计划实际阅读的字节；它不是完整回滚包。实施者必须在首次编辑每个相关文件前保存其字节快照或相对当前 dirty 内容的 binary patch，禁止用 `git checkout/reset` 覆盖其他人的修改。

## 2. 不变量

以下行为必须在每批变化中保持：

- `CompiledCatalog` 仍是唯一 Operation 调用权威；不得产生第二份合同注册表、第二调度器或新生命周期状态。
- Root 仍能读取绑定的总体目标原文及其精确引用。投影不得把 `research_objective`、`objective` 或等价声明端口从可调用合同和 producer 输入中删掉。
- Worker 继续拥有科学结论；Root 只选择动作、绑定原件并读取完成结果。投影函数不得选择“最佳”科学字段或解释结论。
- Run 输入冻结、instance 绑定、currentness、独立 review、human approval、side effect 和 recovery gate 的准入逻辑不变。
- full/detail 读取继续可用；默认请求保持兼容。历史对象可读不等于资格恢复。
- exact error、missing/null/empty、omitted children、分页游标和 original access path 必须显式保留。页面截断不能证明不存在。
- producer 投影只展开**即时生产者输入**，不递归遍历图、不自动选目标、不自动绑定、不写数据库。
- pending `fig4_retardation_execution_20260921_1` 及其审批、实例和科学对象不属于实施或验收夹具。

## 3. 现状根因映射

| 根因 | 当前符号/边界 | 计划变化 | 默认与兼容 |
|---|---|---|---|
| poll、目录导航、决策读取共用过宽 `run_status` | `RunStatusInput`；`RootRunRoutes.run_status`；`mcp_response_views.run_summary` | 增加显式读目的并按目的组装/投影 | 默认 `compat` 保持现有响应；full/detail 仍可取全部 |
| `run_status(output_paths=[])` 仍重复 signal、bindings、native/recovery/timing | 同上 | `poll` 只返回状态必需字段；`navigation` 不返回 signal；`decision` 只返回选中原文和一次 signal | 既有 `output_paths=[]` 无显式目的时字节兼容 |
| exact producer 的冻结端口已在 Run 中，但目录只给平面 parents | `RunStatus.inputs`；`RunService.completed_for_output`；`_run_output_family`；`_transform_output_family`；`_transform_input_groups`；`artifact_catalog` | 增加即时 producer 输入投影，复用现有 producer-family 推导 | `parents/detail` 保持；无 producer、历史或歧义显式降级 |
| describe 从同一 catalog 返回包含执行器权限等非调用字段的完整详情 | `DescribeInput`；`UnifiedMCPRouter.describe`；`operation_detail`；`SchedulerOperationView` | 从同一完整字典派生 `invoke` 视图 | 默认 `full` 不变；interface describe 仍是完整接口 Schema |
| Root 还承担 UI/计量排障和工具正文打印 | scheduler guide、调度运行规范 | 把原始 trace/UI 排障移出科研 Root，只回传固定度量摘要或证据路径 | 不新建产品协议或控制状态；不是主要产品修复替代物 |
| output index 仍可能重复目录 | output 声明、run_status index | 仅在前三批实测后再决定 `decision_paths` | 无数据则不改 Schema |

## 4. 分批实施

### P0：冻结候选差异与建立可比较测量

实施开始时创建独立证据目录。记录 HEAD、dirty status 的 hash/条数、所有待编辑文件的 before hash，并保存能恢复当前 dirty 字节的快照或 patch。每批只把该批文件列入 candidate diff；记录 `git diff --check`、after hash 和逆向检查结果。回滚按该批快照恢复，绝不重置整个工作树。

现有 `root-context-independent-sol.json` 只有分类统计与少量 run-status 元数据，**不能直接执行新旧 projector 重放**。P0 必须先冻结可执行输入：从原生 trace 的明确起止 response id/时间窗口流式提取仅 P1-P3 需要的结构化 MCP 请求和响应，按 response id 去重；fixture manifest 逐项记录 canonical JSON SHA-256、来源 response id/时间、Operation/接口版本，以及保留、置空和脱敏字段清单。原 trace 的目标窗口 byte hash、提取脚本 hash、fixture manifest hash 和 replay 脚本 hash 一同记录，防止继续增长的会话文件改变样本身份。

fixture 不得纳入隐藏思维、凭据、child chat、工作区路径或无关 transcript。若 selected scientific values 是验证 exact projection 所必需，只放在访问受限的临时证据文件，仓库 manifest 保存 hash、Schema 和机械投影；临时文件位置、权限、销毁时点写入 manifest。若安全边界不允许提取真实值，则改用合成 fixture，并明确它只能证明结构/golden 兼容，不能声称“同一保存输入”的样本字符收益。

只读、确定性的 replay 输入上述冻结 fixture，输出每次请求的请求序号、fixture identity、可见工具字符、响应 output/reasoning、首次/末次/峰值输入、净增长和请求数。初始历史、累计输出、cached token 与当次输入分别报告；跨 compaction 的段不得拼成一个虚假的连续净增长。该 replay 只比较投影字节和语义身份，不能宣称真实模型行为收益。

同时约束验收线程：UI、meter、wrapper 诊断在独立非科研线程进行；Root 只收到固定字段摘要或证据路径。这个约束减少任务混入，但不得替代 P1-P3 的产品边界修复。

### P1：`run_status` 目的投影

在 `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` 的 `RunStatusInput` 增加：

```text
response_profile = "compat" | "poll" | "navigation" | "decision"
default = "compat"
```

它是请求时读投影，不持久化到 Run。组合规则在接口 Schema 和校验错误中写清：

- `poll`：仅与 `output_mode="values"`、`output_paths=[]` 一起使用；
- `navigation`：与 `output_mode="index"` 使用，可带目标 path、offset 和 limit；
- `decision`：与 `output_mode="values"` 和一个或多个明确 `output_paths` 使用；
- `compat`：完全保持当前组合与默认行为。

组合规则如下；`RootMCPRouter._call_tool` 必须在移除 `view` 前校验，`root_response` 再做防御性校验：

| profile | 合法 view | output 组合 | diagnostics | 响应字段 |
|---|---|---|---|---|
| `compat` | `summary`、`detail` | 完全保持当前规则 | `diagnostic_after/diagnostic_limit` 保持当前规则 | 当前 summary/detail；只有 `compat + detail` 表示 full |
| `poll` | 仅 `summary` | `output_mode="values"` 且 `output_paths=[]` | 可选；请求时附加原有 `events/next_after` | 下述 compact lifecycle/failure 字段，不含科学 payload/signal 正文 |
| `navigation` | 仅 `summary` | `output_mode="index"`，可带 path/offset/limit | 可选；请求时附加原有 `events/next_after` | compact lifecycle + exact index/origin/missing/omitted/paging |
| `decision` | 仅 `summary` | `output_mode="values"` 且 `output_paths` 非空 | 可选；请求时附加原有 `events/next_after` | completed 时 selected values + 一次 signal；其他状态仅 lifecycle/failure |

任何 non-compat profile 与 `view="detail"` 组合均返回稳定的精确校验错误，不允许 detail 把 compact profile 静默扩成 full。`diagnostic_limit` 沿用现有上下限和游标规则；省略 `diagnostic_after` 表示 compact status **不返回 events**，显式 `diagnostic_after=0` 才读取第一页，后续使用返回的 `next_after`。

在 `mcp_root_run_routes.py::RootRunRoutes.run_status` 按 profile 延迟组装，而非先计算完整对象再丢弃。所有 compact profile 的共同字段为 name、operation id/version/digest（历史记录没有某项时为显式 null/availability，而非套用当前同名 Operation）、state、deadline/completed/finished、exact `reason`、`recovery_available`、`sealed_output_status` 和 `scheduler_signal_status`。失败或未完成状态还保留当前 `diagnostic_summary` 的安全定位字段：`failure`、`latest_rejection`、`latest_tool_error`、`recent_errors`、`rejection_count`。所有 failed compact 响应另保留 `compact_recovery_status`：从现有 control recovery record 机械投影 `delivery_preserved`、`resume_available`、`draft_available`、`recovery_pending`、条件性的 `original_retained`，以及受控 `reason_code`；不返回 coverage、tool evidence、draft、文件、路径或完整 recovery detail。

`reason_code` 只允许现有 recovery code 枚举中经安全审查的机械值，包括 `snapshot_unavailable`、`contract_unavailable`、`writers_unconfirmed` 等；未知值映射为稳定的 `other`，不得透传自由文本。需要原始控制诊断时，沿用既有、受同一访问控制的 `run_status(response_profile="compat", view="detail")` 入口按需读取，并遵守不打印 draft、路径或工作区内容的输出规则。该投影不新增 recovery 状态、算法或数据库字段。其上：

- `poll` 不携带完整 `scheduler_signal`、`bound_inputs`、native execution、tool timing 或 recovery detail。
- `navigation` 返回上述状态、exact `output_index`、origin、missing/omitted/next_offset 和 signal availability；不返回 signal 正文。
- `decision` 只有在同一响应明确为 `completed` 时返回 exact selected values、pointer/origin、missing/omitted/paging，加一次完整 `scheduler_signal`。失败或未完成只返回上述 lifecycle/failure 字段，不泄露未封存科学内容。
- `compat` 经过现有 `_run_status_value`、`run_summary` 和 detail 路径，保持当前字段与字节语义。

显式请求 diagnostics 时，compact profile 追加现有 durable `events` 和 `next_after`，事件中的 `engineering.reference` 原样保留，并继续通过 `diagnostic_read` 精确读取原件。常规 poll 不展开 native/tool/recovery 全详情。output rejection、tool failure 和 framework failure 须能由 summary + event/reference 定位；没有 diagnostic event 的 recovery failure 由 `compact_recovery_status` 的 gate 与受控 `reason_code` 定位，必要时才走上述 compat detail 入口。

在 `mcp_response_views.py` 增加按 profile 的纯投影函数，并由 `root_response` 调用。接口层校验非法组合，route 保留防御性校验；两处共用一个枚举/规则源，避免漂移。不得更改 SchedulerSignal Schema、sealed payload、Run state、recovery state 或诊断存储。

P1 正反例：

- 正：queued/running 的 `poll` 不含 signal 正文；completed 的 `decision` 在一次响应中含 selected output 与一次 signal；unknown structure 的 `navigation` 可分页后转 exact decision。
- 负：`poll` 加非空 paths、`navigation` 加 values、`decision` 加空 paths、任一 compact profile 加 detail 均返回精确校验错误；failed/timed_out 不被当成 completed；missing 与 omitted 保持不同。
- 兼容：旧客户端不传 profile 时，`output_paths=[]` 仍有当前 `bound_inputs`/signal 行为；`view="detail"` 的 full path 不变。
- golden：queued/running/completed/failed/timed_out、output rejection、tool failure、framework failure分别覆盖省略 `diagnostic_after`（无 events）、`diagnostic_after=0`（第一页）和后续 page；另覆盖 `recovery_pending=true`、draft preserved 但 resume unavailable、`writers_unconfirmed`、`snapshot_unavailable`，证明 compact 与 compat 对 recovery gate 的判读相同，同时 exact event/reference 不丢、未完成 payload 和 recovery detail 不可见。

### P2：即时 producer 端口投影

在 `ArtifactCatalogInput.view` 增加 `producer_inputs`。继续使用既有 parent_offset/parent_limit 作为 lineage view 的分页参数，避免再造一组游标。

实现必须先在 `operations/invoke.py` 定义一个共用的内部 `ProducerInputProjection`（名称可等价），单项至少包含 `port_name`、稳定 `item_index`、exact `ArtifactRef`、可选 frozen `artifact_name` 和 `source_name`。`ProducerOutputFamily` 持有这组记录；现有 approval/admission family 从同一记录只取 port/ref，`artifact_catalog` 从同一记录生成读响应。两条路径不得分别 join `RunStatus.inputs` 或猜端口。

实现必须复用：

- `RunService.completed_for_output(ref)` 确定唯一完成 producer；
- `mcp_root_operation_routes.py::_run_output_family` 读取冻结 `RunStatus.inputs`；
- `_transform_output_family`、`_transform_input_groups` 和 invocation fingerprint 处理 transform；
- 扩展后的 `ProducerOutputFamily.producer_inputs` 作为唯一端口映射结构。

将 producer-family 推导提取为 Root routes 可共用的私有纯 helper，或在当前 mixin 中通过明确方法调用共用；不得在 `artifact_catalog` 复制另一套端口猜测。Run 分支先由 `completed_for_output(ref)` 且 `status.output_ref == ref` 证明 exact producer，再直接从冻结 `RunStatus.inputs` 构造共用记录，不依赖当前 catalog 才能返回 port/ref。只有 current compiled Operation 的 id、version、digest 全部与 frozen producer identity 相符时，才用当前 spec 补充或验证合同信息；catalog 无 id、同 id 异 version 或同 id/version 异 digest 均标为 historical/unavailable，不得用当前同名合同解释。

transform 仅在 producer id/version/digest 与 compiled declaration 相符、且 `_transform_input_groups` 得到唯一解时，把分组实际写入同一个 producer-input 记录；记录的 item index 是端口内稳定次序。输出最少包含：subject identity；producer kind、operation id/version/digest 和 availability；按端口和 item index 排序的 exact artifact refs；允许暴露时的冻结 Run `artifact_name/source_name`；当前 instance 中仍精确绑定 exact ref 的 `current_access_name`（否则 null）；schema/kind；以及具体 unavailable reason。

兼容/降级规则：

- Run 的历史 compiled contract 不在当前 catalog、或同 id 异 version/digest 时，仍按冻结 input port_name 返回输入，producer contract 标为 historical/unavailable；不得丢掉原 port 或借当前同名 Operation 解释旧 Run。
- transform 合同缺失或端口分组多解时返回 `producer_contract_unavailable` 或 `producer_input_mapping_ambiguous`，保留已有 `parents` 访问路径。
- imported/no-producer 返回 `producer_unavailable`；多 producer/corrupt lineage 保持现有 exact error。
- 输入已改名或解绑时，current access name 为 null，当前 instance 内 producer 的冻结原名仍可保留。若 exact producer Run 属于另一 instance，则 producer 标为 `cross_instance`，冻结 `artifact_name/source_name` 一律置 null；只允许当前 instance 对 exact ref 确有绑定时返回本实例的 `current_access_name`。不得泄漏另一 instance 的 semantic name，也不得用“最新同 schema”替代。
- `research_objective` 等总体目标端口与其他端口同等返回，现有公共 ref/read 保持。

P2 正反例覆盖 agent Run、多项端口次序、唯一 transform 分组、改名/解绑、另一 instance、imported/no-producer、catalog 无 id 的历史 Run、**同 id 新 digest/version 的历史 Run**、历史 transform、同 schema 多端口歧义、多个 producer、分页稳定和读操作零写入。父链 view 的现有顺序和 null 语义不得变化。

### P3：同一编译合同的 callable 视图

在 `mcp_gateway.py::DescribeInput` 增加 `view="full"|"invoke"`，默认 `full`。`UnifiedMCPRouter.describe` 对 Operation 仍先从 `operation_catalog(operation_id=..., view="detail", scope="all")` 取得同一完整权威对象，再调用 `mcp_response_views.py::operation_invoke_contract` 做纯投影。interface describe 只接受/返回 full；显式对 interface 请求 invoke 给出明确不支持错误。

`invoke` 必须保留所有会改变一次合法调用或其判读的字段：operation id/version/digest、scope/executor kind、purpose/applies_when/not_for、每个 input 的完整 schema/cardinality/nonnull/usage/exposure/current/media/byte限制、outputs、input admission/validation、complete transform family、consequence、review edge、独立 review/human approval、timeout、总输入上限、默认 attempts 和动态 runtime binding。还要从同一 `ReviewSpec` 派生 `revision_policy`：至少包括 `max_revisions`、相邻 change request 是否必须有可验证 progress、适用的 revision-base/change-request/progress 端口。组件实现标识和 fingerprint 值不外露，但 `revision_limit_reached`、`revision_progress_unavailable`、`revision_no_progress` 必须可映射到上述规则。仅移除调用请求无须使用的执行器 native/network/tool 权限、输出聚合资源上限和可选服务详情等执行说明。

digest 采用单一方案：从现有 `CompiledOperation.digest` 向 scheduler catalog/full item 增加 `operation_digest`，invoke 直接投影该值，MCP 层不得重算。兼容条件改为：full/default 除这个明确的 additive 字段外语义兼容，不再要求逐字节相同；旧字段、默认 view 和错误语义不变。invoke 视图不改变 `operation_invoke` 的准入、错误路径或 compiled declaration。

编译一致性测试遍历所有 public Operations和 `_prepare_operation_call` 的准入来源，证明 invoke 视图的每个端口、currentness、cohort/approval、complete producer family、review、revision policy、attempt/runtime applicability 和 consequence 都与同一 full item 或统一 `operation_invoke` interface Schema 一致。`on_conflict`、`execution_profile`、`max_attempts`、`resume_from`、`draft_from` 等通用请求字段只由 interface contract 描述，不复制进每份 Operation。再用最小正向 invoke 和缺必填、过 cardinality、stale/currentness、review 不匹配、revision limit/no-progress、approval 缺失等负例证明错误可定位；不得用手写期望列表形成第二合同。正向只使用无外部 side effect 的代表性 fixture；Effect/approval 用 preflight 或拒绝 fixture，不提交外部执行、不代替 UI 审批。

### P4：以证据决定是否加入 `decision_paths`

完成 P1-P3 的确定性 replay 后，先统计 navigation 的实际调用次数与正文，确认它是否仍是显著剩余边界。若已不显著，停止，不改 output Schema。

只有 matched replay 显示多个公共 Operation 仍因未知结构反复 index，且目标路径可由 plugin 作者静态声明时，才另立小批：在 OutputPortSpec/compiled projection 增加可选、经 JSON Pointer 校验的 `decision_paths`，纳入 Operation version/digest；更新相关 plugin 声明。历史 Operation 或未声明的输出继续 index/full。core 不根据字段名猜科学重点，Root 也不得把路径列表当成必填科学 checklist。该批需要单独设计复审，不与 P1-P3 同时合并。

### P5：最后裁剪指南并同步安装产物

只有接口和 focused tests 稳定后才更新：

- `roles/scheduler.md`：selected Operation 优先 `scid_describe(..., view="invoke")`，需要执行诊断时才 full；保留完整调用约束、独立 review、approval、recovery 和 instance 规则。
- `roles/scheduler/results.md`：poll/navigation/decision 各自一次读取；completed decision 同响应读取 exact values 与 signal；保留 error/omission/paging/original path。
- `roles/scheduler/inputs.md`：优先 `artifact_catalog(view="producer_inputs")` 恢复即时端口；失败原因指向 parents fallback，不递归全图。
- `roles/scheduler/domain-analysis.md`：用 producer_inputs 取得准确绑定，只有真实诊断才读 detail/native/recovery。
- `docs/ARCHITECTURE.md` 与 `.zh-CN.md` 同步规范事实；约束矩阵只在实际实现和独立复审后更新符合性，不预先宣称通过。

`src/scidiscovery/platforms/codex.py`、guide generation/install tests 与 `deploy/install.sh` 的安装副本/runner 检查必须同步。源码 guide 通过而已安装 `.codex/scidiscovery-guides` 未更新，不算完成。

安装后行为验收不仅检查文件存在，还检查新路径采用率：按 describe、poll、navigation、decision 四类分别报告 eligible 调用数、实际新参数调用数、compat/full fallback 数、每次 fallback 的精确原因和正文字符。selected Operation 应使用 `scid_describe(view="invoke")`；必要轮询应使用 poll；只有未知结构才 navigation；完成决策应一次 decision。存在无解释的 eligible compat/full fallback，或新路径根本未被调用时，不得把字符或模型差异归因于本计划。实际生成的 `AGENTS.md` 必须改为 invoke-first，安装的 results/inputs/domain-analysis guides 与运行入口 Schema 记录同一版本/digest。

决策语料处理：本文件登记为 active proposal；独立分析与原 trace 保持 scoped evidence/audit，不改写历史结论。旧计划只有在实现、验收和独立复审完成后才按实际覆盖范围标注 superseded/partially superseded。

## 5. 串行验证矩阵

所有工程测试逐批串行，通过 `scripts/compiled_worker_process_guard.py run_process_group` 执行，`768 MiB`、`sample_interval_seconds=.1`；不全量、不自动加预算。每批先 `git diff --check -- <exact paths>`，再运行以下最小集合，失败即停止该批并保存 exact command、exit、峰值 RSS 和日志路径。

| 批次 | 最小源码测试 | 跨边界/安装检查 |
|---|---|---|
| P1 | `test_run_status_output_selection.py`、`test_mcp_response_views.py` 中新增 profile 用例；`test_root_context_boundary.py` 的 live gateway 子集 | unified MCP 实际 call：poll/index/decision；queued/completed/failed/timed_out；default compat |
| P2 | `test_m6a_direct_instance_management.py`、`test_root_draft_routes.py` 的 producer/parents 子集；新增 historical/ambiguous/read-purity 用例 | 实际 Root façade 的 agent Run 与 transform；跨 instance 与 null access name |
| P3 | `test_unified_mcp.py`、`test_mcp_response_views.py`、`test_compiled_declaration_consumers.py` 的 describe/catalog 子集 | 构建后的 installed entrypoint `test_catalog_installed_entrypoint.py`：full/invoke 均由已安装包返回，非源码 import 假通过 |
| P5 | `test_scheduler_guides.py`、`test_platform_configuration.py`、必要的 deploy script 子例 | 临时 prefix 安装后读取实际 `.codex/scidiscovery-guides`；runner/服务若 vendored 包或常驻进程，重建/重启后再探针 |
| 文档 | `scripts/validate_architecture_constraints.py`（仅当该脚本支持 exact docs scope；否则对应定向测试） | EN/ZH 关键规范 parity，不改历史 audit |

测试 fixture 只证明确定性合同、兼容和边界，不证明真实 scheduler 会减少调用或模型 token。安装探针必须记录 wheel/package/version/commit、可执行入口解析路径和返回的 contract digest；隔离安装通过不能冒充正在运行服务已更新。若生产 runner 是独立 artifact、容器或 daemon，发布清单必须列出其构建和重启步骤，并在实际运行入口重复只读 contract probe。

每批需要一个未参与实现的跨边界复审者，检查 MCP Schema→route→compiled catalog/Run→response projection→guide/install 链路。复审通过前不合并下一批。回滚单位也是单批；接口字段均为 additive，先恢复 guide 使用，再恢复服务端新增投影，默认 compat 始终可接旧客户端。

## 6. 两层验收与通过条件

### 6.1 确定性投影重放

用同一份保存输入分别经过旧/新投影，逐请求比较：

- 操作、版本/digest、端口映射、目标 ref、review/approval identity、Run state、exact selected values 和 SchedulerSignal 内容相同；
- error/missing/omitted/paging/original access path 不丢失；
- compat/full 输出除 P3 明确新增的 `operation_digest` additive 字段外保持语义等价；
- 报告每类投影的字符数和调用次数，不换算或承诺模型 token 百分比。

任一科学对象身份、资格 gate 或错误可解释性变化即失败。只有 P1-P3 都通过后才进入安装验收。

### 6.2 真实模型 A/B（后续、需单独调度授权）

使用与基线相同模型和推理档、相同初始历史快照、相同用户输入、catalog 版本、隔离 instance/artifacts，并以同一科研阶段边界结束。至少做两对 matched runs，结束点可设为生成同一类待审批执行请求，绝不调用 solver 或批准 side effect。

每个 run 单独报告：请求数；每请求 input；首次、末次、峰值和净增长；output 与 reasoning；可见工具字符；cached/cumulative token；compaction 边界；最终 scientific object/review/approval identity 与 scheduler decision。另按 describe、poll、navigation、decision 报告 eligible/actual/fallback 采用率、fallback 原因和字符；没有实际采用新路径就不得归因收益。把 wrapper/JS 调试和 UI/meter 排查放在独立线程，不混入科研 Root。

真实 A/B 的通过条件不是预设百分比，而是：新链能完成相同阶段、没有增加违规调用或丢失 gate、matched 请求的上下文增长和/或请求数有可重复下降。差异若来自 cache、compaction、模型随机行为或不同科学路径，标为 unverified，不归因于投影。

当前 Fig4 请求不用于此 A/B。任何实例级工作先由交互式 Root 调用 `instance_current`；未绑定时只能给用户管理 URL，由用户页面选择/创建。审批只走 approval UI。

## 7. 完成定义与剩余风险

P1-P3、P5 的代码、编译声明、指南、隔离安装和实际 runner（若存在）都通过定向验证，独立复审没有 P1/P2，且真实 A/B 结果按上述边界记录后，本计划才可标记 implemented/accepted。P4 可以由数据明确判定“不实施”，不阻塞完成。

主要待决风险：

1. `response_profile` 的字段集合必须在实现时用现有客户端 golden responses 校正；默认 compat 是迁移安全线。
2. transform 历史记录可能缺少足够声明来唯一恢复端口；该情形必须显式 unavailable，并保留 parents，而不是猜测。
3. invoke 视图中哪些 runtime 字段实际参与准入需用所有 public Operation 的负例验证；发现会改变调用合法性的字段必须保留。
4. 常驻生产 runner 的构建来源尚未由本计划操作确认；安装验收需分别证明隔离包和实际服务版本。
5. 真实模型收益尚未测量；本文不承诺具体降幅，也不把 deterministic fixture 当成行为验收。
