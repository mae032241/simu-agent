# 前两项工程修复实施记录

2026-09-13；独立实现复审R2 PASS，绑定R3精确候选。首轮两项缺口及用户追加的4项旧回归问题全部关闭。Fig.4科学任务仍暂停，未创建科学Run、执行或审批。

## 精确范围

本轮仅实现 [PLAN](PLAN.zh-CN.md) 的机械登记清理和失败追溯；第三项数值对照适用范围与实验价值属于科学工作，不改其结论、方法或科学角色。原工作树已有改动，基线为 `baseline.json` 的322文件快照及HEAD记录；本轮差异见 `INCREMENT_R3.patch`，文件摘要见 `REVIEW_MANIFEST_R3.json`，不能拿全部HEAD差异当作本轮修改。

- 删除意图、完整计划及曲线消费者的observable原文登记和基线角色重复要求；同步模型可见合同。明确baseline key保持权威，唯一已标记baseline/control可确定性补全；歧义、未知案例、真实冻结/变化矛盾继续报错，不引入科学依赖判断。
- 保存晚提交、终态工具错误和校验拒绝到原run_activity；不延长deadline、不变更四态或接收迟交成果。同次工具调用开始/结束归属同一Run。
- 原run_status提供按需错误分页，原run_list提供语义名分页，均限实例。默认摘要仍精简；错误保留时间、字段、规则、类别、scoped工程引用。派生输出错误保留其输出归属，删除无效子项引起的假空数组级联。来源工具指出source_aliases索引，不接受未绑定的工作区帮助索引为证据。
- 双语架构同步，没有数据库迁移、通用新状态机、额外Operation或Worker权限。

## 验证与失败归因

所有命令通过本目录check.py串行执行；进程树RSS和地址空间各512 MiB，单批150秒，BLAS单线程。未运行全量、并行、真实Agent或VM求解。git diff --check通过。

新增回归覆盖真实Run提交→物化→修订→审查、正确拒绝后同Run修正、晚提交和终态错误持久性、同Agent新Run调用归属、历史分页和跨实例拒绝、来源错误修正后有限分析提交。隔离环境重新构建core/TCAD/curve/figure wheels，仅从安装包加载生产模块并经过MCP router；没有证明daemon、平台Agent或真实科研链运行通过。 `installed-files-r2.json`逐项确认R2候选12个生产文件与测试wheel的SHA256全部一致。

本轮早期失败原样保留：新夹具缺目录/活动Run槽冲突已修正；基线补全首次触及冻结模型，before-validator方案又破坏严格JSON数组转换，最终在模型构造期沿用SchemaModel的规范化方式；派生错误顶层文本过于笼统已改为具体第一条诊断。首个安装探针因测试辅助模块需要figure插件而缺包，补齐隔离测试wheel后通过，未更改产品依赖。

扩大回归发现4项既有失败：candidate_binding_crash_windows_and_response_replay、status_is_pure_and_failure_recovery_is_explicit、real_process_failure_isolation_windows_replay_after_restart、recovery_without_snapshot_keeps_original_and_reports_pending。baseline_recheck.py在冻结修改前源码中逐项复现，详见原始日志；分别涉及旧错误消息/响应形状断言，以及旧测试要求隐藏工程异常原因与现有共享诊断之间的差异。用户追加要求一并处理后，已修正4项旧断言：检查具体结构化原因、Root错误引用、已耗尽尝试的准确类别，以及原因可见但路径/凭据脱敏。原候选不可变、重试幂等、只读和终态断言保留；后半段恢复代码全部继续运行，test_l2_run_invariants.py最终26项通过。基线复现仍留存，不改写历史失败。

历史分页只能提供run_activity已保存事件：旧数据没有详情时明确null；不能重建历史丢失错误，也没有增加平台/原生进程的无限历史查询。

|命令|退出码|秒|峰值MiB|日志|
|---|---:|---:|---:|---|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py`|1|7.47|126.5|[check-1789293006474927348.log](check-1789293006474927348.log)|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py -k prose_and_baseline or mcp_pages`|1|4.09|134.4|[check-1789293044527284850.log](check-1789293044527284850.log)|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py tests/operations/test_validation_reaudit_removal.py`|1|11.15|124.6|[check-1789293113329764296.log](check-1789293113329764296.log)|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py tests/operations/test_validation_reaudit_removal.py`|0|13.42|125.4|[check-1789293382591771541.log](check-1789293382591771541.log)|
|`python -m pytest -q tests/operations/test_agent_contract_alignment.py tests/operations/test_contract_attempts.py`|1|49.78|138.6|[check-1789293405643330006.log](check-1789293405643330006.log)|
|`python -m pytest -q tests/operations/test_agent_contract_alignment.py::test_experiment_materialized_constraints_are_correctable tests/operations/test_registration_diagnostics_repair.py::test_derived_plan_failure_keeps_payload_owner tests/operations/test_l2_run_invariants.py tests/operations/test_log_preservation.py tests/operations/test_execution_collection.py::test_worker_error_reference_and_tool_time_survive_router_reopen`|1|14.38|187.8|[check-1789293490791311885.log](check-1789293490791311885.log)|
|`python docs/plans/evidence/registration-diagnostics-repair/baseline_recheck.py`|1|3.49|185.3|[check-1789293594907373455.log](check-1789293594907373455.log)|
|`python docs/plans/evidence/registration-diagnostics-repair/installed_smoke.py`|1|7.58|119.2|[check-1789293629203674726.log](check-1789293629203674726.log)|
|`python docs/plans/evidence/registration-diagnostics-repair/installed_smoke.py`|0|13.2|148.9|[check-1789293684353746874.log](check-1789293684353746874.log)|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py tests/operations/test_general_transform_operations.py::test_materialize_maximum_legal_goals_and_current_selection_without_expansion tests/operations/test_validation_reaudit_removal.py::test_curve_compiler_deduplicates_references_without_policing_case_roles`|0|9.94|125.6|[check-1789293735788210725.log](check-1789293735788210725.log)|
|`python -m pytest -q tests/operations/test_l2_run_invariants.py::test_candidate_binding_crash_windows_and_response_replay tests/operations/test_l2_run_invariants.py::test_status_is_pure_and_failure_recovery_is_explicit tests/operations/test_l2_run_invariants.py::test_real_process_failure_isolation_windows_replay_after_restart tests/operations/test_l2_run_invariants.py::test_recovery_without_snapshot_keeps_original_and_reports_pending`|1|3.99|172.7|[check-1789293900570119032.log](check-1789293900570119032.log)|
|`python -m pytest -q tests/operations/test_l2_run_invariants.py`|0|12.97|184.4|[check-1789293928777036466.log](check-1789293928777036466.log)|
|`python -m pytest -q docs/plans/evidence/registration-diagnostics-repair/review_probe_r1.py`|1|2.38|114.5|[check-1789294193778350620.log](check-1789294193778350620.log)|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py tests/operations/test_l2_run_invariants.py tests/operations/test_analysis_evidence_recovery.py::test_corrupt_preserved_receipt_fails_successor_open_explicitly`|1|26.03|192.7|[check-1789294449099322426.log](check-1789294449099322426.log)|
|`python -m pytest -q tests/operations/test_registration_diagnostics_repair.py tests/operations/test_contract_attempts.py tests/operations/test_analysis_evidence_recovery.py::test_corrupt_preserved_receipt_fails_successor_open_explicitly`|0|32.24|134.7|[check-1789294552553085430.log](check-1789294552553085430.log)|
|`python docs/plans/evidence/registration-diagnostics-repair/installed_smoke.py`|0|17.89|149.3|[check-1789294600336208261.log](check-1789294600336208261.log)|
|`python -m pytest -q docs/plans/evidence/registration-diagnostics-repair/review_probe_r2.py tests/operations/test_registration_diagnostics_repair.py::test_failed_reuse_open_belongs_to_selected_run tests/operations/test_l2_run_invariants.py::test_candidate_binding_crash_windows_and_response_replay tests/operations/test_l2_run_invariants.py::test_status_is_pure_and_failure_recovery_is_explicit tests/operations/test_l2_run_invariants.py::test_real_process_failure_isolation_windows_replay_after_restart tests/operations/test_l2_run_invariants.py::test_recovery_without_snapshot_keeps_original_and_reports_pending`|0|8.98|185.9|[check-1789294837272170067.log](check-1789294837272170067.log)|

## 当前交接

首轮独立审查见[INDEPENDENT_REVIEW_R1.zh-CN.md](INDEPENDENT_REVIEW_R1.zh-CN.md)，结论REVISE；不能继承通过。已按F1/F2修正：物化变量错误在构造处保留proposal/variable索引；RunStateConflict仅增加内部已选Run归属，打开/重连失败在共享Worker边界绑定该Run后记录，只有确无新任务时才返回旧终态。服务保留open原异常，外层消息使用同一脱敏原因。新增同Run纠错及workspace失败、重连失败、恢复证据失败、打开前过期分支；源码39项定向回归通过。最终[独立实现复审R2](INDEPENDENT_REVIEW_R2.zh-CN.md)已PASS：19/19候选及13/13 wheel文件独立核对，11项独立检查通过，含非零proposal/variable索引、跨实例失败归属、脱敏/引用隔离、失败后继续新任务、4条open失败分支及4项旧回归。当前未部署，不启动暂停的科学实验。

R3候选19文件，其中13个生产文件与新构建、测试通过的wheel逐项一致（installed-files.json）。安装探针增加F1完整路径以及4种F2错误归属分支，已通过；生产未部署。

收尾只更新当前状态索引和本实施记录；R3受审生产、测试与双语架构字节保持不变。原R1/R2候选、审查及失败探针不覆写。最终文件检查见FINAL_VERIFICATION.json；测试进程树峰值为192.7 MiB，未跑全量或并行测试。
