# R5-A2：旧发现权威与旧创建入口删除记录

状态：第四轮独立复审通过；R5-B 已放行。

日期：2026-08-29  
上位计划：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`

本文件冻结 R5-A2 精确候选和实现方证据。只有未参与实现的审查者明确给出“通过”，才能把
R5-A2 标为通过并开始 R5-B。

## 1. 本阶段回答的问题

R5-A1 已将最后两个设备参数角色迁成 TCAD 插件内的公开 Agent Operation。A2 继续删除旧系统中
仍可形成第二权威的发现和创建表面，使生产行为只剩两条来源：

1. 安装包只通过 `scidiscovery.plugins` 发布一个完整 `PluginDefinition`；
2. 调度器只通过启动期编译目录的 `operation_invoke` 创建 Agent、Transform、Approval 和 Effect。

本阶段没有修改科学流程、增加注册表、复制状态机或把旧调用包进兼容门面。

## 2. 已删除的旧发现权威

- 删除 `src/scidiscovery/platforms/roles.py`，不再扫描源码 `plugins/`、role pack 或 frontmatter；
- 删除 `scidiscovery.agent_role_packs`、`scidiscovery.transform_adapters` 和已断裂的
  `scidiscovery.operation_specs` 发布入口；
- 删除 `ArtifactTransformAdapter`、`select_transform_adapter()` 与
  `load_transform_adapters()`；保留的 `ScientificStateTransformAdapter` 只是被已编译 Transform
  组件调用的纯算法，不再发现或选择行为；
- `open_runtime()` 不再加载角色，不再构造 `role_output_contracts` 或
  `role_context_policies`；`TaskService.schedule()` 只接受精确 `TaskOperationAuthority`、
  `context_profile="operation"` 和同一次预检的提交前置条件；
- Codex 配置只遍历同一个 `CompiledCatalog` 生成 Operation Agent 配置和 Worker MCP 服务；
- scheduler 文本由 `platforms/scheduler_prompt.py` 作为窄静态资源读取，已删除无消费者的
  scheduler role frontmatter，不参与领域能力发现。

TCAD author/reviewer 文本中仍存在的领域上下文说明是当前编译提示的一部分，不是运行时注册表；
它们及已经无运行时消费者的旧上下文策略文件按上位计划 R5-C 的统一上下文/领域逻辑删除门处理，
本阶段不通过改变 TCAD prompt 字节制造无关 Operation 摘要漂移。

## 3. 已删除的旧行为创建表面

调度器可见 Root MCP 已删除：

- `task_schedule`；
- `artifact_transform`；
- `approval_request_create`；
- `execution_request_create`。

不存在同名 facade 方法、空 loader 或兼容转发。已编译 Transform 和 Effect 分别调用 Root 内部的
窄执行方法，但这些方法只接受完成预检的 `BoundOperationCall`，不是第二个公开调用协议。

保留的 `execution_approval_request_create` 是对已经由已编译 Effect 创建的精确 ExecutionRequest
发起本地审批，不创建 Effect，也不能替代 `operation_invoke`。ApprovalService、ExecutionService
及历史无 compiled identity 对象的拒绝逻辑继续保留，避免删除入口破坏恢复与审计。

## 4. 安装与部署泛化

首次独立审查指出通用安装器默认绑定 TCAD；第二轮指出 TCAD→core-only 会残留 Skill 与 unit；
第三轮进一步指出仅凭事务布尔和同名路径会误删用户自有 Skill。针对三轮部署阻断项，安装路径
现已修订为：

- `SCID_PLUGINS` 默认空集合；core-only 是标准正例，不再隐式选择 TCAD 或 curve；
- 验证用户选择的每个领域包确实发布 `scidiscovery.plugins`；
- 编译一次已安装目录并验证 Operation 编号唯一；
- 对三个旧 entry-point group 做失败关闭检查；
- 验证 Root 只包含目录/预检/调用三项统一行为入口且四个旧入口均不存在；
- 从实际编译目录选择一个 Agent 类型，再探测 Worker daemon 的任务生命周期工具；
- 通用来源探针不导入 TCAD Python 包，不断言固定角色数、固定 transform profile 或固定
  TCAD/curve Operation 列表；
- 通用 control/Worker 只在用户显式选择 `tcad_artifact` 时接收其配置参数；core-only 路径不要求
  TCAD 状态目录、Sentaurus 手册/技能、插件配置或 systemd 服务；
- TCAD policy 与运行时配置的物化代码归
  `plugins/tcad_artifact/deploy/configure_runtime.py` 所有；通用安装器只在显式选择 TCAD 后调用该
  插件自有部署能力，不包含 TCAD Python import 或配置格式算法；
- `tcad-control.service`、Sentaurus 技能和 transport wrapper 仅在显式 TCAD 选择下安装；三者
  始终作为精确受管路径纳入既有安装事务，TCAD→core-only 时撤销活动表面，安装失败时由同一
  事务恢复原字节；
- 撤销函数只能在安装事务已经武装时运行，并校验三个目标的绝对路径、稳定文件名及 Skill 目录
  内无符号链接，不进行宽目录删除；TCAD 科学状态和历史配置仍保留；
- 每个安装器复制的 Skill 都写入规范所有权标记，标记绑定管理者、稳定事务目标名和除标记外的
  完整目录内容摘要；用户修改内容后旧标记不能继续授权删除；
- 删除由既有 `install_transaction.py remove-target` 执行，稳定目标名与绝对路径必须精确存在于
  当前 `prepared` manifest；仅设置 `ROLLBACK_ARMED` 不足以授权；同名无标记、内容漂移或不属于
  当前事务的 Skill 均失败关闭并保持不变。

没有新增插件注册表、部署状态机或 Operation 名称分派。插件选择仍只解析各包的单一
`scidiscovery.plugins` 发布入口。

## 5. 真实入口与失败路径

新增 clean-wheel 测试从已安装 core wheel 依次真实进入：

1. `open_runtime()`，确认目录对象来自唯一已安装插件组；
2. `scid init codex` 的 CLI `main()`，生成真实 `.codex/config.toml` 和 Operation Agent；
3. control daemon `main()`，完成参数解析、目录编译、运行时贡献装配、Root builder 和一次真实
   `tools/list` 路由；
4. Worker daemon `main()`，完成运行时打开、目录编译、Worker 贡献装配、精确 Agent 类型解析和
   一次真实 `tools/list` 路由。

无限阻塞的 socket 循环只由测试 daemon 替身截断；被测的两个生产 `main()`、目录、运行时、
router 和工具投影均为真实实现。

负例从真实 Root router 验证四个旧工具名返回 `unknown root tool`。旧角色/变换/operation-spec
entry point 在 core、full 和 full+InGaAs wheel 中均为空；源码模块
`scidiscovery.platforms.roles` 不存在，`transforms` 不再导出旧 loader。精确派发、Broker 重启、
handoff-only 输入和操作级 Worker 权限测试全部改由编译测试 Operation 创建任务，不再在测试中
复活角色合同。

## 6. 实现方验证证据

所有测试均串行运行，并使用：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

首次候选曾以 `248 passed` 提交审查；前三轮分别发现干净安装领域耦合、插件集合收缩残留、事务
成员/所有权证明不足。完成三项修复后，当前精确结果为：

- clean-wheel 四入口专项：通过；
- core-only 与显式 `tcad_artifact,curve_score` 两条真实安装预演、插件自有 TCAD 配置器、
  TCAD→core-only 撤销/回滚，以及未绑定、无所有权、内容漂移负例：`31 passed`；
- A2 旧发现、旧调用、平台、派发、生命周期和部署聚焦矩阵：`48 passed in 42.22s`；
- 全仓回归：`252 passed in 90.81s`；
- `git diff --check`：通过；
- 生产源码扫描仅在 `operations/catalog.py` 命中一次 `entry_points()`，其 group 常量为
  `scidiscovery.plugins`；旧 loader、角色映射、旧 Root 工具定义和旧发布组均无生产命中；
- core/full/full+InGaAs 目录仍为 `28/51/52` 个 Operation，附加 InGaAs 前后的既有 Operation
  digest 集完全相同；A2 未修改任何 Operation 声明或资源；
- 冻结复杂度口径：R0 核心聚合 `9931` 行，低于 A1 候选的 `9986`；operations 包仍为
  `2060` 行；`deploy/install.sh` 当前为 `1021` 行，不超过冻结上限 `1026`；新增的 TCAD 插件自有部署
  配置器为 `84` 行；通用核心领域 token 计数仍为 `78`。

## 7. 第四轮独立复审结论

第四轮独立复审逐项确认：

1. 是否确实只剩一个插件发现 group 和一个调度行为创建入口；
2. 私有 compiled Transform/Effect 执行方法是否不能被未预检调用绕过；
3. `TaskService` 是否已完全拒绝无 compiled authority 的新任务；
4. clean-wheel 四入口是否属于真实生产入口而不是只检查元数据；
5. core-only 标准安装是否不导入、不要求、不渲染 TCAD，显式 TCAD 路径是否仍可预演和实际物化
   插件配置，且旧发布组仍失败关闭；
6. TCAD→core-only 是否在事务内撤销 Skill、transport 与 unit，失败回滚是否恢复精确旧字节，且
   未引入插件生命周期状态机或宽路径删除；
7. 删除目标是否同时绑定当前 manifest 和安装器内容收据，无标记、内容漂移及未绑定路径是否
   失败并保留；
8. 删除是否未损害 Approval、Execution、恢复、Worker 最小上下文和 33 项约束族；
9. 是否存在兼容 facade、空 loader、新注册表或因测试改写而隐藏的旧路径；
10. 当前复杂度、完整回归和目录摘要证据是否足以放行 R5-B。

结论为“通过，放行 R5-B”。报告见
`reviews/R5_A2_LEGACY_AUTHORITY_REMOVAL_INDEPENDENT_REVIEW_ROUND4.zh-CN.md`。该结论只放行
R5-B，不代表 R5-B 或后续阶段已经实现。
