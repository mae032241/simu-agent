# Fig.4 路线剪枝 R2：已撤回的安装状态根结构性分离尝试

- 实施日期：2026-09-22。
- 实施者：交互式 Root。
- 状态：**用户已终止并撤回；不实施、不部署，不是活动候选。**
- 起因：[R3 独立复审](../../reviews/FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R3_20260922.zh-CN.md)证明 `preserve-sqlite` 的 canonical alias、SQLite sidecar 和 nested profile 三个 P2。用户决定不继续支持 state 嵌入可回滚配置树。

> 撤回说明：用户随后明确安装回滚不属于 Fig.4 主线，可不实施。相关生产代码、测试断言和安装文档已恢复到既有安装合同；下文只保留尝试过程，不构成当前实现、部署要求或验收门。

## 唯一不变量

生产安装的 `SCID_STATE_ROOT`，以及启用本地 TCAD 时的 `TCAD_STATE_ROOT`，不得与源码、workspace、安装、配置、备份或 Codex launch root 相同、互为祖先或互为后代。比较使用 `realpath -m`，因此已有父目录 symlink alias 也不能绕过。默认 `/var/lib/scidiscovery` 与 `/var/lib/scidiscovery/tcad` 满足该规则。

运行数据库和 Artifact CAS 不再是安装事务成员。事务只复制并恢复程序、配置、角色、指南、service unit、launcher 和 skill。这个边界保留 Artifact、Run、approval、execution、qualification、binding 与 TCAD submission 的单一控制事实，不需要在 rollback 内维护“恢复但排除子状态”的第二套规则。

有意不再支持：生产 `deploy/install.sh` 将 state root 配置到上述任一受管树中。开发态 `open_runtime` 与测试临时目录未被全局禁止；限制只属于生产 installer。

## 删除与收敛

- `deploy/install_transaction.py`：删除 `preserved_databases`、`preserved_sqlite` manifest kind、`--preserve-sqlite` CLI 和对应 canonical-overlap 算法；恢复原 `--sqlite` 快照/恢复合同。
- `deploy/install.sh`：新增安装前 `validate_state_roots_are_separate`；数据库不再加入 transaction；framework/workspace/launch 的 `.codex` 重新作为普通精确目录整体备份与恢复。
- `src/scidiscovery/platforms/codex.py`：nested workspace 重新拒绝任何 `.codex`，删除 state-only 例外。
- 测试删除 preserve-inside-target 专用夹具，改为生产 state-root 分离正负例；old/new installed cohort 把真实控制 state 放在 transaction tree 之外，仍验证回滚后 exact C0 reader 可读取 C1 新 Artifact、binding、Run、approval、execution 与 qualification/admission 状态。
- `docs/INSTALL*` 与 `deploy/README*`：同步“只回滚程序/配置，运行状态位于事务树之外”的中英文规则。

该删除直接移除了 R3 三个 P2 的共同表面：事务 CLI 已没有 preserve identity 或 preserve sidecar；生产 profile validator 不再接受 nested `.codex` state 或未知内容。

## 串行验证

均设置 `ulimit -v 6291456`，未并行运行测试。

1. 语法、移除后的 CLI、原 SQLite 恢复、state-root 分离、transaction target 与 nested profile：`6 passed in 1.51s`，MaxRSS `107564 KiB`。
2. core/TCAD dry-run、旧服务回滚、launch root、平台权限和 profile 重编译：`6 passed in 6.76s`，MaxRSS `95364 KiB`。
3. 唯一 old/new wheel installed cohort：`1 passed in 53.06s`，MaxRSS `103860 KiB`。五种 distribution cohort、C0/C1 profile 回滚、C0 reader 对 C1 新控制状态和 qualification/admission 的读取均完成。
4. 追加 source/workspace/symlink alias/install/config/backup/launch state-root 负例及独立 state 正例：`1 passed in 0.28s`，MaxRSS `69552 KiB`。
5. `bash -n deploy/install.sh`、相关 Python `py_compile`、全工作树 `git diff --check`：PASS。

未运行全量 pytest、生产 systemd 安装、live browser、科研 Run、外部 execution 或 solver。R3 报告中的测试夹具失败和此前历史报告原样保留，不改写审查结论。

## 边界与遥测

- 部署：否。
- 科研 Run：否。
- solver：否。
- Root token：不可观测，未估算。
- 既有 Planner、Reviewer 与修复 subagent token：collaboration 接口不可观测，未估算。
