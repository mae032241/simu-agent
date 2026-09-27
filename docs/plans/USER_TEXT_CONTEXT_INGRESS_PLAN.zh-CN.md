# 用户文本接入与研究节点续接计划 R2

日期：2026-09-14。状态：已按独立 R0/R1 审查修订，**待独立复审，尚未实施**。

依据：[R0 独立审查原文](reviews/USER_TEXT_CONTEXT_INGRESS_PLAN_R0_REVIEW_20260914.md)。该审查针对上一版“文本登记＋统一补齐 current_progress”的五点方案，结论 REVISE；本计划不改变其历史结论。

R1 [独立复审](reviews/USER_TEXT_CONTEXT_INGRESS_PLAN_R1_REVIEW_20260914.md)指出调度层重建输入时遗漏 producer_inputs。本版将 RunService.schedule 的同一投影补入 P2，保留其权威重建与再次预检；A4 覆盖实际 preflight → invoke 的有说明和无说明路径。[R1 送审原文](reviews/USER_TEXT_CONTEXT_INGRESS_PLAN_R1_REVIEWED_SNAPSHOT.zh-CN.md)保持不变。

## 1. 目标与范围

用户可以直接提供一段补充说明，指定从某个已有研究节点继续。Root 保存原文，按已编译的 Operation 绑定原节点、必要的历史记录和说明；科研 Agent 决定如何理解、采纳或处理。用户无需手写文件、输入内部标识、填写科研合同或先要求另一个 Agent 改写原话。

本功能交付的是“从历史节点创建一个明确绑定的新任务”，不回滚 current、不改写旧 Run 或成果、不自动执行后续全部环节。设计、分析和相应修订仍具有各自的职责与前提；用户补充不冒充独立审查、批准、仿真输出或已确认事实。

最小方案调整：新增一个文本登记工具；新增统一的可选 user_context 输入；保留现有 current_progress 声明及其容量。原方案将背景材料统一当作 evidence_inventory 的做法撤回，避免触发新的引用枚举和证据集合扩张。无需新增数据库表、研究状态机、科研实体 Schema、摘要 Agent、UI 编辑器或自动重算机制。

## 2. 职责与文档归属

| 所有者 | 本轮职责 | 不由其决定的内容 |
| --- | --- | --- |
| 用户 | 提供原始说明及希望继续的位置/方向 | 无需填写控制身份和引用清单 |
| Root 调度者 | 原文转交登记；从目录选择合适 Operation；显式绑定历史记录和说明 | 不把意见改写为科学成果，不伪造修订审查 |
| 控制层 | UTF-8 字节、来源标记、名称绑定、版本、输入投影与资源边界 | 不分类科学真假，不生成目标/结论，不决定是否采纳 |
| 科研 Agent | 判断用户信息的意义、证据力度、与旧计划的关系及可交付范围 | 不修改旧成果或把聊天当作执行审批 |
| 领域工具/执行器 | 沿现有合同实施被授权的动作 | 不因背景文字改变执行参数或权限 |

用户明确提出的任务要求应由相应角色处理；对事实主张的采信属于科学判断。对于职责或输入不足，Agent 可报告有限结果或缺口，不要求机械复述、逐条采纳证明或“覆盖全部用户意见”。

当前规范仍由 ARCHITECTURE.md/中文对应文件及科学设计宪章拥有。此文件只拥有待实施范围和验收条件；原 handoff 实现记录及已有审查保持。实施后仅同步受影响的规范段落。R0 报告按原文归档，索引指向 R2，不能把计划修订写成审查通过。

源码基线：HEAD 096a13fd89aacf2d4e73f77e87ab3174e5f89ec3 加当前既有工作树；已部署的 handoff 改进尚有未提交文件。实施前冻结涉及文件的当前摘要，不从 HEAD 覆盖这些改进。两份用户 Fig4 文档保持原样。

## 3. 对五项审查意见的处理

| R0 必改项 | R1 决定 |
| --- | --- |
| 可选 inventory 激活新引用枚举，连无说明调用也受影响 | user_context 使用现有 prior_signal 用途、opaque 文本和显式描述；不增加 evidence_inventory，不修改原引用枚举触发条件。无说明时原合法输出继续通过，包括 foundation 内已有来源键。 |
| 背景父记录被当作正式证据集合 | 保留完整父链，按生产 Run 已记录的端口绑定取得精确正式来源/审查对象；不从“所有父记录”推断证据集合。文本引用只证明引用了用户说明。 |
| current_progress 四项已满 | 独立 user_context 零到四项，不挤占旧槽位；明确字符/字节/总输入预算，见第 4 节。 |
| 改输入后错误使用 resume_from | 已完成节点建普通新 Run；失败工作增加说明走 draft_from；原样恢复才使用 resume_from，见第 7 节。 |
| 存储来源标签不等于 Worker 可见 | 在既有 assignment 的对应输入项投影简短来源标记和原文路径；分析入口保留同样导航，见第 6 节。 |

prior_signal 已用于可读的上下文/既往信号，未被当前 producer-family 收入 evidence_sources；这里复用其非资格用途，不新增 usage 枚举。新文本没有生产 Operation、审查 verdict 或批准身份；因此不会获得独立审查效力。下游角色能读取或引用说明，不代表它成为原论文证据。此选择须通过下面的完整链路测试，不能只按字段名称认定成立。

## 4. P1：文本登记入口

在 Root 的 ROOT_TOOLS 声明中新增 artifact_ingest_text，调用参数只有 name、text 和既有 on_conflict。name 由 Root 选择，用户只提供原话。固定媒体类型 text/plain; charset=utf-8，Schema 沿用 opaque；Artifact kind 使用通用 source_text。固定来源标签 source_origin=user_via_scheduler，creator 保留实际调用者身份，不伪造直接人工签名或审批。

工具将 text 原样编码存储：不 trim，不改换行，不转 Unicode 规范形式，不加说明前缀，不生成摘要。来源等机械信息位于元数据而非原文。复用 ArtifactService.register、当前实例语义名称、完整请求指纹、创建锁和 on_conflict 机制，不先在项目目录制造临时文本文件。

一致的输入上限：text 为 1—8,192 个有效 Unicode 码点，标准 JSON Schema 使用 minLength/maxLength 公开；最坏 UTF-8 大小为 32,768 字节。编码失败定位 text 字段。不得再添加比已公开字符限制更紧、却未公开的字节门槛。空白字符和末尾换行原样保存，不以 strip 后为空增加科学判断。边界测试包括中文、补充平面字符及 CRLF。

同名、同字节、同固定元数据为幂等请求；内容变化经 create_revision 建新记录，原记录保持可读。工具只登记并绑定当前实例，返回语义名称和既有绑定状态；不创建 Run、改变 current 或把“已登记”称作“已继续”。

生成 Codex Root 工具清单仍从 ROOT_TOOLS 派生；不建立第二份手写 enabled_tools。原 artifact_ingest_file 接口与行为保持。

## 5. P2：统一声明 user_context，保存引用和证据边界

### 5.1 端口与覆盖

共享声明助手在 OperationSpec 构造阶段显式添加 user_context：schema=opaque，codec=现有 opaque_codec，媒体为 text/plain 和 text/plain; charset=utf-8，usage=prior_signal，exposure=on_demand，min_items=0，max_items=4，max_item_bytes=32,768。codec/Schema 资源使用明确的 general_science 组件引用，避免在领域插件中解析到同名私有组件。只用于公开 Agent；Transform 和 Effect 不增加此端口。

当前覆盖基数为 25 个公开 Agent。通过 scientific_agent_operation 的调用者复用同一助手；TCAD 作者/审查及参数角色的直接构造器显式调用该助手。以实际编译目录逐项核对，不靠修改一个助手推断覆盖完成。已有 current_progress 端口保持原声明。

每个加入 user_context 的 Agent 将聚合 max_input_bytes 在原声明上增加 131,072 字节，为四条说明预留最坏容量；其他端口的逐项容量、基数以及输出/计算预算不变。四条既有 current_progress 加一条新说明必须可达。所有文件仍计入完整输入预算，on_demand 不表示免费容量。

超过文本长度、条数或总预算时，指出实际字段/端口和公开上限；不静默删除必要历史、不截断原文、不合并改写多条说明来绕过。Root 只显式续传仍相关的原说明，不能把整个历史自动累积到每轮。若用户要求同时保留的材料超过支持范围，应如实指出，不能宣称续接已经完成。

### 5.2 输出引用

不增加或收紧 evidence-source-enum 的触发条件。新端口自身不激活 inventory 引用枚举；已经激活枚举的角色，其允许来源仍由编译声明及实际绑定投影。

在已有 context_validator 的输出声明中增加可选 user_context 来源，使现有引用检查可以认识实际输入别名。没有 context_validator 的输出不新建检查器。附属二进制、工具收据等输出不增加人工引用任务。未绑定说明时不产生别名，不改变原合法来源集合；尤其保留 hypothesis 对 foundation 内来源键的既有支持。

这一步必须先核对现有上下文消费者：user_context 可用于说明引用，不允许被“其余全部 sources”隐式解释为参数原始来源或结构化科研对象。参数提取通过既有 ValidationSources.binding_descriptors 中的 port_name 取得 source_material 实际别名，正式 source_catalog 只接收这些别名；一般引用检查仍可认识用户说明。不得按别名前缀猜端口，也不新增另一份来源映射或改 context_validator 调用签名。原要求清单、数值和身份检查只读取自己的既有来源。无说明负控必须验证原 Schema/语义接受行为，不要求合同 digest 字节不变。

### 5.3 正式来源与完整父链

所有 Run 输入继续进入输出 parent_refs；不为了减少检查而删掉用户说明的来源关系，也不从 Artifact kind 或用户文字内容猜测其科学用途。

复用已存 RunInputBinding，为以下现有只读载体增加默认缺省的生产输入投影：InvocationArtifact 和 ProducerOutputFamily。字段 producer_inputs 为有序的（port_name, ArtifactRef）序列，未知为 None，已知空集合为空序列。由 Root 和 RunService.schedule 各自从与该输出精确对应的 completed Run 记录提取；不读取科学正文、不使用当前端口顺序重建旧输入、不持久化第二套记录，不把内部引用暴露给 Worker。

该投影只在这两个现有消费边界需要时构造，不增加 RunStatus 默认正文或全历史扫描。Root 与 RunService.schedule 权威重建处的 InvocationArtifact 构造均已有 completed_for_output 查询，分别复用已取得的 producer.inputs，保留同一已完成生产者及精确输出身份核对；调度层重新 preflight 的行为不变，不能只补 Root 或直接信任上游对象；ProducerOutputFamily 同样复用其已取得的 status.inputs，不为每条原说明另查历史。共享解析逻辑复用现有生产身份核对。投影与原输出身份/父链的一致性归控制层记录完整性；不让科学 Agent 填表证明。

定点替换以下“全部父节点就是正式来源”的推断：

- general_science_components._evidence_revision_cohort：从精确审查生产输入中的 source_material 取得原来源集，再与此次绑定来源比较。原 intake、审查、foundation、portfolio、critic 关联条件保持。
- parameter_operations 的资格 projector：从精确提取/审查生产输入分别取得要求清单、声明的原始来源和审查成员，保持原顺序/身份等价要求。user_context 仅保留在完整追溯中，不混入这些正式成员，也不变成审批新前提。
- parameter_operations.validate_extract_context：从已知正式端口别名确定 source_catalog 来源；引用用户说明的能力与登记参数来源的能力分开。
- _run_output_family 的 evidence_sources 现有用途筛选不扩大；user_context 的 prior_signal 不进入该集合。

历史生产 Run 存在时从其旧绑定读取；无法确认时，报告定位明确的历史元数据缺口，不把全部父记录当作来源回退。对原工具生成或 Transform 家族保持既有实现；不把它们改为接收用户文本。本轮不扩展普通 family 的含义或给所有消费者建立新的通用依赖图。

如果用户提供的是希望作为原始研究资料处理的文本，Root 可在合适的新任务中将同一原文绑定到该 Operation 已有 source_material/reference_material 端口。不得在同一 Run 重复绑定同一个 Artifact，也不得通过 user_context 自动升级其用途。是否支持科学主张仍由 Agent 判断。

## 6. P3：新 Agent 实际可读

run_assignment 在 user_context 对应输入项显示其现有别名、媒体、路径和固定范围的 source_origin。只投影这个来源标记，不传完整 labels、内部身份、hash 或 token。说明角色为“用户提供、Root 原文转交”；这不是经过独立验证的事实标签。

分析的 analysis-start.json 输入索引显示相同来源及原文路径；不因文本不能解析成 JSON 而遗漏它。短提示要求先查看本轮用户补充原文，再结合原任务判断。原文只存一份，compact entry 只导航，不生成第二份全文或科学摘要。其他角色通过原 assignment 输入索引读取相同文件。

共享角色上下文说明：用户信息可能表达要求、建议或事实主张，由该角色按职责判断；若改变了实现所需计划，应返回合适设计/修订环节。不得新增“必须复述用户意见”“必须逐条采纳”“必须证明已读”的提交规则。

对缺少新来源字段的旧 assignment 保持现状，不补造“用户提供”标签。Local 与 Hardened 均验证声明与可读文件一致；在实际选用的 Local 平台验证新 Agent 和同角色复用 Agent 的新 assignment 接手。

## 7. P4：从历史节点继续与失败恢复

Root 的调度提示加入统一使用说明，运行机制仍是既有工具组合：

1. 根据用户指定节点，通过 artifact_catalog 的精确父链恢复原目标及该 Operation 必需的相关记录。
2. 原文调用 artifact_ingest_text；给新任务绑定节点原件和 user_context。
3. 相同不可变请求 preflight 成功后 invoke，按返回的编译角色派发。
4. 读取封存成果和 signal，选择下一项工作；需要继续参考用户说明时绑定同一原记录。

单纯登记成功但后续预检未过，不算继续成功；原说明保留，错误定位到真实缺失条件。不会自动制造一份否决旧对象的审查。

普通设计可以绑定原计划及说明重新形成完整新计划，但仍需原目标、foundation、portfolio、critic 的匹配输入。专用修订仍需要其声明的 change_request；用户说明不能替代。整体目标或假设集合的改变超出某个修订入口时，选择实际支持的提出/设计入口，不能声称任意节点都能修改任意不变量。

完成节点：普通新 Run，旧输出作为正式输入。
失败节点：新输入或新合同下使用 draft_from，继续相同 Operation 的已验证草稿；草稿不成为科学证据。
原样恢复：只在输入与编译合同不变时使用 resume_from。
保留既有恢复预算、后端与来源检查，不自动增加尝试次数；历史草稿缺少所需保存信息时如实说明。

复用仍存活的 Agent 只限编译 agent_type 完全相同、空闲且不审查自己的成果；无论新建或复用，都先创建新 Run 并重新 open assignment。原记忆不替代新绑定。

## 8. 实施顺序与文件责任

实施前把本计划送独立复审；通过后才按下面顺序修改。当前仅修订文档。

| 步骤 | 生产文件/明确责任 | 完成依据 |
| --- | --- | --- |
| P0 范围冻结 | 记录下列文件当前摘要和 25 个 Agent 的原声明/有效输出样本；保留既有脏工作树 | 无说明接受基线、两条来源集合边界和一个满槽任务可复现 |
| P1 Root 文本 | interfaces/mcp_root.py、mcp_root_instance_routes.py、service/intake.py | 原文、名称绑定、幂等/新版本、公开长度边界和真实工具入口 |
| P2 共同输入声明 | operation_declaration.py；TCAD plugin.py、parameter_operations.py 的 Agent 构造处 | 25 个 Agent 的可选端口、容量、输出引用一致；零 Transform/Effect 新增 |
| P2 来源投影与消费 | operations/invoke.py 的既有数据载体；mcp_root_operation_routes.py；service/runs.py 的权威输入重建投影；general_science_components.py；parameter_operations.py | 不把背景当正式来源；源缺失/替换仍被原准入发现，完整父链仍可追溯 |
| P3 接手投影 | service/run_assignment.py、curve_score/analysis_workspace.py；共享角色提示 | 原文路径和来源可见，分析首读入口可达，旧 assignment 仍可读 |
| P4 调度/恢复 | roles/scheduler.md 的说明；复用 runs.py 既有行为，不改恢复算法 | 新输入 draft_from、原样 resume_from、普通历史节点新 Run 均正确 |
| P5 验证/文档 | 受影响的现有 operations 测试与少量有意义的新入口用例；双语 ARCHITECTURE 受影响段落 | 定向检查、一次隔离安装入口、独立实现审查及现场最小任务 |

计划中的生产修改预计集中在上述 12 个 Python 文件和 1 个角色文件；重复出现的 parameter_operations.py 只算一次。curve_score/science_operations.py、TCAD result_analysis.py、figure_science_operations.py 已通过共同声明入口的部分优先只验证；仅当其真实来源消费者需要显式端口分离时才定位一处最小修改，并在实施记录解释，不作顺手重构。

修改 callable 逻辑时按现有 ComponentSpec.configuration_identity 记录身份变化；不要假定 Python 函数体或共享助手自动进入全部编译摘要。声明/资源变化按现有编译器生成摘要，不增加第二套身份机制。禁止为了本功能统一 bump 全部 Operation.version。

若发现必须修改上述之外的持久化格式、资格策略或通用运行算法，先报告与本计划不符的边界并修订范围；不按“兼容”名义顺带扩张。

## 9. 定向验收矩阵

| 编号 | 实际行为与必要负控 |
| --- | --- |
| A1 原文登记 | 中文、换行、前后空白、补充平面字符逐字节保存；8,192 码点边界公开一致；超限/非法编码定位 text；同请求幂等，改文本新版本，重启后旧版可读 |
| A2 无说明兼容 | 原 hypothesis 输出引用 foundation 内合法来源键仍可提交；原 25 个声明正常编译，代表性的旧设计/审查/参数/分析无说明输入仍通过，原无效未知引用仍拒绝 |
| A3 新说明引用 | 同一原说明可通过编译 Schema、Worker 任务和既有引用检查；只补 user_context 不新增“所有输入必引用”之类要求 |
| A4 来源集合 | 参数提取有说明、仅审查有说明分别完成并进入正确后续资格路径；通过实际 Root preflight → invoke 调度路径分别验证无说明、仅 intake audit 有说明的 evidence revision 均能排队，正式来源集合不变；仅直接调用 guard 或入口预检不足以验收；缺少生产输入元数据定位报告，不回退全部父节点；说明不自动进入冻结来源，遗漏/替换原来源或匹配审查仍失败 |
| A5 满槽与预算 | 原四条 current_progress 加说明可用；原各端口能力不变；四条说明最坏 UTF-8 大小纳入总量；超界不截断、改写或静默挤掉历史 |
| A6 接手可见 | 新 assignment 和分析首读入口均给出原文位置与真实来源；没有来源标签的旧记录不被冒称用户信息；新 Agent/可复用 Agent 都读取新 assignment |
| A7 续接/历史 | 已完成历史节点＋说明创建新 Run；失败草稿＋说明使用 draft_from；原样 resume_from 可用、改变输入的 resume_from 仍拒绝；同版本旧封存对象及匹配审查保持可消费 |
| A8 安装边界 | 一个临时安装环境，经实际 wheel/stdio 入口展示新 Root Schema、生成 enabled_tools、编译端口、读取与提交；不用 source PYTHONPATH 冒充安装验证 |
| A9 职责边界 | 说明可被讨论、部分采纳或拒绝采纳，均不因“未落实用户建议”而被控制层拒绝；用户文字不能充当独立 change_request、UI 批准或直接修改已有执行参数 |
| A10 现场最小闭环 | 用户提供一条真实说明，绑定选定历史节点，新 Agent 完成有根据的设计/分析/审查；后续任务显式绑定同一说明并可读。记录正式结论、拒绝/错误及耗时，不为验收强行重跑 TCAD |

P0 选已有合法样本，新增测试只针对上述组合缺口，不复制每个角色相同的单元模板。公共端口覆盖采用目录矩阵，端到端重点放在 hypothesis、参数资格、intake revision 和分析接手。

所有测试串行、BLAS/OMP 单线程，使用现有有界运行器，进程树 RSS 上限 512 MiB；常规批次 150 秒，单次隔离构建/安装 300 秒。失败后先定位再重跑，不并行执行全量 suite。静态审查、定向测试、安装入口、真实 Agent 任务分别陈述，不以其中一种替代另一种。

## 10. 部署、回退与完成标准

部署前检查活动 Run：让已有任务在原合同下完成，或明确停止并确认草稿保存；不要让 queued/running Run 跨目录替换继续提交。更新控制端并重启加载新角色；本轮不改 VM runner。新合同改变 digest/agent_type 是预期结果，旧已封存成果不因同版本摘要变化而统一退役。

本轮回退只回到实施前冻结的代码/配置和既有部署事务；不删除新用户文本、旧研究记录或修改恢复状态。回退前同样处理新合同下活动任务。文本是 opaque 原始 Artifact，旧文件摄入与科研结果 Schema 不迁移。

完成必须同时具有：原文可追溯、角色可读可引用、无说明旧任务不退化、正确后续资格/修订可达、控制不代做科学判断，以及一次现场补充后继续任务的证据。不能以“工具能登记”或“全部端口出现”宣布功能完成。

仍不承诺自动从整个聊天提取信息、自动回滚任意节点、修改所有研究不变量、无条件恢复所有旧草稿或总体 token/时间下降。这些不通过新增审查、校验或通用状态机补足。
