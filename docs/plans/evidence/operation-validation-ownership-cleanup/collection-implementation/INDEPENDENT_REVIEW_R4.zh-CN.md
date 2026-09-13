# 执行收集修订版独立工程复审 R4

日期：2026-09-13。结论：**REVISE：当前 local_trusted TCAD 路径尚不能作为本轮停止所有权修复已完成的版本部署。**

R3.1 的仓库调用者遗漏已经修复，R2.1 的准备阶段截止点也通过独立回归。但本次使用真实 `/usr/bin/ssh` 确认：OpenSSH 启动后关闭两个继承的控制锁 FD；传输仍运行且仍在私有进程组。当前停止设计依赖活跃传输保留锁，因此不能把 Python 解析器/RPC 替身通过扩展为原生 SSH 的所有权保证。此项须修订后再复审。

[R1](INDEPENDENT_REVIEW_R1.zh-CN.md)、[R2](INDEPENDENT_REVIEW_R2.zh-CN.md)、[R3](INDEPENDENT_REVIEW_R3.zh-CN.md) 的 REVISE、精确清单与失败证据全部保留。本报告只评价 R4 冻结输入，不为主代理收到新发现后开展的修改提前授予 PASS。

## 1. 受审输入与独立验证范围

输入为 [incremental-manifest-r4.json](incremental-manifest-r4.json) / [incremental-r4.diff](incremental-r4.diff)，共 **47 文件**；改前工作树仍由 [baseline.json](baseline.json) 指向 `/tmp/scid-collection-baseline-1789276126341295526`，未将 `git diff HEAD` 当成本轮增量。复审开始时逐项 SHA-256 **全部匹配**。原计划摘要仍为 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`，修订说明见 [REVIEW_REVISION.zh-CN.md](REVIEW_REVISION.zh-CN.md)。

相对 R3，仅以下四文件变化：`command_adapter.py`、`ssh_transport.py`、`test_execution_collection.py`、`test_log_preservation.py`。两项生产变更都收口到已有 `run_bounded`，没有新建另一套进程管理器。独立读取最新隔离 wheel 环境 `/tmp/scid-collection-installed-354zhfy3`，32 个受影响的已安装生产 Python 文件摘要全部匹配 R4 清单。

本次独立动态验证为第 2、3 节的串行小探针，均通过本目录 `check.py` 的 512 MiB / 150 秒 harness；未执行全量、并行或 xdist 测试。真实 OpenSSH 探针使用 `-F /dev/null` 和本地 `ProxyCommand=/usr/bin/sleep 10`，没有网络连接。未操作科研实例、Worker MCP、审批、VM、部署或求解器。其他测试结果来自读取现有源码、日志及安装文件，没有冒称独立重跑。

## 2. R4.1 — P2：原生 SSH 不保留控制锁，当前停止所有权保证仍有缺口

**归属：本轮停止所有权设计的新缺陷；不是原有科学合同问题，也不是任意第三方主动逃逸的假设。真实当前 SSH 可执行程序的正常行为已独立复现。**

位置：

- `src/scidiscovery/artifact_agent/service/execution_collection.py:35`—`run_bounded` 将锁 FD 通过 `pass_fds` 委托给同组传输；`:153`—父死亡监视器最终杀死整个私有组，包括本身持锁的 collector。
- `plugins/tcad_artifact/tcad_artifact/ssh_transport.py:79`、`:209`、`:225`—解析、下载及非下载 RPC 启动真实 SSH 的调用边界；R4 已正确复用共享执行函数，但不能决定 SSH 程序启动后是否关闭 FD。
- `src/scidiscovery/artifact_agent/service/execution_collection.py:379`、`:411`—监督异常后，顶层进程结束即可释放本地所有者，注释依赖后代继承锁继续约束重启；原生 SSH 不满足这一前提。正常监督路径 `:355` 的实际组停止检查仍有价值。
- `tests/operations/test_execution_collection.py:456`—新版父死亡测试覆盖真实 CommandAdapter → SSHRemoteClient 地址解析入口，但最下层仍是 Python 解析器；没有执行原生 SSH。

### 独立复现

先重跑 R3.1 的实际 Python 调用边界，并补充非下载 RPC：两个入口都报告两个 FD 实际可访问，且在私有组。证据为 [check-1789284059249630273.log](check-1789284059249630273.log)，0.46 秒、峰值 70,504,448 字节。这证明 R4 仓库调用者修复有效。

随后在两个真实 `flock` 文件上创建高编号 FD 100、101，启动独立私有进程，调用真实 `watch_parent(owned_fds=...) → SSHRemoteClient._run → run_bounded → /usr/bin/ssh`。SSH 使用本地 sleep 作为代理命令而持续运行，不联网。通过 `/proc/<ssh-pid>/fd` 检查传入 FD 的设备号和 inode，结果：

```json
{
  "lock_fd_numbers": [100, 101],
  "actual_lock_inodes_retained": [false, false],
  "fd_links": {"100": null, "101": null},
  "same_private_group": true,
  "native_ssh_running": true,
  "network_used": false
}
```

证据：[check-1789284412069878001.log](check-1789284412069878001.log)，0.67 秒、峰值 67,547,136 字节，无资源停止，探针已清理整个私有组。初步低编号检查 [check-1789284359393170449.log](check-1789284359393170449.log) 也保留；它只检查 FD 是否存在，可能混入编号复用，**最终结论以高编号及 inode 校验为准**。

### 触发、影响与最小修复方向

触发条件是正常 SSH 传输启动后，父服务/collector 所有者退出，而原生 SSH 或其同组后代尚未被确认实际退出。原生程序在工作期间已经没有两个控制锁，不能替退出的所有者继续持锁。`SIGKILL` 已发送和目标成员已全部停止不是同一事实；现有 `/proc` 停止检查只在监督者存活且成功走到相应路径时有效。

**本探针证明锁保留前提失效，没有声称在普通可立即终止的 SSH 上已经复现晚写、重复收集或再次求解。** 同组信号回收能力仍存在，不能否认这一已完成修复。但计划要求的“停止未确认则保留 stop_pending 与所有权”不能依靠真实传输不会关闭 FD 这一假设。

最小修复应调整现有收集监督者的所有权：由能够存活至实际受管组停止确认的控制所有者持锁；不得把最后的锁保留责任委托给任意可执行程序。停止信号和释放所有权需要分离，异常/父死亡路径也必须遵守该顺序。继续复用现有收集进程与监督机制，尽量避免新服务、通用队列或 Agent 字段；具体内部进程安排应以精确修订及对应验证评估，不在本报告提前指定未经证明的实现。

补充验收至少应包含真实原生 SSH（可继续本地 ProxyCommand、不联网）和会关闭非标准 FD 的普通传输程序，证明停止尚未确认时锁仍不可重获，确认后才可继续收集。不能仅增加 `pass_fds` 或扩大 Python 替身层数。当前受支持的 SSH 程序正常关闭 FD，不应归入“任意第三方自行 setsid/主动脱离控制”而排除。

## 3. 已关闭发现与回归判断

| 项目 | R4 独立核对与判断 |
| --- | --- |
| R3.1 仓库 `_run` 丢失 FD | 已关闭。resolver 与非下载 RPC 均实际经过共享 `run_bounded`，独立探针确认两个 FD 在 Python 下层仍可访问；原生 SSH 问题另列 R4.1 |
| 旧 CommandAdapter collect | 全分支统一共享执行，未有上下文时仍使用旧配置调用预算。未因收口而套入正式 600 秒预算 |
| R2.1 准备阶段重计时 | 已关闭并独立回归。真实 Worker 的 Run 截止点设为约 3.1 秒，reviewed_package 读取延迟 1.2 秒；适配器得到的截止点比真实 Run 截止点早 0.094 秒，工具返回 not_found、Run 仍 running |
| inspection 内部预算 | inspect/accept 入口冻结原 Run 绝对值，准备和 IO 预留后只取 min；本地 helper 遍历/哈希、读取、accept、副本写入仍消费相同预算。R4 未改这些字节，未发现回退 |
| 工程诊断与有限分析 | 未知异常仍交公共 Worker 工具错误边界，原 unsupported/无文件/额度不足保留有限返回；没有新设 Run 强制失败或分析提交门禁。既有两个工具失败后继续合法提交的证据保持有效 |
| native 观测资源行为 | inherit 默认 reserve=0、analysis=120 保持；共享 launcher 不改变原角色权限。未走 launcher 的平台命令仍不能据此获得完整观测证明 |
| helper/VM 范围 | 接受 `remote_runner_py36.py` 中共享本地 helper 的可选 deadline 参数及循环检查。旧默认调用和远端 RPC 字段没有变更，本轮不要求更新 VM |
| 缓存与登记 checkpoint | R4 未改变完整文件缓存、冻结 collected_at 的 Z 格式及幂等登记恢复。工程缓存不更新科学资格，不导致再次提交 solver |

截止点独立回归证据：[check-1789284251265033677.log](check-1789284251265033677.log)，3.20 秒、峰值 112,582,656 字节。初次探针在完成工具调用后误用不存在的 `runs.get` 读取状态而失败，记录于 [check-1789284211927444356.log](check-1789284211927444356.log)；改用已有 `runs.status` 后通过。该失败属于审查探针 API 错误，不归因于生产代码，也没有删除。

## 4. 安装、测试与全局设计边界

已读取 [check-1789283750837161177.log](check-1789283750837161177.log)：39 passed / 2 failed，两个失败来自旧日志测试仍替换 `subprocess.run`，真实代码已不经过该入口。随后用真实错误传输子进程保留完整 stderr/stdout 断言，两个原测试通过，见 [check-1789283873821519500.log](check-1789283873821519500.log)。这不是删断言或以另一批通过掩盖原失败。

最新四 wheel 验证 [check-1789283941686073370.log](check-1789283941686073370.log) 通过，14.73 秒、峰值 367,562,752 字节；已独立比对安装字节。链路为已安装 stdio proxy main → daemon main → 子进程重开 TCAD command adapter → 实际 collect → 登记 → outputs，无预置 checkpoint。夹具是隔离的历史终态数据库，不执行 solver；独立的精确审批 UI 身份负向对照保留。它证明安装路径可运行，不证明原生 SSH 继续持锁或原 Fig.4 已恢复。

全局审查结论延续 R1，并按当前修复更新：

- **职责与科学身份**：未见新增 Operation、Run 四态之外的科学生命周期、科学 Schema、审批身份或科学 Agent 机械填表要求。工具工程错误仍允许分析形成有限/负向封存结论。恢复工程登记不能替代科学独立审查或更新资格。
- **既有 P2 Hardened 合同冲突仍未关闭**：`general_science_components.py:465` 公共 workspace 有 finalizer 而无 file policy；`hardened_files.py:209` 的默认结果写入规则与 `result_materialization.py:12` 的读取需求不兼容。模型可见输出要求与实际写入准入可能冲突。最小修复归属公共 workspace 合同和真实支持组合测试，不能删除独立审查边换取通过。原 blind.csv 夹具的 unsupported reviewer 是另一个既有测试配置问题。该缺口不作为原 Fig.4 local_trusted 科学失败的证据。
- **恢复/资格组合覆盖有限**：本轮恢复、checkpoint 与工具证据路径有针对性检查；没有重新审核每个 Operation 的 revision/current/qualification 组合，不声明全框架已完成。
- **观测与部署覆盖有限**：裸平台 native 命令、全部自定义 query/proxy 超时组合、非本地管理的远端副作用与原 Fig.4 现场恢复/分析尚未验收。真实原生 SSH 的本地锁问题已经从“未验证”升级为本报告 R4.1 的实际发现，不能继续仅列为抽象覆盖空白。

## 5. 部署结论

**R4 不通过当前 local_trusted TCAD 路径部署复审。** 剩余阻断是 R4.1：最后的锁所有者不能依赖真实 OpenSSH 保留 FD。修订必须提供新的精确输入和原生程序的停止/持锁负向对照，再独立评审。R2.1、R3.1 和既有预算/诊断修复已得到相应证据，不因新发现而撤销其有效结论。

后续工程复审即使通过，适用范围也仅是对应 Linux 控制端 local_trusted TCAD 路径，不是 Hardened、全原生平台或所有自定义配置组合全面通过。它更不能证明 Fig.4 曲线已对齐、原研究目标全部覆盖或科研任务完成；这些仍需同次批准执行的实际产物，以及匹配分析 Operation 的 completed 封存输出。
