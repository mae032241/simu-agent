# R5-D1 Root 路由职责拆分独立审查

日期：2026-08-29  
审查性质：未参与实现的跨边界、简化性与变更范围审查  
结论：**打回**  
门禁决定：**不放行 D2**

## 1. 审查范围

本轮只审查 D1：`mcp_root.py`、共享辅助、实例/Operation/Task/Approval/Execution 五个路由模块、
冻结和当前计量脚本、结构测试及实施记录。重点核对 35 个真实 Root 工具、唯一依赖容器、MRO 与
导入图、权限/谱系/审批/副作用边界、领域中立性，以及 150 行净增是否被诚实计量。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行。所有命令均在 `ulimit -v 7340032`、
`MALLOC_ARENA_MAX=2`、`PYTHONDONTWRITEBYTECODE=1` 下严格串行运行。本轮未修改生产代码、测试、
计划或状态；唯一写入是本报告。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 8.1 节和 R5-D 复杂度门；SHA-256 `e89a506c36d1011a2ea1126c4721572612af640ca62bc316012cebc29c8926d1`。 |
| S2 | `docs/plans/R5_D_RESPONSIBILITY_SPLIT_IMPLEMENTATION.zh-CN.md`；SHA-256 `aff4d3969ee234dda202704d650cf49b262f974d4394d3923db48eb1e81ddf8f`。 |
| S3 | Root 入口 `mcp_root.py`（`48748f10...`）与共享辅助 `mcp_root_shared.py`（`dcf89456...`）。 |
| S4 | 五个路由：instance（`5f698ea9...`）、operation（`5439753f...`）、task（`0b3d1ce7...`）、approval（`2aff9996...`）、execution（`aad91e7f...`）。 |
| S5 | 冻结生成器 `r5_baseline_metrics.py`（`718eac8e...`）、当前 overlay `r5_current_metrics.py`（`8e3db85f...`）及冻结快照。 |
| S6 | `test_r5_root_route_split.py`（`4731afa2...`）、Root/Operation/Agent/Transform/Effect/审批/安装态现有测试和本轮运行记录。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `route_ownership` | pass | S3, S4, S6 | 35 个 ROOT_TOOLS 各有且只有一个公开路由所有者；Facade MRO 无重名方法覆盖。 |
| `single_dependency_container` | pass | S3, S4, S6 | 五个路由无 `__init__`、服务副本、缓存或注册表；Artifact/Task/Approval/Execution/Binding/Catalog 与创建锁仍只由同一 Facade 实例持有。 |
| `control_boundaries` | pass | S1, S3, S4, S6 | preflight/invoke 共用准入；Task、审批和 Effect 仍调用原权威服务，人工决定、编译身份和执行授权边界未复制。 |
| `domain_neutrality_and_imports` | pass | S3, S4 | 七个 Root 文件没有 TCAD、curve、InGaAs、Fig.4 或设备参数分派；路由只依赖共享模块，不反向导入 Root，导入图无环。 |
| `installed_and_runtime_entry` | pass | S3, S4, S6 | `RootMCPRouter` 仍从同一 `ROOT_TOOLS` 解码并按名称调用 Facade；clean-wheel daemon、真实 Operation 和三类生命周期聚焦测试通过。 |
| `split_occam` | pass | S1—S4 | 3035/2885 的 150 行增量换得五个真实变化原因和一个共享窄面；没有建立 route 对象图、repository/service 模板或额外状态，当前增量可接受。 |
| `frozen_metric_integrity` | pass | S5 | R5-0 生成器哈希未变；当前 overlay 未改写冻结文件或快照。 |
| `current_metric_honesty` | **fail** | S1, S2, S5, S6 | overlay 的职责明细计入七个文件，但第一口径 `r0_core` 仍只计拆分后的 535 行入口，少计 2500 行后继职责；结构测试没有约束这一 headline 总数。 |

## 3. 路由拆分本身通过语义审查

### 3.1 所有权和 MRO

当前路由划分为：实例/清单 12 个工具、Operation 3 个、Task 8 个、Approval 2 个、Execution 10 个，
总计 35 个。独立检查 `RootToolFacade.__mro__` 和所有类字典没有同名方法冲突；路由模块不导入
`mcp_root.py`，只单向依赖 `mcp_root_shared.py`，因此没有循环导入或初始化顺序隐患。

路由采用无状态 mixin，而不是为每类工具新建带依赖的 service/facade 实例。这使所有方法继续使用
同一 `self.artifacts`、`self.tasks`、`self.approvals`、`self.executions`、`self.bindings`、
`self._operation_catalog` 和 `self._create_lock`，符合“拆职责、不拆权威”的目标。实例路由对
`self.instance` 的更新仍是原 Facade 会话选择状态，不是路由私有状态。

### 3.2 权限、谱系、审批和副作用

Operation 路由仍由 `_prepare_operation_call` 同时服务 preflight/invoke；Agent 只调原 TaskService，
Transform 只登记原 Artifact/CAS，Approval 仍由编译 projector 和原 ApprovalService 创建，Effect
仍通过原 ExecutionBridge 和 ExecutionService。Task、Approval、Execution 查询路由没有增加写入
替代面。共享模块只保留纯值、纯函数和冻结常量，没有新的准入注册表。

七个 Root 文件的领域词静态扫描无命中；Operation 路由虽然 1313 行，但其方法共同维护编译调用、
生产者族、输入 cohort、修订父链和确定性输出这一条强内聚边界。D1 再把它拆成更小类会增加跨文件
不变量，当前不应继续追求文件尺寸。

### 3.3 150 行增量判断

Root 职责聚合由 2885 增至 3035 行，增量约 5.2%，主要来自六个新模块的导入、类边界、模块说明、
公开导出和结构门。整体生产 Python 为 60299/62533 行，仍净减少 2234 行；operations 包保持
2056/2060。鉴于拆分对应五个真实调用边界且没有增加运行时对象或决策层，这一增量没有构成复杂度
反噬。后续 D2 不应借 D1 再建立同构 route repository 或依赖注入框架。

## 4. 阻断 F1：当前第一复杂度口径少计拆分后继

`r5_current_metrics.py` 通过修改一次性进程内的 `RESPONSIBILITY_SUCCESSORS`，使：

```text
responsibilities[mcp_root].total_lines = 3035
```

这一职责明细是正确的。但同一次输出中的主口径仍为：

```text
r0_core.r5_0_lines[mcp_root.py] = 535
r0_core.r5_0_total = 7135
```

原因是冻结生成器的 `r0_core` 分支继续按六个旧路径直接求和，不读取 successor overlay。按权威计划
“搬迁后继必须加入同一聚合”的真实当前值应为：

```text
7135 - 535 + 3035 = 9635
```

即 `9635/13657`，仍比 8765 基线减少约 29.4%，所以缺陷不会改变复杂度门的通过方向；但当前 JSON
同时提供一个少计 2500 行的 headline 字段，后续 D2—D5 或总审若读取 `r0_core.r5_0_total`，会把
拆文件误报成额外减重。`test_r5_root_route_split.py` 只断言职责明细内部求和，没有断言第一口径等于
全部后继聚合，因此不能关闭这一风险。

## 5. 精确最小修复

1. 保持 `scripts/r5_baseline_metrics.py` 和 R5-0 冻结快照字节不变。
2. 在 `r5_current_metrics.py` 输出中新增明确的 current-successor 第一口径，或在 overlay 输出内把
   六个 R0 owner 的当前行数替换为各自 successor 总和；不得让 `7135` 继续作为当前聚合总数。
3. 测试必须精确断言 Root owner 为 3035、诚实当前总计为 9635，并证明每个 successor 恰好计一次；
   后续 D2—D5 新后继必须沿用同一聚合算法，而不是分别手写 headline 数字。
4. 实施记录把 D1 当前第一口径写为 `9635/13657`，同时保留 Root 局部 `3035/2885` 和全生产
   `60299/62533`，不改写 R5-0 历史值。
5. 复跑结构/冻结计量专项、上述 15 项真实 Root/生命周期/clean-wheel 聚焦测试和 `git diff --check`；
   不需要重写路由实现或无理由重跑真实 solver。

## 6. 独立运行记录

本轮实际执行：

```text
pytest -q \
  tests/operations/test_r5_root_route_split.py \
  tests/operations/test_operation_invoke_installed.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_transform_lifecycle.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_plugin_discovery.py::test_core_clean_wheel_runs_runtime_cli_and_both_daemon_entries
# 15 passed in 30.85s

PYTHONPATH=src python -m py_compile <七个 Root 模块>
# 通过

git diff --check
# 通过
```

已有实现记录的 42 项聚焦和 274 项全仓结果与本轮语义检查一致；因 F1 已足以阻断 D1，本轮没有为
重复数字再次运行全仓。未运行浏览器点击或真实 solver，因为拆分没有改变 UI 决定写入或外部 adapter。

## 7. 最终结论

Root 路由拆分的运行结构、35 工具所有权、控制边界、领域中立性和 150 行增量本身均可接受；没有
发现行为、MRO、循环依赖、权限或生命周期阻断。唯一阻断是当前复杂度 overlay 没有把拆分后继写入
权威第一口径，违反 D1 明确的防搬移要求。

**结论：打回。不放行 D2。**

完成第 5 节的计量最小修复并独立复审通过后，才可只放行 D2；不应借此返工已经通过的路由拆分。
