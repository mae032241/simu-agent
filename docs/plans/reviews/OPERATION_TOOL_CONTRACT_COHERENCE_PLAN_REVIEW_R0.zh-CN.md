# Operation 与工具契约一致性修复计划 R0 独立审查

日期：2026-09-11。结论：**REVISE**。

目标定位正确：应修正类型契约、错误分类、证据到案例的交接和分析输出约束，不能由一次坏请求推导 PLX 能力缺失，也不应先改科学目标或重跑求解器。复用既有编译目录、输入用途、活动记录和证据清单的方向符合最小改动原则。但 R0 仍有五项必须明确的接口决定；其中前三项直接影响真实阻断的解除，后两项影响“共享消费者与全部已安装接口一致”的完成声明。不能仅把它们留为 P0 待发现问题后批准实施。

## 1. 审查基线和方法

- 审查对象：`docs/plans/OPERATION_TOOL_CONTRACT_COHERENCE_REPAIR_PLAN.zh-CN.md`，R0，196 行。
- 计划 SHA256：`99e8a285a796b5fec2165ab6c882e009b42efd09a2d3056ba5cb9e1dabb72da9`。开始和结束读取一致。
- 背景报告：`docs/plans/reviews/TCAD_ANALYSIS_3_BLOCKER_ROOT_CAUSE.zh-CN.md`；SHA256：`96eee592a2c2b2403a39259caa3b6ff84db50193a4d4cd3defeb1b3c323606f3`。
- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树已有大量修改，计划为未跟踪文件。本审查核对读取时的工作树，没有把 HEAD 视为计划实施基线，也没有把既有修改归入本计划。
- 已读取仓库 `AGENTS.md`、跨边界审查技能及相关当前架构条款。按本次明确授权只做工程计划审查；未调度科研 Operation，未读取科研状态、工作区或原执行产物，未调用 `worker_*`。
- 方法：文档与源码静态追踪，核对生产入口及测试实际经过的边界。未运行 pytest、其他测试、目录编译、安装、wheel 构建或求解器。以下“可达场景”是源码推导，不能当作本轮动态复现结果。

## 2. 必须补齐的阻断项

### R1 · P1：公共错误详情没有覆盖最外层 MCP 和 Root 业务包装

**计划位置：**第 5 节 P1，主要位置及修改 1—6、验收；第 9 节 P5.2/P5.5；第 12 节生产修改范围。

**源码证据：**

- `src/scidiscovery/artifact_agent/interfaces/mcp.py:39–64`：所有入口外面还有 `MCPRouter.handle`。正常字典返回统一为 `isError=False`；异常统一成为仅含 `code=-32000` 和 `message=str(error)` 的 JSON-RPC 错误，没有结构化详情通道。
- `interfaces/mcp_worker_protocol.py:14–15` 的 `WorkerToolError` 没有详情字段；`interfaces/mcp_root.py:392–396`、`mcp_local_worker.py:87–90`、`mcp_hardened_worker.py:98–101` 分别把 ValidationError 转成字符串。
- `interfaces/mcp_root_operation_routes.py:221–224` 将已有 `OperationInvocationError` 再转为只保留 reason_code 的 `RootToolError`，port/field 在到达公共传输层前已丢失；`:887–890` 对 Transform 异常另有字符串包装。Effect 准备与 Approval 投影也有独立分类分支，分别见 `:820–827`、`:472–477`。
- 输出错误还有 `operation_declaration.py:82–94` 的中间转换：ValidationError 已经被转成 SemanticRuleViolation 字符串，`service/run_outputs.py:268–278` 无法再获得原字段列表。

**可达场景与影响：**即使按 P1 在三个 router 中构造同一详情对象，正常异常路径仍可能在 Root facade 或 MCP 最外层丢失。直接调用 router 的单元测试可绿，模型实际收到的仍是粗粒度字符串；若改成返回诊断字典规避异常，又会被标为工具成功。输出聚合诊断也不能只在末端恢复已经丢失的字段。P1 的“同义字段诊断”和安全脱敏不能因此成立。

**最小修订：**把 `mcp.py`、`mcp_worker_protocol.py`、Root Operation/执行路由的现有错误包装列为明确接线范围；确定共享错误如何穿过 facade、异常对象和 JSON-RPC/MCP，选择保留既有错误信封并增加有界详情等单一方案。不要增加成功返回状态机。明确预检返回、invoke 异常、Worker 参数拒绝、提交拒绝、未知异常各自的映射，并让中间转换保留原安全详情。现有 `reason_code/port/field` 不重复造另一权威。

**应补验收：**必须经实际 `MCPRouter.handle(tools/call)` 检查字段、错误标志及脱敏；覆盖 Root 参数错误、preflight/invoke 同一错误绑定、Local/Hardened 参数错误和提交语义错误。至少一个 Transform/Approval/Effect 的负例确实经过其业务分支，不能只在最外层放一个错误字段就算覆盖。

### R2 · P1：案例补充映射缺少调用前、封存后及纠正时的完整身份协议

**计划位置：**第 7 节 P3.2—P3.5、P3.7；第 6 节 P2.1—P2.2；第 10 节 P6.3—P6.5。

**源码证据：**

- `plugins/curve_score/curve_score/analysis_tool.py:221–244` 的评分工具只从 request 取得别名并读取原字节；`plugins/tcad_artifact/tcad_artifact/result_analysis.py:184–185` 直接复用它。工具没有读取尚未提交报告的协议。
- `artifact_agent/operation_tool_context.py:29–49`、`interfaces/mcp_local_worker.py:233–269`：`context.evidence()` 提供本 Run 接收记录；常规输入只提供读字节和 input_ref 等能力。它不会自动把 prior analysis 中的映射变成当前评分上下文。
- `result_analysis.py:202–214` 只读取两个恢复清单；`:427–438` 没有独立 prior-analysis 输入端口，只有可复用的 `current_progress`。单说“绑定封存分析”还未定义从该端口定位与验证映射的方式。
- `operations/invoke.py:165–174` 的输入别名随同端口数量和顺序变化。`service/runs.py:952–964`、`service/tool_evidence.py:44–58` 只为恢复清单中的 Artifact 恢复旧别名；原先已注册文件的报告引用没有同样的稳定关联。
- `service/tool_evidence.py:76–89` 用原字节、metadata 和来源组成不可变请求键；相同 output_name 的不同 metadata 被拒绝为 ambiguous_mapping。`:183–208` 的失败 Run 继承会原样复制 metadata。接收后才发现需要补充或纠正依据，不是现有“完全相同请求幂等”的路径。

**可达场景与影响：**旧项目已有 PLX 但无 case，Agent 按 P3.3 仅在正式报告里补映射，然后在提交前评分。工具看不到这份报告；它只能继续信任未核对的请求，或仍按旧声明拒绝。下一 Run 即使绑定了报告与原文件，只要输入由一个变两个或次序改变，旧别名也可能指向另一份文件。恢复文件先被接收、后来补依据，又会遇到同 output_name 的不可变 metadata 冲突。这些都是 P3 承诺覆盖的正常生命周期，不能靠“统一窄解析函数”自动解决。

**最小修订：**明确一个插件拥有的有界映射类型及其读取优先规则，并逐条写清：

1. 原先已注册文件的映射在评分调用时从哪个明确字段进入；不能要求工具隐读尚未封存报告。评分请求与正式报告使用同一映射内容或可核对引用。
2. 控制层怎样把 Worker 别名关联到确切原文件、执行和声明，并让该关联随封存记录保留。Worker 继续使用别名，不能自行填写控制身份；下一 Run 不能靠同名别名或相同字节猜关联。
3. 恢复清单映射与报告补充映射分别怎样被下一 Run 显式绑定、识别并交叉核对；可以复用 current_progress，但须规定 exact 原分析和依据的选择，不能让任意背景报告赋予映射权威。
4. 完全相同请求、首次接收无映射后补充、依据修订、相互冲突、失败 Run 继承各自如何处置。可保留接收记录不可变，把补充科学声明放在报告/请求中；不必新增映射注册表或审批阶段。

**应补验收：**原先已注册且无 case 的文件、恢复文件各完成一次评分→封存→新 Run 重放；后轮增加/重排 solver_outputs，保留一个内容相同但身份不同的文件作负控。覆盖“接收后补依据”和失败 Run 继承，证实既不丢映射，也不把矛盾记录静默升级。

### R3 · P1：取消失败重放后，没有可信失败调用记录供校验器和后轮读取

**计划位置：**第 5 节 P1.5—P1.6；第 8 节 P4.6—P4.8；第 9 节 P5.2；第 10 节 P6.4。

**源码证据：**

- `mcp_local_worker.py:87–90` 的参数拒绝发生在记录活动之前；`:135–139` 只记工具名级别的 succeeded/failed。评分函数返回 `status=unsupported/unavailable/error` 时，传输调用照样记录 succeeded。
- `analysis_tool.py:197–218` 目前对非 error 记录执行确定性重放；TCAD 的对应分支见 `result_analysis.py:339–346`。删除这些失败重放会移除当前核对错误记录内容的主要机制。
- `service/runs.py:764–815` 现有诊断只保存/投影少量输出规则和路径，不含 record_key、请求关联、工具结果或可信失败来源。
- `service/run_outputs.py:212–230` 给上下文校验器的是绑定字节、描述符和截止时间；`operations/input_validation.py:33–56` 没有活动记录投影。不能仅因数据存在 runs.sqlite3 就让插件绕过已声明来源去查库。
- `schema/layered_diagnosis.py:115–135` 的 CalculationRecord 没有“这次调用确实产生此失败”的关联字段；其 request 本来就允许原始任意 JSON。

**可达场景与影响：**新 schema 在 handler 前拒绝字符串轴，因而根本不生成 CalculationRecord。Agent 若要按 P4 保留此尝试，必须自行转写记录；取消失败重放后，校验器既不知道真实调用发生过，也无法机械比较诊断 code/phase。其他计算的错误可以被误挂到这份请求，或把参数错误写成 confirmed unsupported format。反过来，若临时要求当前 Run 活动匹配，则没有收据的旧失败记录及绑定到新 Run 的旧尝试又会被拒绝，违反 P5 的历史读取承诺。

**最小修订：**在既有 Run 活动/受控证据机制上明确一个窄的可信失败关联：边界拒绝和 handler 返回失败均记录；请求关联、工具身份、阶段/错误码及已实际读取来源的关联由控制侧生成。指定上下文校验器怎样得到只读、冻结且有界的投影，报告和后轮怎样显式引用它。根控制台的“最近若干条诊断”不是可引用证据存储，不能成为唯一来源。区分新可信失败、旧封存失败和无收据的历史叙述；后两者可以作为明确标注的历史限制读取，不能伪造新诊断或要求错误在新版重现。computed 仍从原字节重放。

**应补验收：**同 Run 中 handler 前参数拒绝→修正成功→同时保留两次尝试；篡改失败 code/phase、替换请求、冒用另一 Run 失败应拒绝；重启、失败重试及新 Run 显式绑定后仍可核对。无可信记录的旧错误仍可作为历史限制封存，但不得被标成新版工具确认的结论。

### R4 · P1：预计算诊断入口的“完整成功”和计算记录处理尚未闭合

**计划位置：**第 8 节 P4 主要消费者、修改 3—4、6—7 与验收；第 9 节 P5.4—P5.5。

**源码证据：**

- `curve_score/science_operations.py:309–339` 的 curve-error 诊断只有预计算包输入和 BASE_TOOLS，明确不重计算，没有评分工具；但它与其他两个入口使用相同 LayeredDiagnosisReport，接受 calculation_records 和 source_references 字段。
- `:642–655` 仅调用 `_validate_diagnosis_against`；`:658–725` 不遍历这些计算记录/引用，也不调用 `validate_analysis_report`。因此通用/TCAD 入口增加的重放、失败来源或引用规则不会自然覆盖此入口。
- `:720–725` 仅在存在 uncovered_checks 时阻止 overall pass。“所有检查被合同覆盖”不等于 metric_report 中所有必需检查实际通过。objective_key 缺失时 `:674–678` 不会进入目标指标状态核对；把自填 gates 全部标 pass 的工程报告并不因此与失败数值冲突。
- 当前 `tests/operations/test_m2_curve_analysis_boundary.py:1030–1043` 的成功负控专门靠额外未覆盖检查触发拒绝，不能证明“全覆盖但真实指标失败”的情况被拦截。

**可达场景与影响：**预计算包完整覆盖检查，但其中必需残差比较失败；没有 objective_key 的工程诊断自填 pass gates/overall pass，或附加一个未核验 computed 记录。现有上下文分支只检查身份、覆盖和部分目标状态，无法保证计划所称“保留完整成功边界”。改共享模型后仍仅同步删除 prerequisite_status 分支，会留下另一条证据宽松入口。

**最小修订：**明确三个分析入口的证据能力矩阵。预计算入口最小做法是只允许引用 exact 包内确定性结果；不允许其创造新的计算记录或 supplemental source identity。若选择允许，则必须为这些字段规定包内来源和核验方法，不能假定它有评分工具。把实际必需 comparison/check 状态与科学 pass/claim 的关系列为共用检查，复用现有确定性结果，不重跑已固定计算。允许有证据的局部结论时仍按对应证据限制。

**应补验收：**无 objective_key、全覆盖但必需指标失败/不可用的包不能得 overall pass；伪造 computed 记录、未绑定 source reference 不能通过。真实局部有限报告可以提交。测试经过该 Operation 的输出 schema 和完整 submit，而非只调用新共用函数。

### R5 · P2：通用分析的生成 Schema 仍会把计算证据当作输入别名

**计划位置：**第 3 节现有证据结构复用；第 8 节 P4.4、P4.8 及共享消费者验收；第 11 节“分析语义”“安装”检查。

**源码证据：**

- `curve_score/science_operations.py:112` 为 layered diagnosis 声明 `/evidence`；`:222–243` 将其接到 output.evidence_paths。通用分析又声明多个 evidence_inventory 输入，见 `:291–302`。
- `operation_contract.py:305–323`、`:340–355` 触发核心来源枚举投影；`:416–424` 将每个 `evidence.source_key` 限成输入别名，而非报告中的计算/证据键。case 补充引用和 CalculationRecord 不会自动进入此枚举。
- `science_operations.py:543–545`、`:587–601` 的领域检查使用 evidence source key 指向 gate，再以 locator 指向 calculation_records。这一语义与“source_key 必须是输入别名”的生成 Schema 不一致。
- `tests/operations/test_result_analysis_tool.py:328–340` 的 computed 成功测试直接调用 diagnosis_context，保留了 fixture 的 source_key=`metric_report`，实际 sources 只有 plan 和曲线包；它没有经过生成 Schema。`:163–221` 的真正 Worker 交接测试走的是无评分路径。

**可达场景与影响：**通用分析调用 worker_curve_score 得到 record_key=`score` 后，按报告内部唯一证据键引用 `calculation_records:score`，生成 Schema 会先拒绝该 evidence.source_key。为通过而借用 `experiment_results` 等别名，既是未声明的特殊写法，也不能自然表达同一文件支持多个独立证据键。P4 的失败原因证据也会遇到相同问题。TCAD 输出未采用相同 evidence_paths 接线，不能用 TCAD 正例证明通用消费者通过。

**最小修订：**明确区分“报告内部 evidence/source key”和“受控输入 alias”。在曲线插件的输出声明/生成模型上采用适合派生计算证据的窄接线，或扩展既有可声明投影，但公共核心不能硬编码 calculation_records/TCAD。所有输入与计算引用仍由领域校验检查，不通过删除引用完整性规避。若本轮暂不修，必须明确缩小“全部接口一致”和共享分析验收的完成范围。

**应补验收：**增加一个通用分析真实 Worker 的评分→计算证据引用→submit 正例，使用独立 record_key，且同一输入产生两个独立计算；同时覆盖未知输入、未知计算键和未完成计算被冒充成功。直接调用 `_diagnosis_context` 的通过只算局部单元证据。

## 3. 非阻断建议与应保持的决定

- **保持 claim 投影不扩权。**`schema/claim.py:22–42` 只是复制报告的 verdict、numerical status、claim_allowed；本次检索未发现生产调用方据它直接授予执行/人工审批资格。因此不要为弥补上游校验缺口给它新增控制政策；R4 的修复应在拥有输入证据的分析边界完成。
- **把提示词变更纳入同一提交。**`science_operations.py:781–782`、`:858–863` 仍要求全局顺序/最早失败处停止；TCAD `result_analysis.py:367–397` 仍要求案例只能由项目声明证明并把声明修正指向 author。这些位置已在计划主要文件内，但应在 P0 账本明确与 Schema/校验器一起更新，避免形成新的 Agent 可见合同冲突。
- **历史兼容验收使用真实形状。**P2 保留原始 request、P5 不原地改旧 Artifact 的决定合理。新增 typed request 的 model_dump 不应因补入默认字段改变旧 computed 记录的重放比较；可增加省略默认项、显式默认项的旧 computed 固定见证，不需要全面迁移科学 Schema。
- **保留科学方法等价性边界。**计划不自动增加错误算子名、由 Worker 判断等价性正确。现有 `validate_analysis_report:570–577` 只让 evaluator_metric/阈值等机械一致的计算计入原检查覆盖；“科学上论证等价”与“按原检查自动计入覆盖”应在 P6 报告分别说明，不能把方法说明文字当成放宽数值验收的授权。
- **全目录盘点是审计，不是重写许可。**P0 发现同类问题后，先把本报告已证实的接线范围补入修订计划；未知领域功能继续单独有界处理。无需新 Operation、映射审批、通用工具成功信封或新的科研阶段。

## 4. 对五个审查问题的判定

| 问题 | 判断 |
|---|---|
| 是否对准重复接口、准入和输出职责冲突 | 是。类型化请求、明确错误分类、保留有限分析、移除不合理全局传播均针对已确认机制。 |
| 工程方案是否具体可实施 | 主要改动可实施，但 R1—R3 缺失实际传输、映射生命周期和可信失败来源接线，不能按当前文字假定闭合。 |
| 身份、权限、审查、历史兼容是否完整 | 原则正确；R2/R3 尚未定义足够的身份与历史行为，R4/R5 留有共享消费者缺口。无需新增审批以补这些工程缺口。 |
| 是否符合最小改动与奥卡姆原则 | 基本符合。应通过既有入口、字段和不可变记录补连接；不需要新增状态机或路由。修复范围须包含已证实的遗漏消费者。 |
| 验收是否覆盖真实阻断 | P6 明确要求真实 PLX、Worker 自主纠错和下一设计交接，比现有构造正例充分；但需要 R1—R5 的真实入口负控。当前未执行 P6，也未证实真实 PLX 或计划指标可计算。 |

## 5. 审查范围与未验证事项

已追踪：Root/Local/Hardened 至 MCP 传输；preflight/invoke 包装和 Transform/Approval/Effect 的相关错误分支；共享参数/语义错误转换；Run 诊断保存和输出校验上下文；TCAD 原文件/恢复清单、别名、接收幂等、失败继承和后轮重放；通用/TCAD/预计算分析模型与消费者；claim 投影；上述定向测试的调用边界。还核对了 CurveAxis、CurveComparisonSpec、CurveOperatorSpec、SProcessSeriesSpec 的相关结构及当前架构职责条款。

没有进行全目录/全部插件的动态编译审计，没有检查正在运行的安装包、生成 Worker 配置或部署版本，没有读取真实六次拒绝的原始传输记录。本报告只把背景文档作为先前工程证据，并独立核实其涉及源码分支，不重新认证该历史现场。并发环境未冻结完整工作树快照；本轮只新增此审查报告，未修改或回滚计划、源码和他人工作。

R0 应先补齐 R1—R5 的接口决定与对应验收，再提交独立复审。该 REVISE 是工程计划判断，不替代任何封存科学结果、科学独立审查或执行批准。
