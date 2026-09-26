# 四模块任务颗粒度调整：实施计划

日期：2026-09-24

状态：**独立规划草案，图证据实现细节由当前主计划引用；未实施、未测试、未部署、未进行科研验收。**

当前统一实施入口为[四模块主计划：颗粒度优先与配置化 TCAD 自主执行](FOUR_MODULE_SIMPLIFICATION_STRATEGY_R2.zh-CN.md)。本文保留独立规划者的图证据纵向设计；首批排序及 TCAD 执行授权按该主计划落实。用户新增的配置额度内免人工执行审批要求已同步到本文，原规划尚未取得独立审查 PASS。

## 1. 决策与事实范围

**第一优先级是改变科学作者的任务边界。** 先让同一责任主体连续完成一项完整工作，再调整 Root 的接口、绑定与指南。首批必须减少一次真实的作者任务交接；只增加模块包装、隐藏原有微任务链、缩短工具回复，不算完成。

四模块是证据、假设、实验设计与执行、结果分析的责任划分。它们不对应四个固定 Agent、四个巨大 Operation 或四个固定阶段。工具与确定性 Operation 可以细；模型任务应围绕完整成果组织。专业判断本身不构成另开任务的理由：在已定目标、权限和预算内，作者应自行判断、检查和改进。独立审查、科学目标变化、权限变化及已到达的能力或预算边界才要求交接。

本计划依据用户最新的颗粒度优先要求，承接[原四模块策略](FOUR_MODULE_SIMPLIFICATION_STRATEGY.zh-CN.md)的模块划分和可信控制边界，取代其第八节及第十二节的拟议实施排序：**把图证据作者合并作为第一批，而非先完成 Root 读取、自动绑定和自动派发。** 原策略仍保留原状态；本文不是当前运行规范，不继承旧审查结论，也不替原策略宣告已审查或已实施。

静态核查基线是 `5871a64e3585e00f98f5357aadef959d343758c5` 加已有工作树，不能等同裸 HEAD 或当前安装。工作树有大量既有改动和未跟踪材料。独立规划者只新增本文，不改源码、原策略或运行状态；父会话另维护索引。已知历史记录有定向安装测试 138 通过、12 失败；本文未复跑、未重新归因，不宣称全树绿色，也不将修复这 12 项列为首批前置工程。

规范依据为[当前架构](../ARCHITECTURE.zh-CN.md)、[设计宪章](../architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md)及[约束登记](../architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml)。历史 R5-M 账本、R5-N 验收用于了解责任演变，不继承其 PASS；历史文字与当前规范或源码不同处，以明确的当前合同为实施核对对象。本计划按跨边界审查和证据化简化方法追踪生产者及消费者，没有调用实例控制接口。

## 2. 四模块的完整工作与必须保留的边界

| 模块 | 一项完整作者任务应承担什么 | 科学交付 | 模块内连续工作 | 必须独立或返回 Root 的边界 |
| --- | --- | --- | --- | --- |
| 证据 | 对明确来源和问题完成定位、提取、检查、解释适用范围 | 可引用观测、原始来源、机械测量记录、缺口和不确定性 | 图选择、标定描述、工具取点、观察叠图、纠正描述、整理 Intake | 对作者成果的独立审查；需要不同来源/目标；资格审批按消费者要求保留 |
| 假设 | 对当前矛盾形成可证伪的竞争解释及预测 | 假设集合、依据、判别问题和未覆盖范围 | 比较解释、检查依据、消除自身矛盾、正式提交前修订 | 独立 critic；新的证据需求或研究目标变化；封存后修改产生新对象 |
| 实验设计与执行 | 将科学判别问题变成可审查、可执行且有结果记录的实验工作 | 科学骨架、具体计划/项目、独立审查、授权执行原始结果 | 实现作者可连续具体化、写代码、开发检查、普通工程修正；无需每个选择返回设计者 | 科学骨架与工程实现可因专业责任分开；独立综合审查、配置额度内策略授权、超额人工精确批准、受控 adapter 执行必须保留；判据/对照变化返回科学设计 |
| 结果分析 | 对精确结果完成有效性检查、计算、图示和科学解释 | 正式结论、依据、限制、剩余矛盾与有界建议 | 读文件、按需评分、作图、局部重绘、比较解释、交付 | 无原始数据、需要新实验、改变判据或进入另一假设问题；计算结果本身不能授予科学资格 |

完整成果可以是忠实的有限结论或 unresolved；不能把“完整任务”理解为必须证明假设成立。模块内仍可以封存多个机械记录，但不要因此创建多个科学作者 Run。独立审查可能使用另一 Agent；审查失败后的正式修订仍保留新 revision、精确 review 绑定和原次数限制，不伪装成未提交草稿。

## 3. 当前交接、目标路径与处置依据

以下是声明支持的典型路径，不是所有研究必须经过的 DAG。源码链接用于定位符号；实施时重新冻结精确差异与行号。

### 3.1 图证据：首批确实可以减少作者任务

当前：

```text
Root 选来源与目标
  → science.figure.request.prepare.v1              作者 A / Run 1
      inspect → preview → FigureDigitizationRequest
  → science.figure.evidence.materialize.v1          确定性 Transform
      manifest + report + panel + overlays + CSV
  → science.evidence.extract.figure.v2              作者 B / Run 2
      重新理解来源和附件 → ScientificIntake
  → science.figure.evidence.audit.v1                独立审查者
  → scidiscovery.curve-bundle.figure-evidence.v2     需要定量库时规范化
```

目标：

```text
Root 选来源、目标与预算
  → 一个图证据作者 Run
      inspect → 同一工具完成取点、保存及展示 → 作者检查并整理 Intake
      必要的有界纠正仍在本 Run 内；机械记录及时保留
  → 独立图证据审查 Run，消费 Intake 及同一完整来源族
  → 需要时确定性规范化为现有 curve bundle，按消费者要求取得资格
```

| 当前责任/位置 | 处置 | 为什么以及保留什么 |
| --- | --- | --- |
| `figure_science_operations.py:OPERATIONS` 的 request 作者与 intake 作者 | 合成一个新版本作者入口 | 两者服务同一原图和目标，无独立性或权限变化；保留视觉科学判断及一个主要 `ScientificIntake` 输出 |
| `figure_worker_tool.py:_preview` | 扩展为本 Run 内可保留完整测量记录的工具能力 | 目前只把叠图和 details 写入工作区，不等于完整 family 已封存；复用同一个 `build_digitized_figure_bundle` 算法 |
| `operation_transforms.py:materialize_figure_evidence` | 算法内收，旧 Transform 暂留 | 不再强制 Root 在两位作者之间物化；来源、请求、算法身份与结果记录仍保留 |
| `FIGURE_FAMILY_REQUIREMENT`、audit 输入和 `figure_parentage` | 为新来源关系同时调整生产与消费合同 | 当前要求同一 Transform family，且 bundle guard 写明 `science.figure.evidence.materialize.v1` 标签和精确父链；不能直接把工作区文件当原合格附件 |
| 图证据 audit | 保留独立 Agent，提供新版本入口 | 自查预览不能替代独立审查；审查者看原图、request、全部选中附件和限制 |
| figure bundle normalizer | 保留算法，增加消费新来源族的兼容版本 | 必须证明新作者成果真的可供后续计算使用；不为迁移伪造旧 Transform 身份 |

定位：[图 Agent 声明](../../plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py)、[图工具](../../plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py)、[物化及下游父链校验](../../plugins/curve_figure_evidence/curve_figure_evidence/operation_transforms.py)、[插件入口](../../plugins/curve_figure_evidence/curve_figure_evidence/plugin.py)。

### 3.2 假设：保留必要的独立交接

```text
science.hypothesis.propose.v1 → science.hypothesis.criticize.v1
  → 必要时 science.hypothesis.revise.v1 → 精确对象的新审查
```

[`general_science_agent_operations.py`](../../src/scidiscovery/general_science_agent_operations.py) 已将竞争解释组织在一次 propose 中，并声明独立 critic 与修订边。没有证据表明应把作者与 critic 合并，也不应为了“四模块”重写一个假设大 Schema。首批不改这一链。后续仅清除正式提交前无必要的外围搬运；不能把有科学责任的审查说成机械成本。

### 3.3 实验：收口已有连续作者能力，保留不同权力

支持的新骨架路径：

```text
science.experiment.skeleton.v1
  → tcad.deck.author.initial.v1 / 合法 revise、runtime-failure 入口
      具体 execution plan + 源码 + 开发诊断
  → tcad.execution-plan.project.v1                 提取项目内精确计划
  → tcad.deck.review.v1                           独立综合审查
  → 打包 + 配置额度内策略授权／超额精确人工批准
  → tcad.study.execute                           adapter 执行、收集
```

[`general_science_experiment_operations.py`](../../src/scidiscovery/general_science_experiment_operations.py)、[TCAD Operation](../../plugins/tcad_artifact/tcad_artifact/plugin.py)、[`operation_workspace.py`](../../plugins/tcad_artifact/tcad_artifact/operation_workspace.py) 已具备骨架、项目内计划、开发工作区和综合审查。目标是普通实现调整留在作者 Run，不能再通过创建重复设计任务获取同一工作权限。实际科学条件变化、正式修订、生产执行权限仍分开。

[`project_execution_plan`](../../plugins/tcad_artifact/tcad_artifact/operation_transforms.py) 的确定性投影可在后续批次内收，但先保留其 Artifact 与消费者身份。`tcad.deck-review-validate.v1` 的正常链地位应按 [`project_packager.py`](../../plugins/tcad_artifact/tcad_artifact/project_packager.py) 的实际消费核验收敛；不为首批证据合并清理它。当前不把新骨架的 SProcess 支持外推为 SDevice 已适配。

### 3.4 分析：已有合适颗粒度，防止调度把它再拆碎

```text
tcad.result.analyze.v1 / science.result.diagnose.v1
  → 同 Run 读取、计算、保存、绘图、解释 → 正式 LayeredDiagnosis
```

[`result_analysis.py`](../../plugins/tcad_artifact/tcad_artifact/result_analysis.py) 与 [`science_operations.py`](../../plugins/curve_score/curve_score/science_operations.py) 已给分析者评分、图示、文件处理和保全能力。固定预计算解释入口 `science.result.diagnose.curve-error.v1` 是受限任务的合理选择；不把它设成所有分析的必经阶段。后续验收实际任务是否连续、图示失败是否复用计算，不重新建设已有能力或合并不同来源/权限的合同。

## 4. 首批实现方案：一位作者完成图证据

### 4.1 选择理由与最小范围

图证据链有明确的两位作者、共享来源与目标、相同本地视觉权限，分割点是确定性计算；适合直接验证颗粒度调整。相比之下，假设链的主要交接有独立性理由，分析已支持同 Run 连续工作，实验又涉及外部执行权限（其配置额度内自主执行作为主计划首批 B 独立交付）。首批选图证据不是因为它无实现成本，而是它能把收益归因于减少作者边界。

范围限定为**一个事前选定的栅格图、一个 panel、现有算法支持的线性/log10 坐标与明确系列身份**。真实验收来源与目标须在看到候选结果前冻结；优先复用已获使用权且有基线的原图。首批不扩展 OCR、自动识轴、PDF 图像恢复或新的跟踪算法；PDF 旧路径继续保留。无合适真实样本时，工程检查可以完成，但真实颗粒度验收明确未完成，不能用合成图冒充。

默认 TCAD 安装不含可选图插件，见[插件说明](../../plugins/curve_figure_evidence/README.zh-CN.md)。首批安装检查使用明确启用该插件的真实打包入口；不得偷偷改变全部 TCAD 安装配置。

### 4.2 优先复用现有工具证据机制

建议新增版本化的作者入口（例如 `science.evidence.extract.figure.v3`），沿用 `ScientificIntake` 主输出；再使用现有 `tool_evidence` 与 `recovery_manifest_output` 附件端口。不为四模块建立统一报告或新的聚合大 Schema。

现有实现已允许工具通过 `OperationToolContext.accept_evidence(..., derived_from=...)` 保存基于绑定输入的派生文件，并由服务产生 manifest、控制别名及父关系。相关位置：[`operation_tool_context.py`](../../src/scidiscovery/artifact_agent/operation_tool_context.py)、[`tool_evidence.py`](../../src/scidiscovery/artifact_agent/service/tool_evidence.py)、[`tooling.py:tool_evidence_ports`](../../src/scidiscovery/operations/tooling.py)。这条机制目前只识别上述两类集合端口；**不要假定 Agent 可以直接发布现有 Transform 的任意多个类型化输出。**

按以下顺序在一次纵向改动中闭合：

1. 作者仍判断图框、刻度、系列和 guide points。工具接收完整类型化 request，调用现有算法，将规范化 request、manifest、validation report、source panel、两幅检查图及 CSV 按受控别名保存。算法不替作者选择图或猜身份。
2. 工具先验证来源、类型、字节与预算，再保存完整结果并返回有界摘要和访问入口。作者在同一 Run 看原图/叠图/数值重绘，检查结果，必要时纠正描述；不把数值重新手写进输出。
3. 作者提交一份 `ScientificIntake`，其证据引用明确指向唯一选定的测量 manifest。选定 request/family 与该 manifest 的关联必须由工具记录可验证，不能靠作者自由文本或“最后一次调用”推断。未选中的尝试保留为恢复材料，不混入正式证据族。
4. 插件负责解析各附件的已有 Schema、验证选中 family 的完整性和来源。核心继续只管声明的工具权限、不可变记录、预算与 Run 状态。若通用 intake 校验不能接受同 Run 受控证据别名，在图插件声明适用的上下文规则；不能隐式跳过来源校验。
5. 新版本 audit 输入绑定 Intake、同生产者的控制 manifest、选定原图与完整选中 family。用插件内完整性校验替换新入口上不适用的旧 `CompleteTransformFamilySpec`；旧入口保持旧关系。不得简单去掉完整族要求。
6. 新版本 bundle 入口读取新关系并调用现有 normalizer；保留旧 `scidiscovery.curve-bundle.figure-evidence.v2`。新版本号与 ID 在实现前按现有版本规则冻结，不把新工具证据伪标记为旧 materialize Transform 的输出。
7. 新作者 review edge 指向新独立 audit。仅措辞修订须绑定原 Intake、精确非通过 audit 与原完整 family，不重复数字化；原图、标定或系列变化产生新证据和新审查。修订次数、无进展判定沿用现有机制。

这不是保证现有 API 无需改动的承诺。实现首先用该机制证明“选中一族 → 正式 Intake → 独立 audit → bundle”可表达；若必须引入通用嵌套 Run、多版本执行器或另一套来源注册，则停止扩大，记录具体能力缺口并重新决定切口。不能把一套通用工作流平台列为颗粒度改革前置工程。

### 4.3 资源与失败保全

现有工具证据实现有 32 条记录、每条至多 32 MiB、总量至多 256 MiB 等上限；旧图 Transform 可产生更多附件，不能宣称原支持范围无损迁移。首批建议至多 8 条曲线、至多两次完整提取候选：一族约 6 个固定文件加 CSV，两族最多 28 条，为受控记录留出空间。具体条目计数和尺寸须根据所选 fixture 在开工时核对，超出则缩小本批声明范围或走旧路径，不静默丢系列或提高核心上限。

两次提取是本批试验预算建议，不是新的全局研究规则。作者 wall time、token、工具计算次数及 byte 预算在验收前冻结，默认不高于旧两位作者完成同一任务所获总预算；运行中不得自动扩预算。当前 request/intake 声明的 900/600 秒只说明现有上限，不能证明新任务在某个时限下可完成。

完整测量记录在整理 Intake 前保存；后半段失败不应迫使重新取点。逐件登记发生中断时保留已有记录，只有完整 family 才可被选为正式证据；按同一请求重试不得制造不同身份或把半族当成功。恢复只消费已封存记录与明确恢复绑定，不访问另一 Worker 工作区，不继承科学资格。确认现有 adoption/resume 能保存派生父关系、别名和选定族；若不能，这是首批真实阻断，不靠增加上下文或重跑全部算法掩盖。

unresolved 分支须保留真实缺口，不能为满足 ready 条件虚构标定或恢复信息。零曲线的有限 Intake 可供审查，但不得规范化为可用定量曲线库；主链验收仍需另有一个真实正常提取正例。

## 5. 图证据细节的实施分工与顺序

以下首批是主计划的首批 A；TCAD 配置额度内自主执行为首批 B，可独立交付，不以本图证据批次完成为前置。后续实验/分析与 Root 收简遵循主计划。

| 次序 | 文件/责任范围 | 必须形成的结果 | 不作为前置条件的工作 |
| --- | --- | --- | --- |
| 0：短基线记录 | 在一份实施记录中冻结候选、现有改动、fixture、旧路径、预算、直接测试与已知失败 | 可解释的新旧比较；只记录受影响链，不扫描全部研究历史 | 全树测试修复、全部 pending 清零 |
| 1A：作者与工具 | 图插件 `figure_science_operations.py`、`figure_worker_tool.py`；必要的局部 finalizer/validator 放回插件 | 同一作者完成视觉判断、提取、自查和 Intake；受控保留完整结果 | Root 默认 JSON Pointer、全局自动绑定、native 自动 spawn |
| 1B：消费者与封存 | 图插件 `operation_transforms.py`、注册声明、审查/修订 guard；核心证据机制仅在证实通用缺口时最小调整 | 新 family 可审查、可修订、可规范化；旧关系不伪造 | 全部 Artifact 来源系统改写、递归依赖恢复 |
| 1C：同批交付 | 图插件双语说明、`roles/scheduler/evidence.md` 及实际生成入口、直接相关测试 | Root 默认选择新完整作者任务；安装态调用和一个真实作者/审查闭环 | 所有指南重写、退役全部旧 Operation |
| 2：实验/分析实际断点 | TCAD 作者 workspace、现有分析工具、对应 scheduler 指南和精确消费者 | 普通实现调整、计算与绘图在已有作者 Run 连续完成；只修实测断点 | 重做科学骨架、另建四模块运行时 |
| 3：伴随收简 | Root 结果投影、确定性输入准备、用不到的正常入口 | 已经消失的任务边界不再要求手工协议；然后评估旧 writer 退役 | 为无变化的完整微任务链增加外观包装 |

1A、1B、1C 是**一个可独立验收的首批纵向切片**，不是三个必须分别全面部署、审查的阶段。可以按文件分工，但共享代码、合同与测试由一个集成负责人收口；作者与下游修改不得分别宣称完成。其他模块不等待“全部 Root 简化”才能开始，也不要求四模块同时修改。

工程独立复核聚焦本批精确 diff 及生产者—消费者组合；科学 audit 判断具体图证据。二者不能互相替代。若实现影响共享 core evidence/recovery，再按实际影响扩大回归；不要因新计划存在而重做全架构审查。

## 6. 首批验收：完成工作且确实少一次作者交接

### 6.1 正向闭环与结构收益

冻结同一来源、目标、允许算法与科学判据，比较旧路径和新路径。已有基线仅在来源、任务与可观测字段充分一致时复用，否则安排一对有界运行；不做开放式 A/B 搜索。

| 验收项 | 必须观察到什么 |
| --- | --- |
| 完整交付 | 新作者正式 completed；独立审查能读到完整证据并形成适用 verdict；正常正例能得到现有消费者可解析的 curve bundle |
| 任务颗粒度 | 正常初次作者链由两个科学作者 Run 降到一个；没有后台第二作者、隐藏 handoff Agent 或两个串联微任务 |
| 上下文重建 | 定位/标定者随后直接整理 Intake，取消第二作者重新读论文、解释标定和理解附件的一次重建；审查者的独立读取保留 |
| Root 成本 | Root 不再在 request 作者和 intake 作者之间调度物化、逐项搬运 family；可保留必要的独立审查与规范化调用 |
| 质量 | 原图身份、标定、系列、局部缺口、不确定性与适用限制不丢失；结果科学质量由独立审查判断，不能以新旧文字一致代替 |
| 失败成果复用 | 提取完成后注入一次整理/提交前失败，合法恢复直接消费完整已保存提取，不重做成功计算；半族失败不能通过审查准入 |
| 有界成本 | 记录总 token、单作者峰值上下文、重复读取、工具调用、耗时与预算耗尽；缺原生 token 则记不可观测，不按字节推算 |

一次正常正例与直接相关反例足以证明本批支持范围，不能声称普遍效率。若减少交接却超出冻结预算、重复计算或导致上下文不可承受，本批不能宣称简化成功；先确认具体原因，再决定缩小支持范围或保留旧路径。无需达到事后挑选的 token 百分比收益。

### 6.2 集中覆盖的负控

用真实入口和生产者产物构造以下直接风险，不逐项新建计划：

- 混入另一个 request/来源的 CSV、漏一个声明附件、改字节或用未选中族，均在指定校验处拒绝；所有规则在模型可见合同中声明。
- 同一作者身份不能承担独立 audit；原审查不能批准修订对象；原资格不会自动转移。
- 工具记录不是 completed 科学结论；运行中草稿不能作为 Root 科学结果读取。
- 忠实 unresolved 可交付有限结果，但不能成为定量 curve bundle 的合格正例。
- 提交重试不重算数字化；恢复不丢原始目标、来源、选定 request 或新失败信息。
- 新入口声明的边界与运行时上限一致；超限在昂贵提取或任务创建前尽早给出准确错误，不靠反复改 Intake 消耗预算。

优先扩展现有 `tests/operations/test_minimal_figure_extraction.py`、`test_m2_optional_figure_plugin.py`、`test_figure_semantic_compilation.py`，并选取工具证据/恢复的直接测试；真实加载通过插件的 `pyproject.toml` entry point 和既有安装验证路径。具体命令依据最终 diff 和基线选择，不在计划中冻结一个全量测试清单。测试替身通过不能代替实际模型的单作者闭环。

## 7. 迁移、发布与回退

1. **旧记录不改写。** 旧 request、Transform family、Intake、audit、bundle 与失败记录保持原字节、父链和资格。新路径不继承旧审查。
2. **旧入口先保留。** 新旧输入形状和生产者关系不同，采用明确版本。新正常路径验收后再调整默认建议；公开旧 writer 是否退休需确认受支持消费者，静态搜索不能证明无外部消费者。
3. **受影响在途任务先排空。** [`RunService._compiled`](../../src/scidiscovery/artifact_agent/service/runs.py) 比较当前安装的 version/digest，不匹配会报 `Run operation contract changed`。保存 assignment 不等于可跨部署继续。部署前完成受影响 Run；无法完成时明确停止并遵守已有恢复规则。本批不开发多版本执行器。
4. **回退只切候选与新任务入口。** 保留新产生的科学记录和失败现场；不删除历史制造干净状态，不保证旧二进制能继续新 Run。回退前也要处理受影响在途任务，先验证仍有支持新记录历史读取的路径。
5. **自动 native spawn/attach 不是首批门槛。** 保留当前宿主支持的派发方式；没有稳定程序入口时，不新增调度进程管理系统。
6. **输入候选查询保持只读。** 后续机械恢复仅沿显式、已知关系返回候选、缺口和歧义。派生产物登记是显式写命令；不在查询里暗中创建 Artifact，不递归推断科学依赖或自动选最新对象。

## 8. 停止条件、资源纪律与未证实事项

首批在以下事实同时成立时结束：一个真实正常图证据任务以一个作者 Run 完成，独立审查和下游规范化可用，少掉第二作者及其上下文重建，直接负控正确，后半段失败能复用已保存测量，且未突破预算。到此即可交付，不等待 PDF、32 系列支持、自动派发、全局绑定或所有历史文档清理。

若同因失败且没有新证据，或达到事前预算，停止该次尝试并保留有限成果。是否继续由新的范围/价值决定，不自动加次数、改名续跑或降低科学判据；“首轮加一次复验”不作为全局硬次数标准。权限、来源和独立性阻断不能因预算用完而放行。

验证串行开展，遵守当前受限环境的资源约束；不并发叠加安装矩阵、模型审查和 solver。首批无 solver 需求。必要的安装测试集中一次，记录候选、资源及既有失败；除新增失败或共享边界风险外不扩大测试。规划工作本身不授权部署、科研实例选择或外部执行。

尚未证实、必须在对应实施位置验证的条件：

- 工具证据端口对多次图测量、同 Run intake 引用和后续独立审查的完整可达性；当前 preview 并未实现它。
- 跨一次失败恢复后，工具派生父链、别名、选定族与未选中记录能否按现有机制正确保留。
- 新 audit/bundle 的插件校验能否在不扩大 core 权威的情况下表达精确完整性；现有旧 guard 不能直接复用。
- 实际 fixture 的条目、尺寸、数字化次数和上下文是否落在本批预算内。
- 当前宿主对可选图插件的安装/加载与实际 Worker 能力；本轮未核验安装态。
- 单作者是否降低整个任务成本；结构上少一次任务不保证峰值上下文或总 token 必然下降。

这些是明确的实现验证项，不是先开展六项独立研究的理由。首批围绕一条链一次闭合，阻断时记录到同一实施记录。除本文、一份连续实施记录和必要的精确审查/验收证据外，不为每个小修再建计划族。

## 9. 交付报告格式

最终只需回答：候选与安装身份是什么；支持哪类完整任务；由几个科学作者完成；取消了哪次交接和重复阅读；独立审查、来源和权限如何保持；后半段失败复用了什么；实际时间/token/峰值上下文及不可观测部分；哪些旧入口保留；本批是否达到停止条件。

**四模块改革的首个成果应是一项完整科研工作真的由一个有界作者连续完成。接口收简随后服务于这个已经改变的工作边界。**
