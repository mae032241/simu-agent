# Operation 与工具契约一致性修复计划

状态：R4，待独立复审工程提案，2026-09-11。仅修订计划，未实施。沿用“Operation 声明及其引用模型是唯一来源，一次编译，所有入口按职责复用”的主线，按 [R3 独立审查](reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_REVIEW_R3.zh-CN.md) 补清静态合同、摘要和对外身份的无环生成顺序，并收窄动态批准措辞。保留 R2 已审查的接口决定与验收以及 R3 的 C1 消费接线、重复实现删除要求。[R2 独立审查 PASS](reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_REVIEW_R2.zh-CN.md) 仅适用于 [R2 原文](reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_R2_REVIEWED_SNAPSHOT.zh-CN.md)，不自动适用于新版本；[R0 原文](reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_R0_REVIEWED_SNAPSHOT.zh-CN.md)、[R1 原文](reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_R1_REVIEWED_SNAPSHOT.zh-CN.md)、[R3 原文](reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_R3_REVIEWED_SNAPSHOT.zh-CN.md) 及各轮审查保留。计划通过不代表授权实施或科研验收完成。

## 1. 目标、范围与决策归属

目标：所有已安装工具和 Operation 遵守同一套接口、校验、诊断和证据交接原则；让当前 TCAD 案例在已有执行产物上完成真实计算、封存和下一轮交接。修复可重复发生的机制问题，不以增加必填字段、强制科研阶段或放宽证据完整性代替。

**第一准则：一个要求只能有一个声明来源；输入准入只检查输入，输出校验只检查输出及其声称与冻结证据的关系。** OperationSpec 引用模型与窄组件，编译器解析并冻结它们；目录、MCP、Worker 合同、提交、重放和诊断消费同一来源的对应部分。禁止各入口补写另一套字段、前置条件或科学状态传播规则。

当前不是没有编译目录，而是编译闭包尚未覆盖实际执行的全部接口要求。只增加共享 helper、仍保留旧手写 Schema/分支/提示要求，不算完成。必须先完成 C1 的契约归属和消费者接线，再将 P1—P4 的已确认缺陷作为这条主线的具体迁移项。

问题依据：[本次完整根因核查](reviews/TCAD_ANALYSIS_3_BLOCKER_ROOT_CAUSE.zh-CN.md)。首个评分错误是轴参数对象被写成字符串，并被误报为 PLX 格式不支持；比较结构同样错误。产物恢复没有补齐可表达的案例映射，固定层级规则又造成连续输出返工。不能据此先扩写 parser 或重跑 solver。

| 文档 | 归属与处置 |
|---|---|
| 本计划 | 契约一致性修复的活动提案；实施后以精确执行记录标记完成范围 |
| 当前架构、设计宪章、33 项约束 | 继续拥有规范性原则；实施时仅更新受影响条款及中英对应段落 |
| 输入校验阶段修复计划 | 保留 preflight、输出校验、完整性故障分离的既有决定；本计划将工具与消费者接入同一编译来源 |
| 分析内评分计划 | 保留可选评分和无实验前评分门槛；本计划收敛请求类型与错误处理 |
| 受控补收集计划 | 保留字节保全与不可变来源；本计划修正“案例只能来自旧声明”的不完整交接 |
| 既有 PASS、失败和本地验收记录 | 历史证据，原文保留；不追改为此次结果，不继承资格 |

**全局覆盖不等于统一权限或全量重写。** 盘点覆盖 Root 工具、生命周期工具、Local/Hardened Worker 工具及 public/support/internal 的 Agent、Transform、Approval、Effect；共有问题在共有入口修一次，领域差异由插件拥有。文档中的盘点表是工程审计记录，不成为第二运行注册表。

## 2. 必须保持的职责边界

| 边界 | 允许的检查 | 不允许的越界 |
|---|---|---|
| Operation preflight/invoke | exact binding、输入结构与用途、独立审查、预算、当前资格、执行授权 | 要求仅后续分析使用的资料先齐备；为允许有限分析而放开执行门 |
| 工具调用 | 调用参数、已绑定别名与范围、工具权限、I/O 预算、必要的副作用条件 | 把参数写错说成科学缺口；把计算工具不可用升级为所有任务不可提交 |
| 工具结果 | 返回结构、机械计算与明确的成功/失败语义 | 接口调用成功就代表求解器成功、科学成功或独立审查通过 |
| 输出提交 | 输出形状、引用、输出声称与冻结证据的关系、计算记录完整性 | 重新运行输入准入、查询最新资格或重新连接 VM；因诚实报告输入缺口而拒绝报告 |
| 完整性与执行 | 字节/实例/执行来源、权限、精确批准、幂等性 | 用宽松分析规则恢复旧执行资格或允许越权工具 |
| 科学分析/审查 | 可执行目标、局部结论、证据充分性、方法等价性及争议 | 程序根据固定全局顺序替 Agent 选择目标、映射或科学判断 |

输出引用案例与绑定证据不一致，可以拒绝该输出声明；缺案例信息的有限分析仍须可提交。读取冻结输入进行输出对照不属于重新准入。预检后被破坏的输入、校验器异常分别进入现有 integrity_failure/checker_failure/admission_defect 工程故障路径，不要求 Agent 改写科学报告。

## 3. 最小改动约束

- 复用 OperationSpec、CompiledOperation/CompiledCatalog、WorkerToolDefinition.input_model、InputValidationSpec、Run 活动记录、CalculationRecord、AnalysisSourceReference 和现有工具证据清单。补齐当前编译闭包，不另建 ContractSpec、工具注册中心、规则 DSL、依赖解析平台或持久化合同库。
- 不增加 Operation 注册表、任务生命周期、统一依赖图、自动科学路由、万能修复角色、评分独立阶段、默认新审批或远程执行能力。
- 不给所有角色开放所有工具；统一的是契约和诊断规则，权限继续按各 Operation 编译。
- 公共核心不得认识 PLX、TCAD 案例名或评分算子；格式、科学映射、比较请求由对应插件拥有。
- 不重构 VM runner、COMSOL、部署目录或审批页面；本次原则上只更新本地服务/Worker 包与生成配置。若实际变更触及远程协议，必须先明确记录范围，不能顺手扩展。
- 不新建通用工具成功返回大信封或一套通用结果状态机。保留现有成功返回与 OperationInvocationError 等协议，只为错误增加共享的有界结构化详情；固定工具结果需要验证时从其现有模型生成。
- 本次禁止全面迁移科学 Schema 或删除历史字段。现有结构优先保留；改变语义后记录受影响 Operation digest，旧资格不继承。

## 4. P0 与 C1：冻结基线，补齐唯一编译契约

### 4.1 P0：基线与职责盘点

1. 以实施开始时的完整工作树为基线保存文件清单、摘要和精确增量；不把 HEAD 以来所有已有修改算成本计划。
2. 从默认插件组合与含 figure 插件组合编译目录，枚举每个工具/Operation、输入模型、输出 Schema、输入检查器、输出检查器、上下文检查器、权限及生产调用路径。Root/lifecycle 工具从现有声明获取；不通过字符串搜索推断运行目录。
3. 逐个注册检查器标注其职责与实际消费的输入；重点核对：可选变必需、宽泛异常转换、输出阶段重准入、工具任意字典掩盖固定结构、跨角色交接缺口、固定科学状态传播。相同组件只审一次，记录所有消费者。
4. 将每项分为“符合”“本计划修复”“需单独有界处理”。必须列明位置、触发条件、受影响动作和保留的不变量；未检查不能写成符合。没有调用证据的问题不纳入源码改动。
5. 冻结当前 TCAD 真实案例的 exact inputs、受控恢复成果及调用错误见证；科学记录通过 Root/受控 Worker 使用，不能把工程测试脚本变成科学结果生产者。

P0 交付：在 `docs/plans/evidence/operation-tool-contract-coherence/` 保存 BASELINE、CONTRACT_INVENTORY 和实际修改清单。每条记录增加“唯一声明/实现、编译投影、实际消费者、待删除副本、正负见证”；记录仅用于审计，不由运行时读取。公共修复覆盖的调用方必须齐全；新发现但未修的同类违约必须显式列入限制，不能宣称“全部一致”。纯 Python 语义不能靠编译器自动证明，必须人工工程审查。

### 4.2 C1：声明所有权与编译产物

| 要求 | 唯一来源及编译方式 | 消费范围 |
|---|---|---|
| Operation 端口、基数、用途、输入组合与准入 | 现有 InputPortSpec、InputAdmissionSpec、InputValidationSpec；解析现有组件引用，不再复制 required/optional 表 | 目录、preflight/invoke；Worker 仅获得输入合同说明，submit 不执行准入 |
| 工具字段、类型、枚举、默认值、固定返回结构 | WorkerToolDefinition.input_model 及工具现有结果模型；生成可见 Schema、参数验证入口和合法示例 | tools/list、真实 tools/call、Local/Hardened、工具实现；结果检查属于工具完成边界 |
| 输出形状和窄语义规则 | OutputPortSpec 的 schema_resource、semantic_contract、validator/context_validator 和 rule_id；基础 Schema/规则说明一次解析 | Worker 结果合同、submit、历史记录的适用读取/重放；不得重新解析 prose 得出新规则 |
| 工具权限、服务、网络、预算、证据能力 | 现有 executor/tools、permission_template、limits、工具声明；本计划只增加已明确的 record_attempts 开关 | 生成配置、派发、工具调用与执行；默认权限不增加 |
| 来源、清单用途、案例映射、计算与失败记录 | P1/P3/P4 的现有记录模型及单一解析组件；Operation 通过既有组件引用和输入/输出端口声明使用 | preflight 只核对绑定，工具处理请求，submit/重放核对输出引用；复用解析事实，不复用跨阶段拒绝条件 |
| 字段诊断 | 共享安全诊断模型；模型错误定位或已声明 rule_id/phase 的窄语义错误 | MCP 错误、业务拒绝、活动记录、受控失败证明；错误传输不改写原因 |

机械可表达的字段要求归类型模型；不能由 JSON Schema 表达的条件归现有声明的单一 checker，并由同一 SemanticRuleSpec/InputValidationSpec 提供可见说明。不要新增通用条件语言，也不要声称自动生成或证明任意科学算法。编译器检查引用/阶段/路径/输入范围等可确定关系；人工审查和行为测试核对窄 checker 与说明是否一致。

具体落点：

1. `operations/catalog.py` 在现有 compile_catalog 路径中解析工具定义、输出基础 Schema 和语义合同一次；复用 `CompiledOperation` 的 spec、implementations、permission_template，只补存当前缺少的只读工具解析结果和按输出端口索引的基础合同投影。共享工具按既有组件身份在本次目录构建内复用；不添加跨目录全局可变缓存。若现有字段已足够，就直接引用，不再保存第二份 required/permission/rule 表。
2. `operation_contract.py` 保留现有公开投影函数，改为读取编译产物。Run 实际别名、已接收工具证据和修订形状等动态值，仍由同一个投影函数对本 Run 的冻结描述符实例化；不能把别名或当前 Artifact/批准状态缓存为启动期常量。候选冻结后，Worker 可见输出 Schema 与提交使用的对应投影必须一致。
3. `operations/tooling.py` 保留现有查询函数，读取已解析的工具合同；Local/Hardened 只选择已声明 handler 和原生工具适配。`mcp_worker_protocol.py`、Root/Local/Hardened 路由复用同一模型解析与安全错误转换，不再分别定义字段校验或吞掉错误位置。Root 工具仍以现有 RootTool 声明为唯一参数来源，生命周期仍以 operations/lifecycle.py 为来源；启动时用同一投影/验证适配器处理，不把管理工具伪装为科研 Operation。
4. 固定无环顺序：先从声明和已解析组件构造**不含自身 operation_digest 的静态工具参数 Schema、合同材料及相关声明能力**；将其纳入现有 Operation digest 封套计算唯一摘要；最后把该身份注入只读对外合同与配置。现有 reviewer/provider 等有向依赖身份继续按目录原顺序计算，不以排除自身摘要为由删除这些依赖。对外身份只是静态材料的派生元数据，不反向参与自身摘要，不用临时摘要填充完整投影再反复回算；Run 别名、当前证据和批准状态不进入该启动期摘要。已有资源/组件身份已覆盖的部分不另立摘要权威。保证同一模型字段或权限声明变化会改变受影响目录身份、Worker 配置及合同。任意 Python 实现及其传递依赖不假装可自动证明：窄组件的语义变更沿用现有组件/插件协议版本与资源身份管理，并核对安装包；不另造源码递归哈希器。
5. `operation_declaration.py` 与插件 schema/operation 声明只引用一次模型/规则。机器约束段由合同生成；手写角色说明保留目标、方法与判断职责，不复制参数结构或额外前置条件。示例由同一模型验证，防止描述鼓励无法调用的请求。

“一次编译”指每次构建目录时确定规则及其实现引用。进程重启或包升级会重新编译；每次调用仍在所属动作检查实际参数、精确来源、预算与权限，preflight/invoke/execution_start 的现有动态授权要求保留。一次预检不缓存永久执行许可，submit 也不借此接回输入准入。阶段分离由调用路径和其可见上下文落实，不新增万能 validate(stage) 调度器。

### 4.3 C1：消费者迁移与必须删除的重复逻辑

| 现有位置 | 改为消费什么 | 必须删除或停止执行什么 |
|---|---|---|
| catalog/tooling、platforms/codex.py 生成配置、Worker tool facade | 同一编译端口、模型和能力投影 | 重复解析的工具定义、手写工具参数/权限列表；适配器不能补条件 |
| operations/invoke.py、input_validation.py、Root operation routes | 编译输入声明与既有统一准入结果 | 不新增第二准入入口；路由不得另按 operation 名补参数要求 |
| run_assignment.py、operation_contract.py、service/run_outputs.py、service/runs.py | 同一输出基础合同及冻结 Run 投影、声明的输出 checker | Worker 专用/submit 专用的规则副本；提交时调用输入准入；可见可选而执行必需的隐藏要求 |
| curve_score/analysis_tool.py、tcad_artifact/result_analysis.py | P2 生成的输入模型、C1 的调用边界和 P1 诊断 | 手工 allowed-key/轴类型副本；宽泛参数异常转格式 unsupported |
| tool context、tool_evidence、分析上下文和重放 | §7.2 单一清单用途/身份解析、§7.1 单一领域案例解析、§8.1 尝试证明 | 每处各写一份清单选择/案例来源规则；把接收 metadata 当可改映射 |
| 三个分析 Operation 的 Schema、提示与 checker | §8 的各自能力投影与同一个实际完成检查覆盖函数 | 全局层级强制传播；错误的 evidence.source_key 输入别名枚举；把计划覆盖当实际通过 |

移除副本指消除多份可编辑的规则实现，不禁止不同边界调用同一规则检查不同请求。保留输入/输出各自必要的来源核对，但共享解析事实。例如，preflight 核对旧清单配对；submit 核对报告所指 attempt 是否来自该冻结清单，不能在 submit 重新判定该旧输入今天是否准入。

迁移按“声明/模型 → 编译产物 → 全部消费者 → 删除副本 → 正负验证”完成一个行为切片后再进行下一项。C1 先打通现有合同读取和共享入口；P1—P4 随各切片补齐其已确定的模型与规则。不得先新增所有抽象，再留下旧路径等待未来迁移。

### 4.4 C1 退出条件与防回归见证

- 实際消费链均能回溯唯一声明/窄实现；测试和审计记录不得成为生产规则来源。P0 发现的每处副本必须有删除证据或保留理由与适用范围。
- 在现有目录/入口测试加入小型声明变更见证：只改一个工具字段类型或枚举，重新编译后 tools/list、正式 tools/call、两种 Worker 投影与生成身份一起变化；不能再改四份 fixture 才能通过。用有强制/coercion 风险的负例核对可见 JSON Schema 与实际模型接受集合，不能只比较两个 Schema 文本。
- 只改一个端口基数或既有组合声明，目录与 preflight/invoke 同步变化；输出提交不因此重新触发输入准入。只改一个输出结构/声明规则，Worker 合同与 submit 同步变化；声明为可选的进展材料缺失时，诚实有限输出可提交。
- 相同静态声明重复构建得到相同身份，所有对外合同中的 operation_digest 等于其所属 CompiledOperation.digest；模型/能力变更按前述见证改变相应身份。同一 Operation 在两个 Run 使用不同当前别名，彼此投影不得污染，也不得反向改变启动期静态身份；同一候选的可见合同与提交一致。能力声明变化须反映到工具可见/可调用范围；未取得匹配批准或预算耗尽仍由对应动作拒绝，不因静态编译而被跳过，不新增批准撤销功能。
- 编译负例覆盖：未知规则引用、context_sources 越界、将可选输入无条件要求为必需、attempts 清单与原字节权限误接。上述已能由现有编译检查拒绝的情况只补缺失见证，不新建一套检查器。

C1 的通过只证明声明、投影和消费者连接一致；科学语义正确性仍由后续真实工具/提交正负例及独立科学审查证明。

## 5. P1：将公共诊断接入编译合同与真实 MCP

### 主要位置

- `src/scidiscovery/operations/tooling.py`：现有工具 Schema 投影。
- `src/scidiscovery/operation_contract.py`、`operation_declaration.py`：结构化规则错误及通用声明。
- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`、`mcp_local_worker.py`、`mcp_hardened_worker.py`：实际调用入口。
- `interfaces/mcp.py`、`mcp_worker_protocol.py`、`mcp_root_operation_routes.py`：最外层传输、类型化工具异常和 Root 业务包装；均位于上述 interfaces 目录。
- `src/scidiscovery/artifact_agent/service/run_outputs.py`、`runs.py`：提交诊断、持久记录、Root 投影。
- `src/scidiscovery/operations/input_validation.py`、`invoke.py`：沿用输入错误与单一预检路径，只修改已确认的详情丢失点。

### 修改

1. 共用一个从模型校验错误生成安全详情的窄函数，Root、Local、Hardened 不再分别格式化成不一致的字符串。`list_tools` 和实际验证继续使用同一个 input_model；冻结后的模型/组件改变必须影响已有编译摘要，不增加新注册入口。
2. 详情统一表达 `code、phase、path、message、repairable、affected_action`，需要时带预期类型/支持值。复用已有 reason_code、rule_id、port、field 投影，不要求调用方同时填写两套等价字段。
3. 明确五类：可修参数/输出错误、能力不支持、证据/数据不可用、权限/完整性拒绝、框架异常。科学缺口仍由 Agent 的正式结果表达，不变成机械重试命令。
4. 未知异常不能包装成 output_rejected 或 unsupported。必需执行/完整性异常保留失败关闭；可选工具的工程不可用允许有限分析，并保留错误原因。禁止自动重发可能已经执行的副作用请求。
5. 复用 run_activity 的诊断字段持久保存有界的错误详情，并在 run_status 暴露最近错误和限定数量的纠错历史。没有 Run 的 Root 调用只返回诊断，不能为了记错误新建 Run。
6. 诊断仅保留 Schema 路径、数组下标、输入别名、静态模板消息和受限枚举；不原样持久化 ValidationError 的 input_value、令牌、绝对路径、原文件内容或任意映射键。旧记录没有详情时明确缺失。
7. 同次已知的独立输出问题尽可能一次返回；校验器仍按前置结构是否有效执行，不为“收集所有错误”在损坏对象上运行后续计算。

### 验收

同一错误请求经 Root/Local/Hardened 对应入口返回同义字段诊断；错误不调用 handler、不消耗副作用授权、不产生重复执行。普通单文件 Run、缺可选输入的有限报告仍可完成；未知校验器异常不进入输出重试。重启后仍能从控制面查到安全的具体原因。

### 5.1 错误必须到达实际 MCP 调用者

采用一个兼容现有传输的方案：保留 JSON-RPC 错误信封及已有 error.code，在 `error.data` 携带共享安全详情；不新增通用成功信封，不靠解析字符串判定错误类型。RootToolError、WorkerToolError、SemanticRuleViolation 保留可选安全 details；所有中间包装保留字段而不是调用 str 后丢弃。output 的模型异常使用 `errors(include_input=False, include_url=False)` 构造有界详情，继续关联已编译 rule_id。

| 场景 | facade/router 行为 | MCPRouter.handle 的行为 |
|---|---|---|
| preflight 检查出不满足条件 | 现有 admissible=false，保留 reason_code/port/field 并增加详情 | 正常 result，isError=false；这是查询结果，不是执行成功 |
| 同一绑定的 invoke 被拒绝 | OperationInvocationError 原结构进入 RootToolError.details | JSON-RPC error，data 中原因和位置与 preflight 一致；不创建 Run/Effect |
| Root/Worker 参数错误 | input_model 拒绝，typed error 保存路径/类型；handler 不运行 | JSON-RPC error.data；不能返回 isError=false 的普通错误字典 |
| worker_submit_result 输出可修正 | 保留 state=rejected + diagnostics 的正常业务返回 | 正常工具 result；state 明确未完成，不重新包装为传输异常 |
| 计算返回 unsupported/unavailable/error | handler 完成但没有数值结果，保留 CalculationRecord 和失败诊断 | 正常业务 result；日志同时记录“调用完成”和“业务未计算”，不能只写 tool_succeeded |
| 未知框架/完整性异常 | 进入现有工程失败或可选工具不可用分类 | 安全静态 message + data；内部原因链在受控工程记录中保留，不向 Agent 泄漏异常输入 |

Transform、Approval、Effect 路由中的现有包装遵守同样规则：可识别业务拒绝不丢字段，未知异常不变成输入不满足。JSON-RPC 格式错误仍属于协议错误。测试必须调用 `MCPRouter.handle(tools/call)`，不能只直接调用内层 router；包含各业务分支的无副作用负例、错误信封及敏感值脱敏检查。

### 5.2 可引用诊断与冻结来源清单

复用现有 `run_activity.diagnostic_json` 保存调用尝试，不增加表或生命周期。对全部已打开 Run 的工具错误保存安全诊断；只有声明了既有工具清单输出的 Operation 才把有界尝试投影为可引用附属成果。当前选择通用/TCAD 两个可选评分分析入口，预计算分析不获得调用能力。

仅为两个评分工具在现有 WorkerToolDefinition 增加默认 false 的 `record_attempts` 声明，置 true 时编译器核对所在 Operation 已声明清单输出；普通文件工具/心跳不新增可引用成功收据。所有入口仍保留公共错误诊断。对置 true 的调用，控制侧在模型验证前分配 Run 内 `attempt_001` 等局部尝试键，并记录规范请求摘要、工具名及编译身份、phase/code 和调用状态；handler 前拒绝的已读取源集合为空。handler 实际读到的文件，由 OperationToolContext 的读取回调记录完整 ArtifactRef，不让 Agent 自填内部身份。参数超出大小上限只存受限错误及摘要，不保存原值。请求原文若由报告保留，须与控制侧摘要一致；不得为了记录失败而执行 handler。

复用 `scidiscovery.tool-evidence-manifest.v1` 附属清单，新增可选 `bindings` 和 `attempts`，原 records 不变。bindings 是控制侧在该候选中使用的“原别名 → 完整 ArtifactRef/输入端口”映射；attempts 是已终止尝试的只读投影，包括请求/返回诊断摘要及确切读源关联。它不存原始请求中的秘密、自由文本异常或原始文件。缺省字段表示旧版本没有该证明。清单 Schema 的通用形状归现有通用证据代码所有，TCAD RecoveryManifest 与曲线插件引用同一资源；不把 TCAD 类型放入公共核心。

通用评分分析显式声明与 TCAD 同类的可选清单输出（沿用 recovery_manifest_output 名称），原始 tool_evidence 集合允许为空；这不授权读取执行目录或接收任意字节。`_evidence_manifest`、快照准备、发布和读取必须允许 records 为空但 bindings/attempts 非空，不能沿用“没有远程文件就没有清单”的判断。所有普通未声明清单的 Operation 保持原单文件行为。

清单快照进入已有 tool-evidence.json 候选指纹与主输出 parent_refs；ValidationSources 通过只读 snapshot 投影获得它，插件不查 Run 数据库。OperationToolContext 可查询本 Run 尝试的安全字段及来源投影，公开给 Worker 的仅为局部 attempt 键、当前别名和诊断；不接受 Worker 提供 Run ID、摘要或源身份来取得权限。候选接受后禁止新增尝试/来源变更，重试提交前的读取不得改变已冻结快照。

限制：每 Run 最多 64 项可引用尝试、每项安全元数据不超过 4 KiB、完整清单仍不超过 1 MiB；原文件数量/I/O 预算不变。到上限不覆盖旧项；记录有界 limit 错误，允许有限报告，不继续无界评分。只包含被允许显式引用的元数据，不把所有工具输出转成附属 Artifact。

## 6. P2：从同一类型声明贯通评分请求

### 主要位置

`plugins/curve_score/curve_score/analysis_tool.py`、`schema.py`、`science_operations.py`；`plugins/tcad_artifact/tcad_artifact/result_analysis.py`。

### 修改

1. 保持 `record_key/request` 外层调用形状。工具输入中的 request 改为插件拥有的明确模型：公共 comparison_spec 复用 CurveComparisonSpec，源映射按 bundle/CSV/PLX/log 区分；TCAD 复用 CurveAxis、SProcessSeriesSpec，公共曲线插件不反向依赖 TCAD。
2. MCP inputSchema 直接展示这些模型，不再把完整 Schema 塞进任意字典的文字说明。计算器使用同一模型验证后的值，删除对应的重复 allowed-key/轴模型手工定义。描述中的示例也从同一模型校验。
3. 轴写成字符串、缺 comparisons、未知参数等在调用边界明确指出字段；未知算子说明支持集合，不能假装执行成功。对格式确实不支持、数据行错误、时间/点数上限分别给出不同诊断。
4. 只有请求结构正确后才读取/解析原字节。用真实原请求证明错误发生在请求阶段；用规范请求另行验证真实 PLX，不能预设文件一定支持或一定不支持。
5. 不增加 `max_normalized_log_difference` 等同名算子来迎合一次错误调用。科学 Worker 判断现有 residual_max_abs/log10 等算子是否与计划数学定义等价；不等价就明确列出真实能力缺口，不改阈值、不伪造原检查通过。
6. 新工具仅接收结构化请求；持久的 CalculationRecord.request 保留原始 JSON，用于历史读取和失败诊断，不强制历史坏请求通过新调用 Schema。
7. 类型模型补默认值只用于执行，不改写回执中的原 request。旧 computed 记录按原始请求重放，省略默认值与显式默认值分别保留各自原请求表示；新增诊断/attempt 引用不参加旧数值结果的规范 JSON 比较。科学方法等价论证只能成为分析说明；只有现有 check key、metric kind、阈值和单位的机械匹配或匹配修订后的计划，才能算作原检查覆盖。

### 验收

真实错误请求得到 x_axis/y_axis 和比较结构的定位；修正后正常两列 PLX 能进入解析与现有计算路径。独立数据错误仍拒绝。现有正确 CSV/bundle/PLX/log 请求及安装入口保持可用；不因修复 TCAD 扩张其他角色权限。

## 7. P3：以单一来源解析贯通证据与案例交接

### 主要位置

`plugins/tcad_artifact/tcad_artifact/output_recovery.py`、`result_analysis.py`；`src/scidiscovery/artifact_agent/schema/layered_diagnosis.py` 中的 AnalysisSourceReference。`artifact_agent/operation_tool_context.py`、`interfaces/mcp_local_worker.py`、`service/tool_evidence.py`、`service/runs.py`、`operations/input_validation.py` 负责确切来源的只读投影、清单快照与跨轮重放，均不得加入领域判断。

### 修改

1. 明确两种不同事实：运行来源/字节身份由控制工具证明；某输出与科学案例的对应由项目显式声明，或 Agent 引用计划、源码和执行日志提出补充映射。工具接收成功不代表科学映射独立审查通过。
2. 原声明有身份时必须精确一致，禁止覆盖。原声明缺身份时，补充科学映射只进入评分 request 和 AnalysisSourceReference，**不修改 accept_tool 已接收记录的 metadata**。原接收工具继续负责文件到 output_name 的对应；科学映射与字节接收分离，因此接收后补依据不触发同 output_name 的 metadata 冲突。
3. 定义一个有界 CaseMappingBasis：`kind=declared|evidence`、`evidence_refs[{input_alias,locator}]`、`rationale`；experiment_key/case_key 复用外层字段。评分每个 source mapping 可携带 `case_mapping_basis`；正式 AnalysisSourceReference 携带相同内容。既有共享报告允许这一可选字段，具体 TCAD 校验由插件拥有。每个依据最多 8 个、定位为输入内行号/JSON pointer 等有界位置、理由最多 2 KiB，仍受请求 12 KiB/记录 32 KiB/报告总预算约束；长报告用定位引用，不复制源码。
4. 同一文件可作为全局诊断背景，不要求 case。若明确作为逐案例科学曲线使用，则检查目标案例存在、来源在本 Run、依据引用存在、原声明不冲突；多义映射必须保留未决，不按文件名相似度自动选择。跨执行、篡改字节、互相冲突的确定映射仍严格拒绝。
5. 补充映射是 Agent 的可审查科学声明，不获得执行资格或自动独立审查标记。可据其进行明示条件的计算；不确定性限制对应结论。如确需独立审查，由目录中的适用入口审查确切记录；没有适用入口时保留有限结果，不能冒充已审查，也不新增强制映射审批阶段。
6. 删除 result_analysis 的“任意 solver_outputs 无 case 即全报告不能通过”检查。按实际逐案例计算引用及计划所需产物检查覆盖；跨案例 solver_log 不触发该条件。缺少真实必需曲线仍限制完整结论。
7. 新 Run 显式绑定恢复清单、原字节和包含补充映射的封存分析；精确协议如下。新 preflight 检查新输入来源，提交仅校验输出如何使用它们。不能让文件与映射凭旧 Agent 记忆隐式继承。

### 7.1 评分之前及提交时的读取协议

评分工具必须从当前 request 的 source mapping 读取 basis，不能偷读尚未封存的 result.json。TCAD 同一个 `resolve_case_mapping` 函数接收 plan/project、当前别名的确切绑定描述符、source mapping 和 basis：声明存在则核对；声明为空则检查目标存在、依据范围和声明不冲突，并返回标明 evidence 来源的科学映射。只做可确定的来源/字段一致性检查，映射的科学充分性不由代码通过非空字符串判定。

OperationToolContext 增加受限的来源描述符读取能力，只能查询本 Run 已绑定/已接收文件。工具代码可用完整身份作机械核对；Worker 请求仍仅包含别名。依据源也作为评分所需来源读取并进入该尝试的受控 bindings；数值回放只使用数值 sources，依据仅用于身份核对，不能偷偷混入曲线数据。

同一当前报告里，computed record 的 source mapping 与该报告对同一原文件/案例的正式引用必须一致；映射变化使原计算不再支持新的映射，需要重新计算并给出新 record_key。单纯不能证明映射时，失败/有限报告仍可保留原尝试，不能强迫其修正原历史请求。全局日志只作为依据，无需赋单一 case。

### 7.2 下一 Run：显式绑定和别名重排

通用和 TCAD 分析各增加可选单值 `prior_analysis`（exact LayeredDiagnosisReport）与 `prior_analysis_manifest`（该分析的同生产者证明清单）。TCAD 已有的单值 `recovery_manifest` 继续只承担原始恢复文件的接收/执行证明；通用分析不新增恢复文件端口。两类清单类型可相同，但证明的事实和生产者不能混同。当前进展端口里的任意背景报告不自动成为映射来源。

为避免同一 Artifact 跨端口重复绑定，编译输入合同和目录说明必须公布以下唯一选择规则，由 preflight、tool context、输出校验和重放共用一个已解析用途投影：

| 绑定形状 | 上一轮分析证明的选择 | 原文件恢复证明的选择 |
|---|---|---|
| 没有 prior_analysis，只有 recovery_manifest | 不启用 prior 映射/attempt 复用；旧路径保持 | recovery_manifest，按原 receipt/执行身份核验 |
| prior_analysis 与 prior_analysis_manifest | 显式 prior_analysis_manifest；须匹配该分析的直接封存父件及同 producer | TCAD 若另外有恢复文件，仍需其 recovery_manifest |
| TCAD 有 prior_analysis，只有 recovery_manifest，且该清单恰是它的同 producer 直接父件 | 同一个 recovery_manifest 同时承担两种用途，只绑定一次 | 同一个 recovery_manifest，原 receipt 校验不变 |
| 两用途需要不同清单 | 两端口各绑定各自不同 Artifact | 不能用上一轮清单代替原文件 receipt |
| 显式 prior_analysis_manifest 不匹配，或缺 prior_analysis | 拒绝错误配对，不静默回退到另一清单 | 不改变独立的原恢复路径 |

仅需要历史背景时使用 current_progress；请求可信 prior 复用时必须满足上表的配对。若两个端口重复绑定相同 Artifact，继续按原规则拒绝，不放松全局 input_artifact_duplicate；调度者应使用一次绑定的第三行形状。

preflight 检查所选 prior 证明是 prior_analysis 的同 producer 直接封存父件，所选原恢复证明具有原文件的 receipt/producer/执行关系；两者分别核验，不能自动读取未绑定父清单或复制原 receipt 改生产者。所有被选用于计算/依据的来源仍必须在本 Run 显式绑定，计划/执行/项目关系匹配。prior 证明的 bindings 由服务按完整 ArtifactRef 和 lineage 匹配当前别名；不能按字节摘要、文件名、端口位置或旧别名选文件。完整身份最多绑定一次，现有重复规则不变；字节相同但身份不同的文件仍分别对待。没有确切匹配则报告有界缺失，不能去找未绑定文件。

在 assignment 的现有来源清单和 tool context 中提供只读 `prior_source_bindings` 投影：prior_analysis 的旧别名对应当前哪些别名；不把旧别名直接合并覆盖新 inputs。Worker 根据该投影重新提交**当前别名**的 basis；校验器比较解析后的完整来源身份、定位、case 和理由。重放旧 CalculationRecord 时使用隔离的旧别名视图，从确切已绑定 Artifact 机械重建，不改写原 request 或污染全局别名空间。

旧 manifest 没有 bindings 时，只有其 records 内已有完整来源身份的恢复文件可以作确切重放；对原已注册文件的报告补充映射不猜身份。Worker 可从本轮确切输入重新建立 basis；旧报告仍可作历史背景读取，不自动升级可信映射。

三轮必测见证：A 恢复 F 并封存 MA；B 绑定 A、MA、F，MA 只出现一次且承担两种用途，B 不重复接收 F，只计算/补依据并封存 MB；C 绑定 B、`prior_analysis_manifest=MB`、`recovery_manifest=MA` 与 F，分别使用 B 的映射/尝试证明和 A 的原接收证明。MB 的 records 可以为空，bindings/attempts 非空；MB 不把 F 假装为 B 新接收。完整经过 preflight→tool→submit，并检查 MA/MB 对换、不同 producer、缺原恢复证明的负例。缺证明只能拒绝相应复用，仍可另用已准入背景输入提交有限分析，不能绕过该次错误绑定的 preflight。

### 7.3 补充与修订规则

| 场景 | 行为 |
|---|---|
| 相同字节接收请求重复 | 原 accept 幂等规则不变 |
| 接收时没有案例，后来补依据 | 在新评分 request/正式报告中给 basis；不重接收、不改旧 metadata |
| 提交前修正 basis | 新 record_key 重新计算；最终引用采用一致 basis，旧尝试保留为历史尝试 |
| 与项目显式案例冲突 | 拒绝该确定映射；允许不作该案例主张的有限报告 |
| 两条补充 basis 矛盾 | 不能默默选最新；Worker 明确修订及限制，未解决时对应结论不可成立 |
| 失败 Run 的 draft_from/resume | 原字节按既有 exact execution 校验继承；旧 basis/尝试保留原 Run 来源，不能当作新调用或已封存科学判断 |
| completed 后改映射 | 必须新 Run、新报告、新计算；旧记录不变 |

### 验收

声明缺 case 的真实旧项目可得到有据可查的映射和条件明确的计算；有 case 的现有项目行为不变；全局日志不妨碍曲线计算。原已注册文件、恢复文件各完成评分→封存→新 Run 重放；后轮增加/重排输入，绑定字节相同但身份不同的文件作负控。覆盖接收后补依据、提交前修正和失败 Run 继承。无依据、歧义、冲突、跨案例或跨执行映射各有正确定性/科学处置，重启不丢关联。

## 8. P4：分析校验只约束有依赖关系的结论

### 主要位置与消费者

- `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py`：层级、判定、计算记录。
- `plugins/curve_score/curve_score/science_operations.py`：通用分析、预计算 curve-error 分析及 validate_analysis_report/_validate_diagnosis_against。
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py`：TCAD 输出引用与计算重放。
- `src/scidiscovery/artifact_agent/schema/claim.py`：核对 claim 投影未获得新的授权含义；原则上不改实现。

### 修改

1. 保留现有字段和证据引用结构，删除固定顺序中“一层不可评价，后续层全部必须不可评价”的强制传播。独立已有证据可支持对应层事实，缺曲线不能抹掉已完成步骤的日志事实。
2. 停止由 prerequisite_status 统一强制所有目标不可评价、总判定 invalid_study。Agent 可提交有证据的局部结果与总体 inconclusive；objective_assessment 只描述所引用目标/比较，不按全局 observation 状态硬拷贝。
3. 保留严格的完整成功边界：overall pass/claim_allowed 仍要求计划必需检查的实际覆盖、正确证据与计算、无已知相关失败；科学有效性争议不能由工具 receipt 解决。程序不得自动把有限报告升级成 pass。
4. 保留不虚构数值、不引用未完成比较作为成功证据、声明阈值与原计划对应、确定性重放等规则。负面或未测试判断可以与局部已完成事实同时存在；不允许因语义放宽而用缺失计算支持假设。
5. 这轮不删除持久字段或引入新报告物化阶段。保留的纯机械一致性使用一个派生/检查函数，返回所有可安全确定的不一致及建议值；程序不默默改写 Agent 已提交的科学内容。原严格规则的删除与保留项须在 P0 账本逐项闭合。
6. 失败 CalculationRecord 可以保留请求、错误阶段和结构化诊断，作为失败原因的证据，不能作为数值成功依据。case 映射成功校验仅用于实际 computed 或报告确认的科学映射；失败请求中的未成立案例名属于“曾请求的值”，不能阻止诚实失败记录提交。
7. 已解析为 computed 的记录必须从绑定原字节重放核验。非 computed 记录不得包含数值结果；检查 Run 范围/工具来源并保存诊断，不要求坏请求满足成功请求契约或重新得到相同新版错误码。
8. 复用 P1 的活动记录保存工具失败；报告未引用的工程错误仍可追踪。报告中的失败诊断不得把明确 invalid_arguments 声称为 confirmed unsupported format；能机械核对的错误码/阶段须一致，剩余工程归因由审查判断，不写自然语言推理校验器。

### 8.1 失败记录的真实性与历史行为

CalculationRecord 新增可选 attempt 引用（清单输入别名 + 局部 attempt_key）和有界 diagnostics；当前 Run 使用系统提供的清单别名，后轮使用 §7.2 唯一规则选中的 prior 分析证明别名（通常 prior_analysis_manifest，符合单清单条件时是 recovery_manifest）。模型不提供 Run ID 或可信摘要。参数被拒绝时工具错误也返回 attempt_key，因此 Worker 可以记录 handler 前失败，而不伪造“计算器已经运行”。record_key 只是报告内部键，不能代替可信尝试关联。

本轮评分的所有返回结果均与控制侧 attempt 关联；插件只把自身结果模型的非 computed 状态转换成共享安全诊断，控制侧保存该返回摘要，不靠扫描任意字典的 status 猜科学结果。上下文校验器通过冻结清单核对 attempt 确实终止、工具/phase/code、原 request（包含 source mapping/basis）和实际读源关联。computed 仍核验数值重放；失败记录只核对真实调用及返回，不重新要求请求成功，也不重跑读取或服务调用。

三种来源明确区分：

- **当前可信尝试**：当前控制清单中的记录；修改请求、错误码、阶段或嫁接另一个 attempt 必须拒绝。
- **显式绑定的历史可信尝试**：prior_analysis 与其清单配对核实；只证明旧工具在当时返回过该错误，不声称新工具仍不支持。新 Run 重试产生新 attempt，不改变旧记录。
- **无收据的旧封存失败/历史叙述**：允许作为历史限制引用，标明未复核；不能伪装当前工具确认，也不要求补造旧收据。新增可信 attempt 引用不能指向缺失或不匹配清单。

未完成/失败 Run 的调用记录可随既有受控 draft_from/resume 保全作为工程事实继承：沿用来源 Run 和冻结请求/读源，不能变成新 Run 当前 attempt 或已封存科学结论。原 Run 超时发生在 handler 执行中时，只能记录 interrupted/unknown engineering 状态，不能伪造 completed 返回。记录保存失败属于工程故障；已经读到的科学字节仍按原 CAS 保留，不能以没有诊断为由重跑外部副作用。

验收：同 Run 参数拒绝→修正计算→保留两次尝试；修改请求/code/phase、冒用别的 Run 均拒绝。候选后迟到调用不能改快照；重启、失败接续及后轮显式绑定可核验原记录。旧错误只作历史限制仍可提交。

### 8.2 三个分析入口的证据能力和实际成功门槛

| 入口 | 可引用的计算 | 必须拒绝 |
|---|---|---|
| 通用可选评分分析 | 本 Run 工具计算；明确绑定的历史计算/metric report；失败尝试清单 | 未绑定输入、未知计算键、伪造计算或失败收据 |
| TCAD 可选评分分析 | 上述能力加 exact execution 原字节、接收清单和 P3 案例映射 | 跨执行、冲突的明确 case、字节篡改、未证明的映射被当作无条件成功 |
| 预计算 curve-error 分析 | 只引用 exact curve_analysis_package 内已有的 metric_report/固定数据，以包别名与 JSON pointer 定位 | 新建 calculation_records（即便 status=error）、补充外部 source_references、伪造包外计算或 receipt |

预计算入口声明自己的输出 Schema：从同一 LayeredDiagnosisReport 生成后机械收窄 calculation_records.maxItems=0；source_references 只允许 exact 包别名与包内 locator，不能照抄拥有评分工具入口的能力。其提示词同步更新；不为它添加评分工具或重新计算包内结果。旧包含附加字段的 sealed 报告仅历史可读，不能继承为当前有效计算依据。

`validate_analysis_report` 和 `_validate_diagnosis_against` 复用一个“实际完成检查覆盖”函数：同时核验精确计划、合同绑定 check、要求的比较/算子真实状态、metric/阈值/单位和证据引用。合同写了检查只证明设计覆盖，不计作已通过；没有 objective_key 也执行这条检查。overall pass/claim_allowed 必须满足所有本轮必需数值检查真实 pass 且没有相关 required fail/unavailable；其他科学层仍需各自证据，代码不把数值 pass 自动变科学 pass。对失败或有限报告不要求所有检查已完成，只限制所声称的具体成功项。

固定全局 prerequisite 的提示与检查一并撤销，包括通用诊断提示、curve-error 最早失败处停止提示、TCAD 的“case 只能来自原声明”提示；保留原计划中的真实科学依赖，不让宽松报告变成忽略计划。claim.py 保持纯投影，不增加授权逻辑。

验收必须完整调用三个 Operation 的 schema→submit。预计算包全覆盖、无 objective_key、但 required metric 失败/不可用时不得 overall pass；伪造 computed、未知包外引用拒绝；其诚实有限报告可完成。

### 8.3 报告内部证据键与输入别名分离

采用最小插件接线：从曲线插件 `_EVIDENCE_PATHS` 中移除 layered-diagnosis 的 `/evidence` 输入别名枚举投影，其余 scientific-review/evidence 输出保持现状；公共 operation_contract 不增加 calculation_records 或 TCAD 分支。layered diagnosis 的 evidence.source_key 是报告内唯一键，不能再充当 input_alias。

三个分析入口统一解释 locator：原始输入必须有匹配 AnalysisSourceReference，其 input_alias 是当前精确绑定名；计算证据使用 `calculation_records:<record_key>`；失败尝试通过该记录的 attempt 引用核验；预计算入口只允许包别名和合法包内定位。字段结构和唯一键由 Schema 校验，所有原始输入别名/记录键及其使用范围由该入口的领域上下文校验，不因取消错误枚举而取消来源检查。

通用入口新增真实 Worker 的“评分→独立证据键引用→submit”正例：同一输入得到两个独立计算；同时包含未知 input_alias、未知 record_key、失败记录被冒充成功的负例。不能以直接调用 diagnosis_context 的测试代替生成 Schema 和正式提交。

### 验收

重放本次六类拒绝见证：合理字段错误得到明确合并诊断；诚实有限报告一次可提交；失败计算记录能保留；虚构 completed comparison 继续拒绝。通用分析和 curve-error 入口同步验证，不能留下另一套全局顺序回退。完整成功的负向门槛及 claim 投影不退化。

## 9. P5：兼容、全局覆盖和安装包验收

1. 冻结输入与旧 Artifact 不原地重写；原执行仍保留原收集失败状态。历史 completed 结果继续可读，原科学结论不因新代码自动翻转。
2. 新调用使用新工具输入合同；旧 CalculationRecord 和 LayeredDiagnosisReport 保留可读。新增字段可选且有默认值，缺失诊断不伪造。正确旧 computed 记录的数学语义和重放不改变；旧错误记录按历史诊断读取，不能因错误分类修复被拒绝或升级为成功。
3. 不修改冻结候选。接口升级前等待活动 Run 完成或按既有生命周期处理；不跨新旧 digest 复用同一个 Run。新 Run 可显式绑定历史证据，不能继承旧审查资格。
4. 从安装 wheel 编译全部实际插件组合并生成 Worker 配置，列出准确受影响 Operation/agent_type。公共模型可能影响多个角色，不预设“只改一个 digest”，也不为新摘要重做无关科学实验。
5. 公共入口验收至少覆盖 Root、Local、Hardened、普通 Agent、一个 Transform、一个 Approval 和一个 Effect，以及通用/TCAD/figure 插件组合。对仍有同类违规的已安装接口不能写全局符合。
6. 规范文档更新仅涉及唯一声明/编译复用、职责与诊断条款；本计划与原计划在索引中区分提案、已实施、现场验证。原有审查历史不覆盖。

## 10. P6：当前真实案例验收

按 Operation 目录调度，使用原目标、计划、匹配审查、原执行、恢复成果、参考证据和封存进展。新 Agent 不继承父聊天，Root 不代写评分请求、案例映射或科学计算。

验收必须同时满足：

1. 已安装接口与预期一致；原实例/证据绑定可续接。
2. 隔离的真实 Worker 接口纠错见证：错误轴或比较请求得到准确诊断，同一 Run 在预算内修正；无不必要副作用。不可为了测试污染原科学产物。
3. 实际研究分析 Worker 自主构造请求、检查真实 PLX、形成可审查映射，并至少完成一项符合原计划或已明确论证等价的实际计算。不能用任意简单指标替代目标检查充数。
4. 计算、映射、失败尝试与结论限制一同封存；无“参数错误变格式不支持”的错误归因；不依赖删除失败记录才能提交。
5. 新设计 Agent 仅凭绑定记录理解已完成工作、剩余目标和真正能力缺口，提交可交付的下一轮设计；物化后的计划经匹配独立审查。不得把工具适配任务转嫁 author 或要求重复原实验来补元数据。
6. 错配证据、未授权执行、篡改计算和无依据映射仍被拒绝或明确限制，不能用正例通过掩盖负例退化。

若正确调用揭示了新的真实算法能力缺失，记录具体算子/数学定义和影响范围，不临时扩大本计划。可以完成工程阶段，但 P6 对应项标记未完成，不能宣称科研闭环已经跑通。下一轮实际外部执行若确有需要，必须获得精确 UI 批准。

## 11. 定向检查与资源预算

始终一次只运行一个测试进程树，包含 wheel 构建/子进程累计 RSS 的硬上限 512 MiB；不使用 pytest-xdist，不并行安装测试与源码测试，不在等待结果时启动第二组。达到预算停止该组并记录，不通过加大预算硬跑。未运行的检查明确列出。

| 组 | 现有测试入口及新增行为 | 完成证据 |
|---|---|---|
| 公共入口 | test_agent_contract_alignment、test_l2_local_run、test_l5_hardened_run_backend、test_log_preservation | 可见 Schema 与实际参数一致；安全错误详情；重启后诊断；普通 Run 不退化 |
| 请求与计算 | test_result_analysis_tool、test_tcad_result_analysis | 实际坏请求精确报错；正确格式；失败记录；改数值/字节拒绝 |
| 交接 | test_analysis_evidence_recovery、test_analysis_input_descriptors | 旧声明缺 case、原已注册文件、恢复文件、全局日志、跨轮映射与负控 |
| 分析语义 | test_m2_curve_analysis_boundary、test_result_analysis_tool、test_tcad_result_analysis | 混合局部结果能提交；全局成功仍需真实覆盖；所有共享消费者一致 |
| 全局合同 | test_catalog_compile、test_catalog_negative_cases、test_invoke_preflight、test_h2b_domain_boundaries、test_architecture_constraint_matrix | §4.4 单声明变更→全部相关消费者；动态投影隔离；全目录台账；角色无越权；编译与插件依赖不退化 |
| 安装 | test_catalog_installed_entrypoint、test_analysis_tool_installed | wheel 与 MCP 真实入口；源测试不能替代 |
| 现场 | P6 受控记录 | 实际计算、封存、新设计及匹配审查；与本地通过分开 |

先选择相关函数，再按共享影响扩至上述文件；不重复运行已通过且未受后续改动影响的组。保留一个针对通用框架的非 TCAD 插件见证，防止公共代码只对 TCAD 成立。

用户已有低内存要求优先于技能中的全量测试默认建议，本机不跑全量/stress。广泛 CI 矩阵可在资源合适环境单独执行，不能冒称已完成。技能提及的 `validate_architecture_constraints.py` 与 `run_science_control_bench.py` 当前源码中不存在，不写成可直接执行的检查；使用上述实际入口与人工语义审查。

## 12. 执行顺序、变更控制与完成声明

严格主线：P0 基线/盘点 → C1 现有编译产物与共有消费者收敛 → P1—P4 依次完成诊断、请求、来源和分析语义的声明到消费者迁移 → P5 安装与全目录复核 → P6 真实交接。P1—P4 沿用已审查接口的编号，不是四套独立机制。每项均须提交“唯一来源、编译投影、消费者变化、已删副本、正负例”五项证据；缺少删除/接线证据不得宣布该项完成。P2/P3 仅在 C1/P1 已稳定且文件范围独立时可由获授权执行者分工，测试始终串行；本计划不自动启动子 Agent 或实现。

生产修改以 C1 和 P1—P4 列明文件为范围；tool_evidence、OperationToolContext 和相关工作区/快照代码因 §5.2/§7 已明确纳入。catalog/spec/compiler 纳入 §4.2 的既有编译产物、身份和消费接线，不能仍限于 record_attempts 的一项开关校验，也不能扩大为重写编译器。platforms/codex.py 仅接回现有编译投影；Root/lifecycle 保留各自现有声明，不新增科研 Operation。claim 保持纯投影；安装脚本只在 P0 已证明的兼容需要时修改，并先记录理由。新增共用函数优先放现有归属模块，不以拆文件增加权威。其他新增功能或真实算法扩张先修订本计划。

部署前保存可恢复的包和精确增量；回滚仅恢复本次代码/配置版本，不撤销或改写新旧科学 Artifact，不把新 Run 塞回旧合同。若旧运行时无法解释新增可选元数据，停止相关新调用并保留记录，不能删字段使其伪装为旧版本。

最终分别报告：公共契约覆盖、定向源码检查、安装包检查、实际部署、真实计算与跨轮交接。只有 P6 完成后才称本轮真实交接验收完成；总体研究目标是否完成仍由封存科学结果及其审查决定。

## 13. R0 独立审查闭合表

| 审查问题 | R1 明确决定 | 必须经过的验收边界 |
|---|---|---|
| R1 错误穿过 MCP 后丢失 | §5.1 采用现有 JSON-RPC error.data，所有 facade/typed error 保留详情 | MCPRouter.handle + Root/Local/Hardened + Transform/Approval/Effect 负例 |
| R2 映射在评分/后轮/补充时无协议 | §7.1—7.3 显式 request basis、控制 bindings、prior_analysis 配对、隔离别名重放，接收 metadata 不改；R2 版本分离两个生产者的清单用途 | 原注册与恢复文件、输入重排、同字节不同身份、补依据与失败继承、A→B→C 三轮及单清单一次绑定 |
| R3 失败无可信来源 | §5.2/§8.1 复用活动记录和冻结工具清单，区分当前/历史可信/无收据历史 | 参数拒绝后纠正、请求/code/phase 篡改、重启与跨轮 |
| R4 预计算入口可假成功 | §8.2 限定包内引用，禁止新记录，核验实际 required pass | 无 objective_key 且全覆盖但指标失败/不可用的完整 submit |
| R5 通用 Schema 禁止计算键 | §8.3 移除 layered-diagnosis 错误别名枚举，保留领域引用核验 | 同一输入两项计算的真实 Worker 评分→submit 及非法引用负控 |

上表只表示已给出修订方案，不代表独立审查已经认定闭合；以新版本的确切 SHA256 复审结论为准。

R1 唯一剩余阻断由 §7.2 的两类清单、确定性用途选择、重复绑定保留和三轮见证处理。`record_attempts` 仅启用控制侧尝试证明，不借用 evidence_ports 开启原字节接收或执行范围权限；相关编译/workspace 成对检查应支持这种清单独立发布，普通 Operation 与未声明工具保持旧权限。


### R3 主线变更与保留范围

R3 将 §4 的 C1 设为实现主线，修改 §5—7 的消费归属、§9 的覆盖、§11 的声明变更测试和 §12 的顺序/源码边界。R2 的 JSON-RPC error.data、可信 attempt、两类清单及单次绑定、A→B→C、历史计算回放、三个分析入口的限制和真实案例条件全部保留。旧 R2 PASS 只覆盖旧快照；R3 需重新审查编译改动是否足够具体、是否扩大不必要范围、是否真正删除多份规则以及是否仍保持输入/输出分工。

### R4 复审补齐

仅补清 §4.2 第 4 点的静态材料→既有摘要→对外身份顺序，并在 §4.4 增加确定性身份/自引用排除/动态隔离的验收，修正批准措辞与笔误。R3 唯一必要审查问题据此交新版本定向复审；不增加新摘要协议或扩大 P1—P6 的具体接口范围。
