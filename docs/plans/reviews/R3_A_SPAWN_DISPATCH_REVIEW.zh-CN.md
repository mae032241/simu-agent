# R3-A 默认 `spawn_agent` 派发独立复审

日期：2026-08-28  
基线：`baseline/8765-codex@404aeb1`，叠加当前共享工作树中已通过的 R0—R2 与 R3-A 修复  
审查性质：未参与本轮实现的跨边界只读复审；本报告不覆盖历史审查

## 结论

**通过，可恢复 R3-B。**

本轮没有发现阻断项。当前默认 Operation Agent 路径已经恢复为
`task_prepare_dispatch → spawn_agent`；保留的独立 `codex exec` 适配器没有生产接线。
Agent 类型、prompt、模型、原生工具声明、精确 Worker 工具和调用期 Task 权限均由同一
`CompiledCatalog/OperationSpec` 投影。新的真实 run 5 证明了子 Agent 的原生代码工具以退出码
0 成功、已注册领域工具真实成功、父会话没有代调 Worker、结果经受控文件生命周期校验并封存，
Root 最终观察到 `completed`。

这里的“通过”只覆盖已冻结的快速原型边界。Codex 0.150.1 下，子 Agent 继承父会话基础能力；
提示词白名单是可审计的行为约束，不是操作系统级隔离。该事实已在代码、生成配置和当前计划中
如实表达，因此不能据本结论放行真实 TCAD、副作用、生产凭据、原生网络写入或不可逆动作。

## 1. 发现与处置

### 阻断项

无。

### 非阻断项与后续边界

1. `qualification-report.json` 中的 `network_denied=true` 和
   `sibling_read_denied=true` 是 Agent 按 assignment 确认的合同字段，不是一次真实原生网络/兄弟
   路径攻击试验。run 5 因而只证明提示约束被遵守；它没有证明原生网络或原生写入硬隔离。
   当前实施记录已明确限定这一点
   （`docs/plans/R3_GENERIC_OPERATIONS_IMPLEMENTATION.zh-CN.md:151-161`）。
2. 父配置必须公开各 Operation 的继承用 Worker MCP，子 Agent 可能看见其他服务器；当前版本
   以编译提示禁止跨 Operation 使用。Task/Worker 服务端仍按实际认领任务的 authority 校验工具、
   capability、网络、输出与 finalize，但平台层“未声明工具完全不可见”仍属于下一版本独立进程
   加固目标，不能从本轮结论外推。
3. `task_prepare_dispatch` 使用既有按 Agent 类型领取队列，而不是独立进程的精确 transport
   capability。同一 Agent 类型存在多个已派发任务时按队列顺序领取；这符合当前冻结的快速闭环，
   且不会扩大该 Operation 的权限，但不应被描述成“每个 spawn 与指定 task 的密码学精确绑定”。
4. 核心 `spec/catalog/invoke` 已达到 1196 行预算上限附近。R3-B 可以恢复，但不得继续把派发、
   生命周期或科学流程逻辑塞回这三个文件；旧角色/profile 分支的实际删除仍应由 R3-D 完成。

以上均为计划已承认的原型限制或后续清理门，不阻断无真实副作用的 R3-B 继续开发。

## 2. 默认派发路径

- Root 的 `task_prepare_dispatch` 只解析命名 Task、调用既有 `TaskService.prepare_dispatch`，并从
  Task 的 compiled authority 返回 `agent_type`；它不创建或调用独立 Codex 进程
  （`src/scidiscovery/artifact_agent/interfaces/mcp_root.py:1993-2002`）。
- `RootToolFacade` 只有 `operation_catalog`，没有 dispatcher 字段
  （`src/scidiscovery/artifact_agent/interfaces/mcp_root.py:443-473`）。生产 Root router 从
  `open_runtime` 取得同一 catalog，构造参数中不存在 Codex 独立进程配置
  （`src/scidiscovery/artifact_agent/interfaces/mcp.py:82-122`）。
- `open_runtime` 在启动期调用一次 `compile_installed_catalog()`，把同一对象同时交给
  `TaskService` 和 runtime 返回值（`src/scidiscovery/artifact_agent/runtime.py:73-117`）。
- 对当前 `src/scidiscovery/**/*.py` 的搜索表明，`CodexTaskDispatcher` 只有类定义和测试中的显式
  构造；生产入口没有构造点。`platforms/codex_worker.py` 与
  `service/agent_dispatch.py` 因而只是非默认的后续加固代码。
- `tests/operations/test_codex_task_dispatch.py:22-170` 同时验证：Root 准备派发不会启动 Codex
  进程；只有测试显式构造 dispatcher 时才进入保留的独立进程路径。

该实现符合 R2.14、R2.18 与 R3 当前不可覆盖的产品决策，没有再次用“隔离更强”的实现替换
用户要求的快速闭环。

## 3. 单一编译权威与投影闭合

### 3.1 唯一目录

- 安装插件只从 `scidiscovery.plugins` entry point 读取，`compile_installed_catalog()` 有单例缓存，
  编译结果为一个排序的不可变目录
  （`src/scidiscovery/operations/catalog.py:417-449`；`pyproject.toml:26-28`）。
- `CompiledOperation` 的摘要覆盖 OperationSpec、可达组件、权限模板和 reviewer 摘要；Agent
  Task 输出投影在 catalog 编译期即被验证，不能把不可表示合同留到 Worker 运行时
  （`src/scidiscovery/operations/catalog.py:395-430`）。

### 3.2 Agent 配置与 Task 权限同源

- Codex 安装从传入的同一 catalog 枚举 Agent Operation，并生成 Agent 注册、prompt、模型、
  原生工具开关和继承用 Worker MCP；没有按 role/profile 补 Operation 权限
  （`src/scidiscovery/platforms/codex.py:74-176`、`:361-414`）。
- 安装后 probe 反向校验 Agent 集、MCP 集、模型、原生工具声明、prompt 约束和每个 Operation
  的精确 Worker 工具集，任一漂移均失败
  （`src/scidiscovery/platforms/codex.py:199-295`）。
- 调用期 `_agent_authority()` 从 compiled permission template 派生 operation/version/digest、
  Agent 类型、capability、精确 Worker 工具、模型、工作区、原生工具、网络和资源边界，并把
  authority 摘要写入既有 Task；没有第二份角色权限表
  （`src/scidiscovery/operations/invoke.py:316-364`）。
- `WorkerMCPRouter` 只为与当前 `worker_id` 对应的精确 compiled operation 解析插件工具
  （`src/scidiscovery/artifact_agent/interfaces/mcp_worker.py:291-335`）。调用后，服务端再次核对
  当前 Task authority 的 capability 和工具名；注册工具处理器只获得已校验请求
  （同文件 `:337-415`；`src/scidiscovery/artifact_agent/service/tasks.py:1421-1506`）。
- Operation Task 在 schedule、assignment、主输出、附件 item/bundle validator、context
  validator、修订边界和 finalize 路径上读取 Task 中冻结的 authority；旧 role/profile 分支只在
  `operation_authority is None` 的 legacy 路径可达
  （`src/scidiscovery/artifact_agent/service/tasks.py:436-508`、`:1320-1419`、`:3540-3721`）。

未发现 Agent Operation 的 role/profile fallback、按 operation id 的 Root/TaskService/UI
allowlist，或与 `CompiledCatalog` 平行的注册权威。

## 4. 真实运行证据独立核验

有效证据为
`.scidiscovery-state/r3-spawn-agent-native-run5/qualification-report.json`。报告记录 11 项检查均为
真、Operation 类型为 `op_builtin_test_agent_b71a4a7b2bf2`、原生策略为
`inherited_prototype`、网络合同为 `none`、精确 Worker 工具共八个，最终 Task 与 Root 状态均为
`completed`（该文件 `:1-71`）。我没有依赖报告摘要，而是逐行检查两份保留的 rollout JSONL：

- 父会话第 22 行真实调用 `spawn_agent`；父 rollout 的函数调用只有 `spawn_agent` 和
  `wait_agent`，没有任何 `worker_*` 调用。
- 子会话第 47/49 行的 `exec_command` 与同一 `call_id` 对应，命令读取精确任务本地
  `assignment.json`，输出明确为 `Process exited with code 0`。
- 子会话第 59/61 行真实调用 `worker_fixture_inspect`，返回
  `fixture-inspected:registered-domain-tool`；Task 活动收据与之吻合。
- 子会话第 79、85、89 行依次通过 Worker 文件接口创建、传输并提交主输出；第 93/95 行
  `worker_validate_output_file` 返回 `valid=true`；第 101/103 行
  `worker_finalize_file` 返回 `state=completed`。
- 报告内的父事件、两份 session JSONL 均带 SHA-256；独立重算与记录一致。

旧 run 3 的报告仍显示 `pass`，但用当前检测器重放得到
`compiled_native_code_succeeded=False`；其两次原生命令实际均为退出码 101。run 4 也为
`False`。run 5 才重放为 `True`。当前实施记录已把 run 3 定义为旧检测器误判的失败证据，而非
删除或改写历史报告（`docs/plans/R3_GENERIC_OPERATIONS_IMPLEMENTATION.zh-CN.md:158-162`、
`:204-208`），决定语义已一致。

## 5. 误判修复与负边界

- 当前资格检测器先在正确子角色会话中收集原生命令 `call_id`，再只接受匹配的
  `function_call_output` 中明确的退出码 0；已删除“只看到调用”或“会话 completed 即成功”的
  捷径（`tests/operations/live_operation_agent_qualification.py:94-137`）。
- 新回归分别固定退出码 101 必须为假、匹配退出码 0 才为真
  （`tests/operations/test_live_qualification_evidence.py:17-59`）。
- Operation 附件集合、修订范围、精确 Operation 工具解析和受控输出失败关闭由
  `tests/operations/test_r3_agent_contract.py` 覆盖；受限域名、重定向和请求预算的服务端网络门由
  `tests/operations/test_operation_network_authority.py` 覆盖；默认/保留派发分界由
  `tests/operations/test_codex_task_dispatch.py` 覆盖。

本轮真实 run 没有故意发起原生越权写入或网络请求，这是正确的安全界线：当前
`inherited_prototype` 没有声称能在平台层拒绝它们，不能用模型自律测试冒充硬隔离。服务端
Worker/Task/输出/网络副作用边界由代码与负例测试证明；原生能力的平台级隔离留给明确授权的
下一版本。

## 6. 33 项约束族不退化判断

计划明确把 33 项约束当作行为验收矩阵，而不是新增 33 个实体或状态。按其约束族复核如下：

| 约束族 | 本轮判断 | 证据摘要 |
| --- | --- | --- |
| 唯一权威、不可变性、谱系、外部证据 | 不退化 | 只有一个 compiled catalog；operation/version/digest 与 authority 摘要进入既有 Task/Artifact 链；没有 OperationRun 或第二事件存储 |
| Worker 上下文、默认拒绝、服务端授权 | 在冻结原型边界内不退化 | 输入、Task 私有工作区、Worker 工具、网络和输出从 exact operation 派生；未声明 Worker capability 服务端拒绝；父能力可见性被如实限定为提示约束，不冒充硬隔离 |
| qualification/current/人工决定/CQRS/副作用/恢复 | 不退化 | 本轮复用既有 Task、Approval、Execution、CAS/finalize；没有资格/current/审批副本，也没有真实 adapter 或人审旁路 |
| 科学责任与确定性边界 | 不退化 | Root 只准备 Task 和返回编译 Agent 类型；真实科学内容仍应由子 Agent 写入受控文件，父会话零 Worker 代写；validator、codec 和门禁只做确定性合法性检查 |
| 插件解耦、轻控制面、复杂度 | 不退化 | 配置和运行时均从单一插件目录投影；Root/TaskService/UI/scheduler 无 operation allowlist；没有新增持久化实体；`spec/catalog/invoke` 为 319/449/428 行，总计 1196，满足冻结的 1200 行预算 |

因此，本轮没有为了“通过约束”新增平行权威、领域特例或科学状态机。R3-D 尚未删除的 legacy
角色/profile 路径只服务 `operation_authority is None` 的旧任务，不能给新 Operation 补行为；其
存在是有明确退出阶段的迁移债务，不构成当前双权威。

## 7. 独立执行的检查

| 检查 | 结果 |
| --- | --- |
| `pytest -q` | 122 项通过，46.36 秒 |
| R3-A 重点合同/派发/网络/安装 profile 测试 | 26 项通过，24.08 秒 |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| `wc -l src/scidiscovery/operations/{spec,catalog,invoke}.py` | 319 / 449 / 428，总计 1196 |
| 用修正检测器重放 run 3 / run 4 / run 5 | `False / False / True` |

当前基线没有 `scripts/validate_architecture_constraints.py`，实施记录没有再伪称该脚本通过，而是
明确由完整行为回归和本次跨边界审查覆盖
（`docs/plans/R3_GENERIC_OPERATIONS_IMPLEMENTATION.zh-CN.md:139-149`）。

## 最终判定

**通过，可恢复 R3-B。**

放行范围仅为：继续以相同的 `spawn_agent + inherited_prototype + 编译提示约束 + 服务端硬门`
路径，在隔离数据、无真实副作用的条件下完成 R3-B 迁移与真实文本/PDF/图像验收。R3-B 仍须
独立审查；本结论不允许提前进入 R3-C、R4 或真实 TCAD/生产执行。
