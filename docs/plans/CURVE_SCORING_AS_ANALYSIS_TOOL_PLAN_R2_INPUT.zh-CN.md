# 曲线评分移入结果分析的最小修复计划

状态：R2 修订提案，已回应独立 R1 审查，尚待复审与实施；未修改生产代码、未运行新实验、未取得实现审查 PASS。
日期：2026-09-09。
基线：分支 refactor/m7-pre-e5.2，HEAD 2edac5d317a74056869a567bd0daa7f556ecbc85 及当前已有工作树；实施前冻结确切增量基线，不回退既有修改。

审查依据：[独立 R1](reviews/CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN_REVIEW_R1.zh-CN.md)，结论 REVISE。
该结论对应[原文快照](reviews/CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN_R1_INPUT.zh-CN.md)，SHA256 为 478ccdca90ab094f1d2c2c7313307fa55c22a1f009130bb81e11f5e39674d822；不将原审查结论继承为本版通过。
文档所有权：本文件是当前修复提案；R1 报告与输入快照为历史审查证据；README 是状态索引；架构规范和旧冻结计划在实现前保持原样。

## 1. 决策与范围

曲线评分是结果分析 Agent 可选调用的确定性工具，不是每个实验必须经过的独立阶段。
实验前不检查评分配置、指标实现能力或曲线合同完整性，也不因此阻止 author 或执行。
实验计划仍须明确当前目标、实验对照、必须保存的原始输出及科学判断依据；参数、代码、数值执行条件及真实执行授权的检查保留。

目标路径：

实验设计及审查 → author／项目审查／授权执行 → 原始结果 → 结果分析（按需调用评分工具） → 下一轮设计。

评分请求在分析时形成，工具执行时才检查其输入、单位、采样与计算参数。
科学判断标准与计算实现分开：分析方法相对计划发生变化，分析结果必须记载变化、原因及结论限制。
不要求设计者预先选择已注册的 evaluator，亦不把文本中的 evaluator 名称视为已有软件实现。

本提案承接旧计划的局部目标、历史输入和跨轮续研能力，只调整曲线评分的职责和调用位置。
旧冻结计划及科学审查历史保留；旧科学计划 PASS 不等于本修复已通过工程验收。

## 2. 已核实的代码事实

| 位置 | 当前行为 | 修复含义 |
| --- | --- | --- |
| plugins/tcad_artifact/tcad_artifact/plugin.py：INITIAL_INPUTS | curve_contract 与 curve_contract_review 已为可选；执行 Effect 只要求 reviewed_package | 先验证无合同完整路径，不把“改为可选”当成待完成改动；发现真实隐藏约束才修对应位置 |
| plugins/curve_score/curve_score/science_operations.py：_diagnosis_operation | 分析必需合同、合同审查及 metric_report | 移除分析前置评分条件，改为绑定实际实验结果 |
| 同文件：_validate_diagnosis_against | 目标结论由 target-fit 指标及 complete_plan 报告约束 | 评分报告只能支持其实际覆盖的判断，不再代替整体科学判断 |
| plugins/curve_score/curve_score/curve_contract_compiler.py | 总体目标 observable 必须与本轮描述字符串相等 | 新分析工具不经过该目标编译路径；本轮不另造一套实验前目标映射合同 |
| plugins/tcad_artifact/tcad_artifact/curve_operations.py | PLX／日志规范化依赖预先存在的比较合同 | 解析实际输出与比较规则解耦，映射在结果产生后确定 |
| curve_score/schema.py 与 figure_evidence_normalizer.py | 简化曲线点仅保留 x/y，评分默认等距残差 | 原始参考表作为分析输入保留；不得把重采样残差称作原始行分组加权计算 |
| 曲线合同 Agent 提示与输出声明 | 要求报告缺口，却只接收完整合同 | 新路径由分析正式报告可分析部分与不可分析原因，不经失败合同交接 |

## 3. 分步修改

### P0：冻结基线，补真实入口反例

只读确认当前启动目录、已安装实现和工作树差异；保存计划对应的可复现工程证据。
使用已封存实验计划与现有 fixture，建立三个入口反例：

1. 没有曲线合同的科学 author → 项目审查 → 包装／执行预检是否能成立。
2. 有真实输出而没有 metric_report 时，结果分析目前因输入缺失被拒绝。
3. 评分不适用或输入不足时，是否仍能完成正式分析提交。

另固定 R1 的两组集成反例：不预先绑定 bundle 的原始 PLX 分析；无评分时错轮 review／错轮运行结果的拒绝。实施后的正例必须经对应真实入口，不以手工构造已解析 bundle 代替。

P0 不运行真实求解器，不以移除代码／参数／授权校验来使负例通过。
若 author 路径原本通过，则该处不改生产逻辑，只保留回归验证。

### P1：移除调度上的必经评分环节

修改 roles/scheduler.md 的源规则及其生成投影：
- 计划变化仍需相应实验与实现审查，但不自动创建曲线合同或安排评分。
- 结果分析可直接消费执行结果；只有实际分析需要时才调用评分。
- 评分缺项阻止相应定量结论，不阻止其他有效分析及后续重新设计。

核验 plugin.py、project_packager.py 及角色提示中的实际路径；仅删除已复现的评分前置要求。
保留项目输出声明，以实验 case、物理量、单位、时间点等描述输出，不要求使用评分比较生成的 series 名称。
原本满足这一行为的文件不修改。

验收：同一合法项目在有／无曲线合同两种情况下均可进入正确的项目审查和执行授权；错误计划绑定、缺少必要实现、未授权执行仍失败。

### P2：结果输入与曲线规范化解耦

**明确选择同一 Run 内组合工具，不选择“先结束分析，再由 Root 解析后重开”的交接方式。**

保留并调整通用 science.result.diagnose.v1；另由 TCAD 插件声明一个 public Agent Operation，拟定名 tcad.result.analyze.v1。
这是同一结果分析职责的 TCAD 领域入口，不是附加阶段：一次 TCAD 分析只调用该入口，不要求先后调用两种分析。
新增一个领域入口是 R1 数据流缺口所需的范围增量；名称以实施后启动编译目录为准。

接线固定为：

已绑定原始 PLX／日志、manifest、参考材料 → TCAD 分析 Agent 阅读并形成来源映射 → 同 Run 的 worker_tcad_curve_score → TCAD 解析函数 → curve_score 纯评分函数 → 工具记录 → 同 Run 正式分析提交。

- 在 tcad_artifact/result_analysis.py 中声明领域 Operation、窄组合 Worker 工具及领域上下文 validator；复用现有分析输出模型和科学提示的共同部分。
- 工具消费分析时给出的来源映射：绑定输入别名、manifest 输出名、case、物理量／列名、轴与单位，以及本次比较 spec。映射由 Agent 作出，不由 Root 预先选科学内容。
- TCAD 解析仍由现有 plx_normalizer／curve_normalizer 函数负责；提取 curve_operations.py 中可复用的纯解析与字节检查部分，不调用其独立 support Operation。
- 解析结果是同一调用中的内存 CurveBundle，直接交给评分函数；不创建新 Artifact、不追加 Run 输入、不引用其他 Run 的临时文件。
- 同一工具可消费显式列映射的原始 CSV 参考材料：在 analysis_tool.py 增加窄 CSV 列适配，读取指定 x/y 列与单位，不推断标签、不删除原始字段、不实现图证提取；不支持的布局返回 unsupported。原始参考材料保持绑定，不先强制规范化。
- 不评分时不调用组合工具，原始结果和日志仍可直接分析。缺少可用解析能力只影响相应定量结论。
- 依赖方向固定为 tcad_artifact → curve_score → 通用分析模型。TCAD 已声明 curve_score 依赖；curve_score 不导入 TCAD，也不新增核心动态服务发现机制。

**输入及交付上限：**

| 入口 | 必需输入 | 可选输入 |
| --- | --- | --- |
| 通用分析 | experiment_plan 1、experiment_review 1、experiment_results 1—4 | reference_material 0—8、current_progress 0—4、curve_bundle 0—1、metric_report 0—1 |
| TCAD 分析 | experiment_plan 1、experiment_review 1、reviewed_package 1、runtime_manifest 1 | runtime_attestation 0—1、solver_outputs 0—32、reference_material 0—8、current_progress 0—4 |

TCAD manifest、attestation 和每个原始文件分别显式绑定，不能把“运行报告一件”当成其所有子 Artifact 已交付。
TCAD 总输入上限 512 MiB；package 上限 64 MiB，manifest／attestation 各 4 MiB，单原始输出 32 MiB、单参考材料 16 MiB；已有更小 schema 限制仍生效。八工况及其日志按实际文件数计入 32 件。
缺失或未绑定输出只允许形成相应受限分析；不得隐式读存储、默默截断必需输出或推断其内容。若真实案例超限，先明确指出具体文件与有界调整，不将所有上限无条件放大。
采用已有通配 schema／媒体类型 inventory 声明与受控逐项读取，不照搬 curve_score 当前固定 JSON 的 _input helper。
本轮不扩展 CurvePoint 的科学字段，不改变旧显式 support transform 的调用协议；新路径复用其底层函数即可。

### P2a：所有分析路径的确切身份校验

新分析 Operation 明确注册窄 guard；不得假设端口名称自动产生身份保证。

1. **计划—审查：**在 preflight／invoke 共用的 guard 中检查 experiment_review 的 parent_refs 含确切 plan.ref，并检查正式 verdict 为 pass；沿用既有 producer／独立审查资格规则。即使 review 保持 handoff_only，该关系仍通过 BoundInput 元数据检查，不将 handoff_only 偷塞进 context_sources。
2. **TCAD 计划—执行：**guard 检查 reviewed_package 的直接父包含绑定计划、runtime_manifest 的父包含该 package；复用 runtime_parentage 的同执行父集合规则检查每个已绑定 solver_output。若有 runtime_attestation，其父必须包含同一 package、manifest 及它实际审计的输出；本 Run 未绑定的审计输入不得被视为已读文件。
3. **TCAD 字节—case：**最终领域 validator 对每个绑定文件核对 manifest 的 name／媒体类型／size／sha256，利用 package.project 的输出声明及 case 绑定检查分析引用。评分映射不能覆盖这些事实。manifest 本身没有 case 字段，不能仅凭 Agent 自报 case 完成核验。
4. **通用结果：**本轮 experiment_results 只接受 parent_refs 直接包含确切计划的正式结果；没有这一关系的材料只能放 reference_material／current_progress，并明确属于背景。TCAD 原始输出应走上述领域入口，不能借通用入口绕过执行归属检查；本轮不新增通用递归血缘推断器。
5. **失败运行：**manifest 的 failed／cancelled、attestation 的 fail 不构成分析准入拒绝。身份正确的失败运行可分析且允许 solver_outputs 为空；但不得将它表述为完整成功结果。缺少 case 输出时只能对已证实部分下结论。

parentage 检查由输入 guard 拥有；字节及分析引用的一致性由输出 context validator 拥有，与是否调用评分无关。
需要的 plan、package、manifest、outputs、参考材料均采用可供 validator 读取的声明 exposure，并列入相应 context_sources；不读取未绑定父对象或核心数据库。
为相似两轮实验增加错轮 review、错轮 manifest、错 case／篡改输出、合法失败运行的无评分提交反例。

### P3：将评分函数封装成结果分析 Worker 工具

新增 curve_score/analysis_tool.py，并在现有 science.result.diagnose.v1 的新操作版本中注册 WorkerToolDefinition。
复用现有确定性评分代码，不让 Root 另建评分 Run，不通过 Worker 调 Root MCP。
通用工具处理已绑定的标准曲线／受支持表格；TCAD 组合工具复用同一纯请求校验与评分函数，额外负责 P2 的原始输出解析。两者的组件声明、工具引用、语义合同、生成 Worker 配置一并更新。

工具请求：
- 只能引用该 Run 已绑定／受控读取的数据；
- Agent 在分析时选择 series、case、区间、单位、采样与受支持指标；
- 采用现有比较 spec／算子结构能表达的最小请求，不要求总体目标文本相等、实验前合同或合同审查；
- 对不支持的指标明确返回 unsupported；不得静默改成 RMS。
首版不新增通用脚本执行平台、不把当前案例所有特殊统计硬编码进核心。
现有 CurveComparisonSpec 的纯探索比较不能直接通过其 required 约束时，首版明确返回 unsupported；不把探索比较伪装成必须通过的科学门槛。

工具响应分为 computed、unavailable、unsupported、error，携带明确原因和影响的比较项。
返回确定性计算记录：所用输入、请求、指标值／状态及算法版本；它不是科学结论。
同一 Run 可在预算内修正请求，但保留实际用于最终结论的记录，不能以成功状态掩盖未计算项。

计算记录明确嵌入 LayeredDiagnosisReport 的可选 calculation_records 字段，不新建外层包装，保持现有 codec 与下一轮 reader。
每条记录包含输入别名／内容摘要、解析映射（如有）、比较请求、算法版本、状态、标量结果或原因码。来源身份由控制端与绑定 bytes 核验，不依赖 Agent 自报。
通用最终 validator 从绑定 bundle／表格重算；TCAD 最终 validator 从同一批原始 bytes 重新解析并评分。内存 bundle 不必成为新输入或永久文件，重放链在单一正式输出内闭合。

记录的核验与上限固定为：
- computed：重放完整请求，逐项核验确定性结果；篡改数值或映射对应关系拒绝提交。
- unavailable／unsupported：重新验证确定性的缺项或能力原因；这类记录允许正式受限分析，不要求造出数值。
- error：仅表示调用未完成，不是科学依据；校验请求身份及“无可用数值”，不要求第二次复现同一超时或瞬时异常，也不允许它支持成功结论。执行日志负责工程异常事实，结果中的 error 不被提升为经验证的物理失败。
- 每次分析最多保留 8 条用于正式结论的计算记录、每条最多 16 个比较、每比较最多 4096 个采样点；控制单次工具响应不超过 32 KiB，analysis 主输出仍不超过 128 KiB。返回聚合结果与可重放请求，不嵌入原始曲线或每个采样点。
- 工具和最终重放使用同一解析／比较上限；工具调用最多使用剩余预算的一半，并预留最终重放所需时间。实施测试必须覆盖接近上限的真实解析与提交，不仅检查 schema 字节。
- 若重放不能在预算内完成，不能将 computed 记录作为已验证证据；Agent 可移除对该数值的依赖并提交受限分析。已有确定性 computed 值不得以 error 标签绕过校验继续引用。

不新增核心数据库表、状态、跨 Run 临时文件引用或运行时输入追加。

工具只有调用时才检查所需数据。没有调用工具是正常路径，不是隐含错误。
原始行加权、跨工况派生等目前不支持的算法必须如实报告，不用现有等距 RMS 冒充。
扩充此类算法属于后续按真实分析需求作出的有界工具增量，不是实验启动条件。

### P4：分析提交与结论校验不再依赖评分齐全

修改 science_operations.py 中的分析提示、输入声明、上下文校验和语义合同。
沿用 LayeredDiagnosisReport 及现有提交机制；仅在必要处增加可选计算记录／方法变更字段，不创建第二套分析状态机。

分析必须：
- 指明实际分析的 experiment／case、当前目标、已使用证据与结果；
- 分别说明有效发现、不可判断项、所缺条件、仍未完成的总体目标；
- 使用评分时准确引用核验后的记录；未评分时不得宣称已通过定量比较；
- 观测计算不可用可完成正式 inconclusive／受限分析；执行／数值前提无效按现有门状态生成 invalid_study，不将所有失败硬写成同一 verdict；不要求先生成完整评分报告；
- 支持定量结论和非曲线证据判断，但任何主张都必须有相应证据；
- 记录分析方法相对计划的变化，不得在看到结果后无说明地换有利指标。

移除“整体科学结论等于全部 target-fit 状态”的派生逻辑。
保留证据引用、实验身份、方法与结果一致性等机械检查，以及已有科学结果模型的有效约束。
没有评分不等于失败，也不等于成功；由分析 Agent 说明哪些判断可以成立。
必要定量比较未完成时，不能宣称该比较成功或总体目标闭合。
新版分析取消旧 _diagnosis_context 中“残差失败必须另走 curve-error diagnosis”的强制跳转；旧显式操作保留，但本轮分析可就地解释已计算结果及限制。
分别提供“执行有效但观测计算不可用”和“执行失败／数值无效”的合法 LayeredDiagnosisReport fixture，验证现有 gates 与 verdict 派生规则。

下一轮设计继续通过已有 result_analysis / experiment_results / current_progress 端口读取封存结果。
不新增阶段实体、结果审查状态机或全局“所有目标覆盖”门槛。

### P5：兼容、安装与真实续研

旧合同、评分报告和操作历史保留，不追认旧资格。
旧合同设计／审查操作退出默认研究必经路径；首版不为删除旧代码扩充改动范围。
旧显式评分 helper 可保留作为兼容工具，但新分析不得要求调度者先运行它。

更改操作合同后正常更新版本／digest 和生成的 Worker 配置。TCAD 新入口注册到已有插件目录；源码和安装版都验证两个分析入口不是串行依赖，禁用 TCAD 插件后通用分析仍能编译并运行。
仅调整受影响的中英文架构／安装说明和计划索引；不改写历史审查结果。
安装后核对新 Operation 目录、工具列表、输入端口及生成角色，不仅测试源码直接调用。
如升级导致旧科学输入资格失效，明确记录并沿既有资格路径处理，不临时绕过身份检查。

## 4. 文件范围

必需修改：

- plugins/curve_score/curve_score/science_operations.py：分析入口、工具注册、提示、结果上下文校验。
- plugins/curve_score/curve_score/analysis_tool.py：新增窄评分工具适配器、CSV 列适配与可重放请求；提供供 TCAD 调用的纯函数。
- plugins/tcad_artifact/tcad_artifact/result_analysis.py：新增领域分析声明、组合工具、身份 guard 与最终解析／评分重放校验。
- plugins/tcad_artifact/tcad_artifact/plugin.py：注册上述 Operation 和组件；不改其本已可选的 author 合同端口。
- plugins/tcad_artifact/tcad_artifact/curve_operations.py：提取可共享的纯解析／字节核验函数，新工具绕开合同依赖；旧 support 协议保留。
- src/scidiscovery/artifact_agent/schema/layered_diagnosis.py：仅必要的可选计算记录／方法说明字段。
- roles/scheduler.md 及生成规则涉及的 AGENTS.md 投影：调度职责调整。
- 相应现有测试、局部新回归用例、中英文架构说明、计划索引。

条件修改，必须有 P0／集成用例证明必要：

- project_packager.py、author／review 提示：只修真实隐藏依赖；若现有声明不能唯一建立输出—case 对应，只补实际缺失的关联，不借评分合同生成名推断。
- curve_score/schema.py：仅工具入口复用或必要记录类型，不改既有残差数值语义。
- curve_score 的组件注册文件及安装 fixture：仅新工具和新版输入编译所需。
- 图证正规化、核心 Run／数据库／审批实现默认不改。

不得为了固定文件数量省略跨接口必要修复；任何范围增加应说明具体反例与必要性。

## 5. 验收矩阵

| 用例 | 必须结果 |
| --- | --- |
| 合法实验不绑定曲线合同 | author、项目审查和授权执行路径可达 |
| 结果分析不调用评分 | 有界分析可通过 worker_submit_result 正式封存 |
| 安装版 TCAD Worker 仅绑定原始 PLX、运行证明和原始 CSV，不绑定 bundle | Agent 在分析中给出映射，组合工具解析并评分，同 Run 封存且 validator 从原始 bytes 重放成功 |
| 八工况与日志分别作为多项输入，或缺少部分原始输出 | 文件数／总字节限额真实生效；缺少项准确标明，不从 manifest 隐式读取子对象 |
| 分析按需调用标准残差工具 | 与原评分实现对同一显式请求的数值一致，记录可复算 |
| 没有参考曲线／指标不受支持 | 正式报告缺项，仍完成分析；不自动回到实验前合同循环 |
| 无可用解析工具／未知格式／纯探索请求不被支持 | 无需提前准备数据或重开分析；不依赖该计算仍可提交受限结论 |
| 请求单位错、数据缺列或区间不可用 | 工具返回具体问题；只影响相关计算和结论 |
| Agent 篡改计算数值／绑定另一个 case | 提交校验拒绝，不能成为可信证据 |
| 无评分路径绑定计划 A、审查 B 或运行 B | 在规定 guard 拒绝错轮输入；没有评分不是身份检查例外 |
| 身份正确的 failed／cancelled manifest，零个输出或失败 attestation | 可进入分析并提交符合现有门规则的 invalid_study／受限报告，不伪装成功曲线 |
| 调用超时与确定性 unsupported | 超时不要求重现；unsupported 可重放核验；二者均不能支持数值成功结论 |
| 接近记录／采样／字节／时间上限 | 工具与提交核验一致有界，单主输出可封存，不出现工具成功而必然无法提交 |
| 未完成必要定量比较 | 不得声称该目标比较成功或总体闭合 |
| 合法负面／部分分析 | 新设计 Agent 不继承聊天，也能读取发现、限制和后续条件 |
| 错误来源、必要实现缺失、未授权执行 | 原有相关操作拒绝保持有效 |
| 安装版 Operation 与 Worker | 工具和端口可见性与实际能力一致，不依赖旧生成配置 |
| 移除 TCAD 插件，仅使用标准 bundle | 通用结果分析仍可用，不存在 curve_score → TCAD 的反向依赖 |

优先现有 tests/operations/test_m2_curve_analysis_boundary.py、test_l4_local_tcad.py、
test_invoke_preflight.py、test_agent_contract_alignment.py、test_catalog_installed_entrypoint.py、
test_m5_plugin_ownership_and_default_surface.py 的相关用例，并补一条真实 Worker 工具→提交→下一轮输入集成验证。
新 TCAD 路径的集成用例必须从原始文件起步，覆盖 guard、工具、最终重放和封存，不只调用底层纯函数。
先跑增量用例和目录／插件边界检查；已知旧全套失败单独归因，不降低门槛或宣称全绿。

## 6. 当前案例接续标准

当前已通过的 Fig.4 实验计划用于验证无曲线合同的实施路径；是否满足实现所需参数与能力，由对应 author／独立项目审查判断。
取得新执行结果后，分析 Agent 决定是否调用评分工具。
若当前专门统计仍不受工具支持，应封存确切计算缺口与可成立的分析，不退回伪造合同，也不把研究记为成功完成。
“分析可以完成并给出下一步”是本修复的工程验收；“科学假设已得到定量结论”是另一个必须用真实结果证明的标准。
至少证明一次新执行结果进入分析、分析进入下一轮设计；仅目录变更或 fixture 通过不能代替这一点。

## 7. 对 R1 的修订对应

| 审查事项 | 本版明确处理 |
| --- | --- |
| R1：原始输出到同 Run 评分未接通 | P2 选择 TCAD 所有的分析入口与组合工具；绑定全部 bytes，解析结果只作内存中间量；P3 从原始输入重放 |
| R2：无评分路径缺少确切身份校验 | P2a 明确 plan-review、package-manifest-output、字节及 case 检查的位置；失败运行与错轮身份分开处理 |
| 原始媒体与输入件数 | P2 分开 typed 运行见证和 0—32 原始输出，使用 inventory 与明确字节限额 |
| 单主输出／瞬时 error／计算预算 | P3 固定嵌入已有报告模型，按状态校验并限制记录、采样和时间 |
| 旧诊断跳转与 verdict 约束 | P4 取消强制 curve-error 跳转，保留合法门状态并增加两类提交 fixture |
| 插件依赖及安装路径 | P2 只沿既有 TCAD → curve_score 依赖；P5 与验收矩阵覆盖禁用插件、原始文件起点和安装版 Worker |

以上是计划修订，不是已通过实施验证。R1 原报告保持不变，本版必须单独复审，不能以“已回应”代替 PASS。
