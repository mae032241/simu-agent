# P2/P3 最小实施拆分候选

状态：**拆分设计独审通过；P2a(c925873)、P2b(f365776)、P3a(da87484)已独审提交，P2c/P3b推进中。** [独立审查](evidence/THIN_P2_P3_SPLIT_DESIGN_REVIEW_20261017.zh-CN.md)。 本文只细分[主迁移计划](THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)的 P2/P3 文件责任和负控，不新增功能范围或执行授权。R0/P1已先行提交，动态检查仍未运行；以下最小负控为设计与静态审查依据，不是动态通过证明。

接口与资格边界继续由 [TCAD managed seam](THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)及其[设计独审](evidence/THIN_TCAD_MANAGED_SEAM_REVIEW_20261016.zh-CN.md)负责。已核对独审对应 `a1d37aa` 的设计 SHA-256 为 `8ddda0d0873300f7e85500185133d2e3c99385346ad3af692dc8e45c21e6b42e`；当前 seam 仅更新末尾容量补修的证据与独立审查边界，接口/P3 规则未变。本文不批准容量补修、R0 修改或真实生产执行。

## 唯一 owner 与并行边界

| 原件/状态 | owner |
| --- | --- |
| 科研任务、call、accepted/submission/terminal/observation、等待与封存 | 继续由现有 `research_loop/{contracts,experiments,managed_wait,continuation,history}.py` 持有；TCAD 服务库仅持有底层 job 幂等/进程/retire 事实。 |
| 来源绑定、正式审查资格 | P3 在原实例的 host record 中保存不可变原件及 ref；普通 A 分析、工程 audit 与正式独审资格分别解释。 |
| 执行请求、policy/human decision、撤销原件 | P3 实例级授权 owner 写入，绑定同一原 call 身份；不创建旧 Artifact/Run/Approval 数据库镜像。 |
| 累计执行资源 reservation、settlement、明确 grant amendment | 仅 `research_loop/budget.py` 扩展现有 control-ledger 与 writer 锁写入。P2 wrapper 只消费授权 ref、报告后端观测，不写预算或授权状态。 |

P2/P3 可并行开发各自独立模块；`experiments.py`/`native.py` 的最终接线由单一 owner 串行集成，基于已提交 R0/P1 保留既有钩子。不得复制任务注册、引入新 Root、第二份科研状态机或预算池。下表新增文件名为候选责任位置，独审后固定；没有新增通用框架的要求。

## P2：四个可独审小节点

插件路径均为 `plugins/tcad_artifact/tcad_artifact/`，core 路径均为 `src/scidiscovery/`。

| 节点 | 确切责任范围与最小新增 | 复用与定向负控 |
| --- | --- | --- |
| **P2a 共通状态** | `operations/execution.py`、`research_loop/{experiments,managed_wait}.py`：集中 pending/terminal 判定；accepted/queued/cancelling 原状态保真且阻止新 call，cancelled 保留工程原因，不解释为科学否定。 | 复用 Records/query/reconcile/G3 waiting。沿用 `test_composed_execution_results.py` 的无 collect、身份篡改；`test_managed_execution_wait.py` 的失败 native 不自动 wake、wake 一次及旧 unknown 追加恢复，仅补缺少状态分支。 |
| **P2b 精确原件 resolver** | 插件 `project_packager.py`、`execution_adapter.py`、`command_adapter.py`：从 `materialize_execution_inputs` 提取 metadata/open-original 窄回调，供新冻结源使用；旧 Artifact 调用继续适配。 | 复用 package 验证、slots、size/media/hash/storage quota；新增小输入的错原件/缺来源负控。不得构造假 Artifact 服务或按近似路径查源。 |
| **P2c managed wrapper/注册** | 新插件 `managed_execution.py`；`runtime_plugin.py` 仅抽共享底层 adapter 构造并保留旧 local_worker 工具；`plugins/tcad_artifact/pyproject.toml` 加一个 managed 注册。新增 managed 方法、公开输入合同、Records 接受及终态投影。 | 复用 `ExecutionInterfaceRegistration`/`RuntimePluginFactory`、socket/command adapter、native manifest/日志/outputs。opaque、`result_protocol=None`，不造 local command/snapshot 字段。小 fixture 使用可信测试注入的独立假后端；不增加公开测试旁路参数。 |
| **P2d 原调用 retire/恢复** | `operations/execution.py`、`research_loop/experiments.py`、managed wrapper；两底层 adapter 只补留存权威 retire 回执的窄接缝。通过冻结 `AdapterCapability` 加可选方法，缺失时 unavailable；不向 `LifecycleCapabilities` 加字段使旧 call hash 漂移。 | 复用同 call 目录、原 prepared digest、旧 retire/submit 原子互斥。lookup None 不证明未提交；found 才绑定原 job 后 cancel，确认未提交不伪造 external ID。迁移 `test_submission_protocol_recovery.py` 的确切 digest/丢回执语义及既有 G3 恢复负控，不搬旧 Root fixture。 |

P2c 的真实生产 `prepare` 必须在触达底层 prepare/upload 前通过可信 P3 gate，submit 前再核验；P3 未完成即明确 **production blocked**。注册成功不启用真实 TCAD，操作者/Worker 参数没有 allow-unqualified 开关。

## P3：四个可独审小节点

| 节点 | 最小纯规则复用 | 新原件 owner、文件范围与负控 |
| --- | --- | --- |
| **P3a 来源限制** | 从旧 `service/scientific_usage.{output_sources,scientific_use_restricted}`、`reference_proofs.material_snapshot` 抽精确依赖边/不确定性传播；SQL/CAS 查询留旧适配层，纯规则只收验证过的事实。 | 候选共享 `operations/provenance_rules.py`、新 `research_loop/qualification.py`，`contracts.py` 只接输入冻结/结果封存 ref。原 host record 保存完整来源绑定；缺边/歧义 fail closed，reading view 无资格，未声明精确 derivation 的自动成果保守继承 task 全部绑定输入限制。复用 `test_frozen_input_execution.py` 的错 ref、衍生锚点和复制不洗白语义。 |
| **P3b exact-subject 正式独审** | 复用 `operation_origins.review_author_runs` 的可信 producer/声明 authorship 来源，以及 `worker_connections` 的所有作者/参与者排除规则；不搬连接表，不从任意 parent 推作者。 | `qualification.py` 保存绑定精确 subject、当前 review 合同、真实 reviewer 身份证明和 sealed verdict 的 receipt。`contracts/controller` 只增加明确正式审查合同入口，复用现有 native 派发/封存；`native/continuation` 仅提供可验证身份原件，不复制任务注册。普通 A、candidate_audit 或 package 内 pass 文本无正式资格。作者/助手参与者身份不完整即 unsupported；负控为自审、共同作者、未知身份、换 subject/合同，以及无需资格的普通任务仍可完成。 |
| **P3c 可信 UI/策略授权** | 复用 `schema/approval.py` 的执行专用 option 与 subject-set 规范化规则，`service/executions.authorize` 的 exact request/payload 绑定，以及 `approvals.record_ui_decision` 的 nonce/CSRF/HMAC/幂等语义。旧 schema 强制 ArtifactRef 时只抽纯规则，不伪造 Artifact。 | 候选 `research_loop/execution_authority.py` 保存实例/call 下 request、policy 或 human decision、撤销原件。最小 UI handler 只复用安全 JSON/blob 展示原语，不导入旧 `approval_ui.app` 的 Root/session 管理；完整实例 UI 仍归 P4。仅可信 UI 可封存 human decision，聊天/手写 JSON 不授权。请求绑定 payload/来源/资格/目标/policy/预算授权修订；复用 `test_r4_execution_approval_identity.py` 的错身份、revision 不继承、重复/过期决定语义。 |
| **P3d 累计资源与 gate** | 复用 `ExecutionPolicySnapshot.admission`、`collection_context` 及旧 ExecutionService 的 reservation/remaining/settlement 纯数学：已证 actual 覆盖对应维度，未知维度保留 reservation。 | 唯一 `budget.py` owner 扩展原 ledger 的 reserve/settle/明确未提交 release/grant-amend；`contracts/controller` 冻结资源 allowance，授权模块只调用预算 owner。稳定 key 来自原实例/科学授权 owner，不按 revision package 新建池。prepare/upload 前原子 reserve，accepted 绑定 ref；unknown、cancel 请求或 lookup None 不退款。负控为余额不足、同余额竞争、重复 reserve/settle、unknown 不归零、改预算/目标旧授权失效和恢复不重置。 |

P3 授权顺序、来源/资格规则及预算结算仍遵守 seam 第 4 节。预算授权修订锚点区别于不断推进的 clock/消费事件；来源、subject、请求、目标、policy 或预算授权改变后重新判定，不改旧 receipt。模型继续拥有科学结论，控制层只验证原件/身份/资格/授权绑定。每个小节点通过独审都不单独启用真实执行；全部 P3 gate 合格后另行验证生产接线。

## 验证范围与实施条件

这里只做文件/函数定位与既有设计核对，没有执行 pytest、collect、CLI/子进程、导入、构建、安装、模型、SSH、许可证检查或 solver。负控清单是后续最小检查的选择，不是运行结果；不广扫或搬迁旧 suite，不为换环境重跑功能矩阵。后续动态检查仍受主计划的资源与授权约束。

真实 SSH、许可证/solver、跨 boot、真实平台同 session 唤醒、领域候选/重放/交付及软隔离能力，继续承担原计划的未验收限制；fixture、哈希封存、设计 PASS 均不能代替实际生产资格。R0/P1 提交、本文独审及各节点实现独审先后收口后，再推进对应实施。
