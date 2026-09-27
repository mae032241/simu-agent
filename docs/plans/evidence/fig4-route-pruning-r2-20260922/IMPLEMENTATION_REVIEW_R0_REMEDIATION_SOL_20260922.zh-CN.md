# Fig.4 路线剪枝框架 R2：GPT-6 R0 审查修复实施记录

- 执行者：GPT-5.6 Sol / xhigh。
- 基线：`943c4626f8490530e9318eb9fbb409d2670908b9` 加共享工作树中已存在的未提交修改。
- 状态：R0 四项 finding 的首轮本地修复候选已完成；R1 复审确认 P2-1、P2-2、P3 关闭，并指出本节 P2-3 的控制数据库/资格证据仍不充分。该剩余项已有[后续修复候选](IMPLEMENTATION_REVIEW_R1_P2_REMEDIATION_SOL_20260922.zh-CN.md)，仍待独立复审；本文不把 R2 或索引提前标记为通过。
- 边界：没有部署，没有启动科研 Run，没有运行真实 solver，没有改变 `layered-diagnosis.v1` 名称或增加 v2、prune/continuation 枚举、stop pointer、route key/fingerprint、硬 admission 或第二路线权威。
- 历史证据限制：首轮实施没有保存可重放的实施前工作树或不可变补丁序列，故四个旧失败的**历史时序不可核证**。本文只用当前完整 R2 工作树上的差分、反事实和可重放 focused tests 证明当前因果边界，不再把旧失败称为已证实的“实施前既有 dirty baseline”。

## Finding 闭环

### P2-1：真实 producer、decision read、HTTP、非权威建议与停止

1. `test_analysis_decision_contract.py` 对 generic、curve-error、TCAD 三个真实 Agent producer 各执行同一 Worker 的负例再正例：缺少 keyed `objective_assessment` 时精确拒绝；随后提交合法 `layered-diagnosis.v1`，其中 `HypothesisAssessment` 使用真实 `outcome` 且 `evidence_keys` 非空。
2. 每个正例从同一次 `run_status(response_profile="decision")` 核对 `/summary`、`/overall_verdict`、`/claim_allowed`、`/objective_assessment`、`/hypothesis_assessments`、`/limitations`、`/remaining_contradiction`、`/next_action` 八个原 pointer、原值、output metadata 与 `scheduler_signal`，并按同一 Artifact binding 回读封存字节。
3. 一个严格经 `LayeredDiagnosisReport` 解析的合法报告通过真实 Run node、Artifact node、Approval review 三个 HTTP 入口展示；八字段的独特原值均出现，`<script>` 只以转义文本出现，页面没有派生 `prune`/`剪枝` badge。
4. 两份 analysis 除 `next_action` 外字节内容相同；在其余输入相同的条件下，两个 `science.experiment.design.v1` 请求的 preflight 均 admissible、invoke 均创建真实 Run，并冻结各自的 exact analysis Artifact。首个设计先按合法合同完成，避免把同 compiled Operation 的并发 slot gate 混入反事实。
5. 显式停止用例在 decision read 前后比较 Run ID、Execution binding、Approval binding 与 Artifact ID，全部不变。

### P2-2：四项失败按实际合同修复

- A：generic preflight 负例逐项断言真实 `input_result_plan_mismatch` 或 `input_review_plan_mismatch`，没有删除 parent/label 负例，也没有放宽生产合同。
- B：`science.fixture.plan.v1` fixture 保留 producer 原有的 control-owned `recovery_manifest_output`，使工具证据与 collection output 声明一致；没有放宽 catalog compiler。
- C：绘图 prompt 断言只适用于实际具有 `worker_analysis_publish_files` 的 producer；curve-error 无该工具时同时断言不出现绘图职责文本。
- D：需要原生 stderr/stdout 的测试显式请求 `local_process_observation.py --display raw`，后半段的 Run native-error 与 diagnostic-summary 检查继续执行。

四项精确 control 当前为 `4 passed`。旧记录中 `4 failed in 4.67s` 是当时观察值，但没有足够证据证明其先于实施存在；原记录已改为“历史时序不可核证”，没有伪造实施前基线。

### P2-3：隔离 wheel cohort 与故障回滚

1. `deploy/install.sh` 新增最小 `validate_distribution_cohort`：只读取 stage 中 core 与所选 plugin distribution 的真实 metadata/requirements，确认所有分布确实解析到 stage，并在 `install_packages` 激活前拒绝不满足的同 cohort 版本。仍保持 offline `--no-deps` 构建/装载方式；`--no-deps` 的成功不再被当作兼容性证明。
2. 单一串行安装态测试从 Git `HEAD` 构建 exact old wheels，从当前 release fixture 取得 exact new wheels；真实 installer 校验入口接受 `C0/K0/T0`、`C1/K0/T0`、`C1/K1/T1`，拒绝 `C0/K1/T1` 与 `C1/K0/T1`，并核对精确 requirement 错误。
3. R1 复审确认原测试只把 active site、`.codex`、`AGENTS.md` 纳入 transaction；其 `Artifact/binding` 数据库位于事务之外。因此该测试只能证明三个程序/配置目标恢复，不能证明真实 installer 快照的 `artifact_agent/runs/approvals/executions/scheduler-bindings` 状态保留。
4. 原测试的 Run/qualification 使用 `SimpleNamespace`、内存 `Runs` 与 UI 固定 `not_evaluated`；该断言已撤回，不再用作“回滚没有恢复资格”的控制证据。后续修复把真实 installer 的全部数据库声明为 rollback-preserved transaction members，并用 old/new installed site 上的真实 Artifact、binding、Run、approval、execution 以及下游 admission 作前后核对；精确结果和命令见上述后续修复记录。

### P3：字段方向

- UI fixture 已从错误的 `HypothesisAssessment.status` 改为正确的 `HypothesisAssessment.outcome`，并给 hypothesis 与 decisive objective 补齐非空 `evidence_keys`。
- 首轮实施记录中写反的描述已改为“把正确字段 `outcome` 错写为 `status`”。GPT-6 审查报告未修改。

## 串行验证与资源记录

所有 pytest 均设置 `ulimit -v 4194304`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`、`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`，使用 `/usr/bin/time -v` 与有限 `timeout`；没有运行全量 pytest，也没有并发安装矩阵。

| 命令/批次 | final 结果 | MaxRSS |
|---|---|---:|
| 四个 P2-2 精确 control | `4 passed in 7.85s`，exit 0 | 138624 KiB |
| 三 producer keyed 负→正真实提交与 decision read | `3 passed in 7.05s`，exit 0 | 128432 KiB |
| 非权威建议改变后的 next design preflight/invoke | `1 passed in 2.52s`，exit 0 | 122972 KiB |
| 停止后的 Run/Execution/Approval/Artifact 计数 | `1 passed in 1.96s`，exit 0 | 122740 KiB |
| 三 HTTP 入口及修正后的 UI fixture | `2 passed in 1.91s`，exit 0 | 108944 KiB |
| 初版 old/new wheel cohort 矩阵 | `1 passed in 49.25s`，exit 0 | 74248 KiB |
| 最终 wheel cohort + exact site/生成配置事务回滚 + 双 reader | `1 passed in 49.15s`，exit 0 | 92228 KiB |
| 最终非安装态 focused 集合（含 decision 全文件、四 control、admission、HTTP、P3、installer shell/transaction 静态边界） | `15 passed in 13.93s`，exit 0 | 151168 KiB |

安装态矩阵命令为：

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_catalog_installed_entrypoint.py::test_installer_rejects_incompatible_route_pruning_wheel_cohorts
```

最终非安装态命令为：

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_analysis_decision_contract.py \
  tests/operations/test_result_analysis_tool.py::test_generic_compiled_preflight_accepts_no_score_and_rejects_wrong_round \
  tests/operations/test_result_analysis_tool.py::test_no_score_real_review_worker_submit_then_next_design_reads_sealed_report \
  tests/operations/test_tcad_result_analysis.py::test_no_contract_author_review_package_execute_preflight \
  'tests/operations/test_analysis_handoff_report.py::test_other_analysis_operations_finalize_compact_drafts_through_mcp[curve_error]' \
  tests/operations/test_analysis_continuation.py::test_native_read_error_survives_success_and_is_visible_in_completed_root_status \
  tests/operations/test_instance_approval_presentation.py::test_legal_diagnosis_fields_render_escaped_without_route_badges_in_three_http_entries \
  tests/operations/test_instance_presentations.py::test_general_objective_plan_review_and_analysis_preserve_original_facts \
  tests/artifact_agent/test_deploy_scripts.py::test_primary_installer_has_valid_shell_syntax \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface
```

### 保留的过程失败原文

- 第一次 next-design 反事实尝试在首个 design Run 仍 running 时调用第二个 invoke，失败为 `OperationEngineeringError: local_run_creation_failed`，直接 cause 为 `RunSlotBusy: this compiled Operation already has an unopened or running Run`；`1 failed in 2.53s`，MaxRSS 132500 KiB。修正是先合法完成首个 design，再调用第二个；没有绕过或放宽 slot gate。
- 第一次停止计数直接调用未配置 approval secret 的 fixture 上的 `runtime.executions.list_statuses`，失败为 `AttributeError: 'NoneType' object has no attribute 'list_statuses'`；`1 failed in 1.93s`，MaxRSS 123132 KiB。修正为比较该 instance 的权威 `execution`/`approval` bindings，并继续比较 Run 与 Artifact；没有伪造 Execution service。

## 改动文件

- 生产：`deploy/install.sh`。
- 测试：`tests/operations/test_analysis_claim_scope.py`、`test_analysis_decision_contract.py`、`test_analysis_continuation.py`、`test_analysis_handoff_report.py`、`test_catalog_installed_entrypoint.py`、`test_instance_approval_presentation.py`、`test_instance_presentations.py`、`test_l4_local_tcad.py`、`test_result_analysis_tool.py`。
- 记录：`IMPLEMENTATION_R2_SOL_20260922.zh-CN.md` 与本文。

共享工作树还有其他作者/任务的改动；本轮没有还原、整理、提交或归因它们。

## 未完成、部署、科研 Run 与 token

- 未完成项：独立复审尚未执行；因此状态仅为“修复候选待复审”。四项 finding 在本地 focused evidence 中没有已知未关闭测试失败。
- 部署：**否**。隔离临时目录中的 wheel 安装与 transaction 测试不是生产部署。
- 科研 Run：**否**。仅运行工程 fixture；没有启动 Fig.4 或其他科研 Run。
- 真实 solver：**否**。
- Root token：**不可观测，未估算**。
- 执行者 token：**不可观测，未估算**；当前环境没有精确归属接口。
- `git diff --check`：**PASS**，exit 0、无输出。
- 三个相关 untracked 文件（decision-contract 测试、首轮实施记录、本文）逐一执行 `git diff --no-index --check /dev/null <file>`；均只有“相对 `/dev/null` 有内容”的 exit 1，诊断输出为 0 bytes，**PASS**。
