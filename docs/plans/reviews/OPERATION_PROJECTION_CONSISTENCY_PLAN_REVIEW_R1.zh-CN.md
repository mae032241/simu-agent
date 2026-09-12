# Operation 合同投影与纠错一致性计划 R1 独立复审

日期：2026-09-11。总判定：**PASS（计划审查）**。阻断项：0。非阻断实施提示：1。

本次独立检查未发现 R1 尚未覆盖、并足以阻断既定修复目标的可达路径。四项上轮缺口均已在实施要求和验收标准中关闭；这不表示生产缺陷已修复、安装包已验证或真实研究已完成。没有继承旧 R4 的 PASS，也没有将当前工作树的既有改动视为本计划实现。

## 1. 精确对象与审查边界

- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- 审查对象：[修订计划](../OPERATION_PROJECTION_CONSISTENCY_REPAIR_PLAN.zh-CN.md)，R1，共 147 行。
- 计划 SHA256：`6547fbe75d3d7b8a3d257a91e62e0f75688093ef0e39506f042323b40c18c1e1`。
- HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。
- 开始审查时 `git status --porcelain=v1 | wc -l` 为 227；这是既有工作树状态，不是本轮实现范围。
- 审查者未参与该计划编写。应用 `scid-cross-boundary-review` 与 `scid-decision-corpus-maintenance`；只读源码、测试源码和已有证据，只写本报告。
- 未调用控制面或 Worker MCP，未创建科研 Run，未派生 Agent；未运行 pytest、构建、安装、solver 或微型探针。

文档归属如下。本报告不取代规范，不改写历史记录，不宣告实施完成。

| 材料 | 归属与处理 |
| --- | --- |
| [R1 计划](../OPERATION_PROJECTION_CONSISTENCY_REPAIR_PLAN.zh-CN.md) | 当前提案，承诺 A—F 和 E1—E7；本报告只判定这份精确提案是否可进入实施 |
| [架构规范](../../ARCHITECTURE.md)第 67—83、207—224 行 | 当前职责边界；输入准入、输出与冻结证据校验、错误和历史引用规则的规范来源 |
| [投影审计](OPERATION_PROJECTION_AUDIT.zh-CN.md)及 `PROJECTION_*` | 已有缺陷与探针证据；不因本计划 PASS 获得“已修复”含义 |
| 原 R4 及其审查、P6 现场记录 | 保留原适用范围和失败/有限结论，不继承其资格或覆盖原文 |
| [计划索引](../README.md)第 8 行 | 提案入口；本报告不修改索引或计划状态，由主任务维护者处理链接与状态 |
| 本报告 | 绑定上述 SHA 与 HEAD 的独立审查记录；不取代后续源码、安装和现场验收 |

## 2. 阻断项与非阻断建议

### 阻断项

无。现有源码仍存在计划要修复的问题，不能将“尚未实现”重新列为计划遗漏。尤其是回执先截断而回复保留完整诊断、打开回复没有工具合同、Hardened 泛化类型化异常等，R1 都已经明确指定所有者和验收。

### N1 / 非阻断：实施 D1 时保留更具体的既有故障类别

- **计划位置：**第 60、101—106、124 行。D1 要求改变默认失败分类，并为真实检查器异常显式标注 `checker_failure`。
- **源码位置：**`src/scidiscovery/artifact_agent/service/run_outputs.py:34—39` 的 `RunCheckerError` 同时承载 `checker_failure`、`integrity_failure` 和 `admission_defect`；第 247—248 行把已接纳源解析失败标为 `admission_defect`。`service/runs.py:915—918` 区分工作区完整性和候选准备故障，第 526—534、549—553 行已经透传异常类别。
- **可达场景：**提交时已接纳的输入无法按合同解析，或封存工作区完整性校验失败。这些都会经过 `RunCheckerError`，但不是同一种失败。
- **影响：**若把 D1 理解成“所有 `RunCheckerError` 都覆盖为 `checker_failure`”，会抹去现有工程诊断的具体类别。
- **最小建议：**将 D1 的实施解释写成“无更具体类别的检查器错误显式使用 `checker_failure`；已有 `error.category` 原样透传；未分类普通故障默认 `runtime_failure`；明确超时使用 `run_timeout`”。E4 的定向分类检查保留已有 integrity/admission 反例即可，无需新机制。
- **非阻断理由：**计划要求“由明确来源决定”，并未要求删除现有具体类别；涉及的所有者已在范围内。此处是明确实施优先级，未发现必须新增架构或修改科学政策才能满足计划的缺口。

## 3. 四项上轮缺口逐项复核

### 3.1 回复、日志和回执使用最终集合，输出拒绝只记录一次：关闭

**计划依据：**第 35、87—97、123 行。C1 先安全归一化并按实际回执元数据计算剩余空间，C2 返回 attempt 引用与最终集合，C3 不扩展公共引用，C4 对不能保留失败原因的情况明确失败，C5 明确输出拒绝的唯一记录位置。

**源码与可达路径：**`service/tool_evidence.py:208—240` 当前最多取 8 条后再按 4 KiB 删除尾部；`interfaces/mcp_local_worker.py:109—134` 与 `plugins/curve_score/curve_score/analysis_tool.py:296—305` 仍使用传入诊断。MCP 最终错误投影位于 `interfaces/mcp.py:75—90`，直接使用类型化异常的 details；活动日志还经过 `service/runs.py:780—809` 的安全投影。全部实际调用者可通过本计划列出的 service、Local、context 与评分模块完成改动；Hardened 非文件工具复用 Local 调用链（`interfaces/mcp_hardened_worker.py:99—101`）。

`service/runs.py:545—558` 的 `validate_candidate` 已写 `output_rejected` 后抛出，外层 `interfaces/mcp_local_worker.py:202—207` 又写一条无诊断事件；`OperationToolContext.validate_outputs` 和 `candidate_snapshot` 的可达绑定位于 `interfaces/mcp_local_worker.py:299—307、349—351`。C5 针对这条实际重复路径设置进程内标记，不要求移除含义不同的工具尝试事件。

**后续引用闭合：**`service/tool_evidence.py:123—157` 检查终态 attempt、请求摘要、读源身份、结果摘要以及诊断成员关系。复制未入回执的回复诊断会被第 153—155 行拒绝。归档探针确实记录了回复 8 条、回执 5 条和 4,009 字节；本次未重跑。C2 的定稿所有权与 E3 的三处逐字段相等及后续引用验收能直接消除这条反例，同时保留证据核验强度。

**实施验收界线：**须检查通过 `record_activity` 后的实际日志，不能只比较传给日志函数的变量；最终集合在进程内保留安全来源，不能把回读 JSON 当作可信标记。C2/C3 已明确这些要求，所以不另列为遗漏。

### 3.2 升级、历史读取与受控续接协议：关闭

**计划依据：**第 70、82、95、108—115、124—125 行。新旧合同不在旧 Run 内切换；同摘要旧 assignment 可在身份检查后补投影且不改文件；新 Run 显式绑定封存历史；旧请求、默认值省略表示、回执和摘要不重写；回滚使用原包与相应配置。

**源码与可达路径：**`operations/catalog.py:126—148` 冻结工具输入 Schema 并把完整接口纳入资源摘要，第 755—780 行将组件、输出合同等纳入 Operation digest。`operations/tooling.py:101—112` 据此产生 Agent 与 Worker server 名称。`service/runs.py:438—447、1190—1197` 按精确 Operation 身份选 Run 和校验合同，`service/runs.py:1375—1389` 拒绝异摘要的普通 resume。因此 E 的新 Run 和重新生成配置要求具有实际执行依据，不是仅保存一个版本号。

历史 completed 输出在 `interfaces/mcp_root_run_routes.py:98—125` 仍可读取并标为 historical；`operations/input_validation.py:143—193` 使用 prior analysis 与同生产者 manifest 的精确父关系生成局部别名映射，不重新赋予 current 资格。`service/tool_evidence.py:62—158` 消费冻结证明，`plugins/curve_score/curve_score/science_operations.py:699—708` 和 `plugins/tcad_artifact/tcad_artifact/result_analysis.py:388—425` 仅对 computed 记录复算。失败请求不会因新窄模型而被重新执行。

**兼容性判断：**`CalculationRecord.request` 当前是字典（`schema/layered_diagnosis.py:101—112`）；计划明确保留它。`analysis_tool.py:87—100` 保存调用者原始 JSON，结果摘要排除 attempt/diagnostics（`service/tool_evidence.py:57—59`）。新模型只收紧至原本已执行的边界，因此无需迁移旧记录或改变数值算法版本。是否能用某个失败草稿续接仍以已有受控恢复准入为准，计划第 113、115 行没有承诺跨合同继续原 Run。

### 3.3 Agent 实际合同读取入口：关闭

**计划依据：**第 37、51—55、76—85、122、126 行。B 明确一个投影函数、独立 Schema 根和 `$defs`、backend 允许集合、冻结 assignment、两种打开回复及 Codex 读取指引；E6 还要求 Agent 实际读取后自行构造调用。

**源码与可达路径：**`operations/tooling.py:85—91、141—160` 已能提供编译工具接口及生命周期名称；`service/run_assignment.py:20—28、71` 当前只交付名称，调用方 `service/runs.py:317—335` 已有编译对象和 backend 允许名称，不必改变 Workspace backend 接口。`service/local_workspace.py:159—161` 冻结 assignment 与结果 Schema，Hardened 同样通过 RunService 准备工作区。Local 和 Hardened 的实际打开回复分别在 `interfaces/mcp_local_worker.py:242—254`、`interfaces/mcp_hardened_worker.py:178—191`；两者均在修改范围。

`service/local_workspace.py:119—122` 与 `service/hardened_workspace.py:102—105` 声明各自工具集合；`interfaces/mcp_local_worker.py:81—83` 已检查路由器集合。生命周期 Schema 来源为 `operations/lifecycle.py:12—42` 和 `interfaces/mcp_worker_protocol.py:93—96`，不应被误当成领域工具重新注册。B6 保留该来源，领域 Schema 则使用编译冻结值。

Local 原生文件读取与 Hardened 禁用原生读取的差异，在 `platforms/codex.py:454—469、493—509` 明确存在。计划专门规定 Hardened 从打开回复读合同，因此没有依赖一个该 backend 无权访问的文件入口。它也没有把平台内部转换错误宣称为已修复；原 `unknown`/错误数字元组的证据只证明需要这条可读补充路径。

### 3.4 独立数值答案与真实 Agent 同 Run 纠错验收：关闭

**计划依据：**第 123、126—133、147 行。E6 要求无父历史的实际分析 Agent、已注册工具、回执和 sealed output；第 131 行另外要求明确错误后的同 Run 纠正。人工预写请求、模拟 Agent 或有限分析封存都不能替代；无法派发须标未验证，不能关闭修复。

**数值可实施性：**`plugins/curve_score/curve_score/schema.py:209—225` 已声明 `residual_max_abs` 和 `linear/log10`；第 1199—1245 行按采样点求 candidate-reference 或两者 log10 差，再取绝对最大值。计划第 129 行的两端点例子分别为最大绝对差 900 与 1，与这些算子相符，不需改算法或加新算子。实现夹具时以端点采样，即 `evaluation_points=2`；`CurveDomain.min_points` 默认已是 2（第 177—181 行）。这是源码与独立算术核对，本轮没有调用求值函数。

E6 使用隔离工程实例和测试装配的合法材料；现有通用分析入口的最小绑定及 parentage 在 `plugins/curve_score/curve_score/science_operations.py:258—295`，已有测试也展示实际 MCP、错误回执和封存路径（`tests/operations/test_contract_attempts.py:14—40、60—102`）。R1 要求再接上实际 Agent，恰好补齐现有手写请求测试的证据空白。E7 保留真实数据限制与研究目标未完成状态，不以工程数值例子替代真实科学结论。

## 4. 其他审查维度

| 维度 | 判定与依据 |
| --- | --- |
| 缺陷定位 | 准确。计划第 19—21 行区分模型接口丢失、静态上限遗漏与诊断失真，也限制 `$ref` 和平台内部转换器结论；与归档 Schema/模型声明和当前源码一致 |
| 静态边界同源 | 可实施。`analysis_tool.py:69—84` 当前叠加隐藏上限；计划第 68—74 行将其放入分析子类型。TCAD 请求继承 ScoreRequest 和 AnalysisScoreInput（`result_analysis.py:67—76`），不需改通用曲线最大范围；默认值与 raw JSON 保留要求明确 |
| 动态资源预算 | 计划第 71 行保留所有者和共同常量，不将源数据工作量伪装成单字段限制；实际源点、请求字节和乘积预算位于 `analysis_tool.py:92—100、180—187、224—228` |
| 安全纠错 | `operation_contract.py:52—56、98—119、124—159` 已有显式安全关系错误及诊断投影；计划第 72、94 行沿用它，不公开任意异常字符串，不另造规则 DSL |
| 输出不重做输入准入 | 计划第 27、103 行保持边界。`service/run_outputs.py:208—250` 仅调用已声明 context checker；`runs.py:923—932` 提供冻结输入和证明。字段关系与 calculation receipt 的核验是输出声明核验，不是当前资格重判 |
| Root 参数与目录 | 第 103—106 行覆盖共享 DTO 和内部 preflight。实际入口为 `interfaces/mcp_root.py:75—84`、`operations/invoke.py:113—134`；`operations/spec.py:436—454、480—491` 的输入/输出共用视图也已被计划明确要求区别投影，不给输出编造输入语义 |
| 两种 backend 错误包装 | `mcp_hardened_worker.py:80—89` 当前仅保留 WorkerToolError，会泛化其他 DiagnosticError；C6 明确修此路径。正常领域工具和回执不需复制另一套实现 |
| 编译、安装和配置 | 第 110—115、125 行要求隔离安装入口与配置同代；实际插件入口在两个插件的 `pyproject.toml`，`operations/catalog.py:843—844` 从 installed entry points 加载；`platforms/codex.py:270—320、322—391、424—429` 校验工具、模块、Agent 和外部工作区配置。没有把源码导入结果当安装验证 |
| 奥卡姆原则 | 满足。使用现有模型继承、编译投影、进程内错误标记、回执和代际摘要；不新增 Operation、注册表、状态机、评分 Run 或算法版本。修改点可由已确认反例解释；目录补充被明确作为独立小缺陷，不扩大评分失败因果结论 |

TCAD 工具本身有独立 description（`result_analysis.py:500—503`）。实施 A4 时共同预算说明必须确实出现在两份交付合同中，可以放在继承模型的同源说明里；若必须调整 TCAD 顶层工具文案，按计划第 46、64 行记录这个有限依赖后增补范围即可。这不是要求预先修改 TCAD 算法或增加通用工具规则。

## 5. 实际检查、证据限制与后续门槛

实际执行的检查均为只读命令：

```text
git rev-parse HEAD
sha256sum docs/plans/OPERATION_PROJECTION_CONSISTENCY_REPAIR_PLAN.zh-CN.md
git status --porcelain=v1 | wc -l
rg --files ...
rg -n 'finish_tool_attempt|finish_attempt|validate_candidate|record_failure\(|assignment_tool_names|...' src/scidiscovery plugins/curve_score plugins/tcad_artifact
nl -ba <上述源码、计划、审计、测试文件> | sed -n '<相应行段>p'
cat <两份指定 SKILL.md 与下列归档证据>
wc -c docs/plans/evidence/operation-tool-contract-coherence/PROJECTION_*
```

源码追踪包含计划列出的所有生产修改模块，以及 MCP 最终错误投影、生命周期声明、编译器、两个 workspace backend、TCAD 评分与分析 context、通用分析 context、历史证明映射、插件安装声明和已列出的相关测试入口。测试源码只用于确认现有夹具和可达入口，不作为本次测试通过记录。一次 `rg` 使用了不存在的 `operations/*history*` glob，已随后定位并读取真正的 `operations/input_validation.py:143—193`；没有因此遗漏历史映射实现。

已读取的原始证据包括 `PROJECTION_AUDIT_PROBE.py`、`PROJECTION_SCHEMA_FIELDS.json`、`PROJECTION_MODEL_VISIBLE_TOOLS.json`、`PROJECTION_INSTALLED_IDENTITY.json`、`PROJECTION_PLAN_REVIEW_PROBE.log/.json` 和 `PROJECTION_REPAIR_FEASIBILITY_R2.log/.json`。已读审计说明用于确定这些记录的适用边界：归档安装一致性不能证明本次或未来安装仍一致；可行性探针不能证明拟议生产实现完成。没有重跑或修改这些证据。

本次未验证：修改后的 Schema/模型边界、最终诊断三处逐字段相等、真实安装加载、旧新合同混合运行、实际超时、实际 Agent 数值计算与同 Run 纠错，以及 E7 当前研究续接。上述行为均由 R1 的 E1—E7 明确要求，属于后续实施验收，不是本次 PASS 的含义。

资源约束按委托保持：没有启动测试/构建/安装/solver 进程树；只做串行或独立文件读取，未执行计算探针，未测量进程树峰值 RSS，因此不声称完成 512 MiB/448 MiB 的运行负载资格验证。收尾使用 `git diff --no-index --check /dev/null <本报告>`，没有空白问题诊断（新增文件差异退出码 1）；计划 SHA 和 HEAD 复核未变。

**实施门槛结论：R1 可以进入受控实施。关闭修复仍需计划第 147 行规定的 E1—E6 工程证据和 E7 明确现场结果；本报告不代替任何一项。**
