# R5-C Task 与 TCAD 调试归属迁移第三轮独立复审

日期：2026-08-29  
审查对象：第二轮 F2-R2 修订候选  
结论：**打回**  
门禁决定：**不放行 Root 子环节**

## 1. 范围

本轮只核验第二轮唯一剩余阻塞：生产 Task access 是否仅把精确不存在映射为 `None`，其余错误和
状态矛盾是否保持可重试。未重新打开已通过的 F1、正常调试链或 Root 后续工作；未修改生产代码、
测试、计划或阶段状态，唯一写入是本报告。

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/service/tasks.py` | `545b7cc00fb1cf39f7b56e02345461510e9c12f0742131d6e7685f263d7df53e` |
| TCAD 插件 `debug_service.py` | `4172a985adbfc6925e17c4befe45bdd716c35ea5e5a6e1237dc0690a97027997` |
| TCAD 插件 `runtime_plugin.py` | `06b9092c6cb88df64530da6dbd3e57116c7c2a11eca3c9811dbd583d1d5dc857` |
| `test_r5_tcad_debug_ownership.py` | `129f761ee589731d0332dd76caeb47f552d89736750f028968a2b342f4968f91` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | 第二轮独立报告的 F2-R2 与精确最小修复要求 |
| S2 | 当前通用 `TaskNotFound`、TaskService `_row()` 实现 |
| S3 | 当前生产 `TCADTaskAttemptAccess` 与 debug reconciler |
| S4 | 新增 ownership 测试及本轮六项独立聚焦结果 |

`EvidenceAudit`：

| 物质问题 | 判定 | 证据 |
|---|---|---|
| `exact_not_found_mapping` | 通过：TaskService 精确缺失抛 `TaskNotFound`，生产 access 只捕获该类型 | S1—S4 |
| `read_failure_retryability` | 通过：非 `TaskNotFound` 异常传播，reconciler 保持 pending 和 exchange | S1、S3、S4 |
| `attempt_consistency` | **不通过：存在但 attempt 落后的 Task 仍被映射为不存在** | S1、S3、S4 |
| `no_new_authority` | 通过：没有新增表、注册表、TCAD 核心分支或恢复状态机 | S2—S4 |

## 3. 已修复的部分

通用 TaskService 新增了窄的 `TaskNotFound(TaskServiceError)`；`_row()` 只在任务行精确不存在时抛
该类型。生产 `task_for_recovery()` 对 `get_task()` 和 `status()` 只捕获 `TaskNotFound`，SQLite、
Artifact、状态解析及其他运行错误会继续传播。debug reconciler 的既有外层异常处理会保留
`pending`，不写 `reaped`、不删除 exchange。

新增测试也证明：

- 生产 access 把 `TaskNotFound` 映射成 `None`；
- 普通运行错误不会被折叠；
- recovery access 报错时，debug row 保持 terminal 可重试状态，exchange 保留。

这关闭了第二轮报告所列的主要宽泛 `except Exception` 缺陷。

## 4. 剩余阻塞：attempt 逆序仍被当成任务删除

`TCADTaskAttemptAccess.task_for_recovery()` 当前仍包含：

```python
if status.attempt < attempt:
    return None
```

此时 Task 行、不可变 Task Artifact 和状态都存在；只是 Task 权威的 attempt 小于插件 debug row
声明的 attempt。这是跨数据库状态矛盾或损坏，不是精确 `TaskNotFound`。返回 `None` 后，
reconciler 会按“任务已删除”分支永久写 `reaped`、删除 exchange，并丢弃已经 collect 的结果。

因此候选仍未满足第二轮要求“只有 Task 精确缺失才允许 reap；attempt 逆序必须失败关闭”。新增
生产 access 测试只覆盖异常类型，没有构造 `status.attempt < attempt`，六项全绿不能证明该分支。

### 最小修复

1. 将 attempt 逆序改为传播一个已有通用状态冲突异常或普通运行错误；不得返回 `None`。
2. 增加生产 `TCADTaskAttemptAccess` 测试，证明 Task 存在且 attempt 落后时抛错。
3. 增加或扩展 reconciler 负例，证明该矛盾下 debug row 不变为 `reaped`、exchange 不删除、计入
   `pending`。

这是一处分支和一个精确负例，不需要新实体、表、注册表或 TCAD 核心删除钩子。

## 5. 独立运行证据

命令严格串行，并设置 7 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2` 和
`PYTHONDONTWRITEBYTECODE=1`：

```text
pytest -q \
  tests/operations/test_r5_tcad_debug_ownership.py \
  tests/operations/test_tcad_operation_plugin.py::test_registered_tcad_author_debug_and_reviewer_lifecycle \
  tests/operations/test_tcad_operation_plugin.py::test_core_task_service_has_no_tcad_role_or_plugin_import_branch
# 6 passed in 1.34s

python -m py_compile <四个相关生产/测试模块>
# 通过

git diff --check
# 通过
```

## 6. 最终结论

**打回。**

精确 `TaskNotFound` 和普通访问错误已经正确区分，但 Task 存在且 attempt 逆序时仍被错误解释为
“已删除”，可触发不可逆 reap。这是第二轮同一 F2-R2 阻塞尚未完全关闭，不是新范围。

修复上述单一分支并补充负例后再复审；本轮**不放行 Root 子环节**。
