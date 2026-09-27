# R5-M M7.3 科学内容与控制权限边界独立复审

日期：2026-09-03  
审查者：独立子审查进程 `m7_3_boundary_rereview`  
审查对象：当前共享工作区的 M7.3 候选及其证据报告  
审查方式：只读代码追踪、低内存串行测试和不落库的 TCAD 协议探针

## 1. 结论

**PASS；阻断项 0。M7.3 可以关闭并放行 M7.4。**

上一轮审查指出的阻断已经以通用且足够小的方式关闭：正式 Effect 不再在不知道外部提交结果时直接
重发，而是对同一冻结提交描述符先执行领域权威查回；只有权威确认不存在才调用必须幂等的
`submit`。该修复没有增加 `submission_unknown` 状态、数据库表、Root 工具、后台恢复器、第二执行
生命周期或 TCAD 核心分支。

本 PASS 只覆盖计划第 12.3 节和正式 Effect 的不确定提交边界。它不声称真实 Sentaurus、SSH 机器或
许可证已经在本轮重新验收，也不声称默认 Local 是技术沙箱。`SEC-002` 必须继续保持
`known_issue`。

## 2. 上轮阻断的关闭情况

### 2.1 通用调用顺序

`src/scidiscovery/artifact_agent/execution_bridge.py:27-46` 将正式适配器合同收敛为两个相互配合的
要求：

- `lookup_submission(exact_descriptor)` 只读并权威返回既有外部任务或 `None`；
- `submit(exact_descriptor)` 对同一冻结描述符必须幂等。

`ExecutionBridge` 在启动时拒绝没有查回能力的适配器，并在
`execution_bridge.py:83-120` 固定执行：精确审批和 payload 物化 → prepare → lookup → 必要时 submit
→ 本地登记。查询抛错时尚未调用 submit，因而不能把“权威系统暂时不可用”误当成“不存在”。

lookup 与 submit 之间仍天然存在竞态，因此仅有 lookup 不足以保证安全；这里没有掩盖这一点，而是
同时把 exact-descriptor 幂等性写入适配器合同。正式 TCAD 本地实现以 `job_sha256` 数据库主键串行化，
远端 runner 以 submission 摘要派生固定运行目录并在文件锁内检查/创建，均能关闭两个并发调用同时
查无结果后的重复副作用窗口。

### 2.2 故障窗口

`tests/operations/test_r4_execution_approval_identity.py:263-327` 覆盖两种原阻断场景：

1. 外部已保存提交，但提交响应丢失；
2. 外部返回成功，但本地 `record_submission` 失败。

两种场景第一次调用后 Execution 都停在可恢复的 `authorized`，外部实际提交计数为 1；重开控制
runtime 后，查回既有外部编号并登记，计数仍为 1。另一个负例证明查回不可用时提交计数为 0。
`tests/operations/test_r4_execution_approval_identity.py:329-342` 还证明缺少查回方法的适配器在 Root
启动装配时失败关闭。

`src/scidiscovery/artifact_agent/service/executions.py:407-431` 允许相同 external id 的登记重放，但
不同 external id 或错误状态仍然冲突。它复用现有 Execution 行，不建立第二种未知或恢复事实。

### 2.3 TCAD 实际接线

逐段检查结果如下：

| 路径 | 查回身份 | 并发/幂等依据 | 结果 |
|---|---|---|---|
| 本地 socket adapter | 本地 `LocalFileDescriptor.sha256` → `tcad_lookup_submission` | controller 的完整 `job_sha256` 主键和 `BEGIN IMMEDIATE` | 通过 |
| command adapter | 完整本地 marker 描述符 → `lookup_submission` | transport 必须按 marker 指向的远端提交查回 | 通过 |
| SSH transport | 校验本地 marker 后取 `remote_submission.sha256` | submit 和 lookup 使用同一个远端描述符 | 通过 |
| Python 3.6 remote runner | `submission_sha256` → `run_<digest[:32]>` | `submission.lock` 内检查/创建固定运行目录 | 通过 |

独立探针实际执行了 socket adapter、command adapter、SSH transport、remote runner 的参数映射和
found/not-found 返回，并直接验证 socket controller 数据库中的持久查回，结果分别为
`TCAD_LOOKUP_PATHS_OK=4` 和 `TCAD_SOCKET_DURABLE_LOOKUP_OK=1`。

测试 Effect 适配器都提供了同一查回方法。M7 和冻结 Fig.4 夹具的 submit 只是把相同描述符映射到
固定测试 external id；R4 故障注入夹具显式按摘要保存并重放提交。复核过程中发现基线
`NoEffectAdapter` 的测试计数没有在直接重复 submit 时保持幂等；实现者随即按同一摘要先返回既有
提交，并增加直接重放断言。该修正只改测试夹具，没有增加生产分支或状态。复核后的全部 Effect
夹具均与 lookup-before-idempotent-submit 合同一致。

## 3. 第 12.3 节逐项复核

| 计划要求 | 复核结果 | 关键证据 |
|---|---|---|
| 不可信论文/网页不能扩大领域工具、网络、审批或执行权限 | 通过（按已批准的 Local 软隔离口径） | 恶意 CSV 正文要求开启 web、审批、执行和 TCAD 调试；assignment 仍只含编译 Operation 工具，生成 profile 的 web search 仍关闭，且没有产生 Approval/Execution |
| 缺失参数不被控制层补值 | 通过 | 未声明参数在 preflight 拒绝；参数投影将无证据必填量保留为 `blocking_unbounded`，没有默认值 |
| Metric 不生成诊断或结论 | 通过 | 曲线确定性分析 Operation 只产生分析包和图；诊断为单独 Agent Operation，分析包篡改失败关闭 |
| stale current 拒绝 | 通过 | Run 提交时 current 已变化只登记 `stale_rejected`，其后代进入 reviewer preflight 时递归判为 `input_not_current` |
| 混合 cohort 拒绝 | 通过 | 不同 scientific foundation 的 portfolio/critic 与当前 objective 组合被 guard 拒绝，精确同族正例通过 |
| 错误 reviewer 拒绝 | 通过 | direct revision 的生产者 reviewer 合同不匹配返回 `input_revision_review_contract_mismatch` |
| 旧 revision 审查拒绝 | 通过 | 首版 review 不能放行 revision；只有精确审查新对象才可消费 |
| submission unknown 不盲重发 | 通过 | 响应丢失、本地登记失败、lookup 不可用、缺 lookup 四组负例，以及 TCAD 四段接线追踪 |
| 封存拒绝逃逸路径/符号链接 | 通过 | 主结果符号链接和 TCAD 工具目录、preflight 父目录等符号链接负例均失败关闭；结果目标由控制端固定在 Run 工作区 |
| 封存拒绝秘密、机器路径和未声明二进制 | 通过 | 同一真实 Local Worker 提交入口逐项拒绝，修正后合法结果可封存 |
| `SEC-002` 诚实披露 | 通过 | 约束注册表仍为 `known_issue`；证据明确不把 profile/提示限制写成操作系统隔离 |

恶意来源测试证明的是“输入内容不能修改框架已编译的权限”，不是“可信 Local 进程在操作系统层不
可能使用宿主原生能力”。这个限定与当前架构决策一致，没有用测试名称虚构强隔离结论。

## 4. 独立测试

低内存串行执行以下 M7.3 聚焦矩阵：

```text
tests/operations/test_catalog_negative_cases.py
tests/operations/test_invoke_preflight.py
tests/operations/test_l2_run_invariants.py
tests/operations/test_l3_review_and_human_policy.py
tests/operations/test_general_transform_operations.py
tests/operations/test_m2_curve_analysis_boundary.py
tests/operations/test_m6c_producer_topology_removal.py
tests/operations/test_r4_execution_approval_identity.py
tests/operations/test_l4_local_tcad.py
```

结果：`82 passed in 15.82s`，峰值常驻内存 `120936 KiB`。另行执行适配器/运行时组合得到
`40 passed in 48.51s`。夹具幂等修正后的基线 Effect 与 Execution 故障窗口组合由审查者再次串行
复跑，结果为 `17 passed in 42.95s`、峰值常驻内存 `93944 KiB`；审查者同时核对了修正代码和直接
重复断言。
`compileall`、八个受影响 Python 文件的 AST 解析和 `git diff --check` 均通过。

## 5. 复杂度与 33 项约束

本次修复只新增一个窄的适配器查询方法、一条固定调用顺序和已有登记命令的同 id 重放；没有新增
Operation 字段、插件注册表、数据库表、Run/Execution 状态、调度分支、领域特殊准入或恢复线程。
它保护的是 `EFF-002` 已有承重不变量，不是为了一个测试标签添加例外，因此符合奥卡姆剃刀和计划
第 14 节停止条件。

与 M7.3 直接相关的约束没有退化：

- `AUTH-001/AUTH-003`：Execution 和能力合同仍由控制面及编译 Operation 唯一拥有；
- `IMM-002/LIN-002`：revision、current 和 cohort 的精确身份负例仍通过；
- `ROLE-001/DET-002`：控制与 Metric 不补科学内容；
- `HIL-001/HIL-002`：外部执行仍需精确 UI 决定，不能由来源正文或 Worker 创建；
- `CQRS-001/CQRS-002`：lookup 是领域只读查询，本地状态只由显式登记命令推进；
- `EFF-001/EFF-002`：提交、领域状态和收集仍分离，未知提交只查回；
- `PLG-001/PLG-002`：核心只认识通用 adapter 方法，不认识 TCAD；
- `SEC-001/SEC-002`：来源不能扩大编译权限，Local 原生隔离缺口继续公开；
- `RES-002`：测试串行且远低于 8 GiB，调用次数和查询均有界。

本次 PASS 不授权把这些 `pending_review` 自动晋级为 `conformant`。

## 6. 非阻断限制与后续建议

1. 当前生产 TCAD 四段查回由代码追踪和独立协议探针覆盖，但本轮没有连接真实 SSH/Sentaurus。
   这属于发布/真实 solver 资格，而不是 M7.3 科学—控制边界阻断。
2. Local TCAD 开发调试不是正式 Execution，文档已明确不承诺跨进程接回调试会话；它的输出不能
   成为科学证据或生产资格。不要把本次 Effect PASS 外推为调试进程的高可靠恢复保证。
3. 128 位远端运行目录前缀仍有理论摘要碰撞风险；按当前已批准风险口径不为该极小概率问题扩建
   状态机，保留记录即可。

综上，M7.3 的原阻断和第 12.3 节完成门均已满足；允许进入 M7.4，但 M7、R5-M 仍须等待
M7.4、M7.5 及两位最终独立审查完成。
