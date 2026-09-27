# R4 P3 恢复代码有界复核

日期：2026-09-10。范围：`service/runs.py`、`service/local_workspace.py`、`service/run_records.py` 的当前工作树；不审查本人编写的 Root 路由。方法：静态阅读实际调用路径，未运行测试、未编译目录。本记录不是总体独立验收，也不证明尚未运行的真实交接或故障注入通过。

## 当前结论与发现记录

初审发现下列问题并发送给恢复实现者；随后重新阅读实际修订。RCV-1/2/3 均已静态确认修正（见下文），本次有限范围未发现仍未修正的阻断。执行证据仍待父任务提供，静态闭合不等于测试通过。

| 编号 | 严重性 | 具体触发和实现位置 | 影响及所需验证 |
| --- | --- | --- | --- |
| RCV-1 | 阻断 | `RunService._validated_candidate` 将所有 `WorkspaceError` 原样抛出，`submit` / `validate_candidate` 将其记录为 `output_rejected`；`LocalTrustedBackend.open` 的受控绑定/工作区缺失、`_sealed_candidate` 的已接受候选缺失/摘要改变也使用此异常。 | 作者修改输出无法修复控制绑定或已接受候选。完整性错误仍被报告为 running/rejected，不进入 failed 保全。须区分确实可修的空输出/输出预算等错误与控制完整性故障，并覆盖正式提交和预览。 |
| RCV-2 | 阻断 | 完整快照已写入 `complete_snapshot_digest`，`discard` 将原目录移入 quarantine 后失败；此时合同暂不可用，再次 `record_failure` 进入 `_finish_failed_workspace` 的合同不可用分支，`_pending_recovery` 会以新字典覆盖掉完整快照标记。 | 恢复旧合同后无法再用标记续完隔离；snapshotter / seal 只能打开已不存在的原工作区。应保留已建立的完整快照关联，不以部分 output 候选替代；覆盖隔离中断→合同变化→失败重试→原合同恢复序列。 |
| RCV-3 | 待修 | `LocalTrustedBackend.discard` 的原 workspace 和 quarantine 均不存在分支，仅 `_sealed_files` 枚举 recovery 目录，直接返回带请求 digest 的 `RecoveryDraft`，没有重新比较实际摘要。 | 典型窗口是完整副本写好且原件删除后，恢复 manifest 写入失败；重启须先核验材料，再宣布恢复流程完成。状态查询的后续 `_verify_draft` 会拒绝损坏稿，因此这里不构成未经校验的 draft 准入，但显式恢复调用可能返回带假定摘要的记录，未完成一致的保全核验。 |

## 已确认的窄边界

- `schedule` 对 resume/draft 互斥，draft 无来源时不接收摘要；draft 来源身份、backend 身份/版本/capabilities、目标支持、文件实际摘要及原始链次数在 `BEGIN IMMEDIATE` 内重新检查，再插入新 Run。
- `request_digest` 包含 draft 来源及控制读取摘要；无 draft 时不增加空字段，保持既有请求表示。原 `resume_from_run_id` 的意义未替换。
- `_recovery_digest` 仍严格比较源 Operation digest 和有序 ArtifactRef；draft 单独允许同 Operation ID 的新合同和新输入，并不调用源 `_compiled`，但旧记录缺冻结预算时仍需旧合同才能恢复预算。
- 混合 resume/draft 链统一计数，使用根节点冻结次数与目标次数的较小者；祖先遍历拒绝环和双父边。
- 合同不可用分支不会调用新合同 snapshotter/finalizer 或 destructive discard；即使 output 封存成功仍保持 pending，不把它判为完整交付。
- 正式输出接受、Artifact 发布和完成 CAS 仍在科学验证成功之后，发布/完成异常不被统一包装成失败重开。预览不设置 accepted candidate。
- `_validation_inputs` 只核对冻结记录和实际字节，不重新查询输入 current/科学资格。
- 新诊断摘要插入时只保留安全类别、编译规则编号及有限静态 envelope 路径，未存原始异常消息/草稿值；计数来自活动记录。Root 已有原始 reason 投影不属于本次摘要字段，外部调用者提供的 reason 安全性未在此复核中扩展验证。
- `run_records` 读取追加可空字段；数据库迁移追加列，不伪造旧预算。未知预算旧合同丢失时保留工作区而非猜测导出。

## 执行证据限制

尚无本复核自行运行的测试证据。需要父任务在总内存约束下验证上述故障序列、并发/重复提交、普通 Operation 与 author 最新 deck B 的保全、重新读取真实文件摘要及新合同草稿交接。静态符合的路径不代表这些用例已通过。

## 修订后静态复核

- RCV-2：合同不可用分支向 `_pending_recovery` 传回现有 `complete_snapshot_digest`，恢复原合同后可按该标记调用 `discard` 续完隔离；标记不使合同不可用时的部分封存显示 available。静态闭合，故障序列测试待执行。
- RCV-3：无工作区/隔离目录的幂等恢复分支改为调用 `verify_recovery` 重算摘要后返回。静态闭合，损坏稿重启测试待执行。
- RCV-1：新增 `WorkspaceOutputError` 表示空输出、输出预算/内容等可修问题，候选准备分支的其他 `WorkspaceError` 已转为 `integrity_failure`。但 `run_outputs.validate_run_output` 读取封存文件失败仍抛 `WorkspaceError("sealed result is unreadable")`；它发生在 `_validated_candidate` 的第二个 try，该分支尚只捕获 `RunCheckerError`。因此封存后读取失败仍会经 submit 的可修拒绝分支处理。已再次通知实现者；随后第二个 try 增加 `WorkspaceError` → `RunCheckerError(category="integrity_failure")` 转换并保留 `sealed.digest`，重读实现确认正式提交和预览均进入框架失败保全。该项现已静态闭合，相关故障注入测试待执行。
