# 当前架构

简体中文 | [English](ARCHITECTURE.md)

本文描述 R5-L Run v1 上经 R5-M 裁剪、并由 R5-N 收敛调度权威后的当前架构。历史设计与失败审查
保留在 `docs/plans/`；当前实施权威是
`docs/plans/R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md`，R5-L 与 R5-M 计划保留为
已通过的历史基线。
设计宪章和33项当前
行为约束分别位于 `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md` 与
`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`。

## 1. 设计原则

SciDiscovery 的基本行为原子是 `OperationSpec`。它是一份不可变、可编译的行为闭包声明，而不是
包含全部实现的巨型类：声明输入/输出端口、执行种类、组件引用、资源上限、工作区、工具、网络、
独立审查、人工审批与副作用要求；具体 codec、validator、guard、projector、workspace hook、
Worker tool 和 runtime factory 由插件内的窄组件实现。

当前 Operation ABI 17 要求 Agent 输出引用结构化语义合同。每条不能由 JSON Schema 表达的规则
具有稳定 `rule_id`、说明、输出路径和所需输入；编译器拒绝未知输入以及把可选端口暗中声明为必需
输入的规则。每个 Python 内容或上下文校验器必须绑定其中一个已声明 `rule_id`，否则目录编译失败。
编译器把这份合同和从端口、校验器绑定及修订形状机械派生的校验合同嵌入同一份
`result.schema.json`。提交路径先执行这同一份 JSON Schema，再执行少量已绑定语义规则；诊断只能
引用 Worker 已见的 `rule_id` 和字段路径，不得维护提示词专用或提交专用的第二套规则。

科学判断属于调度 Agent 和专业 Worker；控制面只拥有身份、不可变记录、最小上下文投影、生命周期、
资格与副作用门禁；确定性代码只做可重放的机械变换；领域 adapter 只做外部副作用。

每份实验保留有序 `objectives` 及其非空精确子集 `current_objectives`。物化时将原始总体目标放入
每份实验，只展开已经声明的本轮 case；选择理由、后续目标和条件保留在既有 rationale 字段。
未覆盖目标是否妨碍本轮实验，包括同一 observable 下的多个目标，由设计者和独立审查者判断。
需要曲线合同时使用显式 target bindings，局部成功不代表未覆盖的总体目标已经闭合。
曲线评分是结果分析的可选工具，不是 author 或执行的前置条件。通用分析与 TCAD 分析是替代入口，
TCAD 工具在同一 Run 中解析已绑定原始输出并评分。评分不受支持只限制相应定量结论，不阻止受限分析。
即使不调用评分工具，计划、审查、执行、文件与 case 的确切身份检查仍然适用。

## 2. 注册、编译与三种视图

系统只有一个 entry-point group `scidiscovery.plugins`；每个入口返回一个 `PluginDefinition`，
同一发行包当前可以发布多个插件定义。一个插件同时声明冻结组件元组和由这些组件组成的
Operations。组件没有独立 entry point，插件私有实现也不能由 Root 或 Worker 按 Python 路径二次
发现。

启动时 `compile_installed_catalog()` 一次性完成：

1. 插件协议、编号、版本与依赖校验；
2. 组件引用闭包、类型协议、静态资源摘要和运行时工厂校验；
3. Operation 端口、结构化语义规则、资源、权限、review/provider 图与审批合同校验；
4. 生成包含 operation id、version、digest 和冻结实现引用的唯一 `CompiledCatalog`。

既有声明还一次编译出静态 Worker 工具 Schema 和输出合同，目录、任务文件、MCP 与提交入口复用
这些投影；每个 Run 的别名加入独立副本。静态材料先排除自身 digest，再进入既有身份摘要结构。
Root 与 lifecycle 工具保留各自声明，共用严格 JSON 参数解析和诊断。preflight/invoke 负责输入
准入；提交只校验输出及其对冻结证据的主张，不重跑输入资格判断。

公开错误包含有界 code、phase、path、message、可修正性与受影响动作，即时回复与持久活动使用
同一份安全详情；未知校验器异常属于工程故障。声明记录尝试的评分工具在解析前登记调用，包括
拒绝与中断，沿用 Run 活动记录和封存证据清单。失败计算可以说明限制，不能证明数值检查成功。
科学 Agent 和独立审查者判断结论范围、所需检查与缺失证据的影响；校验器不从固定检查表推导科学
verdict，也不按科学／工程标签限定案例数量。历史计算经配对清单和完整 Artifact 身份核验来源；
文件接收收据与科学案例对应关系分别保留。新的计算记录必须有控制层收据；提交不重算。

`public`、`support`、`internal` 和诊断用 `all` 是同一目录的只读投影，不是四套注册表：

- `public`：调度 Agent 可选择的科学行为；
- `support`：公开行为依赖的确定性辅助操作；
- `internal`：仅框架测试和自检；
- `all`：诊断联合视图。

领域产物种类使用格式受限的插件标识，不是核心维护的领域枚举。Worker 的结构化结论和后续建议是
封存科学结果，不是调度命令；具体行为只由调度 Agent 从编译目录选择，并经统一 preflight 决定能否执行。

## 3. 调度 Agent 与 Operation

交互式 Root Agent 读取当前实例的不可变科学输入、编译目录和有界 readiness 建议，从真实科学
矛盾中选择一个最短可辩护的 public Operation。依赖只表达准入条件，不定义固定阶段 DAG。
创建前由 Root 绑定实例内语义 Artifact 名称并调用同一 `operation_preflight`；真正身份、资格、
审查、预算和副作用门仍由控制面执行。

Worker 不输出具有控制权威的后继 Operation 名称。调度 Agent 可以利用封存的 verdict、领域处置、
缺失输入和建议进行判断，但仍须独立选择目录中的 Operation。`change_request` 与 `review_signal` 只
证明精确独立审查和来源关系，不预先指定下一阶段或后继操作。
旧 `next_action_kind`、`accepts_actions` 与 `recommended_task_mode` 字段暂时保留为可解析兼容数据，
所有控制路径均忽略其值；它们不是第二行动目录，也不能导致调用被接受或拒绝。
单个完成 Run 的 `run_status` 返回已校验、已封存的科学载荷，供调度 Agent 做这项判断；运行中 Run
和批量 `run_list` 不暴露科学载荷。若 Run 保存的 Operation 版本或摘要不再匹配当前编译目录，状态
报告 `historical` 并返回封存载荷和可解析的交接摘要，但不恢复资格；生产者插件卸载也不抹去完成记录。
交接不可解析也不遮蔽可独立核验的封存载荷，其限制由 `scheduler_signal_status` 单独报告。
清单和 Worker 输入描述明确标记 historical。`evidence_inventory` 允许历史背景读取；`prior_signal`
与 `revision_base` 在当前端口仍可消费相同类型时允许历史版本，结构化历史 JSON 在创建 Run 前按
消费者输入 Schema 校验。规则依据输入用途，不依据 Agent/Transform 分类。当前独立审查和精确
修订主体仍须匹配，跨版本修订历史不重置次数限制，退休审查不提供当前资格。申请新人工决定时，
历史来源族保留原身份，并核验完整来源、输出集合及唯一端口绑定。历史 blocked/revise 经确定性
变换仍传播非合格标记。可信依据输入和执行授权保留精确合同门；历史读取不恢复旧批准或旧 Run。
结构化对象位于
`sealed_output`，有界 verdict/缺失输入/建议位于同一响应的 `scheduler_signal`。两类审查来源只接受
非通过 verdict，`pass` 不能被当作修订理由；每个信号还必须精确绑定同次调用中的被审查对象。
生产者的公开目录条目同时给出最小 `review_edge`（审查 Operation、输入端口、被审查输出和可接受
verdict），因此独立审查也只从同一编译目录调度，不查角色表或第二套路由配置。public 生产者只可
引用 public reviewer；reviewer 当前不可用时，生产者同步从公开可用集合移除并在 preflight 失败。
Root 调用入口拒绝 internal Operation；support 只保留给已选择 public 行为所需的确定性辅助变换。

设计和计划审查可选绑定 `current_progress`、`experiment_results`、`result_analysis` 三组原件，
每组零到四项、每项至多 8 MiB、全部输入合计至多 32 MiB。它们是 `on_demand` 只读
`evidence_inventory` 文件。仅 Agent 的 inventory 输入跳过 producer-output 资格检查；实例、
大小、current、完整 family、cohort、claim、revision 和 effect 门禁仍走原路径。Schema/media
通配对仅允许用于 `handoff_only` 或 `on_demand` inventory。读取历史不恢复退休资格。
Deck review 将精确 project 作为 `prior_signal`，实现不完整时可以封存负面审查；通过审查、
包装和执行仍须满足原实现要求。

TCAD 实现缺口可携带控制端捕获的有界源码、声明、尝试记录和诊断文件；它们仍是负面开发记录，
不构成可执行项目。审查和修订均接受该交付；修订把旧诊断恢复到 `reports/history`，必须重新
产生当前源码的完成证明。旧缺口若未捕获文件仍可读取，但不能重建先前失败源码。日志摘录维持
现有截断上限，整个缺口仍受 Operation 输出字节上限约束。trusted-local Worker 路由器在前一
Run 终结后可领取同一编译 Operation 的新排队 Run，并清空逐 Run 工具状态。Codex 可复用匹配的
空闲 Agent；不同编译角色、不同目录代次、对自身工作的独立审查仍须新 Agent。记忆不授予访问
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

当前 Codex 原型的工具可见性仍有明确限制：父会话可见的 Worker MCP 可能暴露给子 Agent；编译提示
会显式列出允许和禁止的领域工具，服务端会拒绝未声明的领域工具，但原生文件能力只受软隔离约束。
文档和资格报告不得把提示约束夸大为沙箱事实。
当前唯一接入的派发路径是 `spawn_agent`。未启用的独立进程基座及专项测试已移至
`experiments/worker_process_v2/`，不进入产品包；其实验结果不能作为当前生产隔离证明。

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

Effect Operation 的 `operation_invoke` 在创建精确副作用请求后，直接按同一编译审批合同建立待人工
决定的请求并返回精确回环 UI 地址；它不会写决定或启动副作用。UI 决定后，调度器显式调用
`execution_start`，再做有界 `execution_sync`。唯一 Execution 生命周期负责幂等、状态映射、未知
提交恢复和原始输出登记；已编译 runtime factory 提供的领域 adapter 不能修改科学对象或批准自己。

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

TCAD 插件目前注册 deck author/reviewer、工程工作区与调试工具、打包/运行证明/控制等价变换和
求解器执行 Effect；curve-score 插件注册曲线合同、规范曲线、评分与诊断。TCAD 结果分析组合本插件
的原始输出解析器与曲线插件的确定性评分函数，不增加反向依赖。最终分析校验核验工具收据、计算记录
和精确来源引用，不重跑评分。原始证据直接引用绑定别名，计算证据引用工具返回的记录，无需再次填写
同一份案例映射；只读绑定描述符按登记身份区分同内容文件。可选
curve-figure-evidence 插件注册论文曲线图证据提取/独立审查及其工具，并复用曲线插件的确定性
算法；InGaAs Fig.4 项目插件只注册项目冻结评分能力。核心
不识别曲线 manifest、固定脚本名或图证据集合；原生工具和领域工具均由编译 Operation 投影。
插件不得复制控制面的身份或生命周期。

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
- 审批 UI 的安全合同已经自动化覆盖，但信息层级和视觉可读性仍是产品缺陷；
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
