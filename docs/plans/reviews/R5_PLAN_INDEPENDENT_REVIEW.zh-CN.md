# R5 详细实施方案独立审查

日期：2026-08-29  
审查对象：`docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`  
审查性质：未参与方案编写的跨边界、简化性、决策语料和可实施性审查  
审查范围：只读核对当前工作树、R4 功能/解耦报告及 R5 上位计划；未运行全仓测试  
最终结论：**打回**

## 1. 结论摘要

R5 的主方向和阶段顺序是正确的：先冻结消费者，再迁移最后两个 bridge，删除旧发现与调用面，
随后消除审批族和领域特判，最后才拆分巨型文件并补运行时门禁。方案也明确拒绝新的数据库表、
状态机、注册表、技能物化、插件热升级和真实求解器扩张，没有回到 V12 式宏大控制系统。

但是，当前文本还不能授权执行 R5-0。原因不是缺少更多设计，而是五个可以局部修正的实施闭包
尚未成立：

1. 设备参数领域能力只迁移了两个 Agent bridge，尚未覆盖仍在通用核心中的参数 Schema、资格
   Operation、coverage/uncertainty 和实验意图参数校验；按现计划执行后无法满足“generic core
   无设备参数领域逻辑”的完成门。
2. 删除旧 role loader 没有列出两个真实生产消费者的替代路径，会导致 Codex 配置生成和
   `TaskService` 启动装配断裂，或者迫使实现者继续保留旧 loader。
3. 审批生产者族算法把 `request_fingerprint` 误写成已有 Artifact 标签，且没有冻结 Transform
   调用族的不可变分组、修订基线解析和重复族去重规则；盲插件正例目前不是可实现的总函数合同。
4. 双 daemon 配置摘要只有目标，没有一个现有入口可观察或比较该摘要；同时复杂度门混用了
   已失真的单文件行数预算和正确的全路径净删除口径。
5. R5-F 只要求条件性的单 Agent 工具闭环，没有用户刚要求的有界科学端到端效果评价；纯
   `pytest`、假模型或机械 fake solver 链不能回答科学 Agent 是否仍然有效。

这些问题均不需要新增科学语义内核、工作流状态机、三领域 benchmark 或真实 Sentaurus
生产运行。第 7 节给出冻结的最小修订清单，修订后应重新独立审查。

## 2. 已确认合理、应保持不变的部分

### 2.1 阶段顺序合理

`R5-0 → R5-A → R5-B → R5-C → R5-D → R5-E → R5-F` 的依赖方向可执行。特别是：

- 两个 legacy 参数任务必须先有 Operation 等价路径，随后才能删除 `task_schedule` 和角色装配；
- 审批生产者族应先从 Root 固定端口变成通用解析，再清理 Root 的领域分支；
- `tasks.py`、`mcp_root.py` 等巨型文件必须先删职责、后按剩余变化原因拆分；
- 运行时配置检查不应变成科学 Artifact、资格或新持久状态。

不得为了本次打回交换 R5-C/R5-D，或在 R5-0 前开始移动巨型文件。

### 2.2 R4 的 F1—F5 大体有去向

| R4 条件 | R5 方案位置 | 本轮判断 |
| --- | --- | --- |
| F1 审批生产者族硬编码 | R5-B | 方向正确，算法闭包需修订 |
| F2 旧发现和 Root 创建面 | R5-A | 方向正确，消费者迁移清单需补齐 |
| F3 巨型文件和有限净删除 | R5-D/F | 先删后拆正确，计量口径需修订 |
| F4 运行时缺配置和两端漂移 | R5-E | 边界正确，可观察机制尚未冻结 |
| F5 Skill 非一等组件 | 第 2 节明确延后 | 延后合理；不得在 R5 宣称 Skill 注册已完成 |

F5 不需要在 R5 实现。R4 审查已经判定当前内容寻址提示资源是可接受的失败关闭边界；没有真实
插件需求时新增 Skill 物化会违反奥卡姆剃刀。R5 最终宣传口径应限定为 Agent、Transform、
Approval、Effect、工具、工作区、validator/projector 和 runtime factory 的单入口闭包。

### 2.3 未发现偷偷扩张的系统

方案没有要求新增：

- 数据库表或第四套 OperationRun 生命周期；
- 可变插件注册表、审批 provider 表或第二 catalog；
- Claim/Evidence 科学图、自动候选枚举或固定科研 DAG；
- Skill 市场、热卸载、在线升级、签名或远程 marketplace；
- 真实浏览器资格、许可证系统或真实 solver 生产化。

这些“不做”边界应保留。

## 3. 按严重性排序的发现

### F1（高）：设备参数领域迁移范围不完整，R5-C 的去领域化完成门按当前步骤无法达成

方案位置：

- `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md:123-140` 只明确迁移两个参数 Agent
  bridge；
- 同文件 `:244-290` 要求 Task/Root/readiness 去领域化，却没有列出通用插件和通用 Schema 中
  仍存在的参数实现。

现有代码证据：

- `src/scidiscovery/general_science_plugin.py:33-39` 直接导入四类设备参数模型，并在约
  `:938-1020`、`:2203-2310` 拥有参数审批 projector 和两个参数资格 Operation；
- `src/scidiscovery/general_transform_operations.py:22-29`、`:89-95`、`:732-817` 拥有参数
  coverage、uncertainty、provider 名称及其 Schema/validator；
- `src/scidiscovery/artifact_agent/schema/experiment_intent.py:25`、`:668-690` 在通用实验意图
  校验中直接解释 `DeviceParameterSet`；
- `src/scidiscovery/artifact_agent/schema/__init__.py` 仍公开设备参数类型；
- TCAD 插件目前反向从上述核心 Schema 导入这些类型。

可达场景：只完成两个 Agent Operation 后删除 `TaskService` 的 bridge 特判，core-only 目录仍会
编译参数资格、coverage 和 uncertainty，通用实验 validator 仍认识设备参数。新增别的领域虽然
不需要修改 Root，但“领域能力只存在于领域插件”仍不成立；删除核心 Schema 又会直接破坏
general-science 和 TCAD 插件导入。

最小修订：在 R5-A 或 R5-C 增加一个明确的“设备参数能力归属迁移”逻辑单元，范围只包括：

1. 两个参数 Agent Operation；
2. 参数 coverage、uncertainty、两个参数资格 Approval Operation 及 projector；
3. 设备参数 Schema/算法与实验意图中的参数映射校验；
4. TCAD author/reviewer 输入引用的 provider/Schema。

它们应由 TCAD 插件的同一个 `PLUGIN` 组装，Operation id 可以保持，编译 digest 允许断代变化；
通用 evidence、experiment、ApprovalService 和 ReviewDocument 不复制。修订必须明确 core-only
安装不出现设备参数 Operation、Schema import 或导出，而不是只扫描 Root/Task。

### F2（高）：旧 role loader 的生产消费者没有迁移方案，直接删除会破坏真实启动入口

方案位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md:142-154`。

现有代码证据：

- `src/scidiscovery/artifact_agent/runtime.py:81-105` 用 `load_roles()` 生成 legacy
  `role_output_contracts` 和 `role_context_policies`，并传给唯一 `TaskService`；
- `src/scidiscovery/platforms/codex.py:121-159` 同时从 `load_roles()` 和 CompiledCatalog 生成
  Agent 配置；`:231-236` 的安装 profile 验证也把旧角色加入期望集合；
- `codex.py:198` 还从同一 `platforms/roles.py` 模块读取 scheduler prompt；
- `deploy/install.sh` 的安装探针仍显式导入 `load_roles` 和 `load_transform_adapters`。

可达场景：R5-A 按清单删除 `platforms/roles.py` 或 `load_roles()` 后，`open_runtime` 和
`scid init codex` 不能启动。若实现者为避免失败保留空角色 loader，第二角色发现/装配权威又没有
真正删除。

最小修订：R5-A 的消费者清单必须明确四个替换，而不是增加兼容 facade：

1. 参数 bridge 迁移后，`TaskService` 的 legacy role contracts/context policies 为空或删除该
   构造参数的 legacy 分支；Operation task 继续只消费 `TaskOperationAuthority`；
2. Codex 只遍历一个 CompiledCatalog 生成 Operation Agent 配置和期望集合；
3. scheduler 静态文本资源保留为单独可读资源，但不得再承载角色发现或行为元数据；
4. 安装探针和 daemon 构造删除 `load_roles/load_transform_adapters` 消费。

相应负例必须从 clean-wheel 的 `open_runtime`、`scid init codex`、control daemon 和 Worker daemon
四个入口观察，而不只是断言 entry-point metadata 为空。

### F3（高）：生产者族计划依赖不存在的 Artifact 标签，且未定义修订族与重复族的总函数

方案位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md:194-228`。

现有代码证据：

- 计划第 199 行称 Transform 输出已有“请求 fingerprint 标签”；实际
  `mcp_root.py:1832-1914` 只把 operation id/version/digest/port 写入 Artifact labels，
  `request_fingerprint` 存在于实例级 `scheduler_bindings`，不是 Artifact provenance 标签；
- 当前修订恢复 `mcp_root.py:1575-1660` 依赖固定
  `science.revision.apply.intake.v1`、`science.intake.revise.v1` 和固定端口；
- `OutputPortSpec.revision_base_port` 描述的是 Agent 产生的 patch 输出；应用 patch 的 Transform
  则通过输入端口 `usage="revision_base"` 和 `usage="change_request"` 表达基线与 patch，当前
  revised-object 输出自身没有 `revision_base_port`；
- 方案要求“对每个审批输入”解析生产者族，却没有要求按同一次调用去重。同一 Agent bundle 的
  primary 和三个 collection 成员若都作为审批输入，会生成四份相同 family；当前 projector 的
  单族假设会被破坏。

影响：盲插件测试可能只能靠测试夹具手工补标签通过；真实 Transform/revision Artifact 无法稳定
恢复完整兄弟输出，或向 projector 交付重复、互相冲突的 family。此时 Root 固定端口虽然删除了，
但换成了不完备的隐式约定。

最小修订：R5-B 必须冻结以下无状态算法，不增加表或 provider registry：

1. 对所有 compiled Transform 输出统一写一个内容稳定的调用 fingerprint Artifact 标签，或明确
   证明只使用现有实例 binding 也能在别名、修订和重启后唯一恢复；当前代码证据支持前一种更小、
   更耐久的选择；
2. 用 `(operation id, version, digest, invocation fingerprint, ordered parent refs)` 校验同次调用，
   并按编译输出端口验证恰好完整的兄弟集合；
3. 对修订 Transform，从唯一 `usage=revision_base` 输入取得 base，从唯一
   `usage=change_request` 输入取得 patch，再读取 patch 输出合同中的 `revision_base_port` 验证它
   确实绑定同一 base；不得引用 intake 专用 id；
4. family 按不可变成员集合去重；同一调用出现两个不一致表示必须失败关闭；
5. projector 仍由插件按自己的审批端口挑选所需 family，Root 不新增端口白名单。

盲插件负例应增加“同一 family 的多个成员同时作为 subject”“语义别名无 fingerprint”“两个
调用父链相同但调用 fingerprint 不同”三种情形。

### F4（中）：运行时摘要和复杂度门缺少单一、可观察且不鼓励搬移/压行的口径

方案位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md:351-389`、`:371-387`。

运行时配置现状：`src/scidiscovery/operations/runtime_plugins.py:81-141` 返回的只有 adapter、tool
service 和 reconciler；`CompiledCatalog` 只公开 operation 与 runtime factory。control/Worker
daemon 没有现成健康握手，也没有配置摘要可供部署探针比较。因此“两个 daemon 计算并比较”目前
只是目标，无法由 R5-E 完成门观察。

最小修订：冻结一个非持久、启动期的最小机制，例如由两个 daemon 共同调用同一个纯函数，得到
`(plugin_id, configuration_schema_digest, raw_config_sha256)` 的排序摘要，并由一次性部署
preflight/health probe 同时读取两个 daemon 的实际启动参数后比较。摘要不写数据库、不进入
Artifact、不作为 capability。若不准备增加这个只读启动探针，则把“双 daemon 在线比较”明确
移交 R7，并将 R5-E 完成门收窄为两个 daemon 各自的缺配置早失败；不能一边条件性延后，一边要求
摘要漂移真实 daemon 负例通过。

复杂度现状：上位计划曾冻结 `spec.py <= 320`、`catalog.py <= 450`、`invoke.py <= 430`，当前分别
约为 390、636、494 行，而且代码已经使用多语句单行。继续以单文件物理行数作为硬门会鼓励压行
或把纯函数搬进 helper；这与 R5-D 的合理拆分目标相冲突。

最小修订：保留两项真正防作弊的门：

- 使用 R0 `test_baseline_structure_metrics.py` 的精确通用路径集合，加整个 `operations/` 包，按
  删除文件计零行，达到相对 8765 至少 10% 净减；
- 同时统计全仓 `src/ + plugins/` 生产代码，迁入插件不算删除，并由审查逐项核对“删旧权威”与
  “新增胶水”。

单文件预算降为诊断，不允许用压行达标；`compile_catalog` 的职责/圈复杂度和整个 operations 包
不增长才是拆分门。R5-0 必须生成一份机器可复现的基线，明确 `deploy/install.sh` 是否计入，避免
R4 报告与上位计划使用不同合计。

### F5（高）：R5-F 没有覆盖用户要求的“完整端到端科学 Agent 实际效果”

方案位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md:390-433`。

当前第 10.1 节主要是 pytest/clean-wheel/入口负例；第 407 行只在修改 Worker 边界时要求真实拉起
一个 Operation Agent，验证工具和文件生命周期。R5-D 已计划修改 Worker Router，因此该条件会
触发，但它仍只能证明授权与传输正确，不能证明多角色科学链在删重和拆分后仍能完成研究判断。

最小修订：在 R5-F 之后增加一个有界的 R5-G，或在 R5-F 内增加独立效果门。不得做三领域宏大
benchmark；只做一个当前已支持、数据冻结、规模很小的 TCAD 科学问题：

1. 使用本版本自己的隔离 state、control/Worker daemon、CompiledCatalog 和审批 UI；不连接
   8765 服务；
2. 至少真实拉起证据提取/审查、假设或实验设计、TCAD author/reviewer、结果诊断中与该问题实际
   需要的 Operation Agent；不能用测试代码伪造 RoleResultEnvelope；允许根据矛盾跳过不需要的
   角色，不为验收硬造固定 DAG；
3. 机械 transform、打包、评分和 Artifact/Task/Approval/Execution 生命周期走真实入口；
4. 强制区分两层 solver 证据：R5 必做冻结历史 solver 原始输出或 replay/fake adapter 的机械全链，
   只证明框架与诊断输入；真实 Sentaurus 仅在已有许可、外部执行 UI 授权和资源可用时附加运行，
   缺失不阻塞 R5，也不能把 replay 写成真实求解；
5. 人工审批只通过本地 UI 绑定精确对象。若 debug 环境使用已授权的代审者，报告必须标为调试
   决定，不得冒充用户或科学资格；
6. 由未参与生成的独立科学审查者按预先冻结量表评价：证据可追溯性、物理合理性、假设可证伪/
   可识别性、实验区分度、deck 与计划一致性、诊断与原始曲线/指标一致性；
7. 用相同冻结输入和大致相同模型/工具预算运行一个单 Agent 基线，并引用可解析的 8765 历史结果
   作为结构/科学参考；记录成功率、严重证据错误、专家评分、token/墙钟/修复次数，而不是要求
   R5 必须优于基线；
8. 失败必须归因为框架 admission/工具/文件链、Agent 科学判断、冻结数据/solver、人工审批等待或
   外部环境，不能用“端到端失败”掩盖根因。

通过标准应是：主链产生可独立审查的科学对象，没有因 R5 删除而丢失必要上下文/工具/输出，且
相对 R4/8765 未出现预先定义的严重退化。一次运行不能证明统计优越性，报告必须如实保留这个
限制。

### F6（低）：两项过宽表述会制造不必要工作

1. R5-C 的“删除 TaskMode”没有对应当前 `scheduler_topology.py` 中的精确符号。现有
   `RecommendedTaskMode/NextTaskMode` 是诊断和知识 payload 的受限建议字段，不是控制状态机。
   最小修订应只删除 `RoleRuntimeProfile/_ROLE_PROFILES/role_runtime_profile` 和被证实无消费者的
   readiness 拓扑，不因名称相似删除科学输出字段。
2. R5-B 已有一个盲审批插件夹具；R5-C 又要求一个最小表格研究插件，而 R6 还计划真正的表格
   领域 wheel。R5 只需复用同一个未知核心的合成测试插件验证 Root/Task/UI 零改动；真实第二领域
   接入和科学效果留在 R6，避免重复建设。

## 4. 正负例、回退和独立门判断

除上述缺口外，各阶段的门总体充分：

- R5-A 已要求 bridge 正例、旧入口真实失败、clean-wheel 和目录摘要不漂移；
- R5-B 已要求任意端口、兄弟缺失、digest 漂移和跨实例负例；补 F3 三项后可闭合；
- R5-C 已要求 core-only 无领域 import、readiness/preflight 不重复准入和权限负例；
- R5-D 明确每次只拆一个文件、共用原服务权威，并有逐文件回退边界；
- R5-E 对缺配置、损坏、符号链接和错误插件编号有负例；需按 F4 选定可观察摘要机制；
- 每阶段都有未参与实现的独立审查门，结论语义清楚。

“有条件通过”在本计划中不允许进入下一阶段，这一点正确。实现时应冻结每个阶段精确 diff 或
候选清单，避免审查者在共享工作树中把后一阶段修改误算为前一阶段证据。

## 5. 文档权威与状态

当前文档角色基本自洽：

- `OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 是总体目标、约束和阶段状态权威；
- R5 详细计划是未实施的活动提案；
- R4 功能/解耦报告是绑定 R4 候选的审计输入，不是 R5 状态权威；
- R0—R4 历史失败/通过报告应保持不可改写。

当前总体计划把 R4 标为通过、R5 标为未开始，R5 详细计划标为待独立审查，与代码尚未开始 R5
实施的事实一致。本报告打回后，只应把 R5 详细计划/总体状态改为“方案打回修订”，不能把 R4
历史候选改写成失败。

`docs/ARCHITECTURE.md` 与中文版本目前仍描述按 allow-list Schema 选择 renderer，和 R4 已实现的
固定 ReviewDocument renderer 不一致；R5-0 已正确承接该事实同步。修订方案时无需提前重写历史
报告，但 R5-0 完成门必须包含中英文语义核对，而不只做链接检查。

## 6. 本轮未执行的验证

本轮是方案审查，没有运行全仓或聚焦 pytest，也没有启动 daemon、Codex Agent、审批 UI 或
solver。审查使用了 7 GiB 地址空间上限和串行只读命令，核对了：

- R5 详细计划、上位计划及 R4 功能/解耦报告；
- CompiledCatalog/OperationSpec、Root/Task、legacy role/transform loader；
- Codex 配置生成、runtime plugin 加载、审批生产者族、参数 Schema/Operation 归属；
- 现有 R0 复杂度口径和历史真实 Agent 证据位置。

因此本报告判断的是方案是否可执行，不继承或重新证明 R4 的 121/245 项测试结果。

## 7. 冻结的最小修订清单

再次送审前，只需完成以下六项文本修订，不得借机扩大 R5：

1. 把设备参数 Schema、coverage/uncertainty、参数审批/projector 和参数感知实验校验纳入 TCAD
   单插件归属迁移，并增加 core-only 反例；
2. 为 `runtime.open_runtime`、Codex init/profile、scheduler prompt 和安装/daemon 探针列出旧
   role/transform loader 删除后的精确替代；
3. 修正 producer fingerprint 事实，冻结 Transform 调用族、修订 base/patch 解析、去重和三项
   新负例；
4. 为 R5-E 选定一个非持久、可由两个真实 daemon 启动入口观察的摘要探针，或明确降级到 R7 并
   收窄 R5 门；
5. 用 R0 固定路径加全仓生产口径取代可压行/搬文件的单文件硬门，并明确计数脚本；精确删除
   RoleRuntimeProfile，不删除科学 payload 的建议字段，R5 只保留一个合成盲插件夹具；
6. 增加一个真实 Operation Agent、冻结 TCAD 数据、UI/机械链、独立科学评分、单 Agent 与 8765
   参考、失败归因清楚的有界端到端效果门；真实 solver 保持可选，不扩成三领域 benchmark。

修订后仍应保持 R5-0 为第一实现阶段；方案复审通过前不得修改生产代码。

## 8. 最终结论

**打回**

