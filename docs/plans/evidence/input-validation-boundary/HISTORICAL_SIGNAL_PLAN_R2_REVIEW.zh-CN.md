# 历史判定与分析准入 R2 复审

2026-09-10。结论：**PASS（计划可实施性与跨模块静态复审）**。没有发现新的阻断。由当前审查者重新沿实际调用链复核，未新开独立子 Agent；本结论不冒充独立实现审查、测试通过或线上验收。

审查对象：HISTORICAL_SIGNAL_ADMISSION_MINIMAL_REPAIR_PLAN.zh-CN.md，SHA256：`76449194210618435a7e63aceab7e6016c9e36111701e647b0e5388442b58c86`。计划原文保留其形成时“待复审”状态，复审结论以本记录为准。前版审查 REVISE 保留。

## 前版缺口复核

| 原问题 | R2 处置及代码可实施性 | 结论 |
| --- | --- | --- |
| HSP-1：读取 pass 后仍被当前审查门禁拒绝 | 两个分析的 plan/review 改既有 evidence_inventory 后，review_input_mode 返回 background，不再要求 producer 的当前 review 资格。显式保留 typed schema/resource，并在 guard/input_validation 补齐历史结构、审查生产者、目标和精确父链，避免来源保护随用途一起消失 | 闭合 |
| HSP-2：审批请求误接受旧 pass | _prepare_approval_projection 独立使用原 current signal helper 构造 ApprovalSubjectSnapshot；输入事实不回写。operation_preflight 与 approval invoke 均进入该函数，所以只修该处即可保持两个入口原 projector 条件，不必修改批准服务 | 闭合 |
| HSP-3：恢复 blocked/revise 后部分 claim 被拒绝 | 保留 claim_admissible 的既有含义，明确背景与 claim_evidence 的不同结果并设对照测试。不会全局把历史非通过结果禁止用于诊断，也不会掩盖原非通过判定 | 闭合 |
| HSP-4：修改公共 helper 扩散到执行审批 | 不改 helper/default、is_exact_reviewer_output、执行审批或全局 prior_signal；显式改变实际输入构造与必要消费者 | 闭合 |

## 三文件范围核对

Root 输入构造和资格审批材料构造均在 mcp_root_operation_routes.py，能分别修改而不触及执行审批文件。RunService.schedule 已读取封存历史判定，其当前逻辑可保持。两个领域文件各自包含完整 Operation 声明、guard、input checker、组件配置身份与提示资源，修改用途和声明无需扩充共享 Spec、数据库或新状态。

仅 science.result.diagnose.v1 与 tcad.result.analyze.v1 需要本次用途改变；curve-error 包诊断不使用相同 plan/review 端口，不应批量修改。原 _input/_review_input 还服务其他 Operation，计划明确禁止改其默认值，满足最小范围。

当前 reviewer 验证、批准 provider/subject、外部执行和 strict resume 继续走原实现；本修复不需要削弱这些门禁。改变 usage/组件身份会产生正常 Operation 摘要变化，计划已要求记录影响并以新 Run 接续。

## 必须落实的实现细节（不新增范围）

1. InputBindingDescriptor 当前没有 handoff_verdict，但 guard 的 BoundInput.artifact 有。完成记录对应的 handoff、生产者/输出身份和父链在已有 guard 检查；plan/review JSON、review_target 和 payload pass 在 input checker 检查。两处共同要求 pass 即可，不为重复传递 verdict 增加共享字段或访问存储。
2. parse_bound_json 的失败会抛 BoundSourceError；若不在新输入 checker 内处理，共享 validate_operation_inputs 会把它归为 input_checker_failed。实施须在领域输入解析处转换为稳定 OperationInvocationError，带 experiment_plan/experiment_review 端口及安全字段，不泄漏原值。这是计划已要求的明确输入错误，不必改共享异常层。
3. 历史 review 的来源必须有精确 completed Run 提供的 handoff，并匹配现有独立计划审查生产者、输出端口及 plan；不能从 JSON/标签自行填充 pass。允许历史 digest 不匹配不等于放弃来源身份。
4. 证据/参数资格对照应验证实际 Root preflight 与 invoke，不仅调用 projector。线上分析回归应使用真实 producer 元数据和 materialize 父链，不能以未标注 producer 的手工 plan 避开第二道门禁。

## 验收与限制

R2 已包括源码和 installed 升级交接至 Worker submit、旧 review 不授予当前 author 资格、证据/参数申请前后对照、非通过背景与 claim、错误审查/计划/跨执行日志/结构、提交零输入 checker 调用。测试串行及 512 MiB 总树限制明确，无需全量或真实求解器。

本轮仅静态核对方案和现有代码，未修改生产源码、执行测试、更新部署或调用科研 Operation。因此 PASS 表示计划已具体且可实施，并非保证实现无缺陷；只有原历史执行在安装后的新分析 Run 完成且负例保持，才能关闭线上问题。当前没有需要追加的新机制或扩大生产文件范围的证据。
