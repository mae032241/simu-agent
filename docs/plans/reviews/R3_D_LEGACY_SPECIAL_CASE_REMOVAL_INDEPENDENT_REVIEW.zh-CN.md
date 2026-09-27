# R3-D 通用科学特判拆除独立审查

审查日期：2026-08-28  
审查对象：`baseline/8765-codex@404aeb1` 叠加当前 R0—R3-D 工作树  
审查性质：未参与本轮实现的跨边界、只读独立审查  
最终结论：**通过，允许进入 R3 总审查**

## 一、结论与适用边界

R3-D 已达到本阶段完成门：五个已迁移通用角色不再拥有 legacy 创建入口、
Codex Agent 配置或 output profile 双权威；结构化修订、完整实验计划、图证据和
曲线误差诊断均由同一 `general_science` 插件中的编译 Operation 承接；静态
readiness 角色拓扑已删除；默认派发仍为父调度会话
`task_prepare_dispatch → spawn_agent`；设备参数提取/独立审查和两个 TCAD 角色被
收窄为四个明确的 R4 前领域桥，没有重新泛化为第二套科研行为系统。

本轮审查先后发现并打回了三类真实缺口：旧 scheduler/readiness 入口和设备参数审查
断链、设备参数 extractor 仍加载宽泛 revision/figure context、显式
`catalog_scope` 导致 ABI3 后旧真实运行证据失配。当前三项均已用最小修改闭合，且
最后一项已由当前 ABI3 的三份新真实 `spawn_agent` 运行重新证明。

本结论只允许进入 **R3 总审查**，不表示 R4 领域插件迁移、R5 全局复杂度目标、真实
TCAD、生产凭据、网络硬隔离或外部副作用已获放行。

## 二、审查方法与独立证据

本审查完整读取了活动架构计划、R3 实施记录、R3-A/B/C 历史审查、当前源码、
测试和运行证据；按 Operation → Root → Task → Worker → Artifact → 安装配置 →
恢复/封存边界追踪实际可达路径。没有把实施记录或资格报告中的 `pass` 当作事实。

独立执行结果：

| 检查 | 独立结果 |
| --- | --- |
| `pytest -q` | `155 passed in 47.78s` |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| R3-D 部署顺序与配置探测聚焦测试 | 6 项通过 |
| catalog/context/R3 authority 聚焦测试 | 24 项通过 |
| ABI3 文本、PDF、图像证据逐事件复核 | 三份均通过 |
| 核心预算 | `spec/catalog/invoke = 331/449/410`，合计 `1190 ≤ 1200` |

全仓第一次复跑曾在主进程并行构建同一 fixture wheel 时得到
`140 passed, 15 errors`；15 个错误均共享 setuptools/egg-info 并发构建前置失败。
在并行进程结束后，单独 wheel、安装态用例和上述串行全仓复跑全部通过。因此该记录是
共享测试源目录的并发噪声，不是被隐藏的产品失败；最终证据只采用串行结果。

## 三、R3-D 完成门逐项判断

### 3.1 五个通用角色已退出 legacy 创建面

`platforms/roles.py:21-24` 的核心 legacy 列表只含设备参数 extractor 和其专用
auditor；`ROLE_NAMES` 另外只拼接插件提供的两个 TCAD 角色。`ideator`、`critic`、
`evidence_auditor`、`experiment_designer`、`diagnostician` 只出现在
`platforms/roles.py:26-35` 的保留名称碰撞拒绝集合，不再由 `load_roles()` 创建。
领域 role pack 若试图恢复这些名字，会在 `platforms/roles.py:163-169` 启动失败。

`runtime.py:85-110` 只为 `load_roles()` 的四个领域桥装配 legacy output/context
合同；Operation catalog 独立作为同一运行态目录注入 TaskService。Codex 生成器在
`platforms/codex.py:108-146` 分别投影剩余 legacy bridge 和编译 Agent Operation；
已迁移角色不会再生成旧 TOML。安装探测在 `platforms/codex.py:218-295` 要求 Agent、
MCP、模型、原生工具和精确 Worker 工具集与同一 catalog 完全一致。

结论：未发现五个通用角色的可写 legacy task、Codex Agent 或 output profile 双入口。
仓库中保留的旧角色 Markdown 不是运行时创建权威；它们可在 R4/R5 清理，但当前不可达。

### 3.2 四类旧合同由 Operation 等价承接

`general_science_plugin.py:884-1272` 定义普通 evidence、hypothesis、experiment、
object review 和 diagnosis Operation；`general_science_plugin.py:1275-1531` 定义图证据
bundle/audit 和曲线误差诊断；`general_science_plugin.py:1534-1610` 定义三类有界
revision。完整实验计划不由 Worker 手工膨胀，而由 support Operation
`science.experiment.materialize.v1` 确定性物化。

等价性不是只靠名称替换：

- 图证据 Operation 声明主输出、source panel、overlay、curve table、validation report
  的数量、媒体类型、单项/集合上限，并由
  `general_science_plugin.py:1275-1334` 的 bundle validator 绑定完整文件束；
- 曲线诊断在 `general_science_plugin.py:1470-1529` 精确声明 plan、metric report、
  curve bundle、`worker_curve_analyze` 和 plot collection validator；
- revision 在 `general_science_plugin.py:1534-1583` 把唯一 `revision_base`、
  `change_request`、允许 JSON Pointer 和 contextual validator 放入同一 Operation；
- experiment intent、critic/audit、object review 和 diagnosis 的父对象闭合由各输出端口的
  context validator 与 context sources 承担；
- Worker 工具、原生读取、网络、预算和输出文件数量从同一 compiled operation 投影。

Root legacy `task_schedule` 在 `mcp_root.py:1485-1505` 只接受设备参数两个专用角色，
在 `mcp_root.py:1589-1592` 无条件拒绝 legacy revision scope。TaskService 已删除旧
`primary_profiles`、图 bundle 控制生成、旧 diagnosis signal 和 figure handoff 分派。
`tasks.py:5653-5737` 仍按已知科学 Schema 做任务内 source-key/web-snapshot 绑定；这是
finalize 时的通用来源完整性硬门，不再选择角色、工作流或科学 verdict，故不构成 R3-D
阻断。R4 的第二领域若仍需为新 Schema 修改此 switch，应在 R3 总审查/R4 被视为插件化
失败，而不能把它扩展成新的领域注册表。

结论：四类旧 profile 的实际行为边界已由 Operation 承接，未通过改弱 validator 或删除
科学父链来换取测试通过。

### 3.3 删除 experiment-designer 首检查点没有破坏生命周期

旧 `experiment_designer` 专属首 lease、首次 JSON checkpoint 和专属修复注入已退出。
当前 Operation 在 `mcp_root.py:1180-1225` 从编译限额生成一个既有 `TaskBudget`，继续复用
TaskService 的 claim、绝对 deadline、heartbeat、checkpoint、validate、sealed finalize 和
CAS 终态。全仓生命周期、超时、恢复、handoff-only 和封存回归均通过。

三份 ABI3 真实运行的 tasks 数据库均呈现唯一
`created → dispatched → claimed → completed`，最后活动为 `finalized`；没有出现因删除
角色特判而提前超时、绕过校验或新增 attempt。该角色特判原本不是科学必要条件，删除后由
通用任务预算承担是正确收敛。

### 3.4 R4 前领域桥是最小且闭合的

当前四个 legacy 角色是：

1. `evidence_extractor`，只允许 context
   `scidiscovery.evidence-intake.device-parameters.v1` 和 output profile
   `device-parameter-evidence`；
2. `device_parameter_evidence_auditor`，只允许唯一 parameter-audit context 且不接受
   output profile；
3. `tcad_deck_author`；
4. `tcad_deck_reviewer`。

专用 extractor prompt 在 `roles/evidence_extractor.md:1-40` 明确拒绝普通 evidence、图
证据和 revision；专用 auditor prompt 在
`roles/device_parameter_evidence_auditor.md:1-18` 只审查参数 bundle 的四项科学问题。
首轮修复后 auditor 已恢复“提出者—独立审查者”责任闭环。

终审又发现 extractor metadata 曾指向包含 `default`、structured revision 和 figure
revision 的宽泛 `SCIENTIFIC_REVISION_CONTEXT_POLICIES`。现已在
`core_context_policies.py:148-157` 建立只含唯一 device intake profile 的
`DEVICE_PARAMETER_EXTRACTOR_CONTEXT_POLICIES`，并由
`platforms/roles.py:39-57` 分别绑定 extractor/auditor 两个专用集合。独立调用验证
`default`、structured revision 和 figure revision 均以 unsupported context 失败关闭。

Root 在 `mcp_root.py:1490-1505`、`1572-1588` 再做精确组合门，防止专用角色被换 profile
恢复通用行为。设备参数 coverage、审查、批准组和下游整组准入仍闭合。scheduler prompt 和
实际根 `AGENTS.md` 只列 R4 前 TCAD 闭环所需的精确 domain-only transform profile，且明确
禁止已迁移 generic profile。

结论：专用 auditor 是保持独立科学审查所需的合法领域桥，不是新增通用角色；四个桥均有
明确 R4 删除边界。

### 3.5 readiness、目录和默认派发没有第二权威

`scheduler_topology.py:21-49` 不再保存 `_ADVICE`、`_CAPABILITIES`、阶段表或领域拓扑；
它只对传入的 catalog public 投影做 Schema/数量库存过滤。Root 在
`mcp_root.py:951-984` 从 `self._operation_catalog.scheduler_projection()` 派生可选操作编号，
精确输入、资格、current、review 和副作用仍由 preflight 决定。它没有替 Agent 选择科学
行动，也不返回退役角色名。

本轮按用户提出的可见性问题，将 `catalog_scope` 变为
`OperationSpec` 的显式冻结字段。`operations/spec.py:186-199` 只接受
`public/support/internal`，仍保持十个顶层字段；`operations/spec.py:277-305` 将该字段和完整
spec 一起纳入 ABI3 摘要并投影到 scheduler view；`operations/catalog.py:37-48` 仍只有一个
不可变 operation 映射。分类没有独立配置文件、数据库表、allowlist 或第二 registry，也不再
从 executor 类型/Operation 名称猜测科学可见性。因此显式 `catalog_scope` 是行为闭包的一部分，
符合“单一注册后编译”，并没有把复杂度移回 scheduler。

当前 catalog 独立枚举为 `public=15`、`support=13`、`internal=3`；三者是同一
`CompiledCatalog` 的过滤视图。`general_science_plugin.py:1753-1762` 是 15 个 Agent 与 13 个
support transform 的唯一通用科研插件入口。

默认派发没有接回 `CodexTaskDispatcher`：Root 只准备精确派发票据，父调度 prompt 仍要求
`spawn_agent(fork_turns="none")`。独立 Codex 进程代码继续作为后续权限加固基座，不是当前
Root 默认路径。

### 3.6 R3-C 唯一 transform 权威未退化

`operation_invoke` 在 `mcp_root.py:1118-1178` 对 Agent、Transform、Effect 复用同一编译调用。
`transforms.py:717-730` 对 ScientificStateTransformAdapter 已迁移的全部通用 profile 无条件
拒绝，显式注入旧 adapter 也不能恢复旁路。`artifact_transform` 只保留 R4 前精确 TCAD/curve
domain adapter 兼容面；public/support/internal 目录修改没有重新开放旧 generic profile。

因此 R3-C 的“catalog 是选择权威、旧 adapter 不是新功能入口”结论未退化。

## 四、ABI3 真实 `spawn_agent` 证据复核

新增显式 `catalog_scope` 后，Operation ABI 从 2 升为 3，
`science.evidence.extract.v1` 的当前摘要变为：

`10018a01acfef7b71a137e43214f8fd7edba7514b2ebc8a134ded6bce7c85746`

旧 run8/run5/run3 的 `a61600...` 摘要不再代表当前编译合同。实施方已将它们降为历史证据，
并生成以下三份 ABI3 新运行：

- `deliverables/debug-evidence/r3-science-agent-text-abi3-run1`；
- `deliverables/debug-evidence/r3-science-agent-pdf-abi3-run1`；
- `deliverables/debug-evidence/r3-science-agent-image-abi3-run1`。

独立逐行解析父/子 Codex JSONL、MCP item-completed、工具输出、tasks.sqlite3、Task/输入/
输出 CAS 后得到：

| 边界 | 文本 | PDF | 图像 |
| --- | --- | --- | --- |
| 当前 Agent | 三者均为 `op_science_evidence_extract_v1_10018a01acfe` |
| 父调用 | 仅 `spawn_agent`、`wait_agent` | 同左 | 同左 |
| `fork_turns` | `none` | `none` | `none` |
| 首个子 MCP | exact server 的 `worker_claim_task` | 同左 | 同左 |
| 其他 Worker/Root/网络 | 无 | 无 | 无 |
| 原生能力 | task-local 文本读取成功；一次错误 Schema 相对路径失败后在同一任务根修正 | task-local `pdftotext` 退出码 0，注册 `worker_extract_pdf_text` 成功并读取冻结 excerpt | 同 call id 的 task-local `view_image → ImageView` 成功 |
| 写入生命周期 | exact Worker server 的 begin/chunk/commit → validate(valid) → finalize(completed) | 同左 | 同左 |
| Artifact | CAS 摘要匹配，严格 `ScientificIntake` 通过，唯一 evidence/source alias 为 `source_material` | 同左 | 同左 |
| Root 终态 | `completed` | `completed` | `completed` |

三份报告中 codex-events 和每个 session JSONL 的 SHA 均由审查者重新计算并匹配。所有原生命令
的工作目录、显式绝对路径和媒体路径均在 `worker_materialize_assignment` 返回的精确任务根内。
文本运行中首次误读不存在的 `output.schema.json` 返回 code 1，但没有越界，随后读取正确的
`schema/output.schema.json` 并成功完成；这是真实可修复交互，不应伪装成全程无失败。

因此 ABI3 变更造成的证据代际失配已闭合，不能再以旧摘要作为当前完成门。

## 五、安装态与当前 `.codex` 快照

当前检出目录的 `.codex` 是未重新初始化的旧生成快照，直接调用
`validate_installation_profile()` 会因 Agent/MCP 集不匹配而失败。它不是被忽略的生产成功：
受支持安装入口在 `deploy/install.sh:615-678` 使用同一已安装 catalog 对 source root 和外部
workspace 执行 `initialize_platform()`；`install_all()` 在
`deploy/install.sh:897-929` 严格按“configure → systemctl enable --now → verify”执行；启动后
`verify_installation()` 在 `deploy/install.sh:729-775` 再调用
`validate_installation_profile()`，不一致会令安装事务失败并回滚。

`tests/artifact_agent/test_deploy_scripts.py:497-520` 自动固定重编译早于服务启动、完整验证晚于
启动的顺序；`test_platform_configuration.py:181-205` 动态证明初始化和验证消费同一 compiled
catalog。由此，checked-in `.codex` 不是部署权威；开发者若绕过 installer，仍必须先执行受支持
的 `scid init codex`。这一点应继续在 R3 总审查中保持可见，但不阻断 R3-D。

## 六、33 项约束族不退化判断

仓库没有“33/33”可执行脚本，本报告不伪称存在。按计划定义的行为约束族审查如下：

| 约束族 | 判断 | 依据 |
| --- | --- | --- |
| 不可变 Artifact、精确谱系、current | 不退化 | Operation 绑定精确 ref；CAS/父链/finalize 复用既有权威；真实输出摘要匹配 |
| Worker 拥有科学内容 | 不退化 | prompt 负责提取/批判/设计/诊断；validator 只做结构、机械一致性和来源闭合；readiness 不替 Agent 排序 |
| Agent 间文件通信 | 不退化 | 三份真实链均无父 Worker 代写或直接科学消息，结果只经受控文件与 Artifact 交接 |
| 最小输入、路径、工具、网络 | 不退化但仍是原型 | compiled 端口/工具/预算同源；exact Worker 服务与任务根实证通过；`inherited_prototype` 不构成 OS 级硬隔离 |
| 独立科学审查与人审 | 不退化 | reviewer Operation 精确绑定；设备参数桥恢复专用 auditor；聊天不写决定，外部副作用仍需 UI |
| 确定性/Agent/Effect 边界 | 不退化 | support transform 无选择权威；Agent 产科学判断；domain adapter/ExecutionService 才持有副作用 |
| 幂等、attempt、deadline、恢复、CAS | 不退化 | 未新增 OperationRun 或状态机；通用 Task 生命周期和原恢复负例全过 |
| 单插件入口、单 catalog、无核心 allowlist | 不退化 | `scidiscovery.plugins` 单入口组；显式 scope 位于同一 spec/digest；readiness/平台配置同源投影 |
| TCAD 能力保留 | 本阶段闭合 | 参数 extractor/auditor、author/reviewer 和精确 domain transform 桥可达，删除边界明确为 R4 |

没有新增科学图、资格状态机、OperationRun、并行注册表或控制面科学决策。`inherited_prototype`
仍只证明提示约束被真实 Agent 遵守和服务端硬门有效，不能写成“未声明工具在平台层不可见”。

## 七、复杂度与过度设计判断

相对 R0 基线：

| 文件 | R0 | 当前 | 判断 |
| --- | ---: | ---: | --- |
| `scheduler_topology.py` | 341 | 68 | 静态阶段/能力表实质删除 |
| `platforms/roles.py` | 339 | 328 | 通用角色权威退出，仅留领域桥与安装发现 |
| `runtime.py` | 256 | 215 | 通用 profile 装配删除 |
| `operations/spec.py + catalog.py + invoke.py` | 0 | 1190 | 在冻结 1200 行预算内；统一替代分散注册/调用权威 |
| `mcp_root.py` | 2616 | 2931 | 仍增长，R3 不能宣称整体控制面已净减 |
| `tasks.py` | 6952 | 7318 | 仍增长，R5 全局净减目标尚未完成 |

本阶段的复杂度下降是真实的：341 行领域化 topology 被压到 68 行同源库存投影，五个通用
legacy 角色、四类 output profile、figure/signal/first-checkpoint 特判退出，新增可见性只增加一个
OperationSpec 字段而未增加 registry、表或生命周期。

但 R3-D 通过不等于全仓已经变轻。Root/TaskService 仍大于 8765 基线，通用插件合同本身也较长；
R5 仍必须按计划计算“通用核心净减至少 10%”和全仓生产代码净变化，不能用文件搬迁、测试数量或
本报告的阶段通过替代。当前遗留的未引用通用 context 常量、旧 prompt 文件和
`tasks.py` 的通用 source-binding Schema switch 是后续可审计的删除/抽象候选，但它们没有形成
R3-D 的运行时第二行动权威。

## 八、测试是否通过修改断言掩盖回归

未发现通过删测试或放宽安全断言掩盖功能回归：

- legacy 通用创建从正向测试改为失败关闭负例，符合明确删除决策；
- role/profile 数量断言只更新为当前四个领域桥，并新增 role-pack 碰撞、错误 context、错误
  output profile 和 generic legacy task 拒绝；
- readiness 新测试从空库存、单 opaque source 和科学对象库存验证只返回 public Operation id，
  不再接受旧角色名；
- extractor 专用 context 测试明确拒绝 `default`、structured revision 和 figure revision；
- ABI3 新测试证明 catalog scope 来自声明而非 executor/编号推断，并拒绝未知值；
- 当前 ABI3 真实运行重新覆盖文本、PDF、图像、精确 namespace、任务根、媒体工具和完整封存，
  没有用旧 ABI2 摘要冒充当前证据。

仍有一个非阻塞测试边界：R3-D 没有重跑真实 TCAD 或真实外部副作用；该行为被计划明确留给
R4/R7，且 `inherited_prototype` 不允许以本轮调试证据放行，因此不是应由修改断言隐藏的失败。

## 九、阻断项与非阻断项

### 阻断项

无。

### 非阻断项

1. `inherited_prototype` 不是平台级最小权限隔离；真实 TCAD、网络写入、凭据和不可逆副作用
   继续禁止，必须走后续精确 Worker/执行授权加固。
2. 四个 legacy 领域角色、一个 device collection profile、两个精确 parameter context 和
   domain-only TCAD transform 清单必须在 R4 迁入领域插件后删除；不得长期留在核心。
3. 当前 checkout 的 `.codex` 陈旧；受支持 installer/init 会在启动前重建并在启动后失败关闭
   校验。不得把未经初始化的 checkout 描述成可直接运行的安装态。
4. Root/TaskService 总行数仍高于 R0；R3 总审查应确认这属于已列明的阶段债务，R5 必须按全仓
   口径验证真实净减。
5. 新领域若必须修改 `tasks.py` 的来源 Schema switch 才能获得精确 source binding，应判定为
   R4 插件化失败，而不是继续加核心分支。

## 十、最终决定

**通过，允许进入 R3 总审查。**

放行理由是：R3-D 的旧通用角色/profile/静态 topology 和科学特判已经退出实际创建路径；
Operation 合同等价承接 validator、bundle、context、revision、工具和预算；设备参数/TCAD 桥
已收窄且保持独立审查；显式 `catalog_scope` 仍在同一行为闭包和摘要中；当前 ABI3 的三份真实
`spawn_agent` 证据和 155 项串行全仓回归共同证明默认路径没有退化。上述非阻塞边界必须由
R3 总审查继续保留，不能被本阶段通过提前解释为 R4/R5 或生产安全完成。
