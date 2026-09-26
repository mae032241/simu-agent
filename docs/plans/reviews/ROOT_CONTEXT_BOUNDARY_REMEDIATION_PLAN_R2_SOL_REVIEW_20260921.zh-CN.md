# Root 上下文边界修复计划 R2 独立 SOL 复审（2026-09-21）

结论：**PASS**。

复审对象及身份：

- R2 计划：`docs/plans/ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_20260921.zh-CN.md`
- R2 SHA-256：`8f727cb470fd3df4631a39d2e85674015a02721c197276cc8a02a6ba0f786851`
- R1 快照 SHA-256：`282b690a19c28bec5c41db90affc4020f86945b8675e1af209f74250e4750ef2`
- R2 修订 manifest SHA-256：`0221acb9a204ff58fc1c95a167de637db55f2049e52194b15c37182d72bbd533`

三个哈希均与复审任务给定值一致，manifest 与 R1→R2 实际差异相符。本轮只复核 R1 唯一剩余的 compact recovery P1 及其直接影响，没有重开已通过的 producer、invoke、replay 和新路径采用率四组审查。

R2 已闭合剩余阻断：

1. 所有 failed compact 响应保留 `delivery_preserved`、`resume_available`、`draft_available`、`recovery_pending` 和条件性的 `original_retained`，因此 compact profile 不再把不同恢复 gate 合并成一个 `recovery_available=false`。
2. 没有 durable diagnostic event 的恢复失败由控制已有 recovery record 派生 allowlist `reason_code`；未知值稳定映射为 `other`，不透传自由文本、draft、路径或工作区内容。该设计是只读投影，不增加数据库字段、恢复状态或算法。
3. output rejection、tool failure 和 framework failure 继续走现有 summary + event/reference；recovery failure 走 compact gate + allowlist code，必要时才使用受控 compat detail。两类诊断责任不再混淆。
4. `diagnostic_after` 语义已与当前接口一致：省略时无 events，`0` 为第一页，后续使用 `next_after`。
5. golden 明确覆盖 recovery pending、保存 draft 但不可 resume、writers unconfirmed、snapshot unavailable，以及省略/0/后续 diagnostic page；同时要求 compact 与 compat 对恢复 gate 判读一致且不展开 recovery payload。

该修订没有改变默认 compat、SchedulerSignal、sealed payload、Run/recovery 生命周期、独立 review、approval、currentness、总体目标引用或原始诊断入口，也没有引入第二合同、递归 lineage 或控制状态机。结合 R1 已确认关闭的四组问题，计划已具备工程实施所需的边界、兼容策略和可量化验收条件。

本 PASS 仅批准计划进入实现与其规定的分批验证，不代表代码已经实现、安装已更新或真实模型 token 收益已经成立。实现仍须按计划串行执行 P0/P1/P2/P3/P5、独立跨边界复审、安装/runner 探针和后续单独授权的 matched A/B。

本轮未运行模型、solver、科学 Operation、Fig4、部署或测试，未修改计划和生产代码；唯一新增文件是本复审报告。
