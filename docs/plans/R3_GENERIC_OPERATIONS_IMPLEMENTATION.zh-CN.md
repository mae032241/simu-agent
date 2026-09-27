# R3：通用智能体与确定性变换迁移实施记录

状态：通过。R3-A—R3-D、三种目录视图和总审查返工均已完成；第二轮独立总审查明确允许
进入 R4-A。聚焦 134 项、全仓 167 项通过

基线：`baseline/8765-codex@404aeb1`，叠加已通过独立审查的 R0—R2 工作树。

## 1. 目标与非目标

R3 把六个通用科学智能体、修订/附件等独立合同和通用确定性变换迁到唯一
`scidiscovery.plugins` 目录，使 prompt、输入、输出、校验、工具、网络和预算只由编译后的
`OperationSpec` 决定。继续复用既有 Task、Artifact、Approval 和 Execution 生命周期，不增加
OperationRun、资格副本、current 副本或新的科研流程状态机。

R3 不迁移 TCAD、curve-score、领域审批视图或真实外部执行；这些仍属于 R4。R2 的父权限继承
原型不能用于真实 TCAD 或生产副作用。当前首版必须继续使用 R2 已通过的
`task_prepare_dispatch → spawn_agent` 路径；编译提示显式列出允许和禁止能力，服务端门禁与
受控文件生命周期保持权威。每任务独立 Codex 进程仅是下一版本加固代码，本版不得接默认
Root，也不得替代真实 `spawn_agent` 验收。

## 1.1 派发偏离纠正

R3-A 实施时错误地把 `CodexTaskDispatcher` 接成 Operation Agent 的默认 Root 派发器。该变化
不是 R2 的自然延伸，而是直接违反以下已通过决策：

- R2.14：首版真实验收使用 `spawn_agent`，允许基础权限继承，并由编译提示显式限制行为；
- R2.18：独立 Codex Worker 只保留为下一版本加固基座，不接默认 Root；
- R2 第二轮通过结论：提示词白名单是原型约束，不能冒充生产隔离，但它仍是当前快速闭环的
  已选路径。

因此，R3-A 原独立复审对输出合同、附件、上下文、校验和 Task 投影的结论可以保留；对
“默认独立进程派发已经完成并可进入 R3-B”的放行已失效。R3-B 中通过独立进程取得的任何
文本、PDF 或图像运行结果都只能作为备用进程路径的调试材料，不能证明当前版本完成门。

本轮修复完成门：

1. 撤销 Root/MCP 默认创建 `CodexTaskDispatcher` 的接线；
2. 恢复 R2 已通过的 `task_prepare_dispatch → spawn_agent` 调度语义；
3. 保留独立 Worker 代码和测试，但明确标为非默认、下一版本加固基座；
4. 用真实 `spawn_agent` 重验一个 Operation Agent 的原生工具、已注册领域工具、受控写入、
   validate/finalize、Root 状态确认和父会话零科学代写；
5. 由独立审查者同时检查实现正确性与是否再次偏离“快速闭环、轻控制面、OperationSpec
   单一注册”的目标。未通过前不得恢复 R3-B。

截至 2026-08-28，五项均已完成：Root 与部署入口不再创建 `CodexTaskDispatcher`，
`task_prepare_dispatch` 只返回编译后的 `agent_type` 并准备既有 Task；Codex 启动配置重新从同一
`CompiledCatalog` 生成 Operation Agent 和继承用 Worker MCP 配置。新一轮独立复审见
`reviews/R3_A_SPAWN_DISPATCH_REVIEW.zh-CN.md`，结论为通过、允许恢复 R3-B；该结论不放行
R3-C、真实 TCAD 或任何生产副作用。

## 2. 进入 R3 前的中断恢复基线（历史）

- R2 第二轮独立审查已通过；专项 63 项、全仓 94 项通过。真实 run 6 仍是 R2
  传输原型的历史证据，但 R3 已升级 operation ABI，不能把旧摘要下的运行结果当作当前
  Agent 合同的真实 Codex 证明。
- 运行时只有一个 `CompiledCatalog`，Operation 调用复用现有 Agent/Transform/Effect 生命周期。
- 当时的 Agent Operation 只支持一个 JSON 主输出，不能从 spec 投影附件集合、上下文校验或修订
  边界；R3-A 已补齐这些通用合同，但六个通用角色仍留待 R3-B 迁移。
- 六个通用角色的行为元数据仍在 `roles/*.md` frontmatter、`platforms/roles.py`、
  `runtime._role_primary_output_profiles`、`core_context_policies.py` 和 TaskService 中分散存在。
- `artifact_transform` 的旧 profile adapter 仍是通用变换选择权威。
- 当时工作树已有用户授权保留的精确 capability、稳定 proxy、Broker 恢复和独立 Codex Worker
  代码，但明确不得接默认 Root。R3-A 后来接通默认精确进程路径属于已确认的架构偏离，必须
  回退；不能把这段历史写成当前能力进展。

## 3. 分段完成门

### R3-A：规范生成完整 Agent 合同

1. 一个 Agent operation 恰有一个主输出，可另声明有界附件集合；全部 Task 输出字段从同一
   compiled operation 投影。
2. 主输出、附件项、附件集合和上下文校验均调用 catalog 内已编译组件，不使用 role/profile
   locator fallback。
3. 输入端口固定 `allow_additional=False` 语义；调用者不能补充 spec 未声明输入。
4. Operation Agent 默认沿用 R2 `spawn_agent` 快速闭环，复用同一 Task
   attempt/deadline/finalize 权威；子 Agent 接收编译角色和显式允许/禁止能力说明。独立 Worker
   进程不得成为本版默认派发器。

### R3-B：迁移通用智能体

六个基础角色及 evidence/figure/revision/curve-diagnosis 等不同合同使用独立 operation id。角色
Markdown 只保留 prompt 正文；新增一个测试 Agent operation 时只修改插件声明、组件/prompt
和测试，不修改 Root、TaskService、UI、scheduler 或 allowlist。

### R3-C：迁移通用确定性变换

每个保留的 `ScientificStateTransformAdapter` profile 映射为 transform operation；新调用只按
operation id 选择，父链和非资格输入由端口/guard 声明。旧 adapter 只能作为内部 callable
组件，不再作为新功能入口。

### R3-D：删除通用科学特判

删除 runtime 的通用 role 输出/profile 装配和 TaskService 中已经被 operation 组件取代的
figure、parameter、structured revision、diagnosis 分派。TaskService 只保留文件生命周期、
尝试/期限、CAS、网页证据冻结和 finalize 等通用责任。

## 4. 审查与回退

R3-A/B/C/D 分别聚焦测试并独立审查，任何一段未通过不得进入下一段。回退只移除该段的新
投影或迁移，不恢复第二注册权威。R3 总审查必须同时确认科学内容仍由 Worker 负责、确定性代码
没有产生科学判断、插件没有泄漏到核心、复杂度没有通过转移文件伪装下降。

## 5. R3-A 实现结果与已撤销偏离

- operation ABI 升为 2；输出端口可声明有界 collection、collection bundle validator、
  contextual validator/source 和 structured revision 边界，这些仍是冻结数据引用，不包含
  执行方法或状态。
- `agent_task_output()` 从编译后的输出端口一次性投影既有 `TaskOutputSpec`。Operation 任务的
  locator 字段保持为空；主输出、附件项、附件集合和上下文校验直接调用同一
  `CompiledOperation.implementations`，不回退到 role/profile locator。
- 编译期拒绝：非单一 JSON 主输出、任一输出缺 validator、上下文来源越界、无效修订路径、
  修订与附件集合并存、输出总量超过 operation 限额。调用期仍拒绝全部未声明输入和参数。
- 上下文来源按精确端口别名或严格三位编号别名匹配；`agent_input` 不会误读取
  `agent_input_extra`。附件集合必须与 `bundle.json` 文件集合完全一致，并在封存前执行已注册
  item/bundle validator。
- 真实 Task/Worker 文件闭环先让错误附件集合失败关闭，再以新的精确任务完成主输出、附件、
  validate 和 finalize；失败任务没有声明删除能力，因此没有为测试放宽权限。
- 首次独立审查打回的修订 scope、旧 figure/parameter 特判、Task 输出不可表示合同、运行时语义
  不可见、全 catalog 工具冲突、附件 codec 死声明和虚假内存上限均已闭合：修订 scope 在
  Operation 主输出路径强制；Operation bundle 不再进入旧科学特判；完整 Task 输出投影在启动期
  失败关闭；每个 Agent 输出必须引用同源语义合同资源；Worker Router 只解析当前 Operation；
  附件 codec 必须实际执行且文件已是规范字节；未执行的 `memory_mb` 已从合同删除。
- **已撤销的错误实现：**Root 曾对 Operation Agent 默认启动独立 Codex 进程；该接线已经从
  `RootToolFacade`、Root router、控制守护进程和部署服务中移除。当前默认路径重新由父调度会话
  调用 `spawn_agent`。启动期从同一编译目录生成每个 Operation Agent 的 prompt、模型、原生工具
  声明和精确 Worker 工具集，并为 Codex 0.150.1 注册子 Agent 继承所需的 Worker MCP。由于该
  版本会让子 Agent 看到父配置中的其他能力，编译提示明确写出“可见不等于允许”；服务端 Task
  权限、Worker 准入、受控文件、validator/finalize 和副作用门仍是硬边界。提示约束不宣称为
  生产级隔离。独立进程、精确 capability、稳定 proxy 和恢复代码继续保留并有单元测试，但只作
  下一版本加固基座。
- 插件领域工具处理函数只接收已按其 Pydantic 合同校验的请求，不再获得完整 TaskService、会话
  令牌或 Worker 身份。额外 Agent resource、自定义工作区名和非单项/非 `revision_base` 用途的
  修订基端口在尚无真实运行协议时编译失败，不允许“进入摘要但运行期不用”的虚假能力。
- 历史 run 12 由 Root 拉起独立 Codex 进程，完成精确输入读取、注册领域工具调用、受控文件写入、
  校验与 finalize；原生 shell、网络和未声明分析工具均未获授权，兄弟路径密文没有出现在事件流，
  结束后认证副本和派发票据均不存在。证据保存在
  `deliverables/debug-evidence/r3-exact-agent-run12/`；该目录是本地调试证据，不进入源码发布或提交，
  脚本生成的任务签名密钥会在退出时删除。该记录只证明备用进程代码曾运行，不再作为当前
  R3-A 完成门或进入 R3-B 的证据。

## 6. R3-A 自动化证据

| 检查 | 结果 |
| --- | --- |
| `pytest -q tests/operations tests/artifact_agent` | 122 项通过，43.51 秒 |
| `pytest -q` | 122 项通过，43.86 秒 |
| `python -m compileall -q src tests/operations` | 通过 |
| `git diff --check` | 通过 |
| 33 项架构约束族 | 当前 8765 基线没有逐项验证脚本；由完整行为回归和独立跨边界审查覆盖，不伪称脚本通过 |
| `wc -l operations/spec.py operations/catalog.py operations/invoke.py` | 319 / 449 / 428；合计 1196，不超过冻结的 1200 行总预算 |
| 真实 Codex `spawn_agent` | `.scidiscovery-state/r3-spawn-agent-native-run5/qualification-report.json` 11 项全通过 |

第五次真实运行证明了父会话实际调用 `spawn_agent`、子角色与编译摘要一致、原生代码工具以
退出码 0 成功读取任务文件、已注册领域工具调用成功、父会话没有代调 Worker、结果通过受控
写入/校验/finalize，且 Root 最终观察到 `completed`。Operation Agent 没有自定义只读权限
配置，而是继承父会话基础权限；调试父会话运行在当前外层工作区沙箱内，不再叠加 Codex
0.150.1 的第二层 bubblewrap。由编译提示列出的禁止行为只是首版原型约束，不能证明网络或
原生写入已被硬隔离，也不得据此放行真实外部副作用。

前三次和第四次运行只作为失败诊断保留：第三次的旧检测器只看到了原生调用事件，没有核对
对应工具输出，把退出码 101 误判成了成功；第四次修正检测器后确认二次沙箱仍在命令执行前
失败。第五次才是当前完成门的有效证据。新增回归测试分别固定“退出码 101 必须失败”和
“退出码 0 才可通过”，删除了以子会话完成事件替代原生工具成功的捷径。这些证据仍不替代
独立审查。新复审已独立重放运行证据并通过，R3-B 现已恢复。

## 7. R3-B 实现结果

- 新增唯一 `general_science` 插件入口，一次登记并编译六类科学角色的 15 个行为合同：通用证据
  提取及独立审计、定量图证据提取/审计、假设提出/批判、实验设计、完整对象审查、结果诊断、
  曲线误差诊断和三类有界修订。Root、TaskService、UI 和 scheduler 没有增加 operation id
  allowlist 或领域路由表。
- `roles/evidence_extractor.md`、`ideator.md`、`critic.md`、`evidence_auditor.md`、
  `experiment_designer.md` 和 `diagnostician.md` 已退化为纯 prompt 正文。旧 Task 路径暂由
  `platforms/roles.py` 的显式过渡元数据继续服务；Operation 编译不读取该映射，R3-D 在旧消费者
  清除后删除它。
- 普通文本、JSON、表格、PDF 和图像统一由 `science.evidence.extract.v1` 消费，不按媒体复制
  Operation。Codex 原生文件能力负责普通读取；定量曲线数字化才保留独立变体。自建
  `worker_view_image`、MCP 图像传输类型和 TaskService 图像读取分支已删除，通用证据 Operation
  也不再注册 `worker_read_input`。
- `worker_extract_pdf_text` 只保留“冻结精确页段及来源父链”的证据职责，返回不可变本地路径，
  不再把自己当 PDF 阅读器。普通 PDF 阅读使用原生 shell 的 `pdftotext`；普通图像检查使用
  Codex 原生 `view_image`。
- 当前 Codex 0.150.1 在本环境给独立进程再套 `read-only` 或 `workspace-write` 二次 bubblewrap
  时，会在创建 `/tmp/codex-bwrap-synthetic-mount-targets-1000/lock` 前失败。R3-B 首版因此把
  通用科学 Agent 的原生策略明确标为 `inherited_prototype`，由外层已存在的沙箱承载。编译提示
  如实说明工具可能可见，并分别列出允许与禁止行为；禁止原生写入、Root MCP、网络、委派、
  skill、app 和插件。该提示是可审计行为约束，不是生产级安全隔离，不能用于真实 TCAD、凭据、
  外部副作用或不可逆动作。精确 Worker 加固代码继续保留为下一版本边界。
- 通用科学 Operation Agent 的原生策略已经从残留的 `sandboxed` 统一改为
  `inherited_prototype`，不再让 R3-B 静默覆盖 R2/R3-A 已冻结的快速原型决策。编译生成的子
  Agent Worker MCP 使用与 Operation 摘要一一对应的独立命名空间，不再与父会话 Root MCP 的
  `scidiscovery` 名称冲突。编译提示同时明确：当前身份是被派发的 Operation Worker，项目中的
  scheduler 说明只约束父会话；子 Agent 必须直接从本 Operation 的 Worker 命名空间领取任务，
  禁止实例查询、任务调度和 Root 调用。
- Worker 仍只通过 `worker_file_*` 构造输出，并由 compiled validator/context validator、附件
  bundle validator、validate/finalize 和不可变 Artifact 父链决定能否成为科学结果。原生读取不
  取得 current、资格、审批或执行写权限。
- 修复两个迁移期通用缺口：collection bundle validator 现在一次接收主输出和完整附件集合；
  `worker_curve_analyze` 只按编译 capability 与输出集合准入，不再按 `diagnostician` 角色名特判。
- 首轮独立复审见 `reviews/R3_B_SPAWN_MEDIA_REVIEW.zh-CN.md`，结论为打回：图像 run2 在第一次
  校验失败后读取了任务外仓库源码，而旧 21 项检测器漏报；同时普通提取、图证据、修订和对象
  审查仍采用“完整旧角色 prompt + 末尾覆盖”，把互斥工作模式重新压给 Worker。
- 修复没有增加实体、状态机、注册表或 Operation：九类 Operation prompt 改为插件内独立窄
  resource，普通提取、图证据、修订和对象审查的编译正文分别为 2235、2030、1826、1769
  字符；普通提取不再包含参数、图证据或修订专用模式，对象审查不再先要求 `CriticReview`。
  输出和上下文 validator 通过既有 Worker 校验响应返回精确字段路径、原因码、期望合同与修复
  提示，Worker 无需读取实现源码反查规则。
- `operation_worker_server_name()` 从同一 CompiledOperation 与摘要确定性生成唯一允许的 Worker
  MCP 服务名；编译提示明确禁止探测其他继承可见的 Worker 服务。它由 profile、父继承配置和
  安装探测共同消费，不是第二注册表。资格检测从 `worker_materialize_assignment` 的事件结果
  取得精确任务根，逐个审计原生命令工作目录、绝对路径、框架导入和图像路径，并检查真实 spawn
  参数未继承父上下文；仓库源码越界、项目根工作目录和父提示继承均有合成负例。
- 二次复审 `reviews/R3_B_SPAWN_MEDIA_REREVIEW.zh-CN.md` 进一步发现：文本 run6 在命中正确
  服务前实际探测了 13 个其他 Operation Worker namespace，而 23 项检测只按 `worker_*` 工具名
  判断，仍把运行误报为通过。最终检测器现逐一配对子会话的 MCP function call namespace、
  call id 与 item-completed server/tool，只接受当前 compiled operation 的 exact server，且第一
  个 MCP 工具必须是该服务的 `worker_claim_task`；错误 namespace 即使调用失败也使资格报告
  失败。合成负例固定了这条边界，当时 ABI2 profile 的文本 run8 已通过新增该检查的 24 项门。

## 8. R3-B 真实运行与复审边界

| 检查 | 结果 |
| --- | --- |
| `.scidiscovery-state/r3-science-spawn-text-run8/qualification-report.json` | ABI2 历史真实 `spawn_agent` 文本链路，schema v4 的 24 项全通过；第一项 MCP 调用即 exact server 的 claim，零其他 Worker namespace，显式无父上下文且全部原生调用限定于物化任务根 |
| `.scidiscovery-state/r3-science-spawn-pdf-run5/qualification-report.json` | ABI2 历史真实 `spawn_agent` PDF 链路，原 23 项全通过且二次复审逐事件确认只用 exact server；原生 `pdftotext` 与注册 `worker_extract_pdf_text` 均成功 |
| `.scidiscovery-state/r3-science-spawn-image-run3/qualification-report.json` | ABI2 历史真实 `spawn_agent` 图像链路，原 23 项全通过且二次复审逐事件确认只用 exact server；同一调用号的 `view_image → ImageView` 配对成功，原始会话无任务外读取 |
| `pytest -q` | 132 项通过，40.80 秒 |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| `wc -l operations/spec.py operations/catalog.py operations/invoke.py` | 319 / 449 / 428；合计 1196 |

此前 R3-B 独立进程历史证据保存在 `deliverables/debug-evidence/`，不进入当前完成门。R3-A 的
`r3-spawn-agent-native-run3` 是原生退出码 101 被旧检测器误判的失败记录，
`r3-spawn-agent-native-run4` 是修正检测器后确认二次沙箱失败的记录，
`r3-spawn-agent-native-run5` 才是改用明确的 `inherited_prototype` 后真实成功的当前记录。
失败记录是选择显式原型继承权限的反证，不应删除或改写成成功记录。

R3-B 失败记录同样保留：文本 run2 暴露父 Root/子 Worker MCP 同名冲突；PDF run1 暴露父会话
误走实例绑定；图像 run1 暴露旧 `ImageView` 检测缺口。首轮复审进一步确认图像 run2 虽被旧
21 项报告为 pass，实际越出任务路径读取仓库源码，因此该报告降级为误判证据。修复过程中，
文本 run5 暴露终态后工作区清理导致检测器找不到路径的假阴性，PDF run3 未显式写出
`fork_turns="none"`，PDF run4 因先探测错误 Worker 服务而在物化前扫描项目根；三者均保留为
失败记录，没有通过放宽门槛改写。文本 run6 虽被 23 项报告为 pass，二次复审确认其探测 13 个
错误 Worker namespace，故同样降级为误判证据；文本 run7 使用当前 prompt 但早于 namespace
检测，不作为最终完成门。最终 24 项脚本要求父会话零 Root/Worker 调用、子会话零
Root/网络、唯一 exact Worker server、显式无父上下文、所有原生调用限定在物化任务根、真实媒体能力成功、严格科学
Schema、精确来源、受控 validate/finalize 和 Root `completed` 同时成立；不能以模型自述或子
会话结束代替任一项。

第三轮独立复审见 `reviews/R3_B_SPAWN_MEDIA_REREVIEW_ROUND2.zh-CN.md`，结论为通过、允许进入
R3-C。审查用当前检测器重放旧文本 run6 得到拒绝，并确认文本 run8、PDF run5、图像 run3
均只使用精确 Worker 服务；专项 35 项、全仓 132 项、编译检查与差异检查全部通过。复审同时
确认媒体入口合并、过渡删除点、Operation 集合和快速原型权限边界没有偏离最小架构目标。
`inherited_prototype` 仍不构成真实副作用所需的硬隔离。

## 9. R3-C 实现结果

- `general_science` 仍是唯一通用科研插件入口；同一个 `PluginDefinition` 在既有 15 个 Agent
  operation 之外登记 13 个有真实消费者的确定性 transform operation。没有为
  foundation 或完整 hypothesis portfolio 预造当前 Agent 不会产出的修订/收据变体。
- 迁入的行为覆盖 intake 拆分、目标投影、候选资格合取、实验计划物化、参数覆盖、两类知识
  更新、三类结构化修订应用和三类未变证据收据。新调用统一使用 `operation_invoke`；运行时不再
  自动安装 `ScientificStateTransformAdapter`。该 adapter 只作为固定端口背后的纯 callable
  复用，不再拥有 profile 选择权。
- 非资格输入、Worker payload 可见性、父链和输出语义名均由编译端口与 guard 投影。证据收据
  唯一允许的通配输入被严格限制为 `handoff_only + evidence_inventory + */*`，调用只登记来源
  而不读取大证据载荷。候选审查、科学实验意图、修订补丁、修订结果和差异均校验精确父链；
  工程实验意图走显式无科学父对象的独立形状。
- 原始目录共有 31 项：15 个通用 Agent、13 个通用 transform 和 3 个内置测试 operation。
  为避免把所有行为平铺给规划者，目录现在从同一编译结果确定性投影
  `public`、`support`、`internal`、`all` 四种查询范围：默认 `public` 只返回 15 个可选择的科研
  Agent 行为，`support` 返回 13 个确定性支撑行为，`internal` 仅返回架构自检行为。初版按
  executor kind 和保留命名空间推导的做法已撤销：规划可见性现由 `OperationSpec.catalog_scope`
  显式声明并进入摘要，编译器只接受三个冻结值。这样确定性行为也可以公开、Agent 行为也可以
  只作支撑或内部验证，而无需新增第二注册表；精确调用仍只有 `operation_invoke`。
- transform 不能简单降成普通内部函数：它们跨越 Artifact 注册、来源父链、幂等 fingerprint、
  provisional 传播和语义输出命名边界。只在目录中降低默认可见性，保留其 operation 生命周期，
  避免这些步骤重新变成 Root 或 scheduler 的硬编码后处理。
- 首轮独立审查发现：公开 `artifact_transform` 虽然默认未安装通用 adapter，但部署端显式注入
  `ScientificStateTransformAdapter` 后仍能按旧 profile 绕过 catalog，产物不含 operation 摘要。
  该结论已打回实现。修复在旧 adapter 选择边界对全部 8 个已迁移通用 profile 无条件拒绝；
  显式注入旧 adapter 也不能恢复旁路，尚未迁移的领域 adapter 仍可暂时使用旧入口。
- 调度合同现明确目录发现方式：默认查询 `public`；需要确定性拆分、投影、合取、物化、修订
  应用或收据时显式查询 `support` 并按端口与描述选择；`internal` 不得成为科研规划选择，`all`
  仅用于诊断。因此默认降噪不会把 support 变成只靠核心硬编码才能触达的隐藏行为。
- 新增真实目录驱动测试，覆盖 intake 多输出和幂等、候选/实验父链失败关闭、结构化修订与差异、
  未变证据收据不读取 payload、provisional/非资格传播、通配端口限制以及目录分层。旧
  `artifact_transform` 对已迁移通用 profile 的调用失败关闭；领域 transform 兼容入口留待 R4
  迁移后删除。

R3-C 独立审查见 `reviews/R3_C_GENERIC_TRANSFORMS_INDEPENDENT_REVIEW.zh-CN.md`，结论为通过并
允许进入 R3-D。审查首轮发现旧 `artifact_transform` 显式注入通用 adapter 后仍可绕过
catalog，修复后重新验证全部 8 个旧通用 profile 均无条件拒绝。审查同时确认 13 个 transform
均有当前消费者，目录分层只是同一 compiled catalog 的投影，R3-B Agent 摘要和默认
`spawn_agent` 派发没有变化。总代码净减重、领域 adapter 退出和静态 readiness 删除仍分别属于
R3-D/R4/R5，不能由本轮通过提前宣称完成。

## 10. R3-C 自动化证据

| 检查 | 结果 |
| --- | --- |
| `pytest -q tests/operations/test_operation_invoke_installed.py tests/operations/test_general_transform_operations.py` | 16 项通过 |
| `pytest -q` | 147 项通过，48.04 秒 |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| `wc -l operations/spec.py operations/catalog.py operations/invoke.py` | 332 / 449 / 410；合计 1191，不超过冻结的 1200 行总预算 |
| 目录视图 | `all=31`、`public=15`、`support=13`、`internal=3`；来源均为同一 compiled catalog |

自动化结果只证明合同和回归行为，不替代本阶段独立架构审查。

## 11. R3-D 实现结果

- 运行时不再为已迁移的 `ideator`、`critic`、`evidence_auditor`、
  `experiment_designer` 和 `diagnostician` 装配第二套 legacy role 合同或 Codex Agent 配置；它们
  只能通过编译目录中的 Operation Agent 创建。通用 legacy `task_schedule` 反例确认不会写入
  Task。
- 删除 `_role_primary_output_profiles` 以及 `RoleOutputContract.primary_profiles`。旧
  `structured-revision`、`legacy-experiment-portfolio`、`scientific-paper-evidence` 和
  `curve-error-analysis` profile 均已退出；修订、图证据和曲线诊断分别由已编译的窄 operation
  合同承担。
- Root 的 legacy `task_schedule` 不再接受 revision scope，也不再包含按角色选择修订 Schema 的
  表。通用 evidence extraction 经该入口明确拒绝；调用者必须使用 public operation。
- TaskService 删除旧图证据 manifest 重算、控制生成 validation report、handoff 特判和 scheduler
  signal 投影。相同机械约束由 `science.evidence.extract.figure.v1` 的 bundle validator 与显式
  validation-report collection 承担。删除了按 `experiment_designer` 角色名缩短首次 lease、要求
  首个 JSON checkpoint 和向 assignment 注入专属修复策略的分支；Operation 只使用冻结预算与
  通用 attempt/deadline 生命周期。
- 纯传输、精确派发、Broker 恢复和 handoff-only 访问测试改用尚存的 legacy bridge，而不是为
  测试恢复已退役的 `critic` 注册。默认 `task_prepare_dispatch → spawn_agent` 路径未修改。
  随后为目录降噪加入显式 `catalog_scope` 并提升 ABI3，15 个 Agent operation 摘要因此按合同
  正常变化；不能继续沿用 ABI2 的真实运行证据。
- 删除 `scheduler_topology._CAPABILITIES` 和固定阶段建议。`scientific_readiness` 现在只按当前
  Artifact Schema 库存从同一 compiled catalog 的 `public` 投影导出候选；精确身份、资格和审批
  仍由 `operation_preflight` 决定，不再由第二张角色能力表生成旧角色名。
- 运行时 scheduler prompt 和根目录实际安装的 `AGENTS.md` 受管区块均已刷新：通用创建只指向
  operation id；旧 figure、curve diagnosis、structured revision output/context profile 已退出。
  领域 transform 在 R4 前只保留一段显式标记的 TCAD-only `artifact_transform` 过渡清单，已迁移
  通用 profile 继续无条件拒绝。

### 11.1 唯一保留的迁移桥

设备参数提取仍使用 `evidence_extractor + device-parameter-evidence`；独立审查端使用严格专用的
`device_parameter_evidence_auditor`，Root 只允许其唯一设备参数 context 且不接受 output
profile。两个 prompt 均已删除普通 evidence、figure 和 revision 模式，专用审查角色也只装配
一项 context policy；提取角色同样只装配设备参数 intake context，旧 default、通用 revision 和
figure-revision context 在 TaskService 解析面也全部拒绝。TCAD author/reviewer 仍是 legacy 领域角色。运行态 role 列表因此从 8 个
降为 4 个；唯一 legacy collection profile 仍是 `device-parameter-evidence`。领域 role pack 若
尝试恢复已迁移通用角色名或覆盖过渡桥，启动即失败。以上均是 R4 的显式迁移输入，不是通用
控制面的一部分；R4 必须把参数合同、校验、工具和两个 TCAD 角色迁入领域插件再删除这些桥。

### 11.2 R3-D 自动化证据

| 检查 | 结果 |
| --- | --- |
| 退役 legacy Agent、角色发现、精确派发/恢复和 handoff 边界聚焦测试 | 通过 |
| `pytest -q` | 155 项通过，47.31 秒 |
| ABI3 文本真实子智能体 | `deliverables/debug-evidence/r3-science-agent-text-abi3-run1`：24 项全真，摘要 `10018a01acfe…` |
| ABI3 PDF 真实子智能体 | `deliverables/debug-evidence/r3-science-agent-pdf-abi3-run1`：24 项全真，原生 `pdftotext` 与注册 PDF 工具成功 |
| ABI3 图像真实子智能体 | `deliverables/debug-evidence/r3-science-agent-image-abi3-run1`：24 项全真，原生 `view_image` 成功 |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| 运行态 legacy role/profile | 4 个严格领域 role；1 个 `device-parameter-evidence` collection profile；各 1 个专用 parameter-extraction/parameter-audit context |
| 已删除符号搜索 | `_role_primary_output_profiles`、`primary_profiles`、三个通用 output profile、旧 figure validator/signal 和 experiment first-progress 特判均无生产命中 |
| 单一行动权威 | `scheduler_topology` 68 行且无静态 capability/阶段表；readiness 只返回 compiled public operation id |
| 实际提示安装 | 受支持生成器已刷新根 `AGENTS.md` managed block；旧 generic output/context profile 零命中 |

R3-D 独立审查见
`reviews/R3_D_LEGACY_SPECIAL_CASE_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md`，结论为通过、允许进入
R3 总审查准备。审查当时保留了一个非阻塞但必须在总审查前关闭的安装面缺口：三个
`builtin.test.*` internal operation 仍由核心默认 entry point 安装，并由 Codex 生成普通 Agent/MCP
配置。该缺口现已通过“零 operation 核心组件插件 + 显式架构测试插件”关闭，没有使用 Root 名称
黑名单或第二 scope 注册表；普通目录实测为 `public=15`、`support=13`、`internal=0`，测试安装才
出现三个 internal operation。R3 总审查还必须判断保留设备参数桥是否是最小且明确的领域迁移债务、已迁移
行为是否仍存在可写双入口，以及本阶段是否实际减轻而非转移控制层重量。

## 12. 三种目录视图接入状态与下一步

当前已完成：

- `catalog_scope` 是 `OperationSpec` 与 digest 的显式字段；当前 operation ABI 为 4；
- `operation_catalog` 默认只返回 public，并能显式查询 support/internal/all；
- `scientific_readiness` 只从 public 投影候选；
- scheduler prompt 只把 support 用于已选科学行动后的确定性物化。

本轮已完成：

- 默认 `builtin:CORE_PLUGIN` 缩为六个通用 Worker 文件生命周期组件且零 operation；
- `tests/fixtures/plugins/architecture_operation_plugin/` 通过同一 entry point 组显式安装
  `architecture_fixture:ARCHITECTURE_TEST_PLUGIN`，三项内部操作不再进入生产目录；
- 编译器拒绝 support Agent、Effect 和人工审批合同；support transform 可以声明其输出进入科学
  链前必须完成的独立 reviewer，但该关系只约束升格准入，不赋予 support 科学选择、审批或
  reviewer 结论；public transform 仍合法；
- core-only 安装固定为 public=15/support=13/internal=0/all=28，精确内部调用返回
  `operation_unknown`；显式测试安装才得到 internal=3；
- Codex 生成器没有 scope 黑名单：生产安装自然不生成内部 Agent/MCP，测试安装按同一目录生成；
- 加装测试插件没有改变任一 28 个生产 operation 摘要。

普通 UI 尚未消费目录视图，领域审批仍待 R4-D 迁入 compiled review/projector 合同。下一步只做
独立 R3 总审查第二轮复审，不新增 R3-E 状态、权限模型、scope 注册表或 Root 黑名单；未通过
必须返工，通过后才进入 R4。

## 13. R3 总审查返工与第二轮证据

总审查的打回项已按最小闭包修复：

- `ReviewSpec` 的 reviewer operation、输入端口和可接受结论已冻结到任务输出合同；下游消费时
  必须同时绑定精确被审对象与精确 reviewer 输出，`revise` 等未接受结论不能放行；
- 每个输出端口声明 `allowed_input_usages`，`explore`/`internal` 生产物不能声明
  `claim_evidence`；通用插件不再使用七种用途全开的默认值，收据、修订差异、审查/审计、
  候选准入、物化与覆盖报告均按实际消费者显式窄化；
- 同一生产者用途与精确复审门同时覆盖 `operation_invoke` 和暂留的 legacy `task_schedule`；
  TCAD 上下文只增加可选、`handoff_only` 的 `experiment_review` 见证，是否必需仍由精确生产者
  合同决定，未审计划被拒绝，精确 `pass` 复审与计划共同绑定时可调度 TCAD author；
- 修订目标不再由核心五项 `Literal` 或 schema 名推断，补丁与目标编解码器均由 operation 合同
  冻结，通用范围校验只解释标准化路径；
- `evidence_paths`、集合限制、用途、后果与复审合同均冻结进任务输出快照；集合输出不得声明
  证据路径，未知来源类型直接拒绝，网页与本地证据按精确绑定校验；
- 核心复杂度门保持 `spec.py=320`、`catalog.py=450`、`invoke.py=430`，未新增授权表、运行状态
  或领域分支。

当前可复核证据：`tests/operations` 134 项、全仓 167 项通过；真实 Codex 验收目录
`deliverables/debug-evidence/r3-science-agent-text-abi4-run3/` 的 24 项全部为真，对应 operation
摘要为 `68dfbae6a8e4ec07448b168a635892eae3f4a7d29cf8b6e41f017ceb2c3e3f0c`。独立报告
`reviews/R3_TOTAL_INDEPENDENT_REVIEW.zh-CN.md` 第二轮结论为“通过，允许进入 R4-A”；其中列出的
R4—R7 债务不回填 R3 状态，按后续阶段边界关闭。
