# R2：统一 Operation 预检与行为创建入口实施记录

状态：通过；首版基础权限子 Agent 的真实快速闭环、自动化回归与第二轮独立审查均已通过；
本文件只记录证据，阶段状态以主计划第 26 节为准。

基线：`baseline/8765-codex@404aeb1`，叠加已经通过独立审查的 R0、R1。

## 1. 本阶段实际完成范围

- `open_runtime` 在服务打开前编译一次已安装插件目录，并把同一个不可变
  `CompiledCatalog` 对象交给 Root 调用面和 `TaskService`；运行期不热加载、不重新解释
  `OperationSpec`。
- Root 新增四个窄接口：
  - `scientific_inventory`：只返回当前实例可见的科学对象和显式 current 选择，不生成领域候选；
  - `operation_catalog`：只返回 R1 冻结的调度器安全投影；
  - `operation_preflight`：解析精确 Artifact、端口、schema、媒体类型、大小和准入条件，
    但不写任务、变换或执行状态；
  - `operation_invoke`：在既有创建锁内重复同一预检，并把绑定结果交给现有生命周期服务。
- `operations/invoke.py` 只承担纯输入绑定、调用期权限派生和三种窄执行桥：
  - Agent 生成现有任务调用参数和任务权限快照；
  - Transform 适配到现有 `artifact_transform` 注册、父链和幂等逻辑；
  - Effect 适配到现有 `ExecutionRequest`、审批 UI 和 ExecutionService。
- Agent 调用把 operation id、version、digest、精确输入、任务内别名、工作区、模型、网络和
  资源上限派生为 `TaskOperationAuthority`，直接嵌入现有不可变 `AgentTask`，没有增加表或
  独立生命周期。任务恢复、dispatch、resume 和 finalize 都重新确认安装目录中仍有同版本、
  同摘要 operation；摘要漂移时失败关闭。
- Operation 创建的任务不再继承角色级 `WORKER_CAPABILITIES` 权限并集。核心 Worker 生命周期
  工具和插件领域工具都使用同一个 `WorkerToolDefinition` 注册协议；Worker MCP 只装载已编译
  catalog 中的工具，并在 claim 后按 operation 权限逐调用校验。实际领域工具调用会写入任务的
  持久化成功/失败收据，未声明工具即使伪造调用也被拒绝。旧 8765 任务仍按原行为运行，
  仅用于迁移对照。
- operation id、version、编译摘要和调用期权限摘要进入现有任务 fingerprint、任务记录及
  输出 Artifact 标签；Transform 输出和 Effect 请求 Artifact 同样携带 operation 谱系。
- preflight 与 invoke 共用 Agent/Effect 组件计划和执行桥校验；调用时不会重新执行组件以
  产生另一份行为解释。current 选择在预检后变化时，invoke 必须重新拒绝且不创建任务。
- 内置三个 operation 仍只用于架构验收：一个 critic 合同 Agent、一个字节恒等 Transform、
  一个无真实外部适配器的 Effect。它们不代表通用角色或 TCAD 已完成迁移。

## 2. 复用的既有权威

本阶段没有创建 `OperationRun`，也没有复制下列状态机：

| 行为 | 唯一状态权威 |
| --- | --- |
| Agent | 现有 `TaskService`、Worker claim/文件校验/finalize/reconcile |
| Transform | 现有 `artifact_transform`、CAS、父链和幂等注册 |
| Effect | 现有 `ExecutionService`、ExecutionBridge、ApprovalService 和 UI |
| Artifact | 现有 ArtifactService、CAS、实例绑定和 current 选择 |

`OperationCall` 与预检结果均为请求或内存投影；没有新增 SQLite migration、资格事实、
current 权威、readiness 表或并行插件注册表。

## 3. 失败关闭边界

- 输入端口缺失/多余、数量、重复 Artifact、schema、媒体类型、单项/总字节上限、current、
  独立审查和人工审批要求任一不满足，均在创建前拒绝；调用参数没有声明式 schema，首版
  因此拒绝全部非空参数，不能借参数扩权。
- Agent 输入 `usage` 必须属于现有 `TaskInput` 的有限集合，防止通过插件私有字符串绕开
  任务准入语义。
- Codex 配置生成器已把每个 Agent operation 编译成独立角色配置：精确 prompt、model、
  Worker 工具清单、原生 shell/image 开关、禁用网络、只读权限和 operation 输出合同均不再
  从旧角色补齐；根配置也显式注册每个生成角色。非 `none` 的网络策略仍失败关闭。
- Worker MCP 在 claim 前只允许领取任务；领取后同时按传输绑定身份、operation 摘要和精确
  工具清单校验。客户端隐藏与服务端拒绝是两层独立边界。
- Agent 任务直接使用 spec 编译的 output schema、codec 和 validator，不再复用 critic 输出
  合同；架构测试 Agent 仍只用于验收，不代表通用角色或 TCAD 已迁移。
- review/approval 要求在没有精确既有收据解析桥时保持失败关闭；Effect 仍强制走现有独立
  执行审批。由 spec 生成领域 UI 呈现属于 R4。

## 4. 与计划任务的对应关系

| 任务 | 实现证据 |
| --- | --- |
| R2.1 单次 catalog | `runtime.py`、`mcp.py`、`cli.py` 传递同一对象；安装态测试用对象身份断言 |
| R2.2 三个 operation 接口 | Root 工具清单新增 catalog/preflight/invoke，并新增纯 inventory |
| R2.3 Agent 创建 | 复用 `task_schedule` 隐藏编译调用分支，生成既有 output/budget/context 合同 |
| R2.4 Transform 创建 | `CompiledTransformAdapter` 进入既有 transform 路径 |
| R2.5 Effect 创建 | 生成既有 ExecutionRequest，状态保持 `awaiting_approval` |
| R2.6 谱系与幂等 | 任务 fingerprint、权限摘要和三类 Artifact 标签覆盖 operation 身份 |
| R2.7 旧入口对照 | 旧创建工具仍存在但没有成为 operation 实现依赖之外的新权威 |
| R2.8 竞态一致性 | current 在 preflight 后改变会使 invoke 重预检失败且无任务写入 |
| R2.9 恢复边界 | operation 摘要漂移阻止 dispatch；旧任务状态与比较并交换逻辑未复制 |
| R2.10 纯清单 | 新路径只读取 `scientific_inventory`，不消费旧领域候选 |
| R2.11 最小授权 | 精确输入、工作区、网络和资源摘要嵌入任务；Worker 服务端默认拒绝 |

## 5. 验证证据

| 检查 | 结果 |
| --- | --- |
| `python -m py_compile .../mcp_root.py operations/invoke.py` | 通过 |
| `pytest -q tests/operations` | 63 项通过；包含仓库外 clean-wheel 安装入口 |
| `pytest -q` | 94 项通过 |
| 真实 Codex 原型 run 6 | 结构化事件确认 `spawn_agent`、专属 `agent_type` 和父会话零 Worker 调用；注册领域工具、受控写入、校验与封存全部通过，任务 `completed` |
| `git diff --check` | 通过 |
| `python -m compileall -q src ...` | 通过 |
| `wc -l operations/spec.py operations/catalog.py operations/invoke.py` | 311 / 436 / 421；合计 1168。分项预算在总额不变的前提下由 300/400/500 一次性重分配为 320/450/430：新增额度只覆盖原生工具策略、领域工具协议和审查端口闭包，统一调用少用的 70 行预算被收回；三个文件均有 9—14 行余量 |
| SQLite migration | 未新增、未修改 |

安装态集成测试覆盖：catalog 对象共享、调度器投影不泄漏实现身份、预检纯读、Agent 创建与
权限持久化、精确 Worker 工具注册与伪造调用拒绝、目录摘要漂移拒绝恢复、跨 scheduler/task
数据库的检查—提交原子性、Transform 幂等与谱系、由 spec 投影的 Effect 审批合同、稳定编码
错误以及未声明参数拒绝。

8765 基线仍没有 `scripts/validate_architecture_constraints.py`，不能声称该脚本通过。33 项约束
由现有行为回归、安装态跨边界测试和待执行的独立审查覆盖。

## 6. 尚未完成且不得提前宣称的内容

- 六个通用角色和通用变换尚未迁移到 spec 生成合同；
- prompt/skill、逐 operation 工具清单、受限网络和单任务原生路径的运行平台配置尚属 R3；
- TCAD、curve-score、领域 UI 呈现和插件旧入口删除尚属 R4、R5；
- 尚未证明第二领域可以零核心修改接入，也没有进行真实 TCAD 执行；
- 旧 Root 创建工具仍在过渡期存在，R5 必须在迁移完成后删除，不能永久保留双入口。

## 7. 首轮独立审查结论

首轮结论为“打回”，不允许进入 R3。阻塞项是：任务权限仍是描述性摘要而非真实 Codex
派发边界；spec 的 prompt/model/workspace/tool/output 行为被旧角色合同替代；current 等可变
谓词存在检查—提交竞态；Effect 的声明输出和审批合同与实际请求/UI 不一致；非法 Unicode
instruction 没有稳定 reason code；并且缺少真实 `spawn_agent` 的原生工具、领域工具、受控文件
和恢复链验收。完整证据见 `reviews/R2_UNIFIED_OPERATION_INVOKE_INDEPENDENT_REVIEW.zh-CN.md`。

用户进一步冻结了复审门：必须真实启动控制进程和 Worker broker，并以 `spawn_agent` 拉起
真实 Codex 子 Agent；Agent 实际使用 spec 声明的原生或受控等价文件能力与已注册领域工具，
完成 validate/finalize/reconcile，同时证明未声明工具、网络和兄弟路径不可用。直接调用工具
handler、模拟 Worker 或只检查配置文本均不算通过。

只有完成 R2.12—R2.17、重新通过自动化验证，并由独立复审明确给出“通过”，主计划才能把
R2 标为通过并允许进入 R3。

## 8. 真实 Codex 验收与平台边界

真实验收器位于 `tests/operations/live_operation_agent_qualification.py`。它使用独立持久状态目录，
启动真实 Root daemon 和 Worker broker，经 `operation_invoke` 建立并派发架构任务，再运行真实
`codex exec` 父会话并调用 `spawn_agent`。每次失败均保留 report、事件流、父/子 rollout 和守护
进程日志，不用模拟结果覆盖失败。

- run 11 证明仅生成 `.codex/agents/*.toml` 不会自动注册角色；随后配置生成器增加了明确的
  `[agents.<type>]` 注册。
- run 12 复现 Codex CLI 0.150.1 的项目级角色注册未进入 `spawn_agent` 参数模式；run 13 通过
  会话级重申同一生成配置后，子会话元数据明确记录了编译得到的 `agent_role`，专属 prompt 生效。
- run 13 仍为失败：子会话没有获得角色文件声明的 Worker MCP；只读原生 shell 在启动命令前
  因 bubblewrap 需要写 `/tmp` 锁文件而失败，任务保持 `dispatched`，没有领域工具收据和输出。
- 对应版本官方源码 `codex-rs/core/src/agent/role.rs` 的 `AgentRoleOverrides` 只投影提示、模型、
  少量可降权 feature 和 skill 禁用项；测试 `apply_role_cannot_expand_parent_authority` 明确断言
  `mcp_servers`、`sandbox_mode`、permissions 等保持父会话值且不进入角色层。因此这不是继续
  修改角色 TOML 就能关闭的缺陷。

当时的独立复审结论为“打回”，见
`reviews/R2_CODEX_AGENT_AUTHORITY_PLATFORM_REVIEW.zh-CN.md`。不得将 Worker MCP 提升到调度
父会话来制造通过；那会使调度者获得 Worker 权限，违反最小授权。也不得把“专属角色已启动”
误写成“真实工具链已通过”。下一步只能二选一：要求具备角色级工具/沙箱可信委派的 Codex
版本，或经用户明确修改“必须由内部 spawn_agent 派发”的决定，改用每任务独立 Codex 进程
边界。用户随后为首版原型明确放宽为“基础权限继承 + 提示词行为白名单”，因此本节仅保留为
生产级最小授权尚未解决的历史证据，不能再作为当前快速闭环路径的实现指令。

## 9. 下一版本保留的独立 Codex Worker 加固基座

以下代码已经实现并保留，但不接首版默认 Root 调度入口、不再阻塞 R2 快速闭环。它只替换
Agent 的传输与启动边界，不增加 `OperationRun`，也不复制 Task 状态机：

```text
operation_invoke
→ 现有 TaskService 创建任务
→ Root 精确派发并签发 task/attempt/authority/worker/proxy 绑定能力
→ 可信 supervisor 写入私有能力文件并启动 codex exec --json
→ 专属 Worker proxy 注入传输元数据
→ 现有 Worker MCP、受控文件、validate/finalize/reconcile
```

冻结约束如下：

- capability 正文不得作为命令行参数、普通环境变量或提示内容交给模型；
- Worker 只能领取 capability 指定的 task/attempt，不能再按角色领取队首任务；
- 同一 capability 与稳定 proxy 在 broker 重启后只恢复原 durable session，不生成新 attempt，
  不续期绝对 deadline，也不切换任务；
- Codex JSONL、退出码和最终消息仅是有界运行诊断，不能把 Task 标为科学完成；
- Task 状态、活动事件、受控文件和 checkpoint 仍是唯一可恢复进度；
- 当前架构验收 operation 关闭无法按精确路径安全收窄的原生 shell 与网络，文件访问使用已
  注册的受控 Worker 工具；原生 TCAD 调试 shell 的进一步隔离不在 R2 内扩张实现。

该路径已用自动化测试覆盖精确认领、防伪私有能力文件、错误 proxy/能力拒绝、同一 session
恢复不续期，以及独立进程配置和有界 JSONL 诊断。认证注入、真实原生工具隔离与进程级恢复
留待下一版本单独审查。proxy 和 authority 仍由签名 capability 与 token 哈希绑定，没有为这条
未启用路径提前修改令牌数据库 schema。

## 10. 首版快速闭环决策

首版回到现有 `task_prepare_dispatch → spawn_agent` 路径。调度父会话在启动期获得 Agent
operation 所需的基础 Worker MCP 集合，Codex 0.150.1 子 Agent 继承这些基础权限；编译 prompt
明确本次只允许使用的 MCP、skill 和文件能力。服务端 Task/Artifact/validator/finalize、审批 UI
和 Effect 外部副作用门仍是硬边界。

必须诚实记录：提示词不能构成安全隔离，因此首版只验收隔离架构 operation 与无真实副作用
adapter；真实 TCAD、生产凭据、网络写入和不可逆动作不得依赖该约束放行。R2 快速闭环完成门是
真实子 Agent 调用指定领域工具，经过受控文件生命周期完成 validate/finalize，并由调度端观察
任务已进入 `completed`，再由
独立审查确认没有复制状态机、没有绕过控制面门禁、没有把原型行为约束冒充生产权限隔离。

真实通过证据保存在仓库本地持久目录
`.scidiscovery-state/r2-live-prototype-run6/`。`qualification-report.json` 的 SHA-256 为
`e62e17c0ae6a2c2910fae0ef18bbfbc2c252c5c0772271e64c59c41cde48009a`；验收器结构化解析事件，
确认真实 `spawn_agent` 有接收线程、子会话的 `agent_role` 等于编译角色，且父会话没有调用
`worker_*`。任务记录包含 `operation_tool_succeeded:worker_fixture_inspect`，最终输出精确为
`{"input_seen":true,"tool_result":"fixture-inspected:registered-domain-tool"}`。此前失败 run 2—4
同样保留，分别证明配置未装入隔离 `CODEX_HOME`、输出 schema 门拒绝错误值，以及补丁易用性
问题；没有用模拟结果覆盖这些失败。

第二轮独立审查见
`reviews/R2_FAST_PROTOTYPE_INDEPENDENT_REVIEW.zh-CN.md`，结论为“通过，允许进入 R3”。该结论
不把提示词白名单提升为生产安全隔离，也不授权真实 TCAD、生产凭据、网络写入或不可逆动作。
