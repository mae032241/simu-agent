# R5-D 职责拆分与解耦总体独立审查

日期：2026-08-29  
审查性质：未参与实现的组合跨边界、简化性与变更范围审查  
结论：**通过，只放行 R5-E**  
门禁决定：不提前放行 R5-F、R5-G 或宣称 R5 已完成

## 1. 审查边界

本轮不是把 D1—D5 五份单项报告相加，而是重新核对当前精确工作树中五个权威组合后的所有权、
真实运行链、安装态、三重复杂度和目标偏离。当前分支为 `baseline/8765-codex`，工作树包含尚未提交的
R0—R5 累积变化；仓库没有单独的 R5-D Git 基线提交。因此本报告没有用 `git diff HEAD` 冒充 D 阶段
差异，而使用实施记录冻结的 R5-C 起点、R5-0 机械快照、D1—D5 字节证据和当前源码重算来归因。

审查没有修改生产代码、测试、计划或阶段状态；唯一写入是本报告。审查按
`scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 执行。

## 2. EvidenceAudit

### 2.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | 上位计划 `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，SHA-256 `ebba87f2db43622a82bdf8e8c66f89cb55e87febe870bee21fd812ac5b64ef1a`；D 实施记录 SHA-256 `203a24c33aa629f3fa5d186071b23247992c65a1ea6c7db58391d36c2a1bc5ac`。 |
| S2 | 当前架构 `docs/ARCHITECTURE.zh-CN.md`，SHA-256 `570d811adb87a7add86bc85057fba5214145f215bc58f95845c7ce20b8a0dfad`；最小重构权威 SHA-256 `77bb5c36ee71a683b0ffed5adec55968ba0be35d88af5ff0af5f2d7d951b0494`。 |
| S3 | 当前 Root 七文件聚合 SHA-256 `4d13f818b9f02a116e7faf93a88d71bb37374f707d4ae7b2076ac59ad4dbb632`；Task 五文件聚合 `44372849c44472bf907545d11bd6f4c0f214129e00822748bb153da2b9454057`；Worker 三文件聚合 `1671817b4cdcc8297abd25e6129624d372064662129729a4b583dafbc44e125e`。 |
| S4 | 当前通用插件五文件聚合 SHA-256 `2d142ef536a523c2dffd38edacf49087c10138b0262f1f6df6e05cadbafd8a94`；`operations/catalog.py` SHA-256 `e3c99ce16d668b28add304acb218daf725a75850a4cc7f0f3c2ea4951ae7ef47`。 |
| S5 | D1—D5 最终独立报告，SHA-256 依次为 `614f6df8...`、`c87448a2...`、`db5b5cea...`、`2442c300...`、`4e180e8a...`；本轮只把它们作为历史门和字节定位，不继承其结论。 |
| S6 | 当前计量脚本 SHA-256 `453b6e51af8d28b72835b3674e84dd25eaf988238ea315c417bc307d1ab9dee4`；冻结生成器 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；R5-0 快照 `1b397e2d...`；本轮计量输出 `346ced58733dba65119e2cc717d29c563cbb97623fbbd8bde62dbd6746d0c590`。 |
| S7 | D1—D5、安装态和生命周期关键测试文件的当前聚合 SHA-256 `a422b8c9a3089dec9a863ef75473d27a2694c510246a6e59ccec03b8e38686ee`。 |
| S8 | 部署入口 `deploy/install.sh`，SHA-256 `7c956bd766b0fc50ec04f7d03bf6464900c74e7b5a2a44498b9b9dbaeed76bf7`；部署测试 `f035edf5...`。 |
| S9 | 本轮独立运行：100 项组合聚焦、288 项全仓、37 项部署/平台测试，均在 7 GiB 上限下严格串行通过；21 个 D 生产模块编译和 `git diff --check` 通过。 |
| S10 | 本轮独立静态/运行时重算：10 个职责 owner、25 个全局唯一 successor；Root/Task/Worker MRO 与状态拥有者；52 项 full+InGaAs 目录；167 个跨插件组件引用的 dependency/public 闭包；核心领域标记位置。 |

### 2.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `five_authorities_unique` | pass | S1—S4, S7, S9, S10 | Root 只有一个依赖容器，TaskService 只有一个任务/事务权威，Worker 只有一个会话 Router，通用插件只有一个 `PLUGIN` 组装入口，目录只有一个构造点和一个 installed cache。 |
| `responsibility_boundaries` | pass | S3—S5, S7, S10 | route/mixin/声明/编译阶段均按真实变化原因拆分；没有第二数据库、CAS、状态机、目录、运行时发现或持久编译上下文。 |
| `operation_worker_lifecycle` | pass | S2—S4, S7, S9 | `operation_preflight` 与 `operation_invoke` 共用精确准备函数；Agent 创建、精确派发、受控文件、校验、封存和 Artifact 父链仍经过同一 TaskService。 |
| `approval_execution_lifecycle` | pass | S2—S4, S7, S9 | Approval 仍只由 compiled projector 产生固定审查文档并由回环 UI 写决定；Effect 仍复用唯一 ExecutionService/Bridge，未授权提交、幂等同步和输出封存负例通过。 |
| `runtime_and_clean_wheel` | pass | S2—S4, S7—S10 | core、architecture、full、full+InGaAs 的安装态入口、Root/Worker daemon、Codex 配置和显式 runtime plugin 配置均消费同一 compiled catalog；core-only 不加载领域模块。 |
| `cross_plugin_ownership` | pass | S2, S4, S7, S9, S10 | 167 个跨 owner ComponentRef 均有精确 PluginDependency 且目标组件为 public；general science 的资源、组件和 Operation 只有唯一实现所有者，无私有源码跨插件复用。 |
| `complexity_r0` | pass | S1, S5, S6, S9, S10 | 六职责当前 9776/基线 13657，净减 3881 行、28.42%，超过至少 10% 的硬门；全部 successor 全局不重不漏。 |
| `complexity_operations` | pass | S1, S4, S6, S9 | `operations/` 精确 7 文件、2060/2060 行；catalog 阶段仍在同一统计目录，未把实现搬出硬门。 |
| `complexity_production` | pass | S1, S3, S4, S6, S9 | `src/ + plugins/` 当前 143 文件、60263/62533 行，领域迁入插件仍计入；R5-D 自身净增 114 行被完整披露，不冒充删除。 |
| `deployment_accounting` | pass | S1, S6, S8, S9 | `deploy/install.sh` 当前 1021 行；相对 R5-0 的 1026 行少 5 行，相对 8765 的 1008 行多 13 行，单独报告且 37 项部署/平台测试通过。 |
| `occam_and_no_escape` | pass | S1—S6, S9, S10 | D 新增 15 个生产文件但没有新增 service/factory/repository 层；单元增减精确闭合为 +150、+141、+28、-209、+4，总和 +114，未发现未计 successor、兼容 facade 或系统性压行逃逸。 |
| `constraints_and_goal` | pass | S1—S4, S7, S9, S10 | 不可变性、谱系、最小 Worker 上下文、人工决定、副作用、恢复、单一目录、插件隔离和失败关闭未退化；没有新增科研实体、领域流程拓扑或核心插件名/Operation 名分派。 |

## 3. 五个权威组合后的所有权

| 权威 | 唯一有状态/组装对象 | 拆分后的职责模块 | 组合判断 |
| --- | --- | --- | --- |
| Root | `RootToolFacade` | shared + 实例、Operation、Task、Approval、Execution 五个 route | route 无构造器、连接、缓存或服务副本；35 个工具各有一个 route owner，Facade 持有同一组服务和 catalog。 |
| Task | `TaskService` | shared + Worker 文件、证据、compiled output 三个 mixin | 只有 TaskService 构造 SQLite、表、Artifact、Token、catalog 和工作区依赖；三个 mixin 共用同一个 `self` 和事务。 |
| Worker | `WorkerMCPRouter` | protocol + 一个 dispatch mixin | Router 独占 session、锁、已完成标记、可见工具和注册 handler；dispatch 无状态，全部写操作回到 TaskService。 |
| 通用插件 | `general_science_plugin:PLUGIN` | resources、components、Agent、control declarations | 子模块不能发布 entry point、构造 PluginDefinition 或编译目录；66 个组件、17 个 Operation 只在入口冻结组装。 |
| 目录 | `_build_compiled_catalog()` / `compile_installed_catalog()` | normalize、component closure、contract、review/provider、build | 全生产一处 `CompiledCatalog(...)`，一个 `lru_cache(maxsize=1)`；编译数据只存在于一次调用。 |

控制和 Worker broker 仍有按代理身份缓存的传输 Router，但它们不保存 Artifact、Task、Approval、
Execution 或目录事实，也不重新编译 Operation，因而不是第二科学/控制权威。protocol 中保留的隐藏
legacy Worker 工具名只映射到同一 Router、capability 和 TaskService；它们是 D 前已有的符号投影，
没有旧模块转发函数或第二 handler。旧 `general_transform_operations.py` 则已真实删除且无生产引用。

## 4. 跨边界组合链

当前真实链保持为：

```text
同一 CompiledCatalog
  -> Root operation_preflight / operation_invoke 的同一精确绑定
  -> Agent: TaskService -> WorkerMCPRouter -> 受控文件/校验/finalize -> Artifact
  -> Transform: compiled callable -> Artifact 父链与绑定
  -> Approval: compiled projector -> ApprovalService -> 回环 UI 决定
  -> Effect: compiled runtime binding -> ExecutionService/Bridge -> 收集与封存
```

安装态组合测试同时证明：目录对象传给 TaskService 和 Root Facade 时保持对象身份；Worker 从 TaskService
持有的目录解析精确 Agent 工具；runtime factory 只由同一目录取得；显式 TCAD 配置才产生 TCAD
adapter/service。盲插件、未知 Schema、provider 身份漂移、未声明工具、未授权执行和 legacy Root 创建
入口均失败关闭。没有发现只有各单元分开时正确、组合后却绕过准入的路径。

## 5. 复杂度与奥卡姆判断

| 口径 | 8765/R5-0 基线 | R5-C 起点 | R5-D 当前 | 判断 |
| --- | ---: | ---: | ---: | --- |
| R0 六职责 | 13657 | 9485 | 9776 | 相对 8765 减 28.42%；D 内增加 291，来自 Root +150、Task +141。 |
| `operations/` | 2060 | 2056 | 2060 | 等于硬上限；没有迁出。 |
| 全生产 Python | 62533 | 60149 | 60263 | 相对 R5-0 少 2270；D 内净增 114。 |
| 全生产文件数 | 126 | 128 | 143 | D 净增 15 个职责文件，未伪装成代码量下降。 |
| `deploy/install.sh` | 1008（8765）/1026（R5-0） | 未单独冻结 | 1021 | 对两基线分别 +13/-5，保持单列。 |

所以 R5-D 不是新的“净删除阶段”：Root、Task、Worker 和 catalog 的边界胶水共增加 323 行，通用插件
合并重复声明删除 209 行，最终净增 114 行。若只看单文件缩小，确实会得到虚假的减重叙述；当前
successor 聚合阻止了这种说法。

这 114 行仍符合奥卡姆约束：15 个新文件准确对应五组 Root 路由、三个 Task 变化原因、一个 Worker
协议与一个分派原因、四个插件声明原因；没有为每个工具、Schema 或方法建立类。较大的
`task_worker_files.py`（2433 行）、`mcp_root_operation_routes.py`（1313 行）和
`mcp_worker_dispatch.py`（926 行）仍按共享事务/准入原因保留，没有为了目录美观继续拆层。因而当前
实现是有成本但有真实所有权收益的职责拆分，不是把同一权威复制到更多文件。

## 6. 33 项约束族与目标判断

仓库仍没有逐项编号的“33/33”自动验证器，本报告不伪称运行了该脚本。按冻结的行为约束族复核：

- Artifact/CAS 不可变、精确父链、实例绑定和 current/qualification 单一判定未变；
- Worker 的输入、路径、工具、网络、资源和 operation identity 仍从 compiled authority 派生，默认
  拒绝，科学结果只能经受控文件终结；
- 人工决定仍只来自精确 UI 主体，Execution 仍有单一幂等生命周期和未知状态恢复；
- public/support/internal/all 仍是同一目录投影，普通插件不要求核心加入插件、Operation、Schema 或
  角色白名单；
- 核心领域标记只剩四处通用曲线科学 Schema 的内部导入，不在 Root、Task、Worker、catalog 中形成
  领域行动分派；core-only 安装探针不加载 TCAD、curve-score 或 InGaAs 包；
- 没有新增数据库表、持久状态机、顶层注册表、entry-point group、科学实体或静态科研 DAG。

因此本阶段没有把控制层重新变重为第二科研规划器。它只改善代码所有权；科学效果、真实 Codex
子进程摩擦和 TCAD 小任务结果仍属于后续 R5-G，而不是本阶段可由结构测试替代的结论。

## 7. 独立运行记录

全部命令设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1`，严格串行且未超过 8 GiB。

```text
pytest -q <D1—D5、clean-wheel、installed invoke、Agent/Transform/Approval/
          Effect、runtime plugin、Worker exact dispatch、盲插件组合范围>
# 100 passed in 54.71s

pytest -q
# 288 passed in 91.02s

pytest -q tests/artifact_agent/test_deploy_scripts.py \
          tests/artifact_agent/test_platform_configuration.py
# 37 passed in 5.93s

python scripts/r5_current_metrics.py
# R0 9776/13657；operations 2060/2060；生产 60263/62533；deploy 1021

python <全局 successor、MRO、组件公开闭包与 full+InGaAs 目录重算>
# 10 owners / 25 unique successors；167 个跨插件引用全部闭合；52 operations

python -m py_compile <21 个 D 生产模块>
git diff --check
# 均通过
```

没有运行真实 Sentaurus、真实 Codex 平台任务、公网抓取或人工浏览器会话。R5-D 只调整职责归属，未
修改 solver、科学合同或 UI 决定算法；安装态进程、回环 UI、假 Effect adapter 和失败关闭路径已由
本轮测试覆盖。真实科学效果仍是计划明确保留的后续门，不作为当前失败。

## 8. 最终结论

未发现阻断项。五个权威在组合后仍各自唯一；拆分模块没有复制状态、事务、注册表、目录缓存、分派
路径或行为兼容 facade；Agent、Worker、Approval、Execution、runtime plugin、clean-wheel 与跨插件
公开组件链均闭合。三重复杂度硬门通过，D 自身净增 114 行和 15 个文件已被诚实计入，未用横向搬移
冒充净删除；其边界收益足以覆盖该有限胶水成本。

**结论：通过，只放行 R5-E。**
