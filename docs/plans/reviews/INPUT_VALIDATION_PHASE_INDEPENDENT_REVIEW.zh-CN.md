# 输入校验阶段：独立工程审查

日期：2026-09-10。对象：HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85` 叠加当前未提交工作树。本文独立审查 `FRAMEWORK_REPEATED_CONTRACT_FAILURE_ROOT_CAUSE.zh-CN.md`，不是科学结果，也不表示随附修复计划已获另一轮独立审查通过。

## 结论

支持原分析的核心因果链：消费者的纯输入内容约束遗漏于准入；受控诊断与求解器声明产物的接收语义未闭合；输入矛盾被标成作者可改的输出错误；运行态仅显示活动，无法解释拒绝。这足以解释静态可达的无效重试，不需要归因于模型能力或削弱身份保护。

需要收窄两处表述：提交时检查输入本身并非错误，错误是首次执行原本可以在创建前确定的输入可满足性检查，以及把它的失败归到可修订输出。`preflight` 已有部分内容检查，并非只检查 Schema 名称；但这不覆盖多输入内容关系。不能由本次代码审查独立确认“现场恰好重试 8 次”或旧部署状态。

本轮只读规范和源码并写本文及修复计划；未运行测试、未读研究状态目录、未启动科学 Operation。保留所有既有修改。规范依据为 `docs/ARCHITECTURE.zh-CN.md`、`docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`、`SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；当前比较评估只作实现快照，旧计划和审计不作权威。特别遵守同一编译合同、精确不可变身份、四态 Run、可选评分及只有作者可改错误才使用 `SemanticRuleViolation` 的约束。

## 三个阶段的准确边界

| 阶段 | 检查对象与例子 | 失败责任 |
| --- | --- | --- |
| 输入准入 | 已绑定 plan/package/manifest/注册字节彼此成立；产物名、媒体、摘要及显式案例对应 | 创建前拒绝该绑定，不派 Worker |
| 完整性复核 | 提交时从原 Artifact 重读；注册元数据与冻结绑定、实际字节一致；重用同一输入规则 | 本轮输入不可修，失败终止，不要求修改报告 |
| 输出相对于输入的校验 | 报告引用哪个 alias/case、计算重放、失败执行是否被写成通过 | 报告可修时拒绝候选，保留 running；校验器故障终止 |

失败执行、缺少所需求解器文件、无评分能力不等同结构性输入错误：它们可进入有限/负面分析，但不得得出缺少证据的通过结论。不能将整个 `analysis_context` 搬到准入。

## 对原报告逐项裁决

### F1：确认，高严重度

`src/scidiscovery/operations/invoke.py::preflight_operation` 调用 `_run_guards` 和 `_validate_input_content`；后者处理 required_non_null_fields 和部分历史输入结构，不解析 TCAD manifest 与产物的交叉关系。`plugins/tcad_artifact/tcad_artifact/result_analysis.py::analysis_parentage` 检查父链和审查 verdict。`_identity_context(sources)` 只用输入和描述符：解析 plan/package/manifest、检查已声明案例、逐项对齐 manifest 的输出名/媒体/大小/SHA256及项目路径。生产调用位于 `analysis_context(payload, sources, handoff)`，不是准入。

因此 `_identity_context` 的确定性失败无法通过重写 payload 消除。应前置并复核同一规则；不能删除提交时的字节校验。另一个需闭合的小漏洞：当前 solver_outputs 的 descriptor.output_name 为 None 时被直接 continue。修复应拒绝缺少受控产物身份，而非让无名文件绕过检查。

### F2：确认，需明确诊断身份来源

本地 `execution_control.py::tcad_collect` 和远端 `remote_runner_py36.py::_collect` 均先列出 manifest.outputs，再追加 `tcad_log` 与 `tcad_manifest`。`src/scidiscovery/artifact_agent/service/executions.py::ingest_result` 校验外部执行身份、终态和名称唯一；登记各文件时使用相同 request/payload 父链，并写受控 execution_id、logical_name 标签。

`result_analysis.py::INPUTS` 的 solver_outputs 是可选通配 inventory；`analysis_parentage` 接受与 manifest 相同的父链。故额外日志放入该端口，元数据准入能通过；带 logical_name=tcad_log 的描述符在 `_identity_context` 中找不到 manifest 成员则拒绝。此路径可由源码直接构造，并不依赖日志内容。

方案应明确选择“声明诊断接收方式”：独立可选 diagnostics 端口接收当前收集器 tcad_log，验证受控注册和同执行父链；solver_outputs 保留清单成员语义。不扩大 manifest.outputs，也不把所有任意 reference_material 当成执行诊断。详见计划的唯一实施方案。

### F3：确认，异常机制本身应保留

`service/run_outputs.py::validate_run_output` 将 context validator 的 `SemanticRuleViolation` 加上 context_rule_id 与 `$.payload` 后转为 RunOutputError，其他异常转 RunCheckerError。`service/runs.py::submit` 对前者返回 rejected 并记活动，对后者调用 record_failure。宪章明确限定 SemanticRuleViolation 为 Worker 可修错误；问题是领域函数错误选用它，而非需要重建异常平台。

输入故障前置后，提交复核若发现故障仍需明确终止。不能用“错误文案出现 input/manifest”之类字符串规则判断归属。8 次拒绝属于原报告记录，本轮没有读取现场控制记录验证次数；源码确认的是允许反复重写的机制，不是固定 8 次的重试策略。

### F4：确认，需修正“复用记录即可”的实现成本

`runs.py::record_activity` 只更新时间并插入 run_activity(activity, recorded_at)。Root 的 `mcp_root_run_routes.py::_run_status_value` 已暴露终态 reason，但无拒绝详情与次数；因此并非所有故障都不可见，缺的是 running 拒绝摘要。

次数可从既有 output_rejected 活动派生，原因此前没有持久化，必须做一个小的追加列迁移，不能声称只改投影就可恢复历史详情。摘要不可含自由错误消息、payload、文件内容或内部标识。现有 SemanticRuleViolation 的字符串不天然安全，截断也不是脱敏。

### F5：核心确认，历史成因证据不足

`tests/operations/test_tcad_result_analysis.py` 使用手造 manifest 与对应产物，不能证明收集器额外日志可交接。其 `test_no_contract_author_review_package_execute_preflight` 以两个参数调用 `test_l4_local_tcad.py::test_materialized_sprocess_author_review_package_preserves_case_anchors`，当前后者必需第三参数 produced；静态调用失配确认，未执行所以不声称观测到测试失败。

“此前每一轮为何漏掉”的组织性归因，以及以前打包修复的实际部署效果，本次未独立重放，证据不足。可保留为待验证背景，不能作为修复已有效的凭据。

### F6：局部事实确认，本次不扩张

`deploy/install_ssh_tcad_runner.sh` 的安装及升级探针请求 tcad_capabilities；`ssh_transport.py::handle` 另将 lookup_submission 映射到 tcad_lookup_submission。因此能力查询与其他正式接口的覆盖不同。此次未独立走完部署到正式执行路径，不能把现场 unknown runner tool 的具体根因确认为已复现；不将部署探针或另 12 个接口自动纳入输入校验修复。

## 最小性与剩余风险

现有 guard 只收到 `(BoundInput, parameters)`，其中没有原字节读取上下文，且 parameters 被明确禁止。不能偷塞字节/读取器到 parameters，或让领域 guard 绕过声明读取存储。现有 output context validator 需要尚未产生的 payload，也不能直接在准入调用。一个默认空的 Operation 输入校验声明（实现引用、稳定规则编号和说明）是必要的窄扩展；复用现有 validator 组件、编译引用闭包、读取器和输入描述符即可，不需要新增组件种类、通用依赖图或新状态。

Root 两个公开入口共同调用 `_prepare_operation_call`，而 `RunService.create` 另可直接接收 BoundOperationCall。这两个真实边界都需落实输入检查，不能只在 Root facade 加条件。提交复核和公开 validate_candidate 的输入错误分类也需一致。

尚未以测试证明安全脱敏、并发提交下摘要计数和新旧安装兼容；这些是计划验收项，非本次通过结论。随附计划为下一次实现和独立评审提供具体对象，不授权实施或重新执行研究。

最新规划约束要求宏观抽象而非特例补丁。随附计划因此先定义冻结输入成立性、提交完整性与候选输出正确性的通用责任，再用单一编译输入声明贯通目录、模型合同、准入、创建和提交；TCAD 是首个纵向迁移。日志接收方式只是领域语义，不能替代框架责任闭合。新增声明并不自动证明其他 Operation 的 Python 前提已分类，需要后续基于实际失败逐项迁移，不能声称全框架已无此类问题。
