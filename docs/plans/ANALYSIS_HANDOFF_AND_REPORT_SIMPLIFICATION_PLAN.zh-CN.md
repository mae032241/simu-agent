# 分析接手视图与正式报告简化修订计划 R0

日期：2026-09-13。状态更新于2026-09-14：独立计划审查 PASS，P0—P4 源码实施与限定工程验证完成，[独立实现审查 PASS](evidence/analysis-handoff-report-simplification/IMPLEMENTATION_REVIEW_R0.zh-CN.md)；已安装并完成[真实简版分析交付与下一轮设计预检](evidence/analysis-handoff-report-simplification/LIVE_ACCEPTANCE.zh-CN.md)。现场阅读量与详细错误正文仍有 Root 可见性限制，不宣称普遍提速或总体科学目标完成。详见 [实施记录](evidence/analysis-handoff-report-simplification/IMPLEMENTATION.zh-CN.md)。

通过范围见 [独立审查 R0](evidence/analysis-handoff-report-simplification/PLAN_REVIEW_R0.zh-CN.md)。审查冻结的 R0 摘要记录于该报告；以下实施内容保持不变。基线快照与串行检查记录见同目录 evidence。验收限定实际支持的 local backend，不声称 hardened 分析已通过。

## 1. 第一原则与完成目标

**完整记录保留供追溯，接手时提供紧凑的任务视图；科学结论集中表达，其他位置引用它。**

本轮解决两条已发生的路径：
1. 分析者接手时，先获得本轮目标、案例差异、实际产物与分析规则的位置，默认阅读材料不包含控制生成的 case_parameter_bindings 明细。
2. 分析者完成计算后，集中提交结论、证据、限制与剩余问题，无需重写六层诊断、重复科学摘要或机械引用表。

范围是现有分析角色的共享入口、TCAD 的项目阅读视图，以及共用 LayeredDiagnosisReport 的生产/消费路径。
不扩展到全部科研对象格式，不新增 Operation、工具、Agent、状态机、数据库、通用投影注册表或科学判定器。
保持原始绑定、独立审查、授权执行、结果封存和工具收据机制；不得用本轮简化重新引入输入资格复查、案例登记、逐项覆盖或字数型提交门槛。

## 2. 已定位依据与证据边界

工程基线见 [BASELINE.json](evidence/analysis-handoff-report-simplification/BASELINE.json)，由已完成 Run 的受控记录与现行源码结构核对得到。

- 本轮分析：fig4_shape_basis_analysis_1，842 秒完成、零提交拒绝。成功归约调用约 1.66 秒；发布与提交工具各约 0.55 秒。
- 24 个绑定输入共约 2.50 MB；多数是可按需读取的数据文件，不能等同于全部进入模型上下文。
- reviewed_package 为 122,995 字节；作者结果中的 156 条控制生成案例绑定约 103 KB，源码文件内容及包装约 8.5 KB。
- plan 为 99,856 字节；两提案的 required_observables 在比较合同中各重复一份，重复量约 9.8 KB；共有 156 个逐案例变量期望。
- 现有 analysis-start.json 有 24 KiB 上限和逐字来源指针，但计划摘录仅覆盖目标、当前目标、停止条件等，缺少案例、比较合同和 validation_plans 的实用索引。
- 正式分析约 16.6 KB，其中六层 gates 约 4.4 KB；另有总体、目标、假设、剩余矛盾及 handoff 的多处叙述。
- 已实现引用自动补全，不能把封存后的 13 条 source_references 认定为 Agent 手抄。
- 控制记录尚不能分解阅读、推理、代码生成、平台等待；不得把所有等待时间归因于长材料或填表。

当前源码基点 HEAD 为 be5da77acdbf98054e0b096fc4e940de560d4ba1，工作树含大量此前已部署改动。
实施时须对本轮涉及文件保存精确内容与摘要，不把整个 dirty diff 当成本轮增量。

## 3. 规范归属与承接关系

| 现有文档/机制 | 本轮关系 |
| --- | --- |
| analysis-continuation-minimal/PLAN_R1 的精简入口与案例投影 | 部分承接：扩充阅读索引、减少机械明细展示；恢复、身份与原始证据规则继续有效 |
| registration-diagnostics-repair/PLAN 的机械补全与失败追溯 | 保持；本轮不重建引用映射或错误协议 |
| 当前 ARCHITECTURE 中科学判断归 Agent、身份与封存归控制层 | 保持；实施后仅更新受影响的中英文章节 |
| 本计划及 BASELINE.json | 分别为待实施提案和限定范围的工程基线，不代表部署或科学资格 |

旧审查、旧计划和已封存研究结果保持原样。本计划通过、实施及验收状态分别记录，不能互相替代。

## 4. P1：把“完整原件可读”与“默认接手材料”分开

复用 curve_score.analysis_workspace 的 analysis-start.json、既有 domain-workspace.json 及 TCAD analysis-bindings.json。
不改变 Run 绑定或把裁剪后的 JSON 冒充原 Artifact。

### 4.1 共享入口

在既有输入索引中提供文件大小、端口用途、可用阅读视图与原件位置。保留源 alias 和精确 JSON 指针。
对已支持的实验计划补充结构索引：

- 原始总体目标、本轮目标及后续目标的位置；
- 提案/案例名、数量，以及 comparison_contract、validation_plans、方法和判定条件的位置；
- 当前结果、既往分析及恢复记录分别列明来源，不能选“最新”替换绑定；
- 数据表、图片、日志列为程序或按需查阅材料，避免要求打印全文。

索引只摘录、定位或按结构无损整理已有字段，不概括新科学事实、不决定科学重要性、不推断阶段。
长公式、阈值和方法不能依靠截断摘录执行；入口必须给出读取完整原字段的路径。
未知 schema 或超出视图预算时保留原件索引与明确遗漏说明，不新增准入/提交拒绝。

### 4.2 TCAD 项目与案例视图

在现有 analysis-bindings.json 扩充确定性阅读视图，默认展示：

- solver/profile、入口、源码文件索引及原文位置；
- 明确声明的产物及已有来源对应关系；
- 原计划中的案例配置，以变量表和案例值矩阵表达，避免逐案例重复长描述；
- 已有实现审查及执行状态记录的引用，必要摘要保持原文。

**默认视图不展开 case_parameter_bindings、重复哈希、源码行号证明明细和控制物化回执。**
需要核对实现时定位真实源码和科学参数；控制绑定表不能替代独立物理实现审查。

本轮不改 156 条控制记录的存储、生成与服务端消费，也不改计划的归档格式。
原件保留在既有冻结输入中用于按需追溯；这是阅读路径简化，不新增 native 后端的文件访问安全边界。
视图不成为新 Artifact 或证据来源：科学引用仍指向原绑定 alias/原文位置，工具仍消费完整冻结输入及原始收据。

### 4.3 阅读行为同步

共享分析 guidance 和 Codex 平台指令统一为“先读入口和本轮必要字段，按需追原件”。
将复用 Agent 时的“reread all current inputs”改为核对新绑定并读取本轮必要材料；不允许旧记忆替代当前证据。
继续要求实际调用前阅读该工具的完整合同，但不要求读取所有工具合同。
已有旧工作区没有新视图时，沿用原件与现有索引，不修改旧 Run 文件。

## 5. P2：正式分析以四项内容为主

继续使用 scidiscovery.layered-diagnosis.v1，作向后兼容的字段放宽，不新建并行报告类型。

| 内容 | 现有字段处理 |
| --- | --- |
| 本轮结论 | summary + overall_verdict；结论集中写一次 |
| 关键证据 | 沿用 evidence/已有证据引用；详细数字、图、脚本保存在受控证据文件 |
| 限制与异常 | 增加可选 limitations 文本列表；只写影响结论范围的问题 |
| 剩余问题及建议 | 沿用 remaining_contradiction、next_action，允许无剩余问题时省略 |

具体调整：
1. gates 改为整体可选，旧完整 ScientificGateSequence 原样可读；新报告通过 limitations 说明单项有效性问题，无需为一个问题补写其余五层。
2. objective_assessment、hypothesis_assessments、analysis_method、method_changes 保持可选，只有独立目标/假设处置、方法选择或实际变更需要展开时才写。
3. 不根据 gates 是否缺省、某一数值是否通过自动生成或改写科学结论。省略诊断层不表示该层 pass。
4. 保留 claim_allowed 这一现有显式科学判断，避免扩大声明授权语义改造；不得从 overall_verdict 自动推导它。
5. experiment_key/plan_key 等现有身份仍只表达一次。已有机械引用补全继续工作；多提案下的科学对象选择不能由控制层猜测。
6. 新工具结果仍直接引用 calculation_ref；原始数组、完整请求、哈希、回执不搬入报告。
7. 不设“必须四段”“必须多少字”“必须覆盖全部目标/诊断层”的新校验。简洁是角色要求，来源真实性、输出类型和明确引用冲突仍按既有职责处理。

## 6. P3：交接复用正式结论，补齐消费端

### 6.1 共用现有 finalizer 生成交接

在既有 result_materialization 增加限定于 LayeredDiagnosisReport 的机械交接补全，供通用分析 finalizer 与 TCAD finalizer 共用。
Agent 可省略 handoff 的重复摘要和状态；正式报告的科学字段是唯一来源：

- handoff.verdict 复用明确 overall_verdict 的固定兼容映射：pass→pass，fail/invalid_study→blocked，inconclusive→inconclusive；
- handoff.summary 使用指向 payload.summary 的明确短引用，不复制或截断长结论；Root 继续一起读取 sealed_output 和 scheduler_signal；
- 后续科学建议读取 payload.next_action；不再要求独立 handoff.next_actions 复述；
- 新提交若仍带旧格式 handoff，保留完整记录的可读性；新分析的重复结论字段由 finalizer 按正式 payload 规范化，不覆盖其余未重复的说明。

这里只投影已有科学字段，不创造结论、不授予执行权限、不决定下一 Operation。
输出 Schema 描述封存结果；提示和 workspace 现有 patch_contract 必须明确哪些字段由 finalizer 补齐。
验证必须走“Agent 草稿→finalizer→封存 Schema”，不能用封存格式拒绝尚未补全机械字段的草稿。
不修改其他角色的 handoff 规则。

### 6.2 声明与下游消费

- schema/claim.py：明确支持 gates 缺省的 LayeredDiagnosisReport；缺少 numerical_validity 时 numerical_verdict 为既有 not_evaluable，不能抛 TypeError，也不能补 pass。
- 原 overall_verdict 与 claim_allowed 保留；未知报告类型的处理保持明确，不用通用静默 fallback。
- 检查通用结果分析、TCAD 分析、可选曲线误差分析的共享 Schema/提示/最终化连接。
- 新报告作为 current_progress/prior_analysis 进入下一轮设计或分析时，无 gates、无重复 handoff 摘要仍可读取和正常预检。
- 新增 limitations 进入共享精简入口的可追溯摘录。
- 历史 Artifact 字节、旧计划资格和旧 Run 的编译合同不迁移、不重写；新增 Run 使用重新编译的当前合同。

## 7. 最小代码范围与顺序

| 顺序 | 预期责任文件 | 变更 |
| --- | --- | --- |
| P0 | 本轮基线/实施记录 | 保存涉及文件快照、记录已有失败及本案输入/输出规模 |
| P1a | plugins/curve_score/curve_score/analysis_workspace.py | 共用输入大小/用途/方法索引、阅读指导 |
| P1b | plugins/tcad_artifact/tcad_artifact/analysis_bindings.py | 扩充现有 TCAD 阅读视图，隐藏默认机械明细；复用既有映射 |
| P2 | src/scidiscovery/artifact_agent/schema/layered_diagnosis.py | gates 可选、limitations 可选、无剩余问题字段可省略 |
| P3a | src/scidiscovery/artifact_agent/service/result_materialization.py | 共用分析 handoff 机械补全 |
| P3b | src/scidiscovery/artifact_agent/schema/claim.py | 缺诊断层的兼容消费 |
| P3c | plugins/curve_score/curve_score/science_operations.py；plugins/tcad_artifact/tcad_artifact/result_analysis.py | 同步报告与阅读要求、接线、已编译合同说明 |
| P3d | src/scidiscovery/platforms/codex.py | 纠正复用时全量重读要求 |
| P4 | 既有所属测试、相关架构段落及计划索引 | 真实入口验证、兼容与部署说明 |

预计 8 个生产文件。不得直接修改自动生成的 Agent 配置、另建工具协议、重新设计完整计划模型或重构输入物化。
如果既有 patch_contract 不能准确表达 finalizer 的生成字段，应在计划复审时明确最小增量，不能用隐藏提示例外解决合同冲突。

## 8. 验收矩阵与资源限制

测试全部串行，复用既有 512 MiB 进程树/地址空间、单批 150 秒、BLAS/OMP 单线程的受限检查方式。
使用既有测试文件增加必要用例，最多一个集中新测试文件；不跑全量套件，不进行并发测试，不为断言字符串变化建立大矩阵。

必须覆盖：
1. 默认入口/视图不含控制绑定明细；本案 156 条原记录及原始源码仍原样保留，工具读取来源未变。
2. 案例参数矩阵逐值对应原计划；同一 observable 文本只展示一份；原字段指针均可解析。
3. 核心方法、阈值、单位、当前/后续目标能完整追溯；视图溢出/未知字段不会默默丢失或阻止工作。
4. 精简入口缺省的旧工作区、新 Run、已有恢复副本均能继续；恢复保全行为保持。
5. 简版报告不含 gates、额外目标/假设摘要或手工引用表，仍可从真实 Worker/MCP 提交到 completed。
6. handoff 可由 finalizer 补全，长 summary 不触发机械截断或额外提交拒绝；完整结论从 sealed_output 可读。
7. 旧完整报告、有限结论、负面结论、无评分、运行失败/缺产物报告均可读；缺 gates 不变成通过或输入阻断。
8. claim projection、当前进度、prior_analysis+其精确 manifest 的消费路径接受简版；旧收据身份与历史资格规则保持。
9. 保留真实负例：引用未绑定来源、冒用不同执行、篡改受控收据仍在既有责任层被拒绝，输出拒绝有准确位置。
10. 编译实际生产目录并做隔离 wheel/stdio 验证，确认 Schema、提示、workspace、finalizer 和消费者来自同一安装版本。不同共享分析 Operation 均覆盖，不能只验证 TCAD 纯函数。

优先测试入口：test_analysis_continuation.py、test_analysis_claim_scope.py、test_analysis_artifact_references.py、
test_tcad_result_analysis.py、test_collector_analysis_handoff.py，及现有声明投影/安装编译测试。
实施者先按精确 diff 选择必要用例，记录每批退出码、耗时、RSS 和失败；既有失败与本轮回归分开。

## 9. 真实 Agent 验收与完成标准

安装后，使用本轮已封存 Fig.4 原执行、12 条曲线、参考数据和对应分析证据，开一个新的受控分析 Run。
不重新执行 TCAD，不新增科学实验或改变已审查的比较规则。
可复用已完成数值，目的是验证新 Agent 只凭绑定记录、紧凑视图和简化报告完成交付。

记录：默认阅读材料字节数、原件追查情况、首个有效分析动作、发布到提交时长、实际计算是否重复、所有运行错误/拒绝及日志可见范围。
现有观测不能识别的耗时明确标注，不为本轮新增一套 telemetry；不把进程 stdout 字节当作模型实际 token。

工程验收目标：
- 本案默认首读入口及紧凑视图合计目标不超过 32 KiB，控制绑定明细为零；这是效果指标，不是运行拒绝门槛。
- 报告无强制六层表格和重复 handoff 叙述；详细证据独立保留，最终结论及其限制不丢失。
- 新简版报告完成提交并能进入下一轮设计预检；历史完整报告保持可读。
- 单轮实际耗时与读取量如实对比，不以测试通过或字节减少宣称已证明普遍提速。

完成顺序：计划审查与必要修订→冻结通过范围→按 P0—P4 实施→独立实现审查→用户安装→真实 Agent 验收。
用户已授权通过审查后实施；安装与真实 Agent 验收分别记录，不将工程测试标记为真实运行通过。
