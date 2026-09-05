# R4：领域插件、执行适配器与审批视图迁移实施记录

状态：R4-A 已通过第四轮独立审查并正式收口；R4-B 已通过独立审查并正式收口；
R4-C 已通过独立审查并正式收口；R4-D-A 经四轮独立审查通过；R4-D-B 经六轮独立审查通过并
发布清单收口已通过独立审查；R4-D-C 已通过独立审查；R4-D-D 已通过独立审查。R4-D 的功能实现
已经收口，正在执行最终发布清单与整体边界独立审查。

基线：`baseline/8765-codex@404aeb1`，叠加已经独立审查通过的 R0—R3 工作树。

## 1. 目标与阶段边界

R4 只把领域能力接到 R1—R3 已形成的唯一 `scidiscovery.plugins` 编译目录，继续复用现有
Task、Artifact、Approval、Execution 与 Worker 文件生命周期。不得新增领域任务状态机、第二
catalog、角色名权限表或 UI 决定权威。

- R4-A：迁移 TCAD author/reviewer、任务私有 deck 工作区、文件策略、结果收口和调试工具；
- R4-B：迁移 TCAD 确定性变换、执行副作用与 capability 发现；
- R4-C：迁移 curve-score，处理 InGaAs 示例插件，删除旧 transform entry point；
- R4-D：把审批投影视图接到编译合同，核心只保留固定安全渲染器。

四段严格串行。每段实现和自动化检查完成后先标为“待独立审查”；独立审查打回则只返工该段，
通过后才允许进入下一段。

## 2. R4-A 已实现内容

### 2.1 单一 TCAD 插件声明

`tcad_artifact.plugin:PLUGIN` 由标准 `scidiscovery.plugins` 入口安装，当前登记四个公开操作：

- `tcad.deck.author.initial.v1`；
- `tcad.deck.author.revise.v1`；
- `tcad.deck.author.runtime-failure.v1`；
- `tcad.deck.review.v1`。

三个 author operation 共享一个 author 智能体组件，但分别冻结初次编写、审查请求修订和运行
失败修订的端口合同；reviewer 使用不同智能体组件，编译器据此强制独立性。prompt、项目/审查
Schema、编解码器、输出校验、上下文校验、预算、工具和审查边全部进入同一 operation 摘要。

旧 TCAD 角色正文只作为当前插件编译 prompt 的静态资源保留，不再发布
`scidiscovery.agent_role_packs` 入口，也不是调度权威。断裂的 TCAD
`scidiscovery.operation_specs` 入口已经删除。旧 transform adapter 必须保留到 R4-B 完成，
不能提前造成执行链回归。

### 2.2 通用工作区窄钩子

核心新增四种无状态组件协议：

- `workspace_materializer`：只接收本任务私有根、已物化输入路径和本任务重试快照路径；
- `workspace_file_policy`：只对一个已规范化任务相对路径返回大小、文本和可删除规则；
- `workspace_finalizer`：从任务私有文件树构造一个受输出上限约束的正式结果字节串；
- `workspace_snapshotter`：选择本任务可恢复的有界文件。

这些组件由 workspace 的传递依赖引用，启动编译会拒绝未知类型和同类重复钩子。运行时只从
当前任务冻结的 operation 摘要解析钩子；插件拿不到 ArtifactService、TaskService、数据库、
共享工作区根或仓库路径。默认 workspace 没有钩子，通用科学 operation 行为不变。

TCAD author workspace 引用全部四种钩子；review workspace 只引用只读 materializer。这样
reviewer 不会继承 author 文件写策略、自动结果构造、重试快照或调试能力。

### 2.3 TaskService 去领域化

TaskService 已删除按 `tcad_deck_author`/`tcad_deck_reviewer`、TCAD context profile 或
`tcad_artifact` 动态导入决定行为的分支，包括：

- deck 目录物化和项目模型导入；
- author 专用可写路径判断；
- author 结果自动构造和 JSON 特例；
- deck 专用 checkpoint 文件选择；
- runtime-failure profile 的领域模型解析。

现在 TaskService 只负责调用编译钩子、把钩子错误映射为既有 `TaskInputError`、执行受控写入、
校验、快照、封存和完成。领域模型解析、SProcess 声明式物化、能力字段冻结和 reviewer 只读树
均位于 TCAD 插件内。

### 2.4 调试工具是 operation 能力

`worker_tcad_debug_run` 已从核心静态 Worker 工具集合和按角色生成的 Codex 工具表移除。TCAD
插件把它登记为带任务上下文的 `worker_tool`，只有三个 author operation 引用；reviewer 和
全部通用 operation 不引用。Worker router 在调用已登记上下文工具前仍执行精确
operation/task/attempt capability 与工具名校验，再给 handler 传递会话令牌、worker 名和显式
配置的服务映射。handler 不接收 TaskService 或 Artifact 库。

当前 `TCADDebugService` 的装配仍由既有 runtime 完成，这是 R4-A 的有意过渡边界；R4-B 才把
领域服务配置和外部 adapter 工厂迁出通用 daemon。服务内部不再按 worker 角色字符串授权，
只接受本任务 operation 已冻结的
`tcad_artifact:tcad.development_debug` 与精确工具授权。

## 3. R4-A 验收证据

新增 `tests/operations/test_tcad_operation_plugin.py`，实际完成：

1. 编译 TCAD 单入口及四个 operation，核对独立 reviewer 和工作区钩子闭包；
2. 经统一 `operation_invoke` 创建 author Task；
3. 真实调用受控 JSON patch、新 deck 文件写入和已注册 `worker_tcad_debug_run`；
4. fake adapter 实际经历 submit、poll、collect，且调试结果声明不可作为科学证据；
5. workspace finalizer 构造并校验 `DeckProjectDraft`，完成 seal/finalize；
6. 用精确 author 输出创建独立 review operation，物化只读文件树，确认 reviewer 看不到 debug；
7. reviewer 写入、校验并完成精确 `DeckReviewReport`；
8. 源码结构检查确认 TaskService、Worker router 和 Codex 平台无 TCAD 角色/插件导入分支。

安装态测试同时确认：wheel 只通过标准插件入口增加四个 TCAD operation，author Operation Agent
可见 debug 工具，reviewer Operation Agent 不可见；核心单独安装仍不含 TCAD 模块。

首轮送审前的自动化结果为 TCAD 新增专项 3 项、catalog/插件/平台与安装态聚焦 21 项、
`tests/operations` 137 项及全仓 170 项通过，但这些检查没有覆盖真实调度和真实 Codex
子智能体链路，因此不能作为修复后结论。第二轮送审前重新执行静态编译、`git diff --check`
和全仓测试；第三轮打回修复后，`tests/operations` 为 145 项、全仓为 178 项，静态编译和
`git diff --check` 均通过。

R4-A 收口时核心代码实数为 `spec.py=348`、`catalog.py=462`、`invoke.py=430`；新增通用
`workspace.py=138`。相对首轮数字的 30 行增加用于通用输入 cohort/审批准入和最大尝试次数，
没有新增数据库迁移、运行状态、授权表或第二目录；该偏差交由第二轮独立审查判断是否仍属
最小闭包，而不再用近似数字宣称预算未变。

## 4. R4-A 独立审查门

审查者必须同时判断实现正确性与设计目标，不得只看测试为绿：

1. TCAD 插件能否仅靠一个标准入口增加 Agent operation；
2. OperationSpec 是否仍是行为闭包，而 workspace/tool 只是被引用的窄组件；
3. TaskService 是否还存在 TCAD 角色、Schema、profile 或动态 import 决策；
4. 插件是否只能接触任务私有根和显式输入，能否扫描仓库、Artifact 库或兄弟任务；
5. debug 是否只有 author operation 可见且服务端强制，reviewer 是否独立只读；
6. author 的结果、快照、重试和 reviewer 文件交接是否保持既有可追溯性；
7. 是否引入了不必要实体、第二注册表、重复生命周期或为 R4-B/D 提前设计；
8. 核心单独安装、完整安装、定向测试、全仓测试、编译和差异检查是否通过。

首轮独立审查报告为
`reviews/R4_A_INDEPENDENT_REVIEW.zh-CN.md`，结论是“打回修复，不允许进入 R4-B”。
阻塞项为：正式计划审查端口缺失、旧 TCAD role 调度仍生效、参数 cohort 合同缺失、
静态专业指导与 Worker 权限矛盾、1200 秒任务缺少续租工具、debug 拒绝快照绕过 operation
snapshotter，以及多目录文件封存顺序不确定。未取得复审书面“通过，允许进入 R4-B”结论前，
R4-B 状态保持未开始。

### 4.1 首轮七项阻塞的修复

1. 三个 author 与 reviewer 均声明正式 `experiment_review` 端口，通用 producer admission
   校验精确计划—审查关系；正负链路覆盖缺失、错误对象和未接受结论。
2. 当前调度说明只通过 `operation_invoke` 选择四个 TCAD operation；已迁移的旧
   `tcad_deck_author`/`tcad_deck_reviewer` 不再由 TCAD role 入口暴露。
3. `InputPortSpec` 增加领域无关的 cohort、审批类型和可接受选项声明；TCAD 参数端口以可选
   全组接入，并由插件纯 guard 校验完整组、同一审批、父链、coverage、audit 与 uncertainty。
4. 必需的 Sentaurus 编写、审查和 SDevice 最小合同作为插件静态资源进入 operation 摘要；
   Worker 不再加载宿主隐式技能。真实 Codex 验收证明原生只读能力和注册调试工具可用。
5. author operation 注册 `worker_heartbeat`，`LimitsSpec.max_attempts=2`；可控时钟测试证明
   租约可在绝对预算内续期而不能延长绝对期限。
6. debug 校验拒绝统一调用 operation-aware snapshot；新 attempt 能恢复尚未成为有效项目的
   原始 deck、声明和 handoff，拒绝信息保持有界可操作。
7. TCAD 文件收集同时排序目录和最终相对路径；不同创建顺序产生相同正式字节与摘要。

### 4.2 真实智能体返工与最终证据

持久证据位于 `deliverables/r4-a-live-agent/`。失败轮次没有删除或覆盖：

- 第 5 轮暴露 reviewer 搜索仓库范例；增加任务内审查结构模板、受控补丁工具和输出错误提示；
- 第 6 轮暴露 author 搜索历史 SDevice 工程；把最小 SDevice 合同编译进插件，并把任务根
  提升为所有 operation 原生读取边界；
- 第 7 轮权限全部通过，但独立 reviewer 发现 `Grid="device.tdr"` 未由文件或输入槽闭合；
  修正 SDevice 合同与验收输入槽，未降低审查门；
- 第 8 轮科学审查通过，证据检查器误拒任务根内安全子目录导航；检查器改为解析后不得逃出
  任务根，并增加越界和原生写入反例；
- 第 9 轮权限全部通过，但 author 使用初始化模式，未产生计划要求的源码预检凭据；验收指令
  和报告增加精确 `preflight` 模式检查；
- 第 10 轮 `qualification-report.json` 的 22 项检查全部为真，结论为通过。它实际启动两次
  Codex 父会话并分别派生精确 author/reviewer；父会话无 Worker 代做，两个子智能体只调用各自
  编译的 Worker 服务，只在任务根内原生读取，所有写入经过 Worker 文件生命周期。author
  完成项目、七次注册调试工具调用及精确预检模式，reviewer 无调试权且独立返回通过。

### 4.3 第二轮打回及修复

第二轮独立审查报告为
`reviews/R4_A_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`，结论仍为“打回，不允许进入 R4-B”。
它确认首轮七项阻塞中的六项已经闭合，但发现两个证据边界问题：

1. TCAD 参数 cohort 新增了无正式 producer 的 `parameter_uncertainty`，导致真实参数链不可达，
   且调度投影没有公开 cohort/审批组；
2. 第 10 轮无副作用夹具无条件返回完整成功，却被 reviewer 提升为 Sentaurus 语法通过和执行
   就绪，真实证据只足以证明智能体派发、工具注册、任务私有读取和文件生命周期。

返工没有删除参数不确定性门，也没有增加专用状态机：通用插件新增唯一确定性 support
Operation `science.parameter.uncertainty.v1`，从精确 requirements、parameters 和 coverage
正式产生固定、离散有界、阻塞无界或延后不用四类投影；父链 guard、严格 Schema、TCAD
cohort 和调度投影均来自同一 catalog。测试不再私有 `_register` 第七对象，而是实际调用正式
coverage 和 uncertainty 两个 Operation，再证明整组审批后的 author 可达。普通安装目录因此
从 R3 冻结的 `public=15/support=13/internal=0` 演化为
`public=15/support=14/internal=0`；这是一个可调用的正式生产者，不是第二注册表。

第 11 轮真实验收位于
`deliverables/r4-a-live-agent/run-20260829-11/qualification-report.json`。它的 23 项检查全部为真，
但资格范围明确分开：架构集成为 `pass`，Sentaurus 语法、输入槽解析和执行就绪均为
`not_claimed`，科学主张不可采纳。author 实际调用注册调试工具并完成项目；控制证明明确
`diagnostic_layer=runtime`、`qualified=false`；独立 reviewer 正确返回 `blocked`、
`syntax_fidelity=unknown`、`execution_ready=false`。生产 `TCADDevelopmentDebugBridge` 另有
缺失 `device_grid` 和错误媒体类型两个失败关闭反例。第 10 轮保留为发现过度主张的失败证据，
不再作为放行依据。
第 11 轮资格报告摘要为
`70bb134c56381d4a433b6adc9aa24d2db5ae3a33f8c98ac5df22ad1cd7111de1`。

### 4.4 第三轮打回、通信收口与第 13 轮证据

第三轮独立审查报告为
`reviews/R4_A_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`。它确认第二轮两个阻塞及首轮七项阻塞
均已闭合，但发现第 11 轮子智能体完成消息和父会话最终回复形成了受控 Artifact 之外的第二条
结果通路：聊天中暴露了任务路径、内部会话身份、科学摘要或审查结论。因此第三轮仍然打回，
不允许进入 R4-B。

返工没有增加消息总线、状态或包装实体。编译后的每个 Operation Agent 统一追加固定完成规则：
成功封存后聊天只能返回“已完成受控提交。”；父调度会话只允许返回“子智能体已返回；受控状态
待控制层查询。”，并明确不能复制路径、身份、科学摘要或结论。真实结果只能由 Root 的受控状态
与输出查询取得。自动化验收同时检查作者和审查者的子完成信号与父最终信号，任何额外文本均
失败关闭。

第 12 轮已经实际满足四条固定信号，但验收器把 Codex 在 JSONL 前写入的两条固定运行时提示
误判为聊天泄漏，因此报告保留为失败证据。检查器随后只允许这两类已知前导行，其他非 JSON
输出仍失败关闭。第 13 轮持久证据位于
`deliverables/r4-a-live-agent/run-20260829-13/qualification-report.json`，27 项检查全部为真，
架构集成为 `pass`；Sentaurus 语法、输入槽解析和执行就绪仍为 `not_claimed`，科学主张仍不可
采纳。审查者在无真实求解器资格时返回 `revise`、`syntax_fidelity=unknown`、
`execution_ready=false`。报告摘要为
`241b3759f0fb51297f3ab790958f67f838c5036cfbf511c8540ee7c05c992994`。

第四轮独立审查必须复核第三轮唯一阻塞的修复、第 12/13 轮完整证据、145 项 operation 测试、
178 项全仓测试、静态编译和差异检查。未经书面“通过，允许进入 R4-B”，本阶段仍只是待审。

第四轮独立审查报告为
`reviews/R4_A_INDEPENDENT_REVIEW_ROUND4.zh-CN.md`，结论为“通过，允许进入 R4-B”。独立
复跑聚焦 37 项、operation 145 项、全仓 178 项，静态编译和差异检查全部通过；第 12/13 轮
全部证据哈希独立核验一致。R4-A 至此收口，报告中的复杂度收敛、生成器措辞漂移、前导提示
白名单收紧、可信插件边界和生产式父会话查询缺口作为后续非阻塞债务保留，不在 R4-A 继续
增加实体。

## 5. R4-B：TCAD 变换、Effect 与运行时配置

### 5.1 六个确定性变换进入同一插件目录

R4-B 没有重写 TCAD 算法，而是在 `tcad_artifact` 的同一个 `PluginDefinition` 中登记六个
`support transform Operation`，薄适配组件直接调用既有 `TCADProjectTransformAdapter`。它们
只在科学行动已经选定后被精确调用，不进入默认规划候选：

- `tcad.deck-project-compare.v1`；
- `tcad.deck-review-validate.v1`；
- `tcad.reviewed-deck-package.v2`；
- `tcad.runtime-attestation.v1`；
- `tcad.realization-snapshot-materialize.v1`；
- `tcad.control-equivalence.v1`。

原适配器的 package 与 runtime 父链约束被显式迁为插件 guard；多输出 runtime manifest 由
manifest 中的稳定名称与同序原始输出绑定，control-equivalence 的报告、快照集合和审计仍分别
封存。旧 `scidiscovery.transform_adapters` 中的 TCAD 入口已删除，因此这些行为不存在第二条
发现或调用路径。curve-score 旧入口保留到 R4-C。

### 5.2 外部执行仍复用既有生命周期

公开 `tcad.study.execute` 是一个 `external` Effect。它只消费精确
`tcad.reviewed-deck-package.v2`，生成既有 `ExecutionRequest`，并强制创建独立本地审批；Effect
本身不提交外部任务。审批接受后仍由原 `ExecutionService`/`ExecutionBridge` 负责 prepare、
submit、status、collect 和结果封存，没有新执行状态、新表或领域 outbox。

能力发现不再接受裸执行器名作为调度合同。`execution_capabilities` 和
`execution_capability_bind` 必须接收已编译 Effect 的 `operation_id`，由
`tcad.study.execute` 的 effect component 解析出内部 adapter key。通用 `ExecutionBridge` 只
校验能力文档有界、唯一和结构完整；`tcad.solver-capability.v2` 的领域校验仍由两个 TCAD
adapter 的严格模型完成。

### 5.3 单一配置入口与通用 daemon

`PluginDefinition` 增加可选 `runtime_factory`，它和 `configuration_schema`、每个相关 Operation
一起进入同一编译闭包与摘要；`CompiledCatalog` 只额外投影这些启动期工厂，不建立第二注册表。
两个 daemon 均只接受可重复的：

`--plugin-config tcad_artifact=/绝对路径/tcad-plugin.json`

通用加载器拒绝重复插件编号、未知或无运行时工厂的插件、符号链接、非普通文件和超过 1 MiB
的配置。TCAD 插件配置内部决定使用 socket 还是 command adapter。控制进程取得
`execution_adapters={"tcad_artifact:tcad": ...}`；Worker 进程从同一配置取得
`tool_services={"tcad_artifact:tcad.development_debug": ...}` 和通用 reconciler。限定前缀由
通用加载器依据运行时工厂所属插件生成，Effect 和 Worker 工具只能解析其编译组件所有者的
服务，其他插件即使声明同名局部键也不能冒充。核心 runtime、控制 daemon、
Worker daemon 已删除 `tcad_debug` 字段、`--tcad-socket`、`--tcad-command-config`、TCAD 动态
import 和服务名特判。安装脚本生成只读 `tcad-plugin.json`，向两进程传递相同插件配置。

`runtime_factory` 是已安装代码中的可信控制运行时扩展，不是任务内 Agent 能力，也不属于
普通 workspace hook。默认工厂拿不到 `TaskService`；只有工厂在编译组件中显式声明
`requires_worker_task_service` 后，Worker daemon 才在启动期把该服务交给它。TCAD 的开发调试
服务需要复用既有任务令牌、租约、快照和恢复表，因此是当前唯一声明者。这个服务留在控制侧，
任务内 Worker 只得到精确注册的 `worker_tcad_debug_run` 输入/输出，既看不到启动上下文，也拿
不到 `TaskService` 对象。普通 Agent 组件、workspace hook、变换和 Effect callable 均不获得这项
权限。安装一个插件意味着信任其本地 Python 代码；插件配置只装配已安装工厂，不能加载任意
新代码。后续若把 TCAD 调试账本从 TaskService 拆成通用窄门面，应作为独立简化，不在 R4-B
制造一套重复的任务生命周期。

### 5.4 自动化证据与当前复杂度

新增/扩展测试实际证明：六个变换编译并执行原算法、package 父链失败关闭、运行时配置同时
装配控制与 Worker、危险配置拒绝、能力经 Effect 发现与封存、`tcad.study.execute` 经统一
`operation_invoke` 创建 ExecutionRequest；真实本地 UI 授权后，既有执行服务完成收集，原始
`opaque/application-json` 的 `tcad_manifest` 可由编译后的 runtime-attestation Operation 严格
解析并封存。正式执行器产生的“启动前失败”清单保留 `started_at=null`，仍能得到失败证明。
测试还覆盖旧 TCAD adapter 显式注入旁路、跨插件同名运行时服务冒充、载荷模式版本传播和安装
脚本真实 dry-run。核心 daemon 不含 TCAD 参数或 import，完整 wheel 只剩一个 curve-score 旧
transform adapter。当前 full catalog 为
`public=20/support=20/internal=0`，其中 TCAD 11 项。

本轮自动化结果：`tests/operations` 156 项、全仓 190 项、安装脚本语法、全插件安装 dry-run、
静态编译和 `git diff --check` 全部通过。通用核心当前为 `spec.py=350`、`catalog.py=486`、
`invoke.py=450`，另有启动期 `runtime_plugins.py=162`；领域插件声明、薄变换适配和运行时工厂
共 1249 行。Operation ABI 已因输出端口显式载荷模式版本升为 5。该增量没有状态或
持久化实体，但独立审查必须判断它是否仍是完成插件配置/执行闭包所需的最小实现，尤其审查
是否能通过删除重复声明继续缩减。未经书面“通过，允许进入 R4-C”，R4-C 不得开始。

### 5.5 独立审查结论

独立审查报告 `reviews/R4_B_INDEPENDENT_REVIEW.zh-CN.md` 已明确给出“通过，允许进入 R4-C”。
审查者独立复跑聚焦 17 项、全仓 190 项，并核对了六个变换的真实调用、外部执行审批下限、
运行时服务限定、执行输出父链、三种目录视图和可信插件边界。R4-B 至此收口；报告中记录的
旧 editable 元数据、可信插件非强沙箱、包版本描述和小型启动协议校验属于后续发布或加固债务，
不得在 R4-C 扩张成新的控制层。

## 6. R4-C：Curve Score 与项目插件

R4-C 只迁移 curve-score 保留 profile、处理 InGaAs 示例插件并删除最后的
`scidiscovery.transform_adapters` 与断裂 `operation_specs` 入口。它不得修改 R4-B workspace、
运行时工厂或执行生命周期，也不得提前改审批 UI。

### 6.1 R4-C-A：先冻结迁移边界

本段先审设计边界，不写生产实现。冻结决定如下：

1. 只保留六个有生产消费者的 `support` Operation：多 PLX bundle、通用 curve score、历史
   SProcess log score、论文图证据 v2、reference coverage 和 objective coverage。单项 log/PLX
   normalizer 与 bare consistency 只是这六项复用的插件内部函数，不登记目录；论文图 v1 的既有
   Artifact 仍可只读，但删除新建 v1 产物的可调用入口；
2. 不再让调用方用动态 `solver_output__*`、`curve_table__*`、`reference_curve__*` 名称承担
   科学身份。Operation 只暴露有界集合端口。论文图表由 figure manifest 的 panel/series、data
   item、摘要及 CSV 自描述列绑定；reference bundle 的 series 身份来自内容。多 PLX 是例外：
   原始 PLX 不自描述 series，因此必须额外绑定同次执行的精确 `runtime_manifest`。计划所需的每个
   solver series 必须对应 manifest 中同名的唯一 solver-native 记录，集合顺序必须等于这些记录
   在 manifest 中的顺序，并逐项核对摘要、大小和媒体类型；缺失、额外、重名、错序均拒绝；
3. 多 PLX 的父链由插件 guard 关闭：runtime manifest 与全部 PLX 必须具有完全相同的 execution
   父链；通过的 runtime attestation 必须直接包含该 manifest 和每个 PLX；experiment plan 只声明
   科学 series，runtime manifest 只证明原始字节的执行输出身份。这里不增加通用集合身份字段、
   新 Schema 注册表或文件名推断；
4. InGaAs Fig.4 的基线恢复计算不等同于通用 curve-score：它读取冻结 scorer project 中的专用
   合同并输出项目专用门结果。当前活动研究状态仍保留该基线溯源矛盾，因此不删除算法；把它保留
   为默认不安装的单 Operation 项目插件，迁入标准 `scidiscovery.plugins` 入口。核心、TCAD 和
   curve-score 插件均不得出现图号或 InGaAs 判断；
5. 不新增 schema registry、profile registry、动态端口类型或领域路由器。每个 Operation 的端口、
   输出验证、父链 guard 和薄算法包装都直接属于该插件的唯一 `PluginDefinition`；旧 adapter 类
   只作为插件内部无状态函数门面复用，不再发布为 entry point；
6. 本段完成门是独立审查者确认保留范围、集合身份映射、父链要求、三视图分类和 InGaAs
   保留理由均最小且可实现。未通过不得开始代码迁移。

### 6.2 R4-C-B：迁移 curve-score 单入口

实施内容：

- 新增 `curve_score/plugin.py` 与薄 Operation 包装，六个保留 profile 分别声明精确端口、限制、输出
  Schema、validator、guard 和 `catalog_scope="support"`；
- 对多 PLX、论文图表和 reference bundle 只使用集合端口。多 PLX 同时消费精确 runtime manifest，
  以 manifest 的 solver-native 逻辑名、摘要、大小、媒体类型和声明顺序绑定计划 series；图表严格
  依照 manifest 身份与摘要绑定；reference bundle 的 series 身份来自 bundle 内容，并按内容摘要
  排序后形成稳定审计名称；
- 将 `curve_score` 包入口改为唯一 `scidiscovery.plugins`，删除其
  `scidiscovery.transform_adapters` 和已断裂的 `scidiscovery.operation_specs` 声明；
- 安装脚本和 clean-wheel 测试改为从 compiled catalog 验证精确六个 Operation，并断言三个内部
  函数没有目录项、论文图 v1 精确调用为 unknown、旧 adapter 与断裂入口均为零；不能在 installer
  重写六套 profile 选择逻辑；
- 六个 Operation 都至少执行一个成功路径。多 PLX 必须用 Root `operation_invoke` 从真实
  `execution_outputs` 绑定的 Artifact 进入，并覆盖交换两个不同摘要 PLX、同 Schema/大小的外来
  PLX、另一执行 manifest、attestation 未包含输出四类失败；论文图桥覆盖错序/摘要/父链，评分与
  coverage 覆盖缺项、额外项和输出验证失败；
- 通过专项、全仓、clean full/core-only 安装、dry-run、静态编译和差异检查后，交独立审查。
  审查未明确通过，不得处理 InGaAs 或删除全局旧 loader。

实现记录（2026-08-29）：

- `curve_score` 已改成一个标准插件入口，目录只发布上述六个 `support` Operation；旧 transform
  adapter 继续作为插件内部无状态算法门面复用，但不再作为 entry point 发布；
- 多 PLX Operation 消费同次执行的 `runtime_manifest`、`runtime_attestation`、实验计划和一个有界
  `solver_outputs` 集合。实现按清单记录顺序逐项核对逻辑名、媒体类型、字节数和摘要，guard 同时
  要求清单与全部 PLX 的执行父链完全相同，attestation 直接包含清单和每个 PLX；
- TCAD 运行证明 Operation 的既有原始输出端口补充允许
  `application/x-synopsys-plx`，未增加新的生命周期、注册表或领域路由；
- 论文图 Operation 依 manifest 的 panel/series 顺序和 validation report 的 CSV 摘要绑定集合；
  reference bundle 按内容摘要稳定排序，科学 series 身份只从严格 `CurveBundle` 内容取得；
- 新增专项测试覆盖六项成功路径，并让真实 `ExecutionBridge → execution_outputs → Root
  operation_invoke` 进入 PLX Operation；交换两个 PLX、同 Schema/大小的另一执行 PLX、另一执行
  manifest、未直接包含全部输出的 attestation 四类情况均失败关闭；论文图的错误父链/摘要、端口
  缺项/额外项和输出 validator 失败也有反例；
- 当前聚焦回归为 24 项通过；第一次全仓回归为 194 项通过、1 项安装态期望列表因新增六项而失败，
  修订安装态精确清单后对应 clean full/core 探针 3 项通过。完整复跑和发布清单重建留到独立审查
  前后的最终收口，不把历史失败隐藏为一次全绿记录。

### 6.3 R4-C-C：迁移项目插件并删除旧入口

在 R4-C-B 独立通过后：

- 把 `ingaas.fig4-baseline-recovery.v2` 迁成可选 `ingaas_fig4` 单入口插件中的一个 `support`
  Operation；沿用冻结算法与五个精确输入，不进入默认 full 安装；
- 保留通用重装脚本只作为显式选择该项目插件的便利入口，并把安装探针改为编译目录断言；
- 全仓删除发布配置中的 `scidiscovery.transform_adapters` 与 `scidiscovery.operation_specs`；核心
  loader/旧 Root 表面留到 R5 删除，但在任何发布组合中只能得到空集合，不能再成为运行权威；
- 分别验证 core-only、默认 full、显式 InGaAs 三种 clean 安装：核心启动不得导入
  `tcad_artifact`、`curve_score`、`ingaas_fig4`；默认 full 只增加 TCAD/curve Operation；显式项目
  安装只再增加一个 InGaAs Operation，且不得改变 core、通用科学、TCAD 或 curve-score 的任何
  已编译 Operation 摘要；
- 全量回归、发布清单和独立审查全部通过后，R4-C 才能收口并进入 R4-D。

实现记录（2026-08-29）：

- `ingaas_fig4` 发布配置已从旧 transform adapter 改成唯一 `scidiscovery.plugins` 入口；插件只声明
  `ingaas.fig4-baseline-recovery.v2` 一个 `support` Operation，精确消费冻结 scorer project、曲线
  CSV、目标指标和两份 PLX，并直接复用原无状态评分函数；
- 项目输出由同插件的完整严格模型核对全部顶层与嵌套字段、五项输入摘要、三组 crossing、原始
  复现、两组曲线指标、六项 gate、残差区间、有限数值及 gate 自洽性；Operation 的解释边界明确
  禁止把确定性门结果升级成机制归因或物理模型接受结论；
- 当前发布树全部 `pyproject.toml` 已没有 `scidiscovery.transform_adapters` 或
  `scidiscovery.operation_specs` 声明；旧 loader/Root 表面按计划留待 R5 删除，但 core、默认 full、
  显式项目三种 clean wheel 中旧入口均为空；
- 安装态证明：core 不安装三个领域包；默认 full 只安装 TCAD/curve 且没有 InGaAs Operation；显式
  InGaAs 安装只新增该一个 Operation，并保持既有 46 个 Operation 摘要完全不变；
- 安装态测试夹具改为先复制到测试临时目录再构建 wheel，避免 setuptools 在仓库夹具里产生
  `build/egg-info` 后递归打包；修订后复跑不再污染源码树；
- 专项清洁安装与目录测试 14 项通过，全仓 `204 passed in 57.26s`，显式 InGaAs 安装 dry-run、
  shell 语法、静态编译和差异检查通过。发布清单在独立审查报告写入后统一重建。

### 6.4 状态

- R4-C-A：第二轮独立复审通过；
- R4-C-B：第二轮独立复审通过；
- R4-C-C：第二轮独立复审通过，R4-C 已正式收口；

R4-C-A 首轮报告为 `reviews/R4_C_A_BOUNDARY_INDEPENDENT_REVIEW.zh-CN.md`，因多 PLX 身份不能
只靠集合位置、十项迁移表面过多而打回。返工后第二轮报告
`reviews/R4_C_A_BOUNDARY_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 明确给出“通过，允许进入
R4-C-B”；后续实现必须保留其 Root `operation_invoke` 四类身份负例完成门。

R4-C-B 首轮报告 `reviews/R4_C_B_CURVE_PLUGIN_INDEPENDENT_REVIEW.zh-CN.md` 确认六项实现、真实
执行身份链、单入口和全仓 195 项通过，但因模型可见提示仍暴露内部动态别名，以及集合顺序/输出
validator 反例不完整而打回。返工已完成：scheduler 源、生成 `AGENTS.md` 和双语插件说明只公开
编译集合端口；新增目录端口一致性、两图表错序、两引用库置换不变/重复摘要拒绝，以及 score、
reference coverage、objective coverage 主输出畸形字节的编译 validator 反例。第二轮审查通过前
仍不得进入 R4-C-C。

第二轮报告 `reviews/R4_C_B_CURVE_PLUGIN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 已逐项确认上述
返工有效，并明确给出“通过，允许进入 R4-C-C”。

R4-C-C 首轮报告 `reviews/R4_C_C_PROJECT_PLUGIN_INDEPENDENT_REVIEW.zh-CN.md` 确认单入口、可选
安装、五输入算法边界和既有摘要稳定性正确，但因输出 validator 不完整、核心残留 Fig.4 专用
策略、源码构建缓存重新暴露旧入口、根发布清单过期而打回。返工已将项目结果改成完整严格模型，
增加畸形嵌套对象、缺失 crossing、非有限 metric 和非法残差区间反例；删除无消费者的核心 Fig.4
上下文策略，并增加生产源码隔离扫描；源码范围的 build、egg-info 与字节码缓存已移至可恢复的
临时隔离目录，活动源码探针中的旧 transform/operation-spec 入口均为零。聚焦复跑 30 项通过；
源码态测试改用测试内显式模拟的默认完整插件安装元数据，不再依赖源码 `egg-info`，实际三种清洁
安装仍由隔离 wheel 验证。全仓 `207 passed in 57.98s`，显式 InGaAs 部署预演、shell 语法与差异
检查通过，测试后新增的一处字节码缓存也已隔离。根发布清单将在第二轮审查报告写入后最后重建；
未书面通过仍不得进入 R4-D。

第二轮报告 `reviews/R4_C_C_PROJECT_PLUGIN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 仍然打回：严格结构
模型尚允许相反/空白解释边界和按定义不可能的负 RMS，且 SSH runner 部署测试中的显式
`py_compile` 会重新污染源码。再次返工把解释边界固定为评分函数与结果模型共享的精确常量；raw、
recovery、curve metric 与 residual region 的 RMS/最大绝对残差均设为非负，并增加 RMS 不得超过
同组最大残差的自洽门。测试新增相反/空白解释、四类负 RMS、raw pass 翻转、recovery pass 翻转
和 checks 合取不一致反例。部署脚本改在一次性目录生成显式 pyc，保留语法检查但不写源码树。
同一聚焦集合 `44 passed in 34.36s`，全仓 `207 passed in 58.68s`；测试后源码构建缓存、旧两组
入口和旧 adapter 均为零。当前等待同一独立审查者继续复核，仍未重建最终发布清单。

同一审查者随后独立复跑 15 类输出畸变、聚焦 44 项、全仓 207 项、显式 InGaAs 部署预演、
clean wheel 与源码零缓存/零旧入口检查，确认上述两项返工关闭。最终根发布清单含 274 个唯一条目，
与独立封存发布树的文件集合和逐项摘要完全一致；正式报告摘要也已进入清单。第二轮报告
`reviews/R4_C_C_PROJECT_PLUGIN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 明确给出“通过，允许 R4-C
收口并进入 R4-D”。R4-C 至此完成。

## 7. R4-D：编译审批合同与固定安全视图

### 7.1 R4-D-A 设计冻结

R4-D 不在现有 Schema 分支上继续增加专用页面，也不建立独立审批注册表。审批行为仍以
`OperationSpec` 为唯一原子，新增的只是该闭包已有 `agent`、`transform`、`effect` 之外的一种
执行方式 `approval`：

1. `approval` Operation 使用既有输入端口、guard、limits、`ReviewSpec.approval` 和 projector；
   它没有科学输出端口，不创建占位 Artifact，不增加任务或执行状态。`operation_invoke` 通过既有
   ApprovalService 创建一个精确审批请求并返回既有审批状态/本地 URL；
2. 它的 executor component 与 approval projector 必须是同一个已编译 `projector` 组件；编译器
   拒绝无审批合同、有输出端口、带 workspace/tool/prompt、组件不一致或内部视图的 approval
   Operation。这样不会出现“审批操作”和“审批模板”两套注册权威；
3. approval Operation 属于 `public`：它是当前矛盾满足科学/风险门后可以选择的真实下一行动。
   `support` 仍只容纳被选行动调用的机械变换，`internal` 仍不进入普通调度/UI。三种视图继续只是
   同一 compiled catalog 的投影，不参与任务准入，也不新增权限表；
4. 现有 TCAD external Effect 保持两步生命周期：先产生 ExecutionRequest，再创建独立执行审批。
   它继续使用自身已编译 approval contract，不转换成 approval Operation，也不合并执行与人类决定。

### 7.2 固定 `ReviewDocument`，插件不得提供 HTML

核心定义一个有界、不可执行的 `ReviewDocument`：标题、说明、分节，以及每项的中文标签、精确
subject 序号、JSON Pointer 和固定展示类型。项目插件只能返回这个数据结构，不能返回 HTML、CSS、
脚本、模板路径或任意 renderer callable。核心在请求创建时验证每个 subject、媒体类型和 pointer，
把文档随 ApprovalRequest 不可变保存；UI 打开历史请求时不再运行插件代码。

projector 只接收窄的只读 subject 快照：端口/集合位置、Schema、媒体类型、大小、父引用、冻结标签、
producer handoff verdict 和原始字节。它是受信任、启动时编译并在控制进程内运行的插件组件；窄
快照只表示正式 API 与 authority 最小化，不是进程沙箱。核心不向它传入 ArtifactService、
TaskService、ApprovalService、数据库连接或可写路径，但本阶段不声称能阻止受信插件代码自行使用
Python 文件/网络模块。若未来允许不受信插件，必须另立进程隔离阶段，不能把该复杂度塞进 R4-D。
executor kind `approval` 仍按已有 `projector` component kind 解析，且必须与
`ReviewSpec.approval.projector` 是同一精确引用，不新增重复组件类型。

`ApprovalRequest` 在既有 Artifact 内新增可选的编译合同身份：operation id、version、digest 和
approval contract digest；不新增数据库表。字段可选只为读取历史请求。所有新 compiled 审批必须
写入完整身份，重放时纳入不可变指纹；插件卸载或升级不会改变已保存文档和既有决定，但缺少当前
compiled contract 时不得新建或重建审批。

该身份不是仅供审计的标签，而是后续准入的一部分。`InputPortSpec` 的现有审批 cohort 合同增加
有界 `accepted_approval_operations`，只能列同一 compiled catalog 中 `public + approval` 的
Operation。编译器把每个 provider 的 id、version、operation digest 和 approval contract digest
冻结进消费 Operation 摘要；同一 cohort 的 provider 集合必须相同，provider 不得再依赖审批
cohort，以避免资格环。参数消费端可精确接受 pass/exception 两个 provider，不在 Root 建 allowlist。

ApprovalService 的 provider-aware 查询同时验证 kind、接受选项、同一完整决定覆盖全部必需 refs，
以及请求中保存的 provider 身份与消费 Operation 冻结身份完全相等。历史缺身份、合同漂移或其他
插件同名 kind/option 的决定只可审计，不能为新调用提供资格。Operation cohort、readiness 和剩余
legacy bridge 必须调用这一处查询；删除 foundation 单对象的旧资格语义。审批请求可以包含
extraction primary、frozen sources 等额外 subject，但下游只检查其消费 cohort 是同一个已认可
provider 决定的子集，不重演领域 Schema 分支。

跨插件 provider 引用必须服从既有 `PluginDependency`：消费插件只能接受自身 provider，或显式依赖
插件中的 provider，并校验依赖版本。TCAD 因接受 general-science 的 pass/exception 参数审批，必须
显式依赖 `general_science`。缺依赖、版本不符、provider 非 `public + approval`、provider 自身含审批
cohort 均在启动编译时失败，不能按全局 operation id 偶然解析。

provider 合同也进入 readiness，而不是只在 preflight 生效。scheduler projection 只公开端口声明的
provider operation ids，不公开摘要；Root 在逐个枚举候选 Operation 时使用该候选 compiled catalog
中冻结的 provider identities 和当前精确 cohort 调用同一 provider-aware 查询。对象级库存对具有
多 provider 语义的 scientific foundation 只报告中性的 `available`：对象结构存在且没有已知失败，
不报告任何 provider 决定，更不能升级成对所有候选都有效的全局 `qualified`。这样 provider A 的
决定不会让只接受 provider B 的候选显示 ready，readiness 与权威 preflight 使用同一事实。

源码态 `task_schedule` 只保留当前两个明确的资格前桥接：device-parameter `evidence_extractor` 和
`device_parameter_evidence_auditor` 的固定 context/output profile；它们只产生待审对象，不消费或
授予已批准科学资格。其余需要消费已批准对象的角色必须先迁成带 `InputPortSpec` 的 Operation，
不得从 Root 常量、角色 prose 或“任意已安装 provider”取得资格。这里是在既有两个 legacy bridge
上收紧入口，不增加桥接表或 allowlist。

projector 的窄上下文另含一个由核心从既有不可变 Task/output 映射即时形成的
`producer_output_family`：唯一 primary ref、每个输出端口/collection/item 的精确 ref 和冻结顺序，
以及同一任务冻结的 evidence-source refs/任务内别名。该快照与 subject 内容一起绑定，只读且不
持久化新 Artifact；它不给插件 TaskService/数据库句柄，也不是输出族注册表。找不到 compiled
producer、primary 不是其精确输出、输出映射不完整或内容摘要不一致时，资格审批失败关闭。

family resolver 只允许两个有类型的分支，不能退化成“任意 transform 输出都可申请资格”：

1. **智能体提取分支**：primary 必须是同一个已完成 Task 的精确 primary；族成员只能来自该 Task
   的已冻结 output/collection 映射和 task-scoped evidence-source 映射，规则保持如上；
2. **typed intake revision 分支**：primary 必须是当前 compiled
   `science.revision.apply.intake.v1` 的 `revised_object`。核心从其既有 invocation request
   fingerprint、Artifact producer 标签/parents 和 compiled output ports 即时恢复同一次调用中恰好
   一份 `revision_diff`，并验证精确 base、`science.intake.revise.v1` 产生的 patch、diff 以及
   `science.evidence.receipt.intake.v1` 产生的 `unchanged_evidence_receipt` 的父链闭合。receipt 必须
   覆盖该 exact base、revised object、diff 与 base family 的完整 evidence refs；只有它证明 evidence
   声明不变时，才允许复用 base 的 sibling/frozen-source family，同时必须绑定针对 revised primary
   的新独立 evidence audit。若 evidence 声明改变，则本分支拒绝，必须重新运行完整提取和完整审计。

base family 仍按第一分支解析；若 base 本身也是 typed intake revision，可沿同一受控关系递归，但
深度固定不超过 8，出现环、缺项、多个同端口输出、请求指纹不一致或任一非上述 producer 都失败
关闭。foundation 必须是 revised ScientificIntake 经精确 `science.intake.split.v1` 调用产生的
foundation，并与 revised primary 内声明一致。该 resolver 只读取现有 Task、operation invocation
binding、Artifact labels/parents 和 compiled catalog，不持久化族、不建立第二输出注册表，也不为
hypothesis/experiment 或其他普通 transform 开放人工 evidence qualification。

### 7.3 三类最小 projector 与绕过关闭

通用科学插件只新增三个公开 approval Operation，不增加领域流程：

- `science.evidence.qualify.v1`：消费恰好一个最终科学基础、恰好一个 `extraction_primary`、恰好一个
  独立 evidence audit，以及分别有界的 producer sibling outputs、frozen sources 和适用 deterministic
  validation 集合；初次智能体提取时不得绑定修订对象，typed intake revision 时还必须各绑定恰好一份
  `revision_diff` 和 `unchanged_evidence_receipt`。primary 不得混在通配集合中。projector 以
  `producer_output_family` 证明 subjects
  精确覆盖该 primary 的全部科学输出兄弟项和冻结来源，再要求 foundation 声明的来源、适用
  validation 与 audit 实际输入全部闭合且 audit producer verdict 为 `pass`，最后只投影主张边界、
  证据、未解决项与审查结论；
- `science.parameters.qualify.pass.v1`：消费科学基础、requirements、selected parameters、source
  catalog、deterministic coverage、independent audit、恰好一个 `extraction_primary` 和有界 frozen
  sources，只接受 coverage `pass`，选项固定为批准或要求修订；
- `science.parameters.qualify.exception.v1`：输入相同，只接受 coverage `review_required`，接受项
  固定为必须填写理由的 `approve_with_exception`，另有要求修订。把两个价值决定拆成两个精确
  Operation，避免动态改写已编译选项或增加 option-selector 注册面。

两个参数 Operation 的固定 subject 顺序均为 foundation、extraction primary、requirements、
parameters、source catalog、coverage、audit、frozen sources。参数 projector 迁出 Root 现有的
目标一致、coverage 精确父链/重算、四项 audit check 和 passing handoff 校验，但不照搬错误的来源
集合全等：每个 parameter observation 的 source key 必须存在于 catalog；未被 observation 引用的
catalog 条目按关系明确为 metadata-only，不得贡献参数值、coverage 或独立来源计数；audit 必须按
其合同覆盖完整 catalog，并绑定实际审查过的 extraction primary、三项参数附件、coverage 和全部
frozen sources。audit 不得为凑审批束而伪称直接审查未消费对象；foundation 与 extraction/来源的
闭合由冻结 lineage 单独验证。删除 Root 的参数 Schema 特判。证据 projector 承担最终 evidence
cohort 的同类精确校验。新的 `kind="scientific_foundation"` 审批不能再通过通用
`approval_request_create` 自定义 question/options/presentation 绕过 compiled contract；实例创建、
会话绑定和历史请求仍走控制面专用审批，不伪装成科学 Operation。

TCAD `execution_projector` 改为返回同一个 `ReviewDocument`，展示冻结执行请求、已审查工程、能力、
参数绑定和副作用边界。新 ExecutionRequest 若没有当前已编译 operation id/version/digest 或
approval contract，`execution_approval_request_create` 必须失败；旧请求只能只读显示，不能借旧
fallback 新授权。`execution_start` 不信任“创建时曾校验”：它从 ExecutionRequest 冻结标签解析当前
Effect，再把当前完整 compiled identity 作为显式预条件交给 ExecutionBridge/ExecutionService；
authorize 再次比较决定对应 ApprovalRequest 的 provider identity、精确两个 subjects 与请求标签。
缺身份、漂移、插件缺失或旧 fallback 已决定记录均不能 authorize/start。

### 7.4 UI 收缩边界

`ReviewDocument` 的最小安全协议在实现前固定如下：

- item 类型只有 `json_value`、`json_tree`、`status`、`subject_metadata`、`download`；前三类必须
  引用可解析 JSON 中存在的 RFC 6901 pointer（空串只表示文档根），后二类只引用 subject，不接受
  pointer；
- PDF、图像、CSV、TCAD 包及其他非 JSON subject 只能显示受控 metadata 或经核心固定附件路由下载；
  插件不得提供 URL、data URI、富文本、HTML、内联媒体源、CSS、脚本或 disposition；
- subject 唯一顺序是 approval contract 的 `subject_ports` 顺序，collection 内保持调用绑定顺序。
  projector 只能引用该冻结序号，不能重排、复制或注入 subject；
- 编译期要求全部 subject port 的 `max_items` 总和不超过既有 ReviewManifest 上限 256；preflight
  再核对实际数量、单项/总输入字节。文档最多 64 节、512 项，标题/标签/说明各自有界，规范 JSON
  总量不超过 512 KiB；超限一律不创建审批；
- 核心统一 HTML escape 插件显示词和 pointer 解析值，保持 CSP、`nosniff`、固定 attachment
  disposition 和完整 raw tree。ReviewDocument 没有科学值字段，只保存展示词与指针；历史重放只读
  请求内文档和 subjects，不再调用 projector。

核心 UI 只保留四类固定能力：通用 `ReviewDocument` 渲染、完整安全原始树/安全二进制下载、决定
表单、实例/会话这两类控制面页面。删除 `render.py` 中按 scientific foundation、figure、device
parameter 和 TCAD Schema 选择标题、标签页或专用字段的分支。没有文档的历史科学/领域审批只显示
问题、原始对象和已记录决定；未知/已卸载插件的历史审批仍可审计，但不能重提。

普通行动目录只请求 `scope=public`；support 仅在已执行步骤的 lineage/技术信息中按精确
operation id 展示，internal 不进入普通 UI。Root 对 scheduler 保留显式三视图查询，视图不改变
同一 Operation 摘要、准入、权限或调用路径。

### 7.5 实现顺序与完成门

R4-D-B 严格按以下最小顺序实现，每一项失败均停在本阶段：

1. 增加 ReviewDocument/合同身份 Schema、provider-aware 输入合同、approval executor 编译负例和
   通用调用路径；
2. 实现证据与两种参数 approval Operation，把现有参数校验迁到插件并关闭通用 Root 绕过；
3. 升级 TCAD projector，并在创建审批和 authorize/start 两端复核同一 Effect/contract 身份；
4. 用固定文档 renderer 替换四类领域 Schema 分支，保留历史 raw fallback；
5. 验证恶意 HTML/URL/内联媒体、错误 pointer、错/超量/重排 subject、错父链、错 verdict、错
   coverage、旧/其他 provider 决定、合同漂移、插件卸载历史查看、重复调用、审批 UI 唯一决定，
   以及旧 fallback 已决定仍不可启动；
6. 验证 core-only/default-full clean wheel、public/support/internal 三视图、专项/全仓、源码零缓存、
   发布清单和核心领域 import 扫描。

证据完成门必须使用真实 figure bundle 增加四个独立反例：遗漏一个 collection item、遗漏
validation report、遗漏 frozen source、遗漏 extraction primary；即使其余 subjects、父链和 audit
彼此自洽也必须拒绝。provider 完成门另含：跨插件未声明依赖、provider disable/upgrade、历史无
身份审批，以及“provider A 已批准但候选只接受 provider B”的 readiness/preflight 一致失败。
typed intake revision 另设一正三负：完整的 revised primary、同调用 diff、精确 unchanged-evidence
receipt、base family 和新独立 audit 可以创建资格审批；缺 diff、receipt 未覆盖 exact base evidence、
普通 transform 伪装 revised primary 分别拒绝。该正例还须证明 foundation 来自 revised primary 的
精确 split 调用，负例须覆盖递归环或超过深度上限至少一项。

R4-D-A 必须先由独立审查者判断上述方案是否仍是“单一 Operation 闭包 + 轻控制面”的最小实现，
特别审查 approval executor 是否必要、三个 approval Operation 的集合是否足够且不重复、
ReviewDocument 是否安全可用，以及是否不当地扩大了插件对控制面的权限。书面通过以前不得开始
R4-D-B 生产代码。

明确不做：新审批表、审批 DSL/Schema registry、插件 HTML renderer、动态选项脚本、新资格状态机、
按领域路由器、UI 自己决定准入、把执行授权与科学资格合并、为历史文件维持可新建的兼容入口。

R4-D-A 首轮独立报告
`reviews/R4_D_A_APPROVAL_VIEW_DESIGN_INDEPENDENT_REVIEW.zh-CN.md` 认可 approval executor、固定
ReviewDocument、三个科学审批 Operation 和单一三视图方向，但因五项合同未闭合而打回：provider
身份没有进入下游资格、参数束漏 extraction primary 且旧来源全等规则错误、把受信进程内 projector
误写成硬沙箱、二进制/集合/资源安全协议未冻结、执行启动端未复核同一 compiled identity。上述五项
已逐条写回 7.2—7.5；未取得第二轮书面通过前，R4-D-B 仍未开始。

第二轮报告
`reviews/R4_D_A_APPROVAL_VIEW_DESIGN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 确认首轮五项主体已经
闭合，但再次打回两个断口：通用 evidence qualifier 未证明唯一 primary 及完整 producer 输出族；
跨插件 provider 依赖、readiness 和 legacy bridge 没有唯一合同来源。返工已把唯一 primary、
producer_output_family/evidence-source 窄快照、figure 漏项反例、PluginDependency、候选级 provider
readiness 和仅保留两个资格前 bridge 写入 7.2、7.3、7.5。第三轮书面通过前仍不得实现 R4-D-B。

第三轮报告
`reviews/R4_D_A_APPROVAL_VIEW_DESIGN_INDEPENDENT_REVIEW_ROUND3.zh-CN.md` 确认第二轮的 Task family、
provider 依赖/readiness、legacy bridge、参数、UI 和 execution 边界均已闭合，只打回一个当前公开
路径断口：结构化修订后的 final ScientificIntake 是 transform 输出，不能由 Task family 恢复。
返工已把 family resolver 限定为智能体提取与 typed intake revision 两个分支，并冻结 diff、receipt、
base family、revised split 和新独立 audit 的完整父链与正负测试。第四轮书面通过前仍不得实现
R4-D-B。

第四轮报告
`reviews/R4_D_A_APPROVAL_VIEW_DESIGN_INDEPENDENT_REVIEW_ROUND4.zh-CN.md` 确认 typed intake
revision 的 exact revised object、同调用 diff、base/patch/receipt、base family、frozen sources、
新独立 audit、revised split、递归上限和普通 transform 失败关闭均已闭合；即时 family snapshot
没有成为第二注册表，前三轮已通过边界也无回归。结论为“通过，允许进入 R4-D-B”。R4-D-B 现按
7.5 的顺序从核心合同与通用调用路径开始实现，每个关键环节仍须独立审查通过后才能继续。

### 7.6 R4-D-B 核心审批与科学资格实现状态

第一环实现后的独立报告
`reviews/R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md` 结论为“打回”。
报告确认 approval executor、既有审批生命周期复用、窄 projector context 和编译身份方向正确，
但发现四项失败关闭缺口：审批可带隐藏输入、空 provider 回退形成第二资格权威、JSON pointer
不够严格，以及编译合同未覆盖 ApprovalRequest 的静态界限。按报告要求，核心第一环和三个真实
科学 provider/全部消费者迁移被合并为一个原子返工阶段；当前修复如下：

1. Operation ABI 升为 6；`approval` 成为 executor kind，但只能是 public、无输出、无 Worker
   authority，且 executor component 必须与唯一 approval projector 完全相同；仍复用既有
   ApprovalService、SchedulerBinding 和 HumanDecision，不新增运行表或状态机；
2. `ReviewDocument` 固定为五种 item、64 节、512 项、256 subjects 和 512 KiB，并在请求创建与
   历史读取两端复用严格 RFC 6901 解析；非法 `~` 转义、数组前导零、越界、非 JSON subject 和
   不存在路径均失败关闭；插件只能返回数据模型，不能返回 HTML、URL、脚本或模板；
3. 新 compiled 审批请求冻结 operation id/version/digest 与 approval contract digest；历史请求字段
   仍可为空，但 provider-aware 查询只接受身份完全一致、同一请求/决定覆盖全部必需 refs 的决定；
4. approval Operation 的全部输入必须按编译顺序成为可见 subject；合同在编译期同时限制问题、
   选项数量、决定唯一性、标签和说明长度，不允许“可编译但不可创建”的审批项；
5. `InputPortSpec.accepted_approval_operations`、compiler provider edge、跨插件依赖门、provider
   contract digest 传播和 scheduler 安全投影已接入。所有带审批 cohort 的 Operation 必须声明
   非空 provider；Root 的候选级 readiness 与 invoke preflight 共用同一 provider-aware 判定，
   provider-less 分支已经删除，历史无身份决定只读而不能准入；
6. 通用科学插件已注册 `science.evidence.qualify.v1`、
   `science.parameters.qualify.pass.v1` 和
   `science.parameters.qualify.exception.v1` 三个公开审批 Operation。通用 scientific-foundation
   创建旁路已经关闭；hypothesis、objective、参数不确定性与 TCAD 参数消费者均冻结接受的精确
   provider identity，不再使用全局 kind/option 资格；
7. 证据 projector 从既有 Task/output、Artifact 父链和编译目录即时恢复唯一 producer family。
   初次文本提取真实链路已经贯通；typed intake revision 真实经过结构化修订、确定性应用、
   未变证据收据、新独立 audit、revised split 和重新资格化。普通 transform、递归环、超过八层、
   缺 diff 或 receipt 均不被当作可资格化 producer；
8. 参数 pass/exception projector 已复用既有严格模型和确定性 coverage 重算，并保留
   metadata-only catalog source 的正确语义；figure projector 的完整输出族另有遗漏 collection、
   validation、frozen source 和 primary 四个独立失败闭合测试；
9. `operation_invoke` 已能按 subject port/collection 冻结顺序构造窄 projector context、创建审批并
   保持完整指纹幂等；不会创建 Task、ExecutionRequest 或占位 Artifact。

第二轮独立报告
`reviews/R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 确认首轮四项
阻塞已闭合，但仍打回三个生产边界：未审批 foundation 在对象库存中仍被全局标为 qualified，
两个零调用的 provider-less 查询仍残留；legacy 参数封存仍错误要求 observation source 与 catalog
source 全等；figure 四漏项和修订深度只由人工 projector/private helper 测试，未经过真实跨边界族。

第三轮送审前曾完成以下返工：

1. 当时对象库存从当前编译目录即时枚举与对象 kind 匹配的 approval provider；未命中决定时标为
   `human_review_required`，命中任一 provider 决定后恢复 `qualified`。第三轮独立审查已证明该做法
   仍会把候选相关的 provider 权威错误聚合成全局对象资格，因此此项已被打回；两个零调用的
   provider-less 查询删除仍然有效；
2. legacy 参数封存改为 observation source 必须是 catalog source 的子集；每个 catalog source
   仍必须出现在 intake evidence、冻结输入或冻结 web source 中。真实 Worker 已验证一个未贡献
   参数值/coverage/独立来源计数的 metadata-only source 能依次通过提取 validate/finalize、split、
   coverage、独立参数 audit 和 pass qualification invoke；
3. 真实 figure Operation Agent 已封存 manifest、panel、overlay、curve table 和确定性 validation
   report 的完整 collection family，再由真实 audit Agent、split 和资格 invoke 完成正向链；分别遗漏
   collection item、validation、frozen source 或 extraction primary 时 Root 全部拒绝；
4. 真实 typed intake lineage 连续运行八层 audit、patch 和确定性 apply，并为最终层生成 exact diff、
   receipt、新 audit 与 split；最终资格 invoke 因 family resolver 深度上限失败关闭，不再依赖人工
   `depth`/`visited` 参数证明。

第三轮独立报告
`reviews/R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND3.zh-CN.md` 仅保留一项
阻塞：对象级目录扫描会令参数 provider 决定把同一个 foundation 全局标为 `qualified`，但只接受
证据 provider 的 hypothesis 候选仍不可用且 preflight 拒绝。第四轮送审前按其最小口径修正如下：

1. `ScientificObjectStatus.qualification` 新增中性 `available`；scientific foundation 在结构存在且
   没有 producer、payload 或 handoff 失败时始终使用该状态，不读取或聚合任何审批决定；
2. 删除对象级 `_artifact_qualification` 及全目录 provider 扫描。provider 决定只由候选级
   readiness 和权威 invoke preflight 按消费 Operation 冻结的精确身份解释；
3. `available_artifacts` 明确为结构库存；`effective_kinds` 仍只承载已有全局资格语义。没有 foundation
   时 `unresolved_needs` 只报告结构缺口 `scientific_foundation`，存在后不生成虚构的
   `approved_scientific_foundation` 全局缺口；
4. 新增同一真实 scientific foundation 的跨 provider 回归：无决定、仅参数 provider 决定时，
   foundation 均保持 `available` 且证据候选拒绝；精确证据 provider 决定后候选投影与 preflight
   同时成功；证据 provider 合同摘要变化后两者同时失效而对象状态不变；
5. 既有真实证据链同步验证审批前后 foundation 都保持 `available`，但 hypothesis 的候选可用性只随
   精确证据 provider 决定变化。

第四轮独立报告
`reviews/R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND4.zh-CN.md` 确认 provider
四阶段隔离已经闭合，但打回结构解析顺序：`available` foundation 被 qualified-only 循环跳过，
显式 objective contract 和畸形 payload 均未被发现；`available_kinds` 又在后续校验前冻结，使畸形
research objective 仍残留在结构库存。第四轮计划曾写“聚焦五文件 71 项”，但没有附命令，审查者
按第三轮既定五文件只能复现 57 项；该不可复现计数作废。

第五轮送审前按最小边界完成以下返工：

1. canonical scientific foundation 无论是否具有 provider 决定，都执行严格 Schema 结构解析；失败
   时状态改为 `revision_required`、记录 blocker，并退出结构库存；
2. 结构解析只读取 `objective_contract is not None`。它不会读取 foundation 中的主张作为已批准
   claim，也不会改变任何 provider 准入；显式合同缺少当前 objective projection 时继续产生既有
   `research_objective:projection_missing` 阻塞；
3. `available_kinds` 改为全部 foundation、metric、objective 和 coverage 校验完成后，从最终
   `objects` 状态重算；同 kind 只要还有一个最终有效对象就保留，坏对象不会污染库存，也不会误删
   好的同类对象；
4. 新增真实回归覆盖：合法 foundation 无目标合同；合法 foundation 有合同但无 projection；错误与
   正确 provider 对 objective project readiness/preflight 的隔离；畸形 canonical foundation；畸形
   objective、coverage、metric；以及同 kind 好坏对象并存；
5. `qualified_portfolios`、诊断 verdict、claim acceptance、execution completion 和其他
   `effective_kinds` 消费仍保持 qualified-only，没有机械接受 `available`。

第五轮固定聚焦命令为：

```bash
pytest -q \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_invoke_preflight.py \
  tests/operations/test_general_science_plugin.py \
  tests/operations/test_r4_approval_operation.py \
  tests/operations/test_tcad_operation_plugin.py
```

该命令 72 项、全部 operation 202 项、全仓 236 项通过；`git diff --check`、源码/插件编译、两个
安装脚本语法检查和旧 provider-less/对象级聚合入口搜索均通过。新清洁发布候选含 278 条临时清单
记录并逐项通过，发布树无构建缓存，
核心与通用科学目录精确编译为 32 个 Operation，其中三个是公开科学资格审批 Operation。根
`MANIFEST.sha256` 仍待第五轮正式报告纳入后一次冻结。

第五轮独立报告
`reviews/R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND5.zh-CN.md` 确认上述六项
主体和 72/202/236 测试均通过，但打回最后一个派生顺序缺口：canonical foundation 解析成功后，
实现会在最终状态过滤前聚合 objective contract，令已被标为 `blocked` 或 `revision_required` 的
合法对象仍制造 `research_objective:projection_missing`。

第六轮送审前保持 canonical payload 对所有状态的严格解析，只把合同存在性聚合条件收紧为“解析
成功且该对象最终 qualification 精确为 `available`”。新增真实回归分别覆盖：

1. 合法、含合同但由 `scientific_claim_admissible=false` 标记为 blocked 的 foundation；
2. 合法、含合同但由精确 Worker handoff 标记为 revision-required 的 foundation；
3. 无合同的 available foundation 与含合同但 blocked foundation 同实例并存。

三种情况均不产生目标投影缺口；原有 available foundation 自身含合同时的缺口和精确 provider
门禁回归继续通过。该修复未新增类型、状态、表、缓存、注册表或 Operation，也未改变任何
`effective_kinds` 消费。

第六轮送审验证再次得到固定聚焦 72 项、全部 operation 202 项、全仓 236 项通过；静态检查、旧
入口搜索、源码/插件编译和安装脚本语法检查通过。新清洁发布候选纳入第五轮正式报告后含 279 条
清单记录，逐项摘要通过、无构建缓存，并从发布源码编译得到 32 个 Operation 和三个公开审批
Operation。根清单仍待第六轮正式报告纳入后统一冻结。

第六轮独立报告
`reviews/R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND6.zh-CN.md` 已逐项复现
blocked、revision-required、mixed sibling、available contract/provider 和畸形 payload 五类边界，
并确认固定聚焦 72 项、operation 202 项、全仓 236 项、279 条清洁发布清单、32 个 Operation/三个
公开审批 Operation、零缓存与安装脚本语法检查全部通过。结论为“通过并允许进入 R4-D-C”。

R4-D-B 只待根发布清单纳入第六轮报告并由独立发布审查者核验；该机械收口通过后进入 7.5 第 3 项
的 TCAD execution 身份迁移。

### 7.7 R4-D-C 执行审批身份实现状态

本段只实现 7.5 第 3 项，不改审批界面，不增加表、状态、注册表或领域路由。实现后的唯一新建
授权路径为“编译后的 Effect 创建执行请求 → 同一编译合同创建审批 → 启动时再次核对当前合同”：

1. `ExecutionRequest` 在既有不可变载荷内保存完整 `CompiledApprovalIdentity`；字段保持可选仅为
   严格读取历史请求，历史规范字节不因缺省字段改变。经 `operation_invoke` 新建的 Effect 必须
   同时把 operation id、version、operation digest 和 approval contract digest 写入请求正文与
   Artifact 标签；旧 `execution_request_create` 仍可形成只读历史请求，但不能为其新建执行授权；
2. `execution_approval_request_create` 从请求冻结身份定位当前 compiled Effect，重新核对操作仍安装、
   executor、preparation profile、四项 Artifact 标签和完整审批合同身份。任一缺失或漂移均在创建
   ApprovalRequest 前失败；审批问题、选项、subject 顺序和 `ReviewDocument` 只来自该 Effect 的
   编译合同和 projector，旧 presentation 回退不参与新执行审批；
3. 内置无副作用 Effect 与 TCAD Effect 的 projector 均改为消费窄
   `ApprovalProjectorContext` 并返回固定 `ReviewDocument`。TCAD projector 严格解析同一冻结
   `ExecutionRequest` 与完整 `ReviewedDeckPackage`，展示执行器、准备合同、操作身份、工程、独立
   审查、求解能力和解析输入，不返回 HTML、脚本、模板或领域 UI callable；
4. `execution_start` 不复用创建时结论。它再次从当前 compiled catalog 计算完整身份，再把该身份
   作为显式前条件传给 `ExecutionBridge` 和 `ExecutionService.authorize`；后者重新核对执行请求身份、
   决定对应的精确 ApprovalRequest、审批 kind、ApprovalRequest 身份，以及请求与决定共同覆盖的
   精确 request/payload 两个 subject，全部通过后才写出授权载荷并调用 adapter；
5. 历史兼容只允许读取：缺身份请求、合同漂移、插件卸载、错误身份 ApprovalRequest，即使已有
   `authorize_execution` 决定也不能授权或启动，执行状态保持 `created`，adapter 提交次数保持零。

新增专项文件 `tests/operations/test_r4_execution_approval_identity.py`，并同步迁移安装态统一调用、
真实本地审批生命周期与 TCAD 运行时插件测试。反例精确覆盖：审批前合同漂移、决定后合同漂移、
决定后插件卸载、精确 subjects 但错误 operation digest 的审批身份、以及已有人类决定的无身份历史
请求。安装态正例同时证明新 ExecutionRequest、ApprovalRequest 和编译 Effect 保存同一完整身份，
并只使用 `ReviewDocument`。

送审前固定验证结果：R4-D-C 专项与三条受影响跨边界测试共 14 项通过；全部 operation 测试
207 项通过；全仓 241 项通过；`git diff --check`、六个实现文件与专项测试的静态编译通过。根发布
清单暂不重建：必须先写入本段独立审查报告，再一次性封存并独立核验，避免以审查后新增文件使
清单立即过期。独立审查书面通过前，R4-D-D 固定安全 renderer 不得开始。

R4-D-C 独立报告
`reviews/R4_D_C_EXECUTION_IDENTITY_INDEPENDENT_REVIEW.zh-CN.md` 已独立复跑 14 项专项、207 项
operation 测试和 241 项全仓测试，并补充验证错误 subjects、缺 Artifact 身份标签和审批前插件卸载
三个负例。报告确认请求正文/标签同源、审批创建与启动双端复核、projector 编译来源、服务层精确
对象核验、历史请求只读和单一控制权威均闭合，结论为“通过，允许进入 R4-D-D”。

### 7.8 R4-D-D 固定安全渲染器实现状态

本段只实现 7.5 第 4 项并复核既有三种目录视图，不修改 Approval、Execution、Task、Artifact 或
Operation 的任何生命周期。实现采用直接删除旧领域页面而非在其上增加兼容分支：

1. `approval_ui/render.py` 从 3149 行领域工作台缩为 370 行固定渲染器。它只读取 ApprovalRequest
   内已经冻结的 `ReviewDocument`，按固定五种 item 渲染中文标签、subject 序号和严格 JSON
   Pointer；标题、说明、标签、状态值和 JSON 内容全部经核心 HTML escape，插件不能传入 HTML、
   CSS、脚本、模板、URL、data URI 或媒体 disposition；
2. 删除按 scientific foundation、figure manifest、device parameter、TCAD package 和 problem
   Schema 选择页面、标题、页签、摘要、来源表或图片的全部核心分支。插件领域内容只通过其已编译
   projector 产生的固定文档显示；渲染历史请求时不运行插件，也不访问 compiled catalog；
3. 所有请求始终附带全部 subject 的安全原始树或二进制元数据。非 JSON 字节绝不内联，只能经过
   核心固定 `/subject/<approval>/<index>` 路由以 `application/octet-stream` 和固定
   `Content-Disposition: attachment` 下载；旧 `/preview` 内联图像路由已经删除；
4. 没有 `ReviewDocument` 的历史科学/领域请求统一显示“固定安全回退”和完整原始对象，不按历史
   Schema 猜测含义。实例创建与进程绑定仍保留两种控制面固定标题、完整对象和原有决定表单，不被
   伪装成科学 Operation；
5. 决定表单、CSRF、nonce、本地身份、唯一决定和历史结果继续复用既有 ApprovalService/UI 路径。
   浏览器脚本只保留决定理由必填状态与防重复提交 17 行；样式删除全部图证据、参数、TCAD、树交互
   和专用页签规则，保留固定文档、原始对象、决定、仪表盘与实例维护所需的 231 行；
6. public/support/internal/all 继续是同一 compiled catalog 的既有投影。普通目录默认 public，
   support 和 internal 只能显式查询；本段没有添加 UI 目录副本、视图注册表、权限表或 Operation
   摘要分叉。

新增 `tests/operations/test_r4_approval_ui_renderer.py` 四项真实边界测试：五类文档 item 同页渲染；
恶意标题/说明/标签/JSON/身份文本全部转义且不能形成可执行标签或 URL；伪图像二进制不内联、固定
附件响应带 CSP/nosniff 且旧 preview 返回 404；历史 TCAD Schema 只走 raw fallback；实例/会话
控制面标题仍可用。安装态原有 UI 测试继续证明同一精确对象页面稳定且只能记录一个决定。

送审前验证在单进程约 7 GiB 虚拟内存上限下串行执行：受影响 UI、科学审批和执行审批测试 46 项
通过；全部 operation 测试 211 项通过；全仓 245 项通过。静态编译、差异格式和领域分支/旧交互
搜索通过。

R4-D-D 独立报告
`reviews/R4_D_D_FIXED_RENDERER_INDEPENDENT_REVIEW.zh-CN.md` 已独立复跑 46 项聚焦测试、211 项
operation 测试和 245 项全仓测试，并补充核对恶意 URL/HTML、历史 raw fallback、非 JSON 附件、
控制面固定标题以及 public/support/internal/all 同源投影。报告确认核心渲染器没有领域 Schema
分支、插件可执行 UI 扩展、第二目录或决定权威，结论为“通过，允许 R4-D 收口”。

R4-D 的四个实现子阶段至此均已通过独立审查。最终只剩一次机械发布封存与跨边界总审查；该审查
必须同时核验根工作树清单、清洁发布树自身清单、单一编译目录、三种规划视图和旧入口清除结果，
通过前不得宣布 R4 整体完成。
