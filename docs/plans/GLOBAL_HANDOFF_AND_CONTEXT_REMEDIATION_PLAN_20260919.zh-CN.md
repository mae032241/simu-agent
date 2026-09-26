# 全局交接、合同与上下文整改计划 R2

状态：[R2独立审查PASS（计划设计）](reviews/GLOBAL_HANDOFF_AND_CONTEXT_PLAN_R2_REVIEW_20260919.zh-CN.md)，无剩余P0/P1计划阻断；未实施、未验收，本轮只授权制定计划和审查。Fig4保持暂停。[R0审查](reviews/GLOBAL_HANDOFF_AND_CONTEXT_PLAN_R0_REVIEW_20260919.zh-CN.md)、[R0快照](reviews/GLOBAL_HANDOFF_AND_CONTEXT_PLAN_R0_SNAPSHOT_20260919.zh-CN.md)、[R1审查](reviews/GLOBAL_HANDOFF_AND_CONTEXT_PLAN_R1_REVIEW_20260919.zh-CN.md)和[R1快照](reviews/GLOBAL_HANDOFF_AND_CONTEXT_PLAN_R1_SNAPSHOT_20260919.zh-CN.md)保留。

## 1. 目标和基线

让Agent承担科学选择，让控制层承担已知材料的准确交接，让领域工具承担可恢复的实现诊断；以更少返工和上下文完成相同科学判断。不是只压返回字数，不移除有效的科学审查。

基线为HEAD `943c4626f8490530e9318eb9fbb409d2670908b9` 加当前工作区（检查时288项变动），不能把HEAD等同待改候选。实施前保存具体路径的diff/文件摘要及安装指纹；不得清理或覆盖无关工作。

本文件是全局整改唯一实施入口，吸收 [本轮问题计划](FIG4_HANDOFF_REMEDIATION_PLAN_20260919.zh-CN.md) 和 [Root必修待办](ROOT_REVIEW_CONTEXT_NEXT_FIX_20260919.zh-CN.md)。二者保留现场事实；[观测账本](evidence/fig4-handoff-context-20260919/OBSERVATIONS.zh-CN.md)、H验收及旧边界计划保留原候选口径，不据新代码重写历史。

本轮事实：Root约43.9k→152.2k，三轮计划审查thread峰值139.6k；算法/原表漏绑，设计先选择不存在的通用执行入口；三次开发预检错误被计六次，后续失败报告覆盖异常掩盖原诊断。作者已封存implementation_gap：三分支初始化成功但逐accepted-step守恒输出未实现，17案生产计算未执行。数值为已保存快照，不能视为所有未来流程的基准。

## 2. 职责与不变项

| 主体 | 负责 | 不负责 |
|---|---|---|
| Root | 选科学任务、成果和相关证据，决定分支/预算 | 搬哈希路径、逐个拼已知依赖、代写科学结果 |
| 科学Worker | 假设/方法/结论/科学依赖选择、明确能力缺口 | 注册控制身份、审批执行、伪造缺失证据 |
| 控制层 | 稳定来源映射、已登记依赖解析、冻结绑定、限量投影、唯一状态与诊断 | 猜科学相关性、从脚本文本猜依赖、按评分裁决机制 |
| 领域工具 | 源码材料化、开发诊断、求解和原始输出采集 | 授权自己、把初始化变成科学结论 |

输入准入在preflight/invoke一次完成；输出只校验输出与其明确引用关系，不重跑输入资格。父链可读不等于资格通过，背景依赖不能升级为可信证据或执行授权。不得新增固定DAG、常驻科学控制者、第二数据库/状态机、强制人工填表、通用执行器或TCAD专用核心分支。原目标对所有需用角色仍可访问，不能为省token删掉目标。

## 3. 工作包与顺序

### A. P0：预检、修订与诊断可恢复（先独立交付）

已定位：`plugins/tcad_artifact/tcad_artifact/operation_workspace.py` 的handoff初始化/读取、`_write`与失败报告分支；`plugin.py::_debug_tool`和`interfaces/mcp_local_worker.py`错误记录边界。复用 `service/result_materialization.py` 规范化能力，不建立TCAD专用第二套输出合同。

- 统一新建/恢复/修订模板与preflight/submit的合法结构。科学summary不可由控制层编造；缺少科学内容时明确是尚未填写，不能提供假完成结论。若开发预检无需handoff科学判断，消除该不必要前置依赖。
- 开发中的派生报告可以更新，旧尝试留存于现有诊断记录；已封存输入和结果保持不可变。修正连续失败写同名报告的路径，写报告失败也必须保留原错误。
- 一个错误事件一个权威记录方，保留tool、phase、field、原message；包装层不再补空的同名拒绝。开发预检、最终提交、求解器失败、超时、工程故障分类正确。
- raw_outputs合法字段从同一声明合同投影到模板/帮助/校验；先核查作者误用原因，不以放行未知字段解决。全局扫描同类“可改报告走不可变写入”和重复记录，仅修有生产调用者的同构缺陷。

验收A：失败A→失败B→成功在同Run能恢复；错误A/B均可追溯；新/恢复模板无隐藏要求；事件计数不重复；非法字段仍准确拒绝；输入篡改/符号链接防护不退化。通过真实插件入口及installed-wheel定向验证，负例命中真实边界。

### B. P0：确定性依赖交接与稳定引用（全局核心）

落点先核对 `service/tool_evidence.py` 的 ToolEvidenceManifest/ToolSourceBinding、`run_assignment.py`、Operation输入解析/不可变请求冻结、现有Artifact parents。核心只处理一般关系，领域算法不入核心。

1. Agent选取根成果与用途。控制层读取已登记的必要使用依赖，解析到精确原件；历史来源、实际被引用证据、可选背景、重算必需文件不能混为全量递归父链。
2. 先复用现有manifest的源绑定；存在不可表达的使用关系时，最小扩展现有manifest/Artifact元数据。系统工具保存源与产物时自动登记它已知的关系；Agent只声明控制层无法得知的科学选择。不得解析Python/报告自由文本猜关系，也不得扫描整个工作区补材料。
3. 派生依赖在invoke创建前确定，与根输入一起冻结并计入请求身份和预算；重复同名请求必须复用冻结集合，不能因后来新增材料而漂移。preflight与invoke消费同一解析结果，不能默认多做一遍preflight。
4. 沿现有声明端口/工具许可提供依赖，默认按需可读。若现有端口容纳不了，先明确最小合同改动及编译版本，不以隐藏附加文件绕开schema、用途、数量/字节或Worker权限。限量溢出返回精确缺口和可选缩小范围，不静默漏掉依赖、不截断合同、不自动转成超量全展开。
5. 源引用绑定其产生时的精确上下文；当前alias是投影，不是持久身份。跨Run输出使用已登记来源定位，控制层转换成新任务可用索引，不要求模型搬hash/ID。不可原地改写旧科学字节；历史无映射或歧义时保留原件及明确缺口，不能猜latest。新关系需要新不可变元数据或产物，不篡改历史parents。
6. 源摘要不替代原件；可访问不等于可信。自动附带只允许声明用途，不继承独立审查/资格，不自动满足审批。独立review获得相同必要原始证据，不只获得作者挑选的摘要。

验收B：以本轮分析→算法→765行原表做真实fixture，Root只选成果即可让下游定位原件；别名重排、同内容不同身份、缺失/循环/超限/越实例/失效资格分别测试；循环通过visited去重并报有界错误，不无限展开。恢复旧产物缺manifest仍可读、不会冒充已补齐。冻结请求重试不改变依赖；提交不再重新做输入资格。保留总体目标的可达性。

#### B首版合同（本包实施上限）

只实现“分析发布的复算材料→下一轮假设/设计/审查/作者”的已登记关系，不覆盖任意文件的隐式import/路径依赖。没有确切关系就返回缺口，不能从read_sources或全部parents生成必需集合。

| 项目 | 确定方案 |
|---|---|
| 关系载体 | 扩展现有ToolEvidenceManifest，新增可选、默认空的 `dependencies`；每条为 `subject`（primary或本manifest的工具产物alias）、`sources`（同manifest bindings/records中的来源alias）、`purpose=reproduce`。精确ArtifactRef仅在既有bindings/records中持有；不新建表/图数据库。manifest冻结时校验局部alias及关系边界。 |
| 登记入口 | 现有analysis文件发布/计算工具→`accept_tool_evidence`→`_evidence_snapshot/_evidence_manifest`。受控计算已知的输入/输出关系自动登记；自写脚本发布仅从现有发布请求所声明sources获得关系，若来源未声明则关系未知，不解析脚本推断。若现有发布sources仅代表宽泛来源，需以一个可选reproduce依赖选择作最小区分，Agent只选择材料，控制层解析身份。 |
| primary的关系 | 工具发布的复算材料组可显式归属于本Run primary结果；控制层记录这次发布组与其算法/数据关系，不能把全Run所有读取加入primary。未归属的文件不自动成为primary必需依赖。最终seal确保组内产物均已登记；声明关系不宣称科学有效。 |
| 当前链示例 | 新生成manifest声明primary→算法产物、算法产物→精确curve_tables_002；由受控发布的实际source列表和输出组证明。不修改已封存Fig4 manifest；旧历史fixture验证“缺关系可读但不能自动补齐”，新发布fixture才验证自动交接成功。 |
| 消费端口 | 在编译Operation上为允许的根端口声明一个 `dependency_target_port`，目标必须是已声明的 `usage=evidence_inventory` 端口；无该声明不展开。假设提出/批评/修订、实验设计/审查/修订、TCAD author首版使用current_progress；通用/TCAD结果分析使用reference_material。根端口仅限这些Operation的result_analysis/current_progress/prior_analysis/experiment_plan等明确选定成果，不给所有端口默认递归。 |
| 容量 | 首版自动依赖最多8个唯一Artifact、最多2跳；计入目标端口基数与既有Operation总字节。仅上述消费者current_progress的max_items由4定向增至12，以容纳最多4个显式进度项及8个依赖；单项字节和Operation总字节不增加。reference_material保持原上限，显式项占用后不足则报精确缺口，不挤掉输入。引用与材料索引按需可读，不全量注入。 |
| 去重/冲突 | 同一精确Artifact已在本Run合适用途端口可读时复用，不跨端口重复塞入；不同根共享依赖是去重，只有当前递归栈回边才是循环。重复字节但不同登记身份不合并。所需用途/权限与已有绑定冲突时明确报错，不能升级usage；补充材料不能替代必须的claim_evidence或审批cohort。 |
| 稳定引用 | 不新造Worker控制ID。新输出仍使用现有source_key/alias字段，解释域固定为其生产Run绑定；控制层实际身份为“源产物精确引用+生产alias”。assignment投影只给`原成果当前别名/原source_key → 本轮source_name`映射及可读路径。自由文本中的旧路径只是历史文字，不做自动替换，也不作为绑定权威。原件不改写，映射缺失/歧义明确显示。 |
| 冻结与重试 | Root路由先规范化显式请求并查同名已存调用。相同显式请求且compiled身份/配置一致时使用已存有效依赖集合；不同显式请求保留reject/create_revision规则。仅首次创建或显式新revision解析并把展开后绑定写进现有Run request/inputs和最终fingerprint；显式选择与解析版本保存在现有请求内容，不能靠内存缓存，不用后来关系重算旧同名请求。可选preflight仅返回规范化的显式根选择及配置，其依赖展开只作校验/预览；invoke正常准入时调用同一纯解析函数对精确不可变manifest重新求值，在Run创建时唯一冻结。普通JSON不得自称已验证展开集，不新增快照令牌或信任客户端派生绑定。preflight不创建/保留Run、不强制先调用；相同精确根/manifest和配置应给相同解析结果，若来源或资格已变化，invoke按实际状态给出准确诊断。 |
| 版本边界 | ToolEvidenceManifest新增字段采用显式v2并保留v1只读；OperationSpec新增可选消费策略需升编译ABI，策略参与digest，相关消费者Operation版本一起更新。没有策略的Operation行为不变。先列精确受影响注册项再实现，不要求新增历史合同解释器。 |

这是一项有边界的合同调整，不是零改动自动获知所有依赖。若首版链无法在上述范围实现，B保持未通过，不以隐式全附件或放宽schema代替。既有manifest v1与没有工具发布记录的产物继续沿显式绑定读取。

### C. P1：能力视图与科学可交付性

落点为编译Operation目录与执行能力投影、`general_science_agent_operations.py`/`general_science_experiment_operations.py`/`general_science_resources.py`、scheduler research/dispatch指引。复用当前注册信息，不新增能力白名单。

- 为所有有设计/实现/分析职责的任务投影短小的当前能力说明：新实验执行、已有结果计算、开发诊断的区别；model/权限配置沿现有快照，不混成科学合同。
- 区分已声明支持、仍需作者验证、当前未注册。静态编译可提供接口存在性，动态运行状态只能作带时点的事实；到实际执行仍按现有绑定/授权检查，不能把旧能力摘要当永久许可。
- 设计者给出可交付的方程、边界、输出及判断依据。具体语法/监视接口由作者做有界初始化验证；审查者不能要求计划先交出未来源码，也不能“通过但把关键科学定义丢给author”。
- implementation_gap沿现有产物/审查/修订路径回传；Root判断补输入、实现修订、科学重设计或停止，不增加固定路由状态。

验收C：相同Fig4能力视图不再承诺未注册一维执行；只需分析的动作不会被迫走TCAD；初始化失败不成为机制反证；gap可被审查读取，未完成项目不能打包执行。能力变化/旧Run恢复不静默改写冻结输入。

### D. P1：进入模型前裁剪（Root与所有Worker）

落点为Root MCP run_status/catalog/describe/invoke投影、`service/input_reader.py`、`interfaces/mcp_local_worker.py`、`platforms/codex.py`及公共角色指引。不按Fig4/某角色名写分支。

- Root只取任务决策所需正式内容与状态/限制/矛盾/下一步理由；精确请求与绑定留在编排存储。保留可访问的完整合同，已读合同未变不重读，按schema选择字段不猜另一个报告的路径。
- 合并或按需隐藏重复signal/摘要与机械元数据，不用LLM再摘要。错误、遗漏、分页和原件入口完整保留；summary与detail仍表示同一事实，不新设“轻量状态权威”。
- 单页预算之外明确一次工具/编排输出的累计边界；注册MCP响应由服务端约束。宿主functions.exec和native shell由模型控制，框架无法宣称硬封顶：公共指引要求分批、定位、选读；超量内容留在工作区并给导航，不一次循环读尽再print。不得破坏图像、完整合同或错误可见性。
- 审计compact intent→materialized plan、formal summary→handoff→status的重复表达。先删机械投影和冗余重复，再考虑schema变化；科学方程/验证阈值/结论局限保留单一权威并可访问。每项裁剪列明真正消费者和放弃的旧行为。
- 同Worker接续只重读新任务/变化材料/缺失上下文；上下文保留不能靠hash证明。独立审查不可复用作者。换Worker须原件和目标自足；本轮不引入自动token阈值调度或常驻记忆。

验收D：逐请求测初始输入、每节点增量与峰值；分别报告Root/各Worker、缓存累计与新增内容。单独量化机械响应缩减；原生模型整条交接至少两组同模型同预算配对样本，列波动，不从单样本断言稳定收益。科学分支选择、异常定位、原件访问不退化。

### E. P2：全局一致性扫描、兼容及真实验收

建立有界覆盖表：所有public Agent Operation、Transform生产者、Effect/Approval相关读视图，以及root/worker/CLI/UI/历史恢复投影。按共同实现分组，不为每个Operation复制测试。重点查模板→schema→执行校验→错误反馈是否同源、来源定位是否跨Run稳定、派生报告生命周期、响应重复。

扫描只能删除没有生产用途的重复字段/校验；身份、不可变性、来源、授权、权限与独立审查保留。发现科学判断混入机械规则时移交角色，不另造软硬校验状态机。历史兼容不通过放松所有输入/资格解决。

范围外：浏览器重设计、翻译、通用执行器、全面TCAD物理扩展、全文历史迁移、无依据的测试删减、重写Codex原生循环。

## 4. 合同与部署策略

既有合同仅新增展示或可选导航时不强制升级历史对象；改变输入解析/来源语义/冻结身份按现有版本机制区分。当前 `runs.py::_compiled` 只加载当前目录且严格核对version/digest，本计划不增加多版本执行器。

| 对象状态 | 部署/回滚行为 |
|---|---|
| 已完成旧Run | 字节/身份不变，历史可读；能否作为新任务输入按兼容schema和用途/资格判定，不继承旧审批。 |
| 排队、运行、待恢复旧Run | 当前完整编译身份匹配才允许继续；不匹配明确拒绝原Run续接。升级前完成任务或保持暂停，不隐式迁移。 |
| 新任务/显式迁移 | 新版本重新准入、冻结来源；复用历史草稿/结果按现有新Run机制，不自动沿用旧执行授权。 |
| 回滚旧安装 | 保留CAS/数据库证据；仅承诺旧代码可读其支持的schema。B产生manifest v2后，旧版是否能读/恢复须单列，不兼容则暂停相关运行；不能声称所有新产物都可由旧代码消费。 |

源码、wheel、控制服务和生成角色配置须一致验证；VM只有runner接口实际改动才需同步。逐包列Operation/schema迁移及回滚限制，并测digest漂移续接拒绝负例，不放松身份门。

## 5. 具体验收路径与放行条件

先保存生产trace的metadata基线、当前源/安装文件指纹及确定的回放输入。Root的43.9k历史起点不能与新干净进程的21.7k直接比优化收益。

| 路径 | 验证重点 | 不做什么 |
|---|---|---|
| 分析→新假设→独立批评 | 目标/结果/算法依赖准确传递，负结果范围保留 | 不重算旧六案 |
| 假设/计划修订→同reviewer复审 | 新材料可读，未变材料不机械重读，独立性保留 | 不要求模型申报已读登记 |
| 计划→author→连续失败预检→成功/明确gap | 模板一致、错误可纠正、记录不重复，gap能交接 | 不把缺口输出伪装执行就绪 |
| 未绑定/越权限/未审批/不可用后端 | 错误发生在对应动作，消息具体 | 不让模型改科学文字绕过权限 |

工程测试采用现有定向测试：`test_input_reader.py`、`test_run_status_output_selection.py`、`test_continuation_input_guidance.py`、`test_analysis_continuation.py`、`test_tcad_gap_continuation.py`及实际TCAD插件workspace/debug测试；新增只覆盖缺陷反例，不镜像实现。串行使用现有768MiB进程树守卫；它不能约束原生模型服务，超过本机预算的原生探针交用户执行。不跑全量套件。

确切TCAD测试落点包括 `test_l4_local_tcad.py`、`test_contract_attempts.py`、`test_tcad_initialization_outputs.py`、`test_log_preservation.py`；安装入口为 `test_catalog_installed_entrypoint.py`、`test_unified_mcp.py`，幂等解析为 `test_invoke_preflight.py`。按变更选择其中相关用例，不全部重跑。

每对原生验收预登记：源文件摘要/安装指纹、模型/effort、预算、精确输入集合、期望科学决策范围、起点（身份确认后首次assignment请求）与终点（正式结果封存且Root一次必要读取）。Root另做等历史背景的冷启动对照；用户插话、监控维护和人工修复单列。发生compaction/重启则分段报告初值/末值/峰值/请求数，不能把跨压缩净差当新增工具token。固定可控响应字节与原生净窗口增量分别计量；两组差异小于波动只能说未证明收益。功能项逐项列pass/fail/未验收，不能用平均token改善抵消漏绑或丢诊断。

每包：实现前反例→定向测试→真实安装入口检查→短原生交接→独立实现复审。先测固定机械响应，再测Agent行为，任何真实流程退化不得用工程测试通过掩盖。没有数据的项标未验收。预期方向是Root交接增量减少、无超量截断、依赖漏绑和重复事件为零；不预设无依据的节省百分比。

完成A-E后由用户决定恢复Fig4。先核查作者现有源码和初始化证据，再由科学角色判断逐accepted-step要求能否换成有依据的等价守恒验证，独立审查后继续现有TCAD链。本计划不授权降低科学要求或绕过审批。

## 6. 独立审查问题

审查需回答：问题归因是否有事实依据；依赖关系能否在现有端口/预算/权限和版本下落地；稳定引用是否泄露控制身份或继承资格；响应裁剪是否丢失决策证据；阶段/测试/回滚是否具体；是否引入比原问题更大的复杂度。指出P0/P1阻断并给最小修订，不替计划作者实现源码。
