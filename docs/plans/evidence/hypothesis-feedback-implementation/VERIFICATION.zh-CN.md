# 验证结论与范围

2026-09-16。源码实施与隔离工程验证完成；[独立实施审查](../../reviews/HYPOTHESIS_FEEDBACK_IMPLEMENTATION_REVIEW.zh-CN.md) A/B/组合静态 PASS，包含最终 draft_from 补核。未部署生产、未调用生产科学 Worker、未重跑 Fig4。

## 有效证据

| 范围 | 结果与记录 |
| --- | --- |
| 新反馈闭环、有/无反馈、来源负控、revision key 不变、旧 passing critic 不匹配新 portfolio、design/materialize | `test_hypothesis_feedback_flow.py` 通过；并入最终 15 项批次，`check-1789537959904074089.log` |
| 历史 completed 对象、真实科学审批跨运行时变化、profile 与恢复预算 | 同一 15 项批次通过；没有以 mock 新 review 代替实际 Worker 封存 |
| Root 摘要/按需字段、实际 adapter 超时可见、审批 URL、全部工具清单、分页事件不丢、恢复与有序父链、UI/旧授权负控、figure preview | 最终 37 项批次通过，`check-1789537825093684057.log` |
| Worker 合同 open、旧 assignment、Hardened 必要内联例外、semantic/schema 错误、反馈/提交边界 | `test_agent_contract_alignment.py` 定向批次中的 125 项通过（含其他 Root 节点）；该批 7 处失败为测试消费方式/旧 private API，后续 37 项批次已修复覆盖；既有 blocked-review 投影缺陷单列下文 |
| 评分/残差诊断、完整记录与图像、同 Run 修复、有限结论 | 52 项通过，`check-1789536748078702858.log`；当批新闭环 fixture 的 2 项失败随后修复并重测通过，不抹除原日志 |
| TCAD 恢复证据、跨 Run 计算收据、相同文件身份与原件可读 | `check-1789536834568340510.log` 中 41 项通过；余下新 fixture/局部 import 问题在 `check-1789536895688037065.log` 中修复，16 项通过 |
| TCAD debug 预算/错误/日志、实际 author→独立 review、原采集门禁 | 定向批次；作者/审查及分析 39 项通过，两个失败中的原件读取方式已修复并纳入最终 37 项；预算等另有 7 项通过。原消息断言缺陷单列下文 |
| 源码与 wheel 编译身份、安装后 Local/Hardened 合同、stdlib stdio 错误、评分/诊断/封存、安装后 hypothesis feedback | **12 项通过**，`check-1789537847232248791.log`；一次 wheel 构建/隔离安装，总耗时 59.9 秒、进程树峰值约 218 MiB |
| 真实已安装 proxy→Unix socket daemon→Root MCP，default/detail、text 与 structuredContent 同值、错误字段路径 | 复用上述 wheel 环境，不重建；`installed_transport_probe.py` 通过，`check-1789538308963229788.log` |
| 静态差异、编译身份、范围保护 | `git diff --check` 通过；9 个合同变更、41 个不变；实施前 UI/session 差异保留，新增增量见 implementation.patch 和 changed-files.json |

各批之间串行，未运行全量测试或 xdist；未同时运行多个重任务。所有本地测试/构建子进程树上限 2 GiB、每批 180 秒。包含开发失败与基线对照在内，20 批最高观测峰值 **259.6 MiB**，最长 **98.36 秒**，无内存/时间预算终止。checks.jsonl 与原日志保留完整失败过程，以上通过数不可相加当作独立测试数。

## 信息体积

`measure_responses.py` 使用隔离工程 fixture，同一内容对比原完整业务 JSON 与新投影；没有生产数据、真实求解或 token 遥测。

| 响应 | 完整返回 | 新默认 | 减少 |
| --- | ---: | ---: | ---: |
| execution status/sync | 5,042 B | 329 B | 93.47% |
| curve score | 3,990 B | 815 B | 79.57% |
| completed run_status | 4,582 B | 1,868 B | 59.23% |

执行状态决策仍为一次调用；已知分析 Schema 时，读取结论/摘要/限制/下一行动和 signal 也是一次显式选择，4,582 B → 2,151 B。
全部 25 项 public 摘要加选中 proposal 的完整合同：原一次全目录 107,489 B，新三次合计 9,891 B。默认首页 4,110 B 的减少不能冒充取得全部合同的同等信息量；原件按需展开的往返代价已明确计入。必要合同/详情/无其他读取通道的错误不作为运行时大小拒绝条件。

## 明确未解决或未验证项

1. **真实模型行为 B1/B2/B3 待验证**。当前会话加载旧 Operation Worker 目录；需新合同的隔离可调用环境或用户安装后开启新科研会话。工程 fixture 不能证明 Agent 会正确更新解释、区分数值失败与物理反证、保留不可辨识假设。
2. **原有 object review `blocked` 投影缺陷**：Schema 允许 `payload.verdict=blocked`，既有 handoff 字段投影没有相应映射，提交报 `field_projection_unavailable`。在实施前源码隔离副本也复现，见 `check-1789536943767932499.log`。本轮没有改该 review 合同；不能把“未知引用修正通过”当成这个缺陷已消失。建议单独最小修复，勿放宽所有校验。
3. **旧测试维护问题**：collection schedule stub 缺 execution_profile、Root 私有调用绕过已存在的配置步骤、旧列表结束标记和旧默认全量输出预期；受影响消费者测试已调整。debug 私有目录 symlink 被正确拒绝，但旧测试要求消息含 unavailable，基线同样不满足（`check-1789538106630431726.log`）；未改安全边界来满足文本断言。
4. 未跑全量套件、真实远端 TCAD、浏览器完整人工审批流程。此次 UI/facade 没有新增数据语义，关键读路径和审批合同漂移负控已覆盖；这不等同于全生产平台验收。
