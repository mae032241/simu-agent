# 输入校验阶段最小修复计划

日期：2026-09-10。状态：待实施、待独立计划审查；本轮无源码实施授权。依据同目录 reviews/INPUT_VALIDATION_PHASE_INDEPENDENT_REVIEW.zh-CN.md 的静态审查。本文给定一个实施方案，不表示测试通过、部署完成或科学研究完成。

## 目标与不变量

在 Worker 创建前拒绝冻结输入中的确定性矛盾；同一输入检查在提交时复核；可修输出仍允许重写；固定输入故障不进入重复改稿。真实 collector 的合法求解器产物和附加日志能够进入有限分析，伪造字节、跨执行产物、错误案例仍失败关闭。

不改变四态 Run、独立审查、人工执行批准、历史资格、不可变 Artifact 和 exact current。评分仍由分析者选择，不前置 curve contract、评分器或完整科研目标覆盖。仅改变 TCAD 分析本次确定的输入规则，不批量迁移其他 validator。

## 框架责任模型与抽象边界

本次不是给 tcad_log 放行，也不是把某个报错提前。宏观问题是同一个消费合同缺少“冻结输入是否成立”的第一类责任，且错误被按最终出现的位置分配给输出作者。按三个相互独立的维度组织合同：检查依赖什么（冻结输入/候选输出），何时执行（准入/提交复核），谁能修复（重绑或框架/本轮作者）。阶段不替代责任；提交阶段仍可能发现不可修输入故障。

因果链为：框架责任模型 → 同目录声明的纯输入规则与共享执行入口 → 明确错误归属与工程摘要 → TCAD 首个消费者迁移 → 真实生产消费交接验收。同类 Operation 后续只声明输入规则并提供纯函数，无需在 Root、RunService 或 Worker 路由新增领域分支；本次不猜测并迁移另外所有角色的科学前提。

纯输入规则仅判断由已冻结字节及受控元数据可确定的结构/身份成立性；证据是否足够、选择何种分析方法、如何保留未完成目标以及科学机制是否成立仍交科学 Agent。缺科学证据可以产生有限结果，不能被新槽概括成统一“不准执行”。生产者声明与消费者用途不要求一一同名：诊断和数值产品可来自同一执行家庭，但消费语义应明确、可检验。

## 1. 一个输入检查槽，复用既有目录

修改 `src/scidiscovery/operations/spec.py::OperationSpec`，增加末尾可选字段 `input_validation: InputValidationSpec | None = None`。这个窄声明仅含 validator（ComponentRef）、rule_id（稳定编号）、description（模型可见的输入规则说明），不引入规则图或独立注册表；默认使用全部显式绑定输入，不增加另一份 required_inputs 列表，端口自身拥有基数和可选性。一个 Operation 先只支持一个组合纯输入 checker；它内部可以调用领域纯 helper，不设计动态规则编排。

`InputValidationSpec` 是 Operation 内的值对象，没有独立生命周期或持久化。它的校验拒绝未知 component、空说明、非法/重复 rule_id，并明确不得将可选端口缺失解释为输入合同失败。

不新增 component kind；组件仍用已有 `validator`，调用约定为 `(sources) -> None`。`operation_declaration.py::scientific_agent_operation` 增加同名关键字并传递。TCAD 声明首个 input_validation，其他 Operation 不声明则无新字节检查。rule_id 是该阶段稳定工程定位；错误细分使用 code/port/field。三个字段分别绑定执行实现、机器定位、模型说明，均有实际消费者，不沿用科学输出规则的 output_paths 来伪装输入规则。

`operations/catalog.py::_validate_operation_contracts` 将该引用纳入 _resolve_component(kind="validator")、引用闭包及 callable 检查；`_build_compiled_catalog` 的可达组件摘要包含其 configuration_identity/resources。组件错误、缺失引用、错误 kind 必须编译拒绝。输入错误使用声明的 rule_id 和稳定工程 code/port/field，不借用带 output_paths 的科学 SemanticRuleSpec 来标注输入位置。编译器验证 rule_id 格式和 description 非空，并从这一处声明生成目录与 model-visible validation contract 的 input_admission/integrity_recheck 阶段；`operation_contract.py::operation_output_validation_contract`/`operation_port_json_schema` 的合同投影和 `service/run_assignment.py::assignment_json`/`result_schema_json` 的 assignment/schema 文件引用消费该投影，不手写第二份规则。原 output semantic contract 仍拥有候选输出规则；不得把 input_validation 的 rule_id 附在 $.payload 下。

新增小模块 `operations/input_validation.py` 放共享输入投影和调用函数。把现有 `service/run_outputs.py::InputBindingDescriptor`、`ValidationSources` 原样迁移并从旧模块重新导出，避免 invoke → run_outputs → invoke 导入环；不复制两份类型。已有 `OperationInvocationError` 同样移到该无反向依赖的小模块并在 invoke.py 重新导出，保留原类型与构造签名；否则共享输入执行器引用 invoke 的异常会重新形成导入环。共享描述符追加默认空的不可变 parent_refs/labels 投影，以便提交复核同执行诊断来源；已有必需字段和 output_name 不改。输出上下文仍只收到显式 context_sources 的子集，输入 checker 仅可见本 Operation 显式绑定文件。

共享 `validate_operation_inputs(compiled, sources)` 只运行声明组件。正常返回 None；插件确定的绑定拒绝抛已有 `OperationInvocationError(code, port, field)`，如 `input_manifest_output_mismatch`；未知异常转 `input_validator_failed`，不携带任意异常文本。缺读取器、非法 descriptor、字节/大小/摘要不符分别给稳定输入错误。不得抛 SemanticRuleViolation；该异常若误从输入 checker 出来，按插件故障处理。

必要性：现有 guard 无字节上下文，输出 context validator 需要未来 payload；已有 required_non_null_fields 不能表达跨文件身份。只加这一窄槽，不改 guard 签名，不允许域代码直接读控制存储，也不新增 MCP 命令。

## 2. 接入所有实际入口与完整性复核

1. `operations/invoke.py::preflight_operation` 在端口/预算/guard/现有内容检查后，为声明 input_validation 的 Operation 构造同源描述符并用现有 read_artifact 读受控原字节，调用共享检查。先限制元数据总量；读取后逐项核验真实字节数与 ref.sha256。读取失败闭合为 OperationInvocationError。避免在两个检查阶段重复长期持有原字节；不用跨请求缓存、准入 token 或持久化“已验证”标记。
2. `mcp_root_operation_routes.py::_prepare_operation_call` 现已传 self.artifacts.read；保持 operation_preflight 和 operation_invoke 共同进入它，不各写 TCAD 分支。直接 invoke 不依赖用户先调用 preflight；同一冻结请求和同一存储状态得到相同输入拒绝。preflight 不创建 Run，invoke 在创建前失败。
3. `service/runs.py::RunService.create` 在创建 run_id、冻结/插入记录和工作区副作用之前，基于 Artifact catalog/read 重建本次输入投影并调用同一 checker，覆盖直接服务调用/手造 BoundOperationCall。catalog 的 ref/media/size/父链/labels 必须与传入绑定一致，不信调用者复制的 labels。保留 artifacts.verify 和现有 current/资格/恢复检查，不用新 checker 替代它们。
4. `RunService._validation_inputs` 继续从原 Artifact 存储读，不信 Worker 工作区输入副本；补齐共享 descriptor 元数据。`run_outputs.py::validate_run_output` 在解析/评价候选 payload 之前调用同一 input checker；因此直接 pure validator 调用与 Run submit 都覆盖。准入异常在这里明确转 RunCheckerError，保留安全 code/port/field 供终态摘要，禁止降级成 RunOutputError。`_identity_context` 的输入部分不再由 analysis_context 首次检查；可在上下文中重用纯解析结果/同一纯 helper，不能复制规则或信准入缓存。
5. `submit` 的 RunCheckerError 仍走 record_failure 和既有工作区清理；`validate_candidate` 也必须对输入/检查器故障结束失败或通过其服务边界的同一终止处理，不把固定输入故障返回成可修预览。输出 Schema/引用/计算/结论不合规保持 RunOutputError → rejected → running。accepted candidate 后重试、完成幂等和 CAS 冲突不得降级为新候选或再次登记。

不承诺任意 preflight 成功就一定产出可通过的科学结果；保证的是此处已知、仅依赖冻结输入的前提不等到作者提交才发现。提交重读用于防篡改、存储缺失及版本/实现故障复核，仍然必要。

## 3. TCAD 求解器产物与诊断的唯一接收方案

只修改 `plugins/tcad_artifact/tcad_artifact/result_analysis.py` 的 INPUTS、analysis_parentage、_identity_context、_check_source_identity、analysis_context、PROMPT/SEMANTIC_CONTRACT 和 COMPONENT_SPECS/OPERATIONS。

增加可选 `diagnostics` 端口：0–1 项，opaque Schema、text/plain 媒体族、on_demand evidence_inventory，单项至多 32 MiB，计入现有总输入预算。当前仅接受已登记逻辑名 tcad_log。这是 TCAD 插件内部的收集协议规则，不向核心添加 tcad_log 白名单。

`analysis_parentage` 保持 plan/review/package/manifest 原精确父链要求，并对 diagnostics 验证：与 runtime_manifest 完全相同的 request/package 父链、非空且相同的受控 execution_id 标签、logical_name=tcad_log。输入 checker 利用 descriptor 再复核这些身份与真实字节。无 execution_id、错误标签、跨轮日志、同字节但异父链均拒绝；不按文件名猜身份。可选 runtime_attestation 的精确 package/manifest/solver_outputs 父链要求保留；不追溯要求旧 attestation 包含新 diagnostics 输入，因为诊断不作为求解器产品认证。

solver_outputs 每项必须有 output_name，且存在于 manifest.outputs；保持媒体、大小、哈希和项目声明路径的精确匹配。package.expected_outputs 的显式案例必须存在于原 plan。缺少 required 输出不作为输入拒绝；它仍在报告阶段限制完整通过。manifest 中无项目案例映射的真实输出仍可供有限分析，但不可冒充有案例的计算来源。

diagnostics 可在报告 source_references/evidence 通过 alias 引用，用于解释执行失败。禁止其声称 output_name/experiment_key/case_key 或作为计算 request 的 sources；违反者是可修输出错误。需要参与数值分析的 solver log 必须是 manifest 声明的 solver_outputs，并有显式案例映射。reference_material 保留参考证据用途，不充当新的执行身份通道。

把 `_identity_context` 的纯输入条件抽到 `validate_analysis_inputs`/共享纯 helper，改抛输入异常；analysis_context 保留报告计划身份、引用、计算重放、科学 gate 和 incomplete/unmapped 结论限制。更新端口说明明确 tcad_manifest → runtime_manifest，manifest.outputs → solver_outputs，附加 tcad_log → diagnostics；错误放入 solver_outputs 时前置拒绝，绝不自动重新绑定或改写原请求。

diagnostics 端口是生产消费边界上的领域语义，不是框架为日志开的豁免：所有合法输入仍先过同一 input_validation，再在提交复核。反例 tcad_log 放进 solver_outputs 仍拒绝，证明该迁移没有掩盖框架职责。

不修改本地/远端 collector、TCADRuntimeManifest、ExecutionResultManifest 或已登记 Artifact；无需再次跑求解器。现有 `executions.py::ingest_result` 的受控注册足够提供诊断身份，无需第二份收集清单或新 Artifact 类型。

## 4. 有界工程摘要与生命周期

修改 `service/runs.py::_initialize` 给既有 run_activity 表追加可空 `diagnostic_json TEXT`，使用 PRAGMA table_info 检测迁移，并在事务中幂等执行。不是改写历史活动。`record_activity` 增加可选诊断参数，output_rejected 活动与 last_activity_at 继续同一事务/CAS 写入。拒绝次数从 output_rejected 行 COUNT 派生，不在 runs 再存镜像计数；最新摘要按 recorded_at 和 rowid 稳定排序。

摘要只存受控枚举 `category`（output_validation/input_contract/checker_failure）、稳定 code、编译规则 id（若有）、声明 port、经过校验的静态 field、retryable_in_run、时间；单条最多 1 KiB。禁止存 raw message、input alias 中外来文本、payload 值、内部 execution_id/hash/path、堆栈或科学 verdict。动态 JSON key 路径统一投影到安全结构路径；不依靠简单截断。原详细可修错误仍只给 Worker。

`RunService.submit` 在 RunOutputError 路径写安全摘要。RunCheckerError 复用 `record_failure` 写稳定的安全 reason，不将子异常任意文本放 Root；失败原因本已持久化，不需再加 runs 列。record_failure 的 CAS/终态 fencing、恢复策略和清理保持原语义。诊断写入与拒绝确认原子：并发 loser 不计为一次成功登记的拒绝；重复已完成 submit 不增加计数。

在 `RunService` 增加内部 `rejection_summary(run_id)` 查询，Root `_run_status_value` 添加 rejection_count 与 last_rejection；run_status/run_list 复用该投影，无新 MCP tool，无科学信号。旧记录可给真实累计次数和 last_rejection=null，不能伪造历史原因。终态 input_contract/checker_failure 的 retryable_in_run=false；输出拒绝为 true，不等价于科学有进展。

摘要类别表达框架修复责任，任何 Operation 的输出拒绝都可复用，不依赖 TCAD 错误文本。此追加列是必要且足够的持久化改动：旧表没有原因，纯投影无法恢复。无需持久化输入检查结果、单独故障表、新队列、新重试状态或 8 次特殊阈值。

## 5. 合同摘要、已有记录与部署兼容

显式更新 TCAD 分析组件 configuration_identity 和 Operation 版本；新的输入槽语义应提升 OPERATION_ABI_VERSION（当前 17，实施基线若变化使用下一个值），将 core 与相关插件作为同一版本集合安装。编译摘要变化必须可见，不尝试保留旧 digest 假装兼容；ABI 提升可能影响全目录历史判定，应在发布说明明确，并测试历史读取仍可用。

不修改旧 Artifact、Run、批准或 manifest 字节，不给旧 Run 继承新合同。已完成旧 Run 仍由 Root historical sealed_output 路径只读；新分析使用新语义名称或明确 create_revision，重新 preflight 现有受控执行产物。是否可在新目录下作为输入由现有 historical usage/qualification 规则判定，不专门豁免旧 review/package。若资格确需补齐，停在现有明确门禁而非重跑求解器或伪造审查。

升级前记录目录摘要并排空本地 queued/running 分析；不可用新校验器续跑旧 digest 的活跃 Run。安装验证使用真实 wheel、entry point 和 compile_installed_catalog，确认新增组件被加载且 Root/Worker 生成配置来自同一代。远端 runner 无协议变动；安装探针覆盖升级另立问题，本次不改 deploy 脚本及其他 12 个接口。

## 6. 实施顺序与定向验收（本轮未执行）

1. 先补可独立运行的失败用例和真实 collector 交接 fixture；修正 test_tcad_result_analysis.py 的旧 helper 参数调用，使用现有 produced producer/reviewer fixture，不手工伪造审查资格。
2. 实现共享输入描述符/validator 槽、目录编译和三处调用边界；TCAD 输入规则前移和诊断端口同时落地，不能只提前拒绝却没有合法日志入口。
3. 实现安全活动摘要、追加列迁移和 Root 投影；更新对应合同说明，做独立代码审查后运行以下定向检查。
4. 使用 tests/README.md 的低内存约束，单进程逐文件/明确 node id 运行（不 xdist，不一次运行全套，不重新跑实 solver）；每个进程上限 8 GiB，fixture 原字节用小文件。测试命令由实施时真实环境锁定，不使用此计划虚构运行证据。

必需验收矩阵：

| 路径 | 正例与负例 |
| --- | --- |
| 编译 | input_validation 默认空兼容；引用缺失/kind 错拒绝；配置身份变化改变 digest；installed wheel 能加载；目录/assignment/schema 中规则编号与说明同源，输入位置不标成 $.payload |
| 真 Root preflight/invoke | 同请求合法通过；额外 tcad_log 误入 solver_outputs、缺 logical_name、清单哈希/媒体/案例错配，两入口同 code/port 拒绝且零 Run/工作区 |
| 直接 RunService.create | 不经 Root 的无效 BoundOperationCall 仍拒绝；伪造 label 与 catalog 不同仍拒绝 |
| 提交完整性 | 准入后受控存储字节/注册元数据故障导致 failed，不输出可修改拒绝；Worker 工作区副本不替代原输入；validate_candidate 同归属 |
| 输出相对输入 | 错 alias/case、诊断冒充数值来源、计算篡改仍可修拒绝；失败执行被写成通过拒绝；合法有限报告完成 |
| 持久化/恢复 | 旧表迁移与重启，拒绝计数、最新摘要、无草稿泄漏；CAS 冲突不双计；completed 重交幂等；旧 digest 不被新 Run 继承 |
| 真实生产交接 | 下述 collector → ingest_result → execution_outputs → preflight/invoke → submit，全程不是手造 manifest.outputs 配对 |

复用/扩展 `tests/operations/test_tcad_result_analysis.py`、`test_analysis_input_descriptors.py`、`test_catalog_compile.py`、`test_catalog_negative_cases.py`、`test_catalog_installed_entrypoint.py` 和现有 Run/Root 路由测试；共享准入可单设一个聚焦 input_validation 测试文件，不趁机扩大历史测试体系。按用例切片执行，必要时另起进程释放目录/fixture 内存。

真实交接验收：小型受控本地进程产生一个声明 solver log/小产物并完成终态；必须调用生产 tcad_collect 和 ingest_result，再用公开 execution_outputs 的语义名称绑定分析输入。追加 tcad_log 不进入 manifest.outputs，但以 diagnostics 绑定可完成有限报告。另做失败终态和 required 产物缺失的有限报告正例，以及跨执行同字节日志负例。远端 `_collect` 用现有协议测试入口的小型受控目录验证相同输出分类，不需要 SSH/许可证/真实 Sentaurus。公开分析创建和 Worker 提交走真实服务或现有 MCP harness，完成后 Root 只能读封存结果；不把 helper 单元调用当成整个交接验收。

后续若需要在实际研究实例验证，仍须用户授权范围内选择现有执行产物和新分析 Run，走正常 preflight/独立资格门禁。工程集成通过不等于六案例目标已完成，也不授权新执行。

## 7. 非目标、回滚与未解决事项

不做通用依赖图、统一异常大重构、其他 12 个接口治理、部署探针、文档索引清理、科学对象改写、前置评分、自动重绑或自动重新运行求解器。原报告 F6 只保留独立待办。

回滚单位为完整 core+插件安装集合及生成配置。先停止/完成新版本活跃 Run，再还原匹配版本；保留数据库和新追加列（旧 INSERT 明列三列可继续工作），禁止回滚时删活动或修改旧 Artifact。新 digest 产生的记录在旧安装中仅按既有历史规则读取；不得恢复旧批准或令旧程序处理新活跃合同。迁移前备份只用于工程灾难恢复，不以覆盖运行中数据库方式撤回科学事件。

实现方案无待用户二选一的接口决策。尚未解决的是验证事实：测试能否通过、摘要是否零泄漏、实际旧实例输入资格是否可直接用于新分析，以及安装后的准确目录摘要。它们分别由以上验收和公开准入决定，不能由本次静态计划保证。实施须另行获得授权，本计划本身仍需独立评审，不自授 PASS。
