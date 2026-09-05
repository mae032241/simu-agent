# R5-L2 最小本地 Run 实现独立审查

日期：2026-09-01  
审查者：`r5s_s0_independent_review`（未参与实现）  
结论：**不通过（FAIL）；不得放行 L3—L6**

## 1. 审查边界

本轮以实现方确认冻结后的工作树为对象，只审查、不修改生产代码。关键候选摘要如下：

- 活动计划：`c4b5aa10c82718b95e546fc3e5e1184c82806c6a735715ec5316bcff374b0c92`；
- `runtime.py`：`342a2d699c4f7e85747e1a457b958b2e86c370f49f5e634160b6fa444e2432ce`；
- `mcp_root_operation_routes.py`：`bfa31dfabcd1a749cf43c1b0185d1b3c127fca40fc364b664e5cc4e193286d10`；
- `mcp_local_worker.py`：`0c81a8b66856d3cd636d92499dea7e489b65f6efc911d6ffa55ebbef60a58248`；
- `runs.py`：`8345c2bbd0e09d58b9240fe9270f562779fac27e547b2524a0e7b46441f7bd59`；
- `run_current.py`：`437b1c6578b107cc689678eb2f3f1aaf69542ed1e3f98b8a57dde8c372a778f2`；
- `local_workspace.py`：`1ef076656f56e319c34cc62a48287004e1584df878fbc62098ccae9c8d3cfc26`；
- `operation_tool_context.py`：`c196563732395c8f33ccb4909b96f02d9ca81c81c2b68104ecea635e07ff30e3`；
- `platforms/codex.py`：`e668ef6e3edc7aa81d64799a0dd3889c198cdd77c7449a248806bade03520fce`；
- L2 聚焦测试：`0c7f45e9eb13a412388c825aa938aaf726f7d2a3a1cf5380852f48c16de4da03`。

审查依据为活动计划 L2 完成门、设计宪章、33 项约束以及真实默认入口。没有继承 L0/L1 的历史
verdict，也没有把实现方给出的测试数量视作语义正确性的替代品。

## 2. 已成立的部分

以下实现方向是正确的，但不足以抵消后文阻断：

1. 默认 `RootToolFacade` 在存在 `runs` 时，Agent 类型的 `operation_invoke` 只调用
   `_invoke_local_run`，聚焦测试也证明旧 `TaskService.ready()` 为空；该顺利路径没有同时创建 Task。
2. `LocalTrustedBackend` 当前只负责目录准备、打开、存活探测、封存和删除；未发现它登记 Artifact、
   写 Run 终态、解释科学 verdict 或更新 current。
3. 顺利提交路径的输出合同校验、Artifact 登记和 Run 终态都位于 `RunService`；盲 CSV 的确定性工具
   也来自插件注册，没有在核心按领域名称分支。
4. 新 Run 代码按记录、assignment、current、输出校验、工作区和 MCP 路由拆成窄文件；最大新增文件
   `runs.py` 为 470 行，未形成单一巨型类。九个新增 Run/Local 文件共 1599 行，规模本身不作为失败
   理由，但其重复投影已经造成真实合同断裂，见阻断 5。
5. `OperationToolContext` 的字段表面没有 `Run/Task/token/session/control database/current writer`，领域
   工具也没有 Artifact 登记或 current 写接口。

## 3. 阻断项

### B1：Run 并未实现计划规定的递归 currentness 和提交时精确 CAS

**证据。** `run_current.py:27-63` 读取实例下所有 current ref，然后只要输入 Artifact 是其中任意一个
ref 的后代就视为匹配。冻结记录只有 `current_anchor_refs: tuple[ArtifactRef, ...]`，没有
`(instance, semantic_name, ref)`、生产 Run 或生产收据。这样一个对象只要偶然继承了另一个语义
head，就可能通过不属于自身语义 lineage 的 `require_current`。

`runs.py:264-285` 在封存和 Artifact 登记前于独立连接检查 current；`runs.py:210-261` 随后登记
Artifact 并在另一数据库事务里写 completed，事务内部没有重新检查锚点，也没有 head CAS、
`head_advance=advanced/stale_rejected/not_requested` 收据。因此 current 可在校验与完成之间变化，
形成明确 TOCTOU。

当前树没有任何生产或 fixture Operation 声明 `require_current=True`。所谓 current 测试
`test_l2_local_run.py:200-239` 只直接测试旧 `SchedulerBindingService.select_scientific_object` 的普通
CAS，既没有创建 Run，也没有覆盖递归 stale 后代、并发推进或提交 CAS，不能证明 L2 current 完成门。

**影响。** stale 科学后代可被完成；反过来，无关 current 祖先可误使输入通过。计划第 5.3 节、
`AUTH-001`、`LIN-002` 和 `CQRS-002` 未满足。

**最小修正边界。** 不增加第二 current 实体；把精确语义锚点和生产 Run/收据冻结进 Run 请求，使用
同一个递归判定函数覆盖 preflight/invoke/submit，并在完成控制事务内重检后一次性写完成收据和至多
一个 head CAS。必须增加真正经过 Run 的 stale descendant、错误 lineage、并发推进和部分成功负例。

### B2：候选摘要单调绑定、唯一完成收据和崩溃恢复尚未实现

**证据。** `runs.py:424-451` 的 Run 表没有 `accepted_candidate_digest`、完成收据、head 结果、后端
版本/能力投影或完整请求摘要。每次 `submit` 都重新 seal；首次完整校验后没有 CAS 绑定候选摘要。
`runs.py:210-261` 先向 ArtifactService 登记，再写 Run 终态，中间崩溃后只能依赖 Artifact
idempotency key，无法证明后续重试仍完成同一候选。

`_mark_failed`（`runs.py:384-407`）仅尽力 seal 当前输出并把候选目录名写入
`recovery_snapshot`。没有写入者终止证明或 fencing、隔离旧工作区、恢复 manifest、`resume_from`
完整指纹、显式新 Run 恢复入口，也没有计划第二轮审查要求的三类崩溃窗口测试。源码搜索未发现
`accepted_candidate_digest`、`completion_receipt`、`head_advance` 或 `resume_from`。

**影响。** Artifact 后/Run 完成前崩溃、响应丢失和失败恢复的单调性不可证明；旧写入者与恢复草稿
边界也未闭合。`IMM-001`、`IMM-002`、`RES-002` 和计划已审定的提交协议未实现。

**最小修正边界。** 只实现计划已经批准的一个候选摘要字段和一个完成收据，不新增状态。首次校验
CAS 绑定摘要；重试只能完成同一摘要。恢复先 CAS 失败并 fence/隔离旧写入者，再产生带原 Run、请求
摘要、后端版本、文件摘要和原因的 backend-private 草稿；显式新 Run 才能 `resume_from`。用真实
进程故障覆盖 seal 后、Artifact 后终态前、completed 响应丢失三个窗口。

### B3：`run_status` 和 `run_list` 会写状态，直接违反查询纯读约束

**证据。** `RunService.status` 在 `runs.py:292-299` 发现 deadline 经过后调用 `_mark_failed`；`list`
在 `runs.py:301-310` 又逐项调用 `status`。Root 的 `run_status`、`run_list`、`lifecycle_events`、
`instance_close` 都会经过这些方法。因此读状态会封存草稿、写 failed、reason、completed_at 和
recovery_snapshot。

**影响。** 同一过期 Run 是否失败取决于是否被查询，且 GET/状态观察拥有运行命令副作用。这是
`CQRS-001` 明文禁止的行为，也绕过了已经存在的显式 `run_record_failure`。

**最小修正边界。** `status/list` 必须纯读；timeout/crash 由一个幂等 reconcile/失败命令按 CAS 推进。
增加查询前后数据库摘要不变、重复 reconcile 幂等和并发 heartbeat/timeout CAS 测试。

### B4：所谓显式 Hardened 配置与生产 Root 路由并未闭合，默认运行仍装载两套权威表面

**证据。** `platforms/codex.py:85-148` 的 `worker_backend="hardened"` 只改变 Agent/MCP 配置；
`build_root_router` 没有 backend 参数，并始终把 `runtime.runs` 传给 Root（`mcp.py:67-95`）。
`_invoke_agent_operation` 又只按 `self.runs is not None` 选择 Local（
`mcp_root_operation_routes.py:140-145`）。而 `open_runtime` 永远同时构造 TaskTokenService、TaskService、
LocalTrustedBackend 和 RunService（`runtime.py:72-92`）。所以生成 Hardened profile 后，Root 仍创建
Local Run，Hardened worker proxy 却去旧 Task/Unix 路径领任务；两端没有共同对象。

同时默认 Root 仍公开 `task_ready/task_list/task_status/task_prepare_dispatch/task_retry` 等旧 Task 工具，
默认部署仍启动 `scidiscovery-worker.service`。这不只是尚待 L6 删除的死代码：显式 Hardened 选择当前
会产生可编译但不可执行的断裂组合。

**影响。** “Local 默认、Hardened 显式保留”只在配置生成单测中成立，真实调用会队列错位；默认
复杂度也尚未达到 L2 完成门所说的单一有消费者 Run 状态。`AUTH-001`、`ROLE-002`、`MIG-002` 及
两后端同一调用入口原则未满足。

**最小修正边界。** 不建立第二 invoke。部署应冻结一个 backend 选择并让 Root、Agent profile、MCP
和 daemon 读取同一选择：Local 创建 Run 并直连本地 worker；Hardened 要么在 L5 前明确不可启用，
要么其私有传输也必须绑定同一 Run。不能继续让 Root 创建 Run 而 proxy 消费 Task。默认 Local 不应
启动或暴露无消费者的 Task/token/worker daemon 表面。

### B5：assignment、Agent 提示和实际 Local MCP 是三份不一致的工具投影

**证据。** `run_assignment.py:45` 使用完整 `operation_worker_tool_names`，而 Codex Local profile 在
`platforms/codex.py:345-352` 自行过滤有 handler 的领域工具，Local Router 又在
`mcp_local_worker.py:49-51,248-254` 重复同一过滤逻辑。对本轮盲 CSV 作者独立复算得到：

```text
assignment/full = open, heartbeat, submit, file_write_begin, file_write_chunk,
                  file_write_commit, csv_summarize
local/exposed    = open, heartbeat, submit, csv_summarize
```

因此 assignment 明示三个 Agent 实际不可调用的文件工具。更严重的是，所有盲插件角色仍以前置文本
`OPERATION_AGENT_PREAMBLE` 开头；`operation_declaration.py:25-44` 要求 claim/materialize、禁止原生
写、只能用 Worker 文件工具并调用 validation/finalization。随后拼接的 Local 指令
`platforms/codex.py:355-388` 却要求 open、允许原生写、只用 submit。模型同时收到互相否定的合同。

Local submit 还保留 `valid` 过渡字段（`mcp_local_worker.py:81-95`），与 L0 冻结账本“L2 删除该字段”
不一致。

**影响。** 这正是此前架构要消除的多投影行为断裂。虽然各投影都从同一 Catalog 读取，却以三套
手写过滤/提示语义解释它，违反 `AUTH-003` 和 `ROLE-002`。进程内测试绕过了 Agent 对提示和
assignment 的理解，无法暴露故障。

**最小修正边界。** 从唯一运行投影一次生成 Local 的工具名、assignment 和提示；不要再在 platform、
Router 和 assignment 分别过滤。Local prompt 只描述 open/native workspace/submit，Hardened prompt
只描述受控文件协议。删除过渡 `valid`，以 `state + diagnostics/receipt` 表示一次提交结果。

### B6：`OperationToolContext` 仍通过绝对工作区路径泄漏精确 Run 身份

**证据。** 字段名测试只检查 dataclass 中没有名为 `run_id` 的字段
（`test_l2_local_run.py:193-197`）。实际 `LocalTrustedBackend` 直接以精确 `run_id` 创建
`.../local-runs/run_<uuid>`（`local_workspace.py:74-99`），Worker open 返回该绝对路径
（`mcp_local_worker.py:132-137`），并把同一路径放入 `OperationToolContext.workspace` 和
`output_directory`（`mcp_local_worker.py:163-172`）。领域工具读取 `context.workspace.name` 即得到
内部 Run id，也能看到宿主 state 路径。

**影响。** API 没有显式控制字段，但通过文件名暴露了同一控制身份；这不满足 `AUTH-002` 的“不得
通过文件名暴露控制身份”，也没有达到计划复审要求的身份无关路径。

**最小修正边界。** 保留本地绝对路径能力，但 Worker/插件可见目录名不能等于控制 Run id；使用
backend-private 随机目录/挂载别名并只在 backend 私有映射中关联 Run。测试必须检查实际返回值和
领域工具观察到的值，而不是只检查字段名称。

### B7：没有真实 stdio Worker 进程，更没有真实 `spawn_agent` 证据

**证据。** 本轮唯一 L2 测试直接在测试进程构造 `LocalWorkerMCPRouter`，再由测试代码用
`Path.write_bytes` 代替 Agent 写结果（`test_l2_local_run.py:98-175`）。没有启动
`python -m ...mcp_local_worker`，没有经过正式生成/安装 profile，没有调用真实 `spawn_agent`，也
没有证明模型能在矛盾提示下正确调用领域工具、原生读写并 submit。当前没有 L2 实践证据文件；活动
计划首页仍准确写着“L2 实施中，最小 Run 尚未完成”。

**影响。** L2 最明确的用户要求和完成门——真实拉起通用 Codex Agent，验证原生读写与注册工具——
完全无证据。`ROLE-002`、`SEC-002` 的已知问题边界和 `MIG-002` 真实安装入口都不能由进程内单测外推。

**最小修正边界。** 在以上合同问题修复后，至少用正式生成的 Local profile 运行一个真实父调度
`spawn_agent(fork_turns="none")`：子 Agent 经真实 stdio MCP open，读取精确 CSV，调用注册工具，
原生写 `output/result.json`，经历一次可修正拒绝或直接完成，再由 Root 只读 sealed Artifact。证据需
保留工具顺序、配置摘要、Run 状态和 Artifact 父链，但不能把 child chat 当科学结果。

### B8：Local seal 尚未实现计划承诺的发布边界检查

**证据。** `local_workspace.py:125-183` 只检查符号链接、普通文件、路径逃逸、文件数和总字节，并
按扩展名猜媒体类型。没有秘密模式、机器路径、未声明二进制/媒体类型检查。当前最小 Run 又强制只有
`result.json`，JSON/Schema 校验并不能阻止自由文本字段携带宿主路径或凭证。

**影响。** Local 可以保持 `SEC-002 known_issue`，但该 known issue 是原生工具隔离，不等于放弃计划
6.2 已明确承诺的发布检查。否则受提示约束的 Agent 可把宿主路径或秘密写入正式 Artifact。

**最小修正边界。** 复用已有发布内容扫描/媒体约束，不新增策略注册表；在 seal 或纯输出校验阶段
统一拒绝机器路径、明显秘密和未声明二进制，并增加正反例。若决定不做，必须先修订并重新审查计划，
不能在实现阶段静默降低边界。

## 4. 测试复核

独立运行：

```text
python -m pytest -q tests/operations/test_l2_local_run.py
3 passed in 1.68s

python -m pytest -q \
  tests/artifact_agent/test_platform_configuration.py \
  tests/operations/test_worker_exact_dispatch.py
23 passed in 9.89s
```

这些结果证明顺利的进程内 Local 路径、配置文本生成和既有 Hardened 精确 dispatch 单测仍可运行；
它们没有覆盖 B1—B8 的真实跨边界场景。实现方报告的 81 项聚焦通过和非 live 298 项回归不改变这一
结论，因为缺失的是语义场景和真实进程/Agent 证据，不是更多同类测试数量。

## 5. 非阻断建议

1. 当前拆分方向总体合理，但 `mcp_root_operation_routes.py` 仍有 1309 行、`platforms/codex.py` 有
   749 行。不要仅按行数继续拆；先消除 Local 工具投影和后端选择的重复权威，再按职责抽取纯函数。
2. `RunService` 构造参数直接标注 `LocalTrustedBackend`。L2 可先只实现 Local，但应以计划已冻结的
   五方法窄协议表达依赖；否则 L5 接 Hardened 时容易再次在核心按后端分支。
3. 同一 operation digest 的全局唯一活动槽会串行化不同 ResearchInstance。计划只要求第一版避免按
   角色误领，是否应按 `(instance, operation_digest)` 限制需在真实并发试验后决定；当前不作为阻断。
4. 不要为了修复本报告增加 `CurrentPolicy`、`ReceiptManager`、`BackendRegistry` 等新实体。现有 Run
   记录、SchedulerBindingService、一个 backend 选择和一个完成事务足以闭合这些问题。

## 6. 最终判定与返修门

**L2 不通过。不得进入 L3，也不得以“先在 L3 跑真实 reviewer”补做 L2 的真实 Agent 证据。**

下一轮复审至少需要：

1. B1 的真正 Run current/stale/CAS 正反例；
2. B2 三个崩溃窗口、候选摘要和恢复 fencing 证据；
3. B3 查询纯读与显式 reconcile 证据；
4. Local/Hardened 同一部署选择的端到端路由证据；
5. assignment/profile/Router 工具集合逐项相等且提示无矛盾；
6. 实际值层面的身份无关路径测试；
7. 正式 profile 下真实 `spawn_agent` 完成 open—领域工具—原生写—submit—sealed Artifact；
8. Local 输出发布边界正反例，以及 L0 Hardened 防腐回归继续通过。

满足这些条件并经独立复审前，当前实现只能称为“最小 Run 顺利路径原型”，不能称为已完成的 L2。
