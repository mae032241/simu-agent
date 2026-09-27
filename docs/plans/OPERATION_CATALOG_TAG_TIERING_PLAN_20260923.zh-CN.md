# Operation catalog 标签分级与有界候选查询计划

状态：**两轮独立可靠性复审均要求 REVISE 后的修订候选，待再次复审；未实施、未部署、未做原生 A/B 验收。** 日期：2026-09-23。本文件只提出导航接口设计，不改变当前科研 Run、科学结论、准入、审批或执行权限。标签过滤暂不设为默认；若进入实施，须另记精确代码差异、独立审查与验收结果。本文件不得被计划索引或调度提示当成已生效规范。

## 1. 问题与已核实边界

当前 `scid_catalog()` 经 `mcp_gateway.py:UnifiedMCPRouter.catalog` 转给 Root `operation_catalog(view="summary")`；默认页限 20，仅返回 `operation_id/purpose/executor_kind/catalog_scope/runtime_binding`，再以 `next_before` 续页。`scid_describe(name=..., view="invoke")` 从同一编译项读单个精确合同。`RootOperationRoutes.operation_catalog` 从 `CompiledCatalog.scheduler_projection()` 生成条目，public 还检查后端、工具、Effect adapter 和 reviewer 可用性。`OperationSpec` 已有 `description.purpose/applies_when/not_for`、`consequence`、输入端口 Schema/基数/current 要求、review edge、approval、executor 和 scope；`accepts_actions` 是废弃兼容字段，不能复活为路由权威。

本工作树用 `PYTHONPATH=src:plugins/tcad_artifact:plugins/curve_score:plugins/curve_figure_evidence python` 的本地可加载入口观察到 52 项（public 31、support 21）；这不是隔离 wheel、所有部署组合或长期常量。真入口是 `pyproject.toml` 的 `scidiscovery.plugins` entry point，经 `compile_installed_catalog()`、`open_runtime()`、Root MCP/gateway 和安装脚本的三工具探针。源码手工拼目录不足以证明安装行为。

验收须区分三个集合：`D` 是已编译声明 `catalog_scope=public` 的 Operation；`V` 是同一运行时快照里经后端、工具、Effect adapter、reviewer 等可用性过滤后，Root `operation_catalog(scope="public")` 实际可见的集合；`A(request)` 是给定实例、绑定和权限下，经精确 preflight/invoke 才能判定的请求准入。导航只能索引、筛选 `V`，不能把 `D` 全数当作当前可见，更不能把出现在 `V` 说成 `A(request)` 已通过。`D\V` 应在安装态诊断中保留逐项不可见原因，不作为 Agent 的可调用候选。

现行 gateway 在 Root 上把 `scid_catalog(kind="operations")` 转给 Operation 目录，在 Worker 上即使指定该 kind 也返回该 Worker 的工具接口；Worker 的 `scid_describe` 与 `scid_call` 仍限于所附任务的能力。只读 public 目录本身不授予调用权限，因此**不把“仅供 Root”当成新导航的固有安全要求**；但现行 Worker 指引要求只处理已附任务，不检查控制对象或调度 Agent。未来若开放 Worker 只读导航，须有任务内用途，并同步审查 Worker 指引与 gateway 合同，不能由新增参数悄悄改变现行 Worker 行为。

当前决策所有权见 `docs/ARCHITECTURE.zh-CN.md`、`docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`、`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`（尤其 AUTH-003、TOP-001/002、ROLE-001/002 和插件边界）、`docs/plans/R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md`。`roles/scheduler.md` 与 `roles/scheduler/research.md` 是当前调度指引，`.codex/scidiscovery-guides/` 是安装副本；本提案不得抢其规范地位。与 `docs/plans/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md` 无取代关系，后者管科学结论和下一步价值判断。Fig.4 首次误路由与纠正后的限定验收，以 `docs/plans/evidence/fig4-route-pruning-r2-20260922/FINAL_BEHAVIOR_ACCEPTANCE_20260923.zh-CN.md` 为当前记录：首次把未核对假设集合的竞争解释过早归为实验设计；纠正后假设提案及独立 critic 完成，但机制仍不可识别。目录标签不能从 `inconclusive`、Worker 建议或 `ready_for_experiment` 自动推导下一动作。

## 2. 分级判断：不冻结“八个科学决策主类”

八个互斥主类无法覆盖当前交叉关系：`science.hypothesis.criticize.v1` 是对假设的 review，`tcad.deck.review.v1` 是对实现的 review；人工资格又可针对证据或参数。若把 review、qualify、revise 当成同层科学阶段，会复制 review edge、approval 和修订合同，还会暗示固定 DAG。建议先试六个**非互斥的决策意图标签**，每项 public Operation 可有 1—2 个，另以正交字段表达动作和后果。意图只回答“这项工作可改变哪类判断”，不预判是否值得做或能否调用。边界与例子如下；完整 31 项映射须在实施前逐项审阅，不能按 ID 前缀自动补齐。

| 意图标签 | 进入边界与正例 | 排除边界与反例 |
|---|---|---|
| `evidence_basis` 取得/纠正证据基础 | 来源抽取、审查与局部修订；`science.evidence.extract.figure.v2`、`science.evidence.audit.v1` | 已有执行结果的机制解释；`tcad.result.analyze.v1` |
| `hypothesis_frame` 改变可检验解释集合 | 正式提案或批判其可证伪性；`science.hypothesis.propose.v1`、`science.hypothesis.criticize.v1` | 已形式化假设下选实验对照；`science.experiment.design.v1` |
| `study_design` 定义目标、对照和可计算判据 | `science.experiment.design.v1`、`science.experiment.skeleton.v1`；领域合同如 `science.curve.contract.design.v1` 可作为第二意图待核 | 把设计变成 Deck/代码；`tcad.deck.author.initial.v1` |
| `realization` 构建或修复可执行实现 | 初始 author、限定修订、运行故障修复；`tcad.deck.author.initial.v1`、`tcad.deck.author.runtime-failure.v1` | 外部正式执行；`tcad.study.execute` |
| `execution_observation` 产生或收集执行事实 | `tcad.study.execute`；若将来有公开观察 Operation 才加入 | 解释已封存结果；`tcad.result.analyze.v1`。标签本身绝不授权 Effect |
| `result_interpretation` 判断结果、误差与有效性 | `tcad.result.analyze.v1`、`science.result.diagnose.v1` | 以报告建议自动进入下一轮设计或调参 |

`review`、`revise`、`qualify`、`materialize`、`execute` 是 `action`，不是新增科学主类。当前 `science.object.review.v1` 的精确被审对象是 `experiment_plan` 或 `scientific_skeleton`，因此标 `subject=study`，须由 `action=review, subject=study` 查询直接找到。它也可作为按需早审使用：`science.experiment.skeleton.v1` 没有必经 `review_edge`，不能只沿生产者审查边发现该 reviewer，更不能从标签推断审查为必需。通用 Operation 已知的被审对象应逐项显式标注，不能用 `any_declared` 代替而使精确 subject 查询漏项。交叉标签要有说明，不能使 Operation 获得额外准入。若逐项映射显示六类也不可稳定区分，则退回仅使用正交 action/subject 查询，不为凑分类数扩展词表。

## 3. 字段来源与更新责任

唯一能力来源仍是插件 `OperationSpec` 经启动期编译的 `CompiledCatalog`；标签随 Operation 声明和编译投影，不建独立 YAML/数据库/Root 映射表，不按 TCAD、插件名、Schema 字符串或角色名硬编码。插件作者维护语义描述；编译器验证声明的合法形状、引用和一致性；Root 只从编译项过滤、分页；调度者在选项与封存证据间作判断。六个核心意图只是试点词表，不得做成阻止第三方插件表达新研究领域的封闭枚举：插件扩展值须带命名空间、短定义和版本，并在自身声明中维护；编译器校验冲突、重复和形状，未知值给精确诊断。核心词表的变动仍需逐项语义审查，不能由任意插件静默改义；不认识扩展标签的客户端仍能从完整 public 索引找到该项。

| 导航字段 | 单一来源与责任 | 不得声称 |
|---|---|---|
| `decision_intents`、`action`、`subject` | 若试点证明需要，作为 `OperationSpec` 内显式、受控词表的 `navigation` 元数据由 Operation 所属插件维护；编译器校验。`subject` 是研究对象类型（如 hypothesis、study、implementation、result、evidence），可多值；已知被审对象必须显式标注，不得用 Schema 名推断科学意义 | 自动选择下一项；把 review/approval 当科研阶段 |
| `consequence` | 直接投影现有 `OperationSpec.consequence`、`executor.kind`、approval/Effect 合同；不得复制可手改的第二值 | “低风险”标签绕过人审或 Effect 权限 |
| `required_state` | 只投影当前精确合同可证明的**静态条件**：必需端口与基数、`require_current`、`input_admission`、review edge/approval 要求。可用短提示如“需已封存结果”，但原端口仍是权威 | 对当前实例“ready”、已合格、有可用对象；不从同 Schema 或最近 Run 猜绑定 |
| `independence` | 仅从 `ReviewSpec.reviewer_operation/reviewer_input_port` 和现有独立 Agent 准入投影 | 仅靠标签验证 reviewer 身份或把作者 Agent 作为独立审查者 |
| `input_schemas` | 从 `InputPortSpec` 精确列 schema、端口名、必需性、用途和通配范围；过滤语义是“存在声明端口”，不是“现有实例有合法对象” | 只按 Schema 判定 producer family、资格或 currentness |
| `not_for` | 保持 `OperationDescription.not_for` 原文为单一来源，完整 invoke 合同必含；首版不从自由文本生成排除标签 | 自然语言否定句成为准入规则 |

当前 `json_projection()` 会把新 `OperationSpec` 字段纳入 `CompiledDigestEnvelope`，即使新增字段默认 `None` 也可能使全部 Operation digest 漂移。实施前必须作明确 ABI/身份决定，不能默默加字段：推荐将纯导航元数据作为 `OperationSpec` 声明但在身份投影中**显式排除**，单独给导航投影版本/摘要并验证修改标签不改合法调用、permission template、Operation digest 和已有封存 Run 的可读性；这项例外需独立审查，证明它不会进入 admission/assignment/submit。导航摘要不是现有 `CompiledCatalog.digest()`：后者汇总 Operation digest 与 runtime 插件身份，若导航字段被排除便不会随标签变化，且本身不表示 public 可见集合；插件版本变化仍可能改变该编译摘要，不能据此声称“标签之外零身份漂移”。若审查认为标签改变行为合同必须入 Operation digest，则明确提升 ABI/版本，先列出受影响的全部 Operation、活跃 Run、review/approval provider 链与历史读取影响，等待在途 Run 安全结束后部署，历史读取仅按当前有效合同逐项验证，不预设一律退休，也不伪造兼容摘要或继承资格。试点的第一包可仅投影现有类型字段，无 ABI 变化；需新语义标签时才进入第二包。

## 4. 查询合同与预算

保留 `scid_catalog()` 默认行为与 Root `scid_describe(name, view="invoke")` 的精确单项合同。给 `scid_catalog(kind="operations")` 增加显式导航视图；`kind="interfaces"` 仍是原接口列表，不能误用 Operation 标签。P1 先在 Root 开放完整紧凑索引及由现有结构字段可证明的筛选（如 consequence、executor kind、input Schema），用于验证可见集合、过滤、分页和预算的工程可行性，不拿其科学选路或 token 收益判定语义标签无效；P2 在 P1 工程安全通过且自身声明/身份方案获审后，才开放显式 `decision_intents/action/subject` 及其 facet，不得以 ID 或自由文本猜出试点标签。目标合同分三层，默认是否切换须经 §5 的原生 A/B 门槛单独决定：

1. `view="index", limit?, before?`：返回**完整的当前可见 public ID 集合 `V`**的紧凑索引，每项仅 ID、极短 purpose；Root 投影另含精确 describe 指针。索引不依赖标签筛掉、重排任何项，未标记及扩展标签项照常出现。按稳定 ID 顺序分页，返回 `visible_total/returned/next_before/complete/navigation_snapshot_digest/query_digest`。若一页放不下，Agent 须续完全部页才能声称某 Operation 不存在；任何页的 `complete=true` 只表示该查询已遍历 `V`。目标是可快速扫视全集，不承诺所有安装组合必能单页容纳，也不承诺它比当前两页 summary 少 token。
2. `view="facets", dimension?, limit<=12, before?`：从同一 `V` 计算意图、action、subject 的名称、短定义、计数，列 `unclassified_count`；不返回全部 Operation 或合同。超过单页预算时按 `dimension` 分页，返回该维度的 `total/returned/next_before/complete/omitted_count`；未读完的 facet 值可用同维度游标继续取得，不能只报遗漏数或悄悄裁剪。P1 尚无语义标签时仅返回已支持的结构维度，并明确其余维度未提供。
3. `view="matches", where={decision_intents?,action?,subject?,consequence?,input_schema?}, limit<=20, before?`：从同一 `V` 按字段 AND、同字段多值 OR 过滤，先过滤再按稳定 `operation_id` 分页；每项只含 ID、短 purpose、静态标签和最小 runtime 状态，Root 投影另含精确 `describe` 指针。不给整个输入端口、review 合同或大量描述。`visible_total`, `matched_total`, `filtered_out_count`, `unclassified_count`, `returned`, `next_before`, `complete`, `coverage="filtered_subset"`, `catalog_digest`, `navigation_snapshot_digest`, `query_digest`, `filters_applied` 必须可见；即使非零匹配且 `complete=true`，也只表示**过滤子集**已遍历，绝不表示正确 Operation 已召回。

三个视图的 `navigation_snapshot_digest` 按稳定、规范化投影计算，覆盖导航协议版本、`V` 中每项 Operation ID/digest、参与筛选或展示的标签/字段及影响可见性/筛选的后端、工具、Effect adapter、reviewer 状态；它不是权限摘要。`query_digest` 覆盖 scope、view、规范化 where、排序、调用方投影（Root/Worker）及 facet dimension（如适用）。不透明游标绑定导航快照摘要、query 摘要和最后一个键；Root 与 Worker 游标不得互用。每页重新计算当前快照，若标签、过滤条件或可见集合改变，则返回明确 `catalog_changed/restart_query`，不能把部分页当全集。原 `catalog_digest` 继续只表示编译身份，不被复用为导航快照。Root 选定一个 ID 后继续现有 `scid_describe(name=..., view="invoke")`，必要时看 full；invoke、preflight 和 operation_invoke 不接受导航标签作为准入凭据。

Worker 开放是单独的、**可选的只读接线决定**，不是 P1/P2 标签机制的先决条件，也不预设拒绝。P0 先记录一个明确的已附任务内用途及所需字段；若确有价值，P3 可让 Worker 通过显式 `kind="operations", view="index"/"facets"/"matches"` 读取同一运行时 `V` 的 public 导航投影，但必须先在**同一 session/thread/Run 绑定上成功调用 `worker_open_assignment`**且 Run 仍处于可工作的状态。附着或通过模型 profile 检查本身不足以放行；复用线程绑定到新 Run 后必须为新 Run 重新打开 assignment。访问门须复用 Worker 当前绑定、打开状态和终态判断，不新建可漂移的授权标志；如果不能可靠取得同源打开状态，就不开放 Worker 视图。无显式新 view 时，Worker 的 `scid_catalog()` 和现有 `kind="operations"` 请求仍返回任务工具接口；`kind="interfaces"` 也保持原语义。Worker 响应与 Root 使用同一 `V` 和筛选快照，但 index/matches **不含 `describe` 指针**，并在响应顶层标明 `contract_access="root_only"`；不提供 support/internal/all、实例绑定、preflight、invoke 或调度能力。Worker `scid_call` 仍只接受任务工具，`scid_describe` 不自动扩展为 Operation 合同读取；若任务用途确需精确合同，应另审只读可见范围和上下文成本。Worker 科学报告可描述结论与建议，但目录 ID 不成为后继调度命令；现行 Worker 指引变更须先经独立审查，不得以本提案绕过。

调度指引的拟议顺序是先取得完整紧凑索引，再按科学决定用 facet/matches 缩小候选，最后只读所选 ID 的 invoke 合同；对索引中相关但被过滤排除的 ID、未标记项和可能跨意图的 action/subject，应交叉核对，必要时回到未过滤 public 目录。**非零匹配也触发这项核对**，不能把 `complete` 当语义召回保证。无匹配时返回 `matched_total=0`、`complete=true`、已应用过滤、当前 scope 和通向索引/无过滤 public 目录的提示；不自动扩大为全部候选、不自动改选 Operation。未知标签值返回明确可修复错误和合法值摘要；无标签的第三方 public 项进入 `unclassified`/完整索引，不能因缺标签而从授权目录消失。过滤只缩短展示；public/support/internal/all 的既有作用域和可用性判断不变，support 仅供已选 public 的需要，internal 不出现在调度导航。索引交叉核对能降低错标风险，但不能对任意错标证明绝对召回，须用 §5 负例检验。

响应预算按 UTF-8 字节和实际模型 token 双计：index 的预算由 P0 实测 `V` 规模后冻结，facets 目标 ≤4 KiB、matches 默认一页 ≤8 KiB 且每项目标 ≤320 UTF-8 字节；超限时先缩短可选摘要并报告 `omitted_fields/omitted_count`，保留 ID、cursor、完整性和精确错误，绝不截断 JSON 或静默丢候选。20 项超预算必须可续页（可降低返回项数并给 `next_before`）；最小必需条目若仍超过单页限额，安装编译/导航构建应给出精确不可表示错误，不得返回零进度页或无限重复游标。试点先测真实条目分布再冻结限额；token 以同模型、同任务、同缓存/工具可见条件的原生使用记录计，字符/字节仅为传输代理指标。工具包装、索引、facets、matches、回退、describe 和本轮累计上下文增量均计入；4 KiB 与 8 KiB 是分别的上限，不能相加后仍声称低于附录 B 的约 6.2 KiB 基线。

## 5. 验收矩阵、通过门槛与回滚

先冻结对照：当前源码/安装 wheel、插件组合、catalog digest、`D/V/D\V` 与不可见原因、默认目录页数/响应字节、Root 原生 token/上下文增量、关键分支选择记录。不得从历史 Fig.4 日志推算未知 token。试点评估必须同时有：

- 编译及投影：P1 同一安装快照下，新 index 与旧无过滤 public 目录所返回的 `V` 必须逐 ID 相等；`D\V` 逐项给出实际不可见原因，不能因 31 项源码声明就要求 31 项全部运行时可见。P2 每个 `V` 项须在 index 可达；标签查询覆盖只对其声明的标签负责，未标记者保持 `unclassified`/action 路径，不得编造标签来凑覆盖率。保持准确未标记计数；scope、reviewer 可用性、Effect adapter 缺失、插件禁用/升级/回滚下无陈旧标签；第三方未标记项不隐形。比较标签改变前后 Operation digest/ABI、插件版本、permission template 和历史封存 Run 的只读行为，记录全部变化，不用单元 mock 代替安装入口。
- MCP 负例：通过实际安装 wheel 的 gateway/stdio/proxy 入口验证错误标签、旧 cursor/改过滤条件、标签变化但 Operation digest 不变、后端/工具/Effect adapter/reviewer 可见性变化、零匹配、**非零但错标/漏标的匹配**、index/facet/matches 全部分页、超长最小条目、页尾、权限上下文、`kind="interfaces"`、不可用 reviewer 和 unclassified。错标负例中错误分支仍须返回看似合理的非零候选，正确 ID 不给 Agent 提示，检查其能否从完整索引与交叉查询恢复。`action=review, subject=study` 必须找到可选骨架早审的 `science.object.review.v1`，即使 skeleton 无 `review_edge`，但标签不得使审查必经。`scid_describe` 精确合同、preflight 与 invoke 对同请求仍给相同拒绝原因。未授权 internal 或缺适配器 Operation 不能靠过滤进入 public，标签也不能绕过独立审查、current、人工审批和外部执行授权。
- Worker 只读接线（若选择）：经真实安装态 gateway/stdio/proxy，以未附着、已附着但未成功 `worker_open_assignment`、成功打开且 Run 活跃、打开失败、终态、跨会话及同线程复用到新 Run 但尚未重新打开等状态分别测试显式新 view；仅精确绑定并已成功打开的当前 Run 可读，同线程旧 Run 的打开状态不得继承。已授权的只读查询只能返回同一运行时 `V` 的 public 投影；Worker index/matches 每项无 `describe` 指针，顶层 `contract_access="root_only"`，且调用 Worker `scid_describe` 读取该 ID 仍得到现有拒绝。旧无 view 请求仍返回任务工具接口，`kind="interfaces"` 不变；`scid_call` 不扩权，不能凭目录 ID 调度、检查实例控制对象或获取 support/internal/all。记录该任务的额外 token/上下文成本。若不选择 Worker 接线，则显式新 view 在 Worker 上须明确报不支持，不得静默返回另一类目录。
- 路由离线回放：用封存事实和精确旧输入构造 Fig.4 首次误路由负例，要求 Root 在选择实验设计前核对正式 hypothesis portfolio 覆盖；未覆盖时能找到 hypothesis proposal/evolution 及其独立 critic，已覆盖而缺判别观测才考虑 study design，实现缺陷可考虑 author，数值无效不当物理证伪。再用非 Fig.4 的证据修订、参数资格、曲线分析、TCAD runtime failure、无适用 Operation、通用 review 分支做交叉反例；不能把标签设计成这份 Fig.4 答案表。离线测试只验可发现性、排除误导和合同一致，不宣称科学判断正确。
- 原生对照：实施前冻结由独立审阅者判定的任务集、每题可接受的 Operation ID **集合**（允许多个正确项）与停止条件；开发集用于改标签/提示，保留未见过的跨边界任务作 holdout，不能在看见 holdout 结果后调标签再复用同一集报收益。预设至少 16 个覆盖六类意图、横向 action、无标签插件、无适用 Operation 与非零错标诱饵的封存决策快照，每组基线/候选各至少两次原生重复；若资源不足只报 pilot，不作默认切换判定。两组使用同一模型/effort、任务文本、已封存输入与工具代际，交错/随机顺序并记录缓存状态、失败和超时，不只保留成功回合。一个完整决策 episode 从第一次目录调用到选定 invoke 合同或明确停止，计入 index、facets、matches、回退、describe、重读及工具包装的全部调用、UTF-8 字节、实际输入/输出 token、最大上下文与净新增。不得启动新的 Fig.4 科研或外部执行来证明目录功能。

P1 工程门槛：安装入口正负例、结构筛选与 index/facet/matches 分页、游标代际、预算、`V` 等价、`D\V` 原因、无准入差异及既有 digest/Run 兼容均通过；不能再以“源码 31 项都出现在运行时”为判据。P1 即使没有减少误路由或 token，也不能单独否定 P2 的语义标签假设；P1 若有漏项、越权或无法有界分页，则不得进入 P2。P2/P3 产品收益门槛预设为：语义匹配查询返回候选的中位数 ≤6、95 分位 ≤10（报告查询数与分位算法；这只是导航压缩指标，不等于正确性）；在全部关键 holdout 与错标负例中，最终选择须属于预先判定的可接受集合或正确停止，且相对基线无新增误路由；所有重复回合计入失败率与召回分母。成对 episode 的实际 token 净新增及上下文峰值中位数均至少下降 10%，同时报告每个关键案例、整体分布和更长尾成本；不得以单次 matches 字节替代整轮成本，也不得因多读 index 而隐去开销。样本不足、token 不可观测、关键负例回退失败或总体成本未降时，只报告工程/pilot 结果，标签过滤保持可选，`scid_catalog()` 默认不变。

任一 `V` 项从完整索引漏掉、越权项被放出、分页漏项、digest/历史 Run 意外退休、关键错标负例新增误路由或原生上下文不降反升，均停止默认推广并诊断；单个标签筛选未命中本身不是 `V` 丢失，但不能被宣传为可靠召回。未达到产品门槛时可保留经工程验收的**显式可选**导航，不改现有默认目录入口。回滚只撤导航视图/字段与提示，恢复原 `scid_catalog` 默认查询；保留科研数据库、Run、Artifact、审批与执行记录。若改动已进入 Operation 身份，则不能简单代码回滚后冒充旧合同，须按受影响 Run/插件代际记录退役影响并另作安装事务。

## 6. 最小工作包与替代方案

| 包 | 精确文件面（拟；实施前按真实 diff 复核） | 完成判据 |
|---|---|---|
| P0 只读基线 | `src/scidiscovery/operations/spec.py`, `catalog.py`; `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`, `mcp_response_views.py`, `mcp_gateway.py`; `pyproject.toml`, `deploy/install.sh`, `roles/scheduler*.md` 与本提案所链规范 | 冻结 `D/V/D\V` 及原因、真实安装入口、独立判定的开发/holdout 决策任务、Fig.4 与跨领域任务/整轮成本基线；基线缺精确证据时暂停，不以结构筛选代理语义收益 |
| P1 完整索引与现有字段导航试点 | `mcp_gateway.py` 的 `CatalogInput`/路由、`mcp_root.py` 的 `OperationCatalogInput`、`mcp_root_operation_routes.py` 与 `mcp_response_views.py` 的索引/过滤/分页投影；窄测 `tests/operations/test_unified_mcp.py`, `test_mcp_response_views.py` | 无新标签语义、无 ABI 变化；index 与旧目录的 `V` 完全相同，验证安全、完整性、非零结构过滤负例、三种分页、预算与成本可行性，不以科学/原生收益决定 P2 |
| P2 显式语义标签（P1 工程安全通过且声明/身份方案获审后） | `operations/spec.py`, `catalog.py`；所属插件的 Operation 声明文件（`src/scidiscovery/general_science_agent_operations.py`, `general_science_experiment_operations.py`, `general_science_control_operations.py`、`plugins/curve_score/curve_score/science_operations.py`、`plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py`、`plugins/tcad_artifact/tcad_artifact/plugin.py`, `parameter_operations.py`, `result_analysis.py` 等按逐项清单确认）；`tests/operations/test_catalog_compile.py`, `test_catalog_installed_entrypoint.py` 及上述 MCP 测试 | 每个 public 条目人工核定边界、缺失不隐藏、digest/ABI 选择和插件组合负例过关；语义收益在 P2/P3 独立衡量 |
| P3 接线与发布证据 | `roles/scheduler.md`, `roles/scheduler/research.md` 和 `.codex/scidiscovery-guides/research.md` 的源/生成关系；`src/scidiscovery/platforms/codex.py` 生成/校验；`deploy/install.sh`、已安装 wheel/proxy 探针；现行架构中英对应段与计划索引在审查通过后才更新 | 先作为显式可选导航保持默认兼容；只有原生 A/B 达整轮收益与可靠性门槛、独立跨边界审查通过，才另行决定是否改默认；指南不复制标签 registry |

Worker 只读接线是 P3 的独立选择：P0 须先证明具体已附任务内用途并测量字段与额外上下文成本；若选择，P3 文件面增加 gateway 的 Worker 路由、同源 assignment 打开状态检查、按调用者投影的 describe 指针处理、两种 Worker profile 的生成指引及安装副本，并须经职责与权限边界的独立审查。只读接线不由 Root 导航 A/B 自动放行，也不改变 Worker 已附任务工具的调用白名单；若无用途或收益，保留现有 Worker 接口目录即可，不把“Root 才能读 Operation 名称”写成权限原则。

低成本替代：仅在现有 summary 加 `applies_when/not_for` 摘要并缩小每页长度；优点是不增标签维护，缺点是上下文可能更长且无法可靠过滤。另一替代是客户端按关键词搜索已有 purpose；优点是零 ABI 影响，缺点是同义词、否定句与跨语言召回难证明，且客户端筛选可能漏项。拒绝独立映射表、按 Operation ID/插件名前缀分类、把 `accepts_actions` 复活、按科学阶段建固定 DAG、把标签送入 preflight 作权限规则；它们增加第二权威或混淆科学判断与机械导航。P1 若工程安全失败则先修或停止；仅 P1 结构筛选的收益不足时仍保留 P2 语义假设，最终是否推广由 P2/P3 的独立收益和风险证据决定，而不是为“八类”目标继续扩建。

未决的评审问题：六类实际逐项映射是否稳定；第三方插件是否接受显式 `navigation` 字段及其版本纪律；纯导航字段应否从 Operation 身份排除；当前真实安装/模型能否提供可归属的 token 数据。这些必须用 P0/P1 证据关闭，不能由本计划假定为已解决。

## 附录 A：31 项 public Operation 的初步标签映射

下表是基于当前源码编译目录、逐项 `purpose/applies_when` 和 Operation 职责作出的**提案映射，不是已部署标签或已通过的领域审查**。`—` 表示明确 `unclassified`：该行为可能是横向审查、资格或机械投影，没有单一科学决策意图；它仍须从无过滤 public 目录及 action/subject 查询发现。六类和每项 1—2 个意图只是试验词表，逐项审查可合并、拆分或减少分类数。`†` 表示语义边界需领域维护者和独立审查者核定，尤其不能用标签推断 qualification 或下一步路由。action/subject 是拟议导航值，不是现有 `OperationSpec` 字段，也不参与权限判断。

| public Operation | `decision_intents` 提案 | `action` | `subject` | 待核边界 |
|---|---|---|---|---|
| `science.curve.contract.design.v1` | `study_design`† | `design` | `curve_contract` | 领域合同是设计细化还是 realization，需核定 |
| `science.curve.contract.review.v1` | `study_design`† | `review` | `curve_contract` | 审查只沿所选合同，不成独立必经阶段 |
| `science.evidence.audit.intake.v1` | `evidence_basis` | `review` | `evidence` | audit 不等于资格决定 |
| `science.evidence.audit.v1` | `evidence_basis` | `review` | `evidence` | 同上，审查精确 foundation |
| `science.evidence.extract.figure.v2` | `evidence_basis` | `extract` | `evidence` | 完整 figure family 是输入约束，不由标签证明 |
| `science.evidence.extract.v1` | `evidence_basis` | `extract` | `evidence` | 仅绑定的来源可用 |
| `science.evidence.qualify.v1` | —† | `qualify` | `evidence` | 人工资格是横向后果，不强塞证据主类 |
| `science.evidence.revise-from-critic.v1` | `evidence_basis`† | `revise` | `evidence` | 由 hypothesis critic 的具体事实缺口触发，不是普通假设修订 |
| `science.experiment.design.v1` | `study_design` | `design` | `study` | legacy detailed-plan 路径，不代表固定下一步 |
| `science.experiment.revise.v1` | `study_design` | `revise` | `study` | 精确 review 请求及旧 plan 均需绑定 |
| `science.experiment.skeleton.v1` | `study_design` | `design` | `study` | 科学骨架，不含 Deck 实现 |
| `science.figure.evidence.audit.v1` | `evidence_basis` | `review` | `evidence` | 审查完整 sibling family |
| `science.figure.request.prepare.v1` | `evidence_basis`† | `prepare` | `evidence` | 只是选择/描述图，后续抽取另有合同 |
| `science.hypothesis.criticize.v1` | `hypothesis_frame` | `review` | `hypothesis` | 独立 critic 的 verdict 不是路由命令 |
| `science.hypothesis.propose.v1` | `hypothesis_frame` | `propose` | `hypothesis` | 可演化既有组合，不强制新增机制 |
| `science.hypothesis.revise.v1` | `hypothesis_frame` | `revise` | `hypothesis` | 同一 reviewed portfolio 的有界修订 |
| `science.intake.revise.v1` | `evidence_basis` | `revise` | `evidence` | 只修精确 Intake，不改历史来源 |
| `science.object.review.v1` | —† | `review` | `study` | legacy plan 或 skeleton 的可选通用审查；骨架无必经 review edge，须由 subject/action 查询找到 |
| `science.parameters.qualify.exception.v1` | —† | `qualify` | `parameter` | 人工 exception 与 rationale 要求不能由标签代替 |
| `science.parameters.qualify.pass.v1` | —† | `qualify` | `parameter` | 人工资格不由覆盖率标签自动授予 |
| `science.result.diagnose.curve-error.v1` | `result_interpretation` | `diagnose` | `result` | 消费确定性误差包，不自行重算资格 |
| `science.result.diagnose.v1` | `result_interpretation` | `analyze` | `result` | 失败/不完整结果也可形成有限分析 |
| `tcad.deck.author.initial.v1` | `realization` | `author` | `implementation` | 只实现已给科学计划 |
| `tcad.deck.author.revise.v1` | `realization` | `revise` | `implementation` | 精确独立审查请求和修订界限 |
| `tcad.deck.author.runtime-failure.v1` | `realization` | `author` | `implementation` | 修具体运行故障，不自动改科学设计 |
| `tcad.deck.review.v1` | `realization`† | `review` | `implementation` | 同时审科学充分性与工程证据；是否需第二意图待领域核定 |
| `tcad.execution-plan.project.v1` | —† | `project` | `execution` | public 机械 Transform，无新科学判断或执行资格 |
| `tcad.parameter.evidence.audit.v1` | `evidence_basis` | `review` | `parameter` | audit 与人审资格分开 |
| `tcad.parameter.evidence.extract.v1` | `evidence_basis` | `extract` | `parameter` | 参数值/范围由来源和 Worker 负责 |
| `tcad.result.analyze.v1` | `result_interpretation` | `analyze` | `result` | 分析终态执行，失败不等于机制证伪 |
| `tcad.study.execute` | `execution_observation` | `execute` | `execution` | Effect、审批及 adapter 门不由标签授予 |

此初表 31/31 逐项可见，其中 5 项明确 `unclassified`（三个 qualify、通用 object review、机械 execution-plan project）；`†` 仅为待审标记，不是质量或可调用状态。完整映射必须随实际插件集合重新生成并审阅，新增、禁用或升级插件不能继承这份表作为运行时映射表。

## 附录 B：当前源码 summary 响应字节基线

只读测量方法：以本工作树的 `PYTHONPATH=src:plugins/tcad_artifact:plugins/curve_score:plugins/curve_figure_evidence` 调用 `compile_installed_catalog()`，取 `scheduler_projection()` 中 31 个 `catalog_scope="public"` 项，按 `operation_id` 现有编译顺序构造 `scope="public"` 的静态目录；用 `mcp_response_views.root_response("operation_catalog", ..., {"view":"summary","limit":20或100,"before":...})` 走现有 summary/分页投影。对完整返回对象（含 `scope/view/total/next_before/detail`）用 `json.dumps(ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")` 计字节。扩字段情形是在首 20 项 summary 结果的每个条目中直接追加其同一 `SchedulerOperationView` 的原文 `applies_when` 和 `not_for`，其余包装不变；这模拟直接加字段的成本，不是现有 API 的真实响应。

| 静态源码投影 | UTF-8 字节 | 解释 |
|---|---:|---|
| 默认首 20 项 summary | 3,958 | `next_before=science.parameters.qualify.pass.v1` |
| 后续 11 项 summary | 2,230 | `next_before=null`；两页合计 6,188 |
| 31 项单页 summary（`limit=100`） | 5,964 | 同样 31 项，但只付一次包装 |
| 首 20 项 summary 直接增加 `applies_when/not_for` | 7,473 | 比原首 20 项增加 3,515 字节，约 88.8% |

本测量没有打开 Root runtime、没有调用真实 `scid_catalog` 传输，因此未包含 MCP JSON-RPC/工具包装、动态 `runtime_binding`、public 可用性过滤、安装 wheel/服务配置、任何模型 token 或实际上下文峰值。当前 Python 环境的 entry point 可加载不等于隔离安装或目标部署；真实安装入口、插件组合和原生 token 必须按 §5 另测。上述数字只说明“给每个 summary 条目直接加两段原文”会显著增加本源码样本的可见字节，不能单独证明分级筛选可省 token。
