# 曲线评分移入结果分析工具：独立实现审查 R1

结论：**PASS（本次有界源码实现与所列验证证据）**。最终被审源码未发现尚未修复的实质阻断。此结论不等于安装部署完成、真实研究接续或科学目标完成。

日期：2026-09-09。使用 `scid-cross-boundary-review` 与 `karpathy-guidelines`；审查者只读生产源码及验证日志，仅新增本报告，未运行测试、构建、求解器或科学 MCP。

依据：[R3 计划](../CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN.zh-CN.md)，SHA256 `33d0072b660aa3dd34048f8230cf1be61dd69211981089125267ae657e893ea0`；[P0 基线](../evidence/analysis-tool-implementation/p0-baseline.json)，HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树包含大量先前修改；P0 指向的 `/tmp` 原始归档已在故障后丢失，本审查不声称恢复了完整的历史增量快照，也不为无关修改背书。

## 结论依据

- 通用诊断 v2 与 TCAD 领域入口均允许不评分。TCAD 从绑定原始 PLX／日志／CSV 在同一 Run 内解析和评分；无合同、无预绑定 bundle 不构成必需前置条件。失败执行和缺失观察可以提交受限分析。
- guard 检查确切计划—独立审查、计划—package—manifest 及输出父关系。最终校验通过控制端按确切 ArtifactRef 重建的只读描述符核对输出名、媒体类型、长度和摘要；bytes 与描述符按同一 context_sources 过滤，不扩大 handoff_only 可见性。无评分路径同样核对身份；同摘要不同输出名不能互换。
- computed 记录从确切原始字节重放；unsupported／unavailable 保留可重放的原因。error 无数值且不能支持决定性数值门。最终重放超时会产生可修正的拒绝，不能把未核验 computed 值封存为可信证据。
- 修复了仅凭 validation_check_key 和宽松请求阈值取得原计划 PASS 的路径：只有匹配原计划指标、阈值、方向和单位的实际通过检查计入原门槛覆盖。方法变化仍可保留为受限分析；总体通过不能因此绕过未完成检查。通用目标成功也不能明确引用失败比较作为成功计算。
- 修复了畸形 comparison 元素逸出为 AttributeError、record_key 输入与输出约束不一致、CSV 解析异常未归类及 TCAD 静默忽略未知映射选项。工具可见请求说明包含现有比较 schema 和来源映射要求，不依赖测试 fixture 的隐藏合同。
- 工具在读取前开始计算半剩余预算；解析／比较检查共同截止时间，最终多记录重放使用控制端传入的共同期限。原始文本在 splitlines／逐行对象分配前检查行数，并拒绝可绕过 CR／LF 计数的其他行分隔符；同时保留字节、点数、采样和工作量上限。
- 报告继续使用 LayeredDiagnosisReport 的可选字段，下一轮设计通过既有 result_analysis 端口读取封存内容；未增加评分阶段实体、持久状态或跨 Run 临时输入。

## 验证证据与边界

审查者直接读取父执行者保存的 [source-validation.log](../evidence/analysis-tool-implementation/source-validation.log)：**127 passed，1 deselected，20.25 秒，exit 0**；最大 RSS 110136 KiB。范围包含新通用工具、TCAD 分析、描述符接线、原曲线分析边界、Run 与修订路径。父执行者采用单测试进程和 3 GiB 虚拟内存限额；审查期间未另起测试进程。

另读取 [positive-check.log](../evidence/analysis-tool-implementation/positive-check.log)：原计划条件仍可通过的正向控制 **1 passed**。所阅测试源码覆盖无评分提交→下一轮读取、错轮与同摘要异名拒绝、畸形输入、重放修改、期限耗尽、过多原始行在解析前拒绝以及未完成定量检查不得通过。

本次未把被排除的高资源 stress 用例写成通过。报告封存时父执行者正在串行验证隔离安装入口，其结果尚不纳入本结论。未执行实际部署、真实求解器或真实研究接续；计划 P5／第 6 节的现场证据仍需分别记录。

时间控制是协作式检查加有界单步工作，并非硬实时抢占：单次读取、Pydantic bundle 验证及既有解析原语不可在任意指令处中断。标准 bundle 的对象分配仍受输入字节上限约束；本审查未要求新增通用解析或进程框架，也不据此声称已验证所有极限负载。

## 最终源码指纹

以下为父执行者声明生产源码冻结后读取的完整文件 SHA256；其中未改动部分和先前工作树内容仍包含在文件摘要中。

| 文件 | SHA256 |
| --- | --- |
| `plugins/curve_score/curve_score/analysis_tool.py` | `573fc1ef453ec9f36c3bf39d64943aec0aff975c6eb2b127e94bdf8c9b5a6204` |
| `plugins/curve_score/curve_score/science_operations.py` | `2db57bb7360a38b4c94cb94efd42e66b347499d659043bec840ae9162441f834` |
| `plugins/curve_score/curve_score/schema.py` | `12eb792747d9ea1bb03df1e27af85a46a2a715ef4fe5dd60fd580de07a6b0c62` |
| `plugins/tcad_artifact/tcad_artifact/result_analysis.py` | `83815ea0f175ddc1c8344cc46dfe347d2c7e0f4471dd1ad540ef0f80ea4c5769` |
| `plugins/tcad_artifact/tcad_artifact/execution_control.py` | `c7631974cf822bee41eb71a1d8298a4f9f2715d2295e65b206a0fc00f513df7a` |
| `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py` | `8ed035358fc41dd9288df00b25584c29def514d8447c4978e37f04a79a2337d2` |
| `src/scidiscovery/artifact_agent/service/run_outputs.py` | `5afd93d08107f427b4019c5d10659eb73f556490ec5e679fdbaeee3f37203594` |
| `src/scidiscovery/artifact_agent/service/runs.py` | `4ef2696081c3b5c0c373aff857470243a9dde7b767700762151e663963bf7c90` |
