# Operation 职责与输入交接最小修复计划

日期：2026-09-09。修订：R4（实施基线），补入独立复审 R3 的失败恢复接线；保留独立审查 R1 的 F1/F2/F3 修正，并按用户最新要求增加最小共同上下文交付。初稿由独立角色制定，R3 独立复审允许 A0/A 实施；本次按其 F1 补齐 B 的恢复接线，实施后审查精确增量。A0 的共同参考和角色输入调整、B 的分支/载体/版本决策在本文列明；C0 证据核定任务可开展，C 的生产实现暂停至 C0 验收通过，不能将整份计划标记为已具备全部实施条件。未实施、未运行测试、未部署、未操作研究控制面。

基线为 `123/scidiscovery-e5.2` 当前工作树，包含尚未提交的曲线分析工具、目标反馈、TCAD author 和部署修改。本计划不把 HEAD 或旧报告当作完整工作树快照。唯一新增文件为本文；实施前应冻结相关文件及未跟踪依赖的确切增量，保留全部既有修改。

## 1. 结论与边界

本轮收敛到“上下文足够、任务能交付、缺口能返回、完成有证据”。设计、分析、审查和 author 先获得共同职责参考与相关研究记录，再调整任务交付要求；author 的 blocked handoff 被完整项目及初始化收据要求挡住、初始化成功公式仅证明正常退出，这两项已有生产调用依据的问题才进入必要的代码修复。不建设通用下游端口快照。新增上下文交付只解决已确认的局部视野和材料不可见问题，不能以全局视角名义开放隐藏聊天、全部历史或其他 Worker 工具。

保留现有 Operation、四态 Run、独立审查、不可变父链、资格及审批机制。科学 Agent 判断当前实现需要什么、哪些分析条件可以后置；程序只检查显式结构、绑定身份、收据证据及执行授权。不要以关键词规则判断某个 mask、ledger 或 x_max 是否“科学必需”。

本轮实施集合为四项：

1. A0：通过现有编译角色资源提供共同职责参考；复用已有进展端口，修正已绑定审查的可见性，仅为缺交付入口的角色增加一个受限 current_progress。
2. A：修正设计、修订和计划审查要求，用已有科学字段交付当前可实现任务，不让设计者接手全部缺失工作。
3. B：优先复用现有缺口和审查结构，补齐 author 无项目负结果的提交路径，使其可封存、可独立审查而不可执行。
4. C：针对当前 SProcess R-2020.09 研究路径确定实际初始化证据，在该路径的提交、review/package 和执行准备处复用检查；不推广为所有求解器的统一证据框架。

每项生产修改都必须对应下表中的已发生问题。不能说明减少哪次无效交接、或补哪项完成证据的修改，移出本轮。

| 已发生问题 | 本轮响应 | 不由此扩张的能力 |
| --- | --- | --- |
| 局部角色不能据共同职责理解任务；author 的已绑定科学审查被 handoff_only 隐藏，缺进展入口 | 共享职责参考、审查正文可读和受限进展输入 | 完整聊天继承、全库读取、自动科学摘要 |
| 计划将逐行曲线核对交给没有原表输入的 author，计算域必要量也未交付 | 设计交付必要信息，审查区分当前实现依赖与后续分析条件 | 通用端口快照、依赖图、author 曲线审计 |
| author 要返回输入缺口仍须生成完整项目和初始化收据 | 负结果走现有提交与独立审查路径 | 新 Run 状态、自动路由、任意跨 Run 源码附件 |
| 跳过物理初始化并正常退出仍能得到通过标记 | 当前 SProcess 初始化证据及其执行准入检查 | 跨求解器证明框架、所有异常预先覆盖 |

曲线评分工具现有改动继续保留。不得为 author 增加逐行参考曲线审计、通用原始数据端口、scorer 或参考数据资格职权。

## 2. 静态证据与生产调用链

依据当前 `docs/ARCHITECTURE.zh-CN.md`、科学设计宪章、`SCIENTIFIC_AGENT_CONSTRAINTS.yaml`（AUTH-003、ROLE-001/002、UNC-001、DET-002、EFF-001、PLG-001）、当前比较评估和 R5-M0 候选账本；后两者只是有日期的历史评估，不是本工作树通过证明。另读 TCAD README、曲线评分移入分析计划及其独立实现审查 R1。该实现审查的 PASS 明确不代表部署、真实研究或总体科学完成；TCAD README 中仍称独立 transform/scorer 的段落需要随最终实现收敛为当前分析工具职责。

| 生产位置与符号 | 已证实行为 | 本轮意义 |
| --- | --- | --- |
| `src/scidiscovery/general_science_experiment_operations.py`：design、review、revise 声明 | design/review 有可选 execution_context 和三组反馈；revise 只有 prior_draft、change_request | 不能告诉修订者“读取原始结果”却不给端口；也不能假设 review 可以看到设计时未交付的输入 |
| `general_science_experiment_components.py`：EXPERIMENT_PROMPT、EXPERIMENT_DESIGN_PROMPT、OBJECT_REVIEW_PROMPT | 已要求当前目标、推导方法、资源和缺口；执行上下文目前主要描述 backend/release/arguments | 先明确“任务凭交付输入能否完成”的职责要求，不据此推定必须新增端口描述 |
| `schema/experiment_intent.py`：materialize_experiment_design_intent；components 的 _experiment_materialize | 机械展开 case、比较变量、验证计划，复制 frozen_invariants/resource/value 等科学内容 | materializer 不应补 x_max、选择数据或推导科学范围；必须验证交接信息经过物化不丢失 |
| `schema/experiment.py`：ExperimentProposal、ResourceEstimate；`schema/research_cycle.py`：ScientificReview | 已有数值变量/单位、冻结约束、runtime_basis、rationale、findings/evidence | 可表达本轮参数、依据和科学缺口；暂不新增通用“依赖图”或 readiness 状态 |
| components：_experiment_revision_context、_object_review_context | 前者保留确切实验身份；后者检查目标、真实输入别名和 handoff/verdict 一致 | 身份检查应保留；不能用 Python 阅读 prose 来替代独立科学判断 |
| `plugins/tcad_artifact/tcad_artifact/plugin.py`：INITIAL_INPUTS、_author_operation | curve_contract 可选；没有通用原始参考表端口；输出固定为 DeckProjectDraft，review_edge 指向现有 deck review | 不能以“合同现在可选”推断旧计划文本已经可实施；应修任务或封存缺口 |
| `operation_workspace.py`：materialize_workspace、finalize_workspace | SProcess 声明物化；finalize 先读取完整 metadata/files，再要求 current qualified preflight；initial author 必须 qualified initialization，之后才构造 envelope | blocked handoff 不是有效的无项目退出路径；声明负结论仍会被完整工程形状阻断 |
| `src/scidiscovery/artifact_agent/service/runs.py`：submit、_validated_candidate、_finalize_workspace；`run_outputs.py`：validate_run_output | workspace finalizer → 同一编译 Schema/语义校验 → 注册精确结果 → completed | completed 表示结果封存成功，可包含负科学结果；不需要第五种 Run 状态或绕过提交 |
| `debug_adapter.py`：prepare、collect、_earliest_diagnostic；`local_debug_service.py`：_finish | 初始化使用作者声明的开发入口；成功终态+exit 0 直接诊断 complete；_finish 用此生成 qualified | 代码确认形式成功可冒充初始化完成；本轮未读取现场原始日志，因此不自行断言某次脚本内容和执行事实 |
| `project_packager.py`：ProjectPreflightAttestation、ProjectInitializationAttestation | 初始化继承 preflight 的三条件等价校验；没有实际工作证据字段 | 不能只改 _finish；模型校验和消费方必须同源收敛 |
| 同文件：validate_deck_review_against_project、ReviewedDeckPackage；`transform_adapter.py`：package_reviewed_project | reviewer pass 要 execution_ready、完整一致性与 preflight；package 重物化和参数/case 校验保留；初始化收据被复制，但 review 的 execution_ready 校验主要检查 preflight | 独立 reviewer 正确拒绝仍是有效防线；不能只在 author 初次提交处补门禁，漏掉旧项目/修订/package |
| `operation_transforms.py`：package_parentage；plugin 的执行 Effect | project/review/capability/plan 精确父链进入 reviewed package，再进入精确执行审批 | 不修改通用 Effect 状态机；新建 package 与已封存旧 package 的执行准备入口均须检查 |

共有问题是上游的任务承诺超出下游可见输入，且 envelope 的负 handoff 不保证领域 payload 可表达负结果。TCAD 特例是强制项目工作区、源码物化、开发初始化及执行打包；不能把这些规则放入通用 Run 服务。

## 3. 最小行为修改

### A0. 共同职责参考与最小研究上下文

**三层信息，三个不同用途：**

- 全局职责参考：证据、假设、设计、审查、实现、执行、分析如何协作；谁能做什么、什么不属于自己、缺口有哪些合法处理方向。描述可组合的职责，不是固定顺序或第二套 catalog。
- 当前研究背景：总体目标、当前任务与目标的关系、最近相关结果、已有失败及未完成条件。来自精确绑定的科学记录；由本轮 Agent 阅读理解，不由调度者编造“最新进展”摘要。
- 本轮权威依据：当前计划、输入数据、匹配审查、能力和实际结果。历史建议不覆盖当前计划，先前 PASS 不授予新成果资格，当前任务缺失信息不因知道全局而自动补齐。

#### A0.1 角色—实际输入—缺口—最小修改矩阵

静态入口：`run_assignment.assignment_json` 从 RunInputBinding 生成 source_name/relative_path/usage/exposure，明确排除 handoff_only；local_workspace 只物化受控输入。下表针对实际 exposure，不将“端口存在”当作“Agent 已收到”。

| 角色/入口 | 当前可用材料 | 已确认缺口及修改 |
| --- | --- | --- |
| 实验 design | objective、portfolio、critic、可选 execution_context；current_progress/results/analysis 是 on_demand inventory；foundation 为 handoff_only | 复用全部现有端口及 cohort。提示要求启动时读取本轮绑定的总体目标和相关进展；不扩大 foundation 暴露，不增加新端口 |
| 实验 revise | prior_draft、change_request；无独立进展入口 | 增加一个可选 current_progress，提供原始目标及相关已封存进展。需要新的原始实验数据或整体重设计时仍走已有 design，不批量添加 results/analysis/context 端口 |
| 独立科学计划 review | plan、可选原始 objective/execution_context 和三组反馈 | 复用端口，调度明确绑定原始目标及相关进展；新 reviewer 独立判断，不把此前 verdict 当作结论 |
| TCAD author 初始/修订/runtime-failure | plan/capability；修订另有 prior_project/change_request 或 runtime log；experiment_review 为 handoff_only；无进展入口 | INITIAL_INPUTS 增加一个可选 current_progress，由三类 author 共用；experiment_review 改为 on_demand，使已绑定限制可读；不开放曲线原表审计或其他 Worker 权限 |
| 独立 TCAD deck review | project、共享 INITIAL_INPUTS；科学 review 同样不可见 | 随 INITIAL_INPUTS 复用 current_progress 和科学 review 正文；被审工程、缺口及科学计划仍是精确 subject，不继承作者隐藏推理 |
| 通用结果分析 | plan、results、reference_material、current_progress；experiment_review 为 handoff_only | 复用进展端口，在 current_progress 绑定原始目标/相关进展；只把本分析入口的 experiment_review 改为 on_demand，并纳入 context_sources，不改共享 _review_input 导致所有旧入口变更 |
| TCAD 结果分析 | plan、package、runtime、outputs、reference、current_progress；experiment_review 为 handoff_only | 复用进展端口和父链检查；experiment_review 改为 on_demand，已有动态 context_sources 随之纳入 |
| 其他假设设计、证据审计及曲线审查角色 | 已有各自基础证据、被审对象和专用输入 | 共享前言覆盖全局职责，不批量改变领域端口。安装前列出实际收到此前言的角色清单；发现未收到或确有当前进展缺口时单列事实，不宣称所有角色已完成背景交付，也不顺带扩展本案例无关合同 |

本轮保证前七类实际闭环角色的三层上下文路径；全局职责参考通过已有共享前言覆盖其余使用者。不是给每个 Agent 输入同一套全部材料。独立审查保留同一科学背景和输入身份，但从不继承作者会话、未封存草稿或摘要指令。

#### A0.2 参考的唯一来源、注入和界限

使用 `src/scidiscovery/operation_declaration.py` 中一个短的 `RESEARCH_WORK_CONTEXT` 文本常量，并由现有 OPERATION_AGENT_PREAMBLE 组合。该模块已经是通用科学、实验设计和两种结果分析 prompt 的公共来源；TCAD `role_pack.role_prompt` 只组合这一共同文本与已有角色文件，避免复制文本或拼接重复的整个通用前言。参考正文限定约 4 KiB UTF-8，不创建新 Artifact、状态库、catalog API、Skill 查找权限或流程图解析器。

正文只表达稳定职责与上下文使用规则：作者实现、分析评估结果、审查独立判断、调度选择合法 Operation；不得将分析条件一概前移；有缺口可缩小、后移、改方法或明确不可行，不以必须产出成功对象为要求。准确工具权限和本轮输入仍取自编译 assignment/schema。参考不嵌入可能漂移的 operation ID、端口表或成功状态映射。具体 TCAD 能力由绑定 capability 和现有角色参考给出，核心不硬编码 SProcess。

需要精确上下文时仅通过已声明输入读取工具获取；没有授权的合同检索入口就报告未知，不能让 Worker 浏览全库/catalog。共同参考不得暗示它可以查询控制面或调度其他 Agent。

资源正文进入每个消费它的实际 prompt 字节与摘要闭包；列出受影响 Operation 摘要，避免全角色重部署时旧 Run 跨版本继续提交。共同参考只有一份权威文本，不维护另一份手写端口登记表。

#### A0.3 当前进展的交付决定

复用 evidence_inventory。新增 revise/INITIAL_INPUTS 的 current_progress 为 `schema="*"`、media `*/*`、min=0/max=4、单项最大 2 MiB、exposure=on_demand、usage=evidence_inventory；复用各插件已有 wildcard schema/codec，保留各 Operation 总输入预算，不因加端口提高总上限。进入对应输出 context_sources，绑定字节进入既有指纹。TCAD 的 _input helper 当前未暴露 max_items：该新 inventory 端口使用一个明确 InputPortSpec（复用现有资源），不改所有旧端口默认值。不得把此端口加入 approved_parameters cohort 或把历史材料升级为 claim_evidence；仍按现有来源和身份规则验证。

每次恢复以已查明的原始 objective 为背景起点：有专用 objective 端口则使用；没有的角色将原始 objective 放入 current_progress，剩余至多三项选择最近相关分析、失败/缺口及审查。已有 plan/package/change_request 端口承载的同一记录不重复占用进展槽位。没有前轮结果时省略，不生成“无结果”占位 Artifact。相关性由调度者按当前问题和封存记录选择，不通过 Python 推断科学进度。

提示明确：开始判断前读取总体目标、当前计划/任务及绑定进展；大表、原始日志按需读取。记录过大或父项缺失时给出具体限制；不能把上下文完整性升级为每次必须绑定四项历史的机械门禁。author 可据此指出任务/能力不匹配，但不得自行改变目标；设计者不被要求执行全部缺失工作。

已有计划字段承担研究进度的科学表达：总体目标、current_objectives、deferred objectives/条件及理由；不足信息在现有 findings、missing_inputs 和 handoff 表达。下一 Run 读取领域 payload，而非默认能读取生产者 handoff。调度 instruction 只说明任务与绑定用途，不新增科学事实摘要。不新增共同进度 schema、自动摘要 Run 或研究状态机。

**修改文件边界：** operation_declaration.py；general_science_experiment_operations.py 的 revise 输入/context_sources；TCAD plugin.py 的 INITIAL_INPUTS/exposure、对应 context_sources；curve_score/science_operations.py 的当前通用分析入口；TCAD result_analysis.py 的审查 exposure；TCAD role_pack.py；相关角色提示及 roles/scheduler.md 的绑定指引。run_assignment.py/local_workspace.py 作为验收入口，当前无证据需改其生产逻辑。若实际读取失败只报告具体入口，不默认重构 workspace。

### A. 设计交付与独立计划审查

**修改位置：** `general_science_experiment_components.py` 中共享设计、修订与计划审查要求，以及确实承载相同职责的角色文本。**只读核对位置：** `general_science_experiment_operations.py` 的现有输入声明、`schema/experiment_intent.py` 的物化路径。本项不修改 ExecutionContext、其投影或计划必填 schema；输入/exposure 的必要变化仅按 A0 明确清单实施。

设计者不得假设下游能读取自己看到的全部材料、历史聊天或未绑定文件。先使用现有计划字段交付必要信息，而不是要求它推断未知的下游端口。设计必须做到以下之一：

- 在现有 variables/expectations/units、frozen_invariants、资源 runtime_basis 等实际进入完整 plan 的字段中交付必要数值、边界条件及确切科学依据；
- 给出可复核的推导方法，并将其必要操作数、单位和依据保存在实际交付的计划中；如果确实依赖独立输入，只有明确知道该输入可被合法绑定时才以其为条件，否则记录未解决的交接缺口，不能宣称 author 已具备它；
- 把仅影响后续比较的条件放在 validation/判断方法及 rationale 中，说明受限结论，不把它写成求解代码前置工作。

对于 x_max 一类决定本轮计算域的量，设计者必须凭绑定证据交付数值与单位，或凭可用证据给出充分且可复核的科学替代方案；不能只写“author 去原表求最大值”。本文不选择其数值或方案。小型必要数值不必再造输入文件；大表若为真正实现必要条件且既有端口无法交付，则封存缺口、停止本轮，不悄悄扩展 author 权限。

revise 同样遵守上述职责，仅按 A0 增加一个受限进展入口，不批量增加反馈端口。prior_draft/change_request 与相关背景足以支持的局部修改走原修订路径；需要重新读取原始结果、进展和目标时，由调度者从现有 catalog 选择已有反馈输入的 design，绑定确切原始目标和相关记录。不能给 revise 下达依赖它未收到材料的任务，也不能把不同 review 类型互换来满足端口。

共享设计提示增加“从实际交付输入完成下游任务”的判断，review 提示要求指出尚未交付的**当前必需**条件，并使用已有非通过结论要求解决；不能一面认定当前不可实现，一面 PASS 并把补齐关键输入留给 author。正常的初始化、数值验证和执行审批仍可在相应后续环节进行，不能反过来要求设计前完成全部工作。未来分析条件未准备不自动否定本轮。复用 ScientificReview.findings/evidence 与 RoleHandoff.missing_inputs，无需新增 Review 状态或 Python 科学否决器。完整 plan 字段已能承载交付内容，故本轮不改 ExperimentProposal/Intent 的必填形状；用现有物化回归证明数值、依据、延后条件保留。

重新设计必须选择有依据的响应：删除/后移非当前必要要求、使用已有证据支持的方法、缩小当前目标并保留后续条件，或明确该实验当前不可行。设计者不默认替 author 完成曲线审计、补充研究或求解器开发，也不以必须产出可执行方案为成功条件。review 检查原缺口是否被实际解决，而非改名、转交或新增前置任务；没有输入、范围、方法或能力的实质改变，不原样再启动 author。若共同参考与现有绑定仍不足，封存具体失败，再评估最小描述，不自动扩展通用能力。

### B. author 可提交真实缺口，不伪造项目

**文件/符号：** TCAD `project_packager.py`（输出模型及 author/review validators）、`plugin.py`（project schema/semantic contract）、`operation_workspace.py`（模板、恢复、finalize、review 物化）、`transform_adapter.py`（review validation 的输入解析）；角色 `tcad_deck_author.md`、`tcad_deck_reviewer.md`。

优先复用 RoleHandoff 的 blocked/inconclusive、summary、missing_inputs、assumptions。它只存在结果 envelope，下一 Run 的 payload 不保证带 producer handoff，因此必须在领域 payload 中保存最小缺口信息。

**冻结输出决定：** 保持完整 DeckProjectDraft 原样，author 结果 schema 为 `DeckProjectDraft | ImplementationGap`，两分支严格互斥且禁止额外字段。负分支复用现有 missing_inputs/summary 的表达，不扩展成通用失败分类。具体形状：

- `schema_version: 1`，`result_kind: "implementation_gap"`。
- `summary`：1–2048 字符。
- `missing_inputs`：0–16 个非空字符串，每项不超过 2048 字符；能力或职责不匹配而非缺数据时允许空列表，不能逼作者虚构缺失参数。
- `affected_work`：1–16 项，每项含 `plan_locator`（1–512 字符）、`impact`（1–2048 字符），定位需在绑定计划中存在，程序检查可确定的定位存在性，不判断科学必要性。
- `suggested_resolution`：1–2048 字符，说明设计调整或补充输入的理由，作为建议而非路由指令。

该分支不含 files、entrypoint、case、能力哈希或任何 qualified 收据。关联 plan/capability 继续通过不可变输入父链表达；不另存一份权威身份。复用 RoleHandoff，负分支要求 verdict=blocked，missing_inputs 与 payload 一致；pass 或冲突内容拒绝并返回可修正诊断。无项目并不等于 Run 失败，合法封存后仍为 completed。

**冻结载体与恢复优先级：** 新增一个可选、可删除、上限 64 KiB 的 `deck/gap.json`，只承载上述负 payload；继续使用 `deck/handoff.json` 和现有 finalizer 生成 `output/result.json`。不把 SProcess 控制生成的 project.json 改为可写，不新增提交工具。

1. 当次提交先检查 gap.json；存在则有界解析并验证 handoff，再封 envelope。此分支不读取 files、不物化 declarations、不要求 debug。即使有旧 files/project/declarations，也只视为未提交草稿，不混入负结果；gap.json 错误必须返回错误，不能回落到完整工程提交。
2. 恢复只在最新的适用 provisional root 内选择：受控保存的当前领域草稿优先，显式 gap.json 优先于 raw tree；只有没有领域草稿时才回退 result.json，结构有效不等于已接受或最新。gap 存在但损坏仍恢复为待修正的缺口草稿，不能静默回退较旧工程。恢复 gap/handoff，不将该目录残留源码作为后续成功候选。没有 gap 时保留原有 raw-tree/完整工程恢复行为。
3. Worker 若在同一受控工作区解决缺口并改交完整项目，必须显式删除 gap.json，再按原完整工程路径重新物化和诊断；旧封存 Artifact 不覆盖。工作区说明必须公开这一选择规则。
4. independent review 的 project 输入按同一 union 解析。gap 只作为只读缺口输入展示，不创建假源码；复用现有 findings/missing_inputs/unknown fidelity 和 blocked/revise 结论，execution_ready 必须为 false。正常工程仍走既有完整审查。

**冻结版本决定：** 保留逻辑 schema ID `tcad.deck-project.v1` 和旧完整项目的原 JSON 形状；该 ID 的唯一 schema 资源扩展为上述 union，不并行注册第二份同 ID schema。作者各入口及 deck review 的 Operation version 从 1 增至 2，包含 A0 上下文变更，资源摘要覆盖新 schema、解析器和工作区/角色要求。`project_validator` 及 author context validator 先按 union 分派；不能通过放宽 DeckProjectDraft 必填字段实现。编译时目前校验资源 `$id` 与端口一致，未要求根节点必须是完整工程模型；安装验收仍须验证实际 JSON Schema 和摘要，不能只依赖这一静态结论。

| 消费者 | 明确行为 |
| --- | --- |
| author 输出、deck reviewer 的 project 输入 | 接受上述 union，按分支处理 |
| author revise/runtime-failure 的 prior_project | 仍要求完整 DeckProjectDraft，gap 返回明确不适用 |
| compare、realization、package、执行准备 | 仍用完整工程解析入口，拒绝 gap，保留已有身份和源码校验 |
| design 的 evidence_inventory 反馈 | 可读 gap/review 的领域 payload，不恢复其 claim 资格 |

旧完整工程仍可读；旧 Run 不跨新合同提交，旧 review 不授予新输出资格。共享 helper 影响到的其他 Operation 通过其声明资源摘要失效，实施时记录确切 catalog 差异，不任意扩大语义变更。

本轮负分支解决任务/输入不足及职责、能力不匹配；原因放在 summary、affected_work 和 suggested_resolution 中，不新增通用失败分类。已有完整项目的诊断、修订和恢复保留；不重新设计代码调试失败格式，不新增跨 Run 任意源码附件或自动路由。无项目缺口解决后按 catalog 新建 author，不能把 gap 冒充 prior_project。

### C. 当前 SProcess 路径的初始化必须证明实际工作

**文件/符号：** TCAD `debug_contract.py:CollectedTCADDebugRun`、`debug_adapter.py:prepare/collect/_earliest_diagnostic`、`local_debug_service.py:_finish`、`project_packager.py:ProjectInitializationAttestation/validate_deck_review_against_project`、`operation_workspace.py:finalize_workspace`、`transform_adapter.py:package_reviewed_project`；必要时更新 declaration materializer 中初始化声明及角色合同。

初始化与语法预检的语义分开：exit 0 仅证明进程正常终止。本轮只修当前 SProcess R-2020.09 路径。先从已有可信输出和读取能力中选定一项能证明实际初始化步骤发生的原生证据，再决定既有收据需补的最少字段。沿用 source/project/declarations、开发入口和受控输出的确切绑定，不重复保存另一份权威状态。

证据必须能区别“构造并初始化了本次结构/状态”与“打印 skipped 后退出”。实际结构/网格状态输出可作为候选，但只有证实其格式可验证、与本次入口和源码相符、覆盖要求的初始化步骤后才能采用；文件存在、任意非空输出、作者自行 puts 的完成标记都不够。确定性读取证明实际步骤，独立 reviewer 判断物理实现和计划的一致性，不能把两者互相替代。

**C0 状态：待执行；C 生产实现：暂停。** 静态证据已经排除“直接复用现有 TDR 读取器”的假设：`debug_adapter.prepare` 清空 expected_outputs，`prepare_submission` 拒绝非空 expected_outputs；`_evaluate_runtime_assertion` 的 tdr_metadata 分支固定报告 provider 不可用。`attest_runtime_contract` 的名称不构成可用证据。不得仅加收据字段再手工构造正例。

C0 是有界核定任务，不是另一个 Operation 或新科研阶段。其唯一交付是一份工程证据决策记录，必须包含：

1. 从合法可读的既有真实 SProcess R-2020.09 开发记录获得一份可信正样本及其来源、摘要、输入源码/入口对应关系。测试中的 fixture-tdr 和手写成功日志不作为可信正样本。若没有合法可用样本，明确记录缺少哪份输入，C 保持暂停；不得绕开研究绑定读取私有状态或擅自运行求解器。
2. 选定一种原生证据、能够证明的具体初始化步骤及读取函数。日志方案须证明能区别跳过和作者伪完成标记；文件方案须能验证格式与状态，不能只验存在/非空。若现有工具无此能力，列出最小领域读取实现；不能用未经验证的 TDR 格式猜测填补。
3. 列明完整生产路径：初始化模式生成有限输出声明 → `prepare_submission` 对该模式的精确例外 → 既有 transport 提交与收集 → `collect` 校验实际字节和本次绑定 → `_finish` 生成证据收据 → 统一执行用途检查。若选日志，明确复用现有哪份受控日志，保持 expected_outputs 禁止规则；若选文件，只允许本证据所需的输出，不把任意 study 输出带入 debug，也不修改其他模式的边界。
4. 冻结资源上限：最多一个证据文件或一份现有日志，单份最多 8 MiB，不超过既有 debug 剩余输出预算；解析最多 10 秒且不超过剩余任务期限，单进程、无网络、无后续求解。若实际样本超出此界限，先证明原因再修订范围，不能自动扩大。
5. 给出可信正例通过同一 prepare/transport/collect 入口的验收设计，以及 skipped+exit0、伪标记、错来源/旧证据、源码或声明变更的拒绝设计。记录哪些能定向夹具验证、哪些需要合法真实运行；不得以 mock qualified=true 验证真实初始化。

C0 决策经静态复审确认可实现后，才把选定证据、确切文件增量及适用 capability 写回本计划并解锁 C。若没有可信证据，A0/A/B 可以继续，但 C 和本案例执行就绪验收保持未完成；不得因只能验证 exit 0 而放行。

对该 SProcess 路径复用一个证据校验，贯穿 `_finish`、收据验证、author 提交、`validate_deck_review_against_project` 和 `package_reviewed_project`；同一源码的修订不能靠省略开发入口绕过。旧已封存 package 可能绕过重新打包，因此还需在 `project_packager.py:validate_reviewed_deck_json` 的执行用途入口及 `runtime_plugin.py:execution_projector` 复用此检查；`execution_adapter.py`、`command_adapter.py` 现有准备路径消费该入口，无需新建 Effect 状态。历史分析保持兼容解析，不把旧结果一律判不可读。

保留 preflight 的结构/语法意义；初始化证据通过不自动产生独立 review PASS。共享代码中的适用范围须明确限制为本轮 SProcess 路径，不顺带更改 SDevice 或其他版本的资格政策，不声称其初始化问题已经修复。若无法在现有插件内限制范围而必须改造所有求解器，停止该扩展并重新评估。

**B 恢复接线（R3/F1）：** 在失败隔离前调用该 Operation 已声明的 workspace_snapshotter，使用当前 recovery digest/candidate 保存领域草稿；不调用 finalizer、不要求语义有效或 debug。仅声明 hook 的工作区启用，最多 132 文件/32 MiB，路径和字节仍由 backend 验证；无 hook 保持原 result 恢复。snapshot 覆盖 gap/handoff；有 gap 时不要求 files 存在，无 gap 时保存现有 project/declarations/files。snapshot 失败不得偷偷选旧 result 假装最新草稿已保存，应保留失败原因/无恢复事实。已接受候选仍优先保留原 exact digest，不替换接受后的内容。必要修改范围包括 runs.py 与 local_workspace.py 的已有 seal/discard seam；不增加数据库状态或提交工具。

真实 fail/timeout→discard→新 Run 验收必须覆盖：旧 result+新 gap；旧 gap result+删除 gap 后的新源码；无 result 的损坏 gap；普通无 hook 的 result 恢复。不能只手造 provisional root 测 helper。源码/输入身份与原重试预算保持不变。

## 4. 合同、历史兼容与部署

- A0 不改原始科学对象字节或必填形状。新增 optional current_progress 对旧请求保持可省略；experiment_review 改为可读不放松其原身份、review/admission 要求。能力未知或无历史时可以报告限制，不以背景不齐为所有操作统一拒绝条件。
- A0 的 revise、当前通用分析和 TCAD 分析在各自当前 version 基础上增加 1；author/deck review 与 B 合并为 version=2，不重复增加。仅共享前言字节变化的其他 Operation 保持自身语义版本，由编译资源摘要体现行为变化；实际发布清单列明所有改变的摘要和活跃 Run，不能只列 TCAD。若当前实际版本已变化，先记录新基线再增加，不覆盖已有版本。
- 不修改旧 Artifact 字节、父链、旧 review verdict 或旧 qualified 值。旧完整项目、旧上下文、旧初始化报告保持可解析；对本轮 SProcess 路径，旧 exit-0 初始化报告只能作为历史诊断，不能升级为新执行资格。需要新增证据版本/profile 时保留旧 profile 的历史解析，不改写 v1 内部意义；其他求解器不在本轮资格变更范围。
- gap 合同按 B 的同 ID 单一 union 资源、author/reviewer version=2 决策实施，贯穿 schema、context validator、workspace hook、review、重试及工程消费者。若实际编译入口拒绝该方案，记录具体错误并回到合同决策复审，不在各消费者私自引入其他版本或第二套 author。
- changed plan 必须产生新 revision，重新科学审查；changed source/初始化声明使现有 source/project/declaration 摘要失效，必须重新诊断与独立 deck review。不得沿用旧 review、package 或执行批准。Run completed 仅表示负/正结果已封存，UI/调度不得据此声称工程可执行或总体目标完成。
- 更新组件资源与 Operation digest；检查静态角色资源是否进入摘要闭包。部署前保存所改源码、wheel、catalog 摘要和活跃 Run 清单；现有控制面会拒绝合同漂移，不能添加“兼容放行”绕过。旧 active Run 在原合同下完成或显式失败后新建 Run，不能跨版本提交隐藏会话。
- 先完成静态独立审查与小范围行为验收，再在现有 deploy/install.sh、reinstall.sh 路径做一次必要安装验证和部署。部署脚本本身不预设需要修改；已有轮子/角色资源打包足够则只使用它们。源码检查、安装验证、部署和真实研究恢复分别记证据，不复用某一步的 PASS。
- 本轮 SProcess 路径中缺少新证据的旧 package，即使已审批也不得在修复后自动启动；真实恢复应从确切计划/项目审查重新进入现有绑定和审批链。已经执行的旧作业只保留真实历史，结果分析说明证据限制，不撤写运行事实。

## 5. 实施顺序、停止与回滚

1. 冻结相关工作树及合同基线；核对 B 冻结合同与实际编译资源，开展 C0；C0 没有通过时明确暂停 C，不用占位探针模拟成功。
2. 做 A0：共享参考、矩阵中确切端口/exposure 和调度绑定要求，先核验实际 assignment 与输入文件；再做 A 的角色职责调整，保留科学字段和 materializer。检查提示没有要求读取未绑定材料，也没有把正常后续验证提前。
3. 做 B：union 负分支一次贯穿 submit/review/恢复/执行拒绝；通用 Run 服务原则上不改。若必须新增通用状态或第二套提交协议，停止并重新审查范围。
4. 做 C：仅当前 SProcess 的证据生成和同源准入检查。无证据负例先成立，再以可信 SProcess 正例证明正常工程可以推进；不得只实现拒绝路径。
5. 串行运行下节小集合；修复仅限失败揭示的本轮问题。独立工程审查通过后做一次安装入口验证，最终再按现有批准机制部署和恢复真实研究。

回滚只撤本轮明确增量，不回退整个工作树；保留新旧封存对象。角色要求回滚仍须匹配相应 Operation 摘要。若已写出新 gap/初始化证据对象，回滚服务必须保留其只读兼容能力；否则停止该实例新工作。不得通过回滚重新让本轮 SProcess 的旧 exit-0 收据取得执行资格。新旧合同不能在同一活跃 Run 混用。

## 6. 少量行为验收（本轮不执行）

| 行为 | 最小检查及复用位置 |
| --- | --- |
| 相关角色实际收到三层上下文 | 复用 assignment/role contract 和现有 author、analysis 夹具，参数化覆盖矩阵前七类入口：真实编译 prompt 含同源职责参考；assignment 可见原目标/计划/进展别名；on_demand 文件确实可读取；原 handoff_only 科学 review 在指定入口已可读；无新端口的 design 正常复用旧绑定。检查原 mandatory 身份门禁保持，optional 背景缺省不制造新拒绝。不要新增只断言提示词句子的回归 |
| 缺分析条件仍可实现 | 复用 `test_general_transform_operations.py` 和 `test_l4_local_tcad.py` 的 materialized author/review/package 路径，构造已交付必要数值、未绑定曲线合同/评分资料的计划；确认 current case/数值/延后分析条件经过 materialize、author 输入仍准确，真实工程可推进。不要新增大规模曲线评分回归 |
| 缺实现条件封存可审查并返回设计 | 扩展现有 `test_local_tcad_author_debug_and_independent_review_share_one_operation_path` 或同文件最小同路径夹具：无 files/入口/诊断的 gap 经 submit 成为 completed 负结果，下一独立 review 从实际 payload 读到缺口且 execution_ready=false；以实际生成的 Artifact 名和完整正确 cohort 调用 design preflight，打开新设计输入确认 gap/review 可读。覆盖错误 cohort 或负记录作为 claim_evidence 的拒绝；package/修订不得误接 gap；pass handoff+gap 必须拒绝 |
| 跳过初始化不能放行 | 替换 `test_materialized_sprocess_binds_declarations_and_seals_initialization` 中仅模拟 exit 0 的成功证据；扩展 `test_author_submission_requires_current_control_diagnostics`：exit 0+skipped/无真实证据、旧 profile、源码变化均不得获得新执行资格；同时覆盖 review/package 的历史项目入口及旧 package 直接执行准备入口 |
| 完整输入真实推进 | 复用 `test_materialized_sprocess_author_review_package_preserves_case_anchors`；采用可信初始化记录正例验证 submit→独立 review→package 的精确绑定。部署后真实研究只使用封存真实输入，独立 author/review 与 loopback 审批，运行和分析分别留下证据 |

前两行的科学可行性判断仍由实际独立 Worker 的封存内容验证；单元测试只证明结构与接线，不能证明 x_max 科学合理。安装入口验证复用现有 `test_catalog_installed_entrypoint.py` 或既有有界安装探针，只有本轮资源打包/摘要风险需要时才选一个；不重复安装。

B 另复用现有恢复夹具做一个有意义的分支测试：gap 与残留 files/declarations 共存，经 retry 仍是 gap；损坏的 gap 返回诊断而非回退工程。沿用旧完整工程解析正例，并核对新 schema/角色进入摘要。C 的正例必须经 C0 指定的真实收集入口；旧 package 执行拒绝与历史分析可读分别断言，不能在基础解析模型中一并拒绝旧 JSON。

能力/职责不匹配的负例复用同一 gap 接线：missing_inputs 为空但 affected_work 和理由明确时可封存，不能强制生成占位输入或代码；结果不具执行资格。背景不能覆盖本轮权威对象的科学判断由实际独立 Worker 验证，单元测试不模拟语义理解或自动判读自然语言。

测试预算：严格串行、单进程，不用 xdist；每条命令建议 `ulimit -v 3145728`（KiB，约 3 GiB）及 `timeout 180s`，安装探针单独有限超时。选命名用例，不运行全量、压力、benchmark 或重复安装；一次通过后不无理由重跑。内存/超时不足应记录并调整有证据的单项范围，不自动扩大资源或追加全套测试。

### 真实跨轮验收：当前研究案例

定向测试只证明结构、绑定和准入机制。整轮完成还须留下以下真实流程证据，不继承聊天背景，不以测试通过替代：

1. 调度者按下表恢复完整科学 cohort 及反馈，使用同一不可变请求 preflight→invoke。新设计 Agent 只凭绑定记录说明进展、当前可实现目标、必要输入及后续未完成目标。
2. 匹配的独立科学审查收到同一原始目标及相关背景，确认任务可交付，没有将未解决的关键输入包装成 PASS 后的 author 义务。author 通过计划、可读科学审查及相关进展理解本轮目的、职责和后续条件，完成真实项目与本次 SProcess 初始化；独立领域审查核对成果；外部实验遵循精确 UI 审批。各 Agent 均不继承聊天。
3. 实际结果进入现有分析 Operation，原始目标和相关进展通过 current_progress 提供，匹配科学审查正文可读。证据或可选评分不足时，分析封存有限或不确定结论，说明对总体目标、本轮目标和后续工作的影响；不要求先补齐所有评分条件才能返回结果。
4. 下一位设计 Agent 绑定该结果、分析及相关进展，形成有理由的下一轮目标与计划，保留总体目标和未覆盖部分。取得第一轮结果不等于总体研究完成。
5. 中途出现缺口时，封存缺失条件、影响工作和建议；调度者根据 catalog 返回设计、证据或代码修订的适用入口。记录输入或任务发生了什么改变，不原样重试。遇到新缺陷先判断是否直接属于 A0/A/B/C；无此关系的另记问题，不自动扩充本轮。

真实流程尚未跑完时，状态只能是“机制修复已验证、真实跨轮验收未完成”或具体阻断，不能称整轮已通过。所有 Agent 和验证串行运行，实际求解资源另按已审查计划及执行预算约束。

**冻结设计恢复接线：** 先 instance_current；从当前计划沿唯一 prior plan 父链回到物化计划，查询各直接父项的 schema，恢复原始 objective、foundation、hypothesis portfolio、critic review；从 design intent 的父链定位相关反馈。名称必须通过当前实例 catalog 验证，不按文本或同 schema 猜替代品。

| design 端口 | 必须绑定的确切记录及条件 |
| --- | --- |
| scientific_foundation | 原计划所用且与以下三项匹配的 foundation，满足既有 qualification/admission |
| research_objective | 物化计划直接父项中的原始目标；其父链匹配同一 foundation |
| hypothesis_portfolio | 原计划所用 portfolio；父链匹配同一 foundation |
| critic_review | 与上述 portfolio 和 foundation 匹配的独立 critic；保留 catalog 声明的 review/资格要求 |
| execution_context（可选） | 当前选定 capability 的既有上下文投影，不加入通用端口描述 |
| current_progress（0–4） | 当前计划、匹配科学审查、本次 author gap、本次领域 review；按需取相关记录，不超过端口上限 |
| experiment_results（0–4） | 本次设计确需的原始参考或实际结果，如该案例两张曲线表；精确绑定，不只在指令中写名称 |
| result_analysis（0–4） | 有则绑定相关封存分析；初次恢复没有分析时省略，不构造空成果 |

以上数量以调用时 catalog 为最终依据。feedback 的 evidence_inventory 允许读取负/历史记录，但不授予 claim 资格，也不替代四项必选 cohort。缺父项、资格过期或 cohort 不匹配时，保留精确拒绝与有界缺口；仅从 catalog 选择适用补救及既有审批，不猜替代记录、不转换聊天为批准。后续科学审查绑定同一原始目标和相关反馈；不能把领域 review 当 generic change_request。

## 7. 明确不做与待决事项

不新增 Operation、研究状态机、通用依赖 DAG、ExecutionContext 下游端口描述、revise 批量 results/analysis/context 端口、自动缺口路由、跨求解器初始化证明框架、曲线审计阶段、万能科学 validator、每行 ledger 交接协议；不自动修改旧科学计划或补实验数据；不为 author 加曲线评分能力；不以完整代码的存在、Run completed、exit 0、测试数量证明科学成功。

通用 `run_outputs.py` 的 envelope/compiled-schema/sealed-negative 机制保留；`runs.py` 与 local_workspace.py 仅增加上述已声明 snapshot hook 的失败恢复接线；若发现负分支在通用服务中被硬编码为正结论，才凭具体调用证据追加最小修复。通用 review 复用已有 verdict/findings，materializer 复用已有科学字段，不新增实现阶段状态。无需改变执行 Effect 和人类审批语义。

A0 的矩阵和受限端口/exposure 在 R3 明确列出，B 的分支、载体、恢复和版本策略沿用 R2，均待复审与实施验证。唯一剩余工程前提是 C0 的可信样本和生产证据路径，未通过前 C 明确暂停。旧计划的必要科学数值由真实恢复中的设计/审查 Worker 依据绑定记录判断，工程计划不预判或代填。
