# R5-E：运行时插件早期门禁与双进程配置证明实施记录

状态：第二轮独立复审通过，只放行 R5-F；R5-E 已冻结，R5-G 未开始。

日期：2026-08-30  
上位计划：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`

## 1. 本阶段回答的问题

R5-E 只回答两个启动期问题：已安装并声明运行时工厂的插件是否都在本进程成功完成配置与贡献
构建；control 与 Worker 两个实际进程是否使用了同一份编译目录和同一组原始配置字节。它不判断
科学内容，不证明求解器能力，也不增加在线协调。

冻结边界如下：

- `CompiledCatalog` 仍是唯一插件与 Operation 目录；只增加不可变的运行时插件编号、配置 Schema
  摘要和目录整体摘要投影，没有第二注册表或可变状态；
- `operations/runtime_plugins.py` 只保留领域插件实现需要的工厂上下文、贡献和工厂协议；配置文件
  读取、启动装配和健康探针归应用启动模块
  `artifact_agent/runtime_plugin_bindings.py`，不污染 Operation 编译包；
- Root 只检查本地 Effect adapter；Worker 只在领取任务前检查本地声明服务；二者均不在逐请求
  路径读取对端摘要；
- 摘要文件位于 systemd `RuntimeDirectory`，不是 Artifact、数据库记录、capability、科学对象或
  runtime registry。

## 2. 实现结果

### 2.1 编译目录的最小运行时投影

`CompiledCatalog` 新增三个只读能力：

- 枚举声明 runtime factory 的已安装插件编号；
- 读取其配置 Schema 资源的 SHA-256；
- 对排序后的 Operation 编译摘要和每个运行时插件的完整递归声明身份摘要计算目录整体摘要。

目录编译同时验证配置 Schema 资源是带非空 `$id` 的 JSON 对象。工厂和配置 Schema 必须成对
声明，既有闭包、依赖、公开组件和未使用组件门仍由同一次编译处理。目录没有保存配置路径、配置
内容、adapter 实例或进程可用状态。

### 2.2 启动装配与失败关闭

control/Worker daemon 共同调用唯一启动装配函数。它要求配置 assignment 的插件集合精确等于
当前目录中声明 runtime factory 的插件集合；随后按插件编号排序执行：

1. 以 `O_NOFOLLOW` 打开不超过 1 MiB 的普通配置文件；
2. 验证原始字节是 JSON 对象；
3. 调用该插件同一个编译工厂，由领域工厂完成严格领域 Schema/条件校验并构建本进程贡献；
4. 校验贡献只使用局部绑定名，再加编译插件编号形成全限定 adapter/service 名；
5. 只在全部工厂构建成功后产生
   `(plugin_id, configuration_schema_digest, raw_config_sha256)`。

缺配置、未知插件、重复 assignment、损坏 JSON、符号链接、错误工厂结果和无效局部绑定都会在
daemon 建立 socket 前失败。Worker 工厂声明需要可信 TaskService 时，只有 Worker 启动装配会
获得该精确服务；control 不会获得它。

### 2.3 两个实际进程的摘要与部署健康门

两个 daemon 都新增必填 `--runtime-summary`。只有目录编译、配置读取、领域校验和贡献构建全部
成功后，进程才以 `0640` 权限原子替换摘要。摘要只含：

- `schema_version` 与进程模式；
- 当前目录整体摘要；
- 排序后的插件编号、配置 Schema 摘要、原始配置字节摘要。

systemd 模板把文件固定到：

- `/run/scidiscovery/runtime-summary.json`；
- `/run/scidiscovery-worker/runtime-summary.json`。

安装健康检查在两个 socket 可用后运行同一模块的只读探针。探针拒绝缺失、符号链接、非普通
文件、非 `0640`、超限、字段漂移、模式错误、目录摘要不等于当前安装目录、插件集合或任一三元组
不一致。探针不重读插件配置，不连接 daemon，也不写控制状态。由于两个 daemon 都要求当前目录
的完整运行时插件配置，比较的是同一完整集合，而不是宽松的部分交集。

### 2.4 调用前的本地可用性

- `operation_catalog` 对 Effect 显示其全限定 adapter 及 `available/unavailable`；对需要 Worker
  service 的 Agent 明确显示服务清单与 `verified_on_worker_claim`，不虚构 Root 已观察到对端；
- `operation_preflight` 在 Effect adapter 缺失时返回专门的
  `runtime_binding_unavailable`，不再误报科学输入或工程准备错误；
- `WorkerMCPRouter` 从当前 Agent Operation 的编译工具合同求出所需服务，在调用 TaskService
  领取任务前失败关闭。服务齐全时仍走原 `claim_next/claim_exact` 和原文件生命周期。

TCAD capability 的 adapter、profile、solver kind 与冻结字节校验没有被摘要替代。

## 3. 实施中发现并修正的问题

首轮实现把只读健康探针放入 `operations/` 新模块，功能测试通过，但全仓结构门发现这会把
Operation 编译包从冻结的七个文件扩为八个文件。这违反 R5-D 的包级复杂度约束，未通过候选没有
提交审查。

修正后：

- 删除该 Operation 子模块；
- 把启动配置、摘要和健康探针统一归入应用启动装配模块；
- 把 `operations/runtime_plugins.py` 收缩到 61 行纯协议；
- `operations/` 保持七个文件并从 2060 行降至 2016 行。

这次修正没有放宽冻结测试，也没有保留导入兼容 facade。

首轮独立审查随后发现第二个、也是该轮唯一阻断：原目录整体摘要对运行时插件只绑定插件编号与
配置 Schema 字节摘要，因此合法的零 Operation runtime-only 插件只改变插件版本或 factory
ComponentSpec 时，目录摘要不会变化。该反例意味着双进程探针尚不能证明“同一编译目录”。首轮
报告为 `reviews/R5_E_RUNTIME_PLUGIN_GATE_INDEPENDENT_REVIEW.zh-CN.md`，结论为“打回，不放行
R5-F”。

最小修复仍位于同一次目录编译：每个运行时插件新增不可变声明身份摘要，绑定插件编号与版本、
配置 Schema 与 runtime factory 的完整递归组件闭包（全限定编号、提供插件版本、完整
ComponentSpec、资源摘要），以及 `requires_worker_task_service` 静态权限合同；不散列 callable，
不增加注册表。目录整体摘要同时
编码该身份摘要。新增两个合法零 Operation 负例，分别证明版本漂移和 factory 实现定位漂移会
改变目录摘要；另由实际 control/Worker daemon 分别使用两种漂移目录写摘要，健康探针均失败
关闭。修复后 Operation 包仍为七个文件、2053/2060 行。

## 4. 验证证据

新增专项覆盖：

- 真实 control daemon 对缺配置、损坏配置、符号链接、重复 assignment、错误插件编号全部在摘要
  与 socket 建立前拒绝；
- 真实 control/Worker daemon 使用同一 TCAD 工厂成功构建贡献并分别写出实际摘要；
- 对 Worker 仅改变 JSON 空白、保持语义对象不变时，原始字节摘要漂移并被健康探针拒绝；
- Worker 缺少 TCAD 调试服务时，`claim_next` 调用次数保持为零；配置服务后领取成功；
- Root 目录正确显示 Effect 可用/不可用，缺 adapter 的精确预检返回
  `runtime_binding_unavailable`；
- core clean-wheel 的两个 daemon 真实入口使用空插件集合写摘要，full 与冻结 E2E Effect 入口继续
  通过。

验证结果：

- R5-E 运行时、目录、clean-wheel 与部署聚焦回归：`51 passed`；
- 结构纠偏后的冻结目录与实际 Effect 专项：`10 passed`；
- runtime-only、本地/跨插件递归身份、实际双 daemon 与目录专项：`12 passed in 2.14s`；
- 最终全仓串行回归：`296 passed in 91.70s`；
- 无落盘 AST 语法解析、`git diff --check`、`bash -n deploy/install.sh` 通过。

所有命令均串行并在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2` 下运行。

## 5. 当前复杂度与非扩张证明

- R0 六职责：9818/13657，仍比 8765 基线减少约 28.11%；R5-E 的 42 行增加来自 Root 目录可用性
  投影；
- `src/scidiscovery/operations/`：7 文件、2053/2060 行；
- `src/ + plugins/` 全生产 Python：144 文件、60723/62533 行；
- `deploy/install.sh`：1026 行，较 R5-D 增加 5 行，只是一次只读健康命令；
- 新增数据库表、科学对象、持久状态机、entry-point group、在线握手、可变 registry：均为零。

本阶段新增 393 行启动装配模块是配置安全读取、实际贡献构建、原子摘要、严格只读解析和 CLI
健康门的单一变化原因；它不持有数据库连接、目录缓存或运行时可变服务定位。独立审查必须判断
这部分边界成本是否符合奥卡姆原则，不以测试通过自动视为合理。

## 6. 待独立审查门

审查者必须独立确认：

1. 摘要确由两个真实 daemon 在贡献构建成功后写出，且没有配置路径或内容泄漏；
2. Root/Worker 本地门禁不会引入对端在线协调，也不会把运行配置变成科学语义；
3. `CompiledCatalog` 仍是唯一目录，启动装配模块不是第二 registry；
4. TCAD 正负例、core/full clean-wheel、部署模板与全仓回归均通过；
5. 33 项架构约束、通用插件目标和最小授权未退化；
6. 393 行启动装配的变化原因内聚，且没有可证据支持的更小实现。

第二轮独立审查已明确通过；复审报告为
`reviews/R5_E_RUNTIME_PLUGIN_GATE_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`。R5-E 不再接受夹带修改，
后续退化必须回到其唯一责任阶段修复并重新复审。
