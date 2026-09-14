# Agent 信息交接实现独立审查（基线 096a13f）

日期：2026-09-14。审查对象：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2` 当前工作树相对检查点 `096a13f` 的 P1—P5 增量，以已通过 R1 计划为准。

**结论：需修订一项错误诊断边界；正常交接路径及其余四项未发现阻断性缺陷。** 此为实现静态审查，不表示测试或安装通过。

本次只读源码、计划、精确 diff 和相关测试源文件；未运行测试、编译或 solver，未调用科学控制面/Worker，未读取实际运行目录，未派生 Agent，未修改仓库文件。沿用跨边界审查与简化审查技能。父侧独立运行定向检查及安装验证，其口头通过数不作为本报告独立测试证据。

## 必须修正：省略 handoff 的草稿中，正式字段错误被机械字段缺失掩盖

**位置：**

- `src/scidiscovery/artifact_agent/service/result_materialization.py:59—66,86—88`。
- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:611—627`（已包含本次审查中父侧新增的 `isinstance(verdict, str)` 修正）。
- 下游控制边界：`src/scidiscovery/artifact_agent/service/run_outputs.py:120—128`。
- 对应 R1：P4 第 124—132 行的可省略机械字段、同一封存 Schema、非法正式 verdict/summary 具有准确输出诊断；P4 的目标同时要求不把机械补写交给 Worker。

**可达场景：**

1. TCAD reviewer 从新默认 `review-template.json` 起步，handoff 没有 summary/verdict，正式 payload 已有摘要，但把 `payload.verdict` 写成 `[]` 或无效字符串。
2. 当前 `finalize_review_workspace` 对无效正式 verdict 不生成 handoff；`materialize_summary_handoff` 在 verdict 不可映射或正式 summary 不是字符串时也直接返回。
3. `validate_run_output` 先调用 `parse_role_result(decoded)`，其中 payload 为 Any，尚未检查正式 payload Schema；因此结果先停在 `$.handoff.verdict`、`$.handoff.summary` 或 `$.handoff` 缺失，无法给出真正的 `$.payload.verdict`/`$.payload.summary` 错误。

ScientificReview 的新无 handoff 草稿遇到同样的正式字段错误也经过此路径。gap 先用 ImplementationGap 模型校验正式 payload，因此该具体问题不影响 gap summary 错误定位。

**影响：** Run 不会错误完成，但 Worker 按合法的新草稿合同省略机械字段后，收到的诊断却要求补写这些字段；容易导致额外提交循环或重新写第二份摘要。正常正例通过不能证明此边界符合 R1。

**最小修正：** 在机械字段无法由其正式来源生成时，给出指向正式来源的有界可修订诊断；保持科学原值不变、严格封存 Schema 不变，不添加新的科学结论或第二套完整草稿验证器。不要仅在负例中手工补齐 handoff 绕过默认入口。

**必要验收：** 保留新增的真实 TCAD 默认模板负例（`test_tcad_gap_continuation.py:234—240`）：错误正式 verdict 必须 rejected 且包含 `$.payload.verdict`，随后同一 Run 修正正式值即可完成。用现有 ScientificReview 提交用例覆盖同样的无 handoff 草稿，以及一个正式 summary 错类型；无需扩大到全部输出类型或全量测试。

**本次已修正的前置问题：** 初读代码在 TCAD finalizer 中直接执行 `payload.get('verdict') in {…}`，`[]`/`{}` 会触发 TypeError，经 `runs.py:1039—1040,548—561` 变成 Run failed。父侧已加入字符串类型判断，独立复核确认该异常入口消除。当前剩余问题是上述诊断来源，而不是仍存在相同 TypeError。

## 已核对且未发现阻断问题的边界

| 项目 | 具体核对结论 |
| --- | --- |
| P1 源码说明交付 | 作者角色把探针对应关系及未测 reset 范围移至正式源码注释，并明确在最终诊断前写入；reviewer 从当前源码和 attestation 独立核对。现有 source-tree/project 摘要包含注释，完整项目封存及 review 物化路径未变。新增测试确实通过正式 author→submit→review 读取注释，不依赖 Root signal。 |
| P2 Root 省略/选读 | `output_paths=None` 保持旧 sealed_output；`[]` 在 `_sealed_output` 中读取 payload 前返回元数据；completed 门禁、historical 状态、绑定及 signal 保留。selected values 与完整对象分开，null/missing/omitted 区分，指针转义和数组索引规则正确。32 KiB values 与累计 8 KiB 导航分别计量；一层导航保留准确指针、类型、子树大小和遗漏数。完整读取后备及批量选读说明明确，无新增检索或科学摘要。 |
| P3 Local 合同 | 当前 assignment 有合同即给路径/pointer，start_here 成为独立导航；旧无合同 assignment 仍经同一 `_compiled` 身份检查回退，损坏 JSON 不用新合同替换。Hardened 文件未修改且保持内联；相关现有测试覆盖合法 Local/Hardened、旧合同及嵌套 `$defs`。 |
| P4 正常摘要与兼容 | 默认作者 handoff 仅有其他可选字段；gap 可保持模板原样或缺省整个文件。显式旧 summary 用 setdefault 保留，合法 assumptions 等不覆盖；完整项目仍严格要求作者 handoff。ScientificReview、TCAD review、gap 才使用新摘要 helper；CriticReview、EvidenceAudit 无新 handoff 生成，LayeredDiagnosisReport 原行为保留。通用及 TCAD 组件配置身份均已显式变化。 |
| P5 指导可达性 | 三个分析 prompt 只改为短导航；curve 的两个 analysis Operation 绑定 analysis workspace；TCAD materializer 调用同一 workspace 并保留 patch_contract。完整 GUIDANCE 仍在 analysis-start，REPORT_GUIDANCE 仍在 domain patch_contract，恢复新 Run 使用相同入口。没有删除角色科学职责或权限规则。 |

实现范围与 R1 一致，主要是读取投影、角色说明、机械字段 finalizer 和显式组件身份，没有改 Run 存储、solver、审批、科学模型或曲线算法。未发现必须新增其他抽象、工具、状态机或泛化校验的理由。

## 验证与完成边界

已读取的新测试包含真实 submit、未编辑自动模板、显式旧 handoff、损坏 gap、Root 禁止正文读取、历史/未完成状态、导航成本、合同 fallback 和身份传播；它们与计划相关，不是纯粹提示字符串测试。实际测试结果与 wheel/stdio 安装结果由父侧继续记录。

修正唯一剩余诊断问题并通过对应定向负例后，可对该修正作一次窄范围复核；无需重开整个设计或扩大测试矩阵。实际 token 节省仍不能由静态 diff 推定；同一任务的总回复字节/往返与之后平台原始计量按 R1 分别记录。
