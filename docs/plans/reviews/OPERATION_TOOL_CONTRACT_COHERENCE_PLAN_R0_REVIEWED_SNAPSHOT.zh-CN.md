# Operation 与工具契约一致性修复计划

状态：R0，待审查工程提案，2026-09-11。仅制定计划，未授权实施、未宣称通过独立审查。

## 1. 目标、范围与决策归属

目标：所有已安装工具和 Operation 遵守同一套接口、校验、诊断和证据交接原则；让当前 TCAD 案例在已有执行产物上完成真实计算、封存和下一轮交接。修复可重复发生的机制问题，不以增加必填字段、强制科研阶段或放宽证据完整性代替。

问题依据：[本次完整根因核查](reviews/TCAD_ANALYSIS_3_BLOCKER_ROOT_CAUSE.zh-CN.md)。首个评分错误是轴参数对象被写成字符串，并被误报为 PLX 格式不支持；比较结构同样错误。产物恢复没有补齐可表达的案例映射，固定层级规则又造成连续输出返工。不能据此先扩写 parser 或重跑 solver。

| 文档 | 归属与处置 |
|---|---|
| 本计划 | 契约一致性修复的活动提案；实施后以精确执行记录标记完成范围 |
| 当前架构、设计宪章、33 项约束 | 继续拥有规范性原则；实施时仅更新受影响条款及中英对应段落 |
| 输入校验阶段修复计划 | 保留 preflight、输出校验、完整性故障分离的既有决定；本计划补齐工具与消费者交接 |
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

- 复用 OperationSpec、CompiledCatalog、WorkerToolDefinition.input_model、InputValidationSpec、Run 活动记录、CalculationRecord、AnalysisSourceReference 和现有工具证据清单。
- 不增加 Operation 注册表、任务生命周期、统一依赖图、自动科学路由、万能修复角色、评分独立阶段、默认新审批或远程执行能力。
- 不给所有角色开放所有工具；统一的是契约和诊断规则，权限继续按各 Operation 编译。
- 公共核心不得认识 PLX、TCAD 案例名或评分算子；格式、科学映射、比较请求由对应插件拥有。
- 不重构 VM runner、COMSOL、部署目录或审批页面；本次原则上只更新本地服务/Worker 包与生成配置。若实际变更触及远程协议，必须先明确记录范围，不能顺手扩展。
- 不新建通用工具成功返回大信封或一套通用结果状态机。保留现有成功返回与 OperationInvocationError 等协议，只为错误增加共享的有界结构化详情；固定工具结果需要验证时从其现有模型生成。
- 本次禁止全面迁移科学 Schema 或删除历史字段。现有结构优先保留；改变语义后记录受影响 Operation digest，旧资格不继承。

## 4. P0：冻结基线并完成全目录职责盘点

### 工作

1. 以实施开始时的完整工作树为基线保存文件清单、摘要和精确增量；不把 HEAD 以来所有已有修改算成本计划。
2. 从默认插件组合与含 figure 插件组合编译目录，枚举每个工具/Operation、输入模型、输出 Schema、输入检查器、输出检查器、上下文检查器、权限及生产调用路径。Root/lifecycle 工具从现有声明获取；不通过字符串搜索推断运行目录。
3. 逐个注册检查器标注其职责与实际消费的输入；重点核对：可选变必需、宽泛异常转换、输出阶段重准入、工具任意字典掩盖固定结构、跨角色交接缺口、固定科学状态传播。相同组件只审一次，记录所有消费者。
4. 将每项分为“符合”“本计划修复”“需单独有界处理”。必须列明位置、触发条件、受影响动作和保留的不变量；未检查不能写成符合。没有调用证据的问题不纳入源码改动。
5. 冻结当前 TCAD 真实案例的 exact inputs、受控恢复成果及调用错误见证；科学记录通过 Root/受控 Worker 使用，不能把工程测试脚本变成科学结果生产者。

### 交付与退出条件

在 `docs/plans/evidence/operation-tool-contract-coherence/` 保存 BASELINE、CONTRACT_INVENTORY 和实际修改清单。公共修复覆盖的调用方必须齐全；新发现但未修的同类违约必须显式列入限制，不能宣称“全部一致”。纯 Python 语义不能靠编译器自动证明，本阶段必须进行人工工程审查。

## 5. P1：公共参数与错误诊断收敛

### 主要位置

- `src/scidiscovery/operations/tooling.py`：现有工具 Schema 投影。
- `src/scidiscovery/operation_contract.py`、`operation_declaration.py`：结构化规则错误及通用声明。
- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`、`mcp_local_worker.py`、`mcp_hardened_worker.py`：实际调用入口。
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

## 6. P2：评分请求变为真实可用的类型契约

### 主要位置

`plugins/curve_score/curve_score/analysis_tool.py`、`schema.py`、`science_operations.py`；`plugins/tcad_artifact/tcad_artifact/result_analysis.py`。

### 修改

1. 保持 `record_key/request` 外层调用形状。工具输入中的 request 改为插件拥有的明确模型：公共 comparison_spec 复用 CurveComparisonSpec，源映射按 bundle/CSV/PLX/log 区分；TCAD 复用 CurveAxis、SProcessSeriesSpec，公共曲线插件不反向依赖 TCAD。
2. MCP inputSchema 直接展示这些模型，不再把完整 Schema 塞进任意字典的文字说明。计算器使用同一模型验证后的值，删除对应的重复 allowed-key/轴模型手工定义。描述中的示例也从同一模型校验。
3. 轴写成字符串、缺 comparisons、未知参数等在调用边界明确指出字段；未知算子说明支持集合，不能假装执行成功。对格式确实不支持、数据行错误、时间/点数上限分别给出不同诊断。
4. 只有请求结构正确后才读取/解析原字节。用真实原请求证明错误发生在请求阶段；用规范请求另行验证真实 PLX，不能预设文件一定支持或一定不支持。
5. 不增加 `max_normalized_log_difference` 等同名算子来迎合一次错误调用。科学 Worker 判断现有 residual_max_abs/log10 等算子是否与计划数学定义等价；不等价就明确列出真实能力缺口，不改阈值、不伪造原检查通过。
6. 新工具仅接收结构化请求；持久的 CalculationRecord.request 保留原始 JSON，用于历史读取和失败诊断，不强制历史坏请求通过新调用 Schema。

### 验收

真实错误请求得到 x_axis/y_axis 和比较结构的定位；修正后正常两列 PLX 能进入解析与现有计算路径。独立数据错误仍拒绝。现有正确 CSV/bundle/PLX/log 请求及安装入口保持可用；不因修复 TCAD 扩张其他角色权限。

## 7. P3：补齐证据到案例的可审查交接

### 主要位置

`plugins/tcad_artifact/tcad_artifact/output_recovery.py`、`result_analysis.py`；`src/scidiscovery/artifact_agent/schema/layered_diagnosis.py` 中的 AnalysisSourceReference。优先复用现有 metadata/CAS/清单；`service/tool_evidence.py` 只在需要机械传递新增元数据时修改，不加入领域判断。

### 修改

1. 明确两种不同事实：运行来源/字节身份由控制工具证明；某输出与科学案例的对应由项目显式声明，或 Agent 引用计划、源码和执行日志提出补充映射。工具接收成功不代表科学映射独立审查通过。
2. 原声明有身份时必须精确一致，禁止覆盖。原声明缺身份时，在现有接收请求及报告引用结构中增加可选、有界的案例映射依据：目标 experiment/case、依据别名及定位、理由。服务保存来源类别（声明或证据补充）与原始空声明，不改旧项目/manifest。
3. 映射覆盖原先已注册文件与后来恢复文件。已注册文件可直接在正式报告的结构化引用中补充；恢复文件可复用接收清单的依据。一个插件内的窄解析函数统一读取两种记录，评分、报告校验和下一轮读取使用同一解析规则，不能再建立两套优先级。
4. 同一文件可作为全局诊断背景，不要求 case。若明确作为逐案例科学曲线使用，则检查目标案例存在、来源在本 Run、依据引用存在、原声明不冲突；多义映射必须保留未决，不按文件名相似度自动选择。跨执行、篡改字节、互相冲突的确定映射仍严格拒绝。
5. 补充映射是 Agent 的可审查科学声明，不获得执行资格或自动独立审查标记。可据其进行明示条件的计算；不确定性限制对应结论。如确需独立审查，由目录中的适用入口审查确切记录；没有适用入口时保留有限结果，不能冒充已审查，也不新增强制映射审批阶段。
6. 删除 result_analysis 的“任意 solver_outputs 无 case 即全报告不能通过”检查。按实际逐案例计算引用及计划所需产物检查覆盖；跨案例 solver_log 不触发该条件。缺少真实必需曲线仍限制完整结论。
7. 新 Run 显式绑定恢复清单、原字节和包含补充映射的封存分析；新 preflight 检查新输入来源，提交仅校验输出如何使用它们。不能让文件与映射凭旧 Agent 记忆隐式继承。

### 验收

声明缺 case 的真实旧项目可得到有据可查的映射和条件明确的计算；有 case 的现有项目行为不变；全局日志不妨碍曲线计算。无依据、歧义、冲突、跨案例或跨执行映射各有正确定性/科学处置。重启及下一 Run 重放不丢来源类别和依据。

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

### 验收

重放本次六类拒绝见证：合理字段错误得到明确合并诊断；诚实有限报告一次可提交；失败计算记录能保留；虚构 completed comparison 继续拒绝。通用分析和 curve-error 入口同步验证，不能留下另一套全局顺序回退。完整成功的负向门槛及 claim 投影不退化。

## 9. P5：兼容、全局覆盖和安装包验收

1. 冻结输入与旧 Artifact 不原地重写；原执行仍保留原收集失败状态。历史 completed 结果继续可读，原科学结论不因新代码自动翻转。
2. 新调用使用新工具输入合同；旧 CalculationRecord 和 LayeredDiagnosisReport 保留可读。新增字段可选且有默认值，缺失诊断不伪造。正确旧 computed 记录的数学语义和重放不改变；旧错误记录按历史诊断读取，不能因错误分类修复被拒绝或升级为成功。
3. 不修改冻结候选。接口升级前等待活动 Run 完成或按既有生命周期处理；不跨新旧 digest 复用同一个 Run。新 Run 可显式绑定历史证据，不能继承旧审查资格。
4. 从安装 wheel 编译全部实际插件组合并生成 Worker 配置，列出准确受影响 Operation/agent_type。公共模型可能影响多个角色，不预设“只改一个 digest”，也不为新摘要重做无关科学实验。
5. 公共入口验收至少覆盖 Root、Local、Hardened、普通 Agent、一个 Transform、一个 Approval 和一个 Effect，以及通用/TCAD/figure 插件组合。对仍有同类违规的已安装接口不能写全局符合。
6. 规范文档更新仅涉及职责与诊断条款；本计划与原计划在索引中区分提案、已实施、现场验证。原有审查历史不覆盖。

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
| 全局合同 | test_catalog_compile、test_catalog_negative_cases、test_h2b_domain_boundaries、test_architecture_constraint_matrix | 全目录检查器台账；角色无越权；编译与插件依赖不退化 |
| 安装 | test_catalog_installed_entrypoint、test_analysis_tool_installed | wheel 与 MCP 真实入口；源测试不能替代 |
| 现场 | P6 受控记录 | 实际计算、封存、新设计及匹配审查；与本地通过分开 |

先选择相关函数，再按共享影响扩至上述文件；不重复运行已通过且未受后续改动影响的组。保留一个针对通用框架的非 TCAD 插件见证，防止公共代码只对 TCAD 成立。

用户已有低内存要求优先于技能中的全量测试默认建议，本机不跑全量/stress。广泛 CI 矩阵可在资源合适环境单独执行，不能冒称已完成。技能提及的 `validate_architecture_constraints.py` 与 `run_science_control_bench.py` 当前源码中不存在，不写成可直接执行的检查；使用上述实际入口与人工语义审查。

## 12. 执行顺序、变更控制与完成声明

严格顺序：P0 → P1 → P2 → P3 → P4 → P5 → P6。P2/P3 实现可以在范围独立时由执行者分工，测试仍串行；本计划不自动启动子 Agent 或实现。

生产修改以 P1—P4 列明文件为范围；catalog/spec/compiler、tool_evidence、claim、安装脚本只在 P0 已证明的接线/兼容需要时修改，并先记录理由。新增共用函数优先放现有归属模块，不以拆文件增加权威。其他新增功能或真实算法扩张先修订本计划。

部署前保存可恢复的包和精确增量；回滚仅恢复本次代码/配置版本，不撤销或改写新旧科学 Artifact，不把新 Run 塞回旧合同。若旧运行时无法解释新增可选元数据，停止相关新调用并保留记录，不能删字段使其伪装为旧版本。

最终分别报告：公共契约覆盖、定向源码检查、安装包检查、实际部署、真实计算与跨轮交接。只有 P6 完成后才称本轮真实交接验收完成；总体研究目标是否完成仍由封存科学结果及其审查决定。
