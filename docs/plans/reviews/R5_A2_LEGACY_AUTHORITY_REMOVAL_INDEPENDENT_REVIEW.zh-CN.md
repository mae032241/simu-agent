# R5-A2 旧发现权威与旧创建入口删除独立审查

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-A2 冻结候选  
结论：**有条件通过**  
门禁决定：**不放行 R5-B**

## 1. 审查范围与方法

本轮未参与实现。审查前完整读取并遵循 `scid-cross-boundary-review`、
`scid-find-simplifications`、`scid-change-scope-checks` 三项技能和仓库 `AGENTS.md`，逐项核对
上位计划第 5.2—5.4 节、R5-A2 实现记录、当前架构、生产代码和安装态测试。

审查沿以下边界进行：安装包 entry point → 启动期目录编译 → Codex/两个 daemon → Root
预检与调用 → Task authority → Worker 工具投影；并单独检查部署脚本能否在不绑定 TCAD 的情况下
安装用户选择的插件。只写入本报告，未修改生产代码、测试、计划或实施状态。

当前工作树包含 R1—R5 的大范围未提交候选，Git HEAD 不是独立的 A2 基线；本结论只适用于审查时
的精确工作树。实现方记录的全仓 `248 passed` 可作为候选证据，本轮没有将其冒充独立复跑。

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 5.2—5.4 节及 R5-A 门 |
| S2 | `docs/plans/R5_A2_LEGACY_AUTHORITY_REMOVAL.zh-CN.md` |
| S3 | `src/scidiscovery/operations/catalog.py`、各包 `pyproject.toml` |
| S4 | `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`、`operations/invoke.py` |
| S5 | `src/scidiscovery/artifact_agent/service/tasks.py` |
| S6 | `src/scidiscovery/runtime.py`、`platforms/codex.py`、control/Worker daemon 入口 |
| S7 | `deploy/install.sh`、`deploy/plugin_selection.py`、systemd 模板 |
| S8 | clean-wheel、Agent/Transform/Effect 生命周期、Worker authority 和部署脚本拥有者测试 |
| S9 | 本轮独立串行运行的 18 项测试、源码扫描、复杂度计数和 `git diff --check` |

| 检查 | 判定 | 证据 |
|---|---|---|
| 唯一插件发现权威 | 通过：生产发现只选择 `scidiscovery.plugins`；旧三个组及旧 loader 无生产后备路径 | S3、S6、S8、S9 |
| 唯一调度创建入口 | 通过：四个旧 Root 工具不可达，Agent/Transform/Effect 均从 `operation_invoke` 进入 | S4、S8、S9 |
| Task compiled authority | 通过：新建任务必须带精确 `TaskOperationAuthority`、operation 上下文及提交前置条件 | S5、S8、S9 |
| 私有 Transform/Effect 边界 | 通过：内部执行方法不公开、不动态发现，只接收同次预检形成的绑定调用，未发现第二调用者 | S4、S8、S9 |
| 四个真实启动入口 | 通过：clean wheel 实际进入 runtime、CLI、control daemon 和 Worker daemon；仅截断无限 socket 循环 | S6、S8、S9 |
| 安装器领域中立性 | **不通过**：主安装器默认、来源门、Python 探针、服务渲染和安装生命周期仍强制 TCAD | S1、S2、S7、S9 |
| Operation 摘要与复杂度 | 通过：专项验证 core/full/full+InGaAs 为 28/51/52；operations 包 2060 行、安装脚本 1026 行可复现 | S2、S8、S9 |
| 33 项约束与奥卡姆边界 | 核心运行链未退化且没有新注册表/状态机；但通用安装入口仍复制领域选择，扩展目标尚未闭合 | S1、S3—S9 |

## 3. 已通过部分

### 3.1 旧发现权威已真实删除

- `operations/catalog.py:22` 将唯一组冻结为 `scidiscovery.plugins`，生产源码只有
  `catalog.py:623` 一处 `entry_points()` 消费；core 与各领域包也只发布该组。
- `platforms/roles.py` 已删除；`scidiscovery.agent_role_packs`、
  `scidiscovery.transform_adapters`、`scidiscovery.operation_specs` 及
  `load_roles()`/`load_transform_adapters()` 在生产源码和插件中无命中。
- `ScientificStateTransformAdapter` 只是已编译组件调用的纯算法，不发现、不选择 Operation，未形成
  第二注册表或兼容 facade。

### 3.2 四个旧 Root 创建表面已不可达

`ROOT_TOOLS` 仅公开统一的 `operation_catalog`、`operation_preflight`、`operation_invoke` 及现存控制
生命周期工具；`task_schedule`、`artifact_transform`、`approval_request_create`、
`execution_request_create` 均不在映射中，真实 router 对它们返回未知工具。

保留的 `execution_approval_request_create` 只为已由 compiled Effect 创建的精确执行请求发起本地
决定，不创建 Effect。`_invoke_compiled_transform` 和 `_invoke_compiled_effect` 是非 MCP 私有方法，
生产调用者只有 `operation_invoke`；调用前先完成同一 compiled catalog 的绑定和预检。它们不是
密码学 capability，但在当前单进程可信核心边界内没有外部或动态消费者，足以满足本阶段“不能由
调度器绕过”的要求。

### 3.3 Task 与 Worker 权威未退化

`TaskService.schedule()` 的 `TaskOperationAuthority` 为必需参数，并要求
`context_profile="operation"`、Agent 类型、输出合同、authority digest 和提交前置条件一致。历史无
authority 分支只用于读取或拒绝旧记录，没有新的创建路径。Worker 的 assignment、工具集合、输出
合同和任务恢复继续绑定该 authority；本轮生命周期和 handoff-only/最小上下文测试通过。

### 3.4 四个 clean-wheel 启动入口可信

安装态测试真实调用 `open_runtime()`、`scid init codex` 的 CLI `main()`、control daemon `main()`
及 Worker daemon `main()`，并走真实目录、runtime contribution、router 和 `tools/list`。测试只用
daemon 替身避免进入永久 socket 循环，没有以元数据读取代替启动链。

core/full/full+InGaAs 的目录数量为 28/51/52，InGaAs 安装前后既有摘要集合不漂移。A2 未改
Operation 声明；Approval、Execution、恢复和 Worker 权限的拥有者测试保持通过。

## 4. 阻塞问题

### F1（阻塞）：主安装器仍是 TCAD 纵向部署器，不符合第 5.4 节和实现记录

上位计划要求“只安装用户选择的包”，删除固定 TCAD import，并允许 TCAD 独有服务由 TCAD 部署
子命令管理。实现记录第 4 节进一步声称安装探针“不再导入 TCAD Python 包”。当前字节与该声明
不符：

- `deploy/install.sh:10` 在用户未选择时固定默认 `tcad_artifact,curve_score`；
- `:23`—`:26` 固定安装两个 TCAD/论文图技能；
- `:49`—`:80` 无条件要求 Sentaurus 手册、TCAD 技能、TCAD 插件和 TCAD systemd 模板存在；
- `:118`—`:119` 明确拒绝未选择 `tcad_artifact` 的安装；
- `:145`—`:148` 的通用来源探针直接 `import tcad_artifact`；
- `:218`—`:270` 为通用 control/Worker 单元无条件注入 `tcad_artifact` 配置，并始终渲染
  `tcad-control.service`；预览也固定加入 `plugins/tcad_artifact` 的 `PYTHONPATH`；
- 后续安装、恢复、健康检查和 systemd 生命周期继续无条件创建 TCAD 状态、策略、插件配置及服务；
- `tests/artifact_agent/test_deploy_scripts.py:478` 反而冻结了固定 TCAD/curve 默认值，因此现有测试
  不能证明第 5.4 节所要求的通用安装路径。

这不是允许保留的“显式 TCAD 部署选择”：当前没有一条主安装器的 core-only 或非 TCAD 插件路径
可绕开上述门。结果是新领域虽然能通过唯一 entry point 编译，却不能使用仓库的标准部署入口而
不携带 TCAD。这正是 R5-A 要删除的领域注册/部署耦合，直接影响“插件一次注册、低成本扩展”的
目标，不能推迟到 R5-B。

#### 最小修复要求

1. 让通用安装路径不再隐式选择 TCAD/curve，不再要求 `tcad_artifact`、TCAD 手册/技能/配置/状态/
   服务，也不直接 import TCAD 包；它只处理用户显式选择的插件并编译
   `scidiscovery.plugins` 目录。
2. TCAD 专用技能、policy、runtime config、远程执行服务及 systemd 单元要么移入一个明确的 TCAD
   部署子命令，要么完全受“用户显式选择 TCAD”条件控制；不得建立第二插件注册表或按 Operation
   名单分派。
3. 通用 control/Worker 的 `--plugin-config` 从显式选择/配置产生；未选 TCAD 时不得写入 TCAD
   配置参数或渲染 TCAD service。
4. 增加真实的 core-only 或核心未知非 TCAD fixture 安装/预览正例，证明不导入、不要求、不渲染
   TCAD；另保留显式 TCAD 安装回归。修改目前冻结固定默认值的测试。
5. 修正 R5-A2 实现记录第 4 节，使其只陈述重新验证后的事实，并在相同 7 GiB 串行门下复跑部署
   拥有者测试、四启动入口和相关回归。

这些修复不需要新实体、注册表、状态机或兼容 facade，只需把现有部署条件与唯一编译目录对齐。

## 5. 独立运行证据

所有命令严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

本轮结果：

```text
pytest -q \
  tests/operations/test_baseline_plugin_discovery.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_transform_lifecycle.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_baseline_role_contracts.py \
  tests/operations/test_baseline_worker_authority.py
# 12 passed in 32.99s

pytest -q \
  tests/operations/test_r4_approval_operation.py::test_generic_root_cannot_create_a_scientific_qualification \
  tests/operations/test_tcad_operation_plugin.py::test_explicit_legacy_tcad_adapter_cannot_bypass_compiled_operation \
  tests/operations/test_runtime_plugin_configuration.py::test_generic_daemons_have_no_tcad_runtime_switches_or_imports \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_probes_compiled_operation_authority_without_fixed_counts \
  tests/artifact_agent/test_platform_configuration.py::test_legacy_role_discovery_module_is_absent \
  tests/operations/test_catalog_installed_entrypoint.py::test_legacy_domain_entry_points_are_not_an_operation_discovery_fallback
# 6 passed in 24.47s

git diff --check
# 通过

wc -l deploy/install.sh
# 1026 deploy/install.sh

find src/scidiscovery/operations -maxdepth 1 -type f -name '*.py' -print0 \
  | sort -z | xargs -0 wc -l
# 2060 total
```

源码扫描还确认：生产 `entry_points()` 只有唯一组消费者；旧三个发布组、旧 loader 和旧 Root 工具
定义无生产命中。已发现 F1 后没有重复全仓 248 项，因为部署领域耦合是静态且可直接复现的完成门
失败，重复无关测试不会改变门禁结论。

## 6. 最终结论

**有条件通过。**

R5-A2 的核心删除工作成立：旧发现权威、四个旧 Root 创建表面和无 authority 新任务路径已经收口，
四个真实 clean-wheel 启动入口及 Agent/Transform/Effect/Worker 生命周期未退化，也没有新增兼容
facade、注册表或状态机。

但第 5.4 节尚未完成，且实现记录关于安装器不再导入 TCAD 的事实声明错误。主安装器仍强制整个
平台成为 TCAD 纵向产品，新领域不能只凭插件选择使用标准部署入口。因此本报告**不放行 R5-B**；
只能按 F1 的最小范围修复并重新独立送审。修复后必须重新验证通用非 TCAD 安装路径和显式 TCAD
路径，两者都通过后方可把结论提升为“通过”。
