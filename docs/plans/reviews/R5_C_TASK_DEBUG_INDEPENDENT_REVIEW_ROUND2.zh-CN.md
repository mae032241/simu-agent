# R5-C Task 与 TCAD 调试归属迁移第二轮独立复审

日期：2026-08-29  
审查对象：首轮 F1/F2 修订候选  
结论：**打回**  
门禁决定：**不放行 Root 子环节**

## 1. 范围与精确对象

本轮未参与修复，只重新核验首轮报告的 F1/F2、两个新增恢复负例及修复是否引入新的失败关闭
旁路。仍按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行。没有修改生产代码、测试、计划或阶段状态，唯一写入是本报告。

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/service/tasks.py` | `545b7cc00fb1cf39f7b56e02345461510e9c12f0742131d6e7685f263d7df53e` |
| `src/scidiscovery/artifact_agent/schema/task.py` | `5baf014eb361e8a4d42968d5fbf21c76bbcd2965b957c7288e91ec66fe9ce5a2` |
| `src/scidiscovery/artifact_agent/schema/provisional.py` | `f9ed2663ac75cf3f440772c87be9865f76115583fa50dc9c6931a50813ad7fec` |
| TCAD 插件 `debug_service.py` | `4172a985adbfc6925e17c4befe45bdd716c35ea5e5a6e1237dc0690a97027997` |
| TCAD 插件 `runtime_plugin.py` | `06b9092c6cb88df64530da6dbd3e57116c7c2a11eca3c9811dbd583d1d5dc857` |
| `test_r5_tcad_debug_ownership.py` | `9ac52305e483cafb48a9cba2789dc58249dc89d6bbe7622ccd8e3fb8067c49d5` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | R5-C 第 7.1 节与首轮独立报告的 F1/F2 |
| S2 | 当前通用 TaskService、task/provisional Schema 精确字节 |
| S3 | 当前 TCAD debug service、生产 `TCADTaskAttemptAccess` 精确字节 |
| S4 | 新增恢复负例及既有 TCAD/运行时/安装态测试 |
| S5 | 本轮静态扫描、语义追踪和独立串行测试 |

`EvidenceAudit`：

| 物质问题 | 判定 | 证据 |
|---|---|---|
| `F1_core_reason_removal` | 通过：核心只保留有界通用 Operation 工具候选/结果语义 | S1、S2、S5 |
| `F2_terminal_task_recovery` | 通过：inactive 但可读 Task 可 cancel、collect、封存和清理 | S1、S3—S5 |
| `F2_deleted_task_reaping` | 部分通过：精确缺失路径可 reap，但生产适配器不能证明“精确缺失” | S1、S3—S5 |
| `recovery_fail_closed` | **不通过：任意任务访问异常都会被解释为已删除并触发不可逆回收** | S1、S3、S4 |
| `authority_and_occam` | 部分通过：无新注册表/状态机，但错误折叠破坏单一 Task 权威 | S1—S5 |

## 3. F1 已闭合

通用 `src/scidiscovery` 已无 `development_debug`、`tcad_debug`、`TCADDebug` 或
`store_development_debug_snapshot` 命中。原专用语义已经收敛为：

- `operation_tool_candidate`；
- `operation_tool_result`；
- `TaskService.store_operation_tool_snapshot()`。

这些值是有界 Literal，不是任意插件字符串；接口只封存控制生成的临时 Operation 工具结果，
不解释 TCAD、solver、mode、run name 或领域输出。TCAD 插件适配器负责把领域文件映射成通用
`_WorkspaceSnapshotFile`，通用 TaskService 不再决定领域内容。静态门也已扩展到专用 reason 和
method。本轮认定首轮 F1 关闭，没有发现为此新增 reason 注册表或第二快照状态机。

## 4. F2 的主路径已修复，但失败关闭仍有阻塞

`TCADDebugService.reconcile()` 现在正确区分：

- active attempt：按原状态查询；
- inactive 但 Task 仍存在：cancel/确认 terminal 后 collect，通过通用临时快照封存，再记录
  `collected` 并清理 exchange；
- Task 已删除：仍先 collect/确认外部 terminal，然后记录 `reaped`、清理 exchange，且不重建
  Task/Artifact 控制对象；
- adapter 状态、cancel 或 collect 不确定：保留可重试记录为 `pending`。

新增两个测试可以证明 debug service 在 fake access 明确返回“可恢复对象”或 `None` 时的这两个
分支，首轮“必经 active `task_for_attempt()` 导致永久 pending”的错误已删除。

### F2-R2（阻塞）：生产适配器把任何读取失败当成“Task 已删除”

位置：`tcad_artifact/runtime_plugin.py` 的 `TCADTaskAttemptAccess.task_for_recovery()`。

当前代码把 `get_task()` 和 `status()` 包在：

```python
try:
    ...
except Exception:
    return None
```

而 debug service 把 `None` 解释为“Task 被有意删除”，随后永久写 `reaped` 并删除 exchange。于是
以下并非删除的情况也进入不可逆回收：

- SQLite 暂时锁定、I/O 或数据库损坏；
- Task row 存在但其不可变 Task Artifact 读取/校验失败；
- `status()` 解析 scheduler signal 或依赖状态失败；
- 其他 TaskService 实现缺陷。

此外，`status.attempt < debug_row.attempt` 当前也返回 `None`。这表示 Task 权威与插件记录矛盾，
不是“Task 已删除”，同样应失败关闭而不能丢弃现场。

可达后果是：外部 run 已 terminal、`collect()` 已成功，本次恰逢 Task 读取故障；适配器返回 `None`，
reconciler 把真实存在的任务误判为删除，丢弃收集结果、删除唯一 exchange，并将插件记录永久
reap。后续恢复机会消失，违反不确定外部副作用和精确 Task 权威的失败关闭约束。

新增测试没有覆盖这个生产边界：`_RecoveryAccess(recoverable=False)` 直接返回 `None`，没有经过
`TCADTaskAttemptAccess`，因而既不能证明真实 Task 删除识别，也不能阻止上述异常折叠。

#### 精确最小修复

1. `task_for_recovery()` 只能把“精确 Task 不存在”映射成 `None`。为通用 TaskService 提供专用
   `TaskNotFound` 或等价原子 `get_task_if_present` 语义；不要比较错误消息，不要先 exists 再 get
   形成竞态，也不要恢复 TCAD 删除分支。
2. SQLite、Artifact、状态解析和其他 TaskService 错误必须传播给 reconciler；现有外层捕获会让
   该 run 保持 `pending`，下轮可重试。
3. `status.attempt < debug attempt` 必须作为不一致失败关闭；只有 Task 精确缺失才允许 reap。
4. 增加生产 `TCADTaskAttemptAccess` 负例：
   - 精确缺失返回 `None`；
   - 非 not-found 异常传播，debug row 不变为 `reaped`、exchange 不删除；
   - attempt 逆序不 reap。

这只需要区分“缺失”和“读取失败”，不需要新表、注册表、回调系统或 TCAD 核心分支。

## 5. 已保持的边界

- debug service 仍只持有 `TCADDebugTaskAccess`，生产只传入插件自有
  `TCADTaskAttemptAccess`；Root/Artifact registry/跨任务扫描没有暴露给服务。
- worker 主动调试仍经 active claim 与编译 Operation capability/tool 验证；recovery 读取接口不
  能被 Worker 调用。
- debug lease/run 只写插件数据库；通用 Task 数据库未恢复双写或领域删除表。
- Task 活动状态的删除保护仍由通用 `dispatched/claimed/finalizing` 门承担。
- F1/F2 修复没有引入新的持久实体、注册表、Operation 分派、状态机或 TCAD 物理算法。

## 6. 独立运行证据

所有命令严格串行并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
pytest -q \
  tests/operations/test_r5_tcad_debug_ownership.py \
  tests/operations/test_tcad_operation_plugin.py::test_registered_tcad_author_debug_and_reviewer_lifecycle \
  tests/operations/test_tcad_operation_plugin.py::test_core_task_service_has_no_tcad_role_or_plugin_import_branch
# 4 passed in 1.30s

pytest -q \
  tests/operations/test_r5_tcad_debug_ownership.py \
  tests/operations/test_tcad_operation_plugin.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_baseline_tcad_debug.py
# 21 passed in 29.46s

python -m py_compile <本轮四个相关生产/测试模块>
# 通过

git diff --check
# 通过
```

实现方声称的 23 项没有被继承为批准；本轮选择的 21 项覆盖同一拥有者文件、正常 Worker 调试、
运行时装配及安装态入口。它们全绿，但语义检查直接发现生产 adapter 的异常折叠，重复全仓测试
不能改变该门禁结论。

## 7. 最终结论

**打回。**

首轮 F1 已闭合，F2 的正常 terminal/删除恢复分支也已修复；但生产
`TCADTaskAttemptAccess.task_for_recovery()` 仍把任何任务访问异常和状态矛盾等同于“Task 已
删除”，使 reconciler 可能不可逆丢弃仍有控制权威的调试结果。这是同一 F2 边界上的失败关闭
阻塞。

修复 F2-R2 并增加生产适配器精确负例后再独立复审；本轮**不放行 Root 子环节**。
