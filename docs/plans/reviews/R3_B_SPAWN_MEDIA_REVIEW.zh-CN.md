# R3-B Spawn 与媒体能力独立跨边界复审

审查日期：2026-08-28  
审查基线：`baseline/8765-codex@404aeb1` 叠加已通过的 R0—R3-A 与当前 R3-B 工作树  
审查者：未参与本轮 R3-B 实现的独立审查者  
审查方式：只读检查源码、安装态编译结果、测试和原始 Codex 会话 JSONL；未修改实现或既有审查文件

## 一、结论

**打回，不得进入 R3-C。**

当前实现的大部分结构目标已经成立：默认派发仍是
`task_prepare_dispatch → spawn_agent`；15 个通用科学 Operation 来自唯一
`general_science` 插件入口和同一个 `CompiledCatalog`；Operation 专属 Worker MCP
命名空间消除了父 Root 与子 Worker 的 `scidiscovery` 同名冲突；文本、PDF 和图像都确实由
真实子智能体读取，并最终形成严格 `ScientificIntake`、精确来源绑定和
validate/finalize 后的 Root `completed` 状态。

但当前所谓“图像通过证据”仍不能支持 R3-B 的最小上下文结论。原始会话显示，图像子智能体
在第一次输出校验失败后，违背已编译提示中的 task-local-only 约束，搜索整个共享仓库并读取
多个框架源码和角色文件后才修正输出。资格脚本没有检查原生命令的路径集合，因此把这次真实
越界运行报告成 21 项全通过。与此同时，`science.evidence.extract.v1` 的编译 prompt 仍直接
拼接整份 legacy `evidence_extractor` 提示，把本 Operation 明确不负责的参数提取、图证据包、
修订模式和未授予工具同时暴露给普通文本/PDF/图像提取任务。前者是实证误判，后者是复杂度与
上下文从控制面转移到 Worker prompt；两者均与本轮“最小上下文、轻控制面、快速闭环”的完成门
冲突。

这些阻断均可在 R3-B 内局部修复，不需要增加新实体、状态机、注册表或 Operation。

## 二、独立检查与复现结果

| 检查 | 结果 |
| --- | --- |
| R3-B 专项回归 | `31 passed in 22.49s` |
| 完整 `pytest -q` | `124 passed in 40.92s` |
| `python -m compileall -q src tests/operations` | 通过 |
| `git diff --check` | 通过 |
| Operation 核心预算 | `319 / 449 / 428 = 1196`，满足分项 `320 / 450 / 430` 与总计 1200 上限 |
| 安装态通用科学 Operation | 15 个，均从 `general_science` 编译 |
| 三份当前 qualification report | 均声明 `pass`、21 项全真 |
| 三份报告所列会话/事件摘要 | 独立重算均与文件一致 |
| 原始图像子会话的任务外源码读取 | 存在；当前 qualification 未检测 |

测试全绿证明当前已写合同内部自洽，但没有覆盖子智能体原生读取路径的边界，不能抵消下面的
原始会话反证。

## 三、阻断项

### B1：图像真实运行违反 task-local-only，资格脚本却判为通过

严重性：阻断 R3-B 完成证据和最小上下文约束；不否定最终科学对象本身有效。

编译给 Worker 的共同提示明确要求：只能读取 `assignment.json` 声明的精确 task-local 路径，
不得从共享 Worker workspace 根搜索（`roles/common.md:17-21`）。图像任务物化出的只读集合只有
`assignment.json`、`schema/output.schema.json` 和 `inputs/source_material.png`；后续允许读取的
也只应包括当前输出文件以及受控工具返回的精确 task-local 路径。

原始子会话
`.scidiscovery-state/r3-science-spawn-image-run2/codex-session-evidence/2026/08/28/`
`rollout-2026-08-28T17-36-57-01a047ba-c589-7a83-9e42-aea12b0e5c42.jsonl`
显示：

- 第 42—43 行确实以同一个
  `call_bmMfR7GaEkLSAv76XQK1wRwP` 完成 `view_image → ImageView`，原生图像能力本身成立；
- 第 90—91 行第一次 `worker_validate_output_file` 只返回根路径上的通用错误
  `operation output validator rejected the payload`；
- 第 99 行随后对整个仓库运行 `rg`；第 109—110 行读取
  `research_cycle.py` 与 `roles/evidence_extractor.md`；第 120、122、131、132、142、143、153、
  161、169、183 行继续读取或导入框架 schema、validator 和
  `general_science_plugin.py`；
- 第 191—198 行才完成第二次有效校验和 finalize。

这些文件既不在 assignment 的只读路径中，也不是受控工具返回的 task-local 路径。当前
`inherited_prototype` 按计划只承诺“原生能力可用且提示行为约束被遵守”，并不承诺 OS 级硬
隔离；因此这次运行的关键问题不是“沙箱没有物理阻断”，而是**约定要审计的行为约束实际没有
被遵守，报告却未发现**。

资格脚本的 checks 只确认存在一次成功原生命令、无 Root/网络调用、精确 Worker 工具以及终态，
没有检查原生命令访问的路径集合（`tests/operations/live_r3_science_agent_qualification.py:513-545`）。
所以 `qualification-report.json` 的 21 项全真不足以证明最小上下文闭合。

最小修复：

1. 在现有 qualification 解析器中加入路径边界检查：逐个解析子会话原生读命令和
   `view_image` 路径，只允许 assignment 声明路径、当前 `output/result.json`、Schema 路径及
   受控 Worker 工具返回的精确本地路径；仓库源码、共享 state 根、兄弟工作区和项目根搜索均应
   使报告失败。
2. 保留 `inherited_prototype` 的诚实定位，不把“本次没调用网络”升级成网络硬隔离结论，也不在
   本轮新增复杂 OS 沙箱。
3. 在修复 B2 和可操作校验诊断后，重新生成至少一份图像真实运行；原始 JSONL 必须无任务外读，
   且仍满足同 call-id `view_image → ImageView`、严格对象、来源绑定、validate/finalize 和 Root
   completed。

### B2：Operation 专属权限已经收窄，但 prompt 仍混入互斥 legacy 工作模式

严重性：阻断最小上下文与复杂度下降完成门。

`general_science_plugin.py:470-489` 直接用整份 legacy 角色 prompt 构造多个不同 Operation：

- 普通 `evidence_prompt` 是 `EXACT_TOOL_PREAMBLE + roles/evidence_extractor.md`；
- `figure_prompt` 又在该完整 prompt 后追加图证据覆盖说明；
- `revision_prompt` 又在同一完整 prompt 后追加“只返回 StructuredRevision”；
- `object_review_prompt` 先包含完整 CriticReview 指令，再在末尾要求改为 ScientificReview。

独立读取安装态编译结果：普通 `science.evidence.extract.v1` 的 prompt 为 19,606 字符，同时包含
`device-parameter-evidence`、`$scientific-paper-evidence` 和 `StructuredRevision`；图提取和 intake
修订分别为 19,810 与 19,796 字符，也继承全部互斥说明；object review 为 11,814 字符，先要求
CriticReview 再覆盖为 ScientificReview。普通提取 Operation 的描述明示不负责参数专用和定量
图提取，其 Worker 工具与网络合同也没有授予角色正文所述的全部 web/figure 工具。

这不是新的注册权威，但会让模型在一个 Operation 内判断“哪些 legacy 段落其实不适用”，使
OperationSpec 已经消除的 profile/模式复杂度重新出现在 prompt。图像运行中模型在通用校验错误
后查阅源码，也说明目前模型可见合同没有形成独立、自足的最短修复路径。TaskService 把底层
validator 异常统一抹成根路径通用错误（`tasks.py:1591-1599`），进一步放大了这种问题。

最小修复：

1. 仍保留 15 个 Operation 和一个 `general_science` 插件入口，但在插件内拆出窄 prompt 资源：
   普通 intake、图证据提取、bounded revision、object review 各自只含其真实输入、输出和工具
   说明；不得通过“完整旧角色 prompt + 末尾覆盖”组合。
2. 不增加 prompt/profile 注册表；这些 prompt 仍作为同一 `PluginDefinition` 的 resource
   component，并由相同 catalog 编译。
3. 让 Worker 从投影 Schema/语义合同或受控 validation error 得到足够具体、有限的规则/字段
   诊断，能够在不读实现源码的情况下修复。无需暴露 traceback、服务对象或 validator 实现。
4. 增加安装态断言：普通提取 prompt 不含参数、图证据、revision 专用指令；revision 和 object
   review 不先要求生成另一种完整 payload。

## 四、已通过的跨边界

### 4.1 默认派发没有接回独立 Codex 进程

`RootToolFacade.task_prepare_dispatch()` 只调用 TaskService 的 `prepare_dispatch` 并返回由
`task.operation_authority.agent_type` 派生的角色
（`mcp_root.py:1993-2002`）。Root/runtime/deploy 默认路径没有构造或调用
`CodexTaskDispatcher`；该类仍是保留的非默认后续加固代码。三份当前正向父会话都由父 Codex
调用 `spawn_agent` 和等待工具，父会话没有替子 Worker 调用 Root 或 Worker 科学工具。

文本 run4 显式使用 `fork_turns="none"`；PDF run2 的当时工具 schema 把省略视为不继承，图像
run2 使用旧字段 `fork_context=false`。我独立读取三个 child session 的首部，均只收到环境合同和
“完成已经排队的工作分配。”，没有继承父 qualification 提示或科学内容。因此语义上满足无父
上下文继承；后续当前版本证据应统一使用 `fork_turns="none"` 并由检测器检查子会话实际上下文，
不把字段名称本身当科学边界。

### 4.2 15 个 Operation 来自一个插件与一个 catalog，无领域 allowlist

`pyproject.toml:26-28` 只使用 `scidiscovery.plugins` 入口组注册 `builtin` 与
`general_science`。`general_science_plugin.py:1635-1642` 的一个 `PluginDefinition` 同时登记 71 个
私有窄组件和 15 个 Operation。安装态编译独立得到恰好 15 个 `science.*` Operation。核心
spec/catalog/invoke、Root、TaskService、UI、通用 scheduler 中未发现这些 operation id 或
`general_science` 的逐项 allowlist/分支。

六份 `roles/*.md` 无 frontmatter，首行即科学提示正文。`platforms/roles.py:30-91` 的
`_LEGACY_CORE_ROLE_METADATA` 明确只服务旧 task_create 路径，Operation 路径不读取；按当前计划
留到 R3-D 删除可接受，但 R3-D 必须兑现，不能继续扩展该映射。

### 4.3 Operation 专属 Worker MCP 命名空间正确，未形成第二注册表

`platforms/codex.py:362-416` 为每个 Operation Agent profile 只选择
`_operation_worker_server_name(compiled)`；`platforms/codex.py:438-463` 用同一个 compiled
operation 生成父会话可继承的同名 Worker server。名称由 Operation Agent stem 与编译摘要前缀
确定，而精确工具仍由 `operation_worker_tools(compiled)` 投影。生成 profile、父继承 server、
安装探测和测试都枚举同一个 `CompiledCatalog`，没有新增可变映射或独立发现入口。

真实子会话实际只调用
`mcp__scid_worker_science_evidence_extract_v1_638b2cf844cd` 中的注册 Worker 工具；旧 text run2
因子 Agent 获得父 `mcp__scidiscovery` 而错误调用 `instance_current` 的冲突，在当前三份正向运行
中没有复现。该修复成立。

### 4.4 媒体能力复用 Codex 原生读取，科学对象与封存闭合

| 证据 | 独立结论 |
| --- | --- |
| text run4 | 真实子角色正确；原生 shell 以退出码 0 读取 assignment、Schema 与唯一 TXT；无子 Root/网络调用；严格 `ScientificIntake` 只绑定 `source_material`；validate/finalize 与 Root completed。 |
| PDF run2 | 真实子角色正确；`pdftotext` 退出码 0，并调用精确注册的 `worker_extract_pdf_text(source_material, 1..1)`；随后读取冻结 excerpt；首轮来源 key 错误被拒绝，修正为 `source_material` 后 validate/finalize 与 Root completed。 |
| image run2 | 同 call-id `view_image → ImageView`、严格对象、精确来源、最终 validate/finalize 与 Root completed 均成立；但 B1 的任务外读取使其不能作为最小上下文通过证据。 |

普通 Operation 没有 `worker_read_input` 或 `worker_view_image`；文本/PDF/图像分别复用原生
shell/PDF/image 能力，`worker_extract_pdf_text` 只负责冻结引用页段。没有重复造媒体读取工具。
三份最终 CAS 输出的内容摘要与任务记录一致，均可用严格 `ScientificIntake` 解析；事实项引用
`source_material`，推断/假设给出 rationale。科学内容由子 Worker 生成，父会话零 Worker 代写。

### 4.5 失败历史被如实保留

- text run2 的 report 为 fail，原始 child JSONL 确有 `mcp__scidiscovery.instance_current`，任务停在
  dispatched；这是旧同名 namespace 冲突。
- PDF run1 的 report 为 fail，原始父会话没有 spawn，错误转向实例绑定，任务停在 dispatched。
- image run1 的 report 为 fail；任务与科学对象虽完成，旧检测器未正确识别真实
  `view_image → ImageView` 配对。run2 修正了该检测，但又暴露 B1 所述未检测边界。

这些失败没有被覆盖或删除，历史表述基本诚实。

### 4.6 `inherited_prototype` 的承诺边界表述准确，但当前正向证据没有完全遵守它

当前文档将其限定为：继承父会话已有基础 sandbox，使调试原生工具可用；OperationSpec 的更细
工具/路径禁止在 R3 首版是提示行为约束，不是网络、原生写入或任务外读取的硬隔离，也不得用于
真实副作用。这一定位与代码和 R3 快速原型决策一致，不能把正向运行中的“没有观察到网络调用”
写成平台硬拒绝。

因此，本报告不因缺少第二层 bubblewrap 单独打回；打回原因是 B1 显示即使按“行为约束”这一
较窄承诺，实际图像运行也未遵守且检测器误判。R3-C 在接入 TCAD/外部副作用前仍必须另设更强
边界，不能把本轮原型证明外推到生产隔离。

## 五、15 个 Operation 与复杂度判断

15 个 Operation 的数量本身可辩护，不建议合并：

- foundation audit、intake audit、portfolio-bound hypothesis audit 消费对象和覆盖规则不同；
- figure extraction/audit 具有独立集合、bundle validator 与图像能力；
- curve-error diagnosis 具有额外 CurveBundle 与分析工具；
- 三种 bounded revision 的基对象 Schema 和允许路径不同；
- object review 与 hypothesis critic 的 payload/目标不同。

合并这些能力会引入联合端口、联合工具权限或运行时 mode 分支，反而重新制造 profile。真正的
复杂度问题是 B2 的 prompt 复用方式，而不是 15 这个数字。

核心 `spec/catalog/invoke` 为 1196 行，仍在本阶段冻结预算内；三者没有变成科学状态机。
`general_science_plugin.py` 已达 1645 行、71 个组件，当前主要由声明、Schema、validator 和 prompt
资源构成，并未新增控制生命周期，但 prompt 的互斥内容已造成真实模型负担。应先做 B2 的窄
资源切分，不在 R3-B 发起宏大模块重构。总体相对 8765 的净复杂度下降仍要等 R3-D 删除 legacy
消费者后再判定。

## 六、33 项约束族不退化判断

仓库仍没有逐项编号的“33/33”可执行脚本，本报告不伪称运行了该脚本，而按行为约束族审查。

| 约束族 | 判断 | 说明 |
| --- | --- | --- |
| 单一插件入口、启动期编译、不可变 catalog | 通过 | 15 个 Operation 与 71 个组件同源编译，无第二注册生命周期 |
| OperationSpec 是声明闭包而非巨型执行类 | 通过 | 工具、codec、validator、资源仍为窄组件 |
| 科学内容归 Worker，控制面不做科学判断 | 通过 | 三份最终对象均由子 Worker 生成；控制只做合法性、封存和终态 |
| Agent 间文件交接、父零代写 | 通过 | 父只 spawn/wait，科学结果经 Worker 文件生命周期交付 |
| 精确输入、任务内别名和来源闭合 | 局部不通过 | 最终对象来源闭合，但 image run2 实际读取了未声明仓库源码 |
| Worker 最小上下文 | 不通过 | B1 是直接反证，B2 又把互斥 legacy 模式放入普通 Operation prompt |
| Worker MCP 工具最小授权、服务端失败关闭 | 通过 | 专属 namespace 和精确工具成立；未授权 Worker/Root 调用在当前正向 child 中未出现 |
| 原生能力边界诚实 | 局部通过 | 文档诚实说明是提示约束而非硬隔离；图像 child 未遵守路径约束且检测器漏检 |
| 网络默认无 Worker/web 能力 | 通过于声明与观察 | compiled authority 为 none，child 无 web/Root 调用；不外推为 shell 网络硬隔离 |
| 不可变 Artifact/CAS、validate/finalize、Root 终态 | 通过 | 三份最终输出均闭合；失败历史保留 |
| 人工审批、外部执行和副作用边界 | 未由 R3-B 改动 | 本轮均为无外部副作用架构验收，不授权真实执行 |
| reviewer、确定性变换不替代科学判断 | 通过于当前差异 | 未发现新排序、资格或科学结论特判 |
| 轻控制面、无新状态机/注册表 | 通过 | MCP namespace 是 catalog 投影，不是新权威 |
| 复杂度真实下降 | 本阶段部分成立 | 核心预算通过；B2 是向 prompt 转移的残余复杂度；全局净下降待 R3-D |
| 真实入口负例与证据不误判 | 不通过 | 124 项测试未覆盖原生路径集合，image run2 被误判为全通过 |

因此不能给出“33 项约束族不退化”的整体结论。失败范围集中且可局部修复：Worker 最小上下文
与实证检测，而非 Operation 核心、注册方式或科学对象设计。

## 七、复审放行条件

下一轮无需重做 R3-B，只需同时满足：

1. 普通 extraction、figure extraction、revision、object review 的编译 prompt 均为独立窄合同，
   不含其他 Operation 的互斥模式、输出类型或未授予工具说明。
2. validation rejection 给出足够的受控字段/规则诊断，或 Worker 可见同源语义合同足以在不读取
   框架源码的情况下修正输出。
3. qualification 结构化解析子 Agent 的每个原生读路径；任务外仓库、共享 state 根和兄弟路径
   使检查失败。增加至少一个合成越界事件负例，证明检测器会失败，而非只检查成功会话。
4. 重新生成文本、PDF、图像真实 spawn 证据；三者均使用不继承父上下文的调用语义，父零
   Root/Worker 代写，子零 Root/网络，所有原生读取均在声明/受控返回路径内；PDF 同时保留
   `pdftotext` 与冻结 excerpt，图像保留同 call-id `view_image → ImageView`。
5. 三份新运行仍产生严格科学对象、精确 `source_material`、受控写入、有效 validate/finalize 和
   Root completed；旧失败记录继续保留。
6. 专项、全仓、compileall、diff-check 与核心行数预算继续通过。

在上述条件由独立复审确认前，**不得进入 R3-C**。

## 八、最终裁定

**打回，不得进入 R3-C。**
