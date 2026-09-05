# R5-L0：S2 候选归类与加固后端防腐冻结

日期：2026-08-31  
状态：L0 实现审查候选；本文件只冻结迁移边界，不宣称 L1—L6 已实现

## 1. 范围与判定原则

基准是 `R5_S2_START_SOURCE_SNAPSHOT.sha256` 所列生产源码。该快照之后发生变化的源码必须归入
以下四类之一。分类单位是可执行符号或合同字段，不以整文件粗暴归类；同一文件可以同时含共享合同
和待迁移的加固实现。

- **共享保留**：两种后端必须具有且不形成第二权威的声明或纯函数；
- **最小后端复用**：可被 `LocalTrustedBackend` 直接复用，但必须脱离 Task/session/token；
- **加固后端迁移**：只为并发、远程、不可信或跨守护进程恢复服务，L1—L4 防腐保留；
- **从默认路径撤回**：迁移期间可能仍在旧 Task 路径中，L2 不得进入普通 Run，L6 删除默认消费者。

任何未列出的新状态、注册表、准入入口或兼容转发都不因本文件获得授权。

### 1.1 可复算终点

终点清单为 `R5_L0_SOURCE_ENDPOINT.sha256`，共 209 项，清单摘要为
`5811ae85499247ef56977b2e1e3f62a2f64bb9a9aab24875a345e341f975d986`。它等于 S2 起点的
208 个路径加唯一新增的 `operations/lifecycle.py`；相对起点恰有 28 项内容变化、0 项缺失、1 项新增。
下表逐项列出这 29 个路径的 S2/L0 变化职责。`共享`、`Local复用`、`Hardened`、`撤回` 是职责
分类；同一文件可含多类，但同一职责只能有一个终点。

| 路径 | 变化符号或合同字段 | 唯一终点 |
| --- | --- | --- |
| `deploy/install.sh` | Worker 三动作安装/运行探针 | 共享；L6 默认部署撤回 Worker daemon 探针，Hardened profile 保留动态探针 |
| `curve_score/figure_science_operations.py` | `BASE_TOOLS`、`AUDIT_TOOLS`、`OPERATIONS` | 共享：删插件重复 lifecycle/checkpoint 声明 |
| `curve_score/science_operations.py` | `BASE_TOOLS`、`AGENT_OPERATIONS` | 共享：同上 |
| `tcad_artifact/operation_workspace.py` | materialized assignment patch 合同 | 共享：删除手工 checkpoint 字段；workspace hooks 留给两后端 |
| `tcad_artifact/parameter_operations.py` | `_BUILTIN_TOOLS`、`_PARAMETER_TOOLS`、Agent `OPERATIONS` | 共享：删重复 lifecycle/checkpoint |
| `tcad_artifact/plugin.py` | `_FILE_TOOLS`、`_AUTHOR_TOOLS`、`_REVIEW_TOOLS`、`PLUGIN` | 共享：只保留领域/文件工具声明 |
| `tcad_deck_author.md` | Worker 生命周期指令 | 共享：只使用三动作，无手工 checkpoint |
| `tcad_deck_reviewer.md` | Worker 生命周期指令 | 共享：只使用三动作 |
| `roles/common.md` | 通用 Worker 生命周期指令 | 共享：一次 submit 完成 |
| `mcp_worker.py` | `WorkerMCPRouter.__init__/list_tools/call_tool` | 共享 router 投影；exact/session 分支迁 Hardened；无 capability role queue 撤回 |
| `mcp_worker_dispatch.py` | `WorkerToolDispatchMixin._call_tool` | 三动作语义共享；文件工具/恢复迁 Hardened；纯工具调度投影给 Local；role queue fallback 撤回 |
| `mcp_worker_protocol.py` | `LIFECYCLE_WORKER_TOOLS`、`REGISTERABLE_WORKER_TOOLS`、`WORKER_TOOLS`、工具组件 | 三动作共享；服务端文件协议 Hardened；非生命周期仍需 Operation 注册 |
| `mcp_worker_proxy.py` | `_AutomaticLeaseKeeper.observe` | Hardened；只观察 open/rejected/completed，不属于 Local |
| `schema/provisional.py` | `ProvisionalSnapshotManifest.reason` | 共享：删除 `manual_checkpoint` 枚举；剩余快照只归 Hardened/恢复策略 |
| `schema/task.py` | `AssignmentProvisionalContext.reason`、`TaskOperationAuthority.lifecycle_protocol_digest` | 前者共享删除 checkpoint；后者 Hardened 私有，普通 Run 撤回 |
| `security/task_tokens.py` | `TaskTokenService.claim_exact/inspect_exact_dispatch/verify_session_binding` 的过期恢复 | Hardened；普通 Run 撤回全部 token/session |
| `service/task_outputs.py` | `validate_output_file`、`submit_result`、`finalize_file`、`_finalize_validated_output` | 一次 submit 语义共享；纯校验 Local复用；seal/replay Hardened；Artifact/终态职责迁 RunService |
| `service/task_shared.py` | `WORKER_CAPABILITIES`、finalization/snapshot 常量 | lifecycle capability 共享；finalization/snapshot Hardened；普通 Run 撤回 |
| `service/tasks.py` | `prepare_exact_dispatch`、`claim_exact`、`heartbeat`；另有 `prepare_dispatch/claim_next` | 前三者 Hardened；后两者及角色队列 fallback 明确撤回，不属于 Hardened 目标 |
| `builtin_plugin.py` | `CORE_PLUGIN.components` 中 lifecycle/checkpoint 组件 | 共享：删重复声明，保留真正文件工具组件 |
| `general_science_agent_operations.py` | `BASE_TOOLS`、Agent `OPERATIONS` | 共享：删插件重复 lifecycle/checkpoint |
| `general_science_components.py` | `component_specs`/`COMPONENTS` 中 heartbeat 组件 | 共享：删除，生命周期改由编译器拥有 |
| `operations/__init__.py` | lifecycle/tooling 导出 | 共享 |
| `operations/catalog.py` | `_validate_operation_contracts` 的 lifecycle 注入与名称碰撞 | 共享，单一目录 |
| `operations/invoke.py` | `_agent_authority` 的 lifecycle 工具投影和摘要 | 工具投影共享；摘要字段 L2 从普通 Run 撤回、仅 Hardened 可消费 |
| `operations/spec.py` | `OPERATION_ABI_VERSION=9`、`AgentLifecycleTool/Protocol`、`PermissionTemplate.lifecycle` | 共享编译合同 |
| `operations/tooling.py` | `operation_lifecycle_protocol`、`operation_worker_tool_names`、提示投影 | 共享 |
| `operations/lifecycle.py` | `AgentLifecycleInput`、`AGENT_LIFECYCLE_PROTOCOL`、`AGENT_LIFECYCLE_BY_NAME` | 唯一新增；共享单一声明源 |
| `platforms/codex.py` | `_operation_toml`、profile 校验与完成指令读取编译工具投影 | 共享；Hardened profile 显式启用时继续消费 |

## 2. 共享保留

| 所有者 | 精确符号/合同 | 理由 |
| --- | --- | --- |
| `operations/spec.py` | `AgentLifecycleTool`、`AgentLifecycleProtocol`、`PermissionTemplate.lifecycle` | 编译器统一投影三个外部动作；不是运行状态 |
| `operations/lifecycle.py` | `AgentLifecycleInput`、`AGENT_LIFECYCLE_PROTOCOL`、`AGENT_LIFECYCLE_BY_NAME` | 唯一声明来源 |
| `operations/catalog.py` | 生命周期名称与插件工具名称冲突检查；编译 PermissionTemplate 时注入协议 | 防止插件重复注册或覆盖生命周期 |
| `operations/tooling.py` | `operation_lifecycle_protocol`、`operation_worker_tool_names` | 从同一 `CompiledOperation` 派生公开工具投影 |
| `operations/invoke.py` | Agent authority 从编译目录取得 agent、工具、网络和生命周期投影 | 调用仍只有一个 Operation 权威 |
| Worker 外部合同 | `worker_open_assignment`、`worker_heartbeat`、`worker_submit_result` | 两个后端共同语义；提交一次完成 |
| Schema/提示/插件声明 | 删除手工 checkpoint 和插件重复 lifecycle 组件 | 生命周期不再由领域插件逐项拼装 |

`worker_submit_result` 的 L0 旧路径暂时返回 `valid` 诊断字段以承载可修复错误；它不是第四个动作，
也不允许先校验再完成。L2 的新 Run 返回完成收据或有界错误后应删除这一过渡字段。

## 3. 最小后端可复用的窄能力

下列实现只能被拆成无 Task 身份的纯工作区能力后复用，不能把旧 Service 包进新 backend：

| 当前符号 | L2 目标 |
| --- | --- |
| `operations/workspace.py` 中的 `WorkspaceContract`、物化/文件规则/冻结值对象 | 形成 `WorkspaceBackend` 参数和值对象；无数据库权威 |
| `TaskCompiledOutputMixin._encode_operation_output`、上下文和集合完整性校验中的纯合同部分 | 迁到 RunService 使用的机械输出校验器 |
| `TaskWorkerFilesMixin` 的相对路径、普通文件、大小、媒体类型、秘密和机器路径检查 | Local seal 复用纯校验函数；服务端编辑协议不随之进入 Local |
| `operation_workspace_hooks` 与 TCAD materializer/finalizer/snapshotter | 由 backend/context 调用；核心不得按 TCAD 名称分支 |
| 已注册 `WorkerToolDefinition` 的 handler/contextual handler 调度 | 改投影为不持久化 `OperationToolContext` |

这些条目不包括 `session_token`、`worker_id`、Task 数据库连接、Artifact 登记、终态写入、current
更新或 reviewer 创建。

## 4. 加固后端迁移冻结

### 4.1 精确调度与私有状态

- `TaskDispatchCapability`、`TaskTokenService.issue`、`claim_exact`、
  `verify_session_binding`；
- `TaskService.prepare_exact_dispatch`、`claim_exact`、`heartbeat` 以及 attempt/lease/
  absolute-deadline 的比较交换；
- `WorkerMCPRouter` 的 exact 分支、`WorkerBrokerRouter`、`_AutomaticLeaseKeeper`、精确私有 capability
  文件；
- backend-private 状态：dispatch、proxy、worker、session、attempt、lease、absolute deadline、
  `claimed`、`finalizing` 和有界 replay deadline。

这些状态不得出现在普通 Run Schema、简单插件投影或默认部署依赖中。

### 4.2 服务端文件协议

冻结 `worker_file_write_begin/chunk/commit`、文本 patch、JSON patch、delete、move，以及
`TaskWorkerFilesMixin` 对写入目标、摘要、路径、大小、符号链接、普通文件和 workspace snapshot 的
实现。该协议由 `HardenedWorkerBackend` 私有持有；`LocalTrustedBackend` 使用 Codex 原生工作区写入，
只在 seal 时执行共同安全检查。

### 4.3 加固提交与恢复

冻结 `validate_output_file`、`freeze_workspace_snapshot`、`finalize_file`、`submit_result` 当前用于
封存候选、提交响应丢失重放和同一 attempt 恢复的机制，直至 L5 拆分。拆分后 backend 只返回
`SealedWorkspace`，不得保留以下旧职责：完整科学合同解释、正式 Artifact 登记、Run/Task 终态、
current CAS、scheduler signal 或 reviewer 调度。

### 4.4 防腐测试清单

L1—L4 每阶段至少运行下列目标测试；文件中的迁移见证测试不因此全部冻结：

- `tests/operations/test_l0_lifecycle_contract.py` 全部：碰撞、协议摘要传播、Task/Codex/Router/deploy
  一致、首次 submit 完成、拒绝后修正、外部 analysis 正例；
- `tests/operations/test_worker_exact_dispatch.py` 中 exact task、同 session 重启、错误 proxy/capability、
  authority/task/attempt/worker/session、三个真实进程提交崩溃窗口、硬期限、私有 capability 文件和
  数据库不扩张；其中普通 role queue 两项只是迁移见证，L6 必须删除；
- `tests/operations/test_r5_worker_router_split.py` 全部；
- `tests/operations/test_r5_runtime_plugin_gate.py` 全部；
- `tests/operations/test_r3_agent_contract.py::test_worker_router_resolves_tools_only_for_its_exact_operation`；
- `tests/operations/test_baseline_worker_authority.py` 全部；
- `tests/artifact_agent/test_platform_configuration.py` 全部；
- `tests/artifact_agent/test_deploy_scripts.py` 中安装编译目录、Codex profile、Worker service 和事务覆盖
  探针；
- TCAD workspace 路径、8 MiB、finalizer 确定性和 debug context 负例。

`test_broker_restart_restores_only_the_same_session_without_renewal`、真实进程级三个崩溃窗口、不同
proxy/capability 拒绝、私有 capability 文件读取、路径逃逸/符号链接/越界大小拒绝是不可删除的关键
防腐事实。测试可以迁名到 Hardened 目录，但不能在 L5 真实消费者验收前消失。

## 5. 从默认路径撤回

| 当前候选 | 撤回要求 |
| --- | --- |
| `TaskOperationAuthority.lifecycle_protocol_digest` | 只可保留为 Hardened 私有 dispatch 指纹；普通 Run 只冻结 `CompiledOperation.digest` |
| `claimed`、`finalizing`、session/attempt/lease | 不进入 Local Run；L6 默认 wheel 不导入 |
| Worker daemon/proxy | 不由默认 deploy 启动；只由 Hardened profile 显式启用 |
| `prepare_dispatch`、`claim_next` 和无 capability 的 role queue fallback | 迁移期见证，L2 不进入 Local，L6 删除；Hardened 也只接受 exact dispatch |
| 服务端分块/patch/move/delete 工具 | 不出现在简单插件和 Local Operation 投影 |
| 旧 TaskService 的 Artifact、终态、current、review/scheduler 职责 | 迁入唯一 RunService，不能由 Hardened 包装后继续拥有 |
| `allow_expired` 和 completed replay 分支 | 仅服务 Hardened 封存恢复；不得扩大普通 token 有效期 |
| L0 `valid` 过渡响应 | L2 删除，不形成兼容层 |

## 6. L0 可测试边界

当前过渡实现满足：

- 插件只声明领域工具，生命周期由编译器统一注入；
- 缺失运行服务在领取启动槽之前失败；
- `worker_submit_result` 一次完成，校验失败保持可修正；
- 已声明工具以外的工具在 router 中不可见；
- operation 非实时测试集通过，未通过测试的冻结计数已按真实声明边界更新；
- 真实 Unix Socket Worker daemon 在封存后、Artifact 登记后 CAS 前和 completed 响应丢失后三个窗口
  退出，新进程只恢复同一 session/manifest；超过 finalization hard deadline 失败关闭；
- 没有新增第二目录、第二 preflight、第二 invoke 或新数据库状态。

该结论只允许进入 L1。L0 未实现 `RunService`、Local 后端、盲 CSV 插件或 TCAD 新闭环，也不把旧
Task 路径误记为目标架构。

L0 第一轮独立实现审查曾以“账本不可复算、Hardened 恢复未冻结、生命周期合同回归不完整”打回。
返修后证据为：终点 209 项自校验通过；聚焦跨协议 `75 passed`；完整非 live operation
`294 passed`；平台与部署测试包含在聚焦集合中。最终结论仍以第二轮独立审查为准。
