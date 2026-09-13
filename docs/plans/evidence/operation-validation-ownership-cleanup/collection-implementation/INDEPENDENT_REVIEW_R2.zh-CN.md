# 执行收集修订版独立工程复审 R2

日期：2026-09-13。结论：**REVISE：R2 仍有一项已复现的 P2 截止点重计时缺陷，不授予部署通过。**

R1 的主要修复方向已经落实，实际安装传输链也已补充；本次独立复审发现分析工具的准备阶段仍会延长适配器获得的 Run 时间预算。主代理收到该发现后开始下一次修订，本文仍针对精确 R2 输入，不能自动变为修订后 PASS。[R1](INDEPENDENT_REVIEW_R1.zh-CN.md) 原结论及证据保留。

## 1. 精确输入与独立验证

- 初审基线仍为 [baseline.json](baseline.json) 指向的 `/tmp/scid-collection-baseline-1789276126341295526`，Git HEAD 不代替该基线。
- 复审输入为 [incremental-manifest-r2.json](incremental-manifest-r2.json) / [incremental-r2.diff](incremental-r2.diff)，**46 文件**。开始复审时逐项核对当前文件 SHA-256，全部匹配。相对于 R1 有八个文件变化：公共索引、socket facade、分析恢复工具、共享 inspection helper、native 观测器、两个所属测试文件及收集协调器。
- 冻结计划 SHA-256 仍为 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`；范围解释见 [REVIEW_REVISION.zh-CN.md](REVIEW_REVISION.zh-CN.md)。本复审没有改变原计划或 R1。
- 独立核对 [installed-smoke.json](installed-smoke.json) 指向的隔离 venv：**32 个受影响的已安装生产 Python 文件**逐项 SHA-256 均与 R2 清单一致，覆盖 core、TCAD 及 curve_score 相关模块。这一步证明现有安装证据对应 R2 字节，不只证明同名模块可导入。
- 独立动态验证仅运行第 2 节的小探针，经本目录 `check.py` 串行执行，512 MiB / 150 秒边界内完成。其余结果为审阅已有测试源码和日志，未冒称独立重跑。没有运行科研实例、MCP 科学 Worker、审批、VM、部署或求解器，也没有全量或并发 pytest。
- 主代理收到新发现后进行的源码修改属于后续输入；本文源码位置按 R2 摘要与对应函数定位。

## 2. 剩余部署阻断

### R2.1 — P2：分析入口在准备工作之后使用旧剩余秒数创建新截止点

**归属：本轮预算修复仍不完整；通过真实 Worker 工具入口独立复现。**

位置：`plugins/tcad_artifact/tcad_artifact/output_recovery.py` 的 `_inspect`：先执行 `context.execution_scope`、`context.read_input('reviewed_package')` 和 `context.io_budget(reserve=True)`，随后才使用 `context.remaining_seconds` 计算 `timeout`，并以新的 `time.monotonic()` 建立 `deadline`；`OutputInspectionService.inspect` 又将相对 `timeout` 转回 `now + timeout`。剩余秒数来自 `mcp_local_worker.py` 构建 `OperationToolContext` 时的快照，不是动态读取的当前剩余时间。

触发条件：精确执行来源解析、绑定输入读取/校验或 IO 额度预留消耗了部分 Run 时间，但尚未达到真正 Run 截止点。这些工作完成后，原剩余秒数被重新完整授予适配器。R2 在远程调用后的本地哈希和副本处理已加入检查，但不能补回开始远程调用前丢失的时间。

独立探针：建立隔离的真实分析 Worker 及终态执行夹具，将该 Run 数据库中的实际截止点设为约 3.1 秒后；仅在读取 `reviewed_package` 时注入 1.2 秒延迟。通过实际 `worker_tcad_inspect_outputs → OutputInspectionService → adapter.inspect_outputs` 记录传给适配器的绝对截止点，适配器返回有限的 `not_found`，不运行传输或求解。

实际观察为：

```json
{
  "context_remaining_seconds": 3,
  "adapter_deadline_exceeds_run_seconds": 1.226,
  "tool_status": "not_found",
  "run_state": "running"
}
```

证据：[check-1789282825999790030.log](check-1789282825999790030.log)，耗时 3.24 秒、峰值 113,315,840 字节，无资源停止。探针证明**适配器实际获授的时间晚于原 Run 截止点**，不是只检查函数接受新参数；它未声称科学结果在过期后被成功提交。

影响：当适配器用完所获预算时，可在原 Run 时间耗尽后继续查询/读取；随后 `accept_evidence` 或 IO 结算的 Run 状态检查才拒绝，并不能使先前 IO 按原时间停止。该行为违背“准备、查询、读取、登记共用同一绝对截止点”的计划承诺。

最小修复：在 inspect/accept 工具入口、进行任何准备工作之前冻结该次 Run 的绝对 monotonic 截止点；准备与额度预留后取其**当前**剩余量，并将同一个绝对截止点传入服务、适配器和本地消费回调。已有相对 timeout 调用可保留兼容包装，但本次受控路径不能再以旧秒数重启时钟。补充准备阶段耗时的负向对照，验证传到适配器的值不超过入口冻结值；保留 R2 已验证的本地哈希和有限分析提交行为。

## 3. 对 R1 六项发现的复审结果

| R1 项目 | R2 复审核对 | 结论 |
| --- | --- | --- |
| R1：嵌套 command 进程逃逸 | `watch_parent` 标记私有进程组，`run_bounded` 在该范围内不再另建 session；独立查询仍拥有自己的组。collector 外围最终处理自有组，作者 debug 继续受私有外层管理。父死亡测试现在真正调用 command 适配器并核对组、后代终止及无晚写；作者新/旧 collect 超时也检查传输 PID | 原已复现的独立组逃逸路径已修复；停止确认的极端边界见第 4 节，不宣称所有后代状态均已证明 |
| R2：服务内部读取未消费预算 | local socket 传原 deadline 进入共享 helper；遍历、路径检查、逐块读取/哈希都有检查。本地证据读取、accept 与副本写入进入原 IO 结算区间 | 原 helper 缺口已修复，但 R2.1 的入口准备阶段重计时仍阻断完整闭合 |
| R3：可选工具吞掉工程异常 | 未知工程异常交共同 Worker 边界；明确 unsupported/缺失/额度不足仍可有限返回。新测试经 inspect/accept 两入口检查引用、脱敏、工作区报告，错误后 Run 仍 running 并能提交合法有限分析 | 已修复已指出路径；工具级 MCP 错误没有被改成科学 Run 强制失败，也未新建 Agent 必填诊断字段 |
| R4：inherit 隐式保留 120 秒 | CLI 默认改为未指定，控制 policy 决定 analysis=120、inherit=0；实际默认 CLI 测试有只剩 10 秒的 assignment deadline | 已修复；环境与完整 stdout 对照保留，旧分析入口的默认保留额继续存在 |
| R5：general workspace/Hardened 写入冲突 | 生产源码未修改；修订说明明确既有问题及 local_trusted 部署限定 | **未修复，明确延期**；不能报告全 backend 兼容。它不构成原 Fig.4 local_trusted 的现场失败证据 |
| R6：安装 smoke 预置 checkpoint | 新 probe 经过已安装 stdio proxy main、daemon main、collector 子进程重新加载 TCAD command 适配器、真实 collect、登记与 outputs；启动前断言没有 checkpoint，重复调用断言 collect 仅一次 | 已补足本轮 command 安装链证据，仍是隔离终态夹具，并非 VM/SSH 现场验收 |

安装新路径还揭示了控制生成时间格式的问题：原 `_now()` 输出 `+00:00` 与既有 manifest 的 `Z` 合同不符。R2 改为控制生成 `Z`，没有修改科学 Schema 或要求 Agent 填时间。失败 [check-1789282319222811454.log](check-1789282319222811454.log) 保留；后续安装链通过是有意义的反例修复，不应删除此前失败记录。

## 4. 全局与停止边界的保留判断

**进程组停止范围改善，不等于所有内核状态均已完成回收。** R2 的 `ExecutionCollection._watch` 最终向自有组发送 SIGKILL 后，仍依据直接子进程的 `poll()` 释放父侧锁，没有逐一观测所有非僵尸后代实际退出。父死亡测试另外等待传输 PID 终止后才尝试恢复，证明该受控情形可以结束；不能据此证明处于不可立即回收状态的成员仍占有恢复锁。本复审没有复现 R2 正常本地 command 在锁释放后继续晚写，因此不将此限制伪装成 R1 原故障重现。若继续承诺计划中的 `stop_pending` 覆盖此类状态，应补相应所有权持续或停止确认机制；发送信号本身不是完整的停止证明。

**共享 helper 的范围澄清合理。** `remote_runner_py36.py` 的变化仅在 `_inspect_directory` 增加兼容的可选本机 deadline 和循环检查；远端 RPC 调用未增加字段，默认调用仍使用原协议及行为，未修改求解入口。该小范围共用函数修改比复制一份本地遍历器或新建进程层更直接。本次可接受“无需为此更新 VM runner”的部署说明，不能写成“remote_runner 源码完全未改”。

**作者调试预算解释合理。** 原 360 秒账本是提交时预留的 solver wall time；把余额用尽解释为禁止收回已完成产物，会新增未声明 IO 门禁。保留该账本、终态收集使用当前 Run 预算及停止余量，且不套用正式收集 600 秒默认值，符合既有职责。该解释不授予新的求解或重复 submit 权限。

**有限工程失败与科学结论继续分开。** R2 未增加科学 Run 状态、Operation、科学字段或额外资格门槛；共同诊断记录是工程事实，可选工具失败后的合法提交仍由现有 output 合同判断。没有观测数据仍不能推出没有 native 错误，也不能把工具不可用解释为模型无法拟合。

以下仍未完成验收，不随 R2 测试绿色关闭：原 Fig.4 同次执行的现场恢复及封存分析、全部自定义 query/proxy 预算组合、平台未经过 launcher 的原生命令、所有插件和 backend 组合、Hardened 公共工作区兼容，以及异常存储/不可立即终止进程的所有恢复组合。

## 5. 验证证据与部署判定

本复审读取并核对以下有范围的证据：

- [check-1789282183292299150.log](check-1789282183292299150.log)：37 passed，涉及收集、实际嵌套 command 父死亡、作者调试、诊断与观测。
- [check-1789282288471519436.log](check-1789282288471519436.log)：2 passed；真实 socket 服务的慢哈希对照在一个块后停止后续处理，普通状态查询仍可用。
- [check-1789282422521861867.log](check-1789282422521861867.log)：40 passed，分析恢复所属文件。
- [check-1789282593309946733.log](check-1789282593309946733.log)：1 passed，本地哈希耗时进入同一 IO 结算区间，工具错误后 Run 仍 running。
- [check-1789282517491317150.log](check-1789282517491317150.log)：四 wheel 隔离环境实际安装链通过，14.52 秒，报告峰值约 354.47 MiB，小于 512 MiB；该路径使用显式标注的历史终态数据库夹具，审批 UI 的负向测试另行保留。
- 本次新增独立探针 [check-1789282825999790030.log](check-1789282825999790030.log) 确认 R2.1；没有因已有 37/40 pass 将其忽略。

**R2 不通过部署复审。** 修复 R2.1 后须提交新的精确摘要和准备阶段预算对照，连同停止确认边界的准确声明再复审。R5 可作为明确的既有 Hardened 缺口单独保留，但部署结论只能针对受检的 local_trusted 路径，不能扩展为全框架或全配置通过。

即使后续工程复审通过，也只能授权进入对应工程部署/恢复步骤；不会证明 Fig.4 曲线已对齐、全部原研究目标覆盖、科学机制唯一确定或科学任务已完成。这些结论仍需同次执行产物及匹配 Operation 的 completed 封存分析。
