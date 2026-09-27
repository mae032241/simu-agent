# 假设反馈实施收尾

日期：2026-09-16。用户授权补齐实施复审的两个收尾点。源码修复、定向与 wheel 测试、三组合成真实模型行为验收及[最终独立复审](../../reviews/HYPOTHESIS_FEEDBACK_CLOSEOUT_REVIEW.zh-CN.md)均完成。控制层增量和既定有限行为验收 PASS；科学产物的两个数值缺陷单列，不能据此判定科学质量通过。未部署、未写入生产 Fig4 实例。

## 生产修复

仅两处生产增量：ScientificReview 的机械 handoff 映射补 `blocked -> blocked`；对应共享 result_finalizer configuration_identity 更新为 v3。不更改 Schema 合法值、不放宽来源或 pass 资格。

既有测试扩展到五种 ReviewVerdict，blocked 测试不再手填 handoff，真实 Worker 提交后验证精确 blocked 匹配成立、pass 匹配不成立，再将原件绑定为下一轮 current_progress。

最终定向批次 45 项通过，37.17 秒，峰值 144,060,416 B，无预算终止。日志：`../hypothesis-feedback-implementation/check-1789541989950594729.log`。含历史完成对象兼容性与假设反馈闭环；未运行全量测试。

共享 finalizer 的编译身份影响 16 个 Operation，见 digest-changes.json；这不是 16 处业务改动。旧封存结果按原兼容规则读取，旧在途合同不静默续接。

## 独立源码审查

独立审查者 blocked_closeout_review 只读审查结论 PASS：新增映射保持科学 verdict，不授 pass 资格，版本身份进入实际编译摘要；未发现指定增量阻断问题。审查者没有跑测试或生产操作。

审查建议已落实：隔离 probe 的审批 fixture 限于本实例精确 foundation、scientific_foundation kind、approve option 与 science.evidence.qualify.v1 provider；说明明确人工历史输入是 fixture，新 Agent 输出不能预制。

## 真实行为验收方法

live_probe.py 只管理 `/tmp/scid-feedback-closeout` 中的人工合成案例，调用新源码实际编译的 Operation，严格 preflight normalized_request -> invoke -> 生成角色 -> 独立 CLI Worker -> worker_submit_result -> completed 后读取。仅既有 foundation 人工决定用限定 fixture 替代，不产生审批或执行操作。

三个案例：B1 有效反例，B2 无有效结果的数值失败，B3 现有观测不能区分候选。新 proposal/critic/design 由真实 Worker 生成；不读取其聊天作为科学结论。请求配置一致为 gpt-5.6-sol / medium，中文叙述。完整声明、精确请求、封存状态、launcher receipt 和工程日志保留。

本地 pytest 仍为 2 GiB / 180 秒串行。真实模型 CLI 由既有 launcher 的 1 GiB 进程树保护，使用 Operation 已声明的 Run 时间预算；一次只运行一个 Worker，不并行构建或测试。

## 测试环境错误追踪

- 初始隔离脚本漏了 figure 插件的 Python 导入路径；补齐测试路径。
- 父脚本同时加入源码元数据与临时 entry point，触发 duplicate builtin；移除父脚本重复元数据路径，Worker 保留独立目录。
- 原单实例 fixture 的 idempotency key 在三个测试实例复用；改为实例限定的测试登记键。
- 测试 runtime 未初始化审批服务；补入仅测试使用的 receipt secret。
- 合成 foundation 把人工条件标成 inference 却漏 rationale；preflight 精确拒绝该项。修正测试输入，保留旧失败实例，不放宽校验。
- 第一 CLI 启动缺临时项目 Git 标记，尚未领取 Run 即退出；初始化临时 Git 目录后启动。生产仓库未改。
- 第一模型尝试被测试脚本额外的 165 秒限制终止，未提交；不是 Operation 的 900 秒超时。控制层拒绝将未到 deadline 的 Run 标成 timed_out，随后按外部进程中止记录 failed，保留交付，人工检查恢复状态后显式将该恢复链预算从 1 设为 2，精确输入与合同续接；未增加原 Run 时间或掩盖历史失败。

### B1 当前结果

proposal_retry、critic、design 三个新合同 Run 均 completed。旧 y=2x 在有效反例下被替换；critic 明确新两个解释仍不可辨识；design 选择一个非整数判别点和同轮控制，未机械重复参数扫描。未授权或执行新的测量。设计有一次 output_context 拒绝（新设计应使用 validation_intent，而非旧 validation_plan），具体诊断已保留，Agent 在同 Run 修正后完成。此处只判断反馈与行为路径，不把未经 object review 的设计当成可执行或全部数值无误的实验计划。

### 安装包验证

最终源码重新构建隔离 wheel，12 项 installed 测试通过（58.53 秒，监控总批 59.27 秒、峰值 228,438,016 B），日志 `../hypothesis-feedback-implementation/check-1789542717703608083.log`。安装包额外逐一检查 ScientificReview Schema 的五种合法 verdict 都能生成 handoff，包含 blocked；源代码与 wheel 编译身份保持一致。

### B1 独立行为复核与科学限制

独立验收者读取三个 completed 的正式输出与 signal，结论为“限定行为 PASS”：反例改变候选，critic 保留不可辨识性，design 转向差异预测。未读取聊天作为科学结果。

同一复核指出设计自身的误差预算问题：两端输入各允许 ±0.005，仿射配对差最坏界应为 `0.02+0.02+2*(0.005+0.005)=0.06`，原设计写 0.05；相应保守区间应为 [0.44,0.56]。没有声明输入误差抵消关系。该科学产物未经过 object review、未获执行许可，不用于生产或真实测量。此缺陷属于科学设计内容，不能归责控制层映射或以新增控制校验器“修复”。本轮验收只证明已批准的 B1 反馈行为，不声称科学计划质量验收通过。

### B2 当前结果

proposal 与 critic 均 completed，均无提交拒绝。提出者保留原线性机制，明确 points/reference_measurements 为空、旧预览无效，不以 Newton 不收敛作为机制反证；新增竞争候选明确为待检验假设而非失败运行所支持的解释。critic 的封存摘要同样指出失败既不支持也不反驳机制，建议取得有效独立响应。未强制进入 design 或外部执行。

独立复核另发现饱和候选的数值区间漏计内部极值：`C(s)=-4s/((1+s)(1+2s))`，`s∈[0.25,1]` 的最小值在 `s=1/√2`，模型区间约为 `[-0.686292,-0.533333]`，原 proposal 写 `[-0.667,-0.533]`，critic 未指出。该区间仍与线性候选的零 contrast 分离，不推翻 B2 的限定行为验收，但不能据此认可全部科学推导。原封存记录保留；未将这项科学内容缺陷转为控制层校验规则。

### B3 与实际运行总计

proposal 和 critic 均 completed、均无拒绝。两者明确现有 x=0,1 观测同时符合线性与二次候选，不支持选赢家；原候选保持，x=2 是后续有区分力的观测条件。本例没有启动额外 design 或执行。

三个案例合计 8 个 Run：7 completed、1 failed（外层测试限制）。全程 1 次输出拒绝（B1 design 的旧验证表达，已同 Run 修正）。独立 CLI 共 9 次启动：一次 Git 标记不足、一次外层 165 秒中止、七次正式完成；完整 launcher receipt 保留在 records/launch-receipts。最高观测子进程树 816.34 MiB，1 GiB 守卫未触发。测试、构建和实际 Worker 全部串行。

正式科学内容只从 completed 的 Root run_status 读取。records 保留封存内容、signal、具体拒绝、精确绑定与配置；不复制模型聊天或认证文件。请求模型配置来自新 Run 的 execution_profile，launcher 记录同一配置；此处不声称拿到了服务提供方内部模型遥测。未部署生产、未运行 TCAD、未替用户批准真实执行。
