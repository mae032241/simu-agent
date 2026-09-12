# Operation 各消费侧投影审计

日期：2026-09-11。状态：只读工程审计；发现缺陷，尚未实施修复。

## 结论

问题不局限于 Agent 的工具展示。已确认三种失真：完整结构在模型接口中丢失；实际静态约束未进入发布的 Schema；明确的错误事实在诊断投影中被泛化或改错类别。另有 Root 公共参数合同和实际准入不一致。

“一次编译、各处复用”已经减少了重复注册，但尚不能保证两件事：实际执行约束全部进入编译声明；每个消费侧拿到的信息足以完成其职责。此次两点都存在反例。

## 审计范围与证据

- 工作树：`123/scidiscovery-e5.2`；HEAD `2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树已有大量未提交修改，本次未修改生产源码、现有测试或冻结计划。
- 从当前源码编译的 figure 目录共有 50 个 Operation、25 个 Agent；检查了 25 份输出包 Schema 和 9 种本地领域工具 Schema 的引用解析。
- 独立从实际安装目录 `/opt/scidiscovery-m7/site` 加载插件入口，核对 25 份角色配置、26 个 Root 工具 Schema 和 3 个生命周期工具 Schema。
- 源码、安装入口与运行服务公布的目录摘要相同：`adb285db97177f951626220939864f8b899c3c1a0f62422befb256fcd893ecc8`。另外直接比较了 8 个相关源码文件与安装文件，字节一致。
- 当前会话工具声明来自 `ALL_TOOLS` 元数据。安装态 MCP 检查只使用生产路由器的 `tools/list` 路径和无状态后端描述，没有打开真实 Run、调用 `worker_*`、读取未封存科学草稿或启动求解器。
- 两个探针串行执行，用时约 2.66 秒和 1.14 秒，进程树峰值分别约 107.5 MiB、99.6 MiB。未运行全量测试。

可复核记录：

- [源码与行为探针](../evidence/operation-tool-contract-coherence/PROJECTION_AUDIT_PROBES.json)
- [当前模型可见工具声明](../evidence/operation-tool-contract-coherence/PROJECTION_MODEL_VISIBLE_TOOLS.json)
- [安装态 MCP 元数据与配置核对](../evidence/operation-tool-contract-coherence/PROJECTION_INSTALLED_MCP_METADATA.json)
- [安装文件一致性](../evidence/operation-tool-contract-coherence/PROJECTION_INSTALLED_IDENTITY.json)
- [相关字段的原始 Schema](../evidence/operation-tool-contract-coherence/PROJECTION_SCHEMA_FIELDS.json)

探针源码归档为同目录的 `PROJECTION_AUDIT_PROBE.py`、`PROJECTION_INSTALLED_PROBE.py`；资源记录为 `PROJECTION_AUDIT_CHECK.json`、`PROJECTION_INSTALLED_CHECK.json`。

## 已确认的缺陷

### F1 / 高：工具结构在模型可见声明中丢失，且没有完整合同的工作区入口

已定位的链路：

1. `operations/catalog.py::_load_implementation` 从工具输入模型生成 Schema 并冻结。
2. [tooling.py](../../../src/scidiscovery/operations/tooling.py) 的 `WorkerToolDefinition.schema()` 返回冻结 Schema 的投影。
3. `LocalWorkerMCPRouter.list_tools()` 和 `MCPRouter.handle(tools/list)` 保留这些结构。安装态探针也返回完整 `$defs`。
4. 当前会话模型可见声明中的 `worker_curve_score.request`、`worker_tcad_curve_score.request` 都变成 `unknown`，没有展开字段和枚举。
5. [run_assignment.py](../../../src/scidiscovery/artifact_agent/service/run_assignment.py) 的 `assignment_json()` 只投影工具名称；`local_workspace.py::prepare()` 提供 `schema/result.schema.json`，没有工具参数合同文件。角色无法通过获准的工作区读取路径补足工具输入定义。

因此可确定的信息丢失边界是 **MCP 完整 Schema 到平台提供的模型工具声明之间**，框架自身还缺少完整合同的可读入口。安装遗漏和服务端 Schema 引用损坏已被本轮证据排除。

这里必须限制结论：当前 Root `operation_invoke.inputs` 的 `$ref` 能展开，图形预览的对象 `$ref` 也能展开，不能声称平台完全不支持 `$ref`。平台内部转换实现不在此仓库和可读安装 Python 源码中，本轮没有确定其具体转换函数，也没有证明是 `oneOf`、嵌套深度或长度阈值导致评分请求整体降级。

另一个已确认的同类例子是 `worker_curve_figure_preview`：

| 字段 | 服务端声明 | 当前模型可见声明 |
| --- | --- | --- |
| `plot_bbox` / `binding_bbox` | 四个整数的固定长度数组 | `Array<string>` |
| `axis_calibration.x.ticks` 等 | 两组数值坐标对 | `Array<string>` |
| `series[].seeds` | 数值坐标对数组 | `Array<Array<string>>` |

这些字段的 `prefixItems` 在服务端完整保留；消费侧出现了错误类型。它不是本次评分失败的直接原因，但证明问题范围超出评分工具。本轮没有实际调用图形工具，也不声称已复现该工具的生产失败。

影响：Agent 只能通过报错试探参数，或依据错误类型构造参数。评分工具已有 `value_space: linear | log10`，但消费侧看不到这一关键选择；不能把先前未使用该选项归结为算子不存在。完整科学目标能否由现有算子满足，仍需科学角色依据封存输入判断。

### F2 / 高：评分输入的发布上限与实际参数校验冲突

[analysis_tool.py](../../../plugins/curve_score/curve_score/analysis_tool.py) 复用 `CurveComparisonSpec`，随后又在 `ScoreRequest._calculation_bounds()` 中加严上限。这些更严格的约束没有进入该工具发布的字段 Schema：

| 项目 | 发布 Schema 上限 | 分析工具实际上限 |
| --- | ---: | ---: |
| comparisons 数量 | 10,000 | 16 |
| 每个 comparison 的 evaluation_points | 1,000,000 | 4,096 |
| 每个 comparison 的 operators 数量 | 256 | 16 |

合成反例：对合法测试请求只把 `evaluation_points` 改成 5,000。Draft 2020-12 Schema 校验通过；同一请求经 `TCADScoreInput.model_validate_json(..., strict=True)` 被拒绝。拒绝在读证据、计算之前发生。

服务端原始原因明确是“最多 4096 个采样点和 16 个算子”，但投影后只有 `$.request` 和泛化的字段关系错误。`parse_score_request()` 的 12 KiB 请求预算也仅写在运行校验中。

影响：即使把完整 Schema 交给 Agent，照该 Schema 构造的调用仍可能被拒绝。仅修展示或给 Agent 加提示不足以解决这一类冲突。

这些约束属于分析工具的具体边界；修复时应由该调用合同表达其真实上限，不应误改其他场景可合法使用的通用曲线对象上限。

### F3 / 中：输出与工具诊断丢失可修正的具体原因

[operation_contract.py](../../../src/scidiscovery/operation_contract.py) 的 `validation_diagnostics()` 对未显式声明为安全诊断的普通 `ValueError` 使用统一文案：

`Value violates the declared type, bounds, or field relationship.`

在 [layered_diagnosis.py](../../../src/scidiscovery/artifact_agent/schema/layered_diagnosis.py) 中复现：

- `AnalysisSourceReference` 只给 `experiment_key`、不给 `case_key`：原始错误指出二者必须一起声明，输出诊断只剩 `$` 和统一文案。
- `CalculationRecord` 声明 `computed` 却没有 `result`：原始错误指出必须有结果、不能有 reason，输出诊断同样丢失关系。

这两个关系也未编码到上述模型的字段 JSON Schema 中，合成反例均通过该 Schema 而被运行模型拒绝。JSON Schema 本来不必表达所有科学判断，但这类程序可确定的字段关系至少必须通过合同说明或明确纠错诊断向消费者提供。

即时回复和持久化日志如今能保持一致，但一致地保留泛化消息仍不能指导纠错。这不是要求回显任意异常字符串或用户输入；已有 `declared_violation()` / 安全诊断路径可以保留由代码拥有者声明的静态原因。

### F4 / 中：超时在 Run 诊断摘要中被错误分类为校验器故障

实际封存控制记录 `P6_ANALYSIS_FIRST_FAILURE.json` 中：

- `reason = run_deadline_exceeded_after_worker_return_without_sealed_result`；
- `diagnostic_summary.failure.category = checker_failure`。

路径是 `RootRunRoutes.run_record_failure()` → `RunService.record_failure()`。后者的 `category` 默认 `checker_failure`，`timed_out=True` 只检查截止时间，不决定错误类别。`_safe_diagnostic()` 的类别白名单也没有超时，未知类别继续归为 `checker_failure`。

影响：原始 `reason` 仍在，但只消费诊断摘要的调度、排查和统计会把预算耗尽解释成校验器崩溃。该事实并不证明 P6 发生了校验器异常。

### F5 / 较低：Root 公共 parameters 合同允许对象，所有 Operation 的准入却只接受空对象

[mcp_root.py](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root.py) 的 `OperationCallInput.parameters` 声明为最多 32 项的任意字典。`operation_preflight`、`operation_invoke` 共用它。

[invoke.py](../../../src/scidiscovery/operations/invoke.py) 的 `preflight_operation()` 在操作分支前无条件拒绝一切非空 `parameters`，报 `parameters_not_declared`。

探针确认 `parameters={"x":1}` 通过公共输入 DTO，随后在准入中被拒绝。没有创建 Run。此处尚无生产失败证据，但公开参数模型与当前所有操作的支持范围不符；若保留兼容字段，应明确表达只接受空对象。

这是准入阶段的接口问题，不能与“输出提交重新检查输入资格”混为一谈；本次没有据此证明后者复发。

## 其他投影的核查结果

| 投影 | 结果与边界 |
| --- | --- |
| Operation → Root 目录 | 50 个 Operation 的输入名称、Schema ID、数量上下限、必非空字段与声明一致；目录从同一 `scheduler_operation_view` 产生。 |
| 目录端口详情 | `SchedulerPortView` 未包含 `usage`、`exposure`、`require_current`、媒体类型和逐项字节上限，而准入/工作区会使用这些信息。例如设计的 foundation 是 `handoff_only`，current_progress 是 `evidence_inventory/on_demand`。这是可确认的信息缺口；本轮没有将它归因为当前失败或证明已经造成错误授权。 |
| Operation → 输出工作区合同 | 检查 25 份完整 envelope 的 JSON Schema 和局部引用，未发现失效引用；payload 自带 `$id`，不能因 `$defs` 嵌套就判其损坏。字段关系的可读性缺陷见 F3。 |
| Operation → 本地角色/工具名单 | 25 份安装配置的角色工具名单、父会话继承工具名单、后端说明均与当前编译结果相符；未发现名字或摘要漂移。 |
| 工具数值结果 → 检查覆盖 | 独立分析工具调用使 `covered_validation_check_keys` 默认空；最终检查覆盖由 `_actual_check_coverage(plan, report, spec)` 结合请求中的映射、阈值和实际结果重新确认。空字段本身不能证明工具缺失验收能力；仅填写 check key 也不能证明已经执行该检查。未发现应直接把字段自动补满的依据。 |
| 审批对象 → UI → 决策 | 静态追踪中，ReviewDocument 保存对象索引和 JSON 指针，服务验证指针，渲染器读取冻结对象并保留原始对象/下载入口，Root 决策查询读取封存决定。未发现本轮同类信息丢失；未执行真实审批或浏览器交互，不代表整体 UI 验收通过。 |
| 封存结果 → Root 状态 | 状态接口仅在 completed 后读取封存结果，并区分历史合同；本轮未发现需绕过完成门槛或读取草稿的理由。超时诊断的失真见 F4。 |

## 为什么之前的检查没有发现

现有检查能证明工具模型具有 `$defs`、源/安装目录一致、MCP 能按事先写好的合法请求调用成功。例如 `test_score_request_contract.py` 明确检查 `$ref` 和判别器存在。这些都是服务端证据。

但这不能证明模型消费侧仍能读取完整结构，也没有覆盖“已发布 Schema 接受、实际参数模型拒绝”的 5,000 点反例。完整类型进入同一编译对象以后，运行期额外约束和平台转换仍然可能让三者不一致。

## 最小修复方向

1. 工具输入合同继续由当前编译对象拥有，同时提供工作区内完整可读的投影；平台简化声明不能成为唯一读取途径。明确验证当前实际平台中的复杂对象和数值坐标结构。
2. 将可静态表达的工具范围约束放回同一输入合同，使 Schema 和参数解析共享真实范围；保留运行预算检查，并提供具体预算原因。
3. 保留由代码声明的安全字段关系诊断，并让 Run 终止类别忠实于实际原因；不放松科学、身份或执行门槛。
4. 验收补上少量消费侧反例：完整合同可读、Schema 与运行参数范围一致、拒绝能指出字段与修法、超时没有改写成校验器故障。继续用当前研究案例验证可交接性。

本审计仅给出修复范围建议，没有启动实施，也没有改变原实验或科学结论。
