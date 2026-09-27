# 分析接手视图与正式报告简化：实施独立审查 R0

日期：2026-09-13。结论：**PASS（限定工程实现审查通过，最终版本已冻结）**。

最终审查版本未发现未解决的 P1/P2 问题。实现落在已通过 R0 的八个生产文件内：复用原工作区和 finalizer，简化展示与报告，不改变原件、科学来源判定、输入准入或封存生命周期。审查期间指出的实现审查指针、未知 schema 阅读说明与设计消费验证均已补齐。此结论不代表用户环境已部署，也不代表真实 Agent 验收完成。

## 1. 精确范围和证据来源

审查对照 `/tmp/scid-handoff-report-baseline-flmih_xb` 的逐文件原件及 `baseline.json`，没有用全工作树 dirty diff 归因本轮。基线 HEAD 为 `be5da77acdbf98054e0b096fc4e940de560d4ba1`。`incremental.diff` 只作索引；后续 matrix_order、/review 和 schema_id 的补充直接对照了当前源码。

八个生产文件为：

- `plugins/curve_score/curve_score/analysis_workspace.py`
- `plugins/tcad_artifact/tcad_artifact/analysis_bindings.py`
- `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py`
- `src/scidiscovery/artifact_agent/service/result_materialization.py`
- `src/scidiscovery/artifact_agent/schema/claim.py`
- `plugins/curve_score/curve_score/science_operations.py`
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py`
- `src/scidiscovery/platforms/codex.py`

已逐项核对这八个当前文件的 SHA-256，与 [installed-smoke.json](installed-smoke.json) 中 `packaged_source_sha256` 完全相同。该记录 SHA-256 为 `c677b318005ac0a9d7428bf3e136c63c58d8efb2e7cecb9de762d8dfd9233cc9`，其中最终 `analysis_bindings.py` SHA-256 为 `0ba9c80694691145454cead778671590af0477be318b284fbaacc8f23dd8867e`。本次源基线清单 [source-baseline.json](source-baseline.json) 的 SHA-256 为 `48362665f14ff80479fb134fffb6f284e32fa3eb2e4ffe7d2fde04199296686c`。

同时只读检查了新增 `test_analysis_handoff_report.py`、原 `test_analysis_continuation.py` 的单处断言调整、有关源码路径、检查日志、离线测量脚本与安装烟测脚本。审查者没有运行测试、导入/编译框架、调用科研 MCP/Worker、读取私人 Run 草稿或修改生产源码；测试结论来自下列明确记录。

## 2. 草稿到封存，再到消费者：三角色接线完整

`service/result_materialization.py:46` 的 `materialize_analysis_handoff` 只读取正式 payload 的 overall_verdict 与 summary，按计划固定映射写 handoff verdict，并写入指向 `run_status.sealed_output.payload.summary` 的短引用。缺少科学 verdict 时不猜默认结论；缺省 handoff 可以补齐，已有 assumptions、missing_inputs、next_actions 等其余说明保留。payload 本身的科学结论、claim_allowed 和证据没有被投影代码改写。

`materialize_general_result` 在同文件 `:62` 仅对 `scidiscovery.layered-diagnosis.v1` 启用该投影，其他角色的既有规则保持。TCAD `analysis_bindings.py:249` 显式组合 handoff 与原 source references 补全，避免只修改通用 finalizer 而漏掉 TCAD。曲线误差角色在 `science_operations.py:352` 改用现有 `analysis_workspace`，因而也拥有共用 materializer/finalizer；该角色的固定 package、专用输出 Schema、禁止新增计算记录及无评分工具边界保持。

`analysis_workspace.py:245` 发布既有 `patch_contract`，明确草稿可省略 `/handoff` 和生成字段来源。三角色提示共用 REPORT_GUIDANCE；通用分析原“逐 gate 填写”要求已删除。封存 envelope 的必填规则没有被全局放宽，也没有另建草稿 Schema。

已沿现行真实路径核对：`service/runs.py:1018` 在 seal 前调用 finalizer，`runs.py:1158` 通过 backend 写回主结果，`service/run_outputs.py:120` 随后解析最终 RoleResultEnvelope；`:257` 从已验证 handoff 生成 scheduler signal。此次没有修改这些核心服务。Root 仍在 completed 后同时返回 sealed_output 与 scheduler_signal，短引用不会代替科学正文。

## 3. 简版报告和历史记录兼容

`schema/layered_diagnosis.py:170` 将完整 gates 整体改为可选；`:177` 增加可选 limitations，并放宽 remaining_contradiction/next_action。其余可选评估维持原有形式。旧完整 ScientificGateSequence、旧计算记录和 source references 继续可读，不迁移历史 Artifact，也不把省略诊断层解释为通过。

`schema/claim.py:29` 明确按 LayeredDiagnosisReport 类型消费；缺 gates 时输出既有 `not_evaluable`，保留 overall_verdict 与 claim_allowed 原值；不支持的报告类型仍抛明确 TypeError。引用、计算收据、study/plan 身份和 historical manifest 配对规则均未改动。

新增测试通过实际 local Worker/MCP 提交无 handoff、无 gates 的草稿，覆盖 pass、fail、inconclusive、invalid_study、长 summary 和缺产物执行；检查封存后的完整科学结论与 claim 投影。其后将同一封存报告作为 prior_analysis+精确 manifest 或 current_progress 打开下一轮分析，并比对旧 Artifact 未变。

`test_analysis_handoff_report.py:103` 补充“已封存简版→设计 preflight→设计者打开原件”路径，读取到的 current_progress 字节与原分析 Artifact 相同。该用例复用既有设计 cohort 与审批 stub，只证明反馈传输和消费，不证明真实审批 UI 或科学设计质量；这个边界已在测试注释中说明。

## 4. 展示预算与完整科学映射分开

`analysis_workspace.py:55` 按最终 UTF-8 JSON 字节计量，输入索引先于摘录，加入大小、schema、端口用途和原件位置。计划索引提供原字段名、案例位置、比较合同和 validation_plans；observable 只按完整原文相同去重，所有原指针保留。长摘录明确是导航，未知 schema 保留索引并说明没有生成摘录。

`analysis_bindings.py:173` 先为 TCAD 首入口使用 12 KiB 预算，加入最终视图指针后再计算剩余的 32 KiB 合计展示预算。`reading_view` 在案例矩阵前放入既有来源对应关系，避免矩阵先占满预算、迫使 Agent 重查大部分已知身份。放不下的明细尝试保留精确 pointer，否则保留 omission count 与 assignment 输入索引入口；没有通过字节阈值拒绝 Run。/review 指针只在原 package 实际具有该字段时加入，不推造审查内容。

案例矩阵按原合同 baseline/comparison 顺序组织，每行保留原 variable 指针、expectation_indices、单位和比较规则。matrix_order 明确表头被省略时必须追该行自己的原合同，不能套用上一提案表头。源码索引指向 `/project/files/<index>/content`；明确嵌入源码正文不是已物化的同名文件。

完整 `source_bindings` 函数和原引用补全逻辑与本次快照相比未变。只在 `reading_view` 副本中省略历史 basis 明细；评分、上下文校验和 finalizer 仍调用完整来源映射。原 `test_analysis_continuation.py` 的调整只把历史 basis 断言从已删除的展示副本转向实际 prior_analysis 原件，仍检查最终封存 basis；没有移除来源完整性断言。

最终 [fig4-view-measurement.json](fig4-view-measurement.json) 记录：入口 11844 字节，TCAD 视图 16867 字节，合计 **28711 字节**；156 个案例值逐项核对，13 个已有产物对应关系全部展示，原 156 条控制绑定保留，默认视图控制明细为零，原件字节与完整工具映射未变。入口有 17 项遗漏，TCAD 视图无遗漏；只读核对生成入口的结构，仍保留 24 个输入索引、两提案/比较合同及两 validation_plan 的原位置和 objective 摘录。当前目标与方法等其余内容继续由原字段索引追溯。

该测量使用精确封存 plan/project、从 completed 绑定记录取得的真实 13 个产物名称，以及其余数据输入占位项；属于离线结构验证，不能等同于真实 24 个绑定输入的 Agent 首读量。脚本和记录明确了这个限制。记录 SHA-256 为 `d091677b8ec2b15d871b639a0305d569a31ab45187602ecccdbb0804ecb6d9c8`。

## 5. 已观察验证与失败处置

记录见 [checks.jsonl](checks.jsonl)，均由既有受限串行 runner 执行，日志保留退出码、耗时与进程树 RSS；不将多批有交集用例加总为独立测试数量。

| 证据 | 实际结果与意义 |
| --- | --- |
| `check-1789310824345360411.log` | 修改前限定分析基线 68 项通过。 |
| `check-1789311574240591305.log` 与 `check-1789311654540103151.log` | 实现中间批 71 通过、6 失败；后续新增 9 用例加相关两项回归共 11 项通过，覆盖这六项所涉路径。中间失败未隐藏。 |
| `check-1789311682914099105.log` 与 `check-1789311800665170184.log` | TCAD/collector 56 通过、2 失败、1 deselected；两项在修改前源码隔离覆盖层同样复现，均为预期错误码 `input_producer_contract_changed` 与实际 `input_independent_review_incompatible` 的断言差异。负面 author 资格仍被拒绝，不属本轮回归，不扩大为无关修复。 |
| `check-1789312349361859246.log` 与 `check-1789312439497688086.log` | 31 项通过、新增设计测试因夹具未初始化审批服务失败；修正夹具后，设计消费与两项平台配置定向检查 3 项通过。生产审批逻辑未改。 |
| `check-1789312714469037982.log` | 最终八文件版本的新增报告、continuation、claim_scope 和 artifact_references 四文件合并批次 **78 项全部通过**；58.91 秒，峰值进程树 RSS 157880320 字节。 |
| `check-1789312805081098837.log` / `installed-smoke.json` | 从最终实际发布源码构建并安装 wheel，隔离环境编译 50 项 catalog，三角色 local Worker stdio 均提交到 completed；八个安装源码 SHA 与当前审查源码一致。13.73 秒，峰值进程树 RSS 250191872 字节。 |
| `check-1789312804299757880.log` | 最终源码离线 Fig.4 视图测量通过，0.66 秒；13 个实际产物名称与 156 个案例值完整展示。 |

安装烟测此前的三个失败记录保留。最后一次失败的曲线误差夹具曾先在内存 Worker 打开 Run，再让另一个 stdio Worker 尝试首次打开；该角色不具备带 tool_evidence 分析的 reopen fallback。最终验收脚本将其保持 queued、由 stdio 首次打开并提交，未为修测试改动生产生命周期。安装探针使用测试夹具生成输入，但核查生产模块全部来自隔离环境，并通过真实 MCP stdio 子进程交付结果。

现有引用未绑定来源、错误执行身份、受控收据篡改的责任层没有被绕过。此次没有新增评分前置条件、整体目标覆盖门槛、字数门槛、输入资格复查或科学结论自动推导。

## 6. 审查结论的边界

本轮工程实现在已通过范围内通过审查；无需新增 Operation、数据表、统一投影注册器、通用草稿协议或 backend 重构。local 首次接手与复用提示均在 `platforms/codex.py` 更新，仍要求核对新绑定、追溯本轮原件和在调用前阅读所选工具完整合同。

三种分析角色原本声明 native shell/view_image，hardened 现行能力规则不支持这些要求。既有 hardened 的 finalizer/file-policy 写入缺口沿用计划审查边界，不作为本轮阻断，也未声称 hardened 端到端通过。

尚未证明的是用户运行环境部署、真实 Agent 的自主阅读/计算/提交过程及端到端耗时收益。隔离 wheel/stdio、离线字节测量和受控测试不能替代这部分验收；计划、实现、安装与真实运行状态应继续分别记录。
