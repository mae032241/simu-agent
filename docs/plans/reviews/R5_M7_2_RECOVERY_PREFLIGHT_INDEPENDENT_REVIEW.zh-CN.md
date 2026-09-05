# R5-M7.2 恢复预检共享校验独立审查

日期：2026-09-02  
审查范围：当前工作树中的 `RunService` 恢复校验、Root Operation 预检接入及 L2 恢复不变量测试  
审查方式：只读代码追踪、聚焦测试；未修改运行状态或科学数据  
结论：**通过；阻断项 0。允许进入一次全新持久证据根上的最小恢复实跑。**

## 1. 结论摘要

本候选已经消除此前确认的恢复请求 `preflight`/`invoke` 断裂：恢复源状态、恢复草稿存在性、
Operation 摘要和精确输入引用只在 `RunService._recovery_digest()` 中定义一次；Root 预检通过
`RunService.validate_resume()` 使用它，实际调度又在 Run 数据库的 `BEGIN IMMEDIATE` 事务内，
对冻结后的输入重新调用同一校验。

因此，预检不是实际调度的替代权威；它是同一规则的纯查询投影。实际 Run 创建仍由事务内校验拥有
最终决定权。没有增加恢复表、恢复状态、第二注册表、领域分支或新的科学实体。

## 2. 实际追踪的调用链

### 2.1 纯预检

`RootOperationRoutes._prepare_operation_call()` 先用当前编译 Operation 完成端口绑定，再将：

- 当前实例中解析得到的源 Run；
- 当前编译 Operation 摘要；
- 按编译端口次序形成的输入 Artifact 引用；

交给 `RunService.validate_resume()`。后者只读取 Run 状态，并委托
`RunService._recovery_digest()`；没有创建 Run、绑定、Artifact 或恢复文件。

错误输入现在在 `operation_preflight` 返回
`recovery_source_unavailable`，不会再先显示可准入、到 `operation_invoke` 才因
`RunService.schedule()` 失败。

### 2.2 实际调度

`RunService.schedule()` 没有信任预检结果。它在 Run 数据库的写事务中：

1. 通过 `RunCurrentGuard.freeze()` 再冻结当前实际输入；
2. 在同一事务连接中重新读取源 Run；
3. 对冻结后的 Artifact 引用再次调用 `_recovery_digest()`；
4. 只有校验成功后才计算请求摘要并插入新 Run。

这保留了调度时最终校验，关闭了“预检后输入或源状态变化便直接放行”的窗口。校验异常会退出事务，
不会留下半条 Run。源 Run 一旦进入带恢复草稿的 `failed` 终态，现有生产路径不会将其恢复为运行态；
即使预检和调用之间发生外部文件丢失，后端准备阶段仍会失败关闭并显式记录新 Run 失败，而不会把
草稿登记为科学结果。

## 3. 单一权威与次序判断

共享关系为：

```text
validate_resume（纯查询入口）
        └── _recovery_digest（唯一规则）
                    ├── Root preflight
                    └── schedule 事务内复核
```

`validate_resume()` 不是第二套校验逻辑，只负责把源 Run ID 解析为不可变状态记录；真正的四项规则只
存在于 `_recovery_digest()`：

- 源 Run 必须失败且具有恢复草稿；
- Operation 摘要必须一致；
- 有序输入 Artifact 引用必须一致；
- 草稿摘要必须存在。

调度次序正确：先冻结实际输入，再比较恢复输入，最后建立新 Run。没有先插入 Run、再补验恢复源。
预检中恢复检查位于通用端口/Schema 绑定之后、下游准入检查之前；全部是只读且错误被统一失败关闭，
不会形成授权或数据泄漏问题。

## 4. 测试证据

独立执行：

```text
PYTHONPATH=src pytest -q tests/operations/test_l2_run_invariants.py \
  -k 'status_is_pure_and_failure_recovery_is_explicit or \
      timeout_reconcile_uses_activity_compare_and_set or \
      failed_workspace_reconcile_is_idempotent_across_backend_reopen'
```

结果：`3 passed, 8 deselected in 1.37s`。

其中恢复测试已覆盖：

- 失败 Run 形成恢复草稿；
- 错误输入的恢复请求在 `operation_preflight` 阶段拒绝；
- 拒绝前后 Run 列表完全相同；
- 错误请求没有建立 Run 绑定；
- 正确输入能够建立显式新 Run；
- 新 assignment 将恢复草稿标记为 `scientific_evidence=false`。

另外两项继续证明超时观察使用活动时间比较交换，以及失败工作区隔离可在后端重开后幂等收口。

## 5. 非阻断限制

1. Root 将恢复校验的具体异常统一投影为 `recovery_source_unavailable`。这减少了对调度者暴露的内部
   细节，但也会隐藏数据库故障与合同不匹配的区别；当前行为是失败关闭，不影响本阶段授权正确性。
2. `RunService.schedule()` 本身没有额外比较源 Run 的 `instance_id`。当前唯一生产调用者先通过
   当前实例的 scheduler binding 解析源 Run，因此实际 Root 路径保持实例隔离；若未来出现绕过 Root
   的第二个服务调用者，应先补实例一致性，而不能直接传入任意源 Run ID。
3. 本轮没有解决 `LimitsSpec.max_attempts` 在最小 Run 主干中未消费的问题。后续实跑可以证明一次
   新 Run 的时间、文件和字节边界，以及“失败后显式新 Run、绝不续接旧会话”；在尝试次数语义明确
   并落实前，不应把该结果扩大为“任意恢复链总次数已经有界”。
4. 已存在的 `m7-live-generic-20260902-01` 中，唯一带草稿的历史 reviewer Run 使用旧 Operation 摘要，
   不能通过当前共享校验。不得为复用它而覆盖当前目录或手工恢复旧 catalog。

这些限制不阻止一次全新、当前摘要下的最小持久恢复实跑。

## 6. 放行边界

本 PASS 只允许下一步按已审定方案执行：

```text
当前编译 Operation
→ 独立确定性 Worker MCP 子进程打开 assignment、写合法草稿后非零退出
→ Root 用精确 state/last_activity_at 比较交换记失败
→ 同一 Operation、同一指令、同一完整输入以 resume_from 建立新 Run
→ 一次真实、内存受限的 Codex 完成受控提交
→ 重启后从 Run/Artifact/恢复草稿持久事实复核
```

不得修改 SQLite、手工登记草稿、恢复旧 Codex 会话、覆盖旧 Operation 摘要、增加恢复插件或第二
状态机，也不得把失败进程退出码、聊天或 recovery 文件本身当作科学结果。

本报告不宣称 M7.2、M7 或 R5-M 整体完成。
