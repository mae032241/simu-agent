# R5 E5.2：当前 Fig.4 阻断的最小修复计划

日期：2026-09-05
状态：最终独立计划复审 PASS；实施中；基线提交 `a6742b7`；P1 已通过并提交为 `322d281`；P2 已通过并提交为 `c7c692a`；P3 已实现并通过聚焦测试及 GPT-6 独立复审（0 blocker/high/medium/low）；P4 未实现。

本文是 [真实缺陷账本](R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md) 的 E5 有界返工计划。
采用 [当前架构](../ARCHITECTURE.zh-CN.md)、
[设计宪章](../architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md) 与
[33 项约束](../architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml) 的权威边界。
当前代码 `operations/spec.py::OPERATION_ABI_VERSION` 为 16；架构正文中仍出现的 ABI 15 是文档滞后，
不是本轮升级理由。本版保留 ABI 16，但 P2 必须把来源 Schema 投影版本纳入受影响 Operation digest，
不得再以 ABI 不变推导合同摘要不变。历史 Run、Artifact、E5.1 实现及审查原样保留，不继承其通过结论。

## 1. 决策：四个独立补丁，不再把五类问题当成一个大修

原计划方向有必要，但把缺陷绑定成 C0—C7 单一门链，并预设新增来源校验 helper、改 normalizer、
重建 objective 判别模型和全曲线 finding 分类，超过当前阻断所需。

建议按下表实施和审查。编号表示工程施工顺序，不是科研调度 DAG。

| 补丁 | 解决的问题 | 依赖与独立性 |
|---|---|---|
| P1：曲线定量语义 | confirmed coincident 共享支持、局部可能遮挡导致全曲线未决 | 两者在同一物化→验证→归一化路径中组成可验证结果，放在一起；不依赖核心合同修改 |
| P2：Run 可见来源合同 | 审查目标被隐藏排除、集合实际别名未进入可执行 Schema、投影改变未进入 digest | 合同身份与生成→assignment→submit 一起交付；不依赖像素算法 |
| P3：忠实性审查措辞 | 把忠实报告来源不足误判成 unknown | 独立的 prompt/semantic resource 补丁；不改 verdict 聚合、review edge 或资格策略 |
| P4：objective 条件 Schema | Schema 接受后置校验拒绝的 closure 组合 | 移出当前 Fig.4 批次，保留为独立计划内补丁；一文件修复，不借机改全部模型 |

P1—P3 是当前 Fig.4 主批次；P4 不进入其发行包，也不作为其交付或真实 E5 验收的前置门。
P4 的缺陷和验收仍留在本文，单独实施、审查、安装和关闭，不删除或宣称已解决。
P1—P3 通过后可分别记录主批次交付与 E5 验收；只有 P4 也有独立证据时本文才整体关闭。

## 2. 问题证据与现有可复用能力

本次核对了当前工作树代码、测试与账本；未查询或修改生产状态库，未重新作出科学审查结论。

| 缺陷 | 可到达的代码和现有测试 | 判断 |
|---|---|---|
| 共享引用被禁用 | `figure_digitization.py::_materialize_shared_support` 未传现有 `shared_eligible`；`_curve_csv` 因而排除复制行。`figure_evidence_validation.py::_validate_declared_shared_support` 在 coincident 分支还要求复制行 ineligible、eligible 总数至多 1 | 本地只读探针复用 `_coincident_overlap_request` 得到 6 个共享引用、3 个 eligible、3 个物理像素。前两项应变成 6/6，物理像素仍为 3 |
| 局部推测变全曲线失败 | `figure_digitization.py::_overdraw_findings` 只有 `build_digitized_figure_bundle` 一个生产调用者；结果并入 `findings` 后，`bool(local_findings)` 同时控制 CSV、manifest ambiguities、qualified count 与 overlay | 启发式没有独立展示或调试消费者；可以删除生成器和调用，不必增加 severity 或 blocking 表 |
| 可见来源与提交规则错位 | `run_assignment.py::result_schema_json` 只收 compiled；`run_outputs.py::validate_run_output` 已有精确 source-name→port 映射；`general_science_components.py::_evidence_audit_context` 私下排除两个固定目标名 | `InputPortSpec.usage`、`OutputPortSpec.evidence_paths` 已存在；既有 JSON Schema 执行入口足以承载别名 enum |
| 参数清单误标为来源 | `parameter_operations.py::EXTRACT_INPUTS` 把 required_parameter_checklist 标成 evidence_inventory；提取 prompt 明说它是约束而非证据，context checker 只让 source_catalog 对齐 source_material | P2 必须修正这一声明；`_parameter_qualification_document` 还从 evidence_sources 查清单，须在同文件改用既有精确父链，不能只改 usage 后宣称参数路径不受影响 |
| closure 组合隐藏规则 | `research_objective.py::ObjectiveClosureRequirement._subjects_match_type` 检查类型、非空与唯一性；生成 Schema 只声明普通数组 | 本地探针中默认 target_coverage 加 target_keys 与 comparison_purposes 通过 JSON Schema，却被 Pydantic 以 “target_coverage accepts only target_keys” 拒绝 |
| 忠实性与充分性混淆 | `general_science_resources.py::Resources.evidence_audit_semantic_contract` 把 missing support 与 fail/unknown 连写；图 `AUDIT_PROMPT` 未明确正确报告限制可以 pass；`_validate_audit_handoff_and_sources` 机械聚合任意 unknown 为 inconclusive | 要澄清 Worker 的比较对象；没有证据表明需要改聚合器或下游准入 |

现场账本及原 E5.2 记录另外给出：真实重合区间 [180,368) 有 188 个共享物理像素，
InAlAs 的 453 个直接像素被 12 个 possible_overdraw 一并降级；Audit 连续两次来源绑定拒绝。
这些数值是历史现场证据，不是本次重新运行结果。执行前从控制面冻结对应完整请求和输出，
不能仅以这段 prose 重建夹具。

必须保留的现有能力：

- `figure_evidence_normalizer.py::_quantitative_runs/_valid_intervals` 已按实际 eligible 行和 point_index
  连续段生成有效区间；它不按 support_kind 排除共享行。修好生产者后先验证，不改 normalizer。
- `RunService.submit` 已把 RunOutputError 作为可纠正 rejected，把 RunCheckerError 作为 failed；
  `SemanticRuleViolation` 已区分预期语义拒绝与程序故障，不重建异常分类。
- `operation_port_json_schema` 已同时服务 Worker schema 和 submit；利用这条共同入口。
- `_intake_split` 已机械复制 problem_frame/foundation；审查 pass 不会自行删除限制或创建人工资格。

### 2.1 审查意见裁决：保留前轮决定并处理最新 FAIL

| 上一轮意见 | 本版决定与理由 |
|---|---|
| P2 合同代际缺口是 blocker | 采纳。`catalog.py::_build_compiled_catalog.operation_digest` 只摘要 ABI、声明、可达组件声明/资源、权限和审查/批准依赖；`_resource_digest` 不摘要普通 callable 或 `operation_port_json_schema` 的实现。仅修改投影代码不保证摘要变化 |
| 改 ABI 17 或纳入投影版本 | 选择后者，拒绝本轮全局 ABI 17。ABI 是所有摘要的输入，局部来源投影不需要让无关求解、评分等合同一并退休；第 5.1 节规定唯一实现与影响范围 |
| 损坏 evidence_paths 必须 fail-closed | 采纳进 P2 正文与负测。`OutputPortSpec.issue` 仅检查 JSON Pointer 语法，catalog 目前也没有验证路径指向实际 evidence 数组；只拼 properties 可能产生永不触发的约束 |
| P4 uniqueItems 字段级、allOf 模型级，处理默认类型 | 判断正确，属于 P4 的局部实现要求，写入第 7 节，不增加补丁或全局 validator 工作 |
| 内存门应为 Codex 4 GiB、WSL 增量 8 GiB | 采纳，恢复账本 E5 的两种不同边界；原文“8 GiB 测试进程树”不能替代它们 |
| “0 新增抽象”应为“0 新公共抽象” | 采纳。私有拼装函数也是抽象，不能在允许它的同时宣称零抽象；第 9 节单独列公共面与私有函数上限 |
| P4 移出当前 Fig.4 批次 | 采纳。它修复独立结构缺陷；当前没有证据证明它阻断 Fig.4 的 P1—P3 回归 |

最新独立复审报告两个 blocker；下表是本轮依据源码作出的裁决，不代表复审已通过。

| 最新意见 | 本轮裁决与代码理由 |
|---|---|
| required_parameter_checklist 会错误进入来源 enum | 采纳 blocker；仅改 EXTRACT_INPUTS 的该端口为 prior_signal。`validate_extract_context` 保留清单科学字段一致性和 source_catalog 精确来源闭合；核心只按 usage 投影，不按端口名排除 |
| 对最小 usage 修正的消费者核对（本轮新增发现） | 单独修改 usage 不充分。Root `_run_output_family` 会把 prior_signal 排除在 evidence_sources 外，而 TCAD 资格 projector 正从此列表核对提取清单；必须同步在同文件以 package 的已封存有序 parent_refs 核对清单与来源。第 5.2 节列出精确影响、局部版本绑定和资格正负控；不扩大到其他 usage 清理 |
| 退役 queued/running 可用现有显式失败命令收口 | 采纳 blocker，删除承诺。`record_failure` 在 seal 和 UPDATE 前调用 `_compiled`，摘要变化时抛 RunStateConflict；状态仍为 queued/running。本轮只如实记录并负测，不修生命周期 |
| 投影构造/绑定一致性异常应为 RunCheckerError | 采纳。当前 `_validate_payload_schema` 只包装 jsonschema 模块异常，普通 ValueError 等会外逸；P2 在现有调用点包装投影构造与绑定故障，正常 enum 不匹配仍为 RunOutputError/rejected，不新增异常类型 |
| 完整 operations/artifact_agent 串行回归 | 采纳。中央合同影响所有 Agent 输出入口；聚焦反例之后必须串行跑完整两个目录，沿用 Codex 进程树 4 GiB、WSL 常驻增量 8 GiB 门。回归范围不等于科学语义证明 |
| 保留旧 overdraw 距离字段，弃用且忽略 | 采纳。`figure_digitization_contract.py::FigureLineTracking` 属于请求 v2，当前唯一算法消费者是待删的 `_overdraw_findings`；移除字段会令 extra=forbid 拒绝旧合法请求。仅在原字段说明中标明兼容保留、弃用且忽略，不建弃用机制 |
| ABI16、选择性投影 digest 与 P1/P3/P4 边界可保留 | 采纳。上述修正没有改变 OperationSpec 形状或组件协议；保留第 5.1 节方案与 P1—P3 主批次/P4 独立边界，只另记必要领域声明和版本的实际摘要影响 |

代际问题可到达：`RunService.schedule` 把 `operation_digest` 和 `inputs_json` 写入 Run/request，
再用 `result_schema_json(compiled)` 物化工作区；`LocalTrustedBackend.open` 复用已有目录，不刷新 Schema。
服务升级后，`RunService._compiled` 只比 operation version/digest，`_validated_candidate` 和
`run_outputs.py::_validate_payload_schema` 则调用当前投影代码。若摘要未变，旧 running Run 的旧 Schema
与提交规则可以不同；failed Run 的 `_recovery_digest` 也只核对摘要和输入，不能识别这次行为变化。
P1/P3 的资源改动可能顺带改变部分摘要，但不能替代 P2 自身的代际保证，尤其是未改资源的插件合同。

## 3. 不变量与非目标

冻结以下行为，不能用“简化”削弱：

1. 只有经独立身份、两侧直接锚点、成员贡献、逐列联合覆盖和距离检查确认的 coincident_overlap，
   才允许双方引用同一真实像素作各自曲线的定量支持。共享不等于统计独立。
2. 每个成员继续受自己的 default_eligible、检测下限与显式排除区间约束。
   strict overdraw 的被遮盖复制行仍不可定量，旧 covered_eligible 字段不获得新权限。
3. 曲线引用计数允许重复；同一来源像素的全局计数去重。保留 shared_group、ownership、
   source series、原始/亚像素坐标及不确定性，不插值、不平均、不伪造隐藏像素。
4. 真实身份、种子、整体跟踪或声明共享合同失败继续阻断。局部提示消失不删除真实 gap。
5. 普通结构规则由同一 JSON Schema 执行；跨输入/跨字段科学语义留在少量已绑定 checker。
   预期不合格返回已有 rule_id 和字段路径；程序异常终止 Run。
6. Artifact、父链、旧 revision、审批和收据不可变；新合同或内容不继承旧审查、资格或批准。
   exact family、currentness、review 和人工批准仍由原控制面负责。

不新增 OperationSpec 字段、ABI、Registry、规则 DSL、数据库实体、Run 状态、资格体系、MCP 或公共工具。
不修改 UI、TCAD 求解/物理代码、执行器、恢复、部署协议、强隔离或全仓 validator。
TCAD 参数侧仅允许 P2 已证明的提取清单 usage 和同文件资格父链核对修正，不清理其他端口用途。
不建立跨曲线 covariance/权重统计模型，不通过降低阈值、缩成无科学意义的小片段来凑通过。
不迁移旧数据，不改写历史审查，也不在本计划中关闭 33 项约束的既有 pending_review/known_issue。

## 4. P1：修正曲线支持；优先删除无消费者的启发式

先修改失败测试，再改生产代码。

| 准确文件／符号 | 最小修改 | 必要性 |
|---|---|---|
| `plugins/curve_score/curve_score/figure_digitization.py::_materialize_shared_support` | 仅 coincident 分支调用现有 mark_shared 时传 shared_eligible=True；复用 _curve_csv 的本地资格计算 | 修复已证明重合仍不能定量；不新增 TracePoint 字段 |
| 同文件 `_overdraw_findings/build_digitized_figure_bundle` | 删除 _overdraw_findings 及唯一调用；保留原 trace.findings、binding 检查及其全曲线传播 | 直接移除没有独立消费者的错误推测来源，约 60 行；不另建 finding 分类 |
| `plugins/curve_score/curve_score/figure_digitization_contract.py::FigureLineTracking.overdraw_candidate_endpoint_distance_px` | 原字段的 Field description 写明“请求 v2 兼容保留，已弃用，物化时忽略”；字段名、类型、默认 8.0、范围 [0,1000] 和序列化形状不变 | 唯一算法消费者随生成器删除；保留旧请求可解析，不增加 deprecated 元数据、告警、版本分流或新文件 |
| `plugins/curve_score/curve_score/figure_evidence_validation.py::_validate_declared_shared_support` | coincident 复制行只检查真实来源一致性，删除“复制必不合格”“eligible 最多 1”两条禁令；strict overdraw 分支不变 | 让校验器接受正确结果，同时保留所有像素/坐标/成员/锚点/距离负控 |
| 同文件 `VALIDATOR_VERSION` 与 `plugins/curve_score/curve_score/figure_evidence.py::FigureEvidenceValidationReport` | 使用既有版本字段递增为 5；读模型继续接受 2/3/4/5，v5 继承 direct/shared 计数检查 | 明确确定性实现代际；报告仍为 v1，不新增版本路由或 ABI |
| `plugins/curve_score/curve_score/figure_science_operations.py::REQUEST_PROMPT/FIGURE_REQUEST_SEMANTIC_CONTRACT` | 删除 copied rows 不可定量的错误承诺，说明双方可定量且物理观测共享 | 请求 Worker 必须看到与物化器相同的支持语义 |

不改 `figure_line_tracker.py`，不改 normalizer 或评分器。unsupported_seed、too_few_points、
insufficient_visible_support、超阈值 undeclared_gap、ambiguous_path 等旧 trace finding 原样有效。
局部 gap 用 CSV 源列/point_index、报告 gap count、manifest max_gap 和原图/overlay 复核；
不再保留没有独立消费者的 “possible overdraw by …” 猜测文本，这是明确放弃的行为。

失败测试先行：

- 更新 `tests/operations/test_curve_figure_digitization_tool.py::test_coincident_overlap_uses_one_real_source_per_column`：
  两个成员共享行均 eligible，3 个真实像素不变；双方规范化有效区间覆盖重合段。
- 现有 `test_shared_copy_cannot_be_made_independently_eligible` 固化了错误语义；
  用“合法 coincident 多引用可定量”和“strict overdraw 复制资格仍拒绝”取代，不删除后者的保护。
- 增加只有局部 possible_overdraw 条件、但未触发 tracker 阈值的夹具：两侧直接点保持 eligible，
  gap 和分段域仍可见；同夹具超出原 max_gap 或破坏身份后仍 unresolved。
- 单成员 below-limit/排除区间只影响该成员；坐标脱钩、假来源颜色、缺锚点/成员贡献/列、
  距离超限负例继续失败。保留旧 Fig.4 无 coincident 请求的黑线未决/红线可用负控。
- 同一冻结输入物化两次全部字节一致；报告 v2/v3/v4 可读取，v5 计数一致；
  归一化和评分不跨 ineligible 空档。
- 请求 v2 仍接受省略或显式提供旧 overdraw_candidate_endpoint_distance_px；合法取值变化不改变
  跟踪点、eligible、findings、有效区间与评分语义。保留字段的原有范围校验；请求字节、请求摘要或
  带请求身份的输出可随取值变化，不能把“算法忽略”误测成不同请求的所有输出字节相同。

验收：以上新反例先红后绿，已有身份与 strict overdraw 负控仍绿；独立审查后才合入 P1。
旧测试通过不再等于科学语义正确。

## 5. P2：版本化来源投影，并把实际别名写入既有可执行 Schema

### 5.1 唯一代际方案：受影响声明的投影版本进入现有 digest

保留 `operations/spec.py::OPERATION_ABI_VERSION = "16"` 和 `CompiledDigestEnvelope` 原有字段。
在 `operation_contract.py` 增加一个私有选择函数 `_evidence_source_projection_version(spec, port)`：
仅当 executor 为 agent、输出非 collection 且声明 evidence_paths、至少一个输入声明
usage=evidence_inventory 且 exposure 非 handoff_only 时返回固定投影版本 `evidence-source-enum.v1`，
否则返回 None。版本字面量仅在此定义；Schema 生成、usage 注释和 catalog 摘要共用此选择函数。
它依据声明而非本 Run 成员数量判定，因此有 inventory 但零绑定仍属于同一新版合同。

`operations/catalog.py::_build_compiled_catalog.operation_digest` 先照旧建立 `CompiledDigestEnvelope`。
若有适用输出，按输出名排序形成 `(output_port, projection_version)` 元组，并对
`{"compiled": 原 envelope, "output_schema_projection": 元组}` 调用既有 `canonical_digest`；
没有适用输出时，对原 envelope 原样摘要，连空键或 None 字段也不能追加。reviewer_digest 和
approval provider identity 仍通过现有递归传播，不能为了压低退休数量切断真实合同依赖。
不摘要包含自身 operation_digest 的完整 result.schema.json，避免自引用。

前轮只读源码探针编译当时六插件组合共 49 个 Operation：模拟 ABI 17 时 49 个摘要全部改变。
按上述声明直接适用的是两种通用 Audit、图 Intake、图 Audit 和 `tcad.parameter.evidence.extract.v1`
共 5 个；沿当前 reviewer/provider 摘要依赖闭包共 8 个。这个数值仅用于比较 P2 单独修复，
不是硬编码名单或完整发行包的摘要承诺；本轮清单 usage 修正后提取仍有 source_material inventory，
因而仍直接适用。P2 的领域声明/Approval 版本修正、P1/P3 资源变化及正式包版本变化须另列实际影响，
不得继续把 8 个当作整个 P2 或主批次的固定退休总数。

不选的方案及边界：

- ABI 17 的代码行数更少，但会无条件改变全部 Operation，包括不消费来源投影的插件合同；
  也使它们已有 Run、审查和审批身份失效。本轮没有 OperationSpec 形状或组件协议变化，不支付这项成本。
- 不给 `CompiledDigestEnvelope` 增加全局默认 version 字段；其 dataclass 规范序列化会把新字段写进
  每个摘要，仍造成全目录退休。选择性包装只改变需要该投影的行为身份。
- 不冻结完整 compiled result Schema 到 Run。当前 RunStatus/SQLite 没有 Schema 内容或其摘要字段，
  backend 只把 Schema 写到 Worker 工作区；文件只读位不构成可信存储。只冻结摘要不能执行旧 Schema，
  信任工作区文件则可被替换；安全冻结必须增加可信字节存储、请求绑定、旧行缺值策略及恢复验证，
  还无法冻结 codec/context checker 的 Python 行为，不能独自解决跨代际提交。范围大于本轮所需。

投影版本只是现有 compiled digest 的构建输入，不成为新的规则清单、数据库事实、公开字段或迁移表。
新程序只有一份当前投影实现，不按旧版本选择 validator，不支持旧 Run 跨代际继续提交。
新程序仍可读取历史合法记录，但其旧资格、审查、恢复和当前消费权不自动升级。

### 5.2 同一绑定投影用于 prepare 和 submit

直接从 OperationSpec 约定编译生成校验可行，而且就在本补丁范围内：输出端口的 schema_resource
生成类型、必填、枚举、范围和普通条件校验；输入 usage、输出 evidence_paths 与冻结 Run 绑定
进一步生成本次调用的来源 enum；运行时复用现有 JSON Schema validator 执行，不另生成 Python
校验代码或规则 DSL。静态目录只编译端口级模板，集合实际别名必须等 Run 绑定后机械展开。

OperationSpec 不能凭声明自动发明“这个 Intake 是否忠实”“两条曲线是否具有科学上相同身份”等
科学判断。可机械验证的跨输入约束仍由该 Operation 已声明的 validator/context_validator 组件引用
实现（当前类型是 ComponentRef），绑定既有 rule_id、说明、字段路径与所需输入；Worker 和 submit
消费同一份编译合同。独立科学审查继续归 Worker，不能藏入编译器。

不新增来源校验器。沿现有函数传递一份 source-name→port 映射，在已有 Schema 生成入口作绑定投影，
提交仍执行这份生成规则。Worker 文件是派生视图；submit 从冻结 Run 记录重建，不能信任 Worker
可能修改过的 workspace schema。

| 准确文件／符号 | 最小修改 |
|---|---|
| `src/scidiscovery/operation_contract.py::_evidence_source_projection_version/operation_port_json_schema` | 共用第 5.1 节的适用条件；增加可选 keyword 绑定映射，从既有 inventory 端口选实际 source_name，在 evidence_paths 数组项 source_key 处追加 enum |
| 同文件 `operation_output_validation_contract` | 仅对上述适用输出的 context_sources 静态项补 usage；说明 checker 上下文不等于 evidence。实际允许集合只存在于 Schema enum，不保存第二个 allowed_sources 清单；其他输出保持原投影 |
| `src/scidiscovery/operations/catalog.py::_build_compiled_catalog.operation_digest/_validate_operation_contracts` | 选择性摘要投影版本；在已有输出 Schema 校验循环中复用私有拼装函数检查 evidence_paths 能否落到实际结构，损坏声明使用既有 output_evidence_path_invalid 失败关闭 |
| `src/scidiscovery/artifact_agent/service/run_assignment.py::result_schema_json` | 接受并传递绑定映射，输出本 Run 的完整 envelope schema |
| `src/scidiscovery/artifact_agent/service/runs.py::RunService.schedule` | 在既有 prepare 调用处从 frozen_inputs 构造映射；不改生命周期、SQL 或 backend API |
| `src/scidiscovery/artifact_agent/service/run_outputs.py::validate_run_output/_validate_payload_schema` | 将已有 input_source_ports 传给同一 operation_port_json_schema；在现有调用点把投影构造/冻结绑定故障包装为 RunCheckerError；正常 Schema 内容拒绝复用 RunOutputError 和 runtime.schema |
| `src/scidiscovery/general_science_components.py::_evidence_audit_context/_validate_audit_handoff_and_sources` | 删除硬编码目标排除、重复来源集合检查及目标存在检查；目标必需性已由 InputPortSpec/review 绑定负责。保留 decisive evidence_keys 和 verdict 聚合，可收拢原有私有函数 |
| `plugins/tcad_artifact/tcad_artifact/parameter_operations.py::EXTRACT_INPUTS/_parameter_qualification_document/_approval_operation` | 仅把提取端口 required_parameter_checklist 的 usage 改为 prior_signal；资格 projector 用 package 的既有有序 parent_refs 核对清单，证据集合只含真实来源；同文件两项共享 projector 的 Approval 使用既有 Operation version 从 1 递增为 2，绑定这一实现变化 |

清单修正的边界与附带消费者必须一起闭合：

- 不改端口名、可选基数 min_items=0、exposure=full、Schema/codec 或 EXTRACT_OUTPUTS.context_sources。
  `prior_signal` 已在 Agent usage 白名单中；该端口不是 wildcard，不触发 InputPortSpec 的 wildcard
  特殊限制，也不是 revision_base/change_request，不改变修订形状或 claim_evidence 准入。
  assignment 和冻结 Run inputs 会如实显示新 usage，编译 Operation 声明本身随之改变摘要。
- `run_outputs.py` 按 context_sources 的端口名投影 checker 输入，不按 usage 筛它；因此可选清单
  仍进入 `validate_extract_context`，缺省时仍可省略。保留 source_catalog.keys 恰等于已绑定
  source_material 别名及清单科学字段一致性检查；允许 display_name 调整的原规则不变。
  `_validate_parameter_family` 的 observation→source_catalog→foundation 来源闭合和 source_type
  一致性继续有效。新增 enum 只阻止 foundation 再把清单当额外证据，不能替代这些家族约束。
- 已有提取角色文件明确写着清单是约束而非来源，故 `roles/parameter_evidence_extractor.md` 无需修改。
  不修改 AUDIT_INPUTS、Approval 输入或 coverage/uncertainty 等其他端口的 usage；参数 Audit 当前
  没有 evidence_paths，不属于本次投影，不借本缺陷启动全参数合同整理。
- Root `_run_output_family` 从 Run inputs 的 claim_evidence/evidence_inventory/cached_excerpt
  派生 evidence_sources，新提取家族不再把 prior_signal 清单列作证据。这是应有变化；不在 Root
  加回清单、扩展 ProducerOutputFamily 或新增 constraint_sources。
- 资格 projector 当前通过 evidence_sources 查清单，简单改 usage 会错误拒绝有清单的合法请求。
  在同一 `_parameter_qualification_document` 删除这项查找及排除清单的来源过滤；保留 run_input
  种类、source alias/ref 唯一性与 frozen_sources 精确有序相等检查。使用这些已核验 frozen_refs，
  要求 `package_subject.parent_refs == (*optional_checklist_ref, *frozen_refs)`；可选清单只允许零或
  一个精确 ref。依据是 `_register_candidate` 按全部 frozen inputs 保存父链，而当前 EXTRACT_INPUTS
  顺序就是可选清单后接全部 source_material。这是 TCAD 插件对自身固定提取合同的核对，不是核心
  按端口名特判。漏清单、多清单、换 ref、漏/加/换/重排来源都不能只靠相同科学字段通过。
  清单科学字段比较、完整展开族、coverage 重算与 Audit 精确有序父链检查保留。
- 普通 projector callable 源码不进入 `_resource_digest`。因此两项参数资格 Approval 的既有 version
  必须一起递增；不新增 Operation ID，不把协议版本当实现版本，不靠整包版本偶然改变身份。
  单独记录它们及既有 provider 依赖传播的摘要变化；第 5.1 节无适用投影时原样摘要的规则不变。

绑定投影的具体边界：

- 使用 evidence_paths 指向的现有 evidence 数组，附加普通 nested properties/items/allOf 约束。
  拼装前必须核对路径存在、终点为数组、items 为含字符串 source_key 的对象；只沿声明路径检查
  properties/items 和实际使用的本地 `#/$defs/...` 引用，并对循环、外部引用或无法确定的形状失败关闭。
  复用同一私有拼装函数作编译期形状检查和 Run 投影，不增加 payload checker、通用引用解析器或 DSL。
  不得以“拼出了合法 JSON Schema”替代证明 enum 约束实际可达。
- 集合端口使用 frozen_inputs 的实际别名，例如 curve_tables_001、curve_tables_002；
  不靠前缀猜测，也不从模型输出反推输入。未绑定的可选成员不进入 enum。
- 仅对第 5.1 节选中的合同应用该含义。
  不把全部 claim_evidence/prior_signal/revision_base 输入重新解释成原始来源；
  不迁移假设、实验、诊断或批量参数合同。除上述清单及其资格消费者修正外，没有该声明的旧 Operation
  保持原有来源投影行为。
- 已声明 inventory 但本 Run 没有绑定成员时，禁止非空 evidence 项的 source_key，
  允许基础 Schema 本来允许的空 evidence；不要生成 JSON Schema 不合法的空 enum。
- figure Intake、figure Audit、通用两种 Audit 已具备所需声明。
  通用 Intake 的现有 context_sources=source_material 检查无隐藏目标排除，本轮不为了统一形式而改它。
- 不修改静态 catalog 的调用要求；未传绑定时仍返回静态 Schema。正式 Run prepare/submit 必须传绑定。
  不修改组件回调签名，不改变 OperationSpec ABI；投影摘要按第 5.1 节改变，参数声明/Approval 版本
  按本节单独列示影响。
- JSON Schema 的 enum 错误已经包含实际值和允许值；沿现有路径生成精确
  $.payload.evidence[0].source_key 与 runtime.schema，足以纠正。不要新增错误详情类型或 source rule。
  错误分流明确如下：
  编译时 evidence_paths 损坏以 output_evidence_path_invalid 拒绝、零 Run；正式 submit 的投影构造
  ValueError/KeyError/TypeError、未知绑定端口、冻结来源映射不一致，以及 Schema 构造/执行器异常，
  在 `run_outputs.py` 的构造/执行边界统一包装为既有 RunCheckerError，令同代际 Run failed。
  当前代码对非 jsonschema 模块异常直接 re-raise，故这项包装是 P2 的必要实现，不能只写“沿用”。
  从正常 iter_errors 返回的 enum 等内容不匹配仍在异常包装之外形成 RunOutputError/runtime.schema，
  submit 返回 rejected 且可修正；不能用捕获所有异常把它变为系统失败。
  prepare 构造异常沿 schedule 现有 workspace preparation failed 路径记录 failed 并抛 RunError；
  不增加准备阶段生命周期。checker 的 SemanticRuleViolation 与程序异常仍沿原有分流。

预计只有两个现有对外 Python helper 增加可选参数：
operation_port_json_schema 与 result_schema_json；其余是内部透传或删除。
允许在 operation_contract.py 内新增至多两个私有函数：上述版本/适用性选择函数和有界 Schema 拼装函数
（含路径形状检查）；不建新模块、数据类或注册面。

失败测试先行：

- 在 `tests/operations/test_m5_figure_review_closure.py` 通过真实 Root→Local Worker
  prepare/open/submit：从生成的 result.schema.json 取允许集合，合法 candidate 首次完成；
  scientific_intake、抽象 curve_tables、未绑定别名和 revision 输入作 evidence 均在 Schema 阶段 rejected。
- 同一拒绝返回准确元素路径、实际值、允许值和已声明 rule_id；Run 保持 running，
  修正后完成。破坏 checker 的程序负控仍直接 failed。
- 在 `tests/operations/test_agent_contract_alignment.py` 覆盖集合展开、可选 inventory 空集合、
  相似前缀别名和不含 inventory 的现有合同；确认 workspace payload schema 与提交重建 Schema 等价。
- 通用 foundation/Intake Audit 复用相同测试。扩充 `tests/operations/test_m2_parameter_package.py`
  的真实 Root→Local Worker 路径：有/无可选清单、单/多 source_material 的可见 enum 只含实际来源；
  在其他字段合法的 foundation.evidence 中加入 required_parameter_checklist 必须于 Schema 阶段
  rejected，返回 `$.payload.scientific_intake.scientific_foundation.evidence[i].source_key`、
  runtime.schema 和允许值；修正后可完成。现有 invented alias 测试改断言新 Schema 诊断。
- 在相同参数夹具上，合法来源配篡改清单科学字段仍被 parameter.source_binding 拒绝；丢失/新增
  source_catalog 项、观测引用未声明 source_key、source_type 不符仍被既有家族/context checker 拒绝。
  正确清单、清单缺省及只改 display_name 各有正例，证明 usage 未撤销 checker 上下文或扩大可选性。
- 扩充 `test_real_parameter_run_reaches_expansion_audit_and_qualification` 至有/无清单和多来源：
  新提取家族 evidence_sources 不含清单，但 package.parent_refs 保留清单；完整展开、Audit、
  qualification preflight/invoke 均成立。提取时有清单而资格请求漏掉/替换它（含同科学字段不同 ref）、
  提取时无清单却额外绑定它，以及来源遗漏/新增/替换/重排，均在 preflight/invoke 拒绝、零 Approval。
  复用现有通过与例外资格测试夹具，验证两项共享 projector 的版本与 provider identity 传播。
- 用一个无领域名称、嵌套 evidence 路径的最小 Operation 验证实现消费声明，不按 Schema/插件名路由。
  不把这个测试 fixture 升格为生产扩展层。
- 同夹具声明语法合法但不存在的路径、非数组终点、缺 source_key 的 items、本地引用失效/循环，
  在 catalog 编译失败，零 Run；不能产生永不生效的 enum。prepare/submit 遇到损坏 Schema 时按已有
  系统故障路径终止，不向 Worker 返回可修订的内容拒绝。分别注入非 jsonschema ValueError 的投影
  构造故障、未知端口/映射错配以及 checker 程序故障，证明 submit 返回 failed、零 Artifact/receipt，
  而普通 enum 错误仍 rejected/running；prepare 故障记录 failed，不留下 queued 或可提交的坏合同。

### 5.3 代际负测与旧 Run 的确定行为

在 `tests/operations/test_catalog_compile.py` 先增加隔离 P2 的红测：固定插件/Operation 版本、声明、
资源字节和绑定，只改变来源投影代际，要求受影响 digest 改变；没有适用声明且不依赖受影响
reviewer/provider 的 Operation 必须保持旧 digest 原值。再覆盖重编译稳定、审查依赖传播、两份不同
实际绑定的 Run request 不同而 compiled digest 相同。不能靠修改 prompt 或包版本使这个测试变绿。

在 `tests/operations/test_l2_run_invariants.py`、`test_l2_local_run.py` 复用现有 Root/Local 路径，
旧目录分别创建 queued、running、带恢复草稿的 failed、completed 四种 Run；各分例关闭并重开
同一临时状态库，加载新目录，再检验以下行为。不要为了同时造 queued/running 绕过每 digest 的
唯一活动槽。测试必须发生投影版本引起的真实摘要变化，不能只改一个 operation version 字符串：

| 旧记录 | 新安装下的既有行为与断言 |
|---|---|
| queued | 新安装当前 digest 的 Worker open/reopen 不领旧槽，提示 no exact queued Run；新目录不能用旧 digest 构造 LocalWorkerMCPRouter。直接提交旧 queued Run 先被 `_require_running` 以 Run is not running: queued 拒绝。Root 显式 run_record_failure 在正确 CAS 条件下仍因 `_compiled` 的 contract changed 被拒绝，不能收口；状态保持 queued，零新 Artifact/receipt |
| running | 当前 digest 的 Worker open/reopen 同样不领旧槽。截止前晚提交旧 Run 在 `_compiled` 抛 `RunStateConflict("Run operation contract changed")`，早于 seal、Schema/codec/checker 和登记；过期时先被 `_require_running` 以 deadline expired 拒绝。正确 CAS 的显式失败命令（含已过期 timed_out=true）仍在 `_compiled` 被拒绝，状态保持 running，零新 Artifact/receipt |
| failed 且有恢复草稿 | `recovery_available=false`；新合同的 resume preflight/invoke 因 `_recovery_digest` 的 digest differs 被拒绝，零新 Run；旧草稿保留，不能改写来源身份后继续 |
| completed | Root `run_status.sealed_output_status=contract_retired`，sealed_output/scheduler_signal 均为空；旧 completed、Artifact 和 receipt 保留。`RunService.submit` 对已完成 Run 只幂等返回 completed，不重新校验/登记，也不使旧输出获得当前合同消费权 |
| 未受影响合同 | 无适用投影且无已变 reviewer/provider 依赖、也未作其他声明/资源/版本修改的合同保持原 digest。其 queued 可打开、running 可重开/提交、failed 可恢复、completed sealed output 可用，均受原有输入、后端、currentness、时间/次数条件约束 |

`contract_retired` 是已完成输出的只读可用性，不是新增 Run 状态；queued/running/failed 的 sealed output
仍为 unavailable。上述“不能打开”限定为新安装的当前编译 Worker 入口，不宣称旧 workspace 文件
从操作系统不可读；`RunService._open_exact` 本身按调用方 digest 查槽，并不是独立的当前目录门。
测试必须从当前 Worker router 进入，不能把任意旧 digest 的内部 service 调用冒充新安装入口。

本轮明确保留旧 queued/running 不能由现有命令收口的限制：`record_failure` 在 seal、状态 UPDATE
和 workspace 处置之前调用 `_compiled`；摘要不同即退出。断言失败命令前后 state、last_activity_at、
reason、recovery draft、Artifact/receipt 和 workspace 不变；纯查询与失败命令均不自动修复记录。
这些旧活动记录仍留在列表；`one_active_run_per_operation` 按 digest 唯一，旧槽不占新 digest 的槽，
使用新请求身份可正常创建新 Run，但不能把它描述成恢复旧 Run。不得新增生命周期修复、启动扫描、
迁移器、自动失败或清理逻辑；也不得通过改旧记录、清库或绕过 `_compiled` 来使负测通过。
同一当前代际下还要证明：新 Run 的可见 Schema 与 submit 重建一致；篡改工作区 Schema 不能扩大
提交接受集合；相同 digest 的正常失败恢复仍有效。

验收：可见接受集合与 submit 相同，隐藏排除代码消失；无需修改 Worker MCP、backend 或异常体系。
独立审查必须特别检查“没有 inventory”和“有 inventory 但零绑定”两种情况没有混同。

## 6. P3：只澄清审查判断，不创建资格捷径

只修改：

- `src/scidiscovery/general_science_resources.py::AUDITOR_PROMPT/Resources.evidence_audit_semantic_contract`；
- `plugins/curve_score/curve_score/figure_science_operations.py::AUDIT_PROMPT`。

明确 check.status 比较“Intake 的陈述是否忠实于精确来源”：

| 情况 | status |
|---|---|
| 来源支持陈述，或 Intake 正确保留其限制、局部缺口、检测下限、共享依赖或未决身份 | pass，basis 保留限制 |
| Intake 把不合格点写成合格、隐瞒来源限制、错误绑定身份或作无支持肯定陈述 | fail |
| 所需材料缺失/不可读，或对象无法比较 | unknown |
| 检查不适用 | not_applicable |

不改 fail→blocked、unknown→inconclusive、否则 pass 的机械聚合；
不改 split 的独立审查准入，不补第二 verdict，不由 Python 推断“忠实”。

先在 `tests/operations/test_m5_figure_review_closure.py` 放入同一有限来源的两份候选：
忠实 Intake 配通过审查可 split，并逐字保留限制；夸大 Intake 配 fail 必须被后继拒绝；
真正缺乏比较条件配 unknown 保持 inconclusive。测试证明承载/准入行为，不能冒充科学判断测试。
真实独立 Worker 的比较结果另在 E2E 验收。

审查 pass 只证明忠实性，可以让忠实的“不充分”结果继续被保存/机械展开；
逐点资格、目标所需覆盖和人工科学资格仍按已有门禁判断。不新增“审查通过必授科学资格”的承诺。
P3 应单独审查和回滚，不能把一次正常负面科学审查当作 P1 曲线代码失败。

## 7. P4：保留 ObjectiveClosureRequirement 原模型，仅补条件 Schema

唯一生产文件：
`src/scidiscovery/artifact_agent/schema/research_objective.py::ObjectiveClosureRequirement`。

不用三类判别模型替换原类，不改 exported name、默认 requirement_type、字段名、序列化形状或调用者。
在模型级 json_schema_extra 的 allOf 中添加普通 if/then 条件，并在三个数组的
`Field(json_schema_extra={"uniqueItems": True})` 声明唯一性；不要在模型级 extra 中重写 properties，
以免覆盖字段原有 items、默认值与长度约束。
保留 _subjects_match_type 的现有 Pydantic 防御。不要扫描或重写其他 model_validator。

| requirement_type | 必须非空 | 必须为空/省略 | 既有合法组合 |
|---|---|---|---|
| target_coverage（含省略类型时的默认值） | target_keys | comparison_purposes、validation_check_keys | 不改变默认构造 |
| comparison_present | comparison_purposes | validation_check_keys | target_keys 可以同时非空 |
| validation_check_present | validation_check_keys | target_keys、comparison_purposes | 不增加其他含义 |

条件 Schema 必须处理“字段省略由 Pydantic 使用默认值”的情况，不能要求用户补历史合法负载中没有的字段。
target_coverage 分支在类型省略时也适用；其余两分支的 if 必须显式 required requirement_type，
防止 properties 条件在字段缺失时同时命中。then 只要求该类型已有必填非空数组，并对禁止数组使用 maxItems=0。
数组唯一性也是当前模型已拒绝的结构规则，不引入新科学判据。

在 `tests/operations/test_agent_contract_alignment.py` 增加参数化失败测试：
三类正例、空数组、交叉污染、重复项、默认类型省略、comparison+target 合法组合。
比较 JSON Schema 与 strict JSON Pydantic 的接受集合，并从真实 ScientificIntake 的嵌套 $defs 验证；
至少一条无效组合走实际 Run submit，返回 runtime.schema，修正后可完成。
跨对象 target key 引用是否存在仍是既有语义校验，本补丁不处理。

验收：历史合法 JSON 接受集合不变，已知非法组合在 Worker 可见 Schema 提前拒绝。
独立审查单独放行 P4；不要求先完成曲线代码，也不扩张为全局验证器整改。
P4 只改变已有 schema_resource 的内容，`catalog.py::_resource_digest` 已将资源字节纳入摘要；
以旧/新嵌套资源摘要对照验证传播，不新增第二个投影版本或 ABI。它的安装态检查单独执行。

## 8. 分阶段门与真实 Fig.4 验收

本计划自 P2 实现复审起，后续独立审查者统一使用 `gpt-6-astra`。审查必须以本补丁既定边界和
复杂度预算为约束：只有当前差异直接造成且阻断本阶段目标的问题才可阻断；不得借审查引入新实体、
注册表、状态机、全局治理机制，或把后续安装态/真实端到端门提前扩成当前补丁范围。

1. 方案门：未参与本次设计的审查者核对现有反例、代际影响与文件边界。通过只授权实施，不代表缺陷已关闭。
2. 补丁门：每个补丁先提交能复现旧行为的失败测试，再提交最小修复；运行直接受影响文件和跨边界负控。
   独立审查者核对实际 diff、代码消费路径和测试，PASS 且阻断 0 后才交付该补丁。
   不为每个 helper 再设审查阶段，不把全仓测试数量作为放行证明。
3. 集成门：先串行运行 P1—P3 的聚焦反例、图审查家族/一般合同、参数提取至资格路径及 installed-entrypoint
   回归，再至少串行完成一次完整 `tests/operations` 和完整 `tests/artifact_agent`；两个目录分开运行，
   前者结束后才启动后者，记录各自命令、结果及未完成项。中央投影与 digest 变动不能只凭聚焦测试放行。
   全仓测试不作为额外要求，完整目录回归也不能代替语义负控、安装态和独立科学审查。
   设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，pytest 不并发，每次仅一个真实 Worker。
   Codex 进程树内存熔断为 4 GiB，整轮 WSL 常驻内存相对开跑前基线增量不得超过 8 GiB；分别记录峰值，
   超界停止本次探针，不能把 8 GiB 当作 Codex 进程树预算。
   内存门覆盖聚焦与完整目录测试、安装探针及真实 Worker；超界的未完成目录不能记为通过，先缩减
   同时驻留进程后串行重跑未完成门，不新增监控产品或提高预算。
   通过后按下述实际安装入口验收；P4 修改不进入主批次发行包，自己的结构与嵌套 Schema 新用例独立执行。
   完整目录中既有 objective 测试仍正常运行，不能以 P4 独立为由跳过它们。
4. 真实门：以下为必须产生的证据清单，不授权调度器照抄固定阶段流程。

installed entry path 不是直接 import 源码的替代名称。扩充
`tests/operations/test_catalog_installed_entrypoint.py`，复用 `installed_environments/installed_probe`
的 release builder→wheel→独立安装→`entry_points(group="scidiscovery.plugins")`→
`compile_installed_catalog` 路径；默认组合、Fig.4 组合均在源码目录外执行，清除源码 PYTHONPATH，
核验模块实际来自安装目录。通过真实 Root→Local Worker prepare/open/submit 执行合法来源和非法别名
正负例，对照工作区 Schema 与提交结果，并验证 generated Codex profile、Worker router 和 Root 的摘要一致。

用修复前后的干净安装环境、各分例自己的隔离测试状态根执行第 5.3 节四类旧 Run 与未受影响合同的
重启验收，包含旧 queued/running 显式失败命令不可收口；
不读取或改写生产状态库。记录完整目录摘要差异及 reviewer/provider 传播，包含无关合同不变负控。
P1 还须在安装态看到 validator v5，P3 必须看到新静态资源；只更新源码或 ABI 数字均不足以放行。
安装态参数路径须看到 checklist 的新 usage 和两项资格 Operation 的新 version，并重放有/无清单
资格正例及漏/换清单负例；旧 overdraw 距离字段仍可按请求 v2 读取，但不再控制算法。
随后沿既有 `scripts/build_git_release.py`、`deploy/reinstall.sh`/`install.sh` 的离线暂存包探针、
完整服务切换、平台配置生成和事务回滚路径验收；安装器可以使用自身暂存 site，不能指向源码冒充安装态。
重启服务和 Codex，避免启动缓存或旧 profile 造成混合代际；不修改部署/恢复协议。

真实验收使用用户已明确继续的 ResearchInstance。先 instance_current；未绑定时给出其精确管理 URL，
由用户在页面选择既有实例，不自动建立默认实例。

从冻结 PDF 和完整、可复核的 Fig.4 请求重新物化。若当前请求合同摘要已退休，按当前 public catalog
重新调度请求 Worker；不得由调度器重写请求或用旧 CSV 造输入。对每次行为使用目录声明的端口、
精确 immutable binding、同一 preflight/invoke，并沿其 compiled review_edge 调度独立审查。
Agent 用控制返回的 agent_type、无父历史；只消费 completed Run 的 sealed_output/scheduler_signal。
旧对象原样保存，新名称/有意 revision 不继承旧批准。

必须观察到：

- 已确认 coincident 区间内，双方在各自本地资格允许的位置均有非空定量支持；
  全局物理像素去重、共享来源和不确定性可逐点回溯。
- InAlAs 的直接点不再仅因 possible_overdraw 全部失效；真实 gap/低于检测下限区间仍不可被评分跨越。
  两个目标具有科学上有意义的有效区间，不能以任意非空或四像素片段作为成功。
- Intake/Audit 合法 candidate 的首次 worker_submit_result 完成；故意非法来源在真实入口被精确拒绝。
  若发生拒绝，分别记录合同错误、真实内容错误与程序异常；“零拒绝”不是放宽校验的理由。
- 独立图 Audit 判断忠实性并保留限制；通过审查的精确 Intake 能 split，匹配同族输入能规范化。
  错审查、缺表、换来源与旧代际结果依旧在正式入口失败，不能借此放松 review/family/current 门。
- 需要人工资格时，只使用 operation_invoke 返回的精确 review URL 和 sealed UI 决定；
  审查 pass、聊天、进程成功均不得当作人工批准。

若来源实际不足、身份未决或 Intake 夸大，保留真实 blocked/inconclusive 和有界原因。
这样的结果可以证明工程合同正常，但不能宣布 Fig.4 科学资格通过或恢复后续实验。
最终由未参与实施的审查者核对安装态、正式提交、sealed 审查、父链、逐点计数和负控，
明确分别判定“补丁完成”和“E5/E6 放行”。本文不实施假设、实验、TCAD 或完整求解。

## 9. 复杂度预算、删除项与回滚

预计生产 Python 改动：

| 范围 | 生产 Python 文件上限 | 新增公共抽象／实体／注册面 |
|---|---:|---|
| P1 | 5 | 0；复用 TracePoint/报告版本，删除一个启发式函数；在既有请求合同文件注明旧字段弃用且忽略 |
| P2 | 7 | 0；原 6 文件加既有 parameter_operations.py 的清单声明/资格消费者修正；至多两个模块内私有函数，无新公共类型 |
| P3 | 2（其中 figure_science_operations.py 与 P1 重合） | 0；仅静态资源 |
| P4 | 1 | 0；保留原模型 |
| Fig.4 主批次 P1—P3 去重 | 13；其中通用控制基础设施仍为 5 个文件 | 0 新公共抽象、0 新实体、0 新注册面；0 新表/状态机/工具/Operation |
| 含独立 P4 的计划总上限 | 14 | 同上；P4 不占当前主批次范围 |

文件数不包含直接对应测试及已有发布包版本元数据。包版本是否需要递增由既有发布约定决定，
不能为压低数字漏记实际改动；新增生产文件、第三个既有公开 helper 签名变化或额外核心文件必须重新审视范围。
P2 只扩展两个既有公开 helper 的可选参数，不增加新的公开 helper；私有函数明确计数，不声称零抽象。
P2 的 7 文件为 operation_contract.py、operations/catalog.py、service/run_assignment.py、service/runs.py、
service/run_outputs.py、general_science_components.py 及插件 parameter_operations.py；资格修正不增加
第六个通用控制文件。新生产文件总数为 0；提取角色 Markdown 无需改动。上限增长来自两个已证明
消费者/兼容声明所在的既有文件，不是通用端口清理或生命周期工程。
本轮 ABI 保持 16，代际修复由第 5.1 节的选择性投影版本承担；禁止用包版本或其他补丁的资源变化代替它。

相较原计划明确删除/推迟：

- 删除第二个来源遍历 checker 和独立 allowed_sources 清单，使用普通 Schema enum 与既有 runtime.schema。
- 删除 possible_overdraw 生成器，旧距离请求字段仅作 v2 兼容保留、弃用且忽略；取消 blocking 白名单、
  severity 体系及 normalizer/评分器预设改动，不引入正式弃用机制。
- 取消 objective 三模型判别联合；保留单类的条件 Schema，P4 独立交付。
- 不要求 P3 与曲线算法同补丁，不增加 qualification evaluator 或 verdict。
- 取消 C0—C7 每个小步骤重复独立放行，保留方案、补丁、集成、真实科学四层证据门。
- 继续推迟全局 checker/usage 迁移、相关性统计、UI、TCAD 求解、恢复和部署协议工作。

33 项仍是验收矩阵，不是新运行实体。此次直接保护 AUTH-003、ROLE-001/002、DET-001/002、
EVD-001、UNC-001、PLG-001/002；跨边界负控保护 IMM-001/002、LIN-001/002、TOP-002、HIL-001/002、
MIG-001/002。其余约束不因本次聚焦通过而自动改状态；SEC-002/UI 已知限制保持诚实记录。

回滚按完整补丁进行：

- P1 的生成器、验证器、报告读模型及 prompt 必须一起撤回；只回退一半会再次产生自拒绝合同。
- P2 的 catalog 投影身份、路径核对、prepare/submit 透传及参数清单 usage/资格父链核对/Approval 版本
  一起撤回；不保留新 enum 配旧 digest，或新 usage 配旧资格 projector 的混合安装。
- P3 可单独回退静态资源，P4 可单独回退 Schema 投影；不能以回退方式重写历史 verdict。
- 使用既有安装事务回退完整发行包，不改 CAS、父链、收据或 schema 文件来让旧 Run 继续。
  新版本生成的 v5 报告在旧版本不保证可消费；保留原始记录并按既有合同退休规则停住，
  不自动降级为 v4，不宣称双向兼容。新代码继续读取旧合法记录是本轮向前兼容边界。
- 回退发行包后，新投影 digest 下的 Run 也按第 5.3 节的既有规则不可提交/恢复，完成输出不可作为
  当前合同内容。旧历史记录不被删除或迁移，不实现双版本 Schema/validator 运行层。
- 若 P1 的确定性输出或 P2 的接受集合无法与 Worker 可见合同对齐，停在该补丁审查，
  不追加新状态机、不无限修订科学文字，也不进入真实科学主线。
