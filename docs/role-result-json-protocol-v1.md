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

角色必须先读取 `assignment.json` 和 `schema/output.schema.json`，并使用原生只读
文件/检索能力查看其中明确声明的任务路径；不得从共享 workspace 根目录递归搜索。
所有变更通过当前 worker session 绑定的 `worker_file_*` 接口写入
`output/result.json`。该暂存文件必须使用稳定的两空格缩进、多行 JSON，禁止把非平凡
结果压缩成单行；控制面拒绝任何超过 24576 bytes 的 JSON 物理行。嵌套 JSON 的局部
修订优先使用 `worker_file_json_patch`：只支持有界 `test/add/replace/remove` JSON Pointer，
以当前内容摘要或精确 `test` 作为 CAS 前提，并在一次调用内 parse、全部应用、大小检查和
原子替换；任一 operation 失败时文件字节不变。JSON 数值类型在 round-trip 中保持为
integer 或 float，显式浮点不会变成 strict integer。文本/solver 文件继续使用标准 unified diff；短 diff 直接 apply，长 diff
通过 `operation=patch` 分块上传后应用。只有尚不存在的文件可用
`operation=create` 分块新建，已有文件不能全文覆盖。PDF、曲线、日志、图片和表格保存在
`inputs/` 中，不嵌入结果 JSON；结果只使用任务内的 `source_name` 和精确定位信息
引用它们。

只有 assignment 显式声明附件 collection profile 的角色可以通过 `worker_file_*`
或受控 analysis output mount 另外写入：

```text
output/bundle.json
output/collections/<collection>/<item>
```

`bundle.json` 只声明任务内的 collection、item、media type 和相对路径。文件数量、
单项大小、总大小、允许的 media type 和必需项都由 assignment 给出的严格 Schema 与
collection 规格限定。未启用 profile 的角色仍只能写 `output/result.json`；启用 profile
时，未声明文件、路径穿越、符号链接、重复项、错误类型和任何越界均使整个提交失败，
不会登记部分附件。

启用 collection 的 `worker_run_analysis` 将完整输出目录挂载为 `/outputs`，将已安装的
确定性论文图工具只读挂载为 `/tools/digitize_plot.py`，CSV/证据包校验器只读挂载为
`/tools/validate_evidence_bundle.py`。分析代码可写
`/outputs/result.json`、`/outputs/bundle.json` 和 `/outputs/collections/...`；分析阶段
立即执行上限检查，必需项和精确集合在 validate/finalize 时检查。

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
    "next_actions": [],
    "evidence_bundle_fingerprint_sha256": null
  },
  "payload": {}
}
```

- `handoff` 只供调度使用，不承载详细科学报告。
- `payload` 是角色专用严格表单，其完整 JSON Schema 随任务提供。
- `schema_version`、`handoff` 和 `payload` 都必须显式填写。
- 裸 payload、额外字段、错误字段类型和未声明的证据来源均在登记前被拒绝。
- `evidence_bundle_fingerprint_sha256` 通常为 `null`；启用
  `scientific-paper-evidence` collection profile 时必须填写为对最终 staged
  collections 重新运行确定性 validator 得到的精确 bundle fingerprint。

## 角色 Payload

| 角色 | Payload | 主要内容 |
|---|---|---|
| `evidence_extractor` | `ScientificIntake` | 问题框架和有来源的基础资料 |
| `ideator` | `HypothesisProposal` | 互相区分、可证伪的假设及预测 |
| `critic` | `CriticReview` | 物理合理性、可证伪性和可识别性审查 |
| `evidence_auditor` | `EvidenceAudit` | 参数、结构、结果和结论的证据核验 |
| `experiment_designer` | `ExperimentDesignIntent` | 最小判别实验的科学选择；控制层展开完整计划和机械验收字段 |
| `diagnostician` | `LayeredDiagnosisReport` | 数值、实现、物理和观测层诊断 |
| `tcad_deck_author` | `DeckProjectDraft` | 完整可运行工程及实现清单 |
| `tcad_deck_reviewer` | `DeckReviewReport` | 物理实现和代码一致性独立复核 |
| `tcad_deck_author`（revision profile） | `DeckProjectDraft` | 在任务私有文件沙箱中直接修订后的完整有效项目；控制面生成规范对象与差异 |

`evidence_extractor` 遇到支撑定量陈述的论文图时必须使用
`$scientific-paper-evidence`。主 `ScientificIntake` 继续只保存问题框架和来源化科学
基础；像素级证据保存为受限附件：恰好一个
`scidiscovery.figure-evidence-manifest.v1` manifest，以及 assignment 允许的源图/面板
PNG、JPEG 或 WebP、PNG 审计叠加图和逐系列 CSV。每个系列必须显式绑定可见图例、
图内标注或 caption，并记录绑定来源、可见文字、置信度、备选项和
`matched|unresolved` 状态。无法唯一绑定、坐标无法标定或遮挡无法量化时必须记录为
`unresolved`，不得猜测身份或据此给出已合格的定量结论。

角色专用表单可以不同，因为科学职责不同；统一的是外层交接方式、来源引用规则和
文件传输边界，而不是把所有科学内容压成同一个宽松对象。

## 控制面处理

1. 按 assignment 中的精确 Schema 校验整个信封。
2. 按角色的专用 Schema 再校验 `payload`。
3. 校验 payload 中的任务内来源引用和冻结网页证据。
4. 若启用了 collection profile，校验完整 `bundle.json`、所有声明文件及整体上限；figure
   manifest 的 provenance 还必须逐项匹配所有 sibling 的 SHA-256、字节数和 media type。
   对论文图证据，控制面还会打开逐系列 CSV，重算行数、标定值、资格标志和共享像素，
   并登记控制面生成的 `validation_reports/validation_report.json`；Worker 文本中的计数
   不参与此判定。figure handoff 的 fingerprint 必须匹配该报告，且
   `assumptions`/`missing_inputs`/`next_actions` 必须为空；科学假设保留在
   payload/manifest，控制面从最终 manifest 和固定 audit 动作投影调度字段，防止早期
   提取轮次的结论污染最终调度信号。
5. 原子完成规范化后的 `payload`、附件和归一化 bundle 映射；任一失败都不产生可枚举的部分结果。
6. 从 `handoff` 确定性生成有界调度信号；figure evidence 的摘要、missing inputs 和
   audit 动作以最终注册 manifest/report 为准。
7. 下游角色只获得控制面按输入画像选择的 Artifact，不获得上游任务身份。

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
6. 启用附件的角色继续通过 `worker_validate_output_file` 和
   `worker_finalize_file` 完成同一文件生命周期；不建立第二套完成状态机。
7. 公共 Worker MCP 不再暴露主结果的 begin/append/commit 文本上传工具；旧调用仅在
   兼容路由中保留，不进入新生成的 Agent 配置。
8. 全量自动化测试通过后才部署。
