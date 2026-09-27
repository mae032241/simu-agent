# R5-C 静态拓扑、上下文策略与调度提示词收口独立审查

日期：2026-08-29  
审查性质：未参与实现的只读跨边界、简化性与变更范围审查  
结论：**通过**  
门禁决定：**本子阶段可以收口；本报告不预先批准 R5-D。**

## 1. 审查范围与候选

本轮核对 R5-C 第 7.4 节的精确候选：删除静态科研拓扑和旧上下文策略，收缩父调度提示，并证明输入可见范围、Worker 文件通信、独立审查和人工审批仍由同一个编译 Operation 合同及既有控制生命周期承接。

审查按 `scid-cross-boundary-review`、`scid-find-simplifications`、`scid-change-scope-checks` 执行。所有测试严格串行，并在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、`PYTHONDWRITEBYTECODE=1` 下运行。

当前关键文件摘要：

- `AGENTS.md`：`85cd01826a2aadc07d38b022b00741e9c4e48a12ee88943c576ebadbf33c5a0c`；
- `roles/scheduler.md`：`44dec3f75512c898eb5a3d912a8706c3994eb2028083ab2367775620d9d6d66c`；
- `src/scidiscovery/operations/catalog.py`：`4e5a5de78e4bd07051cd3737f1ed50b8ce69a47c5f4136987ae6c393f44b9822`；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`：`7facd5a5869a07b26e29b866954216287b15e46d3a6afebefcf5bfa9cb35f077`；
- `src/scidiscovery/artifact_agent/service/tasks.py`：`545b7cc00fb1cf39f7b56e02345461510e9c12f0742131d6e7685f263d7df53e`；
- `tests/operations/test_r3_catalog_authority.py`：`36ee6a806977770877f2f4a2cc125754fdcfae4511df7dcace4114f190dc27cb`；
- `tests/operations/test_tcad_operation_plugin.py`：`ba3f867b98dd5183135ed5a1937a5e3f232761f1d2df1dbcd7fea7f6a3a834df`。

## 2. EvidenceAudit

### 来源声明

| 来源键 | 来源 |
| --- | --- |
| S1 | `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 3、7、14 节及当前架构中 OperationSpec、单一目录、Worker、Approval 边界。 |
| S2 | 当前删除状态及全生产树消费者检索：`scheduler_topology.py`、核心两个 context 文件和 TCAD `context_policies.py` 均不存在。 |
| S3 | `roles/scheduler.md`、根 `AGENTS.md`、`platforms/scheduler_prompt.py` 与 `platforms/codex.py` 的真实提示生成链。 |
| S4 | `operations/catalog.py`、`operations/spec.py`、`mcp_root.py` 的编译目录、目录投影、inventory、preflight/invoke 路径。 |
| S5 | `operations/invoke.py`、`service/tasks.py`、Worker MCP/精确 dispatch 与平台配置的 OperationAuthority、输入 exposure/usage、工具、文件和终态路径。 |
| S6 | TCAD 插件声明、author/reviewer 编译提示、review edge、workspace hook 与生命周期聚焦测试。 |
| S7 | 本轮测试日志：四组聚焦测试共 39 项通过；严格串行全仓 `268 passed in 89.79s`；静态扫描、独立目录投影脚本与 `git diff --check` 通过。 |

### 检查记录

| 检查键 | 结论 | 证据 | 简要依据 |
| --- | --- | --- | --- |
| `retired_topology_context_authority` | pass | S1, S2, S7 | 四个旧文件均删除，生产 Python、插件、部署及活动角色提示无旧模块、角色表或 capability 表消费者。 |
| `scheduler_prompt_domain_neutrality` | pass | S1, S3, S7 | 调度提示只声明科学选择原则、精确绑定、preflight/invoke、文件通信、生命周期和最小授权；无固定领域 Operation id、端口或阶段顺序。 |
| `single_catalog_projection` | pass | S1, S4, S7 | public/support/internal 由同一不可变 `CompiledCatalog.scheduler_projection()` 按 `catalog_scope` 过滤；直接编译得到 25/27/0、合计 52 个唯一 Operation。 |
| `inventory_not_recommender` | pass | S3, S4, S7 | inventory 只读列举最新语义 Artifact、显式 current 和同一 public 投影，不解析 payload、不排序候选、不建议下一步。 |
| `worker_minimum_context` | pass | S1, S5, S7 | 端口编译得到 exposure/usage/大小、TaskOperationAuthority、任务本地别名和允许工具；handoff-only、精确 dispatch、文件路径及服务端工具负例保持关闭。 |
| `review_and_human_boundary` | pass | S1, S5, S6, S7 | 独立 review edge 仍由编译器验证，Approval 仍绑定精确 provider/subjects；聊天不成为决定，Root 不能直接制造科学资格。 |
| `blind_plugin_extensibility` | pass | S1, S4, S7 | R5-B 未知盲插件的 Agent/Transform/Approval 正负例继续通过，Root、Task、Scheduler、UI 无新增插件名分支。 |
| `anti_regression_coverage` | pass | S2, S3, S6, S7 | 防回潮测试同时覆盖四个删除路径、生产源码旧权威、调度提示领域中性和两个真实 compiled TCAD prompt。 |
| `occam_complexity` | pass | S1, S2, S4 | 删除 1531 行旧表/类型并把 scheduler 提示从 274 行收缩到 60 行；未增加注册表、数据库表、状态机或兼容 facade。 |

## 3. 关键审查结果

### 3.1 删除是职责消除，不是迁移旧表

`scheduler_topology.py`、`artifact_agent/context_policy.py`、`core_context_policies.py` 和 TCAD `context_policies.py` 已全部消失。生产路径不再按角色、context profile、领域 artifact kind 或静态 capability 表选择输入和下一步。

原本仍有必要的约束由已有 OperationSpec 字段承担：输入端口负责 schema、media、数量、大小、exposure、usage、cohort 和 current；编译器冻结 prompt、工具、工作区、资源、review edge 与 approval contract；TaskService 只接受与当前编译摘要一致的 `TaskOperationAuthority` 并在服务端执行读取、工具、输出和终态门。这里没有新增另一套 context 对象。

### 3.2 调度提示不再编码科研产品流程

`roles/scheduler.md` 为 60 行，未检出 `science.*.vN`、`tcad.*.vN`、`scidiscovery.*.vN`，也未检出 TCAD、InGaAs、设备参数、图像提取或曲线评分领域词。根 `AGENTS.md` 的受管区以该文件开头，再追加 Codex 的通用 dispatch、无父历史、Worker MCP 可见不等于授权、聊天不可信以及本地 UI 决策边界。

提示仍明确要求调度 Agent依据当前科学矛盾从 public 投影选择一个有界行动；这保留了 Agent 的科学判断职责，同时禁止从提示中的固定角色表或 DAG 获取行动权威。

### 3.3 单一目录与 inventory 边界

`CompiledCatalog` 只持有一个不可变 Operation 映射。`operation_catalog` 对同一 `scheduler_projection()` 做 scope 过滤，`all` 只是诊断联合视图；`scientific_inventory` 直接复用其中 public 结果，没有缓存、注册或复制另一张行动表。

独立脚本对 core、通用科学、TCAD、curve 和 InGaAs 五个插件的同一编译目录核验：public 25、support 27、internal 0，三个集合互斥且并集与 52 个唯一 Operation 完全一致。

### 3.4 Worker、文件通信与审批未退化

真实平台生成、安装态 Worker 权限、TCAD author/reviewer 生命周期和精确 dispatch 测试证明：父调度只接收不可信的子 Agent 完成信号，科学内容必须经过任务私有文件、校验和 finalize；Worker 的输入别名、读取模式、领域工具与资源限制仍来自精确编译权威。独立 reviewer 不获得 author 的调试工具，人工资格仍只能由既有 ApprovalService/UI 针对精确对象产生。

审查中曾发现 author/reviewer 的模型可见提示仍含一个已删除 TCAD context policy 模块引用。实现方按最小范围删除两行遗留前置元数据，并把 TCAD 删除路径和两个 compiled prompt 的反回潮断言加入测试。本报告只依据修复后的完整对象重新编译和复测；未沿用修复前观察作为批准。

## 4. 测试记录

修复后独立执行：

1. 删除、目录投影、调度提示与 TCAD 编译提示：`6 passed in 0.53s`；
2. 平台配置、安装态 Worker 权限与 TCAD author/reviewer 生命周期：`9 passed in 27.18s`；
3. inventory/精确 preflight 与 R5-B 盲插件：`13 passed in 28.54s`；
4. Approval provider/资格边界与精确 Worker dispatch：`11 passed in 2.18s`；
5. 全仓严格串行回归：`268 passed in 89.79s`。

此外，四个删除路径存在性检查、生产/角色提示 `rg`、目录集合独立脚本及 `git diff --check` 均通过。未运行真实外部 solver 或浏览器人工点击：本子阶段未改执行 adapter 或 UI 写决定路径，这些仍属于 R5-F/R5-G 的安装和科学效果门，不能由本轮单元/安装态测试代替。

## 5. 复杂度与 33 项约束族

本阶段净删除旧科学流程表、角色上下文注册和重复调度提示，没有以新服务、状态机或“科学语义内核”替代。不可变 Artifact/父链、唯一 current 与 exact admission、Worker 最小上下文、独立审查、人工 UI 决定、外部副作用授权、幂等终态和插件失败关闭等承重约束仍由既有权威保护。

删除量为：静态 topology 341 行、核心 context 类型 105 行、核心 context 表 764 行、TCAD context 表 321 行；scheduler 提示由 274 行收缩为 60 行。复杂度是真实消除，没有搬到另一张注册表或隐藏到提示词。

## 6. 最终判断

未发现剩余阻断项。当前候选完成了静态科研拓扑、旧上下文策略和领域调度提示的实质删除，同时保持 OperationSpec 单一行动权威、Agent 科学选择、Worker 文件通信、最小授权与人工审批边界。

**结论：通过。本子阶段可以收口；不得据此跳过 R5-C 总门或预先进入未经独立审查的 R5-D。**
