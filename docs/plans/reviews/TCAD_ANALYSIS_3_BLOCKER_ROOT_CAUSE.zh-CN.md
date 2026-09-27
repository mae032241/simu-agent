# TCAD analysis 3 阻断根因核查

日期：2026-09-11。对象：`fig4_continuation_execution_analysis_3`。工程审查，不修改或替代其封存科学结果。

## 证据与范围

- Root completed 状态、封存结果和 evidence_outputs：产物恢复成功；分析经历六次拒绝，最后以有限结果完成。
- 本次 Worker 的实际评分调用与七次提交工具响应：仅用于工程调用和拒绝原因核查，不使用子 Agent 聊天作为科学证据。
- 当前工作树 HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`，存在既有未提交修改。审查未改变源码。
- 安装目录中的 result_analysis.py、plx_normalizer.py、analysis_tool.py、layered_diagnosis.py 与当前源码逐字节一致。以下问题不是这四个文件未部署造成的。
- 仅运行一次安装包的合成两点 PLX 复现，进程地址空间上限 512 MiB，峰值 RSS 61,844 KiB。未跑 pytest、求解器或修改原执行文件。

## 1. 首个计算失败是请求错误，被误报成 PLX 格式不支持

实际调用把 `x_axis` 传为字符串 `x`，`y_axis` 传为字符串 `ZnPhen`。`SProcessSeriesSpec` 要求两个字段都是 `CurveAxis` 对象（name、unit、scale）。`parse_tcad_sources` 在调用 PLX normalizer 前就校验该模型。

`evaluate_tcad_request` 把这类 Pydantic ValidationError 统一变成 `status=unsupported, reason_code=tcad_layout_unsupported`，丢失字段与原因。

安装包合成复现：

1. 字符串轴得到 x_axis/y_axis 的 `Input should be an object`。
2. 外层工具返回 `tcad_layout_unsupported`。
3. 只改成正确轴对象，同一合成 PLX 正常解析出两点。

因此，封存报告中“实际 PLX 布局不受支持”的归因未经该调用证实。此审查没有对真实曲线重新计算，也不声称真实文件已经通过解析。

位置：`plugins/tcad_artifact/tcad_artifact/result_analysis.py:130`、`:169`；`plugins/curve_score/curve_score/schema.py:61`。

## 2. 请求还有第二层结构错误，且使用了未注册的算子名

实际 comparison_spec 使用 `operator/pairs/normalization_left/normalization_right` 结构；工具要求 `CurveComparisonSpec`，包含 `spec_key/comparisons`，每项指定 reference_series、candidate_series、domain、interpolation、operators。

调用的 `max_normalized_log_difference` 不是当前 CurveOperatorSpec 的六种 kind 之一。修正轴对象后，原比较结构仍得到 `input_or_request_invalid`。这不代表所需数学计算必然无法由现有算子组合实现；该等价关系尚未由科学 Worker 判断，不能由调度者擅自替换。

工具描述已有轴对象说明和比较 schema，故不能归因于完全没有文档。但 request 在 MCP schema 中是任意字典，错误只在内部暴露，又被归类为“unsupported”，没有帮助 Agent 在原任务内修正。实际记录只有一次评分调用。

位置：`plugins/curve_score/curve_score/analysis_tool.py:41`、`:155`；`plugins/curve_score/curve_score/schema.py:209`、`:333`。

## 3. 上游可选案例身份，下游要求显式身份；恢复工具不能补齐

ExpectedOutput 的 experiment_key/case_key 允许同时为空。分析 input validation 只在存在 case_key 时检查其属于计划。缺少身份的历史记录可以进入分析，这本身符合有限分析要求。

但 `_check_source_identity` 只认可原项目输出声明中的案例身份；计算成功记录必须显式带 output_name、experiment_key、case_key。`accept_tool` 可以接受实际文件与声明 output_name 的对应关系，却只能复制原声明的 experiment_key/case_key，不能表达基于源码、日志和证据建立的新案例映射。

所以恢复字节到“可正式逐案例计算”之间仍缺一个可表达的交接。本次第五次提交明确触发 `analysis case differs from explicit project output case`。即使工具返回 unsupported 记录，其 mapping 仍会经过该身份检查，因此连保留失败计算的诊断记录也可能被拒绝。

这不是应当把所有历史缺标识记录拒绝在 preflight 的理由。应允许有限分析，同时明确可验证案例映射的来源和作用范围。

位置：`plugins/tcad_artifact/tcad_artifact/execution_control.py:93`；`result_analysis.py:232`、`:264`、`:314`；`output_recovery.py:130`。

## 4. 另一个可达缺陷：全局日志被纳入逐案例完整性阻断

`analysis_context` 的 unmapped 检查遍历所有 solver_outputs，只要有一个输出缺 case_key 就禁止 claim_allowed 或 overall_verdict=pass。没有区分跨案例 process_log 与逐案例曲线，也没有按实际结论引用范围限制。

本次绑定包括全局 solver_log。即使后来曲线身份齐全，只要保留没有单一 case_key 的全局日志，该分支仍可能拒绝成功结论。这是源码确认的后续风险，不是本次六次拒绝中的已触发分支。

位置：`plugins/tcad_artifact/tcad_artifact/result_analysis.py:360`。

## 5. 六次提交拒绝的确切序列

| 次数 | 规则 | 工具返回的具体原因 |
|---|---|---|
| 1 | payload_consistency | downstream prerequisite gate must be not_evaluable |
| 2 | payload_consistency | objective assessment status must match the ordered objective gate |
| 3 | payload_consistency | overall verdict does not match the ordered scientific gates |
| 4 | payload_consistency | invalid study cannot support or contradict a hypothesis |
| 5 | context_binding | analysis case differs from explicit project output case |
| 6 | context_binding | objective comparison lacks a completed calculation |

第七次提交成功。前四项来自 LayeredDiagnosisReport 的固定层级依赖及多个重复派生状态，逐次抛异常导致 Agent 逐字段返工。第六项禁止把未完成计算写成已有比较依据，原则合理。

这次不能笼统说成“提交重新准入所有输入”。第五项确实是输出声称的案例身份与绑定声明比较；但唯一可接受身份来源过窄，且失败计算记录同样受约束。前四项又把局部证据不足传播为全报告 invalid_study，削弱分别表达已知事实与未完成判断的能力。

位置：`src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:43`、`:176`；`plugins/curve_score/curve_score/science_operations.py:596`。

## 6. 错误信息和最终记录未形成可靠诊断闭环

评分工具吞掉了轴字段校验详情；Root 的持久诊断摘要又有意只保留 rule_id 和粗粒度路径，删除 message，无法仅靠 run_status 区分具体错误。这次完整拒绝信息来自 Worker 工具传输记录。

最终封存报告的 calculation_records 为空，却仍保留“解析不支持 PLX”及相关后续建议的文字，同时新增案例身份阻断。输出校验允许了这些叙述与真实技术触发原因之间的不一致。封存代表受控接收，不代表报告中的工程根因已经独立验证正确。

位置：`src/scidiscovery/artifact_agent/service/runs.py:775`。

## 7. 为什么此前测试没有暴露

现有恢复评分测试覆盖了工具检查、接纳、评分、封存和跨 Run 重放，但使用已有案例键和程序构造的正确评分请求。历史缺身份测试验收的是能够提交有限分析，并非补收集后完成真实逐案例比较。它们证明局部协议可用，没有证明本研究的实际交接及自主纠错能完成。

位置：`tests/operations/test_analysis_evidence_recovery.py:47`；`tests/operations/test_tcad_result_analysis.py:30`、`:67`、`:180`。

## 工程结论与修复方向

根因链为：Agent 请求错误 → 工具把可纠正参数错误误报成格式能力缺失 → Agent 未修正评分请求 → 案例身份只有旧声明一个来源，恢复证据无法补充 → 固定层级和派生状态触发连续拒绝 → 最终只封存了有限且工程归因不准确的报告。

最先应修请求诊断与同轮纠错；随后解决案例身份交接和全局日志误阻断；再减少重复派生状态导致的连锁返工，并保留可追踪的失败计算诊断。不要先扩写 PLX parser、要求 designer 改科学目标或重新运行求解器。真实 PLX 是否还有独立格式问题，必须由正确请求另行验证。
