# 科学骨架与 author 实施职责：最小跨边界改动计划

状态：R0，待独立工程审查的提案；未实施、未部署、未运行测试、模型或 solver。本轮只新增本文。不存在继承的计划 PASS、实现 PASS 或科学资格。

源码基线：实际 Git 仓库 `123/scidiscovery-e5.2`，HEAD `943c4626f8490530e9318eb9fbb409d2670908b9` **加本轮读取时既存 dirty 工作树**；不能把本文判断归于裸 HEAD。相关 general_science、experiment、TCAD author/reviewer、物化、分析和 scheduler 文件已有未提交改动，实施前须冻结精确候选及差异，保留他人修改。下文路径均相对该实际仓库；定位以符号为准，行号只是本轮快照导航。

## 1. 目标与证据边界

优先消除“把有疑义的实现约束当作科学成功标准，反复产生无效 author 任务”的路径，同时保持独立科学审查、源码审查、生产审批和结果分析。不是压缩每轮 token 后继续做同样的无效工作。

[Fig4 R4 收尾](evidence/fig4-r4-e2e-20260920/ROUND_CLOSEOUT.zh-CN.md)记录：原生 t=0 表面必须等于 C0 的要求，经过两次有界初始化尝试失败，才被独立科学审查识别为零体内初场与 t=0+ 边界语义混淆；重标 t0 为 pre-boundary 后原成功源码可直接复用。相关返工为 69 次模型请求、输入峰值 101,350 token。这是本计划的故障场景，不是新实现的成本基准承诺。

同一记录说明正时间三案最后完成执行、分析与独立下一步价值审查，但整体 Fig4 机制识别未完成。本文没有重新核验科学结论，不把历史开发观察当新生产证据。[progress.json](evidence/fig4-r4-e2e-20260920/progress.json)的 `phase`/`conclusion` 支持该收尾范围；其旧 `solver_scope` 文字仍写 development only，须结合后续 execution/production 事件理解，不能凭单字段否定收尾或借此授予执行权限。本轮未展开日志或原生会话。

职责共识：

| 主体 | 拥有的决定 | 不能越过的边界 |
|---|---|---|
| 假设提出 | 候选解释、竞争机制、全局研究路线 | 不替 author 预定全部离散和初始化方法 |
| 实验设计 | 科学骨架：比较谁、改变与保持什么、观察量、判别依据、不可改条件、停止条件 | 不为了“可执行完整”强迫提前选定所有数值实现、具体 case 枚举和原始文件 |
| author | 具体实验方案、实现方法、离散、初始化、检查点、原始产物、代码；授权开发验证及局部纠错 | 不自行改科学目标、对照含义、成功标准或生产审批 |
| 独立执行前 reviewer | 联合检查科学骨架、具体实现与开发证据是否足以支持本次受控执行 | 不能仅审“忠实实现了错误要求”，不能自己运行/修改 deck 或授予生产权限 |
| 控制、领域 adapter、分析 | 原有不可变绑定/资格/权限、受控副作用、实际结果的独立分析 | 不增加科学正确性硬编码、不把初始化成功视为科学成功 |

“骨架”不等于模糊愿望。对研究判断不可缺的物理边界、初态、参数依据、对照关系、定量标准仍由设计明确；仅由工程实现选择的时间离散、solver 表示、采样文件名等不应假扮为冻结科学条件。具体数值是科学变量还是实现选择，由科学语义和证据判断，不能按字段名一刀切。

## 2. 已核对的现状与根因

| 代码入口 | 当前行为与后果 |
|---|---|
| `src/scidiscovery/general_science_experiment_components.py:EXPERIMENT_PROMPT` | 要求设计给出数值判据、提取/归约算法、不确定度传播、模型/边界/outputs；同时要求后续 author 完成源码和数值验证。职责不是完全错误，但“完整可实现计划”的粒度容易前移。 |
| `artifact_agent/schema/experiment_intent.py:ExperimentProposalIntent`、`materialize_experiment_design_intent` | compact intent 仍必需具体 `cases`、case expectations、`validation_intent`；展开成 `ExperimentPortfolio`，不是本次所需的科学骨架。不能只改提示词而保留同一必填写 Schema。 |
| `artifact_agent/schema/experiment.py:ExperimentPortfolio` | 每个 proposal 必须有完整 ValidationPlan；case、changed_factors、comparison_contract 有闭合约束。该模型适合最终具体计划，继续复用；不应把约束全部删除来兼容未展开骨架。 |
| `general_science_experiment_operations.py` | `science.experiment.materialize.v1` 与 `science.experiment.revise.v1` 为完整计划声明到 `science.object.review.v1` 的 review edge。 |
| `plugins/tcad_artifact/tcad_artifact/plugin.py:INITIAL_INPUTS` | `experiment_plan` 必需且默认 usage 为 claim_evidence；`experiment_review` 虽 min_items=0，也不能据此说计划预审已可省。控制根据 producer 的冻结 review edge 要求确切 witness。 |
| `operations/review_admission.py:review_input_mode` 与 `interfaces/mcp_root_operation_routes.py` 的 review admission | 除审查对象、直接修订、历史背景用途等明确情形，下游必须提供对应 producer 的审查见证。把 usage 改成 evidence_inventory 会改变权限语义，不能用作普遍绕门。 |
| `project_materializer.py:materialization_contract`、`materialize_deck_project` | 从完整计划生成不可变 case/控制值合同；控制不解析 solver 科学语义。author 的 declarations 只声明入口、case anchors、raw_outputs，文件名并不是全部由 designer 固定。 |
| `operation_workspace.py:materialize_workspace/finalize_workspace` | author 工作区在开始时从 plan 建物化合同，最终扫描源码/声明、纳入可信开发记录。当前需要在开工前已有完整计划。 |
| `roles/tcad_deck_reviewer.md`、`project_packager.py:DeckReviewReport` | reviewer 主要审实现忠实性与执行准备，不明确拥有独立重审科学判别充分性的合同；现有字段 physical/implementation/numerical fidelity 不能单独证明已审科学骨架。 |
| `operation_transforms.py:package_parentage/package`、`transform_adapter.py:package_reviewed_project` | 包审查需绑定 exact project/capability/plan；project、plan 的 claim_evidence 保留 review admission。optional experiment_review 用于准入 witness，`package()`仅传四个基础 payload 给 adapter；不能误报 adapter 拒绝 optional review 为现存 bug。 |
| `result_analysis.py:analysis_parentage/validate_analysis_inputs`（约 91/331） | 强制一个原始 plan、一个 `science.object.review.v1` 的 passing `scientific_review`，review_target 为 experiment_portfolio；plan 必须是 package 直接 parent。仅放开 author 会在分析这里断路。 |
| `operations/catalog.py` review 编译、`operation_contract.py:direct_revision_contract`（约 320） | 一个 review edge 的 subject outputs 要匹配同一 reviewer 输入 Schema；直接修订要求唯一 primary output。不能随手给 author 加一个异构 plan 主输出并声称框架无需改。 |
| `roles/scheduler/research.md`、`dispatch.md` | 研究指引目前要求 changed plans 的科学和实现审查；dispatch 已约束独立 reviewer 不能复用自己的 author Agent。后者保留，前者需要区分审查时点与覆盖范围。 |

根因是职责粒度、写合同与资格时点共同固定了路线：设计承担过多具体化，一旦成为已审计划，author 被推向忠实实现；实现矛盾又容易被解释成“还需要诊断”。R4 已补充的可信开发证据交付仍有价值，但不能修复上游要求本身错误，也不能代替对下一次任务科学价值的判断。

## 3. 推荐实现：一个骨架、一个项目内具体计划、一次独立执行前审查

这是局部合同调整，不是仅改两段 prompt。最小不可省范围为 **设计 producer → author 物化 → 独立 review → package/analysis lineage**，并覆盖安装投影、兼容和反例。Artifact、Run、执行器、审批、恢复状态机保持原职责。

### 3.0 先比较更简单的复用方式

| 候选 | 是否足够及取舍 |
|---|---|
| 只改设计/author/reviewer prompt，继续旧 intent→Portfolio→预审 | 最少文本改动，但 intent 仍必须先给具体 cases/validation，author 仍受已冻结详细计划约束，无法实现用户要求的职责转移。可立即改善解释习惯，不能当本次完成。 |
| Designer 留空工程字段，沿用现有 materialize 自动补全 | 现有物化是确定展开，不能创造方法/参数；允许它填默认值等于控制层替 author 做科学/工程选择。不可采用。 |
| 把现有 compact intent 编辑权移给 author，仍另开原 materialize Run | 可以复用模型/算法，但 author 开工物化、诊断、修订需要具体方案；把每个局部选择送外部设计/物化再重启 author 会造成新的任务循环。推荐方案仍复用该模型闭合与确定物化函数，只把编辑/物化时机放入当前 author 工作区。纯提取一次最终计划不需要模型任务。 |
| 先做作者自己的独立“详细设计” Operation，再做代码 author | 避开项目扩字段，却强制分割同一 author 的方案—实现—验证闭环，遇到实现证据后仍要往返；背离减少无效任务的首要目标。 |
| 直接把计划嵌入项目，所有下游都改读嵌套字段 | 少一个纯投影 Operation，但要改现有分析/评分的 plan 输入及引用路径；为已有稳定 Portfolio 端口扩大消费者改动。推荐只增加薄提取，保留其数据合同。 |
| 在所有现有设计 Operation 中直接替换为新骨架 | 少一个新目录入口，却使所有 legacy/non-TCAD 消费者立刻缺必需 Portfolio；不符合局部迁移。本提案保留旧路径并显式支持新 TCAD 路径。 |

新增成本限于一个科学骨架写合同、一个复用现有设计 Agent 的入口、项目中复用的 Portfolio 字段及一次纯提取；不新增另一套执行计划模型、Agent 类型或调度状态。若实施证明现有受控产物发布机制能够在不破坏唯一 primary/revision 识别的情况下可靠发布该同一嵌套计划，应优先复用它并删除独立投影入口；必须保持相同来源/资格语义，不为保留本提案形式而新增 Operation。

### 3.1 新骨架写合同与旧完整计划并存

在 `experiment_intent.py` 增加独立的轻量写模型（建议 `ExperimentScientificSkeleton`，新 schema ID），复用现有目标、假设引用、prediction/identifiability/value 的适用类型；不要把旧 `ExperimentDesignIntent` 任意放宽为可缺 cases 的混合体。

骨架只要求本轮科学选择：原目标/当前目标、竞争解释与对照关系、改变/保持条件、观察量、科学判别依据及必要阈值/依据、不可改条件、停止条件、尚未解决的可行性限制。具体科学参数若决定判别必须给值或可复算依据；无需具体运行 case 的全枚举、逐 case 工程值、原始输出路径、完整数值检查表。用已有有界文本/列表表达科学关系，不新增逐要求 ID、逐判断签名或一套必填追踪表。

为避免非 TCAD 消费者被全局强迁移，新增一个薄的骨架设计 Operation（建议 `science.experiment.skeleton.v1`），复用设计 Agent、objective/hypothesis/critic/current_progress/execution_context 输入与现有基础资格。旧 `science.experiment.design.v1`、materialize、完整计划 revision 的历史和兼容入口保留，目录明确它们交付详细 legacy plan。新 Operation 不是新角色，不注册新调度框架。它的骨架输出**不声明强制 review edge**，因为它本身不授予执行资格。

需要修订骨架时同一新 Operation 可绑定确切旧骨架与正式变更依据，产一个新不可变骨架；按普通新设计输入验证其目标/假设一致性，不能冒用已有 direct_revision_contract 的特权。不要标成 revision_base 后要求核心放宽唯一主输出/审查规则。批准之前，具体命名和输入描述由声明单源投影到目录和模型合同。

### 3.2 author 具体化：复用 Portfolio，不新造第二执行事实

现有 TCAD author 的新调用允许在“骨架输入”和“legacy experiment_plan 输入”中明确二选一（输入预检检查 exact-one）；revision/runtime-failure 可从 prior_project 恢复原骨架绑定，不能凭聊天改换。新骨架路径不强制提前 review；基础证据/参数批准、执行 capability 和预算要求不变。

author 在工作区编写一个具体计划文件，内容仍为现有 `ExperimentPortfolio`；它是该科学骨架的执行化选择，包括 cases、实施对照、离散/初态具体表示、检查点和验证计划。科学冻结内容来自骨架，实施细节由 author 选择并验证。raw output 路径仍只写现有 declarations；不在 Portfolio 再登记同一文件清单。

最终只交付**一个** `DeckProjectDraft` 主对象。在其中增加一个对旧对象可缺省的 `execution_plan: ExperimentPortfolio` 字段，新骨架 author 路径必须具备；旧项目缺省解析/序列化保持旧字节语义。该字段为最终具体计划唯一事实；工作区文件是它的编辑入口，物化合同、case bindings、输出预期、差异都是其派生结果。骨架保持原始不可变输入，通过现有 Run/artifact bindings 追溯，不要求 author 手写 ArtifactRef、哈希或重复科学约束副本。

开发前不再强迫等待 designer 填完整计划。author 写出首个有界具体方案后，现有 project materializer 使用该本地方案生成机械合同，再允许诊断；方案修改会重新物化。初始/最终控制检查是结构、同源性和声明闭合，不能由比较字符串决定科学等价。数值方法改动如影响现有 attestation 被证明对象，必须使证明失效；不能只改计划而保留与它冲突的旧开发证明。

保留唯一主输出，避免破坏 direct revision 和 review edge。需要外部消费者的 `experiment_plan` Artifact 时，增加极薄确定性投影（建议 `tcad.execution-plan.project.v1`），从已封存 project 的 `execution_plan` 原样提取 Portfolio；不由新 Worker 再生成、不改变科学内容。这个投影只为满足现有端口类型，不拥有另一版计划。投影 artifact 的 parent 必须为 exact project，字节/规范化对象一致性由控制验证。

投影操作必须能在项目独立审查之前调用，输入使用已存在的历史/材料用途读取 exact project，并以局部 admission 明确它**不授予执行或科学 claim 权限**；否则会形成“review 需要 plan、project 投影又需要 review”的循环。这是一个显式的纯投影例外，不扩散到 package/execution。plan projection 无强制 review edge；它的可执行性只由后续 exact project 综合审查和 package 约束证明，不把它单独作为已审科学结论。

放弃“author 新增 Portfolio 第二主输出”方案：它会破坏现有直接修订识别，推动无必要的核心框架改造。也不把所有新计划藏在自由文本 handoff，否则物化/分析没有可靠唯一来源。

### 3.3 一次独立 review 同时承担科学与实现审查

保留 `tcad.deck.review.v1` 与 author→project 的现有 review edge，提升该 Operation 的 version、role/semantic contract 和真实输出 Schema。新路径输入：exact project、投影的 execution plan、原骨架、capability、既有参数依据/必要上下文；项目带有受控开发诊断附件。输入预检验证投影来源、project 中 plan 一致、骨架是 author Run 的确切输入，reviewer 看到完整科学骨架而不是只看到物化摘要。

在 `DeckReviewReport` 增加一个有界 `scientific_assessment`（旧对象可缺省，新骨架项目的 passing review 必需）。它表明科学骨架与当前具体方案是否一致、对照和判断是否有效，并给理由/限制；复用 report 的 findings/rationale，不再新增逐项机械 requirement 表。控制只验证该部分存在、状态与总 verdict/execution_ready 一致，不能计算“科学正确”。

Reviewer 独立判断：骨架中的要求是否真的支持当前研究决策；具体实现是否保留对照与标准；开发证据是否在相关层区分有效/无效实现。对“忠实实现了不必要或自相矛盾要求”也可以 revise/blocked，明确回骨架还是局部实现。一个总 verdict 管理该 exact project 是否 ready，不再自动安排一次 science review 加一次 deck review。独立 Agent 的现有身份约束保留；author 不得审自己的项目，读到早期 review 也不能继承其结论。

不得仅因模型输出 `scientific_assessment=pass` 就承认是新综合审查：package 必须核对来自实际完成的、对应新合同 digest/version 的独立 reviewer Run；旧 reviewer 不能凭加字段或伪造 labels 获得新资格。

### 3.4 提前设计审查是可选行动，不是新状态

昂贵/不可逆执行、对照含义争议大、author 发现要求语义冲突时，可在开工前或中途请求独立骨架审查。扩展现有 `science.object.review.v1` 的输入选择：完整 legacy plan 或新 skeleton 二选一，保持原 plan 分支不变；`ScientificReview`/review_target 与相应上下文 validator 显式支持 skeleton，不把骨架伪装成完整 Portfolio。该 review 仍是正式不可变结果，不是聊天意见。

不加 `design_approved` 状态、计数器或每次必填风险问卷；scheduler 从实际科学矛盾选择是否调用公开 Operation。提前 PASS 不替代后续具体实现综合审查，提前 REVISE 必须在正式新骨架中处理，不能由 author 擅自消除冻结条件。骨架输出无强制 review edge，因此其可选审查的独立性须复用现有独立科学 review 的运行身份验证能力；若现有通用服务只对声明 review edge 执行独立身份校验，WP0 必须定位该入口并以 review Operation 的局部 exact-subject guard 接入既有身份检查，不能假定省略 edge 就仍自动独立。该点列为实施前阻断检查。

### 3.5 package 与 analysis 不留断路或绕过

新路径：

`骨架 → author(project 内嵌 Portfolio + 源码 + 可信开发记录) → 纯 plan 投影 → 独立综合 review → reviewed package → 原生产审批/执行/收集 → TCAD analysis`。

可选早期 review 是支路，不改变后半条链的准入。

Package 继续以 project 的 exact passing review 为必要资格。其 `experiment_plan` 必须是该 project 的投影，review 同时绑定 exact project/capability/plan/skeleton；校验综合 review 的科学部分、执行准备与开发证明。包直接 parents 继续保留 plan/project/review/capability（以及声明的 skeleton），保持分析的 original-plan parent 语义。新路径不要求 `science.object.review.v1` 的 experiment_portfolio PASS；legacy 路径原有 plan review witness 要求完整保留。

TCAD analysis 继续绑定原始执行的 `experiment_plan`、package、runtime manifest。端口提供旧 `experiment_review` 与新 `execution_review` 的明确兼容分支：legacy 包仍要求原 passing ScientificReview；新骨架包要求 exact 综合 DeckReviewReport，核对 package 内同一 review、review Run 的 project/plan/skeleton 绑定和受支持生产合同。不能只把 experiment_review 改 optional，不能任取两种报告中一个 PASS。分支由 package/project 的真实 schema/producer lineage 决定，不由调用者自由选择；跨分支或冲突证据拒绝，错误定位到输入端口。

保留原 plan 必须是 package 直接 parent、manifest 必须来自 exact package、输出 case/path/media/bytes、execution_result/recovery receipts 的检查。分析可读已执行历史链，不授予新 author/execution 资格。骨架只作为科学依据；数值评分和 case 解释使用原执行 Portfolio，不使用后来“更好”的方案。后续追溯分析方案仍走 current_progress。

`curve_score` 通用分析和 TCAD curve-contract Operations 当前也有 legacy scientific_review 依赖；本轮不宣称它们自动支持新骨架 producer。新路径以 `tcad.result.analyze.v1` 及其既有可选同Run评分工具为受支持消费链；旧泛用 Operation 继续公开其既有输入要求，不自动成为新路径前置。若验收发现该 TCAD 分析工具必经新的同类 review 硬锁，须在本轮显式修该实际调用点或阻止宣称闭环；不借此扩展成所有插件迁移。

## 4. 防止 t0 式无效返工的动作规则

这部分必须进设计/author/reviewer 和 scheduler 的实际合同，不只留在本文。

1. 开发问题首先说明“当前观察/失败可能改变哪一个科学判断或执行有效性判断”。既有证据已能回答就复用原件；没有区别信息的重复诊断不产生新任务。
2. 发现 solver 表示、初始化时刻、边界施加顺序与冻结要求冲突时，author 用现有 gap/handoff/源码注释表达冲突、证据、影响及最小变更建议；不能无依据把它标成 solver bug，也不能把条件偷偷改掉。
3. 若只是科学上等价的实现选择，author 在同一授权开发任务中做局部纠错并验证；“所有实现选择都回设计”仍属于失败。涉及科学意义/成功标准的实质改变，先形成有界科学判断/骨架修订，再决定是否需要 author。
4. 若原源码已足够，允许只修新科学骨架/具体计划并重新封存项目及独立审查，复用未改变源码对应的合格证据应遵循现有证明身份规则；不承诺旧 receipt 可以跨新 Run 自动成为当前 attestation。身份不兼容则做明确最小验证，不能借机重跑全方案。
5. Scheduler 不因一次 gap 自动派“大 author 再尝试”，不扩预算/换名字延续同一无信息重试；每个下一动作必须有可改变的判断。已有 AGENTS 的停止细分/科学重设计原则保留。

在 t0 场景中，期望先暴露 pre-boundary record 与 t=0+ 边界的语义问题，请独立科学判断它影响何种观察/成功条件，再决定修骨架或修实现；不是预置“t0 要求永远错误”的领域判定规则。

## 5. producer—consumer 修改清单与顺序工作包

每包串行，先保证一个场景能组合，再扩大；本轮未执行下列工作。

| 工作包 | 具体文件/合同 | 交付与退出条件 |
|---|---|---|
| WP0 合同切口冻结 | `operations/review_admission.py`、`operation_contract.py:direct_revision_contract`、`operations/catalog.py`、`interfaces/mcp_root_operation_routes.py`（先只读）；`general_science_experiment_operations.py`、TCAD `plugin.py/operation_transforms.py` | 记录 exact 工作树候选；证明单项目主输出、review edge、骨架可选独立审查、纯投影准入、legacy witness 与新综合审查均可由现有机制表达。任何依赖新状态机的方案退回缩小范围。 |
| WP1 骨架 producer | `artifact_agent/schema/experiment_intent.py`；`schema/research_cycle.py:ScientificReview`；`general_science_experiment_components.py`、`general_science_experiment_operations.py`；必要 resource/view 映射 | 新骨架写 Schema 和 Operation、可选科学 review/精确修订输入、模型 prompt 对齐；保留旧 intent/Portfolio readers/materialize/review。假设职责只在 `general_science_resources.py` 的相关 prompt 最小澄清，不改变 hypothesis evidence/critic gates。 |
| WP2 author 与唯一执行事实 | TCAD `plugin.py`、`project_packager.py`、`project_materializer.py`、`operation_workspace.py`、`operation_transforms.py`、`transform_adapter.py`；`roles/tcad_deck_author.md`、`roles/sentaurus_author_contract.md` | 骨架/legacy 输入分支；可编辑具体方案、项目内 Portfolio、纯投影；计划变更与 attestation 身份审计；materialize/diagnostic/finalize 采用同一方案。初始、review revision、runtime-failure、gap、重开恢复均不回填伪科学默认值。 |
| WP3 综合 review、package 与 analysis | TCAD `roles/tcad_deck_reviewer.md`、`roles/sentaurus_review_contract.md`、`project_packager.py:DeckReviewReport`、`plugin.py`、`operation_workspace.py`；`operation_transforms.py:package_parentage`、`transform_adapter.py`；`result_analysis.py` | 同一次 review 有科学充分性与实现证据；source-bound proofs 原约束；新/旧 package、analysis 双路径同时完成。不得先发布放松 author 准入、后补执行/分析门禁。 |
| WP4 调度/文档/安装投影 | `roles/scheduler/research.md`、必要 `domain-analysis.md`；`roles/scheduler.md` 与生成入口按现有关系核对；`dispatch.md` 仅检查独立性表述；`docs/ARCHITECTURE.md/.zh-CN.md`、TCAD README 对应段 | 新路径为 TCAD 默认选择，legacy 入口说明清楚；提前 review 不是必经；语义冲突先问科学影响；原 dispatch/审批不改权限。更新 source-owned 文档再由现有安装器生成，不直接改已安装指南充当源码。 |
| WP5 定向验证与独立验收 | 下节列出已有测试落点及新增反例；安装入口沿 `deploy/install.sh`/平台配置原机制检查 | 串行低资源验证、独立跨边界审查后才具备部署候选；没有真实行为证据时只能报工程合同闭合，不能宣布防止无效任务已验收。 |

若 gap 在没有完整 execution_plan 时产生：继续允许 ImplementationGap 封存，不补假 cases/假计划；将 `validate_implementation_gap` 当前只支持 experiment_plan locator 的入口扩展为精确 skeleton 或 plan 的声明选择，输出仍为已有 gap 类型。gap 不可投影为可执行 Portfolio，不可打包，review 可以给正式负面结论。

工作区 `deterministic` 当前与 plan 存在及 sprocess 绑定；改动须明确覆盖实际受支持 sprocess 路径，sdevice 非声明分支不能默认为已适配。若不能以同一局部方案覆盖 sdevice，目录/合同标明新路径支持范围，legacy sdevice 保持原合同。本轮不新增 executor 或 Skill 执行权限。

## 6. 权限、资格与历史兼容

- 不变：科学基础/参数审批 cohort、开发预算、受控 debug 工具、独立 Agent 约束、reviewed package 的执行请求、网页审批、sealed decision、实际 executor 与恢复收据。author 不可审批、重命名绕预算或自行替换科学标准。
- 输入预检只在 invoke/preflight 验证冻结输入结构、exact-one、身份、已完成状态、parentage、资格和声明支持范围。输出提交只校验新产物结构、与冻结输入的绑定一致性、可信开发附件和 verdict 一致性；不在 submit 再归约科学数据、重新入场历史资格或强迫模型修控制事实。
- 新骨架/新项目/新 review 的 schema/operation digest 变化是新资格边界。旧运行冻结合同和旧 reviewer 结果不能自动为新项目、变更 plan 或变更 skeleton 资格背书。
- 历史详细计划、已审项目、已执行 package 和原始分析链继续可读。缺省新字段不注入旧对象重新序列化；旧实验无需回填 skeleton/scientific_assessment。新接口从旧计划起步仍走 legacy 审查契约，不能拿“新路径不预审”洗掉老 producer 的冻结 edge。
- 新项目修改源码/声明/具体 plan/科学 skeleton 任一项，按对应现有身份规则重新生成/审查对象；原科学 review/开发记录仅作确切证据，不能被同名新对象继承。
- 打包和分析从实际 producer/project 内容识别新路径，并验证单一 plan；同 project 的后投影输出没有相同字节或 exact parent 即拒绝。投影不应加人工 hashes、manifest 或 Root 逐项登记步骤。
- 无需重写通用 `_is_exact_reviewer_output`、审批服务和 Run 状态机；若需要为可选骨架 review 调用既有身份校验，修改限定为现有服务入口的局部复用，先经 WP0 独立确认，不趁机泛化依赖系统。

## 7. 低资源串行验收与负例

本计划不申请资源、不开始 A/B、不跑模型或 solver。实施后分层验收，任何高层资源试验以前置合同闭合和用户已有授权为边界。

### 7.1 先做可判定的工程路径

复用现有夹具与断言落点：

- `tests/operations/test_experiment_intent_writer_contract.py`：新骨架不要求具体案例/工程检查表；历史完整 intent 仍可物化；只读 reader 不放松新写合同。
- `test_compiled_declaration_consumers.py`、`test_agent_contract_alignment.py`：声明变化真实贯通 catalog、完整 contract、Worker schema、invoke/preflight/submit；多 primary 的错误方案不被引入。
- `test_reviewed_claim_admission.py`：legacy review witness、错误 subject、伪造 labels、新旧合同资格分离；新 plan 投影只允许无副作用提取，不能直达执行。
- `test_tcad_development_lifecycle.py`、`test_tcad_development_delivery.py`、`test_tcad_initialization_outputs.py`：本地方案物化与最终 plan 同源；声明变化刷新相关证明；可信诊断交到 reviewer，伪造报告/缺记录不通过；纯源码语法修订不强制完整动态实验。
- `test_tcad_result_analysis.py`、`test_collector_analysis_handoff.py`、`test_analysis_claim_scope.py`：新综合审查链可分析、旧链可继续分析，错 plan/package/manifest/review/receipt 拒绝；失败执行、零输出、未评分仍可封存有范围的分析。
- `tests/artifact_agent/test_scheduler_guides.py`、`test_platform_configuration.py`：安装生成的指南与角色实际带新职责，独立性和审批边界不变。安装候选检查串行隔离，不部署生产。

测试按当前变更的最小相关集合运行一次，失败再定向扩大；不要以测试个数证明用户场景解决。不能把裸 fixture 内调用 validator 当作真正 entrypoint 证据：至少一条新路径和对应否定对照必须走编译 Operation → invoke/assignment → submit → package 准入 → analysis 准入，副作用用已有受控夹具隔离。

### 7.2 必须说明的真实场景和反例

| 场景 | 验收结果 |
|---|---|
| Fig4 t0 原要求与 solver 时刻表示冲突 | 先交付其影响何种科学判断的正式说明；有界独立科学判断在继续实现搜索之前发生；若只需澄清科学条件，原源码可复用，不自动新建大型 author 或追加同义诊断。 |
| solver callback 没有随时间更新，正时间观察不变 | author 仍必须取得能暴露动态缺陷的许可开发观察并局部修复，不能借“方法自选”逃避证据；review 不因 exit 0/文件存在而 PASS。 |
| 网格/时间步为普通实现选择 | author 选择并验证即可；没有改变结论范围或标准，不新建 designer/review-precheck 循环。 |
| 网格或时间采样正是研究的对照变量 | 必须维持骨架的对照关系和判断依据，不能以工程选择自由改它。 |
| 为省计算把阈值 0.001 放宽或移除不利对照 | author 不可自决；正式骨架修订后重新综合审查和必要审批。 |
| 昂贵或不可逆实验/重大科学争议 | 能主动先做骨架独立 review；早期 PASS 不能跳过实现完成后的综合审查或生产审批。 |
| 缺物理事实/参数或执行 route 不支持 | 交付具体 gap/缩小科学范围，不由 author 猜事实、发明 executor 或不停重试。 |
| 新项目只有旧 deck fidelity PASS、伪造新科学字段 | 打包拒绝，不能以旧合同 report 充当综合 review。 |
| author 与 reviewer 同 native Agent / 早期 reviewer 是骨架 author | 现有独立身份约束或其局部复用必须拒绝；提示词声称独立即使内容完整也不算。 |
| 历史已执行包 + 原计划/原 scientific_review | 原分析仍可进入；换上最新回顾计划或新 skeleton 不能偷换执行事实。 |
| 两个内容相同但不同来源的 projected plan / 新 plan 配旧 review | 按 exact parent/binding 拒绝错误组合；同字节不是同执行来源。 |

工程验收通过以后，可在另获相应运行授权时做**一个有界、串行**模型行为验收：提供原科学语义冲突及足够既有证据，观察其是否产生正确的下一科学任务，而不是先做大量实施搜索。必要时另用一个真实实现缺陷作为反例，证明没有把所有故障都推回设计。无需先做昂贵成组 A/B，也无需重跑 Fig4 全部生产案例。

记录的主指标是无信息 author/诊断任务是否实际避免、关键科学问题何时被识别、独立审查覆盖与审批是否保持；模型请求数、峰值 token、solver 时间只作为观察量。不承诺固定百分比，不以新方案一次“零失败”代替反例，不预判具体科学 verdict。预算不够则报告未验证范围并停下，不能放宽标准后宣称完成。

## 8. 文档归属、非目标与独立审查清单

文档归属：

| 既有材料 | 本提案的关系 |
|---|---|
| `docs/ARCHITECTURE.md/.zh-CN.md`、编译 Operation 与 Schema | 当前规范仍由现有源码/文档承担；本文是未发布提案，不能当线上行为。实施时只更新受影响职责/审查时点段落。 |
| [Fig4 author 动态验证/token 计划](FIG4_AUTHOR_VALIDATION_AND_TOKEN_REMEDIATION_PLAN_20260920.zh-CN.md)及 reviews/evidence | 保留可信开发附件、最小动态验证、身份与历史兼容事实；本文只承接“谁决定实现方案/何时审科学”问题，不追改其历史 PASS 或失败。 |
| [根因修复交接计划](ROOT_CAUSE_REMEDIATION_IMPLEMENTATION_PLAN_20260919.zh-CN.md) | 部分职责理念重叠；其依赖/引用和机械交接方案不由本文实施，本文不宣称该计划已通过/已完成。 |
| Fig4 ROUND_CLOSEOUT 与 progress | 历史过程证据，原件保持；不是新接口规范或新科学资格。 |
| `docs/plans/README.md` | 本轮无修改权限；实施或经授权整合时新增 proposal 入口，并明确局部承接范围，不删除历史链接。 |

非目标：机械产物绑定自动化；Root 一次选结果自动补齐所有分析输入；通用依赖图/注册表/状态机；Artifact/Run/审批/恢复重写；任意插件自动适配；新 solver 或 executor；放宽开发预算；取消参数批准/独立性；自动科学正确性硬判；token 优化主线、A/B 资源申请、生产部署或新研究方向选择。

独立审查必须逐项回答：

- [ ] 新骨架真的不强制 author 专属工程字段，同时没有丢掉科学判别、事实依据、冻结条件与停止条件？
- [ ] 具体计划只有 project 内一份事实，投影不再创作；单主输出和直接修订仍成立？
- [ ] 投影可在 review 前安全完成且不授予执行权，所有 package/analysis 消费者核对真实 lineage？
- [ ] 可选骨架 review 的独立身份是否经真实入口验证，而不是仅靠 prompt？
- [ ] 最终 reviewer 确实审科学充分性、实现、开发证据；一个 PASS 绑定同一骨架、具体方案、源码和证据？
- [ ] legacy 科学 review 分支、新综合 review 分支以及 gap/失败/恢复都没有“只放开上游”的断路？
- [ ] 新字段/合同/digest 不能伪造或借历史 PASS 继承资格；author 没有审批权？
- [ ] 科学等价的工程选择留在 author，真正目标/对照/标准变更回设计；t0 场景先判断影响再决定是否实现？
- [ ] 校验没有新增机械重复填写或科学正确性硬门，input admission 与 output validation 仍分离？
- [ ] 声明、Schema、角色、Skill 引用、安装生成指南与实际支持插件范围一致？
- [ ] 验收包含真实入口负例与任务是否避免的行为证据，并诚实保留未运行/未覆盖项？

主要风险是骨架过于空泛、综合 reviewer 只看代码、方案变更未使证据失效、optional 误用为准入绕过、同 bytes 错 lineage、以及为省一个投影而改动核心多主输出框架。分别由明确科学边界、实际 reviewer 合同、现有证明身份、局部 admission、exact 绑定和唯一主输出选择控制。若 WP0 证明不能在局部组件内保持这些条件，应报告最小不可省的新增边界并重新审查方案，而非宣称只是提示词小改。
