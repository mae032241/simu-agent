# E8 安装后受控续接验证

日期：2026-09-11。结论：失败草稿和既有计算的受控续接已完成；真实研究闭环尚未完成，不能声称所有评分／输出问题已消失。

用户确认安装重启并在 UI 绑定原 `M7-test0` 后，Root 查询当前 public 编译目录、原计划父链、原始目标及既往封存分析，选择 `tcad.result.analyze.v1`。新请求明确使用同一已有执行和参考材料，`draft_from` 指向失败任务 `fig4_continuation_execution_analysis_6`。旧 Run 保持 failed；新 Run、输入合同、预算和成果独立管理。

精确请求、预检和创建结果见 [LIVE_E8_START.json](LIVE_E8_START.json)。当前编译角色以无父会话历史的新 Agent 打开队列任务；Root 没有读取 Worker 草稿或运行 Worker 工具。最终结论仅据控制面 completed 状态和封存结果，见 [LIVE_E8_COMPLETED.json](LIVE_E8_COMPLETED.json)。

## 执行事实

- 新 Run：`fig4_continuation_execution_analysis_7`。
- UTC 创建时间 13:34:31，Worker 打开 13:34:55，13:39:58 完成。
- 预检通过；一次输出上下文拒绝后在同一 Run 修正完成，没有超时或另开重试 Run。
- 正式输出：`fig4_continuation_execution_analysis_7.output`。
- 已封存 4 份 computed 计算记录；它们全部标注 `proof_kind=recovery`、`manifest_alias=tool_recovery_manifest`，对应恢复尝试 002—005。这是旧失败 Run 的计算被正确接续，不是本轮新计算的证明。
- 正式分析还登记了 10 项附属恢复证据及 `fig4_continuation_execution_analysis_7.output.recovery_manifest`。后续消费须按目录绑定相应精确对象，不使用旧 Workspace 路径。
- 本轮控制诊断 `latest_tool_error=null`，输出拒绝次数 1。唯一公开拒绝仍是泛化的 `$.payload` / `output_context` / `tcad.result_analysis.context_binding`，不足以确定具体出错字段；不猜测它就是已删除的映射检查。
- Root 没有启动求解器、测试、构建或第二个并行研究 Agent。512 MiB／448 MiB 是新任务的明确计算预算；本轮没有独立进程树内存采样，不能把源码测试的 242.2 MiB 峰值当作现场测量。

## 封存分析报告了什么

分析者报告：同一材料 primary/tight 曲线的归一化对数差分项通过 0.05 decade 阈值；InAlAs 最大值为 `5.783536437320436e-06 decade`，InGaAs 为 `5.436555024829204e-06 decade`。该判断由四份恢复计算记录及分析者对网格、相同 Cs 和方法适用范围的解释支撑。Root 不将其升级为独立科学审查结论。

整体仍为 `inconclusive`。报告没有提供原计划所需参考行筛选／依赖组权重、加权 WRMSE、J、G、T 和类别稳定性的完整计算记录；没有给出机制结论。原执行仍是 failed/97，报告区分了求解日志中的案例完成和 TDR 声明／收集问题，没有改写执行终态。

## 不能据此得出的结论

这轮证明“旧失败任务中的成果可以恢复、修正并封存”，没有重现旧的连续七次拒绝加超时。源码与安装测试另行证明提交不重算及省略重复映射可通过；本次封存报告仍保留 source_references，所以现场运行本身不能单独证明“省略全部重复结构”的路径。

报告 summary 和 method_changes 仍沿用了“本轮调用”“无 required comparison 被拒绝”等历史叙述。现有计算证明明确标记 recovery，且本轮控制诊断没有评分工具错误；不能把这些叙述当作新版发生了同一评分拒绝，也不能把旧工作量限制当作新一轮实测。科学结论和任务能力判断引用前，须明确区分历史尝试与当前验证。

下一项研究工作应针对尚未完成的观察归约及其实际工具能力选择最小可执行任务；不能凭这一份有限分析宣布原研究目标完成。泛化输出错误诊断仍是已观察到的工程缺口。此次验证结束，未再次原样调用分析者，也未改写已封存对象。
