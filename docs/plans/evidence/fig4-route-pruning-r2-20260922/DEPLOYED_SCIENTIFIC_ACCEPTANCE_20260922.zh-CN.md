# Fig.4 路线剪枝 R2：部署后科学行为验收

- 日期：2026-09-22
- 实例：`M7-test0`
- 结论：**进行中；真实分析通过，首次调度分支判断失败，假设重设计尚未完成。**
- 新 Run：`fig4_route_pruning_acceptance_20260922_1`
- 正式输出：`fig4_route_pruning_acceptance_20260922_1.output`

## 验收边界

从既有正式节点 `fig4_retardation_frozen_metrics_20260921_1.output` 的即时 producer 投影恢复 30 项冻结输入；分页完整，无名称猜测或全实例展开。输入包括原实验计划、科学骨架、综合执行审查、reviewed package、execution result/runtime manifest、九条 PLX、诊断、参考材料及相关封存进展。

调用当前安装的 `tcad.result.analyze.v1` version 2，冻结执行配置为 `gpt-5.6-sol`、`medium`、`zh-CN`。Run 正常完成。未创建 execution，未运行 TCAD/solver，未重新拟合原始证据。

## 正式结果

封存报告给出 `objective.fig4_mechanism_discrimination` 的 `objective_assessment.status=inconclusive`，`overall_verdict=inconclusive`，`claim_allowed=false`。它保留两个 `N_T*K≈1` 点作为“单终态模型反事实”，没有把有限改善误写成总体机制成功，也没有把失败执行直接写成物理反证。

报告同时明确：继续同类 `N_T/K` 微调最多细化候选脊，不能改变“总体机制判别仍不成立”的决定；能够改变总体目标判断的是第二时长或去源再退火 profile、恢复材料覆盖并做冻结参数预测。正式联合门的现有数据后处理缺口仍保留，但即便补齐，也不能解决单一材料、单一时刻的可识别性缺口。

## Root 首次调度错误与修正

用户预先给定的验收分支为：若下一轮目标是假设重设计，则完成重设计；若是实验设计或 author 改进，则停在当前节点。

Root 首次把上述下一目标判定为实验设计重构并宣布停在分析节点；该判断**不通过验收**。错误不是 Worker 科学结论缺失，而是 Root 锚定了报告的实验建议，只检查“当前假设是否被证伪”，没有先检查“当前正式假设集合是否覆盖报告提出的表面历史竞争解释”。`inconclusive` 且无 falsifier 不证明假设集合充分。

修正后的调度规则是：当 `remaining_contradiction` 提出决策相关竞争解释时，先沿精确 producer 输入恢复当前 hypothesis portfolio；未形式化的竞争解释进入 bounded hypothesis proposal/evolution，已形式化但缺判别观测才进入实验设计，假设与设计充分但实现有缺陷才进入 author 改进。Worker 的建议和 `next_action` 不替代此检查。

精确恢复确认当前正式组合为 `fig4_postfinite_hypothesis_evolution_20260921_1.output`；假设重设计 Run `fig4_hypothesis_redesign_20260922_1` 因冻结模型名 `gpt-6-Astra` 与平台身份 `gpt-6-astra` 大小写不一致而未能打开 assignment。该控制层阻碍不是科学失败；本轮在成功完成假设重设计及所需编译审查前不标记最终 PASS。

## 上下文与 token

- Root 精确 token：平台未暴露，**不可观测，未估算**。
- 科学 Worker 精确 token：平台未暴露，**不可观测，未估算**。
- 本轮科学 Worker：1；独立审查 Agent：0。
- Root 曾一次性预读五份阶段指南并过宽返回 producer 明细，造成可见上下文浪费；字符或上下文比例不换算成 token。
- 已在 `roles/scheduler.md` 登记：指南按下一实际动作懒加载，禁止预读未来阶段，同一安装版本维护复用台账。

## 未宣称

本次记录不表示 Fig.4 科学目标完成、不证明机制真假、不证明实验设计质量，也不覆盖 token A/B、全量测试或新外部执行。当前只证明部署后的分析能够识别“继续微调不改变总体决定”；首次 Root 路由未先检查假设集合覆盖，最终行为验收仍待假设重设计闭合。
