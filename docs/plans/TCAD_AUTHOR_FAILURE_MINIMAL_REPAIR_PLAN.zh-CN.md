# TCAD author 失败最小修复与重新验收计划

状态：**2026-09-08 独立计划复审及实现复审均 PASS；R0—R2 工程修复完成，92 项相关测试通过。R3 部署及新会话核验完成；R4 全新 author 已 completed，并取得同一项目的当前双证明，但封存交接为 blocked；R5 预检拒绝，未创建审查 Run。** 第 11—12 节记录崩溃后核验、临时证据丢失边界和本轮有界结果；尚未通过完整 author/独立审查验收。

后续实施入口：[校验纠错与跨轮续研最小实施计划](RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md)。它承接实验设计目标/反馈原提案及其独立审查意见，尚未实施；本文保留原修复和 R4/R5 事实，不因新计划而获得放行。

源码根：`123/scidiscovery-e5.2`；分支：`refactor/m7-pre-e5.2`；核查 HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。实施基线必须包含当时完整的工作树差异及未跟踪文件，不能只用该 HEAD 代表已部署代码。

## 1. 所有权、范围与已知状态

本文是本轮 author 失败修复及重新验收的唯一执行计划。[原 Skill/execution_context 计划](SKILL_VISIBILITY_COMPATIBILITY_AND_EXECUTION_CONTEXT_REPAIR_PLAN.zh-CN.md)保留原修复范围、S0—S5 实施记录、上游复用边界及 S6 科学资格要求；本文补充 S6 再次运行前的工程条件，局部取代原计划中 TCAD 相关文件“默认零改动”的范围限制。[端到端账本](R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md)只索引本轮子计划，历史 Figure 缺陷和审查结果不改写。

截至 2026-09-08 03:39 UTC 的会话受控记录：原修复已部署，四个过期旧 Run 已受控终结；S5 design 已 completed。S6 初次 author 与随后 recovery 均 failed，无 accepted project，未开始独立 deck review 或正式外部执行。该记录是过去时点的状态，部署和续跑前仍须重新查询。

首轮已知失败链是重复 `init` 建结构、修正后出现字段赋值语法错误、调试预留耗尽、最终初始化证明不合格、绝对截止时间到期。恢复还出现旧控制证明进入作者元数据的独立框架缺陷。此前使用 `resume_from` 偏离原计划；两次失败保留，不通过重写状态或继承旧证明修饰结果。

本轮只处理：恢复证明字段污染、最早错误诊断、已有预算的可见性，以及 author 执行要求与部署验收。保留当前 qualified preflight/initialization 门、Run 生命周期、独立 review 和 UI 执行审批。

明确不做：提高 360 秒调试预算或 1200 秒 Run 上限、改为实际耗时退款、新预算服务/数据库/状态机、新 public Operation、新 Agent 类型、放宽提交验证、迁移旧 draft、重做已审查科学上游、重写部署器。**完整恢复材料保存另列维护项，不作为本次全新 S6 Run 的前置条件。**

| 审查缺口 | 本文的修正位置 | 放行证据 |
| --- | --- | --- |
| 修复未经过部署和新 Worker 合同验证 | 第 5 节身份、第 7 节 R3—R4 | 安装文件/目录身份、实际提示和工具定义、精确新 preflight |
| 预算只覆盖正常返回，缓存/拒绝及首次调用前不可见 | 第 3 节、第 6 节 T3—T5 | 实际 Worker 返回覆盖 pending、完成、缓存、领域拒绝；首调用前可读规则 |
| 字段清理被误称为完整 recovery 修复 | 第 2 节、第 6 节 T1—T2 | 两种恢复入口可调试且不继承资格；诊断保存明确未解决 |
| 首次实现过晚、最小入口与生产逻辑覆盖关系不清 | 第 4 节、第 7 节 R4—R5 | 可见工具时间线、源码覆盖核对、同一最终项目双证明和独立 review |

## 2. 恢复修复只承诺解除证明污染

在 TCAD `operation_workspace.py` 的作者 materialization 中，统一处理 envelope 恢复及 raw deck 恢复；不能只把 `if revision` 改成包含 retry，因为 raw 分支已经写出 `project.json`，会跳过后续 `if not metadata_path.exists()`。

恢复为作者可继续编辑的项目时，由控制层剥离旧 `preflight_attestation`、`initialization_attestation`、派生 `materialization_report`，按本次精确输入重新建立控制元数据与文件权限。保留允许恢复的作者源码、声明及交接；当前 reports 不从历史包继承。两个入口均在候选 finalizer 前完成此处理。

finalizer 对作者填写非空证明的拒绝保持不变。即使源码恰好未变，新作者任务也必须重新取得本次证明。独立 reviewer 对 completed 项目的只读展开继续保留封存证明，不得被通用清理误删。旧恢复包不原地修改；operation/backend/input/次数准入不放宽，旧失败 Run 不因本次修复获得新的恢复资格。

本地 backend 目前只封存 canonical output，未保证保存最新未快照源码、失败 handoff 和诊断。字段污染修复的完成名称限定为“TCAD retry 证明污染修复”，不能写成“恢复功能完整”。本轮不修改 `service/runs.py`、`service/local_workspace.py` 或 snapshot 协议来建设完整恢复。

后续若要使用携带最新失败材料的 recovery，应另行确定有界文件集合、诊断脱敏/长度限制、失败和超时的封存时点及真实恢复入口测试。届时仍将材料标为非科学证据，不继承资格。本次 Fig.4 继续使用全新 Run，**不绑定 `resume_from`，不向新作者转交失败子 Agent 的聊天、旧工作区或草稿。**

## 3. 预算是现有事实的完整公开投影

### 3.1 单一计数来源与首调用前可见规则

继续以领域工具现有 `context.state` 为预算和名称计数来源，以 `context.remaining_seconds` 为该次调用的 Run 剩余时间快照。不新增持久计数器，不改计费、租约或重试策略。

在实际 `DEBUG_TOOL.description` 中明确总预留上限 360 秒、最多 6 个已创建名称、模式上限 preflight 60 秒 / initialization 120 秒 / smoke 180 秒、按提交上限预留且不按实际耗时退款。同名同模式调用只轮询/取既有结果；源码修正后用新名称，名称变化不重置预算。工具描述从既有领域常量/小型 helper 生成，不建立第二份可漂移配置。author 提示要求在第一次调试前读取这些规则。

模式上限不等于实际扣款。每个成功提交的调试作业按 `prepared.wall_time_seconds` 扣除一次；该值已被项目资源上限、模式上限、剩余调试预留和 Run 剩余时间压缩。候选校验、prepare 或明确发生在提交前的拒绝不扣款；已成功提交但 solver 失败仍保留预留；轮询和收集不重复扣款。保持现有异常与终结语义，不能为返回余额而吞掉 terminal checker 错误。

### 3.2 每次响应中的预算信息

在已有领域工具响应增加一个有界 `budget` 对象，不新增科学 Schema、Artifact 或 MCP 工具。字段语义固定如下，均为本次调用快照：

| 字段 | 唯一含义 |
| --- | --- |
| `total_wall_seconds` | 当前调试总预留上限 360 |
| `reserved_wall_seconds` | 已成功提交作业累计预留，不是 solver 实际运行时长 |
| `remaining_wall_seconds` | `max(0, total_wall_seconds - reserved_wall_seconds)` |
| `max_runs` / `created_runs` / `remaining_runs` | 名称上限、现有已创建记录数和剩余额度；失败的候选请求不占新名称 |
| `run_remaining_seconds` | 当前调用上下文给出的绝对 Run 剩余时间，不因 heartbeat 延长绝对截止时间 |
| `effective_wall_seconds` | `max(0, min(remaining_wall_seconds, run_remaining_seconds))`，后续提交仍受项目和模式上限约束 |

有已创建作业时另返回该作业实际 `reserved_wall_seconds_for_run`，供核对单次预留；该值随作业固定，不随轮询变化。静态模式上限在工具描述中可见，不在多个地方重新手写。

预算投影覆盖 TCAD 领域 handler 正常返回的 pending、完成、solver 失败、缓存、领域拒绝及可修复候选验证拒绝。缓存只保存作业诊断；每次返回时从当前上下文重新附加预算，不能缓存余额。可修复的 `RunOutputError`/`WorkspaceError` 保留原 `diagnostics` 路径、类型和内容，不能变成笼统 budget 错误。余额或名称耗尽的拒绝要说明耗尽维度且不得追加作业。

`RunCheckerError` 必须原样抛给通用 Worker router，由其继续以既有 CAS 终结并返回 `failed/diagnostics=[]`；该框架终结返回不承诺预算，不能在领域层捕获为可重试返回。未通过鉴权、未打开 assignment 或无法建立有效上下文的外围拒绝也不编造预算。领域返回加入预算后仍受既有 32 KiB 限制，不能只检查加入字段前的诊断。实现保持在 TCAD 工具边界，不为该投影扩展通用 Worker router。

## 4. 诊断与 author 执行要求

### 4.1 先定位实际错误

`debug_adapter.py` 按实际失败行及邻近上下文分类，排除 `Syntax check complete` 等成功标记。用本次两种日志固定回归：结构创建后 `No regions specified !` 分类为 initialization；`space required after '='` 分类为 parser，并在日志具备依据时定位初始化入口第 12 行。正常日志中的 syntax/contact/newton 等词不能单独压过实际错误。

source locator 的文件、行号、命令必须来自同一错误上下文，不能拼接不同栈帧；只暴露安全相对路径及有界片段。没有依据时保留既有 runtime 分类、空 locator 或 `log_only` 定位，不猜文件/行号，不新增诊断层枚举。保留真正 parser、numerical、resource_limit 和 output_contract 错误的既有含义。

### 4.2 以可见轨迹验证执行节奏

落实现有 author 角色“materialization 后 120 秒内形成首个完整候选或完成一次有依据的局部修正”的要求；手册查询继续遵守既有 Skill 的首写前最多一次针对性查询。工具可见时间线记录任务打开/物化、首次源码写入、首次候选可调试、首轮调试、最后一次源码/入口/声明修改、最终两项诊断和提交，不新增生产追踪协议。先验证最小源码，不为广泛手册阅读或元数据文字推迟第一轮调试。

首次写入和完整候选分别记录，不能用占位文件满足 120 秒目标。若无法做到，记录实际耗时和具体输入/实现缺口，不能把该项写成通过；该指标是本次工程验收要求，不新增 Run 状态或自动终结计时器。

author 根据实际预留和 Run 剩余时间安排一次有依据的修正，并为最终预检、初始化、收集及提交留出余量。以默认上限保守规划时，最后一组检查最多需要 180 秒预留和 2 个新名称；调试余额充足也不保证绝对截止时间充足。每次修正后重新评估；不得通过撤回已知正确修正来迎合旧证明，也不得在预算耗尽后循环换名或重复失败提交。余量不足时明确停止本轮调试，由 Root 按既有状态及 CAS 记录失败；不把 blocked handoff 当成可绕过双证明门的成功 author 产出。

### 4.3 最小入口覆盖生产关键逻辑

新作者由精确已审查输入重新实现源码，科学参数、方程选择和 case 范围仍由 Worker 与独立 review 负责。Root 不直接修科学 deck，不把失败 Run 草稿塞进新 assignment。

初始化入口须覆盖生产入口中与本次风险相关的字段定义、结构初始化、方程/回调注册、边界和首次 solve；存在多 case reset 时还须说明最小诊断实际覆盖了哪些重置路径。它可以省去长时间演化和完整网格遍历，不得改成省略关键状态/物理的替代模型来取得 qualified。

作者给出有界入口/过程对应说明，独立 reviewer 阅读封存源码核对覆盖关系与未覆盖边界，不新增字段或控制面推理器。同一项目 hash 只证明字节绑定，不能代替上述语义核对。已知字段赋值语法修正只说明下一步可验证方向，不预定它足以使所有方程和 solve 成功。

最终顺序保持：完成所有 source/invocation/declarations 修改 → 当前 qualified preflight → 同一未改变项目的 qualified initialization → 受控提交 completed。其间任何相关修改都要求重新取得两项当前证明。

## 5. 实施文件与合同身份

| 文件（相对源码根） | 本轮允许的最小改动 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` | 两条作者恢复入口清理控制证明/派生元数据；保留只读 reviewer 证明和 finalizer 严格门 |
| `plugins/tcad_artifact/tcad_artifact/local_debug_service.py` | 已有计数的预算快照、实际单作业预留、缓存返回刷新、完整响应边界；不改计费政策 |
| `plugins/tcad_artifact/tcad_artifact/debug_adapter.py` | 实际错误分类与同一上下文定位；复用已有模式上限向工具描述提供规则 |
| `plugins/tcad_artifact/tcad_artifact/plugin.py` | 工具描述、领域拒绝原诊断与预算组合；更新真正变化组件的 configuration_identity |
| `plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md` | 明确首调试前预算阅读、最终验证余量、停止条件和最小入口覆盖；引用既有 Skill，避免重复整份配方 |
| `tests/operations/test_l4_local_tcad.py` | 真实 local Worker 的两分支恢复、预算全返回路径、日志负控及现有证明门回归；小型日志样本可就地保存并标明来源 |
| `tests/operations/test_catalog_installed_entrypoint.py` | 打包安装后实际 TCAD 工具定义和行为、受影响组件摘要及上游 admission |
| `tests/artifact_agent/test_platform_configuration.py` | 生成 author 的提示/工具权限与安装目录一致；reviewer 仍无 debug |
| `tests/operations/test_tcad_knowledge_closure.py` | 只扩展受角色资源变化影响的必要断言；不把安装 Skill 内容嵌入科学 prompt |

修改按行叠加在既有 dirty tree 上，不重置其他人的 Figure/Curve、Skill 或部署改动。现有 `test_l2_run_invariants.py`、`test_skill_policy_producer_compatibility.py`、部署事务测试默认只运行相关既有回归，不为本轮扩展 core、Skill、部署脚本或发布构建器。

组件实现源码和 worker tool 描述并非都自动进入 `resource_digest`；不能假定只修改 Python 即获得新 operation identity。实施时在现有 ComponentSpec 更新受影响的 workspace materializer、debug tool 等配置身份，角色资源通过现有字节摘要变化。共享 materializer 对 reviewer 及其他可达消费者的真实传播如实记录，不能为缩小传播遗漏身份更新。

生成逐 Operation 的修复前/后摘要及可达变化原因，证明无关科学 producer 保持稳定。保持 plugin version、operation_id、框架 ABI 和 digest 算法；不新增旧摘要白名单。恢复负控使用本次新合同创建的失败测试 Run，不尝试跨合同恢复现场旧 Run。任何意外退役上游的变化均在部署前定位，不能靠重跑科学链掩盖。

## 6. 必须先复现、修后通过的测试矩阵

| 编号 | 真实入口与场景 | 成功判据 |
| --- | --- | --- |
| T1 | 临时 instance 中通过 Root/Local Worker 生成带控制证明的 TCAD 候选，受控失败，使用同一候选合同创建 retry，进入 debug | 不修改恢复后的只读元数据，debug 能到 adapter；新报告缺失时提交仍拒绝，重新双诊断后才可完成 |
| T2 | raw deck materialization 分支及 revision/reviewer 回归；作者故意填写证明 | raw 分支也清理污染、权限正确；作者伪造仍拒绝；reviewer 展开仍保留封存证明。raw 测试不宣称 local backend 已会保存该目录 |
| T3 | Worker 调用 60/120/60/120 四个作业；夹入同名轮询、完成缓存、solver 失败和候选拒绝 | 实际预留累计符合规则；轮询不扣、候选拒绝不扣、solver 失败不退款；第五个新请求因余额拒绝，adapter.submit 次数不增加 |
| T4 | 项目上限或 Run 余量较小；六个小额度作业耗尽名称；完成早期作业后又消费预算，再查询其缓存 | 预留按 clamp 后实际值，余额/名称/绝对时间分别准确；缓存预算反映当前调用，诊断仍属于原作业；新增预算后完整返回不超过 32 KiB |
| T5 | 首次调用前的实际工具描述；pending、领域拒绝及候选 checker 路径 | 规则在首调用前可见；领域返回及可修复候选拒绝含准确预算、原 diagnostics 保留；terminal `RunCheckerError` 仍由 router CAS 终结，精确返回 `failed/diagnostics=[]`，不要求预算 |
| T6 | 本次实际日志的有界脱敏 fixture；补充真正 parser、numerical、resource_limit、output_contract 样本 | 成功标记不误分类；两种已知错误定位正确；文件/行号属于同一上下文，不暴露绝对工作区路径 |
| T7 | 已有 current-qualified 提交门和独立 review 纵向测试 | 缺失/失败/过期证明、改 source/入口/声明仍拒绝；两项当前证明成功才能提交；reviewer 无 debug 权限 |
| T8 | 构建 wheel、隔离安装，通过实际 loader/local Worker 入口检验 T1/T5 核心场景，并比较 catalog | 不从源码根偷导入；安装提示、工具描述、配置身份匹配；精确合法上游可 admission，旧不兼容项目仍拒绝 |

测试逐文件、逐进程串行，沿用原计划的禁用自动 pytest 插件、cache、多线程数值库和 8 GiB 进程树上限；不与 wheel 构建或真实 Agent/solver 并发。先运行 owning test 的失败复现和修后验证，再运行涉及 TCAD 工具/Workspace、catalog、平台与兼容性的相关文件及 `git diff --check`；不得只补镜像实现的断言。

T1—T8 的领域作业可使用受控测试 adapter，目的是证明机械合同、真实 facade 和部署入口。它们不证明 Sentaurus 初始化或物理实现已正确；真实 solver 和新 Agent 的证据只由 R4—R5 提供。相关路径的 skip、不正确拒绝位置或安装态导入回源码都不算通过。

## 7. 执行顺序与每阶段出口

| 阶段 | 工作与出口 | 当前状态 |
| --- | --- | --- |
| R0 固定基线 | 保存本次 diff/未跟踪文件、源与安装身份、可复现日志样本和失败断言；重新查询运行/执行状态。分开记录已有环境失败和本轮缺陷 | 已完成，见第 9 节 |
| R1 最小实现 | 按第 5 节修改；通过 T1—T7；保持双证明和科学/控制所有权 | 已完成，5 个生产文件净增 76 行 |
| R2 安装包与工程复审 | 完成 T8、摘要传播矩阵、相关回归及独立工程审查，四项计划缺口均有对应证据，无未解决阻断 | PASS，92 项测试通过，独立复审无未解决阻断 |
| R3 事务部署 | 执行下述安装、健康及新会话检查；旧部署成功不代表本轮已安装 | 安装、健康、profile 与新会话绑定已核验；seal 归档证据及读取限制见第 11 节 |
| R4 全新 author 验收 | 当前精确 preflight/invoke、无父历史派发；第 4 节节奏/覆盖可核验；同一最终项目双证明后 completed | `fig4_r4_tcad_author_1` 已 completed、当前双证明 qualified；交接 blocked，覆盖未独立审查，120 秒候选目标未独立核验，验收未闭合 |
| R5 独立 deck review | 从当前 catalog 的 review_edge 选操作，绑定新封存项目和精确上下文；completed sealed review 通过后才允许进入后续执行准备 | 精确预检拒绝 `input_scientific_claim_forbidden`（project）；未 invoke，见第 12 节 |

### R3：修改必须交付到实际 Worker

复用[原计划 S4 的事务安装和回滚规则](SKILL_VISIBILITY_COMPATIBILITY_AND_EXECUTION_CONTEXT_REPAIR_PLAN.zh-CN.md#s4事务安装服务重启与新会话加载)，不新增安装流程。部署前通过控制接口确认没有受影响的 queued/running Run 或活动外部 execution；不热换正在工作的编译 Worker。沿用已核实的部署参数和维护入口，完成 dry-run、事务安装、服务重启、健康检查、installed profile 和 seal。

逐项核验：安装文件与本轮审查候选一致；runtime identity、control/UI/MCP 健康；安装 catalog/组件摘要与预期矩阵一致；生成 author 提示、实际 `worker_tcad_debug_run` 工具描述和权限属于同一代；完整已安装 Skill 仍可按原只读规则访问。失败按既有事务规则处理，不能把旧成功安装作为这一步的证据。

关闭旧会话并新建会话加载编译定义。回退代码必须是保留当前科学数据库的新安装事务；不得恢复旧数据库快照抹掉 S5/S6 对象。R3 完成后仍须 R4 的真实新 preflight，不能沿用旧会话或修复前的 preflight 成功结果。

### R4—R5：只重新验证 author 及其独立审查

新会话先 `instance_current`，按用户明确继续的实例工作；未绑定时只给管理 UI 链接。读取当前 catalog 和 immutable inventory，按[原计划第 6.3 节](SKILL_VISIBILITY_COMPATIBILITY_AND_EXECUTION_CONTEXT_REPAIR_PLAN.zh-CN.md#63-复用边界)重新解析精确已审查输入，保存本次完整请求。可选参数输入组依当前声明全有或全无，不制造缺失资料。

所选 public author 的 preflight 通过后，以同一不可变请求 invoke，使用返回的 agent_type、`fork_turns="none"` 派发，消息只要求完成已排队 assignment。使用新语义名，不使用 `resume_from`；不把失败聊天、日志或草稿转给新科学 Worker，不以本轮工程报告代替其绑定科学输入。S5 的新 design intent 不替换既定 reviewed plan；无关来源、证据、假设、计划和 contract 不重跑。

实际 author 轨迹验证第 4 节，并由 Root 在 completed 后读取 `run_status.sealed_output` 与 `scheduler_signal`，确认当前双证明存在。超时、预算不足、源码错误或未提交成功均明确保留为失败；按现有受控生命周期和最新 CAS 前提处理，不自动再次恢复或重复新建 Run 直到碰巧成功。若发现新的科学前提缺口，由当前 contradiction 与 catalog 决定后续行动，本文不指定替代科研操作。

独立 reviewer 只读新封存项目、证明和精确上下文，核对最小初始化与生产入口的关键逻辑对应，保留未覆盖的边界；不能运行 debug 或用文字补造证明。R5 通过只说明可以继续准备受控执行，不等于 Fig.4 结果成立。正式执行仍须当前 catalog 的精确请求和 loopback UI sealed decision。

## 8. 停止条件与完成口径

出现任一情况即停止相应阶段：修复必须放宽双证明/身份门；需要修改生产数据库或作者只读控制元数据；首次调用前规则仍不可见或缓存/拒绝余额错误；源码和安装定义不同代；上游 admission 意外退役；相关真实入口负控失败；author 无法取得当前双证明或独立 review 不通过。

工程代码修复完成仅可在 R2 通过后声明；本次修复已部署仅可在 R3 通过后声明；author 阻断已解除须 R4 真实 completed；继续受控执行准备须 R5 通过。完整 recovery 材料保存始终是本轮未覆盖项。阶段结果附精确候选、测试/安装证据及受控状态，不以历史通过数量或旧 solver 日志替代本次验收。

## 9. 2026-09-08 实施与独立复审记录

证据可用性更新：本节及第 10 节的 `/tmp` 路径是崩溃前的历史证据位置，系统重启后临时文件已丢失。历史测试/审查结果保留为当时记录，不伪造补回日志；当前重新核验的安装证据保存在仓库第 11 节链接中。

### 精确对象与范围

用户要求追加独立审查，通过后按最小改动计划执行。本次 GPT-6 独立审查先指出 terminal checker 预算承诺矛盾；只修订第 3 节两段及 T5 的终结例外后，[计划复审 PASS](/tmp/scid-author-plan-independent-review-20260908/report-rereview.zh-CN.md)。接受计划 SHA256 为 `beb83ceb4b59f7e4071198a94ca2bcdc198084b04056da2066f25bfbe10079a8`；[接受版本副本](/tmp/scid-author-repair-baseline-h1e53nkm/accepted-plan.zh-CN.md)保留原样。之后本文仅更新阶段状态和证据记录，未放宽设计要求。

R0 保存目录为 `/tmp/scid-author-repair-baseline-h1e53nkm`，包含原 dirty tree、687 个源文件摘要、相关文件副本及安装态比较。相对该基线，本轮仅修改第 5 节允许的 5 个生产文件、3 个测试文件，以及本文和 README 状态索引；其他既有修改未变。生产文件净增 76 行，未修改 core、数据库、预算上限、Skill 或部署器。[本轮补丁](/tmp/scid-author-repair-baseline-h1e53nkm/implementation.patch) SHA256：`a43fce0648f479526d0dff0443a2d448a7aa19f014f36caabd83519300c6c73a`；[逐文件摘要](/tmp/scid-author-repair-baseline-h1e53nkm/implementation-files.json)绑定最终 8 个生产/测试文件。

R1 实现两条作者恢复入口的旧证明清理、完整且逐调用刷新的预算响应、实际错误分类与同一片段定位，以及 author 的预算/生产入口覆盖要求。T1 在真实同合同 retry 后只补全允许编辑的 case anchor，未改只读元数据；完整失败材料恢复仍未承诺。现有 Hardened 拒绝码断言在原包/原测试中同样失败，已保存基线证据，本轮仅对齐实际拒绝码，未修改生产准入。

### 测试、身份与 R2 判定

先保存恢复污染、首次调用描述缺失及两种现场日志诊断的失败复现，再修复并串行验证。独立实现审查另发现两个真实日志省略标记仍会造成跨片段误定位；探针和失败测试确认后，仅扩展既有上下文边界，并在本地及隔离安装路径补回归。最终[独立实现审查 PASS](/tmp/scid-author-plan-independent-review-20260908/implementation-review.zh-CN.md)，无未解决阻断。

| 检查 | 通过数 |
| --- | ---: |
| Local TCAD，含恢复、预算、诊断和双证明门 | 35 |
| wheel 隔离安装与实际 loader/Local Worker | 8 |
| 平台配置和角色权限 | 14 |
| 上游 producer 兼容 | 5 |
| Run 不变量 | 21 |
| TCAD Skill/打包闭合 | 3 |
| 相关既有部署事务回归 | 6 |

合计 **92 passed**，选定路径无 skip，进程树峰值最大 187.2 MiB，`git diff --check` 通过。每组命令、耗时、资源及日志索引见[检查记录](/tmp/scid-author-repair-baseline-h1e53nkm/passing-checks.json)；末次诊断修正后已重跑受影响的 Local TCAD 和安装组。没有以全套测试或真实 solver 运行替代本轮有界工程验证。

[目录摘要比较](/tmp/scid-author-repair-baseline-h1e53nkm/catalog-comparison.json)包含完整前后 49 项：三个 author 与共享 materializer 的 reviewer 共 4 项变化，其余 45 项不变，无增删。workspace materializer/debug tool 的配置身份更新至 v4，保持既有插件版本、ABI 和 Operation ID；合法上游 admission 与旧不兼容项目拒绝均有验证。

### R3—R5 交接

[部署维护交接](/tmp/scid-author-repair-baseline-h1e53nkm/r3-deployment-handoff.zh-CN.md)已按第 10 节用户追加要求更新：当前 command 模式无需设置 `TCAD_STATE_ROOT`，真实 dry-run 已通过，正式安装仍未执行。当前会话只能写仓库和 `/tmp` 且不能提权；系统部署需有权限的维护终端，随后必须关闭旧会话并加载新会话。

[交接时受控状态](/tmp/scid-author-repair-baseline-h1e53nkm/control-status-before-handoff.json)记录 M7-test0 无 queued/running Run、execution 或 pending approval；真正部署前仍须再查。当前未创建新的科学 author/reviewer，未改写旧失败对象。R4—R5 继续严格按第 7 节，以全新 Run 和新封存结果验收；本轮尚不能声称 author 阻断已解除。

## 10. 用户追加：简化 TCAD 部署状态目录

2026-09-08 用户明确要求统一状态目录、避免扩大复杂度，追加授权修改 `deploy/install.sh` 和 `deploy/reinstall.sh`。本增量独立于第 9 节已审查的 author 实现：仅将本地 TCAD 默认目录改为 `${SCID_STATE_ROOT}/tcad`，并把目录校验、权限处理、数据库事务备份与目录创建限定到已有 `TCAD_LOCAL_SERVICE` 条件。外部 command 模式忽略该参数，保留旧本地数据；本地模式支持显式旧路径，不自动迁移。不改执行服务、运行协议、Operation 合同或科研流程。

两个生产脚本合计净增 2 行。原部署测试增加默认/显式路径及外部模式负控；先在原实现复现 5 项失败，再验证整个 `tests/artifact_agent/test_deploy_scripts.py`：**63 passed**，10.14 秒，进程树峰值 111.0 MiB。检查了真实安装分支生成的服务路径、目录操作和事务目标，特权操作由测试记录器代替；原目录中的哨兵文件保持原样。Bash 语法检查和 `git diff --check` 通过。双语安装说明及部署交接同步更新，原独立审查报告与 author 候选文件保留原样。

按现有实际部署参数、未设置 `TCAD_STATE_ROOT` 的 `deploy/reinstall.sh --dry-run` 返回 0、`deployment preview: pass`，只渲染 control/UI 服务；没有安装包、状态或服务写入。系统 unit 检查的已有提示保存在原日志中。增量、文件摘要、红绿测试及预览日志见 `/tmp/scid-tcad-state-simplify-n8t3wwib/`。正式事务安装、安装后核验和新会话仍属 R3 待办。

## 11. 安装完成及崩溃后继续

用户报告安装完成后系统重启。重新只读核验：control/UI 服务 active，审批页 HTTP 200，Python runtime identity 通过；5 个已安装 TCAD 文件与会话保存的独立审查摘要及当前源码均一致。已安装 catalog 共 49 项，与运行服务目录摘要一致，4 个受影响 TCAD Operation 摘要符合预期。复用安装器的校验入口验证 framework/外部 workspace 的 profile，以及 launch root 的 dry-run 无差异；25 个 MCP、24 个 Agent、完整 author 提示和预算工具描述匹配。已安装 Skill 的 17 个文件与源码一致。

本次事务归档目录 `/var/backups/scidiscovery/transactions/20260908T062017Z-70115` 存在。其 manifest 受权限限制未直接读取；按现有 `seal_transaction` 先写 `state=complete`、再原子移动至归档目的地的顺序，归档存在作为 seal 完成的推断证据，不冒充已读取 manifest。原科学数据库未由 Root 回滚或改写。

新会话初始为 unbound，用户在实例管理 UI 选择已有 M7-test0 后，`instance_current` 确认 active。启动前受控查询无 queued/running Run、external execution 或 pending approval。重新从当前 public catalog 选择 author，核对精确既有计划/审查/曲线合同/能力，参数批准输入组因全部缺席而整体省略；新请求 preflight admissible 后以同一请求 invoke，按返回编译角色无父历史派发。

`fig4_r4_tcad_author_1` 于 2026-09-08 06:33:03 UTC 创建、06:33:33 UTC 进入 running，绝对截止时间为 06:53:03 UTC。Root 只读取受控状态，completed 前不读取或转交草稿和科学内容。当前接口不暴露精确首次源码写入时间；不能仅用 started/activity 时间宣称 120 秒候选节奏已独立验证。随后完成情况及 R5 预检结果见第 12 节。

精确请求、摘要、重新核验结果及上述限制保存于[仓库内部署记录](evidence/TCAD_AUTHOR_DEPLOYMENT_2026-09-08.json)。

## 12. R4 封存结果与 R5 准入阻断

受控 `run_status` 显示 `fig4_r4_tcad_author_1` 于 2026-09-08 06:49:55 UTC completed，candidate accepted，输出为 `fig4_r4_tcad_author_1.output`。其 preflight 和 initialization 均 qualified、succeeded、exit code 0，并绑定同一项目、源码树及声明摘要。本次证明覆盖了新项目的有界开发检查；不能由此认定完整研究已实现、正式生产求解已执行或物理结论成立。

完成后读取的封存 `scheduler_signal.verdict` 为 `blocked`。作者报告已实现两个 3×3 stage-A 主族筛选，对应 36 个材料求解；依赖前序筛选/细化结果的 tail、消融、背景敏感性和收敛阶段，仍缺精确选定参数及其传入后续直接求解入口的机制。这是作者的有界陈述，尚未接受独立科学审查；36 个求解指实现范围，不是已完成的正式运行数。最小初始化与生产逻辑的对应也尚未完成独立核对。

从当前编译 review_edge 选择独立审查，绑定上述新项目及原五项精确上游，预检请求名为 `fig4_r5_tcad_deck_review_1`。返回 `admissible=false`、`port=project`、`reason_code=input_scientific_claim_forbidden`，因此未 invoke、未派发 reviewer，也未开始正式 execution。

源码与安装态一致：TCAD reviewer 的 `project` 输入沿用 `_input` 的默认 `usage=claim_evidence`，其 consequence 为 scientific。通用准入对这种输入同时检查标签和生产者交接，`blocked`/`revise` 均不合格。本次 inventory 的 `claim_admissible=true` 只反映标签检查，另列 `producer_handoff=blocked`；该字段不是本次完整准入判定，不能用它覆盖预检拒绝。参见 `plugin.py` 的 `REVIEW_INPUTS`、`mcp_root_shared.claim_admissible`、`mcp_root_operation_routes._validate_operation_input_admission` 及 `mcp_root_instance_routes.scientific_inventory`。

本轮停在该精确拒绝，保留有界未决结果。没有重写作者交接、放宽门禁、复制项目绕过准入或自动重试。待审对象能否以非证据用途进入独立审查，以及后续阶段参数如何按已审查计划交接，是两个仍需分别核查的缺口；本节不预先批准修改合同或重新设计实验。精确封存摘要、交接与 R5 请求/拒绝保存在[本轮结果记录](evidence/TCAD_AUTHOR_R4_R5_2026-09-08.json)。
