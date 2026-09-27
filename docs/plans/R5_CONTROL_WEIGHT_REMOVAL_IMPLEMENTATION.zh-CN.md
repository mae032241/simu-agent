# R5：旧控制重量删除、领域硬编码迁出与复杂度收口实施计划

状态：方案、R5-0、R5-A1、R5-A2、R5-B、R5-C、R5-D、R5-E 与 R5-F 均已独立审查通过；
R5-G D3 已完成旧补丁协议删除并通过独立审查。D4-Q 真实 ABI 8 状态代际、当前证据提取、独立
审计和本地 UI 新资格均已完成并通过后置独立审查。D4-H 与独立诊断只放行的唯一一次 D4-H2 均
完成，但两个新 critic verdict 都为 `blocked`；第三轮修订和实验设计已关闭，正在进行最终后置
独立复核。最终复核、323 项全仓回归和 373 条发布清单均已闭合；科学结果与审批 UI 可用性仍未
通过，因此 R5 发布冻结未放行。

上位方案：`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`。

输入证据：

- `R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md`：R4-A—R4-D 的实现记录；
- `reviews/R4_FINAL_MANIFEST_AND_CLOSURE_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`：
  R4 冻结候选的最终发布见证；
- `reviews/R4_FUNCTIONAL_DECOUPLING_AND_OCCAM_INDEPENDENT_REVIEW.zh-CN.md`：
  R5 必须闭合的功能解耦、巨型文件与奥卡姆条件。

本文件是 R5 唯一详细实施记录。上位方案继续拥有阶段状态与总体架构约束；R4 报告只证明其
精确候选，不作为 R5 的并行状态权威。

## 1. R5 要解决的问题

R1—R4 已建立可工作的统一主路径：领域包通过一个 `scidiscovery.plugins` 入口注册组件和
`OperationSpec`，启动时编译成一个 `CompiledCatalog`，调用时由 `operation_invoke` 复用既有
Task、Artifact、Approval、Execution 和 Worker 文件生命周期。

R5 不再增加新的科研能力。它只回答：

> 如何删除统一主路径之外的旧注册、旧调用和领域特判，并在不削弱科学与副作用边界的前提下，
> 让核心代码真正比 8765 更小、更内聚，使新领域不再需要修改 Root、Task、Scheduler、UI 或
> 安装脚本？

R4 独立审查已经确认四类剩余问题：

1. Root 仍按固定端口、操作编号和设备参数对象解释审批生产者族；
2. 旧角色扫描、旧变换加载器和旧 Root 创建入口仍存在于生产代码；
3. `tasks.py`、`mcp_root.py`、`mcp_worker.py` 和通用插件声明仍混合多个变化原因；
4. 运行时插件缺配置会较晚失败，控制端与 Worker 端没有配置内容一致性证明。

R5 的成功标准是净删除旧权威和领域胶水，而不是把同一复杂度移动到更多文件。

## 2. 明确不做什么

R5 不包含：

- Claim/Evidence/Uncertainty 科学图或新的科研世界模型；
- 新的任务、审批、执行、资格或插件生命周期状态机；
- 新的数据库表、事件存储、注册表、服务定位器或第二目录；
- 通用 Skill 一等物化；当前静态专家合同继续作为内容寻址的提示资源；
- 插件热卸载、在线升级、活动任务跨版本迁移或远程市场；
- 真实浏览器自动化、真实 Sentaurus、许可证或远程 Runner 科学资格；
- 为了行数机械拆分内聚的 Schema、审批服务、执行服务、远端单文件 Runner；
- 重写 TCAD 物理算法、curve-score 算法或已经稳定的 CAS、SQLite、Worker 文件沙箱；
- 历史状态兼容。R5 继续采用当前源码断代原则，不为旧调用面新建兼容包装层。

上述能力只有在 R6/R7 或真实新领域需求提供证据后才能另行设计，不能夹带进 R5。

## 3. 不可退化约束

所有 R5 子阶段必须保持：

1. Artifact 内容寻址、不可变字节、显式父链和实例语义绑定；
2. 调度 Agent 只选择编译目录中的公开 Operation，不生成 Worker 科学结果；
3. Worker 只看该任务绑定的输入、路径、工具和提示资源，聊天不成为第二结果通路；
4. 科学判断属于 Worker，机械校验属于确定性组件，副作用属于领域 adapter；
5. 人工决定只由本地审批 UI 写入，并绑定精确主体与编译合同身份；
6. 外部执行仍复用唯一 Execution 生命周期，具有幂等、重试和不确定状态恢复；
7. `public`、`support`、`internal`、`all` 继续是同一个 `CompiledCatalog` 的投影；
8. 插件私有组件只能被已编译闭包消费，Root 和 Worker 不能按 Python 路径重新发现实现；
9. R5 新增数据库表、持久状态机、顶层注册表和 entry-point group 的数量全部为零；
10. 任一普通新领域插件不得要求核心新增 operation 名称、插件名、Schema 名或角色名白名单；
11. 删除旧路径前必须证明其生产消费者已经迁移；删除后必须有从真实入口失败的负例；
12. 每个关键子阶段实现后必须由独立审查者同时审查正确性、目标偏离和复杂度，未通过不得进入
    下一子阶段。

## 4. R5-0：权威语料、基线和删除清单冻结

本阶段只改文档与测量脚本，不改生产行为。

实现记录与删除清单见 `R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md`；该文件提供证据，不取代
本文件的阶段状态权威。

### 4.1 当前权威同步

1. 同步 `docs/ARCHITECTURE.zh-CN.md` 与 `docs/ARCHITECTURE.md` 中已经被 R4 替代的描述：
   - Operation 是行为闭包，插件是包级注册边界；
   - 审批 projector 来自编译合同，核心只解释固定 `ReviewDocument`；
   - UI 不再按领域 Schema 选择页面；
   - 三种目录视图是一个目录的投影；
   - 当前原生工具限制仍是提示约束原型，不夸大为系统级隔离。
2. 历史 R0—R4 计划和审查报告保持原文，不把失败轮次改写成通过。
3. 本次 R4 功能/解耦审查作为 R5 输入纳入下一代发布清单；新一轮 R5 审查报告继续作为其精确
   候选的清单外见证。

### 4.2 机械基线

冻结并由测试生成以下基线，不手工维护近似数字：

- 旧 entry-point group、源码角色扫描器、旧 Root 工具及其 production/dynamic-entry/test/
  current-doc/historical-doc 五类精确消费者文件集合；
- generic core 中出现的 TCAD、设备参数、图号、领域 profile 和 operation id 分支；
- `src/scidiscovery/operations/` 全包生产代码行数；
- R0 `tests/operations/test_baseline_structure_metrics.py` 已冻结的精确通用路径集合，以及版本化
  职责后继路径；删除文件按零行计，职责拆到新文件必须追加到原所有者聚合；
- `src/` 与 `plugins/` 下全部生产代码总量，防止把核心领域代码搬进插件后误记为净删除；
- `tasks.py`、`mcp_root.py`、`mcp_worker.py`、`general_science_plugin.py`、
  `general_transform_operations.py`、`operations/catalog.py` 的行数、顶层职责和依赖方向；
- `deploy/install.sh` 作为部署表面单独跟踪，不混入通用 Python 核心的 10% 指标，但其删除与新增
  仍必须在变更报告中计量；
- core-only、full、full+InGaAs 的安装态插件入口、Operation 数量和摘要；
- 当前 121 项跨边界聚焦测试、245 项全仓测试及 7 GiB 串行运行方式。

同时冻结 R5-G 使用的一个最小 TCAD 科学任务，不重新证明已经闭合的整篇论文链：

- 将任务陈述、输入文献/证据、已知矛盾、历史原始 solver 输出、8765 结构/科学参考和所有文件
  SHA-256 写入版本库内的 fixture manifest；原始文件不得只存在于 `/tmp`；
- 冻结每个所需 Operation 的精确 id、端口绑定、必需输出、允许跳过条件，以及同模型/工具和
  定量 token/墙钟预算；
- 冻结 replay/fake adapter 的 id、版本、请求与实现摘要，并验证它只重放四项 exact 历史输出，
  不宣称为本轮真实 Sentaurus；
- 冻结 ActiveResearchBundle 的 exact replay project/review/audit、scorer 实现和内嵌合同；如果
  旧导出缺少当前通用机械链的精确父对象，必须显式停用该链，严禁伪造或重绑定来源；
- 冻结 InGaAs/Fig.4/480 °C 语义范围；用户定义目标不得冒充论文证据，InAlAs/candidate/Fig.7
  字段不得成为当前主张证据，mesh diff 仅是 prior signal；
- 若现有历史材料不能提供可独立核验的输入、原始输出和参考结论，R5-0 必须先换成另一个已有
  完整证据的小任务，不得在 R5-G 临时补答案或调量表。

### 4.3 删除候选分类

每个候选必须标记为：

- 活跃主路径：保留；
- 最后两个设备参数桥的生产依赖：先迁移再删；
- 发布集合为空但仍可调用的旧入口：直接删除；
- 仅测试/历史文档消费者：删除生产实现，按当前合同重写测试；
- 领域内聚实现：留在插件，不因行数迁回核心；
- 未能证明无消费者：停止该删除项并提交独立审查，不能猜测。

### R5-0 完成门

- 中英文架构事实一致且链接可解析；
- 删除清单列出每个符号的生产、测试、文档和动态入口消费者；
- 基线命令可在 7 GiB 限制下复现；
- 独立审查确认 R5 没有借“轻量化”删除任何承重边界。

## 5. R5-A：迁移最后桥接能力并删除旧注册/调用权威

R5-A 先保证能力对等，再删除旧入口；不允许在旧入口外再包一层适配器。

### 5.1 R5-A1：迁移完整的设备参数领域能力

设备参数不是通用科学核心概念。R5-A 必须把它作为一个完整的领域能力纵切面迁入 TCAD 插件，
不能只迁移最后两条 Agent bridge 后把其余参数逻辑留在通用核心。

先将当前仅允许的两条 legacy 任务迁为 TCAD 插件的公开 Agent Operation：

- `tcad.parameter.evidence.extract.v1`：消费精确目标、需求和冻结来源，产生一个主 intake 以及
  `parameter_requirements`、`device_parameters`、`source_catalog` 完整集合；
- `tcad.parameter.evidence.audit.v1`：消费上述完整生产者族、coverage 和每个冻结来源，执行
  独立审查并输出精确审计结果。

要求：

- 复用现有 evidence extractor/auditor 的 prompt、Schema、validator 和 Worker 文件生命周期；
- 完整集合由 Operation 输出端口和 bundle validator 声明，TaskService 不再识别三个集合名；
- 新 producer identity 来自编译 Operation，不再制造
  `legacy.device-parameter-evidence.v1`；
- coverage、uncertainty 和资格审批保留现有 operation id，但实现与声明归入 TCAD 插件，不复制
  算法；
- 新任务、产物、审计和后续审批全部记录 operation id、version、digest；
- 新路径真实运行通过后，删除 AGENTS 与 Root 中的两个 bridge 例外。

同一逻辑单元还必须迁移：

- `device_parameters` Schema、单位/条件/覆盖与不确定性算法及其导出；
- `science.parameter.coverage.v1`、`science.parameter.uncertainty.v1` 的 Transform 声明、组件、
  codec 和 validator；
- 两个参数资格 Approval Operation、projector 和资格规则；
- TCAD author/reviewer 对设备参数 provider、Schema 和完整批准组的引用；
- 通用实验意图 validator 中设备参数映射的解释逻辑。通用 validator 只验证领域无关的实验
  意图；参数感知映射由 TCAD 插件中的专用 validator/guard 或 materialize 组件验证。

所有上述能力由同一个 TCAD `PLUGIN` 组装。Operation id 可以保持稳定，迁移导致的编译摘要允许
按源码断代原则变化。不得复制通用 evidence、experiment、`ApprovalService` 或
`ReviewDocument`。迁移完成后，core-only 安装不得导入或导出设备参数 Schema，也不得编译任何
参数 Operation；TCAD clean-wheel 安装仍必须编译并运行整条参数链。

### 5.2 R5-A2：删除旧发现入口

删除：

- `scidiscovery.agent_role_packs`；
- `scidiscovery.transform_adapters`；
- 已经断裂的 `scidiscovery.operation_specs`；
- `platforms/roles.py` 对源码 `plugins/` 的扫描和 entry point 优先级覆盖；
- `mcp_daemon.py`、测试装配和安装脚本中的 `load_transform_adapters()`；
- 无生产消费者的 role frontmatter 行为元数据和旧 output profile。

保留普通角色的文本身份仅用于用户可读说明；运行时 prompt、工具、Schema、工作区和权限只能从
CompiledOperation 取得。

删除前必须逐一替换现有生产消费者：

1. 参数 bridge 迁移后，`open_runtime` 不再调用 `load_roles()` 构造 legacy
   `role_output_contracts`/`role_context_policies`；`TaskService` 对这些映射的构造参数和旧分支
   必须为空或直接删除，Operation task 只消费 `TaskOperationAuthority`；
2. `scid init codex` 和 Codex profile 校验只遍历一个 `CompiledCatalog` 生成 Operation Agent
   配置与期望集合；
3. scheduler 提示保留为独立静态资源及窄加载函数，不再位于角色发现模块，也不携带角色行为
   元数据；
4. control daemon、Worker daemon、安装脚本和测试装配删除
   `load_roles()`/`load_transform_adapters()` 的导入与探针。

不得以空 loader 或兼容 facade 保留第二发现权威。删除完成后必须分别从 clean-wheel 的
`open_runtime`、`scid init codex`、control daemon 和 Worker daemon 真实入口验证，而非只检查
entry-point 元数据。

### 5.3 删除旧 Root 创建表面

从调度器可见 Root MCP 删除：

- `task_schedule`；
- `artifact_transform`；
- 已迁移科学审批的直接 `approval_request_create`；
- 已迁移 Effect 的直接 `execution_request_create`。

保留 ApprovalService、ExecutionService 及实例/进程绑定等控制面专用审批。控制服务内部可以有
窄方法，但调度器不能绕过 `operation_invoke` 直接构造已迁移科学行为。

### 5.4 安装与部署去领域断言

- 安装器只安装用户选择的包，再编译目录并验证其声明的插件编号和协议；
- 删除固定角色数量、固定 transform profile、固定 TCAD import 和 curve operation 列表断言；
- TCAD 独有服务、配置文件和远程 Runner 可以由 TCAD 部署子命令管理，但通用控制/Worker daemon
  不得 import TCAD 包；
- 若安装包仍发布任一旧 entry point，安装探针必须失败，不得静默忽略。

### R5-A 测试门

- 两个参数 Agent Operation 的真实 Worker 正例和完整集合负例；
- 参数 coverage、uncertainty、两项资格审批、实验意图参数映射和 TCAD author/reviewer 引用的
  安装态正负例；
- 旧 bridge 调用、旧 role entry point、旧 transform entry point 和旧 Root 工具均从真实 MCP/
  安装入口失败；
- clean-wheel 的 `open_runtime`、`scid init codex`、control daemon 和 Worker daemon 均不依赖旧
  loader；
- core/full/项目插件 clean-wheel 编译通过；
- core-only 目录、模块导入与公开 Schema 导出中没有设备参数能力；
- 已有 TCAD、curve、InGaAs Operation 摘要不因删除旧入口漂移；
- 独立审查明确确认只有一个发现权威和一个行为创建入口。

### R5-A 内部独立门

R5-A 分两次独立放行，不新增产品阶段或运行时实体：

1. **R5-A1 参数迁移门**：完成第 5.1 节完整设备参数纵切面、所有真实消费者迁移及其
   core-only/TCAD clean-wheel 正负例；由未参与实现的审查者确认能力对等、核心无参数泄漏后，
   才允许开始破坏性删除；
2. **R5-A2 旧入口删除门**：在 A1 已通过的精确候选上执行第 5.2—5.4 节，随后运行四个真实启动
   入口、旧调用失败、目录摘要与完整回归，并再次独立审查。

R5-A1 未通过时严禁删除旧 role/transform/Root 创建入口；R5-A2 未通过时不得进入 R5-B。

## 6. R5-B：把审批生产者族变成领域无关的编译关系

> 历史状态说明：第 6.2—6.3 节记录的是已经独立通过的 R5-B 实现事实。其调用指纹、Agent/Transform
> 完整成员解析、去重和失败关闭仍然有效；其中“结构化修订 Transform 递归恢复原生产者族”这一
> 局部分支拟由 R5-G 直接完整对象修订计划取代。该说明不改写 R5-B 的历史审查结论。

### 6.1 当前缺陷

Root 当前只为固定 `extraction_primary` 端口构造生产者族，并直接识别设备参数 legacy 角色、
`science.revision.apply.intake.v1`、`science.intake.revise.v1`、`revised_object` 和
`revision_diff`。这使新的审批生产者族不能只靠插件接入。

### 6.2 目标模型

不新增持久对象或注册表，继续复用现有：

- CompiledOperation 的输入/输出端口；
- Task 的 `OperationAuthority` 与完成输出合同；
- transform 输出已有的 operation id、version、digest 和输出端口标签；
- OutputPortSpec 已有的 `revision_base_port`、collection 和输入用途；
- Artifact 的父链及实例 binding。

当前请求 fingerprint 只存在于 scheduler binding，并未写入 Artifact。R5-B 选择一个最小、耐久
且对所有领域一致的补充：每个 compiled Transform 输出统一写入
`operation_invocation_fingerprint` Artifact 标签。该标签由同一次调用的规范化 Operation 请求
计算，不能由插件提供，不能含领域字段，也不新增数据库列或第二 provenance 对象。

实现一个无状态、领域无关的生产者族解析函数：

1. 对 Agent 主输出，从 `completed_output_contract` 和编译输出端口取得完整集合；
2. 对 Transform 输出，以
   `(operation id, version, digest, operation_invocation_fingerprint, ordered parent refs)` 为族身份，
   从编译输出端口找到同次调用的兄弟输出，并验证每个单值/集合端口都恰好完整；
3. 对修订 Transform，从唯一 `usage=revision_base` 输入取得 base，从唯一
   `usage=change_request` 输入取得 patch，并读取该 patch 输出合同的 `revision_base_port`，验证其
   精确绑定同一 base；验证通过后递归取得原生产者族，再以本次编译输出替换被修订主对象；不得
   引用 intake 专用 operation id 或端口名；
4. 对每个审批输入尝试解析生产者族，成功则放入现有 `ApprovalProjectorContext`，失败保持显式
   缺失；projector 自己按编译端口决定是否必需；
5. 按不可变成员集合对 family 去重；同一族身份解析出两个不一致成员集合时失败关闭，同一完整
   family 的多个成员同时作为审批 subject 时只交付一份 family；
6. Root 不再按端口名、operation id、插件名、角色名或 Schema 选择解析算法。

### 6.3 盲插件反例

测试夹具安装一个此前核心未知的审批插件：

- 使用非 `extraction_primary` 的端口名；
- 一个 Agent 或 Transform 产生主对象和附件集合；
- 一个修订 Operation 产生修订对象和差异；
- 一个 approval Operation projector 要求完整生产者族；
- 不修改 `src/scidiscovery`、Root、Task、Scheduler、UI 或安装器。

该插件必须成功创建精确审批；删去兄弟输出、篡改 fingerprint、漂移 producer digest 或绑定另一
实例对象时必须失败。还必须覆盖：同一 family 多个成员同时作为 subject 时只解析一次、缺少
`operation_invocation_fingerprint` 时失败，以及父链相同但 invocation fingerprint 不同的两次
调用不得合并。

### R5-B 完成门

- `rg` 在 generic Root 中找不到上述固定 operation/端口/角色/Schema；
- 新审批族只靠安装插件即可工作；
- Transform 输出的统一调用指纹由调用器生成，族身份、完整性、修订基线和重复族均有失败关闭
  测试；
- ApprovalService、ReviewDocument 和人类决定生命周期未复制；
- 独立审查确认生产者族解析是总函数，不是另一张 provider 表。

## 7. R5-C：移出 Root、Task、readiness 和上下文中的领域逻辑

### 7.1 TaskService 去领域化

删除或迁出：

- `_validate_device_parameter_evidence_bundle` 及相关设备参数 Schema import；
- 已由 compiled output validator/bundle validator 承担的 figure、parameter、TCAD 输出分支；
- 按 role、context profile、output schema 或集合名选择验证行为的路径；
- TCAD debug 的领域记录解释、capability 解析和结果映射。

TaskService 最终只负责：任务创建/领取/租约/终态、受控文件读写、调用编译后的 validator/hook、
Artifact 封存和通用恢复。TCAD debug 的运行实现与操作记录归 TCAD runtime plugin；它只能获得
任务编号、attempt、精确 OperationAuthority 和任务私有路径的窄接口，不得持有完整 Root facade、
Artifact registry 或跨任务扫描能力。不得新增通用调试状态机；保留现有表时只允许移动所有权，
不复制数据。

### 7.2 Root 只保留通用门面

删除：

- revision target、device parameter cohort、TCAD review/package readiness；
- 按领域 Schema/profile/operation id 选择下一动作或构造输入的分支；
- 已经由 R5-B 统一解析的审批生产者族特判；
- 已经由 Operation preflight 覆盖的重复准入白名单。

Root 只负责实例语义名绑定、读取同一个 catalog、绑定输入、调用 preflight/invoke、查询既有服务
状态和返回受限结果。

### 7.3 `scientific_readiness` 收缩

以只读 `scientific_inventory` 取代当前大型领域投影：

- 输出当前实例可见的语义 Artifact 摘要；
- 输出 compiled public catalog 的声明性行动；
- 可调用同一个 `operation_preflight` 给出 exact invocation 的拒绝原因；
- 不生成候选排名、固定阶段、领域 blocker、角色拓扑或下一步科学判断。

调度 Agent 负责根据科学矛盾选择行动，控制面不把 TCAD 流程重新写回 readiness。

### 7.4 删除静态拓扑与上下文策略

- 删除 `scheduler_topology.py` 中精确的角色运行时残留：`RoleRuntimeProfile`、
  `_ROLE_PROFILES`、`role_runtime_profile`，以及 `_ADVICE`、`_CAPABILITIES` 和角色预算表；不得删除
  科学 payload 中表达 Worker 建议的 `RecommendedTaskMode`、`NextTaskMode` 或其数据字段；
- 删除已经被 Operation 输入端口、用途、exposure、cohort、guard 和 review edge 覆盖的
  `core_context_policies.py` 分支；
- 保留尚未迁移的真正控制面实例/会话策略，但必须按所有者单独命名，不能继续作为科学角色总表；
- 重写 AGENTS 受管调度区块：只说明选择原则、输入绑定和生命周期，不手写领域 operation 顺序。

### R5-C 完成门

- core-only 进程的 `sys.modules` 无 TCAD、curve、InGaAs；
- generic core 无 TCAD、图号、设备参数 Schema 或插件 operation id 分派；
- 复用 R5-B 的同一个核心未知盲插件，证明其 Agent/Transform/Approval 能力不修改 Root、Task、
  Scheduler、UI 或安装脚本；R5 不再另造表格领域插件，真正第二领域扩展留给 R6；
- Root readiness 与 mutation admission 不再分别编码同一准入规则；
- 全部权限、来源、审批和执行负例不退化并通过独立审查。

## 8. R5-D：删除后再拆分真正不内聚的巨型文件

本阶段只能处理 R5-A—C 删除后仍然存在的职责。不得先搬迁后删除，也不得为每个函数建立
repository/service/factory/interface 四层模板。

### 8.1 `mcp_root.py`

目标：Root facade 只做 DTO 解码和委派。按现有唯一服务拆成：

- Operation 目录、预检与调用路由；
- 审批路由；
- 执行路由；
- 实例/语义绑定和只读 inventory 路由。

这些模块共享同一个 Root 依赖容器，不各自缓存目录、不写数据库、不拥有审批或执行状态。旧桥接
模块不得保留；删除代码不迁移。

### 8.2 `tasks.py`

在一个 TaskService 权威下提取：

- 任务生命周期与租约；
- Worker 文件写入、patch、校验和 finalize；
- compiled output 验证与 Artifact 封存；
- 通用证据缓存/摘录。

协作者通过构造注入现有 registry、CAS 和数据库事务设施；不得互相建立状态副本。TCAD debug
不得作为新的 Task 子模块留下。

### 8.3 `mcp_worker.py`

Router 只负责 task/session token、工具名解析和调用分派；文件、PDF/表格、图像及注册领域工具
handler 按协议拆分。允许工具集合仍只来自 CompiledOperation，不能新建全局工具注册表。

### 8.4 通用插件声明

将 `general_science_plugin.py` 和 `general_transform_operations.py` 按以下变化原因拆开：

- Schema/提示/语义合同资源；
- codec、validator、guard、projector 等组件；
- Agent Operations；
- Transform/Approval Operations。

唯一 `general_science_plugin:PLUGIN` 负责组装冻结元组。子模块不能发布 entry point、维护 ID 映射
或在运行时再次发现组件。

### 8.5 `operations/catalog.py`

把 500 余行 `compile_catalog` 拆为启动期纯阶段：声明规范化、组件闭包解析、Operation 合同校验、
review/provider 图校验和摘要构建。只保留一个 `CompiledCatalog` 构造点和一个 installed cache；
不得把阶段结果变成可变 registry。

### 8.6 不按行数拆分的文件

默认保留内聚的曲线/实验 Schema、ApprovalService、ExecutionService、TCAD debug service、
远端 Python 3.6 Runner、图证据 validator。TCAD `project_packager.py`、curve adapter 等领域文件
只有出现独立变化和测试边界时才另行拆分，不作为 R5 放行条件。

### R5-D 复杂度门

1. 第一口径严格复用 R0 `test_baseline_structure_metrics.py` 的精确通用路径集合，删除文件按零行
   计；若原职责迁到新文件，新文件必须加入同一聚合，不能通过移动、重命名或压缩多语句单行
   逃逸；该聚合相对 8765 基线至少净减少 10%；
2. 第二口径统计整个 `src/scidiscovery/operations/` 包，R5 完成值不得高于 R5-0 基线；
3. 第三口径统计 `src/ + plugins/` 全部生产代码；领域代码从 core 迁入 plugin 仍计入总量，不得
   宣称为删除。全仓中真正删除的旧注册、特判、拓扑和兼容代码必须多于新增
   compiler/facade/probe 胶水；
4. `deploy/install.sh` 作为部署代码单独报增减，不纳入第一口径，也不得因口径外而免于审查；
5. `spec.py`、`catalog.py`、`invoke.py` 的单文件物理行数只作诊断，不能靠压行达标；硬门是整个
   operations 包不增长、`compile_catalog` 只协调声明规范化、组件解析、合同校验、图校验和摘要
   构建等可独立测试的纯阶段，不再内嵌全部实现；
6. 每个新模块必须有单一变化原因、生产消费者和独立测试，不允许只为目录美观拆分；独立审查
   必须逐项对应“删除的旧权威”和“新增的必要胶水”。

## 9. R5-E：运行时插件早期门禁与配置一致性

### 9.1 缺配置早失败

- 启动时记录已经安装且声明 runtime factory 的插件，以及本进程已解析的配置绑定；
- `operation_preflight` 对需要 effect adapter 或 Worker tool service 的精确 Operation 检查绑定是否
  齐全；
- 目录仍可描述已安装能力，但 inventory 明确给出运行时不可用，不把缺配置误报为科学输入缺失；
- 不为该状态建表，不把部署配置变成科学 Artifact。

### 9.2 控制端与 Worker 端配置证明

- 新增一个无状态纯函数：对每个实际解析并成功构建贡献的运行时插件产生排序元组
  `(plugin_id, configuration_schema_digest, raw_config_sha256)`。其中 Schema digest 来自当前
  CompiledCatalog 的资源组件，raw digest 对 daemon 实际读取的原始配置字节计算；不得把重序列化
  后的对象当作原始字节，也不得记录配置路径或内容；
- control/Worker daemon 在完成参数解析、配置读取、Schema 校验和 runtime contribution 构建后，
  分别原子写入由显式 `--runtime-summary` 指定的启动摘要文件。部署模板固定使用各自 systemd
  `RuntimeDirectory` 下的短生命周期 JSON 文件，重启覆盖、服务停止后由 `/run` 生命周期清理；
  文件不是数据库、Artifact、capability 或运行时注册表；
- 增加一个只读部署健康探针，显式接收 control 与 Worker 两个实际摘要文件，校验摘要格式、进程
  模式、当前 catalog digest，并只对两个进程共同需要的插件比较上述三元组；探针不重新读取配置
  代替 daemon 声明，也不建立在线握手；
- 该探针是部署健康门：systemd/安装验证只有在两个实际 daemon 摘要一致后才把该服务组合标为
  healthy。Root preflight 只验证 control 本地 adapter 绑定，Worker claim 只验证 Worker 本地 tool
  service；R5 不把对端摘要引入每次请求准入；
- 日志只公开插件编号和摘要，不泄露配置、密钥、socket 或远端身份；
- TCAD capability 仍必须与当前 adapter/profile/solver kind 独立匹配，配置摘要不能替代 capability
  证明。

R5 的一致性证明止于上述“两个实际 daemon 启动摘要 + 一次性健康探针”。在线协调、租约或跨进程
共识明确移交 R7；R5 不得为此新增持久协议或分布式配置权威。若操作者绕过部署健康探针手工
启动两个配置不一致的 daemon，R5 不承诺逐请求发现该漂移；本地缺配置仍分别由各进程失败关闭。

### R5-E 完成门

- 缺配置、配置损坏、符号链接、重复 assignment 和错误插件编号有真实 daemon/preflight 负例；
  两端摘要漂移有真实 daemon 摘要加部署健康探针负例；
- 正常 TCAD control/Worker 配置可启动并解析同一 runtime factory；
- 两端摘要必须来自实际 daemon 成功构建 contribution 后写出的短生命周期文件；仅对同一配置
  调用纯函数的单元测试不能替代真实入口测试；
- 无新的科研对象、数据库表或 runtime registry。

实现与验证记录见 `R5_E_RUNTIME_PLUGIN_GATE_IMPLEMENTATION.zh-CN.md`。该记录不取代本文件的阶段
状态；只有独立审查通过后才允许开始 R5-F。

## 10. R5-F：发布、扩展性与最终独立审查

### 10.1 必测矩阵

每个子阶段先运行最小拥有者测试，R5-F 再统一运行：

1. `git diff --check` 和 Python/脚本静态检查；
2. catalog 编译正负例、旧 entry point 复活负例；
3. core/full/full+InGaAs clean-wheel 安装态测试；
4. Agent、Transform、Effect、Approval 四类 `operation_invoke` 真入口测试；
5. 两个新参数 Agent Operation 的真实 Worker 文件闭环；
6. 盲审批插件的任意端口/生产者族/修订链正负例；
7. TCAD author/reviewer 工具和工作区最小授权负例；
8. runtime 缺配置与双 daemon 摘要漂移负例；
9. 固定 UI XSS、未知 Schema、原始附件和精确决定测试；
10. 全仓串行测试。

若 R5 修改 Codex 工具生成、Worker Router 或任务文件协议，必须额外真实拉起一个无父上下文继承
的 Operation Agent，验证原生只读能力、一个注册领域工具、受控写入、validate/finalize、Root
完成状态和父会话零代写。没有修改这些边界时，不为仪式重复昂贵模型运行。

所有本地测试使用：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

严格单进程串行；禁止并行 pytest，单个进程不得超过 8 GiB。

### 10.2 最终量化门

R5 必须同时满足：

- 已安装 entry-point group 只有 `scidiscovery.plugins`；
- 运行时只有一个 CompiledCatalog；
- 新科学行为创建只走 `operation_invoke`；
- public/support/internal/all 是同一目录投影；
- generic core 没有领域 operation id、端口名、Schema、插件名或角色名分派；
- core-only 启动不导入领域包；
- 新领域插件不改 Root、Task、Scheduler、UI 或安装器；
- 旧控制代码净删除达到第 8.6 节复杂度门；
- 不新增数据库表、持久状态机、注册表或 entry-point group；
- 121 项 R4 聚焦能力的等价覆盖、全仓测试和新增 R5 负例全部通过。

### 10.3 独立审查门

R5-0、R5-A、R5-B、R5-C、R5-D、R5-E、R5-F 每个阶段完成后都必须由未参与该阶段实现的审查者
给出书面结论：

- `通过`：允许进入下一阶段；
- `有条件通过`：只允许修复当前列出的缺口，不得进入下一阶段；
- `打回`：回到当前阶段设计或实现起点。

审查者必须同时检查：正确性、单一权威、33 项约束族、真实安装入口、负例、复杂度净变化和是否
偏离“灵活、低成本、可扩展的通用 AI 科学家”目标。测试全绿不能代替该判断。

## 11. R5-G：端到端科学 Agent 实际效果回归

R5-F 通过表示代码实现和机械回归已经闭合，但 R5 总体状态仍不得标为完成。随后必须在同一冻结
候选上执行一次有界科学效果回归；这不是三领域 benchmark，也不以重复已知 TCAD 链来证明
“通用性”。它只检验本轮删除、迁移与拆分没有让现有科学 Agent 丢失必要上下文、工具或输出。

### 11.1 隔离环境与真实入口

- 使用本版本自己的新 state root、control daemon、Worker daemon、当前 CompiledCatalog 和本地
  审批 UI，不连接旧 8765 服务，也不复用其活动状态；
- 只使用 R5-0 冻结的任务、输入和 checksum。完整 state、secret、socket、隔离 Codex home、原始
  daemon/模型日志保存在权限 `0700`、非 `/tmp`、被 Git 忽略且不进入发行包的持久目录
  `.scidiscovery/r5-e2e-private/<run-id>/`；运行报告必须记录该目录、保留/清理策略和所引用证据的
  SHA-256，但不得复制 token、密钥、配置内容、内部身份或未脱敏绝对路径；
- 版本库 `deliverables/r5-e2e/<run-id>/` 只保存冻结输入 manifest、可公开的封存科学对象副本或
  摘要、量表、脱敏运行证明和最终比较报告；release builder 与 secret scan 必须有负例证明私有
  state、原始日志和 secret 不进入 Git、wheel、sdist 或交付集合；
- 根据当前科学矛盾，真实调起证据提取/审查、假设提出或实验设计、TCAD author/reviewer、结果
  diagnosis 中确实需要的公开 Operation Agent。不得用测试代码伪造 Worker 结果或
  `RoleResultEnvelope`，也不得为验收硬编码固定阶段 DAG；
- Agent 仍由调度器从 compiled public catalog 选择，Transform、打包、评分及 Artifact、Task、
  Approval、Execution 生命周期全部走真实入口；Agent 的聊天结束信号不是科学结果。

### 11.2 审批与 solver 证据分层

- 每个人工决定只通过本地 UI 绑定精确对象。调度器只展示 URL 并读取已封存决定，不把聊天文字
  转成批准，也不代表用户点击；等待审批单列为环境状态，不伪造成框架失败；
- 必做层使用冻结历史原始 solver 输出和已登记 replay adapter 跑通同一 Execution 生命周期，并用
  `ingaas.fig4-baseline-recovery.v2` 对 exact replay project、target、baseline 与 replay PLX 复算
  评分。历史 ActiveResearchBundle 没有导出当前通用 package/attestation/curve-score 所需的 exact
  legacy experiment plan、capability 和当前 review schema，因此本夹具明确不伪造这三个父对象，
  也不把领域 metric 冒充通用 curve-consistency report；报告必须显著标注“重放”；
- 科学诊断由真实 evidence/audit/hypothesis/experiment/deck Agent 封存对象以及独立量表共同评价。
  当前通用 curve diagnosis Operation 只在其精确 generic metric/curve/plan/review 输入真实存在时才
  调用；不得为满足拓扑字面要求伪造 Schema 或来源；
- 真实 Sentaurus 仅在许可证、资源和精确外部执行 UI 授权均可用时附加执行。缺失不阻塞 R5，
  重放结果不得命名为真实求解结果。

### 11.3 独立科学评价与单 Agent 基线

在运行前冻结量表，由未参与生成或实现的独立科学审查者读取精确封存对象、原始曲线和确定性
指标，分别判断：

1. 证据是否可追溯且没有严重错引；
2. 物理解释是否合理，假设是否可证伪/可识别；
3. 实验是否具有区分度，而非只重复已知流程；
4. deck 实现是否与实验计划一致；
5. diagnosis 是否与原始曲线、评分和失败事实一致。

使用相同冻结输入，另运行一个评估专用的单 Agent 基线，给予大致相同的模型等级、可见原始内容、
领域工具和总 token/墙钟预算。它的输出保存为对照证据，但不进入生产 Artifact/Approval 权威。
同时引用可解析的 8765 历史输出作为结构和科学参考。报告记录两路的任务完成、严重证据错误、量表
结果、token、墙钟和修复次数；一次运行不能宣称统计优越性，也不把“必须胜过单 Agent”设为
架构放行条件。

### 11.4 失败分类与通过标准

每个失败必须归入且只能归入主要类别之一，并附原始证据：

- 框架准入/工具/文件生命周期；
- Agent 科学判断；
- 冻结数据或 solver；
- 人工审批等待；
- 外部环境。

通过标准是：主链产生可由独立审查者复核的科学对象；没有因 R5 删除而丢失必要上下文、工具、
输出或审批/执行边界；相对 R4/8765 未出现 R5-0 预先定义的严重退化。独立科学审查未通过时只
允许修复已定位的 R5 回归并重跑精确受影响链；不能通过改量表、换任务或扩大框架绕过。R5-G
书面审查通过后，才可冻结发布清单并把 R5 标为完成。

### 11.5 现场发现：审批安全边界闭合，但界面可用性未通过

2026-08-30 的 R5-G 真实证据资格审批确认了决定只能由回环 UI 写入，且决定绑定精确对象族；但
用户现场反馈该页面“基本不可读”。本次批准只证明审批生命周期、精确主体绑定和写入权威有效，
**不构成审批 UI 的信息架构、可理解性或操作效率验收**。R5-G 可以继续评价科学链，但最终报告
必须把 UI 可用性列为明确未闭合项，不能用安全渲染测试或一次成功点击将其标为通过。

同日 D4-Q 的 ABI 8 新九对象资格页面再次完成了真实决定，但用户再次明确反馈“排版太差，还需要
后续改进”。这使问题从一次现场感受升级为跨两次真实资格审批可重复观察到的产品缺陷：当前页面
虽能安全提交决定，却不能帮助用户高效理解科学对象、差异和风险。后续 UI 工作必须单独立项并做
真实可用性验收；不得把第二次成功提交解释为该缺陷已经缓解。

后续审批 UI 重构必须保持现有安全和权威边界，并至少满足以下要求：

1. 使用“决定摘要 → 科学重点与差异 → 完整精确对象/附件”的三级渐进展示，默认页面不得平铺
   完整对象族；
2. 顶部固定展示审批问题、候选决定、关键警告、对象类型和修订关系；来源摘要、哈希及完整原始
   JSON/附件放入可展开区域，但必须始终可核验；
3. `OperationSpec`/审批 projector 只声明通用、安全、可验证的展示节点和分组，不允许插件提供
   HTML、脚本或第二套领域 UI 路由；
4. 摘要、差异和重点必须由确定性投影产生并绑定同一批 subjects，UI 不调用模型、不产生新的
   科学结论，也不改变审批所绑定的原始字节；
5. 为 JSON、文本/差异、表格、图像和 PDF 提供受限的通用查看组件；未知类型仍安全下载，不得
   假装已经被用户阅读；
6. 增加真实用户可用性验收，至少记录完成一次资格审批所需时间、能否正确复述关键结论与限制、
   是否能定位来源/差异，以及误批或漏看警告的情况。纯渲染单元测试不能替代该验收。

这是一项后续产品重构，不允许在当前 R5-G 科学运行中临时增加领域硬编码摘要、第二注册表或新的
审批状态机。当前运行的现场观察保存在其 Git 忽略的持久私有目录中，最终脱敏报告只引用问题与
边界，不复制临时 URL、token、内部身份或完整私有状态。

R5-G 本地验收脚本仍存在一类低概率加固项：具备本地状态写权限的调用者可能主动拼接历史对象与
自洽摘要，试图误导阶段输入选择。当前只保留已实现的精确报告摘要和 Root preflight，不再为该
理论场景新增 subject-set 签名、第二清单或额外状态。该项记录为后续评估工具加固，不作为当前科学
闭环阻断；一旦发现普通操作可达、真实错绑或权限边界扩大，再提升优先级。

### 11.6 现场修正：假设阶段不重复证据审计和候选资格汇总

R5-G 假设阶段真实运行暴露了一个设计性断裂：`science.hypothesis.audit.v1` 试图在已经完成
“证据提取→独立审计→人工资格”的科学基础之后，再对假设组合重复读取原始来源；随后
`science.candidate.eligibility.v1` 又把同一组合的批评和重复审计合成为第二个准入对象。该链路既
重复科学职责，又与生产者声明的唯一独立评审关系竞争下游准入权威。

当前默认链固定收敛为：

```text
冻结来源
  → 证据提取
  → 独立证据审计
  → 已批准科学基础
  → 假设提出
  → 独立批评
  → 实验设计
```

具体边界如下：

1. 删除通用目录中的 `science.hypothesis.audit.v1`、
   `science.candidate.eligibility.v1` 及专属 Schema、组件、守卫和转换路径；不保留兼容入口；
2. 假设批评继续逐项检查物理合理性、可证伪性和可识别性，并增加证据边界检查：事实前提必须存在
   于已批准科学基础，推断必须显式，缺失输入和历史观察不得升级为已证机制；
3. 批评发现不受支持的前提时，要求最小证据/假设修订并回到既有证据资格路径；批评者不重新读取
   原始来源，也不授予证据资格；
4. 实验设计的科学内容仍只消费 `research_objective` 和 `hypothesis_portfolio`，并把
   `critic_review` 作为独立评审门；另绑定一个对 Worker 不可见的已批准
   `scientific_foundation` cohort witness。既有 `RequiredParentage` 必须证明目标、组合和批评均
   直接来自同一精确 foundation，且批评直接审查该组合；
5. 实验物化保留工程单输入形态和科学五输入形态（意图、foundation witness、目标、假设、批评）。
   witness 与批评只参与准入和父关系检查，不进入确定性科学物化函数；不新增字段、表、注册表、
   状态机或固定调度拓扑。

该修正减少两个 Operation、一个科学实体以及对应专属控制组件。它是对 R5 “控制层只负责边界和
准入、科学判断由 Agent 承担”目标的纠偏，不是删掉独立审查：证据对象由证据审查者检查，假设由
批评者检查，实验计划仍由对象审查者独立检查。

真实重跑后，独立批评以 `blocked` 结束，暴露出“对象必须修订，但未通过评审的对象不能进入修订”
的控制死锁。随后为结构化补丁生产和应用分别增加准入例外的尝试又形成第二段断裂。该局部修复已
被打回，不再继续增加例外；当前改由
[直接完整对象修订简化计划](R5_G_DIRECT_OBJECT_REVISION_SIMPLIFICATION.zh-CN.md)处理：原专业 Agent
读取精确旧对象、必要科学上下文和可选精确评审，直接输出完整新对象；旧对象不可变，新对象重新
独立审查。补丁、应用、差异收据和修订生产者族特判应从发布路径删除。

同时澄清批评者的设计期可识别性口径：尚未产生的未来观测本身不是不可识别；只要可以在实验前
界定有限观测、竞争假设和结果判据，就可以形成可识别设计。未产生观测应登记为待获取输入；无限
兜底机制、未枚举的自由度以及事后解释结果的映射仍必须打回。当前两条现场假设还需要把自由度和
结果映射改写为有限、预注册的判据，再由新的独立批评重新判定。旧批评不得被继承为通过。

## 12. 执行顺序与依赖

```text
R5-0 权威/基线冻结
  ↓
R5-A 最后桥迁移 + 旧注册/调用删除
  ↓
R5-B 审批生产者族编译化
  ↓
R5-C Root/Task/readiness 领域逻辑迁出
  ↓
R5-D 对删除后的剩余代码做职责拆分
  ↓
R5-E 运行时早期门禁与配置证明
  ↓
R5-F clean-wheel、复杂度与独立总审查
  ↓
R5-G 隔离端到端科学效果回归与独立科学审查
```

不得交换 R5-C 与 R5-D：先拆文件会把即将删除的领域分支扩散到更多模块。R5-B 可以在 R5-A 的
参数桥正例可用后与旧特判删除一起提交，但独立审查门仍分别判定。

## 13. 回退边界

- R5-0 只含文档和基线；
- R5-A 按“参数桥迁移、旧发现删除、旧 Root 表面删除、安装器泛化”四个逻辑单元回退；
- R5-B 只改生产者族解析与审批调用，不改 ApprovalService 状态；
- R5-C 按 Root、Task、inventory/context 三个逻辑单元回退；
- R5-D 每次只拆一个文件，并以拆分前后相同测试和摘要证明行为不变；
- R5-E 只增加运行时可用性检查，不修改 capability、审批或执行状态机；
- R5-G 的普通效果回归不修改框架合同；本轮已定位的直接完整对象修订子阶段会按独立计划 D0—D4
  修改并简化 catalog、Task/Worker、Root family 和插件合同，必须逐阶段回退并重新通过受影响的
  catalog、Task/Worker、插件、安装态和 clean-wheel 门；
- 任一回退不得恢复第二 entry point、领域 Root 白名单或旧调度拓扑。

## 14. 停止规则

出现以下任一情况立即停止当前子阶段并送独立审查：

- 需要新增数据库表、可变注册表、科学状态机或插件生命周期系统；
- 为一个具体领域在 generic core 新增 operation id、端口名、Schema、插件名或角色名；
- 删除旧入口后必须靠另一层兼容 facade 才能让主路径工作；
- 拆分文件导致生产代码总量增加，且不能证明新增代码保护新的必要约束；
- readiness 与 mutation preflight 再次分别编码同一准入规则；
- clean-wheel 与源码测试结果不一致；
- 低风险探索新增人工审批；
- Worker 获得未由 CompiledOperation 派生的路径、工具、网络或上下文；
- 运行时配置摘要被错误当作科学 capability 或人工批准；
- 测试为绿但无法证明旧调用从真实发布入口不可达。
- 开发或测试失败需要在多个相邻层增加特判、例外或收据才能闭合；此时必须先重新审视架构所有权
  和数据流并送独立审查，禁止以局部补丁连续缝合。

## 15. 完成定义

只有第 10.2 节全部量化门、R5-F 独立总审查、R5-G 科学效果审查和下一代发布清单都通过，R5
才能标为完成。届时允许进入 R6 的真正第二领域插件和扩展性验收。

R5 完成只表示冻结小任务的重放链与科学判断没有严重回归；不表示真实 Sentaurus 本轮已运行、
三领域通用性、浏览器部署、插件热升级或通用 Skill 已获资格。这些边界必须在后续阶段继续明确
标注，不能用“插件化完成”笼统覆盖。

## 16. 实施状态

| 子阶段 | 状态 | 当前证据 | 下一动作 |
| --- | --- | --- | --- |
| 方案审查 | 通过 | 三轮报告依次为“打回、条件通过、通过” | 保留历史，不重写结论 |
| R5-0 | 通过 | 三轮报告依次为“打回、打回、通过”；专项 6 项、聚焦 127 项；统一 replay Effect/UI/Execution 生命周期与 19 项持久输入闭合 | 保持冻结 |
| R5-A1 | 通过 | 第三轮独立审查确认真实 PDF 双 Worker 工具调用、读取视图边界、精确来源绑定、错配负例与核心无泄漏；92 项跨边界、255 项全仓通过 | 保持冻结 |
| R5-A2 | 通过 | 第四轮独立复审确认 manifest 精确绑定、内容收据、撤销/回滚、显式安装、旧权威和生命周期均通过；31+12+6 项独立测试通过 | 保持冻结 |
| R5-B | 通过 | 第二轮独立审查重放同 Schema 附件负例、合法主对象修订及 clean-wheel；43 项独立测试通过 | 保持冻结 |
| R5-C | 通过 | 三轮总体审查依次为“打回、打回、通过”；第三轮确认 core 隔离、公开跨插件组件、TCAD 本地语义验证、真实曲线工具路由与 270 项全仓回归闭合 | 保持冻结 |
| R5-D | 通过 | 五个拆分单元与总体独立审查均通过；唯一权威和三重复杂度口径闭合 | 保持冻结 |
| R5-E | 通过 | 第二轮独立复审确认 runtime-only、递归及跨插件身份闭包、真实双 daemon 漂移负例和 296 项全仓回归均通过 | 保持冻结 |
| R5-F | 通过 | 独立全仓 299 项通过；真实双 Agent、单一目录/插件入口、复杂度与发布门均通过 | 保持冻结 |
| R5-G | 已收口，科学未通过 | 证据阶段、D0—D3、D4-Q 均通过独立审查。D4-H 首轮 blocked 的独立诊断只放行一次 D4-H2；D4-H2 新 critic 仍为 `blocked`，最终复核确认实现与停止门通过、科学结果未通过。第三轮修订和实验已关闭。323 项全仓回归通过；最终工程报告纳入后，清洁发布 374 条清单严格校验通过。审批页排版差仍是独立未闭合产品缺陷 | R5-G 停止于假设阶段；不得进入实验设计或发布冻结。后续若提升科学成功率，应作为新评估/提示工程任务，不得续接第三轮或放宽门禁 |
