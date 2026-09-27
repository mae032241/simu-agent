# 曲线评分移入结果分析工具计划：独立工程审查 R1

结论：**REVISE**。方向正确，核心工具和封存机制可复用；目前两处跨接口契约尚未闭合，补齐后可以进入实施。这里审查的是工程计划的完备性和可行性，不是科学结论，也不是要求恢复评分独立阶段。

日期：2026-09-09。

## 审查对象与基线

- 计划：`docs/plans/CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN.zh-CN.md`。
- 计划 SHA256：`478ccdca90ab094f1d2c2c7313307fa55c22a1f009130bb81e11f5e39674d822`（父审查任务提供的冻结摘要）。
- HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`；基线包括当前已有工作树修改，不能等同于纯 HEAD 内容。只读检查了实际工作树。
- 计划摘要：删除分析入口的必需曲线合同和评分报告；结果分析 Agent 可直接分析实际输出，按需调用确定性评分工具，将可复算计算记录随单一正式分析封存，再通过现有端口进入下一轮设计。
- 按 `scid-cross-boundary-review` 技能审查；未改动被审计划或生产代码。本次只新增本报告。

## 必须补充的发现

### R1 · P1：分析中才确定的来源映射，尚无可执行路径进入 TCAD 解析 helper 并返回当前 Run

**计划位置：** P2 第 64—78 行、P3 第 82—98 行。

**触发条件：** 分析 Run 只有已登记的原始 PLX／日志及运行证据，没有预先生成的 `curve_bundle`；Agent 阅读结果后决定调用标准残差工具，并在此时确定输出、case 和轴的来源映射。

**实现证据：**

- `plugins/tcad_artifact/tcad_artifact/curve_operations.py:341` 的 `_operation` 声明是 `support` 范围的独立 transform；第 371 行附近的 PLX Operation 接受不可变输入 Artifact，不是分析 Worker 的本地工具。
- 同文件第 93 行的 `bundle_sprocess_plx` 消费绑定 bytes，并由 `_bound_contract` 取得比较声明；移除比较合同后，还必须定义新映射的承载和生产路径。
- `src/scidiscovery/artifact_agent/operation_tool_context.py:14` 的 `OperationToolContext` 提供已绑定输入读取和本地工具服务，不提供追加 Run 输入或调用任意 Operation 的接口。
- 计划 P3 只明确在 `curve_score` 的 diagnosis 中注册评分工具，同时禁止 Worker 调 Root；P2 又要求解析仍由 TCAD 插件负责、不得增加反向插件依赖。现有 scoring 函数 `schema.py:1005` 的 `evaluate_curve_consistency` 接收的是 `CurveBundle` 和 `CurveComparisonSpec`，不能直接处理 PLX。

**影响：** 仅实现这些声明后，“已有 bundle → 评分”能够成立，“原始输出 → 分析时决定解析和评分”仍断开。若以总是提前生成 bundle 来填补，会把解析变成分析前的隐含步骤，并可能再次要求调度者提前决定科学来源映射。评分数值单元测试和预先准备 bundle 的集成测试无法发现此问题。

**最小补充要求：** 在计划中选择并写清一种实际可接线的方案，明确映射由谁形成、哪个已注册接口消费、解析产物怎样在同一分析中被评分和最终复算，以及 TCAD 与 curve_score 的依赖方向。可以使用 TCAD 所有的窄解析工具／已存在的服务扩展机制，也可以明确设计独立的有界数据准备交接；若选择后者，应写明新分析如何取得封存映射和 bundle，并保证不需要评分的分析直接完成。无需新增通用脚本平台或核心状态机。

补一条从原始 PLX 和原始参考材料开始、**不预先注入 bundle** 的安装版 Worker 集成用例；同时验证无解析工具或不适用时仍可正式提交受限分析。明确 manifest、attestation、多 case 原始输出如何计入 P2 的 1—4 件限制；不能默认为运行报告自动包含其所有子 Artifact 的可读 bytes。

### R2 · P2：新分析入口的“确切审查／结果身份”不能仅沿用目前 diagnosis 的上下文校验

**计划位置：** P2 第 72 行、P4 第 110、118 行及验收矩阵。

**触发条件：** 同一实例有两轮结构相似的计划和结果；调用者将计划 A、计划 B 的审查、结果 B 绑定给新分析，或在未调用评分的路径提交一个内部 evidence key 自洽的分析。

**实现证据：**

- `plugins/curve_score/curve_score/science_operations.py:263` 的 `_diagnosis_operation` 没有声明 `guards` 或 `input_admission`；`experiment_review` 目前为 `handoff_only`，未列入第 329 行附近的 `context_sources`。
- `src/scidiscovery/operation_declaration.py:114` 的 `scientific_agent_operation` 默认 `guards=()`、`input_admission=None`，不会因为端口叫 `experiment_review` 就自动建立其与计划的精确关系。
- 当前 `_diagnosis_context`（第 569 行）和 `_validate_diagnosis_against`（第 624 行）主要通过合同、plan digest 和 metric coverage 校验比较语义；新路径删除这些必需输入后，原始执行结果的归属校验需要重新接线。
- `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py:137` 开始的验证确认内部 evidence 引用和门状态一致，不会单独证明某个原始结果属于绑定的实验执行。
- `src/scidiscovery/operations/catalog.py:344` 明确禁止将 `handoff_only` 输入直接放入输出 `context_sources`。若想通过最终 validator 读取 review，必须有意识调整 exposure；也可保留隐藏方式并在 admission/guard 层检查精确 parentage。

**影响：** “保留身份检查”的表述不足以指定新路径的实际保证。评分未调用时也必须检查结果归属；评分记录中 case 名与自报映射一致，不等于与真实执行一致。无需也不应为解决此问题恢复评分合同。

**最小补充要求：** 明确新分析的 exact plan-review 关系由哪一个现有 guard／admission 或新增窄 validator 校验；明确运行报告、manifest、attestation 和实际输出如何关联到绑定计划及 case，哪些只能作为背景证据而不能作为本轮执行结果。为无评分路径补“错轮 review／错轮结果拒绝，合法失败运行可提交”的真实入口反例。可复用现有 parentage 和证据机制，不需要新增全局资格门槛。

## 已确认可行、无需扩大范围的部分

1. **没有新增实验前评分门槛。** 计划第 1 节及 P1 明确禁止检查 evaluator 实现能力和评分配置来阻断 author／执行。TCAD `plugin.py:439` 的 `INITIAL_INPUTS` 中合同与合同审查确实已可选；第 623 行附近的执行输入使用 `reviewed_package`。对已通过路径只增加回归证据是合理的最小策略。
2. **评分可复用底层函数。** `schema.py:1005` 的 `evaluate_curve_consistency` 可在没有总体目标编译和实验前合同的情况下计算显式 bundle/spec，默认报告可为 standalone。无需把 Root 评分 Run 塞进 Worker。
3. **Worker 工具注册是真实能力。** `src/scidiscovery/operations/tooling.py:32` 的 `WorkerToolDefinition` 支持 contextual handler；已有 `figure_worker_tool.py` 展示受控输入读取和确定性工具。注册组件、操作工具引用、语义合同和生成配置仍须同时更新。
4. **单主输出和复算校验可复用。** `run_outputs.py:186` 的 context validator 会收到声明输入的实际 bytes，适合重算记录。应把记录嵌入 `LayeredDiagnosisReport` 的可选字段，保持现有分析 schema/codec 路径；若采用新的外层包装，须同步调整 codec 和下游 reader，不能只改输出 JSON。
5. **下一轮设计端口已存在。** `general_science_experiment_operations.py:36` 的 `_FEEDBACK_INPUTS` 对三个端口使用通配 schema、媒体类型和 on-demand inventory；分析的负面或部分结论不要求新增阶段实体。计划要求工具→提交→下一轮输入的集成测试是必要且恰当的。
6. **兼容和安装方向合理。** 保留旧 Artifact／Operation 历史、更新操作身份及生成 Worker 配置、不继承旧资格、安装后核对真实目录和工具，均与现有编译模型一致。无需为了此修复删除旧评分代码。

## 实施时应明确但不单独阻断计划的事项

- 新原始输入不能直接照搬 curve_score `_input`（`science_operations.py:172`）：它固定 JSON codec、`application/json` 和有限 schema 映射。需采用已有通配 inventory 声明方式，并协调单件／总量 bytes 上限。
- `CurveComparisonSpec` 第 347 行附近要求至少一个 required comparison，而 exploratory diagnostic 不能 required。若首版要支持纯探索请求，应在窄请求适配层处理，不能把探索比较伪标为科学成功门槛。首版明确不支持并返回 unsupported 也符合本计划的有界目标。
- `LayeredDiagnosisReport` 会把 prerequisite 的 inconclusive/fail 派生为 `invalid_study`，不是所有计算失败都可写成 overall `inconclusive`。部分观测不可判与执行数值无效应各有一个合法 payload fixture；保持已有因果约束即可，不要求新增状态机。
- 最终复算需对 computed、unavailable、unsupported 和临时 error 作明确处理；非确定性的超时不能要求第二次必须重现相同错误才能提交。请求数、采样量、输出记录大小和复算耗时需沿用有界原则，避免工具能完成但封存超出 128 KiB 或时间预算。
- 当前旧 `_diagnosis_context` 第 598 行附近还会因可分析 residual failure 强制改走 curve-error diagnosis；新版应明确去掉这一跳转要求，旧显式操作可保留兼容。

## 核查范围与验证边界

已核查计划全文、工作树状态及上述 diagnosis 声明／提示关联、比较模型和评分入口、TCAD normalization 声明与 parentage、TCAD author 和执行输入声明、WorkerToolDefinition／OperationToolContext、目录编译约束、最终提交校验、LayeredDiagnosisReport、下一轮设计 inventory，以及 curve_score 包入口声明。

未运行测试、未启动安装版服务、未调用研究 Operation／Worker 工具、未运行求解器、未验证真实 UI 授权或续研结果，也未读取科学 Worker 草稿。因此本结论是**源码支持的计划可实施性审查**，不是已完成工程验收或生产行为证明。R1、R2 补齐后再审；其余事项可作为实施验收清单，不要求提前实现额外统计能力。
