# 安装后有界诊断验收

日期：2026-09-12。七个生产文件与已审源码逐一匹配；服务已重启，用户通过管理页继续绑定原 M7-test0。安装核对见 [postinstall.json](postinstall.json)。本轮只更新验收记录，没有新增源码修改、部署或求解器运行。

## 受控任务与结果

从当前 public catalog 选择 tcad.result.analyze.v1，经相同请求的 preflight/invoke 创建 fig4_uncertainty_diagnosis_1；max_attempts=1，无 draft_from。新编译角色不继承父聊天，只读取明确绑定的原计划/审查、总体目标、回顾性方法/审查、原执行和已封存分析产品。

绑定输入由上轮 34 份收敛为 25 份，这是依据本轮诊断目标作出的调度选择，并非程序自动筛选。科学子 Agent 返回后，Root 确认 Run 为 completed，再读取 sealed_output 和 scheduler_signal。主成果为 fig4_uncertainty_diagnosis_1.output，另有三个工具证据及恢复清单；未把子 Agent 的完成聊天当作科学结果。

创建于 11:16:29.014228 UTC，打开于 11:16:48.915818 UTC，完成于 11:21:51.825703 UTC。创建至完成 322.811 秒，打开至完成 302.910 秒。原始受控状态与观测见 [live-diagnosis-completed.json](live-diagnosis-completed.json)，调用与预检见 [live-diagnosis-start.json](live-diagnosis-start.json)。

以下科学内容只转述该已封存分析，并非调度者新作科学判定：

- 没有重跑求解器、60 个拟合单元或曲线工具。分析者只对原参考表做行级角点资格复核，48 个结果与原封存账目完全一致：38 个因变换后的 x 不严格递增，10 个因 y-minus 出现非正浓度而失效。
- 原因被定位为逐行边际不确定度与已审查的全局角点构造不能共同保持合法数据：不同大小的 x 不确定度导致点序重合或逆序，S 掩码允许部分 y-minus 不为正的行。不是 QR 拟合失败、插值错误、未算完或常数 D 模型导致的角点故障。
- 原有中央值和掩码敏感性描述仍有支撑：仿真端点更深、过渡更宽、尾段浓度更高；前尾区域仅满足候选区的最小支持条件。数字化范围、兼容性分类及物理平台一致性仍不可确定。
- 原外部执行 failed/97 的 TDR 声明路径错误与上述科学方法问题分开保留；有限后处理不改写执行收据。微观机制仍不可识别。
- 若下一轮确需数字化兼容性，分析者建议只修订并独立审查不确定度传播方法，或补充合格原始 SIMS 不确定度信息；利用已保存中央结果重算受影响的范围。机制区分仍需另外设计有限的、能够改变形状的模型反事实。上述建议不是 Operation 路由指令，本轮未继续调度。

## 错误与可观测性

| 项目 | 本轮证据与定位 |
| --- | --- |
| 提交拒绝/校验失败 | Root rejection_count=0，无 latest_rejection；任务完成封存。 |
| 工具错误/超时 | Root latest_tool_error=null、failure=null；本轮未超时。这只表示控制层所观测范围。 |
| 原生命令错误 | 已封存 payload.method_changes[1] 记录一次读取不存在的可选恢复文件，返回 No such file or directory。Agent 随后使用显式绑定的既往记录完成工作。不能将本轮描述为“完全没有运行错误”。 |
| 文件路径错误根因 | curve_score/analysis_workspace.py 的 materialize 无条件输出 paths.recovery_manifest；同文件 _restore_scratch 在无 provisional_roots 时却正确返回 coverage_path=null。两个入口对可选文件是否存在的表达不一致。本轮无 draft_from，错误与安装版本不匹配或新输入资格无关。 |
| 日志可见性 | Root native_execution.coverage=unobserved。上述命令错误由 Worker 主报告保留，未进入控制层错误摘要；因此端到端自动原生观测仍不完整。 |
| 旧错误 | failed/97、之前绘图库/启动器问题和此前提交拒绝属于历史记录，不能计入本轮失败次数。 |

剩余的路径缺陷未阻断任务，已定位为共享分析工作区的可选路径投影问题。后续最小纠正应复用已生成的恢复可用性，在无恢复时不宣称恢复文件可读；无需增加校验、新状态或要求 Agent 填字段。本轮保持已安装源码不变，避免把未部署改动算作此次现场验证。

## 验收边界

已证明：新 Agent 可仅凭绑定记录完成有科学意义的有界续接、形成有依据的有限结论，并且本轮没有提交拒绝和拟合重算。

未在本轮实际覆盖：失败草稿的可编辑恢复；曲线工具的历史案例映射复用；最终 source_references 的自动补全。本轮无 draft_from，calculation_records 和 source_references 均为空。这些能力仍由之前的隔离安装/stdio 用例证明，不能把本轮的零拒绝归因于案例补全。

Root 未提供本轮首项计算时间、读取返回量或截断统计，不能声称已量化阅读量改善。本轮诊断工作量也小于上轮十个拟合单元，322.811 秒不构成入口改动的因果性能证明。未再运行测试、构建或研究并发任务。
