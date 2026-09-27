# R3-B 通用科学 Operation 独立跨边界审查

审查日期：2026-08-28  
审查基线：`baseline/8765-codex@404aeb1` 叠加已通过的 R0—R3-A 与当前 R3-B 工作树  
审查者：未参与 R3-B 实现的独立审查者  
审查范围：只读审查，不修改生产代码或测试

## 一、结论

**打回。当前不允许进入 R3-C。**

R3-B 已经证明了几个重要的正向结果：六类通用科学角色可以从一个
`general_science` 插件入口编译为 14 个 Operation；通用调用路径没有新增按
operation id、角色或领域分流的 allowlist；角色 Markdown 已经退化为 prompt；集合级校验和
曲线分析准入也已从旧角色特判迁到编译合同。

但这还不足以通过。当前存在五项完成门阻断，其中前三项直接破坏本计划承诺的最小授权、
精确科学审查父链和 Worker 可见合同：

1. `inherited_prototype` 不是受限只读原型，而是生产可达的
   `danger-full-access` 原生 shell；禁止写入、联网和跨任务读取目前只是提示词。
2. 新机制链缺少绑定“精确假设组合”的独立证据审查 Operation；现有确定性资格变换可把一个
   无关基础审查与后续假设组合拼接为 `ready`。
3. 所有科学输出共用三条通用语义占位文本，未投影实际运行 validator 的关键跨字段规则；
   Critic、EvidenceAudit 等关键任务也缺少输入相关的上下文闭合校验。
4. 图证据提取和审查把原始论文声明为 `evidence_inventory`，与“只有
   `claim_evidence` 可以支持主张”的统一输入语义冲突。
5. 图像真实运行报告用事件全文是否出现 `view_image` 字符串来判定原生图像工具已调用；实际
   事件只有 shell 的 `file` 命令，没有 `view_image` 工具调用，现有 pass 结论不能支持该声明。

这些问题都可在 R3-B 内作局部修复，不需要新增科学图、状态机、注册表或领域路由。

## 二、审查方法与独立复现

本审查读取了当前的 spec/catalog/invoke、`general_science` 与 `builtin` 插件、Root 通用调用、
TaskService 输出生命周期、Worker 工具代理、Codex 独立进程启动、部署单元、六个角色 prompt、
R3 计划与三个真实运行证据目录。

独立运行结果：

| 检查 | 结果 |
| --- | --- |
| `pytest -q tests/operations` | 82 项通过 |
| `pytest -q` | 113 项通过 |
| `python -m compileall -q src tests/operations` | 通过 |
| `git diff --check` | 通过 |
| 当前核心行数 | `spec.py` 319、`catalog.py` 444、`invoke.py` 428，合计 1191 |
| 无关 audit 拼接负例 | `_derive_candidate_eligibility` 返回 `ready / pass / ('h1',)` |
| 空审查对象负例 | `CriticReview(reviews=())` 与 `EvidenceAudit(checks=())` 均通过自身模型校验 |
| Worker 可见语义合同抽查 | intake、critic、experiment 三种输出得到完全相同的三条通用规则 |

自动化通过只能说明当前测试覆盖的合同自洽，不能抵消下述未被穿透测试覆盖的真实边界。

## 三、阻断项

### B1：`inherited_prototype` 实际拥有未收窄的生产级原生权限

严重性：阻断。

证据：

- `NativeToolPolicy.issue()` 接受 `inherited_prototype`
  （`operations/spec.py:98-109`），而 `general_science_plugin._agent()` 给全部通用科学
  Agent 设置该策略（`general_science_plugin.py:490-536`）。
- Codex 配置把该策略直接翻译为 `sandbox_mode = "danger-full-access"`，同时启用
  `shell_tool` 和 `unified_exec`（`platforms/codex_worker.py:395-432`）。
- “不得原生写文件、不得联网、不得访问 Root MCP、不得读取任务外文件”只出现在
  `_native_tool_instruction()` 的文字中（`platforms/codex_worker.py:320-346`）。OperationSpec
  和服务端没有对 shell 子命令、路径或 socket 做相同强制。
- 子进程由 `subprocess.Popen` 直接启动，工作目录虽是当前任务工作区，但没有另一个按任务
  收窄的 OS 隔离包装（`platforms/codex_worker.py:137-169,187-207`）。
- 生产 systemd 单元允许控制用户写整个 `STATE_ROOT` 与 `RUNTIME_ROOT`，并允许
  `AF_INET/AF_INET6`；因此同用户的 danger-full-access 子进程可达共享数据库、兄弟工作区、
  运行期 secret 目录和系统网络，而不只是当前任务文件
  （`deploy/systemd/scidiscovery-control.service.in:18-28`）。
- `materialize_assignment()` 创建的输入目录为 `0750`、输入文件为 `0440`
  （`tasks.py:1930-1975,6372-6388`）。这只能阻止不同用户写文件，不能阻止拥有父目录写权限的
  同一用户 unlink 后替换输入。finalize 校验输出及其原始 Artifact 父链，但没有在封存前重新
  核对 Worker 实际读取的物化输入内容。
- `general_science` 已作为安装态插件入口存在，`open_runtime()` 默认编译并交给生产 Root 和
  TaskService；没有 `architecture_acceptance_only`、隔离 state root、无副作用运行或 TCAD 禁用
  的强制 guard（`pyproject.toml:26-28`、`runtime.py:60-116`、
  `mcp_root.py:1257-1369`）。
- 三个正向真实运行都只证明模型服从提示。事件甚至显示 shell 直接读取
  `output/result.json`；没有负例真正尝试兄弟目录、数据库、网络、Root socket、输入替换或原生
  输出写入并被 OS 拒绝。

判断：

“工具可见，但 OperationSpec 禁止”在当前实现中并不准确。OperationSpec 实际准许了完整
shell；更细的禁止项只存在于 prompt。文档如实承认它是“可审计行为约束，不是生产级安全
隔离”，这一表述本身诚实，但该行为约束没有与真实调用入口隔开。因此它可以用于观察模型是否
守规矩，不能证明最小授权，更不能承载正式科学结果或后续 TCAD/外部执行链。

最小修复集（二选一，优先第一种）：

1. 在 R3-B 首版将已安装通用科学 Operation 恢复为 `shell=none`，文本/PDF/图像使用受控、
   任务绑定的 Worker 读取能力；或者
2. 真正把 Codex 子进程放入按任务的 OS 边界：只读挂载精确 inputs/schema，仅输出/暂存路径
   可写，无网络，不可见共享 state/runtime/仓库/兄弟工作区，只暴露精确 Worker 代理 socket
   和一次性 capability。

若为了调试暂时保留 `inherited_prototype`，还必须在编译/调用或部署边界硬拒绝正常生产调用，
只允许显式的隔离架构验收实例；提示词字段不能充当这个 guard。修复后必须增加实际攻击负例：
输入替换、兄弟任务读写、共享数据库读写、Root socket、原生写 output、shell 网络和未声明工具
均应被平台拒绝，而不是仅在事件里“没有发生”。

### B2：假设证据审查没有绑定精确假设组合

严重性：阻断。

证据：

- `science.hypothesis.propose.v1` 的 review 只指向
  `science.hypothesis.criticize.v1`（`general_science_plugin.py:719-756`）。
- `science.evidence.audit.v1` 只消费 `scientific_foundation` 与可选来源，目标是审查 foundation，
  不消费 `hypothesis_portfolio`（`general_science_plugin.py:557-600`）。
- 候选资格变换只验证 critic 的 hypothesis key 与 portfolio 相同；它从 audit 的 check status
  直接形成整个组合的证据 verdict，没有验证 audit 的目标、组合摘要、假设覆盖或父链
  （`transforms.py:221-240,604-639`）。
- 独立负例构造了一个仅声称“无关基础元数据格式正确”的 pass audit；与一条全 pass critic
  和任意新 portfolio 组合后，当前函数返回 `status=ready`、`evidence_verdict=pass`。

影响：基础证据审查可以错误地资格化后续才生成的新机制。这违反“新机制的 critic 与 evidence
auditor 都必须绑定同一精确 portfolio；foundation-only audit 不得资格化后续假设”的既有科学
边界。

最小修复集：

- 新增或复用一个“假设证据审查”Operation，精确输入至少包含
  `hypothesis_portfolio`、`scientific_foundation` 和其来源；审查输出必须逐项覆盖该组合。
- 候选资格变换必须验证 audit 的精确 portfolio 父链/摘要和声明覆盖；不匹配时失败关闭。
- 不必机械增加第 15 个 Operation：如果通用 foundation audit 没有独立调度价值，可将
  `science.evidence.audit.v1` 改为组合审查；否则第 15 个是有科学责任差异的正当最小增量。
- 不得用 Root/scheduler allowlist 修补。

### B3：Worker 可见语义合同是占位文本，关键上下文闭合没有强制

严重性：阻断。

证据：

- `Resources.semantic_contract` 只有三条通用描述，所有输出端口都通过同一个 `SEMANTIC`
  引用它（`general_science_plugin.py:235-247,427-464`）。
- 对 evidence extract、critic、experiment 三个不同输出调用
  `operation_port_json_schema()`，其 `x-scidiscovery-semantic-constraints` 完全相同，只说科学内容
  由 Worker 生成、事实可追溯、应满足 validator；并未说明 validator 的实际规则。
- 实际模型包含大量 JSON Schema 无法完整表达的 `model_validator`：假设竞争关系和证据引用
  闭合、每个未解决 critic 维度的最小行动、ScientificReview verdict 与失败维度关系、实验
  case/预测/资格映射、诊断跨对象一致性等。
- `science.hypothesis.criticize.v1` 没有 context validator。虽然 prompt 要求“每个假设恰好一
  行”，`CriticReview` 自身允许 `reviews=()`；EvidenceAudit 也允许 `checks=()`。因此任务可
  validate/finalize 一个没有覆盖任何输入对象的空 payload。
- critic 的 handoff verdict 与 payload 各维度、audit 的 handoff verdict 与 checks 也没有统一
  上下文校验，可能向调度器发出与科学对象相反的 bounded signal。

影响：Worker 只能从失败反馈猜测隐藏规则，或产出结构有效但没有覆盖输入的“审查”；这违反
33 项约束中的“带运行时跨字段规则的模型必须从同一已安装 validator 注册表投影 Worker 可见
语义合同，缺投影则派发前失败”。

最小修复集：

- 按实际输出/validator 登记窄语义合同，不再复用一个三句占位资源；合同必须由与 finalization
  相同的已安装 validator 定义或同源声明投影。
- 为 critic 增加精确 hypothesis key 全覆盖、不得多/少行以及 pass 耦合的 context validator；
  为 audit 增加精确目标、来源/主张覆盖及 verdict 耦合；为 object review 增加精确 target 与
  verdict 耦合。
- 这些 validator 只检查引用闭合和状态一致性，不替 Worker 做物理或科学判断。
- 增加通过完整 Worker 文件生命周期提交空、错 key、错 target、handoff/payload 冲突的负例。

### B4：图证据原论文端口的 usage 错误

严重性：阻断。

证据：

- `science.evidence.extract.figure.v1.paper_source` 与
  `science.evidence.audit.figure.v1.paper_source` 都声明为 `evidence_inventory`
  （`general_science_plugin.py:961-968,1031-1038`）。
- 通用 Worker 输入合同明确只有 `claim_evidence` 可以支持任务主张；`prior_signal`、修订基、
  change request 等不得替代 claim evidence（`roles/common.md:34-40`）。既有调度约束也要求图
  审查中的 paper 为 claim evidence，提取主结果为 prior signal，附件为 inventory。

影响：图像像素、论文坐标和图注等事实没有一个正式可支持 claim 的输入；若 Worker仍从 paper
得出事实，就违背端口 usage，若严格遵守 usage，则任务无法完成科学目标。

最小修复集：把两个 Operation 的 `paper_source` 改为 `usage=claim_evidence`；保留 manifest、
deterministic report、panel、overlay、curve table 和 figure request 为 inventory。增加 assignment
物化断言及错 usage 负例。

### B5：真实图像验收是字符串误判，不证明 `view_image` 路径

严重性：阻断当前 R3-B 完成证据；不是新的架构实体缺口。

证据：

- `live_r3_science_agent_qualification.py:299-302` 用
  `"view_image" in event_text` 判定图像工具已使用。
- 图像任务的 instruction、schema/prompt 和最终文本本身包含 `view_image`，所以即使没有工具事件
  也会得到 true。
- 对 `r3-science-agent-image-run1` 的 JSONL 逐项解析显示：启动项只有
  `command_execution` 与 `mcp_tool_call`；图像识别实际调用是 shell 的
  `file .../inputs/source_material.png`，不存在 `view_image` item/tool call。
- 同理，`network_absent` 只检查没有 `web_search` 事件，不能证明已启用 shell 无法调用 curl；
  `root_mcp_forbidden` 也只证明本次没调用，并未做拒绝负例。

最小修复集：用结构化事件类型和精确 tool 名匹配，不搜索任意事件文本；重新运行图像任务并保留
真正的 `view_image` item。网络、Root、兄弟路径和写入结论只能由实际拒绝负例给出，不能由正向
运行中的“未观察到”替代。

## 四、已通过的边界与非阻断项

### N1：单一插件入口和通用调用路径成立

- `pyproject.toml` 只有 `scidiscovery.plugins` 一个发现组，核心安装登记 `builtin` 和
  `general_science`；安装态测试验证 catalog 只从这一组编译。
- `open_runtime()` 启动期调用 `compile_installed_catalog()`，同一个 catalog 传入 TaskService、
  Root 和 Codex dispatch；部署入口因此已接通。
- `RootToolFacade.operation_invoke()` 只按 compiled executor kind 分派 Agent/Transform/Effect，
  未对 14 个科学 operation id 写分支（`mcp_root.py:1257-1369`）。

结论：R3-B 新路径不需要 Root、TaskService、UI 或 scheduler 的 operation allowlist。旧 Root 和
`scheduler_topology.py` 中仍有 8765 角色分支，但它们未参与 compiled Operation 路径，属于明确
待 R3-D 删除的 legacy 消费者；本项暂不阻断，R3-D 必须兑现删除门。

### N2：角色 Markdown 已退化为 prompt，旧元数据边界可辨认

六个核心角色文件均无 frontmatter，只含科学提示正文。Operation 使用
`load_core_role_prompt()`，并禁止角色目录 override 影响内置 Operation
（`platforms/roles.py:300-329`）。`_LEGACY_CORE_ROLE_METADATA` 和旧 collection/profile 仍服务
`task_create` 旧路径，注释和计划已声明 R3-D 删除。

结论：当前没有发现 compiled Operation 从 legacy role/profile 回填 prompt、输出、工具、预算
或上下文的 fallback。双轨仍增加总复杂度，但在 R3-D 完成前可作为非阻断迁移债务。

### N3：集合级校验和曲线分析去角色特判正确

- Operation 输出集合先逐项执行 compiled codec/validator，再把主 envelope 与完整附件映射一次
  交给 compiled bundle validator；旧图证据/参数特判只在
  `operation_authority is None` 的 legacy 路径执行（`tasks.py:3499-3721`）。
- `worker_curve_analyze` 依赖已登记 capability、精确输入和
  `curve_analysis_plots` collection，不再以 `diagnostician` 角色名决定准入
  （`mcp_worker.py:582-668`）。

### N4：14 个 Operation 没有明显机械过度拆分，但集合仍不闭合

普通文本/PDF/图像共享一个 evidence extract；定量图提取、曲线误差诊断和三类 bounded revision
具有不同工具、集合或修订基类型，保留为变体是可辩护的。当前更大的问题不是“14 太多”，而是
B2 所述必要的假设证据审查缺失。修复应优先复用/改造现有 audit，不为实现细节新增 operation。

`general_science_plugin.py` 当前 1319 行，说明复杂度从六份元数据集中到一个声明模块，但它仍是
声明与窄 validator/资源组合，而不是状态机或巨型 OperationSpec 类。后续可在保持一个插件入口
和一个 `PluginDefinition` 的前提下按声明资源拆模块；这不是本轮阻断，也不应先于上述边界修复。

### N5：核心预算满足活跃计划，但文档数字需同步

当前实测 `319 / 444 / 428 = 1191`，满足活跃计划冻结的 `320 / 450 / 430` 分项上限及总计
不超过 1200。R3-A 报告与 R3 实施记录仍写 `315 / 444 / 428 = 1187`，这是非阻断文档漂移，
应按当前工作树更正，不能继续引用旧数字作为验收证据。

## 五、33 项约束族不退化判断

| 约束族 | 判断 | 说明 |
| --- | --- | --- |
| 单一注册、启动期编译、不可变 catalog | 通过 | 新科学 Operation 由唯一插件组编译，Worker/调度器不能实时编译 |
| OperationSpec 是声明闭包而非巨型执行类 | 通过 | 执行、codec、validator、工具仍为窄组件 |
| 科学判断归 Worker/调度智能体 | 通过 | 新代码没有在核心排序假设或生成科学结论 |
| 确定性变换不新增科学判断 | 局部通过 | eligibility 只 join 状态，但 B2 允许错误组合父链 |
| Artifact/CAS、任务、审批、执行唯一权威 | 通过 | 未新增平行状态或注册表 |
| 文件交接与输出封存 | 局部通过 | Worker 文件 validate/finalize 闭合；danger-full-access 可旁路物化输入/暂存边界 |
| 精确输入、不可变来源与谱系 | 不通过 | B1 同用户 shell 可替换物化输入；B4 paper usage 错误 |
| Worker 去身份、任务私有路径、兄弟隔离 | 不通过 | B1 无 OS 级任务外路径隔离，真实负例缺失 |
| 工具最小授权与服务端默认拒绝 | 不通过 | Worker MCP 白名单成立，但完整 native shell 仅靠 prompt 收窄 |
| 网络默认关闭与来源冻结 | 不通过 | Worker 网络工具关闭；shell 网络没有被平台隔离，正向事件不足以证明拒绝 |
| Worker 可见 schema/语义规则同源 | 不通过 | B3 使用通用占位合同，关键 context validator 缺失 |
| 产出与独立审查精确绑定 | 不通过 | B2 缺 portfolio-bound evidence audit |
| 人工决定与外部副作用唯一门禁 | 核心未退化但受暴露威胁 | 既有 Approval/Execution 仍权威；B1 shell 自身却可产生未声明外部副作用 |
| 审查不替 Worker 做科学判断 | 通过 | 当前 validator 只做结构/引用闭合；建议修复也不应增加科学判定 |
| 幂等、恢复、CAS 与终态注册 | 通过于已测路径 | 现有正向运行完成并撤销 attempt secret；未证明 hostile shell 下的隔离 |
| legacy 删除和复杂度下降 | 尚未完成 | R3-B 新路径简化成立；总体净下降须等 R3-D 删除旧消费者后判断 |

因此不能给出“33 项约束不退化”的整体结论。失败集中在最初设计最重视的 Worker 上下文可见
范围、最小授权和精确独立审查，而不是可推迟的样式或文档问题。

## 六、放行 R3-B 的最小条件

不要求宏大重构。下一轮复审只需看到以下五项关闭：

1. `inherited_prototype` 从默认/生产可达路径硬隔离，或真正实现按任务 OS 隔离；完成输入、兄弟
   路径、共享 state/runtime、网络、Root socket、原生输出写入的拒绝负例。
2. 增加或复用精确 portfolio-bound evidence audit，并让 candidate eligibility 验证同一组合父链
   和完整覆盖。
3. 以同源方式投影各输出的实际语义约束；critic/audit/object review 增加最小上下文闭合及
   handoff 一致性负例。
4. 图证据两个 `paper_source` 端口改为 `claim_evidence`，并验证物化 assignment。
5. 修复真实运行事件判定并重跑图像能力；把“未观察到越权”与“平台拒绝越权”分开报告。

在这些条件完成并由独立复审确认前，R3-C 不得开始迁移 TCAD 或真实外部副作用路径。

## 七、最终裁定

**打回。当前不允许进入 R3-C。**
