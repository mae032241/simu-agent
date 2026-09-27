# 执行收集修订版独立工程复审 R6

日期：2026-09-13。结论：**PASS（范围限定）：冻结的 R6 可部署到当前 Linux 控制端 local_trusted TCAD 路径。**

本轮已发现的进程停止所有权、准备阶段预算、具体工程诊断、资源预留和真实安装链缺口，在当前范围内均已关闭。R5.1 的观察失败提前解锁及 R5.2 的父监督迟调度分类问题，已通过代码核对和独立负向对照确认修复。本次没有发现新的范围内 P1/P2 部署阻断。

这不是全框架、所有 backend/配置或科研能力全面通过。既有 Hardened 公共工作区合同冲突、未观测的裸平台命令、未验收配置组合以及原 Fig.4 现场科学闭环仍未关闭。各项适用范围和优先级见第 6 节。

[R1](INDEPENDENT_REVIEW_R1.zh-CN.md)、[R2](INDEPENDENT_REVIEW_R2.zh-CN.md)、[R3](INDEPENDENT_REVIEW_R3.zh-CN.md)、[R4](INDEPENDENT_REVIEW_R4.zh-CN.md)、[R5](INDEPENDENT_REVIEW_R5.zh-CN.md) 继续保留各自冻结输入上的 **REVISE**，其失败日志没有删除或改写。当前 PASS 只属于 R6 精确输入。

## 1. 精确输入、安装字节与独立性

受审输入为 [incremental-manifest-r6.json](incremental-manifest-r6.json) / [incremental-r6.diff](incremental-r6.diff)，共 **47 文件**。改前工作树仍由 [baseline.json](baseline.json) 指向 `/tmp/scid-collection-baseline-1789276126341295526`；HEAD `be5da77` 不被当作本轮改前基线。逐项读取当前文件的 SHA-256，**47 项全部匹配**。原冻结计划摘要保持：

`db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`

相对 R5 仅 `src/scidiscovery/artifact_agent/service/execution_collection.py` 与 `tests/operations/test_execution_collection.py` 变化。必要修订、共享 helper 范围澄清及历史方案被取代的关系，已在 [REVIEW_REVISION.zh-CN.md](REVIEW_REVISION.zh-CN.md) 中明确。

独立读取 [installed-smoke.json](installed-smoke.json) 指向的隔离安装环境 `/tmp/scid-collection-installed-t2s26ljg`，**32 个受影响的已安装生产 Python 文件摘要全部匹配 R6 清单**。没有仅凭 wheel 文件名或源码测试推定安装字节相同。

审查者没有参与生产代码或测试修复。本轮仅写本报告，并使用本目录 `check.py` 进行第 3 节的一批串行独立验证；上限为 512 MiB / 150 秒，没有全量、并行或 xdist 测试。未重跑未变化且已验证的完整 43 项分析恢复文件。未操作科研实例、Worker MCP、审批、VM、部署、网络或求解器。

## 2. R5.1 / R5.2 的精确关闭判断

### R5.1：观察不可用时停止所有者提前退出 — 已关闭

位置：`execution_collection.py:161` 的 `_group_running`；`:515`、`:534` 的 guard 正常及清理循环。

当前实现对组存在检查、`/proc` 可用性、整个目录枚举以及单个进程状态读取的 OS 观察错误，统一返回“仍存在或尚未证明不存在”。仅明确的组不存在或完整观察确认无非僵尸成员，才能作为退出证明。错误不再从 finally 的循环条件逃出；停止信号发送错误也不会使 guard 提前退出。guard 继续存活并持有原两把锁。

首次观察错误通过共同 `EngineeringDiagnostics` 保存，控制回执 `stop.json` 记录其引用与具体事实；只读 `summary` 可查看 `stop_observation_error`。诊断写入或回调失败不会转化为“工作已停止”。没有新科学状态、准入门或 Agent 填报要求。

独立对照使用真实 guard：实际工作 leader 退出而后代仍活跃时注入 `/proc` EIO。guard 仍发出停止信号；在无法确认最终停止的窗口，原执行锁不能重获，另一执行也因全局槽 busy 被拒绝；具体 EIO 可读。恢复观察后才退出并释放。该对照覆盖了 R5 原探针的触发条件与影响，详见第 3 节。

### R5.2：guard 自行到期被父监督记为一般失败 — 已关闭

位置：`execution_collection.py:492` 的停止回执写入，`:523` 的真实停止原因，以及 `:390` 的父监督消费。

实际决定因预算停止的 guard 写入 `reason=collection_total`，父监督在最终分类前读取该事实。因此父线程迟获得调度，不再依靠本地 `signalled` 猜测停止原因。相应最终状态为 timed_out，公共诊断包含 timeout 与 collection_total。已有具体收集错误仍保留，停止原因另有明确字段，不以新摘要抹掉先前失败原因。

独立重跑原 0.8 秒收集预算、父 `_watch` 初次调度延迟 1.3 秒的对照，正确记录 timed_out / timeout / collection_total。没有延长实际预算，也没有改变科学 Run 状态或分析提交规则。

## 3. 本次独立动态证据

通过 [check-1789286071469277896.log](check-1789286071469277896.log) 独立串行执行三项，**3 passed**，4.57 秒、峰值 172,056,576 字节，无资源停止：

1. `test_collection_guard_keeps_locks_when_stop_observation_fails`：真实 guard、观察 EIO、停止信号、两把锁、可读诊断及观察恢复后释放。
2. `test_collection_timeout_reason_survives_delayed_parent_watcher`：guard 实际超时原因不依赖父监督调度。
3. `test_parent_death_stops_collector_before_restart_releases_lock[True]`：真实原生 OpenSSH、本地 sleep ProxyCommand、暂停整个实际工作组、杀父进程；未停止时持锁，确认停止后才能再次 collect。

第三项不联网，没有接触 VM。该证据继续确认 R4.1 的正常原生 SSH / 父死亡修复没有因 R6 回执和异常处理而回退。它没有被描述为真实远端 SSH/求解器现场验收。

本批之外，读取已有 R6 所属 [check-1789285875989510430.log](check-1789285875989510430.log)：26 passed。前一轮同 26 项通过记录未累计为额外 26 个独立用例。审查没有将所属测试绿色替代实现和实际调用者检查。

## 4. 当前修改目标及跨边界实现核对

| 本轮目标/边界 | 实现及证据判断 |
| --- | --- |
| 日志同步与正式产物收集分离 | terminal sync 不调用 collect；只读状态/进度在收集期间可用。正式收集是显式有界控制动作，不新建科研 Run，不重新提交 solver |
| 共享单槽与停止所有权 | ExecutionCollection 仍有一个全局槽、一份实际收集；guard 独占继承锁，实际工作在独立组中。正常结束、父 EOF/TERM、预算到期及观察故障均以实际组停止确认约束解锁 |
| 真实 command/SSH 调用者 | 旧/新 CommandAdapter 和 SSH resolver、非下载 RPC、下载均经过现有共享执行逻辑；嵌套受管命令不另起会话。锁不再委托给会关闭额外 FD 的原生程序 |
| 作者旧 collect / debug | 保持自身 Run 预算与私有停止边界，不给作者加正式收集全局锁。旧 collect 保留原配置调用预算；360 秒账本仍是 solver wall time 预留，不是禁止终态读取的新 IO 门禁 |
| 同一绝对截止点 | formal collection、guard、实际 collector 沿用创建时冻结的上下文；分析 inspect/accept 在入口冻结 Run 截止点，准备、查询、读取、哈希、登记和本地副本只消费/裁剪原值。R2.1 的独立延迟读取证据保持有效，R6 未改这些字节 |
| 完整缓存与 checkpoint 恢复 | 完整文件缓存、执行范围绑定、冻结 collected_at 的 Z 格式及幂等登记保持；没有把恢复下载等同于重新求解或科学资格更新 |
| 具体工程诊断 | 共同错误链保留超时类型、errno、日志与可读引用，支持范围受限读取和存储失败事实。未知工程异常进入共同 Worker 工具错误边界，明确 unsupported/无文件/额度不足仍允许有限返回 |
| 有限科学分析 | 工具错误不新增 Run 强制失败或科学门禁；原 inspect/accept 失败后仍能合法提交有限分析的证据保持。工程原因不会成为模型参数、曲线结论或科学机制的替代证据 |
| 可选 native 观测 | 共享 launcher 沿用原权限和环境，inherit 默认 reserve=0、analysis=120 的修复保持。没有把无遥测当成无计算错误，也没有把未观测的平台命令描述为已覆盖 |
| socket / VM 兼容 | 共享 Python 3.6 helper 仅增加本地可选 deadline 及循环消费；旧默认调用和远端 RPC 字段未变。该必要范围澄清可接受，本轮不要求更新 VM runner |
| 安装与实际适配器恢复 | 最新 wheel 链真实启动 stdio/proxy/daemon/guard/collector，重开 command adapter 后 collect、登记并读取幂等 outputs；没有预置 outputs checkpoint 跳过关键路径 |

### guard 与停止回执的最小性

guard 是同模块内不执行 adapter 的私有控制进程，不是新服务、后台队列或科学 Operation。它与可能被强杀的工作组分离，解决了真实 OpenSSH 正常关闭 FD 后无法承担所有权的问题。追加的进程启动消耗原 collection 预算；没有为每个文件/SSH 调用增加另一层管理器。

`stop.json` 由 guard 单写，父监督与只读 summary 消费。新尝试在取得原执行锁和全局槽后，先归档包含旧停止事实的 summary，再清除旧回执；不会继承上次超时原因。此回执记录控制事实，不引入独立生命周期、科学状态或 Agent 手工交接表。损坏或读取失败经现有工程诊断呈现，不能悄悄当作已停止。

当前保护对象是控制创建的本地工作组。正常 native 程序关闭额外 FD 已被设计覆盖；任意第三方自行脱离会话、强杀整个控制所有者、内核/主机故障或不受本地管理的远端副作用，没有被本次测试扩大为已证明可恢复。

## 5. 安装证据与历史发现关闭记录

最新四 wheel 安装验证为 [check-1789285906311869670.log](check-1789285906311869670.log)，通过，16.01 秒、峰值 413,675,520 字节（394.51 MiB），低于 512 MiB。32 个受影响安装文件已独立比对。

该安装路径使用隔离历史终态数据库；实际链为 stdio proxy main → daemon main → guard → collector 重开 TCAD command adapter → 无预置 checkpoint 的 collect → 登记 → outputs。原精确审批 UI 身份负向对照保留为独立证据。它证明安装行为，不证明 Fig.4 现场数据已经收回，也没有运行 solver。

| 历史发现 | R6 状态 |
| --- | --- |
| R1 进程组逃逸、未实际停止即释放所有权 | 已由共享受管组和独立 guard 关闭；真实 command/native SSH 与观察失败对照共同支持 |
| R1 socket/helper 内部预算、分析本地读取预算及 R2.1 准备阶段重计时 | 已关闭；原慢哈希、真实 Worker 准备延迟及 IO 结算证据保持，未改字节不重复测试 |
| R1 可选工具吞工程异常、native reserve 策略误扩散 | 已关闭；共同诊断、有限提交以及 inherit/analysis 不同默认行为保持 |
| R1 安装测试预置 checkpoint 掩盖实际重建和登记 | 已关闭；新增真实安装链还暴露并修复了 collected_at 格式问题，原失败保留 |
| R3.1 SSH 仓库调用者丢失 FD | 调用者已收口；R6 不再把传递锁 FD 当作原生程序持锁保证 |
| R4.1 原生 OpenSSH 正常关闭 FD | 已关闭：控制 guard 持锁至工作组停止；原生 SSH 无须保留锁 |
| R5.1 观察异常提前退出；R5.2 父监督迟调度误分类 | 已关闭，见第 2、3 节 |
| R1 既有 Hardened 公共 workspace/finalizer 冲突 | 未关闭，明确不纳入本次 local_trusted PASS，见第 6 节 |

## 6. 全局设计残余问题与优先级

### P2，既有实际兼容问题：Hardened 模型输出合同与文件准入冲突

位置：`src/scidiscovery/general_science_components.py:465`、`src/scidiscovery/artifact_agent/service/hardened_files.py:209`、`src/scidiscovery/artifact_agent/service/result_materialization.py:12`，支持性判断在 `hardened_workspace.py:60`。

公共 workspace 声明 finalizer 而没有 file policy；Hardened 默认 `output/result.json` 写入规则与 finalizer 必须读取该文件的要求不兼容。在受支持 Operation 组合中，模型可见合同要求的唯一结果文件可能无法写入。该问题的归属和源码与改前基线一致性已在 R1 独立核实，R6 未改相关文件。

最小后续修复应归属公共 workspace 合同和真实受支持组合测试。不得通过删除 review 边、放宽科学资格或让 Agent 反复修改科学 payload 来绕过。原 blind.csv 夹具先因 unsupported reviewer 预检拒绝，是另一个既有测试配置漂移；两者不能混作同一失败。此 P2 阻止宣称 Hardened 全面兼容，**不阻止本次精确 Linux local_trusted TCAD 部署，也不证明原 Fig.4 现场科学失败**。

### 未验证的组合与观测范围，不登记为已发生的故障

| 范围 | 当前实际限制 | 后续最小行动 |
| --- | --- | --- |
| 自定义 query/proxy/collection 预算组合 | 旧配置默认值及当前定向路径有验证；所有自定义值组合未穷举 | 根据实际部署配置增加有界对照，不能从默认值通过推导全配置通过 |
| 裸平台 native 命令及其他平台 | 仅共享 launcher 与受管传输有相应观测；没有完整覆盖所有平台原生调用 | 保留明确的未观测状态，按实际入口补证；不增加机械科学证明字段 |
| 全 backend/plugin/revision/current/qualification 组合 | 本轮只针对修改调用者和恢复路径检查，没有全组合审查 | 按新增或变更的真实组合验证，保持精确不可变身份、独立审查和资格边界 |
| 任意外部副作用 | 本地组信号不能证明任意脱离会话或远端副作用已终止 | 由相应 adapter 的明确合同负责，不能从本地 PID 推导远端科学状态 |
| Fig.4 现场恢复与科学闭环 | 本次没有读取现场产物、运行分析 Operation 或验证曲线/目标覆盖 | 后续按同次批准执行取回实际产物，并由匹配分析 Operation 形成 completed 封存输出 |

全局职责边界在本轮差异中保持：控制层拥有执行身份、预算、工程停止和结果登记；科学 Worker 拥有科学内容。未发现本轮新增预检与输出冲突、科学资格绕过或机械 Agent 交接字段。这个结论限于本轮差异和已注明的全局抽查，不是每个 Operation 的全量正确性证明。

## 7. 部署结论及无法据此证明的能力

**批准工程审查结论：R6 PASS，可部署冻结清单对应的 Linux local_trusted TCAD 控制端版本。** 当前范围内已报告的必须修复项已关闭，停止所有权与具体诊断有独立负向证据，安装字节和实际安装链匹配。本报告不执行部署，也不替代后续对实际部署字节及服务启动的核对。

该 PASS 不覆盖既有 Hardened 缺口、未验证配置组合或所有平台 native 能力。它也不能证明 Fig.4 曲线已经对齐、原研究目标完整覆盖、机制唯一确定或科研任务完成。科学结论的实际范围仍由同次执行产物与匹配分析 Operation 的 completed 封存结果决定。
