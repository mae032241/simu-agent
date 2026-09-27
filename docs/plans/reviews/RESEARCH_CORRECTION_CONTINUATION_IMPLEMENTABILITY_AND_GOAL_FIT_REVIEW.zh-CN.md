# 校验纠错与跨轮续研完整实施计划独立审查

日期：2026-09-08。整体结论：**REVISE**。本报告审查完整新计划，不继承先前七文件提案的结论。

| 维度 | 结论 | 判断 |
| --- | --- | --- |
| 可实施性 | REVISE | 五个直接 Operation、两处输入规则及大部分十文件落点成立；但计划要求 Root 执行的精确历史寻源没有现成查询投影，至少须增加一个已有查询文件到范围。 |
| 用户目标匹配 | REVISE | 已覆盖同 Run 纠错、负面审查、本轮选择、正式目标保留和两轮真实推进；冷启动的确切绑定恢复仍缺一段，新增字段和文件可读性不能补足。 |

唯一确定阻断是 R1；未发现必须新增状态机、服务、公共 Operation、固定 DAG 或通用包装器的理由。

## 1. 冻结身份与边界

- 源码根：`123/scidiscovery-e5.2`；分支 `refactor/m7-pre-e5.2`；HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`。
- 计划：`docs/plans/RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md`；核验 SHA256 为 `182fc74bdf66248df9b5e4802785fba61538f49e4cf81326921bcc9767cfe9f3`。
- 按当前大量修改、删除及未跟踪生产文件审查，包括未跟踪的 `curve_contract_compiler.py` 和 `execution_context.py`；结论不适用于单独 checkout HEAD，也不代表这些既有修改整体通过审查。
- 已读工作区根及发布副本 `AGENTS.md`。本次为独立工程审查，未进入 ResearchInstance、科学 Worker、审批或执行生命周期；未读取失败 Worker 草稿。
- 已应用工作区根三个 `scid-cross-boundary-review`、`scid-find-simplifications`、`scid-change-scope-checks` 技能，并对照设计宪章、架构、约束登记及现有评估文档。仅写本报告。

## 2. R1：Root 看不到计划承诺让它追踪的确切父链（阻断；必须改范围）

**计划位置：** 72–74、178–195、216–222 行要求 Root 找到设计时的同一目标和相关反馈，明确包括经 revise 的计划，并禁止仅凭相同 key 猜测原件；243、324 行将新会话恢复作为验收。252–265 行十文件清单没有现有 Artifact 查询实现文件。

**源码证据：**

- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py:140–166` 是当前完整 Root 工具面，没有另一项 provenance/input 查询。
- `mcp_root_instance_routes.py:134–175` 的 inventory 仅列每个 logical_name 最新版本；`:246–263` 的 artifact_catalog 只有名称、Schema、尺寸、时间及过滤后的 labels，无父名称或输入绑定；`:78–104` 的 current 只给显式所选对象。
- `mcp_root_run_routes.py:10–35,58–82` 的 run_list/status 能找 Run 及其输出，不能查其 inputs。sealed_output 的 payload 也不含控制绑定。
- `mcp_root_approval_routes.py:10–47` 只给审批状态/决定，`mcp_root_execution_routes.py:444–491` 只给执行结果/输出名称；`mcp_root_operation_routes.py:57–73` 给目录声明。preflight 检查调用者已提供的绑定，不揭示某个已有计划来自哪个 intent。
- 实际父链已存在：`service/runs.py:848` 登记所有确切输入父引用，`mcp_root_operation_routes.py:880–900` 登记 Transform 父引用；这些是内部存储能力，尚不是 Root 可调用的读投影。

**可达场景与影响：**

1. 首份物化计划已经生成，随后目标/基础有新修订或实例内存在另一组同 key/statement、不同 mandatory_targets/closure 的目标。新会话只知道计划名称、最新 inventory 和旧 design Run 输出；没有计划→intent/原目标的可查询边，无法证明选回设计当时的确切原件。原目标是 Transform 输出，不能假设存在可由 run_status 读取的目标 Run。
2. 计划经 experiment.revise 产生完整新对象后，新 Run 的实际输入只有 prior_draft/change_request（`general_science_experiment_operations.py:149–163`）。新会话既看不到这条绑定，也不能沿旧物化计划继续找原目标。增加 review 的可选目标端口和 key/statement 校验只验证传入内容，无法发现上述同文本异约束的错误选择。

仅有一个目标且父会话还记得名字时，L4 可能表面通过；这不能证明“不继承聊天、依据确切记录续研”。让 Root 猜名字、读控制数据库、扫描旧 Worker 工作区，或试遍未知材料组合，都不是本计划声明的恢复路径。

**最小修正：** 将 `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py` 加入生产范围，使清单成为 **11 个已有生产文件**，在现有 `artifact_catalog` 响应增加有界的语义父名称投影。只从当前实例已存在的 Artifact bindings 映射确切父引用；保留旧 revision 的准确名称，不换成 latest。缺少本实例绑定时明确表示无法定位，不泄露其他实例的对象名称。无需新工具、数据库字段、递归服务或包装对象；Root 按现有查询逐层读取。若实现需要辨别同型父项，投影既有来源别名即可，不能凭 payload 文本重建关系。不得返回内部 ID/ref、摘要、令牌或 Worker 路径。

同时把计划 222 行写成真实查询与绑定步骤，并在 P2/P3 和 L4 明确以下验收：

- 固定版本、清空父聊天，仅从实例中的一个首轮计划名称，经真实 Root MCP 读入口恢复其原目标及相关输入；存在同 key/statement 的新目标时仍返回旧原件。
- 对经过至少一次 revise 的计划重复上述验收；审查绑定错误目标时不可把“key 相同”记为恢复成功。
- 历史版本可定位；跨实例父引用无名称泄露；无写操作、无控制身份进入 Worker；绑定变化仍改变请求指纹，新计划仍须新审查。

## 3. 已核对的可实施部分

| 路径 | 结论及具体依据 |
| --- | --- |
| 同 Run 修正与 checker 故障 | `service/runs.py:453–477` 已将 RunOutputError/WorkspaceError 返回 rejected 并保持运行，RunCheckerError 记录 failed。复用而不改生命周期合理；新增语义错误仍须按既有 SemanticRuleViolation 合同交付。 |
| blocked 项目 admission | `mcp_root_operation_routes.py:1329–1361` 先验证当前 producer，再允许确切 reviewer 主体；`:1119–1129` 的 claim 禁止仅适用于 claim_evidence。project 改 prior_signal 可解开此门，不等于放宽旧 producer 身份。 |
| review workspace 与负面 submit | `operation_workspace.py:320–352,391–428` 的确定性物化只用于 author，review 解析并只读展开。`project_packager.py:1233–1236,1249–1294` 的 case/参数实现检查和 `plugin.py:108–136` 的 uncertainty 检查正是需拆分的落点；计划已明确处理三类，不只换 usage。结构不可解析或冻结参数上下文错配仍拒绝符合范围。 |
| pass、package、Effect | `project_packager.py:713–743,784–786,1434–1476` 保留报告一致性、执行准备及 pass 条件；`operation_transforms.py:171–180,407–425` 保留精确项目/能力/计划父链及包装输入。共享 inventory 例外限 Agent，不触及这些 Transform/Effect。现有正常路径及假 pass 负控仍须按 P1 实测。 |
| 五个 Operation 与十文件中的目标修改 | design/materialize/object.review/experiment.revise 位于 `general_science_experiment_operations.py:35–285`，deck.review 位于 `plugin.py:563–599`。目标 Schema、物化和完整修订校验均有计划所列落点；未发现生产下游读取旧 proposal.objective 的直接消费者。R1 以外未证实必须扩大范围。 |
| 反馈真实交付 | `_agent_input` 已有 wildcard/opaque 资源；`spec.py:114–124` 是 wildcard exposure 阻断，producer admission 的逐项入口是另一阻断。`service/runs.py:236–242` 排除 handoff_only，其余交付原件；Local 输入只读、context_sources 和父链复用可成立。计划三组可选、总预算和集合别名要求足够具体。 |
| 证据引用与修订 | `operation_contract.py:285–302,317–333` 只把可见 inventory 投影到 evidence 枚举。object.review 使用 evidence_paths=() 并校验实际可见别名，可避免只允许引用反馈而不能引用 plan/objective。`general_science_experiment_components.py:141–180` 与 Root 精确 review 检查提供完整修订基础；可选输入不能写进 required_inputs。 |
| 局部设计到结果 | `curve_contract_compiler.py:115–124` 按本轮 required_observables 选择目标；`science_operations.py:658–680` 的 complete_plan 指精确本轮 validation plan。内存探针确认：未选另一 observable 的未来目标时，当前曲线合同可编译，同时 objective_coverage 返回 fail。没有发现必须因目标列表文字而生成未来 case 的下游机制。 |
| ABI、安装与资格恢复 | ABI 16 位于 `spec.py:10`，编译器使用 ABI 参与合同身份；17 的共享变更说明合理。现有安装流程重建 profile/AGENTS，无需新部署入口。P5 在部署前逐项证明新资格建立路径、旧资格不继承的条件具体且必要；本审查未把该条件当作已经完成。 |

## 4. 目标匹配与非阻断限制

- **正式 payload 与 handoff：** 计划 74、199–210 行明确让目标、选择理由和未来条件进入正式 intent/plan，审查缺口和诊断依据进入已有报告；`runs.py:840–848` 登记的是科学 payload，signal 分开保存。这个区分正确，不需要新增 progress wrapper。尚须由 L1/L4 检查内容实际存在，而非只检查数组非空。
- **全目标与本轮选择：** 保留 Portfolio.objective、每个 proposal 的完整列表/current 子集，移除 `experiment.py:550–564` 的单轮全部 observable 覆盖循环，同时保留严格 case/变量/validation 关系，符合用户目标。目标是否暂缓合理属于独立科学审查；字符串子集校验不能替代这项判断。
- **领域粒度限制（已验证，是否影响 Fig.4 未确定）：** curve compiler 以 observable 选 mandatory_targets，不读取新的 current_objectives。内存负控证明两个 target 使用同一 observable 时，省略其中一个仍被 `curve_contract_compiler.py:121–124` 拒绝。因此不能将计划宣称为任意 target 粒度的分轮能力；P2 需用实际选定的 Fig.4 当前范围检查。若科学选择确需拆开同 observable 的 targets，再据反例修订领域范围；目前不足以将其升级为本案例阻断。
- **九个既有 inventory 消费者：** 内存编译已枚举两项通用 evidence audit、两项 curve contract、两项 parameter evidence、figure request、figure extract 和 figure audit。图表完整 family、参数审查主体/审批及后续确定性消费仍有独立门；未发现本次只读例外直接授予执行资格。P3 逐项负控仍必要，不能用两个新 feedback Operation 的正例替代。
- **旧记录与升级：** `mcp_root_run_routes.py:89–99` 对退休合同不提供 sealed_output，signal 也随之不可读。新 inventory 文件能交付旧 payload，不能恢复旧 handoff 独有解释。计划已在 74、230–246 行明确这一限制，并把同版本会话续研与部署恢复分开；不构成新增阻断，也不能声称历史信息完全补齐。
- **P0–P6/L1–L5：** 已要求真实结果、封存分析、目标调整、独立新审查和第二轮实际输出，排除仅排队/启动/文本计划，足以发现“只新增字段”的假完成；R1 的两版目标及 revise 冷启动负控必须补入。科学有据停止与整条两轮 PASS 分开合理。固定一个 Fig.4、保留原评分算法、分步验证后一次发布均是合理范围约束。

## 5. 实际验证、未验证与最小处置

- 已执行只读身份/源码检索；用 `PYTHONDONTWRITEBYTECODE=1`、显式源码 PYTHONPATH 在内存编译五插件目录：**成功，49 个 Operation，9 个现有 Agent inventory 消费者**。没有创建运行时、数据库或科学对象。计划摘要复核、`git diff --check` 和报告空白检查通过。
- 使用 `test_m2_curve_analysis_boundary.py` 的纯模型 fixture 调用现有 curve compiler 与 objective coverage：不同 observable 的局部合同编译成功，总体覆盖 fail；同 observable 省略 target 得到预期 SemanticRuleViolation。不是 pytest 执行，也不是新目标 Schema/真实科学研究已经通过。
- 未运行 pytest、wheel、平台子进程、真实 Agent 或 solver；计划尚未实施，不能验证未来修改、实际安装/资格恢复及 L1–L5。P4 的安装态和串行回归、P5/P6 的受控真实验收仍保留。
- 最小处置是修订计划：增加一个现有 Artifact 查询文件和 R1 验收，保留其余 Operation/Schema 设计；无需推翻已确定的十文件内工作。修订后再审该具体增量；本 REVISE 不授权部署或科学执行。
