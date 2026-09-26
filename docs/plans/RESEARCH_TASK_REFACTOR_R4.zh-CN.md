# R4：按完整研究任务重构

## 1. 当前状态

2026-09-26 更新。本文是 R4 唯一主计划；本节及第 4.1 节为当前状态和修复顺序，第 6 节保留当时的实施与验证事实，不作为当前完成声明。已通过的 R3 工程验收不等于本轮通过。

当前进度：完整任务、原生内部助手、插件运行时 API 与 Root 接口收敛已实现。`3a4cc12` 临时安装版本已在当前 Codex 会话完成图像证据作者与独立审查，但转换交付因同名不同对象被误合并而失败，审查默认响应也暴露 schema 投影失配。本轮修复冻结引用、具体调用输出族、当前/历史决策投影与 UI；独立审查发现的次级产物名称冲突也已关闭。源码按 131 文件串行验证，1453 项通过、70 项属于其他测试层；隔离 wheel 检查 1 项通过。随后已将 `4206621` 离线安装到原临时入口，保留旧环境和状态快照，真实完成图像作者 → 独立审查 → bundle → 后续分析；幂等重试及第二调用后的原件消费预检通过。分析任务实际派发了原生助手，但最终采用记录不充分。作者发生三轮 schema 补填，Root Token 收益仍未证明；这是图像证据子链通过，不是完整 F/TCAD/阶段 UI 验收完成。此前完整 installed/process 的证据仍属于其各自节点。
初轮 R4 基线为当时 e5.2 未提交工作树，其累计实现已保存为 Git 节点 `6c3d76e`。本次插件边界与 Root 接口实现以该节点为基线。保留他人改动、其他 worktree 和原验收证据。按用户要求破坏式替换被淘汰的旧入口，但有效能力必须先有等价去向。

当前执行范围：按已有授权串行修复与测试，默认使用配置化 2GB 进程地址空间限制以及进程树 RSS、系统内存、脏页采样止损；不声称 cgroup 聚合硬隔离或绝不 OOM。修复阶段仅短暂启动临时服务供审查会话使用，测试前及复核后均关闭；随后按用户继续测试授权，启动了三项当前科学 Worker 与一个原生助手。仅替换临时安装入口，旧环境和科学证据保留；原常驻服务与个人配置未更改，真实 TCAD 未执行。同 UID 隔离问题 SEC-002 仍未关闭。
## 2. 已确认的设计原则

- Root 面向证据、假设、实验、分析四类完整任务；不固定流水线、常驻 Agent 数或 Run 数。
- 一个负责人连续完成一件任务。上下文压力优先通过按需读取、checkpoint 和有界工具结果处理；必要时内部使用 Agent as a tool，不为每个子环节固定创建作者任务。
- 实验主体是通用实验 Agent，连续负责科学设计、实现、局部调试、发起执行、收集和完整交付。TCAD 插件提供领域 Skill、类型、工具和适配器，不再独立公开一整套实验调度入口。
- 实验各子环节明确提交结论和产物，UI 自动读取。阶段交付、进度展示、独立审查和人工审批分别定义。
- 子环节提交后正常继续，不强制独立审查、人工审批或 Root 确认。必要的大节点关口须明确对象、触发条件和关口类型；其余是否审查由 Agent 根据需要决定。
- 正式独立审查必须核验与作者的独立性；内部助手意见不能直接成为通过凭据。修订是新对象，不继承旧审查。
- Root 正常路径不读取操作指南 MD；调用合同、默认决策响应和常见错误必须自包含。Root 做科学选择，控制层处理确定性绑定和工程推进。
- 端口与 gate 必须实质收减：身份、版本、来源链、审查见证、预算归属、执行能力等机械字段由控制层解析和冻结，不能让 Agent 反复填表。重复检查、固定阶段关卡、字段复述、无实际消费者的强制输入，以及代码代替科学判断的充分性 gate，随旧路径删除；不能仅换名或搬到服务器继续保留。
- 内部机械端口和绑定禁止对科学 Agent 可见：从 catalog、invoke 合同、assignment、工具响应和错误等所有出口移除；不能仅标为 optional、handoff_only 或“无需填写”。Agent 只接触科学意图、必要材料/语义引用和真正选择项。控制层内部仍保留精确身份、绑定和审计，公开/内部合同由同一权威声明投影，不建立第二真相表。
- 查询只读。执行由明确命令和执行服务推进，不能藏在 `run_status` 或 UI 读取中。
- 2GB 存储（2,000,000,000 字节）、3600 秒以内的有效 TCAD 请求继续按配置策略授权，不因处于“大节点”而重新要求人工执行审批。配置与实际资源保护不得硬编码成另一套不可调阈值。

## 3. 保留、改造与退出

| 分类 | 范围 |
| --- | --- |
| 保留 | Run/Artifact 不可变身份与来源；OperationSpec 与唯一编译目录；统一 MCP；workspace/tool evidence/checkpoint；预算、授权、执行恢复；CAS/流式传输；求解器、提取、评分和解析算法 |
| 改造 | 通用科研任务合同；领域能力向任务的受控组合；阶段交付和 UI 投影；Root 决策/绑定接口；Worker 内部 Agent 工具；按需审查和大节点关口 |
| 替代后删除 | 科学骨架与 deck 作者强制交接；重复初始/修订/失败作者入口；Root 机械投影/打包/执行推动；仅服务旧流程的字段、提示、Schema 和测试 |

每个现有 gate 逐项列出：保护的具体约束、真实调用方、是否重复、保留/合并/删除决定。只有权限/预算、不可变身份与真实来源、适用的正式审查独立性、执行幂等与真实终态等承重检查保留在控制层；一般科学不足由 Agent 说明局限、请求帮助或改变方案，不能仅因没有按固定模板凑齐字段就阻断任务。结构校验只检查真实消费必需的数据，不制造无消费者必填项。

SDevice 详细计划、有效数据类型及来源校验先确认消费者和等价能力，不按名称含旧词就删除。普通审批政策不因清理而静默改变。

## 4. 实施批次

各批串行实施，实施者结束后再独立审查；批次涉及的跨文件合同必须闭合，不能留下生产注册引用已删除入口。

### A. 通用实验任务贯通（第一优先级）

- 以通用科研插件的实验 Operation 承接研究问题、精确证据/假设锚点、约束和可选的原实验/反馈；领域能力通过现有插件/组件注册组合，不增加第二注册表或核心按 TCAD 名称分支。
- 一个作者工作区内完成设计、实现和调试。执行通过受控工具及现有授权/执行服务，普通失败返回同一负责人。不能把旧的多作者 Run 流程包进一个外层入口冒充合并。
- 初次、修订和失败恢复共享任务入口但保留准确模式约束；恢复、重试和子任务共享原预算，未知提交先查原执行，取消覆盖后代。
- 冻结本轮能力、工具、权限和必要科学约束，作者可以提出实质变更并说明理由；需要改变研究方向时才返回 Root。
- 主要落点：通用实验声明、Operation 编译/工具上下文、TCAD 声明与 workspace、执行服务与适配器。先记录实际消费者，再同批迁移和退出旧入口。
- 完成条件：Root 不再分别派发骨架、deck 作者、调试和正常执行；SProcess/SDevice 能力有明确等价路径。

### B. 阶段交付与 UI

- 设计、实现、调试、执行各自提交结论、对应版本、依据/产物与剩余问题。Agent 提交科学解释，执行器提供退出码/资源/文件等事实。
- 复用现有不可变产物和 checkpoint；不为每阶段造一个审批对象或新的任务生命周期。
- 显式增加“运行中读取已封存阶段产物”的合同；未提交草稿不当作结果，阶段完成不等于整个任务完成/获得资格。最终交付明确选择采用的阶段版本。
- UI 只读这些交付，展示进展、阻碍、依据和版本历史。Root 默认只收取必要决策事项与最终交付，不自动接收全部中间日志。

### C. Root 合同与按需关口

- 默认状态响应给完成结论、局限、剩余矛盾及有界候选；详情按需读取，不手填 JSON Pointer。
- 从精确锚点沿声明父链解析确定性绑定并冻结；歧义/缺失报错。科学选择给候选，不能按类型或“最新”暗中决定。
- 对每个公开端口记录来源：科学选择、控制层派生或实际不需要。派生端口退出 Agent 手填合同，无消费者端口删除；校验器、UI、提示和测试同步，不以一个巨型 JSON 参数藏回全部旧字段。
- 行动合同和错误自包含；共享默认值由代码合并。压缩主提示，操作指南只保留维护/复杂诊断用途，不先删文档造成隐藏规则。
- 仅按明确政策保留大节点关口，其余按需请求独立审查。审查输入映射、独立性、重复通知/重启幂等由控制层保证。
- 有界限制、分页和遗漏标记覆盖工具目录、父链和日志。平台全工具注册表若不受框架控制，明确该边界，不承诺框架能硬拦截任意原生工具输出。

### D. 内部 Agent 工具

- 修改当前 Worker 全面禁止 delegation 的生成合同，提供受控的内部委派，而非直接放开控制接口或执行凭据。
- 子任务得到目标、相关材料和任务范围，能按需读取文件、使用适用 Skill、分析/修改代码并进行父任务已获准的局部验证。继承父任务已有能力，在实际任务范围内收窄；不能默认关闭 shell、文件访问、Skill 和全部领域工具而退化为纯文本调用。网络和外部执行沿用原任务权限及领域执行政策，不因委派新增授权。
- 不继承完整 Root 历史；返回有界结论、依据/产物及限制。负责人承担采用、验证、整合和最终交付责任，不把每个助手子步骤重新交给 Root。
- 优先复用实际平台委派与现有 Worker 工具/生命周期；先核实安装平台能否承载所需能力，不假定原生接口可用，也不另外搭建一套完整 Agent 调度框架。现有 CLI 推理封装若无独立消费者，随替代删除；单轮文本推理不能作为本项完成证明。
- 层数、活动数、预算和权限可配置；当前部署/验收保持串行，父任务等待期间的线程占用必须按真实平台规则计算。
- 正式独立审查与内部助手区分；保存工具调用证据，取消、超时和清理覆盖子任务。总 token 未必减少，不预设收益。

### E. 其他科研任务收敛与旧路径清理

- 证据内部使用提取/参数工具；假设统一提出与修订；分析内部连续计算、绘图和相关诊断，保留已有 checkpoint 复用。
- 不为整齐的 Operation 数强造巨型 Schema，也不将所有上游正文打包注入 Worker。
- 对每个淘汰入口完成生产者、消费者、注册、UI、角色与测试迁移；保留真正有用的内部类型和工具。只删除本次替代产生的无用路径，不重新开展无关大扫除。

### F. 真实运行与上下文验收

- 先做与精确改动相关的最小验证，不恢复全套/重复安装业务矩阵，不重跑无关512MB/2GB大文件测试。
- 实际模型运行前以不调用模型的最小检查验证 CLI、shell、工具宿主及会话生命周期，防止再次花模型 token 诊断基础设施。
- 独立 Codex/安装/TCAD 需在用户恢复相应执行范围后开展。保持会话与绑定真实，不伪造用户实例选择，不把 Codex resume 当作框架代理身份继续。
- 串行、2GB 内存预算、提前止损与超时；虚拟地址预留与物理内存分别记录，无 cgroup 聚合硬隔离时不声称绝对不会 OOM。临时安装及凭据结束后删除。

## 4.1 当前剩余项与修复顺序

1. **收敛作者的实际交付负担。** `4206621` 的安装后图像链已通过，但作者首次草稿约 7.5KB/117 个标量值，连续三次被 Intake 的条件字段校验拒绝。figure 的专用语义合同只说明图像来源绑定，没有包含其复用的通用 Intake 参数/单位/推断理由规则；应统一声明与校验的来源，并检查重复的目标、摘要和证据描述，避免只往提示词追加长说明。科学判断仍由作者负责，不让控制层伪造依据。
2. **完成 F 剩余效果与上下文观察。** 当前原生助手已真实 prepare、启动、使用 shell、完成并 release，负责人最终封存分析；但最终分析没有显式说明助手结论的采用/拒绝，不能将 release 等同采用证明。Root 长维护会话累计输入不是干净基线，尚未证明 Token 收益；通用实验阶段、真实 TCAD 和浏览器端阶段展示仍未覆盖。
3. **处理明确的未关闭边界。** SEC-002 需要可信启动器与 OS/沙箱边界，不能用同 UID token 代替隔离。旧 figure 历史 UI 仍按 fingerprint 聚族，两个历史调用可能歧义；该问题不影响本次当前公开 bundle 路径。UI 原件读取上限仍为 4MiB，超过上限明确不可用，不扩大为已支持全部 7MiB 合法参数包。跨库崩溃原子性及更广泛基础设施改造另需具体证据。

下面保留最初修复计划的依据和交付范围，反映记录时状态；这些实现已完成，最新验证和剩余项以上文及文末记录为准。

### 原修复计划的问题范围与依据

| 状态 | 问题 | 影响与边界 |
| --- | --- | --- |
| 已确认设计缺口 | 内部助手仅对所供材料推理，正常调查和执行能力被禁用 | 不满足内部 Agent 完成子任务的目标；一次真实文本调用不能证明任务委派成立 |
| 已确认实现残留 | `OperationSpec.agent_context` 保留 `legacy/scientific`，默认 legacy；assignment/schema 分支使用不同投影 | 统一模型可见规则；不是两套 Operation 注册表，也不能把确定性 transform 数量等同于受影响 Worker 数量 |
| 强删除候选，需完整可达性确认 | TCAD `operation_workspace.py`、`worker.py`、`curve_operations.py` 与 core `audit.py` 共 2055 行，本次搜索未发现生产引用 | 检查插件字符串注册、入口脚本、安装资源和有效测试消费者后删除；不按文件名或行数盲删。另一个建议中截断的文件名和“12 个收集错误”尚未复核 |
| 已确认结构问题 | ExperimentExecution/内部助手访问 RunService 私有成员；服务层反向导入 MCP；构造器反向挂接 | 数据与生命周期所有权不清，扩大后续修改影响范围 |
| 已确认配置缺口 | 实验输出导出硬编码 2e9 字节，导出/收集硬编码 120 秒，读取分页硬编码 16KiB | 前两项形成配置之外的限制；120 秒不是 solver 运行上限。分页复用统一响应预算，不为每个常数新增配置 |
| 已确认语义漂移 | `ReviewedDeckPackage.review` 已可为空；AGENTS/架构/TCAD README 仍含旧流程 | 类型与默认说明误导维护者/Agent；源模板、生成物和当前文档须一致 |
| 已确认实现方式，影响待量化 | 执行状态遍历实例 execution 绑定，助手事件按 JSON scope 过滤重建 | 优先利用现有 task/scope 键限定查询；不在没有证据时另造状态库或性能框架 |
| 未闭合的运行问题 | 最近认证 401、验收 harness 失败却显示 awaiting_user、中断后残留不明 | 认证根因未证实；先核实改动是否在中断前落地，不能声称当前认证有效或清理完成 |
| 未完成验收 | 完整模型链、负责人真正使用助手、阶段 UI、正常 Root 上下文与基线 Token 对照 | 不用源码测试、独立 transport 或 solver 探针代替真实研究闭环 |

量化比较另行保留边界：其他 Agent 提供的 HEAD 5871a64 与当前工作树统计，本轮未重新编译复核；它不是 R4 开始时的未提交工作树基线。Operation/端口缩减可反映合同收敛，总代码行数不能单独证明重构完成度。首次失败 Root 只有一份新生成 scheduler；旧 AGENTS 与本地诊断命令之间没有已证实因果关系。

### 修复顺序与交付

所有实施项串行；下面保留当时的修复范围和交付标准。当时测试暂停，随后用户已恢复受限测试授权，实际结果见文末。正式独立审查在相关实现基本完成后进行，不对每个内部步骤设置审查/审批 gate。

1. **冻结范围，确定内部 Agent 合同。**
   - 记录当前候选与前序修改边界，保留他人改动；不强行拆分交叠的历史提交，也不提交临时凭据/运行日志。
   - 明确助手承担有意义的子任务，拥有父任务已获准的相关工具与工作区能力，负责人保留整合责任。平台委派的可用路径通过已有源码/配置核实，不通过反复启动模型探索。
   - 交付：本计划中的能力、权限、责任和生命周期边界；不增加第二份助手流程文档。

2. **统一合同并真正退出旧路径。**
   - 清点淘汰 Operation 对应的实现、插件组件、资源、角色、UI、安装入口和测试消费者；删除确认不可达的旧模块与测试，保留仍服务完整任务的算法。
   - 检查 TCAD compare/review-validation/realization/control-equivalence 等 support 的实际消费者；无消费者则退出注册和实现，有消费者则保留所需能力，不能凭静态导入缺失直接判死。
   - 统一 agent-visible 投影并移除 `agent_context` 模式开关。科学意图和必要材料保留，机械端口、身份和绑定在所有模型可见出口隐藏。
   - 对 gate 按真实消费者复核，删除旧工作流/重复表达约束；保留来源、权限、预算、终态和适用的独立性检查。不给 Agent 增加补表负担。
   - 交付：每项删除有去向或无消费者依据；生产注册不残留旧引用；不通过恢复旧 API 维持过时测试。

3. **完成有工具的内部 Agent，并收敛所需服务接口。**
   - 复用平台/Worker 能力，让助手能完成局部调查、代码修改或获准验证；负责人等待并整合，不让 Root 搬运中间过程。简单算术使用确定性工具，不为演示而强制委派。
   - 原任务的预算、超时、取消与未决副作用贯穿助手；恢复不刷新额度，助手不能获得 Root 控制权或变成正式审查通过凭据。默认串行，不把无限递归/并行当成本轮目标。
   - 从实际调用点提取少量 RunService 公开能力，例如任务谱系、冻结合同、活动记录和受控原件读取；在统一装配入口注入。移除服务对接口层的反向导入和构造器反向注册，不机械包装每个私有方法，不整体重写 RunService。
   - 用现有任务/scope 索引限制执行和助手查询；只有实际查询需要时才增加索引，不建立并行事实账本。
   - 交付：助手的工具能力、输入/输出、实际权限及父子生命周期一致；删除被替代的重复 launcher/状态和无消费者推理专用路径。

4. **归一配置与执行包语义。**
   - 自主执行限额继续从已有策略读取；输出导出限额明确采用哪个配置，导出/收集超时不得超过剩余任务预算。复用统一分页预算；配置名、单位、默认值和实际生效点一致。
   - 将 `ReviewedDeckPackage` 收敛成实际的执行包概念，同步消费者、schema/错误/说明；审查记录是按需关联的独立事实，不由类型名暗示已通过。允许按既定破坏式更新原则删除无用旧兼容分支，不改写封存历史或继承旧资格。
   - 交付：改变配置不会被另一处硬编码悄悄截断，包结构不误表达审查状态。

5. **同步默认入口，压缩文档与验收维护成本。**
   - 更新 scheduler 源模板、仓库对应生成 AGENTS、架构与受影响插件说明；普通 Root 无需读 guides，复杂维护指南保留按需入口。外层安装实例/个人配置单独标记，不因修改源码静默覆盖。
   - 只维护本 R4 主计划；历史证据不改写。仓库保留必要结论、方法、版本/hash 与可定位清单，原始运行日志放在可找回的独立归档，不能只留失去原件的 hash。
   - 合并重复验收脚本，保留必需的资源保护、串行约束和状态记录。修正失败/等待/中断的显示与退出语义；认证失效不自动循环重试，残留进程按真实身份确认。
   - 交付：默认安装和当前文档表达同一套规则；没有新的平行计划栈和额外必经 gate。

6. **实现完成后再恢复最小验证与真实对照。**
   - 当前不执行；待用户恢复后先做与上述改动相关的最小串行验证，再跑一条完整研究任务。正常子环节不交回 Root，阶段结论可由 UI 读取；选择确有价值的助手子任务，检验负责人采用结果。
   - 分别记录 Root/负责人/助手每次请求的 input、cached、output、输入峰值、工具响应原始字节及模型可见字节，并记录失败/重试、交接与是否重复读取。累计 input 不当作新增，字节不冒充 Token。
   - 对照使用相同任务、模型、输入、成功标准和可比权限。若使用 HEAD 5871a64，只称其为该提交对照；没有可重建的 R4 开始状态就不宣称 R4 单独收益。先报告成功与绝对成本，再判断 Token 收益。
   - 不重复无关大文件、安装业务全矩阵或长期 TCAD 测试。没有完整模型链的证据，整体计划保持未完成。

### 本轮静态实施记录

- 第 2/3 批已退出旧合同模式与无消费者路径，并将内部助手迁到原生委派；相关权限/生命周期实现待统一独立审查，不能把源码落地当作实际助手收益证明。
- 第 4 批将当前 TCAD 包统一为 `ExecutionPackage` / `tcad.execution-package.v2`。历史归档只保留旧 schema 的来源遍历识别，不保留旧运行别名或改写原件。`execution_io` 五项配置进入 Run 快照；实例显式覆盖（包括等于包默认的值）与公共设置合并，恢复不刷新。helpers 同样修正实例覆盖。模型 normalized_request 继续冻结模型偏好，控制资源配置在创建 Run 时冻结且不新增 Agent 表单。
- 第 5 批同步 scheduler 源、e5.2 AGENTS、架构/TCAD README 双语；外层 AGENTS、个人和运行实例配置不改。正常 Root 不读指南；平台编译器、ABI/摘要、配置身份、三级可见性和版本化 Schema 保留。
- 临时验收 harness 只修源码：失败/中断不再显示 awaiting_user，不自动重试；未启动或清理任何进程，认证和残留状态仍未确认。没有归档或删改历史原始证据，也没有新建平行计划。
- 本批证据为源码前后哈希、精确 diff 与 AST/引用静态结果；没有执行 pytest、collect、业务 import、catalog 编译、生成器、构建安装、模型或 TCAD。整体 F 验收仍未完成。插件平台的新评审在本轮实现后另行只读核对，不预先承诺删除规模或新增一层空 API 包装。

独立静态审查修复：A1 在同一数据库写事务内互斥活动助手与负责人准入；释放后允许复用，历史参与作者记录保留。A2 执行包载荷版本改为领域 capability 必填声明，并进入编译身份；TCAD 显式为 2，不从 Schema 名推断。A3 架构双语同步 run_status 默认 decision、显式完整输出及禁止 values 根指针。针对断言已补写但未执行；待同一审查者复核。

### 插件运行时边界实施（基线 `6c3d76e`）

用户已批准串行实施，仍不运行测试。顺序：公共窄 API 与 figure 首个消费者 → curve → TCAD → 收敛真实重复模式 → Root 工具/读取面 → 统一独立审查后提交。平台编译器、ABI/摘要、组件配置身份、三级可见性及版本化 Schema 保留，不设置删行目标。

首批已实现：纯展示构造函数从 UI 迁入 `plugin_runtime.presentation`，UI 保留发现、来源验证和总预算；`plugin_runtime.evidence` 只返回稳定证据记录字段，完整 attempt/recovery 模型留在核心 schema，来源认证/登记仍控制侧拥有。figure 不再导入 service/approval_ui，也不再调用 curve 私有声明构造器；共有 transform 声明/输入函数归 `operations.transforms`，领域算法不变。公共边界参考见 [PLUGIN_RUNTIME_API.md](../PLUGIN_RUNTIME_API.md)，其余 workspace/计算/collection/诊断能力先明确所有权，待实际消费者逐项落地，不预造空 SDK。

第二批 curve 已落地：任务工作区文件能力迁为实际公共实现；算法返回科学 `CalculationResult`，真实工具 context 完成计算/登记与 checkpoint 来源身份推导，验证 context 返回已核验的计算值，插件不构造私有 receipt/attempt。原生分析 launcher 的安装/日志归一供核心和插件共用，Run 权限和生命周期仍归控制；curve 已退出 service/interfaces/approval_ui 导入。TCAD 仅同步共用评分返回类型和组件身份，全量迁移留下一批。

第三批 TCAD 已落地：复用计算登记/已核验结果/工作区/展示能力；collection 的预算、流式有界进程及诊断纯值、机械结果填充、通用 MCP/Unix transport 迁为核心与插件共用实现。执行 socket 配置和 CLI 保留，Root/Worker 业务 router、权限/注册、执行 supervisor 与诊断存储未迁公共。三个生产插件和公共 runtime 对 service/interfaces/approval_ui 的直接及字符串依赖归零；保留领域 SSH/solver/数值逻辑。证据记录视图排除私有 calculation/checkpoint proof，历史 source_ports 由核心配对事实提供。下一步收敛 Root 工具与响应面，然后统一独立审查。

本批只做 AST、导入图和差异检查；模型、安装、编译、测试与 TCAD 均未恢复。旧 raw evidence 不纳入本轮提交，完整科研闭环与 Token 收益仍待验收。

## 5. 验收指标

| 方面 | 可观察的完成条件 |
| --- | --- |
| 任务颗粒度 | 一个实验负责人完成设计至结果交付；正常局部修复不反复交回 Root |
| 阶段可见性 | 实际完成的阶段有不可变结论，UI 可读，返工有版本；读 UI 无副作用 |
| Root 负担 | 正常路径不读操作指南，不手工搬机械依赖；每次介入有科学决策理由 |
| 内部 Agent | 按需使用相关工具完成有意义的子任务，负责人采用/否定并整合；既非强制阶段也非仅一次文本推理，权限和预算不超出父任务 |
| 审查/授权 | 子环节无强制关口；大节点政策明确；独立性、版本绑定和配置内自主执行仍成立 |
| 执行可靠性 | 失败/超限如实终止；未知提交不重复执行；恢复/子任务不刷新预算 |
| 上下文 | Root/Worker 分别记录每轮及累计 input、cached、output、输入峰值和工具返回量；标明截断/遗漏和原始响应与模型可见内容差异 |

累计 input 包含重复上下文，不能当新增内容；字节不能冒充精确 token。对照收益必须同任务、同模型和同成功标准，否则只报告绝对值。重点回归此前发现的重复 scheduler 指令与宽泛工具枚举注入，不能用验收专用提示掩盖默认行为。

## 6. 实施记录

- 2026-09-25：用户要求开始，建立本轮唯一计划；先串行核对 A 的生产消费者与最小实现路径。用户随后允许受限定向源码验证；独立 Codex、安装构建和真实 TCAD 继续停止。原 R3 证据保留。
- 用户进一步明确：合理删除各类 gate，低价值校验必须退出；大量机械 port 交给控制层自动填充，禁止再次让 Agent 大量填表。该要求作为各批合同与代码审查的硬约束。
- 用户进一步要求：不该展示的端口、绑定等内部信息禁止对 Agent 可见，需覆盖全部模型可见出口，不能以自动填充代替隔离。
- 用户进一步要求：Operation 声明、提交校验和正式审查范围一致；删除无用审查与 gate，只保留有实际消费者的关键结构、来源、权限、预算与适用独立性检查，不以角色提示新增隐藏通过条件。
- A 实施中（未验收）：新增通用实验声明、同 Run 阶段工具、执行控制服务及 TCAD 能力贡献；唯一编译器选定单一领域提供者并冻结其工具和资源。已解除执行包强制通过审查及旧 workspace 强制 preflight/initialization 提交条件。首次定向目录编译通过；仍须完成旧入口消费者迁移、执行结果来源闭合与定向负例，不代表生产链路完成。
- 正式独立审查的前置：Operation 已基本修订完成，声明、输入输出、校验、科学 Agent 合同与必要生产消费者基本闭合，并完成作者最小自检。阶段交付与作者自检均不代替独立审查；不在半成品期间发起正式 review。

### 2026-09-25：A 源码候选达到可审状态（candidate_ready，尚未独立审查/部署验收）

- 通用公开入口为 `science.experiment.v1`；TCAD 通过现有 PluginDefinition/components/catalog 贡献实现与诊断工具，单一编译配置选定能力并冻结，歧义拒绝。不增加 TCAD 专属公开实验入口。通用 Run 封存设计/实现/执行/有效性科学材料；只要求最终 completed 采用真实实现、对应 collected 执行及引用该执行的有效性判断，设计/debug 无固定模板门槛。
- 已注销旧公开设计/skeleton/revise/materialize、TCAD author.initial/revise/runtime-failure 与公开 `tcad.study.execute`；旧 TCAD reviewer 迁入可选的 `science.object.review.v1` 科学审查。已实质删除旧 author 机械输入表、旧 skeleton/作者版本 gate、强制通过 review 的 packaging 分支和无消费者注册；workspace 不再强制 preflight/initialization 报告。仍有历史消费者的 schema 与实用结构规则保留。
- 科学输入只包括研究目标、必要科学材料、可选原实验及科学文件。执行能力、精确原始来源、来源 hash、批准和预算绑定均由控制维护。私有 tool evidence 快照留在控制数据库/CAS；assignment、工具索引、结果 schema、公开 catalog、invoke/status、工具结果和工程错误使用科学投影。控制 manifest 不作为可读取/导出的科学输出。
- `ExperimentExecution` 复用原 ExecutionService/Bridge/Collection：原预算所有者、策略重判、已准备提交查询、幂等启动与真实终态保持；gateway/standalone 共用服务绑定。取消涵盖任务及恢复祖先的正式执行和持久 debug 账，取消失败保留 recovery_pending，不清除 workspace。状态查询不产生新科学证据。
- SProcess/SDevice 使用同一实现工具；SDevice grid 通过 file_reference 精确绑定。文本原始输出可分段读，二进制输出可经受控流式 export 写入本 Run scratch 后作局部分析；原 CAS 文件与私有 manifest 不变。

保留关键约束的单一声明与执行点：

| 约束 | 声明 / 执行 |
| --- | --- |
| 科学结果结构、completed 所需证据关联 | `general_science_experiment_task.ExperimentReport` 与同文件 `experiment.sealed_material` / `validate_report`、`validate_completion`；控制服务只封存真实 collected 观察 |
| 最终交付无未结束副作用 | 同一 `experiment.sealed_material` / `ExperimentExecution.require_idle`，由 Run 最终提交调用 |
| 文件、solver 与科学 grid 的真实结构和来源 | `experiment_capability.Implementation`、既有 `DeckProjectDraft`/`ReviewedDeckPackage` / `prepare` 与原 Artifact 校验；不要求 review pass |
| 执行权限、政策和原科学预算 | 内部 effect 的既有 ApprovalContract + adapter 的管理员策略 / 原 `ExecutionBridge.start`、`ExecutionService` 授权及预算预留；本批不复制政策判定 |
| 可选正式审查独立性 | `science.object.review.v1.independent_review_ports` / `WorkerConnections.attach`；Run 打开要求已验证 attachment，standalone 不能绕过 |
| Agent 可见端口和控制材料隔离 | `agent_context`、`agent_visible` / catalog、assignment、科学 evidence 投影与状态投影；无控制派生实现的隐藏输入在编译时拒绝 |
| debug 恢复/取消不重置预算 | 原科学目标绑定与持久 debug 预约账 / `LocalTCADDebugService.experiment_activity`，取消保留原预约与已消费额度 |

最小定向验证（均为源码检查，无模型/安装/TCAD）：`/tmp/scid-r4-check-final/result.json`，配置 `/tmp/scid-r4-final-check.json`。

| 精确节点（test_r4_experiment_task.py） | 用时（秒） | 采样树 RSS 峰值（字节） | 结果 |
| --- | ---: | ---: | --- |
| test_complete_experiment_compiles_with_one_domain_provider | 1.540 | 101158912 | pass |
| test_completed_experiment_requires_linked_control_observations | 0.523 | 58703872 | pass |
| test_scientific_projection_preserves_private_control_snapshot | 0.526 | 58523648 | pass |
| test_real_worker_seals_and_executes_without_legacy_gates | 2.191 | 116379648 | pass |
| test_reviewer_and_scientific_surfaces_use_declared_contract | 2.407 | 117403648 | pass |
| test_debug_recovery_cancellation_preserves_original_budget | 0.737 | 67547136 | pass |

- 实际覆盖：Root invoke、Worker assignment、工具封存、真实 Run/CAS/执行数据库、政策授权/超限不提交、幂等、collected 原始输出、只读状态、SDevice 精确 grid、二进制导出、最终交付、独立 reviewer 拒绝同作者/未绑定入口、科学出口负例、gateway 路由缓存与 debug 取消/恢复账。执行 adapter 和采集内容为测试替身；没有真实求解器/模型调用。
- 每项通过既有受限 guard 串行运行：每进程 AS 2,000,000,000 字节、树 RSS 1,500,000,000 字节采样提前止损、每项 120 秒、数值线程 1；MemAvailable 至少 8 GiB、相对下降不超过 2 GB、Dirty 不超过 128 MiB。均正常退出，无超时/止损。不声称 cgroup 聚合硬隔离。
- 候选与 R3 既有修改区分依据：`/tmp/scid-r4-a-baseline.json` 为本批前原 hash；`/tmp/scid-r4-candidate-files.json` 为精确文件集合，`/tmp/scid-r4-candidate-manifest.json` 为候选 hash。既有未跟踪 guard 脚本不在原 hash 集合，单独标记，不能伪称有原始快照。
- 未覆盖/后批：真实 TCAD、真实 debug 运行、安装部署和模型交互未执行；完整运行中阶段 UI、其它科研 Operation 收敛、内部 Agent 委派仍属 B/E/D。历史 TCAD 分析入口保留其实际原始执行输入消费者；新实验的局部读数与有效性判断在同一 Run 完成。独立审查尚未进行，本记录仅说明源码候选与作者自检状态。

### 2026-09-25：A 独立审查六项修复候选（待复核）

- debug `collected` 纳入统一终态；receipt 恢复使用本 Run 封存 implementation/package/receipt 关联，不再读取旧 author finalizer。实际收集后重读、重建宿主读取、幂等取消和最终提交已覆盖，原预算账保留。
- 公共 Operation 构造器统一将 recovery manifest 标为控制输出；Root 科学 artifact 的 producer_inputs/parents/detail 与 run_list detail 使用科学投影，保留科学材料名称。任务内私有执行绑定不进入 execution_list/lifecycle_events，Root 执行入口亦拒绝直接访问，控制原件保留。
- 正式 reviewer 必须由可信 gateway caller 与 exact Run 的 attachment 一致绑定；standalone 不承载正式独立审查。科学实现和执行包共用 `ScientificDeckImplementation` 的字段/schema/必要文件语义规则，公开输入错误给出可修正的安全字段诊断，不新增科学 gate。
- 修复验证：`/tmp/scid-r4-review-fix-02/result.json` 的 5 个准确节点全通过；最后 Root 旁路修改只复跑受影响 reviewer/SDevice 节点，`/tmp/scid-r4-review-root-02/result.json` 通过。成功运行采样树 RSS 最高 118820864 字节，最长节点 2.711 秒；无超时或资源止损，沿用每进程 2 GB/120 秒/系统内存 guard。两个中间失败分别为缺失 ConfigDict 导入、execution_status 经 _binding 的旁路，均已定点修正后通过。
- 修复前 hash：`/tmp/scid-r4-review-fix-baseline.json`；修复候选精确文件及 hash：`/tmp/scid-r4-review-fixed-candidate-manifest.json`。未进行真实 TCAD/模型/部署测试，不扩大后批范围；记录为作者修复自检，尚未替代独立复核。

### 2026-09-25：A 独立复核完成

- 实施者封存修复候选并停止修改后，原独立审查者只读复核六项发现：debug 终态、封存回执恢复、控制 manifest 隐藏、Root 读取旁路、正式 reviewer 可信身份、prepare 声明与结构校验。六项均闭合，限定范围内未发现直接阻塞回归。
- 复核核对源码及既有定向验证记录，没有并行测试或新增执行。实际 debug 服务收集与恢复使用测试执行适配器；宿主重建验证不能代替完整跨 Run 恢复、真实 TCAD、模型及部署验收。
- A 源码实现、自检与本轮独立复核完成；后续按 B/C/D/E 推进，F 继续遵守当前未恢复的执行范围。

### 2026-09-25：B 阶段交付与 UI 源码候选（candidate_ready，待独立审查）

- 沿 A 同一 Run 的 tool evidence/CAS 封存增加单一只读 `stage_deliveries` 投影；设计、实现、调试、执行、有效性按实际已封存材料展示，不制造固定阶段流程或审批。`StageSubmission` 允许执行科学解释及可选 `remaining_question`；作者结论、科学产物和执行器事实分别标注，不由 adapter 代写科学结论。
- 重复提交相同材料保持幂等，修改材料保留新版本；版本取同类/同阶段封存顺序，最终采用仅来自 completed Run 的既有 `adopted_stages`。运行中明确标注尚无最终采用和未评估资格，草稿不进入读取。
- 复用 `run_status` 显式 `stage_offset`/`stage_limit` 与 `stage_reference`/`stage_text_offset`；默认短状态不读取科学 payload。UI 主视图、节点页与节点 API 自动读取同一投影，按名称导航到依据和科学材料。阶段默认 4 项、最多 8 项/约 32 KiB，原文每段最多 8192 字符；预览省略与续读位置可见。无新增公开工具、控制状态表或阶段审批对象。
- 控制身份、私有 manifest、预算归属与调试工作区路径不进入新增科学投影；当前实例/Run 所有权核验、浏览凭据及名称绑定继续有效。数据库/CAS 文件快照证明受测读路径无 mutation；未调用执行推进。实际浏览器交互与大负载未验收。
- 定向源码验证命令：`python scripts/run_r3_source_acceptance.py --config /tmp/scid-r4-b-final-check.json --execute --output /tmp/scid-r4-b-final-check`。每个准确节点独立进程串行运行；每进程 AS 2,000,000,000 B、采样树 RSS 1,500,000,000 B、120 秒、数值线程 1；MemAvailable 最低 8 GiB/下降不超 2 GB、Dirty 不超 128 MiB，均正常退出，无止损或超时。不是 cgroup 聚合硬隔离。

| 精确节点 | 秒 | 采样树 RSS 峰值/B | 结果 |
| --- | ---: | ---: | --- |
| `test_r4_stage_delivery.py::test_running_and_final_deliveries_share_readonly_scientific_projection` | 2.415 | 121778176 | pass |
| `test_r4_stage_delivery.py::test_large_material_pagination_and_instance_boundaries` | 2.115 | 118910976 | pass |
| `test_r4_experiment_task.py::test_complete_experiment_compiles_with_one_domain_provider` | 1.210 | 102162432 | pass |

- 覆盖真实 Run/CAS/执行数据库→Root/read_model/API 路由/HTML renderer、运行中读取、草稿不可见、重复版本/最终采用、原文续读、名称导航、实例隔离、浏览授权拒绝与读快照不变；执行 adapter 为测试替身，API/HTML 路由由测试直接调用。无真实 TCAD、模型、安装构建、浏览器或全套 pytest。第二项首次失败为测试夹具漏传 `approvals`/`executions` 构造参数，修正后通过。
- 本批基线 `/tmp/scid-r4-b-baseline/manifest.json` 记录原内容/hash及既有未跟踪标志；精确候选为 `/tmp/scid-r4-b-candidate-manifest.json`，批次差分为 `/tmp/scid-r4-b-candidate.diff`。引用的旧 A `/tmp/scid-r4-review-fix-02/result.json` 本轮不存在，未重读或重跑；采用已核对源码的同一 guard 新建本批证据。B 已停止修改，可交独立审查；C/D/E/F 未因此完成。

- B 独立审查未发现 P0/P1；唯一 P2 为 debug `missing_outputs` 未进入预览且未标省略。已修复为最多 8 项、每项 512 字符并在裁剪时标明续读，workbench 展示同一字段。准确负例 `test_r4_stage_delivery.py::test_initialization_missing_outputs_are_visible_or_explicitly_omitted` 经原 guard 单节点通过（2.816 秒，采样树 RSS 121266176 B，无超时/止损）；诊断执行事实为替身，注册 Worker 工具封存及 Root/UI 读取为真实服务路径。结果 `/tmp/scid-r4-b-review-fix-check/result.json`，修复前快照 `/tmp/scid-r4-b-review-fix-baseline/`，冻结清单 `/tmp/scid-r4-b-review-fixed-candidate-manifest.json`。作者修复自检完成并停止修改，待独立复核。

- B 修复候选冻结后，原独立审查者只读复核确认上述 P2 闭合，未运行额外检查；B 无剩余审查发现。阶段交付与 UI 源码批次完成，继续 C。

### 2026-09-25：C 通用机制与 Root 边界源码候选（candidate_ready，待独立审查）

本批范围为通用声明/编译/派生/Root 边界及共同 receipt 的科学与控制分离；全体系 Agent 不可见验收须待 E 的旧科研消费者迁移完成。无安装、部署、模型、真实 TCAD 或外层会话 AGENTS 修改。

| 事实分类 | 已落地链路 / 范围 |
| --- | --- |
| 科学输入 | 保留实例内材料名称、研究选择、可选材料和可读原文；自动恢复的 critic 科学基础仍进入 assignment，保留 source alias 与材料读取，不要求作者手填机械 port |
| 可确定派生 | 单一 `InputPortSpec.derivation` 从精确锚点沿声明 producer input 链求 subject/siblings/sources；compiler 拒绝无实现隐藏必填、环与无效锚点，invoke 拒绝手填自动端口，缺失/歧义给科学锚点诊断，不选最新/按类型猜 |
| 现存生产消费者 | `science.hypothesis.criticize.v1` 从 portfolio 恢复原 foundation；`science.evidence.qualify.v1` 仅给 foundation，控制恢复原 extraction、siblings、sources、audit；validation_results 合并到原 producer siblings，无重复输入组 |
| 删除/合并 gate | 普通任务不再因 reviewer 不可用而不可调用，不强制每个下游绑定 exact-review witness；review edge 明确 optional。正式 review 一旦选择仍由同一声明派生独立性要求。低价值旧 revision/template gate 随 E 退役入口迁移，不能称已全部删除 |
| 保留重大政策 | evidence qualify 仅用于采用 foundation 的、声明其 approval 的消费者，要求精确当前 producer/audit 与独立来源审查及 UI 决定；不是所有任务完成门槛。原不可变来源、权限、预算、幂等及终态校验保留；2e9 字节/3600 秒 TCAD 自治配置不复制、不重硬编码 |
| Root 合同与读取 | invoke 展开端口默认值，声明 invocation/dispatch/qualification/review；生成 scheduler 正常路径自包含，guide 仅维护。默认 completed status 按声明取适量科学决策字段，缺失和 scheduler_signal 裁剪显式报告；显式 poll 保持短状态，`output_fields` 允许科学字段名；高基数 parents/producer_inputs 有分页与遗漏语义 |
| 控制真相与展示 | Root catalog/full/status/run_list/artifact/detail/producer_inputs 与 assignment 采用声明分类；不递归按键名删除科学 payload。共同 workspace tool-evidence 为科学材料列表，submit 与 acceptance 两端一致校验；私有 DB/CAS proof 完整，恢复从真实 records/attempts/accesses 重建，不从公开 workspace receipt 反推。错误保留内部诊断、公开可修原因；不声称能硬拦平台全工具表或任意 native 输出 |

最小源码验证均由既有 `scripts/run_r3_source_acceptance.py` 串行执行；每进程 AS 2,000,000,000 B，采样树 RSS 1,500,000,000 B 提前止损，节点 120 秒、数值线程 1；MemAvailable ≥8 GiB/下降≤2 GB、Dirty≤128 MiB。所有最终节点正常退出，无超时/资源止损；并非 cgroup 聚合硬隔离。

| 精确节点（均位于 tests/operations） | 最终秒 / RSS 峰值 B | 验证内容 |
| --- | --- | --- |
| `test_r4_root_contracts.py::test_root_contracts_compile_and_prompt_is_self_contained` | 1.715 / 103591936 | 当前目录编译、隐藏无派生/派生环负例、自包含 prompt、可选 review、单锚点 qualifier |
| `test_r4_root_contracts.py::test_root_default_decision_and_exact_origin_binding` | 2.215 / 121860096 | 真实 Root 默认决策/显式 poll/科学字段名、exact prior 来源派生、幂等、缺锚点和手填机械端口拒绝 |
| `test_r4_root_contracts.py::test_control_receipt_recovery_uses_records_not_public_workspace` | 2.214 / 118259712 | Run/CAS receipt 分离、已注册工具 attempt 持久记录、跨 Run 原 proof 恢复；未执行网络工具 |
| `test_r4_root_contracts.py::test_qualification_derives_exact_sources_and_rejects_old_audit` | 3.218 / 123936768 | 实际 extract→独立 audit→split→单 foundation qualifier、幂等 pending 审批；只升级审查声明即拒绝旧 PASS 且不新建审批 |
| `test_r4_experiment_task.py::test_reviewer_and_scientific_surfaces_use_declared_contract` | 2.215 / 119111680 | A 正式 reviewer 可信身份与科学出口回归 |
| `test_r4_stage_delivery.py::test_running_and_final_deliveries_share_readonly_scientific_projection` | 6.342 / 122388480 | B 阶段读取/最终采用回归；其默认短状态断言现显式选 poll，C 默认改为有限决策字段 |

证据为 `/tmp/scid-r4-c-final-check/result.json`（5 节点）、`/tmp/scid-r4-c-closeout-check/result.json`（最后生产清理后 2 个受影响节点）、`/tmp/scid-r4-c-qualification-check/result.json`（新增真实资格入口正反例）。均为实际源码服务/SQLite/CAS 路径，执行 adapter 为测试替身，不代替安装或真实运行。中间夹具失败为不存在的 intake Operation 名、初始恢复预算漏设及未声明 limitations 值断言；已分别纠正为实际 extract 名、请求初始 max_attempts=2、缺失状态断言，没有放宽生产校验。

**E 必迁生产消费者（本轮必须关闭，不是可选优化）：**

- `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py` 的 `CalculationRecord.input_digests/attempt` 与 `CalculationAttemptReference.proof_kind`；`plugins/curve_score/curve_score/analysis_tool.py`、`diagnostic_tool.py` 仍构造私有来源/attempt/checkpoint input_refs/input_digests，并公开诊断文件 receipt。应随旧分析入口迁移为科学结果与私有 proof 两份明确声明。
- `src/scidiscovery/artifact_agent/service/analysis_artifacts.py::publish_analysis_file/retain_calculation` 将完整 record 写入 `.operation-tools/analysis/` 并公开 `calculation_path`、sha256/path；同文件 calculation source/reference/recovery 校验、`service/tool_evidence.py` 的 calculation_sources 消费者、`plugins/curve_score/curve_score/analysis_workspace.py` 和 `plugins/tcad_artifact/tcad_artifact/result_analysis.py` 的工具/结果消费须一起迁移。C 没有先删 finalizer 所需字段。
- `plugins/curve_score/curve_score/science_operations.py` 的 prior_analysis_manifest/recovery_manifest context、`general_science_agent_operations.py` 的三个 source_manifest 输入及旧 hypothesis revision 的 max_revisions/progress_fingerprint、`plugins/curve_figure_evidence/curve_figure_evidence/figure_science_operations.py` 的旧 family/revision 绑定与 `plugins/tcad_artifact/tcad_artifact/parameter_operations.py` 的 parameter_audit/approval family cohort：E 合并科研任务时使用同一 InputDerivationSpec 精确原始链或随退役入口删除，不能继续把机械端口交 Agent，也不能把旧 gate 改名隐藏。

候选以 `/tmp/scid-r4-c-baseline/manifest.json` 的原内容/hash/原 untracked 状态为界，避免将既有 R3/A/B 工作归入 C。精确批次差分 `/tmp/scid-r4-c-candidate.diff`，文件与 hash 清单 `/tmp/scid-r4-c-candidate-manifest.json`。作者自检已完成，封存后停止修改；独立审查尚未进行。

### 2026-09-25：C 独立审查三项 P2 修复候选（candidate_ready，待复核）

- 独立审查无 P0/P1，发现三项 P2：公开诊断分页被科学白名单整体丢弃；未批准 foundation 的错误路径使用不存在的 cohort 字段；多跳派生跨 Transform 时沿用初始锚点名称。修复保持 C 范围，E 必迁项不变。
- `mcp_root_run_routes` 恢复安全失败原因和 `diagnostic_events.next_after`。存储诊断先按当前声明重新校验，再仅返回类别、可修正科学字段及修复说明；工程附件、原始 reason、控制事件和身份保持私有。公开 RunStatus schema 同步明确 terminal/detail/compat 页及默认决策字段行为。
- 资格错误从同一 `input_admission.approval_subject_ports` 沿派生锚点映射到可见科学输入，preflight/invoke 均给 qualification/UI 修复动作，不要求填写 cohort 或隐藏输入。多跳来源每跳以精确 ref 查本实例材料名称并验证原件，继续只走声明 producer edges；不替换为最新或按类型猜。
- 最小受限验证：`test_r4_root_contracts.py::test_failed_run_safe_reason_and_diagnostic_pagination` 于 `/tmp/scid-r4-c-review-fix-check/result.json` 首次通过（2.615 秒，树 RSS 117420032 B），之后未重复。`test_qualification_derives_exact_sources_and_rejects_old_audit` 于 `/tmp/scid-r4-c-review-fix-chain-check-04/result.json` 最终通过（3.620 秒，树 RSS 131751936 B）：实际未批准 foundation 的 preflight/invoke 锚点、已完成实验 Run→split Transform→原 intake 的多跳调用、缺失来源拒绝、单 foundation qualifier 幂等与旧 audit 版本拒绝。未 mock 来源解析器，未执行新增实验副作用。
- 中间失败均为测试材料搭建问题：split 主输出名称、基础缺 objective_contract、opaque 提取源不接受 foundation、实验 Worker 缺既有服务绑定。已使用合法实验消费者与原运行服务完成夹具，没有放宽生产 schema/资格 gate。所有节点遵守原串行 AS 2e9/RSS 1.5e9/120 秒/线程 1 及系统内存 guard；无超时/资源止损、安装、模型或真实 TCAD。`git diff --check` 通过。
- 修复前内容/hash/原 untracked 状态在 `/tmp/scid-r4-c-review-fix-baseline/manifest.json`；修复增量 `/tmp/scid-r4-c-review-fix.diff`，本批累计候选 `/tmp/scid-r4-c-review-fixed-candidate.diff` 与 `/tmp/scid-r4-c-review-fixed-candidate-manifest.json`。作者修复自检完成，封存后停止修改，等待原审查者复核。

- C 修复候选冻结后，原独立审查者只读复核三项 P2 均闭合，未发现直接回归，未新增测试。C 本轮无剩余审查发现；E 明确列出的旧消费者仍须迁移，不能据此宣称全体系隔离完成。先推进 E 再 D，避免在旧控制信息表面上增加委派能力。

### E 源码候选封存（2026-09-25）

- 证据提取/修订复用 `science.evidence.extract.v1`；假设提出/修订复用 `science.hypothesis.propose.v1`。移除独立 intake/evidence/hypothesis revision 注册、固定 revision/fingerprint 的领域使用及旧提示。
- 参数仅保留 `tcad.parameter.evidence.extract.v1` 完整科学 package 和内部 `worker_parameter_check` coverage/uncertainty 计算。audit、expand、coverage、uncertainty、pass/exception qualification 的旧调度链没有当前外部采用消费者，整组退役；通用 evidence.foundation 资格政策保留。
- `science.result.diagnose.v1` 内连续评分/绘图/诊断，计划和审查为可选上下文。旧 curve-contract design/review、curve-error analyze/专用 diagnose、curve score/reference/objective coverage 与 TCAD PLX/log normalize 调度注册退役。算法保留，实际工具继续调用：`worker_curve_score/diagnose` 和 `worker_tcad_curve_score/diagnose`；后者经 `parse_tcad_sources` 调用 PLX/log 原解析器。
- Calculation 的公开 schema/CAS/工具返回只保留科学记录；input digests、attempt 和工程诊断保存在同次工具 receipt 的私有 metadata，finalizer/recovery/reference_access 从精确原件复原。checkpoint 的数值与来源 proof 分离；图像 request/manifest/validation/selected-family 按明确文件格式投影，并从同次 receipt 复原原字节供原检验使用，不递归删除科学 payload 字段。
- 同一 `InputDerivationSpec.producer_output_port` 声明派生 prior-analysis/figure 私有来源；compiler、Root resolver、冻结和完成 Run 查询共同检查精确 producer/port/Run。复用 figure 按当前 Run 已接纳的 exact evidence 成员选取。科学 assignment 隐藏机械 port；workspace/continuation 由已有 control binding 读取。展示模式不再停用真实 RunDB 恢复 proof。
- 作者源码验证：`python scripts/run_r3_source_acceptance.py --config /tmp/scid-r4-e-candidate.json --execute --output /tmp/scid-r4-e-candidate-01`，7 节点均通过。3 完整节点分别为 calculation 科学/私有封存及 reference read、parameter+ready figure 同次原件复原/连续复用、checkpoint 中断恢复仅重绘与改变方法拒绝；另含目录编译、C receipt recovery、C qualification 正反例、A SDevice 科学/独立审查回归。
- 7 节点耗时依次 2.416/3.219/2.416/1.108/2.013/2.719/2.012 秒，树 RSS 峰值依次 117813248/126648320/121167872/100610048/115236864/122519552/115490816 B。均采用 AS=2000000000 B、RSS stop=1500000000 B、120 秒、数值线程1及现有 MemAvailable/Dirty guard，均正常退出。
- 随后仅静态清理已替代的 calculation_path/公开 private-inline receipt/手填 hidden manifest/退役入口测试，保留独立评分、解析、schema、科学判定及来源算法测试；纯数值测试改读科学摘要或直接算法结果，capture/audit 不再搬运 source_manifest。33 个变更测试模块 AST 解析及本地 fixture import 检查闭合，`git diff --check` 通过；未新增生产修改、未重跑矩阵。
- E 独立基线 `/tmp/scid-r4-e-baseline/manifest.json`（原内容/hash/untracked），精确候选集合 `/tmp/scid-r4-e-candidate-files.json`，差分 `/tmp/scid-r4-e-candidate.diff`，验证原始记录 `/tmp/scid-r4-e-candidate-01/result.json`，静态检查 `/tmp/scid-r4-e-static-check.json`。差分相对此批开始时工作区，不混 HEAD 既有修改。
- 未覆盖：安装包/真实模型/真实 TCAD/浏览器/F 外部实验验收；未运行全套 pytest。A 科学实验和 SDevice 源码回归通过；2GB/1h TCAD 配置政策未改。E `candidate_ready=true`，停止代码和测试修改，等待独立复核。

#### E 独立复核修复封存（2026-09-25）

- 修复 P1：所有 `agent_visible=False` 输入按同一声明从实际 workspace materialization 与 reference roots 排除；私有 proof 仍由控制 context/RunDB 读取。真实检查确认 hidden manifest 文件未生成、原始 bytes 未落到 inputs、`read_input.py --file` 失败、reference alias 读取被拒绝。此前 reference manifest pairing 已拒绝读，不将其描述为已成功泄漏。
- 修复 P2：当前 Run 已注册且输出声明可见的科学材料可用 `worker_reference_read` list → content reference 读取；复用原有不可变 CAS 校验、分页、IO/响应预算，不复制私有 receipt，不接纳其他 Run 未绑定材料或 hidden manifest。
- 修复 P2：从报告 schema 删除作者填写的 `calculation_records`，同步 finalizer/科学校验/语义声明/提示与旧测试；报告只引用工具封存的科学材料别名。真实节点验证该字段在 schema 层拒绝，而别名报告能正常封存。
- 同一修复候选 7 节点全部通过：`python scripts/run_r3_source_acceptance.py --config /tmp/scid-r4-e-candidate.json --execute --output /tmp/scid-r4-e-review-fix-final-01`；耗时依次 2.821/3.319/2.619/1.211/2.014/2.920/2.217 秒，RSS 峰值 116953088/127037440/117919744/100585472/114835456/121872384/115224576 B，沿用上述资源 guard。随后只修正旧测试静态语法，全部修改 Python AST 解析与 `git diff --check` 通过。
- 修复前独立基线 `/tmp/scid-r4-e-review-fix-baseline/manifest.json`，修复差分 `/tmp/scid-r4-e-review-fix.diff`；完整 E 精确集合及差分仍为 `/tmp/scid-r4-e-candidate-files.json`、`/tmp/scid-r4-e-candidate.diff`。`candidate_ready=true`，停止修改，交原独立审查者复核；外部验收边界不变。

#### E 引用恢复回归修复（2026-09-25）

- 定点修复 `adopt_reference_access` 误用了仅存在于读取分支的变量，恢复从当前控制绑定调用 `_reference_alias(value, target)`；其余已复核的科学/私有边界不改。
- 原 calculation 完整节点增加真实持久引用读取 → 原 Run 失败 → `draft_from` → `worker_open_assignment` → 再读 → 引用报告封存。确认原 artifact/root/chain/proof/budget_scope 保留、adopted_from 精确关联原访问，重读不新增访问记录。
- `python scripts/run_r3_source_acceptance.py --config /tmp/scid-r4-e-calculation.json --execute --output /tmp/scid-r4-e-reference-adoption-01` 通过；3.929 秒、树 RSS 118706176 B，资源 guard 不变。仅运行此节点；修改 Python AST 与 `git diff --check` 通过。
- 独立增量基线 `/tmp/scid-r4-e-reference-adoption-baseline/manifest.json`，增量 `/tmp/scid-r4-e-reference-adoption.diff`；完整 E 集合和差分同步更新。`candidate_ready=true`，停止修改，交复核。

- E 原三项审查发现及随后引用恢复直接回归，均经作者定向修复和原审查者只读复核闭合。未执行额外审查测试；E 本轮无剩余已报告发现，继续 D。真实模型、安装部署、浏览器与求解器验收仍未恢复。

### 2026-09-25：D 内部助手源码候选（candidate_ready，待独立审查）

- 完整科学任务通过已有 `with_reference_access` 声明组合获得可选 `worker_helper`，仍由唯一 Operation 编译器冻结工具、权限和摘要；统一 gateway、local 与 hardened Worker 共用 RunService 注入。助手不是公开 Operation、独立 Run、正式 reviewer 或 approval actor；负责人验证并整合意见。
- 输入仅科学名称、任务、选定输入别名/科学输出文件；控制层冻结有界 UTF-8 快照及私有原始绑定。返回科学 name/status/result、结论/依据/原引用/局限，不传 Root 历史、Run/thread/session、摘要、凭据或预算归属。`ask/status/result/cancel` 共用一个合同；ask 最多短等 0.2 秒，避开现有 MCP proxy 10 秒时限；status 只读且不消耗 attempt 预算，不重复正文，建议至少间隔 5 秒，由负责人取 result，不让 Root 代轮询。
- 配置位于全局 agent settings 的 `helpers`：本版仅支持 max_depth/max_active 为 0 或 1（默认 1），拒绝伪支持的递归/并行值；默认最多 4 次、每次最多 300 秒、累计预留 600 秒、输入 32768 bytes、输出 8192 bytes，权限限 supplied_materials。每次保守预留完整时限；未知/失败不退还、不自动重试。沿既有恢复父链共用 activity 账本和冻结政策，不重置计数；原 Run deadline 始终生效。
- 生产 transport 为新建的受控 `codex exec` 路径，未复用旧调试 launcher。沿用父 Run 冻结 model/effort，只白名单读取已配置 provider routing 和必要模型认证；独立临时 cwd/HOME/CODEX_HOME，清理继承环境，不修改当前宿主配置。0.157.0 对应官方源码/schema 已静态核对；禁用 shell/web/image/MCP/继续委派、插件/Skill 自动注入；权限 profile 只准读取材料目录和平台 minimal 路径。仍可能注册 apply_patch 等原生辅助工具，不声称零工具或 OS 完全隔离；实际 sandbox 行为留 F。未知 system config/requirements 或不支持的 provider 配置拒绝启动。
- 后台 transport 与同 MCP 宿主取消不互锁。普通 Python supervisor 持有独立 CLI 进程组、父进程存活/时限监测和临时认证清理；控制侧保存 PID/starttime 与子进程 receipt，避免 PID 复用误杀。父失败/超时覆盖助手；未知清理保持未终态及 recovery_pending，不提交成功。正式提交复用声明中的“助手须终态”和 Run validator，不增加科学充分性或强制调用/审核关口。
- CLI 树 RSS 默认提前止损 1.5GB（可配置且上限 2GB），虚拟地址默认 16GiB 单独记录；采样不等于 cgroup 聚合硬限制。保存 CLI 原始 input/cached/output usage（缺失为 unknown），bytes 不代替 tokens，也不宣称 CLI 单次精确 token 硬上限。
- 受限源码证据：`/tmp/scid-r4-d-final-checks-1/result.json` 13 节点/14 项通过，19.748 秒、采样树 RSS 峰值 118464512 bytes；真实 router→账本→后台 transport 替身覆盖幂等、越权材料、引用/输出限制、恢复预算、父失败取消和终态；普通 Python 子进程覆盖输出/超时/后代及宿主退出后的认证清理。`/tmp/scid-r4-d-generation-1/result.json` local/hardened 生成配置 2 项通过；最后进程清理增量 `/tmp/scid-r4-d-process-final-1/result.json` 通过。均经串行 guard（AS 2e9、RSS 止损 1.5e9、系统内存/Dirty 止损、120 秒、numeric threads=1）。没有运行 Codex/App-server/模型、安装构建、真实 TCAD、全套 pytest/global collect。
- 跨批漏迁闭合：旧 gateway 测试仍要求公开 operation_digest/invoke.compact.v1，已按 C 的科学合同静态更新，独立业务断言保留；新 R4 gateway 节点验证实际入口，未重复旧 archive 矩阵。生成验证曾被 `_validate_scheduler_guides` 的旧 prompt/guide 字面量 gate 阻断，按授权删除该无消费者文字要求，保留必要生成文件内容/结构和角色合同检查；没有把读 MD 要求放回 Root。
- F 尚须真实验证 CLI 登录/provider、实际工具表与权限、线程/slot 占用、usage 语义及内存启动边界：父 native Worker 等待时仍占原平台线程；助手是独立 CLI 会话，不把它冒充原生 subagent slot 的释放或复用。源码/替身通过不能证明真实模型委派或性能收益。
- 本批原始内容/hash/tracked 状态在 `/tmp/scid-r4-d-baseline/manifest.json`；精确候选文件与差分为 `/tmp/scid-r4-d-candidate-files.json`、`/tmp/scid-r4-d-candidate.diff`。`candidate_ready=true`；完成作者自检后冻结，等待独立跨边界审查；未 commit/push/部署。

- D 冻结后已完成独立只读审查，未发现可确认的阻塞性源码缺陷。实际注册、材料权限、原账本/恢复、终态和取消、supervisor 清理及正式审查边界已核对；未运行额外测试。A–E 源码批次完成，进入 F 执行范围恢复前的候选状态。

### F 真实验收范围（用户已授权，启动中）

1. 在当前工作目录内创建独立临时候选，串行验证打包安装、实际配置及不调用模型的宿主启动。先确认 CLI/认证/provider、权限配置与资源约束可用。
2. 运行最小真实 Root→完整科学任务→一次内部助手→交付/阶段 UI 链；记录 Root/Worker/helper 各自 input、cached、output、峰值及工具返回大小，核对是否重复注入指南、原始控制字段或大工具列表。
3. 在原执行范围恢复后做短 TCAD 及必要取消/恢复验证，沿现有配置与真实原始结果验收。完成后清理临时安装、进程、任务目录和认证材料，保留有界的脱敏证据。

用户已明确允许上述真实验收，并随后临时放宽验收总内存预算到 13GB（13,000,000,000 字节）。继续全程串行、内存采样、提前止损和超时，CLI 虚拟地址预留与实际 RSS 分开记录；验收运行参数单独配置，不据此改变 TCAD 的 2GB 文件存储/1 小时自主执行政策。已恢复隔离安装构建、真实 Codex/内部助手及短 TCAD 验证权限；结束后清理临时环境并保留脱敏证据。

### F 首轮真实验收与正常宿主接续（2026-09-25，部分通过，未闭环）

- 冻结完整当前候选 4702 文件，构建安装核心及 3 个实际插件 wheel；独立 venv、`python -I` 的四包导入均来自安装目录，pip check 通过。默认生成 Root 合同位于独立 git 根，未增加跳过合同的验收提示。永久证据与逐目标矩阵：`evidence/research-task-r4-f-20260925/summary.json`、`acceptance-matrix.json`。
- 本机 CLI 0.157.0 的 app-server initialize/thread-start（无模型）、真实 daemon/proxy/MCP 三工具注册及 UI HTTP 200 通过。默认 local native command 精确阻塞：固定 `/tmp/codex-daemon-1000` 被外层沙箱两层只读 tmpfs 遮蔽为 mode 000；CLI bubblewrap 要求同 UID 的 0700 目录。该检查不影响已通过的模型/MCP初始化。未 chmod/unmount/换 UID/关闭 sandbox。12 个现有科学 Agent Operation 都声明 native shell；local assignment 又要求原生读取角色/输入，不能用手搬正文或更改声明冒充合法部分链。
- 找到并定点修复真实 D 缺陷：CLI `-c` 键按 literal dotted path 解析，原逐组件引号导致 strict config 拒绝 `"approval_policy"`。保留修前快照/hash及两文件差分，补充嵌套 provider 和特殊 filesystem 键验证；定向测试及修后安装包 strict-config 初始化通过，仅重建/重装核心 wheel。`fix-files.json`、`helper-cli-key-fix.diff`、`fixed-core-wheel.json` 记录确切候选；待独立复核。
- 一次真实 installed CodexHelperTransport 成功返回合成三点的斜率 1/2、截距 2、指定材料引用及局限：CLI turn usage input 7515、cached 0、output 151；任务 payload 450 UTF-8 bytes（不当 token），12.11 秒，助手采样树 RSS 201506816 bytes，临时认证及进程已清理。有效配置确认 root deny/workspace read/network false/agents false/MCP空；无工具调用事件，实际发送工具表与 provider 隐藏重试未捕获。不是 Run 内 `worker_helper`/负责人整合通过；Root/Worker 尚无模型请求，不能宣称 token 降幅。
- 当前 installed runner 的全新串行 SSH 短任务 SProcess/SDevice 均 succeeded/exit 0，消费墙钟 18/13 秒；8 项输出流式收集 SHA256/大小一致，缺授权提交实际拒绝。远端树 RSS 峰值 173395968 bytes，无残余任务进程。2,000,000,000 bytes 文件/3600 秒自治政策保留。此为求解器/传输工程验收，不冒充模型作者的设计、debug、阶段交付与科学有效性闭环。
- 全部阶段串行，50ms 采样、树 RSS 11e9 提前止损、MemAvailable 2GiB 下限，名义预算 13e9；虚拟 AS 独立 64GiB。未获得 cgroup 聚合硬隔离；观测宿主阶段峰值 581316608 bytes。
- 正常宿主接续命令已具体准备：外层 `.r4f-20260925/host-run.py`。它先检查固定 socket 目录和候选 wheel，再运行正常 sandbox shell 控制，成功后才启动真实 Root。持久 app-server 同线程继续，实际 Root 返回实例管理 URL 后仅用户页面可选择；不使用 exec resume。MCP 原始字节 tap 与 rollout/token审计保留实际大小及未知项。脚本语法检查及本嵌套沙箱的提前拒绝分支已验证，正常宿主尚未执行。临时安装/必要认证和远端隔离 runner 按接续要求保留，结束后必须清理。
- 尚未通过：完整研究负责人、多阶段真实 UI/版本、Root 自包含及机械隐藏真实 workspace、按需正式 review/修订不继承、取消恢复幂等预算、Run 内助手整合、Root/Worker 逐请求消耗及 scientist-owned TCAD 全链。F 与整体计划保持未完成。

#### F 正常宿主首轮与身份兼容修复候选（待独立审查）

- 用户在正常宿主启动既有接续脚本；native sandbox控制通过，实际Root运行一轮后暂停。真实0.157元数据有session/thread但普通Root省略可选thread_source，旧gateway误作必填，catalog与describe均拒绝；尚未生成实例管理URL、未选择实例、未创建科研Run。
- 官方0.157源码确认session_id是Root及所有descendants共享的Root线程ID；thread_id是当前线程ID，thread_source为Option。候选把该可信身份关系收敛到一个解析器，gateway/proxy/daemon共用；缺可选source不再失败，显式source/parent/subagent标记冲突仍拒绝，Worker仍受原Run/模型/独立性绑定。精确5文件前后hash及差分：`metadata-fix-files.json`、`metadata-identity-fix.diff`（同F证据目录）；未重装或重启正在等待的服务。
- 两项受限定向验证通过：gateway真实缺source形状下Root/Worker权限与绑定；真实proxy→daemon缺source的Worker不登记为scheduler、不能调用Root，Root正常登记。详见`metadata-fix-checks.json`；首次长fixture socket路径失败与新测试lazy client表前置误设均原样记录后更正fixture。既有混合安装测试仍失败：deploy/install.sh的probe_root_context_contract保留poll/可见digest/invoke.compact.v1旧断言，确认为另一项未修兼容缺陷，单独交后续串行审查，不报通过。
- Root失败轮精确证据：7次CLI请求，累计input122577/cached92672/output513，单请求输入峰值18496；累计input不等于新增。共有一次限定3工具的ALL_TOOLS筛选、2次MCP拒绝、3个本地guide诊断命令；只有一份生成scheduler块，未重复外层旧强制guide指令。`root-first-turn-metadata-failure.json`记录逐请求tokens与模型可见输出字节。正常研究路径Root负担尚不能据此判定，Worker/任务内helper仍未启动。
- 修复期未发新turn，现有app-server会话awaiting_user；保留原13GB预算/截止时间，无自动延时或重试。候选完成后停手，交父串行独立审查与其余同类缺陷修复。

#### F 同类契约缺陷修复候选（2026-09-25，待独立复审）

- 独立审查认可身份修复，另确认并修复安装器旧断言和 TCAD 历史分析私有来源缺失。`deploy/install.sh` 两阶段按当前 `decision` 默认、隐藏 digest、`invoke.scientific.v2` 检查；保留三工具、完整分页与契约能力检查。
- materializer/finalizer 获得只读的完整冻结输入字节与 descriptor；复用控制侧原件完整性检查，不把私有 manifest 写回科学 workspace。TCAD hook 以此读取 prior-analysis proof。精确7文件差分/前后hash：F证据 `contract-surface-fix.diff`、`contract-surface-fix-files.json`（manifest SHA256 `073afdca6b1171f4503dd724426ff6ba360a267932d82e2077f11227c07622ef`）。测试仅提取既有明示合成 package 为3.7KB数据，移除测试对已删AUTHOR_PROMPT/旧必需review输入的依赖，未恢复旧生产API。
- 受限真实services回归：首次TCAD曲线计算封存→合法prior_analysis派生→open→历史计算读取→submit通过；私有文件不出现于workspace inputs且reference reader拒绝私有alias；无sealed producer副本和不兼容version均拒绝。末次4定向用例全过（5.40秒，采样树RSS128352256 bytes），兼顾失败/取消零输出及通用science私有proof路径；非模型作者验收。精确过程失败、修正和采样阈值见`contract-surface-fix-checks.json`/`contract-surface-fix-summary.json`。
- 独立临时site安装新core/TCAD wheel（含已审身份修复），其模块逐字节匹配当前候选。安装器原始installed-package probe及真实daemon→stdio MCP三工具/Root invoke probe全部通过（2.88秒/RSS185614336 bytes），临时daemon已退出。wheel SHA见`contract-surface-fixed-wheels.json`；未覆盖旧host venv，未重启/续跑Root，本轮无模型/TCAD调用。发布候选后仍需协调host/control/proxy重启再续验，不可把此工程验证算作完整研究验收通过。
- 收尾读取既有guard采样仍实时更新（约2050秒/3600秒，8进程，RSS约45MB），Root awaiting_user且无待发turn；工具命名空间/proc不可见正常宿主PID，不能据此宣称退出。`contract-fix-host-observation.json`保留准确观测。候选执行者现已停止新增工作，等待独立复审。

#### F 复审通过后的宿主重启准备

- 父任务独立复审通过身份兼容修复及两项P1，私有来源hook未发现直接回归。通过既有`host-control.py stop`停止首轮宿主；guard正式终态exit0、2194.04秒、无残余进程，峰值树RSS615727104 bytes。首轮失败turn、逐请求usage、MCP/CLI日志和rollout完整保存在临时`history/first-root-metadata-failure/`，永久失败与审查证据保留。
- 已串行受限安装审过的core+TCAD wheels到临时host venv（1.318秒/RSS89387008 bytes）；四wheel pin及222个安装文件hash已更新，未改个人配置/现有服务，未发新模型或TCAD请求。证据`reviewed-host-redeployment.json`。
- 相同正常终端命令`python /home/da/project/ai4s/tcad/git_release/scidiscovery-agent/.r4f-20260925/host-run.py`已准备好；下一次使用独立guard `39-normal-host`、原13GB监督及3600秒预算，保持默认sandbox，先无模型基础检查再开始真实Root。当前为`prepared_awaiting_normal_host_start`，没有存活研究session；实际Root返回新管理URL后仍仅用户UI选实例。部署准备执行者已停止，交父安排用户单次启动，完整F仍未完成。


#### §4.1 第2批：统一科学投影与注销旧实现（2026-09-26，仅静态）

- 已删除 `OperationSpec.agent_context` 双模式开关；assignment 对所有 Agent 一致隐藏机械 port/ArtifactRef，result schema 一致过滤私有来源；缺服务错误不再因旧模式泄露内部服务名。声明、实验/审查入口和对应断言同步；未改变编译器/catalog ABI、组件配置身份、public/support/internal或schema版本机制。
- 核对生产Python引用、字符串ComponentSpec资源、插件入口和CLI后，删除不可达 TCAD `operation_workspace.py`、`worker.py`、`curve_operations.py` 及 core `artifact_agent/audit.py`。注销无当前消费者的 compare/review-validation/realization/control-equivalence 四support、组件及包装函数；保留 execution-context投影、analysis可选runtime-attestation及其完整性/parentage校验，保留当前execution/result-analysis使用的reviewed-package schema。未改project_packager算法、helper接口或策略阈值。
- 删除仅服务旧author/review流程的测试；混合文件保留纯诊断、数据与当前分析/来源边界。输出收集、日志冲突和实际进程限额/清理测试迁至生产 `remote_runner_py36`，不恢复旧worker/API。所有改动以当前工作树原件归档 `/tmp/r4-step2-20260926/before/`，精确增量 `step2.diff`、前后hash `final-manifest.json`，未提交。
- 仅做AST解析、残留引用/入口扫描及限定diff检查；明确未运行pytest/collect、业务import/catalog编译、安装构建、模型或TCAD。静态结果不代表运行通过；宿主验收和认证处理仍暂停，后续串行批负责通用插件API、helper/service/config/docs边界。

### 2026-09-26 修复步骤 3：原生内部助手源码候选（未运行验证）

- 退出旧 supplied-materials CLI/进程守卫/后台轮询链及专用测试替身。负责人用 `worker_helper.prepare` 冻结科学子任务/文件引用，再按返回指示 fresh native spawn（不带父历史），原生等待/通知后整合；`release` 只撤销同 Run 工具访问，原生线程仍由平台关闭。子任务正文只在准备时填写，子线程通过可信 `parent_thread_id` 自动取得冻结任务，Root 不搬运身份或中间结果。
- `WorkerConnections` 内增独立 participant 绑定，owner 连接不变；任务谱系限定准入计数和单活动访问，恢复不刷新额度，未知 native spawn 不自动重试。配置仅 0/1 层、0/1 活动访问、累计准入数及准备输入字节；不是原生线程数、RSS、模型调用数或 token 的硬限制。原始任务 deadline 与科学工具 attempts 继续生效，native 调用在 MCP 之外的时限执行仍由平台负责。
- 同父任务工作区、Skill/native 许可与科学工具；助手使用独立 assignment/工具合同投影，不覆盖 owner 文件。声明的 `owner_only` 同时约束列表与实际路由，排除最终提交、阶段封存和继续委派；参与作者身份纳入正式独立审查排除。共享任务锁/工具状态，hardened 复用同 Run transport lease但保留独立 caller。
- 提交/失败撤权不再等待不存在的 native 完成 receipt，也不宣称 native 进程已终止；真实外部执行未终态检查保留。助手结论/文件通过原生完成返回，由负责人检查，不另造正式结果或审批凭据。未提供可信平台 usage 时明确 unknown；本批不新增完整 app-server controller。
- 新增实际消费的 RunService `task_lineage/compiled_operation/running_task` 接口；Worker service loader 移至统一 runtime 装配模块，ExperimentExecution 退出 service→MCP 反向导入与构造器反向注册。执行查询用既有 `(instance, namespace, name)` 绑定索引和当前 task 前缀限定；participant 记录纳入实例归档，历史归档迁移不伪造身份。
- 本批遵守“不测试”：只静态 AST、引用检查与精确 diff；未 import catalog、collect、pytest、运行 Codex/模型、安装/构建或 TCAD。旧助手测试已替换为待执行 gateway/持久身份/撤权断言，不称已通过。源码基线、独立 diff/hash 与静态记录位于 `/tmp/r4-step3-20260926`。
- 仍待用户恢复验证后确认：安装版 0.157 子线程真实 metadata、fresh context 和权限/Skill 继承、hardened 同 Run 路由、native close/异常停止及 slot 回收、真实原始 usage、完整负责人采用助手成果链。框架撤权不会停止已经在运行的原生命令；LocalTrusted 共享工作区不是新增 OS 隔离。3 月本地 Codex checkout 未当成 0.157 行为证明。


### 2026-09-26 修复步骤 4/5 与统一复核完成（仅静态）

- 当前执行包统一为 `ExecutionPackage` / `tcad.execution-package.v2`，保留可选审查记录的真实含义；旧 schema 仅用于历史原件来源遍历。`execution_io` 的导出/分页字节与收集总时限、单文件时限、无进展时限进入 Run 冻结配置；实际执行受剩余 Run 时间约束。实例 `helpers/execution_io` 按显式字段覆盖，全局值可被实例显式默认值覆盖，恢复沿用原快照。
- 同步 scheduler 源、e5.2 受管 AGENTS、架构与 TCAD 中英文当前说明；外层 AGENTS、个人配置和既有服务不变。临时验收脚本静态修正 failed/interrupted 不再显示 awaiting_user，无认证或进程操作。第4/5批快照及差分保存在 `/tmp/r4-step45-20260926/`。
- 三批候选的96个路径哈希经独立审查匹配；审查发现并修复：活动helper可被再次attach为另一Run负责人；通用执行包版本硬编码2；架构仍描述旧run_status合同。负责人attach与helper admission在同一数据库写事务中双向互斥，release后可复用且保留参与作者独立性；新增capability必填执行包版本，进入资源摘要和Operation身份；当前状态文档同步decision默认和显式全量读取。
- A1修复曾误伤只读worker_identity，已以两行生产增量分开查询与准入，再经原审查者复核闭合。A1/A2/A3无剩余已确认阻塞；证据 `/tmp/r4-consolidated-review-20260926.json`、`/tmp/r4-review-fixes-20260926/` 及其 `increment-owner-identity/`。新增回归断言未执行。
- 全程串行，仅编辑、AST、引用、差异及独立只读审查。测试、模型链、平台线程清理/usage、认证及此前残留进程状态继续未验，不依据历史部署记录宣称当前候选可运行。

### 追加插件平台评审（历史记录：当时仅为候选，后续实施见文末）

- 保留Operation编译器、catalog ABI/digest、组件配置身份、三级可见性与版本化schema；它们是平台能力。已有 `operations` 稳定声明API，根包空 `__all__` 不能证明无插件API；真正缺口是运行时扩展接口。
- 静态统计（排除build）TCAD/curve/figure分别依赖34/19/12个核心模块，其中12/5/2个来自service/interfaces/UI内部层；blind_csv参照为385行、6个核心模块、0内部层。数量仅描述耦合范围，不证明能删除一万行。
- 后续按真实消费者划定受控workspace、证据/计算登记、collection预算、诊断和presentation的窄公共协议/值类型；共用声明构造器进入现有公共声明API。不能只重导出RunService、私有凭据模型或内部函数来掩盖耦合，也不把领域算法移进核心。
- 29个Root逻辑接口（含10个execution接口）仍需按正常任务/诊断恢复消费区分可见性；wire仅三元工具，不等于每次注入29份完整合同。新任务管理的execution已拒绝Root直接操作。后续可收敛普通结论/导航/明确全量读取意图，保留精确证据访问与响应预算。
- `legacy/scientific` 在本轮已经删除；旧独立助手CLI拓扑已经退出，不能把旧助手启动成本当作新原生委派成本。签名/进程机制按实际身份、幂等和生命周期消费者判断，单用户本身不是删除依据。

### 2026-09-26 源码 Git 节点范围

用户要求本轮完成后提交一个 Git 节点。节点保存 HEAD 5871a64 以来尚未提交的累计源码、测试源码、部署模板及文档变更；本轮独立静态审查只覆盖上述修复候选，不外推为整个历史差分的运行验证。未跟踪的 `docs/plans/evidence/` 原始验收数据、日志与源码快照继续保留在本地，不纳入本节点；历史文档中的相关链接需要原始归档，不能据节点缺少原件重建或宣称验证通过。临时宿主环境和生成 AGENTS 不入库，生成源已保存。未运行测试、构建、模型或 TCAD，未更新现有部署。


### 2026-09-26 插件边界第 4 批：Root 入口与读取意图（仅静态）

- RootTool 同一声明标记 research/execution；默认科研面退出十个独立执行接口，三元 wire 工具仍为三个。独立 Effect/历史恢复在目录、描述和调用中一致显式选择 execution；完整实验继续由 worker_experiment_execute 推进，task-managed execution 禁止 Root 操作。能力绑定与重新提交复用现有编译可用性判断拒绝 internal，历史只读状态不重新授予执行资格。ExecutionService、UI、授权、预算与幂等未删除或弱化。
- run_status 破坏式替换为 decision（默认）、status、navigation、full 四意图；删除旧 profile/view/output_mode/include_full_output 组合与兼容投影。保留具名字段或准确路径选读、明确遗漏、索引/阶段分页、终态封存判断；navigation 保留科学输入名与证据原件名，full 仅显式读取封存科学输出。私有恢复/native/工程记录仍由 control/UI 保存。
- 已同步实际 Effect 探针、安装合同探针、受影响测试源码、scheduler/维护说明、e5.2 生成 AGENTS、架构双语和公共 API 说明；外层 AGENTS/个人配置/live 服务与历史证据不动。改前快照、精确增量、前后 hash 和静态结果在 /tmp/r4-plugin-api-20260926/batch4。未运行测试、collect、业务 import、catalog 编译、生成器、构建安装、模型、TCAD、认证或进程操作；候选待统一独立审查与另行授权运行验收。

插件边界统一审查修复：PAPI-1 将完整实验协调器注入替换为实际工具 host 派生的单 Run 窄能力，TCAD 不再访问 runs/executions/artifacts；PAPI-2 执行详情导航返回完整 scid_call 请求，surface=execution 位于网关层而非业务参数。已补针对性源码断言，未执行；同一独立审查者已定向复核通过，两项发现均闭合。


### 2026-09-26 插件运行时 API 与 Root 收敛完成（仅静态）

- 基于 `6c3d76e` 串行完成公共运行时 API、figure/curve/TCAD 迁移和 Root 入口收敛。公共 `scidiscovery.plugin_runtime` 提供实际共用的工作区、科学计算结果、证据视图、收集预算、诊断、展示及传输能力；声明构造器进入 `operations.transforms`。三个真实插件不再直接导入核心 service/interfaces/approval_ui，领域算法仍归插件；控制层继续持有身份、授权、计算凭据、Run 生命周期和资格判断。
- 统一审查进一步核对实际对象注入，发现并修复 TCAD 获得整个执行协调器的问题：改为绑定单 Run 的窄能力，gateway/local/hardened 使用一致边界，拒绝跨 Run 重绑定。执行详情与能力导航均提供含网关层 `surface="execution"` 的完整调用，避免默认科研面导致导航失效。
- Root 默认科研面为 19 个逻辑接口，10 个执行接口需显式选择 execution 面；wire 仍为 3 个元工具。`run_status` 统一四种 intent，保留准确证据选读、分页与明确全量读取；未削弱 task-managed 执行限制或编译目录的操作权威。编译器、catalog ABI/摘要、组件配置身份、三级可见性及版本化 schema 保留。
- 公共 API 说明见 `docs/PLUGIN_RUNTIME_API.md`；同步源码模板、安装探针及受影响测试源码。批次快照、哈希、增量及静态记录位于 `/tmp/r4-plugin-api-20260926/batch1` 至 `batch4`、`review-fixes`，统一审查匹配 110 个候选路径，修复复核匹配 10 个路径。两项审查发现已闭合；未执行新增断言。
- 仅完成 AST、静态引用、差异检查和独立源码审查。既有基线测试问题、真实插件运行链、原生助手权限/生命周期、Root 与 Worker 逐请求 Token 对照仍未验证；不宣称运行验收完成。下一步需恢复验证后先做定向源码验证，再验证最小完整研究任务与 Token。测试、安装构建、模型及 TCAD 当前继续暂停。
- 本轮保存新的本地 Git 节点，不推送、不部署；未跟踪的历史 `docs/plans/evidence/` 原始数据保持本地，不纳入源码节点，生成配置与临时环境不入库。


### 2026-09-26 全量测试代码重构与受限验证完成

- 以 `efe39f7` 为基线，按真实当前消费者删除退役 design/materialize/deck 作者/计划审查流程测试，迁移有效科学来源、资格、权限、恢复、隐藏端口与阶段交付检查；共享可信 Worker fixture 取代绕过身份的测试准备。`test_*.py` 从 133 文件/37158 行/1040 个测试函数变为 131 文件/34830 行/972 个函数；参数化用例数独立统计，不以删除数量代替覆盖证明。
- 默认源码层与 installed/process/stress/live 分开。统一 `scripts/run_tests.py` 和配置替代历史 R3 精确节点脚本，拒绝并发；源码按文件或小批运行，安装共享一次 session 构建缓存，解释器使用链接、依赖缓存复用、磁盘日志有界、临时环境与已观测子孙在退出时清理。资源阈值和运行说明见 `tests/README.md`。大 Skill 复制/回滚改小型合成素材；审批业务链移至进程层；保留一个真实 release/manual 完整性验证。
- 最终证据：源码 1386、安装 16、进程 54 项通过，均为当前文件/节点哈希对应的分批证据；首轮系统内存止损、单批 300 秒超时和主动中断均保留且不计通过。安装/进程收尾峰值树 RSS 335925248 字节，未提高限额。没有真实模型/求解器验收；安装证据是离线复用运行依赖后的 wheel 隔离验证，未覆盖 Python sdist 路径。
- 测试揭示并修复实际缺陷：实例归档遗漏五张执行策略/预算表；预算科学归属跨实例，原数据库账本必须保留以免归档返还额度；当前/历史恢复、冲突、中断和只读归档浏览均有回归。历史合同不可用不再使科学清单读取崩溃，私有恢复记录仍隐藏，历史资格不恢复。三处实际 Worker 提示与可选 objective assessment 校验统一。
- 独立审查匹配 205 项候选；TH-01 进一步补齐含真实 execution 行的旧归档只读路径，TH-N1 恢复通用 Schema projector 异常负控，TH-N2 明确 sdist 未覆盖。最后 9 项定向回归通过，同一审查者复核闭合。证据在 `/tmp/tg-summary.json`、`/tmp/tg-*-current-receipts.json`、`/tmp/ti-fix2/result.json`、`/tmp/ti-review-final.json`，原失败和删除依据保留在临时审计目录；原始日志不入源码节点。
- 本轮仅保存本地 Git 节点，不推送、不更新部署。下一轮先核实用户追加的身份入口、基础工具重复、公共 schema 边界及部署入口建议；跨库合并或全面重写须有具体消费者和收益证据。


### 2026-09-26 底层基础设施建议核实与实施计划（本批已完成）

基线为测试重构节点 `6adf018`。用户要求在测试轮完成后判断追加评审并实施有价值部分；已完成只读消费者审计和隔离临时 socket/JSON Patch/heredoc 探针，材料 `/tmp/infra-review.json`、`/tmp/infra-probe-result.json`。不接触真实控制服务、凭据、求解器或现有部署。

| 建议 | 核实结论与决定 |
| --- | --- |
| Root/Worker 元数据身份 | 临时真实 socket/broker/gateway 证明可用自报元数据进入 Root 路由。同 UID shell 还可能访问控制数据库与密钥；SO_PEERCRED UID 或同 UID 可读令牌不能建立角色隔离。明确 LocalTrusted 只信任协作式本机 Agent/宿主用户，不将正常接口 gate 声称为恶意同 UID shell 的安全边界。强隔离另需 Worker OS 身份/沙箱隔离 socket、数据库、CAS、批准密钥及可信启动器绑定，未实现前保持 SEC-002 未关闭。 |
| RunService 拆分 | 外部访问确存在；只收敛已有能力可替代的编译合同/诊断访问，保留同库身份事务，不新建通用数据库连接 API 或按行数拆类。 |
| 合并所有 SQLite | 未证明一致性缺陷；临时客户端、UI 缓存、领域提交账本生命周期不同，CAS 与外部执行仍需幂等。暂不合并；后续必须先证明具体收益和恢复迁移方案。 |
| canonical JSON 统一 | 不统一既有身份字节；归档 ASCII、模型/声明投影、独立 reader 与远端 stdlib 各有合同。只归并输入域和字节都可证明相同的实现，保留冻结向量；不同用途明确说明。 |
| 公共插件 API | 运行时边界文档确实遗漏已注入上下文、adapter 协议及实际公开 schema 值类型。补精确支持范围，不复制类型、不承诺整个 schema 包稳定。 |
| hardened | 现存 MCP-only 消费者应保留；未证实所称死锁，默认科学 Operation 不兼容和 heartbeat 租约限制如实说明。立即修复已复现的负数/非规范/越界数组 JSON Patch。 |
| TCAD 独立控制面 | socket/command/stdio 均有消费者；通用控制授权/预算与领域 executable/host/runner 限制职责不同，保留。当前同 UID daemon 是故障/进程边界，不是凭据隔离。 |
| 安装器 | 两处数据插值 heredoc 在单引号路径下确有语法错误，改成引用 heredoc+参数传递，不为此全面重写安装事务。 |
| 死代码/Root 再合并 | 两个约 992 行模块为候选，核清动态加载/现行类型消费者后决定删除；不以原评审 1245 行为事实。preflight/invoke 的验证与创建语义不同，current 查询与选择也不可混为一谈。 |
| 新发现发布缺口 | 构建清单遗漏当前 API/R4 文档、测试 fixtures 和 CI 引用的资源运行器。修复明确支持的源码发布闭包，不递归打包私人历史证据。 |

实施批次全程串行：

1. **确定缺陷与信任说明**：修 JSON Patch 数组 grammar/范围与不存在成员错误，确保失败不修改文件；修安装器两处路径插值；同步安全、后端、TCAD 授权分层说明。受限源码/进程针对性验证。
2. **公共边界与可证简化**：精确公共 API 清单；有消费者依据的 RunService 窄访问；相同输入域 canonical 编码冻结向量；确认不可达旧模块后删除并迁移有效测试。无法证明等价的序列化保持原样。
3. **发布闭包**：明确当前文档与完整 hermetic tests/fixtures/runner 的来源清单；保持凭据、真实宿主数据及历史原始证据排除；检查合法负例与发布扫描的关系；从生成包受限收集并做最小代表性测试。
4. **独立复核与 Git 节点**：核对确定 bug、删除依据、身份字节不变、发布闭包和准确验证结果；不启动 F 真实模型/TCAD、不推送或部署。

强隔离的后续设计前提：可信控制进程独立 OS 身份；Worker 无法读取/写入控制 socket、数据库、CAS 和授权密钥；启动器经不可伪造通道绑定 Root/Worker/Run；验证原生 shell 越权负例、正常工具、取消/恢复和权限继承。不以额外填写 Agent 字段或可读 token 代替该边界。本批只收敛已支持的本地可信运行，未宣称修复恶意同 UID 攻击能力。


### 2026-09-26 基础设施三批实施与独立复核结果

- 第 1 批：数组 JSON Patch 拒绝负数、非规范及越界索引，嵌套访问同规则，对象空键有效；输入错误使用专门异常返回可修正诊断，失败不改文件，权限/租约错误不扩大为可重试。安装器 preview/configure 两处 heredoc 改为引用代码与参数传值，正常/空格/单引号路径 8 组验证通过。源码 91 项、进程 1 项定向通过；同 UID 信任边界及 TCAD 核心/领域授权分工、Hardened MCP-only 与心跳限制已在当前文档明确。材料 `/tmp/ic-batch1.json`。
- 第 2 批：公共插件 API 补齐现行注入上下文、adapter 协议、Operation 声明/运行时协议和选定 schema 类型，不复制类型或公开控制服务/私有凭据。三个外部私有调用改用现有 compiled_operation 或窄公开诊断方法，同库 Worker 身份事务保留。删除无生产/动态加载消费者的 `project_materializer.py`（622 行）和旧 `schema/comparison.py`（370 行）；活跃 `schema/experiment.py` 的 ComparisonContract 保留，旧未声明模块导入兼容有意退出。仅图形证据输入记录编码器归并至共用 canonical_json，在实际 string/int 原生输入域保持字节/hash；不承诺对任意 Python 对象等价，其余身份编码不改。改后 99 项源码定向通过。材料 `/tmp/infra-api-batch2/summary.json`。
- 第 3 批：公开源码发布有完整 hermetic tests/fixtures/运行器配置及递归脚本依赖；未跟踪私人历史脚本的专用测试删除，避免隐式双测试范围。当前 API 文档发布，全部私人 `docs/plans/` 排除；仅生成副本中的历史链接和文字明确指向现有 RELEASE 公开状态说明，原计划/历史不改。发布扫描未放宽，合成测试路径使用中立占位值。最终生成 503 文件（185 测试相关文件、11 脚本）；从生成目录收集源码 1410、安装 16、进程 54 项，并实际运行 14 项代表性源码与 3 项隔离 wheel 检查，另 5 项源码定向通过。最终外层耗时 25.028 秒、峰值树 RSS 240357376 字节；锁 FD、日志预算、临时环境清理均沿用监督器。材料 `/tmp/infra-release-batch3/summary.json`、`/tmp/ir-final/result.json`。
- 独立审查匹配三批合并 31 个路径哈希，未发现新增明确缺陷或阻断性覆盖缺口；检查了补丁原子性、公开调用、删除消费者、指纹输入域与发布包加载来源。报告 `/tmp/infra-final-review.json`。新增用例和定向结果不冒充一次新的完整 suite；未进行 sdist、真实 Codex/TCAD、强隔离或完整 F/Token 验收。
- 本批不实施无效同 UID token 修补、不合并数据库、不全面重写 RunService/安装器、不删除仍有消费者的 TCAD 控制面或 Hardened。SEC-002 与可信启动器/OS 权限隔离后续条件继续明确保留。本地 Git 节点保存当前修正，不推送、不改现有服务。


### 2026-09-26 追加评审收尾：上传、六项守卫与残留消费者

基线 `e3855fa`，实现和独立复核全程串行。本轮源码/测试差异 26 个路径，+218/-964；文档状态更新另计。

- 上传 commit 开始即消费当前上传状态，复制出写入内容后释放缓冲区；字节数不符、不支持的 patch 和受控写入失败均可重新 begin，失败不修改目标文件。修正 JSON Pointer 报错：`/` 表示合法空键，空指针对应的整文档替换不支持。
- 六项守卫处理：`input_scientific_claim_forbidden` 保留，真实封存作者与不同身份审查覆盖 blocked/revise 无审查拒绝、精确通过可解除、其他对象通过不可替代、明确非科学来源即使通过也拒绝、复制标签不继承资格；`independent_review_subject_invalid` 补负例并修复编译器先 set 去重导致重复声明漏检，正常显式端口与推导 review edge 合并仍有效。`input_revision_review_contract_mismatch` 和 `input_independent_review_incompatible` 经通用插件真实公开 preflight/invoke 可达，保留并验证拒绝及恢复后成功。`input_review_subject_exact_one`、`input_review_target_invalid` 无现行组件消费者，连同旧 validator 和直接测试删除。
- 修正测试退休记录：旧流程退出不代表科学来源保护退出；此前随旧夹具删除 A1 覆盖是遗漏，本轮已恢复当前路径回归。历史 transform 缺少已知作者时仍无法新建独立审查，这是基线身份入口的既有限制；没有绕过身份，也不把当前作者 Run 测试算作历史 transform 成功证据。
- 删除三个无消费者的零测试函数模块、仅被测试维持的 role_pack/schema.claim、五份旧角色资源；实际安装探针改为验证当前 ExperimentCapability 与参数提取资源。两个独立 reader 拒绝 NaN/Infinity，有效 Unicode/有限浮点的身份字节向量保持不变；不是完成全部 canonical 实现合并。
- 最终验证：`scripts/run_tests.py --lane source --per-file --output /tmp/e52-source-files`，127 文件、1426 passed、70 deselected（其他 lane），累计测试进程 427.071 秒，观察树 RSS 峰值 193609728 字节；最小 installed 检查 1 passed，5.614 秒、峰值 146243584 字节。沿用默认 2000000000 字节进程地址空间、1500000000 字节观察树 RSS 止损和每批 300 秒；没有提高限额。初始失败、夹具修正及主动中断保留，不计通过。
- 独立只读复核未发现本轮阻断性缺陷，源码差异 SHA256 `298498b0647644abacc4ebdb00de1770d8643cad0d65fdf4367f96deb57ba69a`；材料 `/tmp/e52-review-cleanup/ledger.json`、`/tmp/e52-independent-review.json`。未重跑完整 process/live，未启动真实模型、TCAD、远端任务或更新部署。SEC-002 保持未关闭。保存本地 Git 节点，历史原始证据仍不入库。


### 2026-09-26 真实衔接缺陷修复：冻结输入、输出族与决策投影

基线 `3a4cc12`。本轮根据真实图像交付失败及跨边界审查实施；保留原失败和科学证据，未重装现有临时实例。

- **输入身份贯穿执行。** Transform 直接读取已冻结 ArtifactRef；Agent 别名以端口与精确引用配对。`OperationOrigins` 从原 Root 移出共享来源解析，预检与 Run 事务冻结复用声明派生规则，并核对精确引用、原始名称绑定、实例和来源。隐藏的同名不同对象、兄弟输出、集合与组合来源可正确消费；没有新增 Agent 表单或审查 gate。
- **输出族属于具体调用。** 新 Transform 保存调用名称和实例，与请求指纹分离；旧数据按精确持久名称布局恢复，继续核对父引用与生产合同，不按内容相同合并或继承资格。同输入不同名称的调用各自可继续消费，同名相同请求幂等，不同请求冲突。
- **独立复核补齐名称冲突。** 原执行入口对次级输出仅比较内容，可能复用无关原文或在报错前留下主输出。现改为写入前检查全族占用名称、binding 指纹、类型/schema、父引用、生产标签与内容；两个公开 `artifact_ingest_text` → `operation_invoke` 负例证明相同/不同字节冲突都不会新增绑定。此改动解决预存名称冲突，不声称跨库存储失败具备新的原子回滚。
- **输出投影跟随 schema。** 三个 EvidenceAudit 默认读取 checks，分析默认含真实 verdict/claim_allowed/next_action；实验、审查和参数包展示使用实际字段。Run 新增可空的决策字段快照，历史读按冻结声明；无快照且无匹配合同则显式返回不可用原因和有界导航，不把新合同套到旧对象。旧只读归档不写迁移，恢复路径包含新字段。UI 补齐 Intake open_questions 和大于 64KiB 参数包的分页来源指针，原 4MiB 读取限制不变。
- **验证。** 输入定向 91 项、输出新增 17 项、归档定向 14 项，以及冲突红/绿回归先行；最终完整源码 `scripts/run_tests.py --lane source --per-file --output /tmp/e2e-frozen-full-source`：1453 passed、70 deselected，131 文件累计测试进程 454.935 秒，树 RSS 峰值 193413120 字节。最小 installed 检查 1 passed，5.039 秒，峰值 147644416 字节，验证四包安装环境中的新模块、三个审查声明及图像依赖。初次安装探针把字段名 checks 误写成 /checks，修正测试后通过，原失败保留。没有上调资源限制。
- **独立审查与边界。** `/tmp/e2e-frozen-independent-review.json` 与 `/tmp/e2e-frozen-independent-rereview.json`：阻断项 FROZEN-REVIEW-01 已关闭；历史 UI 观察 FROZEN-REVIEW-N01 保留。源码实现与测试明细在 `/tmp/e2e-input-fix.json`、`/tmp/e2e-output-fix.json`；最终结果在 `/tmp/e2e-frozen-full-source/result.json`、`/tmp/e2e-frozen-installed-final/result.json`。未重跑完整 process、浏览器、真实模型/TCAD 或更新临时科学实例；不将源码 fixture 成功当成真实 F 闭环，也不将字段减少当成 Token 收益。
- 本地 Git 保存源码、必要回归及本计划/索引；不推送。未跟踪的历史 evidence 原始资料和临时运行凭据不入提交。


### 2026-09-26 `4206621` 安装后真实图像链及填表负担观测

- 四个当前 wheel 离线构建、独立 venv 安装并切换原临时入口；旧 venv 与数据快照保留，用户在管理页重新选择已有实例。安装监督器耗时 5.612 秒、峰值树 RSS 126205952 字节，没有资源止损。该数字只覆盖受监督安装，不代表原生 Codex 进程总内存峰值。
- 旧作者/审查被正确标为历史合同，缺少决策字段快照时返回有界导航；旧交付重试返回 input_origin_unavailable，未改写摘要、原件或资格。随后使用同一原图/说明重新运行 `synthetic-calibration/extract-4206621`、`audit-4206621`，完成 `bundle-4206621` 和 `analysis-4206621`。输出为 501 点的合成图像工程证据，禁止扩展为生成器原始值或物理实验结论。
- Root 审查调用仅选择 Intake 与用户说明，转换仅选择 Intake 与审查。控制层自动恢复原图和整套派生材料；bundle 包含 27343 字节曲线对象及 471 字节归一化审计。相同请求重试结果完全一致；第二个命名输出族创建后，原 bundle 仍可通过后续消费预检。默认作者/审查/分析响应直接返回实际字段，未重现空字段与额外导航问题。
- 分析负责人通过 `worker_helper` prepare 派发 fresh-context 原生助手，等待后 release 并自行封存分析。助手实际执行 9 次原生 exec_command，非单次文本 LLM；其 14 次请求累计 input 310756、cached input 291200、output 3273。负责人结果与检查范围一致，但封存 analysis_method 未明确注明助手结果的采用/拒绝，所以只证明真实委派、工具访问和完成/释放路径，采用可追踪性仍不充分。
- **仍有填写负担。** 作者初稿 7462 字节、117 个标量值；审查 5129 字节/83 个；分析 3905 字节/35 个。这是实际草稿统计，包含数组元素、科学内容和自愿填写，不能等同于强制字段数。作者有三次提交拒绝：参数缺值、带单位无值、推断缺理由；修复后又依次发现参数缺单位及缺理由。figure 专用语义说明没有完整复用 Intake 条件规则，这些条件首次明确出现在拒绝诊断中。审查与分析首次实际提交成功。
- **Token 仅为观察。** Root 从本轮“继续执行测试”开始至 `2026-09-26T13:53:03Z` 采样，共 62 个去重 response usage：input 7707010、cached input 7524352、output 15104，单请求 input 峰值 146747。其中包括安装、排障和字段审计；长期历史与缓存占主要部分，不是纯科研 Root 或干净基线，也不包含采样后的请求/最终答复。作者 43 请求（1297911/1235328/8144），审查 29（728857/693888/5374），分析 38（1030424/997632/5722），括号依次为 input/cached input/output。按逐响应计数，不累加累计用量；未证明 token 成本下降。
- 本地临时证据位于当前临时安装的 `current-session/acceptance-4206621/`：`scientific-results.json` 保存真实封存读取与调用结果，`usage-and-fields.json` 保存逐请求 usage、字段路径和拒绝诊断，无原始凭据。只更新本计划与入口，不重复全套源码测试，不把本图像子链冒充完整 F、真实 TCAD 或浏览器验收。
