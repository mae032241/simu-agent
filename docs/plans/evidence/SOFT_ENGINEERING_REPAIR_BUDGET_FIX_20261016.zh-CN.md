# Soft 工程修复预算门槛修复

## 根因和范围

`controller._repair_funds` 被普通 audit 后 W 修复、closeout 状态投影和 closeout 修复启动共用。它原先不区分 soft/hard，要求同时存下完整 W 目标、后续 A 目标和收口 floor；这与已有 soft node admission、exploration admission 和 continuation 的剩余预算语义冲突。

本场剩余 952,486 token / 717.075 秒，W 目标 650,000 / 480、后续 A 150,000 / 120、floor 200,000 / 120。原式要求 1,000,000 / 720，因此拒绝；必要后续预留实际为 350,000 / 240，仍有 602,486 token / 477.075 秒可用于修复。

本次生产仅在 `_repair_funds` 加 soft 分支：剩余必须严格大于 A + floor，并满足既有 W/A/外部动作步数预留。hard 原式保留。没有改科学审计、候选实现、预算授权、修复次数、冻结实例或启动命令；没有自动重跑真实场。

## 后继门槛核查

- 普通修复之后的 `exploration_admission`：soft 的 `delivery_reserve` 保护一个后续 A + 收口 floor；W 目标不是准入所需余额。
- closeout 修复的 `node_admission`：soft 保护 floor + 后续 A，W 需有正剩余。
- `accept_continuation`：soft 不要求完整剩余 W 目标，仍保护普通 delivery reserve，或 closeout repair 的 floor + 后续 A；原先消耗继续累计。
- `execution_blocked`、未知用量和步数保护保留。没有把未知外部动作当作可重复提交。

沿用现有 `_repair_funds` 的完整 cleanup floor 口径；没有在这次修复引入 preparation_seconds 减免。closeout repair 的 advisory hint 尚未显示后续 A 预留，本报告不宣称所有建议字段完全一致。

## 定向证据

受管命令：`python scripts/run_tests.py --lane source --output /tmp/scid-soft-repair-budget-20261016/source-r1 tests/research_loop/test_repair_budget_admission.py tests/research_loop/test_audit_engineering.py::test_known_unsealed_repair_worker_resumes_exact_session_without_rewriting_seals`。

结果：20 passed；pytest 65.04 秒，监督 65.611 秒；cleanup_complete=true，峰值进程树 RSS 300,720,128 字节，无内存停止。原始日志和 resource 位于上述目录 `batch-001/{pytest.log,resource.json}`。

18 项新检查覆盖实际余额、严格 reserve 等号/不足、步数、unknown/blocked、hard 原门槛，以及 ordinary/closeout 两入口在正常和已知失败后原 session 续接情况下到达既有 cov fixture 的 `delivery_confirmed`。已有 2 项续接检查额外证明后续 A reserve 不足仍拒绝、不会接受新 attempt，充足时原 session 成功且重复恢复不增加执行。均使用无模型确定性 fixture，不代表真实模型重新执行。

`git diff --check` 通过。生产和测试本批期间保持冻结。未跑全量或新 installed build：本次只改同一现有 Python helper 的预算条件，没有安装/注册变化；不将源码检查冒称安装包验收。

## 文件

- `src/scidiscovery/research_loop/controller.py`：仅 6 行新增；SHA256 `6918d5ee464f5af2239a232892ab9e5572611b2add68b053901f5c89bbb3862a`。
- `tests/research_loop/test_repair_budget_admission.py`：SHA256 `f10d206e8b76b2b4c6fdeb5b27f1aa301703816a0b6b09a6804d5c0a0b7aa396`。
