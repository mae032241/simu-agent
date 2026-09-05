# R5-C Task 与 TCAD 调试归属迁移第四轮独立复审

日期：2026-08-29  
审查对象：第三轮剩余 attempt 逆序修订候选  
结论：**通过**  
门禁决定：**放行 Root 子环节**

## 1. 范围

本轮只复核第三轮唯一剩余阻塞：Task 权威 attempt 小于插件 debug attempt 时，是否失败关闭而不
再被解释成 Task 删除。未重新打开前三轮已经闭合的核心 reason、正常/删除恢复或插件装配边界；
未修改生产代码、测试、计划或阶段状态，唯一写入是本报告。

精确字节：

| 文件 | SHA-256 |
|---|---|
| `plugins/tcad_artifact/tcad_artifact/runtime_plugin.py` | `073bb64b8e5482a08df500de08b8fe30f8e5e098fb1bb8cac2e0945176d13f0f` |
| `tests/operations/test_r5_tcad_debug_ownership.py` | `027e53527c8e8de49832e4ab1035619eeed9c1f66b7f5f798f92a1587c253cb8` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | 第三轮报告所冻结的唯一 attempt 逆序阻塞 |
| S2 | 当前生产 `TCADTaskAttemptAccess.task_for_recovery()` |
| S3 | 当前生产 access 及 reconciler 恢复负例 |
| S4 | 本轮静态检查、编译检查和四项独立串行测试 |

`EvidenceAudit`：

| 物质问题 | 判定 | 证据 |
|---|---|---|
| `attempt_reverse_mapping` | 通过：Task 存在且 attempt 落后时抛通用状态冲突，不返回 `None` | S1—S4 |
| `recovery_retryability` | 通过：冲突沿既有异常路径保持 pending，不 reap、不删除 exchange | S1—S4 |
| `exact_deletion_semantics` | 通过：只有精确 `TaskNotFound` 仍映射为 `None` | S2—S4 |
| `scope_and_occam` | 通过：只改变一个分支和负例，无新实体、表、注册表或状态机 | S1—S4 |

## 3. 阻塞已闭合

生产 access 当前逻辑为：

- `get_task()` 或 `status()` 精确抛 `TaskNotFound`：返回 `None`，允许已删除 Task 的确定性 reap；
- SQLite、Artifact 或其他 TaskService 错误：继续传播；
- `status.attempt < debug attempt`：抛通用 `TaskStateConflict`；
- Task 存在且 attempt 不落后：返回精确 Task，允许 terminal 恢复收集。

因此 attempt 逆序不再进入“任务已删除”的不可逆分支。`TCADDebugService.reconcile()` 的既有宽边界
异常处理会把该次恢复计为 `pending`，保留插件记录和 exchange 供后续调查/重试。已有
`test_task_access_error_stays_retryable_and_keeps_exchange` 证明异常路径不 reap、不删 exchange；新增
生产 access 断言则精确证明 attempt 逆序产生 `TaskStateConflict`。两者共同覆盖第三轮阻塞。

修复没有恢复通用核心的 TCAD 删除钩子，也没有引入专用状态、第二任务权威或插件注册表。

## 4. 独立运行证据

命令严格串行，并设置 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2` 和
`PYTHONDONTWRITEBYTECODE=1`：

```text
pytest -q tests/operations/test_r5_tcad_debug_ownership.py
# 4 passed in 0.17s

python -m py_compile \
  plugins/tcad_artifact/tcad_artifact/runtime_plugin.py \
  tests/operations/test_r5_tcad_debug_ownership.py
# 通过

git diff --check
# 通过
```

本轮没有重复前三轮正常 Worker、安装态或完整 TCAD 测试；当前变化只触及一个错误分类分支，上述
生产 access 与恢复错误负例是能直接推翻该修复的最小可信集合。

## 5. 最终结论

**通过。**

第三轮剩余的 attempt 逆序误删语义已经关闭：状态矛盾会失败关闭并保持恢复现场，只有精确
`TaskNotFound` 才允许按已删除 Task 处理。没有发现新增权威、领域核心分支或复杂度反弹。

因此，本轮**放行 R5-C 的 Root 子环节**；该放行不预先批准 Root 子环节的设计或实现。
