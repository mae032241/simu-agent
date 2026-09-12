# Operation 职责与输入交接修复计划：独立工程审查 R3

日期：2026-09-09。审查对象：`docs/plans/OPERATION_RESPONSIBILITY_HANDOFF_REPAIR_PLAN.zh-CN.md`，SHA256：`eb30209f6ccf3e47d3ac5aeb3301c30ede64e2db92036de5d1df6fdd2dfaf57c`（读前及写报告前一致）。仓库：`123/scidiscovery-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。实际基线是含大量既有修改及未跟踪依赖的工作树，HEAD 不代表该快照。

遵循明确工程审查授权和 `scid-cross-boundary-review` 技能，读取适用 AGENTS.md 与 R1 报告，独立核对当前代码，不继承旧结论。仅定向静态阅读；未运行测试、构建、安装、部署、求解，未调用研究控制面或 Worker 工具，未再开子 Agent。唯一写入本报告，未改计划或源码。以下行号均针对本次工作树。

## 总体判定

**REVISE（仅 B 的恢复生产接线）；A0/A 可独立实施，C0 可开展，C 继续暂停。** R3 已足够明确共同参考、可选背景、gap union、版本策略及完整 design cohort。剩下一处实际生产断点：B 把已有恢复 helper 当成已接通的领域草稿保存路径，而当前失败路径只保存 output 候选。此问题不需要新状态机或新提交协议，但实施前应补一段有界的快照接线决定并修正恢复优先级。不能称“唯一工程前提只剩 C0”。

| 维度 | 判断 | 依据及范围 |
| --- | --- | --- |
| 目标定位 | PASS | A0 的共同职责/背景与 A 的当前必要信息交付分工合理；B 处理真实负成果；C 不再把 exit 0 当作物理初始化证明。没有将后续评分变成 author 前置职责。 |
| 工程完备性 | REVISE，限 B 恢复 | 输入资源、schema、validator、版本和 review 消费面基本明确；F1 所述 raw draft 保存没有当前生产调用，承诺的 retry 验收尚不可实现。 |
| 科研闭环逻辑有效性 | PASS_WITH_CONDITIONS | 现有绑定、独立审查、负记录反馈和结果分析机制可形成有界闭环；B 须修正 F1，C 须先通过 C0，真实必要科学数值仍由绑定输入和独立 Worker 判断，真实跨轮验收尚未完成。 |
| 最小改动 | PASS_WITH_REQUIRED_ADJUSTMENT | 一个共同文本、少数 exposure、两个复用式进展声明及一个 gap 分支足够。F1 只要求接通已有领域快照 seam 和明确草稿选择，不支持扩展成统一恢复系统。 |

## 必要 finding

### F1 — P1：B 的 gap/raw-tree 恢复没有生产保存路径；“有效 result 优先”还会保留过期候选

**计划位置：** 第 135–139 行冻结载体与恢复规则、第 194 行限制通用 Run 修改、第 212 行 retry 验收、第 249 行认为通用服务足够，以及第 251 行“唯一剩余工程前提是 C0”。

**已核实的生产事实：**

- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:647` 的 `snapshot_workspace` 只定义了领域草稿快照；第 650–672 行收集 project/declarations/handoff/files，当前未含 gap。`plugin.py:508,517` 注册并声明该 hook；全仓静态引用显示没有生产调用者消费 `workspace_snapshotter`。仅为该函数加 gap 不能保存任何新草稿。
- `src/scidiscovery/artifact_agent/service/runs.py:515–544` 的失败收尾只调用 `backend.seal` 并记录候选 digest；第 552–566 行 `_finish_failed_workspace` 把该 digest 传给 `backend.discard`，没有调用领域快照 hook。`local_workspace.py:234–253` 的 `seal` 只读取 `workspace.output_directory`；第 339–363 行 `discard` 仅将对应 candidates 复制到 recovery，随后第 366 行删除隔离工作区。
- `runs.py:788–803` 将单一 `recovery-draft` 交给 materializer；但 `operation_workspace.py:202–235` 的 `_restore_retry_tree` 要求其中已有 `deck/files`，`_restore_retry:156–183` 的 raw fallback 同样依赖 deck 文件。当前生产保存链没有放入这些文件。已有 helper 的存在不能证明 raw-tree retry 已接通。
- `runs.py:730–753,823–848` 先 finalizer 写 `output/result.json`，再做输出语义校验。一次失败的校验可以留下结构有效的 result；后续 deck 修改不自动重写它。`operation_workspace.py:505–523` 又明确 result 由 finalizer 独占。故 result 结构有效或被 backend 按字节 seal，不等于它已通过 Run 校验，也不证明它比当前 deck 草稿更新。

**可达场景及影响：** author 在某次提交被 context validator 拒绝后，补写 `deck/gap.json` 或修正源码，尚未再次完成提交便失败/超时。当前失败保存链只保留旧 `output/result.json`；若从未生成 result，则可能根本没有可恢复候选。新 gap、包括损坏但应可修复的 gap、以及较新源码均不会抵达新 Run。B 第 212 行“gap 与残留 files 共存，经 retry 仍是 gap”通过实际 Run 路径无法成立。即使补齐快照保存，照第 138 行无条件以有效 result 优先，也会在同一快照内覆盖较新 gap，或让删除 gap 后的新工程草稿退回旧 gap。

这是 B 明确承诺的恢复行为所需的工程接线，不是要求处理本轮范围外的所有失败。它主要造成工作丢失和无进展重试；不据此声称已有执行资格可绕过。

**最小修正：** 在 B 补一项窄决定：失败隔离前通过已声明的 `workspace_snapshotter` 获取领域恢复草稿，沿用现有 recovery-draft/digest 和不可变输入检查保存；仅对声明该 hook 的工作区生效，明确有界文件数与总字节预算，覆盖不完整/损坏 gap，不能要求先完成源码物化或 debug。允许在已证实的 Run/backend seam 做必要接线，不用“不得新增状态”误解为不得修调用者。不要把草稿塞入成功 output 的单文件合同，也不要增加第二套提交协议。

同时把第 138 行改为可实施的权威选择：存在受控保存的当前领域草稿时按其显式 gap/删除 gap 后的工程选择恢复，只有没有该草稿时才回退 result；或提供同等明确、可验证的同源新旧判定。无需新增时间戳状态机。结构有效的 result 不称“已通过的封存成果”。保留同一 operation digest、输入及重试预算约束。

**最少验收：** 复用实际 Run 失败/恢复夹具，经 `fail/timeout → discard → 新 Run materialize` 验证：① 旧结构有效 result 加较新 gap，恢复 gap；② 旧 gap result 加显式删除 gap 后的新源码，恢复工程草稿；③ 尚无 result 的损坏 gap，恢复为可修正 gap 而非丢失或回退工程。保留普通无领域 hook 的 result 恢复正例，检查恢复预算和原输入身份拒绝。至少一例不能手工构造 provisional root 后直接调用 `_restore_retry_tree`，否则仍未覆盖断点。无需启动求解器。

## 其余重点交叉核对

**共同前言与摘要。** `operation_declaration.py:28` 的公共前言确实被 `general_science_resources.py:163–166`、`general_science_experiment_components.py:364–366`、`curve_score/science_operations.py:844–849` 及 TCAD `result_analysis.py:290` 的 prompt 使用。TCAD `role_pack.py:8–9` 目前只读角色文件，`plugin.py:212–213` 消费其返回文本；按 R3 加同一个短参考即可，无需重复整个通用前言或改 Worker 权限。`operations/catalog.py:135–142,713–716` 对实际资源字节计算摘要并纳入编译闭包，计划要求列全受影响摘要成立。其余未使用此前言的角色只列实际覆盖，R3 未虚称全部背景已经交付。

**current_progress 与 validator。** general_science 的 wildcard schema/opaque codec 已注册（`general_science_components.py:383,423,481`；`general_science_resources.py:177`），可被 TCAD 跨插件引用；TCAD 分析已经采用该方式（`result_analysis.py:335–345`）。`plugin.py:274–301` 的 `_input` 确无 max_items 参数，新增明确 InputPortSpec 是准确的最小决定。revise validator 按 prior_draft/change_request 名称读取并保持计划身份（`general_science_experiment_components.py:168–194`），不将每个额外 source 都当作计划。author、runtime author、deck review wrappers 及参数 cohort 同样使用明确名称（`plugin.py:89–115,145–176`；`project_packager.py:1179–1307`），新增 inventory 不会自动加入批准参数 cohort。gap 分派应覆盖 wrapper 的 readiness 检查，不能只改底层模型；计划已列 plugin/context 修改面。

**exposure 与 review 身份。** assignment 明确过滤 handoff_only（`run_assignment.py:40–53`），故改 on_demand 有真实交付作用，但只使所绑 review 的 payload 可读，不会自动带 producer handoff。通用分析的 `_diagnosis_context` 按名字读取主计划、metrics 并允许来源别名，不会把新增科学 review 当成 metrics（`science_operations.py:613–625`）；TCAD 的 `analysis_context/_identity_context` 也按固定端口读取主计划/package/runtime（`result_analysis.py:158–189,212–282`）。既有 review 准入依赖精确 producer/subject 而非 exposure（`mcp_root_operation_routes.py:1361–1395`）；TCAD 分析另有 plan/review/package/runtime 父链 guard（`result_analysis.py:36–61`）。背景可读不替代这些门禁，不需要另加自然语言 review 分类器。

**版本策略可实现。** 通用 builder 的 version 固定为 1（`operation_declaration.py:144`），但当前通用分析已用局部 `.model_copy(update={"version": "2"})`（`science_operations.py:311`）；因此 revise 与两种分析可按各自当前版本局部递增，无需把共享 helper 所有用户一起升版。TCAD author helper 与 deck review 独立声明处可按 B 升到 2。公共 prompt 字节变化仍会改变其他消费者摘要；应按计划核对真实 catalog，不能把相同语义版本当成相同合同。

**gap schema、handoff 与独立 review。** 保持完整 DeckProjectDraft 不变并在同 ID 的唯一资源提供 union，在当前编译资源模型下可行；仍需实施验证。`RoleHandoff` 的 missing_inputs 是最多 16 个字符串（`schema/role_result.py:21–29`），与 gap 的字符串列表兼容；允许空列表不要求更改通用 schema，比较时按 JSON 值规范化即可。`DeckReviewReport` 没有必填 project SHA，capability SHA 可为 null，unknown/blocked/revise 和 execution_ready=false 都能表示负审查（`project_packager.py:690–744`）；确切 project/plan/capability 身份由绑定父链保持，不需要往 gap 虚填工程 hash。现有 review validator/template/transform 仍按完整项目解析（`project_packager.py:1218–1251`；`operation_workspace.py:263–305`；`transform_adapter.py:85–109`），均已列入 B 修改面。必须按分支保留完整工程的 manifest/source/capability 校验；gap 不进入 prior_project/package/执行解析入口。这是所计划的实施工作，不重复报成缺陷。

**design 返回路径和历史资格。** R3 第 230–243 行补齐 objective/foundation/portfolio/critic 的确切恢复关系，与 `experiment_science_cohort` 的四条父链约束（`general_science_experiment_components.py:393–402`）一致。evidence_inventory 跳过 Agent 的 producer review 资格要求（`mcp_root_operation_routes.py:1326–1331`），claim_evidence 仍单独检查（第 1114–1128 行），require_current 仍按声明执行（`run_current.py:79–87`）。因此旧负 gap/review 可以作为背景读取，但不能恢复 claim 或新执行资格；完整必选 cohort 不可用时仍按精确拒绝处理。当前正式计划、匹配审查和结果不会因增加背景端口而在结构上被替换；科学理解是否正确必须留给真实 Worker 验收。

## C0 与完成条件

R3 第 163–177 行诚实暂停 C，给出了可信真实正样本、来源绑定、证据选择、prepare/transport/collect/收据生产路径、8 MiB/10 秒边界及反例要求。该核定任务已经足够明确，可以开始；没有合法样本则继续暂停，不是本次再报的实现缺陷。不能把已知不可用的 TDR provider 或手写日志作为通过依据。

A0/A 可以在保持现有工作树的前提下独立实施；B 的 schema/提交/review 部分有明确方向，但恢复范围须先按 F1 补齐，不能将整个 B 标为可按原文直接完成。C 只有 C0 决策被复审确认后才实施。本案例执行就绪及整轮完成仍须新的初始化证据、匹配审查、精确 UI 审批、实际执行与有限分析、下一轮设计等真实记录；旧历史可读与新执行资格保持区别。本报告不构成科学结论、执行批准或测试通过证明。
