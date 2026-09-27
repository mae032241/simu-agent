# R5-S S0 方案与基线首轮独立审查

日期：2026-08-31  
审查对象：`R5_S_PRODUCTION_CODE_SIMPLIFICATION_PLAN.zh-CN.md` 首轮冻结候选  
候选摘要：`dd756b5ad20f5bf0c343b703cdd94759e18bd8117147fd84e549530592d2fe6a`  
审查边界：只判断 S0 是否完成并只放行 S1；不参与实现，不修改候选，不审查后续实现结果

## 结论

**打回。S0 不能通过，不能放行 S1。**

S1 的三个候选方向成立：架构测试插件、table observation 证明插件和未启用 Worker 进程实验均未
发现正式运行入口，适合移出生产包。但总体方案有四项阻断，必须修订后重新独立复审。

## 阻断一：S2 扩大原生写权限缺口

首轮方案允许 Agent 使用原生工具写任务目录，同时移除受控写入协议。但当前 `spawn_agent` 没有
任务目录级操作系统沙箱，原生工具可以触及父工作区；最终提交只能拒绝发布非法结果，不能阻止 Agent
提前修改其他任务或源码。

这与设计宪章中的服务端受控文件操作冲突，也使跨任务写入负例无法由控制面真正执行，并扩大
`SEC-002` 已知问题。

要求：任务级操作系统沙箱完成前保留服务端受控写入。可以合并校验和完成、压缩编辑工具，但不能
仅靠提示词改用原生写入；原生写入只能在 Worker V2 隔离完成后另行放行。

## 阻断二：S3 误删消费端输入语义

首轮方案同时删除 `InputPortSpec.usage` 和 `OutputPortSpec.allowed_input_usages`。后者是过重的生产者
下游授权；前者仍承担真实责任：

- 投影到 Worker assignment，区分 `claim_evidence`、`revision_base` 和 `change_request`；
- 纳入任务授权摘要；
- 防止 Transform 把非证据输入机械晋级为合格主张。

相关路径为 `operations/spec.py`、`artifact_agent/schema/task.py`、
`artifact_agent/service/task_worker_files.py` 和 `operations/invoke.py`。全部删除会使旧修订底稿可能被
当作独立证据，并破坏非资格传播，危及 `EVD-001`、`IMM-002`、`LIN-002` 和 `AUTH-003`。

要求：删除 output allowed usages 和生产者侧用途准入；保留由消费 Operation 声明、Worker 可见的
输入认识论角色。它只说明当前输入在本行为中的责任，不授权未来下游。

## 阻断三：`scheduler_sessions` 是不可推导事实

`scheduler_sessions` 保存 `session_key → instance_id` 的最终选择，不能从 ResearchInstance 推导。
`instance_current` 依靠它在重启后恢复当前实例，生产消费者位于 `scheduler_bindings.py` 和
`mcp_root_instance_routes.py`。

要求：实例提案、候选和 Approval 复用可以删除，但最终 session 绑定必须保留为唯一持久事实，不能
移入内存、换表重建或建立第二 current。

## 阻断四：S0 精确冻结不足

首轮方案只统计核心树的 30 张表，漏掉 TCAD 插件的 `submissions`、`tcad_debug_leases` 和
`tcad_debug_runs`，全生产树实际共有 33 个唯一建表名称。

此外，候选以提交叠加大量未提交工作树为基线，却没有可重建的文件清单或检查点；开始 S1 后无法
可靠区分阶段前后变化。

要求：冻结生产源文件摘要清单、33 张表名、目录摘要和可重放测试命令，或建立明确本地检查点。

## 已核验正确的事实

- 150 个生产 Python 文件、59,200 行；
- 核心 34,840 行；
- 239 个组件、48 个 Operation；
- 28 public、20 support；
- 24 Agent、20 Transform、3 Approval、1 Effect；
- 225 个输入端口、66 个输出端口；
- 组件种类和四种目录组合统计正确；
- S5 合并数据合同、逐项审计 support Operation 的方向合理；
- S1 三个移出生产面的候选方向正确。

## 复审要求

四项阻断全部按最小边界修订后，必须以新候选重新进行独立 S0 审查。本文结论绑定首轮摘要，不因
后续文件变化自动转为通过，也不授权任何生产代码修改。
