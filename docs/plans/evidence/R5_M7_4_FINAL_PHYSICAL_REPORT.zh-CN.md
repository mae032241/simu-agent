# R5-M M7.4 最终物理成果与复杂度报告

日期：2026-09-03  
状态：首轮审查 FAIL 后完成四项事实返工；全新独立复审 PASS、阻断 0，M7.4 已完成  
比较基线：R5-M0 冻结工作树  
当前生产树摘要：`d6bfe480ec7b9b724f27c901bce6277da2a2a489dd7823b1f30a7857385078cd`

## 1. 结论摘要

R5-M 没有把旧中央控制器换成另一套包装器。默认运行主干仍是：

```text
编译一个 Operation 目录
→ 绑定输入并建立四态 Run
→ 物化任务目录和角色合同
→ Agent/Transform/Effect 执行
→ 校验并封存 Artifact
→ 仅按 Operation 声明进入独立审查、人工决定或外部执行
```

相对 M0，生产 Python 从 146 文件、50,023 行变为 141 文件、47,177 行，净减 5 文件、2,846 行
（5.69%）。对 8765 基线中六个集中责任作保守的整文件后继追踪，当前为 7,062 行，较原
13,657 行减少 6,595 行（48.29%）。这里已把旧 Task 的职责计入 Run、输出、工作区和工具上下文，
把旧角色/调度责任分别计入整个 Codex 平台文件和 scheduler prompt；它是防止“移文件冒充删除”的
保守物理口径，不是全系统语义复杂度得分。

这不是“所有代码都轻”。TCAD、曲线分析、审批和 Run 仍包含真实领域/可靠性复杂度；本报告把它们
与默认路径、可选路径和已经删除的控制复杂度分开列出，不以总行数替代架构判断。

## 2. 实际文件与物理行变化

### 2.1 各阶段净变化

下表是每一阶段前后生产 Python 实物的净变化。它包含同阶段的删除、增加和文件内重写，因此不把
“净减少”冒充“总删除量”。

| 阶段 | 文件变化 | 行数变化 | 主要原因 |
|---|---:|---:|---|
| M1 | -5 | -1,144 | 删除死 Schema、未注册工具、重复事件和在线清除面 |
| M2-01 | 0 | +122 | 用一个参数证据包闭合 Agent 单输出，并增加确定性展开 |
| M2-02 | -1 | -46 | 删除曲线专用 Worker 工具/双层结果，复用确定性分析 |
| M2-03 | +2 | +63 | 把非默认论文图纵向能力迁为一个可选插件 |
| M3 | 0 | -621 | 删除四类 TransformAdapter、profile 分发和 legacy 包装 |
| M4 | -2 | -969 | 删除无消费者知识 reducer、Schema 和伪科学晋级桥 |
| M5 | 0 | -39 | 统一组件所有权并令非默认运行产品惰性加载 |
| M6 | +1 | -419 | 直接实例管理取代三套伪审批；收敛准入、拓扑预测和 Effect 审批断点 |
| M7 | 0 | +207 | Local 软隔离、恢复上限、真实探针和未知提交权威查回 |
| **合计** | **-5** | **-2,846** | **146/50,023 → 141/47,177** |

### 2.2 整个生产模块删除与新增

R5-M 实际退役的八个完整生产模块为：

- `artifact_agent/schema/discovery.py`；
- `artifact_agent/schema/decision.py`；
- `artifact_agent/schema/pdf_excerpt.py`；
- `artifact_agent/schema/web_evidence.py`；
- `artifact_agent/web_fetch.py`；
- `curve_score/worker_tool.py`；
- `artifact_agent/schema/knowledge.py`；
- `artifact_agent/schema/hypothesis.py`。

新增的三个完整生产模块为：可选 `curve_figure_evidence` 插件的两个 Python 文件（当前 58 行），以及
直接实例管理模块（当前 145 行）。M7 没有再增加生产文件。文件内删除还包括 Task 生命周期、旧
TransformAdapter、事件日志、生产者下游用途预测、分散资格字段和多个兼容桥；其净变化已经计入
上表。

当前物理分布为：

| 范围 | 文件 | 行数 |
|---|---:|---:|
| `src/scidiscovery` | 95 | 24,756 |
| `plugins` | 46 | 22,421 |
| 合计 | 141 | 47,177 |

最大的文件现在主要是 TCAD 工程打包、曲线 Schema/分析、参数操作、审批、Run 和执行控制。仍超过
一千行的通用控制文件包括 `approvals.py`、Root Operation 路由和 scheduler bindings；它们是后续
维护热点，但本轮没有证据表明再拆文件本身会减少权威或行为，因此不为满足行数目标增加包装层。

## 3. 删除、退出默认面与保留必须分开

| 能力 | 是否随核心安装 | 默认是否注册/实例化 | 默认是否导入 | 当前处置 |
|---|---|---|---|---|
| `builtin + general_science` | 是 | 是 | 是 | 核心发行的两个固定入口，共同提供领域无关基座 |
| 曲线能力 | 否，独立 wheel | 安装后注册 | 未安装时否 | 领域插件 |
| TCAD 能力 | 否，独立 wheel | 安装后注册 | 未安装时否 | 领域插件 |
| 论文图提取/审查/bundle | 否，独立可选 wheel | 默认核心不注册，显式选择后注册 | 否 | 真正退出默认安装与目录的可选插件 |
| Hardened 后端 | 随核心源码分发 | 默认 Local 不实例化 | 普通 Local 启动不导入 | 显式后端策略，不伪称已物理拆包 |
| portable 管理 | 随核心源码分发 | 仅管理命令启用 | 普通 CLI/runtime 不导入 | 惰性管理表面 |
| TCAD socket/command/SSH/远端 runner | 随 TCAD wheel 分发 | 只实例化配置选中的 transport | 普通启动不导入未选 transport | 一个领域插件内的可选运行产品 |

因此，“一个注册入口”不是说所有代码都默认加载。统一入口只负责编译声明；安装、注册、实例化和
导入是四个不同事实。

## 4. 控制面可数事实

### 4.1 Root、表与状态

| 指标 | M0 | 当前 | 解释 |
|---|---:|---:|---|
| Root 公共工具 | 30 | 26 | 删除实例 prepare/status/select 和手工 Effect 审批创建；未增加替代入口 |
| 默认通用数据库表 | 20 | 15 | 删除两个重复事件表和三个实例/会话提案候选表 |
| Hardened 额外私有表 | 1 | 1 | 只在显式后端存在，不属于 Local 默认状态 |
| Run 状态 | 4 | 4 | 仅 `queued/running/completed/failed` |
| Execution 状态 | 10 | 10 | 只在声明 Effect 时使用；未把它塞进普通探索 Run |

当前 15 张通用表按责任分为：Artifact 3、Scheduler/current 5、Run 2、Approval 4、Execution 1。
显式 TCAD controller 自有一张 `submissions` 表，不进入通用数据库。current 没被删除：精确科学 head
仍由 `scheduler_scientific_selections` 承担，Run 恢复则由新 Run、失败 Run 和冻结草稿承担，两者不
混成一套 checkpoint 状态机。

### 4.2 Operation 合同与目录

下表比较的是 M0 与当前的同一“显式 TCAD+InGaAs、未启用论文图”五插件组合，不是安装器默认目录：

| 指标 | M0 显式五插件 | 当前显式五插件 |
|---|---:|---:|
| `InputPortSpec` 字段 | 16 | 12 |
| `OutputPortSpec` 字段 | 18 | 17 |
| `OperationSpec` 字段 | 11 | 12 |
| 三者合计 | 45 | 41 |
| 组件 | 220 | 186 |
| Operation | 46 | 43 |
| public/support/internal | 26/20/0 | 24/19/0 |
| Agent/Transform/Approval/Effect | 22/20/3/1 | 20/19/3/1 |

`OperationSpec` 增加的唯一字段是可选 `input_admission`，它取代了每个输入端口重复的 cohort、审批
类型、选项和 provider 四个字段；不是新增第二准入体系。当前 12 个顶层字段仍覆盖身份、用途、执行
器、输入输出、后果、可选准入/审查/guard/资源上限。继续强行压成一个巨型字典只会失去编译期合同，
真正的安装器默认核心只安装 `builtin + general_science`，当前为 63 组件、14 Operation
（11 public/3 support；10 Agent/3 Transform/1 Approval/0 Effect）。显式曲线组合为 103/22；
曲线加论文图为 116/25；显式 TCAD（含曲线依赖）为 180/42；再加 InGaAs 为 186/43；最后再显式
加入论文图才是 199/46。所有组合仍由一个 `compile_catalog` 事务产生；`public/support/internal`
只是同一目录投影，不是三个注册表。

## 5. 插件接入劳动

M7.1 的盲 CSV 插件是不修改核心和 Scheduler 的最小异领域实例。它的有效源码为 4 个 Python 文件、
353 行，加一个 17 行 `pyproject.toml`：

- 一个 `PluginDefinition` 和一个标准 entry point；
- 一个领域 Schema/输出校验器；
- 一个只属于该 Operation 的领域工具；
- 两个 Agent Operation（作者与精确独立审查者）及其 review edge。

干净 wheel 安装后，同一入口可在 Local 和显式 Hardened 后端编译并完成 Run；核心没有 CSV 或插件名
分支。这个结果证明注册机制不要求修改多张注册表，但不应夸大为“任意科学领域只需几十行”：353 行
中包含该领域自己的合同、工具和测试夹具，复杂 TCAD 插件仍需承担真实 solver 工程能力。

TCAD、曲线、论文图和盲 CSV 的共同接入成本只有：声明组件与 Operation、提供实现、在一个 entry
point 注册。它们不需要另写 Scheduler、Root 路由、current、资格表、UI renderer 或 Worker 生命周期。

## 6. 有意放弃的内部兼容行为

本轮按计划不保留下列旧内部接口的兼容别名、双写或自动迁移：

- `scidiscovery.agent_role_packs`、`transform_adapters` 和已损坏的旧 operation entry point；
- `TaskService`、中央 Worker service、旧 task/attempt/session/token 文件协议；
- `artifact_transform`、手工 `approval_request_create`、手工
  `execution_approval_request_create` 等绕过统一 Operation 的入口；
- 只写不读的 Artifact/Approval event 日志和在线删除 API；
- 旧 profile TransformAdapter、`TransformOutput` 二次包装和 `_legacy()` 领域桥；
- 没有真实消费者的知识状态 reducer、伪科学晋级状态与旧内部 Schema；
- 实例创建/选择的提案审批对象和旧资格向新 revision 的继承。

旧只追加 Artifact、审查决定和 Execution 事实没有被静默升级。M1 只允许精确旧 v1 事件表以只读
形状存在；未知旧表或结构漂移仍失败关闭。这里放弃的是未发布 Python/内部协议兼容，不是科学来源、
父链、人工决定或外部副作用可追溯性。

## 7. 33 项约束现状

注册表仍精确包含 33 项：7 项 `conformant`、25 项 `pending_review`、1 项 `known_issue`。

当前明确 `conformant` 的是：`AUTH-001`、`DET-002`、`HIL-002`、`PLG-001`、`PLG-002`、`UI-001`、
`MIG-001`。它们分别对应唯一控制权威、确定性程序不替代科学判断、资格/执行授权分离、核心无领域
分支、插件可组合、审批层次和旧资格不升级。

唯一 `known_issue` 是 `SEC-002`：可信 Local Agent 的原生文件可见性目前依赖任务目录和提示约束，
不是操作系统强沙箱。领域 MCP、提交、Artifact、review、approval 和 Effect 仍有服务端硬门，但不能
据此宣称跨目录读取在技术上被禁止。

25 项 `pending_review` 不是失败，也不会因最终回归数量自动晋级；主要未关闭范围包括真实远端长期
执行/失联恢复、通用大附件流式输入、多租户强隔离、更多科学领域的质量验证以及发布代际证明。
M7.5 的终审只能更新有直接证据的项目。

## 8. 验证

结构数据由 `scripts/r5_current_metrics.py`、独立 AST/Pydantic/SQLite 探针和生产树哈希共同得到：

- 生产 Python `141/47,177`；
- 8765 六个集中责任的保守整文件后继集合 `7,062` 行，其中旧 Task 后继为 `3,101` 行；
- operations 包 `8/2,100`，唯一目录编译器 `734` 行；
- 通用核心领域 token 命中 `0`；
- Root `26`，fresh DB `15`，字段 `12/17/12`；
- 默认核心目录 `63` 组件、`14` Operation；显式 TCAD+InGaAs 组合为 `186/43`；
- 33 项状态为 `7/25/1`。

结构、插件默认面、实例/current、准入边界和 successor 唯一性的修订后串行回归为
`39 passed in 15.91s`，峰值常驻内存 `104164 KiB`、无 swap；M7.3 的 `82 passed` 和独立 PASS
作为相邻行为证据保留。

## 9. M7.4 阶段判断

本报告证明：默认控制主干的权威和实体数量实际下降；可选能力没有被混报成删除；新领域可通过单一
插件入口接入；current、四态 Run、Artifact、独立审查、人工决定和 Effect 边界仍在。它也诚实保留
大领域实现、部分千行责任文件和 `SEC-002` 限制。

全新独立复审者已复算数字、检查默认导入/注册边界并串行运行 39 项结构测试，结论 PASS、阻断 0；
据此关闭 M7.4 并放行 M7.5。行数本身不构成通过条件。
