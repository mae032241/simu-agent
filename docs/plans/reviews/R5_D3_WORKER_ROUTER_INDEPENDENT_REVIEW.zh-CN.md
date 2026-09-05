# R5-D3 Worker Router 职责拆分独立审查

日期：2026-08-29  
审查性质：未参与实现的跨边界、简化性与变更范围审查  
结论：**通过**  
门禁决定：**只放行 D4，不提前放行 R5-D 总审、R5-E 或后续阶段**

## 1. 审查范围

本轮只审查 Worker MCP 的职责拆分：唯一 Router、协议投影和一个无状态分派混入，以及它们与
CompiledOperation、TaskService、网络准入、通用原生工具、TCAD/曲线注册工具、Codex Worker 配置和
安装态入口的组合边界。审查没有修改生产代码、测试、计划或阶段状态；唯一写入是本报告。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行。当前插件是启动期加载的受信代码；把任意不受信插件移入独立进程是
既有文档明确保留的未来加固要求，不是 D3 文件拆分的当前失败条件。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | 权威计划 `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，SHA-256 `ebba87f2db43622a82bdf8e8c66f89cb55e87febe870bee21fd812ac5b64ef1a`；使用第 3 节、第 8.3 节和 R5-D 复杂度门。 |
| S2 | 当前架构 `docs/ARCHITECTURE.zh-CN.md`，SHA-256 `570d811adb87a7add86bc85057fba5214145f215bc58f95845c7ce20b8a0dfad`；最小重构权威 `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`，SHA-256 `77bb5c36ee71a683b0ffed5adec55968ba0be35d88af5ff0af5f2d7d951b0494`。 |
| S3 | Worker 三个生产模块：`mcp_worker.py`（SHA-256 `208a04bf...`）、`mcp_worker_protocol.py`（`84133e58...`）、`mcp_worker_dispatch.py`（`576b9253...`）。 |
| S4 | 编译工具合同 `src/scidiscovery/operations/tooling.py`（SHA-256 `be9e367e...`）与 Task 服务端 capability、注册工具收据和网络授权实现 `tasks.py`（`0772d1ea...`）。 |
| S5 | TCAD `DEBUG_TOOL`、curve-score `CURVE_ANALYZE_TOOL`、通用/内建工具组件、Worker daemon/proxy、Codex Worker 装配及其实际消费者。 |
| S6 | 结构门 `tests/operations/test_r5_worker_router_split.py`，SHA-256 `8db99774...`；网络门 `test_operation_network_authority.py`，SHA-256 `dcd728b3...`；精确工具、TCAD、曲线、通用 Agent、namespace 与 clean-wheel 测试。 |
| S7 | 当前计量脚本 `scripts/r5_current_metrics.py`，SHA-256 `20f243f3...`；本轮输出 SHA-256 `795ac0b0caf898a4a17ec9a506ef31729b38a29983a452de1dceb5aaa808d186`。 |
| S8 | 冻结生成器 `scripts/r5_baseline_metrics.py`，SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；冻结快照 `tests/fixtures/r5_structure_inventory.json`，SHA-256 `1b397e2dfea1bc579b2597caf5d3a37f5ef44e40d66b92f509b349b51b77983a`。 |
| S9 | 实施记录 `docs/plans/R5_D_RESPONSIBILITY_SPLIT_IMPLEMENTATION.zh-CN.md`，SHA-256 `b9216e4a...`。 |
| S10 | 本轮独立运行记录：15 项跨边界聚焦测试、280 项全仓测试、AST/导入身份/当前计量检查、三模块编译检查与 `git diff --check`。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `single_router_authority` | pass | S1—S5, S10 | 只有 `WorkerMCPRouter` 构造并持有 TaskService、worker/proxy/dispatch capability、tool services、session、completed、锁、可见工具、注册 handler 和 handler 局部状态；protocol 与 dispatch 均无构造器或状态副本。 |
| `protocol_projection` | pass | S3, S4, S6, S10 | protocol 只声明输入 DTO、同一个 16 项公开工具元组、12 项隐藏兼容投影、capability 映射、不可变 task access 和编译组件对象；没有发现、服务实例、可变目录、缓存或第二工具注册表。 |
| `compiled_tool_binding` | pass | S3—S6, S10 | Router 只枚举与精确 `operation_agent_type` 相同的 compiled Agent Operation，工具由 `operation_worker_tools()` 解析；同 Operation 重名被拒绝，未声明工具同时受到 Router 可见集合和 Task authority 的工具名/capability 门约束。 |
| `dispatch_and_task_boundary` | pass | S3—S6, S10 | 分派混入只有 `_call_tool`，无状态；claim 后先校验精确 capability 与工具名，再调用注册 handler；文件、输入、PDF、分析、输出、活动、validate/finalize 全部委派唯一 TaskService，没有直接 CAS、SQLite 或任务目录写入路径。 |
| `network_authority` | pass | S3, S4, S6, S10 | 当前唯一联网 Worker 工具是编译的 `worker_fetch_web_evidence`；初始请求及每次重定向在 I/O 前调用 TaskService 的 HTTPS、域名、精确工具和次数预算门。测试 patch 实际实现所有者，禁止初始地址、禁止重定向和预算耗尽均失败关闭。 |
| `legacy_component_identity` | pass | S3—S6, S10 | 既有 `scidiscovery.artifact_agent.interfaces.mcp_worker:..._TOOL` 实现字符串仍可导入，且 16 个编译常量逐个与 protocol 对象保持 `is` 同一性；没有旧模块代理 handler、第二 fetch 实现或重复执行路径。 |
| `native_and_domain_tools` | pass | S3—S6, S10 | 通用文件/PDF/Web/分析工具保留原 Task 权限和封存链；TCAD 调试工具只由精确 author Operation 和插件 service 取得，reviewer 不可见；曲线工具通过 contextual handler 的窄 Task access 产生并校验声明集合，成功/失败均登记收据。 |
| `domain_neutrality_and_imports` | pass | S1—S6, S10 | 三个 Worker 核心模块没有 TCAD、设备参数、InGaAs 或领域 Operation 分派；`render_curve_support.py` 仅作为通用论文图证据分析沙箱的只读辅助资源，不选择曲线科研 Operation。模块导入无环，真实 daemon/Codex/clean-wheel 入口通过。 |
| `complexity_and_occam` | pass | S1, S3, S7—S10 | Worker 职责真实聚合为 1269/1241（+28）：Router 105、protocol 238、dispatch 926；全生产 60468/62533，operations 包 2056/2060。只按“协议/状态分派”两个变化原因拆分，没有为 16 个工具建立 service/factory/class。 |
| `constraints_and_goal` | pass | S1—S6, S10 | 精确身份、最小上下文、文件通信、人工审批、唯一 Artifact/Task/Execution 权威、来源与恢复均未退化；未新增科研实体、状态机、数据库表、目录权威或插件外领域流程。 |

## 3. 边界判断

### 3.1 一个 Router，而不是三个服务

当前运行时仍只有一个 `WorkerMCPRouter` 对象。protocol 是不可变协议与编译组件投影；dispatch 是同一
对象上的无状态方法集合。后两者都不能独立 claim 任务、建立 session、发现工具或访问数据库。
`WorkerToolDispatchMixin` 读取的全部状态来自 Router，并把有状态操作交回其唯一 TaskService，因此拆分
没有产生协调协议、复制状态或第二生命周期。

注册工具也没有形成全局表。Router 从同一个 startup-compiled catalog 中，仅选择
`operation_agent_type(compiled) == worker_id` 的精确 Operation。工具可能因 Codex 原型限制而在父环境
可见，但服务端调用仍须同时命中该 Router 的工具对象和当前 Task authority 的工具名/capability；这与
“可见不等于授权”的现有原型边界一致。

### 3.2 网络、受信插件和最小 Task access

Web 证据路径的 monkeypatch 从旧 facade 改到 `mcp_worker_dispatch.fetch_web_evidence` 是正确的真实
所有者修正：旧 `mcp_worker` 不再导入 fetch，也没有兼容转发。初始 URL、重定向 URL 和次数预算仍在
TaskService 中逐次授权，拒绝发生在对应 I/O 之前。

当前两个领域 handler 都不声明网络能力：TCAD handler 取得插件配置的调试 service，曲线 handler 只
取得不可变 `WorkerTaskAccess`，其中只有精确输入读取、声明输出目录、输出校验和活动记录。插件组件是
启动期受信 Python 代码，现有架构从未把该窄对象描述为不受信代码沙箱。未来若开放第三方不受信插件，
其进程隔离和系统级网络强制需要单独阶段；本轮不为尚未实现的安全性质增加代理层。

### 3.3 兼容投影不是第二权威

12 个 legacy Worker 工具仍可被旧任务调用，但不出现在公开 `list_tools()`，它们与 16 个公开工具共用
同一 Router、session、capability 表、TaskService 和 finalize 状态，没有 facade、loader 或另一份
handler。编译组件继续由原 `mcp_worker:..._TOOL` 路径解析，只是对象定义归入 protocol；这种符号身份
保持不会创建另一条行为路径。

## 4. 复杂度与奥卡姆判断

拆分前 Worker 文件为 1241 行，三个 successor 合计 1269 行，净增 28 行，约 2.3%。新增量是模块
导入、协议边界和一项结构门；运行时对象、状态字段、数据库、工具发现和调用分支没有增加。Router
降为 105 行，清楚显示唯一状态与装配；protocol 独立承载稳定 DTO；dispatch 仍以一个 926 行混入
保留彼此共享 session/capability/TaskService 前置条件的 16 项内建调用。

继续按文件、PDF、表格、图像或每个工具建立类，会复制授权前置条件并扩大 MRO/注册面；当前没有
独立状态或替换理由支持这种拆分。因此 +28 行边界成本可接受，但不能把入口单文件缩小单独宣称为
减重，后续计量必须继续使用 1269 行职责聚合。

## 5. 独立运行记录

全部命令在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1` 下严格串行执行。

```text
pytest -q \
  tests/operations/test_r5_worker_router_split.py \
  tests/operations/test_operation_network_authority.py \
  tests/operations/test_baseline_worker_authority.py \
  tests/operations/test_r3_agent_contract.py::test_worker_router_resolves_tools_only_for_its_exact_operation \
  tests/operations/test_curve_score_operation_plugin.py::test_curve_analysis_tool_is_invoked_through_the_compiled_agent \
  tests/operations/test_catalog_compile.py::test_network_tool_compiles_only_with_exact_restricted_scope \
  tests/operations/test_catalog_negative_cases.py::test_network_tool_and_policy_must_be_declared_together \
  tests/operations/test_live_qualification_evidence.py::test_worker_namespace_audit_accepts_only_the_compiled_server \
  tests/operations/test_live_qualification_evidence.py::test_worker_namespace_audit_rejects_even_a_failed_probe \
  tests/operations/test_runtime_plugin_configuration.py::test_runtime_plugin_config_is_startup_only_and_shared_by_control_and_worker
# 15 passed in 32.78s

pytest -q
# 280 passed in 87.49s

PYTHONPATH=src python <AST、16 项对象身份与旧实现路径导入检查>
# 通过

PYTHONPATH=src:scripts python <当前职责与全生产计量重算>
# Worker 1269；全生产 140 文件 / 60468 行

python <三模块 compile 检查>
git diff --check
# 均通过
```

未运行真实 Sentaurus、公网抓取或浏览器人工决定：D3 没有修改 solver adapter、HTTP 获取算法或审批
写入口；其运行边界已由注册工具真实路由、网络授权负例、全仓安装态回归和此前资格证据覆盖。这些
外部未来观测不是当前职责拆分的缺失证据。

## 6. 最终结论

未发现阻断缺陷。D3 保留了唯一 Worker Router 与 TaskService 权威，protocol 只是同一工具合同的
不可变投影，dispatch 只是授权后的无状态方法集合；原生、网络、TCAD、曲线、文件封存、恢复和
clean-wheel 路径没有退化。净增 28 行没有形成复杂度反噬，也不应继续按每个工具拆类。

**结论：通过。只放行 D4。**
