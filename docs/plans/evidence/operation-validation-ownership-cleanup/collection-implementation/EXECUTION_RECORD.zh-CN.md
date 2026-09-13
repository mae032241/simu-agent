# 执行收集修复实施记录

依据：已通过 R2 工程复审的 EXECUTION_COLLECTION_DIAGNOSTICS_REPAIR_PLAN.zh-CN.md，SHA-256 `db00f49fe6070c5babba0dfffcb55dadeae293001d2b5cf404ed79de8d16f592`。

用户已授权实施。当前阶段：P0—P4 源码修复与源码修复与六轮独立审查完成，当前R6独立复审PASS（限Linux local_trusted TCAD控制端）；26项所属定向回归、最新隔离安装链及3项独立负向对照通过。R1/R2/R3/R4/R5的REVISE保留。后续用户已安装重启；[现场验收](POSTINSTALL_RESULT.zh-CN.md)已完成原执行收集与有限分析封存，总体对齐和机制目标仍未完成。下方各轮“未部署”描述保留其当时证据边界。

基线见 baseline.json，包含345个相关文件的字节副本位置、摘要和当前实际超时配置；保留全部既有改动，不自动提交 Git。原 Fig4 求解不重启。串行 check.py 采用512MiB进程树预算和150秒单批时限；结果写入 checks.jsonl。

## 实际改动及职责

本轮增量见 [incremental-manifest.json](incremental-manifest.json) 与 [incremental.diff](incremental.diff)，以本轮改前快照为基准，不能以包含多轮未提交改动的 Git HEAD diff 替代。初审输入共44文件：36个生产/角色/脚本/文档文件，8个测试文件。其中 tcad_transport_contract.md 只有当前摘要，没有本轮改前字节，明确单列。

- P1：Root、Local/Hardened Worker、Run checker、proxy 和 TCAD 传输复用工程诊断；保留异常链、超时类型/预算、退出码、受限 stdout/stderr。原始详情保存在控制目录；按当前实例/会话读脱敏详情，Worker在自己工作区读副本。诊断记录自身失败不替换原错误。operation_contract 仅补充诊断消息中被拒输入的脱敏，没有新增准入或输出规则。
- P2：execution_sync 只同步日志和状态；execution_collect 显式启动同一 daemon 共享的单槽进程。进程在预算内停止、回收后释放锁；忙时不排队，重复调用不延长预算。控制层保存进度、完整输出清单和稳定登记时间，重启从同一执行恢复。
- P3：command、SSH、socket、作者 debug、分析文件恢复消费共享 CollectionContext 或绝对截止点。正式收集默认600秒、查询5秒、文件120秒、无进展30秒；作者和分析使用自己的剩余授权预算。旧配置可读。完整文件经大小/摘要核对后复用，未完成文件重传。初审后仅为 remote_runner_py36.py 中本地socket复用的目录/哈希helper增加可选本机截止点；远端RPC不传，协议与求解行为不变，无需更新VM，具体范围澄清见 REVIEW_REVISION.zh-CN.md。
- P4：共同 MCP 边界记录工具耗时，复用已有 tool-attempt；允许原生命令的工作区共用一个可选 launcher。分析保留既有512MiB/单线程策略，其他角色继承自己的环境、stdin和正常输出。区分未接入、无记录、损坏和有效观测；裸平台 shell 仍可能未观测，观测不成为提交条件。

收集器依托控制层的 execution_collection 模块和 daemon 生命周期；适配器只实现具体传输。观测入口依托公共 Worker/Run 边界和 local_process_observation。作者 debug 使用自己的受控子进程与 Run 预算，复用同一进程监督和预算实现，既不成为新科研角色，也不占用 Root 的正式收集槽。

## 验证与真实边界

全部命令、时间、RSS和失败保存在 [checks.jsonl](checks.jsonl) 及对应原日志。初审时共27批串行检查，最大进程树RSS269.14MiB，无内存/时间预算终止；未运行全量pytest、xdist或真实求解。多次检查含重叠用例，不把通过数相加当独立覆盖数。

| 范围 | 结果/证据 |
| --- | --- |
| 收集协调器、进程死亡/重启、43文件恢复、登记中断、真实proxy/daemon、socket、作者受控收集、工程诊断 | 最新所属文件23通过，check-1789281444461983267.log；额外覆盖监督线程启动失败后的实际杀进程/释放锁及关闭前日志落盘。 |
| 分析文件恢复及共同观测 | 48通过，check-1789279514031528294.log。 |
| 日志定位及TCAD状态进度 | 17通过；同批另一个新诊断测试曾失败，修正后单项通过，见 check-1789278950938064439.log / check-1789279008805290006.log。 |
| 批准身份、真实socket收集/inspection | 18通过，check-1789280526425904326.log。 |
| 通用工具合同/失败尝试与动态Schema诊断 | 合同尝试23通过；动态工具本地/hardened与拒绝输入脱敏4通过，check-1789280215800126617.log / check-1789280381635020504.log。 |
| 平台与部署脚本 | 同批97通过、2个旧断言失败；修正原生识图能力断言和安装前已有pyc的比较方式，两项单独通过。check-1789280835597390230.log / check-1789280962586934432.log。 |
| 作者原debug行为/预算/响应封存 | 10通过、1个响应界限处理退化，修复保留原TCADDebugError后该项通过；check-1789279595521531416.log / check-1789279759191454303.log。 |
| 隔离安装 | 四个真实wheel、独立venv、不从源码导入；目录/新Root Schema/旧配置、精确UI决定、真实收集子进程和语义输出通过。最新 installed-smoke.json、check-1789281470204729876.log，11.26秒/169.29MiB。 |

失败记录均保留。实现过程中修正了 scratch 目录缺失、SSH流式测试替身、作者错误分类、诊断动作字段、Pydantic错误泄露被拒输入等实际发现；没有通过删生产校验或调大测试预算消除失败。git diff --check 通过。本仓库没有技能中提及的 validate_architecture_constraints.py，未冒称运行；全平台/全量控制基准按资源约束不运行。

## 独立审查与剩余验收

用户要求完成后的独立全面审查，[初审报告](INDEPENDENT_REVIEW_R1.zh-CN.md)已完成，结论REVISE，确认1项P1和5项P2。范围同时包括本轮实现和全局职责/合同/交接/恢复/观测，不把主代理计划复核改称独立审查。本轮范围问题已按[修订记录](REVIEW_REVISION.zh-CN.md)修正，独立复审正在进行；既有Hardened公共workspace问题另列，没有扩张本轮框架范围。

修订精确输入：[incremental-manifest-r2.json](incremental-manifest-r2.json)、[incremental-r2.diff](incremental-r2.diff)，共46文件（增加共享helper和索引更新）；初审44文件的原输入不改写。

修订后证据：

- 真实嵌套command父死亡/作者超时、可选工具错误后合法提交、短Run默认观测入口等37通过，check-1789282183292299150.log。
- 真实socket正常读取与服务端慢哈希实际停止2通过，check-1789282288471519436.log；分析恢复所属文件40通过，check-1789282422521861867.log；本地证据哈希计入同一IO预算1通过，check-1789282593309946733.log。
- 不预置检查点的新安装链首次暴露collected_at格式错误，check-1789282319222811454.log原样保留；修复后四wheel、真实stdio proxy/daemon、适配器重开、实际收集、Z时间登记与幂等outputs通过，check-1789282517491317150.log，14.52秒、354.47MiB。此结果替代初审安装smoke的有限结论，不是把原测试自动当作更强证明。
- 所有检查继续串行，未扩大512MiB上限，未运行求解器或全量pytest；独立探针失败与成功也在同一账本保留。

R2独立复审又确认准备材料读取耗时未扣除，适配器截止点比原Run晚1.226秒；[R2报告](INDEPENDENT_REVIEW_R2.zh-CN.md)保留REVISE。再次修订在两个工具入口固定Run截止点，并补充受管进程组停止确认和控制锁FD向下传播。精确输入为 [incremental-manifest-r3.json](incremental-manifest-r3.json) / [incremental-r3.diff](incremental-r3.diff)，46文件，未改变原科学合同。最新证据：

- 准备延迟与诊断/局部哈希5通过，check-1789283049536392036.log。
- 两级受管传输FD继承、父死亡、重启与收集所属文件23通过，check-1789283274829656234.log。
- 完整分析恢复所属文件43通过，check-1789283382907880161.log，38.56秒。
- 最终四wheel真实安装全链再次通过，check-1789283436473293720.log，14.81秒、350.60MiB；本轮累计峰值仍354.47MiB。安装位置见 installed-smoke.json；仅在/tmp隔离环境，没有修改生产服务。

R3又独立确认实际SSH地址解析和非下载RPC未继承控制锁FD；[原R3报告](INDEPENDENT_REVIEW_R3.zh-CN.md)保持REVISE。修订让这两个分支和旧Command collect统一复用run_bounded，并将原合成下层测试改为真实SSHRemoteClient地址解析入口。最终输入 [incremental-manifest-r4.json](incremental-manifest-r4.json) / [incremental-r4.diff](incremental-r4.diff)，47文件（新增一个日志测试文件，替身改为真实程序）。组合39通过、两个替身失效原失败保留，修正后2通过；check-1789283750837161177.log / check-1789283873821519500.log。最新四wheel真实安装链再次通过，check-1789283941686073370.log，14.73秒。R4独立复核进行中；既有Hardened问题及现场科学验收仍保留。

已交审查者核实的既有候选：hardened blind.csv 旧测试在改前快照同样被 operation_runtime_unavailable 拒绝；临时移除仅测试夹具review后，通用finalizer与hardened result.json路径权限出现冲突。该临时夹具修改已还原；两个原测试未通过，不能以其他hardened动态工具用例通过替代。相关 check-1789279853442855254.log / check-1789280962586934432.log。需区分真实hardened后端兼容问题与测试前置条件，不映射成Fig.4 local_trusted的现场失败。

安装后仍须刷新 fig4_iterative_alignment_execution_postinstall_1 的原终态日志，显式收集同一次执行，经原计划/审查/执行包/参考证据进入封存分析。科学目标仍为掺杂深度、曲线形状、前尾平台。现有成功solver结果尚未通过新代码现场恢复；本轮未改安装目录、服务、VM或科研对象。待安装与实例绑定后继续，不能重新提交原solver。

R4独立复审确认真实OpenSSH会关闭额外FD，原继承锁解释不足，报告保持REVISE。现改为同模块私有guard保留锁直到唯一实际工作组停止；具体范围及原生负向对照见REVIEW_REVISION的R4节。24项所属回归通过（check-1789285233730332650.log）；实际四wheel安装链通过（check-1789285266474714483.log），最新累计峰值393.59MiB，无预算终止。初次两项源码夹具模块路径失败原日志保留。R5输入将以新清单冻结，未部署。

R5的正常原生SSH路径独立通过，但观察异常释放锁和超时错分类仍为REVISE；现已修订完整观察异常边界和单一停止原因回执。26项所属测试通过，错误记录可读且未知停止状态继续持锁。详见REVIEW_REVISION的R5节，旧输入及失败记录保持原样。

最新安装链通过：check-1789285906311869670.log，峰值394.51MiB，仍低于512MiB，未部署。R6精确清单为incremental-manifest-r6.json / incremental-r6.diff。

## 最终独立结论（R6）

[完整R6报告](INDEPENDENT_REVIEW_R6.zh-CN.md)已完成，PASS仅覆盖冻结R6的Linux local_trusted TCAD控制端。47文件摘要、32个已安装生产文件和冻结计划哈希独立匹配；观察故障持锁、迟调度超时分类、原生SSH父死亡三个负向用例独立通过，check-1789286071469277896.log。

- 本轮已发现的进程停止、预算贯通、工程错误详情、观测策略和真实安装链问题已关闭。
- 既有P2：Hardened公共workspace的结果文件写入权限与finalizer消费合同冲突，仍未修复；不是当前local_trusted部署的阻断。
- 未验收：裸平台命令的完整观测、所有自定义预算与backend/插件/资格组合、原Fig.4现场产物恢复和科学闭环。不能把这些范围写成通过或已经发生的故障。
- 全过程串行低资源验证，当前累计峰值394.51MiB，无资源预算终止；未运行全量测试、真实求解或生产部署。

R6通过后仅更新本实施记录与docs/plans/README.md的状态，不再修改生产或测试文件。送审清单与报告不改写，最终交付摘要见final-delivery.json，明确记录这些文档状态更新。下一步安装后收集同一次已成功执行，继续匹配分析；不重算原solver。
