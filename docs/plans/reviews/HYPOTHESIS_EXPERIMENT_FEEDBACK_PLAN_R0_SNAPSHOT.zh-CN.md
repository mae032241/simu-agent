# 实验反馈进入假设演化的最小修订计划 R0

日期：2026-09-16。性质：活动提案，待独立审查；未实施、未部署。
代码基线：`90a7b3a5865eb45649f1a39221337f9d939a3d71` 加当前工作区。
工作区已有会话生命周期、工作台及对应测试修改，本计划不包含、不覆盖这些修改。
本次用户授权为制定计划及独立审查；计划通过不等于已授权执行本轮源码实施。

## 1. 目标与范围

接通一条完整的反馈路径：

封存结果与分析 → 新 hypothesis proposal → 独立 critic → 必要的有界纠错 → 消费新假设的实验设计。

使研究者能够根据证据保留、削弱、替换或新增解释，也能判断现有解释仍不可区分或当前结果没有机制判别资格。
不要求每次反馈都改变假设集合，不以 proposal 数量或报告长度衡量成功。

本轮不实现观察先行的实验模式、实例全文检索、新研究记忆对象、多保真执行器、自动审批或统计评估平台。
不改 Run/Artifact/Approval/Execution 状态机，不新增角色和 Operation，不扩大 Worker 默认读取权限。
`execution_status/sync` 默认重复返回日志的问题单独记录于第 9 节，不混入此科学反馈补丁。

## 2. 已核实问题及规范所有权

| 当前所有者 | 已核实事实 | 本轮处理 |
| --- | --- | --- |
| `src/scidiscovery/general_science_agent_operations.py` | proposal 无实验反馈端口；critic 无对应原件入口；revise 只有旧稿、批评与基础 | 为三条相关路径增加有界可选历史输入，保留初次提案方式 |
| `general_science_resources.py` | critic 要求事实前提位于 foundation；没有实验反馈的适用性说明 | 明确基础证据、运行观察、分析解释三者的不同用途 |
| `general_science_components.py` | 输出引用只允许其声明的 context_sources 与基础来源；revise 保持原假设 key 集合 | 接通新端口的引用可见性；保留纠错边界 |
| `general_science_experiment_operations.py` | 设计已有 current_progress/experiment_results/result_analysis | 直接复用，不新增设计端口 |
| `artifact_agent/schema/layered_diagnosis.py` | 已有 summary、hypothesis_assessments、limitations、remaining_contradiction | 保留 Schema 和可选性；不新增报告表格 |
| `plugins/curve_score/curve_score/analysis_workspace.py` | 已集中结论、允许省略重复分层报告 | 只补充短的跨轮变化表达要求，继续允许简版报告 |
| `roles/scheduler.md` | 当前目录决定路由；绑定反馈、历史查询、复用和独立审查已有机制 | 补齐假设演化的选择、绑定与终止语义 |

文档关系：

- 本计划扩展 [校验纠错与跨轮续研](RESEARCH_CORRECTION_AND_CONTINUATION_PATHS.zh-CN.md) 的假设反馈消费范围，不取代其工程历史。
- 保留 [假设审查与路由修订](HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_REVISION.zh-CN.md) 中有界纠错、防措辞空转与独立审查职责。
- 保留 [分析交付简化](ANALYSIS_HANDOFF_AND_REPORT_SIMPLIFICATION_PLAN.zh-CN.md) 与 [信息交接修复](AGENT_HANDOFF_INFORMATION_REPAIR_PLAN.zh-CN.md) 的按需读取、单处结论和机械信息归控制层原则。
- 本计划只声明拟议行为；当前规范仍以运行代码为准。历史审查和已封存报告不改写。

## 3. 输入合同：可选反馈，共用声明，原件按需读取

在 `general_science_agent_operations.py` 为 hypothesis 操作定义局部共享端口元组，不建立跨插件上下文注册表。

| 端口 | proposal | critic | revise | Schema / 媒体 | 单项上限与数量 |
| --- | --- | --- | --- | --- | --- |
| `previous_hypotheses` | 可选 | 可选 | 不增加（已有 prior_draft；更早历史可用 current_progress） | hypothesis-proposal.v2 / JSON | 128 KiB × 1 |
| `experiment_results` | 可选 | 可选 | 可选 | `*` / `*/*`，沿用设计反馈表达 | 8 MiB × 4 |
| `result_analysis` | 可选 | 可选 | 可选 | `*` / `*/*`，容纳现有不同分析产物 | 128 KiB × 4 |
| `current_progress` | 可选 | 可选 | 可选 | `*` / `*/*` | 2 MiB × 4 |

新增端口均 `min_items=0`、`exposure=on_demand`、`usage=evidence_inventory`、`require_current=false`。
单 Run 基础 `max_input_bytes` 设为 48 MiB，既有 user_context 的 128 KiB 总预算由现有声明器追加。
这是绑定原件的上限，不是提示词展开预算；不把反馈全文复制进 prompt、handoff、summary 或新“背景包”。
不增加 output 字节、时间、尝试次数或网络权限；保留当前 required 输入与 foundation 审批合同。

具体用途：

- `previous_hypotheses` 是比较对象，不是 correction base，不能命名为 `prior_draft` 来触发修订 key 守卫。
- 原始 CSV、PLX、运行记录、计算记录等放 `experiment_results`；原分析的工具凭据、计划、审查及必要原件按用途放 feedback 端口。
- `result_analysis` 是封存解释，不因已 completed 或 verdict=pass 自动成为独立实测事实。
- 原分析为 fail/inconclusive/invalid_study/blocked 仍可作为历史材料读取；必须保留失败层次。它不授予执行资格。
- 旧 key 若未出现在新集合，相关比较在现有 contradiction/stage_objective 与 evidence 中说明；控制层 parent 关系保存历史连接，不新增 Agent 手填谱系表。
- foundation 仍提供原总体目标与原基础。新反馈不能覆盖 objective_contract，也不追溯修改旧 foundation 的资格。
- 缺少原件时允许限定结论或报告缺口；只有 Agent 声称独立核对了某数值时，才需要实际读取相应原件。不得以“绑定了所有历史”替代相关性选择。

## 4. 提示词、校验和消费必须一致

### 4.1 proposal 与 critic

更新 proposal 的 purpose/applies_when/not_for 和 IDEATOR_PROMPT：

- 初次提案仍可只读 problem_frame 与 foundation。
- 有反馈时，对旧问题描述与新结果作有来源的对照；problem_frame 是问题起点，不要求重新抽取基础来消化每次结果。
- 区分支持/削弱、未检验、不可区分、实现或数值失败；不把残差自动解释为机制缺陷。
- 可以新建假设集合，也可以有理由保持原集合。新集合不继承旧 critic 的通过结论。
- 若现有模型集合不足但暂时没有可交付候选，使用现有缺口 handoff 和有界结论，不强迫编造机制。
  当前 critic 不接收空 portfolio；Root 读取该缺口后停止此分支或选择补证据，不为此放宽 critic/design 准入。

更新 CRITIC_PROMPT：

- 原 foundation 中事实和新绑定实验反馈都是可查来源，不能再以“未写入旧 foundation”一律否定新运行观察。
- 分析的解释不等于原始观察，模拟结果不等于独立实验测量；核查有关数值/实现有效性、适用范围和不确定性。
- 仍只审查可行性、可证伪性及有限判别可能性，不替代结果分析、实验设计或执行批准。
- Root 根据 proposal 的 bound_inputs/parents 给 critic 绑定相关原件，不能只给作者摘要；缺少关键原件时 critic 明示受限范围与最小缺口，不凭空 PASS。
- 不新增“作者和 reviewer 的全部输入集合必须相等”的机械门禁；科学相关性由 reviewer 判断。

### 4.2 有界纠错不能丢失反馈

revise 增加相同三个 feedback 端口，保持 prior_draft/change_request/foundation 不变。
Root 从受审 proposal 的精确绑定恢复仍相关反馈，再交给 revise；修订后的 critic 同样读取相关反馈。
这只是让修订者看见其正在纠正的任务证据，不把 revision 改成证据扩张入口。
外部新证据要求重新组织候选时，选择新 proposal；旧 critic 不是新证据的替身。
同一 correction 内仍保持 hypothesis_key 集合、既有 review edge、max_revisions 和无进展指纹。

### 4.3 输出合同只核对输出

将新增端口接入三条操作的 context_sources，使 assignment 的引用候选、输出 Schema 和输出校验使用同一绑定集合。
多项输入别名如 `experiment_results_001` 由现有编译/工作区路径产生；不手工生成第二份来源登记。
核查 `_hypothesis_objective_context` 和 critic 的编译引用投影确实可接受新增反馈 alias；只修改不一致的位置。

输入结构、大小、实例身份、资格及历史可读性仍在 preflight；输出只检查输出格式、引用真实性、目标身份和既有纠错边界。
不在提交时重新检查输入资格，不对反馈 verdict 设置 pass-only 限制，不以 hypothesis_assessments 缺失、报告不够长或假设未变化拒绝提交。
不新增自然语言匹配、全历史覆盖、手工 case 登记或“必须调用评分工具”的要求。

### 4.4 跨轮分析与下一轮设计

只在共享 REPORT_GUIDANCE 增加短要求：涉及旧报告时，在现有 summary 中交代本轮改变了哪些判断；若未改变，说明原因。
旧观察、解释和限制继续通过 evidence 指针追溯；hypothesis_assessments 仍可选，不把旧报告全文累计进新报告。
TCAD 及通用分析沿用现有 current_progress/prior_analysis/manifest 规则，不更改分析 Schema 或原执行身份。

Root 从完成的报告与 signal 中选择动作，不从 next_action 文本直接取得 Operation 名。
新 proposal 经匹配 critic 后，下一轮 design 绑定原 objective/foundation、新 portfolio/critic、相关结果分析。
若 critic 要求补证据或模型对照，按实际目录行动；本补丁不把反馈循环改成强制固定 DAG。
设计与 materialize 的原科学 cohort、author/review/execution 审批链保持。总体目标不能被本轮诊断目标替换。

## 5. 兼容、版本与部署边界

1. 新输入均可选，既有 Operation ID 与 HypothesisProposal v2、CriticReview v2、LayeredDiagnosis v1 不变；不创建并存的新注册表。
2. 声明和 prompt 变化必须进入现有 compiled contract digest；若修改校验实现，同步更新其 ComponentSpec configuration_identity。
   不仅修改源码函数而保持实际合同身份不变。输出 Schema 未改变时不为装饰性版本号复制 Schema。
3. 新 Run 使用新合同，历史 sealed Artifact 保持原字节和父链。旧 completed 输出作为 evidence_inventory 可读，不自动变成新通过审查对象。
4. changed-contract Run 不能冒充 resume_from；维持原 draft_from/恢复规则。部署前先结束或保全活动 Run，不热切换已打开的 assignment。
5. 原 foundation 的有效审批不得因为消费者增加可选反馈而被无故退役；用真实旧合同生产对象测试现有历史兼容规则。
   若现有兼容机制意外阻断，先定位到精确身份投影并修订本计划，不能全局豁免 current/资格/来源检查。
6. critic 对象必须匹配当前新 proposal，旧 portfolio 的通过审查不能拿来替代；该负控走已有 preflight/父链机制。
7. 只部署框架和生成的新 Agent 配置；本范围不改 VM runner 协议、求解器或旧 Fig4 产品。

## 6. 文件范围与实施顺序

| 步骤 | 预期文件 | 交付与完成条件 |
| --- | --- | --- |
| P0 基线 | 本计划的 evidence 目录 | 记录工作区差异、三操作合同与选定定向测试基线，保存受影响文件快照；不提交/覆盖无关 UI 修改 |
| P1 声明和角色合同 | `general_science_agent_operations.py`、`general_science_resources.py` | 三条路径新增可选输入、同一真实来源规则、purpose/prompt/schema 投影一致 |
| P2 输出引用适配 | `general_science_components.py`，仅存在实现差异时修改 | 新反馈引用可提交；原目标、revision key 和独立 review 边界保持；不新增输入重检 |
| P3 消费和调度 | `plugins/curve_score/curve_score/analysis_workspace.py`、`roles/scheduler.md` | 跨轮变化短表达；proposal/critic/revise/design 精确补绑；沿既有流程生成同步 AGENTS 投影 |
| P4 工程验证 | 现有 hypothesis tests、必要的 `test_hypothesis_feedback.py`、安装入口测试 | 完成下面验收矩阵，收集失败、修复及资源记录 |
| P5 独立实现审查及行为验收 | 审查报告、简短验收记录 | 工程通过与 Agent 科学行为结果分开报告；失败不伪装成未完成的接口字段 |

预计直接生产逻辑涉及上述 5 个现有 Python 文件以内及 1 个角色源；不强行为满足数量压缩必要修改。
若需改变通用准入引擎、状态机、运行恢复协议、设计 Schema 或 TCAD 执行逻辑，则超出本计划，须先写出证据并重新审查范围。
文档更新仅含索引、受影响规则和必要的生成投影，不批量重写历史方案。

## 7. 验收矩阵与资源约束

### 7.1 确定性工程验证

| 编号 | 路径 | 必须观察到 |
| --- | --- | --- |
| E1 | 无反馈的旧 proposal/critic/revise | 原必需输入与提交方式继续可用 |
| E2 | 新反馈 preflight → invoke → worker assignment | exact normalized request 一致；可读原件、稳定 alias、on_demand，不展开全历史 |
| E3 | 引用新反馈完成 proposal 与 critic 提交 | 模型可见 Schema 接受、运行校验也接受；未知 alias 仍拒绝且定位具体字段 |
| E4 | fail/inconclusive/invalid_study 的封存分析与失败结果 | 可作为背景输入；不会授予成功、审批或执行权限 |
| E5 | 新 proposal 改变集合；revision 不改变集合 | 新 proposal 允许增删；revision 增删仍拒绝，合法局部修订可完成 |
| E6 | critic 要求修订后的完整接续 | revise 及后续 critic 均读得到同一相关反馈；旧稿、change_request 匹配 |
| E7 | 新 proposal → critic → design → materialize | 新 cohort 进入设计，原目标保持；错绑旧 critic 被原门禁拒绝 |
| E8 | 旧分析、旧 foundation、旧 proposal 和合同变化 | 历史可读；旧审批不被无关变化重置；changed-contract resume 不能绕过既有规则 |
| E9 | 简版 LayeredDiagnosis，无 assessments/gates | 能提交并由 proposal 消费 summary 和限制；不要求增加重复字段 |
| E10 | 隔离 wheel/真实 Local Worker MCP | 安装入口声明、工作区引用候选和提交三者一致，不只单独调用 validator |
| E11 | compiled identity 差异 | 变化可解释；生成角色不增加永久模型角色；无关执行器与审批合同不因补丁漂移 |

优先复用 `test_hypothesis_objective_boundary.py`、`test_hypothesis_review_routing.py`、
`test_agent_contract_alignment.py`、`test_catalog_installed_entrypoint.py` 的 fixture 与定向节点。
新增集成用例按行为参数化，不复制庞大初始化；一个纵向生命周期可同时覆盖 E2/E3/E6/E7。
测试必须经过实际 preflight/Worker 封存，不能用直接手写已通过 review 的对象冒充整条链成功。
安装验证允许脚本化受控测试 Worker，不把它宣称为真实 LLM 科学行为通过。

### 7.2 有界 Agent 行为验收

使用三个明确标注为验收合成材料的微型案例，保存在隔离测试实例，不能登记成生产 Fig4 证据。
科学判据由独立评审检查正式输出，不用新增运行时校验器强制“正确答案”。

| 案例 | 行为要求 |
| --- | --- |
| B1 有效反例 | 已验证实现、数值稳定且确实削弱旧预测；proposal 改变相应解释/适用范围或明确提出模型集合不足，critic 引用实际证据，design 不机械重复无判别力扫描 |
| B2 数值失败 | proposal/critic 保留物理结论边界，允许返回数值诊断；不能将执行失败当机制反证；不强制继续 design |
| B3 不可辨识 | 两候选与当前证据均相容，保留竞争解释，说明能区分的补充条件或有理由停止；不能强行选赢家 |

B1 至少走 proposal→critic→design 三个独立受控 Run；B2/B3 各走 proposal→critic。
每个案例最多增加一轮有具体纠错内容的修订，不通过则记录行为缺陷，不无限重试，也不现场扩合同。
全部使用相同已配置模型/推理强度、Operation 预算、独立审查边界；不给 Worker 预期答案或 Root 的隐藏研究总结。
从全新 Agent 启动，仅读绑定正式记录，观察是否能接续；不能以预制结果 fixture 替代此行为验收。
真实 Fig4 本轮 sealed 双水平诊断只用作之后部署接续的负结论范围核查，不重跑求解、不宣称物理机制被否定。
Agent 行为验收需要新合同的隔离可调用运行环境或用户安装后执行；环境未就绪则明确列为待验证，不能用工程测试冒充。

### 7.3 资源和证据

- 所有测试串行，一次一个 pytest 进程；不使用 xdist、不并行构建安装环境、不跑全量套件。
- 本地测试/构建子进程树合计内存预算 2 GiB，单批最长 180 秒；先确认机器可用余量，沿现有进程树监控方式运行。
  达到限制即停止并保留诊断，不自动扩预算。远程 LLM 等待与本地计算耗时分别记录。
- 独立审查与测试不同时启动本地重任务。安装包最多构建一次供定向探针复用。
- 验收记录：精确请求、completed/failed、关键证据引用、拒绝原因/字段、工具错误、超时、字节规模和可观测资源。
  Root 默认只读状态和关键结论，必要时展开诊断；字符/字节减少不冒称真实 token 减少。
- 不以测试数量证明科学发现能力；最终分别给出工程通过、行为验收结果、尚未验证的生产风险。

## 8. 独立审查要求与交付门

审查者未参与本计划编写，应独立核查源码，逐项回答：

1. 第一批是否真正闭合结果→假设→批评→设计，包括 critic 返修和负结果？
2. 是否出现看得见却不能引用、能引用却不能绑定、或输出重检输入的职责冲突？
3. 是否保留唯一控制权、旧合同恢复、历史可读性与精确审查/审批边界？
4. 是否引入重复字段、强制变更假设、第二研究状态或不必要的测试成本？
5. 兼容与安装验收是否能够发现真实生产路径缺口？

审查报告给 PASS/REVISE/FAIL、具体问题、最小修订和未核实项，绑定本计划 SHA-256。
审查不写产品代码、不启动仿真、不部署或操作生产控制状态。
通过后本轮交付计划和审查结论，等待用户实施指令；实施后仍须独立检查实际差异，计划 PASS 不继承为实现 PASS。

## 9. 后续事项（未纳入本轮实施）

1. 执行接口精简：status/sync 默认只给极短状态、耗时、错误和诊断引用；完整日志留存、按需展开。
   collect 保持独立后台 I/O，不改变日志与产品不同的超时规则。这是独立的小修复计划。
2. 观察先行：贯通 intent、portfolio、设计准入、物化与审查；区分研究目的与探索/确认性证据，不以 engineering 绕行。
3. 证据召回：先以现有缺口→补绑→新 Run 验证；只在观测到召回瓶颈后设计受控只读检索。
4. 实验选择及独立预测验证：先用现有 value/priority/prediction 表达预测差异和成本，不编造数值信息增益。

这些事项不作为本补丁通过的附加条件，也不意味着其科学能力已经实现。
