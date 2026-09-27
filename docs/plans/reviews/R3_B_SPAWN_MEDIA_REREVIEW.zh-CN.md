# R3-B Spawn 与媒体能力独立复审（二次）

审查日期：2026-08-28  
审查基线：`baseline/8765-codex@404aeb1` 叠加已通过的 R0—R3-A 与当前 R3-B 工作树  
前次审查：`R3_B_SPAWN_MEDIA_REVIEW.zh-CN.md`  
审查者：未参与本轮修复的独立审查者  
审查方式：只读检查当前源码、安装态编译结果、测试、三份报告及其全部父子 Codex JSONL；未修改实现和既有审查文件

## 一、结论

**打回，不得进入 R3-C。**

前次两类实现缺陷已基本关闭：普通提取、图证据、修订和对象审查现在使用独立窄 prompt；
TaskService 会把校验异常投影为有限的字段/指针/原因/期望/修复提示；资格检测也能从真实
`worker_materialize_assignment` 完成事件获得任务根，并拒绝仓库绝对路径、项目根工作目录、
框架导入和父上下文继承。PDF run5 与 image run3 的原始会话完整满足当前完成门。

但 text run6 仍被错误报告为通过。其子 Agent 在调用正确 Worker 服务前，实际探测并调用了
13 个其他 Operation 的 `worker_claim_task`。这些调用虽被服务端拒绝，却直接违反当前设计中
“唯一授权 Worker MCP 服务、不得探测其他可见服务”的原型行为约束。现有 23 项检测只把所有
`worker_*` 都视为允许，没有校验 MCP namespace 必须等于所选 compiled operation 的唯一服务；
因此仍存在真实证据误判。并且 text run6 的生成 profile 早于当前“提示中写出精确服务名”的
修复，其 report 仍为 schema version 2，不能证明当前最终配置。

只剩这一项局部阻断。修复不需要新增实体、状态机、注册表或控制面流程。

## 二、独立检查结果

| 检查 | 结果 |
| --- | --- |
| 修复专项 | `36 passed in 3.49s` |
| 完整 `pytest -q` | `130 passed in 41.11s` |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| Operation 核心预算 | `319 / 449 / 428 = 1196`，满足分项与总计上限 |
| 安装态 `science.*` Operation | 15 个，仍从一个 `general_science` 插件编译 |
| 普通/图证据/修订/对象审查 prompt | `2235 / 2030 / 1826 / 1769` 字符，互斥模式已移除 |
| PDF run5 | 23 项报告通过，原始会话复核通过 |
| image run3 | 23 项报告通过，原始会话复核通过 |
| text run6 | 23 项报告通过，但原始会话发现 13 个未授权 Worker namespace 调用；报告误判 |

三份报告列出的 `codex-events.jsonl`、最终消息与全部 session JSONL 的 SHA-256 均已独立重算，
与报告相符。问题不是文件被替换，而是检测口径缺失。

## 三、唯一阻断项

### B1：text run6 探测其他 13 个 Worker 服务，资格检测没有失败

严重性：阻断真实完成证据与 Worker 最小授权行为约束。

当前源码已明确：唯一授权服务由同一个 `CompiledOperation` 和摘要确定；子 Agent 必须从该服务
领取任务，其他可见服务不得探测（`src/scidiscovery/operations/tooling.py:105-116`）。这是一条
R3 首版可审计的提示行为约束，不是 OS 级硬隔离，但真实验收仍必须证明 Agent 遵守。

原始子会话：

`.scidiscovery-state/r3-science-spawn-text-run6/codex-session-evidence/2026/08/28/`
`rollout-2026-08-28T18-06-46-01a047d6-0eed-7180-9884-9f2bb5793753.jsonl`

逐事件解析得到：

- 第 30、38、46—57 行，子 Agent 分别调用 evidence audit、intake audit、hypothesis propose、
  critic、hypothesis audit、experiment design、普通/曲线 diagnosis、figure extraction、intake/
  experiment revision、object review 与 builtin 等其他 namespace 的 `worker_claim_task`；
- 第 52 行才同时调用正确服务
  `mcp__scid_worker_science_evidence_extract_v1_a61600b59e20`；
- 第 58—81 行显示其他服务调用均为 `failed`，正确服务为 `completed`；失败并不把未授权探测变成
  合法行为；
- 正确领取后，任务内原生读取、输出写入、validate/finalize 和最终科学对象本身均有效。

text run6 的 developer prompt 仍使用旧表述“from this Operation's Worker MCP namespace”，没有
当前源码已经生成的精确服务名与“Every other visible Worker MCP server is forbidden”正文；其
`qualification-report.json` 也是 schema version 2。PDF run5 和 image run3 的 developer prompt
则已包含精确服务名。这说明 text run6 不是当前最终 profile 的同版本实证。

资格脚本 `tests/operations/live_r3_science_agent_qualification.py:664-701` 的 23 个 checks 没有
“仅使用 exact Worker server”检查。`_child_root_and_network_calls_absent()` 只拒绝 Root、web 和
非 `worker_*` 工具；任何其他 Operation namespace 只要工具名仍以 `worker_` 开头就会被接受。
现有负例覆盖任务外路径、项目根、框架导入和父上下文，却没有错误 Worker namespace 负例。

最小修复与复审条件：

1. 在资格解析器中从同一 compiled operation 得到期望 server name；检查子会话所有
   `function_call.namespace` 与 `item_completed.server`。任何其他 `scid_worker_*` 调用都必须使
   报告失败，即使调用结果为 failed。
2. 增加一个合成负例：先调用错误 Worker namespace、再调用正确 namespace，检测结果仍必须为
   false；不能只验证最终成功服务。
3. 用当前精确服务名 prompt 重新生成文本真实运行，报告使用当前 schema version；原始 child
   JSONL 只能调用一个 Worker namespace，并继续满足 `fork_turns="none"`、任务内原生读取、
   strict ScientificIntake、精确 `source_material`、受控写入、validate/finalize 与 Root
   `completed`。
4. PDF run5 和 image run3 已满足 exact namespace 口径；若实现只改资格解析器而未改变 profile、
   catalog 或媒体合同，可保留它们，不要求为仪式重跑。

## 四、前次打回项复核

### 4.1 独立窄 prompt：通过

`general_science_plugin.py:340-601` 现在定义共同的最小工具前言以及九个独立科学 prompt；资源
组合不再加载完整 `roles/evidence_extractor.md` 后在末尾覆盖。

安装态独立检查：

- 普通 `science.evidence.extract.v1` prompt 为 2235 字符，包含 `ScientificIntake`，不含
  `device-parameter-evidence`、`$scientific-paper-evidence`、`StructuredRevision` 或
  `CriticReview`；
- 图证据 prompt 只描述可见系列、标定、identity、bundle 与图像检查，不含参数/修订/critic
  模式；
- revision prompt 只要求 `StructuredRevision` 与 allowed paths，不先要求重写 ScientificIntake；
- object review prompt 只要求 `ScientificReview`，不先要求 `CriticReview`。

`tests/operations/test_general_science_plugin.py:205-250` 对长度、必需内容和互斥内容有安装态回归。
本项没有新增 profile 注册表；这些仍是同一 `PluginDefinition` 中由同一 catalog 编译的资源
component。

### 4.2 Worker 可见 validator 诊断：通过

TaskService 对 output validator 与 context validator 使用同一个 `_validation_details()` 投影，
最多返回 64 个叶错误，并在摘要中最多显示 8 个；每项包含：

- `path` 与 `json_pointer`；
- `message` 与稳定 `reason_code`；
- `expected_contract`；
- 局部 `fix_hint`。

Worker 的 `worker_validate_output_file` 直接返回这些有限字段
（`mcp_worker.py:898-914`）。专项通过完整 Worker 文件生命周期提交空 payload，获得具体缺失
字段而不是根级“validator rejected”占位文本
（`test_general_science_plugin.py:252-328`）。我另以一个 objective 不一致的有效对象触发
cross-field validator，得到“problem frame and scientific foundation objectives differ”和局部修复
提示；结合输出 Schema 足以修复，不需要读实现源码。

诊断来自 payload/schema validator，不包含 Artifact、task、approval、execution、token、session
或控制服务对象；未见控制身份泄漏。generic cross-field 错误仍可能位于 `$`，但其消息明确指出
冲突双方，属于可用诊断而不是本轮阻断。

### 4.3 task root、路径与父上下文检测：通过

资格脚本从真实 `worker_materialize_assignment` 的 `item_completed.result.structuredContent`
读取唯一 `workspace_path`，没有从项目根、任务编号或报告摘要猜测
（`live_r3_science_agent_qualification.py:193-211`）。

`_native_calls_are_task_local()` 要求每个原生命令 workdir 精确等于任务根，绝对路径和
`view_image` 路径均位于该根内，并拒绝 `..`、框架导入与原生写工具。相应测试覆盖：

- 合法任务根读取；
- 仓库源码绝对路径；
- 项目根 workdir；
- `import scidiscovery`；
- materialize 完成事件恢复任务根。

`_spawn_has_no_parent_context()` 同时检查显式 `fork_turns="none"`/旧等价 false 字段和 child user
消息不含父 qualification marker，并有继承父提示负例。三份当前父会话实际都显式使用
`fork_turns="none"`，child 只收到“完成已经排队的工作分配。”。

这些是原型行为证据，不是 shell、网络或路径的生产级硬隔离；文档仍如实保留这一边界。

## 五、PDF run5 与 image run3 原始证据复核

### 5.1 PDF run5：通过

- 父会话只调用一次 `spawn_agent` 和一次 wait，精确 agent type，`fork_turns="none"`，无 Root/
  Worker 代写；
- child 只调用
  `mcp__scid_worker_science_evidence_extract_v1_a61600b59e20`，没有其他 Worker、Root 或 web；
- materialize 完成事件返回唯一任务根，全部原生命令 workdir 精确为该根；
- `pdftotext inputs/source_material.pdf -` 成功；随后精确调用
  `worker_extract_pdf_text(source_material, 1..1, max_chars=4000)` 并读取返回的任务内 excerpt；
- 输出经 Worker 文件 begin/chunk/commit、valid=true、finalize=completed；Root task 状态 completed；
- CAS 摘要与任务 output ref 相同，严格 `ScientificIntake` 解析成功，唯一来源为
  `source_material`，问题框架和科学基础 objective 相同。

### 5.2 image run3：通过

- 父调用与 child 上下文边界同 PDF；child 只调用 exact Worker namespace；
- materialize 后全部 shell workdir 为精确任务根，无仓库/项目根/框架源码读取；
- `view_image` function call 与 `ImageView` 完成事件共享
  `call_l3CBP1d4zGk4ooRRctOPnYol`，路径为任务内 `inputs/source_material.png`；
- 输出经受控写入、valid=true、finalize=completed，Root completed；
- CAS 严格解析成功，唯一来源为 `source_material`，观察事实限定于橙色面板，没有外推。

两份证据没有重复制造 `worker_read_input`/`worker_view_image`：PDF 普通阅读用原生
`pdftotext`，受控工具只冻结引用页；图像用 Codex 原生 `view_image`。

## 六、默认路径、注册与复杂度

- 默认仍为 `Root.task_prepare_dispatch()` 返回 compiled agent type，由父 Codex
  `spawn_agent`；Root/runtime/deploy 没有接入 `CodexTaskDispatcher`。独立进程类仍是可选后续加固
  代码。
- 15 个通用科学 Operation 仍来自 `pyproject.toml` 的唯一 `scidiscovery.plugins` 入口组、一个
  `general_science.PluginDefinition` 和一个 `CompiledCatalog`；Root、TaskService、UI 与通用
  scheduler 中未出现逐 Operation allowlist。
- Operation 专属 MCP 名称由 `operation_worker_server_name(compiled)` 投影，同一函数被 profile、
  父继承配置和安装探测复用，不是第二注册表。B1 是真实 Agent/检测行为缺口，不是注册权威
  重复。
- 15 个 Operation 的科学职责仍可辩护：普通/图证据、foundation/intake/portfolio audit、
  critic/object review、三种 revision 与曲线误差 diagnosis 具有不同输入、输出、工具或集合权限；
  合并会重新引入 mode 分支和联合授权。
- 核心 1196 行满足预算。`general_science_plugin.py` 因独立窄 prompt 增至 1759 行，但新增内容是
  相互独立的模型可见资源，不是控制状态机；该局部增长换取了真实上下文删除，可接受。全局净
  下降仍由 R3-D 删除 legacy 消费者后验收。

## 七、33 项约束族不退化判断

仓库仍没有逐项编号的“33/33”执行脚本；以下按行为约束族判断，不伪称脚本全通过。

| 约束族 | 判断 | 说明 |
| --- | --- | --- |
| 单一注册、启动期编译、catalog 唯一权威 | 通过 | 无新入口、注册表或运行时编译 |
| OperationSpec 是行为声明闭包 | 通过 | prompt、codec、validator、工具仍由窄组件组合 |
| 科学内容归子 Worker | 通过 | 三份科学对象均由 child 生成，父零代写 |
| 文件交接、CAS、validate/finalize、终态 | 通过 | 三份输出本身均闭合且严格可解析 |
| 精确输入、task-local 来源与路径 | 通过于新路径证据 | 三份原生读均在 materialized root；旧 image run2 被保留为失败反证 |
| 父上下文最小化 | 通过 | 三份均显式无 fork，child 无父 qualification 内容 |
| 唯一 Worker MCP 服务 | **不通过** | text run6 探测 13 个其他服务，检测器漏报 |
| Root、网络、未声明分析工具 | 通过于观察 | 三份 child 无 Root/web；不外推为硬网络隔离 |
| Worker 可见 Schema/诊断可修复 | 通过 | 窄 prompt、Schema、字段级诊断同现有 validator 路径 |
| 人工决定与外部副作用边界 | 未退化 | 本轮无真实副作用或审批替代 |
| 控制面不增加科学判断 | 通过 | validator 只做结构、引用和一致性检查 |
| 无新实体/状态机/第二注册权威 | 通过 | 修复集中于 prompt 资源和只读资格检测 |
| 快速闭环与复杂度预算 | 局部通过 | 核心预算通过；只剩一个检测器和一次文本重跑 |
| 真实证据不误判 | **不通过** | B1 直接反证 23 项报告不完备 |

因此当前不能给出整体“不退化”结论，但失败只集中于 Worker 服务唯一性实证，不需要宏大重构。

## 八、最终裁定

**打回，不得进入 R3-C。**

完成 B1 的检测器负例与当前配置文本真实重跑后，PDF run5 和 image run3 可继续作为有效证据；
届时再做一次仅针对 exact Worker namespace、完整回归与文档证据版本的独立复核即可。
