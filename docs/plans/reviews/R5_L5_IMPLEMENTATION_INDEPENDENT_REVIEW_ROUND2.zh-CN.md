# R5-L5 实现第二轮独立审查报告

日期：2026-09-01  
审查者：独立实现审查者（未参与返修实现）  
结论：**FAIL**  
放行范围：**不放行 L6，不放行正式发布**

## 1. 审查范围与方法

本轮完整核对：

- `docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md` 的总体目标、Hardened 合同、L5/L6 完成门、33 项约束和自动停止条件；
- 首轮 FAIL 报告 `R5_L5_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
- 更新后的 `evidence/R5_L5_OPTIONAL_HARDENED_AND_POLICIES.zh-CN.md`；
- 当前 Hardened workspace、文件编辑器、Worker MCP、runtime、Codex 投影、TCAD Operation 与相关测试。

按要求未重跑已记录的 329 项非 live 全集，只在 7 GiB 虚拟内存限制内串行运行聚焦回归，并另外编写一次性只读复现脚本验证首轮三个阻断以及返修引入的跨运行行为。除本报告外未修改生产代码或测试。

## 2. 结论摘要

首轮 B1、B2、B3 的原始缺陷均已实质修复：

- 接管后旧 owner 在 Worker MCP 入口即被拒绝，不能进入领域工具、文件工具、候选校验处理器或提交；
- `open_runtime(worker_backend="hardened")` 不再创建 Task/token，生产 Hardened Root 因而不持有或回退读取旧 Task 的 signal/reviewer 事实；
- Hardened 通用文件编辑器已提供真实的精确上下文文本 patch，TCAD 声明不再是固定失败的虚假工具。

返修仍不能通过 L5，原因是出现两个新的、可复现的架构阻断：

1. fencing 使用一个 SQLite `BEGIN IMMEDIATE` 写事务包住整次 Worker 调用，导致所有互不相关的 Hardened Run 全局串行；长工具调用会使其他 Run 的工具和 heartbeat 最多等待 30 秒后报数据库锁错误；
2. Hardened TCAD Codex profile 仍启用原生 shell/unified exec，生成提示还明确承认运行时无法技术性隐藏其写能力。因此 Agent 可绕过刚补齐的服务端 patch/路径/所有权协议直接写工作区；对 shell-enabled Operation，当前“加固服务端文件边界”仍是表面隔离。

第一项直接违背 Hardened 用于并发、远程和长任务的目的；第二项与计划中“只有任务根文件系统沙箱或 Hardened 才能关闭 SEC-002”的表述冲突。两项均不能留给只负责旧路径删除和安装矩阵的 L6。

## 3. 首轮阻断复核

### B1：接管后旧 owner 全能力失效——通过

`HardenedWorkerMCPRouter.call_tool` 在 Run 打开后，将每次 Worker 调用置于同一个 `transport_guard` 中。guard 在分派前核对 owner 和租约，接管写入与旧调用不能交错。

独立复现确认：

- 第二 owner 在租约过期后成功接管；
- 旧 owner 调用注册领域工具：`WorkerToolError: exact Run transport ownership is stale`；
- 旧 owner 调用服务端文件 begin：同样失败；
- 旧 owner 提交：同样失败；
- 将领域处理器替换为会执行 `OperationToolContext.validate_outputs()` 的通用探针后，旧 owner 在处理器调用前即失败，`handler_called=False`。

这证明拒绝来自统一 transport 边界，不是针对 CSV、文件工具或 submit 的分别补丁。

### B2：Hardened Root 脱离旧 Task 科学权威——通过

当前 `open_runtime` 行为为：

- `local`：只创建 Run + Local backend；
- `hardened`：只创建 Run + Hardened backend；
- `legacy_task`：才创建 Task/token，不创建 Run。

生产 `build_root_router(worker_backend="hardened")` 将 `tasks=None` 传入 Root facade；其 signal、reviewer、inventory 和 Operation 准入均不可能再回退到旧 Task。Hardened Codex profile 仍指向 `mcp_hardened_worker`，未回到旧 proxy。

旧 `mcp_worker_daemon` 和一批历史测试仍显式使用 `legacy_task`。默认安装当前已禁用旧 Worker service，但模块、unit 模板、Task 路由和兼容 selector 仍存在。这些属于计划明列的 L6 必删项，本轮不把“尚未删除”误判为 B2 未修复；L6 不得将它们继续保留为正式兼容层。

### B3：TCAD 声明文本 patch 真实可用——通过

`HardenedFileEditor.text_patch` 是领域无关实现，先经同一个 workspace policy 准入，再用安全目录句柄读取和原子替换。独立验证结果：

- Codex `*** Begin Patch` 格式正确修改目标；
- 标准 unified diff 正确修改目标；
- 陈旧上下文失败关闭；
- 重复上下文失败关闭；
- Codex envelope 目标与声明路径不一致时失败关闭；
- TCAD 真实工作区完成 `deck/files/main.cmd` 创建、patch、字节核对，第二次陈旧 patch 被拒绝；
- 既有 8 MiB、output/preflight/debug 父目录符号链接负例继续通过。

核心 patch 实现没有 TCAD、Deck、Sentaurus 或 schema 名称分支，也没有增加第二注册表、第二 preflight 或第二 invoke。

## 4. 新阻断项

### N1：一个 Run 的 ownership guard 全局串行所有 Hardened Run

严重性：阻断。

`transport_guard` 在共享的 `dispatch.sqlite3` 上执行 `BEGIN IMMEDIATE`，并将该写事务保持到整个 Worker 工具调用结束。SQLite 写锁是数据库级而不是 `run_id` 行级；因此即使 `run_a` 和 `run_b` 的 owner、Operation、工作区完全独立，二者也不能并行调用。

独立最小复现：

1. 在同一 Hardened backend 中分别 claim `run_a/owner_a` 和 `run_b/owner_b`；
2. `run_a` 进入 guard 后仅睡眠 1.2 秒；
3. 同时测量 `run_b` 进入自身 guard 的等待时间。

实际结果：

```text
unrelated_run_guard_wait_seconds=1.311
```

这不是测试噪声，而是数据库写锁的必然行为。生产连接超时固定为 30 秒，所以任何超过 30 秒的注册工具、候选校验或 submit 都可令其他完全无关的 Run heartbeat/工具调用报 `database is locked`。Hardened 原本用于并发、远程和长任务；当前修复虽然保证了同一 Run 的 fencing，却以全系统串行为代价，破坏多 Agent 并行和短租约存活语义。

返修完成条件：同一 Run 的 claim/takeover 与旧调用仍必须互斥，但不同 Run 的 guard 可真实并行。应采用通用的每 Run 锁或等价 fencing 原语；SQLite 事务只做短时 owner CAS，不能包住领域工具、外部调用或完整提交。新增“双独立 Run 不互相阻塞”并发测试，以及同一 Run 接管不能与在途旧调用交错的测试。不得为某个 Operation 增加例外。

### N2：shell-enabled Hardened Operation 仍可绕过服务端文件协议

严重性：阻断。

TCAD 作者 Operation 声明 `NativeToolPolicy(shell="inherited_prototype")`。Hardened Codex 生成器据此设置：

```text
shell_tool= True
unified_exec= True
instruction_admits_no_technical_hide= True
```

生成提示原文承认 native tools 的写能力无法被运行时技术性隐藏。Worker 同时获得绝对 `workspace_path`，所以原生 shell 可以直接改写 Deck、创建符号链接或访问同权限范围内的其他路径，绕过：

- `HardenedFileEditor._admit`；
- 文本 patch 精确上下文与陈旧检测；
- 服务端路径、大小、摘要和 owner guard。

最终 seal 可以发现部分非法输出，但不能恢复“所有写入都经过服务端协议”或阻止跨工作区读取/写入；提示禁令不是技术隔离。盲 CSV 的真实 stdio 消费者因 `shell="none"` 不受该问题影响，但 TCAD Hardened profile 和 L6 计划中的 Hardened+TCAD 组合受影响。

返修完成条件可选择最小诚实边界之一：

- 对 Hardened 技术性关闭原生可写工具，并为必要读取提供真正只读的任务根能力；或
- 在编译/安装时拒绝将 shell-enabled Operation 投影到当前 Hardened backend，明确它尚不能承诺不可信 TCAD Worker；或
- 提供真实任务根文件系统沙箱，使原生工具只有任务内所需读取权且不能绕过服务端写协议。

不能继续同时宣称 Hardened 关闭 SEC-002、支持不可信 Worker，并依赖提示词要求可写 shell “只读”。该问题应在能力投影/运行后端边界统一解决，不能添加 TCAD 特判。

## 5. 其他边界判断

以下项目继续成立：

- Local 与 Hardened 消费同一个 `CompiledCatalog`、`operation_invoke` 和 `RunService`；
- Hardened backend 仍不登记 Artifact、不解释科学终态、不推进 current、不创建 reviewer；
- `OperationToolContext` 没有 Task/session/token/current/Artifact 写权；
- 普通 Run schema 未增加 qualification/cohort/approval/effect/session/token/lease 字段；
- qualification cohort、人工决定和 Effect 只由声明相应 Operation 的现有窄服务消费；
- 新代码没有领域特判、隐藏测试标签、第二目录、第二准入或第二科学权威。

返修后三个 Hardened 模块由 616 行增至 781 行，其中约 88 行是通用文本 patch，约 63 行是 ownership 辅助。文本 patch 在 L6 删除旧 Task patch 实现后将成为唯一实现，增量本身可接受；但 `renew_transport`、`assert_transport` 与 `transport_guard` 当前形成三套相近 owner 检查，前两者没有生产消费者。N1 返修时应收敛为一个生产 ownership 原语，避免继续叠加锁与校验层。

## 6. 独立测试结果

所有聚焦命令串行运行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

- L5 全文件、TCAD Hardened patch、8 MiB 与三条符号链接关键负例：`11 passed in 3.95s`；
- 独立 B1 stale-owner 领域/文件/submit 复现：全部失败关闭；
- 独立 B1 候选校验处理器探针：处理器未被调用；
- 独立 Codex/unified patch 与 stale/ambiguous/wrong-target 负例：符合预期；
- 独立不同 Run 并发复现：`run_b` 被无关 `run_a` 阻塞 1.311 秒，N1 成立；
- Hardened TCAD Codex profile 静态/生成检查：原生 shell 和 unified exec 均为 true，且提示承认无法技术隐藏写权，N2 成立；
- `git diff --check`：通过；
- 更新证据列出的八个 SHA-256 与当前工作树一致。

## 7. 奥卡姆剃刀与 33 项约束

返修没有恢复旧中央控制器，也没有新增领域状态机。B1—B3 的修改方向符合“一个 Run 权威、一个目录、一个通用文件编辑器”。

但 N1 用数据库级长事务替代每 Run fencing，把一个局部安全问题扩大为全系统串行协议；N2 则在服务端实现完整写协议的同时保留可直接绕过它的原生写入口。前者是复杂度反噬，后者是表面隔离，分别违背多 Agent 可并行、最小授权、能力声明真实和 SEC-002 不得以提示冒充技术隔离的约束。

因此当前候选尚不能判定 33 项约束在 Hardened 路径上得到诚实、最小的实现。

## 8. 放行决定与 L6 边界

本轮结论为 **FAIL**，不放行 L6。

只有 N1、N2 均以领域无关方式闭合并补入直接负例，经下一轮独立复审通过后，才可只放行 L6。届时 L6 仍必须完成以下事项，不能把它们回填为 L5 已完成：

- 删除旧 Task/token/session/assignment/lease/finalizing、Worker daemon/proxy、Task routes 和 `legacy_task` selector；
- 清除默认 wheel/deploy 中旧模块、unit 与导入；
- 验证默认 Local、显式 Hardened、无 Hardened 插件、TCAD、review、approval、Effect、回滚和干净安装矩阵；
- 证明最终只剩一个 Run 科学权威并完成双重独立总审查。
