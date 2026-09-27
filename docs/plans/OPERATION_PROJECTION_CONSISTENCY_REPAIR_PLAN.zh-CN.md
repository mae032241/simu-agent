# Operation 合同投影与纠错一致性修订计划

日期：2026-09-11。版本：R1。状态：已按本轮审查意见修订，待复审，尚未实施。

本计划承接已部署的一次编译机制所暴露的消费者投影缺陷，不继承旧计划的审查 PASS。
本轮交付仅为计划修订；不修改生产源码、不部署、不创建科研 Run。

## 1. 文档归属与事实边界

| 材料 | 归属与处理 |
| --- | --- |
| 本计划 | 本次投影、诊断和升级兼容修复的提案入口；实施状态须另有证据 |
| [决策索引](README.md) | 指向当前提案，区分计划、实现、安装和真实研究验收 |
| [原 R4 计划](OPERATION_TOOL_CONTRACT_COHERENCE_REPAIR_PLAN.zh-CN.md)及其审查 | 冻结历史，不覆盖原文、不扩大既往 PASS 的适用范围 |
| [投影审计](reviews/OPERATION_PROJECTION_AUDIT.zh-CN.md)及探针 | 本计划的问题依据，不是修复完成证明 |
| [P6 现场记录](evidence/operation-tool-contract-coherence/P6_REPORT.zh-CN.md) | 保留失败和有限分析事实，不改写为真实计算或跨轮闭环通过 |
| 架构规范、注册声明和运行数据 | 本次计划修订不变更；实施时仅由下述明确的源码所有者修改行为 |

已确认：分析评分 Schema 允许 5,000 个采样点而实际模型拒绝；完整 MCP Schema 到模型可见接口发生信息丢失；部分字段关系诊断和 Run 超时分类失真。25 个 Agent 输出 Schema 引用可解析，不能据此宣布全部合同失效。

完整 MCP Schema 到平台模型接口的内部转换位置仍未定位。简单 `$ref` 可正常展开；本方案不假定所有 `$ref` 有问题，也不宣称修复了平台内部转换器。

## 2. 第一准则与本次范围

唯一声明经过一次编译，向每个实际消费者交付完整且有正确作用域的合同；可静态表达的限制必须与执行一致。运行时才可确定的限制由原执行所有者检查，并向调用者说明其条件。

preflight 负责输入绑定与准入；输出校验只负责本次输出及其已声明的证据关系，不重新执行输入准入。历史记录的读取、可信引用和执行许可保持分离。评分仍是分析角色的可选工具，不成为设计、author 或执行的前置环节。

本次不新增状态机、合同注册表、Operation、查询工具、独立评分 Run、统一规则 DSL 或 VM runner 协议。数值算法、既有结果格式和科学资格政策保持原义；不为本次展示修复新增科学门禁。

## 3. 四项审查缺口的关闭要求

| 审查缺口 | 修订后的要求 | 对应实施/验收 |
| --- | --- | --- |
| 回复、日志和回执诊断不一致 | 在原回执字节预算内先形成最终诊断集合，再写回执、回复和日志；同一次输出拒绝只记录一次 | C；E3 |
| 升级与历史兼容没有执行协议 | 明确合同摘要变化、配置再生成、旧 Run 不迁移、新 Run 绑定历史、旧请求与旧回执不重写 | E；E4/E5 |
| 保存合同但消费者未必读得到 | 一个投影函数连接编译目录、assignment 和两种 backend 的打开回复，并在角色提示中指定读取路径 | B；E2/E6 |
| 有限分析成功不能证明工具已修好 | 新 Agent 仅凭绑定材料与实际交付的合同构造调用，完成有独立数值答案的计算，并验证错误后同 Run 纠正 | F；E3/E6/E7 |

诊断缺口已有小型复现：8 条回复诊断只进入回执 5 条，回执为 4,009 字节。后续 `calculation_sources` 按回执逐条比对，复制完整回复可能再次被拒绝。见[复现输出](evidence/operation-tool-contract-coherence/PROJECTION_PLAN_REVIEW_PROBE.log)及[资源记录](evidence/operation-tool-contract-coherence/PROJECTION_PLAN_REVIEW_PROBE.json)。

## 4. 实施顺序与源码所有权

先冻结当前工作树增量基线，再按 A—D 完成相互依赖的实现；E 完成安装及历史验证，F 完成消费者和现场验收。不得用修改前的测试结果证明修改后的包已通过。

下表为生产修改边界。测试在现有所属文件内补充；没有对应缺陷和验收的改动不纳入本轮。若实现证明必须越过此范围，先记录具体依赖并修订范围，不顺带重构。

| 所有者文件（相对仓库根目录） | 本轮职责 |
| --- | --- |
| `plugins/curve_score/curve_score/analysis_tool.py` | 分析专用请求类型、原预算的共同常量与说明、接收最终回执诊断 |
| `src/scidiscovery/operations/tooling.py` | 从编译产物生成 backend 实际允许工具的完整合同投影 |
| `src/scidiscovery/artifact_agent/service/run_assignment.py` | assignment 交付同一工具合同投影 |
| `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py` | 打开回复、最终诊断回复与日志、一次拒绝记录 |
| `src/scidiscovery/artifact_agent/interfaces/mcp_hardened_worker.py` | 同一合同读取入口、保留已有类型化错误 |
| `src/scidiscovery/platforms/codex.py` | 两种 backend 的合同读取指引 |
| `src/scidiscovery/operation_contract.py` | 安全且具体的字段限制和已声明关系诊断 |
| `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py` | 已发生的关系错误使用同源静态说明，保留历史请求表示 |
| `src/scidiscovery/artifact_agent/service/tool_evidence.py` | 在现有预算内完成一次诊断定稿，返回内部引用与最终集合 |
| `src/scidiscovery/artifact_agent/operation_tool_context.py` | 传递最终诊断，保持公共 attempt 引用格式 |
| `src/scidiscovery/artifact_agent/service/run_outputs.py`、`service/runs.py`（同属 `artifact_agent`） | 输出拒绝记录所有权；超时、checker 和普通运行故障分类 |
| `src/scidiscovery/operations/spec.py` | 目录按输入端口真实声明投影现有元数据 |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`、`src/scidiscovery/operations/invoke.py` | Root 和内部入口复用“仅空 parameters”合同 |

不预设修改 TCAD 算法、Workspace backend 接口或目录编译器。TCAD 评分优先通过现有继承获得请求修复；现有摘要机制负责追踪声明变化，不另造版本权威。

### A. 把实际静态限制放入分析输入声明

1. 在现有评分模块定义分析专用的 `CurveComparison` / `CurveComparisonSpec` 子类型：每次最多 16 个 comparison，每项最多 4,096 个采样点和 16 个 operator。通过字段约束生成 Schema；`ScoreRequest` 使用该类型，通用分析和 TCAD 分析共同继承。
2. 删除 `_calculation_bounds` 中对应的重复判断。保持通用、非分析用途的曲线模型上限不变；不把分析工具的资源政策扩散到其他操作。
3. 保留默认采样点 257，以及调用者原始 JSON、默认值省略方式和摘要算法；不把解析后的默认值写入 `raw_request`。持久化 `CalculationRecord.request` 仍可保存旧字典，不换成新窄模型来拒绝旧记录。
4. 现有请求 12 KiB、源点数和工作量预算仍由其实际所有者检查。将本次需展示的预算值收敛为共同常量，生成工具说明；依赖实际源数据的预算不伪装成单字段 Schema 上限，也不重复实现校验。
5. 字段上限错误给出完整字段路径和实际上限。已发生的 `experiment_key/case_key` 配对、计算状态与结果/原因关系，沿用 `declared_violation`：规则所有者提供静态安全说明，合同说明和诊断复用它。其执行判断仍只有一处，不批量改写全部科学模型校验器。

验收：4,096/4,097、16/17 等边界在 Schema 与实际模型一致；5,000 负例在源文件读取前返回明确位置；合法旧请求的有效值、原始表示和数值结果不变。

### B. 把完整合同交付到实际 Agent

1. `operations/tooling.py` 提供一个投影函数，从编译后的工具定义及现有生命周期声明生成 `tool_contracts`，只选择 `backend.assignment_tool_names` 允许的名称。结构为工具名到 `{description, inputSchema}` 的映射；不维护第二份模型或注册表。
2. 每个 `inputSchema` 保留独立的根、`$defs`、默认值、枚举、字段边界和关系说明；不可把多个 Schema 的 `$defs` 混到一个错误的根作用域，也不可静默截断。已有工具说明继续承担不能用 JSON Schema 表达的执行语义。
3. assignment 在已有 `tools` 名称旁增加上述映射。Local 和 Hardened 的 `worker_open_assignment` 回复均交付同源映射；新 assignment 使用冻结内容，两种打开路径不得各自重新推导规则。
4. Codex 角色指引明确：打开 assignment 后，按对应工具的 `tool_contracts` 构造调用；Local 可补读 `assignment.json` 同一字段，Hardened 从打开回复读取。即使平台把参数显示为 `unknown` 或把数字元组显示错，也有同轮可访问的完整合同。该补读路径不授予新工具或文件权限。
5. 对合同摘要相同、但旧 assignment 尚无此附加字段的 Run，只在现有合同身份检查通过后，从该编译合同提供打开回复的投影；不重写旧 assignment。摘要不匹配按 E 处理，不能借补读兼容绕过身份检查。
6. 验证实际交付内容与 MCP/编译产物相等，并解析所有局部引用；不能仅断言字段存在。生命周期工具使用其已有合同来源，领域工具使用编译时冻结的 Schema，禁止在各消费者重新调用模型造副本。

验收：Local/Hardened 的允许工具集合分别准确；评分请求的嵌套限制、`value_space` 和 figure preview 数字元组在交付内容中可读。平台简化接口若仍错误，记录其剩余显示限制；以实际补读并调用的 E6 验证可用性，不称平台 bug 已修复。

### C. 同一份可引用诊断贯通回复、日志和回执

1. 维持现有 `ToolAttempt` 最多 8 条诊断和 4 KiB 回执预算。先安全归一化，再按真实回执元数据计算剩余空间、选取可保存的有序集合，然后一次定稿。回复不能保留回执丢弃的尾部诊断却让 Agent 把它们当成可引用证据。
2. `finish_tool_attempt` 在内部返回“现有 attempt 引用、最终诊断集合”。更新 Local `_finish_attempt`、`OperationToolContext.finish_attempt` 和评分工具调用者；回复、对应活动日志和回执都使用该最终集合，不再次各自格式化或裁剪。
3. 公共 attempt 引用及 `CalculationAttemptReference` 结构不扩展；不把诊断塞入引用对象。保持结果摘要排除 attempt/diagnostics 的既有规则。类型化的安全诊断标记只在进程内受信，不把任意外部字典升级成可信错误。
4. 非成功结果在可保存时至少保留一条有效原因；若元数据已使有效失败回执无法写入，返回现有 `attempt_recording_failed` 等明确工程故障，不生成“有证明但无原因”的伪成功，不扩大预算。诊断较多时，Agent 先据已交付集合纠正，再进行有界重试。
5. 为输出拒绝确定唯一记录位置。`RunService.validate_candidate` 已写日志的错误，通过最小的进程内标记交给外层直接回复；外层不得补一条缺诊断的同名事件。尚未记录的直接 `WorkspaceError` 等由边界记录一次安全详情。不同含义的工具尝试事件仍保留，不误删为重复事件。
6. Hardened 包装路径保留已类型化的 Worker/诊断错误，不再用泛化错误覆盖它们。未知异常仍只公开安全工程诊断，不直接回显可能包含敏感值的任意异常字符串。
7. 后续输出引用失败记录时，与原回执最终诊断逐项核对。旧回执保留当时的文本和表示，不用新格式器重新生成；不能通过放松证据成员关系来解决本次不一致。

验收：超过回执容量的诊断在回复、日志、回执中的路径、代码、阶段、消息及数量一致；后续分析按真实回复引用可通过。领域工具触发已记录的输出拒绝时，只有一次对应拒绝事件且保留具体详情。

### D. 修正相邻的已确认小投影缺陷

1. Run 失败分类由明确来源决定：`timed_out=True` 使用 `run_timeout`，真实 `RunCheckerError` 显式使用 `checker_failure`，未分类的一般失败使用 `runtime_failure`。同步调整安全诊断类别白名单和原默认调用点，不用检查器故障承接全部未知错误。
2. 保留四态 Run 生命周期、截止时间检查、原失败原因和封存事件；不解析旧自由文本来批量重写历史分类，也不放开尚未超时 Run 的超时终止条件。
3. 为现有 `parameters` 定义共享的“只接受空对象”请求类型，Root preflight/invoke 及内部调用边界复用。省略和 `{}` 保持原行为；非空值在正确输入入口拒绝，不新增参数功能，不移到输出提交时检查。
4. 目录输入端口按原 `InputPortSpec` 增补 `usage`、`exposure`、`require_current`、`media_types`、`max_item_bytes`。仅投影已有声明，不新增准入规则；共享展示类型不得给输出端口编造输入语义。

验收：超时、检查器异常和普通故障分别落到正确摘要；Root Schema 与实际入口一致；目录新增信息与声明逐项匹配。目录元数据缺失作为独立小缺陷验收，不冒称其已被证明是此次评分失败的直接原因。

### E. 安装、合同代际与历史续接

1. 实施前记录当前 HEAD、脏工作树文件及相关基线；按本计划增量判断，不覆盖既有改动。完成定向源码检查后构建隔离安装包，再测试真实安装入口；记录包、目录及生成配置摘要。
2. Schema 修改可能改变 Operation digest 和 `agent_type`。安装后按现有流程再生成角色配置并重启对应服务/会话；核对安装包、运行目录、生成 profile、实际暴露 MCP 合同是否属于同一代。若不一致，报告部署故障，不让 Agent 通过改写科学结果来补救。
3. 旧 Run 保留原合同、绑定、预算和所有成果。合同已变时不得在原 Run 静默切换新版校验器；创建新 Run，以现有端口显式绑定需要的已封存历史。旧 Run 恢复失败不得转化为绕过 digest 检查的许可。
4. 已封存分析、恢复 manifest 与原执行文件按现有读取和引用规则续接；不重新赋予过期资格。失败 Run 的草稿仅通过已有受控恢复入口、且其 preflight 允许时续接，不读存储拼装替代输入。
5. 旧请求原始 JSON、默认值省略方式、原回执诊断和已有摘要原样保留。新模型只准确表达已执行的分析上限；算法未变则保留 `ALGORITHM_VERSION`，以相同有效输入复算确认数值一致，不以改算法版本掩盖序列化变化。
6. 回滚使用原先冻结的代码包和对应生成配置，不改写数据库历史或批量重签旧对象。当前合同不能恢复的旧 Run 仍应可按既有历史读取规则诊断；不承诺可跨合同代际继续执行。

### F. 分层验收与结束条件

| 编号 | 必须证明的行为 | 证据与失败判定 |
| --- | --- | --- |
| E1 静态合同 | Schema/模型上限一致；合法默认值与原始请求不变；运行时源预算仍有效 | 边界正反例、5,000 点反例、既有请求重放；不得只比较 Schema 快照 |
| E2 实际投影 | 编译、MCP、assignment、打开回复保持同一工具合同；两种 backend 仅暴露其允许集合 | 实际入口内容和引用解析，包含数字元组、嵌套字段、默认值、枚举；单声明变更可贯通 |
| E3 可纠错交接 | 错误请求得到明确诊断，预算内同 Run 修正后完成；回执容量截断不造成后续证据拒绝 | 8 条长诊断压力小夹具；回复/日志/回执一致；新 Run 引用原失败回执；一次拒绝事件 |
| E4 历史与状态 | 新旧合同不串用；同摘要旧 assignment 可补读；旧请求与回执原样可读；故障分类准确 | 新旧记录混合的定向兼容测试、真实超时与 checker/普通故障正反例 |
| E5 安装态 | 测到安装包而非源码路径；生成配置与运行合同同代；正确职责边界不回退 | 隔离环境、真实 MCP 入口、摘要对照；不得把源码 PYTHONPATH 混入安装态测试 |
| E6 新 Agent 实际计算 | 无父会话背景的新分析 Agent 从绑定测试材料和交付合同自行构造调用，得出已知数值 | 实际注册工具调用、回执和 sealed output；人工预写请求或仅模拟 Agent 不能替代 |
| E7 当前研究续接 | 新版分析角色能读既有封存记录并进入分析，不再卡在此次合同猜测及诊断引用错误 | 受控现场 Run 与封存结果；根据真正的证据限制保留有限科学结论 |

E6 使用隔离工程实例中已有分析 Operation，不新增生产操作或伪造真实科研实例的资格。绑定夹具由测试装配，不由 Root 生成科研事实。一个可复核的数值例子：reference 两点为 `(0,10)`、`(1,100)`，candidate 为 `(0,100)`、`(1,1000)`，在两个端点用已有 `residual_max_abs` 分别按 `log10` 和线性数值空间计算，独立 oracle 为 1 和 900。oracle 由验收方持有，不通过给 Agent 预写请求或答案来“通过”。若实际模型对该夹具另有合法字段要求，在既有支持范围内补齐，不新增算子或改算法。

E3 同 Run 修正除直接调用测试外，还须保留实际 Agent 至少一次明确错误后的纠正证据；可在隔离验收任务要求其先验证一个明确超限的边界，再构造合法调用，不把完整请求直接交给它。失败类型、纠正调用和封存记录须同属该受控 Run。

若实际平台无法派发 E6，标记该项未验证；不能拿部分分析封存或安装入口测试代替。E6 是确定性工具的工程能力验收，E7 是真实科学工作推进验收；真实数据缺少比较依据时允许有限结论，但不能因此宣布所有研究目标或原 P6 跨轮闭环已完成。

## 5. 测试与资源约束

在现有所属文件补充或调整必要用例：`tests/operations/test_score_request_contract.py`、`test_contract_attempts.py`、`test_l2_run_invariants.py`、`test_agent_contract_alignment.py`、`test_analysis_tool_installed.py`、`test_catalog_installed_entrypoint.py`、`test_r4_author_recovery.py`、`test_tcad_result_analysis.py`。按实现改动选择其中相关用例，不承诺这些文件整套均通过，不重复新增只镜像实现的测试。既有 Hardened 旧夹具失败单列来源，不隐去、不混成新回归。

任一时刻仅一个测试/构建进程树；内存上限 512 MiB，进程树 RSS 达 448 MiB 提前停止并保留日志。禁止 xdist、多路同步测试、全量 pytest、求解器重跑和大规模采样压力测试。实际 Agent 验收串行派发，不与本地构建/测试叠加；远端模型资源不冒充已被本地内存限额覆盖。

采用 `scid-change-scope-checks` 选择覆盖上述边界的最小可信检查；通过后只因新改动或未解决失败而扩大测试。最终交付列出准确通过项、未覆盖项、原有失败和最高内存，不用测试数量代替边界证明。

## 6. 本轮交付与实施门槛

本轮已修订的是计划中的四项缺口，不代表这些生产缺陷已消除。复审应逐条检查 C 的最终诊断所有权、B 的实际消费者连接、E 的合同代际规则，以及 E6/E7 不混淆的完成标准。

计划通过后，实施依序提交可审查增量、定向测试与安装态证据，再按实际授权执行现场验证。关闭本次修复必须有 E1—E6 的工程证据以及 E7 的明确现场结果；科学目标未完成时继续保留其真实状态。
