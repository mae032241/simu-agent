# Fig.4 路线剪枝框架 R2 独立实现效果复审 R2

审查日期：2026-09-22。Reviewer：GPT-6 Astra / xhigh；独立于计划作者、Sol 实施者及此前 GPT-6 Reviewers。

**Verdict：REVISE（修复效果级）。P1：0；P2：1；P3：1。**

[R1 唯一 P2](FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R1_20260922.zh-CN.md)的主要反例已在互不重叠的部署路径下修复：控制数据库不再恢复旧快照；安装态 old reader 能按真实 Artifact/binding 寻址，old foundation 仍合法，新 revision 的 `revise` 决定仍使实际下游 preflight 拒绝。但新 `preserve-sqlite` 没有排除与恢复目标的路径冲突，仍存在被 installer 接受且丢失新登记的配置，故该 P2 **尚不能完全关闭**。

唯一 installed 批次 **2 passed**；非安装态批次 **13 passed、5 failed**。五个失败是同一既有 installer 夹具的配置目录问题，下面保留失败原文和归因证据，没有把测试合计写成全绿。本轮不重审 R1 已关闭的 P2-1/P2-2/P3；只做 producer/HTTP 的最小 smoke。工程修复结论不代表 Fig.4 科学判断、live 验收或 token A/B 已验证。

## Findings

### P2-1：preserve 路径与恢复目标可重叠，manifest 的保留声明不能约束实际回滚

**精确位置：** [install_transaction.py](../../../deploy/install_transaction.py) L36–49、L66–82；[install.sh](../../../deploy/install.sh) L1197–1198、L1238–1245。输入安全检查只有名称唯一性和绝对路径等检查（前者 L254–258，后者 L242–251），没有检查相同路径或父子路径之间的处置冲突。

**可达情形：**

1. 真实 CLI 接受 `--sqlite snapshot=/tmp/.../db.sqlite3 --preserve-sqlite preserve=/tmp/.../db.sqlite3`。名称不同，但数据库相同。rollback 先跳过 `preserved_sqlite`，随后仍从 `sqlite` 快照恢复该文件。
2. 真实 CLI 接受 `--target program=/tmp/.../tree --preserve-sqlite state=/tmp/.../tree/database/db.sqlite3`。rollback 跳过数据库条目后删除并恢复整个 `tree`，快照后数据丢失。
3. installer 明确把 `${WORKSPACE}/.codex` 当作恢复目标，又允许环境变量指定 `SCID_STATE_ROOT`。`require_sources` / `validate_local_workspace_root` 没有禁止 `SCID_STATE_ROOT=${WORKSPACE}/.codex/state`；runtime 的 `_validate_state_root` 也没有这个排斥条件。该组合同时产生 `workspace-codex` target 和六个 `preserved_sqlite` 条目。

**独立执行证据：** 第一、二项均通过真实 `install_transaction.py begin/rollback` CLI 复现：`before` 后新增 `after-preserve`，begin/rollback 都 exit 0，rollback 后只剩 `before`。进一步运行原 shell 的 `install_all → verify_installation → ERR trap → rollback_install → rollback CLI`：普通独立 state 返回 `artifact_rows=["before","after"]`；嵌套 state 返回 `["before"]`。两者 manifest 都有六个 `preserved_sqlite` 条目，并将 22 个程序/配置 target 恢复；失败码均为注入的 42。后一个结果是保留属性 **FAIL**，不是测试程序 exit 0 就表示工程通过。

该 shell 探针把 systemctl/chown 和构建、配置等主机动作替换为隔离夹具；将固定 `/etc`、`/usr/local`、源码受管路径映射到临时目录，只改绝对路径，不改 target 名称、数据库集合、kind 或事务 CLI。保留实际 `install_all`、`begin_install_transaction`、`verify_installation`、trap、`rollback_install` 和 `complete_install_transaction`。在真实 verify 的 `probe_mcp` 调用处返回 42，观察启服、失败后停服、daemon-reload、旧服务重启的调用序列。它证明实际 shell 连接到本语义，不声称启动了 systemd 或生产 MCP。

**影响：** 合法接受的事务可以声明“保留数据库”，同时恢复同一数据库或其祖先目录，静默丢失快照后登记；数据库中的 ID、binding、approval 等引用可能退回旧集合。CAS 字节可能仍存在，不能据此称对象仍可寻址。旧 `--sqlite` 原本就是恢复语义；本 finding 针对新 preserve 保证缺少互斥校验，不把原快照机制重新归因为本次新增。

**最小修复：** 创建事务及拷贝快照前统一校验完整 target 集合，解析路径别名/既有父目录，拒绝 preserve 与任一恢复路径相同或存在覆盖关系的请求；同时确保 installer 的科学/控制 state 根不处于将被恢复的程序/配置目标内。诊断给出冲突的两个名称和路径。不要简单让 preserve 覆盖其他 target 的策略，否则会静默跳过本来必须恢复的程序/配置。补同路径、祖先目录、路径别名与正常独立路径的 CLI/installer 正负例即可，不需要新状态机或生产部署。

### P3-1：英文安装教程仍要求恢复数据库备份，与新语义和中文相反

**位置：** [docs/INSTALL.md](../../INSTALL.md) L487 最后一句；对照[中文](../../INSTALL.zh-CN.md) L429，以及英文同文件 L38–44。

英文末段仍写 `Roll back with matching code, roles, database and configuration transaction backups.`；本次改过的中文明确要求保留控制数据库并验证旧 reader。实际 installer 已不为这六个数据库生成备份，新低层测试也断言 `transaction/databases` 为空。

**影响与最小修复：** 运维读者会得到相互矛盾的恢复指示。同步英文这一句为代码、角色、配置回滚并保留数据库，保留精确 release cohort 的兼容性前提。其他未改段落无需重译。该项不单独构成 P2，但不满足本轮要求的双语一致性。

## R1 唯一 P2 的逐项核验

| 检查面 | 本轮结论与证据 |
|---|---|
| 机械 preserve 语义 | **正常路径通过。** manifest v1 明确记录 `name/path/kind/existed`；`preserved_sqlite` 不生成数据库或文件备份，rollback 在删除文件、WAL/SHM 前跳过；既有数据库及事务期间新建的数据库均保留。缺口是上面的路径组合冲突。 |
| 原 `--sqlite` 兼容 | **通过。** 独立 CLI 探针验证既有库恢复 `before`、快照时缺失但之后创建的库被删除；用 exact HEAD 旧模块生成 schema_version=1 manifest，再由新 CLI rollback，恢复正常。原语义没有被 preserve 全局覆盖。 |
| 参数和失败处理 | 相同名称跨两种策略明确报 `duplicate transaction target name: db`；相对路径报 `transaction target must be absolute`。不同名称的同一路径未拒绝，是 P2。begin 在验证失败时留下无 manifest 的局部 snapshot 目录，但未修改原目标；该清理行为在 HEAD 已存在，本轮未将其算成新增缺陷。 |
| seal / rollback | 真实 shell `begin_install_transaction → complete_install_transaction → CLI seal` 正常产生 `state=complete`，保留条目不产生备份；故障路径真实到达 rollback CLI，恢复程序目标及服务调用序列。没有仅靠字符串测试推定这些函数被调用。 |
| 主数据库集合 | [runtime](../../../src/scidiscovery/artifact_agent/runtime.py) L71–135 的 artifact_agent、runs、approvals、executions、scheduler-bindings 五库，及本地 [TCAD](../../../plugins/tcad_artifact/tcad_artifact/execution_control.py) L411 的 submissions，均由真实 begin 函数记录为 preserve；TCAD 条件与本地服务选择一致，外部 command transport 的状态不在本地事务管理范围。没有把 site、unit、secret 或其他非状态 target 改为 preserve。 |
| 其他 SQLite | 另外发现 [scheduler-bindings-clients.sqlite3](../../../src/scidiscovery/artifact_agent/service/scheduler_bindings.py) L95、hardened [dispatch.sqlite3](../../../src/scidiscovery/artifact_agent/service/hardened_workspace.py) L39。它们不是这六项 manifest 成员，但正常布局中也不属于任何恢复 target，故仍原地保留；不能把“六库”说成仓库全部 SQLite。UI [trajectory](../../../src/scidiscovery/artifact_agent/approval_ui/trajectory.py) 是派生缓存，archive/export 的 SQLite 是副本。未发现正常布局中另有一个被事务快照恢复却漏改 preserve 的权威数据库。上述嵌套根问题也影响这些未枚举文件，需由路径边界共同排除。 |
| Artifact / binding 寻址 | installed 测试的 before/after/verify 子进程使用 exact old/new site 和真实 `open_runtime`。恢复 old site 后通过 semantic binding 取 ID，再 `get_by_id/read` 和严格 v1 解析，old/new 报告及新 foundation 可读取。不是只检验 CAS 文件仍在。 |
| Run / execution | 新 site 通过真实 `operation_invoke` 创建 control Run，未 attach Worker 即标记为工程失败；真实 `ExecutionService.create` 创建 `created` 记录。恢复 old site 后重新打开相同数据库，经 binding 读取状态、原因及 execution payload_ref。此证据只针对合成控制记录，不代表实际科研或 executor 执行。 |
| qualification / admission | 通过 installed catalog 的 `science.evidence.qualify.v1` 冻结 `CompiledApprovalIdentity`、真实 `ApprovalService.create_request/review/record_ui_decision`，给 old foundation `approve`，给不同 Artifact 的 rev2 `revise`。old reader 回滚后仍读到 `decided/revise`；真实 `science.hypothesis.criticize.v1` preflight 对 old 输入 admissible，对 rev2 返回 `input_cohort_approval_missing`。没有 UI 固定字段、SimpleNamespace 或单纯记录数替代。该路径验证 human qualification provider，不宣称启动了独立科学 Reviewer Worker。 |
| schema 前向兼容 | exact old reader 实际打开 new 初始化过的五库。Artifact registry、Approval service、TCAD execution_control 文件与 HEAD 相同，scheduler/execution 初始化 AST 相同；Run 初始化有已有工作树中的额外表/索引，不能声称全部数据库 schema 未变，但本次 old reader 开库/读状态实际通过。结论限于本候选，不外推未来迁移。 |
| TCAD 证据边界 | installed 回滚用 `submissions.sqlite3` 中的 `rollback_probe` marker 验证整文件不恢复，未走真实 `tcad_submit`。TCAD 真实 schema/reader 文件 old/new 字节相同，可作兼容性静态支持；没有把 marker 称为已验证完整真实 submission 生命周期。本轮按授权没有提交 TCAD 作业或运行 solver。 |

对应 installed 测试的核心位置：[test_catalog_installed_entrypoint.py](../../../tests/operations/test_catalog_installed_entrypoint.py) L197–219（真实 runtime）、L257–280（冻结身份及 UI decision API）、L291–370（前后状态及 admission）、L383–436（site/配置和六库事务）。正常路径的新增工程证据可信，R1 对事务外数据库、内存 Run 和 UI 固定资格标记的质疑已经被替换；目前阻断点是新增的冲突路径反例。

## 复测命令、结果与资源

从真实仓库 `123/scidiscovery-e5.2` 执行。依照 [R5-N](../R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md) L72–82，各批串行，没有并行 pytest，没有叠加第二个安装矩阵或其他 Reviewer 进程。每批先检查 `MemAvailable >= 8388608 KiB`，设置 `ulimit -v 6291456`；这是每进程地址空间上限，不伪称进程树 cgroup 总量限制。每批使用 `/usr/bin/time -v` 和有限 timeout。

共同前缀：

```bash
test "$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)" -ge 8388608
ulimit -v 6291456
env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  MALLOC_ARENA_MAX=2 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/time -v timeout 180 python -m pytest -q -p no:cacheprovider \
  tests/artifact_agent/test_deploy_scripts.py::test_primary_installer_has_valid_shell_syntax \
  tests/artifact_agent/test_deploy_scripts.py::test_install_transaction_rolls_back_program_files_but_preserves_control_databases \
  tests/artifact_agent/test_deploy_scripts.py::test_complete_tcad_skill_install_integrity_removal_and_rollback \
  tests/artifact_agent/test_deploy_scripts.py::test_core_install_retires_and_rollback_restores_tcad_surfaces \
  tests/artifact_agent/test_deploy_scripts.py::test_upgrade_removes_legacy_worker_unit_and_rollback_restores_it \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_only_manages_local_tcad_state \
  tests/operations/test_analysis_decision_contract.py \
  tests/operations/test_instance_approval_presentation.py::test_legal_diagnosis_fields_render_escaped_without_route_badges_in_three_http_entries
```

**该批 final FAIL：5 failed, 13 passed in 8.43s，exit 1；wall 8.91s，MaxRSS 138668 KiB；MemAvailable 15003368 KiB。**

失败 selector 均为 `test_installer_only_manages_local_tcad_state` 的五种参数：`socket-`、`socket-legacy`、`command-`、`command-legacy`、`command-unused-relative`。首项精确错误为：

```text
FileNotFoundError: [Errno 2] No such file or directory:
'/tmp/pytest-of-da/pytest-73/test_installer_only_manages_lo0/config/agent-settings.json'
tests/artifact_agent/test_deploy_scripts.py:1714: AssertionError
```

原因是夹具 L1691–1700 将 `install` 替换为仅记录操作，又没有替换 `ensure_agent_settings`；后者真实打开不存在的 config 目录。停止后检查 HEAD 与候选：该测试函数 AST、`ensure_agent_settings` 和 `create_instance_archive_root` 函数体逐字/AST 相同；事务 wrapper 也只是记录 begin 参数，没有执行新 preserve 实现。故不归因于本修复，不称为环境故障，也不把这五项计为通过。没有修改夹具或重复运行这个批次。

安装态沿相同内存/环境前缀，timeout 改为 300，**只运行这一个批次**：

```bash
python -m pytest -q -p no:cacheprovider \
  --basetemp=/tmp/fig4-review-r2-installed-20260922 \
  tests/operations/test_catalog_installed_entrypoint.py::test_installer_rejects_incompatible_route_pruning_wheel_cohorts \
  tests/operations/test_catalog_installed_entrypoint.py::test_installed_route_pruning_cohort_keeps_plugin_identity_and_v1_reader
```

**PASS：2 passed in 53.52s，exit 0；wall 53.77s，MaxRSS 104060 KiB；MemAvailable 15007364 KiB。** 五种真实 wheel 组合仍为 C0/K0/T0、C1/K0/T0、C1/K1/T1 允许，C0/K1/T1、C1/K0/T1 被真实 shell distribution validator 拒绝。C0 来自 exact HEAD archive，C1 来自当前 release builder；不是生产已安装 cohort 的身份声明。随后实际运行 old/new reader、真实控制状态与资格/admission 回滚测试。

另外两个独立、无 wheel 重建的 stdin Python 工程探针均使用：

```bash
test "$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)" -ge 8388608
ulimit -v 6291456
env PYTHONDONTWRITEBYTECODE=1 MALLOC_ARENA_MAX=2 \
  /usr/bin/time -v timeout 60 python - <<'PY'
# 临时目录中的真实 CLI 与源 installer 探针；检查内容和结果逐项记于下表。
PY
```

上面是共同执行外壳，不冒充完整可重放脚本；最小故障重放源码在下一节。完整 stdin 请求保留在本轮工具执行记录，未新增仓库脚本。

| 探针 | final 观察与判定 | 资源 |
|---|---|---|
| CLI / manifest / 参数 / HEAD 夹具对照 | 旧 `--sqlite` existing/missing 回滚、旧 manifest 读取、preserve seal/无备份、重复名称拒绝、相对路径拒绝通过；同路径和父目录冲突的保留属性 **FAIL**。进程 exit 0 表示反例断言复现成功。 | MemAvailable 14996492 KiB；wall 0.50s；MaxRSS 31760 KiB。 |
| 实际 shell 失败与 seal 路径 | 普通 state：六库 preserve、22 targets 恢复、停启调用链通过；嵌套 state：快照后行丢失，保留属性 **FAIL**；真实 complete/seal 通过。两个失败注入子进程均 exit 42；探针总进程 exit 0。 | MemAvailable 14981384 KiB；wall 0.55s；MaxRSS 20112 KiB。 |

两个 pytest 批次合计 **15 passed、5 failed**；另有两类独立反例确认一个 P2。最终进程检查没有遗留 pytest/pip/Worker 测试子进程。没有重新运行已通过的 installed 批次。

## 最小可重放 P2 反例

以下是已执行探针中两项冲突检查的等价收窄版本；只操作自身临时目录，明确区分“反例被复现”和“保留保证通过”。它不要求真实数据库服务、systemd 或科研 Run。

```bash
python - <<'PY'
import sqlite3, subprocess, sys
from pathlib import Path
from tempfile import TemporaryDirectory

cli = [sys.executable, str(Path('deploy/install_transaction.py').resolve())]
with TemporaryDirectory(prefix='fig4-preserve-conflict-') as directory:
    root = Path(directory)
    for kind in ('same-path', 'ancestor'):
        tree = root / kind
        tree.mkdir()
        database = tree / 'db.sqlite3'
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE records(value TEXT)')
            db.execute("INSERT INTO records VALUES ('before')")
        transaction = root / (kind + '-transaction')
        restore = (['--sqlite', f'snapshot={database}'] if kind == 'same-path'
                   else ['--target', f'program={tree}'])
        subprocess.run([*cli, 'begin', '--root', str(transaction), *restore,
                        '--preserve-sqlite', f'preserve={database}'], check=True)
        with sqlite3.connect(database) as db:
            db.execute("INSERT INTO records VALUES ('after')")
        subprocess.run([*cli, 'rollback', '--root', str(transaction)], check=True)
        with sqlite3.connect(database) as db:
            rows = db.execute('SELECT value FROM records').fetchall()
        assert rows == [('before',)]
        print(kind, 'counterexample reproduced; preserve property FAIL', rows)
PY
```

## 范围、证据所有权与候选摘要

真实仓库为 `123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`，HEAD `943c4626f8490530e9318eb9fbb409d2670908b9`。无指定外部 base，因此审查相对 HEAD 的当前未提交候选。报告创建前 status 为 130 个 tracked 修改、273 个 untracked 条目、0 staged、0 deleted；目录条目不是文件数，没有把共享 dirty diff 归给某一作者。外层路径不是 Git 仓库，最初在那里查询得到 `fatal: not a git repository` 后即定位真实仓库，没有改动工作树。

完整阅读外层和真实仓库 AGENTS、[R2 计划](../FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md)、[R1 复审](FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R1_20260922.zh-CN.md)、[原修复记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R0_REMEDIATION_SOL_20260922.zh-CN.md)、[新修复记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R1_P2_REMEDIATION_SOL_20260922.zh-CN.md)及指定四个 SKILL.md。`scid-cross-boundary-review` 决定追踪真实 installer、状态与 admission；`scid-change-scope-checks` 决定最小串行复测；`scid-decision-corpus-maintenance` 用于双语与历史台账边界；`karpathy-guidelines` 限制为本报告和必要诊断。

文档 owner：Architecture/AGENTS/R5-N 是规范；R2 是活动方案；两份 Sol remediation 是对应候选的实施台账；R1 保留其当时 REVISE，本报告是此候选的独立审查记录。没有覆写旧审查、计划、索引或实施记录。新记录对旧“事务外数据库/UI 固定资格”主张的撤回正确，但“全部控制数据库”需按上表理解为六项显式 manifest 成员，不能外推全部状态。

| 候选文件 | SHA-256 |
|---|---|
| deploy/install_transaction.py | `850a099c831016f2b92c6dc582a4487f1e0d5db9c19bcd0ed1b465ccc2cd7fd3` |
| deploy/install.sh | `562fdd79c274c2dcffbef9f3f757c2c999e1a6ec3b2a131c7c234be2a1820545` |
| deploy/README.md | `0077fc500535f2eb916ac54306b3c4ba975499586bf02946d46d186a43be6516` |
| deploy/README.zh-CN.md | `dce52ca70e272d61737b063ef8bcde740a2279bcceaa8cf94fbf1ffa195ef4d3` |
| docs/INSTALL.md | `567195ac5d30fe1a75993295b8cb7697bb652aa44e96588275ac330f285c1c37` |
| docs/INSTALL.zh-CN.md | `c1df7855178da3cbc022823dfab526de81617f934a66081d575d3680b2f26de6` |
| tests/artifact_agent/test_deploy_scripts.py | `ee9477ddc0070bc66d18109872ea6f0fbc9ee507421dead3afc3c20d32f73885` |
| tests/operations/test_catalog_installed_entrypoint.py | `e70535856413b593d41fcef7b2be3a23b5d79a29c63d4f1cb83c5f13b11edce1` |
| 新修复记录 | `edfe9aeee08eebc4880da9973a5f885988a8d46caf95d79b182a2f816cf5fc57` |

## 未运行项与交付边界

未运行全量 pytest、全 operations、science-control bench、生产部署/systemd 切换、live browser、真实外部 execution、solver、Fig.4 exact 科学原件审计、真实 Root replay、模型剪枝行为或 token A/B。没有为了此复审创建生产实例或科研 Run。installed fixture 的合成 control Run 不 attach Worker、不产生科学输出，不能作为 Fig.4 科学证据。新 producer/HTTP 最小 smoke 通过，不重开 R1 已关闭的其他 findings。

残余风险包括本报告 P2，以及未执行的生产并发停启、hardened transport 和真实 TCAD submission 生命周期。schema/reader 结论仅限上述 exact C1→C0；不授权未来不兼容迁移沿用 preserve。R1 主要缺口在普通布局下已得到有效改善，但当前不能授予完整工程验收或部署 PASS。

部署状态：**未部署**，仅临时目录中的 wheel/site、SQLite 和外部动作被隔离的 shell 探针。Root、Sol 修复者、本 Reviewer 的 token：**不可观测、未估算**；没有取得可唯一归属的原生 usage/trace，RSS 和耗时不换算 token。

交付检查：全工作树 `git diff --check` **PASS**；本报告相对 `/dev/null` 的 whitespace 检查无诊断，exit 1 仅表示新文件有内容差异。16 个 Markdown 本地链接全部存在，未发现未填正文占位符，上述候选摘要交付前均未变化。只新增本报告；未修改实现、测试、README、Architecture、计划、实施记录或既有审查，未提交、还原、覆盖或整理他人改动。
