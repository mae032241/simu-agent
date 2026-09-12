# R4 最终增量实现审查

日期：2026-09-10。当前结论：**PASS（有界静态实现审查）**。初审 REVISE 的 FCR-1/FCR-2 已经两轮实际源码复核闭合，详情见文末；下文发现保留为修复记录。这不是完整测试验收或部署批准。使用 `scid-cross-boundary-review`；未运行测试、编译、安装或求解器，未创建子 Agent。

基准：HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`，工作树包含大量前史。本审查按 R4 计划、MIGRATION_INVENTORY、EXECUTION_RECORD、RECOVERY_CODE_REVIEW 界定范围，不把整个 dirty diff 当成本轮增量。此前系统崩溃用户已确认来自另一个程序，本报告不将其归因于本任务。

## FCR-1：非通过 TCAD 审查仍被被审输入的参数错误阻止（阻断）

位置：`plugins/tcad_artifact/tcad_artifact/project_packager.py::validate_deck_review_task_output` 调用 `_validate_approved_parameter_bindings`，审查时行 1318–1320；helper 行 1341–1348、1364–1369。

触发：被审 project 引用不存在的 approved_parameter_key，或 coverage 对其为 missing/conflict/not_comparable；reviewer 正确交付 revise/reject，指出该问题。当前调用虽传 `require_implementation=False`，helper 仍无条件拒绝上述 project/parameter 输入关系。没有参数上下文但 project 声称 approved binding 的分支同样如此。

影响：这是纯冻结输入条件，修改审查输出无法解除；真实 context → `SemanticRuleViolation` → `RunOutputError` 将其报告成可修候选错误。它属于本轮明确要清理的存量职责越界，不是声称这些 helper 分支均由本轮首次引入。只给 coverage.status/value/unit 的部分检查增加条件尚未闭合整个审查入口。

最小修复：非 pass 审查跳过对被审 project 的参数实现有效性要求，保留 report 与 project 的身份、要求覆盖、证据及 handoff 对照；author 和 passing review 保留防虚假成功校验。不要将“被审对象必须没有参数错误”机械迁成审查准入条件。验收应覆盖 unknown approved key 和不可用 coverage 的非 pass 审查可正式提交，pass 仍拒绝。

## FCR-2：admission_defect 目前没有实际分类产生者（中等，合同缺口）

位置：`service/run_outputs.py::validate_run_output` 的 context 通用异常分支及各 context 的冻结输入解析。

静态搜索中 `admission_defect` 只出现在 RunCheckerError 和安全摘要的允许值里。比如 context 对冻结源 `model_validate_json` 解析失败，经通用异常分支统一得到 `checker_failure`。R4 规定解析实际暴露准入漏检时应标记 admission_defect；当前无法在安全摘要中区分准入缺陷和 checker 实现错误。

这不等于成果丢失或可修拒绝：当前此类异常已经走 failed/保全。最小修复是在实际必要的源解析边界分类准入缺陷，保留普通实现异常为 checker_failure；不得在 submit/preview 重跑 input_validation 来主动找输入错误。补一条人为准入漏检的实际提交分类验证。

## 已检查且未发现新增阻断的路径

- `InputValidationSpec` 经声明、catalog 可达 validator/resource 校验进入编译身份；目录 `scheduler_operation_view` 与 Root 的真实 `model_dump` 投影保留独立 input_validation，未替换 input_admission。Worker payload JSON Schema 使用同一 projection helper；assignment 使用该 schema。
- Root preflight/invoke 共享 `_prepare_operation_call`；服务 schedule 从 Artifact 注册记录重建 schema、媒体、字节预算、父链、标签和 current，再调用共享 preflight。纯输入 checker 仅在创建前接入；submit、preview、validate_run_output 未调用它。
- general critic/hypothesis/experiment/revision/object review、parameter audit、runtime author、TCAD analysis 的表列输入规则已沿实际上下文入口核对。curve contract review 不再要求被审合同先通过机械验证；figure request 的请求恢复仍依赖候选，属于输出检查。FCR-1 是该迁移面的残留。
- TCAD analysis 的 diagnostics/solver_outputs 分端口，输入 manifest 关系在准入；输出检查保留实际引用、计划/案例、计算重放及失败/缺产物时不得夸大成功。未看到将可选评分工具变成 Run 提交硬前提。
- `_compiled` 在 finalizer 前核对原合同；`_validation_inputs` 核对冻结身份/字节，不重查 current 科学资格。submit/preview 的完整性错误归 failed；accepted candidate 与发布/完成 CAS 保持原有幂等路径，未被统一吞成可重开失败。
- 恢复合同不可用时不调用新合同 hook，不以 output 候选证明 deck 完整覆盖；pending 保留完整快照标记；discard 在删除隔离目录前校验恢复副本，重启幂等分支同样重算摘要。旧预算未知且旧合同不可得时不猜测放行。
- draft_from 在 Root 和 Run 请求摘要中包含来源与受控摘要；与 resume 互斥。schedule 在事务内复核实例、Operation ID、backend 身份/能力、文件摘要和混合恢复链预算；strict resume 仍要求原合同与有序输入一致。Root 只投影来源和恢复状态，不发布未验收草稿内容。
- 新增 None 字段仅在规范化 OperationSpec 时窄省略；启用规则、可达组件及 reviewer 摘要会改变真实身份，不假装兼容旧活动 Run。安全诊断不持久化原始异常值，拒绝次数由活动记录派生。

## 证据与审查限制

只读观察 Root 已落盘日志：`check-1789031531661894904.log` 为 L2 两文件 32 passed；`check-1789031658993188878.log` 为 hypothesis routing/revision/curve/parameter 组合 65 passed。对应 checks.jsonl 显示成功退出，测试树峰值分别 164474880 和 111931392 字节。没有自行运行或把先前失败命令改称成功。

这两组结果不能替代尚由 Root 进行的最终目录闭包、真实安装入口、历史身份传播矩阵、FCR 修复验证及剩余定向测试；测试尚未结束本身不作为代码缺陷。没有完整发布前目录与 after 对照时，不宣称所有历史资格影响均已量化。未审查无关部署脚本、先前目标 schema 演进或其他旧 diff 的整体正确性。

FCR-1/FCR-2 已及时发送 Root；修订后应重新读取实际修改并更新本报告状态，不能仅凭修复者消息改判通过。

## 第一轮修订复核

重新读取实际文件，FCR-1 静态闭合：`validate_deck_review_task_output` 仅在 report.verdict 为 pass 时调用参数实现 checker；author 路径不变，report/project 及 handoff 校验仍执行；review_context 配置身份为 `input-boundary-r4:v2`。新增测试源码包含实际 Root/Worker 的 unknown approved key 非通过提交，以及 conflict coverage 非通过允许/pass 拒绝。未自行运行，执行结果待 Root。

FCR-2 部分闭合：新增 `BoundSourceError`、`parse_bound_json` 仅转换源解析的 ValidationError/UnicodeError；context 捕获该错误并映射 admission_defect，不重跑输入checker，其他异常继续 checker_failure。已阅读 TCAD 故意遗漏准入、接受 malformed manifest 后正式提交 failed 且 delivery_preserved、零 rejection 的测试源码。

仍需补齐变量承载的实际冻结源解析，例如 `_hypothesis_objective_context` 的 raw_prior、`_validate_parameter_uncertainty` 的 raw，以及 project_packager 的 prior_raw/experiment_plan/parameter_raw/coverage_raw。它们并非候选，但尚未使用新分类。另须确认新触及的 curve diagnosis_context/curve_contract_context 等组件最终身份有变化，避免新错误分类代码验收旧合同而摘要未变。以上已发送 Root。

## 第二轮修订复核与最终静态结论

重新读取上述指定实现后，确认 FCR-2 已指出的解析边界补齐：raw_prior、parameter_uncertainty.raw、parameter checklist.raw、project_packager 的 prior_raw/experiment_plan/parameter_raw/coverage_raw，以及 reviewer 对冻结 DeckAuthorResult 的解析均使用 parse_bound_json。候选 payload 仍按原输出解析，不会因本次包装变成输入责任。curve diagnosis_context 与 curve_contract_context 均已加入 `input-boundary-r4:v1` configuration_identity，由现有可达组件摘要机制传播。

FCR-1 复核仍成立：非 pass 审查跳过被审项目参数实现检查，author/pass 路径保持严格。FCR-2 已有明确 admission_defect 产生与封存路径，无新增 submit/preview 输入checker调用；异常类别范围修订没有改变控制／科学输出责任。

本次只复核已指出项，不扩大为所有确定性 transform、批准 projector 或输出自身 parser 都必须使用输入故障分类。当前有界静态范围无未解决阻断，结论更新为 PASS。测试源码阅读不等于执行通过；Root 尚在串行运行的测试、最终动态目录/兼容矩阵与发布验收仍由 Root 单独汇总，不因本结论自动通过。

## 最后身份增量与执行证据补记

仅复核收尾增量：`parameter_operations.py` 的 parameter_extract_context 已加入 `configuration_identity="input-boundary-r4:v1"`，与 required checklist 冻结源解析分类变更对应。没有据此重开无关实现审查，静态 PASS 不变。

只读确认 Root 已落盘的新证据：

- `check-1789032300278621979.log`：通用合同、hypothesis objective、curve/parameter 和 figure 定向组合 **169 passed**。
- `check-1789032086367758731.log`：TCAD 定向组合 **36 passed, 1 deselected**；本轮源码包含 admission omission 的正式 Run 保全用例。
- `check-1789032167554047346.log`：installed 入口组合 **5 passed**。
- 最终 TCAD wheel 重建并重装后，`check-1789032394828237590.log` 明确报告 installed Root/Worker 输入合同 **13 Operations 一致**且声明 draft_from。
- `check-1789032395794690422.log` 与 catalog-source.json 来源表明最终源码默认目录 45、含 figure 目录 50。Root 汇总其相对已部署环境为 20 changed、30 unchanged；该汇总是部署版本对照，不冒充本轮修改前干净工作树基准。

以上均为读取父进程记录，不是本审查自行执行。读取时另有后续组合 `check-1789032436800051009.log` 在 next_design preflight 断言失败（14 passed 后停止），仍由 Root 定位；本报告不将未定位的断言直接判作本次 identity 修订缺陷，也不把该命令计为成功。最终全任务通过数、剩余失败处置、兼容传播与发布结论以 Root 完整执行记录为准；有界静态 PASS 不覆盖部署或真实求解器。
