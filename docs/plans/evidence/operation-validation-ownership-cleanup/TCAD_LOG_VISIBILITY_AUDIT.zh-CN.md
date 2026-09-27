# TCAD server 日志对 Agent 的可见性核查

> 后继记录：本报告保留修复前事实；其后源码修复与验证见 [R3 修复完成记录](REVIEW_R3_FIX_COMPLETION.zh-CN.md)，[最终独立复审通过](INDEPENDENT_REVIEW_R3_FIX.zh-CN.md)。未完成生产 VM 复测。

2026-09-13。按用户要求沿当前源码、已编译端口和隔离 MCP 调用核查。**结论：终态日志已有受控读取路径，但运行中的日志和实际耗时没有传到作者；正式执行日志进入运行失败修订角色还存在媒体类型不兼容。因此，不能认为 Agent 已具备充分的服务端进度信息来判断耗时预期。**

这份核查由主代理完成，与新的独立校验修订审查分开。未修改生产源码、连接生产 VM、执行 Sentaurus 或读取生产研究内容。

## 谁可以看到什么

正式 `tcad.study.execute` 是 effect，由执行适配器运行，不是另一个能自主读日志的科学 Agent。需要区分作者的开发调试、正式执行的调度方，以及事后的分析/修订角色。

| 使用者和时机 | 当前能力 | 实际限制 |
| --- | --- | --- |
| 作者，开发调试仍运行 | 同一 `worker_tcad_debug_run` 名称轮询状态和预算 | 无 log_excerpt、日志路径、solver started_at 或 elapsed_seconds |
| 作者，开发调试结束 | 返回日志摘要及 `deck/reports/log-<name>.txt`；作者可读该目录 | 是有采集上限且脱敏的完整诊断，不是无限量 server 原始日志；debug 返回未保留 manifest 的起止时间 |
| 调度方，正式执行仍运行 | execution_sync 更新执行状态 | 通用适配器 status 只返回状态字符串，没有传播日志片段或 server 进度 |
| 结果分析，正式执行已收集 | 将 tcad_log 精确绑定到 diagnostics，读取 runtime_manifest 中的时间 | 需显式绑定；不是自动读取全部 server 日志，不能用此能力实时监控未结束的执行 |
| 运行失败后的作者修订 | 声明了 solver_log 必需输入 | 当前端口只接收 text/plain，与 runner 实际导出的带 charset 类型不兼容 |
| 后续设计/作者 | current_progress 可绑定相关已封存历史记录 | 作者该端口最多4项、每项2 MiB；不自动附带所有历史日志，也不开放 server 文件系统 |

作者 prompt 已明确要求完整日志不在摘要中时读取 log_relative_path，不要为了补看文本重跑求解器。工作区 read_paths 包含 deck，故该读取路径是被允许的。

## 运行进度在哪一层丢失

- 本机控制服务 `execution_control.py:555` 和 VM runner `remote_runner_py36.py:369` 的 status 返回 state、accepted_at、exit_code、done，没有实时日志或 solver 开始时间。
- `execution_adapter.py:145` 和 `command_adapter.py:190` 又把该响应缩成单个 state 字符串；debug bridge 直接沿用这个接口。
- `local_debug_service.py:109` 在非终态直接返回 pending，`_pending`（305行）没有日志字段；debug_response 中的 reserved_wall_seconds 是预留上限，run_remaining_seconds 是 Agent Run 剩余时间，均不等于求解器已运行时长。
- VM runner 在 `remote_runner_py36.py:456` 记录 started_at，并在519行写入终态 manifest。`debug_adapter.py:400` 读取该 manifest 后，仅投影退出状态、错误层级、摘要和日志，没有将起止时间或 manifest 文件交给作者。
- `execution_bridge.py:176` 仅在终态 collect。已存在的 inspect_outputs 也在 `remote_runner_py36.py:890` 拒绝未终态执行，不能作为实时日志旁路。

因此，作者可以从终态日志里已经存在的计时文本人工估计，但不能依赖接口稳定取得实际运行时长；当前预算数字不能当作测量结果。

## 已确认的日志类型交接缺口

本机 `execution_control.py:730` 与 VM runner `remote_runner_py36.py:421` 都将 tcad_log 导出为 `text/plain; charset=utf-8`。执行收集服务 `executions.py:513` 按原媒体类型登记，Artifact 模型验证参数是否合法但不剥离参数。

`plugin.py:478` 的 runtime-failure 作者 solver_log 端口只声明 `text/plain`。`operations/invoke.py:359` 按完整媒体类型字符串检查，因此实际 runner 日志会被拒绝为 `input_media_type_mismatch`，不是缺少读取文件权限。

对照结果：实际编译的 solver_log 端口接受 text/plain，拒绝 text/plain; charset=utf-8；Root preflight 对后者也在 solver_log 报该错误。见 `check-1789264013982505111.log`。

边界：Root 对照使用的 prior_project 是未资格化的合成记录，所以 text/plain 分支随后在 prior_project 被拒绝；这不是完整的作者交接验收。正例仅证明实际 solver_log 端口接受 text/plain，负例确认生产声明所导出的类型在相同端口被拒绝。没有假称替换类型之后整项任务已获准执行。分析角色的 diagnostics 使用 wildcard 端口，并按基本媒体类型检查 text/plain，因此不受这个具体缺口影响。

## 动态证据

- `log_visibility_probes.py` 前两个探针实际调用作者工具并读取输出文件，确认 pending 无日志/时间、terminal 日志可读，以及有时间戳的 server manifest 经 debug bridge 后丢失时间字段。
- 同组既有测试覆盖本机/VM runner 实现的 stdout、stderr、solver 日志保存，摘要外错误仍在完整日志中，缺口成果携带完整日志。测试中的进程是微小 shell fixture，不是 Sentaurus。
- 上述9项通过：`check-1789263555043472364.log`，2.99秒，峰值124.9 MiB。
- 媒体类型探针期望互操作的断言失败：`check-1789264013982505111.log`。其前一次探针错误地假设合成 prior_project 可直接准入，原日志 `check-1789263834573631843.log` 保留，后一次补了端口正负对照并明确了限制。

## 最小后续方向

1. 先对齐现有运行失败修订端口与 runner 导出的日志媒体类型，不取消日志身份和执行来源检查。
2. 沿同一 job 的现有轮询链，提供受限、只读的最新日志片段和明确的实际时序：接收时间、solver 开始时间、已运行时长、当前上限、最新日志更新时间。保留终态完整日志路径。不要新增日志 Agent 或要求作者直连 server。
3. 终态开发诊断保留 runner 已经记录的起止时间，让下一轮可使用可追溯的实际耗时；Agent 结合日志判断仍需等待还是任务预算不合适，不把预留预算当作预测，也不由控制层虚构完成百分比。

这三项是核查后的建议，本轮没有实施新的日志/进度接口。
