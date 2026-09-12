# R4 安装后真实记录验证

2026-09-10。实例 M7-test0 已绑定，新目录明确暴露 input_validation 与 diagnostics 端口。线上验证尚未通过；本次没有创建新分析 Run、派发 Worker 或执行求解器。

原 fig4_continuation_execution_analysis_1 仍为 failed，8 次拒绝；无封存分析，恢复状态 pending，不将它作为可用草稿。原 execution_1 已 collected，execution_outputs 返回 solver_log、fig4_al_own_anchor_primary_plx、tcad_log、tcad_manifest。

新请求 fig4_continuation_execution_analysis_2 使用 catalog 中 tcad.result.analyze.v1，精确绑定：

- experiment_plan：fig4_continuation_experiment_plan_3。
- experiment_review：fig4_continuation_experiment_review_6.output。
- reviewed_package：fig4_continuation_reviewed_package_2。
- runtime_manifest：fig4_continuation_execution_1.output.tcad_manifest。
- solver_outputs：同次执行的 solver_log 与 fig4_al_own_anchor_primary_plx。
- diagnostics：同次执行的 tcad_log。
- reference_material：fig4_continuation_reference_bundle_1。
- current_progress：fig4_continuation_objective_2、fig4_continuation_experiment_intent_3.output、fig4_continuation_execution_1.result。

operation_preflight 返回 admissible=false，reason_code=guard_rejected，port=result_analysis_parentage。未绕过该拒绝；后续内容校验尚未运行，不能宣称它已通过。

已证实的阻断：review_6 的 run_status 为 completed，封存 handoff=pass，sealed_output_status=historical。Root _prepare_operation_call 从 _scheduler_signal_for_output 读取输入判定；该 helper 调用 signal_for_output 的默认 require_current=True。其生产 Operation 摘要已经变化，_compiled 失配后返回 None。analysis_parentage 要求 review.handoff_verdict == pass，因此先被拒绝。相比之下，RunService.schedule 权威重建输入已经使用 require_current=False；二者不一致。

这属于历史事实投影与当前资格混用的兼容遗漏，不是本次输出拒绝，也没有分析候选可供修改。历史封存判定是否可读与当前独立审查/批准资格必须分开。修复应对齐 Root 输入事实投影及服务创建入口，保留现有独立审查、来源、授权和当前资格门禁；不通过重新审查原计划来掩盖投影错误。

现有 collector 交接测试使用同一目录下新产生的 review，因此没有覆盖“真实封存 review → 更新其生产合同 → 旧执行结果进入新分析”的组合。必须补该回归，同时验证旧 review 仍不能为需要当前独立审查的作者或执行动作授予资格。

本次仅定位并记录，未修改生产源码或部署。最终代码静态 PASS 和定向测试通过仍是对应本地范围的历史证据，不能等同于本次线上验收通过。
