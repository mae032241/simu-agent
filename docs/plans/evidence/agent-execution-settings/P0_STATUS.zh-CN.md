# 执行配置 P0：隔离 CLI 验证记录

2026-09-15。**P0 已通过，开始 P1；P1–P6 尚未完成。** 用户已授权按 R1 执行；原启动目录问题已通过独立 CODEX_HOME 解决，正在继续实际角色分发与受控提交。下方旧失败保留为历史证据，不能把它们当作当前阻断或平台能力结论。

## 已完成

- [R1 独立计划审查](../../reviews/INSTANCE_AGENT_EXECUTION_SETTINGS_PLAN_R1_REVIEW.zh-CN.md)已 PASS；实施计划 SHA256 为 `d76e5ee486c1595fa7dc77c5776f3319b0650c9992f1914190b6ed69c9c731ec`。
- [源码基线](BASELINE.json)冻结 378 个文件，包含部署前已有工作树修改；[工作树状态](WORKTREE_BEFORE.txt)单独保存。未改运行源码、生成角色或生产配置，未提交 Git。
- 通过现有安装目录 `/opt/scidiscovery-m7/site` 取得 [50 项 Operation 与工具合同基线](CONTRACTS_BEFORE.json)；该只读探针成功，进程树峰值 88.05 MiB。
- 本机 `codex --version` 为 `codex-cli 0.154.0`。检查了既有 `run_compiled_codex_worker.py` 与 CLI 参数；使用独立 `/tmp/scid-execution-settings-p0` 工作区，配置 `--ignore-user-config --ephemeral`，SQLite 和日志位置指向临时目录。认证仍交给 CLI 自身，不复制或打印凭据。

## 尝试及准确失败层

| 记录 | 结果 | 说明 |
|---|---|---|
| [p0-connection.json](p0-connection.json) | 保护器终止；516.84 MiB | 通过 npm/Node 启动的最小无工具连接探针，3.608 秒触及 512 MiB 进程树预算；尚无模型回复。 |
| [p0-connection-native.json](p0-connection-native.json) | exit 127 | 首次指定原生二进制路径不正确；未启动 CLI。随后按已安装启动脚本核对实际路径，没有重复使用错误路径。 |
| [p0-connection-direct.json](p0-connection-direct.json) | exit 1；149.43 MiB | 直接使用已安装原生二进制，同时限制线程/分配 arena；不再触及内存预算，但初始化 in-process app-server 时遇到只读文件系统错误，耗时 31.595 秒。 |
| [p0-startup-trace.json](p0-startup-trace.json) | exit 1；149.41 MiB | 初次 syscall 选择只覆盖 openat 等，未捕获 musl 使用的 open；此记录不用于声称定位完整。 |
| [p0-startup-file-diagnostic.json](p0-startup-file-diagnostic.json) | exit 1；149.46 MiB | 完整文件类 syscall 追踪确认最终失败路径；33.389 秒正常报错退出，没有超时或内存终止。 |

命令的约 32 秒耗时属于 CLI 启动过程，不是模型分析耗时。没有模型回复或 Agent 子任务完成事件，无法确认请求模型已经被调用。单次模型连接探针也不能替代后续同角色两组配置的 P0 验收。

最终文件调用证据：

```text
chmod("/home/da/.codex/tmp/arg0", 0700) = -1 EROFS
open("/home/da/.codex/installation_id", O_RDWR|O_CREAT|O_LARGEFILE|O_CLOEXEC, 0644) = -1 EROFS
Error: failed to initialize in-process app-server client: Read-only file system (os error 30)
```

第一个调用对应启动警告；第二个调用紧邻内部服务初始化失败。当前会话只允许写项目工作区和 `/tmp`，`/home/da/.codex` 为只读。`--ignore-user-config` 和临时 SQLite/日志路径没有避免 CLI 打开 installation_id 为可写。没有放宽沙箱、修改该文件权限、改写用户配置或提高预算。

## 执行边界与后续

R1 P0 第 5 项要求：“只有 P0 通过后才实施 P1–P5。”当前是独立 CLI 启动环境不足，不能跳过 P0 把正式角色解除模型绑定，也不能使用通用 Agent 冒充受控角色。

后续需要在允许 CLI 使用其自身可写运行目录的隔离环境继续 P0，保持原 512 MiB 预算与串行方式，完成角色生成、两组实际模型/推理配置、固定模型负对照和受控提交证据。当前已加载的生产角色均固定模型，不能用本会话直接覆盖它们替代该测试。

此轮未运行全量测试、浏览器、仿真或科学 Operation；所有自有探针已退出。完整文件 trace 仅留在 `/tmp/scid-execution-settings-p0`，公开记录只保存上述必要错误路径，不复制认证材料。

## 独立 CLI 续测（当前）

按用户建议，独立 CLI 使用 `/tmp/scid-execution-settings-p0/cli-home` 保存自己的运行状态，只链接既有认证文件供 CLI 自身读取；未读取或复制认证内容。独立 TMPDIR 避免与外层沙箱的只读挂载锁冲突。两者都仅作用于测试子进程，未修改父会话配置、沙箱权限或生产状态。

- `p0-isolated-connection`：连接成功，12.793 秒，422.54 MiB。
- `p0-dispatch-a`：子 Agent 初始化阶段触发 512 MiB 守卫（528.36 MiB），未完成；后续按本机原生分配器设置 arena/回收参数，限制仅在测试启动脚本内。
- `p0-dispatch-a2`：关闭 code-mode host 导致 spawn 不可用，已恢复；CLI exit 0 不代表提交成功。
- `p0-dispatch-a3`：同一生成角色实际模型 `gpt-5.6-luna`、强度 `low` 已从平台 turn_context 观测，但测试父 CLI 遗漏 Worker MCP 配置，未受控提交；已复用安装生成的精确 Worker 服务配置。71.899 秒，209.73 MiB。
- `p0-dispatch-a4`：Worker 领取成功；本地命令因共用沙箱临时挂载锁只读失败，最终 Run 截止时间到期。118.631 秒，364.19 MiB。该错误属于测试嵌套 CLI 启动环境，不是输出校验。已显式记录测试 Run 失败。
- `p0-private-tmp-shell`：独立 TMPDIR 下，保持 workspace-write 沙箱，真实 `pwd` 执行成功。14.311 秒，181.47 MiB。

实际模型只采信平台 session_meta/turn_context，不采信 Agent 自述。受控完成只采信 Root run_status，不采信 CLI 退出码或 completion chat。全部探针串行，真实 Fig.4 未启动。P0 仍需两组成功提交与固定模型负对照；通过后才进入 P1。

## 最终 P0 结论：PASS

`dispatch_a5` 与 `dispatch_b` 的 Root 状态均 completed；同一编译角色的实际模型/强度分别为 luna/low 与 sol/medium，均调用原 Worker 领取、CSV 工具和提交。耗时分别 62.293 秒、83.337 秒，进程树峰值分别 496.67 MiB、396.54 MiB。角色数量始终为 1，动态角色字节已恢复并核对。

负对照1仅由调度 Agent 预测拒绝，不作平台证据；负对照2创建后立即关闭，缺实际模型观测，不作优先级证据。负对照3真实请求 luna/low，角色固定 sol，平台实际 turn_context 为 sol/low：固定模型优先，平台未拒绝创建。无任务入队，Worker 如实报告无精确任务；随后关闭该测试 Agent。47.996 秒，340.70 MiB。该行为证明部署必须移除角色固定模型，不能只传 spawn 参数。

[最终矩阵](P0_RESULT.json)、[平台元数据](P0_PLATFORM_OBSERVATIONS.json)和两个 `P0_*_STATUS.json` 是通过证据。所有历史失败日志保留。独立 CLI 暴露的 close_agent 已在正、负测试中实际使用；不能把本父会话仅有的 interrupt 说成关闭。生产源码、实例、生成配置仍未改变，现按原 R1 顺序进入 P1。
