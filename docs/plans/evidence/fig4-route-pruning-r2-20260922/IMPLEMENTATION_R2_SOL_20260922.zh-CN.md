# Fig.4 路线剪枝框架 R2：Sol 本地工程实施记录

- 实施基线：`943c4626f8490530e9318eb9fbb409d2670908b9` 加 2026-09-22 实施开始时已存在的共享未提交修改。
- 实施者：GPT-5.6 Sol / xhigh。
- 状态：**WP0—WP3 本地工程候选已完成；未部署、未启动 Fig.4 科研 Run、未获得独立实现复审。**
- 科学证据边界：没有取得计划列出的 Fig.4 exact sealed payload、任务原文、bindings、manifest、用户原文及父链；本轮新增夹具全部是明确标注的 synthetic 工程夹具，不是 Fig.4 科学证据、模型质量证明或路线失败结论。
- 权限边界：没有放宽审批、身份、qualification、预算或 side-effect gate；没有新增硬 admission、route state 或第二生命周期。

## WP0：冻结基线

实施开始前确认 core/curve/TCAD distribution 分别为 `0.1.0/0.2.1/0.1.0`，PluginDefinition 分别为 builtin/general-science `0.1.0`、curve `0.2.1`、TCAD `0.2.0`；三个 producer 的 Operation version/digest 为：

| Operation | version | digest |
|---|---:|---|
| `science.result.diagnose.v1` | 3 | `7814b43e...` |
| `science.result.diagnose.curve-error.v1` | 1 | `96e0845e...` |
| `tcad.result.analyze.v1` | 1 | `99992eab...` |
| `science.curve.error.analyze.v1` | 1 | `0630777b4a8d874bb1b842b02834df8c6994a932498422ea2c2df5a88f6176ad` |

冻结的关键字节摘要如下。带省略号的值是会话压缩后仍可归属的前缀，不被冒充完整摘要；只有写满 64 个十六进制字符的值可作 exact SHA-256。

| 文件/资源 | 实施前捕获值 |
|---|---|
| `pyproject.toml` | `d8ece9...` |
| `plugins/curve_score/pyproject.toml` | `16700e...` |
| `plugins/tcad_artifact/pyproject.toml` | `d5357d...` |
| `plugins/curve_score/curve_score/science_operations.py` | `5c6ee8...` |
| `plugins/curve_score/curve_score/analysis_workspace.py` | `8568a4...` |
| `plugins/tcad_artifact/tcad_artifact/result_analysis.py` | `d8c359...` |
| `src/scidiscovery/general_science_views.py` | `cf14f0...` |
| `roles/scheduler/research.md` | `fae9fb...` |
| `roles/scheduler/results.md` | `3cc679...` |
| `docs/ARCHITECTURE.md` | `dc8c05...` |
| `docs/ARCHITECTURE.zh-CN.md` | `03e8db...` |
| `docs/plans/README.md` | `ce95d7...` |
| v1 `diagnosis_schema` resource | `021eb3df0545b87ceaf76a24810d9f73179493089b60dc816460170d78bd1f02` |
| 原 `diagnosis_semantic_contract` resource | `62f47116bb090099715a47b2f2b8cef028d71319edc47b6773e11cd1c0ec4543` |

这些文件在实施开始时大多已经是共享 dirty 文件；本记录只归属下述 R2 增量，不把 `git diff HEAD` 中其他作者的变更据为本轮成果。仓库没有可归属的旧 wheel，因此没有伪造 C0/K0/T0 wheel hash。

## WP1：producer 条件与 Worker 合同

完成：

- `validate_analysis_report` 只在 exact scope portfolio 的 `objective_key` 非 null 时要求既有 `objective_assessment`；缺失诊断定位 `$.objective_assessment`，`not_evaluable` 合法，null key 不生成身份。
- generic/curve-error/TCAD producer 版本分别变为 `4/2/2`，继续共用一个 validator；没有修改 `scidiscovery.layered-diagnosis.v1` reader。
- 新增仅供报告 writer 可达的 `diagnosis_report_semantic_contract`；旧 `diagnosis_semantic_contract`、package/plot validator 与 support Transform 保持隔离。
- 三类 Worker prompt 和 analysis workspace guidance 说明真实 scope、合法有限答案及 `next_action` 的非权威/可选性质。

最终编译身份：

| Operation | version | digest |
|---|---:|---|
| `science.result.diagnose.v1` | 4 | `1f529599b3b486ee4774ab69d564d07f74db7f41b418e6da993b6b55e6fe0e2d` |
| `science.result.diagnose.curve-error.v1` | 2 | `a95c25d38e69a00ef2f679ec1b2556a73a43ac1d26f51cc30523bed21f04d546` |
| `tcad.result.analyze.v1` | 2 | `9dc27a4bd2536d523323f12540192899254cb948eba96cef7f6d93675ed714fc` |
| `science.curve.error.analyze.v1` | 1 | `0630777b4a8d874bb1b842b02834df8c6994a932498422ea2c2df5a88f6176ad` |

最终 v1 reader resource 仍为 `021eb3df0545b87ceaf76a24810d9f73179493089b60dc816460170d78bd1f02`；旧 semantic resource 仍为 `62f47116bb090099715a47b2f2b8cef028d71319edc47b6773e11cd1c0ec4543`；新 report semantic resource 为 `781905bc5807417dfd46483489d3363a1bda3b31abece8ccb6ed3aa1b9fa6ded`。

## WP2：scheduler 读取与最小展示

完成：

- `roles/scheduler/research.md` 与 `results.md` 区分当前 Run scope、封存科学事实、总体决定和用户投入约束；纯绘图/打包/部署不获得重新裁决物理机制的权限；`next_action`/handoff hint 不成为命令。
- `general_science_views.py` 沿原 provider 增加 `/hypothesis_assessments` 和 `/next_action` 原字段投影，后者显示为“原报告建议（非调度命令）”；没有 prune badge 或派生 route state。
- 双语 Architecture 同步新 producer 条件、历史 v1 读取不变及 scheduler/control 权限边界。
- Run/Artifact/Approval/Workbench/HTTP 沿既有 provider 链验证；没有修改 UI model/render/CSS 来建立第二种表示。

## WP3：跨边界、installed cohort 与发布候选

完成：

- 新增 synthetic decision-contract 测试：`inconclusive + objective fail + claim_allowed=false` 可共存；修改/删除普通建议不影响合法性；同一次 completed decision read 返回八个原字段；显式停止的测试 client 不创建下一 Run。
- prior/manifest/replay/reference/historical 读取使用 v1 原路径回归；没有 v2、双读、route key/fingerprint、stop pointer 或 continuation/prune enum。
- distribution cohort 变为 core/curve/TCAD `0.1.1/0.2.2/0.1.1`；curve 依赖 `scidiscovery>=0.1.1`，TCAD 依赖 `scidiscovery>=0.1.1` 与 `scidiscovery-curve-score>=0.2.2`；PluginDefinition 版本未改变。
- 隔离 installed fixture 从真实 wheel/entrypoint 验证 distribution、dependency、PluginDefinition、Operation version、v1 resource 与 support digest；真实 stdio proxy/daemon、真实 HTTP、UI provider、installer transaction/rollback 静态/临时目录检查分别通过。
- 没有执行生产安装、服务切换、真实 browser 手工验收、真实 solver、TCAD 或 Fig.4 科研 Run。

本次构建但未安装的候选 wheel：

| wheel | SHA-256 |
|---|---|
| `scidiscovery-0.1.1-py3-none-any.whl` | `f08645dd96a6e52528d2ec0c4379176a362785024eb0c623e0275bf5805eb3d5` |
| `scidiscovery_curve_score-0.2.2-py3-none-any.whl` | `b85b0926028205e40fe180bc9839e65c2963106188bffcdf7039e19b3f920433` |
| `tcad_artifact-0.1.1-py3-none-any.whl` | `3304092177fddbd2f17d7915d82a294933b8770f13a8dfdbf757220a01f9885f` |

wheel 位于临时目录 `/tmp/fig4-route-pruning-wheels.7lnDNw`，不是发布仓库或生产安装状态。

## 测试与检查

以下均串行运行。没有运行无授权的全量/高资源 suite。

| 命令（仓库根执行） | final 结果 |
|---|---|
| `python -m pytest -q tests/operations/test_result_analysis_tool.py::test_keyed_generic_scope_requires_objective_assessment_but_accepts_not_evaluable tests/operations/test_m2_curve_analysis_boundary.py::test_keyed_curve_package_requires_objective_assessment_but_accepts_not_evaluable tests/operations/test_tcad_result_analysis.py::test_keyed_tcad_scope_rejects_missing_assessment_then_accepts_not_evaluable tests/operations/test_agent_contract_alignment.py::test_analysis_producer_versions_publish_one_keyed_scope_rule_without_changing_support_transform` | `4 passed` |
| `python -m pytest -q tests/operations/test_result_analysis_tool.py` | `30 passed, 1 failed`；这是当时观察值，历史时序不可核证；当前修复见后续 remediation 记录。 |
| `python -m pytest -q tests/operations/test_m2_curve_analysis_boundary.py` | `28 passed` |
| `python -m pytest -q tests/operations/test_tcad_result_analysis.py` | `36 passed, 1 failed`；这是当时观察值，历史时序不可核证；当前修复见后续 remediation 记录。 |
| `python -m pytest -q tests/operations/test_analysis_handoff_report.py` | `12 passed, 1 failed`；这是当时观察值，历史时序不可核证；当前修复见后续 remediation 记录。 |
| `python -m pytest -q tests/artifact_agent/test_scheduler_guides.py` | `2 passed` |
| `python -m pytest -q tests/operations/test_analysis_decision_contract.py` | `2 passed` |
| `python -m pytest -q tests/operations/test_catalog_installed_entrypoint.py::test_installed_route_pruning_cohort_keeps_plugin_identity_and_v1_reader` | `1 passed in 45.23s` |
| `python -m pytest -q tests/operations/test_catalog_installed_entrypoint.py::test_installed_gateway_returns_full_and_invoke_from_one_compiled_contract` | `1 passed in 43.76s` |
| `python -m pytest -q tests/operations/test_run_status_output_selection.py` | `10 passed` |
| `python -m pytest -q tests/operations/test_instance_presentations.py tests/operations/test_instance_presentation_render.py tests/operations/test_instance_approval_presentation.py tests/operations/test_instance_workbench_render.py` | `39 passed` |
| `python -m pytest -q tests/operations/test_instance_browser_http.py` | `3 passed` |
| `python -m pytest -q tests/operations/test_prior_analysis_sources.py tests/operations/test_analysis_artifact_references.py tests/operations/test_analysis_continuation.py tests/operations/test_reference_access.py tests/operations/test_tcad_gap_continuation.py tests/operations/test_historical_compatibility_paths.py` | `127 passed, 1 failed`；这是当时观察值，历史时序不可核证；当前修复见后续 remediation 记录。 |
| `python -m pytest -q tests/operations/test_unified_mcp.py::test_real_proxy_daemon_preserves_scope_and_worker_does_not_register_client` | `1 passed in 3.69s` |
| `python -m pytest -q tests/operations/test_architecture_constraint_matrix.py` | `1 passed in 0.07s` |
| `python -m pytest -q tests/artifact_agent/test_deploy_scripts.py::test_complete_tcad_skill_install_integrity_removal_and_rollback tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface` | `3 passed in 0.58s` |
| 三次 `python -m pip wheel --no-deps --no-build-isolation --wheel-dir <temp> <core/curve/tcad>` | `3 wheels built`；摘要见上表 |

### 过程失败清单

首轮累计报告中的 11 个失败 case 逐项如下；不能用后续累计 pass 隐去它们：

| # | 失败命令/case | 原因 | 修正后结果 |
|---:|---|---|---|
| 1 | `test_result_analysis_tool.py::test_generic_compiled_preflight_accepts_no_score_and_rejects_wrong_round` | 当时观察到具体 parent mismatch 返回 `input_result_plan_mismatch`，而断言只接受 `guard_rejected`；没有不可变的实施前快照可证明其历史时序。 | 当时仍失败；当前 fixture/断言按实际合同修复并通过，见后续 remediation 记录。 |
| 2 | `test_tcad_result_analysis.py::test_no_contract_author_review_package_execute_preflight` | 当时 catalog 对 `science.fixture.plan.v1` 报 `agent_tool_evidence_contract_invalid`；没有不可变的实施前快照可证明其历史时序。 | 当时仍失败；当前 fixture 保留 control-owned collection output 后通过，见后续 remediation 记录。 |
| 3 | `test_tcad_compact_report_seals_and_preserves_scientific_claim[pass]` | 新 guidance 断言最初用了与实际文本不一致的 “must not be invented”。 | 改为实际合同短语 `no key may be invented`；该 case final PASS。 |
| 4 | 同测试 `[fail]` | 同 #3。 | final PASS。 |
| 5 | 同测试 `[inconclusive]` | 同 #3。 | final PASS。 |
| 6 | 同测试 `[invalid_study]` | 同 #3。 | final PASS。 |
| 7 | `test_other_analysis_operations_finalize_compact_drafts_through_mcp[generic]` | 同 #3。 | final PASS。 |
| 8 | 同测试 `[curve_error]` | 同 #3。 | 此错误点修正；随后触及既有 overlay 断言，见 #10。 |
| 9 | `test_sealed_compact_analysis_reaches_next_design_preflight_and_original_input` | 同 #3。 | final PASS。 |
| 10 | `test_other_analysis_operations_finalize_compact_drafts_through_mcp[curve_error]` | 当时测试要求 curve-error role 含 `reference/candidate\noverlay PNG by default`，但该 Operation 没有文件发布工具；没有不可变的实施前快照可证明其历史时序。 | 当前按实际工具合同限定断言后通过，见后续 remediation 记录。 |
| 11 | `test_scheduler_guides.py::test_guide_installation_is_dry_run_safe_and_idempotent` | 新断言跨 guide 的实际换行匹配不稳。 | 改为稳定原句片段；文件 final `2 passed`。 |

之后发现/修正或保留的失败也完整列出：

| 失败命令/case | 原因 | 修正后结果 |
|---|---|---|
| `test_analysis_decision_contract.py` 两个新增 case | fixture 首稿把 `HypothesisAssessment` 的正确字段 `outcome` 错写为 `status`，并把显式 null 与 selected missing 混同。 | 修正为 `outcome` 并补齐非空 `evidence_keys`，同时修正断言；final `2 passed`。 |
| scheduler guide 同一 case 的第二次运行 | 第一次修正仍命中换行边界。 | 使用稳定子句；final `1 passed`，随后全文件 `2 passed`。 |
| prior/replay/reference/historical 组合中的 `test_native_read_error_survives_success_and_is_visible_in_completed_root_status` | 当时 `local_process_observation` 默认输出 stdout summary，而测试要求原始 `FileNotFoundError` 出现在 stderr；没有不可变的实施前快照可证明其历史时序。 | 当前测试显式请求 `--display raw` 后通过，见后续 remediation 记录。 |
| `python scripts/validate_architecture_constraints.py --help` | 当前仓库没有 skill 所列脚本。 | 记录缺失，不伪造脚本；改跑仓库实际约束矩阵，`1 passed`。 |
| 首次 standalone catalog 摘要探针 | 未设置插件源码 `PYTHONPATH`，`ModuleNotFoundError: curve_score`。 | 设定 `PYTHONPATH=src:plugins/curve_score:plugins/tcad_artifact` 后导入成功。 |
| 第二次 catalog 摘要探针 | 把 `ComponentRef.component_id` 误写成 `.name`。 | 改用公开模型字段 `component_id`；最终编译摘要成功，结果见 WP1。 |

### 历史时序不可核证与当前差分边界

四类保留失败均用一个精确 control 命令重现：

```text
python -m pytest -q \
  tests/operations/test_result_analysis_tool.py::test_generic_compiled_preflight_accepts_no_score_and_rejects_wrong_round \
  tests/operations/test_tcad_result_analysis.py::test_no_contract_author_review_package_execute_preflight \
  'tests/operations/test_analysis_handoff_report.py::test_other_analysis_operations_finalize_compact_drafts_through_mcp[curve_error]' \
  tests/operations/test_analysis_continuation.py::test_native_read_error_survives_success_and_is_visible_in_completed_root_status
```

结果为 `4 failed in 4.67s`，精确错误分别是 `input_result_plan_mismatch`、`agent_tool_evidence_contract_invalid: general_science/science.fixture.plan.v1`、缺 overlay prompt、stderr 为空而 stdout 有 structured summary。该命令能证明当时工作树的观察值，但会话没有保存可重放的实施前工作树或不可变补丁序列，故**历史时序不可核证**，不能再把它们称为已证实的“实施前既有 dirty baseline”。后续 remediation 只以完整可重放的当前 R2 差分、精确反事实和 final focused tests 证明当前因果边界；没有伪造实施前基线。

## 改动文件归属

R2 实施增量涉及：

- producer/guide：`plugins/curve_score/curve_score/science_operations.py`、`analysis_workspace.py`、`plugins/tcad_artifact/tcad_artifact/result_analysis.py`、`roles/scheduler/research.md`、`roles/scheduler/results.md`；
- view/规范：`src/scidiscovery/general_science_views.py`、`docs/ARCHITECTURE.md`、`docs/ARCHITECTURE.zh-CN.md`；
- release metadata：根、curve、TCAD 三个 `pyproject.toml`；
- tests：`test_result_analysis_tool.py`、`test_m2_curve_analysis_boundary.py`、`test_tcad_result_analysis.py`、`test_agent_contract_alignment.py`、`test_analysis_handoff_report.py`、`test_instance_presentations.py`、`test_scheduler_guides.py`、`test_catalog_installed_entrypoint.py`，以及新建 `test_analysis_decision_contract.py`；
- status/evidence：R2 计划状态、`docs/plans/README.md` 本条索引和本记录。

没有修改 R0、R1 或任何既有审查报告。共享工作树中上述已跟踪文件可能同时含其他作者先前变更；本轮没有还原或覆盖它们。

## 未完成项、部署与 token

- 未取得 Fig.4 exact 原件，未完成 Fig.4 历史科学审计或 Fig.4-specific fixture。
- 未运行真实 Worker/scheduler 非迎合行为复审、Root/production compiled Worker token A/B、生产浏览器手工验收、真实 solver 或科研闭环。
- 尚无独立实现审查；本记录只声明本地工程候选。
- 未运行全量 pytest；按 R5-N 内存纪律使用最小可信串行集合。上述四项历史失败的当前修复与最终结果记录在后续 remediation 证据中。
- 部署：**否**。没有安装 wheel、重启服务、切换 site、改变实例或创建科研 Run。
- Root token：**不可观测，未估算**；没有合法可唯一归属的原生接口证据。
- 实施者 token：**不可观测，未估算**；collaboration/本执行会话无合法精确 token 接口。
- `git diff --check`：**PASS**（exit 0、无输出）。另对本轮 6 个 untracked 文件逐一运行 `git diff --no-index --check /dev/null <path>`：均无 whitespace 诊断；exit 1 仅表示文件相对 `/dev/null` 有内容差异。
