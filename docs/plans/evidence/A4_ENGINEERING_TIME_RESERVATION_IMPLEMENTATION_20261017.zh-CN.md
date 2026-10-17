# A4 原调用内工程检查预留：实施账

状态：**独立静态审查 PASS；root 串行定向测试 8 项通过。** 依据[授权/审查修复计划 §6](../THIN_AUTHORITY_REVIEW_REMEDIATION_20261017.zh-CN.md)。此次不实施 A1 隔离，不新增 RPC、权限或预算账。

## 配置、原件与调用顺序

操作者在已有 `--execution-config` 的 `configuration` 中可选设置 `engineering_check_reserve_seconds`，默认 `0`。例如原 `max_seconds=65` 配置选择 `12`，表示原65秒内主实验至多用53秒，检查至多10秒、反馈留2秒；不是65秒之后再续12秒。该字段由 Cov 构造验证有限非负且不接受 bool，随已有 operator configuration、config hash、capability/code proof 冻结。`experiments.configure` 原来的 operator 精确匹配仍禁止 W 自报另一配置；本节点没有新配置绕过入口。

1. Cov 可选 `isolated_replay` 声明支持时间切分，公开能力摘要显示总窗口、所选预留、反馈余量和覆盖限制。未声明能力的插件仍 `unsupported`，不扩必需生命周期接口。
2. 原 `replay_check.acceptance → Records.accept` 在 submit 前封存 `engineering_check` 的总截止与 `time_allocation`。有效预留从同总截止扣除，并裁到现有 soft admission 期限；预留不能容纳实验及反馈时标 `unavailable`，不构造负 timeout、不承诺预留，检查为 `not_run`。不会切分的可选插件标 `unsupported` 预留，仅保持原窗口内尽力检查。
3. `LocalExecution.submit` 仍先消费原 fresh lease，Cov 仅在新 accepted 的 `time_allocation.status=reserved` 时通过私有 `_execution_deadline` 使用冻结的实验绝对截止。旧 accepted 无该字段、默认0和普通 Local 保留原行为，不事后修改期限。
4. 原确认完成后才调用检查；检查截止仍不晚于同总截止减反馈，检查时长不超预留扣反馈后的份额和原能力10秒上限。主训练耗尽实验窗口、未产出已验证成功候选时不会凭空跑检查或给科学结论；检查 `not_run`，原实验事实按既有验证保留。检查 intent 无 outcome 仍 `unknown`，不再执行。
5. `replay_check.public` 只读显示实际 accepted 分配/原截止及原检查结果。检查失败不修改原成功结果、候选或 CLI 成功码；默认0明确 `not_reserved/best_effort`，不冒充保证会查。

## 精确文件

| 文件 | 责任 |
| --- | --- |
| `src/scidiscovery/research_loop/replay_check.py` | 操作者预留数值验证、accepted 分配、同总截止的检查时限、公开分配反馈。 |
| `src/scidiscovery/research_loop/local_experiments.py` | 默认不改变行为的私有 deadline hook；实际 Popen 前复核支持方的原绝对 cutoff。 |
| `src/scidiscovery/research_loop/cov_experiments.py` | 该可选能力/公开摘要及构造验证；仅消费已接受的分配，不重算新预留。 |
| `tests/research_loop/test_replay_reservation.py` | 4个小型 source/时钟测试：冻结与长实验份额、默认/不足/旧accepted、不会切分插件、非法配置。无进程或 solver。 |
| `tests/research_loop/test_early_replay.py` | 原短训练用例显式选择预留并核 accepted 截止；追加接受后窗口耗尽的真实 submit 路径，Popen 哨兵断无进程、unknown、重复 submit 不派发。保留其余依赖错误/失败/未知不重放保护。 |

## root 已裁定的边界

- 接受与 Popen 之间若因调度/IO而耗尽实验 cutoff，允许保留既有 accepted/no-process `unknown`；不伪造 completed、失败 run_id、退出码或永久未提交证明。原 fresh lease 已消费，后续 lookup/submit 只返回同 call unknown，不能自动重放。这个分支没有已知终态清阻保证，原件须保留供维护；本轮不新增 local retirement 系统。
- 预留是原窗口内的调度机会，不保证隔离 leaf 完成。原进程轮询/退出清理、完成原件校验、单次文件 IO/Popen 不能由 Python 硬抢占；这些开销可能耗尽预留，检查仍如实 not_run/unknown，不能刷新原 deadline。
- 只有 Cov 显式支持这项切分；TCAD 远端已接受工作及 solver wall 不改，不新开后置检查/重训。A1 的恶意 Worker 权限隔离仍未具备。

## 静态检查与后续最小目标

已只用标准库 AST 解析上述5个 Python 文件，限定 diffcheck 通过。私有指纹 `.trial/reviews/a4-engineering-reservation-author-final-20261017.json` 不提交。未执行项目 import、测试、收集、构建、安装、模型或服务器。

建议由 root 单一串行运行：source 仅 `tests/research_loop/test_replay_reservation.py`（4项）；process 先原短训练/依赖反馈项与新增接受后耗尽项，再按仍未验证风险选原默认0/unknown不重复项。不安装、不运行完整 cov 科学场；动态结果由 root 后续补证，不能以本静态账代替通过。

## 实际验证

独审见 [A4审查](A4_ENGINEERING_TIME_RESERVATION_REVIEW_20261017.zh-CN.md)。2026-10-17 使用 `/home/da/miniconda3/bin/python scripts/run_tests.py`、原资源配置 `.trial/p_migration_validation_20261017/resources.json`：

- source：`test_replay_reservation.py`，4 passed，监督耗时0.687秒。
- process：`test_early_replay.py` 中 train_only_dependency、reserved_window_expires、optional_check_exception、early_check_reuses 四项，4 passed，监督耗时3.441秒。
- 原始记录：`.trial/authority_remediation_20261017/a4-source`、`a4-process`；峰值149008384字节（约142.1 MiB），无内存止损，两批清理完成。没有安装、真实模型、完整科学实验或TCAD作业。
