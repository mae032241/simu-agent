# R5-M7.2 Trusted-local 启动边界独立复审

日期：2026-09-02

结论：PASS

范围仅包括：

- `scripts/run_compiled_codex_worker.py`；
- `scripts/compiled_worker_native_guard.py`；
- `scripts/compiled_worker_process_guard.py`；
- 对应启动器、Hook、提交门、进程树和失败收据测试；
- TCAD 作者、审查者与 SDevice 任务内合同的边界文字。

本结论不证明 TCAD 科学产物通过，也不把 trusted-local 后端升级为生产级隔离。

## 首轮结论：FAIL

独立审查指出五个阻断项：

1. 根进程退出后，仍存活子孙可能逃逸进程树内存熔断；
2. Hook 对 `apply_patch` 字段和实际工具名缺少稳定契约；
3. Bash 缺省 `workdir` 时的 `cwd` 语义未闭合；
4. native violation 检查与提交之间存在竞态；
5. receipt v4 未禁止额外字段，且 Python `bool` 可伪装成 `int`。

## 返工

- 聚合 RSS 监视器持续记录已观察后代；根进程退出后同时清理原进程组和已观察的脱离后代；
- 根据 [Codex Hooks 官方契约](https://learn.chatgpt.com/docs/hooks) 固化公共顶层 `cwd`、
  `Bash`/`apply_patch` 的 `tool_input.command`、统一执行到 `Bash` 的映射以及代码模式嵌套调用；
- 同步覆盖 `Bash`、`apply_patch` 和已声明的 `view_image`，其他网络、Agent 与 MCP 能力仍按编译
  profile 和精确 Worker server 关闭；
- `PreToolUse`/`PostToolUse` 在同一锁保护状态中维护在途调用数；提交只在零在途、零违规时原子设置
  `submission_started`，之后的新原生调用失败关闭；
- receipt v4 使用精确顶层字段、精确 Worker 事件字段和 `type(value) is int` 等价严格类型；
- 初始化期中断也进入同一失败收据 `finally`，临时事件或审计日志随后清理。

低内存串行组合回归为 `27 passed`。

## 复审结论

独立审查确认五项阻断均已关闭。新增状态只属于启动器/审计代理，不拥有 Run、Artifact、Operation、
current 或科学判断，因此没有形成第二控制面。

仍保留并明确声明的限制：Linux `/proc` 轮询存在采样窗口及未观察 reparent/setsid 盲区，只是本地
可信原型的紧急熔断；生产后端仍需要 cgroup 或等价的操作系统级隔离。该限制不阻断下一次严格串行、
单 Worker、4 GiB 聚合预算的 M7.2 调试运行。
