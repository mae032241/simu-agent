# 分析角色内受控检查与补收集修订计划

状态：R1，工程提案，2026-09-10。尚未独立审查、实施或部署。

本轮只制定计划。以当前工作树为实施基线，保留其他任务的未提交修改；实施前保存精确增量基线，不把 HEAD 以来的全部差异计入本计划。

## 1. 目标与决策归属

目标：现有 TCAD 结果分析 Agent 遇到可修复的产物交接问题时，能够在同一受控 Run 内检查实际文件、提出明确映射、补充收集、继续分析并封存证据；不要求为文件名错误重跑计算或增加一个科研阶段。

第一原则：角色承担判断与交付，工具提供任务范围内的纠错能力。取消对话中提出的独立“产物恢复者”Operation；不建立万能修复 Agent，也不默认给所有角色文件操作权限。

| 文档/记录 | 归属及本轮处置 |
| --- | --- |
| 本计划 | 新增能力的唯一活动提案；不代表当前已支持 |
| INPUT_VALIDATION_PHASE_REPAIR_PLAN.zh-CN.md | 保留输入、输出、运行完整性边界；本计划不得重新在提交阶段进行输入准入 |
| HISTORICAL_SIGNAL_ADMISSION_MINIMAL_REPAIR_PLAN.zh-CN.md | 保留历史可读与当前执行资格分离原则；不重写旧计划及审查 |
| CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN.zh-CN.md | 保留评分为分析内可选工具的决定；本计划扩展其可读取的受控证据来源 |
| evidence/historical-signal-r2/REPORT.zh-CN.md | 保留当时的本地验收记录；新增线上事实另记，不覆盖历史结论 |
| docs/plans/README.md | 增加本计划入口和“提案”状态，不借此重整整个历史索引 |

当前案例的封存见证为 M7-test0 / fig4_continuation_execution_analysis_2.output：分析 Run completed，报告指出原执行的 TDR 声明与实际 `_fps.tdr` 名称不一致，注册产物不足。它是修订动因，不是证明 VM 中未注册文件仍完整存在的证据。首次现场步骤必须通过受控工具核实。

## 2. 已核对的工程缺口

1. `remote_runner_py36.py::_collect_expected` 与 `worker.py` 的收集器遇到首个必需产物缺失就抛异常，后续有效文件未收集。运行异常路径用 97 替换原为 0 的退出码，清单没有单独保存求解器退出结果。
2. `execution_control.py::tcad_collect`、远端 collect 只读取原清单；`execution_bridge.py::sync` 对 collected 直接返回。手工改名后同步不能补齐旧成果。
3. `result_analysis.py::validate_analysis_inputs` 按原清单和项目路径匹配文件；没有受控映射凭据时，补收集文件仍会被拒绝。
4. `OperationToolContext` 只有绑定输入读取等能力；`run_score_tool` 只读启动输入。工作区文件本身不能自动成为可引用或可重放证据。
5. `run_outputs.py::validate_run_output` 只接受 `result.json`，`RunService::_register_candidate` 只注册主结果。仅增加下载工具不会形成正式证据交付。
6. 分析输出规则把原 manifest 的 failed/非零退出码整体视为不能通过数值门槛；补齐文件后若不区分求解失败和收集失败，会继续卡住。
7. `LocalWorkerMCPRouter::_open` 将缺失 required_services 作为无法打开任务的条件。新的可选工具不能因此让无 VM 连接的普通分析失去提交有限报告的能力。

上述七处构成一条实际路径；禁止只修其中的文件名或下载环节就宣称完成。

## 3. 最小范围与职责

首版仅让 `tcad.result.analyze.v1` 选择使用该工具，主结果仍为 LayeredDiagnosisReport。通用 `science.result.diagnose.v1`、所有设计/审查角色不新增运行目录访问权限。

author 保持已有源码修订和开发调试权限，本轮只澄清其应核对真实输出名称、需要源码修改时接回任务；不同时为 author 增加历史生产执行读取能力。后续角色如确有同类需要，通过 Operation 显式声明复用工具，不复制角色或扩大默认权限。

不新增公开 Operation、服务进程、Run 状态、审批环节、依赖图、自动重试平台、全局“忽略缺失文件”选项。原 Execution 状态及原失败成果保持不变；补收集记录是新分析 Run 的工具成果。禁止修改原 manifest 或复用旧成功资格。

允许的修复只包括已结束执行的原始文件读取、原样复制、声明与实际位置的明确映射。不执行 solver、shell 命令、源码编辑、文件覆盖/移动、参数调整或计算结果修饰。不凭相似文件名自动决定案例身份。

## 4. 可见输入和工具合同

### 4.1 分析输入

保留现有 plan/review/package/runtime_manifest/solver_outputs/diagnostics/reference/current_progress。

新增可选、类型明确的 `execution_result` 输入，绑定实际执行结果 Artifact，作为检查远端文件的范围锚点。工具需要它；不调用工具的历史/离线分析可以不提供。preflight 在提供时检查实例、原项目、manifest 与 execution_result 的准确来源关系；不访问远端、不预先要求缺失文件存在。

Agent 只提供输入别名。受信任服务从绑定 Artifact 及执行记录解析适配器和原执行目录，不接受模型传入 execution_id、外部 run id、宿主机绝对路径或 SSH 信息。Worker 的领域服务可以通过受限回调使用这些内部信息，Agent 本身不能借此查询控制存储。

为跨轮复用新增可选 `recovery_manifest` 输入。恢复的原始文件仍通过现有 solver_outputs 显式绑定；preflight 按恢复凭据检查其原执行、逻辑输出、实际路径、摘要和案例对应关系。没有凭据时保持原路径检查，不偷偷改绑。不要求当前历史 review 重新获得执行资格。

### 4.2 两个工具动作（实现名在 P0 冻结）

| 动作 | 模型提供 | 返回和效果 |
| --- | --- | --- |
| 检查执行产物 | execution_result 别名；相对目录或已返回的候选键；受限读取请求 | 有界文件清单、缺失声明、候选文件的原路径/媒体/大小/摘要及必要内容；检查用字节同样保留受控来源记录 |
| 接收产物映射 | 候选键、原声明 output_name、映射理由和对应证据 | 重新核验并原样复制文件，生成服务保存的接收记录、稳定证据别名和本地只读副本；不改远端文件 |

检查动作不给出科学匹配建议，不在代码中写死 `_fps`。工具对已提供的声明、文件名和日志做事实展示；模型决定需要检查谁以及是否能接收。歧义可以继续有界检查，也可以直接交付缺口。

结果至少区分 available/accepted、not_found、ambiguous_mapping、changed_since_inspection、unsupported、unavailable、limit_exceeded；给出具体项、原因和剩余预算。工程异常保留原因链，不要求 Agent 通过改写分析文本修复服务问题。

首次检查与后续接收必须对同一候选重新验证，拒绝软链接越界、跨执行文件、不同候选占用同一逻辑输出以及读取期间发生的内容变化。摘要证明所读字节一致，不证明历史上无人改动；对旧执行无法建立的来源事实必须如实记录，不能以“目录相同”冒充历史完整性证明。

工具可选性：增加最小的可选服务声明/注入语义，与现有 required_services 分开。缺失新服务、旧 runner 不支持或 VM 不可达，仅返回工具不可用；不阻止 open、普通评分或有限分析提交。author 原有必需 debug 服务要求不变。

## 5. 同一 Run 内新证据的最小接缝

不改变冻结输入、不把任意 workspace 文件加入 inputs，也不让 Agent 自填摘要等同于工具证明。

复用已有 OutputPortSpec/CollectionSpec 表达可选的工具证据集合及预算；对显式声明该集合和工具能力的 Operation，增加受信任 `OperationToolContext` 证据接收接口。不得顺便实现任意 Agent 多主结果或通用文件上传系统。

受信任接口必须完成以下闭环：

1. 根据已绑定 execution_result 解析只读执行范围；工具回执绑定当前 Run、原执行、原项目、工具合同、实际文件、摘要和映射理由。
2. 已取得字节保存为不可变本地副本，并持久保存接收索引。复用现有 Artifact/CAS 与 Run 保全机制；不能只存在 `_tool_state` 内存里，也不能依靠模型可编辑的工作区 JSON 证明来源。
3. 为证据生成独立别名空间，例如 `tool_evidence_001`。统一的只读解析器接受“冻结输入”或“本 Run 已接收工具证据”，二者来源类型始终可区分。评分、报告引用、动态 schema 投影和重放使用同一解析器。
4. 主结果仍是 result.json。提交时从服务保存的精确证据快照取得附属集合；不接受 Agent 随意放入输出目录的文件。主报告与所引用证据、恢复清单作为同一候选完成，候选指纹涵盖证据快照。
5. 复用既有候选接受和 completed 发布边界。Artifact 写入可幂等，未完成的候选不得通过 Root 成为成功科学成果；失败保留证据及诊断。并发/迟到工具调用不能改变已接受候选。
6. completed 后 Root 返回有界证据目录和稳定语义 Artifact 名称，能逐项查父链并绑定下一轮；主结果保持原有 sealed_output 形式。远端路径、令牌、内部执行标识不进入调度交接。
7. 会话重启可恢复服务保存的索引。失败 Run 的交接复用现有受控保全/draft_from 入口，并重新核对原执行绑定；原始工具副本和接收回执可复核后使用，失败报告本身不成为科学结论。没有可验证回执时保留缺口，不扫描任意旧工作区代替恢复。

这是本轮唯一必要的通用扩展：工具在执行中取得的证据能够受控交付。初始调用者只有 TCAD 分析。未声明的角色、原单文件 Run 和通用诊断保持旧行为；不要求给所有工具加回执或迁移所有历史 Run。

## 6. 分析与评分如何继续

恢复清单同时保留原声明路径和实际路径，不把实际路径改写成原来期望的名称。逻辑输出及 case 仍来自原项目；接收动作不修改科学方案。

同轮工具接收属于一次工具调用的边界检查；以后将这些成果绑定给新 Run 时，才在新 Run 的 preflight 做输入准入。输出校验只核对报告对已接收证据的使用、映射引用、计算重放和结论一致性，不联网、不重做输入资格或工具可用性检查。已接收副本完整性异常走现有工程故障路径。

`worker_tcad_curve_score` 可选读取受控工具证据别名；同一字节解析器用于计算与重放。现有 `source_references.input_alias` 的兼容形式可以保留，但可见合同必须说明其也可引用受控工具证据，不把这些别名伪装成启动输入。优先不改通用 LayeredDiagnosisReport 结构，通过工具证据描述符明确来源类别。

当前 TCAD checker 还把 `text/plain` 与 PLX 解析形式作硬等同检查。P0 必须核对真实首个 PLX 的媒体声明与现有解析器：允许在受控来源上明确选择并成功解析原生 PLX 文本，不伪造原始媒体标签；真实不支持的格式给有限结论，不通过改扩展名制造兼容。该项仅处理本链实际文件到工具的接口，不新增评分算法或补全所有计划指标。

原执行 overall failed 不自动否定补收集后的一切分析，也不自动转成成功：

- 新 runner 记录明确的 solver_exit_code 与 collection_errors，只有后者失败时可在补齐证据后重新评价输出完整性。
- 原 solver 非零、取消、运行未结束，或者运行审计已失败，不因补收集获得求解成功证明。
- 旧记录缺 solver_exit_code 时为 unknown；分析者可引用绑定日志判断具体步骤发生情况及限制，框架不得猜 0。是否足以评价当前科学检查由 Agent 给理由；不能自动继承“求解成功”，也不能仅因旧综合 97 再次一刀切拒绝有限或有证据支持的局部分析。
- complete outputs 只是证据覆盖，不自动等同初始化、数值收敛或假设成立。未恢复项与评分不支持项仍限制对应结论。

## 7. 按顺序实施

### P0：冻结合同与真实失败用例

保存本轮改动前快照；列出两个工具的请求/响应 schema、optional service、工具证据集合、恢复清单与错误归属；输出 Root/Worker/工具/checker 的对照表。新增小型失败夹具：solver 成功，首个 TDR 路径错，后续 PLX/TDR 均存在；同时保留旧 manifest 形状。

冻结“无服务普通分析”“同 Run 接收→评分→提交”“completed 后新 Agent 重读”的最小贯通用例。P0 不跑真实 solver。不得直到提交测试才补工具证据的 schema 和别名规则。

### P1：修正收集事实，开放受限只读检查

本地与 Python 3.6 VM runner 同步修改收集器：继续收集合法项、保存两类结果、汇总有界错误；预期项顺序不再决定哪些现存文件被保留。总预算耗尽时停止并标明未检查项，不绕过资源或路径保护。

新增列出/读取本次已结束执行产物的 RPC，连接 socket/command/SSH 实际路径。原 collect/sync 行为保留，新工具直接走新增只读能力；旧 collected 不重开。扫描只在 Agent 调用时发生，目录/文件数量及时间均受限。

### P2：实现工具证据保存与发布接缝

实现第 5 节的显式集合能力、受限执行解析回调、持久接收记录、证据解析器、候选关联及 completed 发布。先用确定性小文件验证；未启用集合的原 Run 仍只接受 result.json。补全预览/提交一致性、重启、重复接收、失败保全与跨 Run 负例。

### P3：接入现有 TCAD 分析角色

注册两个可选工具和执行结果/历史恢复清单端口，更新角色提示、预算及可见 schema；实现同 Run 接收后继续读取/评分/提交。工具不给科学 pass。遇到源码或物理变化需求，Agent 在报告和 handoff 中说明，再由 scheduler 从目录选择现有 author/design 行动。

### P4：兼容、部署与原案例验收

生成目录摘要差异与旧输入矩阵，检查 core、TCAD、curve_score 安装组合及 Root/Worker 投影。工具增加可能改变分析 Operation digest；旧 Run 不由新合同验收。不能预先承诺全部 digest 不变，非目标行为变化必须解释或消除。

匹配部署控制端、Worker 和 VM runner，保留原执行目录；无需创建新服务。旧 runner 返回 unsupported，安装不能清理待恢复文件。用原案例创建新的 TCAD 分析 Run，绑定原计划/审查/项目/执行结果及已有封存诊断。由分析者检查文件并决定映射，scheduler 不代写文件配对。

验收记录必须区分：已收集事实、工具恢复成功、分析正式 completed、科学目标是否可评价。若原文件已丢失、身份有歧义或预算不够，封存具体缺口，不为完成本计划自动重跑 solver。随后是否修订 author/再执行属于下一项受控科研决定。

## 8. 文件责任范围

以所列职责限定增量，不用虚假的“三文件修复”承诺掩盖必需接缝。P0 将下面的文件组落实成精确文件清单；新增文件只容纳同一职责，不抽象成独立框架。

| 文件组 | 本轮唯一职责 |
| --- | --- |
| tcad_artifact/worker.py、remote_runner_py36.py、project_packager.py | 收集不中断有效产物；新增兼容的求解/收集事实字段；不改物理源码 |
| tcad_artifact/execution_control.py、execution_adapter.py、command_adapter.py、ssh_transport.py | 同一执行内只读检查/复制协议，原传输与摘要规则复用 |
| tcad_artifact/runtime_plugin.py；新增小型产物工具/服务模块 | 可选运行服务、检查和映射接收；不使用 development_debug 启动计算 |
| operations/tooling.py 及相关编译投影；artifact_agent/operation_tool_context.py、interfaces/mcp_local_worker.py | 可选服务、显式工具证据能力及受限回调 |
| artifact_agent/service/runs.py、run_outputs.py、必要的 workspace/record 保全代码；新增小型工具证据模块 | 接收索引、证据解析、候选封存、恢复；保持输入准入边界 |
| artifact_agent/service/executions.py、interfaces/mcp_root_run_routes.py | 从精确结果引用解析执行范围；完成成果附属目录与语义名发布；不重开旧 Execution |
| tcad_artifact/result_analysis.py、curve_score/analysis_tool.py | 新旧证据同源读取、可重放评分、恢复来源和有限结论规则 |
| roles/scheduler.md、对应生成源及角色说明；ARCHITECTURE 中英对应段落 | 明确工具取证例外仍受声明能力约束；科研结论只读 sealed output；不复制流程全文 |
| 安装/runner 同步说明、受影响测试 | 匹配部署与真实入口验证；除确有遗漏，不重写 installer |

不改一般科学 schema、现有审批策略或全局 review/current 规则。若 P0 发现必须改变这些边界，应先修订计划并说明实际缺口，不能实施中悄悄扩大范围。

## 9. 验收矩阵与资源预算

| 场景 | 必须观察到的行为 |
| --- | --- |
| 前项缺文件、后项有效 | 后项照常收集；原 solver 退出结果保留；错误逐项可见 |
| 有效文件名映射 | 分析 Agent 在同一 Run 内检查、接收、引用/评分并 completed；没有 solver 启动 |
| 全部旧输入已够用、无新服务/runner 离线 | 不调用工具也能提交；调用只返回有界不可用 |
| 内容相同但属于别的执行、越界路径/链接、TOCTOU | 拒绝相关文件接收，报告原因；不把问题包装成分析文本错误 |
| 歧义、重复逻辑输出、缺失、unsupported 格式 | Agent 可检查或交付有限分析，不无限原样重试，不推断缺失数据 |
| 旧综合 97、真实 solver 非零/取消、审计失败 | 不伪造 solver 0；恢复不会清除真实失败证据；旧收集失败不硬挡有边界分析 |
| 工具文件被模型改动、伪造接收回执 | 服务记录不接受伪造；完整性故障保全成果，主结果修改不掩盖故障 |
| 重复调用、进程重启、提交中断、迟到调用 | 复用同一摘要副本和预算，候选不漂移；失败材料可受控接手 |
| completed 后启动全新 Agent | 精确绑定恢复清单及原始成果即可重放/分析，不依赖前轮聊天或 VM 临时路径 |
| 非 TCAD、旧单文件角色、author required_services | 行为保持；新证据能力没有成为全局要求 |
| 安装态本地/socket/command/SSH 协议及 Python 3.6 runner | 声明、运行接口、输入/输出规则一致；旧 runner 有明确兼容结果 |

优先扩展 test_collector_analysis_handoff、test_tcad_result_analysis、test_result_analysis_tool、test_analysis_input_descriptors、test_l4_local_tcad 与安装入口测试；只为新工具证据接缝增加必要的小型集成测试。不以字段存在、快照数量或实现镜像断言替代行为验收。

测试串行，完整进程树内存上限 512 MiB（并取 MemAvailable/4 较小者），不用全量/压力测试，不启动真实 solver。文件传输与摘要按块处理，不把整个目录或二进制 Base64 塞入模型上下文。

工具首版预算：每 Run 最多接收 32 个文件、单文件 32 MiB、累计原始字节 256 MiB；元数据/恢复清单 1 MiB、报告保留 128 KiB 独立上限；候选清单最多 256 项、元数据返回最多 64 KiB/次，读取和下载共享 120 s 且不超过 Run 剩余时限。实际限额取原项目、Operation 总量与上述上限的最小值。重复读取也计 I/O 预算，相同已接收快照不重复存储；缺省不截断原始文件冒充完整证据。确有更大文件时报告预算缺口，不自动提高限额。

## 10. 完成标准与非承诺

完成标准是当前研究的实际交接得到改善：在原文件可用且对应关系有依据时，不重跑计算，现有分析 Agent 自主补收集、继续分析并封存可供下一 Agent 读取的证据；不可恢复时准确交付缺口。

本计划不承诺文件一定仍在，不承诺补齐后所有评分算法均受支持，不把一轮局部成功等同总体研究目标完成。只增加纠错手段及其证据闭环，不再增加一个专门处理文件名错误的角色。
