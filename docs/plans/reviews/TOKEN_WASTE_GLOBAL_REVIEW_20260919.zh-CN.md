# 当前 Agent 流程无效上下文全链独立审查

日期：2026-09-19。范围：当前源码工作树（含未提交与未跟踪实现），`HEAD=943c4626f8490530e9318eb9fbb409d2670908b9`。只读工程审查，仅新增本报告；未访问生产实例，未启动 Agent 探针、求解器、测试或部署。实际安装版可能落后于这些源码。

## 审查结论

**下一项应优先修 Worker 的实际读取方式，尤其是大 JSON 经 shell/外层工具截断后又按重叠范围补读。继续削几个 Root 状态字段的收益，不足以代表全链主要机会。** 当前 Root、工具合同、分析入口和 Schema 阅读已有实质改善，不能把历史完整工具表或重复 handoff 当成尚未修复的现状。

目前没有证据支持“所有科研字段都太多”或“统一缩短全部合同”。最强的问题是**同一必要原文被多次消费**；应保留首次足够完整的科学阅读，并减少传输方式造成的重复。静态可确认的其他问题，是日志展示预算沿用留存预算、TCAD 日志提示落后于返回投影，以及同合同复用时无条件重读角色。后两类机会比真实重复原文读取小，不应反客为主。

本报告的优先级不是声称已量化的 token 回报：P1 是有实际样本或明确可达大输出路径，P2 是确定存在但收益须计量，P3 是小范围改进。未做真实 Worker A/B，因此不虚构总体节省百分比。

## 计量与权威边界

优先观察每次请求的实际输入、峰值、每节点净新增和其中无效内容；其次检查信息充分性，之后才比较未缓存输入、输出和延迟。累计缓存反复携带同一前缀，不等于窗口中同时出现多份前缀；缓存前缀仍占每次窗口。工具返回字符不是 token，磁盘文件大小也不等于模型消费量。

最新 `ROOT_COMBINED_READ_SOL_MODEL_AB_20260919.json` 的两个 Root 均为 `gpt-5.6-sol medium`：峰值输入 24000→21009（下降 12.46%），净增长 9852→6569（下降 33.32%）；累计输入 196669→198990（增加 1.18%）不能否认上下文改进。缓存 150784→156928，未缓存合计 45885→42062（下降 8.33%）；返回字符 33395→25332。请求数 10→11 本身不判输赢。该实验 Worker 是确定性 fixture，不能推断实际 Worker 获益。

历史 `OUTPUT_SCHEMA_READING_MODEL_RESULT_20260917.json` 中 Worker full 路径首/末请求 13250/32815、8 请求，sections 路径 13252/24983、6 请求，是分区阅读曾降低末请求约 23.9% 的证据；不是当前所有 Worker 的收益率，更不是尚未修复浪费总额。旧 handoff 实验的大 assignment 工具表也不能跨版本套用。

规范依据已查阅：`docs/ARCHITECTURE.zh-CN.md` 的第 3、4 节和原生权限角色部分；科学设计宪章第 3、5、6、7 节；`SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的 AUTH、LIN、ROLE、EVD、CQRS、EFF；计划索引及其指向的当前修订/历史缺陷入口。R5-M0 账本和 R5_NEXT_ITERATION_LIVE_DEFECTS 已有日期与接管说明，不能用旧开放项否认今天的实现。总体目标、精确原件、独立审查、当前性、科学权限、审批与执行授权均不得因节省而丢失。

## 保留的发现

### F1 · P1：真实 Worker 的必要计划阅读被传输与补读放大

**证据和可达性。** [脱敏原生计量](../evidence/mcp-response-levels/TOKEN_WASTE_LIVE_REVIEW_USAGE_20260919.json)对应 `science.object.review.v1` 的 `fig4_agent_settings_smoke_review_20260919_1`，不是 TCAD code review。记录仅含 usage 和工具文件/范围/长度，不含推理或科学原文：21 个 usage 记录，输入 22521→67196，节点净增 44675，累计 828939、其中缓存 740480。工具调用先 `sed -n '1,99999p' inputs/experiment_plan.json`，返回显示文本 29418 字符，标记原 10787 tokens、截去787；随后 `fold -w500` 分组读计划及其他输入，显示文本31233字符，标记原14208 tokens、截去4208；再重读 `35:70`、`70:110`，分别显示12096、5631字符。原计划本身32159字符/43147字节。首次 inner helper 设较大输出预算，以及后一批每个 helper 的预算，均未防止 `functions.exec` 聚合出口约10000 tokens 的截断。**真正触发补读的是已观察到的聚合出口边界，不是 MCP 字段目录。**

这证明真实轨迹有重复/重叠读取；仍未精确扣除各次截断区与补读区的相交量，不能把后两次全文都算无效。上述显示文本长度也不是净科学正文 token。不能把净增44675全部归因于计划；初始22521没有匹配的裸平台基线，也不能全部算框架开销。

**producer → consumer。** 控制层冻结原始计划并在 assignment 中给 `relative_path`（`src/scidiscovery/artifact_agent/service/run_assignment.py:66`）→ Worker 原生 shell → exec 的返回显示/外层封装 → Worker 后续输入。文件落盘不消耗上下文；打印出来的段落才进入模型。平台启动提示只泛称需要时读取原件和批量必要读取（`src/scidiscovery/platforms/codex.py:341`、`:364`）；没有具体解释单行 JSON 的“按行读取”实际上可能是全文，更没有说明内层 `max_output_tokens` 与外层显示预算的组合。通用计划审查明确要求完整 supplied plan（`src/scidiscovery/general_science_experiment_components.py:111`、`:115`）；首次完整阅读可能是科学必要内容，不能将其一概删除。

**最小建议。** 针对 Worker 原生阅读补充一种明确的使用范式：先定位 JSON 字段与体量；需大部分内容的独立审查可以完整读一次，但将其按实际 JSON 对象或稳定非重叠字节/行窗口分批输出，合理设置最外层返回预算。不把 compact 单行 JSON 交给 `sed 1:99999`，不把任意 `fold` 页当永久语义定位。截断时只补缺失部分，保留已经读到的部分；外层有截断标记时不能宣称合同已经完整读完。少量字段足够时用 Python 标准库选原值并附原指针，不引入新的科学摘要权威或服务器工具。必要的独立读取可合批，但不能为省轮次把无关输入塞进同一大返回。

**必须保留。** 完整目标与当前选择、案例、验证规则、资源判断、延后目标理由、原始证据和定位；不把完整审查退化成只读摘要。不能用“已读账本”强制科研 Agent 接受遗漏，也不要求新科学自证表。

**频率、风险与验收。** 已知一次真实样本，尚不能估计全任务频率。重叠字符尚需依据实际最终显示内容去重；已有配套计量确认两次外层聚合截断，尚不能算出每部分对后续每次输入的精确贡献。验收应复用同一冻结计划、模型和审查任务，比较每次输入、最高输入、重复显示的原文字节及拒绝/漏审情况；不能只测工具调用数。若修改范式导致实质字段漏读，退回原来的完整读取，同时保留非重叠分段。无需新增机械科学校验。

### F2 · P1（路径确定，实际发生率待测）：分析启动器把日志留存上限当成模型返回上限

**producer → consumer。** `plugins/curve_score/curve_score/analysis_workspace.py:50` 要求分析脚本和准备/检查命令优先用可观测启动器；`:52` 声明 `--command` 返回 stdout/stderr。`src/scidiscovery/artifact_agent/service/local_process_observation.py:26` 设每流 `LOG_LIMIT=128*1024`，`:270` 保存有界原始日志，`:274` 同时把最多这 128 KiB 每流写回 shell stdout/stderr。`policy != "analysis"` 的 command 分支则直接转发全部数据。后者只在采用该 policy 的调用者中发生，不能据此称所有分析命令都无界。

磁盘留存是有用恢复证据；转发才可能进入 Worker 窗口，再受平台工具的输出预算截断。128 KiB 是日志留存上限，不能证明是适合模型阅读的展示预算。该路径可被目录打印、宽 JSON、调试打印触发；本审查没有运行命令验证触发频率，也不把 F1 自动归因于此启动器。

**最小建议。** 保持原始日志留存、错误识别、退出码和恢复语义，区分“有意读取文件正文”和“运行计算/检查”。后者默认返回短状态、完整日志路径、字节数、截断/遗漏标记及定位过的错误；按需读选定段。对 `cat` 等有意阅读命令不得无声吞掉正文；应允许明确选择展示预算或使用原生定向阅读。原生直通也不应被包装文案宣称为始终有界。

**保留/验收/风险。** 保留失败原文、错误位置、覆盖不足和全部已保存字节，不截掉诊断唯一证据。用确定性大 stdout、stderr 中部错误、普通短命令三类用例检查展示大小和可回读性；是否再用模型验证取决于实际部署使用量。回滚限于展示策略，不能变更脚本执行、Run 门禁或原始日志。相较减少角色几句话，这条路径的单次体量上界更值得优先关注，但收益仍待测。

### F3 · P2：TCAD author 的日志阅读提示与当前短回复不一致

**精确路径。** `plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md:186` 仍要求轮询读取 `progress.log_tails`，`:192` 称“debug response 的 log_excerpt”。实际公共 debug 调用 `plugins/tcad_artifact/tcad_artifact/plugin.py:202` 转到 `local_debug_service.py:82` 的 `debug_summary`：完整响应落 `deck/reports/response-*.json`，模型回复只含摘要，progress 仅保留四个时间字段（`:91`），并给 `details_path`（`:94`）。工具说明本身已经指向 details（同文件 `:54`），所以不是完全没有正确路径，而是两个被要求阅读的指令发生张力。

**可达消费。** `role_pack.py:11` 将该文件和研究背景拼为角色，`plugin.py:217` 注册 author prompt，`run_assignment.py:59` 写入 assignment，平台指令要求每次打开后读取。每个 author 新 Run 都可遇到；有多少次因此多轮询或读全 response 尚未实测。

**最小修复。** 修改这一段现有文案，统一为状态看短回复，只有真实诊断问题才从 `details_path` 定向读 `/progress/log_tails` 或 excerpt，完整有界日志按 `log_relative_path` 分段。无需改变日志存储、工具或审批。必须保留“不能为取得省略文字重跑 solver”、时间不等于成功和采集覆盖不足语义。验收对照实际返回形状及一份故障回放，确认不再期待不存在的内联字段；风险低，可单独回滚提示。

### F4 · P2：同合同复用仍反复把完整角色写进 Worker 对话

**producer → consumer。** `run_assignment.py:59` 每份 assignment 保存完整 `role_instructions`，`codex.py:341` 明确每个新 assignment 都读；`roles/scheduler/dispatch.md:16` 允许同 Operation/digest/model/effort 的 idle Worker 复用。`worker_connections.py:48` 对相同编译身份和执行 profile 做准入检查。于是同一已保留上下文的 Worker 接新 Run 时，读取相同角色会成为新增工具输出，而不仅是重复计算缓存前缀。

静态读字符串得到 `RESEARCH_WORK_CONTEXT` 为 2272 ASCII 字符；当前 TCAD author 文本 11645 字符、reviewer 7498 字符，`role_pack.py:11` 将其与背景拼接，因此分别为 13917、9770 字符；这是当前源文本规模，不是 token，也不是模型每次必定全文打印的实测量。角色中多数科学规则有价值；问题是相同字节被再次发回。工具阅读回执也明确以新工作区及完整 assignment 摘要作为 scope（`tool_contract_reader.py:123`），不能据旧回执宣称新合同已读；它是合理的失败关闭实现，不应随便移除。

**最小建议。** 先只调整角色阅读：新 assignment 始终重新读取 instruction、绑定/总体目标入口、预算、语言与输出位置；对已确认同编译身份且模型仍保有全文的角色允许复用，变更/丢失/新 Agent 必须全文读。可以使用当前合同身份或精确角色摘要作导航，不新增持久科研状态、不信任“某工具曾读取过”替代模型记忆。工具合同和输出 Schema 的动态证据变化另行核对，不能拿角色不变推出 Schema 不变。

**验收与风险。** 用两个同合同不同绑定 Run 验证减少同一角色重印，同时第二轮确实使用新总体目标引用、inputs、预算/语言；上下文丢失和不同编译身份为必须重读负例。复用可能携带旧不相关历史，导致第二轮峰值高于新 Worker；因此这项不能变成强制复用政策。实际复用次数和净收益未知，排在 F1 后，不建立自动上下文大小准入门。

### F5 · P3：失败恢复详情透传进常规 Root 状态

`analysis_workspace.py:263` 至多保存 64 个 omitted 明细，每个路径至多 240 字符；这些是合理的恢复覆盖记录。`runs.py:1708` 把 `omitted` 和计数一起放进 recovery.coverage，`mcp_response_views.py:58` 的 `run_summary` 原样保留整个 `recovery`。因此失败 Run 的每次 summary 状态读取都可能重复发回这些路径；仅路径字段理论上限 15360 字符，加 JSON 包装和原因，实际量待测。不是无限历史，也不是每个 Run 都有。

最小修复是在 summary 仅保留覆盖状态、saved/omitted 计数、原因分类和现有 detail 入口；精确遗漏清单保留在 detail/原始恢复文件。必须保留“不完整”“原件是否保留”“是否允许恢复”而非只给成功概览。验收含零遗漏、64 个长路径、损坏恢复文件三种情况。独立可回滚投影，优先级低于 Worker 大原文；不改变恢复预算、重试或快照。

## 全链覆盖与已修好事项

| 边界 | 当前生产源码路径与模型可见内容 | 本次判定 |
|---|---|---|
| Root 启动 | `roles/scheduler.md`、`platforms/scheduler_prompt.py`；安装拼常驻规则和条件式 guide 路径 | 已拆分。guide 条件读取，不能因减少轮次一次加载全套；平台系统/开发指令体积另计，不能归为本仓库全部可删。 |
| Worker 启动 | `codex.py:462` profile 只拼原生生命周期和 completion；科学角色来自 assignment | 按 native 权限共享角色已实现，不再每个 Operation 常驻一整角色；剩余重读见 F4。Root 历史应禁 fork，dispatch guide 已明确。 |
| catalog / describe | `mcp_gateway.py:136` 分页名称/用途；`:147` 只取选中完整合同 | 三工具已实现。完整选中合同是权限/科学充分性必要信息。目录不是合同，不能用删 Schema 换少字符；无证据强制一次 describe 多个未来不用的合同。 |
| invoke / preflight | `mcp_root_operation_routes.py:235` 直接配置/准入/创建；`:211` 为可选预检，成功可返回 normalized_request | 已支持直接 invoke；不能把每 Run 固定“双写请求”作为现状。预检请求仅在明确需要时出现，存储而非打印有帮助。 |
| assignment / 总体目标 / 原件 | `run_assignment.py:66` 给别名、端口、usage、exposure、原文路径；精确完整输入在文件中 | 32 MiB 等输入许可额度不是模型常驻上下文。保留总体目标可访问及相关原始进度，不让控制层先裁决科学相关性。 |
| 打开 Worker | `mcp_local_worker.py:405` 返路径、剩余时间、恢复入口；`:427` 工具合同是 path/pointer | 默认 Local 已不内联完整工具表。Hardened `mcp_hardened_worker.py:209` 仍内联合同，但不是默认消费者，不能计作 Local 残留。 |
| analysis-start / domain manifest | `analysis_workspace.py:159` 生成有界索引/逐字摘录；`:191` 端口用途不逐文件重复；24 KiB start 上限 | 已优化。并不证明 24 KiB 全必要；而且只在 Agent 真读取时入窗。相同字段摘录和随后原文有局部重叠，但没有样本时不能按全文件数认定无效。 |
| output Schema | `output_schema_reader.py:120` 必填/所选字段引用闭包，`:131` definitions-only，`:137` 不比全文短则回全文 | 已有实效。阅读不改变提交 Schema。重复 `--field` 可能再带公共定义，但初次必填+后来实际用的可选字段不同，不自动是浪费；先正确使用 definitions-only 与必要字段合批。 |
| Worker domain tools | `diagnostic_tool.py:183`、`analysis_tool.py:321` 用 retain_calculation(summary=True)；`analysis_artifacts.py:38` 限前4比较、各前4指标且明确遗漏 | 大 calculation/request/localization 留文件，回复短指标与可引用 alias。完整记录是科学可重放证据，不能删；不用把所有工具返回一律判定太大。 |
| Worker shell / 命令输出 | 平台原生工具消费 shell 输出；可观测 launcher 将原流落盘并有条件转发 | 尚有 F1/F2；返回长度需从实际外层显示计量。源码单次留存上限不是最终模型窗口预算。 |
| 执行 status / logs | `mcp_response_views.py:38` execution_summary 去 log_tails，给 logs_available/detail；`local_debug_service.py:82` 工程 snapshot 落盘 | 已有摘要/详情分离；F3 是提示不同步。必要错误、solver 状态、观测时间不能省。 |
| collect | `mcp_root_execution_routes.py:468` 返 collection；`execution_collection.py:327` 返回短运行/时间记录，进程日志落文件 | 没有看到默认把原始 solver 产品 dump 到 Root。collect 成功不等于科学成功，不能为省轮次合并状态权威。 |
| submit / 诊断 | `mcp_local_worker.py:315` 只返 state+diagnostics，成功 `:447` 仅小 receipt；`operation_contract.py:193` 最多16条去敏诊断 | 错误是修复必要输入；不是所有重试都是 token 浪费。机械校验代码应有同源可见规则，不能为压缩而隐藏 rule_id/path/fix hint。未全面重审所有领域校验合理性。 |
| checkpoint / 失败恢复 | `runs.py:740` workspace snapshotter；`local_workspace.py:177` 只读 recovery-draft；analysis scratch 有界快照 | 文件快照不自动入模型。保留能避免重做的源码/计算/日志，不应以磁盘规模裁剪；Root 恢复明细泄入常规摘要见 F5。没有新增任意 checkpoint 总结权威。 |
| 正式交付 / Root 读取 | `mcp_root_run_routes.py:159` 仅封存输出可读；index/values/empty 独立；选值32 KiB、导航8 KiB；`roles/scheduler/results.md` 同次状态+所需正文 | 已修好，不应再开“先空状态、再目录、再值”统一流程。已知字段直接取；多数都要时一次全文。状态 completed、结论/局限/矛盾/信号仍必要。 |
| handoff / 重复输出 | `analysis_workspace.py:26` 正式结论一次，finalizer 补机械 handoff；TCAD author gap `:165` 允许不写重复 handoff | 多个角色已去重复，不可把旧实验当今日现场。Critic/EvidenceAudit 剩余摘要是否语义冗余需单独消费分析，未证明可删。 |
| 跨轮复用 | `worker_connections.py:43` 同合同/profile与终态约束，dispatch guide 禁止自审和旧未绑定事实 | 保留独立性与新绑定。F4 可优化同角色重复字节；复用对峰值可能利弊相反，不建议默认无上限延长会话。 |
| MCP 双表示 | `interfaces/mcp.py:57` 同时 content(text JSON) 和 structuredContent | 这是传输事实，尚不能证明客户端把二者都注入模型。Root 提示已经优先 structuredContent、否则只解析 text 一次。需看实际最终显示，不能凭网络双份字节宣称上下文×2。 |

## 尚未证明、不能据此实施的猜想

1. **平台固有启动上下文全部可省。** 系统指令、原生工具协议、skills目录和会话规则并非都受仓库控制。需按模型实际请求拆来源；本审查不建议删除权限与工具说明。
2. **自动持久读取回执可替代模型记忆。** `tool_contract_reader.py:70` 回执只保存最近全文基准，不能证明上下文未压缩；因此 `--full` 回退必要。把它扩成跨 Run 权威会新增复杂度，不建议为此做大系统。
3. **科学流程节点越少越省。** 错误的细分诊断/无信息增益重试可能比文本包装贵，但源码不能判定某次科学决策无用。要用封存的矛盾、结论、局限与实际下一行动做有界审查，不能用固定节点数量替代科学判断。
4. **Schema、role、analysis-start全部重复。** 当前结构分别承担输出规则、角色职责、输入导航；部分重述未必无效。先量实际字段交集与错误率，再决定删哪段，不以文件大为删除依据。
5. **独立审查应沿用作者隐藏上下文。** 不允许。新审查者的首次原件阅读是独立审查成本；只能改进获取原件的方式。
6. **响应摘要就是科学充分性。** status、index、source指针、短指标只用于导航与定位，不能把未看原文的结论当完成阅读。任何省上下文方案必须保留必要精确原件的路径和读取能力。

## 验收缺口

- 当前 Root 小报告 A/B 能通过并且零接口错误，只覆盖该受控 Root 场景；确定性 fixture Worker 没有检验真实阅读、写作或纠错。不能宣称完整 Worker、失败恢复、执行/收集链已经验收。
- 新真实 Worker 样本证明外层聚合截断及补读在生产式路径发生，但它没有同任务修复后的配对结果。F1 的精确节省率、信息充分性变化和模型稳定性尚未验收。
- F2/F4/F5 已有可达源码路径，缺少真实发生频率和各自单独收益；不得相加成总节省量。F3 文案错位也未证明在某次任务中导致额外调用。
- 当前候选源码、生成配置、已安装包和运行中守护进程是否一致未验证；本次无部署或重启。报告判断适用于上述工作树，不替代安装态验收。
- 未进行全领域语义校验器审计，也未重跑任何测试。历史测试和实验只提供其原边界内的证据，不代表这份报告建议已通过测试。

## 建议的最小推进顺序

先在已有真实 review 样本上确认“最终模型可见内容”的截断与重叠量，落实 F1 的非重叠阅读范式；不要另外启动完整科研链。随后仅处理 F2 的计算/检查输出展示分离，并顺手独立修 F3 文案。F4 需要真实多轮复用样本再排实施；F5 是小投影，不能成为新大阶段。所有验证报告分别列 Root 与 Worker 的每次/峰值/净新增、必要信息覆盖、未缓存/输出和时延；不得把少一次调用、少几个网络字节或缓存累计总额当最终成功指标。
