# R5-M M7.5 奥卡姆简化、架构目标与 33 项约束独立终审

日期：2026-09-03  
审查者：未参与本轮实现的独立终审进程 `m7_5_simplification_final_review`  
审查对象：当前共享工作树中的 R5-M 最终候选、M7.4 物理报告、M7.5 关闭证据、33 项约束注册表及相关生产代码/测试  
结论：**PASS**  
阻断项：**0**  
阶段门：**允许 M7.5、M7 与 R5-M 关闭，但仍须同时取得另一名正确性/跨边界终审者的明确 PASS。**

## 1. 终审结论

当前候选已经朝本轮目标发生实质收敛，而不是把旧控制器改名或包进另一层：

- `OperationSpec` 是唯一行为声明，组件只是被其引用的窄实现；
- 所有插件只经 `scidiscovery.plugins` 一个 entry-point group 进入一次编译事务；
- `public/support/internal/all` 是同一 `CompiledCatalog` 的投影；
- Agent、Transform、Approval、Effect 都从同一编译对象进入同一 `operation_preflight` 和
  `operation_invoke`；
- 普通 Agent 只使用一个四态 `RunService` 和一个任务工作区，旧 Task/attempt/session/token/
  finalizing 协议已退出生产；
- scientific current 只有 `scheduler_scientific_selections` 一个写权威，Run 恢复只创建新 Run 并
  绑定冻结草稿，没有建立第二 current 或 checkpoint 生命周期；
- 通用核心未按 TCAD、曲线、InGaAs、Fig.4、Sentaurus、角色名或插件名分派科学能力；
- 领域运行工厂产生的 adapter/tool-service 映射是从同一目录和精确配置派生的启动期实现绑定，不能
  注册 Operation，也不构成第二行为注册表；
- Local 软隔离的局限被明确记录为 `SEC-002 known_issue`，没有用提示词禁令冒充技术沙箱。

保留下来的 Artifact、current、独立审查、人工审批和 Effect 恢复复杂度都有当前消费者及独立承重
理由；没有发现为了 M7 单项测试增加的领域标签、第二状态机、隐藏准入表或无消费者生产实体。因此
从奥卡姆目标、通用科研 Agent 目标和 33 项约束的诚实口径看，当前候选可以关闭。

## 2. 审查边界与证据方法

仓库是跨多阶段的未提交大工作树；本次没有猜测远端基线，也没有把 `HEAD` 当成 R5-M0。物理变化
采用计划已冻结的 M0 端点和当前字节，架构判断则直接审查当前生产路径。重点检查：

1. `operations/spec.py`、`catalog.py`、`invoke.py` 与所有发行包 entry point；
2. Root 的 operation、instance/current、Run、approval、execution 路由；
3. `RunService`、`RunCurrentGuard`、Local/Hardened 后端和工作区输出封存；
4. runtime plugin factory/contribution 到 TCAD adapter、工具服务和 Effect bridge 的接线；
5. 通用、TCAD、曲线、论文图、InGaAs 与盲 CSV 插件声明；
6. M7.2 恢复上限、M7.3 未知提交查回和对应负例；
7. M7.4 可复算计量、M7.5 全量结果及 33 项注册表。

本次不重复 286 项全量回归、真实 Codex、真实 SSH/Sentaurus 或 M7.1—M7.4 的重型实跑。M7.5 文件中
引用的五份前置证据/复审摘要经重新计算与记录值完全相同；当前差异通过 `git diff --check`。

## 3. 关键架构判断

### 3.1 一个声明入口，不是第二注册表

根包和四个领域包都只声明 `[project.entry-points."scidiscovery.plugins"]`。根包的 `builtin` 与
`general_science` 是同一 group 中两个固定插件定义，不是两种注册协议：前者唯一拥有通用文件工具，
后者拥有领域无关科研角色。`compile_installed_catalog()` 只发现这一组 entry point，随后调用唯一
`compile_catalog()`；生产树只在 `catalog.py` 构造 `CompiledCatalog`。

`RuntimePluginContribution` 只允许已经由目录引用的 runtime factory 在启动时交付 execution adapter、
领域工具服务和 reconciler。其局部名称会加上已编译 plugin id，并且配置集合必须与目录中的 runtime
plugin 精确一致。它不能声明新 Operation、改变 scope、review、端口或权限，所以不是插件私表反向
成为行为权威。

默认核心实测仍为 63 个组件、14 个 Operation，其中 11 public、3 support，执行种类为 10 Agent、
3 Transform、1 Approval、0 Effect。TCAD、曲线、论文图和 InGaAs 的更大数字只在显式安装组合出现。
这说明“统一入口”没有退化成“把所有领域代码默认装入一个巨型目录”。

### 3.2 一个普通 Run 和一个 current

生产代码中只有 `RunService` 拥有普通 Agent Run，持久状态只有 `queued/running/completed/failed`；
Local 与 Hardened 只是同一服务的工作区后端。Hardened 的 `active_transport` 是显式后端的一条互斥
租约，不保存科学终态，默认 Local 不导入该后端。旧 `TaskService`、中央 Worker 服务、调度 token、
attempt/session/finalizing 状态和旧 Worker 路由均已退出生产路径。

scientific current 的唯一可变事实是 `scheduler_scientific_selections`；`RunCurrentGuard` 只读取并冻结
该表中的精确 anchor，在创建和提交处复用，不写第二份 current。`scheduler_bindings` 保存语义名与各
revision 的控制对象绑定，selection 再从这些不可变 revision 中选择 head，两者职责不同。恢复则以
`resume_from_run_id`、失败 Run 和冻结草稿表示，并创建一个新 Run；它没有借 current 表伪装 checkpoint，
也没有另设恢复状态机。

`scheduler_observations` 是 `lifecycle_events` 的持久消费游标，只记录该调度会话已经看过的 Run/
Approval/Execution 状态；真实状态仍分别由原服务拥有。它有生产消费者，并支持中断后不重复报告
进度，不能仅因有一张表就认定为第二生命周期。

### 3.3 控制面只保留有消费者的硬边界

- Artifact/CAS 的三张表分别保存不可变 envelope、父链和幂等请求；旧 `artifact_events` 只允许以
  精确旧 v1 惰性形状被读取，不在新库创建、不参与运行权威。
- Approval 的请求、决定、防重放 nonce 和决定尝试分别保护精确人工决定、访问恢复和并发提交；当前
  通用 evidence qualification 与 TCAD qualification/Effect 都有消费者。
- `InputAdmissionSpec` 不是无消费者实体。当前有通用 scientific foundation、可选科学上下文、TCAD
  参数组和 Deck 参数组四类声明，取代了端口上重复的 cohort/provider/option 字段；编译和 Root 使用
  同一对象。
- Execution 的十态不进入普通 Agent Run，只在声明 Effect 后使用，分别表达请求、授权、提交、领域
  运行/取消、终态、收集和放弃。TCAD Effect 是实际消费者；删成四态会重新混淆“外部已接收”与
  “科学输出已收集”。
- M7.3 增加的 `lookup_submission(exact descriptor)` 是通用 Effect adapter 合同，并已接入 socket、
  command、SSH 和 remote runner；它与幂等 `submit` 共同关闭响应丢失及登记失败窗口，没有增加
  `submission_unknown` 状态、表或恢复守护进程。

这些部件仍然不算“小”，但其复杂度对应不同事实和故障窗口。继续为了行数把它们合并，反而会破坏
不可变性、人工决定或外部副作用不盲重发等承重约束。

### 3.4 多角色与文件交接仍是主干，而非固定科研 DAG

默认目录提供 evidence extraction/audit、hypothesis propose/criticize/revise、experiment design/
revise、object review 等角色；输入端口只定义数据准入，没有阶段计数或“某角色完成后必然调用下一
角色”的状态。调度提示要求从当前矛盾选择一个 public Operation。Worker 的科学内容只经其 Run
工作区、Schema 校验和封存输出进入下一角色；聊天、隐藏上下文和控制身份不参与文件交接。

Local 后端现在直接物化 assignment、Schema、显式输入和可选 recovery draft，允许可信本地 Agent
使用 Codex 原生读写/代码能力。这消除了此前“文件已物化但 Agent 无法读取”的自我阻断，也没有
新增逐文件 capability、读取收据或 MCP 文件代理。领域 MCP、Artifact 登记、review、approval 与
Effect 仍由服务端硬门保护。

### 3.5 没有发现针对测试的生产补丁

生产源码中没有 blind CSV、M7 fixture、恢复随机标记、测试 Schema 常量或特定测试 Run 名称。M7.2
的恢复总次数使用通用 `LimitsSpec.max_attempts` 和整棵 `resume_from` 父链；草稿标记与 Schema 常量
只存在于盲插件/实跑夹具中，用于证明 Agent 真正读取了两份文件。M7.3 的查回规则位于通用
`ExecutionAdapter`/`ExecutionBridge` 并接通所有正式 TCAD transport，不是仅让模拟器变绿。

M7 的独立 `codex exec` 启动器仍位于 `scripts/`，没有包 entry point、数据库状态或 Root 调用路径；
文件头和架构文档都明确它只是低内存实跑承载，不是第二生产调度器。当前生产派发权威仍是编译角色
加同一个 RunService。

## 4. M7.4 物理口径与 M7.5 证据

M7.4 的有限结论成立且没有夸大：

- 生产 Python 为 146/50,023 到 141/47,177，净减 5 文件、2,846 行；
- 六个 8765 集中责任的整文件后继为 7,062 行，相对 13,657 行减少 48.29%；报告明确说明这是防止
  “移文件冒充删除”的保守责任追踪，不是全系统语义复杂度分数；
- M6/M7 使用最终通过端点，分别为 -419/+207；
- 默认 63/14 与显式 TCAD+InGaAs 186/43、再加论文图 199/46 已分开；
- 盲 CSV 接入劳动准确记为四个源码文件 353 行、17 行包元数据、两个 Agent Operation、一个领域工具
  和一条精确审查边；它只证明统一接入机制，不冒充任意领域科学质量。

M7.5 记录的最终全量为 `286 passed in 119.08s`，最大常驻内存 140124 KiB、swap 0；套件包含干净
发行源、wheel、十四种隔离安装组合和部署事务回滚。第一次全量受原地 `compileall` 生成的特殊 runner
字节码污染而失败一项，证据保留该失败并说明只清除了本次确定生成缓存、未修改生产/测试；清洁前置
重跑通过。因此没有把测试环境污染隐瞒为首次成功。

## 5. 33 项约束审计

重新解析当前注册表得到 33 个唯一 id，状态精确为：

- `conformant`：7；
- `pending_review`：25；
- `known_issue`：1，且唯一是 `SEC-002`。

7 个 conformant 仍是 `AUTH-001`、`DET-002`、`HIL-002`、`PLG-001`、`PLG-002`、`UI-001`、
`MIG-001`。本轮没有因 286 项测试自动晋级其余 25 项。`SEC-002` 明确说明 Local 原生文件可见性只
受任务目录与提示约束，不是操作系统隔离；M7.5 也明确排除不可信多租户、任意宿主文件不可读、真实
远端长期失联、大附件流式和任意新领域科学质量等结论。

`UI-001` 的 conformant 只覆盖固定审批文档优先展示问题/结果/来源/缺口/风险并折叠 raw subject；
架构文档仍公开记录视觉可读性是产品缺陷，没有把结构安全验收扩写成用户体验已完善。

## 6. 独立复验

全部命令串行执行，设置 4 GiB 虚拟内存上限、`MALLOC_ARENA_MAX=2` 和
`PYTHONDONTWRITEBYTECODE=1`：

```text
pytest -q -p no:cacheprovider \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/operations/test_r5_catalog_stages.py \
  tests/operations/test_m5_plugin_ownership_and_default_surface.py \
  tests/operations/test_l6_runtime_capabilities.py \
  tests/operations/test_l2_local_run.py \
  tests/operations/test_m6c_producer_topology_removal.py

# 22 passed in 5.09s
# maximum resident set size 95412 KiB；swaps 0

git diff --check
# 通过

约束 YAML 独立解析
# 33 个唯一 id；7 conformant / 25 pending_review / 1 known_issue
# known_issue = SEC-002

五份 M7.1—M7.4 证据/复审 SHA-256 复算
# 与 M7.5 引用值全部一致
```

## 7. 非阻断问题与后续最小改进

### N1：默认无 Effect 时仍暴露九个 execution Root 工具

`root_tools_for_backend()` 当前只按 Local/Hardened 返回同一 26 项工具；默认核心目录没有 Effect，仍会
让调度模型看到 `execution_capabilities/bind/abandon/cancel/list/status/outputs/start/sync`。这些工具
不能绕过目录创建 Execution，因此不是第二权威或当前正确性缺陷，但会增加默认提示与选项负担。

后续如继续裁剪，最小做法是让平台生成器从已编译目录派生工具投影：没有 Effect 时隐藏 execution
工具；存在 Effect 时整体启用。不要建立第二工具注册表，也不要按 TCAD/plugin 名分支。本项不应在
M7 关闭前临时改动，因为它涉及平台配置、Root MCP 暴露和部署矩阵，需要单独候选与安装回归。

### N2：活动计划页首和决策语料索引的阶段摘要滞后

`R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 页首仍写“实施暂停、M7.2 第 5 项待返工”，
`docs/plans/README.md` 的当前执行链仍停在 TCAD 子链；同一总计划第 16 节和 M7.5 证据已经记录到最终
双审。它们不影响运行字节，也没有形成第二运行权威，但会误导读者。

在两位终审都通过后，应把这两个当前摘要一次更新为 M7/R5-M 完成，并保留所有历史 FAIL/PASS 过程
记录；不要重写历史审查或增加文档状态机。本项属于关闭动作，不构成实现阻断。

### N3：不要扩大当前通过范围

审批 UI 视觉可读性、真正强隔离、真实 Sentaurus/SSH 长任务、多租户、大附件和跨更多学科的科学
质量仍未完成。它们已经被文档和约束注册表诚实列出；后续应以独立需求开展，而不应为了“全部
conformant”在当前主干增加状态或校验器。

## 8. 最终判定

**PASS；阻断项 0。**

当前候选没有残留第二 Operation 注册表、第二普通 Run/current、通用核心领域分支、测试专用生产
补丁或无消费者的新实体；保留的治理复杂度均能对应现有消费者和承重不变量。M7.4 的物理口径与
33 项状态诚实，`SEC-002` 未被偷换为通过。

因此，本审查允许在另一名正确性/跨边界终审者也明确 PASS 后关闭 M7.5、M7 与 R5-M。关闭时只需
更新当前计划页首、进度末项和决策索引，不应再为本轮增加生产机制。
