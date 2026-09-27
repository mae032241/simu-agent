# OperationSpec 中心的最小重构计划

状态：唯一活跃的通用化重构提案；R0—R4 已通过。R5-0—R5-F 已完成实现并经独立审查通过；
R5-G 证据阶段已通过，真实假设批评为 `blocked`。“专业 Agent 直接输出完整新对象”的修订简化
计划第二轮独立复审已通过；D0、D1 已通过独立实现审查；D2 最后消费者迁移也已独立审查通过。
D3 经两次实质打回和一次机械冻结修正后已通过独立审查；D4 与唯一一次 D4-H2 均以全新 critic
`blocked` 结束并按停止门关闭。R5-H H0—H6 已依次通过独立审查，H6-C 第二轮总收口复审确认六个
零消费者表面删除、唯一发布清单和职责边界闭合。现新增 R5-S 生产代码裁剪提案；S0 首轮独立审查
打回的原生写入、消费端输入语义、最终 session 绑定和精确冻结四项问题已按最小边界修订；第二轮
确认语义和权威问题闭合，仅打回总图残留表述和摘要覆盖范围。两项机械问题修复后，第三轮独立审查
已通过且只放行 S1；S1 的三项生产降级已经独立实现审查通过。S2 的旧可靠控制器设计虽经第三轮
审查证明合同闭合，但因默认路径复杂度反噬已暂停。替代方案
`R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md` 的 L0—L6 已全部实现，并通过两位未参与实现的
独立最终审查者复核；R5 删除旧重量阶段完成。R6 扩展性验收和 R7 真实 TCAD/文档仍未开始，
不得继承 R5 的审查结论。

基线：`baseline/8765-codex@404aeb1`

目标：在 8765 已跑通的多角色科研闭环上，通过一个轻量、可编译的
`OperationSpec` 收敛分散注册和领域胶水，将控制面恢复为最小上下文授权、质量校验、
谱系与副作用门禁，而不是科研流程编排器。

## 1. 这次重构要回答的问题

这次不再试图先设计一个能描述所有学科的“科学世界模型”，而只回答：

> 如何把现有很重的科研流程控制器，改造为一个智能体主导科学判断、
> 领域能力可通过单一入口注册、低风险探索足够轻、高风险执行仍然可信的
> 通用科研智能体？

8765 是行为基线，不是目标架构。这次可以破坏历史源码和状态兼容，但不得
破坏已证明有价值的科学与副作用边界。

## 2. 8765 的可取之处与实证的重量问题

### 2.1 保留的行为

- 调度智能体根据科学问题选择角色，而不是由数据库状态机生成科学判断；
- 多角色分工中保留“问题提出/产出”和“独立审查”两类责任，但不把它们写死成阶段 DAG；
- `evidence_extractor`、`ideator`、`critic`、`evidence_auditor`、
  `experiment_designer`、`diagnostician` 六个通用角色；
- TCAD 的 deck author 与独立 reviewer；
- 不可变 Artifact、来源、Worker 去身份且默认拒绝的最小上下文和受控文件提交；
- 确定性变换不产生科学判断，外部适配器不改写科学对象；
- 精确人工审批、幂等执行、结果完整性和失败恢复。

### 2.2 必须删除或收敛的重量

| 证据 | 问题 |
| --- | --- |
| `scheduler_topology.py` 同时维护 `_ADVICE` 和 `_CAPABILITIES` | 通用核心仍静态写死 TCAD 角色、阶段和产物 |
| `platforms/roles.py` 同时扫描源码插件、读取 entry point，并按角色名特判输出 collection | 角色发现、输出合同和领域行为混在一处 |
| `runtime.py` 再按角色名补充 output profile | 同一能力需要多处同步 |
| `mcp_daemon.py` 直接 import TCAD adapter | 通用启动路径知道领域实现 |
| transform、role pack、execution 各有入口 | 插件不是一次注册，运行时仍需要补线 |
| TCAD 和 curve-score `pyproject.toml` 声明了实际不存在的 `operation_specs.py` | 安装元数据与可运行能力已经断裂 |
| `tasks.py` 6952 行、`mcp_root.py` 2616 行、核心 context policy 764 行 | 科学特例、生命周期和分派责任过度聚集 |

新设计不得只在这些表面之上增加一个更大的包装类。

## 3. 本轮明确不做什么

- 不建设 Claim/Evidence/Uncertainty 全局科学图；
- 不完整枚举 `OperationSpec × 输入绑定`；
- 不建设 `CapabilityBundle` 或活动/历史双目录作为新权威；
- 不新增 OperationIntent、ScientificAction、Candidate、DecisionSummary 等持久化对象；
- 不为 33 项架构约束逐项建立 Schema、Receipt 或状态；
- 不新建一套科学资格、current 或事件存储内核；
- 不先做生产迁移、在线切换、插件签名、分布式调度或 Claude Code 适配；
- 不为了抽象统一而重写已稳定的 CAS、SQLite、Worker 文件沙箱和 TCAD runner。

## 4. 目标架构：一个行为原子，一个注册入口，一个调用入口

```text
用户目标 + 当前科学 Artifact
            ↓
调度智能体（提出本轮科学问题，判断该做什么）
            ↓ 提出 operation_id + 语义输入绑定
不可变 OperationCatalog
            ↓ 统一预检与调用
  ┌─ Agent executor     → 现有 Task/Worker
  ├─ Transform executor → 现有确定性变换
  └─ Effect executor    → 现有 Approval/Execution/Adapter
            ↓
不可变 Artifact + 现有生命周期记录
            ↓ 结果准备进入正式科学链时
独立审查 operation；必要时再进入人类 UI 审批
```

角色之间不直接对话，也不建立新的消息总线或可变黑板。每次交接都通过受控文件完成：
上一角色的结果冻结为 Artifact，调度智能体只把选定 Artifact 以任务内科学别名投影到
下一 Worker 的只读输入目录。调度消息只负责唤醒 Worker，不携带科学内容。

## 5. 最小运行概念

### 5.1 `Artifact`

继续使用 8765 已有 Artifact、CAS、schema、来源和修订父链。核心不强制所有学科
共享一套科学节点类；领域语义通过类型化 Artifact 和角色内容表达。

### 5.2 `OperationSpec`

`OperationSpec` 是唯一新增的核心行为抽象。它是不可变声明，不是执行器、
调度器、状态机或巨型业务类。

首版字段仅保留：

```python
OperationSpec(
    operation_id,
    version,
    description,    # 给调度智能体的科学用途、适用边界和非用途
    executor,       # agent / transform / effect + 已注册组件引用
    inputs,         # PortSpec：语义名、schema、codec、usage、交付方式/上限
    outputs,        # PortSpec：schema、codec、数量、用途上限
    consequence,    # explore / scientific / external
    review=None,    # 独立审查 operation；可选的人类审批呈现合同
    guards=(),      # 少量可复用准入函数引用
    limits=None,
)
```

输出 validator、角色 prompt、transform callable、执行 adapter factory、必要的领域预检和
可选呈现器都是独立窄组件。它们必须由同一个 `PluginDefinition` 显式登记；
`OperationSpec` 只持有插件内组件编号，编译时解析它们。

它是一个声明式行为闭包：凡是会改变可见输入、可用工具、网络权限、可读写路径、输出、
执行方式、审查义务或后果等级的组件及版本，都必须能从这份 spec 闭合解析并进入编译
摘要；不得依赖按角色名、插件名或 schema 名在别处偷偷补行为。闭包不等于巨型类，spec
本身没有业务方法和可变状态。工具、工作区和网络声明分别放在嵌套的 `executor` 与
`limits` 合同中，不增加第十一个顶层字段。

`PortSpec` 允许插件选择 JSON、CSV、文本、图片或文件束等通信格式，但核心始终只处理
通用文件信封：端口名、相对路径、媒体类型、schema/codec、大小和内容摘要。核心不解析
领域字段来决定科研结论。codec 和 validator 也是窄组件；它们不能建立自己的 Artifact、
任务或审批状态。

### 5.3 `CompiledOperation`

插件安装后的进程启动期编译得到的内存投影：已解析 callable、已验证端口、已闭合的
权限模板和已合并的默认拒绝策略。它不持久化，不是第二套能力权威。运行时唯一目录是
`operation_id -> CompiledOperation`。一次进程只编译一次；任务执行期间不热加载、不重新
解释 spec，也不允许调度智能体或 Worker 编译、替换或扩展 operation。

`OperationCall` 只是 MCP 请求 DTO，`OperationResult` 只是对现有 Task/Transform/Execution
结果的投影；首轮都不建表、不建 CAS 对象。operation id、version 和编译摘要写入现有
任务与 Artifact 谱系元数据，使插件升级后仍能解释历史结果，不另建版本状态机。

### 5.4 两阶段编译与任务最小授权

`OperationSpec` 的生命周期明确分为两个阶段：

1. **启动期编译**：控制面从唯一插件入口读取全部声明，闭合端口、组件、工具、工作区、
   网络、validator、审查与资源上限，生成不可变 `CompiledCatalog`；失败则整个服务拒绝
   启动。
2. **调用期绑定**：`operation_invoke` 只把某个 `CompiledOperation` 的输入端口绑定到精确
   Artifact，把抽象工作区绑定到本次任务私有路径，并据此生成本次任务的最小授权投影。
   这是数据绑定，不是重新编译；它不能增加端口、工具、网络权限或资源上限。

任务最小授权投影不是新实体、表、注册表或资格事实，只是 compiled operation 与本次精确
输入的派生结果。控制面内部部分进入现有 Task 不可变合同和幂等 fingerprint，供恢复时重建
相同权限；Worker 可见部分保持去身份，只包含任务内别名、允许的路径和能力说明。它至少
闭合：

- 可读取的精确输入、`full/on_demand/handoff_only` 暴露方式及总字节上限；
- 唯一任务私有读写根、输入只读路径和输出可写路径；
- 本 operation 可调用的 Worker 工具及其模式/参数边界；
- 默认关闭的网络与搜索；显式开启时的用途、来源范围和数量上限；
- prompt/skill 资源、模型、时限、输出 schema、文件数量和大小；
- 恢复或重试必须保持不变的权限摘要。

所有维度都默认拒绝：未声明输入不可读，未声明工具不可见且服务端仍拒绝伪造调用，未声明
网络不可用，任务目录外不可读写。`on_demand` 只表示对已经绑定的精确输入延迟读取，不是
运行时搜索 Artifact 或扩大上下文。Worker 发现缺少输入或能力时，只能返回缺口；由调度
智能体另建一次 operation 调用，不能在当前任务内增权。

### 5.5 审查与 UI 合同

“有问题提出者和结果审查者”约束的是科学责任，不是要求每个文件转换都复制一对
Agent。具体规则是：

- 调度智能体提出本轮局部科学问题并选择产出 operation；
- 智能体产出的新证据、主张、实验设计或科学解释在升格前，
  `review.reviewer_operation` 指向一个独立审查 operation；它必须读取被审结果的精确
  Artifact，而不是产出者的聊天摘要；
- `explore` 微操作默认可以不审查，但结果不能直接成为正式证据、结论或外部执行输入；
- 结果一旦准备升格为正式科学输入，编译后的 admission 必须验证所需独立审查已经闭合；
- 纯确定性转换不机械增加审查 Agent；它由固定算法、validator、输入谱系和可重放测试负责，
  只有算法或适用性本身成为科学争议时才调度独立审查；
- 优先复用 critic、evidence auditor 和领域 reviewer，不为每个阶段复制新角色类。

需要人类判断时，`review.approval` 可以声明 `ApprovalContract`：精确 subject 输出端口、
领域摘要字段、呈现组件、问题、选项到核心决定的映射及理由要求。编译器据此生成 UI
读取投影和校验规则，避免 UI 为 TCAD 或某个角色写特判。

但以下字段不允许插件自定义：审批绑定的精确 Artifact 内容、审批者身份、决定时间、
决定是否已应用、幂等与恢复规则，以及 `external` 必须审批等安全下限。呈现器只能读取，
不能改写科学文件；插件选项只能映射到核心固定的接受、拒绝、请求修订或带例外接受语义。

## 6. 单一插件注册

所有插件只允许一个 entry-point group：

```toml
[project.entry-points."scidiscovery.plugins"]
tcad = "tcad_artifact.plugin:PLUGIN"
```

```python
PLUGIN = PluginDefinition(
    plugin_id="tcad",
    components=(
        ComponentSpec("deck_agent", "agent", "tcad_artifact.agents:DECK_AUTHOR"),
        ComponentSpec("deck_validator", "validator", "tcad_artifact.project:validate"),
        ComponentSpec("deck_workspace", "workspace", "tcad_artifact.workspace:DECK"),
        ComponentSpec("project_materializer", "transform", "tcad_artifact.materialize:run"),
        ComponentSpec("execution_adapter", "effect", "tcad_artifact.execution:factory"),
        ComponentSpec("execution_view", "projector", "tcad_artifact.views:execution"),
    ),
    operations=(
        OperationSpec(
            operation_id="tcad.deck.author.v1",
            executor=ComponentRef("deck_agent"),
            outputs=(OutputPortSpec(validator=ComponentRef("deck_validator")),),
            catalog_scope="public",
            # 其余行为闭包字段在实际声明中完整填写
        ),
        ...,
    ),
)
```

示例只说明注册关系，不是最终 Python 构造器签名。插件先登记小组件，operation 再组合
这些组件；编译器不会从实现模块中反射或猜测未声明功能。

`PluginDefinition` 是一次安装注册的完整声明，不是科学对象或运行时状态。它同时登记
领域子功能和由这些子功能组成的 operations。每个 operation 通过插件内稳定编号引用
小组件，不再要求插件分别使用全局入口注册：

- role pack；
- transform adapter；
- context policy；
- output profile/collection；
- readiness/topology；
- execution adapter；
- renderer；
- scheduler 领域顺序。

运行时只读取已安装发行包的该 entry point，不再扫描源码目录。编译器一次发现插件、
登记并解析全部组件、检查插件/组件/operation 重名、依赖版本、端口与审查闭包、codec、
输出 validator、审批呈现合同、执行副作用和资源上限。存在引用缺失时启动失败；8765 中
“元数据声明 operation，实际模块不存在”的断裂必须由等价的缺失组件负例在此门立即捕获。

单一编译结果内部可以有一个私有、不可变的组件索引，供 operations 调用；它与公开
operation 映射同属一个 `CompiledCatalog`，没有第二个发现入口、生命周期或配置权威，
也不向调度智能体公开领域内部函数。

## 7. 智能体、控制面和领域插件的分工

### 7.1 调度智能体

- 理解用户目标和当前证据；
- 判断当前最有价值的矛盾、缺口或不确定性；
- 从 catalog 选择已有行为，或先使用通用本地沙箱撰写临时方法；
- 给出任务内科学问题、精确输入绑定和科学理由；
- 根据结果用途选择独立审查，但不能通过省略审查把探索结果升格为正式科学输入。

它不必在控制面生成的完整候选集中选择，也不使用领域化阶段号。

### 7.2 科学 Worker

- 执行证据提取、创意、批判、审计、实验设计、代码编写和诊断；
- 只看到 operation 输入端口的 task-local 科学别名；
- 只获得本 operation 声明并在调用时绑定的文件、工具和网络权限；
- 返回科学内容，不决定资格、current、审批或执行终态。

### 7.3 控制面

- 验证 operation 存在、输入类型、来源、当前性、权限和后果等级；
- 在调用期从 compiled operation 派生并强制执行默认拒绝的任务最小授权；
- 把 operation 分派到现有 Task、Transform 或 Execution 子系统；
- 继续拥有 Artifact、任务、审批、执行、幂等和恢复事实；
- 不根据领域内容排序科学行动，不生成科学结论。

### 7.4 领域插件

- 在一个 `PluginDefinition` 中登记领域 operation，以及解析器、codec、validator、guard、
  prompt/skill 资源、工作区、领域工具、projector、transform 和副作用 adapter 等窄组件；
- 不提供固定 workflow、下一角色、科学排序或第二套 lifecycle；
- 不复制 Artifact、approval、task、current 或 execution 状态；
- workspace、worker tool、codec 和 validator 只能消费控制面传入的精确句柄，不能获得
  Artifact 全库、共享工作区根或控制服务对象来绕过 operation 边界。

不是每个领域函数都应暴露为 operation。只有可被调度智能体独立选择、具有完整输入输出
和可观察结果的能力才是 operation；只服务于另一个 operation 的 PLX parser、deck
materializer 或 UI projector 是已登记组件。这样既能统一安装和编译，又不会让调度目录
被实现细节淹没。

组件内部不跨框架边界的私有辅助函数不登记。换言之，注册的是稳定扩展边界，不是每个
Python 函数：调度能力是 operation，框架会直接调用的插件实现是 component，component
内部实现细节仍由插件自行封装。

## 8. 按后果分级，不让探索承受高风险协议

| `consequence` | 默认行为 |
| --- | --- |
| `explore` | 本地无副作用；不人工审批；结果为非权威 Artifact，不能直接支持下游 claim |
| `scientific` | 精确输入、validator 和谱系；智能体新产出的科学内容须独立复核，确定性派生物机械验证；仅在存在价值/风险选择时进入人工审批 |
| `external` | 除上述边界外，必须有精确执行授权、幂等请求、适配器隔离和结果完整性 |

后果等级由核心对 executor 类型和安全策略做下限校验；插件不能把外部副作用降级成
`explore`。

临时方法不建新的 `MethodProposal` 状态机。首版只提供一个通用沙箱 operation：代码、
依赖、输入和随机种子冻结，输出始终为 `explore`。需要进入正式科学链时，另调用已注册的
独立审查/提升 operation，不暗中自动升格。

## 9. 8765 能力到 operation 的首批映射

| 行为 | executor | 所属 |
| --- | --- | --- |
| `science.evidence.extract` | Agent / `evidence_extractor` | 内置科学插件 |
| `science.idea.generate` | Agent / `ideator` | 内置科学插件 |
| `science.idea.criticize` | Agent / `critic` | 内置科学插件 |
| `science.evidence.audit` | Agent / `evidence_auditor` | 内置科学插件 |
| `science.experiment.design` | Agent / `experiment_designer` | 内置科学插件 |
| `science.result.diagnose` | Agent / `diagnostician` | 内置科学插件 |
| `science.local.analyze` | Agent + 本地沙箱 | 内置科学插件 |
| `tcad.deck.author` | Agent / `tcad_deck_author` | TCAD 插件 |
| `tcad.deck.review` | Agent / `tcad_deck_reviewer` | TCAD 插件 |
| `tcad.project.materialize` | Transform | TCAD 插件 |
| `tcad.project.package` | Transform | TCAD 插件 |
| `tcad.study.execute` | Effect | TCAD 插件 |
| `tcad.result.score` | Transform | curve-score 插件 |

这张表不是工作流。调度智能体可根据当前科学矛盾跳过、重复或并行任何
非互斥 operation；核心只拒绝类型、谱系、权限或副作用不合法的调用。

## 10. 实施阶段

不再使用 Wα/A1—A5 命名。每一阶段都必须产生可独立回退的小提交，并在进入下一阶段前
同时审查实现正确性、约束不变量和复杂度是否真正下降。

### R0：建立 8765 行为特征测试

不重跑已经完成的 Fig.4 科学闭环，只为重构将触碰的稳定行为增加最小黑盒测试：

1. 通用角色加载与一次 Worker 文件完成；
2. 一次确定性 transform 的输入、输出和谱系；
3. 一次无真实副作用的 execution lifecycle；
4. TCAD author/reviewer 的角色和输出合同；
5. 一次精确 Artifact 的 UI 审批与决定观察；
6. 安装态 role/transform/execution 发现结果；
7. 当前额外输入、共享路径、角色级工具和默认网络权限的实际可见边界。

验收：测试只固结已观测行为，不把静态 TCAD 拓扑或分散注册当成必须保留的合同。

### R1：实现最小 `OperationSpec` 与编译器

- 新增单一职责的 spec、port、executor ref 和 catalog compiler；
- 建立内置 science plugin，与第三方插件经过同一编译路径；
- 编译时检查重名、空端口、不可解析组件、codec/validator、审查闭包、审批呈现合同、
  不匹配 executor、过低后果等级，以及 Agent 的输入/路径/工具/网络权限是否闭合；
- 只允许控制面在启动期编译一次，调度智能体和 Worker 不持有编译入口；
- 不修改数据库，不接入科学 readiness。

验收：一个安装态测试插件能编译；构造的缺失组件、冲突 operation 和非法后果降级均在
真实启动路径失败闭合。

### R2：建立统一 operation 调用面

- 对调度器提供 catalog 查询、预检、调用和状态/结果查询；
- Agent executor 复用 `TaskService`，Transform executor 复用现有 adapter，Effect executor 复用
  `ExecutionService/ExecutionBridge`；
- `OperationCall` 中只有 operation 名、语义输入绑定和有限调用参数；
- Agent 调用只做精确输入和单任务路径绑定，生成默认拒绝的任务授权投影，不重新编译；
- 先保留底层专用服务，不在这一步重写任务、transform 和 execution 持久化。

验收：同一入口分别跑通一个 Agent、Transform 和无副作用假 Effect，失败原因稳定可诊断。

### R3：迁移通用科学角色

- 将六个通用角色登记为内置 science operations；
- 将输入输出 codec/schema、validator、collection、文件交付、审查关系和资源上限收进
  各自 spec；
- 由每个 operation 生成独立工具、网络和单任务文件权限，不再继承角色级权限并集；
- 删除 `roles.py` 和 `runtime.py` 按角色名的输出特判；
- 保留 prompt 文件作为窄资源，不把 prompt 内容填入 spec 字段。

验收：新增一个通用 Agent operation 只需 spec、prompt/执行组件和测试，不修改 Root、
`TaskService`、通用调度器、UI 或平行 allowlist；产出者与独立 reviewer 只通过冻结文件
交接，不能互相发送科学消息。

### R4：迁移 TCAD 与 curve-score 插件

- 为 TCAD 和 curve-score 各提供一个 `scidiscovery.plugins` 入口；
- 把 author、reviewer、materialize、package、execute 和 score 声明为 operations；
- 将现有 context policy、validator、transform 和 adapter 作为窄组件复用，不先重写它们；
- 删除 daemon 对 TCAD adapter 的直接 import；
- 安装器只验证已选插件的 operation catalog，不再按领域 profile 写断言。

验收：只安装核心时无 TCAD import；安装 TCAD 后目录出现完整 TCAD operation；两种安装都能启动。

### R5：删除分散注册和静态拓扑

详细施工和验收以
`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 为唯一实施记录。在 R1—R4 已有行为
对等测试后，按“完整参数纵切面迁移 → 旧权威删除 → 领域特判迁出 → 删除后拆分 → 运行时门禁
→ 有界科学效果回归”的顺序：

- `scidiscovery.agent_role_packs`、`scidiscovery.transform_adapters` 和断裂的
  `scidiscovery.operation_specs` 入口；
- 源码目录扫描插件角色；
- `_ADVICE`、`_CAPABILITIES` 和精确的角色运行时 profile 残留；科学 payload 中的任务模式建议
  类型不在删除范围；
- 按 role/schema/profile 猜测能力的分支；
- 已经由 spec 端口和 consequence 规则覆盖的重复 context/readiness 白名单；
- Root 对审批生产者族、端口名和修订 operation id 的硬编码；
- 已迁移科学行为的旧 Root 创建入口；
- TaskService 中已经能由插件 validator、workspace hook 或 runtime component 承担的领域逻辑。

验收：运行时只有一个插件入口和一个 `CompiledCatalog`；其私有组件索引只能被已编译
operation 使用；核心没有领域顺序；
通用核心总代码行数相对 8765 基线至少净下降 10%；一个盲审批插件使用未知端口名和生产者族时
不修改 Root、Task、Scheduler、UI 或安装器；缺失运行时配置在 preflight 阶段明确失败；冻结小型
TCAD 任务的真实多角色 Operation Agent、重放机械链和独立科学评价没有相对 R4/8765 的严重退化。

### R6：验收轻量扩展和 TCAD 回归

1. 用 tests 内的最小表格分析插件验证新领域/新能力无核心改动接入；
2. 验证调度智能体可根据不同科学矛盾跳过或重复角色，不被固定 DAG 拒绝；
3. 对输入、兄弟任务路径、工具、网络和恢复执行最小授权穿透负例；
4. 只在上述结构闭合后，再进行一次经授权的真实 TCAD 回归，不重复 R5-G 已完成的重放链。

验收：表格插件不修改 `src/scidiscovery`、通用 scheduler 或 UI；TCAD 仍保持独立
author/reviewer、确定性评分和外部执行授权。

## 11. 复杂度预算

下列任一超标都不允许进入下一阶段：

1. R1—R4 新增数据库表数：`0`；
2. 新增通用科学实体类型数：`0`；
3. 插件 entry-point group：`1`；
4. 运行时 compiled catalog：`1`，其中公开 operation 映射和私有组件索引同源冻结；
5. 组件独立 entry-point group：`0`；
6. 普通无副作用 operation 所需的核心特例修改：`0`；
7. 第二个测试领域插件所需的核心、scheduler、UI 修改：`0`；
8. 低风险本地探索的人工审批次数：`0`；
9. R5 完成后，通用核心代码行数必须相对 8765 基线净下降；
10. 新架构取消的注册、特判和拓扑代码行数必须大于新增的编译/分派胶水；
11. `OperationSpec` 不含执行方法或可变状态，首版顶层字段不超过十个；
12. 每个任务和产物记录 operation id、version 与编译摘要，不增加新持久化权威；
13. 任务授权投影新增数据库表、顶层注册表和独立生命周期数均为 `0`；
14. 每个 Agent operation 的默认额外输入、额外路径、额外工具和默认网络权限数均为 `0`。

## 12. 33 项约束的使用方式

33 项约束仍是不可退化的验收矩阵，但它们是行为结果约束，不是类图或持久化
对象清单。每一阶段只需证明：

- 唯一权威、不可变性、谱系、外部证据、Worker 隔离、默认拒绝和确定性边界未被破坏；
- 资格、current、人工决定、CQRS、外部副作用和恢复仍有一个权威实现；
- 插件不建立第二状态机，不将领域规则反向泄漏到核心；
- 安全、资源、UI 和迁移边界只保留有现实风险证据的部分。

若一项约束只能通过增加新实体、平行权威或领域特例来“通过”，必须先检查是否
能由现有 Artifact/Task/Approval/Execution 与 operation guard 组合实现。

## 13. 保留、收敛、删除和延后

| 处置 | 内容 |
| --- | --- |
| 保留 | Artifact/CAS、Task/Worker、Approval、Execution、确定性变换实现、TCAD runner、八个已证明角色 |
| 收敛 | role output、context delivery、validator、transform、adapter、资源上限和少量 guard 收入 operation 编译路径 |
| 删除 | 分散 entry points、核心 TCAD 拓扑、按 role/schema/profile 特判、重复 readiness/准入白名单 |
| 延后 | 科学图、完整候选枚举、多代际迁移、插件签名、分布式调度、Claude Code |

## 14. 停止与打回规则

出现以下任一情况，本计划必须停止扩展并回到上一阶段：

- `OperationSpec` 开始包含业务方法、状态或调度循环；
- 调度智能体或 Worker 可以在任务执行中编译 operation、加载插件或扩大上下文；
- 为通信格式、审查或 UI 分别增加平行顶层注册表，而不是作为 spec 的端口/组件引用编译；
- 为了运行一个 operation 又新增第二个 readiness、qualification 或 current 权威；
- 新领域仍需要修改核心候选器、Root 白名单、通用 scheduler 或 UI；
- 普通本地分析需要人工审批或发布正式插件；
- 为了兼容旧设计而保留两套注册和调用路径超过一个阶段；
- 每轮只增加编译和协议对象，却没有删除旧分支和旧注册点；
- 任何 Agent operation 依赖共享工作区根、默认 `allow_additional`、角色级全量工具或默认联网；
- 测试只证明合同自洽，不再测量任务成功、插件改动量、调用摩擦和 TCAD 能力。

## 15. 总完成标准

只有同时满足以下条件，才能说这次重构达到目标：

1. 新增领域 operation 或领域子功能组件不修改核心和通用 scheduler；
2. 插件只有一个注册入口，启动后只有一个同时闭合 operation 与私有组件的
   `CompiledCatalog`；
3. 科学行动和局部问题由智能体提出，核心只做合法性和副作用准入；
4. Agent 间只有不可变文件交接，没有携带科学内容的直连消息；
5. 准备进入正式科学链的产出有独立 reviewer，低风险探索不需人工审批；
6. 插件可自定义通信 schema/codec 和领域 UI 投影，但不能自定义审批事实或降低安全门；
7. 精确谱系、Worker 隔离、确定性/智能体边界和外部执行授权不退化；
8. TCAD author/reviewer、工程物化、执行、评分和诊断仍可通过注册行为闭合；
9. 第二个最小领域插件证明接入不产生纵向产品重开发；
10. 通用核心代码行数、注册点数和领域特判数相对 8765 基线明显下降；
11. 每一阶段的独立审查同时通过正确性、33 项约束不退化和复杂度预算；
12. 每个子智能体的输入、路径、工具、网络和资源权限都从所选 compiled operation 派生，
    默认拒绝且不能在任务内扩大；恢复后权限摘要不变。

本计划的核心成功信号不是“新增了 OperationSpec”，而是：

> 删掉了多个平行注册、领域特判和静态拓扑，同时保持 8765 的科学和执行边界。

---

## 16. 详细实施决策

本节及后续章节是本计划的可执行部分。若前文原则与具体实施步骤发生歧义，以“控制面
不做科学判断、Worker 最小授权且默认拒绝、操作规范不保存状态、单一插件入口、不新增
持久化权威、旧特判必须退出”六条为裁决依据。

### 16.1 本轮采用源码断代，不做状态迁移

- 允许新源码不兼容旧的角色、变换和执行创建接口；
- 保留 8765 数据目录只读快照，重构调试使用全新的状态目录；
- 不迁移未完成任务、审批、执行和会话；
- 已完成 Artifact 只有在新实例显式导入时才作为输入，不自动恢复 current 或资格；
- R0—R5 不执行生产切换，也不修改旧状态目录。

这使每个阶段都可通过回退源码和换回旧状态目录恢复，不需要双写、在线迁移或新旧协议
协商。

### 16.2 统一的是能力创建，不重建统一生命周期

新的调度器公开入口只统一以下三个动作：

1. 查询已编译能力；
2. 对一个精确调用做只读预检；
3. 用一个 `operation_id` 创建 Agent 任务、执行确定性变换或创建外部执行请求。

任务状态、Worker claim/finalize、失败比较并交换、审批状态、执行 start/sync/cancel 和
reconcile 继续由 8765 的现有服务负责。它们是通用生命周期命令，不是领域能力注册点。
本轮不新增 `OperationRun` 表，也不把三个成熟状态机包装成第四个通用状态机。

R5 完成后，调度器不能再直接使用 `task_schedule`、`artifact_transform` 和
`execution_request_create` 创建行为；这三条旧创建路径降为 `OperationInvoker` 的内部
调用。只读和生命周期命令继续保留。

### 16.3 一个行为变体就是一个 operation

凡是输入集合、输出格式、审查要求、资源上限或副作用等级不同的行为，首版使用不同的
`operation_id`，不再从 `context_profile`、`output_profile` 或角色名推断。例如文本证据
提取、论文图证据提取和器件参数提取是三个 operation，可以复用同一个
`evidence_extractor` 智能体类型。

这样会增加少量声明行，但能删除运行时的 profile 分派、角色特判和隐式默认。若多个
operation 后续只有文字说明不同，再在实证后合并；首版不设计变体继承系统。

## 17. 目标源码结构与责任

计划新增的通用生产文件限定为：

```text
src/scidiscovery/operations/
├── __init__.py       # 只导出稳定公共类型
├── spec.py           # 插件、组件、operation 冻结声明、规范化和摘要
├── catalog.py        # 单入口发现、编译、冲突诊断
└── invoke.py         # 统一预检与创建，复用现有服务

src/scidiscovery/builtin_plugin.py   # 六个通用角色和通用确定性操作

plugins/tcad_artifact/tcad_artifact/plugin.py
plugins/curve_score/curve_score/plugin.py
plugins/ingaas_fig4/ingaas_fig4/plugin.py
```

不新增 `registries/`、`capabilities/`、`scientific_actions/`、`workflow/` 或
`operation_state/` 包。三个通用 operation 模块总行数在 R5 验收时不得超过 1200 行。
R2 根据真实职责将原定 300/400/500 分项预算一次性重分配为：`spec.py` 不超过 320 行、
`catalog.py` 不超过 450 行、`invoke.py` 不超过 430 行，总预算没有增加。原因是原估算没有计入
原生工具策略、注册领域工具的协议检查和审查端口闭包，而统一调用复用既有生命周期后少用了
79 行预算；把这些冻结声明和启动失败检查移出声明/编译器只会制造新模块或运行期分支。
本次调整后不得再次挪用；超过上限必须先证明无法通过复用现有服务或删除兼容分支解决。

### 17.1 `spec.py`

只定义冻结数据：

- `ComponentSpec`：插件内稳定编号、组件类别、实现位置、协议版本和可选只读资源；
- `ComponentRef`：指向已登记组件的插件内编号，不直接接受任意 Python 路径；
- `InputPortSpec`：端口名、schema、媒体类型、codec、基数、用途、暴露方式和准入要求；
  暴露方式默认不可读，必须明确选择 `full/on_demand/handoff_only`，不提供
  `allow_additional`；
- `OutputPortSpec`：端口名、kind、schema、媒体类型、codec、基数、大小、validator 和
  可选 collection；
- `ExecutorRef`：`agent`、`transform` 或 `effect` 三种受限联合类型；Agent 分支同时引用
  agent、workspace、worker tool 和只读 prompt/skill 组件，未列出的工具不是隐式默认；
- `ReviewSpec`：独立审查 operation 及可选 `ApprovalContract`；
- `OperationSpec`：前文冻结的十个顶层字段；
- `PluginDefinition`：插件编号、插件协议版本、component 元组、operation 元组和可选
  配置 schema。

这些类型只做结构校验、规范化序列化和摘要计算，不导入 Task、Approval、Execution 或
任何 TCAD 类型，不包含 `execute()`、`schedule()` 或状态迁移方法。

### 17.2 `catalog.py`

只负责一次性编译：

- 从 `scidiscovery.plugins` 读取已安装发行包；
- 登记、验证并解析插件组件和只读资源；
- 验证包括输入、路径、工具、网络和资源下限在内的完整闭包；
- 生成唯一不可变 `OperationCatalog`；
- 提供按编号查询和面向调度智能体的精简说明。

它不判断当前研究阶段，不接受 Artifact 输入，也不保存调用结果。运行时不热更新；安装、
升级或移除插件后必须重启并重新编译，避免目录在任务执行中漂移。调度智能体和 Worker
没有该编译入口；它们只能查询调度器安全投影或消费一次调用的任务合同。

### 17.3 `invoke.py`

只负责把一个已编译 operation 映射到现有服务：

- Agent executor → `TaskService.schedule`；
- Transform executor → 现有 transform callable 与 Artifact 注册；
- Effect executor → `ExecutionService.create` 和现有执行桥；
- Human approval → `ApprovalService.create_request`。

对 Agent executor，它还把已编译权限模板绑定到精确 Artifact Ref 和新建的任务私有路径，
生成现有 Task/Worker 合同；绑定结果不得比模板更宽。它共享同一个 `_preflight()` 实现供
查询和写入调用，写入前再次运行；不得维护一套只供 readiness 使用的宽松规则。

### 17.4 `builtin_plugin.py`

内置科学能力也作为 `scidiscovery.plugins` 的一个普通入口加载。该文件登记通用组件、
角色 operations 和端口，但不定义固定角色顺序。核心发行包与第三方插件经过相同编译器，禁止
内置能力通过私有注册捷径获得优先级。

## 18. 操作规范的精确闭包

### 18.1 调度智能体可见说明

catalog 对调度智能体只投影：

- `operation_id` 和 version；
- 一句话科学用途；
- 适用边界与明确非用途；
- 输入端口的科学语义、数量和可接受 schema；
- 输出端口的科学语义；
- 后果等级、资源上限和是否需要独立审查/人工审批。

不投影 Python 路径、插件安装目录、内部 ID、哈希、数据库表或执行适配器秘密配置。

原 `scientific_readiness` 在 R5 缩减并更名为纯只读 `scientific_inventory`：只列出当前
实例可见的科学 Artifact、schema、审查/审批状态和显式 current 绑定，不再返回
`suggested_capabilities`、领域 blocker 或阶段推断。调度智能体结合 inventory 与 catalog
自行选择少量 operation，再对所选调用执行精确 preflight；核心不枚举笛卡尔候选集。

### 18.2 输入端口

调用者提交 `端口名 -> 一个或多个实例内语义 Artifact 名`。控制面解析为精确 Ref 后：

1. 检查数量、schema、媒体类型和大小；
2. 检查端口声明的 `usage` 与交付方式；
3. 仅在端口显式要求时检查独立审查、人工资格、current 或父链关系；
4. 为 Worker 生成任务内别名：单输入使用端口名，多输入使用
   `<端口名>_001`、`<端口名>_002`；
5. 把精确 Ref 绑定到本次任务只读路径，生成默认拒绝的任务授权投影；
6. Worker 看不到实例语义名和任何控制面身份。

插件不得根据 Artifact 的控制名改变科学行为。需要领域选择时必须来自 Artifact 内容或
operation 本身的显式端口，而不是名称前缀。

不存在“额外上下文”后门：未出现在 compiled input ports 中的 Artifact 即使与当前实例、
角色或 schema 匹配也不能进入任务。`handoff_only` 只向调度器传递有界信号，Worker 不得
读取原始字节；`on_demand` 只能读取调用创建时已绑定的对象。producer 的草稿、临时文件、
聊天和其他任务工作区均不因 reviewer 身份而自动可见。

### 18.3 输出端口和 codec

首版内置三个 codec：

- `json`：严格 schema 的 `output/result.json`；
- `file`：一个声明媒体类型和大小上限的文件；
- `bundle`：一个 manifest 加有界文件集合。

领域插件可通过 spec 引用额外 codec，但 codec 只能在任务私有目录与字节之间做确定性
编码/解码，不能联网、审批、执行外部命令或写控制状态。输出 validator 和 bundle
validator 从端口声明解析，不再根据 role/schema/profile 二次猜测。

任何含运行时跨字段规则的 validator 都必须同时登记面向 Worker 的语义合同资源，并由
编译器投影到输出 schema 的 `x-scidiscovery-semantic-constraints`。缺少投影时 Agent
operation 不得派发；不能让 Worker 只能从 finalize 拒绝文本反推单位、枚举、引用闭包、
唯一性或跨字段条件。纯机械的文件大小、摘要和路径检查不需要伪装成科学语义说明。

每个产物的现有谱系元数据至少记录：

- `operation_id`；
- operation version；
- compiled spec digest；
- 精确输入父 Ref；
- executor 类别。

发行包版本和已安装运行时身份负责绑定 Python 实现；prompt、schema 和其他只读资源的
摘要直接进入 compiled spec digest。插件运行配置在启动编译时固定；组件提供不泄露秘密的
配置身份摘要并进入 compiled digest。密码、令牌、私有路径和完整命令配置不进入 catalog
的调度器投影，外部执行仍由精确 capability Artifact 绑定实际可执行边界。

### 18.4 可复用子组件，而不是巨型 operation 类

首版只允许以下窄组件类别。每个组件先由 `PluginDefinition.components` 登记，再由一个或
多个 operation 引用：

| 组件 | 责任 | 禁止事项 |
| --- | --- | --- |
| codec | 文件与端口值之间的确定性编解码 | 科学判断、状态写入、副作用 |
| validator | 校验单个输出或完整文件束 | 修补内容、选择下一步 |
| guard | 对精确调用做纯准入判断 | 排序候选、写数据库、调用外部系统 |
| agent executor | 生成现有 Task 合同、任务授权和 Worker 配置投影 | 自己运行模型、实时编译或保存新状态 |
| transform executor | 调用一个确定性函数 | 调用模型、审批或外部执行 |
| effect executor | 验证并构造现有 ExecutionRequest | 绕过审批、解释科学结果 |
| workspace | 物化任务私有的领域文件树 | 读取共享工作区/未声明输入、登记 Artifact |
| worker tool | 提供一个有界领域工具调用 | 自行扩权、越过任务授权、直接写控制状态 |
| projector | 生成有界调度信号或安全 UI 文档 | 改写原始 Artifact 或生成 HTML/脚本 |
| resource | 绑定 prompt、schema、skill 或静态模板字节 | 动态执行、运行时下载 |

组件没有独立 entry point。operation 使用 `<plugin_id>:<component_id>` 引用；默认只能
引用本插件组件，跨插件引用必须声明插件依赖和组件的公开可复用属性。编译器拒绝无人
引用的组件，避免单一入口内部重新长出杂物仓库。这里的类别来自 8765 已存在的真实
职责；新增类别必须同时指出将删除或替代哪一组现有硬编码分支。

R3-A 的 Agent 运行时只实际消费一个 prompt resource；额外 `executor.resources`、prompt 的传递
resource 依赖和自定义工作区目录在尚无任务私有物化协议时均于编译期拒绝。后续若要启用 skill
或静态模板，必须先实现精确物化与真实 Worker 读取验收，不能仅把引用写入摘要。当前工作区合同
也固定为既有 `inputs/output/scratch` 三目录，避免插件声明一个文件生命周期并未执行的目录名。

所有插件 Python 组件属于安装时信任边界：本轮保证已安装插件不能通过框架授予 Worker
未声明上下文，不声称能安全运行恶意插件代码。组件接口只接收端口值、任务私有路径或
受限调用句柄，不接收 ArtifactService、数据库连接、共享项目根或完整 catalog。若未来要
运行不受信插件，应另做进程级沙箱与签名，不把它混入本轮最小重构。

## 19. 单一插件编译算法

编译器固定执行以下步骤：

1. 读取已安装 distribution 的 `scidiscovery.plugins` entry point，按插件编号排序；
2. 加载 `PluginDefinition`，验证编号与 entry point 名一致；
3. 验证插件协议版本、声明依赖和安装版本；
4. 登记组件并拒绝同插件重复编号、非法跨插件引用和无人使用的组件；
5. 展开 operation 并拒绝重复 `operation_id`，不允许先到先得或核心优先覆盖；
6. 规范化端口和 ComponentRef，拒绝空端口、重复端口、未登记 codec 和任何额外输入默认；
7. 对每个 Agent operation 闭合其静态权限模板：工具、工作区、网络、prompt/skill、模型、
   输出和资源上限；缺失项按拒绝解释，不从角色默认补齐；
8. 导入所有可达组件并检查其最小协议，不调用科学或副作用实现；
9. 验证 agent prompt、schema 和其他资源存在且可读；
10. 验证 reviewer operation 存在、输入能消费被审输出，并拒绝强制审查环；
11. 验证 effect executor 的 consequence 必为 `external`；任何组件声明外部写入时同样
   强制提升，插件不能降级；
12. 验证人工审批合同的 subject 端口、选项映射、理由要求和安全 UI projector；
13. 对规范化 spec、所有可达组件、权限模板、资源摘要、非秘密配置身份、插件版本和核心 operation
   ABI 计算摘要；
14. 冻结一个同时包含公开 operation 映射和私有组件索引的 `CompiledCatalog`。

任一步失败都阻止控制服务启动，并给出插件、operation、字段和稳定 reason code。不得
跳过坏 operation 继续启动，也不得回退到源码目录扫描。

插件安装、升级和移除只在服务停止且该插件没有非终态 Task/Execution 时允许。安装器在
替换 wheel 前检查现有任务/执行记录中的 operation id/version/digest；存在活动引用时
失败关闭。升级失败保留并恢复上一 wheel 与配置。终态历史 Artifact 和审批不要求旧插件
继续安装，使用核心安全原始视图读取；但不能用新版本组件重新 finalize 旧版本活动任务。
本轮不设计热卸载、热升级或组件 disposal 协议。

负例至少覆盖：缺失模块、缺失属性、错误组件类型、重复插件、重复组件、重复 operation、
无人引用组件、未知 codec、端口冲突、额外输入默认、未声明工具、非法共享工作区、未受限
网络、reviewer 不闭合、审查环、缺失 prompt、effect 降级、UI subject 不存在和插件依赖
缺失。

## 20. 统一调用与最小准入

### 20.1 调用 DTO

首版 `operation_invoke` 输入只允许：

```text
name                 调用者选择的实例内语义名
operation_id         catalog 中的精确操作
inputs               端口到 Artifact 语义名的绑定
instruction          仅 Agent operation 使用的局部科学问题
parameters           spec 显式声明的少量有界参数
on_conflict          reject 或 create_revision
```

调用者不能再提交 role、context profile、output profile、validator、schema、资源上限、
审批选项、executor 或 adapter。所有这些都由 compiled operation 决定。行为合同变化必须
发布新的 operation version，而不能靠调用参数暗改。

### 20.2 永远执行的通用检查

- 当前进程已绑定一个研究实例；
- operation 存在且 compiled digest 与服务启动目录一致；
- 语义输入全部解析为当前实例中的精确不可变 Artifact；
- 端口数量、schema、媒体类型、大小和 codec 匹配；
- instruction/parameters 在 spec 限额内；
- executor 组件可用，资源预算没有超过核心硬上限；
- Agent 的工具、网络和路径权限来自 compiled 权限模板，且没有调用参数可以覆盖；
- 幂等 fingerprint 包含 operation id/version/digest、精确输入、instruction 和 parameters；
- effect 的外部审批与幂等边界不可绕过。

### 20.3 仅由 spec 显式开启的检查

- 输入必须是 current；
- 输入必须经过指定独立 reviewer；
- 一组输入必须在同一次人工审批中接受；
- 输入之间必须具有特定父链；
- 某一纯 guard 必须通过。

### 20.4 Agent 调用期绑定

Agent operation 创建任务时，控制面执行一次纯派生：

```text
CompiledOperation 的静态权限模板
        + 精确 Artifact 输入绑定
        + 新建的单任务工作区路径
        = 本次任务最小授权投影
```

投影写入现有 Task 合同所需字段并进入任务 fingerprint，不新增 `WorkerGrant` 表、服务或
生命周期。Worker assignment 只暴露去身份结果；工具代理同时用控制面内部结果做服务端
校验，不能只相信客户端隐藏按钮或模型提示。任务 claim、代理恢复和同一 attempt 的 broker
重连必须复用同一权限摘要；重试若需要新增输入或工具，必须创建新 revision/task，而不是
修改活动任务。

### 20.5 明确删除的准入行为

- 根据“上一阶段是否完成”决定下一步；
- 用静态 TCAD 工作流推断 readiness；
- 根据角色名补输出 profile、collection 或资源限制；
- 根据 schema 名触发未声明的领域 cohort；
- 根据名字中的 `latest`、revision 大小或任务完成时间推断 current；
- 因为结果尚未人工审批而禁止本地 `explore` 分析；
- 自动把调度智能体建议变成资格或人工决定。

`operation_preflight` 与 `operation_invoke` 调用同一检查函数。前者只返回
`admissible`、稳定 reason code 和缺失端口/门禁；后者在持有现有创建锁后再次检查并写入。

## 21. 文件通信、独立审查和审批 UI

### 21.1 Agent 文件交接

Agent operation 继续复用任务私有目录，但由 compiled ports 生成目录：

```text
task-workspace/
├── assignment.json
├── inputs/<port-or-port-index>/...
├── schema/<output-port>.schema.json
└── output/...
```

- `assignment.json` 只含原始目标、局部科学问题、任务内端口别名、文件位置和资源边界；
- 不含 Artifact、任务、审批、执行、会话、哈希或插件安装身份；
- Worker 进程只挂载本次 `task-workspace`：`inputs/` 与 `schema/` 只读，只有声明的
  `output/` 和 operation 专用临时子目录可写；不得把共享 Worker 根、仓库根或兄弟任务目录
  加入原生文件权限；
- Codex/Worker 配置由本次任务授权投影生成：未声明工具不出现在工具列表，未声明网络时
  关闭网页搜索和任意联网；即便客户端伪造调用，工具代理也按同一投影拒绝；
- 子智能体以不继承父对话的方式启动（Codex 使用 `fork_turns="none"`），调度器唤醒消息不
  携带科学内容；原始目标和局部科学问题只来自受控 `assignment.json`；
- 产出者和 reviewer 不直接通信；reviewer 读取产出者冻结的精确 Artifact；
- reviewer 不继承产出者 prompt、草稿、临时调试文件或工作区，只读取自己端口明确绑定的
  被审 Artifact 和独立科学上下文；
- Worker finalize 后才能生成下游可用 Artifact，暂存文件不能成为调度证据。

### 21.2 审查责任

默认配对如下，但它们是 operation 间的审查关系，不是固定 DAG：

| 科学产出 | 独立审查责任 |
| --- | --- |
| 文本/图像/参数证据 | `evidence_auditor` |
| 假设组合 | `critic`，必要时并行 `evidence_auditor` |
| 实验设计 | 复用 critic 智能体类型，输出已有通用 `ScientificReview` |
| TCAD 源码工程 | `tcad_deck_reviewer` |
| 诊断和科学解释 | 复用通用 `ScientificReview`，只在结论准备升格时执行 |
| 确定性评分和物化 | validator、谱系和可重放测试；默认不启动审查 Agent |

调度智能体可以在探索中跳过 reviewer，但该输出端口保持 `explore`。当它要作为正式证据、
实验计划、工程准入或结论输入时，下游 operation 的端口声明必须要求精确 reviewer Artifact。

### 21.3 由 spec 编译审批合同

`ApprovalContract` 声明：

- 审批种类和问题模板；
- 哪些输入/输出端口构成精确 subject cohort；
- 允许的领域选项以及到核心固定决定语义的映射；
- 哪些选项必须填写理由；
- 一个只读 `view_projector`。

projector 只能返回核心定义的临时 `ReviewDocument`，由文本、键值、表格、图片引用、文件
下载和折叠原始树组成。核心统一转义并渲染；插件不能返回 HTML、CSS、JavaScript 或模板。
`ReviewDocument` 不是 Artifact、数据库记录或新审批权威。

ApprovalRequest 继续绑定精确 subject、manifest 和决定 nonce，只增加编译合同编号/摘要
到现有不可变请求；不新增审批表。实例创建和会话绑定属于核心自身审批，不经过领域插件。
外部执行的“授权/要求修改”安全语义由核心强制，插件只能提供领域摘要。

## 22. 首批 operation 迁移清单

### 22.1 内置科学插件

| 新 operation | executor | 复用内容 | 独立审查 |
| --- | --- | --- | --- |
| `science.evidence.extract.v1` | Agent | `evidence_extractor` prompt/schema；原生读取文本、PDF 或图像 | evidence audit |
| `science.evidence.extract.figure.v1` | Agent | 论文图工具和现有 bundle validator | figure evidence audit |
| `science.evidence.audit.v1` | Agent | `evidence_auditor` | 无强制递归审查 |
| `science.hypothesis.propose.v1` | Agent | `ideator` | hypothesis critic |
| `science.hypothesis.criticize.v1` | Agent | `critic`/`CriticReview` | 无强制递归审查 |
| `science.experiment.design.v1` | Agent | `experiment_designer` | scientific review |
| `science.object.review.v1` | Agent | critic 智能体类型/已有 `ScientificReview` | 无强制递归审查 |
| `science.result.diagnose.v1` | Agent | `diagnostician` | 仅结论升格时 review |
| `science.object.revise.v1` | Agent | 现有 structured revision 文件合同 | 重新独立审查 |
| `science.local.analyze.v1` | Agent | 现有受限分析沙箱 | 始终为 explore |
| `science.intake.split.v1` | Transform | 已有 split transform | 机械验证 |
| `science.objective.project.v1` | Transform | 已有 objective projection | 机械验证 |
| `science.candidate.derive.v1` | Transform | 已有 candidate eligibility join | 机械验证 |
| `science.experiment.materialize.v1` | Transform | 已有 intent materializer | 机械验证 |
| `science.revision.apply.v1` | Transform | 已有 structured revision apply | 机械验证 |
| `science.evidence.unchanged-receipt.v1` | Transform | 已有 unchanged evidence receipt | 机械验证 |

首版不再保留调用时的 `structured-revision`、`legacy-experiment-portfolio` 等输出 profile；
不同合同使用不同 operation id。

### 22.2 TCAD 插件

| operation 家族 | 复用组件 | 迁出核心的内容 |
| --- | --- | --- |
| `tcad.evidence.parameters.extract/audit/cover` | 参数 schema、coverage、提取/审计 prompt | device parameter role/schema 特判 |
| `tcad.deck.author.initial/revise/runtime-failure` | author prompt、任务私有 deck workspace、debug tool | role/context profile 分派和 TaskService TCAD import |
| `tcad.deck.review.initial/revision/provenance` | reviewer prompt、review validator | reviewer readiness 和 schema 特判 |
| `tcad.project.materialize/compare/review-validate/package` | 现有 materializer、packager、diff | transform profile registry |
| `tcad.execution.capability-bind` | 现有 capability discovery | daemon/root 中 TCAD 名称判断 |
| `tcad.study.execute` | 现有 ExecutionService、Bridge 和 adapter factory | daemon 直接 import TCAD adapter |
| `tcad.runtime.attest/control-equivalence` | 现有确定性代码 | readiness 中 TCAD 分支 |
| `tcad.result.diagnose/diagnose-error` | diagnostician + 曲线分析工具 | core context profile 特判 |

TCAD operation 可以共享同一个 author 或 reviewer 智能体类型。区别来自各自端口、workspace、
工具、validator 和审查合同，不复制角色类。

### 22.3 Curve Score 插件

现有每一个公开 transform profile 映射为一个 operation，包括：

- SProcess log/PLX 规范化；
- 多序列 PLX bundle；
- 论文图证据 v1/v2 bridge；
- reference coverage；
- curve consistency；
- 通用 curve score；
- 历史 SProcess log score 只在确认 TCAD 回归仍使用时保留，否则删除。

`CurveScoreTransformAdapter` 可以暂时作为内部组件继续存在，但不再作为 entry point。

### 22.4 InGaAs Fig.4 插件

它作为项目示例插件处理，不得进入通用核心：

- 若冻结 TCAD 回归仍依赖其 transform，则迁移为一个普通单入口插件；
- 若全部能力已经由 TCAD 与 curve-score operations 覆盖，则删除该插件并在历史计划中记录；
- 两种选择均不得在核心添加 `ingaas`、图号或论文专用判断。

## 23. 分阶段施工清单

### R0：冻结真实基线，不重复科研闭环

目标：知道重构必须保住什么，并暴露当前文档和源码不一致处。

修改范围：只增加特征测试、测试夹具和文档状态说明，不改生产行为。

任务：

- R0.1 记录基线 commit、Python 版本、已安装包和单入口生产启动命令；
- R0.2 为 core-only 与 core+TCAD+curve-score 构建安装态 wheel 夹具；
- R0.3 特征化六个通用角色和两个 TCAD 角色的 prompt、输出 schema、context 与资源上限；
- R0.4 跑通一次最小 Agent 文件生命周期：schedule → dispatch → claim → materialize →
  validate → finalize → status；同时记录 8765 基线没有 `task_reconcile`，不得在特征测试中
  虚构该步骤；
- R0.5 跑通一个确定性 transform，固定精确输入父链、幂等和多输出绑定；
- R0.6 跑通一个假 effect：request → UI 授权 → start → sync → outputs，不连接 TCAD；
- R0.7 固定 UI 的精确 subject、原始树、决定、刷新和重复提交行为；
- R0.8 固定 TCAD author/reviewer 的任务私有文件交接和 fake debug；
- R0.9 记录分散注册、核心领域 import、角色/schema/profile 特判和关键模块行数；
- R0.10 修正文档状态：当前源码不存在架构文档声称的 `OperationIntent`、
  `QualificationReceipt` 和 `ActiveHead` 实现；它们不得被当作本轮待保留实现或待实现目标。
- R0.11 固定当前 Worker 权限基线：默认 `allow_additional`、共享工作区根、角色级工具集合、
  默认网页搜索、`handoff_only` 和兄弟任务目录读取行为；正负结果都记录为待替换特征，不能
  把当前过宽权限误写成目标合同。

建议新增测试：

```text
tests/operations/test_baseline_agent_lifecycle.py
tests/operations/test_baseline_transform_lifecycle.py
tests/operations/test_baseline_effect_lifecycle.py
tests/operations/test_baseline_approval_ui.py
tests/operations/test_baseline_plugin_discovery.py
tests/operations/test_baseline_tcad_debug.py
tests/operations/test_baseline_worker_authority.py
tests/operations/test_baseline_role_contracts.py
tests/operations/test_baseline_structure_metrics.py
```

完成门：上述测试必须从打包后的安装目录运行；不得靠源码插件扫描通过。独立审查者确认
测试固结的是行为不变量，而不是旧注册形式、固定拓扑或领域特判。

回退：纯测试/文档提交，可直接回退。

### R1：建立最小 spec 和编译器

修改文件：新增 `operations/spec.py`、`operations/catalog.py`、
`builtin_plugin.py` 的最小空插件；根 `pyproject.toml` 增加唯一 entry point。

任务：

- R1.1 实现冻结 `OperationSpec`、`ComponentSpec` 与嵌套 port/review 声明；R3-D 根据目录降噪
  实测将 `catalog_scope` 补为显式冻结字段并把 ABI 提升为 3，不再从执行器类型或名称推断；
- R1.2 实现稳定规范化 JSON 和 compiled digest；
- R1.3 实现单入口插件发现和插件内组件登记，不写源码扫描 fallback；
- R1.4 实现三遍编译：先组件，再 operation，最后 reviewer/UI 闭包；
- R1.5 实现稳定 reason code 和完整负例；
- R1.6 内置插件只登记三个测试 operation：一个 Agent、一个 Transform、一个假 Effect；
- R1.7 给 catalog 提供调度器安全投影，验证不会泄露组件路径和配置；
- R1.8 编译每个 Agent operation 的默认拒绝权限模板；工具、工作区、网络和资源策略进入
  compiled digest，调度智能体和 Worker 均无编译入口；
- R1.9 确认启动前后所有 SQLite schema 完全相同。

建议新增测试：

```text
tests/operations/test_spec.py
tests/operations/test_catalog_compile.py
tests/operations/test_catalog_installed_entrypoint.py
tests/operations/test_catalog_negative_cases.py
tests/operations/test_catalog_projection.py
tests/operations/test_compiled_worker_authority.py
tests/fixtures/plugins/minimal_operation_plugin/
```

完成门：只有一个 entry-point group 和一个 catalog；重复/缺失/降级均失败关闭；新增数据库
表为 0；operation 核心代码不超过本节预算。独立审查通过后才能进入 R2。

回退：删除新增包和 entry point 即恢复，不触碰运行数据。

### R2：统一预检与行为创建入口

修改文件：新增 `operations/invoke.py`；修改 `runtime.py`、`mcp_root.py` 和 MCP 工具清单。

任务：

- R2.1 `open_runtime` 只编译一次 catalog，并把同一对象传给 Root 与任务装配；
- R2.2 新增 `operation_catalog`、`operation_preflight`、`operation_invoke`；
- R2.3 Agent 调用生成现有 `TaskOutputSpec`、`TaskBudget` 和 context 合同；
- R2.4 Transform 调用复用现有注册、父链和幂等逻辑；
- R2.5 Effect 调用复用 ExecutionRequest，等待现有 UI 授权；
- R2.6 将 operation id/version/digest 写入现有任务/Artifact 标签和 fingerprint；
- R2.7 保留旧三个创建工具作为一阶段内部对照，但新测试和新插件不得使用；
- R2.8 对 preflight/invoke 做竞态测试：预检后输入/current/审批变化时，写入必须重新拒绝；
- R2.9 验证只读 status 不隐式 reconcile，失败和超时仍使用现有比较并交换边界。
- R2.10 将现有 `scientific_readiness` 的对象清单和领域候选拆开；新调用路径只消费纯
  inventory，不读取旧 `suggested_capabilities`。
- R2.11 Agent 调用把静态权限模板绑定到精确输入和单任务路径；任务 fingerprint 覆盖权限
  摘要，恢复/重连保持相同摘要，任何调用参数都不能增加输入、工具、网络或上限。
- R2.12 将 Codex 原生读、写、补丁、命令、图片和网络能力，与插件领域工具统一建模为
  compiled catalog 内的逻辑工具组件；spec 引用带模式和参数边界的工具，不直接继承角色级
  工具并集。不能按精确任务路径或来源边界安全收窄的原生工具必须关闭，并由受控 Worker
  MCP/沙箱等价能力替代；普通 Worker 不得自行创建子 Agent。
- R2.13 派发必须从 exact compiled operation 生成真实 Codex agent 配置；prompt、model、资源、
  工具白名单、网络和工作区边界不能从旧角色名补入。已注册 `worker_tool` 无需修改 Root、
  TaskService、Worker 静态工具表或 Codex 角色表即可被该 operation 使用。
- R2.14 增加真实原型验收：启动控制进程和 Worker broker，经 `operation_invoke` 创建任务，再用
  `spawn_agent` 拉起真实 Codex 子 Agent。首版允许子 Agent 继承调度会话的基础 MCP、sandbox
  和 skill 权限，并由编译 prompt 明确本次只允许使用的 Worker MCP、skill 和文件能力；这只是
  可审计的行为约束，不得写成最小权限安全隔离。原型仅使用隔离数据和无真实副作用 adapter，
  真实 TCAD、生产凭据、网络写入与不可逆动作仍必须失败关闭。Agent 必须实际调用一个已登记
  插件工具、使用受控
  文件生命周期并完成 validate/finalize；同时结构化确认编译角色匹配、父会话本次零 Worker
  调用、逐任务服务端拒绝未授权 Worker capability、任务最终为 `completed`，且外部副作用仍被
  既有审批硬门阻断。直接 Python 调用、模拟 Worker 或模型响应桩不计入验收。
- R2.15 下游创建以预检绑定的精确 Artifact ref 为提交输入；current、独立审查、人工审批等
  可变谓词须在可线性化的写入边界内重验或使用 CAS 前置条件，覆盖输入重绑和并发切换负例。
- R2.16 Agent 输出 schema/codec/validator 和 Effect 的 ExecutionRequest、审批 subject、问题、
  选项、只读 projector 必须来自 exact compiled operation；未实现的组合在 preflight 稳定失败，
  不得静默改用旧 role 或固定 TCAD UI 合同。
- R2.17 所有外部字符串和资源编码异常须映射为稳定 reason code；不得捕获
  `KeyboardInterrupt` 或 `SystemExit`。
- R2.18 已实现的精确 task/attempt capability、稳定 proxy、Broker 恢复和每任务独立 Codex
  Worker 进程代码保留为下一版本的加固基座，本阶段不接默认 Root 调度入口，也不作为快速
  闭环完成门。后续启用前必须单独审查认证注入、未声明工具的平台级不可见性、原生网络关闭或
  受限、兄弟路径隔离，以及恢复后授权摘要和工具集不漂移；这些不是 R2 提示词原型能够证明的
  安全性质。

建议新增测试：

```text
tests/operations/test_invoke_agent.py
tests/operations/test_invoke_transform.py
tests/operations/test_invoke_effect.py
tests/operations/test_invoke_idempotency.py
tests/operations/test_preflight_write_consistency.py
tests/operations/test_operation_lineage.py
tests/operations/test_task_authority_binding.py
```

完成门：三个 executor 由同一入口创建且返回现有生命周期结果；没有 OperationRun 表；旧路径
只作为内部对照存在，不再增加功能。独立审查确认 invoker 没有复制 Task/Approval/Execution
状态机，并审阅真实 `spawn_agent` 原型证据：指定的领域工具与受控文件能力实际可用，任务文件
正常 finalize/reconcile，控制面仍拒绝无效输出和未授权外部副作用。审查必须明确记录：MCP、
sandbox 和 skill 白名单在本版是提示词行为约束，不是平台强制隔离。仅有 schema、服务函数或
模拟 Worker 测试时，R2 不得通过。

回退：移除三个 Root operation 工具和 runtime catalog 注入；旧创建路径仍可运行。

### R3：迁移通用角色与通用变换

> **当前版本不可覆盖的派发决策**
>
> 当前首版的 Operation Agent **必须继续使用 R2 已通过的**
> `task_prepare_dispatch → spawn_agent` 快速闭环。子 Agent 继承父调度会话的基础
> MCP、sandbox 和 skill 权限，由编译后的 Operation prompt 显式列出本任务允许和禁止的
> 工具；服务端 Task 权限、Worker 工具准入、受控文件、validator/finalize、审批和外部副作用门
> 仍是硬边界。这里的提示词白名单只是可审计的原型行为约束，不得宣称为生产级权限隔离。
>
> 每任务独立 `codex exec`、精确 capability、稳定 proxy 和 Broker 恢复代码只作为
> **下一版本加固基座**保留。本版不得把它接入默认 Root 调度入口，不得用其真实运行替代
> `spawn_agent` 完成门，也不得由独立审查者以“隔离更强”为由覆盖这一产品决策。未来若要
> 启用，必须由用户明确授权为新的版本目标，并单独审查工具可用性、MCP 隔离、沙箱、恢复和
> 中间进度保持。
>
> R3-A 曾把独立 Codex 进程接为默认 Operation 派发器。该决定与 R2.14、R2.18 以及 R2
> 通过结论直接冲突，现已撤销；原 R3-A 审查只保留对输出合同、附件、上下文和校验投影的
> 历史审查价值，**不再构成默认派发路径已通过的证据**。

#### R3-A：由 spec 生成 Agent 合同

- 让新 Operation 路径由 spec 投影 prompt、端口、输出模型、validator、collection、context、
  工具和资源上限，且不回退到角色名/profile 分支；
- 本段保留旧角色 loader 供尚未迁移的 legacy 任务使用，不提前删除其历史权威；
- 相同科学角色可以复用基础角色说明，但每个 operation 必须生成自己的工具、网络、路径和
  输入配置；不得为了复用 agent type 把多个 operation 的权限取并集；
- `TaskContextPolicy.allow_additional` 在新路径固定为 `False`；旧默认 profile 不得作为
  operation fallback；
- 首版通过现有 `spawn_agent` 启动真实子 Agent；编译提示必须使用“工具可能可见，但本
  Operation 禁止使用”的表述，不得把可见能力虚构为不存在；
- 子 Agent 继续使用既有任务私有工作区和受控 Worker 文件生命周期。原生工具、Worker MCP、
  skill 和网络的允许/禁止集合均由同一 compiled operation 投影到提示和服务端可执行门；
  首版无法在 Codex 0.150.1 角色层强制隐藏的父权限，必须如实记录为原型限制；
- 不得把 `CodexTaskDispatcher` 或独立 `codex exec` 接成 Root 默认 Operation 派发器。

#### R3-B：迁移六个角色

- 按第 22.1 节登记 evidence、idea、critic、audit、experiment、diagnosis operations；
- `roles/*.md` 仅保留 prompt 正文，不再作为行为元数据权威；`platforms/roles.py` 只保留
  尚未迁移的 legacy 角色装配，不能参与 Operation 权限投影；
- revision、figure bundle、curve diagnosis 使用独立 operation id，不再使用 output profile；
- 现有 schema/validator 原样复用，除发现实际合同缺陷外不重写科学模型；
- reviewer 读取被审精确 Artifact，产出 Artifact 的父链必须包含目标。

#### R3-C：迁移通用确定性变换

- `ScientificStateTransformAdapter` 的每个公开 profile 迁为 transform operation；
- adapter 可暂时作为内部 callable facade，catalog 成为唯一选择权威；
- `artifact_transform` 不再按 profile 搜索 adapter；
- 变换的非资格输入、父链和 payload 选择由 operation 端口/guard 声明。
- 调度目录不得把所有 Operation 平铺成一个默认列表。它从同一 compiled catalog 派生
  `public`（科研 Agent/外部行为）、`support`（确定性支撑行为）和 `internal`
  （架构自检行为）视图；默认只返回 `public`，精确调用仍统一使用 `operation_invoke`。
  分类由同一 `OperationSpec.catalog_scope` 显式声明并进入摘要；编译器拒绝未知值。不得按
  executor kind 或命名空间暗推，也不得为三类建立独立注册表。

#### R3-D：拆除 TaskService 的通用科学特判

- `runtime.py` 删除 `_role_primary_output_profiles` 和 `role_output_collection_profiles`，并删除
  已被 catalog 取代的 legacy 角色/输出装配；
- 将 figure bundle、parameter bundle、structured revision、diagnosis signal 等校验迁到端口
  validator/projector；
- TaskService 只保留通用文件生命周期、令牌、尝试、deadline、CAS、网页证据冻结和
  Artifact finalize；
- 删除按 role/output schema 选择模型与信号的分支。
- 尚未迁移的设备参数 evidence bundle、严格专用 parameter auditor 与 TCAD author/reviewer
  作为 R4 的单一显式领域桥保留；R3-D 不得为追求阶段纯净而破坏 TCAD 能力。除这四项外，
  已迁移通用 Agent 不得再生成
  legacy Codex 配置或接受 `task_schedule` 创建。

完成门：新增一个测试 Agent operation 只改插件 spec、prompt/组件和测试；不改 Root、
TaskService、UI、scheduler 或 allowlist。所有 Agent 间科学交接只经文件。该 operation
不能读取未绑定 Artifact、兄弟任务目录或调用未声明工具；无网络声明时不能搜索联网。
必须通过 R2 同型的真实 `spawn_agent` 路径完成原生代码工具、领域工具调用、受控文件写入、
validate/finalize 和 Root 完成状态确认，并结构化证明父调度会话没有代写 Worker 科学结果。独立审查同时
检查科学职责没有被 projector 或 validator 接管，且不得接受独立 Codex 进程作为本版完成门。

回退：R3-A/B/C/D 各自独立提交；未完成 D 前不删除旧 loader，但旧 loader 不允许再获得
新功能。

#### R3 总审查前置收口：三种目录视图接入

本项不是新的运行阶段、状态机或注册表。它只关闭 R3-D 之后发现的一个安装面缺口：
`catalog_scope` 已经控制目录发现和 readiness，但默认核心安装仍登记三个
`builtin.test.*` 内部操作，Codex 生成器因此仍为内部 Agent 生成普通安装配置。

冻结语义如下：

- `public` 是可由 scheduler 从当前科学矛盾选择的科研或风险行动；它可以由 Agent、确定性
  transform 或 Effect 执行。若选择会改变科学解释、比较目标、方法或外部风险，就必须属于
  `public`；
- `support` 是科学选择完成后的唯一确定性物化。编译器只允许无外部副作用、无人工审批、
  无独立科学 verdict 的 transform 进入该范围；若存在多个会改变科学含义的可选结果，应提升
  为 `public`，不能伪装成支撑操作；
- `internal` 只属于编译、安装和架构验收夹具。它不得进入默认生产插件集合、普通 Codex
  Agent/MCP 配置、scientific readiness 或普通 UI，也不得形成 claim-admissible 产物。

`catalog_scope` 只决定规划可见性，不成为第二套调用授权。`operation_invoke` 继续消费同一
`CompiledCatalog`、端口、guard、effect 和审批合同；Root 不新增 public/support/internal
operation-id allowlist。内部能力通过“测试专用插件是否被显式安装”决定是否存在，而不是由
Root 看到内部名称后再做一层手写禁止。

实施任务：

1. 将原 `builtin` 声明拆成两个同源定义：默认安装的 `CORE_PLUGIN` 只登记六个被通用科学
   operation 复用的 Worker 文件生命周期组件且 `operations=()`；显式测试轮子登记
   `ARCHITECTURE_TEST_PLUGIN` 和三个 `internal` 操作。保留 `builtin` 核心组件编号与版本是为了
   不改变 28 个已编译科学 operation 的摘要，不代表测试操作仍属生产插件；
2. 在 `tests/fixtures/plugins/architecture_operation_plugin/` 建立最小架构验收插件包，通过同一个
   `scidiscovery.plugins` entry point `architecture_fixture` 显式安装三个 `internal` 操作；不得
   新增 `scidiscovery.test_plugins` 或环境变量旁路；
3. 核心普通安装目录固定为 `public=15`、`support=13`、`internal=0`、`all=28`；测试安装在
   同一编译器上得到 `internal=3`。测试插件的存在不得改变任一通用科学 operation digest；
4. 保持 `operation_catalog()` 默认返回 public，`scientific_readiness` 只从 public 投影；
   scheduler 仅在一个 public 科学决定已经作出、需要机械物化时显式查询 support；
5. 编译器增加范围语义负例：support Agent、support Effect、带人工审批的 support operation
   启动失败；support transform 可以声明其输出进入科学链前必须完成的独立 reviewer，但该关系
   只约束升格准入，不赋予 support 科学选择、审批或审查结论；公开 transform 合法，证明范围
   不由 executor 类型暗推；
6. Codex 生成与安装校验继续遍历“已安装目录中的 Agent operation”，不添加范围过滤表；普通
   核心安装因不存在 internal operation 而自然不生成其 Agent/Worker MCP，测试安装则按同一
   规则生成并验证；
7. R4-D 才接入 UI：普通科研行动页面若展示目录，只展示 public；support 只作为父行动下的
   确定性处理/来源记录呈现，不提供科学选择或审批按钮；internal 不进入普通 UI。审批字段仍
   只从 operation 的 review/projector 合同编译，不能按 scope、schema 或领域名选择 renderer。

完成门：

1. core-only 安装中的 `builtin` entry point 只有通用组件且零 operation；`scid init codex` 后
   不存在 `builtin.test.*` Operation Agent、Worker MCP 或目录项；按精确内部 id 调用得到
   `operation_unknown`；
2. 显式安装架构验收插件后，三个 internal operation 可由同一 catalog、preflight、invoke 和
   受控文件生命周期完成无科学主张的测试；
3. 所有 readiness 候选都是 public；support 不成为候选但可经同一 `operation_invoke` 精确调用；
4. Root、TaskService、scheduler、UI 和安装器没有新增 scope→operation-id 映射、第二注册表、
   数据库表或领域分支；
5. 加装/移除测试插件不会改变 28 个生产 operation 的 digest，现有 ABI4 文本/PDF/图像证据
   只有在对应 operation digest 不变时才可沿用；摘要变化则必须真实重跑；
6. core-only wheel、core+测试插件 wheel、Codex profile、目录计数、负例、全仓回归和
   `git diff --check` 全部通过；
7. 独立 R3 总审查确认三种视图只降低规划暴露面，没有变成第二授权系统，才允许进入 R4。

回退：测试插件隔离、范围语义校验和安装/profile 断言分别提交。任一项回归只回退对应接入，
不得把三个测试 operation 恢复到默认 `CORE_PLUGIN`，也不得在 Root 新增内部 operation 名称
黑名单。

### R4：迁移领域插件、执行适配器和 UI

#### R4-A：TCAD Agent 与工作区

- 新建 TCAD `plugin.py`；
- author/reviewer 角色、三种 author 合同、review 合同、deck workspace、debug tool、
  materializer 和 finalizer 全部由 operations 引用；
- TaskService 中的 TCAD role、context profile、schema 和直接 import 分支逐一删除；
- debug 仍只在声明的 author operation 中可见，不能成为通用 Worker 工具；TCAD workspace
  组件只接收本次任务私有根和显式输入句柄，不能扫描仓库、Artifact 库或其他 deck 任务。

#### R4-B：TCAD 变换与 Effect

- materialize、compare、review validate、package、runtime attest、control equivalence 迁为
  transform operations；
- `tcad.study.execute` 引用 adapter factory 和 preparation validator；
- daemon 改用通用插件配置，例如重复的 `--plugin-config 插件编号=配置路径`，删除
  `--tcad-socket`、`--tcad-command-config` 和 TCAD import；
- 外部服务是否使用 socket 或 command 由 TCAD plugin config 和 adapter factory 决定；
- capability 发现作为 TCAD operation/component，不由 Root 根据 executor 名判断。

#### R4-C：Curve Score 与项目插件

- curve-score 所有保留 profile 迁到其单一 `plugin.py`；
- 删除 `scidiscovery.transform_adapters` entry point；
- 对 InGaAs Fig.4 执行第 22.4 节的迁移或删除决定；
- 核心安装不导入 TCAD、curve-score 或 InGaAs 包。

#### R4-D：UI 合同

- 为内置科学证据、参数证据和 TCAD execution 编写只读 view projector；
- ApprovalRequest 保存 approval contract id/digest，不新增表；
- core UI 使用固定 `ReviewDocument` renderer；
- 目录或行动页面只消费 public 投影；support 只作为已执行机械步骤和 lineage 展示，internal
  不进入普通 UI；该展示规则不参与 operation admission；
- 从 `approval_ui/render.py` 删除按 scientific foundation、figure、device parameter、TCAD
  schema 选择视图的分支；
- 未知或卸载插件的历史审批仍显示完整安全原始树，但不能重新提交一个缺失合同的新审批。

完成门：核心单独安装可启动且无领域 import；安装一个插件只增加它声明的 operations；
TCAD/curve UI 无核心 schema 特判；外部执行仍只能由精确 UI 决定授权。每个子阶段独立审查。

回退：插件迁移按包分提交；UI 在一个过渡提交中可保留旧 renderer 作为只读历史显示，
但新审批只能走 compiled contract。过渡不得超过 R4-D。

### R5：删除旧控制重量

详细方案见 `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，其七个实现门为：

1. R5-0：同步架构真相，冻结消费者、代码量、clean-wheel、测试基线和小型 TCAD 效果回归夹具；
2. R5-A：把设备参数 Schema、算法、Transform、资格审批、实验映射、author/reviewer 引用及最后
   两个 Agent bridge 作为完整纵切面迁入 TCAD 插件，随后删除旧注册、发现和 Root 创建表面；
3. R5-B：为所有 compiled Transform 输出统一调用指纹，用编译端口、精确 operation identity、
   有序父链和 revision usage 总函数解析、校验并去重审批生产者族，删除 Root 固定端口和 id；
4. R5-C：把 Root、Task、readiness、静态拓扑和上下文中的领域逻辑迁入已有插件组件；
5. R5-D：只对删除后仍不内聚的 Root、Task、Worker Router、通用插件声明和 catalog compiler
   做窄拆分，不新增服务权威；
6. R5-E/F：以两个实际 daemon 的短生命周期摘要补配置早失败与一次性一致性探针，再执行
   clean-wheel、盲插件、复杂度和独立总审查；
7. R5-G：在隔离进程中对冻结小型 TCAD 问题运行真实 Operation Agent、多角色科学链、历史原始
   solver 输出重放、单 Agent 对照和独立科学评价，确认本轮删重没有造成严重效果退化。

完成门仍是：唯一 `scidiscovery.plugins`、唯一 CompiledCatalog、唯一 `operation_invoke` 创建面、
generic core 无领域分派、core-only 不导入领域包、选定核心相对 8765 至少净减 10%，且无新增
数据库表、状态机或注册表；R5-G 只证明冻结任务无严重回归，不宣称统计优越性或三领域通用性。
每一子阶段必须独立审查通过后才能进入下一阶段。

### R6：扩展性与 TCAD 结构验收

#### R6-A：盲接入最小表格研究插件

测试插件至少提供：

- 一个读取 CSV、生成结构化观察的 Agent 或 Transform operation；
- 一个独立 review operation；
- 一种非 JSON 输出或附件；
- 一个领域审批 view projector；
- 无外部副作用。

插件必须从独立 wheel 安装。接入 diff 不得修改 `src/scidiscovery`、通用 scheduler、UI、
数据库 migration 或部署脚本；只能新增插件包、测试和选择配置。

#### R6-B：TCAD 冻结假执行链

使用冻结输入完成：

```text
author operation
→ reviewer operation
→ materialize/package transforms
→ fake external execution approval/lifecycle
→ curve-score operation
→ diagnosis operation
→ 必要时 scientific review
```

这不是重做 Fig.4 科学结论，而是证明 operation 闭包、文件交接、审查、UI、Effect 和
插件隔离的结构闭环。

#### R6-C：非固定拓扑

至少验证三条不同选择：

- 已有冻结基线时跳过 ideator/critic；
- 证据冲突时先运行 audit，再决定是否提出假设；
- 结果解释不足时重复 diagnosis/review，而不被阶段号拒绝。

#### R6-D：安装、重启和失败恢复

- core-only、TCAD-only、curve-score 依赖组合和完整组合分别启动；
- 插件缺失依赖、重复 operation、升级后 spec digest 改变均失败关闭；
- 有非终态 Task/Execution 时卸载或升级其插件必须失败，回滚后原版本仍可恢复；
- 服务重启后，已有 Task/Approval/Execution 用原生命周期恢复；
- catalog 变化不改变历史 Artifact 字节和旧审批决定；
- 未知外部提交仍走现有 reconcile，不自动重提。

#### R6-E：最小授权穿透测试

- 用两个并行任务证明任一 Worker 无法通过原生文件工具或 Worker MCP 读取兄弟任务目录；
- 为同一角色注册“可搜索”和“不可搜索”两个 operation，证明网络权限不因角色复用而合并；
- 为同一角色注册不同工具集合，证明未声明工具既不出现在配置中，伪造调用也被服务端拒绝；
- 验证未绑定 Artifact、`handoff_only` 原始字节、producer 草稿和 reviewer 外的上下文均不可读；
- 验证 broker 恢复、同 attempt 重连和正常 finalize 前后权限摘要不变；
- 验证缺少输入只能产生缺口并创建新任务，活动任务不存在增权接口。

完成门：第二领域零核心改动、TCAD 假链闭合、非固定拓扑成立、重启与最小授权负例通过、
复杂度预算通过，并由独立审查者确认没有把科学选择移入控制面，也没有以角色默认或插件
组件绕过 operation 权限闭包。

### R7：一次真实 TCAD 回归与文档收口

仅在 R6 通过后执行：

- 启动本版本自己的隔离控制、Worker 和审批 UI 进程，不连接旧 8765 服务；
- 使用已冻结且科学问题已经闭合的最小 TCAD project；
- 通过真实 UI 对精确 execution request 授权；
- 执行一次 solver 回归，验证原始输出收集、评分和诊断链；
- 对比 8765 的结构结果、输入/输出摘要、执行状态和评分，不把误差改善作为架构验收条件；
- 更新当前架构文档、安装文档和插件开发指南，历史计划继续保留历史身份。

完成门：真实副作用授权未退化，TCAD 插件没有要求核心增加领域代码；当前规范文档只描述
已经实现并测试的架构。未获得执行授权时，R7 合法停在等待审批，不能用自动代理越权。

## 24. 测试矩阵与量化基线

### 24.1 必测边界

| 边界 | 正向测试 | 负向测试 |
| --- | --- | --- |
| 插件安装 | wheel entry point 编译 | 源码目录存在但未安装时不可见 |
| catalog | 组件与 operation 确定性编译、顺序和摘要 | 重名、缺失、无人引用组件、错误协议启动失败 |
| 端口 | JSON/CSV/文件束正常交付 | schema、媒体类型、数量、大小不符拒绝 |
| Agent | 文件 finalize 后产生 Artifact | 直连消息、未 finalize 暂存、额外文件不可用 |
| Worker 合同 | schema、工具、语义约束和边界在派发前完整可见 | 隐藏跨字段 validator 不得派发 |
| 输入权限 | 仅端口绑定输入按声明方式可读 | 未绑定 Artifact、`handoff_only` 字节和动态增权拒绝 |
| 文件权限 | 仅本任务输入只读、输出/临时声明路径可写 | 仓库根、共享 Worker 根和兄弟任务目录不可读写 |
| 工具权限 | 每个 operation 获得精确工具集合 | 同角色其他 operation 的工具不可见且伪造调用拒绝 |
| 网络权限 | 显式声明范围内的搜索可用 | 未声明网络默认关闭，不因角色或插件默认开启 |
| reviewer | 精确目标父链闭合 | 审查别的 revision 或聊天摘要不能准入 |
| Transform | 可重放、父链完整 | 非确定性输出或未知端口拒绝 |
| Approval | spec 生成视图，决定绑定 exact cohort | 插件 HTML、subject 缺失、重复决定拒绝 |
| Effect | UI 授权后一次提交 | explore 降级、未授权、未知提交自动重试拒绝 |
| 恢复 | 任务/审批/执行按旧服务恢复 | status 查询不能隐式写状态 |
| Worker 恢复 | 同一 attempt 恢复相同权限摘要 | broker 重连、重试或 finalize 不能扩权 |
| 插件生命周期 | 终态历史在卸载后仍可读 | 活动任务期间升级/卸载拒绝，失败升级可回滚 |
| 隔离 | core-only 不导入领域包 | 新领域需要核心 allowlist 即验收失败 |

### 24.2 复杂度基线

R0 固定以下 8765 数值：

| 表面 | 当前值 |
| --- | ---: |
| `scheduler_topology.py` | 341 行 |
| `platforms/roles.py` | 339 行 |
| `runtime.py` | 256 行 |
| `mcp_root.py` | 2616 行 |
| `tasks.py` | 6952 行 |
| `approval_ui/render.py` | 3153 行 |
| `deploy/install.sh` | 1008 行 |
| 插件 entry-point groups | 3 个且清洁安装态 operation group 已断裂 |

R5 计算三个互补指标，精确口径以 R5-0 的可复现脚本冻结：

1. 通用核心指标：复用 R0 测试冻结的六个 Python 路径
   (`scheduler_topology.py`、`platforms/roles.py`、`runtime.py`、`mcp_root.py`、`tasks.py`、
   `approval_ui/render.py`)；删除文件按零行，迁出的同一职责必须把目标文件加入聚合，要求相对
   8765 净减少至少 10%；
2. Operation 包指标：统计整个 `src/scidiscovery/operations/`，R5 结束值不得高于 R5-0；单文件
   物理行数只作诊断，不能通过压行或移入 helper 逃逸；
3. 全仓生产代码指标：统计 `src/ + plugins/`，迁入插件的代码仍计入，不允许把移动文件冒充删除；
   新增编译/调用/projector/probe 胶水必须小于真正删除的注册、分派、兼容和静态拓扑代码。

`deploy/install.sh` 在上表保留其 8765 历史值，但作为部署表面单独报增减，不进入第一项 Python
核心 10% 分母，也不因单列而免于独立审查。

同时记录：

- generic core 中领域包直接 import 数；
- 按 role/schema/profile 的行为分支数；
- entry-point group 数；
- 新增普通 operation 所需修改文件数；
- 新插件所需核心修改行数；
- 本地 explore 到首次结果的控制调用数和人工审批数。

不以测试数量、类数量或文档页数作为成功指标。

## 25. 每阶段独立审查模板

每个 R 阶段完成后，先冻结该阶段 commit/diff，再交给未参与实现的独立审查者。审查必须
同时回答：

1. 实现是否满足本阶段明确验收项；
2. 是否破坏不可变 Artifact、精确谱系、Worker 隔离、人工决定、幂等与外部副作用边界；
3. 科学判断是否仍由调度智能体和 Worker 承担；
4. 是否新增平行 registry、状态机、readiness、qualification 或 current 权威；
5. 新领域是否仍需修改核心、通用 scheduler、UI 或安装特判；
6. 本阶段删除的复杂度是否真实大于新增胶水；
7. 测试是否经过安装后的真实入口，并包含能在目标入口失败的负例；
8. 是否出现本计划停止规则中的任一情况。
9. Agent 的精确输入、原生路径、Worker 工具和网络权限是否均由同一 compiled operation
   派生并默认拒绝；是否存在角色默认、共享根、插件组件或恢复路径的旁路。

审查结论只能是：

- `通过`：允许进入下一阶段；
- `有条件通过`：仅允许修复列出的当前阶段问题，不得进入下一阶段；
- `打回`：回到该阶段起点，重新设计或回退。

审查报告写入 `docs/plans/reviews/`，但当前状态只在本文件第 26 节更新，避免审查报告成为
另一份并行进度权威。发布候选必须先以“待独立审查”状态冻结；冻结后产生的最终外部审查报告
是该精确候选的门禁见证，不反向写入自己审查的清单。该报告及“通过”状态只在下一阶段的下一代
清单中吸收，避免清单与报告相互引用。

## 26. 实施状态记录

状态取值只有“未开始、进行中、待独立审查、打回修复、通过”。任何阶段未经独立审查
不得标为通过。

| 阶段 | 状态 | 当前证据 | 下一动作 |
| --- | --- | --- | --- |
| R0 真实基线 | 通过 | 安装态 11 项、全仓 41 项通过；首轮四项缺口闭合；`reviews/R0_8765_BASELINE_INDEPENDENT_REVIEW.zh-CN.md` 独立复审明确通过 | R1 可开始，但仍须遵守下一阶段独立审查门 |
| R1 spec/compiler | 通过 | 三轮独立审查已关闭 schema/组件 ABI、传递资源权限、Effect 人审下限、网络与总资源、reviewer codec 和稳定错误边界；专项 46 项、全仓 76 项、安装态反例、Manifest 与干净发行均通过；`reviews/R1_OPERATION_SPEC_COMPILER_INDEPENDENT_REVIEW_ROUND3.zh-CN.md` 明确放行 | 允许进入 R2；不得把静态模板当作调用期授权事实 |
| R2 统一调用 | 通过 | 用户冻结“快速闭环优先”后，父会话基础 Worker MCP 与编译提示白名单已接通。真实原型 run 6 以结构化事件确认 `spawn_agent`、专属 operation Agent 和父会话零 Worker 调用，并完成领域工具收据、受控写入、校验和封存，任务为 `completed`；专项 63 项、全仓 94 项通过。安装后 profile probe 已改为从同一 catalog 精确校验角色、MCP 与工具集；精确 capability、稳定 proxy、Broker 恢复和独立进程代码仅保留为下一版本加固基座，未改令牌数据库 schema；`reviews/R2_FAST_PROTOTYPE_INDEPENDENT_REVIEW.zh-CN.md` 第二轮明确通过 | 允许进入 R3；提示词白名单仍只是原型行为约束，真实 TCAD、生产凭据、网络写入和不可逆动作不得据此放行 |
| R3 通用角色/变换 | 通过 | R3-A—R3-D 与三视图安装面已收口。首轮与第二轮复审指出的问题已修复：独立 reviewer 在运行时按精确对象、端口和可接受结论闭合；每个输出端口显式声明最小用途，收据、差异、审查与机械报告不能冒充主张证据；同一生产者用途/复审门同时覆盖 operation 与暂留 legacy `task_schedule`；修订目标/编解码器由 operation 合同冻结；证据路径、集合限制和来源类型由任务快照执行；三个核心文件保持 320/450/430 行。core-only 为 public=15/support=13/internal=0；聚焦 134 项、全仓 167 项通过。ABI4 真实 Codex 证据为 `r3-science-agent-text-abi4-run3`，24 项全真，摘要 `68dfbae6a8e4…`；`reviews/R3_TOTAL_INDEPENDENT_REVIEW.zh-CN.md` 第二轮明确放行 | 允许进入 R4-A；保留债务按 R4—R7 边界逐项关闭 |
| R4 领域插件/UI | 通过 | R4-A 第四轮、R4-B、R4-C 与 R4-D 四个子阶段均已独立放行；最终发布复审第二轮确认 288 项候选、clean-wheel 和状态语料通过。后续功能/解耦审查以 121 项聚焦和 245 项全仓回归确认安装态主路径完成，结论“有条件通过”且允许进入 R5；审批生产者族硬编码、旧入口、巨型文件与运行时配置条件已转入 R5 | R4 历史候选保持冻结；R5 下一代清单吸收外部审查见证 |
| R5 删除旧重量 | 通过 | R5-L L0—L6 已实现；完整矩阵 `200 passed`，两位独立最终审查者分别明确 PASS；唯一 Run、Local/Hardened 两级后端、显式 current CAS、父调度器 reviewer 和旧 Task 中央路径删除证据见 R5-L 计划及 L6 证据矩阵 | 允许另行制定 R6 验收；R6/R7 不继承 R5 结论，`SEC-002` 与 25 项 pending 继续保留 |
| R6 扩展性/结构验收 | 未开始 | 无实现 | 可另行制定验收方案；开始前重新冻结范围并独立审查 |
| R7 真实 TCAD/文档 | 未开始 | 无实现 | 等待 R6 通过和真实执行授权 |

R3-A 已通过派发路径复审，R3-B 已在两轮修复后通过第三轮独立复审，R3-C 已在关闭旧通用
adapter 旁路后通过独立审查，R3-D 已通过独立终审。三种目录视图的生产安装面已经关闭。
R3 总审查首轮与第二轮反馈项已经逐项返工，第二轮已明确通过。R4-A 第二轮打回的正式参数
producer 与真实验收证据范围问题、第三轮打回的聊天第二结果通路均已返工，第四轮独立审查
已明确通过。R4-B、R4-C 与 R4-D 的四个子阶段也已依次通过独立审查。R4 只迁移领域 Agent、
工作区、工具、确定性支撑操作、执行 Effect 与审批投影，继续复用既有 Task、Artifact、Approval、
Execution 和 Worker 文件生命周期，没有新增第四套 operation 运行状态。R4 最终外部复审已
签发绿灯；其后的功能/解耦审查没有打回 R4 主路径，但把剩余旧权威、核心领域特判、巨型文件和
运行时配置问题冻结为 R5 通过条件。R5 三轮方案审查历史完整保留；R5-0—R5-F 已依次实现并经
独立审查通过。R5-G 证据阶段已通过，真实假设批评为 `blocked`；直接完整对象修订简化计划第二轮
独立复审已通过且只放行 D0。D0 候选已撤销半修复、冻结旧死锁并完成机械回归，且已通过独立
实现审查，仅放行 D1；D1 候选已完成结构总函数、通用完整对象修订、来源分离、intake 新资格和
TCAD 复用。D1 首轮独立实现审查因未知插件失败关闭矩阵和 TCAD 真实修订 Worker 生命周期不足而
打回；返工已补齐两者，并修正修订工作区错误继承旧控制证明的所有权缺陷。当前 270 项 Operation
与 307 项全仓/clean-wheel 回归通过；第三轮 D1 独立复审已经通过。D2 已迁移 curve experiment、
盲插件夹具和实际评估脚本，独立审查以 272 项 Operation、309 项全仓回归通过并只放行 D3。D3
候选已提升 ABI 8、删除六个 apply/receipt Operation、补丁 Schema/Task/Root/Transform 链，并重放
TCAD review-request 与 runtime-failure 修订；271 项 Operation、308 项全仓/clean-wheel 回归通过。
D3 独立审查经历两次实质打回和一次机械冻结修正后最终通过，只放行 D4；实验设计和发布冻结仍未
放行。随后 D4 与唯一一次 D4-H2 均以全新 critic `blocked` 结束，科学链按停止门关闭。R5-H
H0—H5 已依次通过独立审查，唯一 current、Worker 文件协议、正式 `spawn_agent` 路径、插件所有权
和审批可读性已经收口。H6-A 一次性评估归档通过独立实现审查；H6-B 发布投影在同步本节状态后经
第二轮复审通过。H6-C 完整消费者审计最终删除六个零消费者表面，没有拆分其余内聚大文件；首轮总审查打回的活动索引、
约束事实、三个漏审死方法和根目录重复清单按最小边界返工后，第二轮独立复审已明确通过。
鉴于当前生产面仍有约150个 Python 文件、59,200行、16个基础 Worker 工具及多层重复准入，现冻结
`R5_S_PRODUCTION_CODE_SIMPLIFICATION_PLAN.zh-CN.md` 作为下一候选。S0 前两轮审查打回项逐项修订
后，第三轮独立审查已经通过且只放行 S1。S1 的三项生产降级与机械回归已冻结并通过独立审查：生产 Python
为144个文件、57,207行，起点216项与终点208项来源摘要均已保存。独立实现审查已经确认生产
消费者、安装/发布边界和33项约束闭合。旧 S2 第三轮结论保留为加固 Worker 后端的设计证据，但其
默认路径实现因复杂度反噬暂停。替代它的 R5-L 已完成 L0—L6：默认 Local Run、可选 Hardened 文件
后端、独立审查/current/人工策略、TCAD 纵向切片和旧中央路径删除均已落地；两位独立最终审查者
分别明确 PASS，最新完整矩阵为 `200 passed`。R5 到此完成；R6 扩展性/结构验收与 R7 真实
TCAD/文档仍是独立后续阶段。
