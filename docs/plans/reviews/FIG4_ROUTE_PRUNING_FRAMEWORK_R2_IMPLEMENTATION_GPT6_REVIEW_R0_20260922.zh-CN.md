# Fig.4 路线剪枝框架 R2 独立实现效果审查 R0

审查日期：2026-09-22。Reviewer：GPT-6 Astra / xhigh，独立于计划作者和实施者。

**结论：REVISE（实现效果级）。P1：0；P2：3；P3：1。**

新增 exact-scope 条件、三个 producer 的版本/公开语义合同、support Transform 隔离、scheduler 职责与 UI 原字段投影，未发现已证实的新增生产逻辑缺陷。本次独立复测合计 **63 passed、4 failed**；四个失败均重现。不能据此判定 WP0—WP3 的全部工程验收已闭合：真实 keyed 提交到读取/展示的验收链仍不完整，四项失败的实施前归因缺少可重放基线，发布组合与整组回滚证据也未完成。

这不是 Fig.4 科学结论，也不证明真实 Worker 或 scheduler 会作出有价值的剪枝。未部署、未访问生产实例、未启动任何科研 Run；测试只使用隔离的临时工程 runtime。

## 审查范围与依据

- 仓库：`123/scidiscovery-e5.2`；分支 `refactor/m7-pre-e5.2`；HEAD `943c4626f8490530e9318eb9fbb409d2670908b9`。审查当前未提交工作树，相对 HEAD 检查 staged/unstaged/untracked 状态，没有假定远程基线。工作树存在大量此前改动，不能把整个 diff 归给 R2。
- 完整阅读外层及本仓库 AGENTS.md，以及 `scid-cross-boundary-review`、`scid-change-scope-checks`、`scid-decision-corpus-maintenance`、`karpathy-guidelines`。按前三项技能区分生产路径、最小验证与文档主张；按后者限制变更，只新增本报告。
- 完整阅读 [R2 计划](../FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md)、[Sol 计划审查](FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_SOL_REVIEW_20260922.zh-CN.md)、[实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md)，并核对 [R5-N](../R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md)、双语 Architecture 的相关现行规则。
- 没有编辑实现、测试、计划、Architecture、README 或已有报告，没有整理、覆盖或还原共享改动。

## Findings

### P1

无。

### P2-1：新规则的端到端验收没有覆盖计划要求，当前测试通过不能支撑“三入口及八字段已验证”

**位置：** [decision-contract 测试](../../../tests/operations/test_analysis_decision_contract.py) L21–64、68–101；[UI fixture](../../../tests/operations/test_instance_presentations.py) L61–74；[HTTP 测试](../../../tests/operations/test_instance_browser_http.py) L36–143；[实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md) L68、74、107。

**证据与影响：** keyed `inconclusive + objective fail + claim_allowed=false` 只经过直接 `Components.diagnosis_context.implementation` 和直接 provider 调用，没有封存。新增 completed decision 测试使用默认 null-key TCAD 工程计划，实际只断言 overall_verdict、next_action 和空 objective_assessment，没有断言另外五项或同响应 scheduler_signal；停止测试只比较 Run ID，未比较 Execution/副作用计数。generic 和 curve-error 的新 missing/`not_evaluable` 用例也直接调用 validator；只有 TCAD 新负例经过 `worker_submit_result`。现有 curve-error compact 提交用例又在提交前因 prompt 断言失败。

UI fixture 的 hypothesis 使用 `status` 且没有 `evidence_keys`，objective fail 也没有证据；它不是可封存的合法 v1 报告。真实 [HypothesisAssessment](../../../src/scidiscovery/artifact_agent/schema/validation.py) L29–36 要求 `outcome` 和非空 evidence_keys。三个 HTTP 用例检查 instance 管理、访问授权、paused client，均未读取 diagnosis 的新增字段。通用渲染测试与直接 provider 测试可以证明局部投影/转义，不能替代三类真实入口的新字段链路。

因此尚未证明 R2 §7 要求的三 producer keyed 正负提交、完整同次 decision read、原字段经过 Run/Artifact/Approval HTTP 展示，以及改变非权威建议后同一下一 Operation 的 preflight/invoke 等价。这是工程验收缺口；不据此声称实际生产一定丢字段或越权。

**最小修复：** 复用现有 fixture，为三个真实提交路径补齐 keyed 正负例；从封存输出核对八个字段、signal、原 pointer，使用同一合法报告覆盖三入口 HTTP/转义/无派生 badge。对同一下一调用控制其他输入不变，验证建议变化不改变准入；停止用例同时检查已有 Run/Execution 与适用副作用计数。将实施记录收窄到已实际验证的范围，再按单个相关用例复测。

### P2-2：四项失败的当前原因可以确认，但“实施前共享 dirty baseline”尚无充分证据

**位置：** [实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md) L20–39、143–160；[generic 断言](../../../tests/operations/test_result_analysis_tool.py) L174；[TCAD fixture 入口](../../../tests/operations/test_tcad_result_analysis.py) L338；[compact 提交 helper](../../../tests/operations/test_analysis_handoff_report.py) L47；[continuation 断言](../../../tests/operations/test_analysis_continuation.py) L154。

**证据与影响：** 本次复测同样得到四项失败。实施证据目录仅有该 Markdown 记录；关键实施前源码摘要只有前缀，没有可重放的 dirty-tree 快照、完整补丁或实施前失败输出。事后 `git diff HEAD` 能显示当前差异，不能证明哪一行在 R2 开始前已存在；实施后再跑同一失败不是 before/after control。

当前调用路径支持较窄的结论：A 是父链错误码断言过时；B 在 fixture catalog compile 阶段失败；C 在 curve-error 提交之前失败；D 在本地观测 stdout/stderr 格式断言处失败。均未触发新增 objective 条件，故**没有证据把这些失败直接归因于该条件**。但也不能按“既有”自动降级：B/C/D 后续的 author-to-execution、compact 封存、错误经历保留等保证都因提前失败而未执行；A 后续的其他 parent/review 负例也未全部执行。

**最小修复：** 若有真实实施前快照，冻结完整摘要并在隔离副本复现；否则明确标记“历史时序不可核证”，可用完整记录的 R2 差分反事实隔离验证因果，不能追认其为真实旧基线。对当前四个测试按实际合同修复 fixture/断言或单独补足被提前阻断的后半段验证，再报告通过范围；不需给 curve-error 硬加不属于其职责的绘图指令，也不能简单删除断言来制造绿色。

### P2-3：新包 cohort 已可安装，但要求的混装拒绝和整组回滚没有得到验证

**位置：** [installed cohort 测试](../../../tests/operations/test_catalog_installed_entrypoint.py) L57–99；[installed fixture](../../../tests/operations/conftest.py) L152–245；[installer](../../../deploy/install.sh) L510–598；[部署测试](../../../tests/artifact_agent/test_deploy_scripts.py) L400–441、1409–1474；[实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md) L39、70–88。

**证据与影响：** 本次独立 installed 批次通过，证明当前 C1/K1/T1 的版本、entrypoint、PluginDefinition、producer 合同及 support digest。所用 fixture 构建的是当前源码各包；没有冻结 C0/K0/T0，也未构造 C1/K0/T0、K1/T1 配旧 C0 或 T1 配旧 K0 的组合。测试检查 `Requires-Dist` 字符串，不等于执行混装拒绝；生产 installer 还使用 `--no-deps`，其现有 catalog 探针没有检查这些 Python minimum。不能从 metadata 推断实际安装入口一定拒绝所有计划列出的不支持组合。

所跑 rollback 用例验证临时技能文件恢复，另两项主要检查脚本文本中的事务覆盖；未把确切旧 site/新 site、生成指南/配置作为一个 cohort 做安装失败后回滚，也未证明回滚后新 v1 字节仍可读且不恢复资格。计划 §8 要求的这部分发布闭合尚未完成。没有旧 wheel 时诚实保留缺口是正确的，但与“WP0—WP3 已完成”的笼统状态不一致。

**最小修复：** 收窄 WP3 完成声明；取得可归属的旧 cohort 后，在一个合并的隔离安装批次中验证计划列出的允许/拒绝组合，以及 exact site+guides+配置的事务恢复和历史读取边界。对实际支持的 installer 路径验证依赖拒绝，不能用 `--no-deps` 安装成功当作最低版本已被执行。无需生产部署或科研 Run。

### P3-1：过程失败记录把 HypothesisAssessment 字段修正方向写反

**位置：** [实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md) L136。

该行写成“把 `HypothesisAssessment.status` 写错为 `outcome`”。现行 schema 的正确字段是 `outcome`，新 [decision-contract 测试](../../../tests/operations/test_analysis_decision_contract.py) L36 也是 `outcome`；因此这句归因方向相反。本次两个测试均通过，但不能以当前文件恢复第一次失败的原始日志。最小修复是按可验证事实更正这句，并把原失败过程注明为实施者记录；不会改变运行时合同。

## 已确认的实现边界

1. **exact scope 机械条件正确。** [shared validator](../../../plugins/curve_score/curve_score/science_operations.py) L582–611 先核对唯一 experiment_key/plan_key 和 study_kind，再检查非 null key 必须有 assessment、assessment key 相同及 comparison 引用。generic L614–624、fixed-package L687–723、[TCAD context](../../../plugins/tcad_artifact/tcad_artifact/result_analysis.py) L453–496 均到达该 helper；源码调用点搜索没有发现额外生产消费者。TCAD 的 scope 来自 `_identity_context` 的原执行计划，不从 current_progress 替换身份。非空标识本身由原 Schema 约束。
2. **历史 null-key 合法。** 本次额外只读 Python 探针把 scientific portfolio 以 strict JSON model 解析为 objective_key=null，直接 context 验证没有 assessment 的报告成功。v1 reader 没有新增全局必填；pass/fail 证据规则、alias 和 comparison 规则保留。TCAD 真实提交的 missing 负例给出 `$.payload.objective_assessment` 与 `tcad.result_analysis.context_binding`，`not_evaluable` 修正后可封存。
3. **资源隔离和版本确认。** [curve declarations](../../../plugins/curve_score/curve_score/science_operations.py) L229–238、848–870、1032–1056、1088–1174 令报告输出/validator 可达新 report semantic resource，support package/plot 和各自 validator 仍可达旧 resource。TCAD 用自己的 result_analysis_semantic。`PrecomputedDiagnosisReport`/reader 的其他 HEAD 差异不能仅凭本次记录归给 R2。
4. **scheduler 具备所需说明和读路径。** [research guide](../../../roles/scheduler/research.md) 区分当前 scope、封存事实和用户允许成本；[results guide](../../../roles/scheduler/results.md) 保留一次八字段示例、completed 前提、missing/null/omitted/historical 区分与 signal。指南没有把 Worker next_action 当命令，没有第二路线权威；这证明合同可用，不能证明模型会正确使用。
5. **UI 只投影原字段。** [provider](../../../src/scidiscovery/general_science_views.py) L17、259–272 把两字段纳入原展示/指针集合；[add_fields](../../../src/scidiscovery/artifact_agent/approval_ui/presentation.py) L108–116 投影原值和 source；[renderer](../../../src/scidiscovery/artifact_agent/approval_ui/presentation_render.py) L68–120 统一转义和限界。read model 沿已授权 lineage 取值；没有看到 R2 增量推导 prune badge、修改审批对象或扩大读取权限。实际新字段 HTTP 漏泄/转义链仍受 P2-1 的验收缺口限制。
6. **prior/replay/reference 边界保留。** 实际读取 `prior_analysis_sources`、`calculation_reference_aliases`、`calculation_sources`、TCAD `source_bindings` 与 completed `_sealed_output`。旧报告通过 v1 解析，新的 output helper 不被拿去重验 prior；manifest 仍要求 direct parent/same producer/exact binding，历史 calculation 原 alias 重绑有自己的 owner。旧 compiled digest 返回 historical 正文不续资格。本次定向正负复测通过，D 的 native-observation 后半段仍未证实。
7. **范围没有扩成 R0/R1。** 所核 R2 增量没有 diagnosis v2、continuation/prune 枚举、stop pointer、route key/fingerprint、永久墓碑或硬科学 admission。没有把用户成本决定或数值失败转写成物理反证。未对整个共享 dirty tree 的作者、时序或所有其他功能作证明。

本次重新编译得到的四个 Operation version/digest，与实施记录的完整当前值完全一致：

| Operation | version | SHA-256 |
|---|---:|---|
| science.result.diagnose.v1 | 4 | `1f529599b3b486ee4774ab69d564d07f74db7f41b418e6da993b6b55e6fe0e2d` |
| science.result.diagnose.curve-error.v1 | 2 | `a95c25d38e69a00ef2f679ec1b2556a73a43ac1d26f51cc30523bed21f04d546` |
| tcad.result.analyze.v1 | 2 | `9dc27a4bd2536d523323f12540192899254cb948eba96cef7f6d93675ed714fc` |
| science.curve.error.analyze.v1 | 1 | `0630777b4a8d874bb1b842b02834df8c6994a932498422ea2c2df5a88f6176ad` |

当前资源摘要也逐项复核相符：reader `021eb3df0545b87ceaf76a24810d9f73179493089b60dc816460170d78bd1f02`；旧 semantic `62f47116bb090099715a47b2f2b8cef028d71319edc47b6773e11cd1c0ec4543`；report semantic `781905bc5807417dfd46483489d3363a1bda3b31abece8ccb6ed3aa1b9fa6ded`。这与所提供的完整历史 reader/support 摘要一致；其他 Operation 没有 exact 旧快照，不能宣称逐项无漂移。

三枚 `/tmp/fig4-route-pruning-wheels.7lnDNw` 候选 wheel 实际存在；本次 `sha256sum` 与实施记录的三个完整 wheel hash 均一致。本次 installed tests 另从当前 release builder 产物构建/安装，不把该批次误称为使用这三枚既有 wheel 完成验收。

## 11 个过程失败与最终 127/1 的独立归因

下表的“当前原因”由本次源码/复测确认；首次失败的时间和当时字节没有原始日志，保留为实施者历史陈述。

| 原编号 | 独立核查结果 |
|---|---|
| 1 / A | 当前期望 `guard_rejected`，实际是 `_diagnosis_identity` 给出的 `input_result_plan_mismatch`；父链负例仍拒绝。后续其他负例未跑到；没有证明该行在 R2 前已存在。 |
| 2 / B | 当前 fixture 的 `science.fixture.plan.v1` 在 catalog L486 因 `agent_tool_evidence_contract_invalid` 失败，尚未进入 R2 output context。生产完整 catalog 可以编译，不把 fixture 失败误称为全部生产目录失败；其纵向测试仍未完成。 |
| 3、4、5、6 | guidance 使用 `no key may be invented`。本次四个 TCAD compact verdict 参数全部 PASS；最初文本不匹配原因只可由实施者历史记录描述。 |
| 7 | generic compact MCP 用例本次 PASS。 |
| 8 | 同一 curve-error 用例已通过新增 guidance 断言，但本次仍在后续 overlay 断言失败；不能写成整个 case PASS。 |
| 9 | compact report 到下一 design preflight/原件传递用例本次 PASS。 |
| 10 / C | 与 #8 是同一个测试的后续错误点，不能当作另一个独立测试通过/失败计数。fixed-package role 没有该 overlay 指令；helper 在写 result.json/提交前已退出。 |
| 11 | scheduler guide 文件本次 `2 passed`。历史两次换行断言失败没有独立原日志。 |
| 后续两个 decision-contract case | 本次 `2 passed`，null 是 selected null，正确假设字段为 outcome；实施记录对字段方向写反，见 P3-1。 |
| 最终 127 passed / 1 failed 的 D | 本次精确失败重现：returncode=1、stderr 为空、stdout 是 structured summary。[local_process_observation](../../../src/scidiscovery/artifact_agent/service/local_process_observation.py) L238–242 明确 analysis 默认 summary，L317–318 只有 raw 才转发 stderr/stdout。旧断言与当前行为冲突；本用例的成功观测、封存、completed status 保留错误等后半段未执行。未重跑全部 128 项，也未把 127 当作本人复测数。 |

其余记录中的缺失架构脚本、首次 PYTHONPATH 缺插件及错误 ComponentRef 字段是检查命令/环境构造失败，不是科研失败。本次确认 `scripts/validate_architecture_constraints.py` 不存在；没有据此编造脚本。当前源码编译成功，不追认这些历史失败已经由本 Reviewer 独立重演。

## 本次实际运行的检查

三批 pytest 串行、独立进程；每批开始检查 `MemAvailable >= 8388608 KiB`，实际约 15,0xx,xxx KiB；使用 `ulimit -v 6291456` 和 `/usr/bin/time` 记录 RSS。安装矩阵只启动一个合并批次；等待测试结束后才继续审查。未启动并行 pytest、全量 suite 或其他 Reviewer。批次结束的当前进程视图未见遗留 Python/pytest 进程；这不是对宿主机全部进程的证明。

共同前缀：`python -m pytest -q`。以下保留 exact selectors，命令从仓库根执行。

**批次 1：19 passed、4 failed；pytest 17.17s；MaxRSS 143248 KiB。**

```text
tests/operations/test_result_analysis_tool.py::test_keyed_generic_scope_requires_objective_assessment_but_accepts_not_evaluable
tests/operations/test_m2_curve_analysis_boundary.py::test_keyed_curve_package_requires_objective_assessment_but_accepts_not_evaluable
tests/operations/test_tcad_result_analysis.py::test_keyed_tcad_scope_rejects_missing_assessment_then_accepts_not_evaluable
tests/operations/test_agent_contract_alignment.py::test_analysis_producer_versions_publish_one_keyed_scope_rule_without_changing_support_transform
tests/operations/test_analysis_decision_contract.py
tests/artifact_agent/test_scheduler_guides.py
tests/operations/test_instance_presentations.py::test_general_objective_plan_review_and_analysis_preserve_original_facts
tests/operations/test_run_status_output_selection.py
tests/operations/test_result_analysis_tool.py::test_generic_compiled_preflight_accepts_no_score_and_rejects_wrong_round
tests/operations/test_tcad_result_analysis.py::test_no_contract_author_review_package_execute_preflight
tests/operations/test_analysis_handoff_report.py::test_other_analysis_operations_finalize_compact_drafts_through_mcp[curve_error]
tests/operations/test_analysis_continuation.py::test_native_read_error_survives_success_and_is_visible_in_completed_root_status
```

先调查上述四个失败的具体调用位置与合同冲突，再运行以下不重复失败项的批次。

**installed 批次：3 passed；pytest 46.21s；MaxRSS 92164 KiB。**

```text
tests/operations/test_catalog_installed_entrypoint.py::test_installed_route_pruning_cohort_keeps_plugin_identity_and_v1_reader
tests/operations/test_catalog_installed_entrypoint.py::test_installed_gateway_returns_full_and_invoke_from_one_compiled_contract
tests/operations/test_catalog_installed_entrypoint.py::test_installed_scheduler_guides_use_context_projection_paths
```

**兼容/修正项批次：40 passed；pytest 15.32s；MaxRSS 156408 KiB。**

```text
tests/operations/test_analysis_handoff_report.py::test_tcad_compact_report_seals_and_preserves_scientific_claim
tests/operations/test_analysis_handoff_report.py::test_other_analysis_operations_finalize_compact_drafts_through_mcp[generic]
tests/operations/test_analysis_handoff_report.py::test_sealed_compact_analysis_reaches_next_design_preflight_and_original_input
tests/operations/test_prior_analysis_sources.py
tests/operations/test_analysis_artifact_references.py::test_saved_calculation_can_be_cited_next_round_with_current_alias
tests/operations/test_reference_access.py::test_report_internal_evidence_key_resolves_locator_and_sealed_record
tests/operations/test_reference_access.py::test_real_worker_reads_sealed_calculation_and_seals_without_explicit_manifest
tests/artifact_agent/test_deploy_scripts.py::test_complete_tcad_skill_install_integrity_removal_and_rollback
tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services
tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface
```

其他实际检查：`git status --short --branch`、`git rev-parse`、定向 `git diff HEAD`、生产/测试调用点搜索、四插件源码编译、资源与 wheel SHA-256、strict scientific null-key 探针、`git diff --check`。`/usr/bin/time` 的 elapsed 分别是 17.93/40.62/12.82s，与 pytest 的计时不同，按各自原输出保留，不用时间差推导性能收益。

本次审查候选关键文件摘要：

| 文件 | SHA-256 |
|---|---|
| plugins/curve_score/curve_score/science_operations.py | `e67d9eec7f27f6ad1df86aacb073f7a086dbe4f9bc43389d2bfcac71969f72d8` |
| plugins/curve_score/curve_score/analysis_workspace.py | `fe229970ab32c88152ed5a30d981e9dc9b8bc393761d3cf25a24468bd5cfc15f` |
| plugins/tcad_artifact/tcad_artifact/result_analysis.py | `8853b770682898709c861bce4ed8cd244945a919aa9b837e6c40568f76ef7df2` |
| src/scidiscovery/general_science_views.py | `59496eb1b45fa32e121d5e13488621e4b64a523309f0fbf5c4d5f32f5ee2a1c6` |
| roles/scheduler/research.md | `76e75cad37c7db5103202b083d91cfed239d7c9004c77556d9da42ebd092e239` |
| roles/scheduler/results.md | `2ebdaf90ca5fedbf2e68ce58b11ced22aa4fa6a5a4f70bd891940f0d1094dbdd` |
| tests/operations/test_analysis_decision_contract.py | `8b52c333f0b582279923eb8c763d0e690fe66506e468b5ec29e908f3d60a77a9` |
| 被审实施记录 | `2bbf28bf8f88c5ca8760bc7ac96e098b0c97d16ca7e7dcde2c083ab39a32f2a8` |

## 文档权威、未运行项与剩余风险

| 文档 | 本次认可角色与处置 |
|---|---|
| Architecture/AGENTS/scheduler guides | 当前规范；双语新增条件及职责边界相符。本报告不修改它们。 |
| R2 | 本地候选的活动计划；计划级 PASS 不等于实现级 PASS。完成状态应按 findings 收窄。 |
| Sol 计划审查与 R0/R1 历史提案 | 保留原历史角色，不能用后续代码改写其当时判断。 |
| 实施记录、计划索引、本报告 | 索引指向当前实施记录；实施记录是作者自报台账，本报告是绑定上述候选的独立审查。P2/P3 更正应追加可审计证据，不能覆盖历史失败。 |

WP0 未取得 Fig.4 exact originals 被明确披露；新 decision-contract 模块明确标为 synthetic，未冒充真实科学效果。这一点合格。仍需精确 sealed payload、任务原文、bindings、manifest、用户原文和父链，才能评价 Fig.4 历史归因；不得仅因工程 fixture 通过而宣布 Fig.4 应剪枝、模型已会剪枝或已节省 token。

未运行全量 pytest/整个 operations、science-control bench、真实模型 Root replay/production Worker、solver/TCAD、生产 browser、生产部署/服务切换、旧 cohort 混装与整组回滚。其原因分别是本次最小复测与禁止高资源/部署/科研 Run 的范围，以及确切旧 cohort/科学原件缺失。未把这些项目算作 PASS。没有重跑原 127/1 整组或所有历史兼容文件；复用现有只读审查和本次精确正负例，保留未覆盖风险。

Root、实施者及本 Reviewer token：本会话没有可唯一归属的原生 usage/trace 接口证据，均为 **不可观测、未估算**。现有 parser 支持按 response_id 解析 native token_usage_record，但硬编码 Sol/medium；这不证明当前 Astra 或 Root token 可观测，也不能用 RSS/字符数补值。条件字段完整性与真实科学选择质量仍是两种证据。

部署状态：**未部署**。本次仅在临时 fixture 内构建/安装 wheel；没有访问生产实例、改变审批或 qualification、调用外部执行或建立科研 Run。全部 findings 关闭前，本报告不授予“完整 R2 工程验收通过”或发布许可。

报告完整性检查：30 个 Markdown 相对链接全部存在；占位符扫描无命中；全工作树 `git diff --check` 退出 0；本文件相对 `/dev/null` 的 `git diff --no-index --check` 无 whitespace 诊断，退出 1 仅表示新文件有内容差异。交付前重新核对的三个关键实现/测试摘要与上表一致。
