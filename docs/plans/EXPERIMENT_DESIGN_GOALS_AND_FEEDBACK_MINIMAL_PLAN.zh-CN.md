# 实验设计目标列表与研究反馈最小实施方案

状态：**2026-09-08 拟议方案；尚未独立审查、实施或部署。** 本文落实用户确认的职责：实验设计 Agent 根据总体目标、当前进展及可选实验结果和分析，保留完整目标清单，独立选定本轮最小实验目标，并说明后续目标的条件。总体、本轮和后续目标全部进入正式计划；只有本轮选中目标展开为执行任务。

源码根：`123/scidiscovery-e5.2`；分支：`refactor/m7-pre-e5.2`；核查 HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树已有大量未提交改动，实施基线须包含这些差异及未跟踪文件，不能只用 HEAD 代表现状。

## 1. 所有权与修正范围

本文是该设计调整的唯一拟议实施入口。采用 [设计宪章](../architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md) 的科学/控制所有权和 [R5-N 调度决策](R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md)：设计 Agent 决定科学任务范围，调度 Agent 从当前目录组织实际行动，控制面冻结输入与输出并执行声明的门禁。

| 文档 | 本轮处置 |
| --- | --- |
| 本文 | 拥有目标列表、反馈输入、本轮范围及实施验收要求；未实施前不作为当前能力声明 |
| [author 最小修复计划](TCAD_AUTHOR_FAILURE_MINIMAL_REPAIR_PLAN.zh-CN.md) | 保留工程修复和 R4/R5 有界结果；对新问题交叉链接，不改历史结论 |
| [Skill/execution_context 计划](SKILL_VISIBILITY_COMPATIBILITY_AND_EXECUTION_CONTEXT_REPAIR_PLAN.zh-CN.md) | 保留已部署修复及历史复用边界；新科学设计不再被误称为旧 author 的自动重试 |
| 当前架构、双语协议说明 | 实施后只更新受影响条目，不提前声称已支持反馈设计 |
| 端到端账本、README | 只更新入口关系，不复制本方案规则 |

原 R4 author 已 completed、双证明合格，但交接 blocked；R5 精确预检拒绝。这些事实见 [封存结果记录](evidence/TCAD_AUTHOR_R4_R5_2026-09-08.json)，不因本方案而改写。

本轮不增加阶段号、阶段状态机、任务类型、研究进度服务、数据库表或新的 public Operation。不修改 TCAD solver 源码、调试预算、执行服务、部署脚本和通用 Agent 前言。不把旧项目的交接改成 pass，也不以取消 `input_scientific_claim_forbidden` 作为解决方案。

## 2. 根因及已有实现的可复用部分

1. `EXPERIMENT_DESIGN_PROMPT` 要求最小有界研究，却未明确“本轮目标由设计者独立判断、未来依赖不成为本轮 case”。`ExperimentProposalIntent` 也没有专门的实验目标列表。
2. `materialize_experiment_design_intent` 将原始总目标写入每个 `ExperimentProposal.objective`。**保留总体目标是正确行为**；应增加设计者表达本轮目标的能力。
3. design 只绑定 foundation/objective/hypothesis/critic/execution_context，没有当前进展、实验结果和分析输入。普通下一轮设计不能被迫伪装成一次独立审查要求的 revise。
4. `validate_experiment_design_task_output` 要求单份计划覆盖总体目标的全部 mandatory targets，混淆了本轮实验完整性和整个研究闭合。
5. 现有通配端口只允许 `handoff_only`，而 Run materialization 和 assignment 明确不向 Worker 提供这种端口的文件。只增加这样的反馈端口，Agent 仍然看不到结果。
6. Root 的 producer admission 不区分只读查阅和资格消费。绑定未审查或合同已退休的研究记录作历史进展时，仍可能先被旧生产者合同/审查门拦住。必须显式处理这一用途，不能复制旧输出为 `opaque` 原始来源来绕过门禁。

现有曲线 compiler 按本份计划的 observables 选择对应目标；TCAD materializer 和 validator 覆盖本份计划的全部 case。**当计划保留完整目标清单、而执行字段只展开本轮任务时，这两处行为应保留。** 总体目标的 coverage/closure 由 `curve_score/objective.py` 等既有评价路径继续判断，不能把局部实验通过当成总体目标通过。

## 3. 实验设计的具体要求

### 3.1 输入

保留既有科学输入和执行背景。在同一个 design Operation 中增加三组可选输入，复用原 Artifact 文件，不创建进展汇总对象：

| 端口 | 绑定内容 | 缺席语义 |
| --- | --- | --- |
| `current_progress` | 与当前问题有关的已封存计划、审查、作者交接所对应的产物、诊断等原记录；续研应包含最近相关计划，以读取完整目标清单和未完成目标 | 首轮可无记录；续研缺席须说明“未提供”，不能推断没有既往工作 |
| `experiment_results` | 相关实验/仿真的已登记输出或确定性指标报告 | 没有结果仍可设计第一轮；不猜测选择结果 |
| `result_analysis` | 已封存的结果诊断、误差分析或科学解释 | 可以仅依据原始结果作设计判断；缺少分析不自动阻断 |

三组均采用已存在的 `schema="*"`、opaque codec、`usage="evidence_inventory"`、`exposure="on_demand"`；每组 `min_items=0,max_items=4`，每项最多 8 MiB；整个 design 输入上限 32 MiB。保留 900 秒和 64 KiB 输出上限，不加 solver/网络/外部执行权限。超限时重新选择最相关的原始记录，不截断后冒充完整原件。

不把三组加入现有 foundation 审批 cohort，也不要求全有或全无。结果、分析和进展是不同用途；同一 Artifact 不重复绑定到多个端口，其他用途在任务说明中指出即可。

Root 负责选择确切记录；科学进展不从子 Agent 聊天或草稿拼装。已启动/未启动等操作事实可依据受控查询写入冻结的任务说明，但不能用这一说明代替科学产物。输入缺少关键信息时，由设计 Agent 说明影响当前目标还是仅影响后续目标。

### 3.2 目标列表与后续目标

只修改实验粒度的目标表达，不改原始 `ResearchObjectiveContract.statement`、其 objective key、mandatory targets、closure requirements，也不修改 `ExperimentPortfolio.objective` 的总体目标含义。

- `ExperimentProposalIntent` 增加必填 `objectives`：设计者提出的完整实验目标清单，包含本轮目标和仍相关的后续目标，最多 16 项，每项沿用目标文本的 8192 字符上限。后续目标用完整语句写明依赖或触发条件；条件尚不能确定时明确写出待获得的信息，不猜测结果。
- 同时增加必填 `current_objectives`：本轮选中的非空目标列表，逐项引用 `objectives` 中的原文，最多 16 项。用字符串子集表达本轮选择，不增加目标 ID、目标服务、阶段节点或状态枚举。格式校验要求列表无空项、无重复且 current 是完整清单的子集；目标选择的科学合理性由 Agent 与独立审查负责。
- 将 `ExperimentProposal.objective: str` 改为 `objectives: list[str]`，并保留相同的 `current_objectives` 字段；Python 继续用严格、不可变 tuple 模型。物化时在完整清单前保留精确的总体目标文本，逐字重复的总体文本不重复插入，不合并或改写其余目标。完整清单最多 17 项，本轮选择逐字复制。原始总目标一致性继续由精确绑定校验。
- `value_assessment.rationale` 说明当前进展、本轮选择依据和最小性、对总体目标的贡献，以及后续目标之间必要的依赖。`handoff.next_actions` 只摘要这些已保存在正式计划中的后续意图，不能成为后续目标唯一存放位置。
- `cases`、变量、原始输出要求、当前预算和验证项只展开 `current_objectives` 的交付；保留在完整清单中的后续目标不会因此自动生成 case，需要未来计算才能选出的参数不得以占位 case 混入本轮。

因此，正式计划同时保存“还要达到什么”和“这次具体做什么”。“完整计划”要求目标清单完整保留、本轮执行方案完整；不要求现在实现所有后续目标。本轮不能为了让目标列表看似全部完成而虚构参数或扩大任务。

下一轮设计必须读取绑定的前一份相关计划与新结果，对照完整清单选择新的 `current_objectives`。尚未完成且仍有意义的后续目标继续保留；已经完成、证据否定或需要调整的目标，在现有 rationale 中说明依据，形成新不可变计划，不能无说明地丢弃。旧版本保留目标演变历史，不新增目标状态库或自动阶段推进规则。

### 3.3 设计、物化与审查

设计 Agent 先阅读当前进展和已绑定反馈，再判断本轮最小目标。存在多种可能行动时说明选择依据；不强制每次沿固定阶段顺序推进。当前输入足够开展某项有意义的有限实验时，后续目标缺参不应使本轮 handoff blocked；当前目标本身缺必需条件时，仍如实报告阻断。

移除 design validator 中“每轮必须覆盖总体 mandatory targets 全集”的循环。保留原始目标、假设集合、case/变量/验证项一致性、来源和单位约束。设计必须说明本轮覆盖及暂未覆盖的总体目标；独立审查判断其科学价值。既有总体 coverage/closure 评价仍须将未完成目标报告为未完成，不能自动变成 pass。

materialize 将完整 `objectives`、本轮 `current_objectives`、本轮 case 和说明转换为完整方案，不能过滤掉未选中的目标。反馈的来源保留在 `plan → intent → 原反馈` 父链中；**不把三组反馈再绑定给 materialize**，不重新计算分析，不借确定性变换给未合格输入授予资格。

`science.object.review.v1` 同样声明这三组可选只读输入，使审查者能独立核对本轮目标选择。Root 复用设计时相关的原记录；若补充反证，必须显式绑定并进入该审查的指纹。不同审查输入产生新审查，不继承旧 verdict。审查者说明缺失或不一致材料对判断的影响，缺少支撑关键判断的原记录时不能给出无保留 PASS。

下一轮根据新进展重新调用已有 design，旧设计和结果作为反馈输入。`science.experiment.revise.v1` 继续用于精确独立审查要求的局部修订；不新增“续阶段”Operation。完整对象修订和不继承资格的规则保留。

## 4. 必须同步的两个窄接口改动

这两项使第 3 节的原 Artifact 反馈真正可用；没有它们，方案会停留在提示词或不可见绑定上。

### 4.1 可见的只读通配输入

在 `InputPortSpec.issue` 的既有 wildcard 限制中，允许 `evidence_inventory` 使用 `on_demand`，保留原 `handoff_only` 路径。不引入任意 `claim_evidence`、revision 或 effect payload 的通配端口，不增加新的 exposure/usage 枚举。

继续走既有 frozen input → Local workspace → assignment 只读文件路径。输入 schema 由所属领域拥有，通用实验插件不导入 `curve_score`、TCAD 的模型，不创建统一结果包装器。不得用通配端口把框架文件系统暴露给 Worker；只有本次确切绑定的字节可读。

### 4.2 查阅历史与消费资格分开

在 Root producer admission 的既有循环中，为 **Agent 的 `evidence_inventory` 输入**明确只读语义：允许查阅已登记的未通过、待审查和历史合同产物，不以当前生产者合同一致或独立审查通过作为阅读前提。检查应位于旧 producer contract/审查资格解析之前，否则历史反馈仍无法进入。

保留实例归属、原字节/父链、显式 current 要求、大小/数量、请求指纹及只读权限。不得把旧对象标成当前合格对象；反馈只提供研究背景。新的设计及其科学前提必须重新接受本轮独立审查，历史 verdict 不继承。

这不是按 design 操作名或端口名写白名单；范围由现有 executor kind 和输入用途声明决定。`claim_evidence`、`revision_base`、`change_request`、`review_signal`、Transform 和 Effect 的原资格及独立审查规则不改，`input_scientific_claim_forbidden` 不删除。Transform 的非合格来源传播规则也不改。

实施时必须枚举已有 Agent `evidence_inventory` 消费者，验证它们确为查阅用途；发现某个消费者依赖这一端口承担资格输入时，先停下记录具体冲突，不把全局门禁删除。该变更不授权读取失败 Run 的未封存草稿。

## 5. 生产改动上限

按当前调用关系，限定为 **7 个已有生产文件**；不新增生产文件或公共行为：

| 文件（相对源码根） | 修改内容 |
| --- | --- |
| `src/scidiscovery/artifact_agent/schema/experiment_intent.py` | 完整 objectives 清单与 current_objectives 子集；物化保留总体及后续目标，逐字复制本轮选择 |
| `src/scidiscovery/artifact_agent/schema/experiment.py` | 同样保存完整清单和本轮子集；取消把总体目标全部覆盖作为每轮设计提交条件；保留其余闭合规则 |
| `src/scidiscovery/general_science_experiment_operations.py` | design/review 三组可选只读反馈端口和输入字节上限；不改 revise 的行为形状 |
| `src/scidiscovery/general_science_experiment_components.py` | design/review 提示与同源语义合同；说明当前目标、后续条件、反馈使用和科学审查要求；避免改共享前言 |
| `src/scidiscovery/operations/spec.py` | 既有 wildcard 规则只增加 `evidence_inventory/on_demand` 组合 |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | 仅将 Agent 的只读 inventory 查阅与 producer 资格消费分开 |
| `roles/scheduler.md` | 选择设计时绑定相关进展/结果/分析，消费设计者给出的本轮范围；不由 Root 代写科学目标或建立固定阶段表 |

TCAD、curve-score 生产实现默认零修改。目标列表变化只需更新其测试 fixture 中的实验构造，不借此改领域算法。若发现未覆盖的真实调用者或要增加新生产文件、服务、Schema 包装器、状态机、公共 Operation，先更新范围和影响分析再审查，不悄悄扩大实施。

文档只同步本方案、索引、两份架构说明中的输入/目标语义和受影响的调度说明。生成的 AGENTS/profile 由安装器重建，不手改生成文件。保留原始目标 schema、插件版本、Operation ID；编译身份按实际可达资源变化传播，不手写旧摘要兼容白名单。是否需 ABI 调整须以真实编译合同检查结论为依据，不能靠固定 ABI 值掩盖行为变化。

## 6. 实施步骤与验收

### P0：冻结基线并审查方案

保存完整当前工作树、7 个生产文件摘要、安装 catalog，以及现有相关正负例结果，证据写入仓库下本次 evidence 目录，不仅放 `/tmp`。审查重点是目标所有权、只读反馈权限、总体资格不被局部通过替代，以及文件范围。本文自身不宣称审查已通过。

### P1：目标列表及设计要求

先以当前代码复现：无法同时表达完整目标清单和本轮选中目标；总体两个观测目标而本轮只研究其中一个时被 blanket coverage 拒绝。完成目标模型、物化、design/review 要求及相应测试。后续目标保存在正式计划但不进入本轮 cases；总体目标继续进入每个实验的目标列表。

### P2：真实反馈输入

先证明当前 `handoff_only` 无 Worker 文件、当前 producer gate 会拒绝未审查/历史反馈，再实施两个接口改动和三组端口。经真实 Root preflight/invoke 与 Local workspace 验证可选性、精确原字节、只读性、上下文数量与大小边界。不能只检查 OperationSpec 字段或提示词关键字。

### P3：跨边界验证与工程独立审查

| 必须验证的场景 | 通过口径 |
| --- | --- |
| 首轮没有任何反馈 | 可正常设计；不得因未绑定可选反馈而出现隐藏必需输入 |
| 仅进展、仅结果、仅分析及三组同时绑定 | Worker 读到对应原字节；输入独立可选、改变输入会改变请求指纹 |
| 未审查/blocked/历史产物作为 feedback | 可以只读；原对象标签、版本和 verdict 不变；当前资格不自动继承 |
| 同一对象作为 claim、直接修订依据或执行输入 | 原身份、独立审查、current 与审批拒绝仍成立；不能借改用途获得执行授权 |
| 目标列表 | 总体、本轮及后续目标逐字保留；current 是非空子集；空项、空列表、超限、重复及不存在的引用均有同源校验 |
| 本轮范围 | 一个有科学价值的局部实验能 materialize；后续目标及依赖仍在正式计划中，TCAD 不要求未来 case |
| 总体目标仍未完成 | 现有 objective coverage/closure 不得返回整体 PASS；未覆盖检查不能被删除或伪造 |
| 独立审查 | 审查者可读取相关原反馈；目标选择依据不足或把后续任务混入本轮时作出有界修订/阻断判断 |
| 领域链路 | 新计划经现有 curve compiler、TCAD materialization/case-control checker；其全部本轮 case 验证保持严格 |
| 新一轮设计 | 封存第一轮结果后，用同一个 design Operation 绑定前一计划和新反馈；原后续目标可被选入新 current，仍未完成目标保留，完成/调整/放弃有依据；不改旧计划或继承审查 |

优先在既有 `test_agent_contract_alignment.py`、`test_general_transform_operations.py`、`test_m6c_producer_topology_removal.py`、`test_catalog_negative_cases.py`、`test_l4_local_tcad.py`、`test_m2_curve_analysis_boundary.py` 和 `test_catalog_installed_entrypoint.py` 中补充拥有该行为的回归。旧 wildcard 测试应改成“只读 inventory 可见，其他用途仍拒绝”，不能简单删除负控。历史 fixture 保持历史语义，新运行 fixture 使用新目标列表。

涉及 core 准入与共享实验 schema，聚焦测试通过后须完成全套回归；受当前环境限制按文件分批、独立进程串行覆盖，不并发 pytest、wheel 或真实 Agent/solver。安装态 wheel/loader/profile 验证合并为一批执行，另跑架构约束检查和 `git diff --check`。记录真实文件清单、命令、耗时与结果，不预填通过数。

### P4：身份传播、部署及真实设计验收

比较前后完整 catalog，逐项解释变化。共享 ExperimentPortfolio schema 会影响可达的设计、物化、审查、曲线及 TCAD 合同，不能声称只影响 design，也不能直接复用已退休资格。仅把旧记录当只读背景，不重写、重新摄入或伪装成新来源。

工程审查通过后沿用既有安装/新会话流程。重新查询实例与目录，根据实际兼容性绑定仍合格的科学基础，并把相关历史进展/结果/分析作为明确只读反馈，启动一个新的有界 design。没有仍合格的必需基础时，记录其精确退役原因，由目录决定所需重审，不用 feedback 端口代替必需资格输入。

真实验收重点是设计 Agent 是否保留完整目标清单、自主选择当前最小目标、说明后续条件，并只将本轮工作展开为执行方案。独立审查之后，再以新计划验证下游 author；不得继承旧 R4 项目的证明或旧 R5 请求。任何 solver 执行仍走原审批 UI。部署、科学设计或独立审查尚未发生时，不宣称本次科学闭环已恢复。

## 7. 完成边界与停止条件

本方案的成功标准是：**同一 design 保留完整目标清单，利用当前进展和反馈选择下一项最小实验；本轮执行方案完整，总体及后续目标不丢失，总体目标仍按原规则最终验收。** 分阶段、追加验证或局部返工不需要新增科研阶段类型。

以下情况停止并修订方案：需要改写科学历史；历史读取被误当成资格升级；仅靠删除负控使测试通过；必须给通用科研插件加入 TCAD/curve 模型依赖；新目标列表丢失总体目标或无说明地丢弃后续目标；当前未完成目标被标成总体 PASS；核心/领域额外改动超出第 5 节；或真实设计仍将未来依赖编入本轮。保留未决结果，不自动重试直到碰巧通过。
