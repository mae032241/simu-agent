# Fig.4 路线剪枝框架 R2：GPT-6 R1 唯一 P2 修复实施记录

- 执行者：GPT-5.6 Sol / xhigh。
- 基线：`943c4626f8490530e9318eb9fbb409d2670908b9` 加共享工作树中已存在的未提交修改。
- 状态：R1 唯一剩余 P2 的本地修复候选已完成，**待独立复审**；本文不修改 GPT-6 审查报告，不把 R2 或计划索引提前标记为通过。
- 边界：没有部署，没有启动真实科研 Run，没有运行 solver；没有改变 `layered-diagnosis.v1`，没有增加 v2、prune/continuation enum、route key/fingerprint、stop pointer、硬科学 admission、双写或第二状态机。

## R2 独立复审后的补正

2026-09-22 的 [R2 独立复审](../../reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R2_20260922.zh-CN.md) 以 `SCID_STATE_ROOT=$WORKSPACE/.codex/state` 的真实合法组合推翻了本文对 preserve-on-rollback 的无条件表述：当时的事务仍把 `${WORKSPACE}/.codex` 作为普通恢复 target，故祖先目录恢复会覆盖其中声明为 `preserved_sqlite` 的数据库，并删除快照后 Artifact CAS。本文以下通过证据只适用于普通 target 与 preserved state **不重叠**的布局，不能证明嵌套布局安全，也不能据此称 R1 P2 已关闭。

当前补救及其新证据由 [R2 overlap remediation 记录](IMPLEMENTATION_REVIEW_R2_OVERLAP_REMEDIATION_SOL_20260922.zh-CN.md) 所有；本文保留当时命令、观察与候选身份，不改写 GPT-6 历史审查。

## 选择的回滚语义

选择“**回滚程序/配置并保留安装期间的控制状态**”，不选择验证窗口停写。

真实 installer 的顺序是：离线构建 package → `begin_install_transaction` → 退役旧服务 → 激活新 site/配置 → 启动新服务 → `verify_installation` → seal。原事务在旧服务停止前快照 `artifact_agent/runs/approvals/executions/scheduler-bindings`，新服务在 seal 前可写；失败回滚会恢复旧快照。R1 的隔离反例已经证明快照后 Artifact/binding 会因此失去登记。

仓库已有 `${SCID_STATE}/maintenance.lock`，Root、Worker、UI/CLI 写入口共同取得 shared guard；但同一 guard 也用于 `open_runtime` 和当前服务探针。installer 若从快照前持有 exclusive 到 seal，新服务不能完成现有真实启动验证。只移动停服时点不能封闭新服务启动后的窗口；新增“验证期只写拒绝”模式会扩大 lifecycle。因而本轮没有发明第三套服务状态。

最小修复是：真实 installer 继续把全部控制数据库列在 transaction manifest 中，但改用 `--preserve-sqlite`。`rollback_transaction` 恢复 site、unit、配置、skill 和 launcher，对 `preserved_sqlite` 不删除、不复制旧快照，也保留事务开始时尚不存在、安装期间新建的数据库。于是验证窗口新增的 Artifact、binding、Run、approval、execution 和 TCAD submission 均保留原身份。恢复的旧 reader 是否兼容这些状态由精确 old/new release cohort 测试负责；未来存在不兼容数据库迁移的 release 必须先提供新的兼容证据，不能沿用本次候选的结论。

## 生产与文档修改

- `deploy/install_transaction.py`：`begin_transaction`/CLI 新增 `preserved_databases` 与 `--preserve-sqlite`；manifest kind 为 `preserved_sqlite`；rollback 明确跳过这些路径。原 `--sqlite` 快照恢复能力保留，没有重构其实现。
- `deploy/install.sh`：真实 `artifact_agent`、`runs`、`approvals`、`executions`、`scheduler-bindings` 以及本地 TCAD `submissions.sqlite3` 全部改为 `--preserve-sqlite`；服务停启、健康验证、seal 和其他 target 集合不变。
- `deploy/README.md`、`deploy/README.zh-CN.md`、`docs/INSTALL.md`、`docs/INSTALL.zh-CN.md`：同步当前安装语义；没有修改 R2 计划或计划 README 状态。
- 测试：`tests/artifact_agent/test_deploy_scripts.py`、`tests/operations/test_catalog_installed_entrypoint.py`。
- 历史主张补正：`IMPLEMENTATION_REVIEW_R0_REMEDIATION_SOL_20260922.zh-CN.md` 撤回用事务外数据库及 UI 固定 `not_evaluated` 证明 P2-3 的主张，并链接本文。

## 真实控制状态与资格边界

安装态测试仍从 Git `HEAD` 构建 exact old `C0/K0/T0` wheels，并使用当前 release fixture 的 exact new `C1/K1/T1` wheels；五种 distribution 组合和三个程序/配置 target 的原有检查保持不变。在同一个隔离状态根上新增以下真实控制路径：

1. 旧 site 用真实 `open_runtime`、`ArtifactService`、`SchedulerBindingService`、`ApprovalService` 和 installed catalog 登记 old v1 报告、old foundation/hypothesis；用 `science.evidence.qualify.v1` 的真实冻结 `CompiledApprovalIdentity` 建立并经 UI decision API 决定 `approve`，随后真实 `science.hypothesis.criticize.v1` preflight 可准入。
2. transaction manifest 使用与生产 installer 相同的五个控制数据库名和本地 TCAD submissions 路径，kind 全为 `preserved_sqlite`；不是事务外 reader-state 数据库。
3. 新 site 在快照后登记 new v1 报告及 `foundation.rev2`/`hypothesis.rev2`，建立 exact `qualification.rev2` 并决定 `revise`。新 revision 的真实 critic preflight 返回 `input_cohort_approval_missing`；旧 approval 没有因名称或历史状态自动覆盖新 Artifact。
4. 新 site 还通过真实 `operation_invoke` 创建一个 control Run 记录，未 attach Worker、未产生科学输出，并立即以明确工程 fixture 原因标为 failed；通过真实 `ExecutionService.create` 建立 `created` execution，并把二者绑定到同一实例。该 Run 只验证 `runs.sqlite3` 身份和状态持久性，不是科研执行。
5. 模拟 post-activation failure 后执行真实 `rollback_transaction`。site、`.codex`、`AGENTS.md` 恢复 old 摘要；五个控制数据库与 TCAD submissions 不被替换。恢复后的 old installed site 用真实服务重新打开同一状态：old/new v1 均严格解析；new Artifact/binding、Run、approval、execution ID 与状态保持；`qualification.rev2` 仍为 `decided/revise`；old foundation 仍由 exact old approval 准入，新 revision 仍被真实下游 preflight 以 `input_cohort_approval_missing` 拒绝。

测试没有使用 `SimpleNamespace`、内存 `Runs`、`approvals=None`、`executions=None` 或 UI `not_evaluated` 代替资格状态。它也没有启动 systemd、生产部署、真实 Worker/模型或 solver。

## 串行验证与资源记录

遵守 R5-N：每批前要求 `MemAvailable >= 8388608 KiB`，设置 `ulimit -v 6291456`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`、`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`，使用 `/usr/bin/time -v` 与有限 timeout；没有全量 pytest，没有并发安装矩阵，批次退出后没有 pytest/pip/compiled-worker 遗留进程。

### 最终低层事务/installer 批次

启动时 `MemAvailable=15111892 KiB`。

```text
python -m pytest -q -p no:cacheprovider \
  tests/artifact_agent/test_deploy_scripts.py::test_primary_installer_has_valid_shell_syntax \
  tests/artifact_agent/test_deploy_scripts.py::test_install_transaction_rolls_back_program_files_but_preserves_control_databases \
  tests/artifact_agent/test_deploy_scripts.py::test_complete_tcad_skill_install_integrity_removal_and_rollback \
  tests/artifact_agent/test_deploy_scripts.py::test_core_install_retires_and_rollback_restores_tcad_surfaces \
  tests/artifact_agent/test_deploy_scripts.py::test_upgrade_removes_legacy_worker_unit_and_rollback_restores_it \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface
```

**PASS：7 passed in 0.67s；exit 0；wall 0.92s；MaxRSS 85984 KiB。** 其中新测试通过真实 `install_transaction.py begin --preserve-sqlite` CLI，证明旧/新建 SQLite 在 rollback 后保留、事务目录不产生这些数据库的快照，而 site 恢复旧字节；其余测试保留原文件、skill、unit 回滚及真实 installer target/时序断言。

### 唯一 old/new installed 批次

启动时 `MemAvailable=15116448 KiB`。

```text
python -m pytest -q -p no:cacheprovider \
  tests/operations/test_catalog_installed_entrypoint.py::test_installer_rejects_incompatible_route_pruning_wheel_cohorts
```

**PASS：1 passed in 51.65s；exit 0；wall 51.90s；MaxRSS 103812 KiB。** 该 selector 同时覆盖原五种 wheel cohort、old/new profile/reader，以及本轮真实数据库、资格/approval、Run、execution 和下游 admission 故障回滚。

本轮没有过程测试失败；因此没有失败原文可记录。没有为获得 PASS 删除断言、放宽 admission 或改变已关闭的 producer/UI/scheduler 修复。

### 最终静态门禁

在仓库根串行运行 `git diff --check`、`bash -n deploy/install.sh`，以及：

```text
python -m py_compile \
  deploy/install_transaction.py \
  tests/artifact_agent/test_deploy_scripts.py \
  tests/operations/test_catalog_installed_entrypoint.py
```

三项均 **PASS（exit 0）**。另对本轮新记录和补正后的上轮记录分别运行
`git diff --no-index --check /dev/null <file>`；两者只有 no-index 表示“文件不同”的
预期 exit 1，whitespace diagnostic 为空，判定 **PASS**。没有修改任何 GPT-6 审查报告。

## 候选摘要

| 文件 | SHA-256 |
|---|---|
| `deploy/install.sh` | `562fdd79c274c2dcffbef9f3f757c2c999e1a6ec3b2a131c7c234be2a1820545` |
| `deploy/install_transaction.py` | `850a099c831016f2b92c6dc582a4487f1e0d5db9c19bcd0ed1b465ccc2cd7fd3` |
| `deploy/README.md` | `0077fc500535f2eb916ac54306b3c4ba975499586bf02946d46d186a43be6516` |
| `deploy/README.zh-CN.md` | `dce52ca70e272d61737b063ef8bcde740a2279bcceaa8cf94fbf1ffa195ef4d3` |
| `docs/INSTALL.md` | `567195ac5d30fe1a75993295b8cb7697bb652aa44e96588275ac330f285c1c37` |
| `docs/INSTALL.zh-CN.md` | `c1df7855178da3cbc022823dfab526de81617f934a66081d575d3680b2f26de6` |
| `tests/artifact_agent/test_deploy_scripts.py` | `ee9477ddc0070bc66d18109872ea6f0fbc9ee507421dead3afc3c20d32f73885` |
| `tests/operations/test_catalog_installed_entrypoint.py` | `e70535856413b593d41fcef7b2be3a23b5d79a29c63d4f1cb83c5f13b11edce1` |
| 上轮 remediation 记录（补正后） | `69feee6924327ea4c03ee30e8624b45568540dd84fd15362f71262922bd3f123` |

这些摘要只绑定本文写入时的共享工作树候选；交付前 whitespace 检查后若文件变化，以最终工作树为准。

## 未完成、部署、科研 Run 与 token

- 未完成项：独立 GPT-6 复审尚未执行；因此只登记“修复候选待复审”。生产 systemd 切换、live browser、全量 pytest 和未来不兼容数据库迁移不在本轮执行范围；本次 exact C1→C0 cohort 已通过兼容性验证，不外推到未来 release。
- 部署：**否**。仅临时目录中的 wheel/site 和 control-state fixture。
- 科研 Run：**否**。临时 runtime 中只创建一个未 attach Worker、立即工程失败的合成 control Run 记录；没有运行模型或科学任务。
- 真实 solver：**否**。
- Root token：**不可观测，未估算**。
- 修复者 token：**不可观测，未估算**；没有可唯一归属的原生 usage/trace。
- 未提交、还原、覆盖、整理或归因共享工作树中的其他改动。
