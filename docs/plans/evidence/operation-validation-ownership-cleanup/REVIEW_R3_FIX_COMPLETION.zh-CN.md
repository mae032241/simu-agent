# R3 复审问题修复与 TCAD 日志交接

2026-09-13。**源码修订完成，最终独立复审通过。未部署，未连接生产 VM，未运行 Sentaurus。**

本记录承接 [第三次独立审查](INDEPENDENT_REVIEW_R3.zh-CN.md) 和 [TCAD 日志核查](TCAD_LOG_VISIBILITY_AUDIT.zh-CN.md)。前两份报告保留当时事实；本记录描述其后修复，不能替代安装后的真实研究验收。

## 最小修订范围

精确改前快照见 [基线清单](REVIEW_R3_FIX_BASELINE.json)，最终17个生产文件（含角色说明）、3个测试文件见 [验证清单](REVIEW_R3_FIX_VERIFICATION.json) 和 [逐文件增量](review_r3_fix.diff)。相对 Git HEAD 的累计修改包含前轮工作，不作为本轮范围。

- 同一受控计算的 inline 和 saved 表示，按实际 manifest 作用域、唯一 Artifact 身份和完整记录归一。继续消费原有收据验证；不同 Run 或不同收据不会因同名、同字节而合并。当前、历史和恢复的合法双表示均可提交。没有让工作区 finalizer 读取额外科学文件；该文件最终与本轮基线一致。
- gap 分支分别定位 gap.json 和 handoff.json 错误，空 handoff.summary 明确指向 `$.deck.handoff.summary`。修正该文件即可在同一 Run 继续提交。
- runtime-failure 作者的 solver_log 接受既有 text/plain 和服务器实际导出的 text/plain; charset=utf-8。没有全局放宽媒体类型匹配。
- 沿现有状态查询补齐日志和时间传递：本机控制服务、独立 Python 3.6 runner、SSH 投影、命令/本机适配器、debug bridge、作者工具和 Root execution_sync。保留原 status 字符串接口，以可选 status_details 承载进度。

跨越17文件主要来自同一状态响应原来在多层被缩减；没有新建角色、Operation、状态机、审批、预算或执行准入要求。工具说明、组件配置身份和作者角色说明同步更新。

## TCAD 执行者现在能读到什么

正式 tcad.study.execute 是执行适配器承接的 effect。作者负责源码和受限开发调试；调度方监控正式执行，失败后可将精确日志绑定给运行失败修订作者。

| 时机与使用者 | 已实现能力 |
| --- | --- |
| 作者调试运行中 | 同名同模式轮询返回 progress：观测时刻、已知开始时间、实际 job wall elapsed、受限脱敏日志尾部及其更新时间。重复轮询不重提任务或重复预留预算。 |
| 作者调试结束 | 保留 manifest 中已知起止时间和可计算的 elapsed；通过 log_relative_path 读取有采集上限的完整脱敏诊断日志。日志和诊断仍沿原工作区保存机制进入后续记录。 |
| 正式执行运行中 | 显式 execution_sync 返回同一 job 的 progress。execution_status 仍是纯查询，不暗中访问服务器，不把瞬时日志变为执行资格或新持久状态。 |
| 正式失败后修订 | 实际服务器日志媒体类型可通过端口准入；新 runtime-failure 作者可从其绑定工作区读取日志。 |

实时扫描最多64个顶层目录项，读取 stdout 和最新 solver log 各不超过2048字节；不递归，不读取 symlink/FIFO，不给 Agent 任意 server 路径。沿用终态日志脱敏规则；截断日志丢弃不完整首行，避免遗漏其脱敏上下文。实时片段可能不包含当前关键步骤，仍需结束后的完整受限诊断。

elapsed 是 runner job 的墙钟时间，不是求解器 CPU 时间、物理初始化成功证明或预计剩余时间。缺少开始时间时保留已知结束时间，不编造 elapsed。旧 runner/适配器不提供 progress 时仍可执行；要获得新增实时观测，部署端和 VM runner 都需同步。

## 工程验证与审查中修正

所有检查由主代理串行执行，使用512 MiB地址空间和进程树 RSS 上限、单线程数值库及150秒外层时间限制；没有全量或并发测试。

| 分组 | 结果与记录 |
| --- | --- |
| 保存计算、原有日志保存、TCAD 作者回归 | 121 passed；[日志](check-1789267255816735454.log) |
| 最终保存计算/收据作用域及日志交接 | 26 passed；[日志](check-1789267992598962851.log) |
| 最终 TCAD 分析、来源解释、通用分析、架构登记及 gap 审查 | 84 passed，1项 stress 排除；[日志](check-1789268051058413290.log) |

分组有重叠，不累加测试数。最大进程树 RSS 为240304128 bytes，约229.2 MiB，未发生资源终止。远端脚本通过 Python 3.6 AST 语法检查，但没有实际运行 Python 3.6 解释器。

保留的失败及原因：

1. 日志交接测试首次忘记为合成 runtime 作者注入其必需的 debug service，工作区打开失败。修正测试装配后通过；[原日志](check-1789267428087966062.log) 不作为生产缺陷。
2. 独立审查指出初版归一只比较完整记录 digest，仍可能把不同 Run 内重置的 attempt_001 混合。MCP 正反对照确认不同 Artifact 身份却相同字节时误接受；[原日志](check-1789267805835665904.log)。已改为限定原有控制 manifest 的登记作用域和唯一 Artifact 身份，并补当前、历史、恢复正例和跨 Run 负例。
3. 独立审查发现缺 start 的终态记录会连已知 end 一起丢失。现独立保留合法时间字段；无足够时间证据时不生成 elapsed。

最终 [独立复审](INDEPENDENT_REVIEW_R3_FIX.zh-CN.md) 无未闭合 P1/P2/P3，审查者独立核对20/20文件摘要匹配。

日志路径测试使用隔离 runner 目录和传输夹具；失败交接使用真实封存的 fixture 项目、服务器收集器实际导出的 charset 日志和合成失败 attestation。它证明完整端口准入及新作者工作区可读，不证明真实 Sentaurus 运行、耗时预测准确性或 Fig.4 科学结论。先前审查记录中的其他历史基线失败未被本轮重写或宣称修复。
