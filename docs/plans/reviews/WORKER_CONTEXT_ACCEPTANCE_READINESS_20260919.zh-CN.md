# Worker 上下文修复验收前置核对

日期：2026-09-19。结论：**尚无修复后候选版本，S1—S5 待实施，不能进行修复收益验收**。

用户确认采用现有原生 Worker 链路，已写入[计划 R1](../WORKER_CONTEXT_WASTE_REPAIR_PLAN_20260919.zh-CN.md)。这次是静态前置核对，不是独立复审通过，也不是模型或源码验收通过。

| 项目 | 当前源码证据 | 状态 |
|---|---|---|
| S1 原文读取 | service/input_reader.py 尚不存在；无对应 test_input_reader.py | 待实施 |
| S2 日志展示 | local_process_observation.py 仍按 LOG_LIMIT 同时限定留存和 analysis command 回显，没有 summary/raw 分离 | 待实施 |
| S3 日志指引 | tcad_deck_author.md Diagnostic logs 仍要求从短回复取 progress.log_tails/log_excerpt | 待实施 |
| S4 角色复用 | codex.py 仍要求每个 assignment 读 role_instructions；local_worker open 未提供计划中的角色指纹 | 待实施 |
| S5 恢复摘要 | mcp_response_views.run_summary 仍直接 pick recovery 整项 | 待实施 |

当前工作树有大量既有改动；本次仅修订计划并记录前置核对，未覆盖或回退任何生产代码。未启动真实模型、pytest、仿真或部署：不存在 after 实现，跑旧测试或旧模型不能证明计划完成，也没有必要再次付费复现已保存的 baseline。安装态亦未声称验收。

下一步先实施 S0 基线冻结与 S1，随后按 R1 串行逐项验证。S1/S4 使用原生真实 Worker，S2/S3/S5 使用定向回放。资源覆盖、usage、信息完整性、源码/加载指纹分别报告。原生进程树内存硬限制未覆盖；legacy CLI 和 fixture 不能替代。
