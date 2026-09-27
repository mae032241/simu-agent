# Operation 与工具契约一致性实施记录

执行依据：R4 计划，SHA256 `e705e70dbf21a32c227adc3d6088afbe69ac80001f4fe2070ac671c05de06e1f`。用户已授权开始实施。计划正文保持送审原文；实施状态由本记录拥有。

当前：P0—P5 的工程实现及定向、隔离安装检查已完成；[独立实现审查](../../reviews/OPERATION_TOOL_CONTRACT_COHERENCE_IMPLEMENTATION_REVIEW.zh-CN.md)已 PASS（限定工程增量/P5），必要阻断 0 项。P6 已完成安装/绑定核对及失败 Run→同一 Agent 新 Run 的受控接续，有限分析已封存；原计划所需定量归约与下一轮设计/审查仍未完成。现场发现参数展示、部分诊断和分析能力缺口，详见 [P6 现场报告](P6_REPORT.zh-CN.md)。BASELINE.json 与 BASELINE_STATUS.txt 冻结了实施前的完整工作树与摘要，本轮增量相对此基线计算。此前改动不计为本计划成果。

检查一次只运行一个进程树，预算 512 MiB，提前终止超过保留余量的进程树；不跑全量或 stress。真实部署与科研验收另列，不以源码测试替代。

## 实现对应表

| 项目 | 唯一来源与编译投影 | 消费者及已删除副本 | 正负例证据 |
|---|---|---|---|
| C1 | 原 OperationSpec、WorkerToolDefinition.input_model、输出资源；CompiledOperation 缓存冻结工具与输出合同 | catalog、assignment、Root/Local/Hardened、submit 读同一投影；删除 facade 的不同 strict 参数解析及重复静态输出构造 | 静态无自身摘要、review/provider 身份保留、动态别名隔离、单工具模型改变贯通两种 Worker；补充输入端口/输出声明经真实 Root/Worker/提交贯通，submit 不重新准入 |
| P1 | ContractDiagnostic 与错误产生处显式安全详情；既有 run_activity 与 ToolEvidenceManifest | MCP 与三个 stdio 外层共用安全信封；即时提交诊断与持久详情一致；删除任意异常文字透传、错误分类的 catch-all 回退 | 参数拒绝在读取前形成 attempt；64 项预算、冻结后不可写、未知 checker 为工程故障；请求/code/phase/attempt 伪造拒绝 |
| P2 | 共用 CurveComparisonSpec/CurveAxis/SProcessSeriesSpec 的类型化请求 | 两个评分工具及重放使用同一声明；删除手写 allowed-key/轴结构和大段 JSON 描述；原 request 不补默认值 | CSV/PLX/log 正例；错误轴、比较结构、未声明算子、格式、选项在参数阶段拒绝；旧 computed 数学结果不变 |
| P3 | CaseMappingBasis、单一 resolve_case_mapping、清单完整 ArtifactRef、prior_analysis_sources | 工具/正式报告共用案例核对；旧别名仅存在隔离重放视图；删除当前命名空间历史别名合并与重复清单猜测 | 有依据的未声明 case 可计算；明确 case 不能覆盖；A→B→C；同字节不同身份、错配清单拒绝；旧 records 回退仅用完整身份 |
| P4 | LayeredDiagnosisReport 与三个 Operation 自身权限，共用实际检查覆盖函数 | 删除全局门顺序和结论级联；删除 evidence.source_key 输入别名枚举；预计算 Schema 禁止新增计算 | 同一输入两项计算使用独立证据键并正式提交；真实失败可解释限制但不能支撑决定性成功；无 objective_key 也必须真实完成必需检查 |

独立审查发现的失败续接缺口通过既有清单的可选、非递归 recovery 部分闭合：保存原 request/operation/draft 身份与冻结 bindings/attempts；报告的 proof_kind 区分 current/recovery。原 attempts 不并入新 Run，原文件不重新登记为新生产者。实际见证已覆盖失败 A→完成 B→普通后轮 C，当前 scoring Operation 的恢复预算只允许一次失败接续，不增加递归恢复机制。

公共诊断接通后，已安装输入 checker 中直接抛出模型错误的旧路径暴露出来。给既有 parse_bound_json 增加明确 admission_port，仅在输入 checker 中将 ValidationError/UnicodeError 投影为输入错误；输出默认仍为 BoundSourceError，未知运行异常仍为工程故障。涉及 general_science 及 TCAD parameter/curve 的调用接线是 P1/P5 全目录一致性的必要消费者，不增加另一套准入。

TCAD 两个 normalizer 仅把原点数上限异常分类为有界资源错误，不增加格式或数学算子。mcp_proxy 的外层错误接入同一诊断，属于实际 Root stdio 消费路径。安装脚本、求解器、claim 投影与科学历史未作本轮修改。

## 最终检查结果与限制

- `p3-p4-final-boundary`：102 通过、4 个旧夹具预期失败；覆盖当前计算、原文件恢复、旧清单兼容、失败续接后的第三轮正式提交。后续 `p3-consumer-expectations`、`p3-background-repair` 及 `p5-public-source` 中对应项已修复；原失败日志保留。
- `p5-public-source`：248 通过、10 失败。编译未知工具引用的 KeyError 已修正；3 个明确输入格式错误及编译负例在 `p5-admission-parser-and-catalog` 的 154 通过中复验。
- 其余 6 个 L5 失败源于原 blind CSV 审查者要求 native shell，Hardened 无该能力，Root 正确拒绝其生产者。`p5-baseline-hardened-witness` 在冻结原工作树复现同一失败。这是已存在的夹具不适配，不通过删除审查或放宽权限修复；相同原因的安装夹具不作为本轮新代码成功证据。
- `p4-generic-and-dynamic-errors`：6 通过，含真实 Local/Hardened Run 的单工具模型改变、MCP 正负调用与持久诊断；不以旧夹具失败否定这份实际边界见证，也不声称 Hardened 总体科研流程已通过。
- 首轮 `p5-installed-wheels` 的 36 失败全部发生在 import scidiscovery 前缀：保护脚本 PYTHONPATH 使 pip 看到源码元数据并跳过 wheel。`p5-installed-clean-env` 清除该环境变量后 33 通过、3 失败；已修正 Local stdio 见证缺少启动参数、旧工程错误字符串断言，以及真实 author 调试诊断被过滤掉的静态 $.deck 字段前缀。没有为此改安装器。
- `p5-installed-final`：**36 通过、1 排除**。从独立 wheel 安装运行，覆盖两套完整目录身份、通用/TCAD 分析、曲线工具、恢复、stdio、Transform 与批准后的 Effect。排除项是上文已复现的旧 Hardened blind CSV 夹具；不声称所有后端科研流程通过。
- `p5-declaration-and-safe-paths`：13 通过、2 个新增见证夹具失败；通过项保留动态输入错误及 protocol 秘密值不泄漏的负例，真实 author 诊断恢复明确字段。新增见证随后修正未使用的组件声明，`p5-declaration-final`：**2 通过**，覆盖仅改变输入端口或输出声明后 catalog/preflight/assignment/MCP/submit 同步，并以提交时输入 checker 已禁止为证确认 submit 不重做准入。
- `p5-final-inventory`：最终默认 45/figure 50 项，数量保持；受公共编译材料影响，摘要分别变化 45/50 项，Agent 类型分别变化 22/25 项。Root 的 26 项、lifecycle 的 3 项工具 Schema 未改变，共享解析与诊断接线变化已有真实入口见证。准确旧/新身份见 CONTRACT_IDENTITY_DELTA.json；两份 INSTALLED_*_CATALOG.json 与最终源码逐项相等。

检查文件逐项保存 command、退出码、时长、整个进程树峰值 RSS 和是否因内存终止。不同组有重叠，不将通过数简单相加作为独立覆盖数。最高已观测峰值约 245 MiB，无内存终止；未运行全量/stress。仅用于环境探查的 `p5-installed-isolated`（pytest --help）不计为测试证据。

工程封存时尚未部署，也没有开启新科学 Run；该历史事实保留在 FREEZE.json 与独立报告。后续用户已安装并绑定，真实分析及续接记录另列 P6_REPORT.zh-CN.md。两项 computed 结果不符合原计划定量定义，不能以本地 pytest 或任意数字替代 P6 验收；没有重跑求解器、代写分析或修改旧科学 Artifact。

## 早期执行日志（历史快照，当前状态以上文为准）

工作树冻结 1161 个路径，约 43 MB；存有可恢复归档。通过 Root instance_current、run_status 和 artifact_catalog 读取了原 completed 分析与直接父名，科学历史保持原样。LIVE_BASELINE.json 是受控状态响应的快照，不是新科学结果。

目录盘点实际完成：默认 45 项、figure 50 项。C1 已将工具定义和输出基础合同缓存于既有 CompiledOperation，工具参数/能力纳入原摘要，保留输出源投影版本；别名从冻结绑定独立实例化。Root/Local/Hardened 参数解析统一为严格 JSON 模型语义。

C1 首组目录 84 项通过。后续入口组 117 项通过、3 项失败：一项发现旧投影版本摘要遗漏，已恢复；两项是新增见证的适用范围/测试审查权限，已按实际声明修正。后续一次别名断言误匹配 secondary 文本，已改为精确 JSON 值断言并通过。Local/Hardened 的单声明改变→真实 MCP 调用/展示/身份均通过，静态不可变与动态隔离通过。检查峰值至今约 161 MiB，未触及预算，原失败日志保留。

P1 公共诊断正在实施。当前实际 MCP 与工具错误持久位置见证已通过；仍需完成可信尝试、清单快照及所有相关消费者。一次旧测试在编译后手改 CompiledOperation.spec 导致合同视图未变，测试已改为从修改后的原声明重新编译，待复验。不是允许运行时绕过编译身份的理由。

上述旧输入测试修正后已通过。P1 的模型验证前尝试、无原文件时清单封存、终止后不可新增、64 项上限与 interrupted 事实、未知输入校验器异常经真实 MCP 返回工程故障共 3 项通过；加入普通单文件 Run 的接线回归共 4 项通过。所有新检查仍由唯一保护进程串行执行。

P2 由一个独立执行者修改评分请求声明及对应测试；该执行者禁止运行测试，检查由父进程统一调度。P3 已移除当前输入空间内的历史别名合并，增加同生产者/直接父清单的精确配对及只读旧别名映射。7 个配对正负例通过；首次失败仅因新测试错误填写 ArtifactRef 字段，已修正，日志保留。跨轮正式提交、科学案例映射与失败重放仍待后续验收，不以这 7 项声称 P3 完成。

## 精确增量与回退材料

IMPLEMENTATION_FILES.json 以 BASELINE.json 的已冻结工作树为原点，不以 HEAD 归属其他未提交改动；IMPLEMENTATION.patch 保存同一增量。最终独立实现报告与本 evidence 目录不参与该增量自身摘要，避免审计材料自引用。封存摘要、文件数量、独立检查结果和包摘要见 FREEZE.json；计划原文摘要保持不变。

ROLLBACK_BEFORE.tar.gz 仅保存本轮变更路径的原字节，新增路径由 ROLLBACK_MANIFEST.json 明确列出；可与精确补丁恢复本轮之前的工作树，不覆盖此前改动。INSTALLED_WHEELHOUSE 保存实际通过最后隔离安装组的四个生产包，测试夹具包不作为部署包。这里没有安装或修改运行服务；部署前还应沿现有安装流程保存实际服务版本/配置。回退只涉及代码和配置，绝不删除或重写科学记录，也不把新合同 Run 伪装成旧合同。

封包核对沿用既有 build_git_release.py 的文本导出规则：当前 catalog.py 的两处行末空格在导出时规范化，其余包内可对应源码字节逐项核对。封包脚本首轮将此既有规范化误判为字节差异并中止，修正核对层后重验；未为此修改源码或构建器。

## 安装后进度

用户确认已安装。通过运行服务摘要与生成配置核对，figure 目录摘要及 25 个 Worker 类型与已审查候选一致。Root instance_current 返回 unbound，必须先由用户通过其精确本地管理页绑定已有实例，才继续真实科学动作；本次没有创建新 Run。FREEZE.json 和独立报告中的未部署状态是封存时的历史事实，本段与 P6_DEPLOYMENT_CHECK.json 拥有最新安装进度，P6 仍未完成。

## 本轮现场结论

fig4_continuation_execution_analysis_4 超时失败并保留恢复材料；analysis_5 通过新预检，以新 Run/预算复用同一编译 Agent，最终 completed，包含原失败尝试和两项真实计算。封存分析为 inconclusive，缺少原计划所需的精确定量归约，故未开启下一轮设计/执行，P6 未通过。当前重点转为已观察的分析能力、参数可发现性与部分诊断缺口；本次仅补充状态/证据文档，没有修改已安装生产代码。

## 归因更正

进一步源码核查确认现有算子已支持 value_space=log10；已封存请求只选择 log10_y 插值，遗漏算子的值空间与阈值。因此“工具缺少对数残差算子”的先前概括不成立；本次实际计算未满足原计划仍属事实。应先解决完整合同可读性及具体诊断、正确调用并核对既有能力，再界定真正缺失的运算。见 P6_REPORT.zh-CN.md 顶部更正，旧封存 Artifact 未改写。
