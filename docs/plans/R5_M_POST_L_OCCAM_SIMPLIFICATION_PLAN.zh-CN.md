# R5-M：L 后生产代码奥卡姆裁剪计划

日期：2026-09-01

状态：**已完成**；M0—M7.5 均已实现并经阶段独立审查，两位 M7.5 独立终审者均为 PASS、阻断 0

前置状态：R5-L0—L6 已完成并通过两位独立终审者复核

问题来源：`CURRENT_PRODUCTION_CODE_REDUNDANCY_ASSESSMENT.zh-CN.md` 及其逐符号复核

## 1. 计划定位

R5-L 已经建立最小默认运行主干：一个插件入口、一个编译目录、一个预检入口、一个调用入口、一个
`RunService`、一个 Artifact/current 权威，以及 Local/Hardened 两种工作区后端。R5-M 不再重写这条
主干，也不建立第三套运行器。

本轮只做一件事：

> 删除或迁出仍挂在 L 主干上的旧责任、重复合同和无消费者表面，使默认系统更小，同时不削弱
> 多角色文件通信、最小上下文、独立审查、精确人工决定和外部执行恢复。

本计划是已完成的实施记录，不修改 R5-L 的历史通过结论。当前规范事实仍由：

- `docs/ARCHITECTURE.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
- 当前生产代码和安装入口

共同确定。冗余评估是候选来源，不是删除授权。

### 1.1 当前阶段的软隔离决策

2026-09-02 起，当前可信本地原型不再以强文件隔离、逐文件读取授权或逐次读取收据为目标。默认
Local Agent 获得一个由控制层物化的 Run 工作区，并可直接使用 Codex 原生文件与代码能力读取和修改
任务内文件。上下文边界由“只向该 Run 物化哪些输入和文件”表达，正式事实边界由输出封存、Schema、
父链、独立审查、人工决定和副作用授权表达。

该决策明确取消以下当前工作：

- 不为 assignment、Schema、普通输入或 recovery draft 新增 MCP 读取协议；
- 不为普通任务内读取建立 capability、receipt、数据库事实或审计状态机；
- 不补齐 Hardened 的资源列表、文件读取和 TCAD 原生工具支持；
- 不把宿主路径不可见、跨 Run 技术隔离或强沙箱作为 R5-M 完成条件。

仍然保留的硬边界是：Worker 不获得控制身份和写接口；领域 MCP、网络和外部副作用仍按编译
Operation 授权；只有完整校验的封存输出才能成为 Artifact；审查者只接收显式输入；人工审批和外部
执行不能由 Agent 绕过。`SEC-002` 因缺少技术沙箱继续保持 `known_issue`，但不阻断当前可信本地
里程碑。已有 Hardened 代码和 M7.1 PASS 作为历史实现与证据保留，本决策不追溯改写已经完成的审查；
它只移除后续阶段继续扩建和再次验收 Hardened 的要求。

## 2. 奥卡姆裁剪规则

### 2.1 允许的修改类型

每个候选只能属于以下一种：

1. **删除**：没有生产或动态插件消费者，且不保护独立不变量；
2. **折叠**：两个结构表达同一事实，保留一个权威；
3. **归位**：真实能力放回其所有者，例如领域算法回到插件；
4. **可选化**：真实但非默认能力退出普通启动、安装和调度表面；
5. **不修改**：证据不足或删除后需要更复杂的替代物。

禁止以“文件很大”“测试少”“暂时没启用”作为单独删除依据。

### 2.2 每个候选的净复杂度门

实施前后必须比较：

- 生产文件和物理行数；
- 数据库表、运行状态和持久化事实数量；
- Root 公共工具数量；
- `OperationSpec` 必填与可选字段数量；
- 插件入口、注册表和编译投影数量；
- 默认启动导入模块和常驻服务数量；
- 新领域插件的声明与胶水代码量。

若一个“简化”新增了注册表、数据库表、状态、守护进程、兼容适配器、第二预检、第二调用入口或
第二领域专用语言，立即停止该候选。若新增代码不少于被删除代码，实施者必须证明新增部分保护了
原来无法保护的独立不变量，否则回退。

### 2.3 不以兼容层换取表面通过

本轮不承诺旧内部 Python 导入路径、旧测试夹具和未发布数据库辅助表兼容。不得为删除旧类增加别名、
转发器或双写。历史 Artifact、收据、审批与执行事实不得被当前合同自动升级；已有数据库中的废弃表
可以保持惰性存在，不能为删表增加在线迁移状态机。

### 2.4 一候选一回滚边界

每个子候选独立提交、独立消费者账本、独立聚焦回归。失败只回退该候选，不把多个删除混成一次大
提交。每个 M 阶段通过独立审查后才允许进入下一阶段；“有条件通过”只允许修复当前阶段。

## 3. 明确保留的承重部件

本轮不以裁剪为由删除或弱化：

- 不可变、内容绑定的 Artifact、父链、修订和幂等登记；
- 唯一 ResearchInstance、会话绑定和 current 比较交换权威；
- `RunService` 的排队、运行、完成、失败四态及有界恢复；
- 一个 `OperationSpec`、一个 `CompiledCatalog`、一个 preflight 和一个 invoke；
- Worker 无控制身份、显式输入文件、封存输出文件和声明工具；
- 作者与独立审查者分离，修订不得继承旧审查；
- 科学资格与外部执行授权分离；
- 外部执行的提交、领域状态、结果收集和未知提交查回；
- TCAD 工程物化、开发调试、Deck 审查、求解结果鉴证和曲线确定性指标；
- 默认 Local 软隔离、任务目录与正式结果提交边界；Hardened 的既有代码和审查只作历史证据，不再
  约束当前默认路径。

完整性审计也不整体删除：可以删除单事件日志，但 CAS、Envelope、父链和幂等记录的离线校验能力
必须保留或迁到管理命令后再删除旧入口。

## 4. 当前目标架构

```text
唯一插件入口
    ↓ 启动期编译
唯一 CompiledCatalog
    ↓ 同一预检与调用
RunService
    ↓
LocalTrustedBackend（当前默认软隔离）
    ↓
有界角色 Agent / 确定性 Transform / Effect adapter
    ↓
不可变 Artifact + 显式 review/current/approval/execution
```

R5-M 只减少各层内部的重复责任，不增加新层。`public`、`support`、`internal`、`all` 仍是同一目录
的投影，不是四个注册表。Hardened/远程强隔离若将来出现真实消费者，只能作为同一 RunService 下的
可选后端另立计划；它不属于当前目标架构的实现范围。

## 5. M0：冻结基线和候选账本

### 5.1 工作内容

1. 冻结当前生产文件、行数、数据库表、Root 工具、Operation 和插件安装组合；
2. 对每个候选列出生产、动态插件、测试、文档和历史消费者；
3. 记录当前可运行能力矩阵：
   - 默认 Local；
   - 显式 Hardened；
   - 通用科研插件；
   - 曲线插件；
   - TCAD 插件；
   - InGaAs 可选插件；
4. 冻结三个公开集合输出 Agent Operation 的真实拒绝原因；
5. 冻结 TCAD 本地作者—调试—独立审查闭环和外部 Effect 审批负例；
6. 把候选标成删除、折叠、归位、可选化或不修改，不允许“待看代码”进入实施。

### 5.2 基线命令

基线至少包含：

- 生产来源及行数的可复算清单；
- 干净 wheel 的插件入口编译；
- `tests/operations` 非实时集合；
- Artifact、current、Run、审批、Effect、部署和 TCAD 聚焦回归；
- `git diff --check`；
- 33 项约束注册表结构测试。

测试顺序执行或小批执行，不使用无界并行；WSL 峰值内存必须低于 8 GiB。

### 5.3 完成门

- 每个候选有确切符号、消费者类别、不变量、放弃行为、测试和回滚边界；
- 未修改生产代码；
- 独立审查明确通过 M0，只放行 M1。

## 6. M1：删除零消费者和重复日志表面

M1 只处理不改变产品行为的候选，不夹带控制面重构。

### M1-A：删除死类型、死工具和死投影

候选范围：

- 无生产和插件消费者的 `schema/discovery.py`、`schema/decision.py`、
  `schema/pdf_excerpt.py`、`schema/web_evidence.py`；
- 仅在自身模块出现的科研周期状态类型；
- 未被已安装插件注册、且运行后端无处理器的网页证据和通用分析 Worker 工具；
- `RuntimeOperationProjection`、`runtime_operation_projection()` 及仅验证该死投影的测试。

保留 `SchedulerOperationView` 作为调度器唯一公开目录视图；运行时直接消费
`CompiledOperation`，不得创建替代投影。

### M1-B：删除在线清除接口

删除无生产消费者的：

- `ArtifactService.purge_registrations`；
- `SQLiteArtifactRegistry.delete_artifacts`；
- `ApprovalService.delete_requests`；
- `ExecutionService.delete_executions`。

普通运行不得临时拆除只追加触发器。将来如果确有清理需求，只允许离线、显式目标、停机校验的管理
命令；本阶段不预先实现该命令。

### M1-C：删除重复事件，不删除完整性检查

- 删除只表达一次注册事实的 `ArtifactEvent/artifact_events`；
- 删除只写不读的 `approval_events`；
- 保留 Artifact、父链、幂等记录、审批请求、决定表和 HumanDecision Artifact；
- 将 `audit.py` 缩为 CAS、Envelope、父链、幂等性和孤儿检测，或迁到惰性加载的管理命令；
- 只有新建数据库不再创建废弃表；已有数据库额外表不参与运行，不增加在线删表迁移状态。

### M1 验收

- 上述死符号在生产源码和安装 wheel 中零命中；
- 默认目录摘要、现有可运行 Operation 摘要不因无关删除漂移；必要 ABI 变更有显式版本；
- Artifact 内容、父链、幂等、审批精确 subject、防重放和执行事实回归通过；
- 人工制造 CAS 缺失、Envelope 错误和孤儿内容仍能被离线审计发现；
- 新增运行实体、状态、表、Root 工具均为零；
- M1 独立实现审查通过后才进入 M2。

## 7. M2：让公开能力与默认运行能力一致

本阶段不为 Agent 集合输出扩建 `RunService` 状态机。复用现有单一主输出和确定性集合 Transform。

### M2-A：参数证据提取

- 参数提取 Agent 产生一个单一领域数据包；该数据包可以复用既有 `OutputBundle` 文件清单，但不得
  为此增加 Run 状态或第二提交协议；
- 确定性支持 Operation 验证并展开为参数、来源和需求集合；
- Agent 负责来源判断、缺失项和不确定性；Transform 只做格式验证和机械展开；
- 不新增“参数任务状态”或领域专用 Run。

### M2-B：曲线诊断

- 确定性曲线分析和绘图成为 support Transform；
- 诊断 Agent 只消费单一分析报告并输出单一科学诊断；
- 表格、指标和图像作为 Transform 的集合输出登记，不经 Agent 集合提交协议；
- Metric 不得直接生成科学 verdict。

### M2-C：论文图证据

先检查 TCAD 默认闭环是否真实消费该公开 Agent：

- 若不是默认消费者，将整项能力从默认公开视图迁到可选图证据插件；
- 若必须保留，Agent 只输出一个清单包，由确定性验证器校准、验证和展开；
- 不在 `RunService` 增加集合草稿、集合终态或第二提交协议。

### M2 目录规则

- 已安装、当前后端可运行的 Operation 才进入调度器可选择的 `public` 视图；
- 已安装但当前后端不支持的能力只进入诊断视图，并给出同一 preflight 的拒绝原因；
- 不为 Local 强行改写只适用于其他后端的 Operation，但默认安装不得宣传永远不可运行的能力。

### M2 验收

- 当前三项公开 Agent 集合输出不再形成默认 Local 的必然失败路径；
- 目录、preflight、invoke、Run 创建和平台配置使用同一个后端能力结论；
- 参数不确定性、曲线 Metric/诊断所有权和图证据来源负例不退化；
- 真实启动至少一个通用 Agent 和一个 TCAD Agent，工具由子智能体直接调用；
- 无新增 Run 状态、集合提交协议或第二目录；
- M2 每个子项可单独回退，整阶段独立审查通过后进入 M3。

## 8. M3：删除新旧确定性变换双层

### 8.1 删除对象

- TCAD `TCADProjectTransformAdapter` 的 profile 分发和 `_legacy()` 桥；
- 曲线 `CurveScoreTransformAdapter` 的 profile 分发和 `_legacy()` 桥；
- 通用科研 `ScientificStateTransformAdapter` 的旧 profile 包装；
- 无生产消费者的 InGaAs 旧 adapter 类；
- 旧 `TransformOutput` 到新输出映射的第二次包装；
- 仅为旧 adapter 存在的 `supports_transform_profile`、父链协议和兼容测试。

### 8.2 保留方式

- 曲线计算、实验机械展开、TCAD 工程物化、运行鉴证和 InGaAs 评分保留为窄函数；
- 保留一个通用的编译 Transform 调用器，负责调用已注册组件、校验输出合同和登记 Artifact；
- 领域算法不得迁入 Root，Root 不按 profile、Schema、TCAD 或插件名称分支；
- 不用新基类或第二框架替换旧 adapter。

### 8.3 字节等价门

对每项生产 Transform 固定输入，比较修改前后：

- 输出字节和媒体类型；
- 父引用；
- Operation 标识与摘要；
- 集合成员名称和顺序；
- 幂等重放和冲突修订结果。

确需修正旧错误时，必须独立成新候选并明确不追求字节等价，不能混入 adapter 删除。

### 8.4 M3 完成门

- 生产插件不再出现旧 profile adapter 或 `_legacy()`；
- Root 仍只有一个编译 Transform 入口；
- DET-001/DET-002 正反例和 TCAD/曲线/通用重放通过；
- M3 独立审查通过后进入 M4。

## 9. M4：删除科学语义兼容桥

### 9.1 旧知识模型桥

优先删除 `_knowledge_portfolio_view`。不得再由确定性代码补造：

- `status="testable"`；
- `support_level="unassessed"`；
- 合成 rationale；
- 空参数集合。

首选最小方案是让知识更新直接消费当前 `HypothesisProposal`、精确独立审查和诊断；若全局知识晋级
没有真实消费者，则保留诊断/结论 Artifact 和显式 current，删除旧 reducer，而不是建设第三个科学图。

### 9.2 实验意图与执行计划只做所有权审计

M4 不预设必须合并两个模型。先建立逐字段所有权表：

- Agent 科学选择：目标、对照、机制变量、预测、证伪条件；
- 确定性派生：案例展开、标识、组合、引用、单位和资源上限检查；
- 领域插件机械展开：TCAD case/project 物化。

只有同时满足以下条件才允许合并重复字段：

1. 不要求 Agent 手工生成机械展开字段；
2. 不让 Transform 选择科学目标、优先级或结论；
3. 合并后模型、转换和测试净减少；
4. 现有实验设计、对照辨识和可重放结果不退化。

否则保留意图→确定性物化→执行计划边界，只抽取共享值类型或删除真正重复字段。M4 可以合法地以
“知识桥已删除、实验模型不修改”结束。

### 9.3 M4 完成门

- 控制/Transform 不再合成科学支持状态；
- 未知、不确定性和冲突不被默认值覆盖；
- 实验机械关系继续确定性生成；
- 不出现第三个知识状态、科学图或固定科研阶段；
- M4 独立审查通过后进入 M5。

## 10. M5：收敛插件所有权和默认产品面

本节记录 M5 已经实施和通过时的历史要求。涉及显式文件工具与 Hardened 的条目由 1.1 部分取代，
不再进入剩余阶段的完成门；其余插件所有权结论继续有效。

### M5-A：公共组件只注册一次

- builtin 统一拥有通用文件创建、补丁、移动和删除工具的组件注册；
- 每个 Operation 仍必须显式引用所需工具，注册公共不等于自动授权；
- 通用科研插件拥有 PDF 等通用科研读取能力；
- general_science 公开领域无关 Schema 资源；
- TCAD、曲线插件通过公开 `ComponentRef(plugin_id=...)` 引用，不从控制包私有路径重新注册；
- 仍只有 `scidiscovery.plugins` 一个入口和一个编译事务。

### M5-B：领域插件按真实依赖收窄

- 先测量 TCAD 对曲线插件的实际引用集合；
- 曲线合同、归一化、Metric 和同领域确定性实现由一个曲线基础发行包提供；
- 论文图数字化、图证据校准和图证据 Agent 由可选插件入口统一激活，未安装该入口时目录中不存在
  这些 Operation；
- “可选”在本轮指注册、调度和默认导入可选，不等同于每个实现文件都物理拆入另一 wheel；只有物理
  拆分能减少运行依赖或权限面且新增胶水明显小于迁出代码时才实施。

### M5-C：TCAD 默认只加载一个执行产品

- 保留当前本地闭环实际使用的一套 TCAD adapter；
- SSH、Python 3.6 runner、套接字守护等其他真实 transport 只通过显式管理命令或运行配置启用，
  普通启动不注册、不实例化、不导入；本轮不为同一 TCAD 领域的少量标准库实现强制拆分 wheel；
- 调试是同一 TCAD adapter 的开发模式，不复制 prepare/submit/status/cancel/collect 生命周期；
- 工程资源限制和 JobSpec 资源限制共享一份领域合同，边界只做显式机械转换。

### M5-D：管理和加固能力退出普通启动

以下是 M5 已完成时的历史验收范围；其 PASS 继续有效。根据 1.1 的后续决策，R5-M 剩余阶段不再
扩建或重复验收 Hardened。

- Hardened 源码和测试保留，但默认 Local 启动不实例化、不导入其 MCP 和文件代理；
- 只有显式选择 Hardened 时才加载相应模块；
- `portable_bundle` 迁到惰性管理命令，普通 `scid` 启动不加载；
- 可选化不得复制目录、运行权威、部署事务或 Operation 声明。

### M5 插件验收

- 核心发行固定包含 `builtin + general_science` 两个入口；核心发行加 curve、TCAD、可选论文图、盲领域
  插件及其组合均能从干净 wheel 编译；`builtin` 可在声明级独立编译，但不伪称存在单独安装状态；
- 缺少可选插件时核心和历史 Artifact 可读，目录中不出现其可调度能力；
- 一个盲小领域插件只需一个入口、少量组件和 Operation 声明，不修改核心、Root、UI、调度器和部署；
- TCAD 本地作者—调试—审查闭环仍通过；
- Hardened 的至少一个纯 MCP Operation 曾按需运行，形成 M7.1 历史证据；`SEC-002` 仍不得被改写成
  已解决；
- M5 独立审查通过后进入 M6。

## 11. M6：折叠重复治理合同

这是风险最高的阶段，必须在前述行为和插件边界稳定后实施。

### M6-A：实例和会话不再伪装成科学审批

- 保留 ResearchInstance、会话到实例的显式绑定、语义名称修订和 current CAS；
- 删除“创建实例提案→审批对象→应用决定”和“选择候选→审批对象→应用决定”的专用状态机；
- loopback UI 直接执行显式创建或选择命令，绑定事实本身就是权威，不增加决定收据表；
- 调度 Agent、Worker 和聊天文本仍无权创建、选择或切换实例；
- 科学资格审批和外部执行授权继续走独立 ApprovalService。

CLI 只能作为显式管理员命令，不得成为交互调度器绕过 loopback UI 的后门。

### M6-B：端口资格合同收敛

把同一 cohort 的四组重复字段从每个输入端口移到 Operation 的一个不可变准入值中，表达：

- 精确 subject ports；
- cohort 标识；
- 审批种类；
- 接受决定；
- 允许的提供者 Operation。

优先复用现有 `ReviewSpec/ApprovalContract` 能表达的结构；只有无法无歧义表达多组输入资格时才增加
一个值对象。禁止增加注册表、数据库表或运行状态。编译器和 Root 必须消费同一编译结果。

### M6-C：删除生产者下游拓扑预测

先生成当前所有生产 Operation 的真实输入输出使用矩阵，再移除
`OutputPortSpec.allowed_input_usages`。替代规则只能由以下已有事实组成：

1. Schema、媒体类型、基数和 current；
2. 下游输入端口声明的用途；
3. 编译 reviewer edge；
4. 精确修订 base 与 change request；
5. 按 Operation 启用的资格准入。

未审查输出可以交给其精确 reviewer，但不能绕过 reviewer 直接作为需要审查的 claim evidence；修订
不得借用旧对象审查。不得用新的全局用途图替换 `allowed_input_usages`。

### M6-D：Effect 自动建立审批请求

- `operation_invoke` 创建 ExecutionRequest 后，按同一编译 `ApprovalContract` 自动创建精确审批请求；
- 返回 loopback UI 地址；
- 不自动写决定，不自动调用 `execution_start`；
- 查询不推进审批或执行状态；
- 合同漂移、插件卸载、错误 revision 和错误 subjects 继续失败关闭；
- 删除调度器额外调用 `execution_approval_request_create` 的公共步骤及重复合同重建代码。

### M6 完成门

- Artifact、Run、current、Approval、Execution 各只有一个权威；
- 普通探索没有 cohort/approval/execution 状态成本；
- 实例创建/选择仍只能由精确显式用户入口完成；
- 资格与执行授权保持两个决定；
- readiness 与 invoke 对同一绑定结论一致；
- Root 工具、数据库表和 Operation 字段净减少；
- M6 分 A—D 逐项独立回滚，整阶段独立审查通过后进入 M7。

## 12. M7：最终回归和默认面验收

### 12.1 安装与运行矩阵

必须覆盖：

- 干净核心发行 wheel，其固定入口精确为 `builtin + general_science`；
- 核心发行 + curve 基础能力；
- 核心发行 + TCAD；
- 完整本地 TCAD；
- 可选图证据入口的安装存在/缺失，以及远程 transport、便携管理命令的显式启用/默认不加载组合；
- 最终物理报告必须分别列出“未安装”“未注册”“未导入”，不得互相替代。

M7.1 已完成的 Hardened 安装/运行结果保留为历史证据，但后续最终矩阵不再要求重复运行、扩展或修复
Hardened。默认矩阵只验证 Local 软隔离路径；可选能力只需证明不进入默认启动和目录。

### 12.2 真实 Agent 纵向回归

真实拉起、由子智能体自己调用工具，不由父进程桥接：

1. 通用作者→独立 reviewer；
2. TCAD 作者→领域调试→独立 Deck reviewer；
3. 修订对象→精确新审查，证明旧审查不继承；
4. 外部 Effect→loopback UI 决定→显式 start→状态同步/收集；
5. 一个失败或超时 Run 的有界恢复。

聊天返回只作信号，科学结果只从完成 Run 的封存输出读取。

M7.2 的实时测试可使用用户明确授权的独立 `codex exec` 承载一个已经排队的编译 Operation，以避免
每次安装测试角色/MCP 后重启交互父会话。该启动器必须只启用精确 Worker MCP，保留不含科学内容和
Run/Artifact 标识的原子启动收据，并由 Root 的完成态、工具活动和封存 Artifact 交叉验证；它不是
Root 默认调度入口、第二 Run 状态机或生产级隔离承诺。

所有 Local Agent 默认可以直接读取 assignment、输出 Schema、显式 inputs、可选 recovery draft 和
领域工作文件，并在任务工作区内使用 Codex 原生文件与代码能力。不再以 `native_shell="none"` 同时
关闭读取、写入和执行，也不新增 `worker_read_*`、MCP resources 或逐次文件读取收据。OperationSpec
继续声明领域 MCP、网络和外部副作用；普通任务内文件能力是 Local 后端基线，不要求每个插件重复
注册。

第 5 项的返工完成门改为：

1. 恢复草稿含一个不能由原始输入或领域工具结果推出的测试标记，新 Agent 的合格输出必须按测试
   合同保留或变换该标记，以功能结果证明草稿确实被使用；
2. 盲领域测试 Schema 含一个不出现在提示、输入和恢复草稿中的必填常量；恢复 Agent 首次提交即带回
   该值，以功能结果证明其读过 Schema，而不是靠 MCP 资源接口或拒绝诊断反推格式；该字段只属于
   测试夹具，不进入生产科学 Schema；
3. 最终结果仍调用声明的领域工具、通过完整校验并作为新 Run 输出登记，草稿本身不成为 Artifact；
4. 现有 `max_attempts` 在同一恢复链上执行一个简单总次数硬上限，超限的 preflight/invoke 均零 Run
   拒绝；不增加 attempt 实体、恢复状态机或后台守护进程；
5. 聚焦回归和一轮独立审查通过。既有失败终审保持历史 FAIL，不自动升级。

### 12.3 科学与控制边界负例

- 不可信论文/网页不能扩大领域工具、网络、审批或外部执行权限；
- 缺失参数不被控制层补值；
- Metric 不生成诊断或结论；
- stale current、混合 cohort、错误 reviewer、旧 revision 审查全部拒绝；
- 提交未知不盲目重发；
- 输出封存继续拒绝逃逸结果路径、符号链接、秘密、机器路径和未声明二进制；本轮不声称阻止可信
  Local Agent 读取宿主可见文件；
- Local 的 `SEC-002` 仍明确标记为已知问题，但不为关闭它新增强隔离协议。

### 12.4 物理成果报告

最终报告分别给出，禁止混报：

- 实际删除的生产文件和行数；
- 退出默认安装/导入面的可选代码；
- 数据库表、Root 工具、Operation 字段和运行状态变化；
- 插件接入劳动；
- 被有意放弃的内部兼容行为；
- 33 项约束的当前证据与未关闭项。

行数不是通过条件。通过条件是默认路径可解释、权威唯一、真实闭环可运行，且没有用新包装层换掉旧
包装层。

### 12.5 最终门

- 全量测试、干净安装、部署回滚、`git diff --check` 通过；
- 两位未参与实现的独立审查者分别复核正确性、复杂度、33 项约束和通用科研 Agent 目标；
- 两份结论均明确通过后，R5-M 才完成。

强文件隔离、Hardened 功能完备或 `SEC-002` 晋级为 conformant 不是本轮最终门。终审只需确认这些
限制被如实记录，且软隔离没有削弱 Artifact、审查、审批和 Effect 的硬边界。

## 13. 33 项约束阶段门

33 项约束是验收矩阵，不转换为 33 个服务、状态或检查器。

| 约束组 | 本轮不可退化要求 | 主要阶段 |
|---|---|---|
| AUTH-001、AUTH-002、AUTH-003 | 控制面事实唯一；Worker 无控制身份；能力只来自同一编译 Operation | 全阶段，重点 M3/M6 |
| IMM-001、IMM-002 | Artifact/收据不可变；变化建 revision 且旧审查不继承 | M1/M2/M7 |
| LIN-001、LIN-002 | 原始目标贯穿；current 与 cohort 递归完整且不可拼接 | M4/M6/M7 |
| EVD-001、EVD-002 | 来源先冻结、精确定位；冲突和来源独立性不被控制层抹平 | M2/M4/M7 |
| UNC-001、UNC-002 | 未知和范围显式；机制与 nuisance 有可辨识对照 | M2/M4/M7 |
| TOP-001、TOP-002 | 从当前矛盾选 Operation；readiness 与 invoke 同源 | M2/M6/M7 |
| ROLE-001、ROLE-002 | Worker 拥有科学内容；全生命周期消费同一合同 | M2—M4/M7 |
| DET-001、DET-002 | 机械关系可重放；Transform 不替代科学选择 | M2—M4 |
| HIL-001、HIL-002 | 人工决定只来自精确 UI；资格与执行授权分离 | M6/M7 |
| CQRS-001、CQRS-002 | 查询纯读；状态只由显式幂等命令推进 | M1/M6/M7 |
| EFF-001、EFF-002 | 提交/领域状态/收集分离；未知提交只权威查回 | M5/M6/M7 |
| PLG-001、PLG-002 | 核心无领域分支；插件独立组合且统一回滚 | M3/M5/M7 |
| SEC-001、SEC-002 | 来源不能扩大领域工具/副作用；Local 软隔离限制诚实记录，不以强隔离阻断当前原型 | M2/M5/M7 |
| RES-001、RES-002 | 大对象和上下文有界；Run 恢复、并发和测试资源有界 | 全阶段 |
| UI-001、UI-002 | 审批页面保留科学层次、单位、条件、风险和精确结果 | M6/M7 |
| MIG-001、MIG-002 | 旧资格不升级；干净安装、失败回滚和发布入口实测 | M1/M5/M7 |

每阶段只更新该阶段新增的证据，不因测试通过自动把 `pending_review` 晋级为 `conformant`；
`SEC-002 known_issue` 在没有技术隔离证据前保持不变。

## 14. 自动停止条件

出现以下任一情况，停止当前候选并回退，不通过局部补丁掩盖：

- 新增第二 Registry、current、Run、preflight、invoke 或准入体系；
- 用新 adapter、兼容别名或双写长期包住旧实现；
- 核心按 TCAD、曲线、角色、Schema、profile 或插件名分支；
- 为一个失败测试增加领域标签、隐藏状态或特殊放行；
- Agent 被要求手工完成可确定重放的机械展开；
- Transform、Metric 或控制层补写科学判断；
- 普通探索被迫创建资格、审批或外部执行状态；
- 可选化产生第二部署事务或第二目录；
- 为默认 Local 增加逐文件读取工具、读取收据、文件代理、租约或第二权限状态机；
- 删除完整性、安全或恢复规则后没有等价且更小的保护；
- 测试峰值内存超过 8 GiB 或依赖无界并行；
- 独立审查没有明确通过。

## 15. R5-M 完成定义

R5-M 只有在下列条件同时满足时才完成：

1. 默认路径仍是“编译 Operation→建立 Run 目录→启动角色→校验文件→登记 Artifact→按需审查”；
2. 无消费者表面、旧 Transform 双层和科学语义兼容桥已退出生产路径；
3. 调度器可选择的 public Operation 与当前后端实际能力一致；
4. 插件公共资源只注册一次，领域插件不引用控制包私有实现；
5. current、独立审查、人工决定和外部执行恢复不退化；
6. TCAD 本地真实闭环和至少一个非 TCAD 真实闭环通过；
7. Local Agent 能直接使用任务输入、Schema 和恢复草稿；可选强隔离能力缺失不污染默认目录和启动；
8. 33 项矩阵如实更新，未关闭问题不被测试数量掩盖；
9. 没有新增未经消费者证明的实体；
10. 两位独立终审者均明确通过。

R5-M 完成不代表多租户或不可信 Worker 安全资格，也不代表 `SEC-002` 已关闭。

## 16. 当前进度

2026-09-01：完成计划初稿及 M0 基线与候选账本，证据见
`evidence/R5_M0_BASELINE_AND_CANDIDATE_LEDGER.zh-CN.md`。当前生产树为 146 个 Python 文件、50,023
行，摘要为 `fc97aa3277e0e9a5144049f95e806b1eb5ad95cd7156069ebcc68162cded6c41`；完整目录 46 个
Operation，默认 Local 的 22 个公开 Agent 中 19 个可运行、3 个因集合输出失败关闭；串行全量回归
`200 passed in 79.98s`。独立审查复算关键数字及 19 个候选后结论为 PASS，报告见
`reviews/R5_M0_BASELINE_AND_CANDIDATE_LEDGER_INDEPENDENT_REVIEW.zh-CN.md`，仅放行 M1。M1 必须先
为 audit 增加损坏负例并收窄事件依赖，再删除事件；同时删除测试 entry-point 夹具对
`RUN_ANALYSIS_TOOL` 的无效导入。M2—M7 未放行。

2026-09-01：完成 M2-01 参数证据提取最小改造，证据见
`evidence/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_EVIDENCE.zh-CN.md`。参数 Agent 由四项集合提交改为
一个 `ParameterEvidencePackage`，新增一个 support Transform 做确定性展开；默认 Local 可运行公开
Agent 从 19/22 变为 20/22，全量回归 `213 passed`。当前等待全新独立审查，审查通过前不进入
M2-02，也不把 M2 或 R5-M 标为完成。

2026-09-01：M2-01 首轮独立审查结论 FAIL，报告见
`reviews/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`。审查复现了“包等审查、
审查等展开”的拓扑闭环，以及资格投影仍解释旧 Task 来源/父链、提交边界未绑定 Run 来源别名三项
阻断。返工将审查边移到确定性展开主对象，使通用 Transform producer family 投影同一已编译 review
元数据，并令 TCAD 投影只消费 Run v1 的 `run_input` 与精确父链；新增真实提取→展开→覆盖→审计→
资格纵向正例及来源、族、verdict、revision 负例。返工后全量回归 `215 passed`，当前仍等待全新独立
复审，M2-02 未放行。

2026-09-01：M2-01 返工后全新独立复审 PASS，报告见
`reviews/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REREVIEW.zh-CN.md`。复审独立跑通真实参数
提取 Run→展开→覆盖→审计→拆分→待人工资格请求，并以领域中性插件确认 Transform review 投影是
通用合同补全；来源、producer family、非通过审计、别名和 revision 负例均失败关闭。M2-01 完成，
当前仅放行 M2-02；M2 整阶段和 R5-M 仍未完成。

2026-09-01：完成 M2-02 曲线分析与诊断边界候选，证据见
`evidence/R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_EVIDENCE.zh-CN.md`。新增一个 support
Transform 复用既有确定性评分、残差定位和绘图，输出一个可复算分析包及 PNG 集合；公开曲线诊断
Agent 缩为一个分析包输入和一个 `LayeredDiagnosisReport` 输出，删除专用曲线分析 Worker 工具和
双层诊断包装。默认 Local 可运行公开 Agent 从 20/22 变为 21/22，插件净删 1 个生产文件、46 行，
核心包、Run 状态、Root 工具和数据库事实不增长，全量回归 `219 passed`。当前等待未参与实现者独立
审查；审查通过前不进入 M2-03，也不把 M2 或 R5-M 标为完成。

2026-09-01：M2-02 独立审查 PASS，报告见
`reviews/R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`。审查独立运行
聚焦 `39 passed`、全量 `219 passed`，并从真实 Root 入口确认污染 PNG 在任何输出绑定前失败、双图
顺序与包内摘要逐项一致、通用 layered diagnosis 可完成知识更新登记。审查发现的插件 README 旧工具
措辞和架构 validator 过宽表述已在放行后按当前事实修正。M2-02 完成，当前仅放行 M2-03；M2 整阶段
和 R5-M 仍未完成。

2026-09-01：完成 M2-03 候选实现，证据见
`evidence/R5_M2_03_OPTIONAL_FIGURE_PLUGIN_IMPLEMENTATION_EVIDENCE.zh-CN.md`。消费者账本确认论文图提取与
审查不是 TCAD 默认闭环的真实依赖，故从默认 `curve_score` 注册中移出，改由一个 60 行、单入口的
可选 `curve_figure_evidence` 插件声明并复用原确定性实现。默认 TCAD 的 20 个公开 Agent 现全部可在
Local 运行；不支持集合提交的可选提取 Agent 仅出现在 `all` 诊断视图。未新增 Run 状态、Root 工具、
数据库实体或集合提交协议，全量回归 `222 passed`。当前等待未参与实现者独立审查；M2 整阶段和
R5-M 仍未完成，M3 未放行。

2026-09-01：M2-03 独立审查 PASS，报告见
`reviews/R5_M2_03_OPTIONAL_FIGURE_PLUGIN_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`。审查独立复算默认/
可选四种目录、消费者端口、干净 wheel 所有权、安装工具、Root/preflight/Run/Codex 同源后端能力和
33 项结构，并完成串行全量 `222 passed in 77.23s`。M2 三个子项至此全部通过，默认 TCAD 的 20 个
公开 Agent 均可在 Local 运行；当前仅放行 M3，不宣称 R5-M 完成，M4 及以后未放行。

2026-09-01：完成 M3 候选实现，证据见
`evidence/R5_M3_TRANSFORM_ADAPTER_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`。删除通用、曲线、TCAD 和
InGaAs 的旧 profile adapter、领域 `TransformOutput` 二次包装及 curve/TCAD `_legacy()` 桥，保留
一个 `execute_compiled_transform` 和插件内窄函数。M2 四种目录组合的 Operation 数量与摘要完全不变，
生产 Python 从 49,018 行降到 48,397 行，全量回归 `225 passed`。首轮独立审查见
`reviews/R5_M3_TRANSFORM_ADAPTER_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`，结论为 FAIL：结构删除本身通过，
但缺少覆盖全部 22 个生产 Transform 的 M2/M3 可执行对照。现已从变更事件精确恢复并在
`../../archive/r5-m2-transform-oracle/` 封存 M2 生产源码。返工新增真实 Root 双进程等价门：同一冻结
语料在精确 M2 与当前 M3 中各执行 22 个生产 Transform，比较完整输出字节、媒体和 Schema、父引用
顺序、Operation 身份、幂等重放、冲突拒绝与修订；9 个父链 guard 均有真实 preflight 正负例。去除
仅用于证明源码版本不同的 `source` 字段后，两份 390,330 字节行为清单完全相同，规范摘要均为
`eb9236dd90914af27201884f37d2e46053eee5d630a0c1b4a436a24ac070d258`。自动化测试
`test_m3_transform_equivalence.py` 已通过，当前等待新的未参与实现者复审；M4 仍未放行。

最终版返工后的完整串行回归为 `226 passed in 126.33s`。

2026-09-01：M3 返工独立复审 PASS，报告见
`reviews/R5_M3_TRANSFORM_ADAPTER_REMOVAL_INDEPENDENT_REREVIEW.zh-CN.md`。复审独立验证精确 M2 oracle、
115/115 生产模块来源、22 个 Transform 的完整双进程行为清单、9 个 guard 正负例与 SchedulerBinding
修订语义；专项 `1 passed`、相关结构与 33 项聚焦 `32 passed`。M3 完成，当前仅放行 M4；R5-M 仍未
完成，M5 及以后未放行。

2026-09-01：完成 M4 候选实现，证据见
`evidence/R5_M4_SCIENTIFIC_SEMANTIC_BRIDGE_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`。消费者账本确认两个
知识更新 Operation 只形成可选自循环，没有调度、Agent、UI、执行或领域消费者；因此删除旧 reducer、
两个专用状态 Schema、七个组件和确定性默认科学晋级桥，不建设替代科学图。实验意图与执行计划经
逐字段所有权审计后保持“Worker 科学判断→确定性机械展开→领域插件工程物化”的边界。生产树相对
M3 减少 2 个文件、2 个 Transform、7 个组件和 969 行，Root 工具、Run 状态、数据库事实均不增加；
保留的 20 个 Transform 与精确 M2 oracle 等价，9 个 guard 继续执行正负例。聚焦回归 `27 passed`；
完整串行回归 `227 passed`，静态检查通过。当前等待新的未参与实现者独立审查，M5 尚未放行。

2026-09-01：M4 独立审查 PASS，报告见
`reviews/R5_M4_SCIENTIFIC_SEMANTIC_BRIDGE_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`。审查者从冻结 M2 oracle
独立复核消费者和删改边界，确认两个 reducer 只有自循环、无真实消费者；诊断、ValidationReport、
不可变 Artifact/current、实验物化到 TCAD 工程链均保留。其串行聚焦回归 `27 passed`，峰值
105,388 KiB；保留 20 个 Transform 的双进程等价和 9 个 guard 正负例成立。M4 完成，当前仅放行
M5；M6 及以后未放行，R5-M 仍未完成。

2026-09-01：完成 M5 实现候选，证据见
`evidence/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_IMPLEMENTATION_EVIDENCE.zh-CN.md`。builtin 成为七个
通用文件工具的唯一提供者，general_science 成为通用科研 Schema/codec 的唯一提供者；默认五插件
组件从 209 收敛到 186，Operation 从 44 减到 43。论文图提取、独立审查和 bundle 转换现在由同一个
可选插件完整注册，显式安装后恢复为 46 个 Operation。TCAD 只惰性导入所选 socket 或 command
适配器，Hardened、portable、SSH/守护/旧 runner 不进入普通启动。完整 Schema 标识无重复，工具仍由
各 Operation 显式授权，未新增注册表、Root 工具、Run 状态或数据库事实。候选已通过聚焦、扩展与
一次完整串行回归，现等待未参与实现者独立审查；M6 未放行。

2026-09-01：M5 首轮独立审查 FAIL，报告见
`reviews/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_INDEPENDENT_REVIEW.zh-CN.md`。其余所有权、工具权限、
惰性加载、盲插件和 Hardened 边界均通过，但真实 Root 证明论文图 bundle 未消费被审 intake/audit，
可在没有独立审查时通过 preflight，故三 Operation 只是共置而非纵向闭合。返工复用既有 ReviewSpec、
exact reviewer-output admission 和 parentage guard：bundle 显式增加 `scientific_intake`、
`evidence_audit`，guard 要求 audit 覆盖 exact intake/manifest/report/全部 table。真实 Local audit Run
正例及缺审查、未受信审查、旧修订、混合 family 四类负例通过；M2/M5 oracle 显式确认转换内容不变、
父链从三类扩为五类。返工聚焦 `31 passed`，全量 `234 passed`，当前等待全新独立复审；M6 未放行。

2026-09-01：M5 返工后全新独立复审 PASS，报告见
`reviews/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_INDEPENDENT_REREVIEW.zh-CN.md`。复审独立确认真实
Local audit Run 的 Root 正例及缺 audit、未受信 audit、旧 revision、混合 family 四类负例；Root
仍复用通用 exact reviewer-output admission，Transform 不解释科学 verdict，M3 其余 19 个
Transform 的严格等价范围未缩减。B1、M3 oracle 和其余防退化三组共 `31 passed`，无 swap。M5
完成，当前仅放行 M6；R5-M 未完成，`SEC-002` 仍为 `known_issue`。

2026-09-01：M6-A 删除实例创建/会话选择的两套伪审批状态机和三张 fresh-DB 表，保留
ResearchInstance、唯一 session binding、语义 revision 与 scientific current CAS。未绑定
`instance_current` 现为纯读并返回短期 AES-GCM 本地管理 capability；loopback UI 用单事务直接创建或
选择并绑定，不产生 Approval/Decision/提案 Artifact。两轮独立审查先后发现 capability 可解码、退役
审批仍可决定、LIMIT-before-filter 和 OFFSET 被过期状态扰动四类问题；最终以 AEAD、退役 kind 只读、
稳定 keyset 分页和状态复核关闭，精确负例均进入回归。实现证据见
`evidence/R5_M6A_DIRECT_INSTANCE_MANAGEMENT_IMPLEMENTATION_EVIDENCE.zh-CN.md`，独立复审见
`reviews/R5_M6A_DIRECT_INSTANCE_MANAGEMENT_INDEPENDENT_REREVIEW.zh-CN.md`；结论 PASS，仅放行 M6-B。

2026-09-01：M6-B 把端口上的四组重复资格字段收敛为 Operation 级 `InputAdmissionSpec`，ABI 升为
10。首次独立审查以真实漂移探针发现 experiment materialize 的 `allowed_port_sets` 和 TCAD
`_PARAMETER_COHORT_PORTS` 仍是 Scheduler 不可见的第二成员权威，结论 FAIL。返工将 all-or-none
检查收敛到通用 `preflight_operation` 且先于 guard，Root 只保留资格查询；materialize 公开四成员
合同，并删除两个 guard 隐藏集合。返工聚焦 `59 passed`、跨层/oracle/约束集 `43 passed`，当前等待
独立复审；M6-C/M6-D/M7 未放行。证据见
`evidence/R5_M6B_OPERATION_INPUT_ADMISSION_IMPLEMENTATION_EVIDENCE.zh-CN.md`，首次审查见
`reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REVIEW.zh-CN.md`。

2026-09-01：M6-B 全新独立复审 PASS。复审以 bomb guard 证明 materialize、revise、TCAD 的部分组
都先由中央 `member_ports` 拒绝；两种 materialize 形状、完整错误父链、真实 TCAD pass/exception、
subject 子集、普通无 admission 零审批调用均通过。复审报告见
`reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REREVIEW.zh-CN.md`。M6-B 完成，当前仅放行
M6-C；M6-D/M7 未放行。

2026-09-02：M6-C 删除 `OutputPortSpec.allowed_input_usages` 及全部生产者未来用途清单，没有建立
替代用途图。Root 只按精确 producer id/version/digest/output port、编译 reviewer edge、下游输入
usage、direct revision/change request 和 Operation 级准入工作；consumer-only 新用途不改变 producer
摘要，缺审查/旧 revision 继续拒绝，explore/internal 输出在 Agent/Transform 两条路径均不可 claim。
ABI 升为 11，目录编译器保持唯一并缩至 734 行，完整串行回归及独立复跑均为 `255 passed`。实施
证据见 `evidence/R5_M6C_PRODUCER_TOPOLOGY_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`，独立审查见
`reviews/R5_M6C_PRODUCER_TOPOLOGY_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`；结论 PASS，仅放行 M6-D，
M7 未放行。

2026-09-02：M6-D 将 Effect 的精确执行审批收回 `operation_invoke`，删除公开
`execution_approval_request_create`，Root 工具 27→26；调用返回 request-specific 回环 URL，但不代替
用户决定或自动 start/sync。首次独立审查发现随机 approval id 在提交/绑定故障窗口产生双请求，以及
Effect subject 顺序的编译合同与授权端不一致，结论 FAIL。返工直接以不可变 `execution_id` 派生唯一
approval id/幂等键，并在目录编译期固定 request→payload subject tuple；连续五次故障仍只有一个可
决定/可授权请求，反向合同在零 Execution/Approval 写入前拒绝。实现证据见
`evidence/R5_M6D_EFFECT_AUTO_APPROVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`，首次审查与全新复审分别见
`reviews/R5_M6D_EFFECT_AUTO_APPROVAL_INDEPENDENT_REVIEW.zh-CN.md`、
`reviews/R5_M6D_EFFECT_AUTO_APPROVAL_INDEPENDENT_REREVIEW.zh-CN.md`；复审 PASS，完整回归
`257 passed`，仅放行 M6 整体回归与独立终审，M7 未放行。

2026-09-02：M6 首次整体终审 FAIL，报告见
`reviews/R5_M6_OVERALL_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。终审发现 Execution 创建提交/语义绑定窗口
仍可按相同调用累积随机孤儿，以及 Approval/Execution 的 status/list 和页面 GET 仍包含过期落库、
令牌轮换或结果发布。返工以完整调用指纹派生稳定 Execution 身份，把审批过期改为只读投影、token
续期改为 loopback+同源+CSRF 的显式 POST，并把执行结果 binding 移入 `execution_sync`/
`execution_outputs` 显式命令；未增加表、Root 工具、Operation 字段或恢复状态机。三次 Execution
binding 故障保持单对象，查询前后数据库摘要不变；组合 `59 passed`、跨边界 `116 passed`、完整
`260 passed`。返工证据已追加到 `evidence/R5_M6_OVERALL_CLOSURE_EVIDENCE.zh-CN.md`，当前等待全新
独立复审；M7 仍未放行。

2026-09-02：M6 整体第一次返工的全新独立复审仍为 FAIL，报告见
`reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW.zh-CN.md`。首次 B1/B2 已转绿，但新 B3 证明 request
Artifact 提交后、Execution 行插入前中断会因动态 `created_at` 与稳定幂等键冲突而永久不可恢复。
第二次返工为 request Artifact 派生稳定 id，只按该 id 取回并完整验证冻结请求，再走原 Artifact
幂等记录后补建同一 Execution；不扫描随机孤儿，不新增表、Root 工具、后台状态机或第二 registry。
连续三次 request-commit 故障保持 `0 Execution/1 request/0 Approval/0 submit`，第四次恢复为
`1/1/1/0`。精确 `19 passed`、组合 `60 passed`、跨边界 `116 passed`、完整 `261 passed`；证据已
追加到整体实施记录，当前等待第二名全新独立复审，M7 仍未放行。

2026-09-02：M6 第二次返工的独立复审仍为 FAIL，报告见
`reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND2.zh-CN.md`。B3、首次 B1/B2、并发和全部字段/元数据
负例均通过，但 B4 证明已有 Execution 行的恢复分支未重放原 Artifact idempotency record；删除或损坏
该记录后仍会建立 binding/Approval。第三次返工让 existing-row 和 no-row 分支消费同一个稳定
Artifact registration/key 重放，registry 缺记录、错 hash/bytes/registration 均在 binding 前失败；
未增加任何状态或公共接口。新增两个精确负例通过，精确 `21 passed`、组合 `62 passed`、跨边界
`116 passed`、完整 `263 passed`；等待第三名全新独立复审，M7 仍未放行。

2026-09-02：M6 第三次返工由第三名全新独立审查者复验 PASS，报告见
`reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND3.zh-CN.md`。两个跨库窗口、请求/Artifact/幂等记录
负例、随机 orphan、并发、全库查询纯读与结构门均独立通过；精确 `21 passed`、组合 `62 passed`、
跨边界 `116 passed`、完整 `263 passed`。阻断 0、非阻断 0；三份历史 FAIL 保留。M6 完成，当前
仅放行 M7，不宣称 M7 或 R5-M 完成。

2026-09-02：M7.1 安装与运行矩阵候选完成。干净 wheel/插件组合 `18 passed`，Local、Hardened、
TCAD 与运行插件 `29 passed`，部署/回滚/远程管理 `33 passed`，源码组合、盲领域插件和已安装 Effect
`4 passed`；便携管理命令惰性表面与 `git diff --check` 通过。核心发行包有且只有 `builtin` 与领域
无关 `general_science` 两个入口，不为字面拆分增加第二部署胶水。证据见
`evidence/R5_M7_1_INSTALLATION_RUNTIME_MATRIX_EVIDENCE.zh-CN.md`。当前等待独立审查；M7.2 未放行。

2026-09-02：M7.1 首轮独立审查 FAIL，报告见
`reviews/R5_M7_1_INSTALLATION_RUNTIME_MATRIX_INDEPENDENT_REVIEW.zh-CN.md`，阻断 3 项、非阻断 1 项。
B1/B2 指出候选混淆固定同 wheel 入口与独立安装、未注册/未导入与未安装；返工选择更小且真实的产品
边界：核心发行固定为 `builtin + general_science`，论文图入口为安装激活可选，曲线实现与远程 TCAD
实现分别继续随同领域 wheel 分发，但只显式注册/启用且普通路径不导入。B3 新增干净核心 wheel 加
blind CSV wheel 的已安装 Hardened 纵向测试，真实完成 Root invoke、profile、Worker 工具、服务端写入
和 Run completed，`1 passed in 38.83s`。生产代码与运行实体零增加；等待全新独立复审，M7.2 仍未
放行。

2026-09-02：M7.1 全新独立复审 PASS，报告见
`reviews/R5_M7_1_INSTALLATION_RUNTIME_MATRIX_INDEPENDENT_REREVIEW.zh-CN.md`。独立复算已安装
Hardened 正例 `1 passed`、干净 wheel/所有权/可选图证据组合 `19 passed`、部署/远程聚焦
`9 passed`、33 项结构 `1 passed`，并用生成 profile 的真实 stdio MCP 命令核对工具集合；阻断 0，
保留 1 项非阻断 N1 给 M7.2 的真实 TCAD 子智能体链路。仅放行 M7.2，不宣称 M7 或 R5-M 完成。

2026-09-02：M7.2 开始。L2/L3/L4 实时脚本已迁到当前 Run 接口；通用作者 Run 持久保存在
`deliverables/m7-live-generic-20260902-01/` 并处于 queued，精确角色为
`op_blind_csv_observe_v1_e97991e668e9`。父会话按约束使用该 exact `agent_type` 派发时，当前 Codex
会话返回 `unknown agent_type`；原因是会话启动时只加载旧根角色，运行中新生成角色不热注册，且根
`.codex` 在当前沙箱中只读。没有退回通用 worker 旁路。解除方式为把验证目录中已生成的角色安装到
根 `.codex/agents` 后重启会话，再继续同一 queued Run。证据见
`evidence/R5_M7_2_LIVE_AGENT_VERTICAL_EVIDENCE.zh-CN.md`；M7.2 仍进行中，后续阶段未放行。

2026-09-02：重启后的第二次真实派发进一步收窄阻断。旧 `author` 已由 Root 明确记录为超时失败；
新动作从当前实例清单与 `public` 目录选择，以同一请求通过 preflight/invoke 创建
`author_recovery`。精确 `agent_type` 已能启动，但子会话没有继承生成 profile 声明的专属 Worker
MCP，因而未打开 assignment；该 Run 也已由 Root 明确记录为失败。根因是 Codex 角色文件不能新增
父会话未加载的 MCP，而根 `.codex/config.toml` 仍只有旧 Root 服务。下一步只需把生成 profile 的
精确 Worker MCP 段注册到父配置并重启；不会恢复两个失败 Run，也不会退回通用 worker 或父会话代
执行。证据已更新；M7.2 仍进行中，后续阶段未放行。

2026-09-02：为避免反复重启交互父会话，用户授权 M7.2 以独立 `codex exec` 承载已排队 Operation。
测试启动器校验生成 profile 与父 Worker 投影，只启用目标 MCP，并在外层 Codex 沙箱中避免嵌套
bubblewrap；默认产品调度路径未改变。首次作者完成后，独立审查者发现 reviewer 的 Spec 同时声明
`native_shell=none` 且没有输入读取工具，导致“必须审查但不能读取”。插件最小修正为明确声明
trusted-local 原型任务内读取能力，没有增加 Root 特判或新注册表。修正后 `author_exec7` 与
`reviewer_exec3` 完成科学闭环，但独立终审因缺少持久 launcher provenance 判为 FAIL，不接受终端
输出替代审计事实。

2026-09-02：返工为每次 launcher 调用增加原子、无覆盖的最小收据，只记录角色/命令投影摘要、不同
invocation、时段、退出码、4096 MiB 上限、外层沙箱模式、目标 server 和 Worker 工具名；不记录
参数、结果、Run/Artifact 标识、路径或科学内容。L3 探针删除写死的 `bridge_used=false`，改为重建
完整命令并校验摘要、profile、server、工具、时间、资源/沙箱模式，再与 Root completed、域工具活动、
精确审查 subject/父链交叉验证。全新 `author_exec8` 与 `reviewer_exec4` 通过，持久账本为
`5 completed / 8 failed / 0 queued / 0 running`；本次范围回归 `31 passed`、差异检查通过。独立
复审结论 PASS，只放行 M7.2 的 TCAD 作者→领域调试→独立 Deck reviewer 子链，不宣称 M7.2、M7 或
R5-M 完成。证据见 `evidence/R5_M7_2_LIVE_AGENT_VERTICAL_EVIDENCE.zh-CN.md`，独立报告见
`reviews/R5_M7_2_GENERIC_CODEX_EXEC_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md`。

2026-09-02：TCAD 收据闭环的首个新作者越界读取仓库/历史交付物并尝试生成伪造网格占位，已中断且
由 Root 明确记为 failed，无输出/current。提示词边界不足，未直接重试。为此加入只属于 launcher 的
原生 Hook 审计与提交门；随后一次重复嵌套 Codex 探针因单进程 `RLIMIT_AS` 无法约束整个进程树而
导致 WSL OOM/强制重启。重启后停止真实探针，改用官方 Codex 0.151 Hook 契约测试，并增加 4 GiB
进程树聚合 RSS 熔断与根退出后代清理。独立首审列出 5 项阻断，返工关闭后复审 PASS；低内存串行
组合回归 `27 passed`。报告见
`reviews/R5_M7_2_TRUSTED_LOCAL_GUARD_INDEPENDENT_REREVIEW.zh-CN.md`。只放行全新根、单 Worker、
严格串行的下一次 TCAD 作者运行；不宣称 M7.2 完成。

2026-09-02：重新审视 trusted-local 守卫后确认其 Hook、原生命令白名单、MCP 代理和提交门已经形成
第二套权限/运行协议，偏离 M7 调试承载目标。当前实现已删除这些机制，独立启动器只保留精确编译
角色启动、兄弟 MCP 禁用、单进程地址空间限制、整棵后代进程树聚合 RSS 熔断和最小启动/内存收据；
所有 Run、工具活动与结果资格仍由既有控制服务判断。启动器聚焦 `9 passed`、与 TCAD/运行插件组合
`18 passed`，独立架构复审 PASS，仅放行串行 4 GiB 的全新 TCAD 重试。

2026-09-02：M7.2 TCAD 与修订子链在候选根
`deliverables/m7-live-tcad-receipt-v7-20260902-01/` 完成。四个独立 Codex 调用依次产生：初始作者合格
预检项目、精确独立 `revise` 审查、绑定真实 `device_grid` 且重新调试的修订项目、针对修订对象的
精确 `pass` 复审。最终状态的 11 项机器断言全部为真，证明四次启动不同、旧审查未继承、修订父链
精确、TCAD 调试成功、预检与源码绑定、复审 subject 精确且通过。独立终审随后判定 FAIL：修订增加
首次求解结构却只执行 `preflight`，违反编译作者合同要求的 `initialization`；探针只核对任意 debug
成功而产生假阳性。v7 保留为失败证据，不关闭 M7.2 第 2、3 项。

2026-09-02：针对该终审阻断实施最小返工。领域调试适配器将 R-2020.09 SDevice initialization 精确
映射为 `sdevice -i <commandfile>`，不再把它误标为 smoke；调试服务写入 source-bound initialization
报告；M7 修订 probe 在排队 reviewer 和最终状态两处都要求该报告与最终 preflight 的源码摘要完全
相同，并新增 preflight 冒充和 stale source 负例。聚焦组合 `22 passed`。下一步仅允许全新根严格
串行重跑 TCAD 四步链，不放行 Effect、恢复、M7 或 R5-M。

2026-09-02：TCAD v8 全新根
`deliverables/m7-live-tcad-receipt-v8-20260902-01/` 已严格串行完成四步链：初始作者、精确 `revise`
审查、绑定真实 `device_grid` 的修订作者、针对修订对象的精确 `pass` 复审。修订作者在同一份未再
修改的最终源码上依次完成合格 preflight 与 initialization；机器状态新增并通过
`revision_initialization_qualified`，其余 Run、父链、旧审查不继承、收据和审查断言也全部为真。
聚焦回归 `22 passed`，语法与差异检查通过，实跑后约 14 GiB 内存可用。当前只形成 TCAD 子链机器
闭环候选，等待独立终审；Effect、恢复、M7 与 R5-M 均未放行。

2026-09-02：TCAD v8 独立终审 PASS，阻断项 0，报告见
`reviews/R5_M7_2_TCAD_V8_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。审查者从持久状态独立确认实际 Job 为
`-P main.cmd` 后 `-i init.cmd`，两份调试归档字节一致且绑定同一最终源码；最终新审查精确绑定修订
Artifact，旧 `revise` 结论未继承；启动器没有成为第二运行时。M7.2 第 2、3 项正式关闭，连同此前
通过的通用子链，第 1—3 项完成。保留三项非阻断限制：测试 transport 不等于真实 Sentaurus、初始化
报告依赖持久 Run 工作区、修订 handoff 的后续动作文字滞后。下一步仅放行第 4 项 Effect/UI/执行链；
第 5 项、M7.2、M7 与 R5-M 仍未完成。

2026-09-02：M7.2 第 4 项使用最小已安装 `m7_effect_fixture` 完成机器闭环。Effect 由统一插件入口和
启动期目录装载，`operation_invoke` 建立唯一 Execution/Approval；审批前 start 被拒绝。首次随机端口
结束后，只恢复同一 pending Approval，不重新创建对象。其访问凭证到期时由真实 loopback UI 刷新；
用户明确授权本次 debug 代审后，父调度者仍按 GET 首页→POST 刷新→GET 精确 review→POST 决定的页面
协议提交，未直接写服务或数据库。密封决定后才显式 start/sync/outputs，Execution 为 collected，输出
与冻结 manifest 字节一致。聚焦回归 `4 passed`，恢复事前审查和最终独立终审均为 PASS、阻断 0，
报告见 `reviews/R5_M7_2_EFFECT_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。第 4 项正式关闭；第 5 项及 M7.2
仍未放行。

2026-09-02：M7.2 第 5 项在全新根 `deliverables/m7-live-run-recovery-20260902-01/` 完成机器候选。
实跑前先修复恢复请求 preflight 与 schedule 的精确 Operation/输入校验断裂；单一规则在 Root 纯预检
和事务内冻结输入后复用，错输入负例证明零 Run 写入，独立复审 PASS。故障注入进程经 stdio Worker
MCP 打开 assignment、调用注册 CSV 工具、写合法草稿但不 submit，以 73 退出；Root 用
state+last_activity 比较交换记 failed。相同 Operation、指令和输入通过 resume_from 创建新 Run，唯一
一个 4 GiB 独立 Codex 重新调用领域工具并完成受控提交。重启后所有机器断言为真，组合回归
`23 passed`。但实跑观察到 Worker MCP 不支持资源列表，Agent 经 6 次格式拒绝才完成，不能证明其实际
读到恢复草稿；此外 max_attempts 尚未落实，只能主张单次恢复的资源有界。

2026-09-02：M7.2 第 5 项独立终审结论为 FAIL、阻断项 2，报告见
`reviews/R5_M7_2_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。阻断一是恢复 Agent 没有可审计的草稿
读取能力，现有实跑只证明相同输入重做；阻断二是 `LimitsSpec.max_attempts` 未被 `RunService`
消费，恢复链没有硬上限，不满足 `RES-002`。另有非阻断的 quarantine 只读候选残留。其余恢复身份、
失败比较交换、错误输入零 Run、草稿非 Artifact、独立新 Run、领域工具复验、CAS/父链和重启终态均
独立复算通过，审查者聚焦回归为 `23 passed in 5.30s`。按用户要求，本轮审查后暂停；未开始修复，
未进入 M7.3，M7.2、M7 和 R5-M 均未完成。

2026-09-02：根据恢复终审暴露出的共性问题，当前计划改为默认 Local 软隔离。输出 Schema 和恢复
草稿已经物化却因 `native_shell="none"` 无法读取，说明把任务内读、写、执行和强隔离捆成一个权限
开关会反向阻碍 Agent。后续不增加 MCP 文件读取面或读取审计实体；所有 Local Agent 直接使用任务
工作区和原生能力，控制面只守住输入绑定、输出封存、Artifact 登记、独立审查、人工决定与 Effect。
M7.2 第 5 项按 12.2 的功能性草稿利用和简单 `max_attempts` 硬上限返工；强隔离与 Hardened 完备性
移出 R5-M 完成门。既有 M0—M7.1 和 M7.2 第 1—4 项 PASS 不受追溯影响，恢复终审 FAIL 也继续作为
历史事实保留。当前仅更新计划和规范，实施仍暂停。

2026-09-02：默认 Local 软隔离与恢复树总次数上限已完成实现，父进程和独立审查者分别完成
`62 passed` 聚焦回归；实现独立审查 PASS、阻断 0。随后在全新持久根
`deliverables/m7-live-run-recovery-soft-20260902-01/` 串行完成故障注入和一个 4 GiB 真实 Codex 恢复
Run。恢复 Agent 读取草稿并保留其随机独有标记，读取 Schema 并在首次提交带回独有必填常量，重新
调用领域工具且 `output_rejected=0`；重启后全部机器断言为真。第二个恢复请求从 preflight 和 invoke
均零 Run 拒绝。证据见 `evidence/R5_M7_2_LIVE_AGENT_VERTICAL_EVIDENCE.zh-CN.md`，当前等待新的独立
终审；M7.2 第 5 项、M7.2、M7 和 R5-M 尚未关闭。

2026-09-02：新的独立恢复终审 PASS、阻断 0，报告见
`reviews/R5_M7_2_SOFT_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。审查者从持久状态独立确认草稿
随机标记进入封存 signal、Schema 独有常量在首次提交进入 payload、领域工具重验、
`output_rejected=0`、恢复树总次数上限及超限零 Run/零 binding。旧 B1/B2 均关闭，M7.2 第 5 项及
M7.2 整体完成；当前只放行 M7.3，M7 与 R5-M 仍未完成。

2026-09-03：M7.3 首轮独立边界预审发现正式 Effect 在外部响应丢失或本地登记失败后可能盲目重提。
返工没有增加未知提交状态、表或恢复器，而是把所有正式适配器统一为“按冻结描述符权威查回→仅在
确认不存在时幂等提交”，并令同一外部编号的本地登记可幂等重放。响应丢失、本地登记失败、lookup
不可用、缺 lookup、恶意来源扩权、通用结果符号链接以及既有科学边界负例全部通过。独立复审运行
`82 passed`，另行核对 TCAD socket/command/SSH/remote runner 查回路径，结论 PASS、阻断 0，报告见
`reviews/R5_M7_3_SCIENCE_CONTROL_BOUNDARY_INDEPENDENT_REVIEW.zh-CN.md`。M7.3 完成，当前只放行
M7.4；`SEC-002` 继续为 `known_issue`，M7 与 R5-M 仍未完成。

2026-09-03：M7.4 首轮独立审查发现物理报告存在四项阻断：Task 后继责任漏计、默认目录与显式
TCAD 组合混报、M6/M7 阶段净变化使用中间端点、盲 CSV 插件少记一个 Agent Operation。返工只修正
可复算计量器、结构门和报告事实，没有修改生产运行语义。全新独立复审重新计算生产树、六项集中
责任后继、六种目录组合、默认导入、Root/数据库/合同字段及 33 项状态，并串行运行 39 项结构测试；
结论 PASS、阻断 0，报告见
`reviews/R5_M7_4_FINAL_PHYSICAL_REPORT_INDEPENDENT_REREVIEW.zh-CN.md`。M7.4 完成，当前只放行
M7.5；M7 与 R5-M 仍未完成。

2026-09-03：M7.5 候选已完成静态门和清洁前置的全量串行回归。最终结果为 `286 passed in
119.08s`，峰值常驻内存 140124 KiB、无 swap；套件实际生成干净发行源和 wheel、安装十四种隔离
组合，并覆盖部署退出旧表面和事务回滚。首轮全量前的原地 `compileall` 生成一个 runner 字节码缓存，
导致部署测试按设计拒绝源码污染；只清除该确定生成缓存后精确项与全量重跑均通过，没有修改生产或
测试代码。候选证据见 `evidence/R5_M7_5_FINAL_REGRESSION_AND_CLOSURE_EVIDENCE.zh-CN.md`。当前等待
两位未参与实现的独立终审者分别审查正确性/跨边界和简化目标/33 项约束；终审前 M7.5、M7 与 R5-M
仍未关闭。

2026-09-03：M7.5 两位未参与实现的独立终审者均已完成审查。正确性/跨边界终审串行复验 16 项，
复核五份 M7 证据、关键实现和四个持久运行根，结论 PASS、阻断 0；简化/架构目标终审串行复验
22 项，独立检查单一目录/Run/current、插件边界、物理口径和 33 项状态，结论 PASS、阻断 0。报告见
`reviews/R5_M7_5_CORRECTNESS_INDEPENDENT_FINAL_REVIEW.zh-CN.md` 与
`reviews/R5_M7_5_SIMPLIFICATION_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。条件已经共同满足，据此关闭
M7.5、M7 与 R5-M。`SEC-002` 仍是唯一 `known_issue`，其余无直接证据的项目不因关闭里程碑自动
晋级。默认无 Effect 时的 execution Root 工具投影、全量原始日志冻结和 UI 视觉改进只登记为后续
独立候选，不在本轮追加补丁。
