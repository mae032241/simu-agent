# R5-S 生产代码裁剪与控制面简化计划

日期：2026-08-31  
性质：R5-H 之后、H7 之前的主动减重方案  
状态：S0、S1 已完成；S2 默认路径实现因复杂度反噬暂停  
基线：`baseline/8765-codex@404aeb1` 加当前 R1—R5-H 未提交成果  
状态权威：阶段总状态仍以
`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 26 节为准；本文件只负责 R5-S 的设计、
施工顺序和验收边界。

> 2026-08-31 设计纠偏：S2 第三轮审查证明的是旧可靠控制器内部协议闭合，没有证明其适合作为
> 所有科研探索的默认运行时。后续以
> [R5-L 最小默认运行主干计划](R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md) 为活动候选：S0、S1
> 成果保留；精确调度和服务端文件协议冻结为加固后端候选，不完全废弃；本文件 S2—S6 不再自动
> 放行实施。

## 1. 为什么在 H7 之前增加 R5-S

H6-C 第二轮独立复审已经通过，证明当前实现没有明显的零消费者生产表面，也没有用机械拆文件
伪装职责收敛。但当前生产 Python 仍有约 150 个文件、59,200 行，其中核心约 34,840 行；启动目录
声明有 239 个组件和 48 个 Operation，基础 Worker 协议暴露 16 个工具，核心和领域插件共显式建立
33 张表。

这不意味着按数字机械删除，而意味着当前系统仍有较高的概念税：一个普通 Agent 输出要同时穿过
文件编辑协议、端口用途、生产者下游准入、资格集合、结构校验、上下文校验、封存和再次校验。低风险
科学探索因此承担了接近正式证据和外部执行的控制成本。

若现在直接进入 H7，端到端测试会把这套较重协议固化为“已经验收的产品合同”，后续再删会更贵。
R5-S 的目的不是继续发明架构，而是用奥卡姆剃刀回答三个问题：

1. 哪些实体和门禁是 33 项约束真正需要的？
2. 哪些只是同一事实的重复表示、测试证明面或未来实验？
3. 能否让普通科学探索只承担最小成本，而把严格门禁留给科学晋级和外部副作用？

## 2. 目标架构

裁剪后的运行主干只有六个承重概念：

```text
调度 Agent
  │ 从当前矛盾选择一个 public Operation，并绑定精确 Artifact
  ▼
启动期唯一 CompiledCatalog
  │ 同一个 OperationSpec 给出输入、输出、执行器、工具、预算、审查和副作用
  ▼
统一 preflight / invoke
  ├─ Agent：任务私有输入只读 → 服务端受控编辑 → 一次性原子提交
  ├─ Transform：确定性程序 → 可重放结果
  ├─ Approval：精确 loopback UI 决定
  └─ Effect：批准后由领域 adapter 执行并恢复
  ▼
不可变 Artifact + Task / Approval / Execution 事实
  ▼
独立 reviewer Operation（只有合同明确要求时）
```

OperationSpec 仍是行为闭包，但它不是巨型类。它只引用插件在同一入口注册的窄组件：数据合同、
执行器、领域工具、可选结果校验器、审查合同和 Effect adapter。编译器只解析引用、检查闭合性并
冻结一个目录，不在运行时重新解释领域规则。

控制强度按既有 `consequence` 分层，不增加新的运行实体：

- `explore`：只检查绑定存在、数据形状、大小、路径、预算和工具范围；允许产生未经资格的探索结果；
- 科学晋级：在上述检查之外，验证 current、父链以及 Operation 明确声明的独立审查或资格；
- 外部副作用：再增加精确人工审批、幂等提交、未知结果查回和收集边界。

控制层不判断假设是否值得、来源应如何取舍、候选如何排序、结果是否具有科学意义。上述判断分别
属于调度 Agent、专业 Worker 和独立 reviewer。

## 3. 裁剪原则

### 3.1 若非必要，勿增实体

只有同时满足下列条件的概念才进入生产运行时：

1. 表示一个不能从现有事实确定性推导的独立事实；
2. 至少有一个真实生产消费者；
3. 删除后会破坏一项明确的架构约束或用户可见能力；
4. 不能用已有 Artifact、Task、Approval、Execution、OperationSpec 或组件引用表达。

仅用于测试架构、展示插件可扩展性、兼容旧文件、预留未来进程隔离或记录同一状态不同投影的对象，
不得留在生产主路径。

### 3.2 Operation 的最小判据

一个行为只有在“能够被调度 Agent 独立选择、独立重放，并产生或改变一等 Artifact、Approval 或
Effect”时才是 Operation。只在某个行为内部做解析、规范化、格式校验或局部计算的函数，是注册组件
或普通实现帮助函数，不因可复用就自动升级为 `support` Operation。

不得为了减少 Operation 数量把多个科学角色塞进带大量条件分支的万能 Operation。TCAD 初次编写、
依据审查意见修订和依据运行失败调试，若输入合同、上下文或专业责任不同，可以继续是三个窄行为。

### 3.3 删除必须有证据

每个删除候选在动手前都记录：

- 精确文件和符号；
- 源码、安装入口、动态插件、测试、文档和发布包消费者；
- 其当前保护的不变量；
- 删除后明确放弃的行为；
- 替代路径或“无替代、因为无生产消费者”的结论；
- 正例、负例、安装态和恢复测试；
- 以本阶段起点提交或工作树快照为回退边界。

移动到另一个生产模块仍计入生产规模，不得把重命名或拆文件报告为减重。

### 3.4 不为兼容增加第二条路

本轮不保证历史源码、旧数据库和旧状态文件在线兼容。旧资料保持只读且不自动升级、不自动删除；
确需提取时使用显式离线工具。禁止兼容别名、双写、双读、版本路由或隐藏回退。

### 3.5 失败先审视设计

测试失败时先判断合同、职责或状态是否重复，不得按具体案例增加 Schema 名称特判、插件 allowlist、
角色名分支、隐藏准入标签或固定科研流程。若修复需要新增生产实体、注册表、数据库表或跨层旁路，
当前阶段自动停止并重新审查方案。

## 4. 必须保留的承重边界

无论能删除多少行，以下行为不可退化：

- Artifact 字节、父链、合同身份和已登记收据不可变；
- 一个控制面拥有实例、current、qualification、任务终态、审批和执行事实；
- Worker 只接收任务内科学别名和声明输入，不接收控制身份；
- 同一 OperationSpec 的编译合同贯穿 preflight、invoke、assignment、提交、收据和恢复；
- 调度 Agent 依据当前科学矛盾选择行为，依赖不构成固定阶段 DAG；
- 作者与独立 reviewer 不合并为同一科学决定；
- 确定性 Transform 只做机械变换和显式 Metric，不替代科学判断；
- 人工决定只来自精确 loopback UI，科学资格和外部执行授权分开；
- 查询纯读，状态推进使用显式、幂等、比较并交换命令；
- Effect 的提交、领域运行和结果收集仍是不同事实，unknown 只能向权威系统查回；
- 通用核心不按 TCAD、曲线、Schema、角色、profile 或插件名称分支；
- 一个插件入口、一个启动期目录、三种目录视图只是同一目录投影；
- 领域工具由 Operation 精确声明并由服务端校验；
- 当前 `spawn_agent` 原生工具隔离只是提示约束，继续如实记录为 `SEC-002 known_issue`，不得宣传为
  技术沙箱。

## 5. 当前复杂度基线

以下数字只用于发现重复和判断方向，不是删除许可：

| 表面 | 当前观测 |
| --- | ---: |
| 生产 Python | 150 文件 / 59,200 行 |
| 核心 `src/scidiscovery` | 34,840 行 |
| TCAD 插件 | 14,280 行 / 25 文件 |
| 曲线插件 | 8,938 行 / 16 文件 |
| 生产数据库表 | 33 张 |
| 启动目录声明 | 约 239 组件 / 48 Operation |
| Operation 端口 | 225 输入 / 66 输出 |
| 基础 Worker 工具 | 16 个 |
| 注册校验器组件 | 57 个 |
| 注册编解码器组件 | 10 个 |
| 注册 guard 组件 | 11 个 |
| 注册资源组件 | 96 个 |
| 测试 Python | 27,711 行 |

总体规划预算是基于消费者证据净删除约 6,000—10,000 行，使核心向不超过约 28,000 行、生产总量向
不超过约 52,000 行收敛。这只是复杂度报警线：不得为了达到数字删除承重不变量，也不得用生成代码、
移动目录或测试内复制实现规避统计。

## 6. 已发现的裁剪候选

### 6.1 测试、示例和未来实验退出生产主路径

| 候选 | 消费者证据 | 处理方向 | 保留的不变量 | 明确放弃 |
| --- | --- | --- | --- | --- |
| `src/scidiscovery/builtin_plugin.py::ARCHITECTURE_TEST_PLUGIN` | 实际产品只使用从它过滤出的 `CORE_PLUGIN`；其余声明用于架构测试 | 将测试声明移入 `tests` 夹具，生产文件只直接声明最小 `CORE_PLUGIN` | 核心生命周期组件仍由同一插件入口编译 | 生产 wheel 自带通用架构测试插件 |
| `plugins/table_observation` | 当前是扩展性证明，真实消费者集中在测试和发布构建 | 移入测试夹具或明确的非生产示例，不进入默认源发布 | 盲插件验收仍从外部测试包安装 | 把示例插件当成产品领域能力 |
| `src/scidiscovery/platforms/codex_worker.py`、`service/agent_dispatch.py` | 当前正式路径使用 `spawn_agent`；两者是未启用的独立 Worker 进程实验 | 保留到 `experiments/worker_process_v2/`，从生产包、默认导入和当前文档移除 | 当前 Agent 派发路径唯一；未来 V2 研究代码可追溯 | 声称当前已有进程级原生工具隔离 |

这一阶段不删除未来 Worker 进程代码，只把它从生产责任和规模中移出。若存在运行时导入或安装后
消费者，则该项停止，不得用兼容转发继续伪装退出。

### 6.2 Worker 文件协议收敛

当前基础协议把 claim、物化、PDF、分析、网络冻结、分块写、文本补丁、JSON 补丁、移动、删除、
checkpoint、validate、finalize 和 heartbeat 都作为通用控制工具。这重复了 Codex 已有的任务工作区
只读查看、受控写入与领域工具协议，让每个 Operation 承担了大量并非自身科学能力的交互概念。

目标是先把任务生命周期压缩成三个工具：

1. `worker_open_assignment`：原子完成精确任务领取和只读输入物化，返回任务私有工作区；
2. `worker_heartbeat`：只在长任务需要时续租，仍受绝对预算限制；
3. `worker_submit_result`：对通过服务端文件工具生成的完整输出目录做一次不可变快照、一次合同校验、
   登记 Artifact 并以比较并
   交换完成任务；失败返回有界诊断，任务保持活动。

在任务级操作系统沙箱真正可用前，Agent 不得用 Codex 原生写入修改输出；所有创建、修改、移动和删除
仍须经过 Operation 精确声明、服务端执行路径/大小/摘要检查的文件工具。S2 可以折叠这些工具的重复
协议，但不能用提示词禁令代替服务端受控写入，也不设置“总工具数必须为三个”的机械目标。普通文本、
PDF 和图像可继续用现有任务内原生只读能力，`SEC-002` 仍如实标记其平台隔离不足。

`worker_submit_result` 必须在服务端重新验证路径、文件数、总字节、秘密模式、声明输出和完整 bundle。
现有
`validate → sealed snapshot → finalize → 对相同字节再次完整校验` 合并为一次提交事务，不保留第二
终态或第二校验权威。

下列能力不再是所有 Agent 的基础工具：

- checkpoint 和重复的文件编辑协议；实际保留的写入原语由 S2 消费者审计决定，且必须继续在服务端
  执行；
- 通用 `worker_run_analysis`；
- 普通文本、PDF 和图像读取封装。

需要正式可追溯网页来源时，保留由 Operation 精确注册的“冻结网页证据”领域工具；需要可审计论文
摘录时，保留精确页码/定位器的证据工具。普通文本、PDF、图像查看优先使用 Codex 原生能力。TCAD
调试、求解器准备和其他领域工具仍由 TCAD Operation 注册，不得被基础工具裁掉。

这个原型仍不能在平台层关闭未授权原生工具。编译提示必须明确列出可见但禁止的工具，领域 MCP 在
服务端继续执行精确 Operation 门禁；进程级隔离留给已移出生产主路径的 Worker V2 实验。

### 6.3 OperationSpec 和准入规则收敛

当前端口同时表达：

- 输入的 `usage`；
- 输出的 `allowed_input_usages`；
- 端口级 `cohort_id`、`approval_kind`、可接受选项和 provider Operation；
- 输出 shape validator、semantic contract、context validator、bundle validator、evidence paths；
- 根路由中的生产者下游准入、cohort 拼接、`claim_admissible` 和 direct revision 特判。

这让生产者必须预知所有下游科学用途，也使控制层以标签决定某对象能否成为主张证据。目标改为：

1. 保留 `InputPortSpec.usage` 作为消费 Operation 声明、Worker 可见的本地认识论角色，用来区分
   `claim_evidence`、`revision_base`、`change_request` 和普通上下文；它不授权未来下游；
2. 删除 `OutputPortSpec.allowed_input_usages`、producer-side downstream admission 与通用
   `claim_admissible` 标签；
3. 输入端口还描述数据合同、基数、字节上限、曝光方式和是否要求 current；
4. 需要完整资格集合的 Operation，在 Operation 层声明至多一个资格组：引用输入端口元组、资格种类、
   可接受结论和 provider Operation；不把同一信息复制到每个端口；当前证据未要求多个资格组，因此
   不预先泛化；
5. 审查与资格只回答“这个精确输入集合是否得到声明的独立决定”，不回答科学内容是否真实；
6. preflight 与 invoke 继续调用同一个准入函数，invoke 必须重检以防检查后状态变化；
7. `explore` 输出可以被后续 Agent 当作显式的未经资格输入，但不能冒充已晋级事实；是否采用由后续
   科学 Operation 和 reviewer 合同决定，而不是由生产者枚举用途。

修订是普通 Agent Operation：输入旧对象、变更依据和必要上下文，输出完整新对象。旧对象保持不可变，
新对象拥有新父链并独立审查。删除 `direct_revision_ports` 和
`_validate_direct_revision_request` 等核心特殊路径，不以补丁对象、schema 名称或角色名识别修订。

### 6.4 数据合同和校验器收敛

插件目前经常为同一结构分别注册 codec、schema resource 和 strict model validator，输出又叠加上下文
校验、bundle 校验和 guard。目标不是引入第四个注册表，而是用一个插件拥有的“数据合同组件”替换
上述三件套：

```text
DataContractComponent
├── 稳定 contract_id 与版本
├── media types
├── decode / encode
├── 结构 Schema 投影
└── 纯机械 validate
```

端口只引用一个数据合同。每个 Operation 允许至多一个可选的结果校验器，一次接收精确输入和完整
输出，只验证跨文件、父子数量、确定性收据等机械不变量。科学合理性、证据取舍和 verdict 必须交给
独立 reviewer。

只重复 Artifact 父链的 parentage guard 应改为一个可见的通用声明关系，若现有谱系已足以证明则直接
删除。正式图像数字化、确定性 Metric 等确实需要工具收据重放的行为可以保留专用校验，但不得把专用
规则提升为所有 Operation 的默认层。

### 6.5 实例和本地管理收敛

保留 `ResearchInstance`、实例语义绑定、唯一 current 和不可变历史。实例创建与选择是本地用户的显式
UI 行为，不是科学资格或外部执行审批，因此不再复用 Approval 生命周期，也不需要候选、提案、会话
决定应用失败等中间事实。

优先审计并移除被新 UI command 替代的中间流程：

- `scheduler_instance_proposals`；
- `scheduler_session_binding_requests`；
- `scheduler_session_binding_candidates`；
- 仅为上述流程存在的候选观察、决定应用和失败记录方法。

`scheduler_sessions` 必须保留：它是不可从 ResearchInstance 推导的
`session_key → instance_id` 唯一持久绑定，`instance_current` 依靠它在重启后恢复当前实例。S4 只删除
创建/选择前的提案和审批包装，不能把最终绑定移入内存、换表重建或建立第二 current。

实例选择仍必须由 loopback UI 发起，聊天文字不能转换为选择或审批。删除/孤儿维护降为显式本地离线
命令：要求无活动任务、审批和执行，先做一致性快照，再输出精确 blocker 或结果；不建设分布式删除
状态机。若 `scheduler_instance_deletions` 只服务该状态机且没有恢复价值，则一并删除；若保存了无法从
不可变事件推导的恢复事实，则保留并记录理由。

## 7. 分阶段实施

一次只施工一个阶段。每个阶段都要冻结精确 diff、自动化证据和消费者清单，再交给未参与该阶段实现
的独立审查者。结论为“有条件通过”或“打回”时，只能修复当前阶段并重新审查，不能进入下一阶段。

### S0：冻结基线和删减账本

任务：

- 记录生产文件、行数、组件、Operation、工具、数据库表和发布包基线；
- 为第 6 节每个候选建立精确符号—消费者—不变量—测试—回退账本；
- 冻结核心、核心加通用科研、再加曲线、再加 TCAD 四种安装组合；
- 冻结当前 Agent、Transform、Approval、Effect 的正反例；
- 将本方案提交独立架构审查，重点判断是否误删 33 项约束、是否仍有过度设计、施工顺序是否可逆。

完成门：没有生产行为变化；账本中不存在“因为看起来复杂”而删除的项目；独立方案审查明确通过。

### S1：测试证明面和未来实验退出生产包

任务：

- 直接声明最小 `CORE_PLUGIN`，将 `ARCHITECTURE_TEST_PLUGIN` 移到测试夹具；
- 将 `table_observation` 变成从外部安装的盲插件夹具或明确非生产示例；
- 将未启用的 Worker 进程代码移到实验目录，删除生产导入、发布投影和当前能力声明；
- 验证干净 wheel 和源码运行暴露同一正式入口。

验收：核心生命周期、插件编译和盲插件测试不变；生产包不包含测试领域或未启用执行路径；生产文件和
行数净下降；独立审查通过。

### S2：压缩 Worker 生命周期并保留服务端受控写入

任务：

- 新建 open、heartbeat、submit 三个生命周期工具并迁移正式 `spawn_agent` 路径；
- 让一次提交完成快照、完整 bundle 校验、Artifact 登记和 Task CAS；
- 在保持服务端文件操作的前提下，按真实消费者合并写/补丁/移动/删除协议，删除 checkpoint、二段
  finalize 及无消费者状态；不得开放原生写入；
- 将网页冻结、正式 PDF 摘录、TCAD 调试等变成 Operation 精确注册的领域工具；
- 真实拉起至少一个通用 Agent 和一个 TCAD 编码 Agent，验证任务内原生只读、服务端受控写入及注册
  领域工具均可实际使用；
- 做跨任务路径、未声明领域工具、超预算、非法 bundle、重复提交、晚提交和任务重启负例。

验收：生命周期只有 `open_assignment`、`heartbeat`、`submit_result` 三个；每个 Operation 另有精确、
最小的服务端文件工具和领域工具；没有第二提交协议；原生写入仍禁止且不宣传为技术隔离；
Task/Artifact 幂等、CAS 和恢复不退化；独立审查通过。

### S3：删除下游用途策略，压缩资格和修订路径

任务：

- 保留消费端 input usage，删除 output allowed usages、producer admission 和 claim-admissible 标签链；
- 将资格从端口重复字段收敛为一个 Operation 层资格组；
- 用统一 consequence 分层执行 explore、科学晋级和 Effect 门；
- 将完整对象修订迁到普通 Agent Operation，删除 direct revision 特判；
- 同时更新目录摘要、preflight、invoke、任务快照、收据和 UI 投影，不留兼容字段；
- 验证同一绑定 readiness/preflight/invoke 一致，unknown 合同失败关闭。

验收：核心不再决定科学用途；未经资格的探索对象不会获得正式资格，但可作为显式探索输入；revision
不继承旧 verdict；科学资格和执行授权仍分离；无 schema/角色/插件特判；独立审查通过。

### S4：实例与本地管理减重

任务：

- 以显式 loopback UI 命令直接创建和选择实例，不复用 Approval；
- 删除提案、候选、请求、会话决定失败等重复状态和无消费者表；
- 将删除/孤儿维护改为停机或无活动对象前提下的本地离线命令；
- 保留不可变实例历史和唯一 current，不自动升级旧 YAML、label 或审批。

验收：聊天不能创建/选择实例；查询纯读；创建/选择命令幂等；活动任务/审批/执行会阻止维护；重启后
current 唯一；数据库表和方法净减少；独立审查通过。

### S5：合并数据合同，审计 support Operation

任务：

- 以单一数据合同组件替代同结构的 codec、schema resource 和 strict validator 三件套；
- 每个 Operation 最多保留一个机械结果校验入口；
- 删除重复 parentage guard，保留真正需要重放的工具收据校验；
- 逐个审计 support Operation：只有可独立选择、重放并产出一等对象者保留为 Operation；
- 检查 TCAD 三类作者行为，避免为减数量合成条件巨大的万能 Operation；
- 重编译通用、曲线、TCAD 和盲插件，确认只有一个组件目录和一个事务代际。

验收：组件数量实质下降，不存在第二数据合同注册表；同一结构不再三重注册；科学 reviewer 未被机械
validator 替代；新领域仍只需一个插件入口；独立审查通过。

### S6：集成验收与总审查

按不超过 8 GiB 的串行策略执行：

- 四种安装组合和干净 wheel；
- 全量单元与边界回归；
- 真实通用 Agent 原生文本/PDF/图像能力；
- 真实 TCAD 编码 Agent 的读写、领域调试工具和完整提交；
- 一个仓库外盲插件只通过 entry point 注册数据合同、Agent、工具和 Operation；
- Approval、Effect unknown、恢复、late finalize、current、mixed qualification、跨任务访问负例；
- 生产文件、行数、表、组件、Operation 和 Worker 工具前后对照；
- 独立工程审查和独立架构目标审查。

本阶段只做 TCAD dry-run 与已授权的安全调试。真实 solver 执行必须另有精确 UI 授权，不因测试计划
自动获得权限。

S6 双重独立审查通过后，R5-S 才结束并恢复 H7。H7 负责最终真实端到端产品验收，不再重复已在
R5-S 证明的结构减重。

## 8. 33 项约束映射

这里把 33 项约束作为行为测试矩阵，不为每一项增加运行实体。

| 约束 | R5-S 保留方式与主要验收 |
| --- | --- |
| AUTH-001 | 实例、Artifact、Task、Approval、qualification、current、Execution 仍只有控制面事实；删除重复 session 状态后做重启唯一性测试 |
| AUTH-002 | `open_assignment` 只返回科学别名和任务私有路径；检查提示、文件名和结果不含内部身份 |
| AUTH-003 | 生命周期工具、服务端文件工具、领域工具、预算、提交和恢复都从同一编译 Operation 派生；无隐藏工具路由 |
| IMM-001 | `submit_result` 原子冻结字节和父链；重复及晚提交不能覆盖已登记对象 |
| IMM-002 | 完整请求指纹继续参与幂等；内容变化产生新 revision，旧 verdict 不继承 |
| LIN-001 | 通用科学 Operation 继续显式绑定原始目标；控制层不补写目标或把目标当证据 |
| LIN-002 | 科学晋级保留传递 currentness 和完整资格组；禁止 stale、mixed cohort 和 revision 继承 |
| EVD-001 | 正式网页和论文证据使用精确注册的冻结/定位工具；普通原生阅读不能自动晋级为证据 |
| EVD-002 | Evidence reviewer 保留来源独立性和冲突，控制层不平均或投票 |
| UNC-001 | 缺失、范围和可调性由科学对象显式表达；删除用途门不允许控制层补默认值 |
| UNC-002 | 实验设计数据合同保留机制与 nuisance 对照结构，科学质量由 reviewer 判断 |
| TOP-001 | public 目录不编码阶段；调度 Agent 从矛盾选行为，support 只作已选行为内部帮助 |
| TOP-002 | catalog、preflight 和 invoke 使用同一准入函数；精确正反例检查等价性 |
| ROLE-001 | 删除 producer downstream admission 和固定用途，让 Worker/reviewer 拥有科学内容 |
| ROLE-002 | Operation 摘要贯穿任务快照和一次提交；退休或摘要漂移任务失败关闭 |
| DET-001 | Transform 和正式 Metric 保持版本、重放与父链；内部帮助函数不冒充 Agent 结论 |
| DET-002 | 数据合同和校验器只做机械判断；排序、来源取舍和 verdict 不进入控制层 |
| HIL-001 | 资格、执行及实例 UI 行为均由 loopback 页面发起；聊天不转决定，revision 不沿用旧决定 |
| HIL-002 | 科学资格与外部执行仍是两个精确合同；简化实例选择不合并二者 |
| CQRS-001 | status、list、readiness 和页面 GET 前后数据库摘要一致 |
| CQRS-002 | submit、reconcile、timeout 和审批后果继续是显式幂等命令并使用 CAS |
| EFF-001 | S1—S5 不合并提交、领域运行和结果收集三轴 |
| EFF-002 | unknown 只经领域 adapter 权威查回，不自动重提；Metric/reviewer 不进入 adapter |
| PLG-001 | 数据合同、工具、Agent、算法和 adapter 仍由插件拥有；核心做领域名称扫描反例 |
| PLG-002 | 四种安装组合、盲插件、失败编译回滚和缺插件启动均必须通过 |
| SEC-001 | 冻结来源只作为数据，不改变工具和网络；做 SSRF、路径逃逸和间接提示注入负例 |
| SEC-002 | 文件写入和领域 MCP 保留服务端精确门禁；原生只读工具隔离继续标为已知问题，不把提示禁令冒充沙箱 |
| RES-001 | 输入严格按端口物化，大对象使用文件和流式摘要；禁止 `all_inputs` 与工具参数内联大对象 |
| RES-002 | 时间、字节、文件、来源、恢复和并发仍有上限；全部测试串行且进程内存不超过 8 GiB |
| UI-001 | 资格与执行页面仍优先展示问题、结果、来源、缺口和风险；实例选择页不伪装科学审批 |
| UI-002 | 单位、条件、精度、状态和维护 blocker 保持可见；S6 做桌面和窄屏人工检查 |
| MIG-001 | 不读取或自动提升旧 label、latest、approval 和 current YAML；旧资料只读 |
| MIG-002 | 干净 wheel、重启、失败恢复和回退演练走实际发布入口；历史收据不按新合同改写 |

## 9. 独立审查问题

每一阶段的独立审查至少回答：

1. 删除对象是否确无真实生产消费者，还是消费者调查遗漏？
2. 是否删除了重复表示，而不是把责任移动到另一个生产文件？
3. 是否仍只有一个事实权威、一个插件入口、一个编译目录和一个调用入口？
4. 控制层是否只做身份、形状、谱系、预算、审查、审批和副作用门禁？
5. 是否出现 schema、角色、插件名、TCAD 或具体测试样本特判？
6. 是否用新实体、表、注册表、兼容路由或隐藏标签补回被删复杂度？
7. Agent、Transform、Approval 和 Effect 跨边界生命周期是否完整？
8. 33 项约束的证据是否来自真实安装和运行路径，而非只测帮助函数？
9. 当前系统是否比阶段起点更容易解释和扩展？若不能，阶段应回退而非勉强通过。

## 10. 自动停止条件

出现任一情况，当前阶段停止并回到设计审查：

- 生产文件、生产行数或运行概念净增加，且不能证明是在同阶段删除更多重复责任的短期中间态；
- 新增数据库表、第二注册表、第二 current、第二提交终态或第二调用入口；
- 核心按领域、Schema、角色、profile 或插件名称分支；
- 插件需要修改核心或通用调度器才能安装；
- 控制层重新决定科学排序、来源取舍、机制解释或 verdict；
- 为通过单个测试增加隐藏标签、固定阶段或样本特判；
- 将提示词工具禁令描述为平台级安全隔离；
- 为减少 Operation 数量引入巨型条件 DSL；
- 自动化测试超过 8 GiB 内存、依赖无界并行或必须删除用户数据才能运行；
- 独立审查没有明确“通过”。

## 11. 测试与资源策略

所有测试使用新的临时状态根或干净 wheel，不修改、迁移或删除用户现有实例和资料。WSL 只有 16 GiB
可用内存，单次测试进程设置不超过约 7 GiB 虚拟内存、`MALLOC_ARENA_MAX=2`，禁止并行全仓测试。
执行顺序是：静态检查 → 聚焦单元测试 → 跨边界测试 → 安装组合 → 真实 Agent → 全量串行回归。

每阶段至少记录：

- `git diff --check`；
- 修改表面的聚焦正反例；
- Operation 编译和真实安装入口；
- 必要的 Scheduler → Operation → Task → Worker → Artifact/receipt → review/approval/effect/recovery 链；
- 生产文件、行数、表、组件、Operation 和工具净变化；
- 独立审查报告的精确候选摘要。

## 12. 完成定义

R5-S 只有在下列条件同时成立时才能标为通过：

- S0—S6 全部逐阶段独立审查通过；
- Worker 生命周期收敛为三个工具，文件写入仍由 spec 精确注册的服务端工具执行，领域能力能被真实
  Agent 成功调用；
- 端口不再携带生产者下游用途策略，修订没有核心特殊通道；
- 实例管理不再伪装科学审批或维护重复会话事实；
- 数据合同和机械校验不再重复注册，组件数量实质下降；
- 四种安装组合、盲插件、通用 Agent 和 TCAD dry-run 通过；
- Artifact、Task、Approval、Execution、current、qualification 和恢复不变量没有退化；
- 33 项约束均有当前实现证据，`SEC-002` 仍诚实标记已知问题；
- 生产规模和运行概念净下降，没有通过移动、拆分或生成代码伪造；
- 独立工程审查与架构目标审查均明确通过。

在这之前，H7、R5 发布冻结和真实 solver 执行均保持暂停。

## 13. S0 基线与删除账本

### 13.1 精确候选边界

S0 只修改本计划、当前状态投影和后续独立审查报告，不修改 `src/`、`plugins/`、数据库、部署运行
逻辑或测试行为。当前工作树叠加了 R1—R5-H 的大量未提交成果；S0 不把 `HEAD` 误当成待删实现，
也不使用 reset、clean、checkout 或自动迁移清除这些成果。

基线复算结果：

| 指标 | S0 冻结值 |
| --- | ---: |
| 生产 Python | 150 文件 / 59,200 行 |
| 核心 Python | 34,840 行 |
| TCAD 插件 | 25 文件 / 14,280 行 |
| 曲线插件 | 16 文件 / 8,938 行 |
| InGaAs 项目插件 | 3 文件 / 668 行 |
| table observation 证明插件 | 4 文件 / 474 行 |
| R0 六项核心责任的当前 successor 聚合 | 9,518 行 |
| `operations` 包 | 7 文件 / 2,064 行 |
| 数据库表 | 33 张 |
| 插件声明 | 239 组件 / 48 Operation |
| 目录范围 | 28 public / 20 support / 0 internal |
| 执行器 | 24 Agent / 20 Transform / 3 Approval / 1 Effect |
| 端口 | 225 输入 / 66 输出 |
| 基础 Worker 工具 | 16 个 |
| 组件种类 | 57 validator / 10 codec / 11 guard / 96 resource / 18 worker tool 声明 |

真实组合编译结果为：基础通用 15 项、加曲线 26 项、再加 TCAD 45 项、再加两个可选证明/项目插件
48 项。33 张表由核心 30 张和 TCAD 插件 3 张组成；核心 30 张中包含 Artifact 迁移 SQL 的 4 张表。
此前只扫描核心得到 30，漏掉 `submissions`、`tcad_debug_leases` 和 `tcad_debug_runs`，现已纠正。

33 张表名冻结如下：

- Artifact：`artifact_envelopes`、`artifact_links`、`artifact_events`、`idempotency_records`；
- Approval：`approval_requests`、`approval_decisions`、`approval_events`、`decision_attempts`、
  `used_nonces`；
- Task/Worker：`tasks`、`task_events`、`task_web_evidence`、`pdf_text_cache`、`task_pdf_excerpts`、
  `task_output_artifacts`、`task_provisional_snapshots`、`assignment_instances`、`task_activity_events`、
  `dispatch_capabilities`、`worker_sessions`；
- Scheduler：`scheduler_instances`、`scheduler_bindings`、`scheduler_instance_deletions`、
  `scheduler_observations`、`scheduler_scientific_selections`、`scheduler_sessions`、
  `scheduler_instance_proposals`、`scheduler_session_binding_requests`、
  `scheduler_session_binding_candidates`；
- Execution：`executions`；
- TCAD：`submissions`、`tcad_debug_leases`、`tcad_debug_runs`。

四种编译目录的冻结摘要分别为：

- 基础通用：`afb069df5ee0b70f291208b2116977622138daede043715a200d77fb8948c292`；
- 加曲线：`9f3f2b2205815ebdd70ae8d238bfc3800cd7e5f433d3ebb396357d4aee1e82a5`；
- 再加 TCAD：`55684f170226d04b65ceb5cb81d1ff6714a204135bb621362594a65e79135aa0`；
- 全部六插件：`5fcafe660d6a686ee33646e0a422589a959c72d831715adf8b5a25a58044fb13`。

S0 还冻结了
[`R5_S0_PRODUCTION_SOURCE_SNAPSHOT.sha256`](evidence/R5_S0_PRODUCTION_SOURCE_SNAPSHOT.sha256)，覆盖
`src/scidiscovery`、四个产品/证明插件、`roles/`、`deploy/`、正式 TCAD skill、根 `pyproject.toml`
和三个发布工具共 216 个当前运行、部署和发布行为输入文件；清单自身摘要为
`99641e05e2080730f2b0cbfa3007afeab15906d4bcb2f8d1d0fa36a99fbccf65`。
后续每个阶段必须先复制上一代清单为审查输入，再用该阶段精确 diff 和新清单比较，不能只比较脏
工作树与 `HEAD`。该清单绑定发布归一化前的本地工作树，只在仓库根验证，不进入精简源发布投影；
生成发布包只使用构建器在输出目录生成的 `MANIFEST.sha256`，不得把两者混为一个摘要权威。

### 13.2 删除账本 A：测试证明面

**精确表面**：`src/scidiscovery/builtin_plugin.py::ARCHITECTURE_TEST_PLUGIN`、该模块内仅服务测试
Operation 的实现和资源，以及
`tests/fixtures/plugins/architecture_operation_plugin/pyproject.toml` 的安装入口。

**消费者分类**：

- 生产入口只发布 `CORE_PLUGIN`；它当前从 `ARCHITECTURE_TEST_PLUGIN.components` 过滤六个 Worker
  生命周期工具，没有生产 Operation；
- `src/`、`plugins/`、`deploy/`、`scripts/` 除该定义和过滤表达式外没有消费者；
- 直接消费者是 `tests/operations/` 多个编译、准入、派发、审批和 Effect 测试；
- 测试 wheel 的 entry point 仍错误指向生产模块中的该测试对象。

**处置**：S1 在生产模块中直接声明最小 `CORE_PLUGIN`；将完整 fixture 的实现、资源和
`PluginDefinition` 放入测试 wheel 自己的包。测试继续验证同一编译边界，但产品 wheel 不携带测试
Agent、Transform、Effect、Schema 和 projector。

**保留不变量**：一个插件入口、编译闭合、Agent/Transform/Approval/Effect 正反例、六个当前基础
生命周期工具在 S2 之前保持原身份。

**明确放弃**：仓库外代码从 `scidiscovery.builtin_plugin` 导入未文档化的
`ARCHITECTURE_TEST_PLUGIN`；本重构不提供兼容 alias。

**S1 验证**：测试 fixture wheel 独立安装；产品 wheel 导出和 entry point 负例；架构编译、网络、
审批、Effect、派发测试；四种产品插件组合。

**回退边界**：S1 起点工作树；若发现产品动态消费者，整项停止，不能用生产转发 alias 掩盖。

### 13.3 删除账本 B：扩展性证明插件

**精确表面**：`plugins/table_observation`、根 `pyproject.toml` 的测试 `pythonpath`、
`scripts/build_git_release.py::SOURCE_TREES` 及安装态测试夹具。

**消费者分类**：

- 根产品 entry point 只有 `builtin` 和 `general_science`；默认部署和运行时不加载该插件；
- `src/`、其他插件、部署脚本和产品文档没有运行消费者；
- 当前真实消费者是盲插件、领域边界和 clean-wheel 测试；
- 精简源发布把它当产品树携带，造成“测试证明即产品能力”的错误投影。

**处置**：S1 将其改为仓库外形态的测试 fixture wheel，或者放入明确不进产品包的 `examples/`；优先
复用现有 fixture 安装设施，不为它建立新的示例加载器。

**保留不变量**：非曲线领域能够只靠 `scidiscovery.plugins` 注册数据、Agent、工具、审查和 Operation；
核心不按插件名分支；插件缺失时核心正常。

**明确放弃**：把 table observation 宣称为已支持产品领域和默认发布内容。

**S1 验证**：从不在产品 `PYTHONPATH` 的 fixture wheel 安装后编译、调用和卸载；clean release 不含
该插件；无插件时核心、曲线和 TCAD 组合正常。

**回退边界**：插件目录原字节；若安装测试无法在真正外部边界运行，先修测试基础设施，不把插件
放回产品面冒充扩展性。

### 13.4 删除账本 C：未启用 Worker 进程实验

**精确表面**：`src/scidiscovery/platforms/codex_worker.py`、
`src/scidiscovery/artifact_agent/service/agent_dispatch.py`、对应 `__init__` 导出、测试和 live 脚本。

**消费者分类**：

- 两个生产模块只相互引用，Root、运行时、MCP daemon、插件目录和部署服务不调用它们；
- 当前正式派发是父调度会话根据编译 `agent_type` 使用 `spawn_agent`；
- `tests/operations/test_codex_worker_process.py`、`test_codex_task_dispatch.py` 和旧 live 脚本消费实验；
- 当前架构中英文文档明确标记它们为未启用的后续加固基座。

**处置**：S1 整体移入不打包的 `experiments/worker_process_v2/`，连同专项测试保留；删除生产导出和
当前产品能力描述。不得把实验代码复制一份后仍保留生产原件。

**保留不变量**：正式派发路径唯一；当前 `spawn_agent` 行为和专属领域 MCP 服务端门禁不变；
`SEC-002` 继续标记原生工具隔离的已知问题。

**明确放弃**：当前产品 wheel 中存在一个“可能以后启用”的独立进程实现；不声称已有平台级隔离。

**S1 验证**：源码和 wheel 不可从产品命名空间导入该路径；正式 `spawn_agent` 配置、worker proxy、
真实任务派发测试保持；实验目录自身的纯测试可单独运行但不进入产品发布门。

**回退边界**：两个模块及其专项测试的 S1 起点字节；若 Root 或部署存在动态消费者则停止整项。

### 13.5 折叠账本 D：Worker 协议

**精确表面**：

- `interfaces/mcp_worker_protocol.py::WORKER_TOOLS` 的 16 个工具；
- `interfaces/mcp_worker_dispatch.py::WorkerToolDispatchMixin`；
- `service/task_worker_files.py` 的 materialize、分块写、文本/JSON patch、move/delete、临时快照和
  sealed output 机制；
- `service/task_outputs.py::{checkpoint_output,validate_output_file,finalize_file}`；
- `service/task_evidence.py`、`web_fetch.py`、Codex 提示和 proxy 状态机。

**重复责任**：Worker 既使用 Codex 原生工作区能力，又通过控制 MCP 重建通用编辑器；
`validate_output_file` 已对完整输出做 `_validate_complete_output` 并冻结不可变候选，
`_finalize_validated_output` 又对同一 sealed bytes 调用 `_validate_complete_output`。validate 与 finalize
之间还引入 `finalizing`、provisional snapshot 和 proxy 中间状态。

**保留不变量**：任务私有目录、只读输入、输出路径/类型/大小/文件数/秘密检查、Operation 摘要、
Artifact 注册、Task CAS、重复/晚提交、失败恢复、正式来源冻结和领域工具权限。

**处置与放弃**：S2 以 open/heartbeat/submit 替代领取、物化和两步提交生命周期；文件创建、补丁、
移动和删除仍由 Operation 精确注册的服务端工具执行，只合并有真实重复责任的表面；正式网页/PDF
证据和 TCAD 调试继续是精确注册工具。放弃 checkpoint 恢复和 validate/finalize 两步用户协议，但
不开放原生写入。平台不能隔离原生只读范围的事实继续公开。

**S2 验证**：真实通用 Agent、真实 TCAD 编码 Agent、跨任务路径、非法 bundle、未声明工具、超预算、
重复提交、late submit、重启、当前合同漂移和 Artifact 父链。

**回退边界**：必须作为一个 Worker 协议代际原子回退，不允许旧写协议与新 submit 并存。

### 13.6 折叠账本 E：准入、资格和修订

**精确表面**：

- `operations/spec.py::OutputPortSpec.allowed_input_usages`、端口级 cohort/approval 字段，以及保留但
  重新明确为消费端认识论角色的 `InputPortSpec.usage`；
- `operations/catalog.py` 对上述字段的编译和 provider 展开；
- `operations/invoke.py::{direct_revision_ports}` 和编译任务投影；
- `interfaces/mcp_root_operation_routes.py::{_validate_operation_input_cohorts,
  _validate_producer_output_admission,_validate_direct_revision_request}`；
- `interfaces/mcp_root_shared.py::claim_admissible`、任务 labels 和实例投影中的同名逻辑；
- 通用、曲线、TCAD 和 table 插件中的字段重复声明。

**重复责任**：下游 Operation 已用输入端口声明自己消费什么，生产者又枚举下游用途；资格组信息复制
到每个端口；完整对象修订还被核心从端口形态推断并走特殊准入。科学用途因此由控制标签而非显式
下游行为决定。

**保留不变量**：数据合同、current、传递父链、完整资格集合、独立审查、revision 不继承 verdict、
preflight/invoke 等价和 invoke 重检。

**处置与放弃**：S3 删除 output allowed usages、producer-side admission 和 claim-admissible；保留
input usage 并投影到 Worker assignment 和任务授权摘要；每个 Operation 当前至多声明一个资格组；
revision 使用普通完整对象 Agent Operation。放弃“生产者授权未来用途”和仓库外旧输出字段兼容。

**S3 验证**：explore 可作为明确未晋级输入但不能获得正式资格；stale、mixed cohort、未知 provider、
旧 revision verdict、TOCTOU 和未知合同均失败关闭；核心无 Schema/角色/插件名特判。

**回退边界**：Operation ABI 单代际回退；禁止长期双字段、自动翻译或兼容 catalog。

### 13.7 折叠账本 F：实例和本地管理

**精确表面**：`scheduler_bindings.py` 的 proposal/session/deletion 方法及九张 scheduler 表，Root instance
路由、Root 初始化 session review、approval UI 的 instance/session decision 分支、`instance_admin.py`
和 `orphan_admin.py`。

**消费者结论**：proposal/request/candidate 三张表不是无消费者死表；Root 和 UI 共同建立了一套以
Approval 表达本地实例创建/选择的完整产品流程。删除必须是 S4 的行为替换，不能在 S1 当作死代码
删除。`scheduler_sessions` 保存不可推导的最终 session 绑定，必须保留；`scheduler_bindings`、
`scheduler_instances`、`scheduler_scientific_selections` 和 current 相关路径也承担真实权威，预设保留；
`scheduler_observations` 是否重复必须另查，S0 不批准删除。

**保留不变量**：实例创建/选择只能来自 loopback UI 明确动作，聊天不能转换；实例、绑定、current 和
历史唯一；维护前无活动任务/审批/执行且有一致性快照。

**处置与放弃**：S4 用本地 UI command 替代 Approval proposal/request/candidate 流程，决定后仍写入
既有 `scheduler_sessions`；删除确认无独立恢复事实的中间表和方法；维护改为显式离线命令。放弃会话
候选审批、在线多阶段删除和历史数据库自动迁移。

**S4 验证**：UI 来源、查询纯读、命令幂等、重启 current、活动对象 blocker、失败维护无半删除、旧
YAML/label/approval 不升级。

**回退边界**：S4 使用全新测试状态根；用户旧库只读，不做原地迁移或删除。

### 13.8 折叠账本 G：数据合同与 support Operation

**精确表面**：239 个组件中的 57 validator、10 codec、11 guard、96 resource，以及 20 个 support
Operation。主要声明位于 `general_science_*operations.py`、`general_science_*components.py`、
`curve_score`、`tcad_artifact`、`ingaas_fig4` 和 table fixture 的 plugin/operation 模块。

**消费者结论**：这些组件通过启动目录动态引用，不能按 Python 直接调用数判死；S5 必须逐引用建立
codec—schema resource—strict validator 三元组和 guard 消费图。20 个 support Operation 也不是默认
可删，只有确认它只在一个 Operation 内做帮助且无独立 Artifact/Approval/Effect 消费者时才降为组件。

**保留不变量**：插件拥有数据和科学规则；Schema 对 Agent 可见；机械校验可重复；正式工具收据可
重放；科学判断仍由 reviewer；TCAD 作者行为不合成条件 DSL。

**处置与放弃**：S5 用一个数据合同组件替代重复三件套，每个 Operation 至多一个机械结果校验入口；
放弃旧组件标识和仓库外直接引用。support Operation 逐项决定，不设机械数量目标。

**S5 验证**：全插件编译、数据合同 Schema 投影、完整 bundle、工具收据、父链、独立 reviewer、盲
插件和 installed wheel；组件必须实质净减且不能出现第二注册表。

**回退边界**：按单个插件原子回退，不允许旧三件套与新 DataContract 并行注册。

### 13.9 S0 自动化证据

在 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2`、禁用 pytest cache 且无并行的条件下：

- 架构约束、installed entry point、四插件组合、盲插件、目录阶段、精确 Worker 派发、正式
  `spawn_agent` 配置、未启用 Worker 实验和部署/平台共 75 项通过；
- 计划与发布投影聚焦测试 36 项通过；
- 干净源发布为 251 个文件，manifest 覆盖除自身外 250 项并全部校验通过；
- `git diff --check` 通过；
- 33 项约束登记与本计划映射均为 33 项，无缺项。

未执行真实 Agent、真实浏览器、真实 solver、全仓 292 项 Operation 回归和完整 pytest；它们不属于
只读 S0 的必要证据，分别保留给 S2、S4/S6、精确执行授权和跨边界生产阶段。

S0 可重放命令为：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
pytest -q -p no:cacheprovider \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/operations/test_catalog_installed_entrypoint.py \
  tests/operations/test_h2b_domain_boundaries.py \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_worker_exact_dispatch.py \
  tests/operations/test_codex_task_dispatch.py \
  tests/operations/test_codex_worker_process.py \
  tests/artifact_agent/test_deploy_scripts.py \
  tests/artifact_agent/test_platform_configuration.py
sha256sum -c --quiet \
  docs/plans/evidence/R5_S0_PRODUCTION_SOURCE_SNAPSHOT.sha256
git diff --check
```

### 13.10 首轮独立审查打回与修订

首轮独立审查结论为“打回”，没有放行 S1。四项阻断已按最小边界修订：

1. S2 不再用原生写入替代服务端文件门禁，只压缩生命周期和重复编辑协议；
2. S3 保留消费端 `InputPortSpec.usage`，只删除生产者侧 `allowed_input_usages` 和下游授权；
3. S4 明确保留 `scheduler_sessions` 最终绑定，只替换 proposal/request/candidate 审批包装；
4. 表清单补齐 TCAD 插件后为 33 张，并新增当时的176文件生产源摘要和四个目录摘要。

首轮报告属于对当时精确候选的历史见证，不能因本文修订自动变为通过。第二轮必须重新核验上述四项。

### 13.11 第二轮独立审查打回与修订

第二轮独立审查再次结论为“打回”，没有放行 S1。第一轮的 input usage、session 绑定、33张表和目录
摘要已确认闭合，只剩两项机械一致性问题：

1. 总架构图残留“原生编辑”，现已改为“任务私有输入只读→服务端受控编辑→一次性原子提交”；
2. 176文件摘要漏掉运行提示、部署入口和正式 skill，现扩展为216文件，加入 `roles/`、`deploy/`、
   TCAD skill 和三个发布工具。

第二轮报告同样绑定修订前候选，不自动转为通过。第三轮只需重新核验这两项、摘要完整性以及是否
引入新的表述冲突。

### 13.12 S0 当前门

第三轮独立审查已经通过，并且只放行 S1。通过候选的计划摘要为
`2114c1b44ad43446a0826ac1e8c1cc969762c85373f249ab136f15abf2e74e8e`，来源清单摘要为
`99641e05e2080730f2b0cbfa3007afeab15906d4bcb2f8d1d0fa36a99fbccf65`；75项冻结回归和216项来源摘要
均由独立审查复算通过。S2—S6、H7 和真实外部执行均未放行。

### 13.13 S1 实现候选与冻结证据

S1 已按第三轮 S0 审查放行的边界完成实现，但在独立审查签发结论前仍是候选，不能标记为通过，
也不能据此进入 S2。精确起点清单为
`R5_S1_START_SOURCE_SNAPSHOT.sha256`，共216项，清单摘要为
`deb7cbe2b358f94e8e04c6717af15f0e7e673cc09e1b835f4140e41cbca9629d`；当前生产终点清单为
`R5_S1_END_SOURCE_SNAPSHOT.sha256`，共208项，清单摘要为
`fcebc33985214e87bbb2a65e4169345440ef7586af2845f2bcf12a0b25e9f9d4`。

本阶段只有三项生产降级：

1. 生产 `builtin_plugin.py` 只保留六个 Worker 文件生命周期组件；三种架构编译证明 Operation、
   对应组件和实现全部移入独立测试 fixture wheel，核心 wheel 不再导出测试插件；
2. `table_observation` 的六个插件文件整体移入 `tests/fixtures/plugins/table_observation_plugin/`，继续
   承担外部插件安装、组合编译和调用证明，但不再进入产品源码发布；
3. 从未接入正式 `spawn_agent` 路径的 `codex_worker.py`、`agent_dispatch.py` 及其专项测试和现场脚本
   整体移入 `experiments/worker_process_v2/`。实验代码可单独运行，但不属于产品命名空间、wheel、
   clean release 或当前能力声明。

起止清单的八个消失项恰好是表格插件六个文件和两个实验模块；生产范围内只有
`builtin_plugin.py`、根 `pyproject.toml` 和发布构建器发生内容变化。生产 Python 从150个文件、
59,200行降为144个文件、57,207行，净减6个文件、1,993行；其中核心从34,840行降为33,321行。
项目插件组合现有225个组件、46个 Operation（public=26、support=20），默认产品组合有216个组件、
45个 Operation（public=26、support=19）；减少只来自不再参与产品组合的证明插件，没有改变正式
Operation 的身份或摘要。

在7 GiB虚拟内存上限、`MALLOC_ARENA_MAX=2`、禁用 pytest cache 且串行执行的条件下：

- 核心安装隔离与干净发布负例聚焦40项通过；
- `tests/operations` 当前全部280项通过；迁出的12项 Worker 进程实验在实验目录独立通过；
- `tests/artifact_agent` 全部37项通过；
- clean release 为243个文件，manifest覆盖除自身外242项并全部校验通过；
- 两个产品 wheel 不可导入实验模块，core-only wheel 不可导入架构 fixture；测试 fixture wheel
  仍能独立安装并编译三种证明 Operation；
- `git diff --check` 和208项终点生产摘要校验通过。

S1 没有修改 preflight、invoke、Task/Artifact 生命周期、权限模板、资格、审批、执行或科研内容，
因此没有伪造新的真实 Agent 或科学效果证据。独立审查需要确认上述三个移动确实没有动态生产
消费者、测试夹具没有成为第二产品注册表、实验代码没有从发布边界泄漏，并复算精确起止差异；
通过前 S2—S6、H7 和发布冻结继续暂停。

### 13.14 S1 独立审查结论

独立 critic 对摘要为 `6e3f0d115e0dace4c2d65750d8f417012b59cf78f9d55d147c06e6a6945dcc70`
的精确候选给出“通过”结论。它复算216→208的全部生产差异、产品 wheel、fixture wheel、entry point、
clean release、正式 `spawn_agent`/Worker proxy 和33项约束，并独立通过80项跨边界、280项
Operation、37项 Artifact/部署/UI 以及12项实验回归。报告见
`reviews/R5_S1_PRODUCTION_BOUNDARY_INDEPENDENT_REVIEW.zh-CN.md`。

本结论只放行 S2。S3—S6、H7、R5 发布冻结和真实外部执行仍未放行；S2 必须重新完成消费者审计、
实现、机械回归和独立审查。

### 13.15 S2 起点

吸收外部 S1 审查见证后，发布构建器只发生一项状态投影变化：源发布中的 S0 审查报告被 S1 审查
报告替代，没有运行时或目录变化。该下一代生产起点以
`R5_S2_START_SOURCE_SNAPSHOT.sha256` 冻结，共208项，清单摘要为
`96740af4dcce821dc376adfb41e9f8bd5cf026a566c7bc8e2b4caf3d67347e53`。S1 终点清单继续见证受审
候选，不因后审查状态吸收而重写。

S2 先执行16个基础 Worker 工具、TaskService 方法、注册组件、角色提示、部署入口和测试消费者的
只读审计。只有证明生命周期、编辑原语和领域能力的精确边界后才允许修改生产协议；“最终只有三个
生命周期动作”不等于把所有文件编辑和领域工具塞进三个巨型接口。

### 13.16 S2 消费者审计与最小实现边界

16个现有基础 Worker 工具可按真实职责分为四组：

| 组 | 当前工具 | 生产消费者事实 | S2 结论 |
| --- | --- | --- | --- |
| 生命周期 | claim、materialize、heartbeat、validate、finalize | 22个 Agent Operation 重复注册 materialize/validate/finalize；heartbeat 由21个注册；claim 是路由固有入口 | 编译期按 `executor.kind=agent` 固有派生 open/heartbeat/submit，不再作为插件组件重复声明 |
| 受控文件编辑 | begin/chunk/commit、text patch、JSON patch、delete、move | 三段写和 text patch 由22个 Agent 使用；三段通道同时承担超过64 KiB的大 patch；JSON patch/delete/move 只由3个 TCAD author 使用 | **S2 完全保持现有流式 create/patch 与四个窄编辑工具**，不以工具数量目标破坏大文件合同 |
| 通用或领域工具 | PDF、Python analysis、web evidence | PDF 由7个产品 Operation 注册；analysis/web 当前产品消费者为0；web 有插件注册正例，analysis 尚无外部插件成功调用正例 | 保持可注册能力；为 analysis 补外部 fixture 成功调用；新 Router 不再把未注册能力列给 Worker |
| 手工 checkpoint | checkpoint | 3个 TCAD author 声明，真实生产/测试/现场调用为0；TCAD role 和物化 `patch_contract` 仍含模型指令 | 同时删除工具、组件、方法、role 和物化合同语义；自动失败、工具结果和 finalization snapshot 保留 |

当前路由会把16个基础工具全部列给每个 Worker，再靠调用期 capability 拒绝未注册工具。S2 改为只
列出三个固有生命周期工具和该 Agent 类型从编译目录得到的注册工具；同角色不同 Operation 仍可能
因 Codex 0.150.1 的原型继承限制看到并集，但精确任务 capability 继续在调用期拒绝越权。这里不把
提示约束误写成技术隔离。

第一次独立设计审查已打回“单次原子 create”方案：完整 JSON-RPC 请求受1 MiB上限约束，无法承载
2 MiB科学主输出和8 MiB TCAD文件；原三段协议还承担大 patch。因此 S2 不再修改任何受控文件
编辑名称、参数、服务端上传状态或字节上限。修订后的最小协议冻结如下：

1. 编译器拥有唯一、领域无关的 `AgentLifecycleProtocol` 值对象，字段只有协议版本，以及三个工具的
   名称、输入 Schema 摘要和 capability。它进入 Agent `PermissionTemplate` 与 Operation 摘要；
   Task authority、Codex profile、编译提示、Router 列表/门禁和部署探针只读该投影。插件不能声明、
   覆盖或复用固有生命周期名称；协议变化提升 ABI 并改变所有 Agent Operation 摘要；
2. `worker_open_assignment` 原子完成精确 claim 与任务私有目录 materialize；若 materialize 中断，
   同一 Router 可幂等重试 open，不再暴露 claim 后未 materialize 的常规步骤；
3. `worker_heartbeat` 只续租，不能延长绝对预算；
4. `worker_submit_result` 在一个 Worker 调用内完成完整 bundle 校验、不可变 seal、Artifact/信号登记
   和 Task CAS；校验失败返回结构化错误并保持可修订，内部 seal/finalizing 状态继续承担崩溃恢复，
   但不再成为 Worker 的二段协议；
5. 同一 Router 在 finalizing 中重复 submit 时从已封存 manifest 继续；同一 Router 在完成响应丢失
   后重复 submit 返回同一 completed 结果。daemon 或 Router 重启后，`worker_open_assignment` 可用
   同一个 exact dispatch 恢复持久 session：只接受原 task、attempt、worker、proxy、authority 和
   session，绝不创建新 session 或延长 absolute/finalization deadline；
6. finalizing 恢复允许原 session 绝对期限已过、但既有 finalization hard deadline 尚未到期的唯一
   情况，并只允许继续 submit，不能恢复编辑、heartbeat 或领域工具；completed 恢复只返回同一有界
   completion receipt。错误 proxy、capability、attempt、authority、session 或已过 hard deadline
   一律失败关闭；若未能在 hard deadline 内恢复，既有协调器将 attempt 标为 timed_out，显式 retry
   后下一 attempt 只读物化 `validation_rejected`、`operation_tool_candidate/result` 或
   `finalization_candidate` provisional snapshot，不把它冒充正式 Artifact；
7. begin/chunk/commit 继续同时承载流式 create 和 patch，保持1 MiB传输边界下的分块、服务端状态、
   摘要/长度检查与最终原子发布；text patch、TCAD JSON patch/delete/move 均保持独立，不合成
   action 联合体；
8. PDF、analysis、web 和 TCAD debug 等能力维持 Operation 精确注册。analysis/web 即使当前产品
   Operation 消费者为0，也只作为插件可注册组件存在，新 Router 不向未注册 Worker 暴露；S2 增加
   一个外部 fixture 注册并成功调用 `worker_run_analysis` 的正例；
9. 删除手工 checkpoint 时，同步删除通用 role、TCAD author role、materialized patch contract、
   `ProvisionalSnapshotManifest.reason`、`AssignmentProvisionalContext.reason`、fallback capability 和
   activity allowlist 中的 checkpoint 语义。自动 `validation_rejected`、
   `operation_tool_candidate/result` 和 `finalization_candidate` snapshot 继续保留。

预期直接删除的生产表面只包括：四个重复生命周期组件、手工 checkpoint 工具/组件/方法、四个旧
Worker 生命周期名称和相关角色提示。文件编辑协议本阶段不动。不会删除 Task/Artifact CAS、自动
provisional snapshot、最终 bytes seal、独立 review、资格、人工审批、Effect 授权、网络域限制或
插件 workspace policy。

实现验收新增：协议字段变化改变 Agent Operation 摘要；profile、Router、Task authority 三方工具
与 capability 完全一致；materialized assignment 不含退休 checkpoint；校验失败后可修正；seal
前后故障、CAS 前后响应丢失、重复 submit、跨 Router/daemon 的 exact finalizing/completed 恢复、
错误 proxy/capability/attempt/authority/session、原绝对期限与 hard deadline 边界、下一 attempt
provisional 恢复和 proxy 完成停止均有回归。未通过独立复审前不修改生产 Worker 协议。

### 13.17 S2 首轮设计审查打回

首轮设计审查绑定计划摘要
`e1dafdb5d355a70491cc14ce06b39e62334be8f17c547c3397d18f68a7f9b815`，结论为“打回”。四项阻断是
单次写超过 Socket 上限、遗漏流式大 patch、固有生命周期缺少唯一编译权威，以及 checkpoint/工具
消费者账本不完整。完整报告见
`reviews/R5_S2_PROTOCOL_DESIGN_INDEPENDENT_REVIEW.zh-CN.md`。

当前修订选择风险最小的边界：S2 不动文件协议；新增一个最小生命周期编译值对象而不是三个分散
常量；完整删除手工 checkpoint 的工具与模型指令；明确 submit 的响应丢失、finalizing 和下一 attempt
恢复责任。修订候选仍未获实现授权，必须重新独立复审。

### 13.18 S2 第二轮设计审查打回

第二轮审查绑定摘要
`5d804bffe5e42c54f32d57126ee8e3ac811d3074d8092df70fbbdf488f6e498e`，确认文件协议、消费者计数和
生命周期单一投影方向已闭合，但再次“打回”跨 Router/daemon 的 finalizing 恢复和 checkpoint
Schema/fallback/activity 遗漏。完整报告见
`reviews/R5_S2_PROTOCOL_DESIGN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`。

第三轮候选现在要求 exact dispatch 恢复同一个持久 session，finalizing 恢复不延长任何期限且只允许
submit，completed 只返回完成收据；并把 checkpoint 从 Schema、fallback capability 和 activity
allowlist 一并删除。`worker_run_analysis` 作为保留插件能力新增外部 fixture 成功调用正例。第三轮
独立复审通过前仍不得开始实现。

### 13.19 S2 第三轮设计审查通过

第三轮独立审查绑定摘要
`5b5b3c0dc874c8b7489b776d5d0862b657f2ce0f2a3a5c0755860dcb4cc791e4`，确认两轮阻断全部闭合，
结论“通过”，只放行 S2 实现。报告见
`reviews/R5_S2_PROTOCOL_DESIGN_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`。

实现只能按第13.16节执行；文件协议、表结构、任务终态、Artifact/资格/审批/Effect 边界均不得借机
修改。S2 候选完成机械回归和真实 daemon 恢复测试后还需独立实现审查，通过前 S3 不放行。

> 后续状态修正：上述 verdict 仅对当时“旧可靠控制器内部是否闭合”的问题有效。它已被本文件
> 开头的 R5-L 纠偏取代，不再授权继续把该协议实现为默认主干；精确调度和服务端文件保护作为
> `HardenedWorkerBackend` 候选冻结保留。
