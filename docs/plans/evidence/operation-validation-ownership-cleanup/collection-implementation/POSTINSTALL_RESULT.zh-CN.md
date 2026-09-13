# 安装后 Fig.4 现场验收记录

日期：2026-09-13。实例 M7-test0。此记录仅整理 Root 控制响应及 completed Run 的封存结论，不产生新的科学判定。原始响应和精确绑定保存在 [POSTINSTALL_LIVE_20260913.json](POSTINSTALL_LIVE_20260913.json)。

## 当前结果

安装后的32个受影响生产Python文件与R6审查字节全部匹配。原执行 fig4_iterative_alignment_execution_postinstall_1 未重新提交求解；execution_sync取得成功终态及原日志，execution_collect于08:09:11.774 UTC接受，08:09:18.016完成。43文件、18,963,737字节全部登记，结果语义名为 fig4_iterative_alignment_execution_postinstall_1.result。本次现场收集没有超时或拒绝。

分析 Run fig4_iterative_alignment_analysis_postinstall_1 超过15分钟预算未完成提交，随后按Root显式失败入口登记run_timeout并保全95文件、971,807字节。原目录保留，recovery_pending=true；已有可交付子集不等于可以删除旧目录。

同一compiled Agent通过新Run fig4_iterative_alignment_analysis_delivery_1续接，重新打开assignment并消费恢复记录，08:29:00.447创建、08:32:17.948 completed，约3分18秒。控制层最终确认29项证据全部采纳，无未采纳项；封存报告声明未重算求解器或数值单元。原失败没有改写为成功。最终科学对象为 fig4_iterative_alignment_analysis_delivery_1.output，同生产者清单为其 .recovery_manifest。

## 封存科学结论的范围

封存报告 overall_verdict=inconclusive，claim_allowed=true 仅表示有依据的有限结论可报告，不代表实现总体目标。报告确认20例完整、实现与本轮计划一致，两材料唯一代表均为mid-D/high-Cs且位于Cs高边界。

| 指标（均来自封存摘要） | InAlAs | InGaAs |
| --- | --- | --- |
| 前区水平误差，历史→本轮，decade | 0.181563→0.005931 | 0.127666→0.009095 |
| 参考x1，um | 0.433058 | 约0.350779 |
| 本轮代表x1，um | 0.716033 | 0.548899 |
| x1偏深量，um | 0.282975 | 0.198119 |
| held-out RMS，历史→本轮，decade | 2.141178→1.838940 | 1.943902→1.713324 |
| 尾部可判定性 | x3之后没有合格三独立单元参考块 | 参考x3不唯一，下游尾指标不可判定 |

x1/x3按已审合同分别是相对前水平下降1/3个数量级的交点。原中文报告部分句子使用“三十倍”措辞，但其analysis_method明确写L_F-3；本记录按合同定义称“3个数量级”，不对数值另作推断。

结论是前区与部分形状指标相对改善，深度偏差仍明显；两个代表的边界状态与尾部观测不足阻止完整shape-consistent判断。不能宣称绝对复现，也不能证明常数D/Cs家族永远无法拟合或确认唯一微观机制。下一轮设计候选由封存handoff提出：有限Cs高侧扩展、解决尾区支持或经审查修订判定合同；此记录没有创建下一轮实验或执行请求。

## 现场错误及归属

| 事实 | 已定位原因 / 处理 | 边界 |
| --- | --- | --- |
| 首轮原生KeyError，08:21:12 | 封存报告说明：InAlAs历史anchor的x3之后没有合格三独立单元尾块，脚本未先处理不可判定分支；改为保留可算指标、尾指标not_determinable | 分析脚本对科学缺口的处理错误；不是求解器或输出校验失败 |
| 首轮原生ValueError，08:22:51 | 封存报告说明：InGaAs参考x3存在多个下降交点；保留front/x1和残差，参考W13及尾指标not_determinable，不任意平滑/选交点 | 科学方法的可判定性限制触发脚本错误；须返回有限结果 |
| 首轮提交超时 | 创建08:12:05.812，截止08:27:05.812；submit开始08:27:32.668，晚约26.86秒。最后原生命令08:24:24.854结束，最后文件发布08:25:41.222完成 | 交付超时，不是求解或传输耗时；不延长原Run，使用剩余一次受控续接 |
| 续接发布analysis_file_unavailable | 将只读tool_recovery_manifest误放进publication source_alias；公共诊断定位publish_files→source_descriptor，删去该非发布别名后再次发布成功 | 工具来源绑定错误，不是科学输出格式拒绝；原错误继续保留 |
| 附加诊断捕获超限 | 封存报告指出runtime_manifest附加诊断超限，但绑定diagnostics及原solver products可读、成功状态不变 | 是报告中的运行诊断边界，不能归作solver失败或补称所有日志无截断 |
| 输出校验拒绝 | 两个Run控制摘要rejection_count均为0 | 超时提交仍是真实失败，不因该计数为0而消失 |

续接工具错误的 scoped reference：diag_3ed34bbbdb44430895f36fa84676cd6b。Root通过diagnostic_read成功读到共同异常链；没有直接读取服务器路径。两个原生命令错误先由native摘要显示类型、时间和退出码，具体科学触发原因后来由completed报告核实。

## 框架验收与后续问题

已在真实现场验证：日志同步与收集分离、原VM兼容、短时间完成43文件登记、工具错误后继续、恢复29项证据、同compiled Agent在新Run交付。first Run创建至首个受控命令约112秒；观测不能把这段等待全部归因于文件读取或CPU计算。原生命令之间有较长间隔，尚不能从这些记录确定Agent推理/读取/编写各占多少。

仍应保留的问题：
- 首轮过截止的提交调用已记录时序，但Root最初仍看到running且错误摘要为空；调度显式run_record_failure后才显示run_timeout。当前生命周期要求调度记录失败，但提交拒绝的诊断呈现仍有空白。
- 只读恢复清单作为发布来源被误用；接口应让可读别名与可发布来源的区别更容易理解，不能只凭“unknown alias”便要求Agent反复猜测。当前详细诊断能定位到函数，但没有指出具体别名/数组项。
- 分析脚本仍需更早处理计划已经允许的not_determinable分支，并更早完成主报告；本轮保存和续接避免了重算，但首轮仍交付超时。
- 封存报告部分中文数量级措辞有误，合同定义与文字表述应一致。
- 原R6审查保留的Hardened公共workspace合同冲突、其他配置组合与裸平台命令完整观测仍未验收。

本轮只完成当前有限包络的执行—收集—分析—恢复交付闭环，总体曲线对齐与机制目标仍未完成。没有运行全量测试、额外VM求解或新科学审批。

