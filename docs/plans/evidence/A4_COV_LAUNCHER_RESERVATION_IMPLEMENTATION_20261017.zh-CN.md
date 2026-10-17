# A4 当前 Cov 启动入口预留接线

状态：实现冻结，待独立静态审查；测试未运行。2026-10-17。

## 根因与精确范围

当前薄 Cov 的私有 `cov_rerun_20261016/prepare_v3.py` 及 `cov_live_20261016/prepare_v3.py` 均复制仓内 `scripts/acceptance/rootless_cov_launcher.py` 为新场 launcher。该 launcher 使用 external 模式，经 `cov_lineage.configure` 自行产生执行配置；此前没有传 A4 已实现的预留字段。普通 `prepare --execution-config` 的配置归属模式不能直接混入这条 external 路径。本次不改旧 pilot、私有准备脚本、历史 launcher 副本、旧实例或 accepted 原件。

精确文件：

- `scripts/acceptance/rootless_cov_launcher.py`：新入口 operator 字段 `cov_engineering_check_reserve_seconds` 默认15，显式0关闭；类型必须为有限数值，非0须大于2且小于原65秒。启动前拒绝不可用配置。经原 main 的真实 configure 调用传递；启动及现有 `exp run` stderr 给短提示，不增加文件、账或执行协议。
- `src/scidiscovery/research_loop/cov_lineage.py`：configure 新增默认0 keyword，非0才加入已有 `engineering_check_reserve_seconds` 字段，经原 experiments.configure/freeze；0保持旧配置 body。旧 config reader 允许该可选字段并调用现有数值验证器。
- `tests/research_loop/test_rootless_fragments.py`：复用原 accepted/registry fixture，新增真实 configure→freeze→load 的15/0两个 source 实例，以及一个非法窗口/unsupported 通道小负控；不启动 namespace、实验进程或模型。
- `docs/ROOTLESS_CLI.zh-CN.md`：说明实际 external launcher 入口、operator 开关及上界限制。
- 本实施账。

## 语义与保护

原单调用65秒、共享科学预算及 ledger 不增加。请求15秒时实验上界50秒，检查上界10秒，反馈2秒，余下预留不变成新额度；实际原任务窗口不足时仍沿 A4 报 unavailable。启动和 exp 提示均为请求上界，不冒充 accepted 的 `reserved` 事实；真实回执继续复用 `engineering_check.time_allocation` 及原绝对截止。backend_file 没有 isolated_replay 能力，提示明确 unsupported/no partition；通用 Local 未修改。

原 accepted 的 deadline/配置不回填，原 freeze 冲突检测保持。检查 intent 未有 outcome 时仍 unknown，不重放。既有接受后启动前耗尽、单次文件/进程系统调用非硬实时及 optional 检查覆盖限制沿原 A4，不声称本节点消除这些限制。

## 静态与待验收

限定三份 Python 只作 AST 解析，不导入项目或执行脚本；结果见冻结通知。未运行任何测试、安装、模型、SSH、HTTP 或业务进程，未使用 Git。

供 root 唯一串行验证的最小新增 source 目标：

- `tests/research_loop/test_rootless_fragments.py::test_cov_launcher_reserve_reaches_real_frozen_configuration`（15/0两项）。
- `tests/research_loop/test_rootless_fragments.py::test_cov_launcher_rejects_unusable_reserve_and_keeps_unsupported_channel_neutral`（一项）。

原 A4 `test_replay_reservation.py` 已有 deadline/旧 accepted/未知不重放覆盖，本次未复制进程矩阵；是否需要一项原 A4 定向复验由 root 决定。新 source fixture 只证明 host 配置消费与提示，不代表真实 Cov 训练、采样检查或模型运行验收。

## root 串行验收追加

新增3个source用例均通过，pytest 0.67秒、监管0.974秒；原始结果位于 `.trial/review_reserve_followup_20261017/cov-source/batch-001/{pytest.log,resource.json}`。采样进程树峰值58,359,808 bytes（约55.66 MiB），清理完成，无内存止损触发。仅执行上述3项；未启动模型、Cov训练、安装或并行测试。它证明实际启动器使用的参数到冻结配置的接线、显式关闭与无能力渠道的中性提示，实际调用的reserved仍由原接受回执判定。
