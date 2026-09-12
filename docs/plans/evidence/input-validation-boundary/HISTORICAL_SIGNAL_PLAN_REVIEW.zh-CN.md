# 历史判定投影修复计划：跨模块只读审查

2026-09-10。结论：**REVISE**。方向正确，但原三点计划不足以证明修复能贯通，也不能承诺批准路径行为不变。未修改生产源码、运行测试、编译目录、访问实例存储或派发科研任务。

使用 scid-cross-boundary-review。基准为当前工作树（包含本轮及此前修改）；审查的是最近提出的历史判定修复计划，并非再次确认全部 dirty diff。

## HSP-1：只改 Root 读取会暴露下一道当前审查门禁（阻断）

TCAD result_analysis.py::INPUTS 把 experiment_plan/experiment_review 声明为 prior_signal。curve_score/science_operations.py 的通用诊断亦如此。RootOperationRoutes::_validate_producer_output_admission 对 prior_signal 不跳过 producer review edge；它允许历史 producer 结构被读取，但仍调用 is_exact_reviewer_output 验证其审查。RunService::is_exact_reviewer_output 强制 _compiled 与当前合同一致。

真实 plan_3 来自 science.experiment.materialize.v1，该 Operation 的输出明确要求 science.object.review.v1 独立审查。真实 review_6 已因该审查合同更新成为 historical。因此即使修正 handoff_verdict，当前源码仍会在后续 admission 以 input_independent_review_missing 拒绝（静态路径推导，尚未运行修改后请求）。不是把首个 guard 修通便完成线上修复。

必须在计划里声明“历史执行分析消费既有计划/审查记录”的正确用途。优先复用现有 evidence_inventory 背景用途，并保留这些端口的具体 schema、预算、历史可读性及分析 guard 的精确来源/计划/执行匹配。不全局放宽 prior_signal，不让所有作者、修订、物化任务都继承历史审查资格，不在 Root 硬编码 TCAD 白名单。最终如何声明须由真实升级测试证明；只设置 handoff 读取参数不能闭合此项。

## HSP-2：资格审批也消费相同的 handoff 投影（高）

RootOperationRoutes::_prepare_approval_projection 把 bound input 的 handoff_verdict 直接复制进 ApprovalSubjectSnapshot。general_science_components::_require_passing_audit 和 parameter_operations 的参数资格 projector 均把该值是否 pass 作为批准请求前提。

因此通用输入投影从 None 恢复历史 pass，也可能改变证据/参数资格申请能否创建；仅保留 is_exact_reviewer_output 不足以证明所有批准路径不受影响。创建审批请求不等于自动批准或执行，但依然是实际准入变化，不能漏报。

修订计划应保持现有资格申请要求：读取历史事实与给资格 projector 提供当前有效审查条件分别处理。可沿用已有当前判定读取能力在审批准备路径显式确认，不新增资格系统，也不让事实字段默默承担版本资格。若某个资格 Operation 本来允许历史审查，须按既有明确合同保留，而非统一放宽或收紧。至少以证据资格、参数资格各一组当前/历史审查对照锁定原有行为。

## HSP-3：blocked/revise 的恢复会使部分 claim_evidence 更严格（中）

mcp_root_shared.claim_admissible 对 None 不拒绝，对 blocked/revise 拒绝。此前 Root 隐藏历史判定后，部分非通过结果可能逃过该项判定；恢复真实历史值后，它们作为 claim_evidence 会被拒绝。

这通常是正确恢复限制，但必须明确验证：同一个非通过历史结果作为 evidence_inventory 可读且可用于诊断，作为要求可用科学主张的 claim_evidence 则不应被包装成可信成功。不得为了让分析继续而统一将历史非通过改成 None，也不能要求背景材料先通过科学审查。

## HSP-4：不能改变公共 helper 的默认语义来扩大补丁（范围控制）

_scheduler_signal_for_output 除输入构造外，还被 mcp_root_execution_routes 的外部执行审批材料构造使用。直接改 helper 默认或全局去掉 signal_for_output 的当前检查，会把输入事实修复扩散到执行审批路径。

最小实现优先只让输入事实构造显式读取封存判定，并针对 HSP-1/HSP-2 调整明确的消费者边界。原 is_exact_reviewer_output、批准 provider/subject 身份、current、执行审批及 strict resume 保留。审查调用点不等于全部调用点都必须修改。

## 必须补入的验收

1. 实际创建并封存计划和审查，再升级生产合同，以旧执行产物完成 Root preflight → invoke → schedule → Worker submit；TCAD 与通用分析各覆盖代表性路径。不得用同一目录创建的新审查替代升级场景。
2. 需要当前独立审查的作者/物化/修订路径仍拒绝不匹配的旧审查；修改过的计划不能继承原计划的 pass。
3. 证据/参数资格请求的当前与历史审核对照；既有审批及执行精确身份要求保持，无聊天批准或额外执行。
4. 历史 blocked/revise 能作背景，不能作为通过的可信依据；无完成 Run 的孤立对象不能伪造封存 handoff。
5. 原分析来源负例（错计划、跨执行日志、字节损坏）继续在正确入口拒绝；提交与预览零输入 checker 调用。

单进程串行、512 MiB 测试树预算，扩展现存测试，不运行全量/压力/真实求解器。若更改 Operation 的端口 usage，正常传播合同身份并更新兼容证据，不能宣称目录摘要完全不变。VM runner 与数据库 schema 不需要因上述修复改变。

## 已检查且计划可保留的边界

封存事实必须来自精确 completed Run 的 output_ref，不能从 payload 或 label 伪造。RunService.schedule 已读取历史 handoff；inventory 及 transform 非通过传播也已经这样做。明确事实投影方向与现有实现一致。源字节完整性、独立 review 精确对象匹配、批准 provider 身份、恢复冻结合同都是独立实现，无需为读取历史事实而放松。

原计划应先补 HSP-1/HSP-2 的具体处置与测试，再进入实施；当前不作“无副作用、已通过”的结论。
