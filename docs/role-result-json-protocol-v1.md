# 角色结果 JSON 协议 v1

## 目的

所有科学 Worker 使用同一种文件通信方式。角色只填写科学内容和一个小型交接表；
控制面负责身份、状态、校验、不可变登记和调度信号，不要求角色抄写任何 ID 或哈希。

## 固定文件

每个任务的控制面工作目录为：

```text
task-workspace/
├── assignment.json
├── inputs/
├── schema/output.schema.json
└── output/result.json
```

角色必须先读取 `assignment.json` 和 `schema/output.schema.json`，然后只写一个
`output/result.json`。PDF、曲线、日志、图片和表格保存在 `inputs/` 中，不嵌入结果
JSON；结果只使用任务内的 `source_name` 和精确定位信息引用它们。

## 统一信封

每个角色都填写相同的外层结构：

```json
{
  "schema_version": 1,
  "handoff": {
    "verdict": "pass",
    "summary": "本角色的一句话结论",
    "assumptions": [],
    "missing_inputs": [],
    "next_actions": []
  },
  "payload": {}
}
```

- `handoff` 只供调度使用，不承载详细科学报告。
- `payload` 是角色专用严格表单，其完整 JSON Schema 随任务提供。
- `schema_version`、`handoff` 和 `payload` 都必须显式填写。
- 裸 payload、额外字段、错误字段类型和未声明的证据来源均在登记前被拒绝。

## 角色 Payload

| 角色 | Payload | 主要内容 |
|---|---|---|
| `evidence_extractor` | `ScientificIntake` | 问题框架和有来源的基础资料 |
| `ideator` | `HypothesisProposal` | 互相区分、可证伪的假设及预测 |
| `critic` | `CriticReview` | 物理合理性、可证伪性和可识别性审查 |
| `evidence_auditor` | `EvidenceAudit` | 参数、结构、结果和结论的证据核验 |
| `experiment_designer` | `ExperimentPortfolio` | 最小判别实验、变量、对照和验收条件 |
| `diagnostician` | `LayeredDiagnosisReport` | 数值、实现、物理和观测层诊断 |
| `tcad_deck_author` | `DeckProjectDraft` | 完整可运行工程及实现清单 |
| `tcad_deck_reviewer` | `DeckReviewReport` | 物理实现和代码一致性独立复核 |
| `tcad_deck_reviser` | `DeckProjectPatch` | 针对审查意见的有界补丁 |

角色专用表单可以不同，因为科学职责不同；统一的是外层交接方式、来源引用规则和
文件传输边界，而不是把所有科学内容压成同一个宽松对象。

## 控制面处理

1. 按 assignment 中的精确 Schema 校验整个信封。
2. 按角色的专用 Schema 再校验 `payload`。
3. 校验 payload 中的任务内来源引用和冻结网页证据。
4. 只把规范化后的 `payload` 登记为下游科学 Artifact。
5. 从 `handoff` 确定性生成有界调度信号。
6. 下游角色只获得控制面按输入画像选择的 Artifact，不获得上游任务身份。

## Clean Break

本协议不读取旧认知角色格式，不接收裸 `HypothesisPortfolio`、`ScientificReview`
或 `DecisionPacket`，也不根据旧字段猜测新字段。部署新版后，未完成的旧任务应丢弃
并在新实例中重新派发；历史数据库不是新科学任务的输入。

## 验收

1. 所有 Worker 角色的 assignment 都暴露 `RoleResultEnvelope[专用类型]`。
2. 裸 payload 必须失败。
3. Worker 不提交独立 scheduler signal。
4. 控制面登记的科学 Artifact 不含 `handoff`。
5. 所有来源引用在登记前完成绑定校验。
6. 全量自动化测试通过后才部署。
