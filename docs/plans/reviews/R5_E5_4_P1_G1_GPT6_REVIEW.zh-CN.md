# R5 E5.4 P1：独立 GPT-6 G1 审查

结论：**PASS**。日期：2026-09-06。没有发现 P1 阻断缺陷。本结论仅覆盖既有 figure 实现的单一归属迁移、生产案例插件删除与关联安装／回归边界，不授予 P2–P6、自动提取、科学资格或部署通过。

## 精确审查对象

仓库为 `123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`；基线及当前 HEAD 均为 `49510146cf314a99978b783d6a130ef39a6e5c59`。审查包含全部 staged、unstaged、untracked 和删除项，共 53 个变更路径，不含本报告。完整阅读仓库 `AGENTS.md`、[E5.4 计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)、[P0 evidence](../evidence/R5_E5_4_P0_CONTRACT_FREEZE.zh-CN.md)、[G0 审查](R5_E5_4_P0_G0_GPT6_REVIEW.zh-CN.md)、[P1 evidence](../evidence/R5_E5_4_P1_PLUGIN_OWNERSHIP_AND_CASE_REMOVAL.zh-CN.md)、设计宪章及 33 项约束注册表。应用跨边界审查、变更范围检查和最小修改技能；未调用科研控制面或 Worker。

审查检查点的身份如下。变更路径清单摘要取 `git diff --name-only 4951014 -z` 与 `git ls-files --others --exclude-standard -z` 的并集，排除本报告，按路径排序；每项为 UTF-8 `路径 + NUL + 内容SHA256（删除项为DELETED） + 换行`，再计算整个清单的 SHA-256。

| 对象 | SHA-256 |
|---|---|
| 53 路径变更清单 | `18ad6af423657c5b35f249350af03f75771692cd3a01d757642b6baca5138cb7` |
| `git diff --binary 4951014` | `c89ae39d87ee3bc1da2d12511d1d29cd034bac827e1a336b320b40d96e751603` |
| E5.4 计划 | `ea8f0ea4436096a965707026f2109ff4ce8cbad496926a0987e0c1e9f37d2f1a` |
| P1 evidence | `b95c7df8aa192ce7d28b95d998e81a0de3a2e92228d8efd80b02e79074ccc2cb` |

## 九项核对

1. **实现与组件单一归属成立。** 九个 `figure_*.py` 文件全部从 curve 包移至 figure 包；逐文件与基线比较，七个字节一致，normalizer 仅将 `.schema` 改为 `curve_score.schema`，science_operations 仅改组件目标并接收迁入的 semantic resource。对旧 `curve_score.operation_transforms` 的顶层定义做 AST 对比，没有任何定义从迁移前后两包的并集中遗漏；保留的 curve 定义只有 `__all__` 改动，迁出的定义只有 `FIGURE_COMPONENT_SPECS` 的实现目标改动。`bundle_figure_evidence_outputs` 与基线适配器中的函数 AST 完全一致。旧适配器的 normalizer import、bundle export 和旧 figure 模块均不存在，没有 shim 或第二份 normalizer。

   figure PluginDefinition 的科学组件目标均在 figure 包，唯一共享目标是既有非空字节 validator `curve_score.science_operations:_NONEMPTY_COMPONENT`，其资源边已指向 figure 所有的 semantic contract。Operation 构造 helper 与 PNG 检查等既有通用 helper 保持单一实现；figure 可以单向导入它们。curve 源码没有 figure 导入，figure 源码没有 TCAD 导入。没有靠复制整个 Operation 模块制造并行权威。

2. **未安装 figure 的 curve 真实评分成立。** 本审查完整回归实际执行了 `test_curve_wheel_scores_without_installing_figure`。它从 release 副本构建并安装普通 wheel，在仓外空 cwd、清除 PYTHONPATH、禁用 user site 后执行。figure distribution 查询失败、`find_spec('curve_figure_evidence')` 和旧 normalizer 查询均为 None；安装的 curve 包没有 `figure*.py`。通用适配器实际生成 metric report、merged bundle、audit 和 PNG，预期不一致输入得到 `aggregate_status=fail`，并核对适配器位于安装前缀、进程未加载 figure 模块。不是只检查 `import curve_score`。

3. **生产案例入口与预填答案已删除。** `plugins/ingaas_fig4/` 整个目录、六个生产文件、wrapper、根 pytest pythonpath 条目、release builder 条目、默认冻结 geometry fixture 及调用它的 helper 均已实际消失。已检查删除文件和所有新增／修改生产代码，未发现 scorer、冻结 compiler、几何、材料标签或固定 source hash 换名迁入通用包。安装负测逐环境检查 distribution、import、entry point 缺席；release 测试要求生产插件目录精确为三个插件，并检查 geometry 与 wrapper 缺席；安装器残留选择负测真实经过 `deploy/install.sh --dry-run` 和既有选择逻辑，没有仅过滤目录输出。

   扫描 `plugins`、`src`、`scripts`、根 pyproject 及排除 README 的 deploy 可执行范围，`ingaas`／`fig4`／`figure_geometry`／`SCORER_CONTRACT`／已知 source hash／`ZnTotal` 的唯一命中是未改动的 `scripts/r5_baseline_metrics.py` 禁止词扫描器。合法历史 replay 的 `ZnTotal` 和实例／历史记录未被机械删除。README／INSTALL／deploy README 的案例安装叙述仍待 P4/P6 收口，P1 evidence 明确记录此限制；本次未把这些文档解释为可用安装入口或最终清理完成。

4. **r5_e2e fixture 没有接管案例 scorer。** plugin 依赖改为已有 curve 插件，source view 输入绑定现有 `CurveConsistencyReport` 和 `CurveBundle` schema。runtime 用相同 Pydantic 模型执行严格校验，再原样输出 bytes；没有材料筛选、PLX 评分、浓度常量或新的比较算法。新增测试接受合法通用合同，拒绝旧简化 JSON／CSV。历史 PLX 使用 opaque 合同但保留原有精确长度、hash 和 `ZnTotal` 验证，未放宽为任意输出。旧 manifest 明标历史状态，旧 operation/scorer/replay closure 改为 `historical_*` 字段；当前 Python 入口不加载它作为资格合同。保留的固定 replay 身份只属于测试历史字节回放，未进入生产插件或通用评分器。

5. **Operation 集精确净减二，无中央修改。** 本审查另在两个独立 Python 进程分别编译已核验基线快照与当前五插件组合，并逐项比较所有保留 Operation 的完整 `spec.model_dump(mode='json')` 和 owner。结果为 50 → 48；只删除 `ingaas.fig4-baseline-recovery.v2` 与 `ingaas.fig4.figure-request.compile.v1`，新增为零，全部保留 OperationSpec／owner 完全相同。当前所有权为 general 15、curve 8、figure 5、TCAD 20。安装回归还验证 core+general、+curve、+figure、+TCAD 和全三领域插件的精确 entry point／Operation 集，没有未知项过滤。依赖从 figure/TCAD 指向 curve，编译成功且不存在反向导入。`src/`、`plugins/tcad_artifact/`、roles、skills 无差异；没有修改中央生命周期、编译器、审批或资格机制。

6. **测试删改符合 P1 边界。** 删除的生产成功路径对应已退休 scorer、冻结 compiler 和预填 Fig.4 测量答案。通用校准、源摘要绑定、PDF 对象恢复／重放、共享支持、局部缺失、假 eligible 行拒绝、完整族及独立审查／修订覆盖仍在并实际通过。synthetic producer 原来复制案例 Operation，现改为显式测试 OperationSpec，具有确定输入、输出和 limits，并写明不证明自动检测或科学证据。

   M3 不再比较旧 M2 案例 oracle，这是计划明确退休的历史发布门；当前仍执行 18 个通用 transform 和 8 个 guard，保留 preflight、真实 invoke、幂等、冲突、revision 与 guard 负例。目录必须精确等于 corpus 加两个另有完整族测试的 figure transforms，没有丢弃未知 Operation 后再比较。未新增 skip/xfail。保留测试不证明新的 source→detector→intent→materialize 自动链；P1 evidence 同样没有作此声明。

7. **完整回归九项失败确为基线失败。** 本审查独立复跑最终工作树完整两个目录得到 451 passed、9 failed、零 skip/xfail。随后逐文件用 Git blob hash 验证 `/tmp/e54-baseline.EPOR4D` 的全部 676 个基线文件与提交 `4951014` 一致，再在该快照、相同环境中复跑相同九个 node ID，全部以同一原因失败。八项源于既有 hardened reviewer/runtime admission，表现为 `operation_runtime_unavailable` 或与旧 `runtime_backend_capability_missing` 断言不符；另一项是既有 `complete_transform_family` 导致旧 OperationSpec 字段序列断言不符。P1 直接涉及的迁移、安装、评分、删除、figure 和部署预览测试均通过。没有以改 admission、skip 或缩小当前目录范围隐藏这些失败。

8. **生产常量扫描与发布路径一致。** 除上述保留的禁止词扫描器外，没有生产 InGaAs/Fig4、geometry、旧 scorer 合同或已知冻结 hash 命中。九模块内容对比也排除了以无关键词数字复制案例算法的情况。历史 archive、不可变 Artifact 与历史 replay 数据不属于本次生产插件扫描的删除目标；本报告不宣称它们对 Worker 不可读。

9. **最小改动与 33 项约束边界保持。** 本次只迁移现有科学实现、删除两条案例能力，并调整必要调用者／安装测试。PLG-001/002 的领域所有权和独立组合获得本次源码及安装证据；DET-001 的既有重放／父链测试与 IMM/LIN/ROLE 相关完整族、修订和审查边未放宽；MIG-001 的历史结果不自动晋级边界保留。AUTH/TOP/HIL/CQRS/EFF/UI 机制无修改，未新建权威或改变状态；EVD/UNC 科学内容与 SEC/RES 的未完成验收没有被迁移成功代替。完整回归中的现有架构约束矩阵通过。本次不是对注册表全部 pending_review／known_issue 的重新资格认证，不更改 33 项状态，也不要求在 P1 修复已记录的 UI、隔离或后续检测问题。

## 独立验证与限制

所有 pytest 串行运行，未用 xdist，环境统一为 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`。外层监测器每 0.1 秒读取 `ps -e -o pid=,ppid=,rss=`，递归汇总 pytest 及其子进程 RSS，达到 8 GiB 时终止进程组。本次没有触及阈值。

| 本审查执行 | 结果 | 监测总耗时／采样峰值 |
|---|---|---|
| 当前树 `python -m pytest -q --tb=line tests/operations tests/artifact_agent` | 451 passed、9 failed；pytest 138.44s | 139.06s／237,220 KiB（约 232 MiB） |
| 已核验基线，相同命令选定下列九个 node ID | 9 failed；pytest 67.64s | 68.12s／194,484 KiB（约 190 MiB） |
| 基线／当前完整 catalog 比较 | 50→48，仅两条预定删除，保留 spec／owner 相同 | 退出码 0 |
| 九文件 diff、定义 AST 对比、生产引用扫描、`git diff --check` | 符合上述结论 | 无 whitespace 错误 |

基线复跑 node ID 为：

```text
tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_pure_mcp_plugin_completes_a_hardened_run
tests/operations/test_l4_local_tcad.py::test_hardened_v1_rejects_tcad_native_shell_before_run_creation
tests/operations/test_l5_hardened_run_backend.py::test_hardened_transport_completes_the_same_run_without_task_science
tests/operations/test_l5_hardened_run_backend.py::test_hardened_rejects_missing_server_file_creation_before_run
tests/operations/test_l5_hardened_run_backend.py::test_hardened_transport_rejects_concurrent_owner_and_recovers_after_lease
tests/operations/test_l5_hardened_run_backend.py::test_hardened_exact_text_patch_is_real_for_a_shell_free_operation
tests/operations/test_l5_hardened_run_backend.py::test_hardened_server_write_rejects_parent_symlink_escape
tests/operations/test_l5_hardened_run_backend.py::test_hardened_stdio_process_recovers_the_exact_running_run
tests/operations/test_spec.py::test_operation_spec_is_the_frozen_declarative_contract
```

监测值为进程树采样 RSS，包含本次构建／venv 子进程，不是 cgroup 强制总量，也不包含整个 live Codex／WSL 增量。安装 fixture 仍使用既有 `system_site_packages=True`；应用包路径和缺席断言成立，但不证明 checkout、技能目录或历史答案无法读取。P4 的实际文件打开负探针、P2/P3 新检测与未决合同、P5 两张真实图及真实 spawn、安装切换与 solver 均未在本次执行。当前九项历史失败仍然存在，完整目录不得称全绿。

本审查只新增本文件，未修改实现、测试、计划、evidence 或历史记录，未提交，未部署。没有要求扩大 P1 的附加修复。
