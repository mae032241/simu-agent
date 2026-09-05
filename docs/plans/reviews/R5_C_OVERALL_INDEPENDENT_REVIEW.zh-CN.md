# R5-C 总体完成门独立审查

日期：2026-08-29  
审查性质：未参与实现的组合跨边界、简化性与变更范围审查  
结论：**打回**  
门禁决定：**不放行 R5-D**

## 1. 审查边界

本轮不是重复批准三个已通过子环节，而是核对它们组合后是否满足
`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 的完整 R5-C 完成门。审查覆盖：Task 与
TCAD debug 所有权、Root inventory/current/preflight/invoke、静态拓扑和上下文删除、R5-B 盲插件、
core-only 加载隔离、权限/来源/审批/执行/恢复负例，以及单一 Operation 权威和复杂度目标。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行。所有命令均在 `ulimit -v 7340032`、
`MALLOC_ARENA_MAX=2`、`PYTHONDONTWRITEBYTECODE=1` 下严格串行运行。本轮未修改生产代码、测试、
计划或状态，唯一写入是本报告。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 7 节、R5-C 完成门及第 14 节；SHA-256 `e89a506c36d1011a2ea1126c4721572612af640ca62bc316012cebc29c8926d1`。 |
| S2 | 当前通用控制路径：`mcp_root.py`（`7facd5a5...`）、`service/tasks.py`（`545b7cc0...`）、`operations/catalog.py`（`4e5a5de7...`）、`operations/invoke.py`（`0a544299...`）。 |
| S3 | 当前 TCAD 插件调试路径：`debug_service.py`（`4172a985...`）、`runtime_plugin.py`（`073bb64b...`）及 `test_r5_tcad_debug_ownership.py`（`027e5352...`）。 |
| S4 | 当前调度模型可见路径：`roles/scheduler.md`（`44dec3f7...`）、`AGENTS.md`（`85cd0182...`）、`platforms/scheduler_prompt.py`（`55a002c3...`）及已删除拓扑/context 文件状态。 |
| S5 | R5-B 未知盲插件及组合准入证据：`test_r5_blind_producer_family.py`（`a753f64d...`）、`test_invoke_preflight.py`（`dde5da26...`）、`test_r4_approval_operation.py`（`8163f71b...`）。 |
| S6 | core-only 安装门：`test_baseline_plugin_discovery.py`（`43561180...`）、`test_catalog_installed_entrypoint.py` 及本轮对当前 clean-wheel core 虚拟环境运行的 `compile_installed_catalog()`/`sys.modules` 探针。 |
| S7 | 当前 generic core 科学合同：`general_science_plugin.py`（`781b423c...`）、`schema/layered_diagnosis.py`（`81ca845d...`）、`research_cycle.py`（`2af46d66...`）、`study_execution.py`（`740b0a4e...`）、`experiment_intent.py`（`ccb8b859...`）。 |
| S8 | 本轮测试记录：两组组合聚焦测试共 47 项通过；紧邻本轮且候选生产字节未再变化的严格串行全仓回归为 `268 passed in 89.79s`。 |

摘要中的省略号只缩写已在本节给出文件归属的摘要显示，不作为独立定位符；阻断文件的完整摘要已在
S1、S6、S7 或本报告命令记录中给出。

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `task_debug_ownership` | pass | S2, S3, S8 | TaskService 不再持有 TCAD debug 表或实现；插件通过窄 access 使用 Task 权威，恢复错误分类、attempt 逆序和任务删除路径失败关闭。 |
| `root_inventory_and_admission` | pass | S1, S2, S5, S8 | inventory 只投影同一 public catalog；current 与 exact Operation 的 claim-evidence 准入共享 `_claim_admissible`；preflight/invoke 共享 `_prepare_operation_call`。 |
| `topology_context_retirement` | pass | S1, S4, S8 | 静态 topology 与三个 context policy 文件已删除，调度提示不含固定领域 Operation、端口或阶段 DAG，模型可见旧权威无检出。 |
| `blind_plugin_composition` | pass | S2, S4, S5, S8 | 同一 R5-B 未知插件的 Agent/Transform/Approval 正负例在组合候选继续通过，无 Root、Task、Scheduler、UI 或产品安装器分派。 |
| `core_only_runtime_isolation` | **fail** | S1, S6, S7 | clean-wheel core 编译目录后仍加载两个 `scidiscovery.*.curve_*` 模块；现有测试只排除三个顶层插件包，未证明权威门要求的无 curve 模块。 |
| `generic_core_domain_neutrality` | **fail** | S1, S7 | generic core 仍直接装配 TCAD 专用诊断校验，Schema 含 `tcad_project`/`tcad.*` 精确引用，并在实验意图中固定曲线评分 Operation profile。 |
| `permission_provenance_lifecycle` | pass | S2, S3, S5, S8 | Worker 最小上下文、精确来源、独立审批、Effect 授权、恢复与失败负例未见组合回归。 |
| `single_authority_and_occam` | revise | S1—S8 | 行动发现、创建和生命周期仍为单一权威且旧表净删除；但两项领域归属残留使 R5-C 轻量插件边界尚未完成，不能据子环节通过推导总体通过。 |

## 3. 唯一阻断族 F1：core-only 加载与 generic core 领域归属未闭合

### F1-a：启动导入阻断

权威完成门要求 core-only 进程的 `sys.modules` 无 TCAD、curve、InGaAs，并在总门再次要求
core-only 启动不导入领域包。现有安装测试仅断言不存在顶层包
`tcad_artifact`、`curve_score`、`ingaas_fig4`；它没有检查 `scidiscovery` 包内被 core 入口点提前
导入的曲线模块。

本轮对聚焦测试遗留的当前 clean-wheel core 环境独立执行：

```text
from scidiscovery.operations.catalog import compile_installed_catalog
compile_installed_catalog()
# 筛选 sys.modules 中名称含 tcad / curve / ingaas

[
  "scidiscovery.artifact_agent.schema.curve_analysis",
  "scidiscovery.artifact_agent.schema.curve_score"
]
```

探针同时断言 `scidiscovery.__file__` 位于该虚拟环境前缀内，未使用源码 `PYTHONPATH`。因此这是安装态
core 的真实加载结果，不是源码树污染。直接原因是 `general_science_plugin.py` 顶层导入曲线 Schema
和 validator，并在 core catalog 中声明 `science.result.diagnose.curve-error.v1` 及曲线绑定的通用
diagnosis。

### F1-b：核心 Schema 本身领域化阻断

该问题独立于模块名字。当前 generic core 仍存在以下确定性领域合同：

- `general_science_plugin.py:52,138` 直接导入并调用
  `validate_tcad_diagnosis_task_output`；
- `schema/research_cycle.py:160` 的通用 `ArtifactKind` 固定包含 `tcad_project`；
- `schema/study_execution.py:54-58` 固定接受 `tcad.deck-review-*` 与
  `tcad.solver-capability.v2`；
- `schema/experiment_intent.py:801` 固定写入
  `evaluator_profile="scidiscovery.curve-score.v1"`。

这些不是未来第二领域才要求的增强，而是当前 R5-C 完成门明确禁止的 generic core 领域 Schema 或
插件 Operation id 绑定。因此，即使通过延迟导入让 `sys.modules` 探针变绿，F1-b 仍不会自动闭合。

## 4. 精确最小修复边界

为避免把 R5-C 扩大成“迁走所有曲线数据模型”，本报告冻结以下边界：

1. **必须修复启动装配。** 将曲线专用 Agent Operation、曲线上下文 validator 与绘图 collection
   validator 从 core 的 `general_science_plugin` 迁到现有 `curve_score` 插件，或作等价的插件自有
   装配；core-only 编译 catalog 后不得加载 TCAD/curve/InGaAs 模块。仅增加更窄的前缀测试或延迟
   一个 import、同时保留 core catalog 的曲线专用行动，不足以关闭此项。
2. **必须移除 generic core 的 TCAD/插件分派。** `tcad_project`、精确 `tcad.*` Schema 引用、
   `validate_tcad_*` 装配和固定 `scidiscovery.curve-score.v1` 应迁到插件合同，或改为由编译端口/
   显式 evaluator 声明传入的领域无关合同；不得新增第二注册表、Operation 名 switch 或兼容 facade。
3. **不要求迁走全部通用曲线科学对象。** 纯数据型、没有插件 Operation id、TCAD 条件或领域分派的
   `CurveBundle`/坐标轴/序列 Schema 可以继续作为 core 中的共享库合同；但 core-only 正常启动与
   catalog 编译不得自动导入它们。安装曲线插件后由该插件显式使用这些共享类型是允许的。
4. **重测完成门。** clean-wheel core 探针应在 `compile_installed_catalog()`、`open_runtime`、control
   daemon 和 Worker daemon 四条入口后检查实际 `sys.modules`；另以静态门拒绝 generic core 中上述
   TCAD Schema、固定 scorer Operation id 和 TCAD validator 装配。随后复跑本轮 47 项组合矩阵及全仓
   串行回归。

该修复边界复用现有 curve/TCAD 插件和单一 `scidiscovery.plugins` 入口，不需要新增数据库表、状态机、
插件注册表或科学实体。

## 5. 独立运行记录

本轮严格串行运行：

```text
# core install/daemon、R5-B 盲插件、TCAD debug 所有权
pytest -q <5 个聚焦选择>
# 17 passed in 29.44s

# Worker 权限、Agent 合同、Approval/Execution、runtime 配置、资格来源
pytest -q \
  tests/operations/test_baseline_worker_authority.py \
  tests/operations/test_r3_agent_contract.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_live_qualification_evidence.py
# 30 passed in 29.74s

# 当前 clean-wheel core，编译已安装目录后检查 sys.modules
# 返回 curve_analysis、curve_score 两个 scidiscovery 内部模块
```

紧邻本轮的 R5-C topology/context 候选已在相同限制下执行严格串行全仓回归：
`268 passed in 89.79s`。此后生产候选字节未变化；本轮只新增审查报告，因此没有重复全仓测试。测试全绿
不能覆盖 F1，因为现有 core-only 断言的前缀范围比权威完成门窄。

## 6. 最终结论

三个 R5-C 子环节在各自边界内仍然成立，组合测试也没有发现 Task、Root、Worker、Approval、
Execution 或恢复回归。但 R5-C 的 core-only 加载隔离和 generic core 领域中立性两项明文完成门尚未
满足。

**结论：打回。不得放行 R5-D。**

修复 F1-a/F1-b 并通过第 4 节冻结的最小重测后，应重新执行 R5-C 总体完成门独立审查；此前的子环节
通过不需要无理由重开，也不能被当作总体批准。
