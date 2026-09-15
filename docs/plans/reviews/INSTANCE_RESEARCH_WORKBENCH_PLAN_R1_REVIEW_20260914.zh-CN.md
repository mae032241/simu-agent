# 实例研究工作台计划 R1 独立工程审查

日期：2026-09-14。结论：**REVISE**。

审查对象：[INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md](../INSTANCE_RESEARCH_WORKBENCH_PLAN.zh-CN.md)，标题 R1，共 374 行。精确文件 SHA256：

```text
91fb0efefc920c7d858c9df53ecbc34c41eb86628dc7eb88b5f155dd15ca67bc
```

源码基线与审查时 HEAD 均为 `da220ce31c8cc9f9a60542a018b279e2f331f4c0`。审查时工作树包含待审计划及父代理对 `docs/plans/README.md` 的修改；本审查不覆盖后续计划版本。审查者独立读取计划与下列生产入口，应用 `scid-cross-boundary-review`；未修改计划或生产代码，未调用科研/Worker 工具，未开展实例工作，未运行测试或构建。

## 1. 结论与两项重点

**功能设计主体充分，但归档实施合同尚不完整。** 同端口审批排版、总体/本轮目标、参数与来源、默认值和不确定性、图件、阶段成果及错误分页均有明确设计和反例。没有要求科学 Agent 重复填表，也没有新增科学 Agent。阻断集中在归档期间实际写入者的隔离、安装后归档目录权限，以及恢复后的实例与工作区状态；这些均直接影响首版承诺的“归档—浏览—恢复—接续”。

**展示层方案未发现必须改动科学主干的理由；归档部分目前尚不能证明不损害主干。** 只读投影、展示扩展与 Operation 编译隔离、冻结审批依据、缓存故障隔离的方向可行。R1 已注意多库事务和 append-only 约束，但“短暂排他锁＋关闭实例＋维护租约”尚未落实到当前实际绕过该边界的入口，直接实施仍可能得到不一致归档或遗漏终态后错误资料。

以下三项为实施前必须修订项，不要求新增科学合同、科学阶段或通用调度框架。

## 2. 阻断项

### B1：关闭实例不能隔离旧审批和终态后的实际写入者

**计划位置：** 第 6.2 节第 3—5 步及第 257—261 行；第 7 节 P5。计划允许准备归档时释放全局锁，却仅笼统规定发现绕过路径后补锁，未固定已存在的绕过路径与判定方法。

**源码依据与可达场景：**

| 入口 | 当前行为及影响 |
| --- | --- |
| `service/scheduler_bindings.py:203`、`:231`；`interfaces/mcp_root.py:407` | `close_instance` 只将实例改为 closed 并删除会话关联。常规绑定会话的 Root 路径检查 active；这不是所有资料写入者的隔离门。 |
| `approval_ui/app.py:299`、`:324`、`:331`、`:450` | 旧审批决定和 access refresh 虽持共享 maintenance 锁，却不检查实例 closed 或归档租约。准备阶段释放排他锁后，一个此前打开的审批表单仍可提交并新增决定资料。 |
| `interfaces/mcp_local_worker.py:94`、`:143`、`:463`；`interfaces/mcp_hardened_worker.py:67` | 独立 Worker 生产入口没有接入 `StateMaintenanceLock`。local Worker 在调用前后记录 timing，异常时还记录错误；不是只有成功提交才写控制资料。 |
| `service/runs.py:827`、`:835` | `record_tool_observation` 只确认 Run 存在，允许终态后追加；`record_error_observation` 明确保留已过期 Run 的错误。因此“没有 queued/running Run”不能推出没有写入。 |
| `service/execution_collection.py:315`、`:390`、`:426`、`:467` | 收集子进程另开服务；监督线程在 execution 已 collected 后仍可写状态和过程日志，最后才释放 `active.lock`/`collection.lock`。这些路径不持全局 maintenance 锁，执行终态或 collected 不能单独证明收尾结束。 |
| `service/local_workspace.py:351`；`service/local_process_observation.py:113`、`:127` | 现有恢复路径刻意保留仍可能被 native writer 持有的原目录；未观测进程不能被推成已经停止。失败 Run 和 `recovery_pending` 既不能一律漏归档，也不能一律立即搬走。 |

由此存在两种实际风险：准备期间旧审批或旧 Worker 改变刚复制的范围；最终切换/清理与后台收尾并发，遗漏错误或在原路径重新生成资料。末次复核可以发现部分变化，但不能代替对整个切换窗口的写入隔离。

**最小修订：** 在计划中把已有“维护租约”落实为唯一的实例存储维护门，明确上述入口的接入位置、锁顺序和归属解析。共享维护锁需覆盖实际受保护的写入；处于维护中的目标实例拒绝新决定、refresh、新 Worker 写入和新的收集/调试开始。已开始的后台收尾须以实际锁/进程退出为依据等待或返回 busy，不能只读 execution.state。旧 Worker 的拒绝诊断也不能再次追加到已经迁出的目标资料。native 写入无法证明停止时，保留原件并返回具体 unknown/busy；未支持的后端必须在预览中明确拒绝。保持普通未归档实例的现有科研语义，不能用新增科学准入字段实现这一门。

**补充验收：** 两实例跨进程负控，覆盖复制期间旧审批提交/refresh、已终态 Worker 的迟到调用、collected 后仍持收集锁的日志收尾、native 停止观测失败，以及服务重启后残留维护记录。证明目标范围冻结、无迟到资料丢失，另一实例仍可读取、提交与执行。单纯调用 `instance_archive.py` 的顺序单测不足。

### B2：固定归档目录在实际安装的 UI 服务中不可写

**计划位置：** 第 6.1 节第 211—212 行、第 7 节 P5/P6、第 9 节部署。当前列出的文件责任和 wheel 验收没有覆盖这个必需的部署修改。

**源码依据：** `deploy/systemd/scidiscovery-approval-ui.service.in:21` 设置 `ProtectSystem=strict`，第 22 行设置 `ProtectHome=read-only`，第 23 行的 `ReadWritePaths` 仅包含 state_root 和 local workspace root。`deploy/install.sh:16`、`:328` 将后者固定为 `<project_root>/.scidiscovery-runs`。新目录 `<project_root>/.scidiscovery-archive/instances` 是它的兄弟目录，不在该服务的写入白名单中。

**可达场景与影响：** 在源码目录内由当前用户运行 UI 的测试可以通过；通过现有安装流程启动的 approval UI 在创建归档临时目录时会失败。wheel import 和浏览器页面截图都不能证明实际迁移可用。

**最小修订：** 将 `deploy/install.sh` 和 approval UI systemd 模板明确纳入 P5/P6：由安装流程安全创建固定归档根并设置现有服务账户所需权限，仅给实际执行归档的服务增加这一精确目录的 `ReadWritePaths`。不开放整个 project_root，不新增账户、服务、端口或环境变量；安装回滚不删除已有归档。若另一个现有进程承担迁移，相应写权限必须给实际承担者，不能只改 UI 页面。

**补充验收：** 验证安装生成的单元及目录权限，在等效 `ProtectSystem`/`ReadWritePaths` 限制下完成隔离实例归档和恢复；同时证明项目源码及其他工作区目录仍不可被维护 API 任意改写。无 systemd 条件时明确记录未验证部署项，不能以源码测试替代。

### B3：恢复时实例开关、会话、工作区根和后端临时身份的处理没有闭合

**计划位置：** 第 6.2 节先关闭/解绑再准备记录包；第 6.3 节要求恢复原记录、绑定、工作目录，同时不绑定会话，并能经现有管理入口接续。

**源码依据与冲突：**

- `scheduler_bindings.py:203` 将 state 改为 closed，`:133` 的管理选择及 `:162` 的选择接口都拒绝 closed；当前没有 reopen 接口。若照第 6.2 节顺序封存关闭后的行再原样恢复，用户无法按第 6.3 节从现有入口选择它。若原样恢复 `scheduler_sessions`，又会违反“不自动绑定会话”。
- `local_workspace.py:124`、`:173`、`:324`、`:441` 显示恢复所需资料不只是 Run 的源码目录：还有 `.bindings/<run映射>`、`workspaces/workspace_<uuid>`、共享 `recovery/<digest>` 及可能保留的 quarantine/原目录。不能从目录名称推断 Run，也不能将一个实例使用的共享 recovery 目录直接独占移走。
- `hardened_workspace.py:34`、`:107` 存有 `dispatch.sqlite3/active_transport` 的 owner/lease 和 `transport-locks`。这些是运输中的临时占用身份；保存审计资料与恢复成活动租约并非同一行为。
- `runtime.py:82`、`:92` 允许不同后端与自定义 local workspace root；`execution_collection.py:311` 的控制记录包含原 state_root 和后台调用信息，执行交换资料也包含本机路径。仅保留原字节并不能证明换根目录后可用，重新播放这些后台请求更不属于恢复授权。

**最小修订：** 补一个仅属于存储维护的恢复规则表：

| 资料 | 首版应固定的处理 |
| --- | --- |
| 原实例状态、语义绑定、current/资格 | 归档冻结前保存精确原状态。恢复原先 active 的实例时，在全量验证后显式恢复为可选择但未绑定会话；原先已经 closed 的实例保留 closed，不伪称可接续。此管理变更不得重写科学资格。 |
| scheduler_sessions、浏览器读取/维护凭据 | 历史内容可以保存作审计；恢复不重新激活旧会话或凭据。用户显式选择走原入口。 |
| Workspace 映射、恢复摘要与原目录 | 精确记录原根目录、Run→workspace 映射、文件权限/必要元数据和共享 recovery 引用。首版可限定恢复到同一 runtime 的原 state/workspace 根；换根、后端改变或占用冲突时给出有界不支持，不修改科学原件凑路径。 |
| Hardened transport、收集请求及过程锁 | 保存历史 bytes，但不得把旧 owner、lease、PID/FD、锁状态重新激活；后续新 Run/收集仍由原机制取得新的占用。明确支持此后端或在预览中拒绝。 |

不需要新增普通 reopen 科研命令，也不需要把这一表扩展成科学工作流状态机。

**补充验收：** 原 active 与原 closed 两类实例；旧 session 已被另一实例使用；同一个 digest 被两个 Run/实例引用；自定义 workspace root；有原目录保留的失败恢复源；hardened 的过期 transport 记录。恢复后在原路径上验证 `resume_from`/`draft_from` 的既有检查，而不是只比较一份文件摘要。

## 3. 已核对且无需扩大的设计

| 设计面 | 判断与源码依据 |
| --- | --- |
| 审批不可变身份与人类决定 | 方向正确。`schema/approval.py:155`、`:190` 将 subjects、review_document 等纳入原请求；R1 明确仅改阅读映射、不改 projector/Schema/subject。`approval_ui/render.py:193` 保留原件出口，正式决定仍复用原逻辑。 |
| 参数及不确定性 | 有现成数据可读。`device_parameters.py:160`、`:228`、`:273` 分别提供来源目录、报告值及选用值；网络时间、事实类型和不确定性不应被合成一个真假标记。R1 的未知展示规则避免新增 Agent 填表和准入条件。 |
| TCAD 审批上下文 | `tcad_artifact/runtime_plugin.py:140`、`:169`、`:189` 已有 resolved inputs、项目资源和独立审查信息。从精确引用补读可实现，不需要新增审批解释 Agent。 |
| 展示扩展 | 一个只接收已授权数据、只返回受限视图模型的可选 entry point 可以保持领域字段在插件中，不构成第二行动目录。应按 R1 验证加载失败及未知版本回退，不扩展为具有 runtime 写权限的插件框架。 |
| 自动轨迹与错误 | `runs.py:756`、`:792`、`:827` 支持从既有 Run 与事件构造节点；`executions.py:666` 确实只有创建时间而非每次迁移时间。R1 区分 source_time/observed_at、completed/资格/收集，且不要求 Agent 生成新轨迹，边界合理。 |
| SSE 与故障隔离 | `approval_ui/app.py:96` 当前 GET 整段持共享锁；R1 已明确拆出等待/网络写入，并限制订阅与缓存。无需把浏览器刷新接到 execution sync/collect。 |
| 多库和 append-only | `runs.py:1624`、`scheduler_bindings.py:828` 已采用 DELETE journal 以支撑 ATTACH 原子提交。`storage/migrations/0001_artifacts.sql:49` 和 `approvals.py:1070` 确有禁止删改约束。只在排他维护事务中暂时处理所需 deny_delete 并提交前恢复、失败回滚的方向可行；前提是 B1 完成，且实际参与库逐一核对，不替换存量数据库 inode。 |

## 4. 归档范围与“只留索引”的判断

保留最小 `instance_id → 归档版本/目录/维护进度` 定位和其他实例确有依赖的共享记录，符合真实迁移。**把所有原 Run、审批和错误表行完整留在活动库，不是只留必要索引。** `runs.py:1641` 起保存 instruction、inputs、signal、receipt、reason、recovery；`approvals.py:1025` 起还保存请求、凭据、决定和尝试绑定。它们是完整历史控制资料。只搬 CAS/工作目录，再将这些行全部称为“索引”，不满足 R1 第 225、251—253 行的活动历史迁出承诺。

因此不建议仅为绕开触发器而改成“文件迁移＋全历史表保留”。最小存储索引和经过证明的共享保留可以采用；若保留完整历史数据库行，则必须先明确缩减用户要求，不能把这个变化隐藏在实施里。

P0 的归属清单需在 P5 前完成，至少包括五个控制库的关联记录、全版本 Artifact/links/idempotency、Run/tool evidence/activity、审批 attempts/nonces、执行交换和收集资料、local workspace 的映射与共享 recovery、hardened 运输记录及 scoped diagnostics。还需核对 `tcad_artifact/runtime_plugin.py:83`、`:95` 声明的 `executor-results` 与 `local-tcad-debug` 等本地插件资料。`engineering_diagnostics.py:125` 的 scope 可作归属依据；`worker:unbound` 不能猜配给某实例。对于无证明归属或跨配置共享的原件保守保留并列明，不能按相似目录名删除。

上述清单无需增加科学 Agent 或要求科学输出补资料。它是本次存储维护的定向清单；不建议为了首版建立通用 GC、任意路径搬运器或新的领域调度接口。

## 5. 再审与实现验收要求

修订 B1—B3 后提供新计划 SHA256 再审。R1 中已有的权限、身份、历史来源、分页、缓存异常、迁移中断和普通更新/删除负控应全部保留；追加本报告的实际入口反例，不需要全量高内存测试。

当前为计划审查，没有运行时正确性证明。尤其未实测 ATTACH 多库崩溃回滚、跨文件系统 fsync、真实旧审批页面或部署后的目录写入。实现审查必须看到对应隔离测试及现场只读展示证据；未经用户管理页面动作不得移动当前 Fig4 实例，也不能把 UI 交付称为科研目标完成。

**最终结论：REVISE。** 展示设计可保留；将归档写入隔离、部署目录权限与恢复规则写成可实施、可反证的合同后，再进入严格实施。
