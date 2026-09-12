# 曲线评分移入结果分析工具计划：独立工程审查 R2

结论：**REVISE**。R1 的同 Run 数据流缺口已在计划层面解决；无评分身份校验已有明确分工，但最终校验器所需的实际输入元数据尚无交付接口。需补齐下面一个窄接口问题，再进入实施；不要求恢复独立评分阶段、实验前评分检查或新增状态机。

日期：2026-09-09。

## 审查对象与基线

- 被审计划：`docs/plans/CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN.zh-CN.md`，R2。
- 自行计算的 SHA256：`48a4d6f57aece33a12ac92ce573bc79629b1d533b7dc2b1c9cdd7b18c11ffbec`，与委托摘要一致。
- HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。检查的是 `123/scidiscovery-e5.2` 的实际工作树，存在大量既有修改及未跟踪计划，不能把本次证据描述为纯 HEAD 结果。
- 已读取前次 `CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN_REVIEW_R1.zh-CN.md`，重新核查相关源码；采用 `scid-cross-boundary-review` 技能。本次仅新增本报告。

## 必须补充：R2-1 · P2，输出身份元数据到最终 validator 的接线仍缺失

**计划位置：** P2a 第 108、112—113 行；P3 第 135—136 行；验收第 220—222 行。

**缺陷：**计划要求最终领域 validator 核对每个实际绑定文件的 manifest name、媒体类型、size、sha256，并验证其 case 引用。但当前输出 context validator 只收到“输入别名 → bytes”，看不到实际 Artifact 的控制端登记名、媒体类型、ref 或 labels。增加 `context_sources` 只授予 bytes，不授予这些元数据。guard 有元数据，却没有 manifest bytes。现有两个接口分别具备一半信息，计划尚未说明在哪里把两者可靠连接。

**源码证据：**

- `src/scidiscovery/artifact_agent/service/run_outputs.py:186`：构造 `sources` 后调用 `context_validator(payload, sources, handoff)`；`sources` 的值完全来自 `input_bytes`，没有绑定描述符。
- `src/scidiscovery/operations/invoke.py:29`：实际 `media_type`、`size_bytes`、`parent_refs`、`labels` 和 `ref` 存在于 `InvocationArtifact`；`BoundInput` 还包含 `source_name`。
- 同文件第 164 行：多件输入的别名为 `solver_outputs_001` 一类序号；它不编码运行输出名。第 312 行的 guard 调用只传 `inputs, parameters`，不传 bytes reader。
- `src/scidiscovery/artifact_agent/service/executions.py:501`：执行输出分别注册，控制端将 `descriptor.name` 放入 `logical_name` label，并记录实际媒体类型；同一执行的输出共享 `(request_ref, payload_ref)` parents。
- `src/scidiscovery/artifact_agent/service/artifacts.py:95`：Artifact 有独立身份；相同内容摘要并不意味着同一个运行输出 Artifact。
- `plugins/tcad_artifact/tcad_artifact/project_packager.py:790`：manifest 提供输出名、媒体类型、大小及摘要；因此最终校验需要将 manifest record 与确切绑定文件关联，而不仅是找到某段相同 bytes。

**可达触发条件：**同一执行产生两个不同名字／case 的文件 A、B，内容相同，例如两个工况输出相同曲线、空文件或同样的失败日志；分析只绑定 A，却将其别名映射为 B。两者共享执行 parents，bytes 摘要和大小也相同。当前 guard 可证明属于同一执行；当前最终 validator 若只按摘要匹配 manifest，则不能证明已读的是 B。类似地，通配媒体输入的实际登记媒体类型不在最终 validator 的可见数据中，不能仅用 Agent 请求或 manifest 中的类型代替实际绑定类型。

**影响：**可以错误报告“已读取／核验 B 的输出”，削弱缺失输出及 case 归属保证。该缺陷同时影响评分重放和不调用评分的引用核验。若直接以“同摘要多记录”拒绝整个分析，又会误挡身份正确、输出恰好相同的有效运行或失败运行。普通不同摘要 fixture 不会暴露此问题。

**最小修订建议：**明确一个由控制端拥有的、无新增持久状态的元数据交接方案，使同一窄校验能看到确切输入别名、ref、实际媒体类型／逻辑输出名，以及已绑定 manifest bytes。可以对既有输出校验上下文增加向后兼容的只读绑定描述符入口，并在 Worker 预检与正式封存两条路径一致提供；若选用其他现有接口，应写出实际函数及其数据来源，证明无需 Agent 自报、隐藏存储读取或跨 Run 状态。只暴露必要的科学输入身份，不交付控制令牌或执行内部身份。同步将确实必要的核心接线文件列为条件范围即可，不需要通用输入追加机制或新状态机。

若决定首版仅做按内容匹配，则必须明确降低其身份承诺：有歧义时不能形成确切文件／case 结论，但仍允许无此依赖的受限分析。不得把“内容可匹配”写成“已核验确切来源”。计划应在这两种语义中作明确选择。

**最小验证：**经真实 Worker 提交路径，覆盖同执行两个不同逻辑名、相同 bytes 的输出：只绑定 A 却引用 B 不能获得 B 的已读资格；正确绑定与引用仍可提交，未知 case 可提交受限结论；实际媒体类型不匹配不能被自报映射覆盖。至少一例不调用评分。验证预检与最终封存使用同一受控元数据，不只验证纯解析函数。

## R1 两项的复核

| R1 事项 | R2 结论 | 核查依据 |
| --- | --- | --- |
| 原始 PLX 到分析时映射、解析、评分、同 Run 提交未接通 | **计划层面解决** | 第 71—87 行选择 TCAD 所有的单一领域分析入口和组合工具，复用纯 normalizer 与 `evaluate_curve_consistency`，不再调用独立 support Operation；第 136 行从原始输入重放。`WorkerToolDefinition.contextual_handler` 和 `OperationToolContext.read_input` 提供实际接线能力。 |
| 无评分时缺乏确切审查／执行归属检查 | **大部分解决，尚受 R2-1 限制** | 第 104—114 行明确 guard、正式 pass、直接 parentage、同执行 parents、失败运行处理；`BoundInput` 提供所需父引用与 handoff verdict，`runtime_parentage` 是可复用的机制。剩余问题是 manifest record 与实际绑定输出名／媒体／case 的关联，不能仅靠最终 bytes validator 宣称完成。 |

这不是重开 R1 的整个设计争议。TCAD 入口、依赖方向和无评分分析原则无需重新选择；只需补足剩余的身份接口。

## 已闭合、无需扩大范围的链条

1. **可选评分和职责边界。**新 TCAD 分析与通用分析是替代入口，不是两次串行分析。TCAD 所有的组合工具可直接调用本插件 normalizer 和 curve_score 纯函数。`plugin.py:475` 与 TCAD `pyproject.toml` 已有 TCAD → curve_score 依赖；没有反向依赖需要新增。
2. **原始输入交付。**P2 已将 package、manifest、attestation 和原始文件分别绑定，明确 0—32 件输出和 512 MiB 总上限；`general_science_agent_operations.py:45` 的通配 inventory 使用 opaque codec，适合非 JSON 文件。`invoke.py:155` 及第 179 行分别执行单项绑定与总字节检查。缺少输出不再假装运行报告自动交付子文件。
3. **错误及失败运行。**P2a 不把失败 manifest／attestation 作为身份拒绝，P4 区分观测不可判与数值前提无效。`LayeredDiagnosisReport` 第 137 行开始的门状态派生可以表达相应受限结果。不得直接复用旧 `_passing_attestation` 或 PLX bundle 的“运行必须成功”门；R2 已明确提取底层函数而保留旧 support 协议。
4. **单主输出和计算记录。**在既有报告模型内增加可选记录，不增加外包装，是符合现有 codec、`run_outputs.py` 单主输出及下游读取路径的选择。computed 重算、unsupported／unavailable 确定性复核、瞬时 error 不冒充物理失败，契约已分清。
5. **工具与最终提交预算。**8 条记录、每条 16 个比较、4096 个采样点、32 KiB 响应和 128 KiB 主输出提供了可实现上界。计划要求真实解析及提交的近上限用例，而不是仅检查 JSON schema；足以作为实施验收要求，无需在计划阶段另建资源调度器。
6. **新分析接入下一轮设计。**`general_science_experiment_operations.py:36` 的三个可选反馈端口已经接受通配 schema／媒体 inventory；新报告 128 KiB 小于其单件上限。保留报告模型并验证 Worker → 封存 → 新设计输入，是闭合该链条的合理最小方案。
7. **安装与兼容。**P5 覆盖组件、Operation、生成角色及工具配置，要求安装版从原始文件起步并验证禁用 TCAD 后通用分析仍能运行。旧合同与显式 helper 保留历史，不继承旧资格；无需为本次职责调整删除旧代码。

## 属于实现细节的事项，不另列阻断项

- `ExpectedOutput` 当前只有 name、path、media_type 等字段（`execution_control.py:93`），没有直接 case 字段。计划第 201 行已允许在真实反例证明必要时补最小输出—case 关联。应使用明确关联，不能从 series 名或文件名猜测；这是已授权的实现范围，不要求再扩大设计。
- 通用入口只接受直接以计划为父的本轮结果，是明确的首版收窄。无法满足该关系的材料作为背景，TCAD 原始结果走领域入口；无需新增递归血缘推断器。真实 fixture 应证明至少一条合法通用结果路径，同时覆盖错轮拒绝。
- 媒体支持必须与 Worker 实际阅读能力一致；首版 CSV 显式列映射和 PLX／日志解析足够，不支持布局返回 unsupported，不要求增加 OCR、图证提取或任意脚本。
- 最终 context validator 当前没有 Run 剩余时间参数；实现可使用确定性工作量上限及工具预留预算，若必须加截止时间信息，可与必要的只读校验上下文接线合并评估。近上限测试须包含多条保留记录的累计重放，及角色结果 envelope 的字节开销。
- 方法变化、无评分证据和未知 case 的引用规则需出现在模型可见 schema／语义合同／提示中，保持工具、提交及后续 reader 一致。计划已要求同步更新，不再以此追加新平台能力。

## 验证边界

完成了摘要校验、工作树与 HEAD 检查、计划及 R1 全文阅读，以及相关 Operation 声明、guard 入参、执行输出登记、Worker 工具上下文、最终校验接口、normalizer／评分入口、报告模型、下游设计端口和插件依赖的源码跟踪。

未运行测试或安装版服务，未调用研究 Operation／Worker MCP，未运行求解器，未读取科学草稿，未修改生产代码或被审计划。本报告是源码支持的工程计划审查；既不证明实现验收通过，也不证明当前科学目标完成。补齐 R2-1 后应针对修订接口复审，无需重新引入评分阶段或无限扩充算法支持。
