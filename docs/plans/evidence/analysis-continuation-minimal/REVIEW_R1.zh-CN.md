# 分析续接与机械映射最小修订计划 R1：独立工程复审

日期：2026-09-12。结论：**PASS**，可按本版本的目标、文件范围与受限资源验收方案实施。此结论是工程计划通过，不代表尚未实现的行为或真实 Agent 耗时已通过验证。

- 被审计划：`docs/plans/evidence/analysis-continuation-minimal/PLAN_R1.zh-CN.md`。
- 冻结被审计划 SHA256：`e30e39e1e476b5e3ae7d90a7ef2e011f69ec95c4fc8ef78a2cd23c626f20b1ed`。
- 既有独立审查：`REVIEW_R0.zh-CN.md`；被审 R0 SHA256 为 `f14c3847f02ad10fc47f37b062bb06e5ddd3994e6e01253f5a3752fa359ae0f2`。
- 基于同一仓库当前工作树及 R0→R1 精确文件差异复审；HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`，有大量既有未提交改动。本审查未改计划或源码，未调用科学/Worker MCP，未运行测试、构建或 solver。

## 1. 阻断关闭

| R0 发现 | R1 修订及复审结论 |
| --- | --- |
| R1：工具原请求摘要与补全后的计算请求不一致；case_key 在 handler 前必填 | P3 明确保留 case_key/series/axes 等选择，且不修改 `_raw_request`、`CalculationRecord.request`、attempt 摘要或通用收据。既有映射只参与派生关系检查和依据复用。与 `begin_tool_attempt`、`run_score_tool`、`run_diagnostic_tool`、`_calculation_attempt_sources` 的实际路径一致，关闭。 |
| R2：将普通 input_alias 错当成 Identifier 并拟回显 | P4 改用固定原因和准确索引/字段路径，禁止回显任意输入及为打印错误新增格式校验。无需更改 `AnalysisSourceReference` 或工具输入 schema，关闭。 |
| R3：旧 launcher latest.json 进入新 Run 活动目录 | P2 明确排除整个既有 `local_process_observation.RECORD_DIR`，保留 recovery-draft 中的历史记录和日志。独立核对 `RECORD_DIR`、`read_summary`、`_directory` 后确认直接消除旧观测误归属，无需修改观测器，关闭。 |

未发现新增阻断。

## 2. 四项必要判断

**目标定位通过。** 计划处理读取重复、恢复文件权限、相同 Artifact/cohort 的既有案例映射和输出错误定位，保留完整原始记录与科学判断归属。没有增加科研目标或重新计算已完成 Fig.4 的要求。

**可实施性通过。** `RunService._materialize_workspace` 和 `_finalize_workspace` 可以用现有 `source_descriptor` 提供只读元数据，不必加载整批 raw 文件；两个 request 默认空字段保持旧调用兼容。共享 analysis materializer、现有 `finalize_result`、TCAD ComponentSpec 及原 snapshot 已覆盖所需钩子。工具维持原模型和请求，解决了 R0 的实际入口矛盾。

**职责一致性通过。** 现有 Artifact/descriptor 与精确 prior manifest 保持身份权威，TCAD 纯函数仅作有界投影。可见入口、工具、finalizer/context 采用同一映射规则；封存前只能补齐缺省机械字段，不覆盖明确新主张。analysis-start 是创建时的入口，新增工具证据在后续消费者读取当前 descriptor，无需增加入口同步状态。来源资格、数值评分、科学充分性不归投影或 finalizer 决定。

**最小变更通过。** 所列共享工作区、LocalWorker 返回、分析 guidance、两个 workspace request/RunService 调用点及 TCAD 小模块可覆盖生产变更。无需修改 generic score/diagnostic 请求协议、ToolAttempt schema、平台生命周期或 launcher。补充既有 installed 工具投影测试与原计划一次隔离 smoke 相符，不是新增测试框架。

## 3. 实施验收重点

沿用计划既有验收范围，重点保留以下可观察事实，不扩大成新的一轮全量检查：

1. 实际 MCP 的新分析 open 返回简明入口和合同位置；不再内联重复工具合同，旧 workspace 仍返回原形态。入口摘取均可追溯，字段溢出有原文位置；真实耗时收益待安装后单独验证。
2. 新 scratch 的复制脚本能编辑、能创建子目录和新 launcher 状态；恢复原件权限及内容保持不变，旧活动观测不进入新 Run，缺失/遗漏如实呈现。
3. 同 cohort 的既有 basis 在真实工具调用和报告物化中复用；原请求及其 receipt 摘要逐字对应。新工具证据使用当前 descriptor。明确错误输出/案例/依据、不同 Artifact 和别名碰撞继续给出正确字段路径。
4. 新报告封存后可在下一轮复用映射；缺映射的有限报告可封存，既有 schema/数量/字节界限继续约束输出，提交不重新准入输入或重算评分。

源码完成后仍须执行计划声明的受限资源测试、生产 catalog 和安装 smoke。审查通过不改变用户自行线上安装、安装后再做真实 Agent 验收的边界。
