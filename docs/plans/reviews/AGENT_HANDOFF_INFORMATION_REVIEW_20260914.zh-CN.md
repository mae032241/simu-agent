# SciDiscovery Agent 信息交接独立源码审查

审查日期：2026-09-14。审查对象：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2` 的当前完整生产源码；HEAD 为 `2d252a9b9d703919e47e7146b5c4c5c4e0dd8316`。以下路径均相对该仓库，行号以本次工作树为准。

本次只读源码、架构宪章、约束登记表和当前决策索引；未调用实例、Run、Worker 或仿真工具，未读取控制状态目录、Worker 工作区或聊天内部存储，未运行测试或编译，不形成科学结论。唯一写入是本报告。开始时确认已有四个修改文件：`plugins/tcad_artifact/tcad_artifact/{operation_workspace.py,plugin.py,project_packager.py}`、`tests/operations/test_tcad_gap_continuation.py`；另有两份未跟踪 Fig4 文档。它们均作为现状保留，未修改、回退或据此推断运行历史。

采用 `scid-cross-boundary-review`、`scid-find-simplifications` 的生产边界与承重不变量要求；结论来自独立源码分析，不以既有审计 PASS 或父代理意见代替证据。

## 结论

交接主干是合理的：精确 Artifact 输入、无父聊天的角色派发、领域工作区、完整不可变结果、独立审查和审批分工都有必要。当前也已经实现了多项直接减少重复劳动的改进。问题集中在相邻层的表达尚未完全收敛：有些本应进入下游的说明留在 Root 专用 handoff；有些本应按需读取的源码、日志和工具合同仍随默认回复返回；已有正式摘要的部分角色仍生成第二份交接摘要。

保留五项高置信 finding，其中一项是信息完整性缺口，其余是可证实的重复交付或表达问题。没有证据支持重建调度状态机、增加摘要 Agent、引入通用 RAG、取消完整审查、取消精确身份验证，或用字数拒绝规则约束科学输出。也没有测得模型实际 token 用量，因此本报告不给节省比例，不用文件字节或耗时推算 token。

## 真实生产链与已经实现的精简

源码追踪覆盖的是发布入口，而非手工构造的测试运行时：

1. `pyproject.toml` 的 `scid` 入口进入 `src/scidiscovery/artifact_agent/interfaces/cli.py:101`；`init` 调用平台初始化。插件通过唯一 `scidiscovery.plugins` entry point 注册；TCAD 入口见 `plugins/tcad_artifact/pyproject.toml:20`。
2. `src/scidiscovery/platforms/codex.py:152` 附近使用 `compile_installed_catalog()`，`_operation_toml`（548）把编译角色提示与 backend/lifecycle 指令组合为平台角色；`src/scidiscovery/artifact_agent/interfaces/mcp_daemon.py:114` 和 `mcp_local_worker.py:532` 的生产进程也从安装目录编译，不另查角色 prose 路由。
3. Root 从同一目录投影选操作并做绑定/预检；`src/scidiscovery/artifact_agent/service/run_assignment.py:21` 生成只含声明输入的 assignment；`RunService._materialize_workspace`（`runs.py:1095`）调用冻结的领域 hook；`LocalWorkerToolRouter._open`（`mcp_local_worker.py:298`）打开精确 Run。
4. `RunService._validated_candidate`（`runs.py:1012`）先 finalizer 后 seal，再由 `run_outputs.validate_run_output`（57）检查完整结果；`RunService._register_candidate`（1220）登记 payload，`SchedulerSignal` 单独保存。Root 仅在 completed 后通过 `RootRunRoutes.run_status`（29）读取二者。
5. 下一角色获得显式绑定 Artifact 文件；普通修订预置 copy-on-write 草稿，TCAD 修订展开源码；失败恢复拥有独立的草稿/证据覆盖与尝试预算，不能继承旧科学资格。

已经落地且应保留的精简：

- **分析接手**：`plugins/curve_score/curve_score/analysis_workspace.py:157` 生成有界入口、来源位置和摘录；`analysis_bindings.py:121` 为 TCAD 提供项目索引及案例矩阵，源码只有位置/大小；32 KiB 是展示预算而非原件截断。工具和校验继续读取完整冻结输入。
- **分析输出**：`result_materialization.py:46` 根据正式 verdict/summary 生成短 handoff 引用；`analysis_workspace.py:26` 明确 gates 和额外评估可省略。`analysis_files.py:76` 要求引用保存的计算记录，避免在报告复制请求、收据和数组。
- **增量修订**：`run_assignment.py:97` 复制精确 base 为可编辑完整草稿；`general_science_resources.py:29,49` 与 `general_science_experiment_components.py:68` 要求局部修改。`run_outputs.py:159` 仍拒绝未变化 payload，新对象不继承旧审查。不能把“最终发布完整快照”误写为“模型必须重新生成全文”。
- **机械事实**：`result_materialization.py:33,59` 已复制 Intake 目标、case_count、proposal objective 和 review verdict；`operation_workspace.py:596` 已复制 TCAD review capability/verdict；TCAD 作者无需手工序列化完整工程，finalizer 扫描真实文件。
- **失败接续**：`analysis_workspace.py:72` 恢复受限 scratch 副本，不把旧 latest telemetry 当本轮运行；`runs.py:1553` 同时公开覆盖情况与保留原目录状态，`run_assignment.py:79` 明确恢复草稿不是证据。`mcp_local_worker.py:304` 允许同编译角色领取新 Run 并清空工具状态。
- **错误反馈**：`runs.py:912` 已有分页诊断；`run_outputs.py:238` 将可修订语义错误与工程故障分开。无需用模型重新解释无界原始异常，更不应为省字删掉具体原因、字段位置或来源身份。

## Finding 1 — P1：TCAD 初始化覆盖说明被指定写入 handoff，却不随项目到达独立审查

**分类：已证实的交接契约缺口；不是已观察到的某次科研误判。**

**准确位置**

- `plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md:114`—118：明确要求在 handoff 解释初始化探针与生产过程的对应关系，以及未测试的 case-reset 路径。
- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:757`：finalizer 构成 `{handoff, payload=project}`。
- `src/scidiscovery/artifact_agent/service/run_outputs.py:151`、257—266：Artifact 内容只编码 payload；handoff 另投影成 `SchedulerSignal`。
- `src/scidiscovery/artifact_agent/service/runs.py:1230`：只登记 `validated.content`。
- `plugins/tcad_artifact/tcad_artifact/plugin.py:484`—487：review 绑定 `project` 和 INITIAL_INPUTS，没有作者 handoff Artifact 端口。
- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:391`：review 只解析 project；`roles/tcad_deck_reviewer.md:70`—73 要求审查探针覆盖。

**生产调用链与可达场景**

初始 author 或 revision author 按提示把“探针覆盖哪些生产过程、哪些 reset 分支未测”的解释仅写到 `deck/handoff.json`，并合法提交。Root 能读到该解释，但 reviewer 通过 `project` 输入只能得到源码和控制 attestation。`ProjectInitializationAttestation`（`project_packager.py:339`）是控制生成诊断，不能承载作者刚写的说明；`DeckProjectDraft`（430）也没有 handoff 字段。普通项目的新 revision 同样不能自动取回旧作者 handoff。失败恢复能够保留某些旧 handoff，并不能补齐这条 completed→review 的路径。

**影响与证据边界**

说明没有从存储中整体消失，但在正式下游输入边界不可见。审查者必须重新从源码推断该说明，或无法得知作者明确承认的未测范围。它仍须独立检查，所以不是把作者说明当证明；问题是框架要求产出的审查上下文并未交付。不能断言所有 handoff 都有此问题：gap 的 `summary/missing_inputs/affected_work/suggested_resolution` 已在 payload；分析也已把主要结论放入正式报告。

**最小建议**

先调整这段 author 提示，把探针对应关系和未测范围写到会随项目封存的相关源码注释中，handoff 仅引用文件/位置；reviewer 再独立核对。源码本就需要通过完整 Artifact 交接，因此无需增加状态实体或新 Agent。对确实不适合放入源码的说明，再单独评估最小可选正式字段；不要把每个上游 handoff 全文自动注入下游，更不要让 Root 从聊天改写科学事实。

**保持的不变量**

作者说明仍是作者主张；独立审查、当前源码对应的 attestation、完整 project 身份和执行批准都保留。新增源码注释属于新源码内容，不能继承旧源码的诊断证明。

**兼容、回退与最低验收**

不回写历史项目；旧对象缺少说明时如实标记缺口。提示变更按正常编译/部署代次处理。最低验收是一条 author→submit→review 的发布路径探针：作者说明只写一次，review 的声明文件中可准确定位；手工改变探针源码后旧 attestation 仍失效；reviewer 不读取 Root signal、旧目录或作者聊天即可完成核查。回退只回退新提示，不删除已封存内容。

## Finding 2 — P1：完成状态查询无条件内联完整 payload，Root 的读取边界仍会带入大量源码/日志

**分类：已证实的默认过度交付；实际 token 和具体运行中是否被平台截断未测。**

**准确位置**

- `src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py:29`、59—69、130—158：每次 `run_status` 都调用 `_sealed_output`，读取完整 Artifact JSON 并放入 `sealed_output.payload`；没有仅状态或字段读取选项。
- `plugins/tcad_artifact/tcad_artifact/project_packager.py:68`、441：项目包含 `files[].content`。
- 同文件 `ImplementationGap`（693）、`attempt_files`（702）：缺口包含完整受限源码/诊断文本；`operation_workspace.py:634` 由控制捕获它们。
- 同文件 `ReviewedDeckPackage`（808）也内嵌完整 project；分析 Worker 的紧凑视图见 `analysis_bindings.py:145`—151，但 Root 未使用该边界。

**生产调用链与可达场景**

author/gap 合法封存后，scheduler 为确认 completion、取得 semantic output name、读取 handoff 或查询错误分页调用 `run_status`。回复不仅给生命周期和科学结论，还携带全部项目源码、绑定矩阵或失败日志。同一 completed Run 被再次查询时会再次全量返回；即使提供 `diagnostic_after` 请求错误页，该载荷仍同时返回。

**影响与证据边界**

这是确定的工具回复重复，随 payload 大小增长；不是把“服务端读了文件”当模型 token，因为这些字节确实进入 Root 返回对象。Root 需要理解科学结果，但调度 TCAD 独立审查并不通常需要把每行 solver 源码或每行失败日志都呈现给调度模型。潜在上下文占用和重要字段被平台展示截断的风险存在；本次没有运行日志证明某一场景实际丢失了字段。

**最小建议**

在现有 `run_status` 增加明确的内容读取选项：先允许仅状态/信号/语义对象元数据；需要正文时，支持对同一精确 sealed Artifact 读取有界 JSON pointer 子树或完整 payload。让新 scheduler 对重复监控、诊断分页使用简式，仅在做科学选择时读取相关正式字段及必要原件。不要把一个删减后的对象伪装成完整 `sealed_output`；返回位置、遗漏状态和原精确名字，完整读取始终可用。不增加摘要 Agent，不让控制面自行判断哪些科学内容“最重要”。

**保持的不变量**

仍只在 completed 后读取；historical/current 状态、绑定身份、完整对象与原始字节、独立审查、审批主体和 collection 门禁都不改变。简式回复不表示资格。Root 不能只看 verdict 而忽略本轮相关限制。

**兼容、回退与最低验收**

先保留旧参数默认行为，新 scheduler 显式选简式；待已有消费者适配后才考虑调整默认。最低验收：含可识别长源码/日志的合法项目在简式状态及诊断分页中不回显正文；显式完整读取逐字保真；字段读取有精确 pointer 和遗漏标记；旧 completed/historical 记录可读，running/failed 不暴露未封存正文，null alias 不被替换。回退到旧完整回复不影响已存对象。

## Finding 3 — P2：按需工具合同交付只覆盖分析入口，其他 Local 角色仍在 open 和 assignment 两处接收同一合同

**分类：已证实的重复交付；不得扩张为“所有可见工具 Schema 都已注入每轮”。**

**准确位置**

- `src/scidiscovery/artifact_agent/service/run_assignment.py:77`—78：assignment 保存全部已允许工具的完整合同。
- `src/scidiscovery/operations/tooling.py:164`—176：合同含生命周期及领域工具的完整 `description/inputSchema`。
- `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:325`—344：只有 `domain.paths.start_here` 存在且可读时，open 返回合同路径/pointer；否则回传完整 `tool_contracts`。
- `src/scidiscovery/general_science_components.py:415`：普通 workspace 没有 materializer/start_here；TCAD `operation_workspace.py:539`—562 的 paths 也没有 start_here。
- `src/scidiscovery/platforms/codex.py:465`—471：角色必须读 assignment 当前输入索引，并在调用领域工具前读完整选中合同。

**生产调用链与可达场景**

通用设计/修订/审查或 TCAD author/reviewer 打开 assignment 时，合同已经作为 open 回复出现；随后读 assignment 的完整文件，合同再次出现。带复杂 debug/PDF/领域工具的角色比只有生命周期工具的角色更受影响。是否逐轮重读全 assignment 取决于 Agent 行为，但第一次 open 的完整交付没有按需选择。

**影响与证据边界**

静态合同内容两处相同，平台提示还说明了完整合同用于弥补工具 Schema 渲染不充分，因此不能直接删除权威合同。但完整合同落在本地受限文件即可，不必以“具有分析 start_here”为是否内联的条件。普通无领域工具角色的收益会较小。

**最小建议**

把 Local 的合同路径/pointer 返回条件从“存在分析入口”改为“当前不可变 assignment 中有合同”；start_here 作为独立导航选项。assignment 可保留原完整合同，不新增工具服务。提示要求先提取输入索引/预算/输出信息，仅在使用某工具前读取该工具的完整子树，包含本地 `$defs`。Hardened 路径不能照搬本地路径方案：必须先确认它已有可用文件读取工具，否则保留原内联行为。

**保持的不变量**

合同仍来自精确编译 Operation，不从新目录替换旧 Run 的合同；工具权限不变；模型使用前仍能完整阅读所选工具的必填、类型、默认值、上限及语义描述。

**兼容、回退与最低验收**

旧 assignment 无合同字段继续走现有 fallback；路径不存在或不可读仍给可用合同，不在身份不匹配时伪造新合同。最低验收：普通设计、TCAD author、review、analysis 的新 Local open 不包含领域 Schema 正文；按所返 pointer 读取到的合同与对应当前 assignment 完全一致；有嵌套 `$defs` 的真实工具调用可合法构参；Hardened 和旧 workspace 行为不退化。回退只恢复 open 内联。

## Finding 4 — P2：已有正式 summary 的审查与缺口结果仍要求第二份 handoff.summary

**分类：已证实的重复表达要求；语义分叉是允许出现的风险，不声称已发生具体错判。**

**准确位置**

- `src/scidiscovery/artifact_agent/schema/role_result.py:21`—25：`handoff.summary` 必填。
- `src/scidiscovery/artifact_agent/schema/research_cycle.py:100`—111：`ScientificReview` 已有必填 summary 和可选 next_actions。
- `plugins/tcad_artifact/tcad_artifact/project_packager.py:698`、753—767：gap/DeckReviewReport 已有正式摘要、缺口、后续建议。
- `src/scidiscovery/operation_declaration.py:73`—74：已有正式 review 的角色仍被要求保留 handoff summary 和 next actions。
- `result_materialization.py:76`—88、`operation_workspace.py:596`—609：只投影 review verdict，不投影 summary。
- `operation_workspace.py:318`—328：review 模板同时放了两份需替换的摘要占位符。
- 对照已实现路径：`result_materialization.py:46`—56 已对分析只生成短引用。

**生产调用链与可达场景**

独立科学计划审查、TCAD 代码审查及 TCAD implementation gap 都需要填写正式结果摘要，同时为 envelope 写另一个非空摘要。Root 读取两者，下一角色通常只读 payload。模型可以用短引用避免实质重复，但当前通用提示及模板没有像分析角色那样明确免除第二次概述。

**影响与证据边界**

至少多了一份模型必须处理/填写的字段，也容许正式摘要已修改、handoff 摘要仍保留旧说法。要求额外“摘要一致性验证”只会再次增加机械负担；分析已经证明可通过同一 finalizer 生成引用来避免双写。

**最小建议**

仅对已有权威正式摘要的类型，沿用现有 finalizer 模式，允许 draft 省略 handoff 的机械 summary/verdict，由它生成指向正式 summary/建议的短引用，并在工作区合同和角色提示中明确。必要假设、限制和可交付缺口应放在下游可读正式字段（先处理 Finding 1），handoff 不承担第二份科学正文。

**保持的不变量**

formal verdict 和 summary 仍由科学 Worker 判断；不自动生成科学建议；Root 仍查看正式内容与控制状态。不能推广到所有 `RoleHandoff`：`CriticReview`（`cognitive.py:129`）和 `EvidenceAudit`（183）没有对应正式 summary，TCAD 完整 project 也没有通用正式结论字段，当前简短 handoff 有用途。

**兼容、回退与最低验收**

只处理新草稿/新封存结果，不改写旧 Artifact 或历史 signal；旧显式 envelope 继续可解析。最低验收：ScientificReview、TCAD review 和 gap 的新 draft 只写一份正式摘要即可通过；正式 payload 字节和结论保持；省略/错误的科学 verdict 仍被正确拒绝；Root 和下一角色读到同一结论；无正式摘要的角色不丢失信息。回退 finalizer 和提示即可恢复原输入要求。

## Finding 5 — P3：分析续接与报告说明在开发者提示和首读工作文件中原文重复

**分类：已证实的重复指令；属于小步瘦身机会，不是首要正确性问题。**

**准确位置**

- `plugins/curve_score/curve_score/analysis_workspace.py:26`、37：`REPORT_GUIDANCE`、`GUIDANCE`。
- 同文件 `_start_file`（157），172：`analysis-start.json` 再写完整 GUIDANCE；`materialize`（222），245—249：domain patch_contract 再写完整 REPORT_GUIDANCE。
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py:466`，`plugins/curve_score/curve_score/science_operations.py:778,881,882`：这些完整说明也组合进三个分析角色提示。
- `src/scidiscovery/platforms/codex.py:578`—585：生成配置又附加共同 lifecycle/backend 指令。TCAD author/reviewer 自身关于 Skill 路径、TMPDIR/cache、禁止越界的说明与 backend 块还有局部重复，但本项优先限定在完全相同的分析字符串。

**生产调用链与可达场景**

分析角色已在 developer prompt 接收两段说明；遵守“先读 analysis-start，再读 domain manifest/patch_contract”的入口协议时，同样内容再次进入读取结果。这与证据原文重读不同：重复的是稳定方法指令，不提供新的科学事实或本轮身份。

**影响与量化边界**

父代理独立的只读 AST/TOML 静态计量显示 GUIDANCE 为 1,302 UTF-8 字节，REPORT_GUIDANCE 为 804 字节；两个完整字符串均出现于三个当前生成分析角色提示。这里只证明静态重复，未证明实际模型 usage、缓存计费或每轮节省量。

**最小建议**

保留一个完整指令载体，另一处只保留本轮参数、明确 generated_fields/draft_may_omit、来源位置和短指针。首选在已确定角色提示包含全文的安装组合中删去首读文件的全文 guidance 重复，保留必要导航；跨插件公开 workspace 的使用者应检查其是否依赖该字段，再决定是否采用短 fallback。不要删除权限、恢复非证据、完整原件可读和机械字段归属这些规则，只消除同源原文的二次呈现。

**保持的不变量**

deadline、精确输入、恢复 coverage、原件位置、可省略字段与当前权限仍在任务入口可见；未知 input schema 仍保留索引；最终校验不增加隐藏规则。

**兼容、回退与最低验收**

不迁移或重写旧工作区。最低验收：三个分析角色各有一个可访问的完整说明载体；新首读视图不再重复同样整段 prose；新旧 workspace 均可按授权协议完成，未增加字段缺失拒绝。回退恢复展示字段即可。此项应在前四项之后，不能借“提示较长”删除有效领域约束。

## 其他候选的独立评价：机会、合理成本与尚未验证部分

### 通用设计/修订/审查缺少分析链已有的首读视图

事实成立：`general_science_components.py:415` 的普通 workspace 仅有 finalizer；`runs.py:1114` 在没有 materializer 时直接返回。其 assignment 输入列表（`run_assignment.py:44`）有 alias、port、description、media、exposure、historical，未提供分析入口中的逐项 schema/size、计划字段导航与摘录。大型 feedback 仍是 `on_demand`（`general_science_experiment_operations.py:35`—50），并没有被强制全文内联。

这适合列为 **P2 可测改进机会**，不是“所有通用角色每轮必须全文重读”的缺陷。最小步骤是把通用 assignment 的首读索引补全必要的 schema/size/port 用途和准确字段导航，沿用现有 workspace hook；可先只做索引，不复制大段摘录。不要让 general_science 反向依赖 curve_score 的分析 workspace，也不必创建通用摘要框架。验收应观察相关输入是否更容易定位、任务遗漏是否增加，并保持所有原件可读。对很小的 design intent，新增视图本身可能比节省的内容还多，需按真实输入分布衡量。

### required_observables 等物化复制是否应在默认阅读中重复

`experiment_intent.py:384,408` 把同一 required_observables 放入 ComparisonContract 与 ExperimentProposal。这是既有完整类型/消费者合同的结构重复，并不要求模型初次设计时写两遍；控制已经完成复制。分析 `_plan_index`（`analysis_workspace.py:126`，145—151）已按完全相同字符串去重展示，并保留全部 JSON pointers，这是合理做法。

可以在未来通用首读视图复用这种“逐字相同内容只展示一次、多个原位置全部保留”的原则。不能按语义相似度合并不同目标、条件或 observable，也不宜先删正式 Schema 字段：那会改变不同消费者的完整合同和历史兼容。没有证据把这件事排在 Root 全量 payload 或 handoff 信息缺口之前。

### 增量修订与控制生成变更位置

普通 copy-on-write 已避免重新生成完整对象；`run_assignment.py:149` 只给 base alias 和 editable target，没有控制生成的变更位置列表。修订开始时“新 revision 与 base”的变化尚未发生，控制不能代替科学 Worker 决定将要修改哪些字段。提交后的精确 JSON pointer diff 可以帮助下一位审查者导航，但只有两份精确对象都明确绑定时才成立。

TCAD 另有 `deck_project_diff`（`project_packager.py:936`），按文件/参数列出机械变化；其调用在 `transform_adapter.py:84`。不能仅看到此函数就宣称当前 reviewer 工作区一定拿到 diff：当前 `REVIEW_INPUTS`（`plugin.py:484`）与 `materialize_workspace` 没有稳定的 prior project/diff 输入和生成路径。因此建议先清理角色说明中的条件适用范围，再决定是否确有消费者需要把已有 diff 的位置显式交付；本次未把该未交付辅助视图定为正确性 blocker。

作为 **P3 待消费者验证机会**，可用已有两份精确绑定输出生成有界变更位置索引，未知结构退回完整阅读；不新建 diff Artifact/状态机、不根据相同文件名选择旧对象、不让 changed-fields 列表成为审查范围上限。独立审查者仍检查当前完整 subject 及关联影响，旧 review 不自动继承。若 prior 未绑定，继续检查当前完整对象就是正确行为。

### Root 目录与诊断的重复投影

`scientific_inventory`（`mcp_root_instance_routes.py:134`，172）每次附带完整 public catalog，而 `operation_catalog`（`mcp_root_operation_routes.py:69`）也可单独返回它。这是同一权威的重复展示，未发现第二注册表。没有当前目录变化时，调度者可复用已读目录条目并以新 preflight 做实时门禁；这可能无需改代码。未来若加入“只刷新对象”的查询选项，必须保留目录可得性和当前可用性校验。

`runs.py:927` 的 diagnostic_summary 还会在 latest_tool_error、recent_errors、latest_rejection/failure 重复某个错误正文，且每次状态查询重发最近窗口。现有分页已可完整追溯，后续可让摘要展示原因一次及计数/定位，详细历史按现有 cursor 读取。该收益次于 Finding 2，不能删除最近实际错误或仅剩不可解释错误码。

### 平台角色提示与可见工具

父代理静态统计的 25 个生成角色 developer prompt 范围为 6,219—20,042 UTF-8 字节：设计 11,119，修订 10,379，通用审查 9,312，TCAD 初作者 17,317，TCAD 审查 13,153，TCAD 分析 20,042。共享研究职责 1,743 字节、共享完整 preamble 3,269 字节。这些是角色协议/提示的静态大小，不等于实际模型 token；不能因为分析角色最大就把它排为第一问题。

Root 生成配置有 26 个 MCP server；每个角色自身配置只有一个 server。Root 可发现的 Worker server/工具数量并不能证明所有 Schema 都进入每次模型调用。`codex.py:443` 的禁止边界目前是可信本地原型所需提示，不应在平台未证明按角色隔离工具前删除。此处只有“可见性与实际 usage 待测”的风险，不能给 token 节省百分比，更不能用提示假装技术沙箱。

### 应保留的合理成本

- 精确 schema、输入 alias、ordered lineage、current/历史兼容和审批检查是执行与结论可审计的前提；不交给模型猜测，也不因重复字符而删除。
- 跨角色无共享聊天、不同 Operation 新 Agent、自审禁止，以及同角色新 Run 重新打开精确输入，都保护权限和独立性。可以记住读法，不能把记忆当证据。
- 独立 TCAD review 读完整当前源码是合理成本。diff 只辅助导航；通用 review 也必须有机会检查局部变动与全局目标、约束的关系。
- 原始有界日志保留、恢复清单、已完成数值文件和 current attestation 都有用途；正确瘦身对象是默认展示，不能为了省 token 销毁 evidence、把遗漏当无错误，或重用旧诊断证明。
- 输出 Schema 比模型直接编写的 draft 更完整可以成立，但机械 finalizer 字段必须提前可见。已有分析 patch_contract 是好的范例；无需为全文契约新增隐式校验或字数失败条件。

## 建议次序与验收边界

先处理 **F1 的下游信息可见性**，再处理 **F2 Root 的有界、按需读取**；随后分别做 F3 合同去重复、F4 正式摘要单写，最后再压缩 F5 稳定 prose。通用首读视图可以作为下一项小实验，先索引、后按真实任务验证是否需要摘录。每次改进只改变一个可回退的投影或字段归属，避免把五项打包成新的“交接系统”。

后续实现验收需要真实安装入口的正/负例，尤其是旧 workspace/historical 记录、复杂工具 `$defs`、失败诊断分页、同角色新 Run 与独立 reviewer。以上只是提出验收标准，本次没有运行这些检查，不宣称运行时通过或实际 token 已减少。
