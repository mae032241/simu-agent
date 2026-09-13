# 当前 Agent 框架未闭合问题清单

日期：2026-09-13。范围：本轮安装后的 Fig.4 实验执行、相关生产源码，以及最近的独立工程复审记录。主代理只读整理，未新开独立审查，未运行测试、重新仿真或修改生产源码/部署配置。源码基准 HEAD：be5da77acdbf98054e0b096fc4e940de560d4ba1；工作树包含此前已安装修订，不把 HEAD 当作实际安装版本。

## 当前事实

- 精确实例：M7-test0。
- fig4_iterative_alignment_plan_review_postinstall_1、fig4_iterative_alignment_author_postinstall_1、fig4_iterative_alignment_tcad_review_postinstall_1 均为 completed，封存结果为 pass，三者 rejection_count 均为 0。
- fig4_iterative_alignment_execution_postinstall_1 的当前状态为 succeeded，result_artifact_name 为 null：求解结束，受控产物收集与登记未完成，新一轮科学分析尚未开始。
- 本轮 Root 实际读取过远端运行耗时、stdout 和 solver_log 尾部。不能再把“运行中 TCAD 日志完全未接入”列为当前缺陷。
- 三个已完成 Agent Run 的 native_execution 仍显示 unobserved；它与上述 TCAD 执行日志是不同观测路径。

## 已确认且尚未修复

### B1 / P1：状态及日志同步被整批产物收集阻塞

位置：src/scidiscovery/artifact_agent/execution_bridge.py:176；interfaces/mcp_root_execution_routes.py:510。

sync 在取得终态后同步调用 collect，收集返回后才把 progress 返回 Root。收集异常因而使已经取得的状态及日志也无法由此次同步响应交付。后续同步若本地已是 succeeded/failed/cancelled，还会跳过 status_details；collected 则直接返回，均不再刷新终态日志。

影响：原本应快速、可重复的运行观测，变成等待整个文件下载事务。日志失败和产物失败混在一个接口结果中。

### B2 / P1：查询、收集和传输的超时语义不一致

位置：interfaces/mcp_proxy.py:22；plugins/tcad_artifact/tcad_artifact/command_adapter.py:34、258；ssh_transport.py:42。

实际 command-adapter 配置为整个传输命令 30 秒，SSH 配置为单次操作 120 秒。Root 代理源码默认 10 秒，两次本轮调用约 10 秒返回；当前代理的实际启动参数未独立恢复，不能把默认值冒充已经读到的运行参数。

影响：较外层时限先结束，收集还可能继续到内层时限，调用者无法由泛化错误分辨是查询超时还是传输超时。日志查询与整批产物收集共用同一 command 操作时限，没有独立收集预算与收集进展表达。

证据：POSTINSTALL_FIG4_COLLECTION_INCIDENT.json；POSTINSTALL_FIG4_COLLECTION_TIMEOUT_PROBE.json。空 stderr/stdout 日志与已安装 TimeoutExpired 分支一致，安装代码的受控合成探针重现了原因及其丢失过程。

### B3 / P1：已下载文件不能被收集重试复用

位置：plugins/tcad_artifact/tcad_artifact/ssh_transport.py:391。

_collect 对每个远端描述符先执行 remote.get，再检查本地不可变文件；没有在下载前验证并跳过已完整下载的同一文件。一次收集仍必须在单次调用内遍历整个列表后才返回描述符。

影响：中断后虽保留部分文件，重试仍从第一项开始下载，浪费时间，可能反复触发同一时限。这是实现中可直接确认的续接缺陷；本轮没有以重复完整下载测试其耗尽行为，也没有重复求解。

### B4 / P1：工程异常丢失根因，“查看日志”可能只指向空文件

位置：interfaces/mcp.py:75；interfaces/mcp_proxy.py:37；plugins/tcad_artifact/tcad_artifact/command_adapter.py:261。

非 DiagnosticError 被统一转换为 runtime_failure，不保留具体类型、原始消息、异常链或可查询的关联错误记录。代理自己的异常也使用同一转换。传输超时分支保存的只是子进程 stdout/stderr，二者可能均为空；有价值的 TimeoutExpired 及其 timeout 没有落入这些日志。

影响：超时、尚未 collected、传输故障都可能显示相同错误。本轮 execution_outputs 在尚未 collected 时拒绝是合理状态边界，但其诊断再次失真。该时段服务 journal 查询未返回相应异常记录，因此不能声称“完整根因已自动记录，只是 Agent 没去读”。

### B5 / P2：观测覆盖与缺失原因表达不完整

位置：interfaces/mcp_root_run_routes.py:37；service/local_process_observation.py:108；plugins/curve_score/curve_score/analysis_workspace.py:146；interfaces/mcp_root_execution_routes.py:441。

Root 对 local_trusted Run 统一读取分析 launcher 的 scratch/.analysis-process/latest.json，而 launcher 由分析工作区路径可选生成，未覆盖所有角色/平台原生调用。文件缺失、格式错误和读取错误统一显示 unobserved。当前 execution_status 也只有求解状态和结果引用，不能说明收集完成多少、哪项失败、当前受哪个预算约束。

影响：用户与调度方难以区分未接入、未运行、读取失败，以及计算完成但收集未完成。不能从 native_coverage=unobserved 推断 Agent 未工作，也不能据此新增提交门禁。

## 已修复或已有本轮正例，不再重复登记为当前故障

- 本轮计划审查、作者交付、独立代码审查均首次成功提交；此前实验审查的六次拒绝没有在本轮重现。
- 同版本历史记录可读与精确绑定消费：本轮使用历史目标、计划和进展的 preflight/invoke 与交付已有成功路径；不能据此宣称所有历史兼容组合全部验证。
- TCAD 运行中日志与实际耗时传递：已在真实 VM execution_sync 验证。作者调试日志能力有已安装代码及此前工程证据；不能把 Root 观测当作作者逐项读日志的证明。
- _fps.tdr 文件名声明：新项目已修正，精确独立代码审查通过。此次完整文件收集尚未完成，文件级最终验收仍待完成。
- calculation inline/saved 收据归一、gap 字段错误定位及 runtime-failure 日志媒体类型：最近源码复审通过并有定向验证；新一轮结果分析和真实失败作者交接尚未运行到，保留实测验收项。

## 未完成的验收及优化，不冒充已复现新 Bug

1. 当前完整闭环尚未完成：结果收集、曲线分析、支持明确科学结论仍待继续。
2. 续接上下文是否足够精简：已有精简入口及恢复机制，但本轮尚无新分析续接的耗时对照，不能宣称解决了此前大量读取开销，也不能仅凭计划较长就断言其内容无用。
3. 审批页面可用性：用户此前明确留待后续处理；本轮审批记录正常生效，未重新复核所有界面问题。
4. 分析角色识图、曲线工具与已修订引用路径的新部署组合仍需本次结果分析实际验收；存在权限/声明不等于已成功使用。

## 调度侧自身问题

首次工具出错时，主代理脚本直接对非 JSON 错误文本 JSON.parse，又产生一层 SyntaxError；后续已改成先检查 structuredContent、保留原始文本。此前还出现将大型目录/完整对象直接打印进入上下文的问题，应只投影当前需要字段。这些是主代理调度脚本问题，不是科学 Worker 输出不合格，不能归罪于科研 Agent 或新增科学校验。

## 当前修复原则

日志查询、产物收集、求解执行分别定义预算与错误语义；查询失败不取消收集/求解，收集失败不重算；收集复用有效已下载文件；错误具体、可追溯，观测由控制层/适配器自动记录，缺失观测不成为科学输出门禁。

此前将 command 超时临时调成 300 秒的提议，已由后续用户讨论明确降为非根本修复，并暂停执行；对应原事故记录仅保留当时建议，不再作为当前修复方案。此次没有部署该配置修改。

