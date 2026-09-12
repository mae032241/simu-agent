# P6 现场验证：有限分析已封存，科研闭环未通过

日期：2026-09-11。原实例 M7-test0；服务目录及 25 个 Worker 类型与候选一致，用户通过本地管理页绑定后继续。本文记录工程验收状态；科学内容仅来自 Root run_status 返回的 completed/sealed_output，不读取或采用失败草稿或子 Agent 聊天作为科学结果。

## 后续核查更正：不能将本次调用失败直接归因于算子缺失

用户追问后，进一步核对现有源码及上述已封存请求：`CurveOperatorSpec.value_space` 已支持 `linear|log10`，默认 `linear`；`_evaluate_operator` 的 residual_max_abs/residual_rms 已实现对数残差并返回 decade。两条实际请求仅设置 `interpolation=log10_y`，没有设置算子的 `value_space`，也没有 threshold，故按默认线性值空间计算且没有阈值检查。对数插值与对数残差是不同设置。

因此，本文下述“分析工具不能完成既定归约”是当时依据封存分析作出的过早概括，应收窄为：本次请求没有产出符合原计划定义的结果，不能据此证明已有工具缺少对数残差能力。参数展示为 unknown、assignment 缺少完整参数合同读取入口，仍是已观察的展示缺口；它是否是遗漏 value_space 的唯一原因未被证明。完整归一化、采样、掩码和加权要求与已有算子的等价性，仍须由科学角色据原计划核对，Root 不代作该判断。不能立即扩充一套新算子来替代正确调用已有能力。

源码依据：plugins/curve_score/curve_score/schema.py 的 CurveOperatorSpec 和 _evaluate_operator；请求依据：P6_ANALYSIS_COMPLETED.json 中两条 computed 的原始 request。封存科学 Artifact 保持原样，后续能力核查应作为新的判断，不回写旧结论。

## 已完成

- 原目标、计划、匹配独立审查、执行结果、恢复清单、11 个补收集产物、原始日志/PLX、参考 bundle/行表和既往分析通过新分析 Operation 预检。
- fig4_continuation_execution_analysis_4 由全新隔离历史的编译 Agent 执行。它发生 5 次工具参数拒绝、1 次计算工作量上限，另有 2 次输出拒绝，未在预算内封存。Agent 返回后 Root 核对截止时间与状态，显式登记 timed_out 并保留恢复材料；没有将它记作成功。
- fig4_continuation_execution_analysis_5 使用相同不可变科学输入及 resume_from，通过新预检创建新 Run，再由同一已空闲、同编译类型的 Agent 重新打开 assignment 接续。运行于 07:35:52 UTC 开始，07:45:09 UTC completed；6 次输出拒绝后提交成功。旧 Run 未重开，旧失败事实未改写。
- 封存结果包含 8 条计算记录：5 条参数错误、1 条工作量上限、2 条 computed；均引用恢复证明中的原尝试。失败尝试和成功计算一同保留，未靠删除失败记录完成提交。
- 封存分析建立了六案例 PLX/TDR 的证据化对应，并对原执行仍为 failed、产物恢复、实现步骤与科学结论作出区分。

详细受控记录见 P6_ANALYSIS_START.json、P6_ANALYSIS_FIRST_FAILURE.json、P6_ANALYSIS_RESUME_START.json、P6_ANALYSIS_COMPLETED.json。P6_LIVE_OBSERVATIONS.json 是续接过程中保存的中间快照，不是最终状态。

## 为什么仍未通过 P6

封存分析的 verdict 为 inconclusive、claim_allowed 为 false。两项 computed 返回原始浓度的最大绝对差，单位 cm^-3，covered_validation_check_keys 为空；分析者明确未将其等同于原计划的 log10(C/Cs) 收敛差。原计划的参考掩码与精确行账本、共享组权重、加权 WRMSE、J/G、无缺口连续支持 T 与类别稳定性仍没有有效受控计算结果。

按计划 §10 第 3 项，任意简单指标不能替代原目标检查。因此不能把“真实工具算出了数字”计为目标计算验收通过，也不能宣称假设已支持或反驳。

按 §10 的能力缺失分支，本次保留原研究问题，当时将未完成既定归约记录为分析能力缺口；后续源码核查已在上方更正这一过早归因。没有为匹配工具而改写科学目标，没有转交 TCAD author 实现分析工具，也没有要求重跑原求解器。下一轮设计及其物化/匹配独立审查尚未开展；P6 总体未完成。

## 现场暴露的工程缺口

1. **参数可发现性未闭合。** 最终编译 Schema 的 request 指向 #/$defs/TCADScoreRequest，并具有完整 definitions；本会话平台可见的工具声明却为 request: unknown。assignment_json 只提供工具名称，没有另一个可读取的完整工具参数合同。封存的前五条记录是逐步构造空/不完整结构的参数探查，说明源码/MCP Schema 一致并不等于实际模型能够读到完整结构。根因范围指向 Schema 到平台可见声明的投影及其读取后备入口，不是假定 TCADScoreInput 又定义了另一套参数。
2. **部分输出错误仍没有可操作原因。** 来源引用及计算记录的 value_error 被替换为通用说明；部分 context_binding 仅定位 $.payload。最后一次拒绝能够保留具体的“computed case mapping requires the same formal source reference and basis”，说明显式安全说明的路径可用，但并未覆盖所有已触达校验。需要在错误所属模型/规则保留安全的具体原因，不能恢复任意异常文本透传。
3. **超时摘要归类需核对。** Root 使用 timed_out=true 及精确截止时间登记失败，但 failure 摘要显示 checker_failure；reason 保留 deadline_exceeded。该摘要不能证明校验器实际崩溃，本次只按预算耗尽和未封存记录失败。

这些发现补充工程阶段的已知限制，不改写冻结的独立审查历史。当前没有进行新的源码修订或部署。

## 验收分项

| 条件 | 当前状态 |
|---|---|
| 安装身份、原实例与证据续接 | 已验证 |
| 参数错误可定位并在同 Run 修正为工具执行 | 已观察；模型参数展示仍有缺口，首轮整体超时 |
| 至少一项符合原计划或论证等价的计算 | 未完成 |
| 计算、映射、失败尝试、有限结论一同封存 | 已验证，含失败 A→完成 B 的真实接续 |
| 新设计、物化及匹配独立审查 | 未开展，分析能力缺口待处理 |
| 错误输出仍被拒绝 | 现场观察到来源/记录/映射拒绝；其他负例沿用 P5，不称现场全覆盖 |

本轮 Root 未调用 Worker 工具、代写请求或计算、运行测试/求解器、修改科学产物，未启动第三轮相同分析。后续工作应先补齐参数展示与具体诊断，正确使用已有能力并核对其与原计划的等价性，再判断哪些运算确实需要最小扩展。
