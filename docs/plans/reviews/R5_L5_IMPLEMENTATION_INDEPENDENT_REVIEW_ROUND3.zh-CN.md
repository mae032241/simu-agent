# R5-L5 实现第三轮独立审查报告

日期：2026-09-01  
审查者：独立实现审查者（未参与本轮返修）  
结论：**PASS**  
放行范围：**只放行 L6；不放行正式发布，也不把 L6 必删项视为已经完成**

## 1. 审查范围与方法

本轮完整核对了：

- `docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md` 的总体目标、6.3、L5/L6 完成门、33 项约束和自动停止条件；
- 前两轮独立 FAIL 报告；
- 更新后的 `docs/plans/evidence/R5_L5_OPTIONAL_HARDENED_AND_POLICIES.zh-CN.md`；
- 当前 Run、Local/Hardened workspace、Hardened Worker MCP、Root Operation 路由、Codex 投影、TCAD/盲 CSV 声明及聚焦测试。

按要求没有重跑证据中已记录的 332 项非 live 全集。所有本轮测试均串行执行，并设置 7 GiB 虚拟内存上限。除本报告外，没有修改生产代码、测试或计划文件。

## 2. 总体结论

第二轮的两个阻断已经以通用且足够小的方式闭合：

1. Hardened transport 改为每个 `run_id` 一把操作系统文件锁，SQLite 只在 owner 查询、CAS 和续租期间持有短事务；不同 Run 的调用可以并行，同一 Run 的接管与在途调用保持互斥；
2. Hardened v1 明确收窄为纯 Worker MCP 后端。任何声明原生 shell、代码或 `view_image` 的 Agent Operation 均由同一个 `supports_operation` 能力结论在目录、preflight/invoke、Run 创建和 Codex profile 生成处失败关闭。

返修没有增加 TCAD、Deck、Sentaurus、盲 CSV 或具体 Operation 标识分支，没有建立第二目录、第二注册表、第二 preflight/invoke 或第二科学权威。盲 CSV 仍是可真实执行的 Hardened 消费者；TCAD 继续在 Local 后端成功运行，而 Hardened+TCAD 被诚实标记为当前不支持。

因此，本候选达到 L5 完成门，可以只进入 L6 删除和最终安装矩阵阶段。

## 3. N1：并发、接管和 SQLite 锁边界——通过

### 3.1 实现边界

`HardenedWorkerBackend` 当前只有三个 transport 动作：`claim_transport`、`transport_guard` 和 `release_transport`。此前无生产消费者的 `renew_transport`、`assert_transport` 已被删除，没有形成重复 owner 协议。

`_run_transport_lock` 将 `run_id` 做 SHA-256 后映射为 backend 私有锁文件，避免路径注入，并以 `flock(LOCK_EX)` 保持单 Run 的跨进程互斥。关键顺序是：

```text
取得本 Run 文件锁
→ 短 SQLite 事务核对或更新 owner/lease
→ COMMIT
→ 执行领域工具、文件工具、校验或提交
→ 释放本 Run 文件锁
```

因此 SQLite 写事务在进入领域调用前已经提交；在途调用只占有该 Run 的文件锁，不占有共享数据库写锁。

### 3.2 独立验证结果

聚焦测试和代码路径共同验证：

- `run_a` 的 guard 被故意阻塞时，`run_b` 可在 0.25 秒门限内进入自己的 guard，没有重现第二轮的约 1.3 秒全局阻塞；
- `run_a` 的在途调用持锁期间，可以直接更新 `dispatch.sqlite3` 中的过期时间，证明 guard 没有跨领域调用占有 SQLite 写事务；
- 租约被置为过期后，新 owner 的 claim 必须等待旧 owner 的在途调用释放同一 Run 文件锁；
- 接管完成后，旧 owner 再次进入 guard 被判定为 stale；
- 前轮已通过的真实双 Router 回归继续确认旧 owner 的注册领域工具、服务端文件写、候选提交均在统一入口失败关闭。

该实现没有用数据库行锁模拟长任务互斥，也没有为某个领域或工具增加例外。对当前 Linux/WSL 部署目标，文件锁加短 SQLite CAS 是满足短租约恢复所需的最小协议。

## 4. N2：原生工具能力统一失败关闭——通过

### 4.1 唯一能力规则

Hardened v1 的唯一规则位于 `HardenedWorkerBackend.supports_operation`：

```text
native shell == none
且 view_image == false
```

同一规则被以下边界消费：

- Root `operation_catalog`：Operation 仍在统一目录中可见，但 `runtime_binding.status=unavailable`；
- Root `operation_preflight` 和 `operation_invoke`：返回或抛出 `runtime_backend_capability_missing`，且不创建 Run；
- `RunService.schedule`：即使绕过 Root 直接请求创建 Run，也在写入状态前拒绝；
- Codex 初始化和安装校验：不生成、不保留该 Operation 的 Agent profile 和 Worker server 投影；
- `_operation_toml`：单独请求生成不兼容 profile 也直接拒绝。

这不是一套新注册表。Local 和 Hardened 仍消费同一个 `CompiledCatalog`；能力判断属于已选 workspace backend 的运行可实现性，不解释科研内容。

### 4.2 独立通用负例

除 TCAD 的 shell 负例外，本轮额外把真实盲 CSV Agent Operation 的声明复制为 `view_image=true`，重新经过正常插件编译，并独立验证：

- 目录运行绑定为 unavailable；
- preflight 和 invoke 均以相同原因失败关闭；
- 没有创建 Run；
- 直接调用 `RunService.schedule` 仍被拒绝；
- Hardened Codex 初始化和 `validate_installation_profile` 通过，但不生成该 Agent profile。

该负例不包含 TCAD 名称或插件特判，证明规则同时覆盖 shell 与 `view_image` 两类原生旁路。

### 4.3 正向消费者与 TCAD 边界

- 盲 CSV 作者声明 `native_shell="none"`、`view_image=false`，真实走过 Root → RunService → Hardened Worker stdio MCP → 注册 CSV 工具 → 服务端文件 → `RunService.submit`，并完成 Artifact 登记；
- Hardened Codex profile 对兼容 Operation 明确关闭 shell、unified exec、网络和 `view_image`，只投影声明的 Worker MCP 工具；
- TCAD 作者声明原生 shell，因此 Hardened 目录标记 unavailable，调用在 Run 创建前被拒绝；
- TCAD Local 作者—调试—独立审查回归继续通过。该回归使用明确命名的 `_ImmediateDebugAdapter` 夹具，验证的是 Local 主干、插件物化/终结和领域工具接线，不将夹具输出冒充为真实 Sentaurus 求解结果。

当前边界是诚实的：TCAD 可由可信 Local 原型运行；Hardened+TCAD 要等真正任务根沙箱或纯 MCP TCAD 工具后才能支持。

## 5. 唯一权威、可选策略与领域隔离

以下前两轮已通过的边界未发生回归：

- Local 与 Hardened 使用同一 `RunService`；Hardened backend 不登记 Artifact、不写 Run 终态、不推进 current、不创建 reviewer；
- `open_runtime(worker_backend="hardened")` 不实例化 Task/token，生产 Hardened Root 不持有或读取旧 Task 科学事实；
- `OperationToolContext` 不暴露 Task/session/token、Artifact 注册、Run 终态、current CAS 或 reviewer 创建能力；
- 普通 `runs` 表没有 qualification、cohort、approval、execution、session、token、attempt、lease 或 finalizing 字段；
- qualification cohort、人工决定和 Effect 只由显式声明相应合同的 Operation 选择性启用；
- Hardened 服务端文件仍由同一 Operation workspace policy、通用安全目录句柄和 `O_NOFOLLOW` 原语限制，路径逃逸、父目录符号链接、大小上限和陈旧 patch 负例继续通过；
- 核心 Hardened、Run、Root 和 Codex 模块扫描没有 TCAD、Deck 或 Sentaurus 分支。

旧 Task 路由和服务文件仍存在于生产包中，但当前只由生产配置拒绝的 `legacy_task` 测试入口引用。这是计划明确留给 L6 的删除对象；本轮确认它们没有重新成为 Hardened Root 或 Codex 的科学权威。

## 6. 奥卡姆剃刀与复杂度判断

三个 Hardened 模块当前为 150、336、280 行，共 766 行。相对初版确有临时增加，但职责边界清楚：

- 150 行 backend 只负责工作区继承、每 Run transport owner 和能力判定；
- 336 行文件模块是一个共享的服务端编辑器，覆盖已声明且有消费者的创建、补丁、移动、删除与路径/大小边界；
- 280 行 MCP 模块复用 `LocalWorkerMCPRouter`、同一 RunService 和同一编译工具目录，只增加 transport guard 与服务端文件分派。

未发现把科学校验、Artifact 提交、current 或 reviewer 复制到这三个模块。每 Run 文件锁不是新增业务状态，`active_transport` 也只是 backend-private 的恢复事实。当前增量对“显式可选加固后端”可接受，但接受的前提是 L6 删除旧 Task 文件代理、daemon、proxy 和重复文本补丁实现，不能长期双轨保留。

从 33 项约束和自动停止条件看，本轮返修符合单一目录、唯一 Run 科学权威、最小授权、能力声明真实、领域逻辑留在插件、多 Agent 可并行以及失败关闭原则，未发现针对测试的补丁或复杂度反噬型新状态机。

## 7. 独立测试与证据核对

测试环境：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

本轮结果：

- L5 全文件、TCAD Hardened 拒绝、TCAD Local 纵向主干及平台聚焦回归：`20 passed in 4.02s`；
- 额外真实编译的通用 `view_image=true` Operation 四边界探针：`generic-view-image-boundaries: PASS`；
- `git diff --check`：通过；
- 更新证据列出的 10 个 SHA-256 均与当前工作树一致；
- 生产 Python 规模复核：159 个文件、62,025 行；L6 仍须通过删旧路径收回临时双轨规模。

已有 332 项 Operation 非 live 全集和 40 项 Artifact Agent 全集只作为已记录证据使用，本轮未重复运行，也未据此替代语义审查。

## 8. 放行决定与 L6 必做事项

本轮结论为 **PASS**，只放行 L6。

L6 仍必须完成，且不得把下列事项写成 L5 已完成：

- 删除旧 Task/token/session/assignment/lease/finalizing、Worker daemon/proxy、Task routes 和 `legacy_task` selector；
- 删除旧服务端文件/文本补丁重复实现及默认 wheel/deploy 中旧模块、unit 和导入；
- 确认默认 Local、显式纯 MCP Hardened、无 Hardened 插件、TCAD Local 成功、Hardened+TCAD 预检拒绝、review、approval、Effect、回滚和干净安装矩阵；
- 证明最终生产路径只剩一个 Run 科学权威，Hardened 仍仅在部署显式选择时加载；
- 完成计划要求的双重独立总审查后，才可判断 L 系列完成或正式发布。
