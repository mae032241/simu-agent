# 历史科学记录兼容性修复计划独立工程审查 R1

结论：**PASS，可按 R1 计划实施。** 未发现需要先退回重写计划的阻断。下列补充是实施和最终 diff 验收的具体要求，均属于既定 P1–P4 范围，不增加新的科学准入门或状态机制。

审查日期：2026-09-12。审查基线：`be5da77acdbf98054e0b096fc4e940de560d4ba1`。对象：`COMPATIBILITY_REPAIR_PLAN.zh-CN.md` R1。审查开始时 HEAD 为该检查点，工作树只有该计划未跟踪；本审查只新增本报告，不修改计划、生产代码或测试。审查使用 `scid-cross-boundary-review`，只读取源码及现有测试，没有运行测试、构建、科研 Operation、控制面查询或外部执行。

## 结论依据

目标正确：当前代码把运行实现身份用于已完成证明消费，确实能产生计划描述的两层拒绝。`RunService.is_exact_reviewer_output` 对 completed 审查调用 `_compiled`，而后者同时比较 version 与完整 digest（`service/runs.py:892、1241`）；Root 对 claim 输入也比较完整 digest（`interfaces/mcp_root_operation_routes.py:1565`）。编译摘要递归包含 reviewer digest、批准 provider 身份、组件和输出合同（`operations/catalog.py:748`），因此 reviewer 或无关实现变化可传播到没有改变的科学记录。拆开“继续原 Run”和“消费其已完成输出”的判定，符合故障原因。

可实施性成立：Run 已保存 operation id/version/digest、精确输入和输出引用，Artifact 已保存输出端口以及 schema/kind/media；人工请求已保存 `CompiledApprovalIdentity`，编译目录已提供 `approval_contract_digest`（`operations/catalog.py:732`）。所需信息齐全，无需重算摘要、改写旧记录、增加数据库字段或兼容性注册表。

科学资格边界足够：同 version 与仍受支持的输出类型只解除实现 digest 漂移产生的拒绝。completed、指定 reviewer、精确 subject_ref、允许 verdict，以及消费者现有的实例、current、非合格状态和输入检查仍承担原职责。原对象可复用自己的旧 PASS；新 Artifact 引用仍需自己的审查和适用人工决定。版本或 schema 标识承担科学不兼容变更的声明责任，程序不推断语义等价。

## 必须在实现中落实的边界

1. **P1 的兼容查询只解释完成记录。** `is_exact_reviewer_output` 的无兼容资格查询选项仍须先满足 completed、精确输出、指定 reviewer、精确 subject 和 verdict 条件，不能变成任意历史审查存在性判断。它只能用于区分“不匹配”与“匹配但不兼容”，不能把查询结果直接当作准入通过。`signal_for_output(require_current=False)` 的既有历史读取语义保留；默认兼容读取不能修改 Run 状态、原 digest 或 `historical` 标记。

2. **端口检查要覆盖新放行的同版本 digest 漂移路径。** 现有 `_operation_output_contract` 仅在 `allow_historical` 时检查 schema/kind/media（`mcp_root_operation_routes.py:1594`）。去掉完整 digest 的准入比较时，不能让普通 claim/change_request/review_signal 绕过计划承诺的端口兼容判断。复用现有端口元数据即可；无需把历史结果按当前 producer 输出校验器重新提交一遍。`operations/invoke.py:219、237` 已有消费者输入检查，其中历史 JSON 通用检查仅适用于 prior_signal/revision_base；本轮不扩成新的全输入 schema 回放机制。

3. **兼容诊断不掩盖其他拒绝。** 有精确审查但其 reviewer version 或输出端口不再受支持时，返回计划中的 incompatible 原因及实际端口；错误 subject、错误 reviewer、非允许 verdict 仍按原本不匹配处理。直接修订入口 `mcp_root_operation_routes.py:1506` 也须保留该区分。重新包装 `OperationInvocationError` 时保留已有的有用 message/field/port，不增加通用诊断框架。

4. **P3 只改变普通研究输入对已决定请求的 provider 匹配。** `ApprovalService.are_subjects_approved_by_provider`（`service/approvals.py:313`）的默认模式保持严格；Root 调用点按消费者是否为 effect、批准 kind 是否为 execution_authorization，决定是否启用兼容模式。原请求与决定的引用、原 subject set、一项已有决定覆盖所需 subjects、kind、允许选项和内容完整性保持现有语义；不新增决定，不重新解释批准到期或撤销语义，不把现有 subject 覆盖检查改成另一种集合规则。

5. **运行和执行身份不能共用放宽后的比较。** `_compiled`、Run 开启/提交/完成、`validate_resume` 及其 `_recovery_digest` 不变。已有 `draft_from` 是创建新 Run 消费保存工作的独立路径，已有跨合同行为与原预算核验也不应被本轮额外收紧（`tests/operations/test_l2_run_invariants.py:1468`）。人工审批展示读取默认 signal（`mcp_root_operation_routes.py:486`）与执行审批 snapshot 读取默认 signal（`interfaces/mcp_root_execution_routes.py:375`）确实都会受 P1 影响；后者仅改变可展示的历史 handoff，不能替代其前置 `_current_execution_contract` 的完整身份比较（同文件 `:280–302`），也不能改变 `ExecutionService.authorize` 的完整身份和精确 request/payload 绑定（`service/executions.py:328`）。

6. **来源族中的 digest 仍是原记录间的完整性事实。** `_run_output_family` 比较 Artifact 标签与原 Run 的身份，`_transform_output_family` 比较同次变换的原兄弟集合（`mcp_root_operation_routes.py:567、643`）；这些比较不是“历史对当前实现”比较，不能随本次修复删除。历史非通过状态、直接修订的精确 review edge、次数和无进展限制也继续保留。

## 验证清单补充

P4 已覆盖正例、反例、真实人工决定、Root preflight/invoke 一致和 Worker 提交，足以定义闭环验收。实施时必须把下面几项落实为具体用例或复用已有有效断言：

- 将 `tests/operations/test_m6c_producer_topology_removal.py` 加入定向检查候选。`:306` 起的参数化用例明确断言同版本旧 digest 必须拒绝，与新政策冲突，需改写为同版本兼容且原审查/使用限制继续生效；`:178` 用例实际改变 version，应保留版本拒绝，调整其误含 digest 的命名即可。不能删除该文件中的非合格状态、精确修订和 inventory 边界测试。
- 至少一个兼容正例先通过真实 Root/Worker 路径生成旧 completed 输出与旧 PASS，再切换编译目录使 version 保持、digest 变化，随后完成新 Run 的 preflight、invoke、打开和提交。仅给 Artifact 标签填假旧 digest 不能证明已完成 reviewer 复用；现有历史 fixture 和部分审批 fixture 使用 stub，不能代替计划要求的真实决定正例。
- 人工资格正例应断言 provider version 与 approval_contract_digest 保持、operation_digest 确实变化，然后由 Root 消费原决定。反例分别改变批准合同、版本或精确 subject，避免把多项变化混在一起而失去区分能力。
- 执行负例必须隔离“同 version、同 approval_contract_digest、仅 operation_digest 不同”仍不得授权。`test_r4_execution_approval_identity.py:700` 已构造这一错误批准身份，可复用；`:668` 的 `_drifted_catalog` 同时改变批准问题和合同摘要，单独运行它不足以证明本轮最容易误放宽的边界。保留 adapter 提交次数为零的断言。默认 signal 的执行 snapshot 调用不需要另建执行机制。
- 版本/输出端口不兼容与无精确审查的诊断分别覆盖，并至少包括一个直接 change_request 修订入口。同版本 digest 漂移后既有 nonqualifying、跨实例、新修订配旧审查拒绝也须保留。

以上按主计划的单进程低资源预算串行执行；本报告未运行任何测试，不能作为测试通过证据。最终审查需要实际命令、结果、资源记录和未验证项。

## 最小变更判断与完成限度

计划已选到合理的最小方案：完成输出读取处一个小型版本/端口判断，Root 生产者准入处移除不合适的 digest 门，批准服务增加默认严格的有限匹配选项。更短地全局删除 digest 比较会误放宽 Run/执行；另建“科学 digest”、重新输出校验、资格迁移或自动再审批都增加不必要机制。不建议扩大本轮范围。

双语架构文档应明确“同版本的原科学证明可复用，原实现身份继续留存”，并保留跨版本历史阅读不自动提供当前资格的限制。最终实现仍需独立 diff 复核。源码通过不代表已部署，也不代表补齐假设反馈端口或总体科研目标；部署后的两份原精确请求需重新 preflight，继续执行须遵守原操作和人工批准边界。
