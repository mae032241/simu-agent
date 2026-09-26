# 当前架构

简体中文 | [English](ARCHITECTURE.md)

本文描述当前通用插件平台和完整科研任务。实施与验收进度以
[R4 主计划](plans/RESEARCH_TASK_REFACTOR_R4.zh-CN.md) 为准。
历史计划与审计仅描述其记录的候选，不覆盖当前合同；静态实现不代表运行验收通过。

## 1. 设计原则

SciDiscovery 的基本行为原子是 `OperationSpec`。它是一份不可变、可编译的行为闭包声明，而不是
包含全部实现的巨型类：声明输入/输出端口、执行种类、组件引用、资源上限、工作区、工具、网络、
独立审查、人工审批与副作用要求；具体 codec、validator、guard、projector、workspace hook、
Worker tool 和 runtime factory 由插件内的窄组件实现。

当前 Operation ABI 20 要求 Agent 输出引用结构化语义合同。每条不能由 JSON Schema 表达的规则
具有稳定 `rule_id`、说明、输出路径和所需输入；编译器拒绝未知输入以及把可选端口暗中声明为必需
输入的规则。每个 Python 内容或上下文校验器必须绑定其中一个已声明 `rule_id`，否则目录编译失败。
编译器把这份合同和从端口、校验器绑定及修订形状机械派生的校验合同嵌入同一份
`result.schema.json`。提交路径先执行这同一份 JSON Schema，再执行少量已绑定语义规则；诊断只能
引用 Worker 已见的 `rule_id` 和字段路径，不得维护提示词专用或提交专用的第二套规则。

科学判断属于调度 Agent 和专业 Worker；控制面只拥有身份、不可变记录、最小上下文投影、生命周期、
资格与副作用门禁；确定性代码只做可重放的机械变换；领域 adapter 只做外部副作用。

Root 根据研究问题选择完整的证据、假设、实验或分析任务。这是职责类别，不是固定流水线或四个
常驻 Agent。`science.experiment.v1` 在同一 Run 内负责设计、实现、局部调试、执行、收集、有效性
判断和交付，TCAD 是该通用任务的领域能力。普通子环节不强制独立审查或审批；适用的资格规则和
外部执行授权仍由明确合同规定。

任务随工作进展封存阶段科学结论和材料引用，UI 读取同一阶段投影，不触发调度。阶段预览不是最终
完成：最终报告选择采用的阶段版本，保留限制。控制层核对精确科学来源、实际采集执行与采用实现，
不增加固定科学检查表。

任务负责人可按需使用原生助手完成有意义的有界子问题。助手使用新上下文，保留负责人的原生权限、
Skill 和任务工作区能力；Worker 工具只准入负责人预先登记的真实子线程。助手不能选择实例、调度
Root 任务、封存负责人阶段、提交父任务或形成正式独立审查。负责人等待并整合发现与文件，然后释放
助手工具访问。默认只准入一个活动助手、一层委派，恢复链共用累计次数。释放 Run 工具权限不等于
停止原生工具或证明线程退出；原生等待、停止、关闭和模型消耗属于平台职责。框架不声称对这些原生
线程提供聚合内存或 Token 硬上限。

结果分析可在同一任务调用领域评分和解析工具。计算保留精确输入与工具证据身份；评分不可用限制
相应定量结论，不引入作者/审查者的固定调度链。

## 2. 注册、编译与三种视图

科学行动只有一个 entry-point group `scidiscovery.plugins`；每个入口返回一个 `PluginDefinition`，
同一发行包当前可以发布多个插件定义。一个插件同时声明冻结组件元组和由这些组件组成的
Operations。组件没有独立 entry point，插件私有实现也不能由 Root 或 Worker 按 Python 路径二次
发现。浏览器的可选 `scidiscovery.instance_views` 只加载纯展示映射，不注册行动、工具或科学准入规则。

启动时 `compile_installed_catalog()` 一次性完成：

1. 插件协议、编号、版本与依赖校验；
2. 组件引用闭包、类型协议、静态资源摘要和运行时工厂校验；
3. Operation 端口、结构化语义规则、资源、权限、review/provider 图与审批合同校验；
4. 生成包含 operation id、version、digest 和冻结实现引用的唯一 `CompiledCatalog`。

既有声明还一次编译出静态 Worker 工具 Schema 和输出合同，目录、任务文件、MCP 与提交入口复用
这些投影；每个 Run 的别名加入独立副本。静态材料先排除自身 digest，再进入既有身份摘要结构。
Root 与 lifecycle 工具保留各自声明，共用严格 JSON 参数解析和诊断。preflight/invoke 负责输入
准入；提交只校验输出及其对冻结证据的主张，不重跑输入资格判断。

来源引用对照控制层的精确输入别名及工具记录解析，不要求在输出 evidence 表中再次登记。
可选来源表补充定位与科学来源说明；重复引用、多个定位及未使用的绑定来源不会形成整份成果的阻断。
审批检查完整冻结对象和独立审查父链，不以审查者是否抄齐来源表判断完成。分析可直接引用工具保存的
计算文件，原有收据与执行／案例身份检查照常适用。已声明的模型／语义错误保留有界具体原因；
不回显整个输入、异常链或堆栈，未知工程异常仍单独记录。

公开错误包含有界 code、phase、path、message、可修正性与受影响动作，即时回复与持久活动使用
同一份安全详情；未知校验器异常属于工程故障。声明记录尝试的评分工具在解析前登记调用，包括
拒绝与中断，沿用 Run 活动记录和封存证据清单。失败计算可以说明限制，不能证明数值检查成功。
科学 Agent 和独立审查者判断结论范围、所需检查与缺失证据的影响；校验器不从固定检查表推导科学
verdict，也不按科学／工程标签限定案例数量。历史计算经配对清单和完整 Artifact 身份核验来源；
文件接收收据与科学案例对应关系分别保留。新的计算记录必须有控制层收据；提交不重算。

残差诊断先封存受控数值 checkpoint，再尝试绘图。同一个 Worker 工具可用 `checkpoint_alias`
只重试绘图：请求、算法和完整输入 Artifact 身份必须一致，checkpoint 必须是本轮或经控制层
接续接纳的证据；可编辑工作区副本不能充当 checkpoint。绘图失败保留已完成指标、已保存残差
及具体诊断，`computed` 不意味着图片已生成。失败接续复用现有收据接纳路径；科学输入或方法
改变须重新计算。报告修正在封存前留在当前 Run，已封存报告始终保持不可变。

`public`、`support`、`internal` 和诊断用 `all` 是同一目录的只读投影，不是四套注册表：

- `public`：调度 Agent 可选择的科学行为；
- `support`：公开行为依赖的确定性辅助操作；
- `internal`：仅框架测试和自检；
- `all`：诊断联合视图。

领域产物种类使用格式受限的插件标识，不是核心维护的领域枚举。Worker 的结构化结论和后续建议是
封存科学结果，不是调度命令；具体行为只由调度 Agent 从编译目录选择，invoke 在创建前检查准入。
preflight 是不创建对象的可选检查，不构成授权或资源预留。

## 3. 调度 Agent 与 Operation

交互式 Root Agent 读取当前实例的不可变科学输入、编译目录和有界 readiness 建议，从真实科学
矛盾中选择一个最短可辩护的 public Operation。依赖只表达准入条件，不定义固定阶段 DAG。
Root 绑定实例内语义 Artifact 名称并直接调用 `operation_invoke`；身份、资格、审查、预算和
副作用门由控制面在创建前执行。`operation_preflight` 保留为同一请求的可选只读检查。

Worker 不输出具有控制权威的后继 Operation 名称。调度 Agent 可以利用封存的 verdict、领域处置、
缺失输入和建议进行判断，但仍须独立选择目录中的 Operation。`change_request` 与 `review_signal` 只
证明精确独立审查和来源关系，不预先指定下一阶段或后继操作。
旧 `next_action_kind`、`accepts_actions` 与 `recommended_task_mode` 字段及其透传代码已移除；
严格模型不再接受这些额外字段。科学建议通过 `next_actions` 表达，行动仍由唯一编译目录授权。
完成 Run 的 `run_status` 默认使用 `response_profile="decision"`，返回声明的有界结论、限制、
剩余问题和 scheduler signal。使用 `output_fields` 选择具名科学字段，或在 `output_paths` 中
选择非根 payload JSON Pointer，两者不同时填写。decision 中缺省路径或 `[]` 都读取声明的
决策字段。活动 Run 保持短状态，除非显式请求已封存阶段预览。

`poll` 不读正文（`output_paths=[]`）；`navigation` 使用 `output_mode="index"` 返回有界结构
索引。显式 `view="detail"` 且未选 profile 时使用 compat，但不会自动返回完整正文。完整封存
输出只适用于 completed Run，必须显式 `include_full_output=true`、`view="detail"`、
`response_profile="compat"`、`output_mode="values"`，并省略或设 null 的 `output_paths`。
compat + detail + `output_paths=[]` 读取记录元数据，不展开完整正文；`diagnostic_after` 选择
持久化诊断的有界页。

JSON Pointer 原值放在 `selected_output`，不将部分内容放入 `sealed_output`；最多 8 个指针、
累计 32 KiB。路径从 payload 内部起算，例如 `/summary`，不是 `/payload/summary`。values 模式
禁止空字符串根指针；`/` 代表空成员键。已选准确值无需重复读取；超预算子树提供有界一层导航
（32 项、8 KiB），missing、null 与 omitted 分开。完整输出始终需要显式 full-output 标志；
signal 可用性与正文展开分开。失败短响应保留安全诊断与恢复信息，扩大视图不把失败任务变成
已完成科学证据。
运行中 Run 和批量 `run_list` 不暴露科学载荷。若 Run 保存的 Operation 版本或摘要不再匹配当前编译目录，状态
报告 `historical` 并返回封存载荷和可解析的交接摘要，但不恢复资格；生产者插件卸载也不抹去完成记录。
交接不可解析也不遮蔽可独立核验的封存载荷，其限制由 `scheduler_signal_status` 单独报告。
清单和 Worker 输入描述明确标记 historical。`evidence_inventory` 允许历史背景读取；`prior_signal`
与 `revision_base` 在当前端口仍可消费相同类型时允许历史版本，结构化历史 JSON 在创建 Run 前按
消费者输入 Schema 校验。规则依据输入用途，不依据 Agent/Transform 分类。独立审查和精确
修订主体仍须匹配，跨版本修订历史不重置次数限制。同 Operation id/version 且输出端口类型
（schema、kind、media）兼容时，封存科学记录及其审查可继续使用，完整运行 digest 漂移本身不撤销
原对象的证明。科学含义不兼容的变更须提升已有 Operation version 或 schema；新对象不继承旧审查，
不兼容 reviewer 须对原精确对象重新审查。申请新人工决定时，
历史来源族保留原身份，并核验完整来源、输出集合及唯一端口绑定。历史 blocked/revise 经确定性
变换仍传播非合格标记。研究输入资格可以复用原对象的已封存人工决定，条件是 provider id/version
及既有 approval_contract_digest 一致；这不创建决定或恢复旧 Run。Run 续接及外部执行/批准仍比较
完整编译身份；provider 匹配服务默认严格，执行授权不启用兼容放宽。historical 标记和来源原 digest 保留。
结构化对象位于
`sealed_output`，有界 verdict/缺失输入/建议位于同一响应的 `scheduler_signal`。两类审查来源只接受
非通过 verdict，`pass` 不能被当作修订理由；每个信号还必须精确绑定同次调用中的被审查对象。
生产者的公开目录条目同时给出最小 `review_edge`（审查 Operation、输入端口、被审查输出和可接受
verdict），因此独立审查也只从同一编译目录调度，不查角色表或第二套路由配置。public 生产者只可
引用 public reviewer；reviewer 当前不可用时，生产者同步从公开可用集合移除并在 preflight 失败。
Root 调用入口拒绝 internal Operation；support 只保留给已选择 public 行为所需的确定性辅助变换。

科学任务通过编译声明的科学输入端口绑定相关证据原件与前序结果。inventory 是只读上下文；读取
历史材料不恢复资格。机械派生端口不进入 Agent 合同、assignment 或输入文件；控制层沿声明的科学
锚点查回精确来源。缺失或歧义返回可定位的修复提示，不要求 Agent 补填身份表。

Root 的 `artifact_ingest_text(name, text, on_conflict)` 将 1—8,192 个有效 Unicode
码点按原样 UTF-8 登记，保留空白和换行。不可变 `opaque` 文本在元数据中记录
`source_origin=user_via_scheduler`，creator 保留实际调用者；来源说明不混入原文。
登记复用现有实例名称、指纹和修订机制，不创建 Run。所有公开科研 Agent 声明可选
`user_context`，最多四条原文、每条至多 32,768 字节，使用 `prior_signal`/`on_demand`。
它不获得证据资格、不占用 `current_progress` 槽位，各 Agent 原聚合输入额度增加
131,072 字节。assignment 和分析导航显示原文路径与已记录来源；Agent 判断科学意义，
控制层不要求填写采纳证明。

全部输入仍保留在输出来源链中。证据修订及参数资格依据生产 Run 保存的原端口绑定区分
正式来源与背景；Root 和调度层权威重建投影相同的保存记录。这不是第二份持久化状态或
新科学主张。完成节点通过显式原输入创建新 Run；失败工作改变输入后使用 `draft_from`，
`resume_from` 保留精确输入及合同身份要求。用户文本不能替代独立审查或 UI 审批。

分析 Worker 从 `analysis-start.json` 接手：入口提供输入大小/用途、逐字摘录和原字段位置。
TCAD 另在 `analysis-bindings.json` 提供有界项目视图和科学案例值矩阵。控制生成的案例绑定账本
保留在不可变原件和服务端工具输入中，不作为默认阅读或报告任务。TCAD 两份展示文件合计预算
32 KiB；放不下的细节保留原件指针和遗漏计数。视图不是新科学证据，不改变来源身份、资格或
native 文件权限。复用 Agent 核对新绑定并读取本轮相关原件，无需全文重读每个输入文件。完整
接续指导位于 `analysis-start.json`，报告说明位于工作区 `patch_contract`；分析角色提示只保留短导航。

Local Worker 打开任务时返回不可变 assignment 的工具合同位置和指针，不再依赖分析导航是否存在。
Worker 使用工具前读取所选工具的完整 Schema 及局部定义。旧 assignment 缺合同字段时保留冻结
fallback；Hardened 保留内联合同。assignment 损坏是工程错误，不能用更新后的合同替代。
TCAD 作者在最后一次源码诊断前，把初始化覆盖与未测试 reset 路径写入源码注释，使其随封存项目
到达审查者；审查者独立核对说明与实际源码、证明。源码注释本身不是执行证明。

`LayeredDiagnosisReport` 以 `summary` 和 `overall_verdict` 集中表达结论，附证据和可选
`limitations`。旧完整 `gates` 对象、剩余矛盾、下一步和逐假设评估均可省略。受支持的通用、固定
曲线误差与 TCAD 分析 producer 新版本在 exact scope plan 的 `objective_key` 非空时，要求填写
既有 `objective_assessment`；key 为空时仍可省略，也不得据此发明身份。这是 producer context
规则，不是 v1 reader 或 prior 准入迁移。`claim_allowed`
仍由科学 Agent 明确判断；缺少数值诊断层时，声明投影为 `not_evaluable`。这类分析报告由
既有 finalizer 在封存前生成 handoff 状态及正式摘要的短引用；工作区 `patch_contract` 声明
草稿可省略字段，Root 同时读取封存正文与调度信号。TCAD、通用和固定曲线误差分析在其支持的
local backend 共用此行为。历史 Artifact 字节保持不变，也不新增评分前提。
Scheduler 把 completed Run 的实际 scope、封存科学事实与用户成本约束下的工作价值判断分开；
报告中的下一步只是建议，不是目录行动权威。停止继续工作不会把 inconclusive 或 invalid study
改写成物理反证，也不需要新增持久路线状态。

ScientificReview、DeckReviewReport 和 ImplementationGap 同样只要求写一份正式摘要；finalizer
补齐省略的 handoff verdict/summary，保留显式旧说明，封存 envelope Schema 不放宽。通用审查
Schema 描述与 TCAD 工作区 patch_contract 说明草稿可省略字段。新作者模板不再生成机械空值，
gap 可省略 handoff 文件；完整项目仍需其作者 handoff。无法投影时诊断直接指向正式来源字段，
使 verdict/summary 错误可在同一 Run 修正。CriticReview、EvidenceAudit 仍需自己的 handoff
摘要；旧封存记录不改写。

TCAD 实现缺口可携带控制端捕获的有界源码、声明、尝试记录和诊断文件；它们仍是负面开发记录，
不构成可执行项目。审查和修订均接受该交付；修订把旧诊断恢复到 `reports/history`，必须重新
产生当前源码的完成证明。旧缺口若未捕获文件仍可读取，但不能重建先前失败源码。日志摘录维持
现有截断上限，整个缺口仍受 Operation 输出字节上限约束。trusted-local Worker 路由器在前一
Run 终结后可领取同一编译 Operation 的新排队 Run，并清空逐 Run 工具状态。Codex 可复用匹配的
空闲 Agent；不同 Operation ID 或编译摘要、不同目录代次、对自身工作的独立审查仍须新 Agent。记忆不授予访问
旧工作区或使用未绑定事实的权限。

框架管理的诊断日志统一遵循：有界保留原始文件，另行生成展示摘要，在展示截断前定位错误。
TCAD 本地和远端 runner 保留 stdout/stderr 合并原流 `worker.log`，独立诊断文件收集有界的
求解器 `.log`、`.err` 文件，开发与正式执行适用同一机制。超过采集上限明确记录覆盖不足，
不能静默删除日志内容。开发 Worker 获得完整有界脱敏日志路径，可按行分段读取；日志随实现
缺口交接，工具回复仍保持短摘要，调试时间预算不变。启动器、传输和 PDF 失败诊断保存在既有
Run/结果目录中。本机制复用文件读取，不新增日志服务，也不授予读取未绑定旧工作区的权限。

`artifact_catalog(name=...)` 返回精确对象的有序 `parent_artifact_names`：无父件为 `[]`，
当前实例没有名称映射的父件为 `null`。名称对应已保存的父件身份，不回退到最新修订；别名沿用
既有首次创建时间和名称排序。直接父件超过 4096 项时明确报错，查询不写状态、不递归搜索历史。
新调度者沿修订计划追溯到物化计划，从其强类型直接父件恢复原始目标，再将相关上下文显式绑定给
下一 Worker；此路径不增加进度对象或阶段状态机。
`producer_inputs` view 优先从准入共用的同一 producer-family 记录投影即时生产者的冻结端口、项序和准确 ref；
它不递归，也不选择替代对象。历史、跨实例、不可用或歧义生产者均显式标记并提供 `parents` fallback，
当前实例之外不暴露冻结名称。

行为都通过 `operation_invoke` 创建。设备参数 Schema、提取/审查 Agent、覆盖与不确定性
变换以及资格审批均由 TCAD 插件一次注册；通用核心不再导入该 Schema 或编译参数 Operation。
旧角色/变换入口以及直接创建任务、变换、审批和执行的工具不再是产品权威。

## 4. 四类执行闭包

### Agent Operation

编译器把 Agent Operation 投影为 Run 的精确输出合同、输入 exposure、工作区、工具、资源和
review 要求。父调度器用 Codex `spawn_agent` 拉起无父历史的专业 Agent；子 Agent 使用任务工作区的
原生能力、该 Operation 编译出的领域 Worker MCP 和静态专家资源，通过统一 submit 产生结果。
聊天完成只是不可信传输信号，控制面封存的 Run 输出才是科学结果。

Worker 的 `assignment.json` 指向 `result.schema.json` 内同源的结构合同、语义合同和校验阶段。
JSON Schema 拥有必填、类型、枚举、范围和基础嵌套形状；语义合同只补充不能由 Schema 表达的跨字段
或输入绑定规则；context validator 只能使用 OperationSpec 明列的来源，并且不能把缺失的可选端口
重新解释为 Worker 输出错误；这种访问属于插件契约故障。内容与上下文校验器只有显式抛出
`SemanticRuleViolation`，才能按输出端口绑定的 `rule_id` 报告 Worker 可修订错误；该异常自身不携带
规则编号，其他异常均属于插件契约故障。文件集合、大小、路径、不可变父链和权限属于封存安全门，科学质量由声明的
独立审查 Operation 判断，而不是由控制面增加隐藏内容规则。

当前默认 Local 路径采用软隔离：控制面把 assignment、输出 Schema、显式输入、可选恢复草稿和领域
工作文件物化到一个 Run 工作区，Agent 可以直接使用 Codex 原生文件与代码能力完成任务。普通任务内
读写不是逐文件注册能力，OperationSpec 只声明领域工具、网络或外部副作用等额外能力。输入源
Artifact 不会因工作区副本被修改而改变，只有声明位置的完整输出通过 Schema、父链和提交校验后才
能登记为正式 Artifact。该边界控制科学上下文和正式结果，不承诺操作系统级文件不可见性。
部署时，正式 Artifact 与控制面数据库仍位于状态根；可信本地 Run 工作区单独放入 Codex 可写的项目目录，
控制服务与 Worker 必须使用同一个编译路径。Run 工作区不是第二套状态权威。

Local 分析工作区在失败时保存 `output/` 与 `scratch/` 的有界、带版本草稿子集。不可变恢复副本与
原目录待清理状态分别表达：Run 失败不证明原生写入者已停止。停写未确认、存在未保存文件或原始日志时，
保留原目录。普通 traceback 可通过规范化副本交付，字节码缓存排除；恢复草稿不继承科学资格。

分析工作区从已安装核心包物化可选的标准库启动脚本，由 Worker 本地调用，不增加服务器执行工具。
它限制日志和数值子进程资源，每次按绝对 Run 截止减去可调整提交余量截定请求超时。Root 只读取
有界的计时与状态元数据；未观测执行仍为未知，不阻断提交。分析者逐个原子保存完整数值工作单元，
绘图从已保存数据局部重试，可选渲染失败不抹去数值结果。`run_status.bound_inputs` 和有序
`artifact_catalog.parents` 只投影精确绑定，不选择替代对象；TCAD 计划/审查端口保持原执行身份，
新分析方案与审查通过 `current_progress` 绑定。

直接修订是普通 Agent Operation：它声明一个 `revision_base` 输入和一个完整输出；两者使用
相同 Schema、媒体类型、codec 和 Schema 资源，并声明独立审查合同。基线可以是必需输入，也可以
与唯一 `change_request` 组成一个无审批、全有或全无的可选输入组。后一种声明使同一 Operation 在
未绑定该组时创建对象，在绑定该组时修订对象，不增加模式字段或平行修订 Operation。编译器静态判断
Operation 是否具备修订能力，运行时只从冻结输入派生本次调用是否激活修订。运行时采用写时复制：普通
JSON 对象把基对象 payload 预置为可编辑的 `output/result.json`，同时声明物化器和最终器的领域工作区
对象（当前为 TCAD 工程）由插件展开精确旧文件并组装结果。Worker 只增量编辑审查涉及的内容，提交时仍接受完整 Schema、
上下文和父链校验，并发布完整不可变新对象；未修改 payload 会被拒绝。该机制复用原生产者的 Agent、
工作区、工具和校验，不建立万能修订管理器，也不创建补丁科研实体。旧对象保持不可变，新对象不继承
旧评审或资格。可选修订必须声明有界次数和问题指纹；目录编译会拒绝畸形 `revision_base` 声明。
原结构化补丁 Artifact、补丁应用 Operation、
差异收据、旧 Task 投影和 Root 递归生产者族仍保持删除。

Codex 只注册一个 `scidiscovery` MCP，公开 `scid_catalog`、`scid_describe`、`scid_call`。
目录仅给名称与用途，选中后按需取得合同；实际调用复用原 Root/Worker 处理器。Operation describe 默认返回兼容的 full 合同，
也可从同一编译项投影 `invoke` view：保留 digest、完整输入/准入、审查、修订、attempts 和 runtime 适用性，
移除不会改变合法调用的执行器细节；interface describe 仍只支持 full。
Root 派发子 Agent 后，以平台返回的线程 ID 调用 `worker_attach`，绑定准确的新 Run，随后通知子 Agent 开始。
服务器根据平台随调用提供的会话/线程元数据解析绑定；Worker 不能通过参数自选角色、Run 或 Root 权限。
绑定持久化于已有 Run 数据库并随实例归档；新 Run 的编译 Operation、模型与推理强度必须匹配才可复用线程。
本地文件、终端和 Skills 仍遵守原有软隔离边界。这不是针对同一操作系统恶意用户的强安全隔离，
也不把提示约束夸大为沙箱事实。
当前唯一接入的派发路径是 `spawn_agent`。未启用的独立进程基座及专项测试已移至
`experiments/worker_process_v2/`，不进入产品包；其实验结果不能作为当前生产隔离证明。
旧 `run_compiled_codex_worker.py` 独立 CLI 探针不能运行新的统一入口角色，会明确报错；它不属于生产派发路径。

### Transform Operation

Transform 是无 Agent 判断、可重放的确定性函数，例如 intake 拆分、实验意图物化、TCAD 工程
打包、运行证明、曲线 bundle 和评分。它消费精确 Artifact，输出内容寻址 Artifact 并保留父链。
Transform 不能调用求解器或生成科学结论。

普通消费者可以只读取某个 Transform 的一个输出。只有确实需要一次调用全部结果的消费者，才在
自己的 OperationSpec 中声明一个可选 `complete_transform_family`：列出与生产者同名的输出端口和
输入端口。Root 仅从冻结的 Operation 摘要、调用指纹、实例绑定和父链恢复该次调用的完整成员，按
端口机械比对，不读取领域 payload。该声明目前只支持一个生产族；它不建立 family 注册表，也不让
生产者预判下游用途。

### Approval Operation

Approval Operation 的插件 projector 只把精确 subjects 投影成核心固定
`ReviewDocument`。Root 不应解释领域 Schema，审批 UI 只渲染固定安全节点、转义文本并提供受限
原始附件视图。人工决定只由回环 UI 写入，绑定精确 subjects、operation identity 和合同摘要；
对话不能代替点击。生产者族由编译端口、调用指纹、Run 完成合同和精确父链派生。直接修订按完整
新输出族重新审查，审批不再递归恢复补丁链。

### Effect Operation

Effect Operation 的 `operation_invoke` 创建不可变执行请求；编译合同显式允许时，可由管理员配置
授权。TCAD 同时不超过配置的总存储和墙钟额度时，不创建人工 approval；其他请求按配置进入
人工审批或拒绝。独立科学审查和精确身份仍然有效。`execution_start` 在提交前重判当前策略；
未知提交先查询原冻结描述符，不能重复启动或通过重命名再次取得同一项目额度。状态与实例 UI
展示 `authorization.source`（policy/human/none）、策略摘要及冻结预算。

`execution_sync` 仅刷新求解状态和有界日志，终态也可刷新；`execution_status` 只读已保存观测，
不联系适配器。产物传输由显式 `execution_collect` 启动，收集完成后由 `execution_outputs`
发布语义名。daemon 统一拥有一个收集槽，消费接收时冻结的总预算（默认600秒，含停止回收）。
私有控制监督进程持锁，直到唯一工作进程组实际停止；daemon退出也不提前释放，不依赖传输程序持锁。
重复请求不延长活动预算，其他执行忙时直接返回、不排队。完整文件及稳定输出清单保留以支持
传输和登记中断后的恢复。适配器仅实现传输，可消费共同 `CollectionContext`，不另建调度器。
查询、单文件、无进展默认预算分别为5、120、30秒。

工程故障使用共同的有界脱敏投影。Root 按实例/会话范围通过 `diagnostic_read` 引用读取详情，
Worker 在自身工作区保留可读报告。既有 Run 活动记录还提供 MCP 调用时序。本地可信工作区
共享可选进程观测入口：分析保留既有执行策略，其他角色继承原环境和资源限制。观测缺失、
损坏均明确报告，不能增加科学提交要求。

错误观测在截止时间后或 Run 终态仍追加到既有活动记录，不续预算、不重开 Run、不接收成果。
同次 MCP 调用的开始与结束归属同一 Run，包括空闲 Worker 打开下一份 assignment 的情况。
选定任务后打开失败，失败归属该 Run 并保留原原因，不能把前一个 Run 的完成当作此次打开结果。
`run_status` 默认仍返回精简摘要；`diagnostic_after=0` 读取已保存错误的第一页，以 `next_after`
续读，`diagnostic_limit` 最大100。`run_list` 返回 `next_before`，供可选的语义名 `before`
游标续读。两种查询均限当前实例；旧事件缺失详情时明确保留缺失，分页不能补造从未记录的信息。

## 5. 控制面与数据面

默认控制面只有四类相互独立的事实：

- Artifact/CAS：不可变字节、内容摘要、父链和实例语义绑定；
- Run：精确 Operation、输入、后端、`queued/running/completed/failed` 和完成收据；
- Approval：仅在 Operation 明确要求时保存精确 subjects、选项和人工决定；
- Execution：副作用请求、授权、提交、同步、收集和不确定状态恢复。

由 Operation 创建的 Run、Artifact、Approval、Execution 记录当前编译 operation id、version
和 digest；用户直接摄入的原始来源 Artifact 可以没有生产 Operation。Worker 只获得 Run 本地别名，
不获得内部 Artifact、Approval、current 写接口或外部执行身份。主 Agent 不制造 Worker 科学输出，
Worker 也不直接写控制元数据。默认 `LocalTrustedBackend` 只管理 Run 目录。已有
`HardenedWorkerBackend` 作为非默认实验/可选实现保留，但强隔离不属于当前阶段的产品完成门，也不
得反向增加默认 Operation、插件或 Worker 的协议成本。其当前没有受控读取预置结果的工具，因此会
明确拒绝直接修订 Operation，而不是宣称一个真实 Agent 无法完成的能力。

## 6. 通用与领域边界

| 通用核心 | 插件负责 |
| --- | --- |
| OperationSpec ABI 与一次性编译 | Operation 与窄组件声明 |
| Artifact、Run、Approval、Execution 生命周期 | 领域 Schema、validator、guard、projector |
| Root MCP、Run 生命周期和工作区后端 | 专业 prompt、工作区 hook 和领域工具 |
| 固定安全审批文档与 UI | 审批内容投影，不提供 HTML/脚本 |
| 通用 preflight/invoke | 确定性变换、runtime factory 和副作用 adapter |

TCAD 插件通过 `ExperimentCapability` 提供求解器项目声明、实现准备、调试、原始结果分析与
内部执行 Effect，不再注册独立的公开作者/修订/审查流水线。控制层生成 `ExecutionPackage`
（`tcad.execution-package.v2`），绑定精确源码、文件和能力；可选审查是独立事实，嵌入报告本身
不授予执行权限。SProcess 与 SDevice 共用通用实验任务。

curve-score 向完整分析任务提供确定性评分/诊断工具；curve-figure-evidence 提供图证据提取、
独立证据审查及所需算法；InGaAs Fig.4 插件提供项目评分器。核心拥有生命周期、绑定和资格，插件
拥有领域算法与声明组件。组件配置身份、catalog ABI 与摘要、public/support/internal 可见性和
带版本的 Schema ID 均保留为平台合同。当前真实插件的依赖边界仍需专门审查，不能因此宣称所有
插件已经不依赖核心内部实现。

确定性 Transform 组件从按端口分组的精确输入字节一次性产生全部输出；涉及多个输出之间关系的
约束，由拥有算法的可信插件组件在返回前闭合。通用调用器只执行编译端口的 Schema、媒体类型、
基数和逐项 validator 校验，再以同一输入父链登记不可变 Artifact；它不解释领域字节，也不按插件、
Operation 或 Schema 分支。Agent 主输出的 context validator 则获得其 OperationSpec 显式声明的
输入来源和工具收据，用于核验输出引用及记录完整性，不重新判断输入就绪状态，也不替科学 Agent
决定结论。这不是新的注册表、状态或科学判断入口。Agent collection
声明虽可编译，但 Run v1 不调用它们作为正式提交；依赖集合提交的可选能力不会进入当前后端的
`public` 调度视图，只在 `all` 诊断视图中给出不可用原因。

## 7. 当前明确限制

- 默认 Local 后端有意采用软隔离，Codex 原生文件可见性不是技术沙箱，`SEC-002` 保持 known_issue，
  但不阻断当前可信本地原型完成；
- Run v1 只接受一个 Agent 主结果；声明 collection 输出的 Agent Operation 统一显示为当前后端
  unavailable，preflight 失败关闭；Transform 多输出不受此限制；
- Hardened v1 的历史实现只支持纯 MCP Operation；当前阶段不扩展、不补齐，也不以其通过作为完成
  条件；
- 审批 UI 已增加结构化参数、证据与原件入口；真实 Fig4 部署后的阅读验收仍需单列，不以合成页面代替；
- 当前测试证明工程边界和 TCAD 最小纵向路径，不证明论文图数字化精度、Solver 科学正确性、三领域
  通用性或相对单 Agent 的统计优势。

R5-L 不增加科学图、插件生命周期系统、第二注册表、第二 current 或固定科研流程。

## 8. 持久化和信任边界

运行状态位于源码和临时目录之外；SQLite 保存控制生命周期，CAS 保存不可变 payload，服务密钥
单独存放。ResearchInstance 与语义绑定是唯一运行时 current；安装器不读取独立 YAML current。
孤立旧 binding 原始行不会被启动过程合成为 `legacy.*` ResearchInstance，也不会进入实例列表、
会话 current 或会话绑定候选；系统不为其增加在线迁移或兼容入口。
生成的平台配置含机器绝对路径，每台设备必须重新生成。

Worker prompt、任务目录和 JSON 校验提供上下文软隔离，不是完整系统沙箱。当前强制边界是精确输入
绑定、输出封存与校验、Artifact 登记、独立审查、人工审批和外部执行授权；不是对每次任务内文件
读取建立控制面记录。外部执行策略仍限制 executable、arguments、环境、资源和输入目录。科学接受
仍依赖来源、独立审查、确定性报告和结果诊断。

TCAD 分析可选择检查所绑定终态执行的原文件并接收明确的输出映射。注册工具将原始字节及持久回执保存在本 Run 的 Artifact 集合中，冻结输入不变。报告和精确证据快照一起完成；Root 仅在 completed 后公开附属语义名称。后轮显式绑定恢复清单及原始文件，可重放原计算别名。检查服务缺失或旧 runner 不支持时仍可交付有限分析。求解器退出结果和收集错误分别保留；恢复不重写原执行，也不授予科学成功。

## 9. 实例浏览、轨迹与资料维护

现有审批 UI 服务提供实例概览、节点、来源图件和资料管理。`InstanceReadModel` 按实例绑定及
精确冻结父链读取记录；通用/TCAD 展示提供者仅把已有原值映射成带出处的正文、参数表和安全图件。
未知字段、缺失来源和展示失败保留缺口，不成为 Worker 输出拒绝。浏览权限、维护权限及原审批
token 各自限定范围；新页面不变更审批 subjects、期限或决定权威。

UI 内只有一个有界观测器，订阅时轮询节点元数据并通过 SSE 发送定位和游标。成果按需读取，
`state_root/ui/workbench.sqlite3` 保存可重建视图与实际观测事件。原始事件时间和首次观测时间分开，
没有历史遥测就不补造历史；浏览器和缓存不触发科研 Run、执行或收集，也不增加 Agent 交接字段。

归档是用户明确发起的存储维护：精确实例资料迁到工作区 `.scidiscovery-archive/instances`，
其他实例仍依赖的共享副本和不能确认归属的资料保留。只读归档使用原记录身份与字节；恢复不重绑
旧会话、不重启进程、不更新资格或延长审批。永久删除尚未提供。持久维护门覆盖 Root、Worker、
审批写入及收集后台的实际写入生命周期；无法确认原生写入者停止时保留现场并拒绝迁移。

为恢复原活动编号，Run 库新增一个全局 `run_activity_sequence` 分配器；普通活动写入在原事务内
分配 rowid。它不属于实例快照，避免一个实例归档后，其他实例重用其历史活动编号。科学 Schema、
Operation 和工具合同保持不变；归档定向事务恢复原 append-only 触发器，维护清单不属于可清缓存。
范围、故障证据和部署边界见[实施记录](plans/evidence/instance-workbench/IMPLEMENTATION.zh-CN.md)。

## 原生权限角色与外部证据

Root 启动指令来自 `roles/scheduler.md` 及项目 `AGENTS.md` 的受管 scheduler 区块。正常操作读取
自足的 catalog 与所选可调用合同，不要求打开指南。`roles/scheduler/` 仍随安装提供，限异常维护
按需使用，不是正常阅读 gate 或第二套路由权威。安装保留非受管项目说明。

Local 工作区包含只读的 `tools/read_tool_contract.py`，仅读取冻结 assignment 中的工具合同。
读取器在 scratch 自动保存可丢弃的阅读回执，调用者只指定工具名。后续相关合同可返回精确
JSON Patch，始终引用最近一次完整响应，不引用前次差异。工作区、assignment 或合同变化，
回执缺失/过期或差异更长时退回全文。上下文丢失后用 `--full` 重读：阅读回执不能证明模型
仍然保留基准。回执故障不拒绝科研任务。不新增 MCP、合同注册表、科研状态或权限，不改变
实际 Schema 和成果。旧工作区仍可直接读原合同；Hardened 不新增原生执行权限。

Local 工作区还提供 `tools/read_output_schema.py`，仅读取当前 `schema/result.schema.json`。
默认保留 envelope/payload 字段结构、所有公共约束，展开必填引用以及 `--field` 选择字段的完整
引用闭包，并列出未展开定义的原文位置。`--definitions-only` 为已保留的当前总览补读字段；
`--full` 返回完整原文。阅读视图不是新的校验 Schema。嵌套资源 ID 与循环本地引用从同一原件
解析；不支持、动态或外部引用说明原因并退回全文。CLI 在 `.read-input/` 保存可丢弃的 Schema 阅读元数据，多 --field 合并处理，后续只补充
未返回的定义、不重印总览；回复或上下文丢失时 --full 恢复原文。缓存缺失、损坏或不可写
退回完整所需视图，不建立科研状态或记忆证明；每次读取当前文件。
不支持的 envelope 形状与旧工作区沿全文读取路径；提交校验和所有科学字段保持不变。

Local 工作区还安装 `tools/read_input.py`，按原文或 JSON Pointer 精确读取，完整回复默认
4 KiB、最大 8 KiB。调用者选择输入别名或唯一端口，可重复 `--pointer` 选取多个字段；
`--file` 选择 assignment、schema 等明确的任务内文件。回复只有精确正文与简短结束/续读
标识，不重复输出转义后的 fragment 包装、路径、哈希或偏移；数字保留原词形，片段不冒充
完整 JSON。仅安装的输入/Schema reader 在 `.read-input/` 内维护可丢弃阅读缓存，避开 output/scratch
恢复扫描；其他 helper 缓存仍放 scratch。首次指定选择后，裸 `--next`、`--repeat`、
`--restart` 沿用当前材料/文件模式、字段和预算。显式读取切换选择，失败不切换；无导航时
须明确选择。最近回复不确定时 repeat，更早内容缺失时 restart。锁保证缓存更新，不保证交付顺序或已读状态。
缓存不跨 Run、不成为科研状态，只检测本次选择首次读取后的内容变化，不核验封存原件哈希；
控制层继续负责输入绑定与工作区初始化。旧工作区收到定向原文读取指引，不热换冻结 helper。
该工具不限制任意原生 shell 输出、不新增提交门禁。analysis launcher 默认返回短观测与日志路径，stdout 数据消费者显式用
`--display raw`，原生 inherit 策略保持 raw 默认。采集上限与展示预算分离。恢复状态只显示
覆盖与遗漏数量，原遗漏清单由 `run_status(view="detail", output_paths=[])` 读取。

Codex 平台角色按 `NativeToolPolicy` 声明的 shell、识图和网页搜索权限组合共享。
科学 Operation 保留各自身份和合同。角色文件仅提供生命周期引导；每轮 assignment
携带当前编译的 `role_instructions`；控制层在 attach 检查 Operation、编译 digest 与封存
profile，在 Worker gateway 检查实际 model/effort，Agent 不再比较角色哈希。Local open
从前一线程绑定及前后工作区实际角色、Schema、工具合同生成 reading_guidance，提示未变
且仍保留时可复用，不建立新登记表；原件不可用则要求读取，动态 Schema 独立比较。
同时依据持久化不可变绑定和用途描述，按别名给出输入未变、变化、新增或未知的信息；
历史不完整时回退为未知。这只是导航，不是阅读登记或模型记忆证明，也不参与提交准入。
重新判断可复用仍保留的原文；缺失上下文或需要科学复核时定向补读。精确原件与总体目标始终可访问。仅受控复用且
完整正文仍在上下文时可跳过重印；首次、续接关系不确定、上下文丢失后必须重读。每轮仍读取新任务、
总体目标/输入绑定、语言与预算。Worker MCP 能力仍由
实际绑定的 Operation 决定。平台角色相同不允许跨 Operation 复用，也不允许审核自己的
成果。安装只移除过时的受管角色文件，不改写历史 Run 或 Artifact。

`science.evidence.extract.v1` 声明实时网页检索及可选的 `worker_capture_source`。
抓取的公共 HTTPS 原文复用现有工具证据存储，由控制层生成引用别名、保存 URL 和抓取时间；
它们是外部来源，不冒充仿真派生产物。来源清单和原文可绑定给 intake 审查及有界修订。
搜索摘要不等于已保存的科学证据；无法取得原文时，应限制结论。其他固定来源的提取与
审查 Operation 不会隐式获得搜索权限。

每轮抓取最多八份原文，每份 16 MiB，最多 24 次 HTTP 请求（含重定向）。传输、DNS 和
重定向均有界，失败保留工程诊断。原生网页检索受 Run 预算及平台策略约束，不计入此 HTTP
计数器。trusted-local 文件系统限制仍是提示边界；权限角色不新增操作系统沙箱。

## Agent 执行配置与科学合同的边界

公共默认在服务启动时加载一次；实例稀疏覆盖保存在 scheduler 数据库的实例行，由同一个配置解析器逐字段合并。优先级为实例任务覆盖、实例默认、公共任务覆盖、公共默认、Operation 兼容默认。语言只按实例统一设置。模型名称不维护第二份目录；平台不可用时保留原错误，不自动替换模型。

invoke 在创建时解析并冻结配置。可选预检生成完整 `normalized_request`，可原样用于 invoke，但不预留动态准入条件。新 Run 冻结模型、推理强度和语言，行为值进入请求指纹，来源说明不参与幂等身份。Run 快照投影给调度方、Worker assignment 和页面，提交不读取最新配置。新写科学叙述遵守语言偏好，字段、代码、单位、引述和要求精确复制的文字不改；输出校验不检查语言。尝试次数仍由原恢复策略管理：显式值优先，恢复链沿用已有调度预算，新的实例默认不会自动延长恢复。

`ExecutorRef.model` 及 permission 模型保留为旧编译摘要中的兼容默认；动态覆盖不重编译科学 Operation。Codex 角色文件不再固定模型/强度，调度使用同一角色显式传参；只有 Operation ID、编译摘要、原生权限组合、实际模型/强度匹配且符合独立审查规则时复用 Agent。语言从新 assignment 读取。未观测配置不声明匹配，interrupt 不等于关闭。

仅增加 `scheduler_instances.agent_settings_json/agent_settings_revision/agent_settings_updated_at` 和 `runs.execution_profile_json` 四列。历史 NULL 表示未记录。旧归档原件不改；恢复采用与安装相同的四列 ALTER 定义生成期望视图，缺失值固定为 NULL/0，并在预检、事务导入和续接收尾应用。无关结构、索引、触发器和记录差异仍冲突；缓存清理不能删执行配置。没有新增状态机、科学 Artifact 类型、翻译角色或模型角色池。

新实验任务绑定科学材料和可选科学文件；控制层准备精确执行包并解析私有执行绑定，不要求负责人
填写 capability ID、审查 witness 或路由字段。Effect 的可选 preparation 仍属于编译 ABI：变换、
输出 Schema 和 validator 都进入身份。外部副作用受适用策略或 UI 授权、精确提交查询和累计执行
预算约束。内容改变产生新对象，不自动继承旧审查资格。

`agent-settings.json` 还配置 `helpers` 与 `execution_io`。公共值与实例显式字段合并，在创建 Run
时冻结，恢复沿用原快照；实例显式写入与包默认相同的值仍能覆盖公共配置。这些是控制配置，不是
科学端口或 Agent 表单。`execution_io` 默认值为 `max_export_bytes=2000000000`、
`read_page_bytes=16384`、`collection_timeout_seconds=600`、`file_timeout_seconds=120`、
`idle_timeout_seconds=30`，容量单位为字节，时间为秒。实验文本分页、流式导出和收集使用冻结值；
导出与收集还受 Run 剩余时限约束。它们与插件配置的求解器存储/墙钟自主授权、RAM 上限分开，
修改这些值不授予求解器执行资格，也不延长正在运行任务的截止时间。

科学语义冲突先回到科学决策；等价的局部工程修正在作者任务内完成。四模块是完整任务职责，
不是固定流程。静态实现/审查不能证明线上运行能力、耗时或 token 收益；本轮未运行测试或部署。
