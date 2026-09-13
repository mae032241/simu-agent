# Fig.4 历史科学记录兼容性最小修复计划

状态：R1，独立计划审查 PASS，源码实施及独立实现复核 PASS，尚未部署。2026-09-12。见 [计划审查](COMPATIBILITY_PLAN_REVIEW_R1.zh-CN.md)、[实施记录](COMPATIBILITY_IMPLEMENTATION.zh-CN.md) 与 [实现复核](COMPATIBILITY_IMPLEMENTATION_REVIEW.zh-CN.md)。

## 目标与恢复点

用户要求先保存当前版本，计划经独立审查通过后执行，最小改动，不增加无用校验。修复前检查点为 `be5da77`，标签 `checkpoint/fig4-before-historical-compatibility-20260912`，包含当时全部源码、测试、计划与本地诊断记录；本次修改以它为唯一 diff 基线。提交不是新的部署/科研验收声明。

解除两次已复现的非科学阻断：同一历史假设的已完成 PASS 因 reviewer 全量 digest 变化被当成“没有审查”；重新审查又因 foundation 生产者 digest 变化被拒绝。并处理同一资格链中的已有人工审批比较，避免修复前一关后落入同因的下一关。

科学进展保留：`fig4_iterative_alignment_scope_review_1` 已完成；`fig4_iterative_alignment_plan_revision_1` 仅预检通过，未创建 Run。这里不改任何科学记录、不生成数值候选、不运行求解器。

## 现状和原则

`RunService._compiled` 用完整 Operation 版本与 digest 判定旧 Run 能否按当前实现继续。这一严格条件被 `is_exact_reviewer_output` 和默认 `signal_for_output` 用来读取已完成审查的证明；Root `_operation_output_contract` 又将它用于 claim_evidence。人工资格匹配比较完整 `CompiledApprovalIdentity`，使无关实现变化也可能撤销已有决定。

本轮采用已有字段，不新增兼容性注册表、摘要体系、数据库迁移或状态机：

1. 完整 digest 是运行实现身份和溯源事实，保持原值，不用它单独撤销历史科学记录的效力。
2. 复用同一科学记录，以已有 Operation id/version、输出端口的 schema/kind/media 和当前消费者已有输入检查为兼容边界。版本相同且结构仍受支持时，提示、工具、预算等导致的完整 digest 漂移不单独阻断。科学含义不兼容的改变必须提升已有 Operation version 或 schema；不靠程序推断科学语义等价。
3. 审查证明仍必须来自 completed Run、对应指定 reviewer、精确 subject_ref 和允许 verdict。旧审查不适用于新 Artifact 修订，背景阅读不产生资格。
4. 既有 `prior_signal`/`revision_base` 跨版本阅读/修订能力保留；跨科学版本的旧审查仍不能提供当前证明，须对原记录发起适用的新审查。
5. 输入准入只在 preflight/invoke 的共享准备路径处理，不向 Worker 输出提交添加输入复审。当前 Run、恢复、外部执行及执行批准继续使用完整运行身份。

## 实施步骤与文件边界

### P1：复用已完成审查与交接

文件 `src/scidiscovery/artifact_agent/service/runs.py`。

- 将已完成结果读取所需的兼容判断与 `_compiled` 分离，使用已保存 Run 与当前输出端口信息，供 `signal_for_output(require_current=True)` 和 `is_exact_reviewer_output` 复用。同版本不同 digest 可消费；版本/输出端口类型不兼容返回不可用。
- 保留原函数的 completed、精确产物、reviewer、subject 和 verdict 条件；先判断是否为该对象的审查，再判断兼容性。
- 为 Root 区分“无匹配审查”与“有匹配但不兼容审查”，允许只查询既有精确审查关系、不给予兼容资格的内部查询选项。不要修改 `_compiled`、validate_resume、submit、finalize 或 SQL 表结构。

### P2：修正历史输入准入和诊断

文件 `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`。

- `_operation_output_contract` 不因同 version 的 digest 漂移拒绝 claim/change_request/review_signal；保留已有端口类型兼容、独立审查、非合格信号、实例和 current 检查。输出端口不兼容仍拒绝。
- 继续允许既有 prior/revision 的跨版本背景/修订消费。不要通过把 claim 改成 evidence_inventory 来绕过资格。
- 无精确审查保留 `input_independent_review_missing`；存在精确审查但版本/输出类型不兼容时给出单独诊断 `input_independent_review_incompatible`。这是现有拒绝的分类，不是新增准入要求。说明应重新审查原对象，不要求作者补字段或改科学答案。直接修订 change_request 的同类拒绝也给出明确原因。
- 重新包装异常时保留已知原因及端口，不能再次退化成泛泛消息。无需新增诊断对象/通用错误机制。

### P3：复用原对象的科学人工资格

文件 `src/scidiscovery/artifact_agent/service/approvals.py` 及 P2 的调用点。

- 复用现有 `are_subjects_approved_by_provider`，默认仍严格。仅在 Root 普通研究输入资格消费时启用兼容匹配：原决定的 provider operation id、version、approval_contract_digest 与当前已声明 provider 一致即可，不要求完整 operation_digest 相同。
- 原有 request/decision 关联、subject_refs、subject_set_sha256、kind、选项、完整性检查全部保留。只复用用户对原精确对象已作出的决定，不新建/代写决定。
- 不对 effect 或 execution_authorization 开启这项放宽；新执行请求、旧执行恢复、审批过期/取消、改过的批准合同仍走原严格路径。不给 Root 额外写审批权限。
- 审批展示读取同版本历史 sealed handoff 使用 P1 共用逻辑，不把它改成“当前 Run”。

### P4：定向验证与最少文档

测试以现有真实 Root/Worker/临时状态 fixture 为基础，新增一个兼容回归文件；必要时只调整与明确改变的旧 digest 策略相冲突的现有断言。不裁剪其他边界测试，不靠 mock 掉准入证明闭环。

必须覆盖：

1. 原生产者与 reviewer 的同版本 digest 变化后，旧原对象+旧 PASS 可 preflight 并 invoke；新 reviewer 也能绑定旧 claim foundation。至少一例走 Run 创建、打开、提交，证明不会提交时再因输入版本失败。
2. 真实已封存人工资格在 provider 同版本、同批准合同但 digest 改变后能被 Root 研究输入消费，preflight/invoke 一致；不能只 stub 审批服务返回 True。
3. 新对象配旧审查、非通过审查、不同 reviewer、版本或 schema 不兼容、缺失/改过的人工批准、跨实例引用保持拒绝，并辨明有审查但不兼容与无匹配审查。
4. `_compiled`/旧 Run 续接依然拒绝完整运行合同变化；外部执行仍需精确批准，执行合同漂移不被本轮放宽。
5. 已有历史背景可读、旧非合格状态保留、来源族身份与直接修订限制不回退。

每次一个 pytest 进程，关闭插件自动加载、BLAS 单线程；复用现有 check.py 的 512 MiB 地址空间/进程树 RSS、150 秒墙钟与 120 秒 CPU 限制，单文件超时则按必要用例拆分，不扩预算、不并行、不跑全量。测试候选：新增兼容文件，test_historical_compatibility_paths、test_review_admission_integration、test_l3_review_and_human_policy、test_m6b_operation_input_admission、test_r4_execution_approval_identity，以及实际涉及的旧 Run/来源族单例。首个相关失败先定位再继续。

独立审查补充验收：纳入 `test_m6c_producer_topology_removal.py`，同 digest 策略断言改为兼容/不兼容版本行为；历史标记与来源族原 digest 必须保持；外部执行负例单独隔离“同 version、同 approval_contract_digest，仅完整 operation_digest 改变”。`signal_for_output` 用于执行 snapshot 只提供展示，执行身份仍由原 `_current_execution_contract`/`ExecutionService.authorize` 检查。

做 `git diff --check`，同步 `docs/ARCHITECTURE.md` 与 `.zh-CN.md` 中历史复用语义，记录测试命令/峰值/未验证项，独立复核最终 diff。当前源码测试不宣称线上已修复；安装重启后对先前两份精确绑定重新 preflight，不能复用安装前预检结论。

## 不在本轮做

- 不新增 hypothesis 的结果/分析/current_progress 端口；它是已识别的后续反馈缺口，单独实施，不伪称本轮已让科学闭环完善。
- 不改 Operation 编译摘要、output Schema/校验器、审批 UI、VM runner、求解器、预算策略。
- 不重算历史结果、不把旧 PASS 继承给新科学对象、不绕过已失败 preflight。
- 不迁移/改写线上历史记录或部署，部署后保留原科研停点继续。

## 审查和完成标准

独立审查目标定位、工程可实施性、研究/执行边界、最小变更以及是否引入无意义阻断。发现阻断先修计划并复审，通过后才修改生产代码。完成时报告 checkpoint、实际修改范围、定向测试与未部署状态。若代码发现超出这三处同因路径的问题，先记录，不借本轮扩大框架。
