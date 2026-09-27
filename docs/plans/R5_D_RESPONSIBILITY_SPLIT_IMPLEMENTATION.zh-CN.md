# R5-D：删除后的职责拆分与复杂度收口记录

状态：完成；R5-D 总体独立审查通过，只放行 R5-E。

日期：2026-08-29  
上位计划：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`

## 1. 目的与边界

本阶段不增加科学行为、权限、注册入口、数据库表或状态机，只拆分 R5-A—C 删除后仍具有独立
变化原因的代码。所有新模块共享原有服务对象和同一个 `CompiledCatalog`；不得缓存目录、复制
Artifact/Task/Approval/Execution 状态或建立第二分派表。

执行单元及门禁：

| 单元 | 范围 | 状态 | 独立审查门 |
| --- | --- | --- | --- |
| D1 | Root 的实例/清单、Operation、Task、Approval、Execution 路由 | 第二轮独立审查通过 | 只放行 D2 |
| D2 | Task 生命周期、Worker 文件协议、compiled output、证据摘录 | 独立审查通过 | 只放行 D3 |
| D3 | Worker Router 与文件/PDF/表格/图像/领域工具 handler | 独立审查通过 | 只放行 D4 |
| D4 | 通用插件资源、组件、Agent、Transform/Approval 声明 | 独立审查通过 | 只放行 D5 |
| D5 | Catalog 规范化、闭包解析、合同/图校验与摘要构建 | 独立审查通过 | 只放行 R5-D 总审 |
| 总审 | 三重复杂度、clean-wheel、全仓回归与目标偏离 | 独立审查通过 | 只放行 R5-E |

## 2. 冻结起点

R5-C 通过候选：

- 全仓：`270 passed in 84.43s`；
- `src/scidiscovery/operations/`：7 文件、2056 行，不高于 R5-0 的 2060 行；
- R0 六职责聚合：9485/13657 行；
- 全生产 Python：128 文件、60149/62533 行；
- 当前大文件：`mcp_root.py` 2885 行、`tasks.py` 6077 行、`mcp_worker.py` 1241 行、
  `general_science_plugin.py` 1791 行、`general_transform_operations.py` 760 行、
  `catalog.py` 636 行。

上述行数只用于防搬移和观察新增胶水；不得通过压缩多语句、改名或迁入未统计目录获得通过。

## 3. 每单元共同完成条件

1. 新模块只有一个变化原因，具有生产消费者和拥有者测试；
2. 原服务对象、事务、CAS、目录与目录编译结果身份保持唯一；
3. 真实 `operation_invoke`、Worker 文件生命周期、审批和执行路径不经兼容 facade；
4. 最小聚焦测试、`git diff --check` 与全仓串行回归通过；
5. 独立审查者同时判定正确性、33 项约束族、奥卡姆原则和通用 AI 科学家目标未偏离；
6. 未通过时只修当前单元，不开始后续单元。

## 4. 进度记录

- 2026-08-29：R5-C 第三轮审查通过，建立本记录；D1 开始，后续单元保持冻结。
- 2026-08-29：D1 将根入口拆为实例/清单、Operation、Task、Approval、Execution 五个无状态
  路由类和一个无状态共享辅助模块。`RootToolFacade` 仍是唯一依赖容器，继续直接持有同一组
  Artifact、Task、Approval、Execution、Binding、CompiledCatalog 与创建锁；各路由没有
  `__init__`、缓存、注册表、服务副本或持久状态。
- 目录工具名、输入 DTO、MCP 解码和公共辅助仍由原根入口拥有；35 个根工具各有且只有一个
  路由所有者。新增结构测试核对工具集合恰好闭合、路由无状态、Facade 的依赖对象保持身份相同。
- R5-0 的 `scripts/r5_baseline_metrics.py` 及其冻结哈希保持不变；新增
  `scripts/r5_current_metrics.py` 只覆盖当前后继路径集合，把七个根职责文件全部聚合到原
  `mcp_root.py` 所有者，避免用拆文件获得虚假减重。D1 根职责由 2885 行变为 3035 行，增加的
  150 行是模块边界、显式导入和结构门禁所需胶水；全生产 Python 由 60149 行变为 60299 行，
  仍低于 R5-0 的 62533 行；按全部后继聚合的 R0 六职责当前值是 9635/13657 行。该净增必须由
  独立审查判断是否符合奥卡姆原则，不以单文件缩小冒充复杂度下降。
- 验证证据：根结构与冻结计量专项 `11 passed in 35.02s`；根真实调用、Agent 生命周期、审批
  与 Effect 聚焦回归 `42 passed in 31.85s`；最新全仓串行回归
  `274 passed in 88.79s`；`git diff --check` 与七个根模块 `py_compile` 通过。D2 尚未开始。
- D1 第一轮独立审查结论为“打回”：路由实现本身通过，但当前计量 overlay 的职责明细虽正确，
  `r0_core.r5_0_total` 仍只统计拆分后的入口文件，错误显示 7135。已按最小修复令当前口径从六个
  owner 的 successor 总量统一生成，并新增 Root=3035、六职责总计=9635、每个后继恰计一次的
  精确测试；冻结生成器和快照未修改。修复后仍须独立复审，D2 继续冻结。
- D1 第二轮独立复审结论为“通过，只放行 D2”。审查者独立确认 12 个 R0 successor 全局唯一、
  六职责聚合 9635/13657，复跑同范围 15 项测试通过；报告为
  `reviews/R5_D1_ROOT_ROUTES_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`。D2 开始，D3 及以后保持冻结。
- 2026-08-29：D2 保留 `TaskService` 为唯一状态、数据库、事务、任务生命周期和 CAS 权威；将
  已有方法按变化原因机械拆入三个无状态混入：`TaskWorkerFilesMixin` 负责受控工作区、文件编辑、
  checkpoint 与封存协议，`TaskEvidenceMixin` 负责只读输入、PDF 摘录和 Web 证据，
  `TaskCompiledOutputMixin` 负责 compiled output 合同、验证、最终化和 Artifact 登记。
  `task_shared.py` 只保存原有错误类型、不可变视图、内部不可变值和跨职责纯函数；所有混入都没有
  `__init__`、数据库连接、服务副本、缓存、目录或注册表，继续通过同一个 `TaskService.self` 使用
  原 ArtifactService、TaskTokenService、CompiledCatalog 和同一个 SQLite 事务边界。
- D2 方法所有权为：生命周期本体 40、Worker 文件 30、证据/输入 8、编译输出 24；四者没有重名
  覆盖。TCAD runtime 插件已经使用的 `AgentTask`、`_WorkspaceSnapshotFile` 和
  `_write_control_output_file` 继续从原模块显式导出，未建立兼容执行路径。
- 当前计量覆盖层把 `tasks.py` 及四个后继文件恰好一次聚合到原 Task owner。Task 职责由 6077 行
  变为 6218 行（+141）；R0 六职责当前为 9776/13657，全生产 Python 为 138 文件、60440/62533
  行，operations 包仍为 2056/2060。独立审查必须判断 141 行边界胶水是否值得，不以单文件从
  6077 缩到 1876 行冒充减重。
- D2 验证候选：结构、Root 计量、精确派发、Worker 权限和通用科学 Agent 聚焦回归
  `25 passed in 34.29s`；最新全仓串行回归 `277 passed in 84.91s`；五个 Task 模块
  `py_compile`、未解析全局符号检查及 `git diff --check` 通过。D3 尚未开始。
- D2 独立审查结论为“通过，只放行 D3”。审查者独立聚焦 `29 passed in 36.70s`、全仓
  `277 passed in 93.14s`，确认唯一 TaskService/SQLite/事务权威、三混入无状态、旧导出和 TCAD
  窄访问闭合，+141 行边界成本可接受。报告为
  `reviews/R5_D2_TASK_RESPONSIBILITY_INDEPENDENT_REVIEW.zh-CN.md`。D3 开始，D4 以后保持冻结。
- 2026-08-29：D3 只拆两个真实变化原因，没有按文件/PDF/表格/图像为每种工具建立类。
  `mcp_worker_protocol.py` 拥有原输入 DTO、16 个公开内建工具投影、兼容工具投影、capability 映射
  与编译组件常量；`mcp_worker_dispatch.py` 的一个无状态混入拥有原授权后分派、注册领域工具调用、
  内建文件/PDF/表格/Web/分析 handler 和纯辅助函数。`WorkerMCPRouter` 仍是唯一进程状态容器，
  独自持有 TaskService、worker/proxy/dispatch capability、会话、完成标记、锁、可见工具、注册
  handler 与 handler 局部状态；未新增服务、目录、注册表、状态机或执行路径。
- 所有既有 `mcp_worker:..._TOOL` 编译实现字符串继续从原模块解析到同一 protocol 对象；
  `WORKER_TOOLS` 仍为同一 16 项元组。Web 网络权威测试的 monkeypatch 改指实际 handler 所有者，
  没有在旧模块增加兼容代理或第二 fetch 路径。
- Worker 职责由 1241 行变为 1269 行（Router 105、protocol 238、dispatch 926，净增 28）；全生产
  Python 为 140 文件、60468/62533 行，Task/R0 六职责口径保持 6218 与 9776/13657，operations
  包保持 2056/2060。D3 聚焦回归 `29 passed in 35.41s`，最新全仓串行回归
  `280 passed in 88.24s`；三模块 `py_compile`、未解析全局符号检查和 `git diff --check` 通过。
  D4 尚未开始。
- D3 独立审查结论为“通过，只放行 D4”。审查者独立复跑聚焦 15 项和全仓 280 项均通过，确认
  Router 仍是唯一进程状态及授权入口，protocol/dispatch 无状态，TCAD、曲线和网络工具的真实
  handler 路径未改变，净增 28 行可接受。报告为
  `reviews/R5_D3_WORKER_ROUTER_INDEPENDENT_REVIEW.zh-CN.md`。
- 2026-08-29：D4 删除仅作内部聚合的 `general_transform_operations.py`，按四个真实变化原因形成
  `general_science_resources.py`（Schema、提示和语义合同资源）、
  `general_science_components.py`（codec、validator、guard、projector、transform 实现及唯一组件
  冻结元组）、`general_science_agent_operations.py`（十个 Agent Operation 声明）和
  `general_science_control_operations.py`（六个 Transform 与一个 Approval Operation 声明）。
  `general_science_plugin.py` 缩为 19 行唯一组装入口；四个子模块均无 `PluginDefinition`、entry
  point、目录编译、运行时发现或 `PLUGIN` 对象。
- 拆分前后组件 ID 集合保持 66 项且唯一，Operation ID 集合保持 17 项且唯一，其中 public 11、
  support 6，执行器为 Agent 10、Transform 6、Approval 1。所有资源实现路径指向资源所有者，
  codec/validator/guard/projector/transform/workspace 指向组件所有者，四个 Worker tool 继续指向唯一
  Worker protocol 实现；插件公开面仍精确为十个组件。
- 当前计量将入口/资源/Agent 声明聚合到原 `general_science_plugin.py` owner（1009 行），将组件与
  Transform/Approval 声明聚合到已删除的 `general_transform_operations.py` owner（1333 行），
  两组后继不相交，总计 2342 行，相对拆分前 2551 行净减 209 行。R0 六职责仍为 9776/13657，
  operations 包仍为 2056/2060；全生产 Python 为 143 文件、60259/62533 行。
- D4 新增结构门验证唯一入口、子模块无第二插件/目录、冻结元组闭合、实现路径归属、公开面和计量
  不重不漏。首次聚焦回归发现审批投影器迁移漏导入 UI 文档类型，已在组件所有者内最小修复；
  修复后完整 D4 聚焦回归 45 项通过。首次全仓回归发现一个目录负例仍引用已删除模块中的旧
  workspace 路径，以及 D3 测试越权冻结了全生产文件/行数；前者改指实际组件所有者，后者收窄为
  D3 真正拥有的 Worker 聚合和 operations 包不变门，没有增加兼容别名。修复专项 6 项通过，最新
  全仓串行回归 `284 passed in 89.07s`；五个声明模块 `py_compile`、AST/symtable 解析与
  `git diff --check` 通过。D4 实现候选等待独立审查，D5 尚未开始。
- D4 独立审查结论为“通过并只放行 D5”。审查者独立复跑聚焦 61 项、全仓 284 项，确认唯一
  entry point/PluginDefinition/组装权威、66 个组件、17 个 Operation、11/6 public/support、
  10/6/1 Agent/Transform/Approval 与十项公开跨插件组件闭合；旧变换模块无生产或动态入口残留，
  clean-wheel 路径未退化。计量 1009+1333=2342，相对 2551 净减 209，25 个既有 successor 无
  重叠。报告为 `reviews/R5_D4_GENERAL_PLUGIN_DECLARATIONS_INDEPENDENT_REVIEW.zh-CN.md`。
  D5 开始，R5-D 总审及以后继续冻结。
- 2026-08-29：D5 没有为目录编译再建子包、service 或持久编译上下文，而是在原
  `operations/catalog.py` 内将 500 余行一体化 `compile_catalog` 提取为五个启动期阶段：声明
  规范化与组件加载、显式组件闭包解析、Operation 合同/权限模板校验、review/provider 图校验、
  摘要与不可变目录构建。`compile_catalog` 现在只有三次阶段赋值和一次返回；全模块只有
  `_build_compiled_catalog` 一处构造 `CompiledCatalog`，只有 `compile_installed_catalog` 一处
  `lru_cache`。阶段数据均为一次编译调用内的显式参数和返回值，没有模块级可变容器、在线 registry
  或第二 installed cache。
- 拆分前后四组目录的 Operation 数量与聚合摘要逐字不变：core 17 项
  `5ac717e6...`，架构夹具+core 20 项 `926e843f...`，full 51 项 `0cc88d23...`，
  full+InGaAs 52 项 `c80c94fa...`。新增结构门独立调用各阶段，核对输入 PluginDefinition 不被
  修改、唯一构造/缓存、无模块级可变注册表、core 冻结摘要和复杂度口径。
- `catalog.py` 由 636 行变为 640 行，净增 4 行；整个 `operations/` 包精确为 R5-0 硬门
  2060/2060 行，全生产 Python 为 143 文件、60263/62533 行。增加的四行对应四个新阶段边界；
  未把逻辑迁出统计目录，也未压缩多语句换取通过。目录阶段/全部目录正负例聚焦 51 项通过；首次
  全仓回归只发现 D3 Worker 测试越权冻结 D5 的 operations 行数，已删除该跨阶段重复断言，D5
  自有精确 2060 行硬门保持不变；修复专项 50 项通过，最新全仓串行回归
  `288 passed in 90.86s`。`py_compile`、四组摘要复算与 `git diff --check` 通过。D5 候选等待
  独立审查，R5-D 总审尚未开始。
- D5 独立审查结论为“通过，只放行 R5-D 总审”。审查者独立复跑聚焦 71 项、全仓 288 项，
  精确复算四组数量/摘要，确认全生产只有一处 `CompiledCatalog` 构造、一个 installed cache、无
  模块级可变注册表；组件闭包 public/private/kind 负例、计量与 `git diff --check` 均通过。报告为
  `reviews/R5_D5_CATALOG_STAGES_INDEPENDENT_REVIEW.zh-CN.md`。R5-D 总审开始，R5-E 继续冻结。
- R5-D 总体独立审查结论为“通过，只放行 R5-E”。审查者独立复跑组合聚焦 100 项、全仓
  288 项、部署与平台 37 项；确认十个职责 owner/25 个 successor 全局唯一，Root、TaskService、
  Worker Router、general-science Plugin 和 CompiledCatalog 五个权威组合后仍唯一，full+InGaAs
  的 52 个 Operation 与 167 个跨插件 ComponentRef 闭合。三重计量为 R0 六职责 9776/13657
  （净减 28.42%）、operations 2060/2060、全生产 60263/62533，deploy 单列 1021 行。
- 总审同时诚实记录 R5-D 自身因边界胶水净增 114 行、增加 15 个生产文件（D1 +150、D2 +141、
  D3 +28、D4 -209、D5 +4）；因此不宣称“拆分本身继续净减重”。审查结论是新增边界对应真实变化
  原因，未形成第二状态、事务、注册表、缓存、分派或行为兼容 facade，奥卡姆门仍通过。报告为
  `reviews/R5_D_OVERALL_DECOUPLING_INDEPENDENT_REVIEW.zh-CN.md`。R5-D 完成，R5-E 开始。
