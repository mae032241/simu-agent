# 假设审查与后续行动契约修订

更新日期：2026-09-03  
状态：历史实现与审查记录；其中机器路由权威已被 `R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md` 取代

> 本文件保留当时发现的假设审查职责错位、结构化处置、修订次数和无进展检测依据。原
> `next_action_kind/accepts_actions` 方案不再是当前规范；当前由调度 Agent 读取封存处置并从唯一
> 编译目录选择 Operation，控制面不再匹配 Worker 生成的动作词。

## 1. 问题与目标

真实 Fig.4 运行暴露出职责错位：假设审查者把数值阈值、提取算法、插值和误差传播继续压回假设文本，
而控制面只有自由文本建议，不能区分“修假设”“补证据”“设计实验”和“当前无法判定”。结果是同一
审查边反复修订、文本不断膨胀，却没有把问题交给真正负责的角色。

本次只修订既有 Operation/Run 主干，不增加科研状态机、全局阶段表或第二注册表。目标是：

1. 假设审查只判断物理合理性、原则可证伪性和是否存在有限区分行动；
2. 数值判据、数据提取/归约算法和误差传播归实验设计；
3. 缺事实时精确路由到证据修订，缺模型反事实时路由到计算实验设计；
4. 允许显式“不确定”或“拒绝”，不强迫生成下一步；
5. 同一缺陷不能通过改写措辞无限触发修订。

## 2. 当前规范所有权

| 事实 | 唯一当前所有者 | 本文件的角色 |
|---|---|---|
| 多角色、最小上下文、文件交接和控制面边界 | `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md` | 仅记录本次落地状态 |
| `RoleResultEnvelope` 与类型化交接字段 | `docs/role-result-json-protocol-v1.md` | 不复制完整协议 |
| Operation、输入端口、审查边和路由接受值 | 启动期编译的 `OperationSpec` 目录 | 记录改变的声明 |
| M0—M7.5 历史资格结论 | 原 M7 证据和独立审查报告 | 保持历史原文，不继承 verdict |

## 3. 已实现的最小契约

- `CriticReview` 升级为 v2，增加类型化处置：进入实验设计、修订假设、修订证据、设计模型反事实、
  当前不确定、拒绝。
- `RoleHandoff` 与 `SchedulerSignal` 增加可选 `next_action_kind`；自由文本 `next_actions` 不再是机器
  路由权威。
- `OperationSpec.accepts_actions` 声明一个 Operation 可以消费的行动类型；Root 在创建 Run 前精确
  校验缺失、冲突和不匹配，不从提示词或角色表猜测路线。
- 新增 `science.evidence.revise-from-critic.v1`，只接收原始 intake、其独立审计、foundation、
  portfolio、同一 critic review 和原始来源的精确父链；不会把“不通过的假设”冒充已取得资格。
- 实验设计接收“进入实验”与“设计模型反事实”两类请求，并明确拥有数值阈值、提取/归约算法和
  不确定性传播；TCAD 实现与执行仍由已有领域插件负责。
- 假设修订边最多两次；问题指纹只看处置和未闭合审查维度，不看问题措辞。相同指纹再次出现时停止
  修订，保留不确定结论。

## 4. 未扩张的部分

- 没有新增中心调度状态、科研对象晋级体系、角色间直连通信或插件私有注册表；
- 没有让 critic 编写实验计划、提取算法或 TCAD Deck；
- 没有让 evidence agent 修改全局研究目标；
- 没有改写 M7 历史审查结论，也没有把旧 `critic-review.v1` Artifact 伪装成 v2；
- 当前线上/调试进程仍使用旧编译目录，必须在安装并重启后才能验证新路线。

## 5. 验收状态

源码级验收至少覆盖：v2 Schema、处置与 handoff 一致性、类型路由缺失/冲突/错配、证据修订精确
父链、同问题无进展停止、两次修订上限、非通过 review 只能进入其声明的补救 Operation，以及完整
通用与 TCAD 插件目录编译。

2026-09-03 的本地结果：

- 类型路由、目录编译和 Root 负例：`55 passed`；
- 完整套件在源码可编辑安装元数据存在时：`295 passed`，3 个子进程用例因测试临时入口与源码
  `egg-info` 重复而失败，另有 1 个既有生产文件总量门失败；
- 临时、可逆地移出该构建元数据后，3 个真实 Worker 子进程用例 `3 passed`；同一环境下排除既有
  文件数门的完整套件为 `296 passed, 2 failed, 1 deselected`，其中 2 项恰好要求源码安装入口存在；
  恢复元数据后这 2 项单独 `2 passed`。因此，互相兼容的分段环境覆盖了除文件数门外的 298 项，均
  通过；
- 结构计量：唯一目录编译器 763 行，`operations` 包 8 文件/2147 行，均在冻结上限内；整个当前
  工作树为 184 个生产 Python 文件，超过历史 159 上限。该问题早于本契约修订，本轮没有抬高阈值或
  借机删除无关文件；
- `git diff --check` 通过。

部署、审批界面、独立审查和新的真实 Fig.4 闭环不属于“源码契约已修订”的证据；它们需要使用新
安装的编译目录单独验证。当前旧进程和旧 `critic-review.v1` Artifact 不得冒充本轮验证结果。

## 6. 首轮独立审查与返工

首轮独立审查结论为 FAIL、阻断项 2，原结论保存在
`reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND1.zh-CN.md`，不因返工而
覆盖。当前候选完成以下修复：

1. `science.evidence.revise-from-critic.v1` 只能绑定 prior intake 的 passing audit 所冻结的完整非审查
   对象父集合；替换、遗漏或增加来源均由既有 guard 在 Operation preflight 阶段拒绝。新增来源必须
   走新的证据行动，不能伪装成同一 intake 的有界修订。该规则不按 `source_file` 等类型猜测证据。
2. 假设修订的上下文 validator 冻结完整 hypothesis key 集合；允许同一集合重新排序，但新增、删除
   或改名均拒绝。问题指纹继续按稳定键、处置和未闭合维度计算，因此改名不再能绕过无进展检测。
3. 新增纯 preflight 正负例、真实 Root 解析/预检负例、key 改名负例和 key 重排正例。63 项聚焦跨
   边界回归通过；Operation 套件排除三个已单独验证的 `egg-info` 子进程环境用例和既有 184/159
   文件数门后，生产行为 246 项通过。唯一中间失败是声明资源改变导致冻结目录摘要更新，更新后对应
   摘要与19项收口回归通过。
4. 没有新增状态机、注册表或通用控制字段；目录编译器仍为 763 行，Operation 包仍为 8 文件/2147
   行，通用插件和变换职责继续处于原冻结上限内。

这些结果只说明返工候选可送交新的独立复审，不继承首轮 FAIL 的 verdict，也不宣称已经独立通过。

## 7. 第二轮独立复审与返工

第二轮独立复审结论仍为 FAIL、阻断项 2，原结论保存在
`reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`。复审证明首轮
问题的表面负例已关闭，但又找到两条可达旁路：选择另一份 passing audit 可以替换来源；从同一原始
portfolio 建立 sibling revision 可以绕过祖先链上的次数和无进展判断。当前候选按现有边界修复：

1. 证据修订 guard 除了比较所选 audit 冻结的完整来源集合，还要求该 exact audit 是当前 foundation
   的父对象。这样 foundation 实际采用 `audit_A` 时，不能改绑 `audit_B` 及其来源；未增加来源类型
   白名单或第二 cohort 状态。
2. `RunService.schedule` 在原有 `BEGIN IMMEDIATE` 事务内，利用已冻结的 Run 输入记录检查
   `(instance_id, operation_digest, revision_base_ref)`；同一基线至多有一个非失败后继。下一次修订
   必须使用该后继的输出作为新基线，原有祖先链上的两次上限和问题指纹因而不能被 sibling 绕过。
   失败 Run 不占用后继位置，恢复和重试仍沿既有 Run 机制进行。
3. Root preflight 提供相同规则的早期、可读拒绝；事务检查仍是并发下的唯一最终权威。同名、同指纹
   的幂等调用继续由既有创建目标处理，不新增修订表、current 或状态机。
4. 新增 exact audit 错配负例、Root 分支拒绝和真实 Run 完成后 sibling 调度拒绝测试。局部契约、
   Root 路由、Run 事务和目录负例共 41 项已通过；更宽回归与下一轮独立复审完成前不得标记通过。

## 8. 第三轮独立复审与返工

第三轮独立复审结论为 FAIL、阻断项 1，原结论保存在
`reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`。复审确认第二轮两项
阻断已经关闭，但发现 Root 把“后继输出名相同”当作“请求幂等”：同一语义名、同一基线换一份 critic
request 并使用 `create_revision` 时，preflight 错误放行，invoke 才由 Run 事务拒绝。

当前候选不再比较输出名，而是复用既有创建目标和完整请求指纹：

1. Agent Run 的 resume 解析、完整请求指纹和创建目标收敛到 `_prepare_local_run`；preflight 与 invoke
   都调用同一函数。
2. 只有创建目标已找到 exact fingerprint 的既有 Run 时才按幂等重放放行；任何新创建目标都先查询
   同一 RunService 后继投影，已有非失败后继即返回 `revision_branch_forbidden`。
3. Run 调度事务内的单后继检查保持最终权威，解决 preflight 后发生的并发竞争。Root 不复制 SQL、
   状态集合或后继定义，只复用同一个只读服务查询。
4. 新增真实 Root 回归：同名同请求 preflight 继续通过；同名、不同 critic request 且
   `create_revision` 的 preflight 与 invoke 均以 `revision_branch_forbidden` 拒绝。聚焦 11 项和相关
   Root/Run 56 项均通过。

## 9. 第四轮独立复审结论

第四轮独立只读复审结论为 **PASS、阻断项 0**，完整见
`reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND4.zh-CN.md`。独立探针确认：

- 同名同请求在 `reject` 与 `create_revision` 下都返回同一 Run；critic、instruction、foundation、
  resume 或运行名任一变化，preflight 与 invoke 均一致拒绝；
- 两个 preflight 后并发 invoke 仍只有一个 Run 和一个 binding；事务层双线程同样只有一个后继；
- completed 后不同基线与不同实例不串扰，failed 后可重试；
- exact audit/source 正例、错配 audit/source 负例、两级无进展/次数限制、稳定假设键及六种 disposition
  路由均通过独立检查；
- Root 的只读提前判断和 Run 的事务最终判断复用同一后继查询，没有形成第二状态权威或领域特判。

本结论只放行当前源码契约。部署后的 daemon/MCP、真实审批界面和新的 Fig.4 科学闭环仍是后续验收，
不得由本次 PASS 代替。
