# 分析续接与机械映射最小修订计划 R0：独立工程审查

日期：2026-09-12。结论：**REVISE**。R0 不应据此开始源码实施；修订下述三项后复审。

- 被审计划：`docs/plans/evidence/analysis-continuation-minimal/PLAN_R0.zh-CN.md`。
- 被审计划 SHA256：`f14c3847f02ad10fc47f37b062bb06e5ddd3994e6e01253f5a3752fa359ae0f2`。写审查前再次核对一致。
- 仓库：`123/scidiscovery-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。实际依据为包含大量既有未提交更改的当前工作树，不能把 HEAD 当作全部被审源码。
- 审查独立于计划作者，使用跨边界审查及最小变更原则。只读计划、必要源码和现有测试；未调用科学/Worker MCP，未运行测试、构建或 solver；唯一写入为本审查文件。

## 1. 阻断项与最小替代

### R1（高）：工具请求补全与现有收据合同冲突，且省略案例无法通过现有解析入口

计划第 71 行同时要求“请求省略已知 output/case/basis 时自动补”和“记录补全后的有效请求”，第 75 行要求保留既有 calculation_records 兼容性。按当前实际入口，这两者不能直接同时成立。

证据链：

1. `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py` 的 `call_tool` 在 `_call_tool`/领域 handler 之前调用 `begin_tool_attempt`。`service/tool_evidence.py:220` 的 `ToolEvidenceMixin.begin_tool_attempt` 对调用者原始 `arguments.request` 计算 `request_digest`。
2. `plugins/curve_score/curve_score/analysis_tool.py:92` 的 `ScoreRequest` 明确保留 `_raw_request`；`parse_score_request` 保存调用者原始 JSON，`run_score_tool:289` 用它生成 `CalculationRecord.request`。`diagnostic_tool.py` 的 `run_diagnostic_tool` 遵循同一规则。
3. `service/tool_evidence.py:153` 的 `_calculation_attempt_sources` 比较 `hash(canonical_json(record.request))` 与原始 attempt 的 `request_digest`。若 TCAD handler 将补全字段写入 record.request，计算可执行成功，但提交仍会因“calculation request differs from its recorded attempt”拒绝。为此改收据模型、摘要规则或增加第二种请求权威会扩大本轮范围。
4. 在进入领域 handler 前，`LocalWorkerProtocol._call_tool:154` 已解析工具模型。`analysis_tool.py:72` 的 `CSVSource.case_key`、`tcad_artifact/curve_normalizer.py:34` 的 `SProcessSeriesSpec.case_key` 均必填。省略 case_key 的调用无法到达 `_check_score_sources`。其中 case_key 还参与原始记录筛选及生成曲线身份，属于实际曲线选择，不能当作普通表格冗余字段处理。

最小替代：本轮保留显式 `case_key`、series、axes、列/数据集和 comparison 选择，原始请求、计算记录 request、attempt 摘要及历史记录均不改写。共享投影只帮助 TCAD 工具识别已经成立的 output/experiment/basis 对应关系，免抄相同历史依据；它用于检查调用者明确选择与已知映射是否一致。完整历史依据的读取经过 `context.read_input/read_evidence` 计入现有 read-source 证明。不要新增通用请求标准化或收据迁移机制。

此收缩不会妨碍 finalizer 对新报告的缺省 source_references 作可追溯补齐；报告物化与工具调用记录是不同的既有边界。共享的是来源解析规则，不必把工具原请求改成报告的物化形式。

必要验收：通过真实 MCP 调用省略已有 basis、保留显式 case_key，成功计算及提交；断言封存的 `record.request` 与原调用完全一致、摘要匹配。再以明确错误 case/basis 作负例，确认准确拒绝且不改原调用。

### R2（中）：P4 将 input_alias 当作 Identifier，实际模型没有这个前提

计划第 84 行拟在错误原因中包含 source_key/input_alias，理由是“受 Identifier 约束”。`src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:144` 的 `AnalysisSourceReference.input_alias` 仅限制字符串长度；`plugins/curve_score/curve_score/analysis_tool.py:63` 的 `AnalysisSource.input_alias` 也是普通字符串。未知 alias 正是诊断会处理的输入，不能先把它当成已经匹配受控来源的标识。Identifier 本身也不是任意内容的安全发布证明。

最小替代：默认采用固定原因和精确字段路径，不回显请求中的任意 alias/locator/rationale。确需预期值时，只使用已命中受控 descriptor 的必要安全语义值。不要为了打印错误新增字符串净化框架、收紧历史 schema 或增加科学字段校验。这能直接满足“拒绝可定位字段”，无需额外系统。

必要验收：无效 alias 含任意文本时，错误仍定位对应 `input_alias`，消息不复述该文本；已知错误 output/case 则定位它自身的字段，不统一落到 basis 或 `$`。

### R3（中）：恢复工作副本不能复用旧 launcher 的活动观测目录

R0 P2 排除 lock/stop/cache，但 `.json/.log` 在恢复白名单内。`local_process_observation.py` 的 `RECORD_DIR` 固定为 `scratch/.analysis-process`，`read_summary` 直接读取其中 `latest.json`，不识别该文件是否来自另一个 Run。若将整个恢复 scratch 的白名单文件复制到新 scratch，新 Run 首次运行前即可读到旧 state、时长或退出码，形成错误的本轮观测。

最小替代：在这一次恢复副本准备中跳过整个既有 `local_process_observation.RECORD_DIR`，旧观测及日志仍通过 recovery-draft 索引读取，新 launcher 自行创建新的活动目录。不改旧日志，不改观测器，不扩展成一般恢复排除规则系统。验收新 Run 在启动前为 unobserved，并确认旧观测仍可读取。

## 2. 目标、可实施性、职责与最小范围判断

| 维度 | 判断 |
| --- | --- |
| 目标定位 | 合理。入口减少重复返回、恢复副本可编辑、复用精确旧映射和准确拒绝，均对应既有分析续接问题。无需重跑已完成的 Fig.4，也无需改研究方法。 |
| 可实施性 | P1/P2 与工作区 descriptor 扩展可沿现有生命周期实现；P3 工具请求行为必须按 R1 收缩。 |
| 职责一致性 | 身份由现有 Artifact/descriptor 持有，科学对应关系来自明确项目声明或精确绑定的既有报告；纯投影没有资格判定权。保留该边界后成立。 |
| 最小变更 | 既有 materializer/finalizer、TCAD handler/context 和一个小型纯函数模块足够。没有证据要求新增状态、操作、通用映射框架或收据协议。P4 不需新校验系统。 |

具体路径已核对如下：

- **P1 简明入口可减少重复工具返回。** `LocalWorkerProtocol._open:222` 当前每次内联 `_assignment_tool_contracts()`，而同样内容已在 `run_assignment.assignment_json` 的 tool_contracts 中。返回 analysis-start 路径和选定合同指针能消除这份内联重复；原 assignment 和输出 schema 仍可按需读取。`platforms/codex.py` 的本地 Worker 指令允许从 assignment 读取完整选定工具合同，因此不必为这一点修改平台 prompt。应依据新工作区实际存在的入口选择返回形态，保留旧工作区行为，避免按当前 Operation 名称替旧 Run 换合同。R0 已正确区分字节减少与真实 Agent 耗时，不能把前者当作后者的证据。
- **P2 复制到新 scratch 是正确的修复位置。** `analysis_workspace.materialize:25` 当前只建空 scratch；`LocalTrustedBackend.prepare`/`_copy_read_only_tree` 交付 0500/0400 恢复树。`local_workspace.write_control_workspace_file:476` 已能通过 no-follow 目录句柄创建 0700 父目录和指定模式的新文件，并在不允许覆盖时拒绝不同内容。复用此边界即可；不应 chmod 恢复原件，不需改 launcher。现有 snapshot 后缀过滤已排除无后缀 lock/stop，重点测试只读父目录而非再造锁过滤系统。
- **工作区 hook 增加 descriptors 可以保持范围很小。** `operations/workspace.py` 的两个 request 是冻结 dataclass，可增加默认空只读映射。`RunService._materialize_workspace:1007`、`_finalize_workspace:1054` 是现有唯一调用点；`ToolEvidenceMixin.source_descriptor:201` 已能提供 startup 输入及当前工具证据元数据。只传可见绑定与被允许的当前工具证据，不调用 `_validation_inputs` 再读整批原始文件，不因元数据传递新增准入检查。
- **历史解析有现成身份依据。** `operations/input_validation.py:143` 的 `prior_analysis_sources` 已验证显式 prior/manifest 对、完整 ArtifactRef 和旧别名到当前别名，不依据相同字节猜身份。TCAD 只需在其上投影原 plan/package cohort 与可映射的 source_references；不要另造历史查找、latest-head 查询或资格检查。已有 `test_prior_analysis_sources.py` 包含相同字节但不同 Artifact、别名碰撞和错误配对负例，可扩展同一组 fixture。
- **工具/入口/finalizer/context 使用同一规则，但无需保存第二份权威。** analysis-start 是工作区创建时的只读投影；之后新增工具证据由工具和 finalizer 使用当前 descriptor 解析即可，无需为了“同步”重写入口或增加缓存。`result_analysis.analysis_context:382` 中“reference lacks matching evidence”是独立重复表格门槛；删除它不要求删除 source_key 唯一性、明确源/输出/案例冲突检查或受控计算收据检查。`result_materialization.finalize_result:11` 已支持封存前投影新 payload；TCAD wrapper 应复用它和共享 snapshot，已声明的输出/schema 上限继续由现有检查持有。

## 3. 复审与验证边界

复审只需确认 R1/R2/R3 在新计划中落实，并保留既有目标与文件边界。实施验收按 R0 的真实 MCP、编译 catalog、finalizer 封存和一次隔离安装 smoke 执行即可；不需要把本审查变成新的一轮全量测试计划。

重点观察三项组合事实：新入口没有再次内联完整工具合同；只读恢复树的可编辑副本支持修改脚本与创建新状态文件；同一精确 cohort 的历史映射能够在工具检查、报告物化和下一次续接复用，同时相同字节的错误身份或显式错误案例仍被拒绝。

本审查没有验证新增实现或声称性能已改善；工程实现和真实 Agent 的耗时收益均尚待各自验收。
