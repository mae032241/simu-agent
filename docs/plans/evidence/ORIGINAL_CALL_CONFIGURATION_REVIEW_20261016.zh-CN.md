# 原 call 跨 attempt 配置修复独立审查（2026-10-16）

**PASS（精确核心修复范围）；整场模型启动 gate 另行判断。** 未发现本次差异新增的 P1/P2 阻断。只读实现，仅写审查文档；未启动模型/solver、未重复测试或提交。

基线 `0c435f87f1e361c44027b3b8919103af8f2498cf`。精确文件与独立核对 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/experiments.py` | `15f3ad6c6bb9baf92b872dbb0ee37d26145be96f77526e1a8b8772b77ecff5c3` |
| `tests/research_loop/test_original_call_configuration.py` | `06a68482a6f96af85ebc80410ebc205d19ca9b42b41cc5bd6be9c2f601eca84a` |

## 跨边界结论

- `configure` 将原本已交给该 W 的配置原字节投影到既有只读控制挂载的 `interfaces/<attempt>.json`，不复制 native/session/home/auth/provider 文件或科学草稿，不扩大 mount 集合。投影冲突先校验，不能覆盖旧 attempt 原件。
- 原 call 由其 accepted.native_attempt 精确选取投影；检查严格 attempt 类型与 execution key，并核 scope、record namespace、accepted interface 一致，再由 load 复验实现和配置摘要。没有按 latest、executor 名称或相似 schema 回退。
- query/lookup/collect/cancel/reconcile、progress 和新 run 前的旧调用扫描均经过同一 resolver。当前选中配置与原配置的能力均须支持操作；collect=false 不调用 collect，未知或 running 不产生新提交。新提交仍由当前 adapter、当前 native_attempt 和原 admission/breadth 接受，原 call 不迁移到新 attempt。
- 能力 gate 指本次所选配置与原接口的兼容约束，不能宣称撤销任意 native Python/backend 权限。旧投影与旧 Worker 本来可保存的配置相同；soft admission 仍核当前 review 的 native_attempt，不授予旧 attempt 新 grant，hard 模式仍沿原 scope/breadth/maxcalls/native 授权。反馈继续使用调用时当前配置。

## 证据与限定

- `/tmp/scid-original-call-config-20261016/source-r1/batch-001/`：18 passed / 1 failed，17.93s；失败为新增 cov 夹具误用 `cov_execution:command`，未到原 call 操作。原日志保留。
- 修正为正式 `cov_execution:experiment` 和相应夹具后，`source-r2/batch-001/`：13 passed，14.03s；监督14.342s、returncode0、cleanup_complete=true。首批其余6项既有生命周期案例已通过，不把重跑相加成额外不同案例。
- 定向覆盖 local/cov/remote 跨 attempt query/lookup/collect/reconcile/lineage-status，新提交归属当前 attempt，异步 success/failed 且无 collect、原 call 保留与重复确认、投影缺失以及 scope/record/attempt/interface/实现/accepted-attempt 篡改、当前 collect 能力缺失拒绝。cancel 路由已静态审查，未声称真实远端取消副作用验收。
- 已独立核对 `.trial/dual_live_20261016/runtime-v2/identity.json` 的冻结源码摘要与实际 site-packages 文件逐字相符。该安装记录核对236个核心文件；wheel 为 `fa6be919b1a8cdb51e9ff37cf4b04d9add5dfa1dbd0603b4ddc2038acdeb1462`。精确 diff 空白检查通过。

采用 `scid-cross-boundary-review` 与 `scid-change-scope-checks`；本次不作全项目扫描。真实 bwrap 下的 cov 全链、generic 默认 local 工具零模型 gate、最终脚本/实例冻结及双场启动结论仍归[启动独审](DUAL_LIVE_LAUNCH_REVIEW_20261016.zh-CN.md)，不能由本核心 PASS 替代。
