# 表格观测插件

这是 H2b 的非曲线盲接入样例。它只通过统一 `scidiscovery.plugins` 入口注册两个
公共 Operation 和一个领域 Worker 工具；核心、通用调度器、UI 与部署代码均不知道表格领域。

- `science.table.observation.analyze.v1`：读取通用实验计划和 CSV，调用确定性表格摘要工具，
  由 Agent 形成有界观测；
- `science.table.observation.review.v1`：独立复核观测与原表一致性及结论边界。

该插件不注册新路由器、Schema 注册表、状态机或规划器。
