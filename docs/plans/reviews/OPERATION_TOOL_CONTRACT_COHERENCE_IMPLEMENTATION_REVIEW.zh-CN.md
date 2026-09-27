# Operation 与工具契约一致性：独立实现审查

结论：**PASS（限定本报告列出的工程增量与 P5 边界）**。必要阻断 **0 项**。本结论不表示 R4 全部工作完成：P6 尚未部署、尚未验收，现有 Hardened 夹具限制也未被本次修改消除。

审查日期：2026-09-11。审查者独立读取源码、增量、测试源码和父级保存的检查日志；未运行 pytest、项目导入、构建、安装或求解器，未调用科研/Worker/实例工具，未读取原科学产物。只写入本报告。依据为 `scid-cross-boundary-review` 的跨边界审查要求，授权范围为工程实现审查。

## 1. 精确审查对象

工作树：`123/scidiscovery-e5.2`。增量相对实施前冻结的完整工作树计算，不相对 HEAD 归属此前未提交修改。

| 对象 | SHA256 |
|---|---|
| [R4 计划](../OPERATION_TOOL_CONTRACT_COHERENCE_REPAIR_PLAN.zh-CN.md) | `e705e70dbf21a32c227adc3d6088afbe69ac80001f4fe2070ac671c05de06e1f` |
| [BASELINE.json](../evidence/operation-tool-contract-coherence/BASELINE.json) | `44aeb87f8f934c3765907ff5416001e652c64159b97cef93a74dc6ccccd937e2` |
| 原工作树归档 `/tmp/scid-contract-baseline-6cbppox7/worktree.tar.gz` | `399b18d84a5b4cea1ef8bccee4bbb76b7e919c525c9f7af26b5464cf13f77591` |
| [IMPLEMENTATION_FILES.json](../evidence/operation-tool-contract-coherence/IMPLEMENTATION_FILES.json) | `1b25a06762bb1c615b790454691d26195eeb38142e700daafca2cf956e899323` |
| [IMPLEMENTATION.patch](../evidence/operation-tool-contract-coherence/IMPLEMENTATION.patch) | `e3524659761845ceb8c3f058397519dc444c966018c407eddcae3ee7686d1c13` |
| [FREEZE.json](../evidence/operation-tool-contract-coherence/FREEZE.json) | `4e2260cc4d54ff15156ec57b47a6f25821bdeeabe476253d8020065ad8e7f9d3` |

审查者重新计算了以上摘要，并逐项核对增量清单的当前文件摘要；55 个路径均匹配。清单包含 35 个生产路径、17 个测试路径、3 个文档路径。最终报告及 evidence 目录明确排除于增量摘要，避免自引用。临时增量 `/tmp/scid-coherence-increment.patch` 与封存补丁摘要相同。

本报告重点追踪 C1 编译与消费、P1 诊断和尝试收据、P3 原始来源与历史重放，以及 P4 中与失败证据/共享分析消费者有关的边界；不把这一范围扩展为全部科研算法、全部后端或框架的穷尽审计。

## 2. 源码审查结论

### C1：单声明、现有编译产物及入口接线

- [catalog.py](../../../src/scidiscovery/operations/catalog.py) 的 `_load_implementation`、`_resource_digest`、`_build_compiled_catalog`（第 109、137、712 行）将引用工具模型和输出静态材料冻结到既有 `CompiledOperation`，工具参数、能力与 `record_attempts` 进入既有身份材料。未知工具引用通过 `_resolve_component` 给出编译错误，不再在端口循环中裸抛 `KeyError`。
- [operation_contract.py](../../../src/scidiscovery/operation_contract.py) 的 `compile_output_contract`、`operation_output_validation_contract`、`operation_port_json_schema`（第 423、448、458 行）先编译不含自身摘要的静态内容，再注入只读身份；Run 别名只进入新生成的动态视图。未发现摘要自循环或跨 Run 污染共享缓存的路径。
- [tooling.py](../../../src/scidiscovery/operations/tooling.py) 的 `parse_tool_arguments`、`operation_worker_tools`（第 94、141 行）为各 Worker 入口复用既有声明和统一严格 JSON 解析。Root 与 lifecycle 继续拥有各自既有声明，没有伪装成科研 Operation，也未增加第二注册表或通用运行时规则编译器。
- [新增声明见证](../../../tests/operations/test_compiled_declaration_consumers.py) 经真实 Root preflight/invoke、Worker assignment 与正式 submit，分别只改变输入 `min_items` 和输出 `required`，核对目录/Schema/身份/行为同步。它在成功准入后禁止再次调用输入 checker，后续提交仍完成；该负控直接覆盖“submit 不重做输入准入”。

### P1：公共诊断、安全详情与可信尝试

- [mcp.py](../../../src/scidiscovery/artifact_agent/interfaces/mcp.py) 的 `parse_rpc_line`、`rpc_error` 已接入 Local、Hardened、Root proxy 的 stdio 外层。畸形 JSON/非对象请求不再绕过统一错误信封；未知异常不透传原文本。
- `validation_diagnostics`/`sanitize_diagnostic_details` 只保留显式进程内 `DeclaredDiagnostic` 的安全原因；一般 Pydantic 自定义 `ValueError` 采用静态类别说明，动态字典键经过过滤。审查实际发现的单位值、参数名等插值异常不能借原始 `msg` 泄露。`DeclaredDiagnostic` 不是客户端可提交的 wire 权限字段。
- [operation_workspace.py](../../../plugins/tcad_artifact/tcad_artifact/operation_workspace.py) 第 74 行 `_protocol_error` 先用所属模型 Schema 净化位置，再加固定 `$.deck` 前缀；核心 sanitizer 对这类已净化的进程内详情保留位置。无需在核心加入 TCAD 字段白名单，`$.deck.entrypoint` 的可修复诊断也不再变成 `$[key].entrypoint`。
- [run_outputs.py](../../../src/scidiscovery/artifact_agent/service/run_outputs.py) 与 [runs.py](../../../src/scidiscovery/artifact_agent/service/runs.py) 的提交/活动记录接线保留输出 payload/context 的实际阶段及受控规则说明，即时响应与持久详情使用同一归一化结果。
- [input_validation.py](../../../src/scidiscovery/operations/input_validation.py) 第 196 行 `parse_bound_json` 仅在所有者明确传入 `admission_port` 时把已知格式/模型错误归入输入准入。已核对 general science、experiment、TCAD parameter/runtime author、curve diagnosis 及 TCAD `validate_analysis_inputs` 的必要调用者；输出调用默认仍为 `BoundSourceError`，未知 checker 异常仍是工程错误。
- [tool_evidence.py](../../../src/scidiscovery/artifact_agent/service/tool_evidence.py) 第 188 行 `begin_tool_attempt` 在工具模型验证前记录受控尝试，并受 64 项总量、冻结后不可写、终态和快照约束。`record_attempts` 未借 `evidence_ports` 开启额外原文件读取或登记权限。

### P3/P4：失败来源、双清单、跨轮重放及结论限制

- `tool_evidence.py` 第 62 行 `calculation_sources` 按明确的 current/recovery 证明和当前/配对历史清单选择隔离来源视图；检查完整 ArtifactRef、实际读取 bindings、请求/来源摘要、终态及返回证据。相同字节不能替代不同身份，历史别名不合并进当前命名空间。参数拒绝/中断作为失败事实验证，不为重放而重新执行坏请求。
- `input_validation.py` 第 143 行 `prior_analysis_sources` 保留已完成 prior analysis 与其直接父清单的同生产者配对。显式错误清单不回退猜测；旧清单仅在没有 `bindings` 字段时从 `records` 恢复完整身份，并要求该身份确为清单父输入。
- `tool_evidence.py` 第 376 行 `recovery_tool_proof` 通过已有 draft/resume 身份和冻结恢复目录校验原始证明；submit 不读取 Worker 可编辑的恢复副本。新增 `ToolRecoveryProof` 为单层、可选、有限结构，原 request/operation/draft 身份及 attempts 保留在 recovery 内，不伪造成新 Run 的 current attempts。
- 第 466 行 `adopt_tool_evidence` 保留原记录及原 ArtifactRef。TCAD 恢复核对移除“原文件 producer 必须等于后轮 manifest producer”的错误等式后，仍检查精确收据、直接父关系、execution 与文件声明。完成 B 并不把失败 A 的原文件重新登记或重新授予资格。
- 失败 A → 恢复 B 完成 → 普通 C 绑定 B/清单的正式提交已有实际测试路径；C 从 B 的单层 recovery 部分验证 A 的事实，不需要把旧失败 Run 当作已完成 prior analysis。当前评分 Operation 的恢复预算没有要求无限失败链；现有非递归结构与实际声明相符。
- [result_analysis.py](../../../plugins/tcad_artifact/tcad_artifact/result_analysis.py) 第 362 行 `analysis_context` 按规范 `calculation_records:<key>` locator 识别计算证据，不把独立证据键误当记录键或输入别名。实际失败可支持 `not_evaluable` 等限制说明；共享分析校验及决定性门/claim 消费仍要求真正完成的定量结果。预计算入口不能凭新增计算记录或仅“覆盖 required 项”冒充成功。

以上输出路径核对冻结输入和证据的身份/关联事实，没有重新执行完整输入准入、当前头资格、批准或预算授权。需要动态授权的既有调用门仍留在原调用阶段。

## 3. 本轮审查中已关闭的问题

| 曾发现的接通缺口 | 最小修复与闭合依据 |
|---|---|
| stdio 外层畸形请求丢失公共诊断，或透传异常文本 | 三个真实 stdio 入口共用解析/错误信封；安装后的 Local、Hardened、proxy 负控与后续有效请求通过。 |
| 已知非法输入被新的工程异常边界错误分类 | 既有解析函数增加显式输入所有者参数，必要消费者接线；不恢复 catch-all 准入。154 项复验通过。 |
| 新编译端口循环对未知工具裸抛 KeyError | 在原组件解析入口解析；原负例重新通过。 |
| 失败 draft 尝试在下一轮及再下一轮失去可信证明 | 单层 recovery 证明保留原始身份；失败 A→完成 B→普通 C 的正式提交通过，伪造 current 证明被拒绝。 |
| 旧清单别名、采用原文件身份与失败限制消费者不一致 | 完整 ArtifactRef 回退、保留原生产者、规范 locator 分派；历史重放、同字节异身份与失败支撑决定性成功的负控保留。 |
| 安全过滤连同所属工作区静态字段一起删除 | 所有者先净化、再添加固定前缀，核心只信进程内标记；author 字段诊断与动态秘密值负控通过。 |

未保留新的必要阻断，也不建议为本次修复增加第二注册表、递归证明树或新的准入阶段。

## 4. 已观察的验证证据及其范围

下列测试由父级执行，审查者读取了源码、日志及 command/退出码/进程树内存元数据；未自行重复运行。不同组有重叠，不累计通过数作为独立覆盖量。

| 证据 | 观察结果与能支持的结论 |
|---|---|
| `p5-declaration-final` | 2 passed；输入/输出单声明变更经实际调用与提交接通，submit 不重准入。 |
| `p4-generic-and-dynamic-errors` | 6 passed；Local/Hardened 真实 Run 的单工具模型变更、MCP 正负调用、持久诊断及独立计算证据键。 |
| `p5-admission-parser-and-catalog` | 154 passed；已知输入格式错误、未知组件、可信尝试及通用分析消费者的修复复验。 |
| `p5-declaration-and-safe-paths` | 13 passed / 2 夹具失败；安全详情与 author 路径见证通过，新增声明夹具随后修复并由 `p5-declaration-final` 通过。 |
| `p5-installed-final` | 36 passed / 1 deselected；隔离 wheel 的目录身份、分析/恢复、实际 stdio、Transform 与已批准 Effect 相关边界。峰值进程树 RSS 234946560 B。 |
| `p5-final-inventory` | 默认 45 / figure 50 项；目录身份对照材料记录源码与安装态一致。Root/lifecycle 保留既有工具 Schema。 |

`p3-p4-final-boundary` 原日志为 102 passed / 4 failed，不能写成全绿；四个失败项分别由 `p3-consumer-expectations`、`p3-background-repair`、`p5-public-source` 中后续对应结果闭合。可信失败证明、失败后第三轮提交等关键正负例已直接读取测试源码。早期安装组受 PYTHONPATH 干扰而在导入前失败；清理环境后又暴露的三个安装问题已修正，由最终安装组重新验证。没有将这些早期失败日志删除或冒充通过。

冻结记录列出实际安装验证所用四个生产 wheel 和 159 个源文件的包内字节核对，以及原构建脚本对 `catalog.py` 两处既有行末空格的规范化。审查者核对冻结记录身份，但没有自行解包并重复这 159 项比对。[ROLLBACK_VERIFICATION.json](../evidence/operation-tool-contract-coherence/ROLLBACK_VERIFICATION.json) 记录父级在临时目录以原字节归档加精确补丁重建，55 个路径均匹配冻结后摘要，未修改生产工作树；本审查读取该记录，没有自行执行回退。

## 5. 保留限制与未验证事项

1. `p5-public-source` 的 6 个 Hardened 夹具失败及最终安装组的 1 个排除仍保留。它们涉及 blind CSV 审查者要求 native shell 而 Hardened 缺少该能力；冻结原工作树的 `p5-baseline-hardened-witness` 复现同一拒绝。新的真实 Local/Hardened MCP 见证足以支持本次契约接线结论，不支持“全部 Hardened 科研流程已通过”。没有为通过测试删除生产审查或放宽能力门。
2. 未运行全量/stress、真实部署、服务重启、求解器或 P6 科研交接。测试与本报告不能替代隔离 Worker 在实际受控记录上自主计算、封存，以及下一轮设计和匹配审查。
3. 未对所有算法数学定义、所有历史版本数据及未触及插件做穷尽审计。非递归恢复证明仅按当前声明和有限恢复预算评估；将来若增加多次失败续接，需要对新增可达链单独验证，不能据本报告自动扩大能力。

在以上明确范围内，冻结工程增量没有尚待修复的必要问题，可进入 R4 已授权的后续部署准备及 P6 验收流程；是否完成真实科研交接须另有受控证据。
