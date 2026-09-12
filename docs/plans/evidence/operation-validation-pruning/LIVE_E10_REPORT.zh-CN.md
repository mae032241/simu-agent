本轮六案例科学闭环记录（2026-09-11 UTC）

本记录汇总控制层确认 completed 的封存分析、计划修订和独立审查，不新增科学判断。本轮六案例的证据恢复、定量分析、独立复算、完成状态修订和独立复审已经完成；总体机制分离研究仍未完成，研究实例继续保留。

最终独立审查：`fig4_continuation_experiment_closure_review_1.output`，verdict = pass；本次审查没有输出拒绝。通过评价的是收尾修订的科学一致性，不构成新实验执行授权或后续科学基础的资格。

封存结论：

- 同一原执行所需的 13 个产物（全局日志、六条 PLX、六个 TDR）已经受控恢复并核对来源。原文件的实际名称含 `_fps.tdr` 后缀；恢复通过检查和接纳映射补齐证据，没有改写原文件或执行历史。
- 原执行仍为 `failed / 97`，原因是声明输出路径与实际 TDR 文件名不一致导致收集失败。该历史终态与当前恢复后的完整证据集合分别保留，不能把本轮闭环表述为原执行成功。
- 当前数据的数值收敛通过。独立分析复算了关键指标，并留下两条受控收敛计算记录；本次收尾没有重新运行求解器。
- Al、Ga 的 own-anchor 加权 WRMSE 分别约为 2.2445、2.0128 decade，均超过预注册 0.15 decade 门限。因此冻结的常数 D / 固定边界模型家族不足以拟合参考剖面。
- 边界增益 G 约为 -0.01409，只能作描述；基础模型充分性未通过，不能据此排除表面边界假设。尾部 T 的类别随预注册掩码变化，也不能获得稳定的支持或排除结论。
- 两个当前目标均完成其注册比较，科学处分均为 inconclusive。当前目标完成不等于机制问题得到解答。

闭环所用正式记录：

- 完整恢复分析：`fig4_continuation_execution_analysis_recovery_complete_1.output`。
- 先前独立复算：`fig4_continuation_execution_analysis_independent_2.output`。
- 完成审查：`fig4_continuation_experiment_completion_review_2.output`，要求 revise。
- 收尾修订：`fig4_continuation_experiment_closure_revision_1.output`，保持六案例设置、身份、原预测、阈值和验证检查，仅更新完成状态、优先级、价值与历史工作说明，并增加明确的阶段停止条件。
- 最终独立复审：`fig4_continuation_experiment_closure_review_1.output`，pass，确认修订充分且最小。完整控制响应见 [LIVE_E10_CLOSURE_REVIEW_COMPLETED.json](LIVE_E10_CLOSURE_REVIEW_COMPLETED.json)。

当前六案例阶段关闭，不再为消除旧 failed 记录或补齐已恢复的证据原样重跑。合同要求非空的 proposal、current_objectives 和 priority_order，因此修订以既有字段明确保存关闭的历史工作；这不是新的执行请求。独立复审接受这一表达，但它不代表系统已经新增正式的阶段关闭状态。

尚未完成的研究条件由封存审查保留：总体 mechanism_separation 需要另行资格化一个有限、可改变剖面形状的结构模型，并在模型明确后核对后端实现可行性与匹配审查。更强尾部结论需要系列身份明确、检测状态一致且有独立不确定度的合格作者原始 SIMS 数据。当前材料不支持直接指定新模型参数或归因于特定微观机制。未来若另有必要创建执行记录，应先修正六个 TDR 的声明路径并完成匹配实现审查；这项维护不是当前科学证据缺口。

本轮也保留了尚未解决的工程问题：

- 新设计尝试在 preflight 被 `input_independent_review_missing` 拒绝；尝试补充对应审查又因基础记录 `input_producer_contract_changed` 被拒绝。没有绕过准入，也没有启动这两个 Run。本轮通过既有计划的独立审查及其精确修订入口完成收尾，尚未证明新模型设计入口的历史资格兼容已恢复。
- 首个完成审查连续发生 10 次 `experiment.review.verdict_consistency` 拒绝，公开诊断只定位到 `$.payload`。已停止该 Run 并如实记录失败，保留交付记录但没有可用 draft；新 Run 在明确既有结构约束后完成。没有证据把旧拒绝进一步归因到某个具体字段，通用诊断不足仍需单独处理。
- 当前计划 Schema 缺少直接表达“无待执行案例”的方式；本轮使用既有字段记录收尾，未修改框架。

资源与修改范围：科学 Agent 串行运行，未启动新的求解器、曲线批量重算、全量测试或依赖安装；本轮没有生产源码改动，仅新增受控过程证据及本报告。512 MiB 上限、448 MiB 提前停止要求已传入任务，但本报告不声称获得了所有 Agent 进程的完整峰值监测。后续研究必须以这些封存记录为进展依据，不应重新解释为产物仍缺失或本轮尚未完成。

