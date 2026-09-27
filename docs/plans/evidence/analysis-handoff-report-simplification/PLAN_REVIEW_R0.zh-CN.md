# 分析接手视图与正式报告简化：计划独立审查 R0

日期：2026-09-13。结论：**PASS（工程实施计划通过）**。

未发现要求扩大范围或阻止实施的计划缺陷。R0 已把科学报告简化、默认阅读视图与不可变原件分开，并明确不增加科学覆盖、评分、字数或输入资格门槛。下面列出的接线与边界是对既定 P1—P4 的源码落实说明，不是新增审批条件。计划通过不代表实现、安装或真实 Agent 验收已经通过。

## 1. 审查对象与方法

- 仓库：`123/scidiscovery-e5.2`，HEAD `be5da77acdbf98054e0b096fc4e940de560d4ba1`，按当前 dirty 工作树源码审查；没有将全部 dirty diff 归为本轮修改。
- 计划：`docs/plans/ANALYSIS_HANDOFF_AND_REPORT_SIMPLIFICATION_PLAN.zh-CN.md`，SHA-256 `d7b25fe3a5fbaa0b1d9cf6e0260cc2a2d930bfd397b4ecfb290957bd67574cd6`。
- 基线：同目录下 `BASELINE.json`，SHA-256 `f1084a0260ce591b9174b71bc73e51ba23e673f2366152eb1c3e4f413a470e58`。
- 使用 `scid-cross-boundary-review` 与 `karpathy-guidelines`；只读源码、声明、测试源码和计划证据。没有运行测试，没有导入/编译框架，没有调用科研控制或 Worker 工具，没有读取科研 Run 草稿或隐藏日志。
- 本审查只写本报告。主实施者通报的 68 项基线检查结果不作为本审查独立运行的证据。

## 2. 草稿、finalizer 与封存 Schema：现有机制足够

实际提交顺序位于 `src/scidiscovery/artifact_agent/service/runs.py:1012`：`_validated_candidate` 先调用 `_finalize_workspace`，随后 backend seal，最后 `validate_run_output`。`_finalize_workspace` 在 `runs.py:1158` 调用所编译的 finalizer，并通过 backend `write_primary_output` 写回其结果。最终 envelope 校验到 `service/run_outputs.py:120` 才发生。

因此，计划 §6.1 的“省略 handoff 重复字段→机械补全→完整封存 envelope”能够利用现有顺序实现。`schema/role_result.py:21` 的 handoff verdict/summary 仍可必填，`service/run_assignment.py:159` 仍可生成封存 Schema；无需另造草稿 Schema、修改所有角色的 envelope，或新增预提交校验。现有公共前言 `src/scidiscovery/operation_declaration.py:68` 已说明 Schema 描述封存结果，生成副本可省略。

具体接线必须覆盖三个角色：

| 分析角色 | 当前源码连接 | 既定范围内的最小落实 |
| --- | --- | --- |
| 通用结果分析 | `plugins/curve_score/curve_score/science_operations.py:307` 绑定 `analysis_workspace`；同文件 `:1028` 挂接通用 `RESULT_FINALIZER` | 在 `service/result_materialization.py` 按精确输出 schema 增加分析专用机械投影；共享工作区发布生成字段说明。 |
| TCAD 结果分析 | `plugins/tcad_artifact/tcad_artifact/analysis_bindings.py:178` 的 finalizer 当前仅补 source references | 在这条现有 finalizer 中显式组合共用 handoff 投影与既有引用补全；只改通用 finalizer 不会覆盖 TCAD。 |
| 可选曲线误差分析 | `science_operations.py:344` 当前绑定 `general_science:workspace`；该工作区有通用 finalizer，但没有 analysis materializer，见 `src/scidiscovery/general_science_components.py:464` | 在已有 `science_operations.py` 内改绑既有 `analysis_workspace`，并同步曲线误差分析提示，使其也获得入口及 patch_contract；保留该角色的固定 package/图片输入和无评分工具约束。无需改造全部 general_science 工作区。 |

`WorkspaceMaterializationResult.patch_contract` 在 `src/scidiscovery/operations/workspace.py:55` 是已有映射字段，由 `runs.py:1139` 原样写进 `domain-workspace.json`。它能够直接声明分析草稿可省略的 handoff 字段、唯一科学来源与 finalizer 规则，无需修改核心工作区模型。只在提示中说“可以省略”、却不发布这份工作区声明，不符合已通过计划。

机械补全应只覆盖计划明确重复的 verdict/summary，保留 assumptions、missing_inputs 等其余说明，不进行自然语言去重或据数值猜测结论。非法 overall_verdict 仍交给现有 Schema；不新造默认 pass/inconclusive。summary 采用固定短引用，指明同一 `run_status.sealed_output.payload.summary`，避免把最多 8192 字符的科学结论塞进 2048 字符 handoff。`interfaces/mcp_root_run_routes.py:59` 同时返回 sealed_output 和 scheduler_signal，`:130` 仅在 completed 后读取科学原件，能够支持这一阅读约定。

## 3. 视图预算与原件引用：只压缩展示副本

现有 `analysis_workspace.py:98` 的入口按 UTF-8 JSON 大小预算逐项加入内容，常量为 24 KiB；`analysis_bindings.py:103` 另写 `analysis-bindings.json`，随后再次修改入口。当前 TCAD 视图没有自己的大小预算。因此实施 §4 和 §9 时，应对**最终序列化后的入口与默认 TCAD 视图整体**计量，包含 TCAD 后追加的指针、中文和 JSON 包装；不能仅测 `_start_file` 追加前的长度。32 KiB 是本案效果目标，超出时应降级为已有字段的原件指针和遗漏说明，不产生 Run 拒绝。

特别需要保留以下源码边界：

- `analysis_bindings.source_bindings` 不只是 UI 数据。`result_analysis.py:264` 的评分来源补全、`:429` 的提交上下文检查、`analysis_bindings.py:180` 的 finalizer 都消费它。预算裁剪只能发生在写给 Agent 的阅读副本，不能裁掉此函数供工具和校验消费的完整来源映射，也不能改它的历史 cohort/条件性依据规则。
- `source_bindings` 的历史映射包含 evidence_refs 和 rationale，见 `analysis_bindings.py:56`；极端情况下这些已有说明本身会很长。默认视图可以指向 prior_analysis 原 `source_references` 项，不应把所有历史 basis 表强制复制进紧凑首读文件。
- `service/run_assignment.py:44` 已提供每个可见输入的 alias、description、usage、exposure 和 relative_path，`WorkspaceMaterializationRequest.binding_descriptors` 已有 size_bytes。P1 不需要新增索引服务或原件副本；索引项预算耗尽后仍可指向完整 assignment 输入索引，并说明遗漏。
- TCAD 源码正文真实位置是 reviewed_package 的 `/project/files/<index>/content`；`project_packager.py:68` 声明的是嵌入内容，不意味着 workspace 已有同名实体源码文件。源码索引应给原 alias、冻结输入路径及这个 JSON 指针；不能把 `relative_path` 当作已存在的独立本地文件。
- 案例矩阵可从 `experiment.py:106` 的 comparison variables/expectations 确定性转置，保留变量单位、比较角色、等价规则及原位置。矩阵值与原 expectation 逐项对应，不用显示顺序或字符串相似度匹配案例。其他 case settings、purpose 和未展开方法保留原字段指针；若没有 comparison_contract，直接索引原 cases，不能推造一份合同。
- observable 去重只针对原文完全一致的重复项，保留所有原字段位置。公式、阈值和方法即使在摘录中被截短，也必须能读取完整原字段。未知 schema 维持原件索引，不能变成新的准入错误。

平台提示应同时落实首次接手和 Agent 复用：`src/scidiscovery/platforms/codex.py:89` 是显式“reread all current inputs”，`:464` 的初次打开指令也需与“先入口、按需原件”一致。两处均在计划已列的文件范围内。

## 4. 简版与历史报告、claim、后续分析的兼容

`schema/layered_diagnosis.py:163` 当前强制 gates/remaining_contradiction/next_action；其余计划要求保留为可选的诊断字段已经可选。仅放宽这三处、增加可选 limitations，能保持旧完整报告可读。旧 `ScientificGateSequence` 无需改造成另一种部分 gate 结构；无 gates 不产生 pass，也不要求补写六层说明。

`schema/claim.py:28` 当前依靠 duck typing 读取 numerical_validity，缺失时抛 TypeError。计划 §6.2 指明按实际 `LayeredDiagnosisReport` 类型处理缺 gates，并输出既有 `not_evaluable`，既解决新简版消费，又保留未知报告类型的明确拒绝。overall_verdict 与 claim_allowed 仍取报告原值，不增设自动批准或结论一致性判定。

`science_operations.py:575` 的通用报告检查针对精确 study/plan 身份与实际引用；`:602` 和 TCAD `result_analysis.py:420` 解析同一模型，不要求必须存在 gates。历史计算复用在 `service/tool_evidence.py:100` 解析 prior_analysis 后访问 calculation_records，能够受益于同一模型的向后兼容。prior_analysis 及其精确 manifest 配对、来源身份、受控收据核对无需改动。current_progress 为既有 evidence_inventory 入口，不需要把旧记录迁移成新格式。

历史科学结果的读取由 `mcp_root_run_routes.py:135` 根据 completed 状态与原 Artifact 提供；新合同导致历史标记不等于重写旧字节或更新资格。计划将新 Run 编译与旧记录读取分开，方向正确。

## 5. backend 范围与既有问题

LocalTrustedBackend 在 `service/local_workspace.py:226` 支持 finalizer 写回；HardenedWorkerBackend 继承它，没有另一条绕过 RunService 的最终封存顺序。

但**本轮三种分析 Operation 的生产可执行路径是 local backend**：`operation_declaration.py:167` 默认启用 native shell，三个角色又声明 native view_image；`service/hardened_workspace.py:60` 明确不支持这些要求。不得手工删掉 native 声明，拼装出“生产 hardened 分析已验收”的测试证据。

另观察到 `service/hardened_files.py:209` 对带 finalizer、却没有 workspace_file_policy 的 `output/result.json` 不提供默认写入规则。这是当前已有的可选平台问题，且上述分析角色先被 backend 能力规则排除。**不作为本轮阻断项，也不要求本轮修改 hardened 文件编辑器、增设 file policy 或扩展 backend 支持。** 本轮报告应明确 local 真实 Worker/MCP 验收范围；不能由继承关系推称 hardened 端到端通过。

## 6. 实施后必须实际证明的结果

沿用计划既有受限串行检查，不新增测试框架或大矩阵。最有判别力的证据是：

1. 三个真实编译分析 Operation 均能发布生成字段说明；合法无 handoff 草稿经过对应 finalizer 和真实 local Worker/MCP 提交到 completed。曲线误差角色保持其专用输出 Schema 限制。
2. 无 gates、含 limitations 的简版，以及旧完整、有限/负面/无评分报告能读取；长 payload.summary 无 handoff 重复长度拒绝；缺 gates 的 claim 为 not_evaluable。
3. 最终首读文件计量与可解析原件指针；156 条控制绑定和源码原件内容未变。大视图降级只影响展示，不改变工具/finalizer 的 source_bindings 结果。
4. 新简版作为 current_progress 和 prior_analysis+精确 manifest 的已有消费入口可用；未绑定引用、错误执行身份和篡改收据仍由现有责任层拒绝。
5. 对实际安装包的 wheel/stdio 检查，以及安装后的新受控 Agent 运行，分别记录；测试或字节减少不代替真实 Agent 验收，更不能证明普遍提速。

以上均属于 R0 已声明目标与验收范围。八个生产文件的预计范围具备可实施性；本审查不要求新增核心协议、全局投影注册或平台重构。
