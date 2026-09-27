# 执行收集修订版独立工程复审 R3

日期：2026-09-13。结论：**REVISE：暂不通过当前 local_trusted TCAD 路径的部署复审。**

R2 已复现的准备阶段截止点重计时已修复；R3 新增的进程组停止确认与锁传递方向合理，但仍漏掉 SSH 地址解析器和非下载 RPC 的真实子进程入口。独立探针确认该入口收到锁编号元数据时，两个锁 FD 实际已关闭。此项须补齐再复审；不能用仅经过共享 `run_bounded` 的两级夹具证明所有实际调用者均已覆盖。

[R1](INDEPENDENT_REVIEW_R1.zh-CN.md) 与 [R2](INDEPENDENT_REVIEW_R2.zh-CN.md) 原 REVISE 结论、失败日志和初始探针均保留。本报告针对冻结的 R3 字节，不为主代理收到新发现后开展的修改提前授予 PASS。

## 1. 精确输入与证据核对

输入为 [incremental-manifest-r3.json](incremental-manifest-r3.json) / [incremental-r3.diff](incremental-r3.diff)，共 **46 文件**，仍以原 [baseline.json](baseline.json) 的改前工作树为基线。复审开始时逐项 SHA-256 全部匹配。相对 R2 仅四个文件变化：`output_recovery.py`、`execution_collection.py` 及两个所属测试文件。原冻结计划摘要保持 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`，修订解释见 [REVIEW_REVISION.zh-CN.md](REVIEW_REVISION.zh-CN.md)。

独立读取最新隔离环境 `/tmp/scid-collection-installed-d__5kdjb`，32 个受影响的已安装 core/TCAD/curve_score 生产 Python 文件 SHA-256 **全部匹配 R3 清单**。因此最新安装日志确实对应受审字节。

本次独立动态验证仅执行第 2 节的串行小探针，使用本目录 `check.py` 的 512 MiB / 150 秒限制。其他验证结果为读取已有测试源码及日志，没有冒称独立重跑；未操作科研实例、Worker MCP、审批、VM、部署或求解器。没有全量或并发 pytest。

## 2. R3.1 — P2：SSH 的 `_run` 子进程入口仍丢失控制锁 FD

**归属：R3 停止所有权修复中的遗漏调用者；通过真实 SSHRemoteClient 入口独立复现。**

位置：`plugins/tcad_artifact/tcad_artifact/ssh_transport.py:79` 的 `SSHRemoteClient._run`，直接调用 `subprocess.run`；其调用者包括 `:223` 的非下载 RPC/清单请求和 `:248` 的 `_destination` 地址解析器。新元数据传播仅在 `src/scidiscovery/artifact_agent/service/execution_collection.py:29` 的 `run_bounded` 中实现。

R3 的 `watch_parent` 将私有组和两个锁 FD 编号记录为控制元数据。`run_bounded` 在该组中使用 `pass_fds` 传给后代，但 SSHRemoteClient 的 `_run` 没有走这段逻辑。Python 的 `subprocess.run` 默认关闭未显式保留的 FD；`_transport_environment` 却可以继续携带组和锁编号环境变量，导致元数据与实际持锁情况不一致。

独立探针在独立进程组内创建并持有两个实际 `flock`，调用真实 `watch_parent(..., owned_fds=...)`，再调用真实 `SSHRemoteClient._destination → _run → subprocess.run`。地址解析器仅检查 FD 并返回 `127.0.0.1`，没有连接网络。结果为：

```json
{
  "metadata_fd_count": 2,
  "locks_accessible": [false, false],
  "same_private_group": true
}
```

证据：[check-1789283614655879252.log](check-1789283614655879252.log)，0.41 秒、峰值 62,464,000 字节，无资源停止。子进程仍在预期进程组，但没有继承任何控制锁；不能将该结果描述为主动关闭 FD 的第三方逃逸，因为关闭发生在本仓库的实际 `_run` 调用边界。

影响：R3 借助 FD 所有权保证“父服务退出后，未实际退出的受管传输仍持续持锁”，该保证没有覆盖地址解析与清单/RPC 阶段。当父级已经退出而该阶段子进程尚未实际结束时，该子进程不能再替父级保持执行锁和全局槽。`_watch` 在父服务存活时新增的 `/proc` 检查有价值，但不能替代父服务死亡后的 FD 所有权。普通可立即终止的子进程仍受同组信号约束；**本探针只证明真实 FD 传播缺口，没有声称 R3 正常传输已经发生锁释放后的晚写或重新求解。**

现有 `test_parent_death_stops_collector_before_restart_releases_lock` 的第二级传输显式调用 `run_bounded`，可验证该共享函数自身的传播，却未经过上述真实 `_run` 分支。因此其 23 pass 不能关闭这一接口遗漏。

最小修复：在单一共享位置提供受控进程组/锁 FD 的投影，供 `run_bounded` 和 SSHRemoteClient `_run` 的实际调用共同使用；或仅在受管分支复用符合原调用行为的共享执行实现。独立 query、旧调用和作者 debug 的权限/预算边界保持原含义，不能把锁扩散到无关任务。补充真实 `_destination` 与非下载 RPC 子进程的 FD、组及退出对照；不需要新服务、科学字段或 VM 协议。

## 3. 已完成的修复与范围判断

| 项目 | 本次复审核对 | 判断 |
| --- | --- | --- |
| R2.1：准备阶段重计时 | inspect/accept 在入口冻结 `run_deadline`；scope、输入读取及 IO 预留后取原值与 IO 额度的 min；服务直接转发绝对值，不再 `now +` 旧剩余量；准备后不足时释放未消费的预留 | 已修复所指出机制。两个入口准备延迟测试实际检查传到适配器的 deadline；无需为科学 Agent 新增时间字段 |
| 本地读取/哈希预算 | R2 的 helper 内循环检查、本地 consume、accept、副本写入及 IO 结算仍存在 | 没有发现本次回退；保留原慢哈希服务端停止和局部耗时记账证据 |
| 工程错误与有限分析 | 未知工程异常仍交共同 Worker 边界，明确 unsupported/缺文件/额度不足保留有限返回；inspect/accept 错误后仍可合法提交有限报告 | 没有新增 Run 强制失败或科学门禁 |
| 进程组实际停止确认 | collector 在直接子进程退出后扫描自己创建组的非僵尸成员；仍活跃则保持 stop_pending 并继续持锁，不将 zombie 当可计算/持 FD 成员 | 方向合理且不新增依赖；R3.1 说明父死亡时的锁传播仍未覆盖全部真实子调用 |
| native 观测策略 | inherit 默认 reserve=0、analysis=120 的 R2 修复未改变 | 已修复行为保持；未经过 launcher 的命令仍没有完整观测证明 |
| 已安装实际收集链 | stdio proxy main → daemon main → collector 重开 command adapter → 实际 collect → 登记 → outputs；无预置 checkpoint，重复调用不再次 collect | 最新安装路径有效，仍为隔离历史终态夹具；不是 VM/SSH 现场验收 |
| 共享 helper 的范围澄清 | 可选本地 deadline 及循环检查未扩展远端 RPC 字段，也没有改求解入口 | 接受该最小兼容修改；本轮无需据此更新 VM runner |
| 作者 debug 的 360 秒账本 | 继续是 solver wall time 预留，终态收集受 Run 剩余预算管理，不套用正式 600 秒默认 | 解释合理；不应改成禁止收回已完成产物的新 IO 门禁 |

停止权限仍来自控制创建的进程组和实际继承关系，不来自日志中任意 PID。`/proc` 检查及 FD 传播不应扩展为通用进程管理框架；当前差异中未见新科研 Operation、科学 Schema、Run 状态枚举或 Agent 机械填表要求。

## 4. 验证记账与部署结论

已读取的 R3 证据包括：

- [check-1789283049536392036.log](check-1789283049536392036.log)：5 passed，两个入口的准备延迟、原本地哈希和工程错误链相关对照。
- [check-1789283274829656234.log](check-1789283274829656234.log)：收集所属 23 passed，实际 command 与显式共享执行下层的 FD/组回收路径。
- [check-1789283382907880161.log](check-1789283382907880161.log)：分析恢复所属 43 passed。
- [check-1789283436473293720.log](check-1789283436473293720.log)：四 wheel 真实安装链通过；对应 32 个生产文件已独立比对摘要。
- 新增独立探针 [check-1789283614655879252.log](check-1789283614655879252.log)：确认真实 SSH `_run` 的锁 FD 丢失。

**当前不能部署为本轮修复已通过的 local_trusted TCAD 版本。** 最小剩余工作是补齐 R3.1 的实际子进程调用者、提供精确新摘要和对应负向对照，再独立复审。原 R2.1 不再是本次阻断，不能因新缺口而否认已经完成的预算修复。

既有 Hardened 公共 workspace/finalizer 写入冲突继续明确延期；裸平台 native 覆盖、所有自定义 query/proxy 预算组合、非本地管理的外部副作用和原 Fig.4 现场验证也继续未关闭。这些不能混写成已经完成，但也不能直接当成 local_trusted Fig.4 已发生科学失败的证据。

后续工程部署通过仍不等于研究完成。只有恢复同一次已批准执行的产物，并由匹配分析 Operation 形成 completed 的封存分析，才能报告曲线对齐、目标覆盖和科学结论的实际范围。
