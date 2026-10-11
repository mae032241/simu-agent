# N1a：持久原生执行与恢复收口

日期：2026-10-11。基线：91368e8。范围：research_loop 的 runtime/native/controller/cli、CLI 说明及 runtime 故障测试。

## 结论

两位独立审查者复审通过；63 项定向回归及安装 wheel 的 CLI 假进程 H→W→A 通过。未调用真实模型；N1b 启用时长与预算修订尚未实施。

## 修改与复审

- 持久 runner 持有执行租约；控制器重启核对任务摘要及进程身份后等待同一执行，未知结果不重放。
- 暂停阻止新派发，已接受工作仍收集封存。原始结果固定并校验后才发布成功终态。
- 独审发现实际启动前预算竞态，已在 Popen 前复查；确定未启动时为零用量 native_not_submitted，保留意图且不自动重试。
- 独审复现主进程退出后子进程残留，现由 runner 的 subreaper 核对并清理归属进程；清理未知则拒绝成功封存。

## 验证

- `python scripts/run_tests.py --lane source --output /tmp/scid-n1a-recheck-final tests/research_loop`：63 passed，9.33 秒。共享串行锁与资源监督入口。
- 生命周期审查者独立重跑两条残留子进程负例，以及原始复现：child_alive=false；报告 `/tmp/scid-n1a-lifecycle-review-fixed.md`。
- 预算审查者独立复测过期 deadline：未执行科学进程、零用量、意图保留。
- 安装验证 `/tmp/scid-n1a-installed/result.json`：安装 wheel 模块来自隔离 venv；prepare/run/status 完成 3 个假角色，重跑不重复执行，models_called=0。wheel SHA256：da77ffd207a0781d247d2f523be737c1698b5b7489bfab10bbeca2319fd776d5。
- `git diff --check` 通过。未运行无关全量平台测试、真实模型、远端求解器或跨天验证。

## 保留边界

当前仍为旧墙钟计时；启用时长与人工预算修订由 N1b 交付。用量来自观测事件，不承诺逐请求硬计费限制。watchdog 的 /proc 核验后数字 PID/PGID 信号不是 pidfd 原子操作；脱离原会话/进程组的后代由启动器管理，不声称任意时序绝不误杀。

真实 cov 总计 3 场包含已完成 live02，后续只新增 2 场，各最多 600 万 token。旧基础场不授予本节点的新恢复能力资格。
