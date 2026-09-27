# 实验反馈与 MCP 信息分级实施记录

基线 HEAD：90a7b3a5865eb45649f1a39221337f9d939a3d71，加 `baseline.diff` / `baseline-dirty-files.tar.gz` 中实施前工作区。两个 R1 计划送审字节不变，用户随后明确授权实施。本记录描述实现，不继承计划级 PASS 为实现 PASS。

当前：源码实施、独立静态审查与隔离工程验证完成。完整结论见 [VERIFICATION.zh-CN.md](VERIFICATION.zh-CN.md)。未安装生产服务，未重新运行 Fig4 求解器；真实模型行为验收仍待新合同环境。

## A：反馈闭环

- proposal / critic 新增可选 previous_hypotheses；proposal / critic / revise 增加有界 experiment_results、result_analysis、current_progress。可读历史/负结果，不授予执行或科学成功资格。
- 精确绑定别名与 foundation 原来源共同构成三类 hypothesis 输出的引用范围。局部关闭这三类输出的 alias-only Schema 枚举；上下文来源校验仍拒绝未知来源。不改全局校验引擎。
- critic 能直接看到 foundation 与反馈原件；提示、语义要求和实际 validator 一致。修订保留假设 key 集合及原有审查/预算；新 proposal 可改变候选。
- scheduler 从结果、限制和原件选择下一步；不给 Root 科学判决权。报告 Schema、REPORT_GUIDANCE、分析 workspace 内容保持。
- `test_hypothesis_feedback_flow.py` 在有/无反馈下，真实 preflight 的 normalized_request→invoke→Local Worker→错误引用拒绝→同 Run 修正→critic→revision→critic→design→materialize 已完成。只有 foundation 人工决定使用 fixture；新 proposal、critic、design 均真实封存。它证明工程接通，不证明 LLM 科学行为。

## B：按需读取

- Root MCP Router 统一施加纯读取投影；完整 facade 保持，UI/轨迹/归档不用跟随 MCP 默认行为改变。
- 状态默认无科学正文/完整 bindings/日志尾部；保留可执行派发配置、恢复预算和实际错误。完整 metadata 用 view=detail，正文用 output_paths，默认 summary 片段明确标记。
- catalog/inventory/outputs/list 采用有界页；catalog 按 operation_id 展开原完整声明。lifecycle 未交付事件不推进观察记录。
- 计算记录先保存完整 immutable bytes，再返回少量实际指标及原件路径；debug、文件候选、figure preview 保存既有工作区详情。不改变评分算法、物理判据或执行授权。
- 所有 29 Root + 19 Worker + 3 生命周期工具逐项记录在[审计清单](../mcp-response-levels/TOOL_AUDIT.zh-CN.md)。显式诊断读取、预检 normalized_request、无详情通道的具体错误保留完整，是必要信息例外。
- **经独立审查修正的最小例外**：Hardened backend 禁原生文件读取，因此保留原内联 tool_contracts；Local 和 legacy Local 返回冻结合同路径。不增加通用读取工具、不扩大权限、不引入全角色协议变更。不能声称 Hardened 目录也已精简。
- stdio / daemon / proxy 保留 text 与 structuredContent 的兼容表示，二者承载相同业务结果。编排仍只消费一份。

## 验证与已知边界

- 每批通过 bounded_check.py 串行监控，2 GiB 进程树、180 秒；checks.jsonl 记录实际命令、结果、峰值和耗时。原始失败日志保留，不能只看最后通过数。
- baseline 对照已确认：既有 object review verdict=blocked 的 handoff 字段投影失败（无该枚举映射）；旧 collection 测试 fake BoundOperationCall 缺 execution_profile。后者补齐测试 stub；前者不改本轮科学合同，记录为独立遗留缺陷，不把它归因于摘要或反馈修改。
- A 三个 hypothesis digest 改变；B 的两个分析、三个 author、一个 figure prepare digest 随实际工具返回变化。其余 41 个 Operation digest 不变，包含执行/审批/设计、curve-error analysis。详见 changed-digests.json。
- 实际模型的 B1有效反例、B2数值失败、B3不可辨识三组行为验收需要新合同的隔离可调用环境或安装后进行。本会话已加载旧 Worker 目录，不以生产绑定或预制答案代替，当前未宣称行为通过。
