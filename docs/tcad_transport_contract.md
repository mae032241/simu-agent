# TCAD 传输与开发调试合同（Run v1）

更新日期：2026-09-13
状态：当前规范

## 1. 权限边界

交互 Agent 不获得机器凭据、求解器控制 socket、可执行文件路径、许可证环境或外部 run id。
`tcad_artifact` 插件在启动时从私有配置构造 adapter，并分别投影为：

- control 进程中的 TCAD Effect adapter；
- Local Agent Run 中由精确 Operation 声明的 `worker_tcad_debug_run` 工具服务。

两者都不能登记 Artifact、批准请求、更新 current、写 Run 终态或解释科学结论。正式 Artifact、Run、
Approval 和 Execution 事实只由通用控制面维护。

插件配置只能选择 `socket` 或 `command` 传输。control daemon 与 Operation Worker 使用同一精确
`--plugin-config tcad_artifact=/path/to/tcad-plugin.json`。配置不完整、路径不绝对、安装目录与编译
插件不一致时启动失败关闭。

## 2. 外部执行 transport

`CommandTCADExecutorAdapter` 每次调用一个管理员拥有的短命令。请求和响应均为有界规范 JSON：

```json
{"schema_version":1,"operation":"capabilities|prepare|lookup_submission|submit|status|cancel|collect","payload":{}}
```

transport 只能：

- `capabilities`：读取管理员冻结的 solver capability；
- `prepare`：物化已审查 package 和 JobSpec；
- `lookup_submission`：按已准备提交的稳定摘要权威查回既有外部任务；
- `submit`：短时提交并返回外部状态；
- `status`：执行一次短查询；
- `cancel`：请求取消并短时返回；
- `collect`：仅在终态后收集有界原始结果。

transport 不等待 Solver、不循环轮询、不生成或修改 Deck、不批准请求、不写 SciDiscovery 控制状态。

状态/日志与产物分开调用：Root 的 `execution_sync` 只同步短观测，终态仍可刷新；显式
`execution_collect` 由 daemon 共享收集器启动一个有界工作进程组；私有控制监督进程持锁至该组
实际停止，daemon退出后仍保留所有权，不依赖原生SSH继承锁。`execution_status` 读取其进度，
`execution_outputs` 只在 collected 后发布输出名。适配器不拥有调度队列或独立重试预算。

正式收集默认总预算600秒，内部预留 `min(2秒, 总预算10%)` 用于停止和回收，单文件120秒、
无字节进展30秒；状态查询默认5秒，Root 代理默认10秒。`collect(external_run_id)` 保留兼容；
可选 `collect_with_budget(external_run_id, *, context)` 消费共同 `CollectionContext` 的单调时钟
截止点、文件/无进展预算及进度回调。command/socket 传递同一剩余预算，不能逐项重置。
旧调用由控制进程封装。作者调试由已有 runtime factory 重建适配器，在独立受控进程中消费
本 Run 剩余时间；手工注入的适配器需实现预算方法，不能直接把无界旧方法放进 Worker 线程。
分析恢复的 `inspect_outputs(..., *, deadline_monotonic=None)` 消费原 IO/Run 较短剩余时间，
不继承正式收集预算。原 VM 协议、已批准求解任务和原始工作目录保持兼容。

`submit` 必须对同一已准备描述符幂等。每次提交前由 adapter 调用
`lookup_submission`：查到既有任务则只返回它，权威确认不存在才可提交，查询不可用则在副作用前
失败。未知提交不能盲目重发。

公开的 `tcad.solver-capability.v2` 只是 allowlist 投影：包含 solver kind、安全发行标签、允许公开的固定
参数子集和私有完整配置摘要；不公开完整路径、环境、SSH、许可证或私有参数。Deck 作者、独立
reviewer、reviewed package、JobSpec 和实际 runner 必须绑定同一 capability 摘要；任何可执行文件、
参数、环境、solver kind 或发行证据漂移均在启动前拒绝。

正式执行只接受 `tcad.reviewed-deck-package.v2` 和 `execution_purpose=production`，先经过独立人工
Effect 授权。提交成功、领域终态和结果收集是三个事实，不能压成一个 succeeded。

## 3. Local Run 开发调试

TCAD 作者 Operation 可以显式注册 `worker_tcad_debug_run(run_name, mode)`。该工具只通过
`OperationToolContext` 获得：本 Run 的候选工作区、精确输入、`execution_capability`、剩余预算、
候选校验/快照接口和私有有界状态。它看不到 Run id、控制数据库、Approval、Artifact 登记或 current。

`mode` 只允许 `preflight|smoke|initialization`。插件根据冻结 release、solver kind 和 entrypoint
确定实际参数；Agent 不能提供 shell、命令、环境、凭据、网络目标或工作区外路径。当前上限为：

- 一个 Run 最多 6 个命名调试动作；
- 累计保留求解器时间不超过 360 秒；
- preflight 60 秒、smoke 180 秒、initialization 120 秒；
- 内存、进程数、文件数、单文件和总输出均由插件固定限制。

同一 `run_name` 永久绑定首次 mode。第一次调用校验并冻结当前完整候选，随后调用只轮询或收集同一
外部运行。外部 id 只保存在 `LocalTCADDebugService` 的 Run 私有工具状态中，不返回 Agent。

收集结果只写入本 Run 的 `.operation-tools/tcad/<run_name>` 私有目录，并返回有界、净化的开发诊断；
结果固定标记 `development_only=true`、`scientific_claim_admissible=false`。成功 preflight 可以由插件
写入 `deck/reports/preflight.json`，但它仍只是作者候选的一部分，不能成为生产 Execution、科学资格、
current 或下游正式证据。最终 Deck 必须通过普通输出校验和独立 reviewer；完整 case portfolio 只能
走单独批准的生产 Effect。

Run 失败时，当前本地原型不承诺跨进程接回调试会话或后台 reconciler。后端可以冻结有界恢复草稿，
但草稿不是 Artifact、证据或 current；显式新 Run 必须重新执行完整校验。旧 Task/attempt/session/
token/provisional-CAS/orphan-cleanup 合同已经删除，不得作为当前调试接口使用。

## 4. 本地与远端实现

本地 adapter 通过受限 socket 调用独立 TCAD controller。远端 VMware 场景中，每次 transport 调用
复用管理员配置的 Windows OpenSSH 和无第三方依赖的 Python 3.6 runner；不要求 VM 安装
SciDiscovery 服务、增加 SSH key、sudo 或端口代理。

确定性测试 executable 只证明控制与传输边界，不证明 Sentaurus 可用、许可证有效、Deck 科学正确
或仿真结果准确。真实调试和生产执行仍需要管理员私有 tool profile、许可证和可达 transport。

## 5. 验收

1. 核心代码不按 TCAD 名称分支，所有能力由插件单一入口注册；
2. Agent 只能通过声明的 OperationToolContext 调用开发调试；
3. 候选路径、父目录符号链接、超限文件和 capability 漂移失败关闭；
4. 开发调试不创建 Approval、Execution、Artifact、资格或 current；
5. 正式执行必须使用已审查 package、精确人工授权和同一 capability；
6. 测试适配器必须标为夹具，不得冒充真实 Solver 或科学效果。
