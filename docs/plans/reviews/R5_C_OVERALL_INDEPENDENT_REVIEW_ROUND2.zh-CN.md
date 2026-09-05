# R5-C 总体完成门第二轮独立审查

日期：2026-08-29  
审查性质：未参与修复的组合跨边界、插件边界、简化性与变更范围审查  
结论：**打回**  
门禁决定：**不放行 R5-D**

## 1. 审查边界

本轮重新审查当前完整候选，不继承首轮结论。重点核验首轮唯一阻断 F1、组合后的
Task/Root/Worker/Approval/Execution 边界、R5-B 未知盲插件、单一编译目录、插件所有权和复杂度。
审查按 `scid-cross-boundary-review`、`scid-find-simplifications`、
`scid-change-scope-checks` 执行；命令均在 `ulimit -v 7340032`、
`MALLOC_ARENA_MAX=2`、`PYTHONDONTWRITEBYTECODE=1` 下严格串行运行。

本轮没有修改生产代码、测试、计划或状态；唯一写入是本报告。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 的不可退化约束、R5-C 完成门和 R5 总门；SHA-256 `e89a506c36d1011a2ea1126c4721572612af640ca62bc316012cebc29c8926d1`。 |
| S2 | 首轮报告 `R5_C_OVERALL_INDEPENDENT_REVIEW.zh-CN.md`，仅用于定位待修 F1；SHA-256 `d18dea74f9c33b2d0a0ae84a193c3203429f16dbe1250633b5e71464e31abdee`。 |
| S3 | 通用与曲线插件声明：`general_science_plugin.py`（`2f94a0d3...`）、`curve_score/science_operations.py`（`82d4e976...`）、`curve_score/plugin.py`（`b7590371...`）。 |
| S4 | Worker 与生命周期实现：`mcp_worker.py`（`6ed6cfdf...`）、`service/tasks.py`（`851a2e84...`）、`layered_diagnosis.py`（`e49cabc9...`）、`research_cycle.py`（`4c758c4b...`）、`experiment_intent.py`（`4105a380...`）。 |
| S5 | 单目录编译器与插件协议：`operations/catalog.py`、`operations/spec.py`，以及 `test_catalog_negative_cases.py`（`719f7e4f...`）。 |
| S6 | 安装态与真实路由测试：`test_catalog_installed_entrypoint.py`（`847d81d2...`）、`test_baseline_plugin_discovery.py`（`9b5426dd...`）、`test_curve_score_operation_plugin.py`（`b32bbd5b...`）、`test_general_science_plugin.py`（`94e6145b...`）。 |
| S7 | 组合边界测试：`test_r5_blind_producer_family.py`（`a753f64d...`）、`test_r5_tcad_debug_ownership.py`（`027e5352...`）、`test_invoke_preflight.py`（`dde5da26...`）、`test_baseline_worker_authority.py`（`e4935ed6...`）、`test_r4_approval_operation.py`（`c1204ed5...`）。 |
| S8 | 结构脚本与冻结快照：`r5_baseline_metrics.py`（`718eac8e...`）、`r5_structure_inventory.json`（`1b397e2d...`），以及本轮当前字节输出。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `prior_f1_core_isolation` | pass | S1—S4, S6 | core-only 编译和四类启动入口不再加载名称含 TCAD、curve、InGaAs 的模块；通用插件目录为 17 项，未装配曲线 Agent、TCAD validator 或固定 scorer。 |
| `curve_operation_ownership` | pass | S1, S3, S6 | 迁出的实验、复审和诊断合同在提示、Schema 与端口上明确绑定曲线，归现有 `curve_score` 插件是诚实所有权，不是按名称伪装的通用 core 行为。 |
| `figure_evidence_boundary` | pass | S1, S3, S4, S6 | `curve_tables` 是定量论文图逐序列证据附件；`render_curve_support.py` 只在受限分析沙箱绘制观测支持，不评分、不选择候选、不含 TCAD/Operation 分派。 |
| `worker_tool_and_lifecycle` | pass | S3, S4, S6, S7 | `worker_curve_analyze` 由编译 Operation 精确工具闭包提供，真实路由覆盖 invoke→Task→WorkerMCPRouter→输出；核心 Worker 无固定曲线分派，最小能力、审批和生命周期未退化。 |
| `single_catalog_and_blind_plugin` | pass | S1, S5—S7 | 行动发现/创建仍经一个目录和 `operation_invoke`；R5-B 盲插件在组合候选中不要求 Root、Task、Scheduler、UI 或安装器新增分支。 |
| `plugin_component_ownership` | **fail** | S1, S3, S5 | 曲线插件绕过编译器已有的跨插件公开组件门，将另一插件的私有实现路径重新声明成自己的本地组件，并直接依赖另一声明模块的私有 Python 符号。 |
| `complexity_and_occam` | revise | S1, S3, S8 | 三重结构口径均改善且未新增注册表/状态机，但 1015 行曲线科学声明同时复制/借用另一插件私有声明面，尚未达到包级低耦合注册边界。 |
| `regression_evidence` | pass | S6—S8 | 本轮两组聚焦测试为 17 项和 63 项通过；严格串行全仓为 269 项通过；`git diff --check` 通过。 |

## 3. 首轮 F1 已真实关闭

### 3.1 core-only 与 generic core

对 clean-wheel 安装态分别检查 core 与 full：core 只发现 `builtin`、`general_science`，目录 17 项；
在编译目录、`open_runtime`、`scid init codex`、control daemon 和 Worker daemon 入口后，
`sys.modules` 中没有名称含 `tcad`、`curve` 或 `ingaas` 的模块。full 发现四个预期插件和 51 项
Operation，曲线行动与工具只随 `curve_score` 出现。

静态检查确认通用插件不再导入曲线评分/分析、实验意图、分层诊断或 TCAD validator；Task 与
通用 Worker 也不再按曲线 reason code 或 `worker_curve_analyze` 写固定分支。剩余 core 中的曲线
Schema 是未被 core 启动自动导入的共享数据合同，不包含 TCAD、插件 Operation id 或调度决策，符合
首轮冻结的最小修复边界。

### 3.2 论文图证据不是领域调度泄漏

通用 figure extraction 的 `curve_tables`、source panels、overlays、manifest 和 validation report
共同构成可审计的图证据包。`render_curve_support.py` 作为 `worker_run_analysis` 的只读挂载脚本，
只在声明 collection 输出的沙箱内可用；它不进入 compiled catalog，不计算曲线一致性分数，也不选择
下一步行动。因此保留这一通用证据能力比把“曲线”字符串机械迁出 core 更符合最小系统原则。

## 4. 阻断 F2：插件组件所有权被源码别名绕过

`curve_score/science_operations.py:64-72` 直接导入
`general_science_plugin` 的 `_agent`、`_payload_validator`、`_schema` 和私有常量，以及
`general_transform_operations._RequiredParentage`。更严重的是 `:958` 与 `:986-993`：曲线插件把
`general_science` 的 `WORKSPACE` 和五个 Resource 实现路径重新声明为 `curve_score` 的本地
`ComponentSpec`。

编译器已经在 `operations/catalog.py:145-148` 定义唯一合法跨插件组件机制：调用方必须声明插件
依赖，被调用组件必须 `public=True`，Operation 再用带 `plugin_id` 的 `ComponentRef` 精确引用。
当前被复用的 `general_science` workspace 和五个 Resource 均是 `public=False`；本地别名使编译器
把实际属于 `general_science` 的实现错误记作 `curve_score:*`，也避开了上述公开边界检查。

这不是运行时 Root/Worker 的 Python 路径分派，也没有形成第二注册表，但它仍是实质性门禁缺陷：
插件依赖声明没有精确覆盖它消费的组件 ABI，目录的组件所有权与源码所有权不一致；修改另一插件的
私有声明实现可以直接破坏曲线插件。对于“普通新领域只经统一入口、低成本注册”的目标，这种模式会
把插件接入重新变成对内核私有源码布局的纵向耦合，不能留作 R5-D 的纯代码美化。

需要特别区分：`science.experiment.*`、`science.object.review.v1`、`science.result.diagnose*` 当前合同
明确是曲线专用，Operation 归 `curve_score` 本身没有问题；阻断只在组件和声明构造面的私有复用。

## 5. 精确最小修复与复审门

不要求迁回领域 Operation，不要求发明新注册表、状态机、组件生命周期或通用科研实体。最小修复为：

1. 对确实共享的 workspace/Schema resource，使用编译器现有的“显式 `PluginDependency` +
   `public=True` + 跨插件 `ComponentRef(plugin_id=...)`”机制；不得在曲线插件中用另一插件的实现路径
   重新声明本地组件。
2. 曲线插件不得再导入 `general_science_plugin` 或 `general_transform_operations` 的下划线私有符号。
   将真正领域无关的声明构造 helper 放入一个明确公开、无状态、无注册/发现职责的窄模块，或在插件
   内保留其领域专用实现；不要复制整套 Operation builder。
3. 增加静态负例，拒绝插件本地 `ComponentSpec.implementation` 指向另一个插件的私有实现模块；
   增加编译负例证明未声明 dependency、非 public 组件和错误 component id 均失败关闭。
4. 复跑 clean-wheel core/full、真实曲线 Worker 路由、盲插件、审批/生命周期聚焦矩阵和全仓串行
   回归；保持 core 17、full 51、core-only 零领域模块加载，且 operations 包不高于 2060 行。

修复可以与 R5-D 预定的通用插件声明拆分共用同一小步，但在该跨插件所有权门通过前，不能把 R5-C
标为完成，也不能开始其余 R5-D 拆分。

## 6. 独立运行与结构记录

本轮实际执行：

```text
# clean-wheel core/full、目录、通用图证据、曲线工具真实路由
# 17 passed in 30.78s

# 曲线插件、R5-B 盲插件、Worker 权限、preflight、审批、TCAD debug
# 63 passed in 38.16s

pytest -q
# 269 passed in 83.77s

git diff --check
# 通过
```

当前机器生成口径为：R0 聚合 `9485/13657` 行，operations 包 `7` 文件、`2056/2060` 行，生产
Python `127` 文件、`59933/62533` 行，`deploy/install.sh` `1021/1026` 行；通用 core 领域 token
门从 `112` 降为 `4`，四处均为未自动加载的共享曲线数据 Schema 之间的 import，不是领域调度分派。
这些指标排除了复杂度总体反弹，但不能证明 F2 的组件所有权正确。

## 7. 最终结论

首轮 F1 的启动隔离和领域迁移已经真实关闭；通用论文图证据边界、真实曲线工具路由、控制生命周期、
盲插件和全仓测试均成立。当前唯一阻断是曲线插件通过 Python 私有实现路径绕过现有跨插件公开组件
门，导致编译目录中的组件所有权失真和低成本插件接入边界退化。

**结论：打回。不得放行 R5-D。**

仅完成第 5 节的最小插件边界修复并独立复审通过后，才可放行 R5-D；不得借此重开已经通过的
Operation 归属迁移或扩大为新的框架层。
