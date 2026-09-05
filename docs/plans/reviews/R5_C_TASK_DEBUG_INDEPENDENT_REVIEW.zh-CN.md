# R5-C TaskService 去领域化与 TCAD 调试归属迁移独立审查

日期：2026-08-29  
审查对象：当前共享工作树中 R5-C 第一关键环节候选  
结论：**打回**

## 1. 审查范围

本轮未参与实现，只读追踪了通用 TaskService、任务/临时快照结构、TCAD 插件调试服务、运行时
装配、独立调试数据库、任务删除门和恢复路径。审查遵循 `scid-cross-boundary-review`、
`scid-find-simplifications` 和 `scid-change-scope-checks`。没有修改生产代码、测试、计划或阶段
状态，唯一写入是本报告。

关键精确字节：

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/service/tasks.py` | `21512945217a1ea6a7f08289bea8aec232e062717dd215e47a80be1401167e4e` |
| `src/scidiscovery/artifact_agent/schema/task.py` | `52e31d96a7f10c9b484ac521ad84dff54bb3532d30cbf6c44e3246a3b721cd38` |
| `src/scidiscovery/artifact_agent/schema/provisional.py` | `189c3807a5ca73ec91c425dff954f9766c617b80863c11b39dd03302f600e288` |
| TCAD 插件 `debug_service.py` | `a12fbba98c140f5181372af4b84a0bed67b4d5c73f31c43a14018258a3156bd6` |
| TCAD 插件 `runtime_plugin.py` | `a9345c7e16f83799cb96bbffbeee7ec3ffd91a13f7c00846698fa4bc2f0bead8` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 7.1 节及当前架构边界 |
| S2 | 当前通用 TaskService、task/provisional Schema 的上述精确字节 |
| S3 | 当前 TCAD `debug_service.py`、`runtime_plugin.py`、调试 adapter 和插件声明 |
| S4 | `baseline/8765-codex` 中原 `tcad_debug.py` 与原 TaskService 删除/数据库实现 |
| S5 | 当前 TCAD、运行时插件、安装态调试测试及本轮独立串行结果 |

`EvidenceAudit`：

| 物质问题 | 判定 | 证据 |
|---|---|---|
| `core_domain_removal` | **不通过：核心仍声明并存储 TCAD 专用调试快照原因** | S1、S2、S5 |
| `plugin_behavior_preservation` | **不通过：inactive/已删 task 的恢复会永久停在 pending** | S3、S4 |
| `narrow_service_interface` | 通过：调试服务只持有 Protocol，生产装配传入 `TCADTaskAttemptAccess` | S1、S3、S5 |
| `database_ownership` | 部分通过：新写入只在插件数据库，但删除/恢复闭环没有闭合 | S2—S4 |
| `active_task_gate` | 部分通过：claimed task 的通用删除门仍在，terminal debug 竞态失去保护 | S2—S4 |
| `tests_and_occam` | 不通过：现有静态门漏检真实领域残留，恢复/删除负例缺失 | S1—S5 |

## 3. 阻塞问题

### F1：通用核心仍保留 TCAD 调试活动语义

R5-C 的明确完成边界要求通用核心不再拥有 TCAD debug 实现、表、活动名和领域删除分支。当前已经
正确删除 `tcad_debug_leases/runs` 的建表、领域删除分支和旧调试服务 import，但以下专用语义仍在
核心：

- `TaskService.store_development_debug_snapshot()`；
- 该方法固定写入 `reason="development_debug_result"`；
- `AssignmentProvisionalContext.reason` 固定列举 `development_debug_candidate/result`；
- `ProvisionalSnapshotManifest.reason` 固定列举同样两个领域值。

TCAD 插件的 `TCADTaskAttemptAccess.validated_candidate()` 和 `store_debug_outputs()` 又直接依赖这些
核心专用值/方法。因此这不是无消费者的历史文字，而是仍在运行的领域纵切面。通用 TaskService
仍然知道“开发调试候选/结果”的 TCAD 工作模型，没有完成第 7.1 节要求的所有权迁移。

现有 `test_core_task_service_has_no_tcad_role_or_plugin_import_branch()` 只检查
`tcad_deck_author`、`tcad_deck_reviewer` 和一个 import 字符串；它在上述四处残留存在时仍通过，不能
作为本门的静态证据。

最小修复要求：

1. 删除 `store_development_debug_snapshot()`；由一个已有或最小的通用临时快照写入接口接收通用
   工具候选/工具结果原因、控制生成文件和 `development_only`，不识别 TCAD、debug mode 或领域
   输出名。
2. 将 task/provisional Schema 中两个 TCAD 专用 reason 改为真正通用且有界的 Operation 工具临时
   结果语义；不要改成任意自由字符串，也不要新建插件 reason 注册表。
3. 增加精确静态门，扫描 `src/scidiscovery` 中的
   `development_debug`、`tcad_debug`、`TCADDebug` 及专用方法，而不只检查旧角色名/import。

### F2：独立数据库迁移破坏 terminal/missing task 的恢复关闭

原实现把 debug 表和 Task 表放在同一数据库，并在 `delete_tasks()` 前调用
`active_development_debug_tasks()`；即使 Task 已经 failed/timed_out，只要其 debug run 未
`collected/reaped`，删除仍失败关闭。当前候选正确移除了这条领域删除分支并把两个表归入插件独立
数据库，但没有在插件侧闭合由此产生的生命周期变化。

可达路径为：

1. claimed author task 已提交外部 debug，插件库的 run 处于 running/submitting；
2. Task 超时、失败或被控制面关闭，变为 terminal；
3. 通用 `delete_tasks()` 只拒绝 `dispatched/claimed/finalizing`，因此该 terminal Task 可以被删；
4. 插件 `reconcile()` 看到 `attempt_is_active=False`，可尝试 cancel 并得到 terminal adapter state；
5. 随后无条件调用 `task_for_attempt()`；`TCADTaskAttemptAccess.task_for_attempt()` 先要求 active
   claim，必然抛错；外层宽泛 `except Exception` 把它记为 `pending`；
6. 下轮仍重复同一路径，run 永远不能 `collected/reaped`，交换目录也不会清理。

即使 Task 尚未物理删除而只是 timed_out，步骤 5 也成立。该行为弱于原恢复语义，并会把私有外部
绑定和本地交换目录留在永久重试状态。独立数据库本身没有双写，但它与 Task 权威之间失去了可
关闭的删除/恢复关系。

最小修复要求：

1. 不恢复通用核心中的 TCAD 删除特判，也不新增调试注册表或第二状态机。
2. 窄接口应区分“Worker 主动调用必须 active”和“reconciler 读取精确 terminal attempt”；仍存在
   的 terminal Task 应能按原语义收集并封存，不能复用要求 active claim 的入口。
3. Task 已删除/不可读时，插件必须在确定外部绑定已经 terminal/cancelled 后确定性转为
   `reaped` 并清理交换目录；不能永久 `pending`。不确定提交仍必须保持可重试，不能伪造关闭。
4. 增加两个真实负例：terminal 但仍存在的 Task 能完成恢复收集；Task 已删时外部运行被取消/确认
   terminal 后可 reap。另保留 claimed Task 经通用 `delete_tasks()` 被拒绝的正向安全门。

## 4. 已正确实现的部分

- 通用核心已没有 `tcad_debug_leases/runs` 建表语句、旧 `TCADDebugService` 实现、
  `active_development_debug_tasks()` 或按领域删除表的分支。
- 插件 `TCADDebugService.__init__()` 的 `tasks` 类型是 `TCADDebugTaskAccess`；服务代码只调用该
  Protocol 的任务局部方法，没有持有 Root、Artifact registry 或跨任务扫描接口。
- 生产 `build_runtime()` 只在 worker 模式用可信 TaskService 构造 `TCADTaskAttemptAccess`，再把
  适配器交给调试服务；control 模式只贡献执行 adapter。
- 权限检查从固定 role 改为当前编译 Operation 的 worker capability/tool 验证；reviewer 无工具、
  rogue runtime 不能满足组件限定 service identity。
- 调试 run/lease 当前只写插件自有 `tcad-debug.sqlite3`，旧 Task 数据库没有继续双写这些表。
- 运行、限额、preflight/smoke/initialization、提交前重验证、未知提交恢复、输出大小限制和
  claim 不可采信标记的大部分原逻辑是从旧服务等价迁移，而不是重写 TCAD 物理算法。

这些优点说明迁移方向正确；F1/F2 都可在当前窄边界内修复，不需要推翻插件运行时设计。

## 5. 测试与复核证据

所有命令严格串行，并设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
pytest -q \
  tests/operations/test_tcad_operation_plugin.py::test_registered_tcad_author_debug_and_reviewer_lifecycle \
  tests/operations/test_tcad_operation_plugin.py::test_core_task_service_has_no_tcad_role_or_plugin_import_branch \
  tests/operations/test_runtime_plugin_configuration.py::test_runtime_plugin_config_is_startup_only_and_shared_by_control_and_worker \
  tests/operations/test_runtime_plugin_configuration.py::test_rogue_runtime_plugin_cannot_satisfy_tcad_runtime_bindings \
  tests/operations/test_runtime_plugin_configuration.py::test_generic_daemons_have_no_tcad_runtime_switches_or_imports
# 5 passed in 1.62s

pytest -q \
  tests/operations/test_tcad_operation_plugin.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_baseline_tcad_debug.py
# 19 passed in 29.50s

python -m py_compile \
  plugins/tcad_artifact/tcad_artifact/debug_service.py \
  plugins/tcad_artifact/tcad_artifact/runtime_plugin.py \
  src/scidiscovery/artifact_agent/service/tasks.py
# 通过

git diff --check
# 通过
```

这些通过项证明正常调试闭环、工具作用域、插件运行时装配和安装态入口没有明显退化，但没有测试
F1 的专用活动名，也没有覆盖 inactive/missing Task 的 reconcile 路径。当前已有可达生命周期
阻塞，重复全仓测试不会改变门禁结论，因此本轮未运行全仓。

## 6. 最终结论

**打回。**

候选已经把 TCAD 调试实现和数据库主体迁入插件，并用窄 Protocol/适配器隔离完整 TaskService；
但通用核心仍拥有 TCAD 专用临时快照活动语义，且独立数据库迁移使 terminal/已删 Task 的调试
恢复永久停在 pending。两项都直接违反本关键环节的去领域化与失败关闭完成门。

修复 F1、F2 并增加上述精确负例后，应由未参与修复的独立审查者复审；本轮不放行 R5-C 下一关键
环节。
