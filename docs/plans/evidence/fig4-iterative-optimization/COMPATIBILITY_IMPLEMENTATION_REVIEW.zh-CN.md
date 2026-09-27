# 历史科学记录兼容性修复独立实现复核

结论：**PASS。当前生产实现符合已通过的 R1 计划，未发现阻断缺陷。** 无需增加兼容性状态、摘要体系、输入复审或输出回放。测试执行与最终验证汇总由主代理负责；本报告是独立工程源码复核，不是部署或科研验收。

日期：2026-09-12。基线：`be5da77acdbf98054e0b096fc4e940de560d4ba1`。复核对象为该基线到当前工作树的三处生产修改、双语架构说明、`test_completed_science_compatibility.py` 和 `test_m6c_producer_topology_removal.py` 的修改。独立复核只读取源码、测试和已有日志，仅新增本报告，没有运行测试、构建、科研控制工具或外部执行，没有修改他人文件。

## 生产边界核对

| 路径 | 实现与判定 |
| --- | --- |
| 已完成输出与旧 PASS | `service/runs.py:889` 新增的小函数只检查 completed、有输出、原 operation id 对应的当前 version，以及原输出端口的 schema/kind/media。没有比较运行 digest，也没有改写 Run、Artifact 或历史标记。`is_exact_reviewer_output` 仍先从精确输出的 completed Run 匹配指定 reviewer、原 subject 和允许 verdict。符合 P1。 |
| 两次审查查询 | `interfaces/mcp_root_operation_routes.py:1471` 的第二次 `require_compatible=False` 查询仅在第一次没有合格审查时执行，其真值直接导致 incompatible 异常；不会给 `reviewer_output` 赋值，也不会添加已消费信号。直接修订入口 `:1552` 同样只有拒绝路径使用该选项。新诊断没有形成第二条授权路径。 |
| 历史 claim 与端口类型 | `_operation_output_contract` 的普通路径仍拒绝 version 不一致；原 prior/revision 跨版本路径继续存在。类型检查条件为 `allow_historical or compiled.digest != digest`，因此新放行的同版本 digest 漂移也经过 schema/kind/media 检查。保留完整来源字段和端口存在性检查，没有把 claim 改成 inventory。 |
| 诊断包装 | Root 保留 reason、field、原 message，并补入实际输入 port。`OperationInvocationError` 构造器始终生成含 message 的单项 details，因此访问 `error.details[0]["message"]` 有现有合同保证，无需再增加兜底验证。 |
| 原人工决定 | `service/approvals.py:313` 的兼容选项默认 False；Root 只对非 effect 消费者启用。服务内部又限定 kind 不是 execution_authorization。兼容比较仅省略 operation_digest，仍比较原 provider id/version 和 approval_contract_digest。请求、决定、subject set、选项和完整性检查保持原样。没有创建决定或改变请求状态。 |
| Run 开启、提交与恢复 | `_compiled`、`validate_resume`、`_recovery_digest` 和提交/完成路径没有变化。新兼容帮助函数只被两处已完成读取接口使用；没有成为活跃 Run 的实现查询函数。已有 `draft_from` 新 Run 路径未收紧，也没有扩大权限。 |
| 外部执行 | `mcp_root_execution_routes.py` 与 `service/executions.py` 对基线无差异。执行审批 snapshot 虽使用默认 signal 读取，但先经过 `_current_execution_contract` 的完整身份比较；`ExecutionService.authorize` 仍比较执行请求与批准的完整编译身份和精确 request/payload。展示旧 handoff 不等于使用旧批准执行新合同。 |
| 来源、实例与当前对象 | `_run_output_family`、`_transform_output_family`、`_is_historical`、实例绑定、current 和非合格状态检查未改变。原 Run 与 Artifact、原变换兄弟之间的 digest 完整性比较继续保留。共享 `_prepare_operation_call` 继续同时服务 preflight 与 invoke。 |

上表核对了主调用与实际旁路；没有发现把“与当前实现兼容”误用于“原记录间身份一致”的位置。输出端口元数据在 Run 和 Root 各有一处小型匹配，分别服务完成 Run 与包括 transform 在内的输入记录；不值得为这几行判断增加跨层通用模块。

## 测试审阅与已见证据

新增兼容用例先通过真实 Root/Worker 生成 completed 输出与审查，再编译同版本而不同 digest 的目录进行消费；成功路径继续打开新 Run 并提交。人工资格用例经过真实请求、UI 决定记录及 Root 消费，未将批准服务 stub 为 True；同时验证默认服务模式仍严格、批准合同或版本改变仍拒绝，以及原对象以外的相同内容不能继承决定。直接修订用例分别覆盖旧兼容非通过审查的复用和 reviewer version 不兼容的明确拒绝。新增跨实例 preflight/invoke 拒绝检查与实例边界相符。

复核时发现的一个覆盖缺口已补齐：旧 schema 负例只经过 `allow_historical=True`，没有覆盖新增加的默认 claim 路径。当前新增 `test_same_version_runtime_drift_preserves_claim_port_type_boundary` 明确使用同 version、不同 digest、默认 `allow_historical=False`，先验证兼容正例，再验证 schema、kind、media 三项不兼容均被拒绝；无需再增加生产校验。

已直接读取主代理生成的以下日志，并核对 `checks.jsonl`，没有自行运行或重跑：

- `check-1789226162306468628.log`：兼容回归最初 7 例通过。
- `check-1789226307248065546.log`：直接修订新增 2 例通过。
- `check-1789226345730083881.log`：相关 review/admission/m6c 边界 38 例通过，排除下面明确的基线失败 1 例。
- `check-1789226395060751589.log`：历史兼容路径与外部执行批准身份 21 例通过。后者包括同批准合同、不同 operation_digest 的错误执行批准身份负例。
- `check-1789226438141467503.log`：17 例通过，含前面 3 例重测及 14 例新增检查；覆盖默认 claim 类型边界、补入的跨实例检查、Run 合同不可用、恢复身份、跨合同 draft、旧 Run 投影，以及真实 stdio Worker 子进程打开、工具调用和提交。

上述成功批次共覆盖 82 个不同用例，后补类型与跨实例检查已有末批日志支持。最大进程树 RSS 为 192,790,528 字节，约 183.9 MiB；记录中没有资源中断。最终 `git diff --check` 与最终验证汇总由主代理记录，本报告不代替该执行证据。

`test_agent_inventory_exception_has_an_explicit_complete_consumer_inventory` 的失败已在当前树日志 `check-1789226188724190428.log` 和隔离基线日志 `check-1789226245398448290.log` 中呈现相同旧目录断言差异，主要涉及已有 result analysis 端口清单。该硬编码断言不在本轮生产修改范围内。保留失败记录、只从本轮相关验证选择中排除该单例，符合最小修复原则；不能将整个测试文件报成全绿。本轮确实修改的旧 digest 策略断言已改为保留版本不兼容拒绝，没有删除 review/usage 限制。

## 完成边界

双语架构说明与实现一致：同版本原科学证明及同批准合同的原人工决定可复用；原来源 digest 与历史标记继续保存；新对象不继承旧证明，活跃 Run 和外部执行仍需完整身份。没有发现应由本轮追加的生产机制或必须继续修代码的事项。

本结论限于上述工作树实现与所述日志快照。未验证安装包、重启后的实际服务、线上历史库或求解器执行；这些不在本轮独立源码审查授权内。上线后仍应对原两份精确绑定重新 preflight，不复用安装前结论，也不据此声称总体科研目标完成。
