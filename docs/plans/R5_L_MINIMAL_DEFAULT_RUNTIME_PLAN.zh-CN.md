# R5-L 最小默认运行主干计划

日期：2026-08-31  
状态：L0—L6 已完成，双重独立总审查通过  
前置成果：R5-S S0、S1 已完成并通过独立审查

## 1. 纠偏结论

R5-S 做对了生产边界清理、插件目录收敛、下游用途解耦方向、数据合同压缩方向，以及 Worker
生命周期对外收敛。但原 S2 仍把高可靠 Worker 代理协议作为所有科学探索的默认成本：外部虽只有
打开、心跳、提交三个动作，内部仍要求精确令牌、代理、会话、租约、封存、晚提交和跨守护进程
恢复。

这些能力不是错误，也不能直接删除：

- 精确调度和恢复能防止并发 Worker 领错任务、重复提交、重启后换任务和远程重放；
- 服务端文件编辑能在 Codex 原生权限无法真正裁剪时强制路径、大小、摘要和原子修改边界；
- 对远程、不可信、并发、长时间或不可逆任务，这些保护具有明确价值。

真正的问题是它们不应定义普通本地科研探索的复杂度下限。因此目标改为：

> 保留同一个 OperationSpec、插件入口、编译目录和调用入口，在其下提供“最小可信本地后端”和
> “加固 Worker 后端”。先用最小后端跑通通用 Agent 与 TCAD；再按真实消费者决定加固后端保留哪些
> 协议。两者是可替换运行后端，不是两套科研框架或两套能力目录。

## 2. 必须保留的成果

- 多角色 Agent 分工，作者与独立审查者分离；
- Agent 间只通过显式输入文件和正式输出文件通信；
- `OperationSpec` 是唯一行为原子，但实现仍由窄组件组成；
- `scidiscovery.plugins` 是唯一注册入口，启动期只有一个 `CompiledCatalog`；
- Artifact 字节和父链不可变；
- 工具、上下文和资源上限从编译 Operation 派生，默认不因角色或领域扩大；
- 人工决定只来自精确 loopback UI；
- TCAD、曲线、证据和通用科研插件已有领域代码；
- R5-S S1 已移出的测试夹具、示例插件和未来 Worker 实验；
- `worker_open_assignment`、`worker_heartbeat`、`worker_submit_result` 三个统一生命周期动作；
- 现有加固文件工具和精确调度实现，在消费者审计完成前冻结保留。

## 3. 目标分层

```text
科学数据层
  Artifact、输入/输出文件、父链、审查结果文件

行为声明层
  OperationSpec → 启动期唯一 CompiledCatalog

最小运行层
  operation_invoke → Run → WorkspaceBackend → Agent/Transform

可选策略层
  ReviewGate、HumanDecision、Promotion、Effect、Recovery

运行后端层
  LocalTrustedBackend | HardenedWorkerBackend | FutureRemoteBackend

领域插件层
  角色提示、Schema/数据合同、领域工具、算法、TCAD adapter
```

`public`、`support`、`internal` 仍只是同一目录的投影。运行后端不提供第二份 Operation 注册或调度
拓扑，也不得按 TCAD、角色或 Schema 名称分支。

### 3.1 唯一运行权威

`Run` 是现有 `Task` 的瘦身后继，不是与 Task 并存的新业务实体。迁移期间可以暂时复用旧表和方法，
但默认入口不得同时创建 Task 和 Run，也不得以 Task 包装 Run。最终只有一个 `RunService` 能够：

- 执行完整输出合同校验；
- 以 Run 身份生成幂等键并登记科学 Artifact；
- 写入 Run 终态和唯一完成收据；
- 在完成事务中复核被冻结的 current 锚点并如实记录是否已经过期；
- 在提交响应丢失后权威返回已有完成结果。

第一次通过完整校验的 `SealedWorkspace` 摘要必须以 CAS 绑定到 Run 的单一
`accepted_candidate_digest`；这不是新状态。后续重试只能继续登记和完成同一摘要，不得重新 seal
不同字节。校验失败的候选不绑定，工作区仍可修正；绑定成功后 backend 必须保持该快照不可变。

运行后端只管理工作区和传输私有状态，领域工具只生成候选或开发诊断；二者都不能登记正式科学
Artifact、解释 Run 终态、更新 current 或调度 reviewer。`RunService` 本身也不得更新 current 或自动
创建 reviewer Run；这两步分别属于 Root 的显式 CAS 和父调度器依据编译审查边作出的下一次调用。

## 4. OperationSpec 最小核心与可选扩展

每个可运行 Operation 的核心只需声明：

1. 标识和用途说明；
2. 执行种类、角色提示和模型；
3. 输入、输出数据合同与基数；
4. 领域或科研工具；
5. 时间、输入字节、输出字节和文件数上限；
6. 可选独立 reviewer Operation；
7. 只有确实消费项目 head 的输入才声明 `requires_current`；Operation 不声明提交时自动推进 head，
   调度器需要选择 current 时另行执行一次精确 Root CAS。

以下能力不作为每个 Operation 的必填控制字段，而是同一插件入口注册并编译进
`CompiledOperation` 的可选策略引用：

- 人工审批；
- 正式科学资格和 cohort 晋级；
- 外部 Effect；
- 远程执行；
- 高可靠恢复；
- 加固工作区。

生命周期和通用文件工具的实现属于运行后端，工具身份只在内置插件登记一次；但每个 Agent
OperationSpec 必须显式引用它获准使用的生命周期、文件工具、原生工具和领域工具。编译目录是唯一
授权源，后端只投影自己能够实现的已授权工具，不得隐式增补。领域插件不重复实现通用文件工具，只
引用内置组件，并注册真正属于该行为的工具，例如 PDF 证据冻结、曲线分析或领域调试。

## 5. 最小默认运行主干

### 5.1 默认事实

普通 Agent/Transform 运行默认只需要：

- `Artifact`：不可变内容、合同身份和父链；
- `Run`：本次 Operation 摘要、精确输入、状态、输出或错误；
- `ResearchInstance` 与 `CurrentBinding`：某实例下一个稳定科学语义名当前选中的 Artifact；
- `HumanDecision`：只有 Operation 明确声明人工决定时才创建。

`current` 只表示当前选中版本，不表示科学正确、已审查或已资格化。独立 reviewer 的结论首先是普通
审查 Artifact，不自动产生全局资格或 cohort。外部执行
状态只在 Effect 策略启用时出现，不进入普通 Run。

Run 记录在创建时冻结：Operation digest、后端种类/实现版本/能力投影、ResearchInstance、原始目标、
精确输入 refs、每个 current 要求及预算。这些字段共同进入完整请求指纹；运行中不得切换后端或
降低能力。原始目标始终是约束上下文，不是 claim evidence。

### 5.2 默认状态

```text
queued → running → completed
                 ↘ failed
queued/running → waiting_human → running/completed/failed（仅有人工策略时）
```

默认后端不使用 `claimed`、`finalizing`、多 attempt assignment、provisional checkpoint 或 late
finalize。超时、Agent 丢失或运行守护进程重启使本次 Run 明确失败；重试创建新 Run，不恢复旧会话，
也不自动换领其他任务。

### 5.3 current 与运行恢复

Run 创建时为每个 `requires_current` 输入冻结：实例、语义名、精确 ref、生产 Run，以及该生产 Run
继承的 current 锚点。currentness 是一个领域无关的递归判定：沿生产收据中标记为
`requires_current` 的输入边向上遍历，所有 `(instance, semantic_name, ref)` 都必须仍等于唯一
CurrentBinding。缓存只可作派生优化，不是第二权威。

目录 readiness、preflight、invoke、submit 和需要 current 的下游准入调用同一判定函数；不能只
检查直接 head。这样当 `A1 → C1` 后 A 的 head 变为 A2 时，即使 C 的直接 head 仍是 C1，C1 也会
被判为 stale。

完成时可以先用 `Run + accepted_candidate_digest` 幂等键登记不可变 Artifact；随后开启一个控制
数据库写事务，在该事务内部重新运行全部递归 current 锚点检查，再写入 Run `completed` 和完成
收据。这是提交时的最终 currentness 观察，不能复用事务外的预检结论。如果任一锚点已推进，
Artifact 仍保留、Run 仍完成，收据记录 `head_advance=stale_rejected`；否则记录
`head_advance=not_requested`。这个兼容字段只报告输入谱系状态，提交事务在两种情况下都不更新
CurrentBinding。

若调度器决定把已完成 Artifact 选为 current，必须在读取完成状态后另行发起 Root 显式 CAS，并绑定
精确预期旧 ref；CAS 失败不得覆盖新 head，也不得由查询路径稍后补写。若编译目录声明独立审查边，
父调度器同样在读取完成状态后显式调用 reviewer Operation。current 选择与 reviewer 调用彼此独立，
都不是 `worker_submit_result` 或 `RunService` 完成事务的副作用。

运行草稿和 current 严格分离：

```text
已完成 Artifact ──显式 CAS──> CurrentBinding
运行中工作区 ──失败快照──> 仅供精确 Run/显式新 Run 恢复
失败快照 ──禁止──> CurrentBinding
```

默认本地后端不暴露手工 checkpoint 工具。恢复命令必须先以 CAS 把原 Run 从 `running` 置为
`failed`、撤销唯一启动槽，并由后端证明旧 Agent 已结束；若不能证明，就原子隔离旧工作区后再冻结。
此后旧 Run 的 heartbeat 和 submit 一律拒绝。

冻结结果是 backend-private、内容寻址的 `recovery_draft`，只记录在失败 Run 的恢复字段中，不登记为
普通科学 Artifact，不能绑定普通 Operation 输入端口、ReviewGate、PromotionPolicy 或
CurrentBinding。显式新 Run 的 `resume_from` 指纹必须包含原 Run、草稿摘要、原 Operation digest 和
完全相同的输入 refs；Agent 可读取草稿并修正，但草稿不是证据，最终结果仍要完整校验和独立审查。
加固后端可以保留更细的自动 checkpoint 和同会话恢复，但仍受同一认识论边界。

### 5.4 唯一调用流程

```text
operation_invoke
→ 从唯一 CompiledOperation 生成 Run
→ WorkspaceBackend 创建任务目录并物化只读输入
→ 启动编译角色 Agent
→ Agent 写正式输出文件
→ 机械校验完整输出
→ RunService 幂等登记 Artifact
→ RunService 在一个控制事务中完成 Run并写入唯一收据
→ 父调度器读取完成状态，按需另行执行 Root current CAS 或调用编译 reviewer edge
```

聊天返回只是运行信号，科学内容只从完成后的正式输出文件读取。

## 6. 两级运行后端

### 6.1 共同窄接口

核心只依赖：

- `prepare(run, inputs, contracts)`；
- `open(run)`；
- `heartbeat(run)`；
- `seal(run) -> SealedWorkspace`；
- `discard(run)`。

`SealedWorkspace` 是一次调用返回的不可变值对象，不是新表、注册表或运行状态。它只包含冻结的
后端身份、Run 绑定、不可变文件清单、相对路径、媒体类型、字节数和
内容摘要。backend 负责证明这些字节不再被该写入者修改；RunService 才能读取它、执行数据合同校验
并登记 Artifact。backend 不返回科学 verdict、Artifact ref、Run 终态或 current 结果。

具体如何写文件、持有会话或恢复，不泄漏到 OperationSpec 和领域插件。Operation 只声明最低后端
能力；唯一 preflight 将其与部署后端的冻结能力投影比较，不能为后端另建 readiness 或准入入口。
Worker heartbeat 先由 RunService 检查 Run 仍在运行且绝对预算未过期，再调用 backend heartbeat：
Local 只报告写入者存活，Hardened 可续其私有租约；两者都不能延长 Run 的绝对预算或写 Run 终态。

### 6.2 LocalTrustedBackend：第一版默认

- 创建一个任务私有目录；输入、Schema 和提示文件只读；
- 使用 Codex 原生读写能力操作任务目录，避免重造文本、PDF、图像和代码编辑能力；
- 通过编译提示明确允许的目录、领域 MCP 和禁止行为；
- 用三个生命周期动作交付目录、可选报告存活和提交结果；
- backend seal 时检查普通文件、相对路径、文件数、大小、媒体类型、秘密模式、机器路径和未声明
  二进制；RunService 再执行完整输出合同校验；
- 输出校验失败保持 `running` 并返回有界诊断；成功后只有 RunService 能登记 Artifact；
- 只用于可信本地调试和可逆科学文件，不携带生产凭证，不直接执行不可逆副作用；
- 明确记录：当前 Codex 原生工具隔离是提示约束，不是技术沙箱，`SEC-002` 保持已知问题。

为了避免按角色误领，第一版同一编译 Operation 同时只允许一个未打开 Run。父调度器先建立唯一启动
槽，再启动对应 Agent；打开失败就停止，不回退到共享角色队列。

### 6.3 HardenedWorkerBackend：冻结保留、按需启用

该后端只承载已有真实消费者证明需要的加固能力：

- Operation 绑定的精确 Run 槽；
- 服务端分块创建、文本补丁、JSON 补丁、移动、删除及路径/大小/摘要校验；
- 每 Run 独立的短租约 owner fencing，允许进程退出后接回同一 running Run；
- 同一 Run 的旧 owner 与接管互斥，不同 Run 不因共享数据库写锁而串行；
- 仍由同一 RunService 负责候选校验、幂等完成和提交响应重放。

旧 S2 的 proxy/session/attempt、多阶段 finalizing 和跨 daemon 复杂恢复没有新的真实消费者，不再作为
Hardened v1 的承诺，随旧 Task 路径在 L6 删除。未来远程后端若需要它们，必须重新以真实消费者和
独立恢复语义进入，而不能留一套无消费者的兼容状态机。

后端由部署配置选择，Operation 可以要求最低后端能力但不能在运行中降级安全级别。两个后端消费
同一 `CompiledOperation`，向同一 RunService 返回 `SealedWorkspace`，不自行产生 Artifact/Run
结果，也不建立第二目录、第二 preflight 或第二科学准入体系。

Hardened 的 token、session、attempt、lease 和 recovery 只能是绑定同一 Run 的 backend-private
传输记录。旧 `TaskService` 中输出校验、Artifact 登记、Task 终态和 scheduler signal 职责必须迁入
唯一 RunService；reviewer 调用迁入父调度器，current 更新保留为独立 Root CAS。不得把拥有这些职责
的旧 TaskService 原样包装成 backend。

Hardened v1 只授权 Worker MCP。声明原生 shell、代码或 `view_image` 的 Operation 在统一目录中仍
可见，但运行绑定标记为 unavailable，preflight 和 Run 创建失败关闭，Codex 安装不生成该 Agent
profile。当前 TCAD Agent 因需要原生代码工具而只由 LocalTrustedBackend 承载；在真正任务根沙箱
出现前，不以提示词“禁止写”冒充 Hardened+TCAD 已受技术隔离。

### 6.4 后端无关领域工具上下文

所有注册领域工具统一消费一个非持久化 `OperationToolContext`，它不是新权威，只是当前 Run 的最小
能力投影：

- 按科学别名读取精确输入；
- 访问本次受控工作区和声明输出集合；
- 检查编译能力与剩余预算；
- 请求一个只供工具使用的候选快照；
- 存放有界开发输出或诊断；
- 记录无科学内容的有界 activity。

插件看不到 Run/Task/session/token/proxy、控制数据库或 current 写接口。Local 和 Hardened 分别把
内部状态投影为同一 context；领域工具不能调用正式 Artifact 登记、Run 完成或 head CAS。

L2 先用一个盲插件注册工具验证该接口。TCAD debug service 随后从 `TaskService + session_token` 改为
只依赖 `OperationToolContext` 和领域 adapter；Deck workspace materializer/finalizer、8 MiB 文件政策、
调试候选快照和开发结果边界均在 L4 做真实验收。

## 7. 三个生命周期动作

三个动作在两种后端中保持相同外部语义，但内部强度可以不同：

- `worker_open_assignment`：取得本次精确 Run 的任务目录；
- `worker_heartbeat`：报告存活，不扩大工具、上下文或绝对预算；
- `worker_submit_result`：请求 backend seal，再由唯一 RunService 校验并提交完整输出；失败返回可修复
  诊断，成功返回唯一完成收据。

最小后端不需要向 Run 复制生命周期协议摘要；`CompiledOperation.digest` 已覆盖合同。加固后端可把
协议摘要纳入其私有 dispatch 权限，但不得使该字段成为所有普通 Run 的基础负担。

## 8. 审查、current、资格和外部副作用

### 8.1 独立审查保留在通用核心

作者与 reviewer 的独立性是多 Agent 科研的基本边界。Operation 的 review edge 只声明如何把作者
已登记 Artifact 绑定给另一个 reviewer Operation；父调度器据此显式调用，运行器既不自动创建审查
Run，也不解释科学 verdict。

后续行为若需要已通过审查，窄 `ReviewGate` 只检查“这个精确 Artifact 是否存在指定 reviewer 的可
接受审查 Artifact”。它不默认创建全局 qualification/cohort。

### 8.2 current 保留为最小默认事实

每个 ResearchInstance 保留稳定语义名到精确 Artifact ref 的唯一 current 映射。它用于跨会话继续
研究、拒绝 stale 后代和恢复调度上下文；不使用 `latest`、文件名、完成时间或标签推断。删除的是
current 周围的提案、候选、审批包装和与资格的隐式捆绑，不是 current 本身。

current 只能由控制面显式命令更新，使用预期旧 ref 做 CAS；Worker、插件和 checkpoint 不能更新它。
所有声明 `requires_current` 的输入都使用第 5.3 节的递归判定，而不是只比较本对象的直接 head。

### 8.3 qualification 改为可选 PromotionPolicy

普通探索不创建 qualification/cohort。需要“正式基线”“批准参数集”或完整资格集合的场景可注册
`PromotionPolicy`。启用后仍满足：

- 控制面是唯一权威；
- revision 不继承旧审查或资格；
- 不同集合不能拼接为完整批准；
- 插件不得自建第二 qualification 或借资格旁路 current CAS。

### 8.4 人工决定和 Effect

人工决定仍只来自 loopback UI，并绑定精确可见对象。普通探索和 reviewer 不默认要求人工审批。
Effect 策略保留提交、领域运行、结果收集三轴及 unknown 权威查回，但这些字段和状态不进入普通
Agent Run。

## 9. 插件接入成本验收

“一个入口”必须同时证明“声明足够小”：

1. 新增一个盲 CSV 插件：一个 Agent 读取 CSV、调用一个注册工具、输出 JSON，并由独立 reviewer
   审查；不得修改核心、调度器、UI 和部署代码；插件注册与胶水不超过 250 行，领域算法和数据模型
   另计；
2. 记录每个 Operation 的必填字段数、组件引用数、首次接入修改文件数和测试步骤；
3. 若简单插件仍需分别登记重复 codec、Schema resource、validator、guard 和 UI projector，本阶段
   不得通过；
4. TCAD 插件必须通过同一入口获得 Deck 工作区和 `worker_tcad_debug_run`，核心零 TCAD 名称分支。

## 10. 33 项约束如何继续遵守

33 项约束仍是行为验收矩阵，但采用条件化解释，不能反向要求所有可选事实常驻默认路径：

- current 始终由最小控制面唯一维护；“条件化”只适用于 qualification、审批和 Effect；
- `LIN-002` 的 currentness 对声明 `requires_current` 的输入始终执行，完整资格集合只在启用
  PromotionPolicy 时执行；
- `HIL-*` 只在声明人工决定时触发；
- `EFF-*` 只在 Effect Operation 中触发；
- `CQRS-*` 继续约束 Run、Decision 和所有可选策略；
- `RES-002` 对最小后端的恢复结论是有界失败和显式新 Run，不是继续旧会话；
- `SEC-002` 不能条件化豁免：LocalTrustedBackend 仍是 `known_issue`，只允许可信本地开发，不能声称
  33 项全部 conformant；只有任务根文件系统沙箱或 Hardened 后端才能关闭该缺陷。

无论使用哪个后端，所有领域 MCP 仍由服务端按编译 Operation 门禁，submit 都拒绝越界路径、秘密、
机器路径、未声明二进制和超限输出。Local profile 不装载生产凭证、远程执行或不可逆 Effect；必须
测试不可信论文/网页提示不能扩大 MCP 权限，并把跨任务原生读写无法被当前平台技术阻断的负例结果
如实登记，不能以提示禁令冒充隔离。

不可条件化削弱的边界仍包括：不可变 Artifact、精确输入、最小上下文、Operation 单一授权、作者与
审查者独立、聊天不构成人工决定、外部来源冻结、控制层不做科学判断、插件不向核心泄漏领域规则。

## 11. 当前 S2 候选的处置

| S2 内容 | 处置 |
| --- | --- |
| 三个生命周期名称与编译投影 | 保留 |
| 生命周期名与插件工具冲突检查 | 保留 |
| 手工 checkpoint 删除 | 保留 |
| `worker_submit_result` 一次校验和幂等完成 | 两个后端共同语义，保留 |
| 服务端文件编辑协议 | 实现留在加固后端；工具身份由内置插件登记一次，每个需要写正式输出的 Agent Operation 显式引用，后端只投影已授权且可实现的工具 |
| 精确调度令牌和 session 恢复 | 冻结并迁入加固后端，最小后端不使用 |
| `lifecycle_protocol_digest` 复制进每个 Task 权限 | 默认撤回；加固后端私有权限可保留 |
| `claimed/finalizing` 跨 daemon 恢复 | 仅加固后端按消费者证明保留 |
| 旧 TaskService 的职责 | Artifact/终态迁入唯一 RunService；current 保留为 Root 显式 CAS；review 调用归父调度器；不得留在加固 backend |

S2 第三轮审查只证明旧可靠控制器内的协议闭合，不再自动放行其成为默认主干。当前未完成 S2 diff
必须在 L0 逐符号归类，不能伪称已经实现。

## 12. 实施顺序

### L0：冻结和设计审查

- 冻结当前未完成 S2 diff；建立保留、最小后端复用、加固后端迁移、撤回四类清单；
- 冻结 Hardened 的精确符号、入口、私有状态、文件协议、安装探针和恢复测试；
- 恢复工作树到可测试的阶段边界，不增加兼容别名；
- 更新活动计划、设计宪章和约束解释候选；
- 独立审查“两级后端”是否真的减少默认复杂度且不虚构安全。

完成门：审查明确通过；未放行 L1 前不继续扩建跨 daemon 恢复。

### L1：最小合同投影和盲插件

- 从现有 OperationSpec 编译最小运行投影，不建立新注册表；
- 将治理字段收为可选策略引用；
- 实现盲 CSV 插件并测量接入成本；
- 合并重复数据合同声明；
- 继续运行 Hardened 编译、干净安装、精确任务绑定和路径逃逸负例，允许未启用但不允许腐烂。

完成门：盲插件达到第 9 节门槛；独立审查通过。

### L2：LocalTrustedBackend 和最小 Run

- 用一个 Run 权威承载普通默认执行；
- 接通唯一 `operation_invoke`、任务目录、三个生命周期动作、输出校验和 Artifact 登记；
- 保留最小 ResearchInstance/current CAS；同一 Operation 单启动槽；超时/崩溃失败并冻结 run-local
  恢复快照，显式新 Run 重试；
- 冻结 `OperationToolContext`，真实启动通用 Codex Agent，验证原生读写和一个注册科研工具；
- 回归 Hardened 编译、安装、精确绑定和服务端文件关键负例。

完成门：默认运行只有一套有消费者证据的 Run 状态，不导入
token/session/assignment/finalizing；独立审查通过。

### L3：独立 reviewer 和可选人工决定

- 真实运行作者—reviewer 文件闭环；
- 实现窄 ReviewGate；
- 只为声明人工策略的行为接入 loopback UI；
- 验证聊天不能转决定、revision 不继承旧审查；
- 回归 Hardened 编译、安装、恢复和路径负例。

完成门：普通探索无 qualification/approval 负担；current 只是一条显式 CAS head，不暗示资格；
独立审查通过。

### L4：TCAD 最小纵向闭环

- 复用现有 TCAD 数据合同、Deck 物化、领域工具和 debug adapter；
- 真实启动 TCAD author，读取输入、修改 Deck、调用 `worker_tcad_debug_run` 并提交；
- 真实启动独立 TCAD reviewer；
- 验证 Deck materializer/finalizer、8 MiB 文件政策、debug 开发快照和结果边界；
- 此阶段使用最小 current head，但不要求先接 qualification 或远程执行；
- 回归 TCAD 服务端文件关键负例，并冻结 Hardened 对原生工具型 TCAD 的显式拒绝边界。

完成门：作者—调试—审查闭环完成，核心零 TCAD 分支；独立审查通过。

### L5：按需接回加固与副作用策略

- 基于真实消费者接通 HardenedWorkerBackend、EffectPolicy 和资格 PromotionPolicy；
- 未启用的策略不建普通 Run 字段，不出现在简单插件投影；
- 对远程、并发、重启、路径逃逸和不可逆副作用做后端专属测试。

完成门：加固能力有真实消费者且不污染默认路径；独立审查通过。

### L6：删除旧中央默认路径

- 删除已无默认消费者的旧 Task/token/session/assignment/lease/finalizing 路径；
- 有消费者证明的实现归入加固后端；
- 删除迁移期间的临时双路由，恢复一个调用入口和一个 Run 权威；
- 默认 wheel/deploy 不启动 Worker daemon，也不导入 token/session/assignment/finalizing；
- 默认 `operation_invoke` 只创建 Run，禁止兼容转发、双 MCP 路由或 Task 包装 Run；
- Hardened 只在有真实消费者且部署显式选择时加载；
- 执行默认 clean wheel、Local、纯 MCP Hardened、无 Hardened 插件组合、TCAD Local 成功、
  Hardened+TCAD 预检拒绝、review、approval、Effect 和回滚回归。

完成门：零默认消费者、唯一 Run 权威和上述安装矩阵通过；行数只作观测，不作删除许可；双重独立
总审查通过。

## 13. 自动停止条件

- 永久形成第二目录、第二 preflight、第二 invoke 或第二科学准入体系；
- backend、领域工具、RunService 或旧 TaskService 越权更新 current、自动创建 reviewer，或由
  RunService 以外的组件登记科学 Artifact、解释 Run 终态；
- 普通 Run 需要 qualification/execution/session/token 字段才能启动；
- 新增没有独立事实、真实消费者和恢复语义的 Run 状态，或把状态隐藏到文件/UI 规避审查；
- WorkspaceBackend 的编辑细节重新成为每个 Operation 的必填字段；
- 用提示词禁令宣称技术隔离已经完成；
- 简单盲插件超过接入规模门且不能证明超出部分属于领域算法；
- 核心出现 TCAD、曲线、角色、Schema 或插件名分支；
- 为个别测试增加隐藏标签、状态或特判；
- 独立审查没有明确通过。

## 14. 完成定义

1. 默认路径可以概括为：编译 Operation、建立目录、启动角色、校验文件、登记 Artifact、按需审查；
2. 普通探索只支付一个最小 current head，不支付 qualification、精确 token、proxy session 和跨
   守护进程同会话恢复成本；
3. 加固调度和服务端文件协议仍可为需要它们的场景启用，而不是被草率删除；
4. 多角色、文件通信、最小上下文、声明工具、独立 reviewer 和人工副作用边界不退化；
5. 简单盲插件达到量化接入门；
6. TCAD 作者、领域调试和 reviewer 真实运行；
7. 旧中央默认路径最终退出，而不是由新包装器长期包裹。

状态数量不是完成标准；完成标准是只有一个 Run 终态权威，且每个保留状态都有不能从其他事实推导的
真实消费者和恢复语义。

## 15. 实施进度

### 2026-08-31：L0 通过

- 已将未完成 S2 逐符号归入共享保留、Local 可复用、Hardened 迁移、默认撤回四类，证据见
  `evidence/R5_L0_S2_CLASSIFICATION_AND_HARDENED_FREEZE.zh-CN.md`；
- 已冻结 Hardened 的精确调度、私有状态、服务端文件协议、安装探针和关键恢复测试；
- 已恢复三动作过渡路径的可测试边界：生命周期由编译器统一声明，缺失 runtime service 不消耗启动
  槽，提交一次完成，插件工具投影不再混入 lifecycle；
- L0 首轮独立实现审查打回三个证据阻断：不可复算账本、缺少真实进程恢复矩阵、生命周期合同测试
  不完整；报告见 `reviews/R5_L0_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 已返修为 209 项终点清单和 29 路径职责账本；普通 role queue 明确列入 L6 撤回而非 Hardened；
- 已增加三个真实 daemon 崩溃窗口、最终硬期限、错误绑定，以及 lifecycle 碰撞/摘要/五方投影/外部
  analysis/首次 submit 的直接回归；
- 返修后聚焦测试 `75 passed`，非 live operation 全集 `294 passed`；
- L0 第二轮独立实现审查通过，报告见
  `reviews/R5_L0_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`；只放行 L1。

### 2026-08-31：L1 审查候选

- 已从唯一 `CompiledCatalog` 按需导出不可变 `RuntimeOperationProjection`，没有第二注册表；
- 已将 reviewer edge 与可选 guard/cohort/人工决定/Effect 引用分开投影，普通操作不携带可选治理；
- 已新增外置盲 CSV wheel：作者读取 CSV、调用一个注册领域工具、输出 JSON，并声明独立 reviewer；
- 注册与胶水合计 250 物理行、221 个非空非注释行；每个操作复用 6 个公共组件，核心没有插件名分支；
- 证据和边界见 `evidence/R5_L1_MINIMAL_PROJECTION_AND_BLIND_PLUGIN.zh-CN.md`；
- L1 首轮独立实现审查以“真实 Worker 工具失败、CSV 用途冲突”两项阻断打回，报告见
  `reviews/R5_L1_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 已删除插件私有 activity，未扩核心白名单；已将原始 CSV 改为 `claim_evidence`，作者输出在
  reviewer 中保持 `prior_signal`；
- 已补真实 Root invoke→exact dispatch→Worker 工具→作者 submit→reviewer submit 的正负回归；
- 返修后 L1 聚焦及 L0 防腐回归 `105 passed`；非 live Operation 全集 `300 passed`；
- L1 第二轮独立实现复审通过，报告见
  `reviews/R5_L1_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`；只放行 L2。

### 2026-09-01：L2 第三轮复审候选

- 已实现默认本地可信 Run 权威、窄工作区后端和后端无关的领域工具上下文；默认入口不再实例化
  Task/token/session/lease/finalizing；
- L2 首轮独立审查以 current 递归与提交竞态、候选崩溃窗口、查询副作用、Hardened 路由错位、工具
  投影分裂、路径身份泄漏、缺少真实 Agent 证据和发布扫描八项阻断打回；报告见
  `reviews/R5_L2_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 第二轮独立复审继续以生产 current 缺少显式 CAS、失败隔离不可重放、状态查询发布输出、Local 工具
  静默降级和桥接进程代调工具五项阻断打回，报告见
  `reviews/R5_L2_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`；
- 已在原有 Root 命令、Run 事务、backend-private 映射和单一工具投影中逐项修复，没有增加新业务状态；
  非 live Operation 回归 `314 passed`，部署/平台/精确 dispatch/干净安装回归 `63 passed`；
- 已真实拉起 `spawn_agent(fork_turns="none")`：子智能体直接启动真实 stdio Worker MCP，自己调用注册
  CSV 工具和 submit，并以原生文件能力写结果；持久化 Run/Artifact 证明完成，证据见
  `evidence/R5_L2_LOCAL_RUN_AND_CODEX_AGENT.zh-CN.md`；
- 当前会话不能热加载探针目录新生成的自定义 Agent 类型，因此本次使用通用 worker 执行同一编译
  提示；该限制明确保留，不冒充已关闭 `SEC-002`；
- 第三轮独立复审已通过，报告见
  `reviews/R5_L2_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`；复审期间发现的跨附加库 WAL
  原子性缺口已用两库 DELETE journal + 启动失败关闭修复；现放行 L3，不提前放行 L4—L6。

### 2026-09-01：L3 实施中

- 复用现有 `ReviewSpec`、作者输出生产合同和 `RunService.is_exact_reviewer_output`，不新建 Review 表、
  verdict 状态机或全局资格；
- 本阶段只增加跨 Root 的精确审查门、真实作者—审查者 Agent 证据，以及 Local 默认路径的可选人工
  决定回归；
- L3 独立审查通过前不实施 L4 TCAD、L5 策略或 L6 删除。

### 2026-09-01：L3 复审候选

- 精确 ReviewGate 已通过“无审查拒绝、精确审查放行、旧审查不覆盖新修订、新审查放行”四段正反例；
- 普通 Local 探索不创建 qualification/approval；只有声明 approval executor 的 Operation 创建待决人工
  对象，Root 没有人工决定写工具；
- 两个无父历史真实子智能体已分别直接完成作者与审查者 stdio MCP，未经过 bridge，持久结果证明
  注册工具、精确父链和 passing exact review；
- 非 live Operation 全集 `317 passed`；证据见
  `evidence/R5_L3_EXACT_REVIEW_AND_OPTIONAL_HUMAN_DECISION.zh-CN.md`；
- 独立复审通过前仍不实施 L4—L6。

### 2026-09-01：L3 独立复审通过

- 独立复审结论为 PASS，无阻断项，报告见
  `reviews/R5_L3_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 普通科学 Operation 的人工审批只由显式 approval Operation 创建；实例注册和外部 Effect 授权仍是
  两类独立、必要的系统级人工边界；
- 当前只放行 L4，不提前放行 L5、L6 或正式发布。

### 2026-09-01：L4 实施中

- 将现有通用 workspace materializer/finalizer 接入 Local Run，不在核心增加 TCAD 名称分支；
- 将现有 TCAD debug adapter 通过后端无关 `OperationToolContext` 暴露给同一注册工具；
- 完成真实 TCAD 作者—调试—独立审查 Agent 闭环并经独立审查通过前，不进入 L5。

### 2026-09-01：L4 独立复审候选

- TCAD 作者在同一编译 Operation 下通过原生文件能力编辑插件物化的 Deck 工作区，直接调用已注册
  `worker_tcad_debug_run`，再由插件 finalizer 和唯一 RunService 完成正式输出；
- 调试服务只依赖后端无关 `OperationToolContext` 与现有领域 adapter，不可见 Task、token、session、
  current 写入或 Artifact 登记；私有调试结果不成为科学输出；
- 已完成两个无父历史真实子智能体的作者—调试—独立审查闭环，未使用父进程 bridge；证据见
  `evidence/R5_L4_LOCAL_TCAD_VERTICAL_SLICE.zh-CN.md`；
- 超过 8 MiB 的 Deck 源文件、私有输出符号链接和未安装插件配置均失败关闭；通用运行核心扫描为零
  TCAD/Deck/Sentaurus 分支；
- 首轮独立审查以 `deck/reports` 和 `output` 父目录符号链接可造成控制写出工作区为阻断项打回，报告
  见 `reviews/R5_L4_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 已用一个通用目录句柄/O_NOFOLLOW 控制写原语修复两条路径，并新增两项真实负例；外部目录保持
  空、Run 保持运行中，不以提示约束掩盖服务端写入缺陷；
- 返修后非 live Operation 全集 `322 passed`，部署/平台/运行时插件/旧 TCAD debug 所有权与 L4
  防腐集合 `64 passed`；
- 独立复审明确通过前仍不实施 L5、L6。

### 2026-09-01：L4 第二轮独立复审通过

- 第二轮独立复审确认首轮工作区外写入阻断已由一个通用目录句柄/O_NOFOLLOW 原语闭合；
- 两条首轮真实复现和既有私有调试目录负例均失败关闭，核心仍为零 TCAD 特判；
- 独立聚焦回归 `40 passed`，结论为 PASS，报告见
  `reviews/R5_L4_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`；
- 当前只放行 L5，不提前放行 L6 或正式发布。

### 2026-09-01：L5 实施中

- 先证明现有 Effect 与 cohort/approval 语义只是按编译 Operation 启用的可选策略，普通 Run 不增加
  字段或状态；
- 再把真正需要精确调度、服务端文件和重启恢复的消费者迁到消费同一 RunService 的
  HardenedWorkerBackend；旧 TaskService 不得继续拥有科学输出、Artifact、current 或 reviewer；
- L5 独立审查通过前不实施 L6 删除。

### 2026-09-01：L5 独立复审候选

- 已实现只管理工作区、服务端文件和短租约传输所有权的 `HardenedWorkerBackend`；它与 Local 消费
  同一个 `RunService`，不持有科学 Artifact、current、reviewer 或 Run 终态权威；
- 盲 CSV 插件已通过真实独立 stdio 进程完成注册领域工具、服务端文件、进程退出、租约后重连和唯一
  Run 提交；并发所有者与符号链接逃逸均失败关闭；
- Hardened Codex profile 已从旧 Task proxy 切换为 Operation 绑定的 Run Worker；
- 普通 Run 表没有 qualification、approval、Effect、session、token、attempt、lease 或 finalizing
  字段；既有 TCAD cohort 和 Effect/人工审批真实消费者按声明启用；
- Operation 非 live 全集 `327 passed`，平台/部署/运行时及加固冻结集合 `76 passed`；证据见
  `evidence/R5_L5_OPTIONAL_HARDENED_AND_POLICIES.zh-CN.md`；
- 旧 Task/token 目前仅为历史恢复测试临时实例化，生产 Root 和 Codex profile 已无消费者；这是 L6
  必删项，不得作为兼容层保留；
- L5 独立复审明确通过前不实施 L6。

### 2026-09-01：L5 首轮审查打回与返修

- 首轮独立审查结论为 FAIL，报告见
  `reviews/R5_L5_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；三个阻断分别是接管后旧 transport 未
  失效、Hardened Root 仍持有旧 Task 科学事实、TCAD 已声明文本补丁却固定不可用；
- 已将所有 Hardened Worker 调用统一置于事务性 transport ownership guard 内，租约接管与旧调用
  不能交错，旧 owner 的领域工具、文件工具、校验和提交全部失败关闭；
- `open_runtime(worker_backend="hardened")` 已彻底断开 Task/token；旧恢复测试和待删除旧 daemon 只
  能显式选择生产配置拒绝的临时 `legacy_task`，不能影响新 Root 的 signal、review 或 inventory；
- 已在通用 Hardened 文件编辑器补齐精确上下文文本补丁，真实 TCAD Deck 创建、修改、字节核对和
  陈旧补丁拒绝均通过，核心没有 TCAD 分支；
- 返修后 Operation 非 live 全集 `329 passed in 122.74s`，`git diff --check` 通过；证据已更新至
  `evidence/R5_L5_OPTIONAL_HARDENED_AND_POLICIES.zh-CN.md`；
- 当前只申请 L5 第二轮独立复审；复审明确 PASS 前仍不实施 L6。

### 2026-09-01：L5 第二轮审查打回与返修

- 第二轮独立审查确认首轮 B1—B3 已实质闭合，但仍以两个新阻断判定 FAIL，报告见
  `reviews/R5_L5_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`：共享 SQLite 长写事务把无关
  Run 全局串行；shell-enabled Hardened profile 可绕过服务端文件协议；
- ownership guard 已改为按 `run_id` 内容摘要分离的操作系统文件锁，SQLite 只做短时 owner CAS；直接
  并发回归证明不同 Run 不互相阻塞，同一 Run 接管必须等待在途调用结束；
- Hardened v1 已收紧为纯 MCP 后端。声明原生 shell、代码或 `view_image` 的 Operation 在目录、
  preflight、Run 创建和 Codex 生成四处消费同一个 backend capability 结论，均失败关闭；
- 盲 CSV 插件已显式声明 `native_shell="none"`，继续作为真实 Hardened 消费者；TCAD 当前需要原生
  代码工具，故 Local 闭环保持成功，Hardened+TCAD 明确不可用，未增加 TCAD 特判；
- 精确文本补丁由一个 shell-free Agent Operation 实际调用并覆盖陈旧上下文拒绝；
- 返修后 Operation 非 live 全集 `332 passed in 123.97s`，Artifact Agent 全集
  `40 passed in 5.98s`，`git diff --check` 通过；
- 当前只申请 L5 第三轮独立复审；明确 PASS 前仍不实施 L6。

### 2026-09-01：L5 第三轮独立复审通过

- 第三轮独立复审结论为 PASS，报告见
  `reviews/R5_L5_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`；
- 审查者独立确认每 Run fencing 与跨 Run 并行成立，并额外用真实 `view_image=true` Operation 验证
  目录、preflight/invoke、RunService 直调和 Codex profile 四个边界统一失败关闭；
- 独立聚焦回归 `20 passed`，未发现新领域特判、第二科学权威、第二注册表或复杂度反噬；
- 当前只放行 L6 旧路径删除与最终安装矩阵，不放行正式发布。

### 2026-09-01：L6 实施中

- 先迁出唯一 Run 仍消费的通用信号与 Operation 编译类型；
- 再成组删除旧 Task/token/daemon/proxy/Root task route 和 `legacy_task` 选择器；
- 最后收敛部署、平台、测试与文档，并执行双重独立总审查。

### 2026-09-01：L6 双重独立总审查候选

- 旧 Task Schema/Service/token、中央 Worker daemon/proxy/systemd、Root Task route 与双运行时选择器均已
  从生产代码删除；默认 `operation_invoke` 只创建 Run；
- Local 与 Hardened 共享唯一编译目录、preflight、invoke、RunService 和 Artifact/current 权威；
  Hardened 只保留每 Run 文件传输围栏；
- TCAD debug 合同已回到插件，领域工具统一消费 `OperationToolContext`；核心无领域名称分支；
- 干净 wheel、Local、Hardened、TCAD Local、Hardened+TCAD 拒绝、review、approval、Effect、部署回滚
  均包含在最终回归中；shell 语法和 `git diff --check` 通过；
- 通用包 `src/scidiscovery` 从 L5 的 159 文件/62,025 行降到 101 文件/27,260 行；当前领域插件另有
  45 文件/22,763 行，全部生产 Python 合计 146 文件/50,023 行；度量只作观测；
- 完整证据与已知限制见
  `evidence/R5_L6_OLD_PATH_REMOVAL_AND_FINAL_MATRIX.zh-CN.md`；
- 当前只申请两轮独立总审查；两份结论均明确 PASS 前不宣告 L 系列完成。

### 2026-09-01：L6 第一轮总审查打回与返修

- 第一轮独立总审查结论为 FAIL，报告见
  `reviews/R5_L6_FINAL_INDEPENDENT_REVIEW_ROUND1.zh-CN.md`；
- B1：增加唯一 `SCID_WORKER_BACKEND=local|hardened`，贯穿 `scid init`、control daemon、systemd、
  安装预览、Codex profile 生成和安装后验证；正常安装由同一值避免错配，profile validator 校验生成
  结果，人为跨后端重生成时由 Worker open 失败关闭；
- B2：旧 `scidiscovery-worker.service` 通过既有安装事务精确删除，成功升级不遗留，失败回滚恢复原
  文件和原服务状态；
- B3：当前中英文架构、设计宪章、角色结果协议、TCAD transport、33 项矩阵和生产规模口径已同步
  到 Run v1；矩阵仍诚实记录 25 项 pending 和 `SEC-002 known_issue`；
- 带集合输出的 Agent Operation 由 Local/Hardened 的同一能力判定显式拒绝，目录、预检和 Codex
  profile 不再给出互相矛盾的可用性结论；
- 首轮复审发现通用核心残留 `deck_review`、`deck_revision` 和 Deck 专用等价理由；已将 Artifact kind
  与推荐行动收敛为插件可声明的稳定标识、把比较理由改为领域中性独立审查，并增加非 TCAD 回归；
- 第一轮返修时完整矩阵为 `196 passed`，shell 语法、字节码编译与 `git diff --check` 通过；当时仅申请
  第一轮复审，复审 PASS 前不进入第二位独立总审查。

### 2026-09-01：L6 第一轮总审查复核通过

- 第一轮返修首次复核关闭部署、迁移、文档和 collection 问题，但发现核心残留 Deck 领域语义，结论
  仍为 FAIL，报告见 `reviews/R5_L6_FINAL_INDEPENDENT_REVIEW_ROUND1_REREVIEW.zh-CN.md`；
- Artifact kind 与 Worker 推荐行动已从核心闭集收敛为格式受限插件标识；通用比较器和 Worker 文件
  协议已领域中性化，核心生产 Python 对 Deck/TCAD/Sentaurus 名称零命中；
- 第二次独立复核结论为 PASS，报告见
  `reviews/R5_L6_FINAL_INDEPENDENT_REVIEW_ROUND1_REREVIEW2.zh-CN.md`；
- 该结论只放行第二位独立总审查，第二位明确 PASS 前不宣布 L6 或 L 系列完成。

### 2026-09-01：L6 第二位独立终审打回与返修

- 第二位独立终审结论为 FAIL，报告见
  `reviews/R5_L6_SECOND_INDEPENDENT_FINAL_REVIEW.zh-CN.md`；
- B1：Hardened assignment 误用 Local 工具投影。现由所选 `WorkspaceBackend` 一次给出有效工具集，
  assignment、Codex profile 和实际 Worker router 消费同一投影；缺少服务端创建工具时在 Run 创建前
  失败关闭；
- B2：无运行消费者的 `roles/common.md` 及五个旧静态科学角色文件已删除，wheel 只分发当前
  `scheduler.md`；Run 协议明确 submit 只完成 Artifact/Run/receipt，current 由显式 Root CAS 更新，
  reviewer 由父调度器依据编译 review edge 另行调用；
- 聚焦回归 `25 passed`，最终完整矩阵为 `199 passed`；字节码编译、shell 语法、退休词扫描和
  `git diff --check` 通过；仍需同一第二位审查者复核，明确 PASS 前保持 L6 未完成。

### 2026-09-01：L6 双重独立总审查通过，L 系列完成

- 第二位终审第一次复核确认运行时工具投影和角色分发问题已关闭，但因活动计划仍保留自动 current、
  自动 reviewer 和文件工具所有权旧描述而继续判定 FAIL，报告见
  `reviews/R5_L6_SECOND_INDEPENDENT_FINAL_REVIEW_REREVIEW.zh-CN.md`；
- 现行计划已统一为三个显式动作：RunService 完成 Artifact/Run/receipt，Root 另行执行 current CAS，
  父调度器另行调用编译 reviewer edge；文件工具实现归 backend，授权仍只来自 Agent OperationSpec；
- 新增活动计划事实防回退测试，并同步中英文入口文档；清理审查生成的未跟踪缓存后，完整矩阵为
  `200 passed in 64.56s`，字节码编译、部署脚本语法和 `git diff --check` 通过；
- 第二位独立审查者第三次聚焦复核为 PASS，独立回归 `18 passed in 39.17s`，报告见
  `reviews/R5_L6_SECOND_INDEPENDENT_FINAL_REVIEW_REREVIEW2.zh-CN.md`；
- 第一位与第二位最终审查均已明确 PASS，至此 L6 和 R5-L0—L6 整个 L 系列按本计划范围完成；
  33 项矩阵中的 `pending_review` 与 `SEC-002 known_issue` 继续保留，不因阶段完成而自动晋级。
