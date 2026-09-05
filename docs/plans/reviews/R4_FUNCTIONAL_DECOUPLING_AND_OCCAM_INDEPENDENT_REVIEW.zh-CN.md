# R4 功能、解耦与奥卡姆剃刀独立审查

日期：2026-08-29  
审查对象：当前工作树中的 R4-A、R4-B、R4-C、R4-D 实现  
审查性质：全新、对抗性审查；既有 R4 审查报告仅作为可核验证据，不继承其结论  
最终结论：**有条件通过**

## 1. 结论摘要

R4 的窄范围目标已经在真实安装入口上实现，且不是只在测试装配中伪造出来的：

- 根包通过唯一的 `scidiscovery.plugins` 入口发布核心插件和通用科学插件；
- TCAD、曲线评价和 InGaAs 分别通过自己的包入口加入同一编译目录；
- TCAD Agent、任务私有工作区、文件策略、调试工具、确定性变换、执行副作用和运行时工厂都能从同一 `CompiledOperation` 闭包追溯；
- 曲线评价及 InGaAs 项目能力已迁到 `operation_invoke`；发布包不再发布旧的 `operation_specs` 或 `transform_adapters` 入口；
- 审批投影由编译合同提供，界面使用核心固定安全渲染器，不执行插件提供的页面代码；
- 121 项聚焦测试和 245 项全仓测试均在单进程、7 GiB 地址空间限制下通过。聚焦测试包含从干净 wheel 创建的隔离安装环境，不能等同于只在源码树中运行的 `pytest`。

但是，当前实现只能证明“R4 迁移批次完成”，不能证明整个框架已经完成通专用解耦或达到插件机制的最终形态：

1. `mcp_root.py` 仍按特定输入端口、科学对象族和通用科学操作名解释审批生产者，新增一类审批插件仍可能要求修改 Root；
2. 旧角色包扫描、旧变换适配器加载器和 Root 的旧创建入口仍在生产代码中，只是发布包已不再向旧入口注册迁移后的能力；
3. `tasks.py`、`mcp_root.py`、通用科学插件和若干适配器仍聚合过多职责，R4 新增闭包没有同步换来足够的旧控制层删除；
4. 工具、工作区、执行副作用和运行时组件能够从闭包解析，但“技能”目前被明确拒绝直接物化，只能将专家内容冻结进提示资源；
5. 运行时配置缺失或控制进程与 Worker 进程配置漂移会在能力绑定/工具调用时失败关闭，但启动阶段没有证明两侧读取的是同一份配置内容，也没有安装后活动任务的卸载/回滚验证。

因此，本报告不打回 R4-A—D 已完成的迁移，也不同意把当前状态描述为“功能解耦、插件注册和复杂度治理已经全面完成”。允许以 R4 为基线进入 R5，但必须把第 2 节的条件作为 R5/生产化门槛，而不能把它们悄悄改写成已完成事实。

## 2. 按严重性排序的发现

### F1（中）：审批生产者语义仍部分硬编码在 Root，限制“只安装插件即可扩展”

证据：

- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py:1319` 的 `_invoke_approval_operation` 负责解释审批操作；
- 同一方法在约 `1362—1367` 行只为名为 `extraction_primary` 的端口建立生产者输出族；
- `mcp_root.py:1439` 的 `_producer_output_family_from_envelope` 仍有设备参数角色、上下文和 Schema 的兼容分支；
- `mcp_root.py:1575` 的 `_typed_intake_revision_family` 直接引用 `science.revision.apply.intake.v1`、`science.intake.revise.v1` 及固定端口语义。

影响：R4-D 已把“显示什么、允许决定哪些指针、谁可复核”编译进审批闭包，但“如何从任意插件输入推导审批对象族”还没有完全变成领域无关合同。新插件若使用当前已支持的审批类型和约定端口可以一次安装；若引入新的生产者族，仍可能修改 Root。这是插件扩展性缺口，不是安全绕过，因为最终审批状态仍只有 `ApprovalService` 一个权威。

最小修复：不要新增审批注册表。将生产者族解析改成编译期可校验的 Operation 端口/输出关系，或限定为从已绑定 Artifact Schema 总函数推导；Root 只执行编译结果。保留现有审批生命周期、不可变 Artifact 和决定权威。

### F2（中）：旧控制面入口仍然存在，但在当前发布组合中未形成第二插件权威

证据：

- `src/scidiscovery/platforms/roles.py:69—103` 仍扫描源码 `plugins/` 并读取 `scidiscovery.agent_role_packs`；
- `src/scidiscovery/artifact_agent/transforms.py:90` 仍定义并加载 `scidiscovery.transform_adapters`；
- `mcp_root.py:1705`、`:1934`、`:2249`、`:2440` 仍分别暴露 `artifact_transform`、`task_schedule`、直接审批创建和直接执行请求创建；
- `mcp_daemon.py:112` 启动时仍调用旧 `load_transform_adapters()`；
- 根包、TCAD、曲线和 InGaAs 的 `pyproject.toml` 当前只发布 `scidiscovery.plugins`，没有发布上述两个旧入口；已迁移 profile 也有旧变换入口拒绝测试。

判断：这是 R5 已明确承接的债务，不足以单独打回 R4。当前发布包下旧发现集合为空，迁移后的 TCAD/曲线能力不能从旧入口被调用，因而没有观察到两个活动注册表同时决定同一能力。不过，旧 Root 表面仍是可调用生产代码，若第三方私下发布旧 entry point，仍会重新激活旁路；最终架构不能长期依赖“希望没人注册”来保持单一权威。

最小修复：完成剩余桥接迁移后直接删除旧 entry point loader 和对应 Root 创建入口，不要给旧入口再包一层新适配器。

### F3（中）：R4 功能增加后，复杂度净收敛很有限，巨型控制文件尚未合理拆分

`tasks.py` 为 6786 行，`mcp_root.py` 为 3531 行。二者分别同时承载任务生命周期/文件协议/科学输出验证/TCAD 调试持久化，以及 MCP 门面/科研 readiness/Operation 调用/旧桥接/审批/执行。这不是“行数大”本身的问题，而是变化原因不同、依赖方向不同的职责必须在同一文件修改。

对基线与当前所选核心文件的机械比较显示：原调度、角色、运行时、Root、Task 和渲染代码合计约从 13657 行降到 11297 行；加入新的 `operations` 包约 2060 行后约为 13357 行，只减少约 2.20%。这不否定 R4 的单目录收益，但说明旧控制层尚未被新闭包实质替换到足以满足奥卡姆剃刀。计划中的 R5 “核心控制层至少降低 10%”尚未达到。

最小修复：按职责提取无状态或单一权威的窄协作者，不增加数据库表、状态机、注册表或第二服务权威。详见第 5 节。

### F4（中低）：运行时配置能失败关闭，但缺少启动一致性证明和缺配置早期门禁

`src/scidiscovery/operations/runtime_plugins.py:81—141` 只遍历命令行给出的配置分配；安装了带 `runtime_factory` 的插件并不要求一定给它分配配置。控制 daemon 与 Worker daemon 分别读取配置文件，没有共同内容摘要握手。

这不会静默调用错误 TCAD 能力：

- 执行适配器按 `plugin_id:local_name` 与编译的 effect executor 精确匹配；冒名插件不能满足 TCAD executor；
- Worker 调试从任务的精确 `execution_capability` Artifact 读取能力，并由 `debug_adapter.py:136—168`、`:472—499` 对当前适配器的 profile、solver kind 和 capability 摘要再次匹配；漂移时失败关闭。

剩余问题是可用性和可诊断性：缺配置时目录仍可展示 TCAD Operation，直到 capability/服务预检或 Worker 工具调用才失败；两 daemon 配置内容不同会导致任务较晚失败。最小修复是让 `operation_preflight` 同时检查该 Operation 的已解析运行时绑定是否齐全，并让两个 daemon 启动时比较同一个配置内容摘要。该摘要应是部署事实，不要新建科研 Artifact 或生命周期。

### F5（低）：插件技能不是一等运行时组件，当前只能使用冻结提示资源

TCAD 作者/审查专家合同已经进入插件资源摘要并随闭包冻结，Codex Worker 也显式关闭宿主隐式技能搜索；这比继承不可审计宿主技能更安全。但 `test_unmaterialized_agent_resources_fail_closed` 明确证明额外技能资源会以 `agent_resources_unsupported` 被拒绝。

因此：

- 原生工具、注册 Worker 工具、工作区策略和静态提示资源已支持；
- “安装任意 skill 并按 OperationSpec 物化给 Agent”尚未支持；
- 不能把当前结果宣传成工具、技能、MCP 和领域资源全部统一注册完成。

R4 原计划把未定义清楚的技能物化拒绝掉是正确的失败关闭选择，不构成阻塞。后续只有出现真实、不可由提示资源表达的技能复用需求时，才应增加一种最小、任务本地、内容寻址的资源物化方式。

### F6（低）：测试证据很强，但不覆盖真实浏览器和真实求解器

本轮没有启动真实浏览器自动化，也没有连接真实 Sentaurus 求解器。固定 UI 的 HTML 安全和路由行为由单元/集成测试覆盖；TCAD 能力绑定、调试工具、执行生命周期由假适配器及真实子进程协议测试覆盖。它们足以判断 R4 合同实现，不足以证明实际部署环境、许可证、远端运行器或浏览器交互没有问题。

## 3. R4-A/B/C/D 实现判定

| 阶段 | 预期能力 | 真实安装入口证据 | 正/负向验证 | 判定 |
|---|---|---|---|---|
| R4-A | TCAD author/reviewer Agent、任务私有 deck 工作区、文件策略、封存与调试工具 | `plugins/tcad_artifact/pyproject.toml` 只发布 `scidiscovery.plugins`；`tcad_artifact.plugin:PLUGIN` 的 author/reviewer 闭包包含 Agent、workspace materializer/file policy/finalizer/snapshotter、Worker 工具和 Schema | TCAD 插件测试验证 author 有调试工具和文件工具、reviewer 无编辑/调试越权；Codex Worker 测试验证真实独立子进程与精确工具集 | **完成** |
| R4-B | TCAD 确定性变换、Effect、capability 和运行时配置迁入同一插件 | TCAD 插件同一 `PluginDefinition` 声明 transform、effect、runtime factory/config resource；`operation_invoke` 从 compiled executor 解析 | 已安装调用、父链、输出 Schema、冒名 runtime、缺 Worker task service、配置 symlink/重复配置均有负例 | **完成；配置一致性为非阻塞遗留** |
| R4-C | 曲线评价迁入单入口；InGaAs 只增量注册；旧 transform/operation-spec 发布入口删除 | curve 和 InGaAs 包各自只发布 `scidiscovery.plugins`；full/ingaas clean wheel 环境从入口加载 | 验证六个曲线操作、输入集合顺序/身份/父链、旧适配器拒绝、InGaAs 添加一个操作且已有闭包摘要不漂移 | **完成** |
| R4-D | 审批合同由编译目录投影，界面只用固定安全 renderer；执行审批身份绑定 | 通用科学插件发布三个审批 Operation；编译闭包含 provider/reviewer/允许指针/renderer projection；UI 不加载插件 Python renderer | 隐藏输入、provider 漂移/删除、允许指针、XSS、未知 Schema 原始下载回退、执行审批身份均有正负例 | **完成；任意生产者族仍受 F1 限制** |

结论是“四个迁移阶段都在安装态主路径完成”，不是“R4 相关测试能手工拼出这些对象”。

## 4. 边界链路与解耦完成度

### 4.1 Scheduler/MCP → CompiledCatalog

优点：

- `operation_catalog` 的 `public`、`support`、`internal`、`all` 是同一目录的投影，不是四个注册表；
- 调度入口按编译 Operation 名选择，`operation_preflight` 绑定精确语义输入；
- clean core 安装得到 32 个 Operation（public 18、support 14），full 安装得到 49 个（public 23、support 26），安装 InGaAs 后得到 50 个且已有摘要保持不变。

遗留：`scientific_readiness` 仍是 `mcp_root.py:633` 起的大型领域投影，旧角色列表和旧 Root 创建工具仍可见。它们是 R5 删除/收缩目标。

### 4.2 CompiledCatalog → operation_invoke

优点：

- `src/scidiscovery/operations/catalog.py` 只从 `scidiscovery.plugins` 加载；
- 编译器校验协议版本、重复插件/Operation/组件 ID、缺组件、错误组件种类、未使用组件、跨插件依赖/导出、Schema 资源和权限闭包；
- `operation_invoke` 只执行编译后的 executor，不从角色名、profile 文本或插件私有列表重新发现实现。

遗留：`compile_catalog` 本身超过 500 行，应拆出纯校验函数，但绝不能因此引入第二目录或第二缓存。

### 4.3 operation_invoke → Task/Transform/Effect

优点：三类执行器共用一个入口，并由 Operation 的 executor 类型决定生命周期；transform 输出及 parentage、Agent task 输入、effect 载荷均有专门负例。

遗留：通用科学变换和曲线/TCAD 变换大量包裹既有大适配器，说明“入口统一”已经完成，而“实现按功能解耦”尚未完成。`artifact_transform` 和 `task_schedule` 仍是旧表面。

### 4.4 Task/Transform/Effect → Worker/Approval/Execution

优点：Worker 只接收编译闭包允许的工具、工作区和资源；审批和执行决定仍由既有唯一服务持久化；插件不能提供可执行 UI renderer；effect adapter 按编译的 `plugin_id:binding` 绑定。

遗留：审批对象族推导仍在 Root，运行时配置两 daemon 无摘要握手，旧直接审批/执行创建入口未删。

### 4.5 Worker/Approval/Execution → Artifact

优点：Worker 正式结果、附件、变换输出、执行 capability/输出和审批主体最终都落在不可变 Artifact/受控状态中；Worker 聊天文本不是结果；输出验证、封存及父链有负例。

遗留：`TaskService` 仍直接识别设备参数和多类科学 Schema，也持有 TCAD 调试表及文件协议，领域知识尚未完全回到插件验证器。

综合评价：目录/调用权威已显著解耦；领域校验、旧入口和服务职责尚未解耦完成。准确表述应是“R4 建立了可工作的统一主路径”，不是“所有旧路径和核心领域硬编码均已消失”。

## 5. 大型生产 Python 文件逐项审查

本轮统计 `src/` 与 `plugins/` 下生产 `.py`，共 40 个文件超过 500 行，其中 14 个超过 1000 行。以下判断不把行数本身当缺陷；“拆”只在文件内存在多个独立变化原因、跨层依赖或可删除旧职责时提出。

### 5.1 超过 1000 行

| 行数 | 文件 | 内聚性判断 | 最小处置 |
|---:|---|---|---|
| 6786 | `artifact_agent/service/tasks.py` | **不内聚**：任务生命周期、租约、输入暴露、文件写入/补丁、输出验证、证据缓存、科学 Schema 分支和 TCAD 调试持久化共存 | 优先拆为任务生命周期、Worker 文件/输出、证据缓存、调试账本窄协作者；共用原数据库和 `TaskService` 权威，不增状态机 |
| 3531 | `artifact_agent/interfaces/mcp_root.py` | **不内聚**：MCP DTO/门面、readiness、Operation 调用、旧变换/任务、审批、执行均在一类 | 按库存/Operation 调用/审批/执行/遗留桥接拆路由模块；最终删桥，不建第二服务 |
| 2470 | `general_science_plugin.py` | 一个插件定义目标内聚，但声明、validator、projector、资源与几十个 Operation 同文件，修改原因过多 | 按合同资源、组件、Operation 声明分文件，最终仍只导出一个 `PLUGIN` |
| 2058 | `tcad_artifact/project_packager.py` | **部分内聚**：均围绕 TCAD 项目合同，但模型、patch/diff、封装、审查、运行时证明混合 | 拆“合同模型”“项目 patch/diff”“封装/证明”三个实现模块；不拆 Schema 身份 |
| 1922 | `service/scheduler_bindings.py` | 单一绑定服务，但 proposal/session/current/deletion 和大量 SQL 生命周期聚合 | 可拆 repository SQL 与无状态校验，保留一个绑定权威；优先级低于 Root/Task |
| 1477 | `schema/curve_score.py` | **内聚**：严格曲线合同及校验共同变化 | 保留；只在算法与模型明显分离时提取纯函数，不能为行数拆 Schema |
| 1387 | `interfaces/mcp_worker.py` | **不完全内聚**：Worker 路由、文件协议、分析、PDF/表格/网络和图证据脚本定位共存 | 按内建工具 handler 拆模块，Router 只分派编译允许的工具；不增加工具注册表 |
| 1322 | `service/approvals.py` | **基本内聚**：唯一审批服务、访问控制和持久化守恒共同变化 | 暂不拆服务权威；可提取纯 JSON Pointer/行转换函数 |
| 1281 | `tcad_artifact/transform_adapter.py` | TCAD 确定性变换相关，但多类 materialize/package/coverage 操作聚合 | 按变换家族拆纯实现，插件组件仍逐个显式引用 |
| 1219 | `service/tcad_debug.py` | 单一调试生命周期，状态复杂但内聚 | 保留一个服务；只提取诊断映射/纯验证，避免另建调试状态机 |
| 1126 | `schema/experiment_intent.py` | **内聚**：实验意图严格合同及交叉校验 | 保留 |
| 1095 | `general_transform_operations.py` | **不完全内聚**：变换实现、资源、组件和 Operation 工厂声明混合 | 拆声明与实现；删除 `_run_legacy` 依赖时直接收缩，不再加适配层 |
| 1065 | `curve_score/transform_adapter.py` | 曲线领域内聚，但 bundle、score、coverage、objective 四个变换家族混合 | 按家族拆纯实现；单一插件/目录不变 |
| 1022 | `approval_ui/app.py` | **不完全内聚**：HTTP 路由、审批页、dashboard、实例和 orphan 运维页共存 | 分离路由与页面模板函数；固定安全 renderer 和审批写权威不变 |

### 5.2 501—1000 行

| 行数 | 文件 | 内聚性判断 | 最小处置 |
|---:|---|---|---|
| 976 | `tcad_artifact/execution_control.py` | 合同、能力策略、执行 facade/router、进程/归档 I/O 混合 | 拆合同/策略与运行器 I/O，保留一个 adapter 权威 |
| 971 | `schema/curve_analysis.py` | 曲线分析合同与确定性分析相近 | 基本保留；若算法变更频繁再拆模型/算法 |
| 901 | `storage/sqlite.py` | 存储初始化和事务设施内聚 | 保留 |
| 893 | `figure_evidence_validation.py` | 图证据验证单一职责 | 保留；规则表可数据化但不要建新 registry |
| 828 | `tcad_artifact/remote_runner_py36.py` | 远端 Python 3.6 单文件部署单元，单文件本身是交付约束 | 保留单文件；拆分会破坏部署原子性 |
| 814 | `schema/device_parameters.py` | 模型与 coverage 计算混合 | 可提取 coverage 纯算法；Schema 保持唯一 |
| 789 | `schema/experiment.py` | 实验合同内聚 | 保留 |
| 767 | `artifact_agent/transforms.py` | 旧 transform loader/adapter 生命周期；当前是待删除债务 | R5 迁完桥后删除，不值得先重构 |
| 729 | `platforms/codex_worker.py` | 独立 Codex Worker 进程原型内聚，但当前主路径消费有限 | 暂保留作下一版本实验；设明确接入/删除门，不扩抽象 |
| 729 | `tcad_artifact/debug_adapter.py` | TCAD 调试 adapter 单一职责 | 保留 |
| 702 | `curve_score/operation_transforms.py` | Operation 变换包装器，同一领域但家族较多 | 仅在修改冲突出现时按 bundle/score/coverage 拆 |
| 691 | `core_context_policies.py` | 多角色/领域上下文策略硬编码于核心 | R5 迁入插件合同后删除或显著收缩，不先美化 |
| 679 | `platforms/codex.py` | Codex 配置、启动、MCP/工具门禁和结果解释混合 | 若继续作为生产启动器，拆启动配置与进程监督；权限决定仍来自 compiled agent |
| 651 | `tcad_artifact/plugin.py` | 单一 TCAD 插件声明，边界清楚但声明密集 | 可按资源/组件/Operations 分文件组装一个 `PLUGIN`；当前可接受 |
| 649 | `tcad_artifact/operation_workspace.py` | author/reviewer 工作区 materialize/finalize/snapshot 同一协议 | 基本保留；只提取共享路径验证 |
| 636 | `operations/catalog.py` | 单一编译权威，但 `compile_catalog` 同时做解析、闭包和全部校验 | 拆纯校验/闭包函数，保留单一 catalog 与一次编译缓存 |
| 627 | `tcad_artifact/project_materializer.py` | TCAD 项目物化单一职责 | 保留 |
| 611 | `service/executions.py` | 唯一执行请求状态服务，内聚 | 保留 |
| 607 | `builtin_plugin.py` | 核心插件声明内聚但声明量大 | 可拆声明片段，仍只导出一个 `PLUGIN` |
| 594 | `service/orphan_admin.py` | 孤儿对象管理单一职责 | 保留 |
| 593 | `portable_bundle.py` | 可移植 bundle 导入导出单一职责 | 保留 |
| 587 | `schema/__init__.py` | 大量重导出，不应承载业务 | 缩减公共导出或生成重导出；不要再手工维护巨型聚合面 |
| 576 | `schema/figure_evidence.py` | 图证据合同内聚 | 保留 |
| 570 | `security/task_tokens.py` | 任务令牌安全边界内聚 | 保留 |
| 559 | `schema/scientific_objective.py` | 科学目标合同内聚 | 保留 |
| 546 | `curve_score/figure_evidence_normalizer.py` | 图证据归一化单一职责 | 保留 |

高置信的首批拆分只应是 `tasks.py`、`mcp_root.py`、`mcp_worker.py`、通用科学插件/变换声明和固定 UI 路由。其余文件多数是领域合同或单一生命周期，不能为满足行数指标机械拆分。

## 6. 插件一次注册编译审查

### 6.1 发布入口

| 安装单元 | package entry point | 结果 |
|---|---|---|
| 根包核心 | `builtin = scidiscovery.builtin_plugin:PLUGIN` | 通过 |
| 根包通用科学 | `general_science = scidiscovery.general_science_plugin:PLUGIN` | 通过 |
| TCAD | `tcad_artifact = tcad_artifact.plugin:PLUGIN` | 通过 |
| 曲线评价 | `curve_score = curve_score.plugin:PLUGIN` | 通过 |
| InGaAs | `ingaas_fig4 = ingaas_fig4.plugin:PLUGIN` | 通过 |

所有发布包只使用 `scidiscovery.plugins`。`operation_catalog` 四种 scope 是同一个编译结果的视图，未发现按 public/support/internal 各自维护 ID 或实现的第二注册表。

### 6.2 闭包组成

编译目录能从同一 Operation 闭包解析并纳入摘要：

- 输入/输出 Schema 与 validator；
- Agent prompt、codec、guard、projector；
- 原生工具权限、Worker 工具及其所需服务；
- workspace materializer、file policy、finalizer、snapshotter；
- transform executor；
- effect executor、runtime factory 和配置 Schema；
- 审批 provider/reviewer、允许决定指针和固定 renderer projection。

TCAD author 闭包包含 deck 工作区、文件工具和调试工具；reviewer 闭包不包含这些写/调试能力。TCAD effect 的 executor、runtime factory 和 capability 由相同插件定义解析。曲线和 InGaAs 没有私有调用旁路。

“skill”是例外：它尚未作为可物化组件开放，而是将专家合同冻结进 prompt resource；这是显式失败关闭，不是漏加载。

### 6.3 失败关闭、卸载与漂移

已验证：

- 重复插件/Operation/组件 ID、协议不匹配、缺组件、错误 kind、未使用组件；
- 未声明的跨插件依赖/实现、权限扩大、网络/工具/工作区依赖不闭合；
- 损坏资源、无效 UTF-8、配置 symlink/过大/重复分配；
- 冒名 runtime 插件不能满足另一个插件的 executor/service；
- approval provider/reviewer 漂移或消失时拒绝；
- InGaAs 增量安装不改变已有 Operation 摘要。

未验证：

- daemon 运行期间卸载/升级插件且已有 Task、Approval、Execution 活跃时的策略；
- 两 daemon 使用内容不同但路径均合法的运行时配置时，能否在启动阶段立即阻止，而不是在 capability 检查时较晚失败；
- 第三方重新发布旧 `transform_adapters`/`agent_role_packs` 后，部署检查是否主动拒绝。

第一项属于后续生命周期/生产化范围；后两项应在 R5 或部署入口加最小失败关闭检查。

## 7. 实现—测试矩阵

| 子功能 | 主要实现 | 正向测试 | 负向测试 | 本轮判断 |
|---|---|---|---|---|
| 安装态目录 | `operations/catalog.py`、各包 entry point | core/full/ingaas clean wheel 加载及 scope 数量 | broken resource、invalid Unicode、重复/缺组件 | 充分 |
| 三类 executor | `operations/invoke.py` | 已安装 Agent/transform/effect 调用 | 错 executor、错输入数量/Schema/父链 | 充分 |
| TCAD Agent/工具 | TCAD plugin、workspace、debug adapter | author 调试/文件工具、reviewer 审查 | reviewer 越权、未声明工具/服务、capability 不匹配 | 充分，缺真实 solver |
| TCAD runtime | runtime factory、execution control | control adapter/worker service 分模式构造 | 无 task service、冒名插件、配置 symlink/重复 | 充分，缺双 daemon 摘要握手 |
| 曲线变换 | curve plugin、operation transforms | 六类操作、集合输入及结果 | 顺序/身份/coverage/parentage 错误 | 充分 |
| InGaAs 增量插件 | InGaAs plugin | 单增一个操作并成功调用 | 未安装时不可见、已有摘要不漂移 | 充分 |
| Agent 子进程 | `platforms/codex_worker.py`、`platforms/codex.py` | 真实独立子进程、结果封存 | 工具越权、secret/env 泄露、错误退出/超时 | 充分，但主线接入仍属后续 |
| 审批合同 | general plugin、Root approval invoke、ApprovalService | 三种审批 Operation | 隐藏输入、provider 漂移、指针越界、对象族不匹配 | 当前支持族充分；任意插件族受 F1 限制 |
| 固定 UI | `approval_ui/render.py`、`app.py` | 已知 Schema 固定视图 | XSS、未知 Schema 原始下载回退、不可编辑隐藏字段 | 充分，缺真实浏览器 |
| 旧入口关闭 | 发布元数据、legacy transform guard | 迁移能力只从 Operation 调用 | 旧 profile/adapter 调用拒绝 | 发布态充分；生产代码仍待删 |

### 7.1 本轮实际执行

所有命令前均设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

执行结果：

1. `git diff --check`：通过。
2. 121 项聚焦测试：`121 passed in 47.33s`。
3. 全仓串行测试 `pytest -q`：`245 passed in 74.16s`。
4. `sha256sum --check --quiet MANIFEST.sha256`：通过。

聚焦命令覆盖：

```text
tests/operations/test_catalog_installed_entrypoint.py
tests/operations/test_catalog_negative_cases.py
tests/operations/test_operation_invoke_installed.py
tests/operations/test_runtime_plugin_configuration.py
tests/operations/test_tcad_operation_plugin.py
tests/operations/test_curve_score_operation_plugin.py
tests/operations/test_ingaas_operation_plugin.py
tests/operations/test_r4_approval_operation.py
tests/operations/test_r4_execution_approval_identity.py
tests/operations/test_r4_approval_ui_renderer.py
tests/operations/test_codex_task_dispatch.py
tests/operations/test_codex_worker_process.py
tests/artifact_agent/test_platform_configuration.py
```

其中 `tests/operations/conftest.py` 构建 release、插件 wheel 和独立 core/full/ingaas/broken 环境，并在无源码 `PYTHONPATH` 依赖的环境中执行安装态探针。这是本轮 clean-wheel 证据。全仓 `pytest` 是源码工作树回归，二者在结论中没有混用。

## 8. 奥卡姆剃刀审查

### 8.1 值得保留的最小实体

- `OperationSpec`：描述一个可调度行为闭包；没有它就无法统一 Agent、transform、effect。
- `PluginDefinition`：一次安装编译的包级边界；没有第二 registry。
- `CompiledCatalog/CompiledOperation`：启动时冻结和校验闭包，运行时只消费结果。
- `Artifact/Task/Approval/Execution`：分别保护不可变科学输入输出、Worker 生命周期、人工决定、外部副作用，不能互相折叠。
- workspace hooks 与 Worker tool 定义：前者保护文件边界，后者保护任务能力；二者不是同一对象。

这些新增实体都有生产消费者和独立安全约束，不属于纯形式抽象。

### 8.2 高置信简化候选

| 候选 | 当前生产消费者证据 | 必须保护的约束 | 最小改法 |
|---|---|---|---|
| 删除旧 transform entry-point loader | `mcp_daemon.py` 仍加载，Root `artifact_transform` 仍调用；发布集合已经为空 | 仅保留尚未迁移的确切桥接能力，已迁移能力不能双入口 | 迁完最后桥后直接删除 loader/Root 表面/相关测试，不建兼容层 |
| 删除源码角色扫描与 `agent_role_packs` | `platforms/roles.py` 仍扫描目录/entry point；compiled Agent 已拥有 prompt/tool/resource | Agent 上下文只能来自其 Operation 闭包 | 确认无旧调度消费者后删除扫描器；不要复制到新 plugin helper |
| 拆 Root/Task 巨型文件 | Root、daemon、Worker router 和 UI 是现有消费者 | Approval/Execution/Task 仍各只有一个状态权威 | 只提取路由和无状态协作者，依赖注入现有 service，不增表/状态 |
| 拆通用/TCAD/曲线插件声明文件 | 编译器只需最终一个 `PluginDefinition` | 一个包入口、一个插件 ID、一个闭包摘要 | 模块化声明片段，在唯一 `plugin.py` 组装，不新增子注册表 |
| 将审批族推导编译化 | 仅 Root 当前消费这套逻辑 | 决定仍由 ApprovalService；所有输入必须显式绑定 | 使用端口/Schema 关系生成总函数，不引入 provider registry |
| 收缩 `core_context_policies.py` | 旧角色上下文仍有消费者；新 Operation 已携带资源/暴露策略 | 最小可见范围和输入 usage 不能削弱 | 按迁移操作逐项删旧分支，以调用图和负向权限测试为门 |

### 8.3 不应做的“简化”

- 不把 Agent、transform、effect 合并成一个巨型可执行类；它们共享描述，不共享副作用边界。
- 不删除 immutable Artifact、审批或执行生命周期来减少类数；这会破坏来源和外部副作用门禁。
- 不为拆大文件引入 repository/service/factory/interface 四层模板；只有存在独立测试和变化原因时才提取一层。
- 不把 `public/support/internal` 拆成三个注册表；它们必须继续是同一目录投影。
- 不恢复宿主隐式 skill/MCP 继承来追求“少代码”；显式闭包和最小权限是框架核心目标。

## 9. 范围归类

### 9.1 R4 范围内已完成

- TCAD Agent、工作区、文件策略和调试工具进入插件闭包；
- TCAD transform/effect/runtime 进入同一插件和统一调用入口；
- curve/InGaAs 通过 package entry point 增量安装；
- 旧 operation-spec/transform-adapter **发布入口** 删除，迁移能力不能走旧入口；
- 审批合同与固定安全 UI 接入编译目录；
- public/support/internal/all 为单目录投影；
- clean-wheel 安装、正负例和全仓回归通过。

### 9.2 R5 明确遗留债务

- 删除旧 `agent_role_packs`、source role 扫描、transform adapter loader 和旧 Root 创建工具；
- 收缩 `scientific_readiness`、静态 scheduler/context policy；
- 将设备参数/科学 Schema/TCAD 调试等领域分支移出 Root/Task；
- 拆分 Root/Task 等巨型文件并实现计划中的核心代码净减少。

### 9.3 阻塞性缺陷

本轮未发现会导致 R4 安装态主路径越权、双重决定、错误实现被调用或不可变结果被绕过的阻塞性缺陷。121 项聚焦和 245 项全仓测试均无失败。

若团队要在 R5 之前宣称“任意新领域只注册插件、完全不改核心即可接入带审批的完整科研链路”，F1 会立即成为阻塞；当前只能作更窄的 R4 结论。

### 9.4 非阻塞改进/未验证风险

- runtime 配置缺失早期门禁及双 daemon 摘要握手；
- 真实浏览器 UI 验收；
- 真实 TCAD solver、许可证和远程 runner 验收；
- 活动任务期间插件卸载/升级策略；
- skill 的任务本地、内容寻址物化；
- Codex Worker 进程原型在主生产调度链路的最终接入或删除决定。

## 10. 通过条件

R4-A—D 不需要返工后才能开始 R5；“有条件通过”的条件针对下一阶段和对外架构结论：

1. R5 必须删除而非继续包裹旧角色/变换/Root 调用旁路，并用发布态负例证明不能复活第二权威；
2. 将审批生产者族推导改成编译合同可表达的领域无关总函数，或明确冻结当前只支持的审批类型，二者必须选一，不能继续隐式靠 Root 端口名；
3. 优先拆 `tasks.py`、`mcp_root.py`、`mcp_worker.py` 与通用插件声明，且不得新增注册表、数据库状态机或服务权威；
4. 在外部执行生产化前，补运行时绑定缺失预检和控制/Worker 配置内容一致性检查；
5. 文档明确区分“静态提示资源已支持”和“通用 skill 物化尚未支持”；
6. R5 收口时重新测量旧控制层删除量、clean-wheel 安装、权限负例和三种目录视图，不能只以文件搬迁或测试桩数量作为完成标准。

在上述边界下，本轮最终结论为：**有条件通过**。
