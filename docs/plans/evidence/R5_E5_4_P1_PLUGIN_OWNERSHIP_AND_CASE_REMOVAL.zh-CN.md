# R5 E5.4 P1：通用归属迁移与案例删除证据

日期：2026-09-06。基线：`49510146cf314a99978b783d6a130ef39a6e5c59`，分支 `refactor/m7-pre-e5.2`。本记录对应未提交工作树；P1 实现待独立 G1 审查，不代表 E5.4 或自动提取验收通过。依据[已审计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)、[P0](R5_E5_4_P0_CONTRACT_FREEZE.zh-CN.md)与[G0](../reviews/R5_E5_4_P0_G0_GPT6_REVIEW.zh-CN.md)。

## 精确迁移与删除

- `curve_score` 下 `figure_source.py`、`figure_worker_tool.py`、`figure_digitization_contract.py`、`figure_line_tracker.py`、`figure_digitization.py`、`figure_evidence.py`、`figure_evidence_validation.py`、`figure_evidence_normalizer.py`、`figure_science_operations.py` 九文件迁到已有 `curve_figure_evidence` 包。更新实现 imports、组件 targets；normalizer 对通用曲线 schema 的依赖仍指向 `curve_score.schema`。
- 把 figure transforms、parentage guard、figure schemas/validators、两条既有 figure support Operation 与 `bundle_figure_evidence_outputs` 切到 figure 包 `operation_transforms.py`；把 figure semantic resource 切到 `figure_science_operations.py`。curve 适配器删除 figure normalizer import 与 bundle export，没有反向 shim、normalizer 副本或 figure 依赖。共用的非空字节 validator 和通用 Operation 构造 helper 仍只有 curve 中的单一实现。
- 删除整个生产 `plugins/ingaas_fig4/`（六文件，含 scorer、geometry、compiler、entry point/metadata），删除 `deploy/apply_ingaas_fig4_profile.sh`、根 pytest pythonpath 项与 release builder 目录项。两条案例 Operation 均消失，没有别名或替代实现；完整生产目录为 general 15、curve 8、figure 5、TCAD 20，共 **48** 条，较基线净减 2。
- 删除案例插件成功测试、semantic compiler/frozen-PDF 成功路径、installed geometry 成功探针和 M3 案例 scorer 场景。删除 `test_curve_figure_digitization_tool.py` 中从固定 PDF 对象与预填 geometry 恢复答案的 helper/测试；经精确范围授权另删孤儿 `tests/fixtures/fig4_measured_continuous_lines.json`。合成图校准、追踪、完整族、修订和独立 review 回归保留；既有 synthetic producer 以显式测试合同定义，不再复制已删案例 Operation。
- M3 当前回归保留 **18** 个通用 transform 与 **8** 个 guard。目录必须精确等于该 corpus 加两条另有完整族测试的 figure transform，未过滤未知条目。历史 M2 包含已删案例 scorer，不再作为当前发布等价性门；历史归档未改。
- `r5_e2e_tcad_plugin` 删除 ingaas runtime import/dependency/专用 schema；source views 严格使用已有 `CurveConsistencyReport`、`CurveBundle` 合同，拒绝旧 JSON/CSV 冒充。历史原始 PLX 输出使用已有 `opaque` 合同；保留既有冻结字节重放与合法 `ZnTotal` 检查，没有复制 scorer。旧 manifest 明标 `historical_only_not_current_qualification`，历史 operation/scorer/runtime closure 移至 `historical_*` 字段，不再暴露可被当作当前合同的 `operation_contract`。

新增生产插件、Agent、Operation、中央字段、注册表、状态机均为 0；`src/` 与 `plugins/tcad_artifact/` 无差异。没有部署、执行 solver、修改实例 Artifact 或提交。

## 红测、安装与回归

实现前已执行计划的 `rg -n 'ingaas_fig4|ingaas\.fig4|figure_geometry|SCORER_CONTRACT|ZnTotal'` 引用扫描（范围：pyproject、plugins、deploy、scripts、tests 与现行 README/INSTALL）。新增 `test_e54_plugin_removal.py` 的所有权／案例目录缺席两项测试，在未迁移时观察到 **2 failed in 0.25s**：figure resource 仍指向 curve 实现，案例目录仍存在。之后实现转绿。

所有下列 pytest 命令均串行，环境为 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`，未使用 xdist。外层监测器每 0.1 秒汇总 pytest 及子进程 RSS，达到 8 GiB 终止进程组。

| 命令范围 | 结果与采样峰值 |
|---|---|
| `python -m pytest -q tests/operations/test_e54_plugin_removal.py tests/operations/test_m2_optional_figure_plugin.py tests/operations/test_figure_semantic_compilation.py tests/operations/test_m5_figure_review_closure.py` | 19 passed，4.71s；107,720 KiB |
| `python -m pytest -q tests/operations/test_catalog_installed_entrypoint.py::{test_curve_wheel_scores_without_installing_figure,test_clean_domain_wheel_matrix_has_exact_plugin_ownership,test_installed_case_distribution_and_import_are_absent,test_installed_detector_resource_uses_existing_compilation_edges}`（四个独立 node ID，不依赖 shell brace 语法） | 8 passed，45.39s；154,928 KiB |
| `python -m pytest -q tests/operations tests/artifact_agent`（删除最后一个旧冻结图 skip 前） | 451 passed、9 failed、1 skipped，132.86s；235,380 KiB。9 项见下节；唯一 skip 对应随后已删除的旧冻结图测试 |
| `python -m pytest -q --tb=line tests/operations tests/artifact_agent`（最终工作树） | **451 passed、9 failed，零 skip/xfail**，132.23s；232,824 KiB。与基线复现的同九项失败一致 |
| `python -m pytest -q tests/operations/test_e54_plugin_removal.py`（加强共享 validator 精确 target 断言后） | 3 passed，0.50s；76,708 KiB |

中间实施回归暴露 synthetic fixture 的显式 limits 缺失、已弃用 PLX resource 未移除和两处旧部署路径断言；修复均在允许测试/fixture 范围，并在上述完整回归通过。没有修改断言来掩盖下节的基线失败。

干净 wheel 从当前 release builder 输出构建，仓外空 cwd、清除 PYTHONPATH、禁止 user site，不使用 editable。精确验证 core+general、+curve、+figure（包含 curve 依赖）、+TCAD（包含 curve 依赖）与全三领域插件；核对完整 entry point / Operation 集、模块安装前缀。curve 环境未安装 figure distribution，`find_spec` 同时确认 figure 包与旧 curve figure normalizer 不存在；实际调用通用 score 输出 metric/bundle/audit/PNG，预期失败数值比较仍得到 `aggregate_status=fail`。各环境均验证案例 distribution/import 缺席。release 目录精确只有三个生产插件且没有旧 geometry；安装脚本 dry-run 经过现有 `plugin_selection.py`，支持三插件并拒绝残留案例选择。

这些 venv 使用既有 `system_site_packages=True`，证明应用包的 wheel 安装／导入边界，**不证明** checkout、技能、历史答案对 Worker 不可读取；后者属于 P4 的实际文件打开负探针。本阶段未实现该门。

## 完整目录的既有失败

对 `git archive 49510146cf314a99978b783d6a130ef39a6e5c59` 生成的独立临时快照，逐项复跑完整目录中的九个失败 node ID，结果 **9 failed in 41.94s**，采样峰值 **209,920 KiB**；全部在同一位置以同一原因失败：

- `test_catalog_installed_entrypoint.py::test_clean_installed_pure_mcp_plugin_completes_a_hardened_run`：独立 reviewer 在 hardened runtime 不可用，得到 `operation_runtime_unavailable`。
- `test_l4_local_tcad.py::test_hardened_v1_rejects_tcad_native_shell_before_run_creation`：同一前置拒绝使实际错误码与旧断言不同。
- `test_l5_hardened_run_backend.py` 的 `test_hardened_transport_completes_the_same_run_without_task_science`、`test_hardened_rejects_missing_server_file_creation_before_run`、`test_hardened_transport_rejects_concurrent_owner_and_recovers_after_lease`、`test_hardened_exact_text_patch_is_real_for_a_shell_free_operation`、`test_hardened_server_write_rejects_parent_symlink_escape`、`test_hardened_stdio_process_recovers_the_exact_running_run`：相同 runtime admission 原因。
- `test_spec.py::test_operation_spec_is_the_frozen_declarative_contract`：旧字段序列断言遗漏基线已有的 `complete_transform_family`。

基线复跑使用相同环境和 `python -m pytest -q --tb=line` 加以上九个精确 node ID。没有以新 skip/xfail、过滤目录、放宽中央 admission 或改 lifecycle 消除失败。完整目录不是全绿；这些旧问题仍需在 P1 之外独立处理。

## 未完成边界

P1 只迁移现有实现并删除案例，不实现 P2 detector 或 P3 intent→materialize 新合同。删除案例 compiler 后，现有 semantic intent 不能自动变成测量请求；保留的合成测量测试只验证既有领域合同和完整族，不构成自动检测验收。未进行 OCR/真实 PDF 自动提取、真实 spawn、第二图盲测、安装切换、solver、科学资格或 P4 文件不可读验收。内存是 pytest/构建子进程树采样 RSS，不是 cgroup 强制上限，不包含整个 live Codex/WSL 增量，不能授予后续真实运行内存门。

按分工，现行 README/INSTALL/deploy 双语说明留给 P4/P6，仍有待删除的案例安装建议；历史 evidence 与独立实例资料保留只读意义。生产插件、根 pythonpath、release builder 已无案例代码／geometry／固定 source hash 引用。`git diff --check` 通过；G1 尚未执行。
