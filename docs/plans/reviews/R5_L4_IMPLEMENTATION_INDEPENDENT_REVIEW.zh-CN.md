# R5-L4 独立实现审查

日期：2026-09-01  
审查结论：**FAIL（打回）**  
放行范围：**不放行 L5；L4 返修后必须重新独立复审**

## 1. 审查口径

本轮审查以当前未提交工作树相对 `HEAD` 为对象。工作树包含 R5 多阶段累计修改，因此本报告不把
全部脏文件都归因于 L4；只沿 L4 新增或改变的真实路径复核：

```text
Compiled Operation
→ Root operation_invoke
→ RunService
→ LocalTrustedBackend
→ Operation 专属 stdio Worker MCP
→ TCAD workspace materializer/finalizer
→ worker_tcad_debug_run
→ 正式 Artifact
→ 独立 reviewer Run
```

同时检查了运行时插件配置、Codex profile、旧 Hardened TCAD debug 路径、持久 probe、生产代码规模和
33 项约束所覆盖的行为边界。本轮只做审查，没有修改生产代码。

## 2. 阻断项

### B1：控制拥有的写入会跟随 Agent 预置的父目录符号链接，能够写出 Run 工作区

这是可达的真实路径逃逸，不是代码风格问题。

第一条路径位于 TCAD 本地调试收尾：

- `local_debug_service.py:142-162` 把预检结果写到
  `workspace/deck/reports/preflight.json`；
- `_write_control` 在 `local_debug_service.py:226-233` 只检查最终文件本身，先对父目录执行
  `mkdir(..., exist_ok=True)`，没有证明 `deck/reports` 是工作区内的真实目录；
- 因此，Agent 在调用工具前把 `deck/reports` 建成指向工作区外目录的符号链接，候选机械校验仍可
  通过，随后控制代码会在外部目录创建 `preflight.json`。

在 7 GiB 限制下，审查者通过真实 L4 `Root → Run → LocalWorkerMCPRouter →
worker_tcad_debug_run` 路径复现，结果为：

```text
{'tool_state': 'succeeded', 'outside_preflight_exists': True}
```

第二条是同一缺陷在通用 Local 后端中的表现：

- `LocalTrustedBackend.open` 在 `local_workspace.py:150-172` 只调用 `output.is_dir()`，该调用会跟随
  `output` 符号链接；
- `write_primary_output` 在 `local_workspace.py:182-188` 把 finalizer 结果交给
  `_write_control_file`；
- `_write_control_file` 在 `local_workspace.py:398-416` 同样只检查最终文件，没有验证父目录；
- `seal` 在 `local_workspace.py:193-234` 也未先拒绝作为根本身的 `output` 符号链接。

审查者把空的 `workspace/output` 替换为指向工作区外目录的符号链接，再调用同一个 TCAD 调试工具。
`candidate_snapshot` 触发通用 finalizer 后，结果为：

```text
{'tool_state': 'succeeded', 'outside_result_exists': True}
```

现有负例 `test_l4_local_tcad.py:455-493` 只覆盖 `.operation-tools/tcad` 私有调试目录，不能覆盖上述
两条控制写路径。因此，证据文件第 34—36 行的“符号链接不能把调试输出写到工作区外”只证明了一个
子路径，不足以证明 L4 的工作区边界闭合。

`SEC-002 known_issue` 不能豁免此缺陷。`SEC-002` 如实承认当前 Codex 原生文件能力只受提示约束；
这里失败的是服务端/控制拥有的确定性写入也跟随了 Agent 构造的符号链接。领域工具和 finalizer 不应
在已有提示隔离不足之外再提供一条工作区外写入能力。

#### 返修完成门

返修应保持小而通用，不新增状态、注册表或 TCAD 核心特判：

1. 通用 Local 后端在 `open`、控制文件写入和 `seal` 前证明工作区根、输出根及目标父目录均为真实、
   非符号链接目录；
2. TCAD 预检报告写入使用同一类“不跟随父目录符号链接”的窄原语，或者在插件边界做等价的逐级
   `lstat`/目录句柄验证；
3. 增加两个真实负例：`deck/reports -> outside` 和 `output -> outside`，均必须失败关闭，并证明外部
   目录未产生文件、Run 未完成；
4. 保留现有 `.operation-tools/tcad` 符号链接与 8 MiB 负例；不得靠提示词或测试专用标签修复。

## 3. 已通过的审查项

### 3.1 同一 Operation/Run 主干与真实 Agent 证据

持久证据目录
`deliverables/l4-local-tcad-agent-probe-20260901-round2/` 中存在两个 completed
`local_trusted` Run：作者输出为 `tcad.deck-project.v1`，审查者输出为
`tcad.deck-review-report.v1`。数据库中的 reviewer 父链精确包含作者 Artifact，作者 Run activity
记录了 `tool_succeeded:worker_tcad_debug_run`。

协作运行器的独立状态也证明两个不同子智能体已完成：

- `/root/l4_tcad_author_agent_probe_round2`：`已完成受控提交。`；
- `/root/l4_tcad_reviewer_agent_probe_round2`：`已完成受控提交。`。

二者的 dispatch 均绑定精确 Operation digest 和专属 stdio MCP；持久结果中 `TaskService` 不存在。
因此，作者—调试—审查确实走了同一 Operation/Run/Local Worker 主干，而不是旧 Task 包装或父进程
代写科学结果。

probe 使用确定性命令传输夹具，不是真实 Sentaurus 许可证运行。证据文件第 77—80 行对此明确披露，
实验目标与 reviewer 内容也把结论限制为有界工程预检，没有宣称物理结论、初始化、收敛或可发表
结果。因此本轮没有把夹具结果当成真实求解实证。需要注意：单独抽出该 probe 的科学 Artifact 时，
公开 capability 与 preflight 本身不会完整显示夹具实现；以后引用这份证据必须连同本证据文档的
适用范围，不能把它用作真实 solver qualification。

### 3.2 通用核心没有 TCAD 特判

对下列通用生产文件扫描 `tcad|deck|sentaurus` 为零命中：

- `service/runs.py`；
- `service/local_workspace.py`；
- `interfaces/mcp_local_worker.py`；
- `operation_tool_context.py`；
- `operations/workspace.py`；
- `operations/tooling.py`；
- `platforms/codex.py`。

通用 `RunService` 只解析编译 workspace hook；TCAD 文件结构、8 MiB 限制、调试 adapter 和 Operation
名称判断均留在 `tcad_artifact` 插件。未发现第二 Operation 注册表、第二 preflight 或 TCAD 专用
调度入口。

### 3.3 OperationToolContext 保持最小权限

`operation_tool_context.py:13-61` 只暴露声明输入的读取/路径/媒体类型/不可变 ref、当前工作区、输出
校验、候选快照、有界 activity 与明确服务。它没有 Task、session、token、proxy、current 写接口、
Artifact 登记或 Run 完成接口。`input_ref` 只是已声明输入的不可变科学身份，不是 Artifact 写权。

### 3.4 运行时配置边界和 Hardened 防腐

Codex 配置只把实际要求服务的插件配置投影给对应 Operation；TCAD reviewer 不携带 debug 配置。
目录外插件标识会拒绝，配置文件以 `O_NOFOLLOW` 和普通文件/一 MiB界限读取。相关平台、运行时插件
与部署预览测试通过。

旧 Hardened profile 仍可显式编译，旧 `TCADDebugService + Task attempt` 实现仍由 `worker` 模式
使用；Local 使用 `local_worker` 分支和 `LocalTCADDebugService`。当前平台明确拒绝把尚未消费 Run 的
Hardened 路径部署为默认，没有用旧 TaskService 包装新 Run。

### 3.5 复杂度与奥卡姆原则

生产 Python 当前为 156 文件、60,974 行；`operations` 包为 2,288 行；本地 TCAD debug 编排器为
236 行。该编排器保存的独立事实仅为本进程内 run-name、适配器 binding、累计预算和最终有界响应，
复用现有 `TCADDevelopmentDebugBridge` 做传输准备与收集，没有复制旧 TCAD debug 的持久 lease、
session、Task、快照登记和恢复状态机。其规模作为 L4 过渡实现可以接受，旧中央路径的最终净删除仍
必须由 L6 兑现。

符号链接缺陷属于边界实现遗漏，不证明整个 L4 分层方向错误；修复应收敛到一个通用安全写原语，
不能再给 TCAD、finalizer 和其他插件各打一套补丁。

## 4. 独立测试证据

所有命令均串行并设置：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
L4 + Codex 平台 + runtime plugin + 旧 TCAD debug + 33项矩阵
24 passed in 4.12s

部署 dry-run + Hardened 精确绑定/恢复负例
7 passed in 3.34s

git diff --check
通过

生产 Python
156 files / 60,974 lines

operations
8 files / 2,288 lines
```

没有重跑完整 `tests/operations`；候选证据已记录当前摘要下 `320 passed in 120.76s`，本轮独立审查
使用最小跨边界集合，并额外执行了上述两条现有测试没有覆盖的真实符号链接负例。

## 5. 33 项约束与最终结论

除 B1 外，未观察到不可变 Artifact、精确输入、Operation 单一授权、最小上下文、作者/审查者独立、
聊天不构成人工决定、插件不向核心泄漏领域规则、普通 Run 不支付 qualification/approval、以及旧
Hardened 防腐边界退化。仓库的 33 项矩阵测试只证明编号和当前登记完整，本报告不伪称自动测试等于
33/33 语义证明。

B1 直接违反任务工作区路径边界和领域工具最小授权，且存在可重复的真实写出结果，所以当前候选不
能以“known issue”放行。结论为 **FAIL**。L5、L6 和正式发布均不放行；完成通用父目录非符号链接
修复、补齐两个负例并由独立审查者复核通过后，才可把 L4 标记为完成并只放行 L5。
