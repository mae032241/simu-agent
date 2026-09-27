# Root 上下文边界修复计划 R1 独立 SOL 复审（2026-09-21）

结论：**需一次局部修订（NEEDS REVISION）**。

复审对象及身份：

- R1 计划：`docs/plans/ROOT_CONTEXT_BOUNDARY_REMEDIATION_PLAN_20260921.zh-CN.md`
- R1 SHA-256：`282b690a19c28bec5c41db90affc4020f86945b8675e1af209f74250e4750ef2`
- R0 快照 SHA-256：`c7c1205e52b591cf6e4c5ba677a475938c8ed2c63e9e1c1eddf87247def1639c`
- R1 修订 manifest SHA-256：`5a27c1f50b7ff8b1f9ad75e7818731518e33166116a3a53ac4896665f6092d17`

三个哈希均与复审任务给定值一致。manifest 的五条修订声明与 R0→R1 实际差异对应。本轮只复核上一轮三项 P1、两项 P2 及修订直接引入的风险，没有重新扩展架构审查；未运行模型、solver、科学 Operation、Fig4、部署或测试，未修改计划和生产代码。

## 已关闭项

以下四组问题已经闭合，不再阻断实施：

1. **producer 投影（原 P1-2）**：R1 定义了共用 `ProducerInputProjection`，承载 port、稳定 item index、exact ref 和冻结名称；Run 先以 exact producer 证明，再区分 catalog 缺失、同 id 异 version/digest；transform 唯一分组写回同一记录；cross-instance 冻结名称置 null。它不递归、不猜历史、不建立第二映射或状态机。
2. **invoke 合同（原 P1-3）**：R1 加入 `revision_policy`，把 revision limit/progress 拒绝映射回同源规则；明确从 `CompiledOperation.digest` 增加 additive `operation_digest`，取消互相冲突的逐字节兼容要求；通用 invoke 参数仍由 interface Schema 承担。完整合同、独立 review、approval、currentness 和 side-effect gate 保持。
3. **可执行 replay（原 P2-1）**：R1 先冻结有 response identity/canonical hash/脱敏清单的结构 fixture，并区分真实值受限证据与合成 golden；脚本、目标窗口和 manifest 均有身份绑定，不再拿分类统计冒充 projector 输入。
4. **新路径实际采用（原 P2-2）**：R1 在安装及真实 A/B 中分别报告 describe/poll/navigation/decision 的 eligible、actual、fallback、原因和字符；未采用新路径时禁止归因收益。已安装 AGENTS/guides、入口 Schema 和实际 runner 都有验证要求。

`run_status` 的 profile × view × output 组合也已基本闭合：仅 `compat + detail` 为 full，compact + detail 明确拒绝；decision 只在 completed 返回 selected values 与一次 signal；diagnostic events 保留原游标和 `engineering.reference`。

## 唯一剩余 P1：compact profile 丢失恢复边界，且计划声称的 recovery failure 定位目前不可实现

R1 第 85–92 行把 compact profile 的恢复信息限定为 `recovery_available`，并明确 poll 不携带 recovery detail；同时要求 recovery failure 能由 `diagnostic_summary + event/reference` 定位。这两条不能由当前生产路径同时满足。

当前 `RunService.recovery_status` 提供的安全机械状态至少包括：

- `delivery_preserved`
- `resume_available`
- `draft_available`
- `recovery_pending`
- 条件性的 `original_retained`

现有 compat `run_summary` 保留这份 recovery 状态。仅保留布尔 `recovery_available` 会把“恢复仍在隔离中”“draft 已保存但不可恢复”“原 writer 尚未确认停止”等状态合并为同一个 false，Root 无法保持原 recovery gate，也无法选择正确的恢复/停止动作。

另外，`snapshot_unavailable`、`contract_unavailable`、`writers_unconfirmed` 等恢复代码写在冻结 recovery record 中；`_pending_recovery` 不会追加 `diagnostic_events`。因此这些情形不能按 R1 当前文字由 event/reference 定位。R1 自己要求的 recovery-failure golden 会暴露这一缺口，但计划尚未定义通过所需响应字段。

最小修订只需补一段，不改变总体方案：

1. 在所有 failed compact 响应中保留一个 **compact recovery status**，至少投影现有 `delivery_preserved/resume_available/draft_available/recovery_pending/original_retained`；不携带 coverage、tool evidence、文件或完整 recovery detail。
2. 若计划仍要求定位具体 recovery failure，则从控制已有 recovery record 投影一个受控机械 `reason_code`（例如现有 code 的 allowlist），并给出按需读取原始安全诊断的现有入口；不得返回 draft、路径或工作区内容。若不增加 reason code，则删去“recovery failure 可由 summary + event/reference 定位”的断言，只要求保留上述 gate 状态。
3. 修正第 83 行游标措辞：`diagnostic_after` 省略时保持当前“无 events 的 compact status”；显式 `diagnostic_after=0` 才是第一页。当前“没有 diagnostic_after 时沿用现有首段语义”与 `RunStatusInput` 的实际接口描述不一致。
4. golden 增加 `recovery_pending=true`、draft preserved but resume unavailable、writers unconfirmed/snapshot unavailable，证明 compact profile 与 compat 对恢复 gate 的判读相同，同时正文不展开 recovery payload。

这是一项局部响应合同修订，不要求新状态、数据库字段、恢复算法或控制大脑。补齐后，上一轮五项审查要求均可闭合；本轮没有发现其他 P1/P2。
