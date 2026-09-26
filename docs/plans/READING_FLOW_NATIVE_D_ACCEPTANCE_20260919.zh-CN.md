# 阅读流程修复：原生 D 验收

日期：2026-09-19。结论：本次固定两轮实测窗口收益成立，功能交付完成；仍有首次读取误用，不能称全部缺口清零。独立实施复审尚未执行。

本记录拥有部署后实测结论；[实施记录](READING_FLOW_REPAIR_IMPLEMENTATION_20260919.zh-CN.md)保留源码与离线验证事实；[计划](READING_FLOW_REPAIR_PLAN_20260919.zh-CN.md)保留验收要求。B/C 历史证据不修改。本轮仅增加计量脚本、证据及状态链接，没有改变部署候选源码。

## 方法与可比性

沿用 frozen native_ab_protocol.json，science.object.review.v1，sol/medium，每轮 600 秒、单次预算。组间新 Worker、组内同线程接续；五份输入与增加参考审查后的六份输入均与 B 精确相同。科学角色、编译 Operation、任务指令与语言分别相同；中文首轮、英文接续。已核对实际模型/强度及部署 helper。总体目标仍绑定。

实际线程 01a0b80b-0b5d-79a3-9f2a-aac287484796；Run worker_context_ab_D_review_20260919_1 和 _2。原生 JSONL 逐请求计量，D1/D2 边界在发送第二项任务之前保存。读数无缺失，无观测到的压缩事件或工具截断；这不证明平台内部完全没有裁剪。原生 Worker 不受离线 768 MiB 采样 guard 的硬限制。本轮串行，未执行 TCAD。

## 结果（tokens）

| 指标 | B 较好基线 | C 回退版本 | D 当前版本 |
|---|---:|---:|---:|
| 首次输入 | 21,583 | 21,648 | 21,595 |
| 首轮峰值 | 58,970 | 59,606 | 53,358 |
| 首轮净增长 | 37,387 | 37,958 | 31,763 |
| 接续轮净增长 | 15,445 | 29,022 | 9,329 |
| 两轮整体峰值 | 74,518 | 88,734 | 62,789 |
| 两轮整体净增长 | 52,935 | 67,086 | 41,194 |
| 请求数（首轮 + 接续） | 23 + 8 | 41 + 20 | 37 + 10 |

D 相比 B：整体峰值 -15.74%，净增长 -22.18%，接续净增长 -39.60%。相比 C：整体峰值 -29.24%，净增长 -38.60%，接续净增长 -67.86%。初始输入基本不变，收益来自运行时增长减少，而不是基底变小。不能把缓存累计输入当窗口；请求数仍高于 B，不宣称所有成本都改善。一组实测支持本次收益，不构成跨任务统计保证。

D 首轮工具可见回复 91,441 字节，接续 15,227 字节。计量口径与 B/C 相同，字节不直接等于 token。首轮 Schema 所在回复 11,093 字节、仅一次；接续收到 reading_guidance，无角色正文或 Schema helper 重读，Schema 错误为零。

## 功能与剩余缺口

两轮均 completed，提交拒绝为零，科学审查判定均为 revise。revise 是对研究计划的结论，不是输出校验拒绝。封存结果保留总体目标、已完成六案不得原样重跑、实现/数值与物理解释区别、尾区/不确定度/InAlAs 限制。第二轮独立指出参考审查中的两项范围问题：backend 名称不足以证明实现可行；停止原样重跑不等于禁止未来研究。Root 检查了封存字段与 scheduler_signal；未把本次内容核对冒充额外独立科学审计。

D1 仍有四次 reader 错误，集中于同一次批量调用：把 inputs/experiment_plan.json、inputs/research_objective.json、inputs/execution_context.json、inputs/result_analysis.json 作为材料名称传入，并缺少 --file。精确错误为 `[read_input error: ValueError: input missing or ambiguous; select one source_name from assignment.inputs]`。现有 helper 区分语义名称与显式文件模式，实际调用误用了已知文件路径。后续纠正后交付；D2 无 reader 错误。此问题不是 C 的裸 next 丢字段问题，也不是提交门禁拒绝；应保留为 reader 易用性缺口，不在验收中悄悄修改候选或重试挑样本。

下一项有证据支撑的改进是缩小上述路径/名称误用及首次多次往返；不扩充科学强制字段，不重新暴露机械哈希。独立实施复审仍待完成。

## 证据

全部计量与诊断文件位于 [D 证据目录](evidence/reading-flow-repair-20260919/)：native_D_loaded_version.json、native_D1_requests.json、native_D_all_requests.json、native_D_stage_boundary.json、两份 completion、native_D_summary.json、native_BD_comparison.json、native_CD_comparison.json、native_BD_comparability.json、native_D_reading_behaviour.json、native_D_behaviour_summary.json。脚本只输出工程元数据，不另造科学成果。
