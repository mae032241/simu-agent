# R5-L 最小默认运行主干第二轮独立审查

日期：2026-08-31  
审查者：`r5s_s0_independent_review`（未参与候选编写）  
候选摘要：`8355374c1de41511c2d9ee92ebe118c435f54b345603d386ea11282e9d1e2301`  
结论：**通过**

结论写回后只机械修改候选第 4 行行政状态；审查者复核确认设计正文未变，当前文件摘要为
`6ac6302bf1c2bc88405e12b2958fe1e8fcfb72e927839f0c1b2ea0e107f48f0b`，原 verdict 继续有效。

## 1. 关闭的阻断项

1. `Run` 已定义为旧 `Task` 的瘦身后继；`RunService` 独占完整校验、Artifact 登记、终态、current、
   reviewer 和恢复收据。backend 只返回非持久化 `SealedWorkspace`。
2. currentness 已改为沿生产收据递归判定，并在完成写事务中重新检查。第一版一个 Operation 最多
   推进一个 head；stale 时保留 Artifact、完成 Run、记录 `stale_rejected`，但不推进 current。
3. recovery 前先 CAS 失败旧 Run 并隔离写入者；`recovery_draft` 是 backend-private、非证据、不能
   成为普通输入、资格、审查或 current。
4. `OperationToolContext` 已形成后端无关的领域工具投影；TCAD 明确从
   `TaskService/session/provisional snapshot` 耦合迁出。
5. LocalTrustedBackend 仍明确是 `SEC-002 known_issue`，只用于可信本地开发，不能携带生产凭证、
   远程执行或不可逆副作用，不能宣称 33 项全部符合。
6. Hardened 从 L0 到 L4 均有防腐回归，L6 以零默认消费者、唯一 Run 权威、无兼容转发和安装矩阵
   为删除门。
7. backend 共同接口包含 heartbeat，不能扩大绝对预算或写终态；完成事务内部重新检查所有 current
   锚点，关闭 TOCTOU。

`accepted_candidate_digest` 是提交崩溃窗口需要的单调围栏，不是第二终态；两个 backend 只是
工作区和传输实现，没有形成第二 Catalog、preflight、invoke、Run 或 current 权威。

## 2. 非阻断实施建议

- 没有真实消费者前不要实现独立 `RecoveryPolicy` 实体；
- `FutureRemoteBackend` 只保留为方向，不预建代码、配置或状态；
- `worker_open_assignment` 的真实验收要证明 Agent 只看到科学别名和身份无关路径；
- `recovery_draft` 清单应包含原 Run/请求摘要、后端版本、写入者隔离证明、文件摘要、原因和时间；
- L2 覆盖候选摘要绑定后的三类崩溃窗口、heartbeat 绝对预算和校验后 current 并发变化负例。

## 3. 放行边界

本次只确认架构计划可以进入分阶段实施。它不证明当前代码已完成迁移，不证明 LocalTrustedBackend
满足完整 `SEC-002`，也不允许跳过 L0 的 S2 候选归类、可测试边界恢复和 Hardened 防腐冻结。
