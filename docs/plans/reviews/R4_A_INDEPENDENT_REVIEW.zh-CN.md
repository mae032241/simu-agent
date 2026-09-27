# R4-A 独立审查报告

状态：独立审查完成（打回）  
审查对象：当前共享工作树中的 R4-A 实现、测试与当前生效的调度说明  
审查方法：跨边界闭环审查、复杂度与重复权威审查、聚焦测试、全量测试、最小动态复现  

## 结论摘要

R4-A 已经完成了若干重要的结构性改进：TCAD 的四个目标行为能够从 `tcad_artifact` 的同一个标准插件入口进入同一个启动期 Operation catalog；工作区物化、文件策略、封存、快照和调试仍是由 OperationSpec 引用的窄组件；TaskService、Worker 路由和 Codex 平台中未发现按 TCAD 角色、上下文、Schema 或插件模块名作核心分派的新增分支；调试工具也具有服务端 author capability 校验。聚焦测试和全量测试均通过。

但是，当前通过的测试没有覆盖实际调度路径和完整科学输入合同。独立复现发现七项阻塞缺陷：正式实验计划无法通过 producer admission 进入 TCAD author；当前生效的调度说明仍把任务派往已失效的 legacy role 路径；参数化 TCAD 所要求的已审查参数 cohort 无法通过新 Operation 输入并保持审批约束；编译后的 Worker 指令一边要求 TCAD skill、一边禁止使用 skill；author 的预算长于租约却没有 heartbeat；debug 校验失败快照绕过新快照钩子而丢失 deck；finalizer 文件顺序不确定。这些问题会分别造成不可达、双权威、权限/资格约束断裂、真实 Agent 不可执行、长任务误超时、重试上下文丢失和不可重复封存。

因此，R4-A 尚未形成可由真实调度器稳定使用的 author→独立 reviewer 闭环，不能据此进入 R4-B。

## 审查范围与证据

重点检查了以下边界：

- `plugins/tcad_artifact/pyproject.toml` 的标准插件入口、遗留入口和安装态；
- `plugins/tcad_artifact/tcad_artifact/plugin.py` 中四个 OperationSpec、输入端口、工具、资源、能力与边；
- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` 中物化、文件策略、封存和快照组件；
- `src/scidiscovery/operations/` 的规范、编译、catalog、工具注入和工作区钩子；
- `src/scidiscovery/artifact_agent/service/tasks.py`、Worker 路由、TCAD debug service 和 Root producer admission；
- 当前生效的 `AGENTS.md`、`roles/scheduler.md` 以及 R4 实施计划；
- R4-A 相关测试及全量测试。

执行结果：

- R4-A 聚焦测试：`20 passed in 30.83s`；
- 全量测试：`170 passed in 61.42s`；
- `git diff --check`：通过；
- 静态编译检查：通过。

测试通过只能说明被测试的直接 Operation 路径成立，不能抵消下述由动态复现确认的跨边界缺陷。

## 阻塞问题

### 阻塞 1：经过通用审查的实验计划无法绑定到 TCAD author

证据：

- `tcad.deck.author.initial.v1` 只声明 `execution_capability` 和 `experiment_plan`；其他消费实验计划的 TCAD author/reviewer Operation 同样没有 `experiment_review` 输入端口，见 `plugins/tcad_artifact/tcad_artifact/plugin.py`。
- `science.experiment.materialize.v1` 的输出合同声明其独立审查者为 `science.object.review.v1`，见 `src/scidiscovery/general_transform_operations.py`。
- Root 的 producer admission 要求：当一个输入 Artifact 的 producer 声明独立审查者时，调用方必须在同一次 invocation 中绑定该精确 reviewer output；除非当前 Operation 本身就是声明的 reviewer。该规则位于 `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` 的 operation 输入准入逻辑。

最小动态复现：先由 `science.experiment.materialize.v1` 产生计划，再完成精确的 `science.object.review.v1` 且 verdict 为通过，随后调用 `tcad.deck.author.initial.v1`。结果不是进入 author，而是：

```text
tcad initial ports ['execution_capability', 'experiment_plan']
operation invocation rejected [input_independent_review_missing]
```

现有 R4 测试直接注册了没有 producer operation 标签的计划 Artifact，绕开了该准入规则，因而产生假阳性。

最小修复要求：

- 给三个 author Operation 和 reviewer Operation 中所有实验计划消费点增加精确的 `experiment_review` 端口；该端口可以是可选声明，但当 producer 合同要求审查时必须精确绑定并通过准入。
- 增加真实 producer 链测试：`materialize → object.review → tcad author` 成功；缺失审查、错误审查者、审查对象不匹配和未通过 verdict 均失败。

### 阻塞 2：当前生效的调度权威仍把 TCAD 派往已失效的 legacy role 路径

证据：

- 当前 `roles/scheduler.md` 和 `AGENTS.md` 仍明确要求调度 `tcad_deck_author` 与 `tcad_deck_reviewer` 旧角色，而不是 R4-A 新增的 `tcad.deck.author.*` 和 `tcad.deck.review.v1` Operation。
- `plugins/tcad_artifact/pyproject.toml` 仍注册 `scidiscovery.agent_role_packs`，所以旧角色并非只读历史资料，而仍能被发现并创建任务。
- TaskService 的新工作区钩子只对带有 `operation_authority` 的任务生效；legacy `task_schedule` 创建的任务没有该 authority。

最小动态复现：通过 legacy `task_schedule` 调度 `tcad_deck_author`，随后 claim/materialize。结果为：

```text
legacy task operation authority: None
has domain_workspace: False
has deck path: False
debug listed: False
```

因此，文档指挥的真实调度路径会得到没有 deck workspace、没有注册文件策略且没有 debug 工具的任务；而测试只手动调用了新 Operation。这是运行时行为断裂，也是旧 role 与新 Operation 的双写权威。

最小修复要求：

- 将当前生效的调度说明改为精确选择四个 TCAD Operation；initial/revise/runtime-failure 的选择依据必须来自 catalog 合同，而不是 prose 中的 role 分支。
- 停止从 TCAD 插件暴露已迁移的 author/reviewer legacy role entry point，或在通用 legacy 创建入口对已迁移角色 fail-closed；不得为此新增 TCAD 核心 allowlist。
- 增加测试：旧 `task_schedule` 对已迁移 TCAD author/reviewer 明确拒绝；标准 Operation 路径成功。

### 阻塞 3：参数化 TCAD 的科学输入合同和同 cohort 审批约束未迁移

证据：

- author 指令要求使用精确 `device_parameters` 和 `parameter_coverage`，并写入 `approved_parameter_key`；reviewer 也要求核对这些对象。
- `project_packager.py` 的验证逻辑会在 project 声明 `approved_parameter_key` 但缺少精确参数/coverage 输入时拒绝。
- 新 TCAD Operation 的端口只有 capability、plan、prior/change/runtime 等，没有 scientific foundation、parameter requirements、device parameters、source catalog、coverage、audit 或 uncertainty 输入。
- legacy Root 准入会校验完整的六对象参数 cohort 及同一个人工审批；通用 `operation_invoke` 当前不执行这一 cohort 校验，并允许非 qualifying 输入进入一般准入检查。

这意味着当前新 Operation 对真实参数化 TCAD 既“无法绑定所需输入”，也不能仅靠补几个端口解决：若只补端口，会绕过既有的同 cohort 审批不变量。

最小修复要求：

- 明确定义 parameter-aware author/reviewer 的完整输入组，至少覆盖当前 33 项约束要求的 foundation、requirements、device parameters、source catalog、coverage 和精确 audit；若当前科学合同要求 uncertainty，也必须纳入。
- 用编译得到的、领域无关的输入组准入事实/guard 保持“完整、同 cohort、同审批主体”约束，不得把 TCAD role/schema 判断重新写回 TaskService 或 Root。
- 增加正负测试：完整且同 cohort 已审批输入成功；部分输入、混合 cohort、审查对象不一致和未审批均失败。

### 阻塞 4：模型可见合同自相矛盾，且没有真实 Agent 证明

证据：

- TCAD author 和 reviewer 提示明确要求使用 `$sentaurus-tcad-code`。
- `src/scidiscovery/operations/tooling.py` 生成的通用 Worker 指令明确禁止使用 skills。
- 当前编译资源只包含 prompt，TCAD Operation 没有注册可解析的 skill/static reference；因此该 skill 既没有成为编译闭包的一部分，也没有被 digest 锁定。
- 当前 `test_tcad_operation_plugin.py` 是测试进程直接 patch 文件并调用路由，不是实际拉起 Codex Agent；它无法验证 Agent 是否能理解权限、调用原生文件能力、调用领域 debug 工具并完成封存。

静态检查结果：

```text
prompt_requires_skill True
compiled_instruction_forbids_skills True
```

最小修复要求：

- 选择最小方案：把 author/reviewer 必需的 Sentaurus 编码/审查指导和选定静态参考编译进同一个受 digest 约束的 prompt resource，并移除与之冲突的禁止语句；或者真正实现受 OperationSpec 注册的 skill resource。不能继续依赖未编译的宿主隐式 skill。
- 真实拉起 author Agent，以 fake adapter 完成 claim、materialize、读取显式输入、写 deck、调用 debug、校验并 finalize；再真实拉起独立 reviewer 完成只读审查和 finalize。测试必须同时证明禁止工具不可用/被明确拒绝，而不是只检查工具列表字符串。

### 阻塞 5：author 运行预算为 1200 秒，但租约最多 600 秒且没有 heartbeat

证据：

- TCAD author limits 声明 `timeout_seconds=1200`。
- TaskService 的 lease 为 `min(600, timeout_seconds)`，故实际最长初始租约为 600 秒。
- author 注册工具中没有 `worker_heartbeat`；当前工具列表只包含物化、文件操作、校验、封存、checkpoint 和 TCAD debug 等。

这会使一个仍在其 1200 秒合法预算内的编译/调试 Agent 在 600 秒后失去租约。TCAD solver 项目编写和调试超过十分钟并不异常，因此这不是理论边角。

最小修复要求：

- 给三个 author Operation 注册 heartbeat 工具并在模型可见指令中说明使用条件；reviewer 是否需要应由其独立预算决定。
- 用可控时钟增加生命周期测试，证明 author 在 600 秒边界前续租后可继续，绝对预算仍不可延长；无需真实等待 600 秒。

### 阻塞 6：debug 校验拒绝快照绕过 Operation snapshotter，丢失当前 deck

证据：

- `TCADDebugService._snapshot_project` 在 finalizer 校验失败时调用 TaskService 私有的 `_workspace_snapshot_files`。
- 该通用旧 helper 只收集普通 output 文件，没有调用 Operation 注册的 workspace snapshotter；而 TaskService 正常失败/重试路径已会调用新钩子。
- 因而 debug service 形成了第二条、行为不同的快照路径。

最小动态复现：author 已在 `deck/files/main.cmd` 写入候选文件，但 project metadata 尚未满足 finalizer，调用 debug 后得到：

```text
debug_error registered worker tool failed
snapshot reason validation_rejected
snapshot_files []
workspace_source_exists True
```

源文件仍在当次 workspace，快照却为空；若随后崩溃/超时，新 attempt 无法恢复候选 deck。最常见的“无效候选→调试→修正”路径因此不具备重试闭环。

最小修复要求：

- 由 TaskService 提供唯一、通用、operation-aware 的快照入口；debug service 调用该入口并由注册 snapshotter 决定 deck 快照，不得再调用私有旧 helper。
- 增加测试：无效候选触发的 validation-rejected snapshot 包含当前 deck；新 attempt 从该快照恢复；错误返回保留安全、有限且可操作的拒绝原因。

### 阻塞 7：finalizer 的文件遍历顺序不确定，破坏不可变结果复现

证据：

- `operation_workspace.py` 的 `_source_files` 使用 `os.walk`，只排序每个目录内的文件名，没有排序 `directories`，也没有对最终结果按 `relative_path` 排序。
- 文件数组会进入 `DeckProjectDraft`，随后进入规范化结果和 Artifact digest；目录枚举顺序变化会改变同一逻辑项目的字节和摘要。
- 动态复现按 `z/a/m` 创建目录，finalizer 输出顺序为：

```text
['z/x.cmd', 'm/x.cmd', 'a/x.cmd']
```

这不是稳定的词法顺序，不同文件系统或不同创建历史可能产生不同结果。

最小修复要求：

- 在遍历时原地排序 `directories`，并对最终文件集合按规范化 `relative_path` 做一次确定性排序。
- 增加测试：以不同创建顺序生成相同目录树，finalizer 输出字节、文件清单顺序和 digest 完全相同。

## 已通过的设计点

以下方面未发现 R4-A 阻塞缺陷：

- `tcad_artifact` 使用一个 `scidiscovery.plugins` 标准入口声明四个新 Operation；没有为这些 Operation 新建第二个通用 registry。
- OperationSpec 仍是不可变行为闭包描述，不承担工作区实现；materializer、file policy、finalizer、snapshotter 和 debug handler 是可注册的窄组件引用。
- 编译器把可达的工作区钩子纳入 compiled closure 和 digest；未发现“钩子已运行但编译摘要未覆盖”的直接证据。
- author 与 reviewer 是不同 component，review edge 指向精确 reviewer Operation；直接 Operation 测试中的文件交接、验证和封存成立。
- debug 工具只由 author Operation 声明，服务端还会校验 `tcad.development_debug` capability；直接 fake adapter 测试通过。
- TaskService、Worker router 和 Codex 平台中未发现新的 TCAD role/context/schema/import 分派；R4-A 没有新增数据库表、通用生命周期或权限状态机。
- 未发现提前实现 R4-B 的 transform 迁移、R4-C 的执行 adapter 迁移或 R4-D 的 UI schema 编译。旧 transform/执行/UI 仍在原位符合本阶段范围。
- core-only 与 full 安装发现测试通过；TCAD 插件静态导入在当前 full 环境中可用。

这些结果说明 R4-A 的“插件入口和窄组件”方向正确，但尚不足以证明实际科学闭环已迁移。

## 非阻塞债务与简化建议

### 1. 插件隔离的表述强于实际技术边界

插件钩子接口只显式收到任务私有根、显式输入路径和有限 provisional roots，没有向插件传入 ArtifactService 或数据库，这一点成立。但插件本质上仍是同进程受信任 Python；收到一个 `Path` 并不构成对恶意代码的 OS 级目录隔离。当前更准确的承诺应是“框架接口不提供仓库、Artifact 库和兄弟任务句柄，已安装插件属于受信任代码”，而不是绝对声称插件“无法扫描”。若威胁模型确实包含恶意插件，需另立进程/沙箱课题，不应塞入 R4-A。

### 2. contextual tool 的错误映射过于粗糙

通用 handler 把多类异常统一映射为 `registered worker tool failed`。这没有泄露内部信息，但会让合法 debug 失败缺少可操作信息，增加无效重试。应保留有限的协议错误码和安全字段，而不是暴露堆栈或吞掉全部原因。

### 3. 核心复杂度预算陈述不精确

当前 `spec.py/catalog.py/invoke.py` 行数为 `321/450/430`，合计 1201，而文档仍把冻结预算表述为保持 `321/450/430` 或 1200。单行差异不是实现阻塞，但预算证据必须说明比较基线、统计口径和允许偏差；不能用近似数字宣称严格满足。新增的通用 `workspace.py` 也应被单列为 R4-A 必要窄扩展，而不是从核心预算中隐去。

### 4. 遗留 transform/daemon/UI 不应在 R4-A 顺手清理

这些属于明确的 R4-B/C/D。当前最小修复应只关闭已迁移 author/reviewer 的旧调度入口和上述闭环缺陷，不应借机重写执行、UI 或生产切换系统。

## 修复后的复审门槛

再次送审前至少应提供以下可重复证据：

1. 通用实验计划真实 producer→独立审查→TCAD author 的正负准入测试；
2. 参数 cohort 完整、同源、同审批的正负测试，且核心无 TCAD 分支；
3. legacy TCAD role 调度 fail-closed，当前调度说明只使用 catalog Operation；
4. 真实 Codex author 和独立 reviewer 的端到端 fake-adapter 运行记录；
5. author heartbeat 生命周期测试；
6. debug validation-rejected 快照与下一 attempt 恢复测试；
7. finalizer 跨创建顺序的确定性测试；
8. 聚焦测试和全量测试继续通过，并更新可信的复杂度统计。

## 最终判定

打回修复，不允许进入 R4-B
