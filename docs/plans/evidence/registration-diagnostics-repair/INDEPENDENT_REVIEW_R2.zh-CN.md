# 重复登记与失败追溯修复：独立实现复审 R2

**结论：PASS，适用于 `REVIEW_MANIFEST_R3.json` / `INCREMENT_R3.patch` 的精确候选。** R1 的两项可达缺口已修正；独立复验及相邻边界检查未发现新的阻断问题。此结论限源码和安装包工程实现，不表示部署、真实平台 Agent、daemon、VM、求解器或暂停的科学目标通过。

审查日期：2026-09-13。沿用 R1 的 `scid-cross-boundary-review`、`scid-change-scope-checks` 和最小改动原则。保留 `INDEPENDENT_REVIEW_R1.zh-CN.md`、`review_probe_r1.py/json` 及首轮失败日志，不修改历史结果；本轮独立新增 `review_probe_r2.py/json`。未修改生产代码或既有测试，未调用科学控制面、Worker工具、真实Run目录或外部执行。

## 精确范围

基线仍为 `/tmp/scid-registration-diagnostics-before-89_k59w5`，HEAD 为 `be5da77acdbf98054e0b096fc4e940de560d4ba1`。R3共19文件，其中13个生产文件、3个测试文件、3个文档文件。独立探针逐项核对当前与快照字节，**19/19匹配清单**；直接读取本轮安装探针实际构建的 wheel，**13/13生产文件字节与候选一致**。没有把原工作树的全部 HEAD diff 归为本轮。

复审已读取 R2→R3 的补充增量及其上下文，重点覆盖 intent 物化、内部异常记录、共享 Worker call 边界、Root scoped诊断，以及4项旧测试保留的恢复不变量。R1已检查而本轮未修改的登记清理、可见合同、Root错误/Run分页、来源别名定位继续适用其审查结论。

## 两项缺口的关闭证据

|问题|修订与独立验证|结论|
|---|---|---|
|F1：派生变量错误指向不存在的顶层字段|构造 ComparisonVariable 时补充 proposal/variable 上下文，保留原 ValidationError。独立负例把错误放在第二个proposal的第二个variable，实际返回并持久化 `$.payload.proposals[1].variables[1].comparison_role`，同时保留 output_payload 和 experiment.design.intent_closure。修改该实际字段的值后，同一 Run 完成提交。|已关闭|
|F2：新 assignment 打开失败写旧Run计时并返回旧completed|RunStateConflict仅新增可选内部run_id，Service在已选中任务的过期、workspace和恢复证据失败中提供该归属。共享call边界在记录前采用该Run并清空旧workspace；仅“无排队任务”沿用旧终态返回。独立跨实例复用负例确认新Run failed且有完整open计时、旧Run状态及计时完全不变、原OSError可读并脱敏，旧实例无法读取该引用；恢复backend后，同Worker可打开随后新建的Run并完成。|已关闭|

本次没有为定位错误而改变 False/0 的既有数值判定。内部Run归属未出现在Worker JSON-RPC错误或公开工程内容中；新增数据不成为Worker输入或新权限。原异常经现有EngineeringDiagnostics记录，直接异常消息复用已脱敏原因；没有另建诊断协议或生命周期。

## 独立验证

所有检查经本目录 `check.py` 串行执行，512 MiB进程树RSS及地址空间、150秒壁钟限制，无并行测试或真实求解。执行批次：

```text
python docs/plans/evidence/registration-diagnostics-repair/check.py python -m pytest -q docs/plans/evidence/registration-diagnostics-repair/review_probe_r2.py tests/operations/test_registration_diagnostics_repair.py::test_failed_reuse_open_belongs_to_selected_run tests/operations/test_l2_run_invariants.py::test_candidate_binding_crash_windows_and_response_replay tests/operations/test_l2_run_invariants.py::test_status_is_pure_and_failure_recovery_is_explicit tests/operations/test_l2_run_invariants.py::test_real_process_failure_isolation_windows_replay_after_restart tests/operations/test_l2_run_invariants.py::test_recovery_without_snapshot_keeps_original_and_reports_pending
```

结果：**11 passed，8.98秒，峰值194936832 bytes（185.9 MiB），无超时/内存终止。** 日志为 `check-1789294837272170067.log`，独立观察事实为 `review_probe_r2.json`。

其中3项为独立编写的探针：

- 当前/基线19文件摘要及wheel内13个实际生产文件字节核对。
- 非零proposal/variable索引的派生拒绝、持久化字段/规则/phase一致，以及同Run纠错完成。
- 跨实例复用后workspace打开失败：旧Run完全不变，新Run有framework_failure和tool_failed、有完整调用计时，诊断保留原因但不暴露run_id、私有路径或token；旧实例访问新引用被拒绝；随后新任务可以正常完成。

另外8项包括workspace失败、workspace_restart失败、evidence失败、expired失败4个分支，以及用户要求处理的4项旧失败。旧测试再次通过，保留候选不可变、崩溃恢复、只读查询、失败后保存、次数限制、幂等重放及脱敏的原验证意义，未发现以删除保护或放松实际断言换取通过。

已读取实施者补充记录：`check-1789294552553085430.log` 的39项定向回归通过；`check-1789294600336208261.log` 的隔离安装探针通过，新增F1完整路径及4个F2分支。安装脚本将生产模块从独立venv的site-packages加载，并调用真实MCP router；源码测试辅助文件只提供合成夹具。上述39项及wheel执行是实施者证据，本审查未把它们列为独立重跑数量。

## 目标与最小性判断

两项工程目标在本候选中得到实现：observable和baseline角色的机械重复拒绝已清理且消费者/可见合同一致；失败通过既有run_activity和scoped工程记录保留，Root可以分页追溯，错误归属和可修改字段经独立负例验证。未知引用、真实变量矛盾、实例隔离、候选不可变和四态保护继续存在；旧数据缺详情明确保留缺失，不伪造历史。

R3追加生产修改仅围绕R1的两个缺口：局部物化路径修正、异常的可选内部归属、打开失败的原因记录和共享router归属处理。没有数据库迁移、新Operation、新状态机或额外Worker能力。科学判断及暂停的Fig.4实验没有被纳入本次工程规则。

未运行全量、平台Agent/daemon/浏览器、真实VM或求解器测试，遵守本轮授权与资源约束。既有Hardened公共workspace限制仍不属于本轮资格范围。后续部署或科学继续需要各自的实际验收；本报告不要求为本次源码PASS重复已通过检查或扩大成全局审计。
