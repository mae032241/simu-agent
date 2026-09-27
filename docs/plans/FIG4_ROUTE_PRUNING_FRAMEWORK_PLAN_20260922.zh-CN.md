# Fig.4 路线剪枝框架实施计划

状态：**历史 R0 提案；[R0 独立审查 REVISE](reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R0_REVIEW_20260922.zh-CN.md)，由 [R1 独立修订提案](FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R1_20260922.zh-CN.md)接管；未实施、未部署**。
日期：2026-09-22。
范围：解决“科学结论为 `inconclusive/claim_allowed=false`，但局部微调价值与路线处置没有结构化表达或机械约束”的框架缺口。本文不把 Fig.4 的误差数值固化为通用科学阈值，也不改写既有封存结果。

## 1. 根因与目标

当前 `LayeredDiagnosisReport` 的 `objective_assessment`、`next_action` 均可省略，`recommended_task_mode` 只是无约束兼容字符串；`RoleHandoff` / `SchedulerSignal` 只投影 verdict、摘要和自由文本建议。通用及 TCAD analysis validator 只校验计划身份、证据引用和计算收据，没有校验“继续同路线是否值得”。

因此：

- `inconclusive` 同时承载“机制尚未证伪”和“当前微调路线不值得继续”，信息被压扁；
- prompt 即使要求判断，Worker 仍可合法省略，control、scheduler、UI 也无法可靠消费；
- `experiment_key` 标识实验，不足以跨计划修订识别同一科学策略，改名即可绕过重复微调判断；
- scheduler 只能从自由文本重新推理，容易把“未严格证伪”误读为“继续调参”。

只改 prompt 不足以解决问题：prompt 不能改变 JSON Schema、提交校验、历史兼容、准入门、UI 或回归测试，也不能阻止合法但缺字段的输出。

## 2. 权责边界

- **Analysis Worker**：依据冻结计划和证据判断目标符合度、局部微调价值、路线处置和需要的变化；不得输出后继 Operation 名称。
- **Control**：验证字段组合、证据 alias、计划停止条件、路线身份和是否出现新证据；不得根据误差大小创造科学结论。
- **Scheduler**：读取正式报告与 signal，从唯一 compiled catalog 选择 public Operation；服从同路线门禁，但不把建议当命令，也不制造科学事实。
- **Independent critic**：假设集合新增、删除或替换后必须重新审查；旧 critic verdict 不继承。
- **UI**：并列展示科学可信度、目标符合度、路线处置和变化类别；不得从摘要文本推导状态。

## 3. Typed contract

在新版本 `LayeredDiagnosisReport` 中增加必填的路线继续性判断；历史版本保持可读：

```json
{
  "continuation_assessment": {
    "branch_key": "stable-id",
    "strategy_key": "stable-id",
    "local_refinement_value": "justified|not_justified|unknown",
    "tested_route_disposition": "continue|prune|defer",
    "required_change": "none|new_hypothesis|model_redesign|new_evidence|numerical_repair|stop",
    "stop_condition_keys_triggered": [],
    "evidence_keys": ["exact_alias"],
    "rationale": "evidence-bound judgment"
  }
}
```

约束：

- `continue` 必须对应 `justified + none`；
- `prune` 必须对应 `not_justified + new_hypothesis/model_redesign/stop`；
- `defer` 必须对应 `unknown + new_evidence/numerical_repair`；
- 每项 assessment 至少引用一个可解析证据；触发的停止条件必须存在于冻结计划；
- `objective_assessment.status=fail` 和 `prune` 均须有证据；
- 明确允许 `overall_verdict=inconclusive` 与 `tested_route_disposition=prune` 同时成立；
- `invalid_study` 不得仅因数值失败自动剪枝物理路线；
- 不设置通用误差阈值，Fig.4 数值仅作为回归场景的冻结证据。

Worker 只在 payload 中作者一次；finalizer 将紧凑字段机械投影到 `RoleHandoff`，`run_outputs` 再投影到 `SchedulerSignal`，不得改写 rationale 或生成 Operation 名。Signal 只提供导航和决策注意标记，不取得路由权。

## 4. 稳定身份与机械门

新 hypothesis proposal 增加稳定 `branch_key`；新 skeleton、design intent、portfolio 增加稳定 `strategy_key`。修订必须保留 key；假设集合变化必须产生新 branch；模型重设计必须产生新 strategy。Control 计算：

```text
route_fingerprint = SHA256(objective identity, branch_key, strategy_key)
```

同路线 continuation Operation 必须绑定当前 assessment。若 disposition 为 `prune`，无新证据的同 fingerprint 参数微调在 preflight 与 invoke 中以相同原因拒绝，并返回准确路径；只允许新 branch、新 strategy 或停止。`defer/numerical_repair` 只允许能改变执行有效性的修复。

重新开放旧路线必须引用旧 assessment，并绑定至少一个旧 assessment 未使用的新 Artifact ref，再由新的 Analysis Worker 判断。路线索引只能是 sealed report 的可重建投影，不能成为第二科学真相或额外工作流状态机。

## 5. 工作包与文件面

### WP0：冻结基线

冻结 Fig.4 fixture、before candidate、Operation digest、判题标准与 token 计量边界。保存当前真实事实：总体 `inconclusive`、`claim_allowed=false`、绝对形貌未恢复，以及用户原文；不把用户判断改写成机械科学阈值。

### WP1：Schema 与投影

主要文件面：

- `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py`
- `src/scidiscovery/artifact_agent/schema/cognitive.py`
- `src/scidiscovery/artifact_agent/schema/experiment.py`
- `src/scidiscovery/artifact_agent/schema/experiment_intent.py`
- `src/scidiscovery/artifact_agent/schema/role_result.py`
- `src/scidiscovery/artifact_agent/schema/run_signal.py`
- `src/scidiscovery/artifact_agent/service/result_materialization.py`
- `src/scidiscovery/artifact_agent/service/run_outputs.py`

采用新版本输出合同，保留旧 Artifact 的宽松读取，避免原地改变既有 Schema 语义。

### WP2：Analysis 合同

更新通用曲线分析和 TCAD result analysis 的 prompt、schema resource、validator 与 semantic contract。要求 Worker 显式区分科学证伪、目标失败、研究价值剪枝和纯数值无效。

主要文件面：

- `plugins/curve_score/curve_score/science_operations.py`
- `plugins/curve_score/curve_score/analysis_workspace.py`
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py`

### WP3：路线准入门

在 operation declaration / contract 编译层定义唯一 continuation guard，供 preflight 与 invoke 共用，禁止两条入口漂移。它只执行封存 disposition 与 route fingerprint，不自行判断科学误差。

主要文件面：

- `src/scidiscovery/general_science_agent_operations.py`
- `src/scidiscovery/general_science_experiment_operations.py`
- `src/scidiscovery/general_science_experiment_components.py`
- `src/scidiscovery/operation_contract.py`
- `src/scidiscovery/operation_declaration.py`
- `src/scidiscovery/operations/spec.py`
- `src/scidiscovery/operations/invoke.py`

### WP4：Scheduler 与 UI

更新 scheduler 源指南，要求先读正式科学结论、目标判断和 continuation assessment，再选择 public Operation。禁止把 free-text `next_action` 当命令。UI 的 Run、Artifact、Approval 三入口展示同一四轴状态：科学可信度、目标符合度、路线处置、变化类别。

主要文件面：

- `roles/scheduler.md`
- `roles/scheduler/research.md`
- `roles/scheduler/results.md`
- `.codex` 指南的生成源与安装投影
- `src/scidiscovery/general_science_views.py`
- `src/scidiscovery/artifact_agent/approval_ui/presentation.py`
- `src/scidiscovery/artifact_agent/approval_ui/presentation_render.py`

`run_status(response_profile="decision")` 支持直接选择 `/continuation_assessment`，但不自动选择下一 Operation。

### WP5：文档、安装与现场验收

同步双语 architecture、plans index、生成配置与安装清单；构建隔离 wheel，并通过真实 stdio/MCP 和浏览器入口检查。计划实施后必须另行独立实现审查；本提案本身不宣称实现或资格通过。

## 6. 迁移与回滚

- 新字段对历史记录可缺失，对新生产合同必填；提升受影响 Operation version 或 configuration identity。
- 旧 Artifact 字节不改，显示 `legacy/no route assessment`，不施加跨修订剪枝硬门。
- 必要时使用 exact plan ref + `experiment_key` 构造仅限原计划的 legacy fingerprint，不把它提升为跨策略稳定身份。
- 回滚按 WP 逆序关闭 guard、UI 投影和新生产合同；保留新字段的宽松读取，绝不删除已封存报告或恢复旧资格。
- 部署失败回滚 wheel/config，不迁移数据库中的科学内容。

## 7. 回归与验收矩阵

| 场景 | 预期 |
|---|---|
| `inconclusive + prune + model_redesign`，证据完整 | 接受并展示四轴状态 |
| `inconclusive + continue`，证据支持局部闭合路径 | 接受，证明框架不强制剪枝 |
| prune 缺证据、伪造 stop key、字段组合冲突 | 精确拒绝 |
| 同 fingerprint、prune 后无新证据微调 | preflight/invoke 同因拒绝 |
| 新 strategy 的模型重设计 | 允许 |
| 新 hypothesis 集合但无独立 critic | 拒绝 |
| `invalid_study` 仅有求解失败却声称物理 prune | 拒绝或要求改为 defer |
| 历史无 assessment 的 v1 Artifact | 可读、无错误硬门 |
| UI Run/Artifact/Approval | 一致展示，不改科学字节 |

最小可信测试覆盖 schema、materialization、signal、通用/TCAD analysis validator、catalog compile、installed entrypoint、preflight/invoke 一致性、历史兼容、UI 三入口和隔离安装。

Live acceptance 在绑定实例中新建一条基于既有 Fig.4 证据的分析，不重跑 TCAD；由 Worker 自主判断。验收目标是框架能够表达并执行 `prune`，不是预设 Worker 必须迎合用户结论。

## 8. Token 与上下文测量

WP0 固定 before/after 代码、任务、输入、模型、effort、工具和计量脚本；至少两对交替、全新线程、串行运行。分别记录 Root 与 compiled Worker 的首次/峰值/末次 input tokens、峰值增长、净增长、output tokens、请求数、schema/prompt/工具可见字节、重复读取和 compaction。

先证明科学输出、错误诊断和路由等价，再比较成本。新增 typed 字段可能增加 Worker schema/output，但应减少 Root 展开全文和自由文本再推理；两者必须分别报告。cached 累计不得当作窗口体积。平台未暴露的 collaboration subagent token 必须记录为“不可观测”，不得估算或用上下文百分比代替。

## 9. 未决问题

1. `branch_key/strategy_key` 应由哪一个现有科学对象首次作者，才能避免 control 生成科学身份；实施前必须冻结唯一 owner。
2. `prune` 是仅禁止参数微调，还是也禁止同策略的数值资格修复；需要用 `required_change` 和 Operation 分类精确限定。
3. 整个假设分支的永久淘汰是否需要额外独立 review，还是“新假设组合必须重新 critic”已足够；不得用 chat 代替正式审查。
4. v1→新版本的 operation migration 是并行保留还是原位版本提升；必须先验证历史 producer/input admission。
