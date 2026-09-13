# 执行收集修订版独立工程复审 R5

日期：2026-09-13。结论：**REVISE：暂不通过当前 Linux local_trusted TCAD 路径部署复审。**

R4.1 的原生 SSH 锁所有权问题在正常监督、预算停止和父死亡路径上已修复：新增 guard 与实际工作组分离，由 guard 保留两个锁，不再要求原生程序继承锁。独立重跑真实 OpenSSH/工作组暂停/父死亡对照通过。但停止观察发生异常时，guard 仍可能从清理条件再次抛错并退出。独立故障注入确认，此时两把锁可以重获，而同组子进程仍在运行。另确认一个不延长预算的 P3 超时分类竞态。

[R1](INDEPENDENT_REVIEW_R1.zh-CN.md)、[R2](INDEPENDENT_REVIEW_R2.zh-CN.md)、[R3](INDEPENDENT_REVIEW_R3.zh-CN.md)、[R4](INDEPENDENT_REVIEW_R4.zh-CN.md) 的 REVISE、原清单和失败证据均保留。本报告评价冻结的 R5 字节，不为收到新发现后的修订提前授予 PASS。

## 1. 精确输入与检查范围

受审输入为 [incremental-manifest-r5.json](incremental-manifest-r5.json) / [incremental-r5.diff](incremental-r5.diff)，共 **47 文件**。改前工作树仍由 [baseline.json](baseline.json) 指向 `/tmp/scid-collection-baseline-1789276126341295526`，未以 HEAD 替代本轮基线。复审开始时全部当前 SHA-256 匹配；原冻结计划摘要仍为 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`。

相对 R4 变化为一个生产模块 `execution_collection.py`、其所属测试以及中英文架构文档和传输合同，共五文件。修订理由见 [REVIEW_REVISION.zh-CN.md](REVIEW_REVISION.zh-CN.md) 的 R4 节；旧 FD 继承解释已明确被替代。独立读取 `/tmp/scid-collection-installed-lke604j7`，**32 个受影响的已安装生产 Python 文件摘要全部匹配 R5 清单**。

本次只执行第 2—4 节的串行有界探针和一个原生 SSH 所属用例，均经本目录 `check.py` 的 512 MiB / 150 秒 harness。没有重跑未变化的 43 项分析恢复测试，没有全量、并行或 xdist 测试。未操作科研实例、Worker MCP、审批、VM、部署、网络或求解器；原生 SSH 仅使用本地 sleep ProxyCommand。其他测试结果来自读取既有日志与源码，没有冒称独立重跑。

## 2. R5.1 — P2：停止观察失败会使 guard 退出并提前释放锁

**归属：R5 新增 guard 的停止异常路径缺陷；已通过明确的 OS 观察故障注入复现。不是原生 SSH 正常路径仍未修复，也没有声称现场已经发生 `/proc` 故障。**

位置：`src/scidiscovery/artifact_agent/service/execution_collection.py:161` 的 `_group_running`，尤其 `:169` 的 `/proc` 目录枚举；`:465` 的 guard 主循环条件和 `:480` 的 finally 清理循环条件。

`_group_running` 对单个 `/proc/<pid>/stat` 读取错误返回 True，含义是“尚不能证明工作组已停止”；但 `os.scandir('/proc')` 自身的 OSError 没有被捕获。实际组 leader 已退出、同组后代仍活跃时，guard 需要调用该函数。目录枚举错误先从主循环条件抛出，随后 finally 在执行停止信号之前又求值同一函数，再次抛出。guard 随即退出，持有的两个锁由 OS 关闭。

### 独立复现

探针启动真实 `_guard` 并传入两个真实 `flock`。唯一工作组 leader 启动一个普通同组 Python 子进程后正常退出，子进程继续 sleep；不另起会话、不主动改变 FD 或权限。仅在 guard 进程内将 `/proc` 枚举注入为 `OSError(5, 'injected /proc enumeration failure')`。检查结果：

```json
{
  "guard_returncode": 1,
  "locks_reacquired": [true, true],
  "actual_descendant_still_running": true,
  "injected_error_seen": true
}
```

证据：[check-1789285551362051692.log](check-1789285551362051692.log)，0.41 秒、峰值 76,673,024 字节，无资源停止。探针最后清理了整个工作组。第一次探针使用 `communicate` 等待仍被活跃后代持有的 stdout/stderr 管道而超时，见 [check-1789285516714496730.log](check-1789285516714496730.log)；改为先 `wait` 确认 guard 退出、再检查活跃后代与锁，最后清理并收管道。原失败保留，不作为独立的生产缺陷。

触发条件是停止组观察不可用，同时 leader 已结束而同组后代未结束。其影响是原来要求的“停止未确认则保持所有权”反转成“无法观察则退出所有者”。重启/再次收集不再受到两把锁约束，因此是当前部署阻断。

最小修复：在同一个停止证明函数中将完整 OS 观察过程的失败视为尚未证明退出；让 guard 继续持锁，并保证观察异常不会跳过停止信号和后续重试。沿用现有布尔“仍存在或无法证明不存在”的含义即可，不需要新服务、科学状态或 Agent 字段。补充枚举失败期间锁不可重获、恢复观察并确认实际停止后才释放的负向对照。不要把异常转换为 False，也不要靠延长 collection 预算掩盖。

## 3. R5.2 — P3：guard 自行超时后，父监督可能记录为一般失败

**归属：R5 双层截止点监督引入的诊断分类竞态；已独立复现。没有导致实际预算延长或 Run 被强制科学失败，不单独作为停止所有权的 P2 阻断。**

位置：`execution_collection.py:467`—guard 自行根据工作截止点停止实际组；`:339`、`:364`—父 `_watch` 仅在自己观察到工作到期、设置本地 `signalled` 时分类 timed_out。guard 没有向父记录本次停止的原因，父若首次获得调度时 guard 已退出，会将仍为 running 的状态记录改为 failed，并捕获一般 runtime_failure。

独立探针使用真实 ExecutionCollection/guard/工作组，收集预算为 0.8 秒；仅延迟父 `_watch` 的首次执行 1.3 秒，模拟父监督线程未及时获得调度。实际 worker 确已启动，guard 自行到期并完成停止，随后父记录：

```json
{
  "worker_really_started": true,
  "total_seconds": 0.8,
  "parent_watch_initial_delay": 1.3,
  "collection_state": "failed",
  "error_category": "runtime_failure",
  "exit_code": 241
}
```

证据：[check-1789285612324952747.log](check-1789285612324952747.log)，1.71 秒、峰值 100,478,976 字节。没有改变 guard 时钟或预算，也没有伪造其返回码；注入的是父监督调度延迟。该复现证明分类依赖调度先后，不声称常规 24 项用例均存在此失败。

影响是具体超时原因丢失，最终可能提示一般运行错误；科学调度不应据此误读成求解器或科学模型失败。最小修复可由实际作出停止决定的 guard 记录有界原因，再由父沿用现有诊断和 collection 状态字段；不需要新 Run 状态或让 Agent 提交时间证明。

## 4. R4.1 关闭与实现范围判断

| 边界 | R5 复核结论 |
| --- | --- |
| guard 与实际工作组 | `:288` 仅 guard 继承两把锁；`:461` 实际工作另建进程组、只保留父管道读端。原生 SSH 关闭额外 FD 不再影响锁所有权。R4.1 的正常路径缺口已关闭 |
| 父死亡与停止请求 | 父 EOF/TERM 设置 guard 停止事件，guard 终止实际组并等待非僵尸成员清空；Root 请求 TERM 而不强杀 guard。正常路径符合停止确认先于解锁的要求；异常观察路径由 R5.1 单独指出 |
| 嵌套命令权限 | 共享 `run_bounded` 仍以私有组标记保持嵌套 command/SSH 同组，锁 FD 环境传播已删除；没有扩展到任意日志 PID 或无关任务 |
| 正常返回与残留后代 | 工作 leader 结束后 guard 仍检查实际组，存在后代就停止并等待；不会仅凭 leader 返回码释放所有权。R5.1 是观察失败例外 |
| 总预算 | 创建 guard 前冻结的同一 CollectionContext 被原样传给 guard 和实际收集，启动耗时计入原预算，没有在新进程层重计时。未证实预算延长；R5.2 仅涉及最后分类 |
| 作者 debug 与分析 | 本次没有给作者增加正式收集全局锁或新 IO 门禁；未改作者 360 秒 solver 账本、分析 120 秒 IO 账本、原 inspect/accept 入口绝对截止点或有限分析提交路径 |
| 实现最小性 | 增加一个不执行 adapter 的私有控制进程，是修复原生程序不能承担锁所有权所需的本地监督边界；仍为唯一实际收集、同一全局槽。没有新服务、Operation、科学 Schema、审批身份、VM 协议或运行依赖 |

独立重跑原生 OpenSSH 对照 [check-1789285620380576932.log](check-1789285620380576932.log)：1 passed，2.62 秒、峰值 175,943,680 字节。该用例暂停整个实际工作组、杀死父进程，在尚未停止的窗口确认恢复仍 pending 且再次 collect 被拒绝，随后实际组结束才允许继续。测试只用本地 ProxyCommand，不联网。它有效关闭正常父死亡路径，不能代替 R5.1 的观察故障对照。

## 5. 验证与全局残余优先级

已读取所属 [check-1789285233730332650.log](check-1789285233730332650.log)：24 passed。首次 [check-1789285189394733518.log](check-1789285189394733518.log) 的两个失败来自源码夹具没有向新增模块子进程传递 PYTHONPATH；随后修正环境传递，原断言保留，没有增加资源或时间预算。

已读取四 wheel 实际安装链 [check-1789285266474714483.log](check-1789285266474714483.log)：通过，15.39 秒、峰值 412,704,768 字节（393.59 MiB）；安装字节已独立核对。实际链路为 stdio proxy → daemon → guard → 实际 collector 重开 command adapter → 无预置 checkpoint 的 collect → 登记 → 幂等 outputs。该夹具使用隔离历史终态数据库而不求解，精确 UI 身份负向对照另行保留。

| 优先级/归属 | 当前问题或限制 | 后续最小边界 |
| --- | --- | --- |
| P2，本轮阻断 | R5.1 停止观察异常导致解锁时仍有活跃工作 | 修复停止证明失败语义，提供精确新摘要与异常持锁对照，再独立复审 |
| P3，本轮诊断缺陷 | R5.2 guard 超时原因依赖父线程调度而丢失 | 由实际停止所有者保存原因，复用原诊断/状态字段 |
| P2，既有全局兼容缺口 | `general_science_components.py:465` 公共 workspace 有 finalizer 而无 file policy；`hardened_files.py:209` 结果写入规则与 `result_materialization.py:12` finalizer 消费要求冲突 | 独立修复公共 workspace 合同与真正受支持的 Hardened 组合；不删 review 边、不扩大科学权限 |
| 未验收，不是已发生的故障 | 全部自定义 query/proxy 超时组合、未走 launcher 的原生命令、全 backend/plugin/revision/qualification 组合及非本地管理的外部副作用 | 仅按后续部署/使用范围补充有界验证，不宣称全框架通过 |
| 科学验收未执行 | 原 Fig.4 同次执行的现场产物恢复、曲线对齐、目标覆盖和匹配分析 | 只能由实际产物及对应 completed 封存分析证明，不能从工程测试推导 |

R1 以来的全局审查重点继续有效：模型可见输出与执行准入必须组合一致；工程异常不能变成科学事实或新的科学门禁；缓存和 checkpoint 不更新资格；工具观测只陈述实际覆盖。R2.1 准备截止点、R3.1 仓库调用者、具体工程诊断及有限报告继续提交的修复均保持，未在未变化的代码上发现回退，也未重复运行已通过的完整分析文件测试。

## 6. 部署结论

**R5 仍不通过当前 Linux local_trusted TCAD 部署复审，主要阻断为 R5.1。** guard 的范围调整可接受，正常 OpenSSH/父死亡路径已有独立证据；不能因该通过而忽略异常时提前释放所有权。新的修订须保留本次发现、提交对应精确字节和负向对照，再重新判定。

后续即使工程复审 PASS，也只适用于受审 Linux local_trusted TCAD 路径，不代表 Hardened 通用兼容、裸平台观测、所有预算配置或全框架科研能力完成；更不代表 Fig.4 或整体研究目标已经完成。
