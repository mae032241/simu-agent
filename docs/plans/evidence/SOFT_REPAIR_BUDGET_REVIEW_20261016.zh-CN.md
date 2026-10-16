# Soft 工程修复预算独立审查（2026-10-16）

**PASS（精确差异范围）。** 未发现本修复新增 P1/P2 阻断。基线 `d70ab2d3a783eb1ff77575b3d060f1768e78e5a8`；仅审 controller 的 6 行 soft 分支及其定向测试，不作全局预算审计。未改实现、未提交或启动新模型场。

| 文件 | 独立核对 SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/controller.py` | `6918d5ee464f5af2239a232892ab9e5572611b2add68b053901f5c89bbb3862a` |
| `tests/research_loop/test_repair_budget_admission.py` | `f10d206e8b76b2b4c6fdeb5b27f1aa301703816a0b6b09a6804d5c0a0b7aa396` |

`_repair_funds` 在 soft 模式只要求剩余 tokens/seconds **严格大于** 后续 A 与 closeout floor，允许 W 使用正余量；不再强制预留完整 W 目标。等于预留额时仍拒绝。hard 原完整 W+A+floor 算式、步骤要求、缺 W policy、unknown usage 与 execution_blocked 拒绝条件均保留。

已追踪普通 audit 后工程 W、closeout 工程 W、状态/恢复入口的共同 helper，以及 `budget.node_admission`、`accept_continuation` 的后续 A/floor 保护。新分支不增预算、不退款、不改旧 seal，也不自动重放真实场。既有 preparation_seconds 保守口径和 advisory hint 未修改；本结论不声称所有提示字段完全一致。

## 验证

复核原始证据 `/tmp/scid-soft-repair-budget-20261016/source-r1/{result.json,batch-001/pytest.log,batch-001/resource.json}`：**20 passed，65.04s**；监督65.611s、returncode0、cleanup_complete=true，tree RSS高水位300,720,128 bytes，无资源触发。由仓库 serial_lock/run_one 管理，数字线程1；独审复用充分证据，未重复运行。

覆盖真实场余量数值952,486 tokens／717.075s的确定性边界、预留额等号/不足与步骤不足、hard完整门槛不变、unknown/blocked拒绝；普通与closeout两个真实 CLI 修复入口及已知失败后同 session 续接均交付成功。断言只接受一个修复 call、旧 seal 字节不变、原预算不变且没有 budget_amend。另两项既有续接 A 预留保护回归通过。精确 diff 空白检查通过。

采用 `scid-cross-boundary-review` 与 `scid-change-scope-checks`。本轮为源码与无模型 helper 工程证据，未重建安装版或重跑真实 cov；先前 cov 停止并不会因补丁自动恢复。真实 generic 的已确认交付/精确 replay 属此前场证据，不作为本补丁已真实运行的证明。
