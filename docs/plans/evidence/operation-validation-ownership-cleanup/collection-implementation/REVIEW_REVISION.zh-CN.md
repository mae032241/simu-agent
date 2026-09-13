# 独立初审后的有界修订

依据：独立 INDEPENDENT_REVIEW_R1.zh-CN.md，初审结论 REVISE 保留。原计划 SHA256 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592` 不改写；本记录解释必要的实现修订与一处文件范围澄清，不扩展科研流程。

| 初审项 | 修订及对应验收 |
| --- | --- |
| R1 嵌套传输逃逸 | 私有 collector/debug 的父死亡监视器标记自身拥有的进程组；共享 run_bounded 在该范围内不另起组。外层回收时清理其组，独立查询仍保留自己的组。真实 command 的父死亡、锁释放与再次收集，以及作者新/旧collect超时均检查嵌套进程不再运行。 |
| R2 读取预算不贯通 | 本地socket将绝对截止点传入共享目录/哈希helper并在循环内检查。分析 inspection/accept 的本地重读、哈希、证据登记与副本写入也在原IO预留和结算区间内检查时间。使用真实socket服务的慢哈希负向对照，证明客户端超时后服务端不继续处理全部文件。 |
| R3 可选工具吞工程异常 | 保留不支持、缺文件、额度不足等明确有限返回；未知工程异常交给现有共同Worker边界记录，不另造工具私有诊断器。该次工具调用返回带引用的工程错误，Run保持running，分析可继续提交有限结论。实际inspect/accept两入口验证超时链、脱敏、工作区报告与后续合法提交。 |
| R4 观测策略误扩散 | analysis默认保留120秒；inherit默认0，不对新角色隐式扣120秒。实际默认CLI在仅剩10秒的Run内可完成短命令，并保留原环境与完整stdout。 |
| R5 Hardened公共工作区冲突 | 既有且不影响当前local_trusted路径，本轮不更改工作区合同。列为下一项有明确边界的兼容修复，不能宣称全后端可用；旧hardened正向测试失败原样保留。 |
| R6 安装链遗漏 | 增加真实四wheel隔离环境中的stdio proxy→daemon→子进程重开TCAD command适配器→实际collect→登记→outputs；不预写outputs.json、不调solver。既有审批UI负向对照保留为独立的有效证据。 |

## 唯一文件范围澄清

remote_runner_py36.py 原先在计划中排除。独立审查确认本地socket直接复用其 `_inspect_directory`，不在helper传递截止点就无法满足P3；另建本地收集实现或额外进程层会重复逻辑。因此仅为这个Python3.6兼容helper增加可选 `deadline_monotonic=None` 和循环检查，execution_control的本地调用传入原绝对值。远端RPC不传新字段，默认行为、协议、求解代码及VM运行方式不变，**本轮无需同步或重装VM runner**。审查者已评估此最小方向可行，修订实现仍需独立复审。

## 安装实测新增发现

不预置检查点的安装测试首次在实际适配器收集成功后、结果登记时失败：新 `_now` 产生 `+00:00`，既有 ExecutionResultManifest 要求 `Z`。这是控制层生成值不符合现有字段格式，初审前预写Z时间的夹具掩盖了它。已统一由控制层生成Z时间，未更改科学Schema或让Agent填写时间。失败保存在 check-1789282319222811454.log，后续真实安装链验证必须通过才可关闭。

## 预算解释与验收边界

作者debug既有360秒账本定义为每次提交预留的solver wall time，不是终态文件IO额度；不得把已用完求解预算解释成禁止取回已完成结果。本轮保留该含义，终态收集使用Run剩余绝对预算并预留停止时间，未新增另一套IO账本或套用正式600秒默认值。分析读取则继续受既有Run/IO双预算约束。

自定义查询预算与自定义proxy预算的所有配置组合、未经过launcher的平台命令、非本地/SSH的外部计算、Hardened通用workspace兼容，以及原Fig.4现场恢复仍未完成验收。此修订没有把它们标为通过，也没有扩大科研角色或门禁。

## R2 独立复审后的修订

[R2 独立复审](INDEPENDENT_REVIEW_R2.zh-CN.md)仍为REVISE，原因是实际Worker准备阶段会将适配器deadline推迟1.226秒，原探针 check-1789282825999790030.log 保留。inspect/accept现在在工具入口一次冻结本轮Run的monotonic截止点；读取材料与预留IO后只裁剪该值，OutputInspectionService直接转发绝对值，不再自行从完整remaining_seconds重计时。准备后额度不足时释放未消费的IO预留，不额外锁死后续读取。两入口准备延迟及原局部哈希/工程错误回归5通过，check-1789283049536392036.log。

同时补足R2指出的停止确认边界：只对控制创建的私有组检查Linux/proc非僵尸成员，仍活跃时保持stop_pending与锁；共享run_bounded把控制锁FD及私有组标记传到command及其受管下层传输，即使daemon退出，仍由活跃传输持锁，不能先释放所有权再开启下一次收集。普通独立query不携带此元数据，作者debug仍归自身Run。真实两级command传输验证两个锁FD仍可访问、同组回收后可续接；所属23项通过，check-1789283274829656234.log。没有新增运行依赖、通用任务队列、科学字段或停止任意日志PID的权限。

该证明针对当前受控本地command/SSH树；任意第三方另起会话、主动关闭控制FD或不受本地管理的远端副作用，不冒充已被同一组回收。若系统不能提供停止证明，就维持所有权，不能据一个顶层返回码宣称全部结束。原solver没有重启或取消。

## R3 独立复审后的调用者收口

[R3独立复审](INDEPENDENT_REVIEW_R3.zh-CN.md)确认准备阶段截止点已修复，但真实SSH地址解析/非下载RPC仍经旧subprocess.run关闭继承FD；原探针 check-1789283614655879252.log 保留。SSHRemoteClient._run现统一复用run_bounded，保持原超时和响应字节额度；CommandAdapter旧collect的直接subprocess.run分支同时收口到该实现，仍使用原调用预算。没有新增第二个进程管理器。

父死亡测试的下层替换为真实 CommandTCADExecutorAdapter→SSHRemoteClient._destination→resolver，验证两个控制锁FD实际可访问，而不是直接拼接两个run_bounded。收集/作者/日志/SSH流式组合39通过、2个日志测试因旧subprocess.run替身未被调用而失败，check-1789283750837161177.log；将这两个替身改为真实错误传输子进程后2项通过，check-1789283873821519500.log，不删除原stderr/stdout完整性断言。修后需要重新核对安装字节与独立复审。

## R4 原生 SSH 所有权修订

[R4报告](INDEPENDENT_REVIEW_R4.zh-CN.md)证实真实OpenSSH正常关闭非标准FD，原FD继承方案不足；上述R2/R3的持锁解释仅代表当时实现，现由本节取代，旧清单与报告不改写。

同一execution_collection模块增加私有guard入口：guard继承并持有两个锁，启动唯一实际收集工作进程组，工作与传输不继承锁。daemon停止、父管道EOF、总预算到期或内部监督错误，均由guard停止工作组并等待非僵尸成员清空后退出。父服务不强杀guard；无法确认工作停止时仍持锁并保留stop_pending。保留原进程组标记，嵌套command/SSH不另开会话；不再向任意原生程序传播锁FD。单槽、一次实际收集、同一绝对预算均不变，没有新服务、Operation、Agent字段、VM协议或运行依赖。多一个短小的本地控制进程是为父daemon退出后仍保留停止所有权，不能由传输实现代替。

所属24项通过（check-1789285233730332650.log），含真实Command→SSH resolver和原生OpenSSH两条父死亡路径。后者只用本地ProxyCommand sleep，不联网；SIGSTOP整个工作组后杀父daemon，在尚未停止的窗口验证锁不可重获，再确认工作结束后才允许新收集。首次两项失败是源码夹具未向新模块子进程传递PYTHONPATH（check-1789285189394733518.log），修复夹具环境传递后原断言通过，没有增加超时或内存预算。

四wheel隔离安装、真实stdio/proxy/daemon及重建适配器的实际收集再次通过，check-1789285266474714483.log，15.39秒，峰值412704768字节（393.59MiB），仍低于512MiB。环境见installed-smoke.json。剩余Hardened公共workspace兼容、未经过launcher的观测与Fig.4现场科学验收仍未关闭。修订等待R5独立复核。

## R5 停止证明失败与超时原因修订

[R5报告](INDEPENDENT_REVIEW_R5.zh-CN.md)保留REVISE，正常OpenSSH/父死亡路径已经独立关闭。新复现为进程观察EIO从guard退出时的finally再次抛出、锁释放时后代仍在运行（check-1789285551362051692.log），以及父监督迟调度后将guard实际超时报为runtime_failure（check-1789285612324952747.log）。

`_group_running`现将完整观察边界的OS/读取错误解释为尚未证明停止；guard仍发送停止信号并持锁，不因观察异常跳过停止循环。原错误仅首次经共同EngineeringDiagnostics保存，在同一执行的停止回执中可读，不把未知停止状态当作科学失败或增加准入。guard独自写一份有界stop.json，记录实际停止原因与观察异常；父监督及只读summary消费它，每次有意新收集清除旧回执，历史status仍归档。这个控制事实避免依赖父线程调度时机，也没有新增生命周期或Agent填报字段。

真实故障注入证明：工作leader退出但后代仍存活时，guard观察EIO仍会发信号，未能确认停止时两个槽锁均不可重获；恢复观察后才退出释放，期间具体EIO可查询。另一用例将父watch延迟1.3秒、收集预算0.8秒，最终明确timed_out/category=timeout/collection_total。所属26项通过，check-1789285875989510430.log；前一轮同26项通过记录check-1789285762250941481.log保留，不累加为52个独立用例。修订等待新的隔离安装及R6精确复审。

R5修后四wheel真实安装链通过（check-1789285906311869670.log，16.01秒，峰值394.51MiB），/tmp/scid-collection-installed-t2s26ljg。R6复审输入现冻结。
