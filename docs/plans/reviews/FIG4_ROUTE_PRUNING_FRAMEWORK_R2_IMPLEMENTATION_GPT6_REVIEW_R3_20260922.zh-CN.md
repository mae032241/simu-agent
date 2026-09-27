# Fig.4 路线剪枝框架 R2 独立实现效果复审 R3

审查日期：2026-09-22。Reviewer：GPT-6 Astra / xhigh；独立于计划作者、Sol 修复者及此前 Reviewers。

**Verdict：REVISE（修复效果级）。未闭合 findings：P1 0；P2 3；P3 0。**

[R2 审查](FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R2_20260922.zh-CN.md)中的实际嵌套目录反例已经修复：`SCID_STATE_ROOT=$WORKSPACE/.codex/state` 不再被整个 `.codex` 的恢复覆盖。本轮真实 shell 故障链、真实配置清理及 exact C1→C0 reader 均通过，R2 的英文回滚说明 P3 也关闭。但路径规范化仍可误认 preserved DB，恢复侧 SQLite 的 sidecar 删除范围尚未进入冲突检查，新增的 nested profile 例外也没有限制为 state-only。三个问题均有独立执行反例，不能授予完整修复 PASS。

本轮两个 pytest 批次合计 **12 passed、0 failed**，只运行一次 installed selector。补充组合探针有两次夹具失败、修正后一次通过；独立反例进程 exit 0 表示反例被成功复现，不能计作保留属性通过。全部失败、修正与资源记录如下。本结论不代表生产部署、科学合同、live 平台或 token A/B 验收。

## Findings

### P2-1：先折叠 `..` 再解析 symlink，会把 preserve 请求绑定到另一个文件

**位置：** [install_transaction.py](../../../deploy/install_transaction.py) L251–260，特别是 L257；调用方 L39–41、L71–76；后续 canonical resolution 在 L293–297。

`_safe_target` 先执行 `os.path.abspath(raw)`，这会按字符串消去 `..`。随后 `resolve(strict=False)` 已没有机会按真实 symlink 语义处理该段。两者只有在前序路径没有 symlink 时才等价。

**独立反例：** 临时目录中，`link -> state/nested`，真实 DB 是 `state/live.sqlite3`。输入 `--preserve-sqlite preserve=/tmp/.../link/../live.sqlite3`；该输入的 `Path.resolve()` 确实等于真实 DB。同时输入 `--sqlite restore=/tmp/.../state/live.sqlite3`。CLI begin **exit 0**，manifest 却把 preserved path 记成 `/tmp/.../live.sqlite3`，也就是另一个、当时不存在的文件。真实 DB 在快照后加入 `after`，rollback **exit 0**，最终只剩 `before`。这既不是随机时序，也不需要修改 manifest。

**影响：** 一个应判为同文件冲突的合法绝对路径组合被接受，快照后登记被恢复掉。现有测试分别覆盖简单 `..` 和 symlink，却没有覆盖二者组合；[测试](../../../tests/artifact_agent/test_deploy_scripts.py) L511–516 的六个负例通过不能排除此反例。

**最小修复：** 在任何词法折叠丢失 symlink/`..` 语义之前确定实际路径身份，使比较、记录和执行采用一致的身份规则；普通 target 的 symlink 自身恢复语义仍须保留。若不支持这一组合，应在 snapshot 前明确拒绝，不能静默改绑。补一个 symlink 后接 `..` 的 preserved/recovery 正反向负例，以及 missing 尾路径例；rollback 读取旧 manifest 时沿同一规则校验。

### P2-2：冲突校验只展开 preserve 的 sidecars，遗漏恢复 SQLite 自己会删除的 sidecars

**位置：** [install_transaction.py](../../../deploy/install_transaction.py) L270–284 对比 rollback L79–82。

校验把 preserved main/`-wal`/`-shm` 展开后，只与 recovery main 的 canonical path 比较。但 `kind=sqlite` 的实际破坏范围还有 recovery main 后的 `-wal`、`-shm`；这些路径也可命中另一个 preserved DB 或其祖先目录。

**独立反例：** `runtime-wal` 是一个正常 SQLite 文件，包含 `before`；`runtime` 不存在。输入 `--sqlite restore=/tmp/.../runtime --preserve-sqlite preserve=/tmp/.../runtime-wal`，begin **exit 0**。向 preserved DB 加入 `after` 后 rollback **exit 0**，`runtime-wal` 被 L82 删除，主数据库完全消失。CLI 没有文件扩展名约束，因此这是已接受的输入，不能以生产默认文件名均为 `.sqlite3` 排除公共事务入口的义务。

**影响：** missing `--sqlite` 的正常清理操作可删除已声明保留的另一库。该缺口属于 R2 原路径处置冲突未完全闭合；不声称当前默认六库命名会产生此碰撞。

**最小修复：** 对每种 recovery kind 按其真实删除/恢复范围展开，再与 protected 集合做 same/ancestor/descendant 校验；SQLite recovery 至少包含 main、`-wal`、`-shm`。begin 和 rollback 共用该检查。保留原 missing/existing SQLite 清理语义，新增这一交叉负例及 `-shm`、目录祖先变体。

### P2-3：nested `.codex` 的例外接受未知非状态内容，不能称为 state-only

**位置：** [platforms/codex.py](../../../src/scidiscovery/platforms/codex.py) L268–279；关联 [install.sh](../../../deploy/install.sh) L878–883。

新 validator 只拒绝 `config.toml`、`agents`、`scidiscovery-guides` 三个已知路径以及带 managed scheduler 标记的 `AGENTS.md`，没有枚举 `.codex` 的剩余内容，也没有把被允许的目录绑定到传入的 `state_root`。真实 configure cleanup 同样只移除三个路径，故未知非状态文件会留在 workspace 并通过最终 profile 验证。

**独立反例：** 用真实 `initialize_platform` 创建 framework profile，nested workspace 内保留 `.codex/state`。随后分别增加 `.codex/unexpected.toml` 和 `.codex/skills/custom/SKILL.md`，真实 `validate_installation_profile` 两次均接受。把整个 workspace `.codex` 改为指向外部目录的 symlink，validator 也接受。对照：三个已知 shadow 路径即使只是 dangling symlink，都被正确拒绝。

顶层 `.codex` symlink 的最后一项仅说明 validator 自身的边界缺口；完整 installer 的 `prepare_managed_platform_paths` L827–828 会拒绝一个既有的此类 symlink，本报告没有把它说成完整安装链已绕过。未知普通文件/skills 目录则不受该限制，会保留至 verifier。

**影响：** 本轮为保留控制 state 引入的豁免扩大成了任意未列名 workspace 内容的许可，无法支持“仍拒绝未知非状态文件”的要求。尤其不能把未经检查的本地指令/skill 内容自动当成 control state。未进行真实 Codex 发现实验，不据此声称已经发生工具权限或科学 approval 绕过。

**最小修复：** 按配置的 state root 明确识别允许保留的 subtree，仅检查 `.codex` 顶层/到达该 subtree 的必要路径，不遍历 state 内部；拒绝其他未知非状态项和边界 symlink。保持三个已知 profile shadow 负例，同时加入 unknown file、unknown directory、顶层 symlink、configured state 与普通 state-only 正例。

## R2 未闭合项与本轮关闭证据

| 边界 | 独立核验结论 |
|---|---|
| R2 P2 的默认 nested state 反例 | **关闭该具体反例，整体 P2 尚未关闭。** 三处 `.codex` 都拆分为 config、agents、guides；另有 AGENTS target。普通 restore targets 不再包含 `.codex/state`，真实故障链保留六库及 CAS。剩余公共 CLI 问题为 P2-1/P2-2。 |
| validation 时点 | begin L36–41 在创建 transaction root、复制任何 snapshot 前检查完整集合；rollback L71–74 在第一次删除前重复检查。简单 same/ancestor/descendant、symlink alias、missing 尾路径和 relative path 的拒绝通过。 |
| old manifest | 用 exact HEAD 的旧模块创建 schema_version=1 SQLite manifest，再由当前 CLI rollback，成功恢复 `before`。另外构造规范 JSON 的旧冲突 prepared manifest：在任何删除前拒绝，post-snapshot marker 不变。没有依赖旧 manifest 绕过新检查。 |
| alias 在 begin 后变化 | begin 后、rollback 前把 recovery 父目录 symlink 指向 preserved 祖先，当前 rollback 拒绝且 DB 不变。它证明重检覆盖阶段间变化；**不证明**最后一次 `resolve` 与实际文件操作之间的并发替换不会发生。代码仍使用 pathname，未作 fd 固定或并发竞态证明。 |
| 原 `--sqlite` 行为 | existing DB 恢复旧内容；missing DB 及后来出现的 sidecars 删除；missing 普通文件清理、普通 symlink 恢复通过。未把所有 SQLite 全局改成 preserve。 |
| config cleanup / backup / permissions | 实际 `configure_platform` 的 nested 三项清理、framework/workspace/launch profile 备份、前后权限准备都覆盖；不再递归遍历整个 `.codex`。受管目录中的 symlink 仍拒绝，state 内 symlink 的独立已有回归通过。state 字节在真实失败回滚前后不变。 |
| copy / verification / rollback | platform 初始化写入上述受管面；备份 `cp -a` 仅复制三项；site 的复制/切换不以 nested state 为 target。真实 `verify_installation` 的 `probe_mcp` 返回 42，ERR trap 调用真实 rollback CLI；三处受管 profile 和 C0 site 均恢复。没有将字符串断言视为真实执行。 |
| R2 P3 安装文案 | **关闭。** [英文教程](../../INSTALL.md) L38–44、L487 与[中文教程](../../INSTALL.zh-CN.md) L35–39、L429 均规定恢复代码/角色/配置、保留控制 DB，并要求 exact cohort reader 兼容；[英文 deploy README](../../../deploy/README.md) L13–22 与[中文](../../../deploy/README.zh-CN.md) L10–16 一致。相关段落已无要求恢复 database transaction backups 的残留。 |

## 唯一 installed 批次及真实故障链

[上轮 overlap 修复记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R2_OVERLAP_REMEDIATION_SOL_20260922.zh-CN.md)如实保留了其 **1 failed、1 passed** 的 installed 批次，失败在 old profile 缺少 guides、无条件 `rmtree` 处，早于 after 写入和 rollback。其后收窄 probe 只有叙述，没有可核对完整源码/命令，无法独立证明没有跳过 transaction/rollback assertions。因此本轮没有仅凭“fixture bug”关闭，也没有要求无关全量重建，而是按授权只执行一次当前最小 installed selector。

[当前测试](../../../tests/operations/test_catalog_installed_entrypoint.py) L396–457 全程执行：exact HEAD archive 构建 C0，当前 release fixture 构建 C1；五种 cohort minimum 正负组合；C0 before；真实 begin；C1 program/profile 激活与 after；真实 rollback；C0 program/config/agents/guide missing-or-existing 摘要恢复；C0 reader；六库 manifest、真实资格及 admission。结果 **1 passed**。修后的 missing guides 分支 L416–417 没有删掉回滚期望，L433–436 仍验证原先 missing/existing 的精确恢复。

为把同一个身份状态验证连接到真实 shell，本轮又复用**该批的同一组 exact C0/C1 sites**，没有再次构建 wheel，运行一个隔离组合探针：

- 从当前源脚本复制临时 release，仅把固定 `/usr/local/bin`、`/etc/systemd/system` 映射到临时目录；主机 systemd、属主、用户切换与安装构建动作被隔离。保留真实 `install_all`、`begin_install_transaction`、`configure_platform`、其 profile backup/permission/cleanup、`verify_installation`、ERR trap、`rollback_install` 和 transaction CLI。
- workspace 位于临时 framework 内，state 为其 `.codex/state`，另有 distinct launch root；三处均从 exact C0 profile 开始。actual configure 的 nested 清理和 framework/launch 再生成实际发生。
- before/after/verify 使用上述 installed selector 的完整 `control_source` 原文，经 AST 取出并在各 exact site 的子进程执行，清除源码 `PYTHONPATH` 影响。after 新建 Artifact/binding、`decided/revise` approval、立即工程失败的 control Run、`created` execution，以及 TCAD marker。
- Artifact/approval/execution/TCAD 四库保持 SQLite 连接打开以保留真实 WAL/SHM；runs 和 scheduler-bindings 源码明确使用 DELETE journal，不强迫其切换 journal mode。已有 shell 回归另验证六组 sidecar 字节的机械保留。
- 在真实 verify 的 MCP probe 处注入 exit 42；shell 实际 exit 42，manifest 为 `rolled_back`。在再次打开 C0 reader **之前**，全部 **30 个 state 文件**的路径及 SHA-256 与 rollback 前一致，其中六个主库、**8 个适用的真实 WAL/SHM**、**13 个 Artifact CAS 文件**。C0 site 与 framework/workspace/launch 的 config、agents、guides、AGENTS 字节恢复。
- C0 再按 semantic binding 读取并严格解析 old/new v1，核对新 Artifact ID 和三种 approval/Run/execution ID 与 after 输出完全相同；execution payload_ref 仍指向同一个新 Artifact。old foundation 的真实 critic preflight 仍 admissible；新 revision 仍返回 `input_cohort_approval_missing`，未借回滚恢复资格。

这是安装边界的隔离工程证据。TCAD 使用真实 SQLite 文件中的 marker，没有调用真实 submit/solver；control Run 没有 Worker attachment、模型执行或科学输出。没有以展示层 `not_evaluated` 代替实际 qualification/admission。

## 执行命令、全部结果与资源

遵守 [R5-N](../R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md) 的串行纪律：每批检查 `MemAvailable >= 8388608 KiB`，设置 `ulimit -v 6291456`；此为每进程地址空间上限，不声称是进程树 cgroup 总量限制。共同环境为 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`（pytest）、`PYTHONDONTWRITEBYTECODE=1`、`MALLOC_ARENA_MAX=2`、`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`，使用 `/usr/bin/time -v` 及有限 timeout。没有并行 pytest，没有第二个 installed 大批次。

小批命令（timeout 180）：

```bash
python -m pytest -q -p no:cacheprovider \
  tests/artifact_agent/test_deploy_scripts.py::test_primary_installer_has_valid_shell_syntax \
  tests/artifact_agent/test_deploy_scripts.py::test_install_transaction_rolls_back_program_files_but_preserves_control_databases \
  tests/artifact_agent/test_deploy_scripts.py::test_install_transaction_rejects_canonical_preserve_restore_overlaps \
  tests/artifact_agent/test_deploy_scripts.py::test_install_transaction_sqlite_snapshot_restore_remains_compatible \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_err_trap_preserves_nested_control_state_and_restores_managed_files \
  tests/artifact_agent/test_deploy_scripts.py::test_platform_backup_and_permission_preparation_do_not_traverse_nested_state \
  tests/artifact_agent/test_deploy_scripts.py::test_complete_tcad_skill_install_integrity_removal_and_rollback \
  tests/artifact_agent/test_deploy_scripts.py::test_core_install_retires_and_rollback_restores_tcad_surfaces \
  tests/artifact_agent/test_deploy_scripts.py::test_upgrade_removes_legacy_worker_unit_and_rollback_restores_it \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface \
  tests/artifact_agent/test_platform_configuration.py::test_codex_framework_profile_is_available_above_nested_workspace
```

唯一 installed 命令（timeout 300）：

```bash
python -m pytest -q -p no:cacheprovider \
  --basetemp=/tmp/fig4-review-r3-installed-20260922 \
  tests/operations/test_catalog_installed_entrypoint.py::test_installer_rejects_incompatible_route_pruning_wheel_cohorts
```

其余均为 `python -` stdin 隔离探针；完整请求在本轮工具执行记录，未向仓库添加测试或脚本。反例的可重放收窄源码见下一节。

| 批次 / 探针 | final 结果 | MemAvailable KiB | wall / MaxRSS KiB |
|---|---|---:|---:|
| 定向 pytest | **PASS**，11 passed in 2.02s，exit 0 | 14996596 | 2.44s / 112400 |
| 唯一 installed selector | **PASS**，1 passed in 52.41s，exit 0 | 14991200 | 52.66s / 103996 |
| 三项独立缺口及 known-shadow 对照 | 三项要求 **FAIL，反例复现成功**；脚本 exit 0 | 14971092 | 0.79s / 61600 |
| 组合探针首次夹具 | **FAIL**，exit 1；错误额外表触发严格 registry schema | 14989452 | 3.48s / 95416 |
| 组合探针第二次夹具 | **FAIL**，exit 1；强制 fixed-DELETE DB 进入 WAL 导致锁冲突 | 14986772 | 3.47s / 95636 |
| 组合探针最终 | **PASS**，外层 exit 0、真实故障 shell exit 42；字节/ID/admission 断言全部执行 | 14989104 | 5.44s / 103456 |
| exact HEAD manifest / 相对路径 / missing / alias retarget | **PASS**，exit 0；旧恢复兼容、冲突在删除前拒绝 | 14979376 | 0.29s / 21960 |

两次 Reviewer 自制夹具失败的精确原因不归于产品：第一次给每个 DB 添加 `rollback_probe`，触发 `storage/sqlite.py:493 RegistryConfigurationError: artifact registry schema differs from migration contract`；修正为只在 TCAD fixture 中建 marker 表。第二次对所有六库强制 WAL，触发 `service/scheduler_bindings.py:1080 sqlite3.OperationalError: database is locked`；源码 runs L1807、scheduler-bindings L1080 明确执行 `PRAGMA journal_mode = DELETE`。最终保留它们的原 journal 语义，只对适用四库保持真实 WAL，未修改生产代码或放宽断言。这两次都早于 after/verify 完成，不能计入成功证据。

上轮五个 `test_installer_only_manages_local_tcad_state` 失败及 Sol 的 installed 首轮失败均未被改写为通过。本轮没有运行该五项、修改其 fixture 或重新归因；本次 installed selector 的 PASS 是当前修正候选的新观察，不能抹去上轮失败。

## 两个 DB 反例的最小重放

从仓库根执行；仅操作自身临时目录，退出码 0 表示下述数据丢失反例按预期被复现。

```python
import sqlite3, subprocess, sys
from pathlib import Path
from tempfile import TemporaryDirectory

cli = [sys.executable, str(Path('deploy/install_transaction.py').resolve())]
with TemporaryDirectory(prefix='fig4-r3-counterexample-') as directory:
    root = Path(directory)
    for case in ('symlink-dotdot', 'restore-sidecar'):
        tree = root / case
        (tree / 'state/nested').mkdir(parents=True)
        database = tree / ('state/live.sqlite3' if case == 'symlink-dotdot' else 'runtime-wal')
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE records(value TEXT)')
            db.execute("INSERT INTO records VALUES ('before')")
        if case == 'symlink-dotdot':
            (tree / 'link').symlink_to(tree / 'state/nested', target_is_directory=True)
            preserve = tree / 'link/../live.sqlite3'
            assert preserve.resolve() == database
            restore = database
        else:
            preserve, restore = database, tree / 'runtime'
        transaction = root / (case + '-transaction')
        subprocess.run([*cli, 'begin', '--root', str(transaction),
            '--sqlite', f'restore={restore}', '--preserve-sqlite', f'preserve={preserve}'], check=True)
        with sqlite3.connect(database) as db:
            db.execute("INSERT INTO records VALUES ('after')")
        subprocess.run([*cli, 'rollback', '--root', str(transaction)], check=True)
        if case == 'symlink-dotdot':
            with sqlite3.connect(database) as db:
                assert db.execute('SELECT value FROM records').fetchall() == [('before',)]
        else:
            assert not database.exists()
        print(case, 'counterexample reproduced; preservation FAIL')
```

## 候选、文档所有权与交付边界

真实仓库为 `123/scidiscovery-e5.2`，HEAD **`943c4626f8490530e9318eb9fbb409d2670908b9`**，分支 `refactor/m7-pre-e5.2`。没有指定远端 base，故检查相对 HEAD 的未提交候选。开始时 130 个 tracked 修改、274 个 untracked 条目、无 staged/deleted；目录条目不是文件数。外层不是 Git 仓库，首次 status 报错后即定位该真实仓库，没有归因或整理共享 diff。

已阅读外层/仓库 AGENTS、R2 审查、overlap 修复记录、[R1 P2 修复及补正](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R1_P2_REMEDIATION_SOL_20260922.zh-CN.md)、[R1 审查](FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R1_20260922.zh-CN.md)及 [R2 计划](../FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md)相关安装/回滚/证据边界。指定四个 skill 均使用：cross-boundary-review 追踪实际配置和状态链，change-scope-checks 限定串行复测，decision-corpus-maintenance 区分规范/候选/历史台账与双语语义，karpathy-guidelines 限制为本报告及必要诊断。

所有权：当前代码与 Architecture/AGENTS/R5-N 约束行为；R2 计划是活动方案；两份 remediation 是各自候选的实施台账；R1/R2 审查是不可回写的历史独立结论；本报告只拥有当前修复候选的复审结论。原补正已明确撤回被 nested 反例推翻的无条件保证，这一点正确。本轮没有修改这些所有者、计划索引或既有报告。

| 审查候选 | SHA-256 |
|---|---|
| `deploy/install_transaction.py` | `cd768bffddf9cf2f890d95aeaf1554c8f34d0709086e5c15916a0f5d3d9c9880` |
| `deploy/install.sh` | `a5c67e9386714843688baaeba525f616f083147cee4b4155b91c91c582f3e5cd` |
| `src/scidiscovery/platforms/codex.py` | `19107703318b57ba37c628586bebbd4b03013235b40b682cc96b03b81460de3c` |
| `docs/INSTALL.md` | `44a3e08c71f875286c6b1b73fe19ea7c1b5cba8b15513044ebfbdf0976b78118` |
| `docs/INSTALL.zh-CN.md` | `c1df7855178da3cbc022823dfab526de81617f934a66081d575d3680b2f26de6` |
| `deploy/README.md` | `0077fc500535f2eb916ac54306b3c4ba975499586bf02946d46d186a43be6516` |
| `deploy/README.zh-CN.md` | `dce52ca70e272d61737b063ef8bcde740a2279bcceaa8cf94fbf1ffa195ef4d3` |
| `tests/artifact_agent/test_deploy_scripts.py` | `f9991076bdd29347334be0e6dfb3616a167474f501dec7924e513e22059fc8a6` |
| `tests/artifact_agent/test_platform_configuration.py` | `1d52ff12fdc87c676f8d039b6eca6520083b5351b5ed4cc587a7f4dd474c6f7d` |
| `tests/operations/test_catalog_installed_entrypoint.py` | `4609197eacbc54921393b245d2cb3dc9a0288aee7000c70de3bf4d371cdf44e8` |

未运行：全量 pytest、全 operations、science-control bench、部署/systemd/live browser、真实 Worker/Root replay、外部 execution/完整 TCAD submission 生命周期、solver、Fig.4 科学复审和 token A/B。此前已关闭的科学合同不重开；没有发现本次 patch 直接要求重审它们的证据。future release 数据库迁移、权限/挂载的实际生产行为和最后一次校验后的文件系统并发替换仍未验证，本次 exact C1→C0 结论不外推。

部署：**否**。科研 Run：**否**；仅隔离 control fixture。solver：**否**。Root、Sol 修复者和本 Reviewer 的 native token usage：**不可观测，未估算**；没有可唯一归属的原生 usage/trace 接口，RSS/耗时不转换成 token。

交付仅新增本报告。全工作树 `git diff --check` 与 `bash -n deploy/install.sh` **PASS**；本报告 16 个 Markdown 本地链接均存在，无未填正文占位符，10 个候选摘要均未变化，重放代码语法检查通过。新报告相对 `/dev/null` 的 whitespace 检查无诊断，no-index exit 1 仅表示文件内容不同；最终无遗留本轮 pytest/pip/组合探针进程。status 仍为 130 个 tracked 修改，untracked 条目仅增加本报告为 275。未提交、还原、覆盖、整理或归因其他人的修改。
