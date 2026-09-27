# Fig.4 路线剪枝框架 R2：preserved DB 路径重叠修复实施记录

- 执行者：GPT-5.6 Sol / xhigh。
- 基线：`943c4626f8490530e9318eb9fbb409d2670908b9` 加共享工作树中已存在的未提交修改。
- 输入：[GPT-6 R2 独立复审 R2](../../reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R2_20260922.zh-CN.md) 的唯一 P2 与唯一 P3。
- 状态：本地修复候选完成，**待独立复审**；本文不修改任何 GPT-6 审查报告、R0/R1 历史计划或计划 README 状态。
- 边界：没有部署，没有启动科研 Run，没有运行 solver；没有触碰 layered-diagnosis、producer、UI 或 scheduler 科学合同，没有双写、数据迁移或第二事务系统。

## 修复语义

生产 installer 不再把 framework、workspace 或 distinct launch root 的整个 `.codex` 目录作为普通恢复 target。三个位置都拆成 installer 实际管理的 `config.toml`、`agents/`、`scidiscovery-guides/`，`AGENTS.md` 仍为独立 target。因而合法的 `SCID_STATE_ROOT=$WORKSPACE/.codex/state` 不在任何普通恢复 target 内；rollback 恢复程序、配置、角色和指南，但不删除或覆盖 state subtree。此边界同时保留显式六库之外的 Artifact CAS、其他 SQLite、execution exchange 和其余状态文件，不能只靠六个主数据库文件推断 Artifact 可寻址性。

当 workspace 位于 framework 内时，`configure_platform` 原先删除整个 `$WORKSPACE/.codex`；现只删除上述三个会 shadow framework profile 的受管面。platform 历史备份和配置前后权限准备也只复制、校验、chown/chmod 这三个受管面，不再遍历 state subtree；state 内 symlink 不会被误当成 platform profile symlink。installed profile validation 相应允许 state-only `.codex`，仍拒绝嵌套 workspace 自带 config、agents、guides 或 scheduler prompt。这里没有用“禁止合法 state root”规避问题。

低层 transaction CLI 对所有输入先验证名称、绝对路径和处置关系，再创建 transaction root 或复制任何 snapshot。比较身份用 `resolve(strict=False)`，所以 `..`、不存在尾路径及既有父目录 symlink alias 不能绕过。每个 `preserved_sqlite` 的主文件、`-wal`、`-shm` 与任一 `--sqlite` 或普通 `--target` 只要 canonical same/祖先/子孙重叠，就报告两个名称和路径并 fail closed。rollback 读取 prepared manifest 后、进行任何删除前重复相同校验，旧的冲突 manifest 也不会执行破坏性恢复。非生产重叠组合没有隐式“preserve 胜出”策略；生产合法组合由上述 target 粒度拆分消除重叠。

原 `--sqlite` 语义不变：快照时存在的数据库恢复旧内容并清除当前 `-wal/-shm`，快照时缺失而后来创建的数据库及 sidecars 被删除。`preserved_sqlite` 主文件和 sidecars 不产生 snapshot、不删除、不复制；生产也不再有祖先 target 能间接覆盖它们。

## 精确修改面

- `deploy/install_transaction.py`：begin 和 rollback 的 canonical disposition 校验；验证先于 snapshot；原 sqlite/preserve 执行语义保留。
- `deploy/install.sh`：三组 `.codex` target 拆成 config/agents/guides；nested workspace 清理、platform 历史备份与权限准备只作用于同三项。
- `src/scidiscovery/platforms/codex.py`：nested workspace 允许 state-only `.codex`，继续拒绝 profile shadow。
- `tests/artifact_agent/test_deploy_scripts.py`：CLI overlap 负例、preserve sidecars、旧 sqlite existing/missing、文件/目录/symlink、真实 ERR-trap installer 回归及 target 清单。
- `tests/artifact_agent/test_platform_configuration.py`：state-only nested workspace 正例与 config shadow 负例。
- `tests/operations/test_catalog_installed_entrypoint.py`：真实 old/new installed reader 状态改放在 active `.codex/state`；配置 target 粒度与 missing/existed guides 回滚。
- `docs/INSTALL.md`：把末段错误的 database backup 指示改为保留控制数据库，并保留 exact release cohort reader 兼容前提。`docs/INSTALL.zh-CN.md` 已是该语义；`deploy/README.md` 与 `deploy/README.zh-CN.md` 也一致，未作无关重写。
- 上轮 `IMPLEMENTATION_REVIEW_R1_P2_REMEDIATION_SOL_20260922.zh-CN.md`：新增显式补正，撤回被重叠反例推翻的无条件主张，并把当前证据所有权链接到本文。

## 真实失败路径与状态证据

新增隔离回归保留源 installer 的 `install_all`、`begin_install_transaction`、`verify_installation`、ERR trap、`rollback_install` 和真实 transaction CLI。它复制 exact 源脚本到临时 release，只把固定 `/usr/local/bin`、`/etc/systemd/system` 映射到临时目录，并替换主机权限/systemd side effect；在真实 `verify_installation` 的 `probe_mcp` 处返回 42。子进程精确 exit 42，证明失败实际经过 trap 与 rollback CLI，不以字符串或 AST 断言替代。

该回归使用 `SCID_STATE_ROOT=$WORKSPACE/.codex/state`。begin 后写入五个 control SQLite 与本地 TCAD `submissions.sqlite3` 的真实 SQLite 行，创建六组 `-wal/-shm` 和 post-snapshot Artifact CAS marker，并修改 site、framework/workspace config、agent 与 guide。rollback 后六库均同时含 `before/after`，sidecars 字节与 CAS marker 均保留；site/config/agents/guides 恢复 old，新增 agent 被删除；manifest 为 `rolled_back`，含六个 `preserved_sqlite`，且普通 target 不在 state 内。

installed old/new reader 路径进一步使用真实 `open_runtime`、Artifact、scheduler binding、Run、approval、execution 和 qualification/admission。C1 在 snapshot 后登记 new Artifact/binding、failed control Run、`revise` approval 与 created execution；rollback 恢复 C0 site/config 后，C0 reader 仍按 binding 读取同一个 new Artifact ID，Run/approval/execution 身份和状态不变，新 revision 的真实 critic preflight 仍以 `input_cohort_approval_missing` 拒绝，old foundation 仍准入。TCAD submissions marker 仍可读。该 control Run 未 attach Worker、无科学输出，不是科研 Run 或 solver 证据。

## 串行测试、失败与资源

全部批次先要求 `MemAvailable >= 8388608 KiB`，设置 `ulimit -v 6291456`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`PYTHONDONTWRITEBYTECODE=1`、`MALLOC_ARENA_MAX=2`、`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`，使用 `/usr/bin/time -v` 与 timeout；没有并行 pytest、全量 pytest、第二次 wheel 构建或残留 pytest/pip 进程。

### 首轮 transaction 定向批次

四个 selector结果为 **3 passed、1 failed in 0.43s；exit 1；wall 0.91s；MaxRSS 67160 KiB；MemAvailable 15011536 KiB**。唯一失败是测试在 rollback 后先 reopen SQLite，SQLite 自身重写 `-shm`，随后才比较字节；生产 rollback 没有触碰 sidecar。断言改到任何 reopen 之前，没有降低期望或改变生产语义。

### 非 installed 合并批次

覆盖 shell syntax、canonical overlap、preserve/legacy sqlite、真实 ERR trap、既有 skill/unit/file 回滚、installer transaction 清单和 nested profile：**11 passed in 3.53s；exit 0；wall 4.09s；MaxRSS 112616 KiB；MemAvailable 15083284 KiB**。

最终修改 symlink/missing 与 rollback manifest 前置校验后，收窄批次 **5 passed in 1.77s；exit 0；wall 2.21s；MaxRSS 103208 KiB；MemAvailable 15025216 KiB**。CLI 负例包括：同一 `--sqlite`/preserve path、`..` alias、symlink alias、普通 target 为 preserve 祖先、普通 target 为 preserve 子孙、直接命中 sidecar；全部在 transaction root 创建前非零退出。原 `--sqlite` existing/missing 恢复、sidecar 清理、普通 missing file 清理及 symlink 恢复通过。

跨边界自查把 platform backup/permission traversal 收窄后，shell syntax、真实 ERR-trap 与“不遍历 nested state”三个 selector **3 passed in 0.47s；exit 0；wall 0.74s；MaxRSS 67432 KiB；MemAvailable 15038088 KiB**。正例在 state 内放置指向外部目录的 symlink；platform preparation 不读取/拒绝/改写它，备份只含 config/agents/guides 且不含 state。

### 唯一 installed 大批次

按 R5-N 只运行一次 wheel/installed 合并批次，两个 selector最终 **1 failed、1 passed in 51.52s；exit 1；wall 51.93s；MaxRSS 95452 KiB；MemAvailable 15097648 KiB**。五种 distribution cohort 判定已完成；失败发生在状态 after/rollback 前：exact HEAD C0 profile 没有 `scidiscovery-guides/`，新增 fixture 却无条件 `shutil.rmtree` 该 missing target，得到：

```text
FileNotFoundError: [Errno 2] No such file or directory:
'/tmp/fig4-overlap-remediation-installed-20260922/test_installer_rejects_incompa0/active/.codex/scidiscovery-guides'
tests/operations/test_catalog_installed_entrypoint.py:415
```

夹具已改为 old missing 时允许 C1 创建 guides，rollback 后验证其再次 missing；old existed 时则验证 digest 恢复。依照“只运行一次大型 installed batch”没有重建 wheel 或重跑 pytest，也不把该批写成全绿。

为验证修正且不重复 wheel 构建，使用该批保留的 exact C0/C1 installed sites 从失败点继续，运行 after 写入、真实 rollback 和 C0 verify：**PASS，exit 0；wall 2.29s；MaxRSS 103400 KiB；MemAvailable 15046380 KiB**。观察到 new Artifact ID、failed Run、created execution、`revise` approval 全部保持；new admission 仍 `input_cohort_approval_missing`；old HEAD missing guides 在 rollback 后保持 missing。该收窄 probe 不冒充 pytest 批次全绿。

### R2 报告中的五个既有失败

没有运行、修改或归因 `test_installer_only_manages_local_tcad_state` 的五种既有失败：`socket-`、`socket-legacy`、`command-`、`command-legacy`、`command-unused-relative`。R2 的精确诊断仍是夹具替换 `install` 后未创建 config 目录，真实 `ensure_agent_settings` 打开不存在的 `agent-settings.json` 而失败；本轮不触碰该 fixture 或相关生产语义，不把它们计为通过。

### 最终静态门禁

全工作树 `git diff --check`、`bash -n deploy/install.sh` 及 `python -m py_compile`（transaction、platform、三个相关测试文件）均 **PASS，exit 0**。本文与补正后的上轮记录分别用 `git diff --no-index --check /dev/null <file>` 检查；两者 whitespace diagnostic 为空，exit 1 仅表示文件内容与 `/dev/null` 不同，判定 **PASS**。

## Final 判定与边界

- 功能语义与收窄行为证据：**PASS**。生产合法嵌套 state 不再与普通恢复 target 重叠；CLI 非生产冲突 fail closed；真实 ERR-trap、sidecars、CAS 和 old-reader 身份/资格一致性通过。
- 唯一大型 installed pytest 批次：**FAIL（1 failed、1 passed）**，原因及修正如上；遵守一次限制未重跑，不能声称完整 pytest 全绿。最终 MaxRSS 取所有本轮测试/探针峰值为 **112616 KiB**。
- 未运行：全量 pytest、全 operations、science-control bench、生产 systemd 部署、live browser、外部 execution、真实 TCAD submission 生命周期、solver、Fig.4 科学复审、Root replay 与 token A/B。
- 部署：**否**。科研 Run：**否**。真实 solver：**否**。
- Root token：**不可观测，未估算**。修复者 token：**不可观测，未估算**；没有精确 native usage/trace 接口，RSS/耗时不换算 token。
- 未提交、还原、覆盖、整理或归因共享工作树中的其他改动。

## 候选摘要

| 文件 | SHA-256 |
|---|---|
| `deploy/install_transaction.py` | `cd768bffddf9cf2f890d95aeaf1554c8f34d0709086e5c15916a0f5d3d9c9880` |
| `deploy/install.sh` | `a5c67e9386714843688baaeba525f616f083147cee4b4155b91c91c582f3e5cd` |
| `src/scidiscovery/platforms/codex.py` | `19107703318b57ba37c628586bebbd4b03013235b40b682cc96b03b81460de3c` |
| `docs/INSTALL.md` | `44a3e08c71f875286c6b1b73fe19ea7c1b5cba8b15513044ebfbdf0976b78118` |
| `tests/artifact_agent/test_deploy_scripts.py` | `f9991076bdd29347334be0e6dfb3616a167474f501dec7924e513e22059fc8a6` |
| `tests/artifact_agent/test_platform_configuration.py` | `1d52ff12fdc87c676f8d039b6eca6520083b5351b5ed4cc587a7f4dd474c6f7d` |
| `tests/operations/test_catalog_installed_entrypoint.py` | `4609197eacbc54921393b245d2cb3dc9a0288aee7000c70de3bf4d371cdf44e8` |
| 上轮 remediation 补正 | `692c4d37bb146c9107e21d118e48f2635f6d8de74bdf8510ea1ccb8fd43ef9a9` |

摘要绑定本文写入时的共享工作树候选；最终静态门禁后若文件内容发生变化，以交付工作树为准。
