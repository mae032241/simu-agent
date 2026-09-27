# 有用事实的校验职责复扫（2026-09-12）

本轮扫描的是上一轮删除后的工作树，不是已安装版本，也不是线上科学 Run 的失败归因。没有修改生产代码、运行全量测试或求解器。已重新编译当前声明的五个插件，核对 50 个 Operation（25 Agent、21 transform、3 approval、1 effect），追踪共享输入/输出校验、模型解析、审查准入与关键领域消费者。

结论：**仍有 6 组需要移位或归并的职责。外层已经分开 preflight 和输出提交，但领域函数、模型校验器、派生字段以及异常分类还在混用职责。** 不是所有读取输入的输出检查都有问题：核对新输出引用的是哪份文件、哪个案例、哪个受控计算收据，应继续保留。

“机械字段自动生成”属于本报告的第 4 组。“诊断信息修复”主要是错误信息传递问题，并不全属于职责移位；当错误责任被归给错误角色时，才与第 5、6 组及附带发现相交。

## 1. 曲线合同的输入身份检查拖到输出提交

- **有用事实**：研究目标与实验计划必须属于同一目标。
- **现址**：`plugins/curve_score/curve_score/science_operations.py:123` 的 `_curve_contract_context` 在提交时调用 `validate_compiled_curve_contract`，后者重新调用编译器；`curve_contract_compiler.py:85` 才检查 `portfolio.objective_key == objective.objective_key`。该设计 Operation 没有声明对应的 `input_validation`。
- **已复现**：在临时控制面中，绑定目标键不匹配、但各自结构合法的目标和计划，`operation_preflight` 返回 admissible=true。提交合法编译结果时被拒绝，诊断是 `output_context / output_invalid / repairable=true`；直接调用同一函数可确认具体原因为目标与计划不匹配。
- **正确落点**：这两个冻结输入之间的身份关系应在设计 Run 创建前检查。输出阶段保留“新合同实际选择的目标、案例、阈值与绑定记录对应”，不再替输入配对兜底。
- **范围**：直接涉及 `science.curve.contract.design.v1`，以及它调用的合同编译工具。审查 Operation 的跨输入身份也应在对应准入检查，不能依赖输出检查替它完成。
- **验收/风险**：同一错误绑定必须在 preflight 拒绝，不能创建徒劳 Run；合法绑定生成的合同仍须拒绝伪造引用。不能简单删除编译器的防御性检查后放开直接工具调用；应复用同一输入事实检查，并正确归属错误。

## 2. TCAD 分析读取工程包时重新执行资格检查

- **有用事实**：工程包创建或用于执行时，项目、审查、能力与输入槽必须匹配，所需运行证明必须真实。
- **现址**：`plugins/tcad_artifact/tcad_artifact/result_analysis.py:264` 的 `_identity_context` 调用 `parse_bound_json(ReviewedDeckPackage, ...)`；`project_packager.py:819` 的模型校验器 `_review_qualifies_project` 又调用 `validate_deck_review_against_project`，检查通过审查、execution_ready、预检证明等。
- **已复现**：一次完成的分析提交中，实际调用链为 `validate_run_output → analysis_context → _identity_context → parse_bound_json → _review_qualifies_project → validate_deck_review_against_project`。跟踪到 1 次资格复查；该正例最终完成，不能据此声称线上已因此拒绝。
- **正确落点**：工程包生成、相应输入准入和授权执行负责资格；分析读取已绑定包时只解析记录和核对新输出的来源/案例/收据。资格策略不应作为通用模型读取的副作用。
- **范围**：已确认 `tcad.result.analyze.v1` 的提交与评分工具读取路径；其他工程包消费者须按“创建/执行/历史分析”用途保留相应检查。
- **验收/风险**：在准入完成后监测资格函数，分析提交不再调用；伪造包、跨案例引用仍在正确边界拒绝。需要明确已准入记录的读取方式，不能用无条件 `model_construct` 接受任意 JSON。上一轮只移除了另一种分析包重算和整体参数 coverage 重判，这条嵌套路径仍在。

## 3. 把图像执行需要的完整恢复信息用于拒绝缺口报告

- **有用事实**：定量提取必须确认原图身份、恢复图像摘要、尺寸及恢复方式。
- **现址**：`plugins/curve_figure_evidence/curve_figure_evidence/figure_digitization_contract.py:109`、`:125` 的两个 source 模型要求完整恢复字段，`FigureDigitizationRequest.source` 无论 ready/unresolved 都必填；`figure_science_operations.py:159` 对两种状态都调用 `recover_requested_image`。
- **已复现**：声明 unresolved、说明尚未恢复图像身份，保留原文件身份但没有恢复图像摘要、宽高和版本时，仍因 4 个字段 missing 被拒绝。PDF 还要求页码和精确图像对象编号，因此无法表达“已知原文件，但页或图像恢复失败”的完整缺口。
- **正确落点**：缺口封存只要求明确绑定原文件、记录已知信息和缺失原因；实际提取要求完整且匹配的恢复身份。复用已有 ready/unresolved 状态，不新增状态机。
- **范围**：`science.figure.request.prepare.v1` 及后续图像物化。原始来源不可省略，但未取得的恢复结果不应被迫编造。
- **验收/风险**：未知图像对象可封存 unresolved，并进入补充/重新设计；同样的请求不能执行定量提取。上一轮 F08 只完成了 bbox/axes/series 的部分字段保存，没有覆盖 source 恢复失败，完成范围不能扩大解释。

## 4. 让 Agent 重写由唯一来源决定的字段，再校验其抄写

这些关系多数应保留为新对象生成后的程序断言，或对外部/历史记录的完整性检查；不应继续成为当前 Agent 的填表任务。

| 事实 | 当前要求/位置 | 应由谁生成 |
| --- | --- | --- |
| 案例数量 | `schema/experiment.py:268` 要求 `resource_estimate.case_count == len(cases)`；修订直接输出完整 Portfolio。 | 当前物化器已在 `schema/experiment_intent.py:404` 计算数量，修订应复用同一生成能力。 |
| 总体目标的重复文本 | `schema/research_cycle.py:143` 要求 frame/foundation 相同；`schema/scientific_foundation.py:160` 要求 objective_contract.statement 与副本相同；`schema/experiment.py:434` 要求每个 proposal 再含总体目标。 | 从当前对象唯一目标或精确绑定的原目标投影副本。当前目标子集、后续目标及科学范围仍由 Agent 判断。 |
| 正式结论与 handoff 镜像 | `general_science_components.py:75,161`、`general_science_experiment_components.py:239`、`curve_score/science_operations.py:149`、`tcad_artifact/parameter_operations.py:248`、`project_packager.py:727,1301,1316` 重查固定映射/复制。 | 正式科学对象保留唯一结论，控制层投影有既定含义的 handoff。不能借生成字段重新用固定公式决定科学结论。 |
| DOI 规范化 work_key | `tcad_artifact/device_parameters.py:183` 要求 `work_key == doi:<normalized>`。 | Agent 识别 DOI；程序规范化得到同一作品身份，继续用于独立来源去重。没有 DOI 的来源身份仍可能需要判断。 |
| 图像恢复元数据 | source 要填写摘要、尺寸、PDF 对象编号和恢复工具版本；`figure_worker_tool.py:76` 已返回这些程序事实。 | Agent 选择具体图像；控制层从那次受控检查结果组装元数据，保留源完整性核对。 |
| 审查中的能力摘要 | `project_packager.py:1572` 的 direct-deck 分支仍要求 review.capability_sha256 与项目一致，尽管此字段在模型中可选。 | 从被审对象绑定能力摘要，不让审查者重抄。审查维度、发现和科学结论不由控制层补写。 |

验收应证明：Agent 只改一次案例或正式结论即可封存一致版本；原总体目标不能被暗换，重复论文不能变成两个独立来源。旧记录继续可读，绝不能原地改写已封存 hash、签名或批准对象。不同语义的字段不能仅因字符串相同就自动合并。

## 5. 确定性转换把输入关系错误拖到执行器，再归成工程故障

- **有用事实**：评分报告与其曲线 bundle、合同和计划摘要必须匹配；运行输出必须对应 manifest。
- **现址**：如 `curve_score/analysis.py:195` 在分析执行中检查 bundle/report 摘要；`tcad_artifact/operation_transforms.py:103` 检查输出集合与 manifest。`src/scidiscovery/operations/invoke.py:337` 将执行器抛出的所有异常统一变为 `OperationEngineeringError(executor_component_failed)`。
- **已复现**：给 `science.curve.error.analyze.v1` 一个结构合法但 bundle 摘要错误的 metric_report，preflight 通过，invoke 才失败；外层只返回 deterministic transform failed，并经 executor_component_failed 包装。
- **正确落点**：与新计算无关、已由输入决定的身份/摘要/集合关系提前准入。真正计算过程中才知道的数据不支持或计算不可用，返回明确受限结果或已声明错误；程序内部异常才标工程故障。不要为了预检而提前把昂贵计算再执行一遍。
- **范围**：当前 21 个 transform 都未声明独立 input_validation，但有各自的端口和 guard 检查；**这不证明 21 个全错**。本轮确定的是上述真实调用与同类叶检查，不能把“无 input_validation”直接当缺陷数量。
- **验收/风险**：错误摘要在执行前被拒绝；真正程序故障仍失败关闭，不能把任意 ValueError 都改成调用者可修正错误。显式负责计算/验证的 Transform 仍可验证自己实际生成的结果。

## 6. 审批投影器同时负责资格判定和页面生成

- **有用事实**：批准对象必须来自精确的抽取/展开/审查族，参数覆盖满足批准用途，来源和批准 cohort 不能混用。
- **现址**：`tcad_artifact/parameter_operations.py:478` 的 `_parameter_qualification_document` 在组装 ReviewDocument 前验证整套来源族、清单、确定性覆盖和独立审查；通用 `general_science_components.py:325` 同样如此。`mcp_root_operation_routes.py:418` 的 `_prepare_approval_projection` 到 `:473` 对投影器所有异常按 approval_projector_failed 处理。
- **证据**：源码调用链，以及上一轮已记录的两种参数审批测试失败。没有在本轮创建真实审批，也没有把旧测试当作新的线上事故。
- **正确落点**：仍由当前审批 preflight 统一负责，但把“资格验证”和“生成展示”区分开；复用已有 ApprovalProjectorContext，不另建注册表。已知的对象/资格错配报告明确准入拒绝，展示代码或内部异常才报告工程故障。
- **边界说明**：现有 preflight 已会调用这个 projector，因此这里不是“批准之后才发现输入错”；错在组件职责与错误归责混在一起。不能删除这些资格检查来让审批通过。
- **验收/风险**：错误清单/来源族只产生明确拒绝，不创建批准对象；展示器异常仍属于工程故障；只有精确 UI 决定可以授权。

## 附带确认：诊断归责与提示同步

1. 图像恢复的依赖缺失、超时会在 `figure_source.py:102` 转成 ValueError，再被 `figure_science_operations.py:170` 包成 SemanticRuleViolation，从而成为 Worker 可改输出。这是**错误责任错配**：工具/环境故障不能让科学 Agent 改校准值来“修复”。原文件或具体图像身份确实错误的分支仍是有效输出检查，必须与环境故障分开。
2. `figure_science_operations.py:85` 仍提示 unresolved 不得保留 partial digitization fields，与上一轮已经放宽的模型不一致。应同步提示；这是上轮实施遗漏，不是新的科学约束。
3. F01 中具体原因被清洗掉，主要是诊断传递缺陷；不能只靠移动校验恢复详细报错。

## 确认应继续保留的边界

- Root 已按 `review_input_mode` 区分背景、被审对象、修订基线和资格凭据；`mcp_root_operation_routes.py:1420` 对精确独立审查的被审对象跳过外部 reviewer 要求。本轮未发现“所有 blocked 对象都无法审查”的统一旧阻断仍在。
- 上一轮移出的 `CurveDiagnosticAnalysisPackage` 输入重算、author 按整份 coverage.status 重判，当前源码中保持移除；不能将旧审计发现重复计为未修。
- 输出对冻结证据的真实引用、计算收据、案例身份、路径安全、字节完整性的核对仍放在正确边界。
- 数值算子的 level/单位/有限值/有效支撑属于当前计算需要，不是要求未来研究条件先齐备。

## 实施顺序与证据边界

优先处理 1、2、3，消除不可能完成的交接或输入重新准入；第 4 组按现有生成器逐项接回；第 5、6 组明确已知拒绝与工程错误的类型和入口。每项都验证“错误输入仍拒绝、合法局部成果可提交、原始记录不改写”，不扩大成全新状态机。

本轮重新编译 50 项目录，追踪共享组件；4 个有界探针分别覆盖错误输入晚拒绝、分析提交重复资格、缺口元数据强制、转换错误归责。临时 Run 全部是隔离的工程测试夹具，未读取或修改用户研究实例。最高 RSS 121,044 KiB，约 118 MiB；进程地址空间上限 512 MiB、CPU 上限 30/45 秒，串行单线程。未验证全部路径、安装包、真实 Agent、审批 UI 或求解器。

可复现输入、结果和逐 Operation 检查范围见 [RESPONSIBILITY_PLACEMENT_EVIDENCE.json](RESPONSIBILITY_PLACEMENT_EVIDENCE.json)。
