# Agent 信息交接与按需读取修复计划 R1

日期：2026-09-14。状态：R1 已通过独立计划复审，获用户授权实施；尚未实施、尚未部署，不代表科学资格或 Fig4 进展。

依据：[独立信息交接审查](reviews/AGENT_HANDOFF_INFORMATION_REVIEW_20260914.zh-CN.md)、[R0 计划复审](reviews/AGENT_HANDOFF_PLAN_R0_REVIEW_20260914.zh-CN.md)、[R1 通过复审](reviews/AGENT_HANDOFF_PLAN_R1_REVIEW_20260914.zh-CN.md)。本轮只修复报告 F1—F5；不重建框架，不新增科学 Operation、摘要 Agent、状态机、通用检索系统或字数拒绝规则。

## 1. 目标、基线和文档归属

目标是让必要说明准确到达下游，并减少默认回复中的源码、日志、重复工具合同和重复摘要。完整记录继续保留，科学判断仍由对应 Worker 负责。

源码基线 HEAD：2d252a9b9d703919e47e7146b5c4c5c4e0dd8316。当前四个既有修改文件为 plugins/tcad_artifact/tcad_artifact/{operation_workspace.py,plugin.py,project_packager.py} 和 tests/operations/test_tcad_gap_continuation.py；另有两份用户工作中的 Fig4 文档。实施必须以当前文件内容为基线，保留这些修改，不能把整个脏工作树当成本轮增量。

| 文档/事实 | 本轮关系 |
| --- | --- |
| docs/ARCHITECTURE.md、中文对应文件、科学设计宪章 | 当前规范；计划通过不等于现状已改变，实施后只更新受影响段落 |
| ANALYSIS_HANDOFF_AND_REPORT_SIMPLIFICATION_PLAN.zh-CN.md 及其实施记录 | 保留已完成的分析入口、简版报告和恢复机制；本计划部分扩展相同做法到其他入口，不重做旧工作 |
| 本轮独立审查 | 固定于其 HEAD 加工作树的源码审查证据；归档原文，不回写成“修复后通过” |
| 本计划 | 已通过的 R1 实施计划；只拥有 F1—F5 的新修改范围、顺序和验收要求 |
| 已封存研究记录 | 不迁移、不改写、不复制为仓库中的研究 checkpoint；Fig4 保持暂停 |

## 2. 不变的边界

1. 输入准入继续由 preflight/invoke 负责；输出校验不重新审判输入资格。不给科学输出增加复述、登记、字数或覆盖全部目标的拒绝条件。
2. Artifact、旧 Run、旧 signal 和审批对象不原地修改；历史可读不表示获得当前资格。
3. Worker 生成科学结论、假设和限制；控制层只复制明确的机械字段、生成准确索引和读取投影。
4. 简式和选读结果必须明确标识，不能冒充完整 sealed_output。缺字段、未观测、内容未展开均不能投影成通过或无错误。
5. 作者说明是待审查主张；独立审查、当前源码对应的初始化证明和执行审批保留。
6. 查询和交接优化不改变四状态 Run 生命周期、恢复预算、执行同步/收集机制或 solver 行为。

## 3. P0：冻结修改范围与验收样本

实施前记录涉及文件的原始摘要与精确增量，使用现有定向测试中的合法项目、缺口和分析样本建立基线；不从生产状态目录或 Worker 私有目录取材料。

基线至少覆盖：一个完整 TCAD 项目、一个内含长日志的 implementation_gap、一份 ScientificReview、一份 TCAD review、一份简版分析，以及一个旧格式结果。记录各入口真实序列化回复的 UTF-8 字节数、机械正文是否出现和同一说明的出现位置。不要把字节数换算成实际 token，也不要从耗时推算阅读量。

比较选读效果时使用相同阅读任务，累计所有状态、导航及选读回复字节和工具往返次数，不能只比较最小的一条回复；对完整读取后备单独标明其成本。P0 只服务本轮比较，不新增长期观测系统、基准测试框架或并发测试任务。

## 4. P1 / F1：必要的初始化说明随正式项目交付

修改位置：

- plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md
- plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_reviewer.md

具体修改：

1. 作者把初始化探针与生产过程的对应关系、未测试的 case-reset 路径写入相关 solver 源码注释，作为项目源码的一部分封存；handoff 只给位置，不重复说明。
2. 说明必须在最后一次生成当前源码诊断证明之前写入。后续改动源码注释也属于源码变更，不能继续使用旧源码证明。
3. 审查者从收到的项目源码读取说明并独立核对源码与当前 attestation；作者声明不能替代实际步骤证据。
4. 当前完整项目无需新增字段、端口或附件类型。gap 已有正式 summary、affected_work、missing_inputs、suggested_resolution，不再要求把相同缺口仅写到 handoff。
5. 旧项目缺少此说明时，审查者依据现有输入判断影响；不加程序化“缺注释即拒绝”的新规则。

验收：通过真实受控输出封存及 review 工作区物化路径，证明一份说明只写一次即可在下游精确读到；下游不依赖 Root signal、作者聊天或旧工作目录；改变源码后旧诊断证明仍不能被用作当前证明。使用隔离测试样本，不运行真实 solver。

## 5. P2 / F2：run_status 保留兼容，支持省略和选读正文

主要修改位置：

- src/scidiscovery/artifact_agent/interfaces/mcp_root.py：RunStatusInput 和 RootTool 描述
- src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py：正文元数据、读取和响应投影
- roles/scheduler.md：Root 的轮询、诊断分页及完成后阅读要求

### 5.1 唯一新增查询参数

在现有 run_status 增加 output_paths：可选的 JSON Pointer 字符串列表，缺省为 null。以 sealed payload 为指针根，不是整个 Run 状态根。

| 调用 | 行为 |
| --- | --- |
| run_status(name=...)，不传 output_paths 或传 null | 保持现有完整返回行为，兼容已有调用者 |
| run_status(name=..., output_paths=[]) | 不读取/内联成果正文；返回现有状态、signal、精确绑定和结果元数据 |
| run_status(name=..., output_paths=["/summary", "/findings"]) | 读取同一个精确封存对象，仅返回所选子树及其原始指针 |

一个参数同时表达旧完整读取、正文省略和子树读取，避免新增多个互相冲突的开关或新工具。run_list、operation_invoke 与 run_record_failure 的旧调用行为不在本轮一并改造。

### 5.2 返回语义与有界读取

1. 未指定参数时，旧 sealed_output 和 scheduler_signal 结构保持兼容。
2. 指定参数时，以明确的 output_delivery 标识 omitted 或 selected。sealed_output 不装入裁剪后的伪完整对象；选读内容放在独立 selected_output 中，包含原 artifact_name、schema、原指针和逐项结果。
3. 原 sealed_output_status 的 available/historical/unavailable 继续描述原成果；正文没展开与成果不存在分别表达。只对 completed 且具有封存输出的 Run 读取科学正文；failed 的恢复草稿不进入该接口。
4. 每次最多请求 8 个指针，选读 values 的规范 JSON 累计上限为 32 KiB。复用已有 JSON Pointer 解析规则，支持转义键、数组索引以及合法 null 值；空指针表示根对象，仍受选读预算约束。
5. 不存在的路径返回明确 missing；超过选读预算的完整子树返回 omitted、原指针和子树大小，不截断公式或字符串、不返回伪造的部分科学值。此时附该子树的一层有界导航：最多 32 个直接子项的精确 pointer、类型和大小，以及剩余项数；只使用此次已解析的原对象，不递归建索引、不增加注册表。导航另限 8 KiB，键本身过长时省略完整条目并计数，不截断为错误指针。Root 不知道字段时可选读空指针获得完整小对象或大对象导航，再批量选择必要字段；导航不足时显式完整读取，不反复猜字段。output_paths=[] 仍不读取正文。无论省略还是超出选读预算，都不拒绝或修改科学 Run。
6. 元数据路径不能调用 artifacts.read 读取正文。子树选择本轮允许先解析已有有界完整 JSON，再选择返回字段；不宣称已经实现流式解析或降低峰值内存。
7. 保留精确绑定、null alias、历史来源和恢复字段；本轮不重新组织全部 Run 状态字段，也不重构恢复资格计算。错误摘要、分页及 diagnostic_read 继续可读，不删具体原因和字段位置。

### 5.3 Root 消费端同步

- 轮询及错误分页显式使用 output_paths=[]，不反复展开 completed 成果。
- Run completed 后，将 signal 与本轮需要的正式结论、限制、缺口、关键证据一起读取，再决定下一操作。不能只看 verdict；缺字段时根据对应输出类型读取相关子树或完整原件。
- 只有需要查看源码、日志或完整方案时才展开这些字段；继续使用准确 Artifact 名称和原指针，不生成新的科学摘要或新资格。
- Root 对函数返回值的本地筛选可以继续使用，但不能把它当作服务端已省略正文的验收证据。
- 仅修改 roles/scheduler.md 源文件；安装时重新生成 AGENTS.md，不手工修改生成配置。

验收：带明显大正文标记的合法项目与 gap，在省略正文的状态和诊断分页回复中不出现标记，且未发生正文读取；显式完整读取保留完整 payload；选读逐值对应原对象，覆盖 missing、null、转义键、数组索引和超预算；completed/historical 可读而 running/failed 不泄漏草稿；omitted/selected 下 scheduler_signal_status 由原封存结果及 signal 是否存在决定，不因正文未内联误报 unavailable；未知字段的大对象可从一次导航选到正式字段，无须整段源码或日志。已有旧调用和权限行为保持。

## 6. P3 / F3：Local 打开任务只给工具合同位置

修改位置：src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py；必要的消费说明位于 src/scidiscovery/platforms/codex.py。

具体修改：

1. 将合同位置返回条件从“存在分析 start_here”改为“当前不可变 assignment 已保存 tool_contracts”。返回现有 tool_contracts_path 和 tool_contracts_pointer；start_here 是独立的可选导航，不再控制合同是否内联。
2. 保留 assignment 中现有完整合同和编译来源，不建立第二份合同文件或解析协议。原型中模型可见接口不完整时，仍可在调用前读取对应工具的完整 inputSchema、局部 $defs、默认值和限制。
3. 阅读指导要求先提取 instruction、预算、输入索引和输出约定，不要求打印整个 assignment；实际使用某工具前读取该工具合同完整子树。
4. 旧 assignment 没有合同字段时保留既有冻结合同 fallback。若 assignment 损坏或旧合同不可恢复，保留真实工程诊断；不得用新目录合同替代旧 Run 合同。
5. Hardened 的内联合同路径保持原样，不借本轮增加其文件权限。

验收：普通设计、TCAD 作者、TCAD 审查、分析的新 Local open 均不内联工具 Schema；返回的指针能读取与当前 assignment 一致的完整合同；覆盖真实嵌套 $defs 的构参/调用入口；旧 workspace 和 Hardened 保持可用。查询合同不需要启动 solver。

## 7. P4 / F4：限定类型的正式摘要只写一次

适用类型仅为已有权威 summary 的 ScientificReview、DeckReviewReport 和 ImplementationGap。保留已完成的 LayeredDiagnosisReport 行为。CriticReview、EvidenceAudit、完整 DeckProject 等没有相同正式 summary 的类型不纳入。

主要修改位置：

- src/scidiscovery/artifact_agent/service/result_materialization.py
- src/scidiscovery/operation_declaration.py
- src/scidiscovery/general_science_experiment_components.py：已有 scientific_review_schema 资源的草稿/封存区别说明
- src/scidiscovery/general_science_components.py：为 result_finalizer 声明显式 configuration_identity，仅此一处；当前编译摘要不散列 callable 函数体，不能只依赖本轮提示同时变化
- plugins/tcad_artifact/tcad_artifact/operation_workspace.py
- TCAD author/reviewer 角色提示，以及 plugin.py 中受影响的契约说明和组件身份

具体修改：

1. 沿用现有 finalizer 机制，允许新草稿省略机械 handoff.summary/verdict，由正式结果生成短引用和已有 verdict 映射；只投影已存在的科学字段，不创造建议或推断新的结论。
2. ScientificReview 与 DeckReviewReport 的模板只要求填写正式 summary；移除第二个要求 Agent 改写的摘要占位符，保留独立审查结论本身的占位/待完成语义。
3. 新作者工作区的自动 handoff 模板省略 summary/verdict 两字段，保留其他已有字段，不再制造 null 占位；gap 分支在验证 RoleHandoff 之前补全机械字段，允许 gap 草稿没有 handoff 文件或省略这两个字段。验收必须从真实 materialize_workspace 创建的、未经 Worker 改动的 handoff 模板起步：作者只写正式 gap 即可提交。完整项目分支仍使用其现有 handoff 要求，缺少实际摘要仍不能提交；不能把 gap 的例外扩大到全部作者输出。旧草稿中显式 null 仍按错误类型报告，不静默清除旧内容。
4. 缺省与损坏分开：已有 handoff 文件的非法 JSON、错误类型仍返回原位置的具体错误，不能当作“省略”静默吞掉。
5. 为兼容旧格式，新草稿中显式提供的 handoff.summary 仍可读并保留；新提示不再要求它。既有 verdict 投影规则保持。assumptions、missing_inputs 等非本轮重复字段不删除、不自动覆盖；必要下游内容按 P1 放入正式可读位置。
6. 不全局放宽 RoleHandoff/RoleResultEnvelope 的封存 Schema。严格维持“作者草稿→finalizer 补齐→同一封存 Schema 校验”。通用审查在现有 scientific_review_schema 资源的描述中明确可省略的 envelope 字段及其正式来源，使编译后的 result.schema.json 可见；TCAD 在现有工作区 patch_contract 中列出 generated_fields/draft_may_omit。角色提示与实际 finalizer 保持一致，不新增 OutputPort 字段、通用工作区 materializer 或第二套草稿校验器。
7. 历史 Artifact 与 signal 不回写。新组件按既有编译身份机制更新；通用共享 result_finalizer 与 TCAD 相关 materializer/finalizer 均显式更新配置身份。验收只改变相应组件配置身份也会改变消费者的编译摘要，不能依赖同时改动的角色提示间接保护；旧 Run 不能被新 finalizer 重新封存。不新增函数源码摘要器。

验收：三个限定类型只写一份正式摘要即可走真实提交到 completed；正式科学内容不被 finalizer 改写；旧显式摘要仍可读；合法的其他 handoff 字段保留；非法正式 verdict/summary 仍有准确输出诊断；gap 缺省 handoff 可提交，但损坏 JSON 不被吞掉，完整项目缺省 handoff 不因此获得新例外；Root 与下游对同一正式内容引用一致。

## 8. P5 / F5：分析指导只保留一个完整载体

主要修改位置：plugins/curve_score/curve_score/science_operations.py、plugins/tcad_artifact/tcad_artifact/result_analysis.py。

选择保留现有工作区中的完整指导：analysis-start.json 的 GUIDANCE，以及 domain patch_contract 的 REPORT_GUIDANCE。移除三个分析角色 prompt 对这两段原文的重复拼接，替换为短导航。这样不改变公开 analysis workspace 的默认交付，也不影响其他使用该 workspace 的插件。

- 保留角色自身的科学职责、当前权限与生命周期说明，不借此全面重写提示词。
- generated_fields、draft_may_omit、完整工具合同位置、恢复非证据和原件可读的约定仍准确可达。
- 核对三个已注册分析 Operation 均实际绑定提供这些说明的 workspace，并覆盖真实生成提示和打开任务路径；若某个真实支持的组合没有该入口，保留它所需的原提示，不在该组合盲删。
- 旧工作区和旧编译角色不原地修改。续接的新 Run 使用新绑定、新工作区和匹配的新编译合同。

验收：通用分析、TCAD 分析、曲线误差诊断的当前有效阅读链各只有一个完整 GUIDANCE/REPORT_GUIDANCE 载体，入口可读且引用可解析；没有因此新增缺字段拒绝；旧冻结任务合同仍可辨认，正常新 Run 与失败续接都能获得必要说明。

## 9. 文件范围与实施顺序

| 顺序 | 责任范围 | 交付门槛 |
| --- | --- | --- |
| P0 | 精确基线及既有测试样本 | 记录改前入口行为，不污染生产状态 |
| P1 | 两个 TCAD 角色提示 | 必要说明随项目可读，当前证明不失真 |
| P2 | 两个 Root MCP 源文件及 scheduler 源提示 | 旧读取兼容，省略/选读正文真实生效 |
| P3 | Local Worker open 与平台阅读指导 | 完整合同按需可得，旧/Hardened 路径保留 |
| P4 | 通用和 TCAD finalizer、输出生成字段声明及角色模板 | 一份正式摘要可提交，其他角色与旧记录不退化 |
| P5 | 三个分析角色的两个 prompt 源文件 | 仅移除已确认的同源重复指导 |
| 收尾 | 相关测试、计划索引及架构中英文受影响段落 | 独立实现审查；明确源码/安装/真实验收状态 |

预期约 13—15 个生产/角色源文件，部分由多步共同修改；不是要求凑足文件数。project_packager.py 的科学模型、全局 RoleHandoff Schema、Run 存储格式、solver/runner、审批服务和曲线算法不在预计修改范围。若实际边界要求触及范围外模块，先记录具体缺口并修订计划，不顺手重构。

## 10. 定向验收、资源预算和失败追溯

复用 tests/operations 中现有 test_analysis_handoff_report.py、test_agent_contract_alignment.py、test_tcad_gap_continuation.py、test_l4_local_tcad.py、test_analysis_continuation.py、test_analysis_input_descriptors.py，以及所属 Root/Worker 入口用例。先确认已有用例归属；仅当现有文件不适合承载新增 Root 选读边界时，允许增加一个集中测试文件。

| 验收组 | 必须覆盖的实际边界 |
| --- | --- |
| A：信息完整性 | author 成果封存→review 物化，必要说明可读且不能替代当前执行证明 |
| B：Root 回复 | 旧完整、正文省略、子树选择、错误分页、historical、无输出状态、null alias |
| C：合同传递 | 四类 Local 角色打开任务、复杂合同解析、旧工作区 fallback、Hardened 不退化 |
| D：草稿到成果 | 三个限定 summary 类型、显式旧 handoff、损坏输入、无正式 summary 类型不误改 |
| E：分析与续接 | 三个分析 Operation 当前生成提示及工作区、恢复覆盖、旧合同、新 Run |
| F：集成 | 安装目录编译及隔离 wheel/stdio 入口；新增查询参数、提示、合同和 finalizer 来自同一候选 |

只做与增量有关的正例和必要负例，不跑全量测试，不用大量提示字符串断言代替生产边界验证。每批串行、BLAS/OMP 单线程，沿用现有受限测试方法，进程树内存目标不超过 512 MiB、单批 150 秒；确有独立编译/安装批次需要更长时单列原因，不能并发补跑或自动放大内存上限。记录峰值 RSS、退出码和超时；测试资源故障不记作科学失败。

记录每次失败的入口、具体诊断、修改原因和后续结果。已有失败与本轮回归分开。确认必要检查通过后停止扩张测试；不得为了所谓 token 验收重跑 TCAD。

## 11. 安装、回退与完成定义

- 本轮改变控制端代码、角色提示及工具查询合同。实施通过后需要常规重新安装、重启控制端并重新加载生成的角色/MCP 配置；不手工编辑生成的 AGENTS.md/.codex 配置。
- 不改 VM runner，正常情况下无需同步 solver 侧代码；部署命令在实现完成并确认最终增量后再给出。
- 旧 Artifact/Run/审批无存储迁移，旧默认查询行为保留。每步可回退其代码/提示投影；回退不删除已经封存的新结果。新旧编译身份不匹配必须诚实显示，不能承诺在旧 Worker 上续用新契约。
- 独立实现审查必须同时检查五项修复和它们之间的交接：尤其 F1 的内容可见性不能被 F4 的摘要自动补全重新丢掉；F3/P5 的短入口必须确实能找到完整合同与说明。
- 工程完成标准是隔离入口验证及独立实现审查通过，不以此声称真实 Fig4 科研闭环已完成。
- 用户继续研究后，再以一次正常的设计/作者/审查/分析交接记录实际读取和提交情况。平台有 input/output/cached token 时记录其原始计量；否则明确缺测，仅报告字节和往返次数。不得推算 token 节省百分比。

## 12. 明确留在本轮之外的候选

审查将以下列为可测机会或合理成本，并非本轮五项已证实问题；在此保留追踪，避免假称已经解决：

- 通用设计/审查首读任务视图：先观察 P2/P3 的效果，再决定是否补充 schema/size/字段导航；本轮不把 general_science 反向依赖 curve_score。
- required_observables 的正式类型复制：保留已有控制物化和分析视图逐字去重，不改历史完整 Schema。
- JSON/源码差异辅助审查：已有 copy-on-write 保留；没有两份精确绑定就不生成 diff，也不把差异当审查范围上限。
- Root 全部状态字段、恢复资格重复计算、catalog 重复投影和诊断摘要窗口：本轮不合并成一次大重构；必要信息与完整错误历史继续可读。
- 平台工具可见性和所有角色提示的大幅裁剪：没有实际注入/usage 证据，不凭静态工具数量扩大修改。

R1 修订针对独立 R0 复审：闭合默认作者模板→gap 提交路径；为已解析的大子树增加按需一层导航；明确省略正文时的 signal 状态；核对通用 finalizer 的间接实现身份。均沿用原入口，无新增科学校验。

执行前需审查本计划的范围、查询接口和兼容矩阵；通过后先提交当前源码及通过计划的 Git 检查点，再按 P0—P5 实施；本文件本身不构成实施已获通过的记录。
