# 假设审查与后续行动契约第三轮独立复审

审查日期：2026-09-03  
候选：第二轮 exact audit 与单后继事务返工后的工作树，统一请求指纹返工之前  
审查者权限：只读，未参与实现，未修改文件  
结论：**FAIL；阻断项 1**

## 1. 阻断项

### Root preflight 与 Run 事务最终检查发生规则漂移

同一语义名、同一 revision base，改绑另一份 critic request 并设置 `on_conflict=create_revision` 时，
`operation_preflight` 返回 `admissible=true`，随后的同请求 `operation_invoke` 才以
`local_run_creation_failed` 拒绝。事务正确阻止了第二个科学后继，但 preflight 没有兑现同一不可变
请求的准入结论。

根因是 Root 只比较既有后继的 `output_binding_name` 与当前派生输出名，把“输出名相同”误当成“完整
请求幂等”，没有比较 Operation、输入、instruction 和恢复来源构成的请求指纹。测试也只覆盖不同
名字的 sibling，没有覆盖同名、不同请求。

最小修复应复用已有创建目标的请求指纹：exact fingerprint 命中既有 Run 才是幂等；否则是新目标，
必须按同一 RunService 后继规则拒绝。Run 事务继续处理 preflight 后的竞态，不应新增状态或第二查询
实现。

## 2. 已确认关闭但不自动继承的结果

- foundation 由 `audit_A/source_A` 形成时，`audit_A/source_A` 正例通过，另一个 completed passing
  `audit_B/source_B` 以 `guard_rejected` 拒绝；
- 双线程同基线调度恰好一个成功；赢家失败后新 Run 可重试；
- 两级真实修订链分别触发 `revision_no_progress` 与 `revision_limit_reached`；
- 当时候选的同名同请求重放返回原 completed Run；
- 假设键增删改名拒绝、重排接受；六种 disposition 和 Run 信号投影未见新断路；
- 未发现第二状态机、第二注册表、隐藏领域 DAG、TCAD 核心硬编码或第二 current。

## 3. 命令与未验证边界

- 聚焦契约、键边界、Run 持久化/恢复：`18 passed`；
- 安装目录非子进程检查：`4 passed`；clean-installed core 入口：`1 passed`；
- 并发探针：一个 scheduled、一个 `RunSlotBusy`，失败后 retry 为 queued；
- `git diff --check` 通过。

未验证部署后的 daemon/MCP 路径、真实 Fig.4 闭环、人工审批 UI，以及六种 disposition 全部经真实
Worker 提交的端到端矩阵；未运行全仓套件。

本报告只约束第三轮候选，后续返工必须重新独立审查。
