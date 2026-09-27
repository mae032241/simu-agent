# R5-M2-02 曲线分析与诊断边界实现独立审查

日期：2026-09-01

结论：**PASS（通过）**

阶段门：**仅放行 M2-03**。本结论只确认 R5-M2-02 当前候选；不把 M2、R5-M、真实模型科学效果、
论文图证据产品面或最终真实 Agent 纵向验收宣称为完成。

## 1. 审查范围与独立性

本审查者未参与 R5-M2-02 实现。本仓库当前 `baseline/8765-codex` 工作树包含大量早于本候选的未提交
和未跟踪修改，且 M2-02 文件没有一个可从 Git 直接恢复的独立阶段基线；因此本报告没有把整棵工作树
相对 `HEAD` 的差异误称为 M2-02 精确差异。候选范围由计划、实现证据、M2-01 已审查物理基线、当前
符号及真实调用路径共同限定。

完整阅读并交叉核对了：

- `docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`；
- `docs/plans/evidence/R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_EVIDENCE.zh-CN.md`；
- `docs/ARCHITECTURE.zh-CN.md`、最小设计宪章和 33 项约束登记；
- 曲线插件 README、单一插件入口、`analysis.py`、`science_operations.py`、评分/绘图既有实现；
- 唯一目录编译、preflight/invoke、Transform 输出规范化和 Artifact producer-family 投影；
- Run v1 assignment、Local Worker 提交、输出 context validator 和知识 reducer；
- M2-02、目录安装、后端能力、平台配置、Run/独立审查和约束结构相关测试。

审查使用 `scid-cross-boundary-review`、`scid-change-scope-checks`、`scid-find-simplifications` 和
`karpathy-guidelines` 的只读审查规则。除本报告外，没有修改生产代码、测试、计划、实现证据或既有
文档，也没有调用 SciDiscovery Root/Worker control-plane MCP。

## 2. 阻断项

**未发现阻断项。**

## 3. 所有权边界判断

### 3.1 确定性分析和绘图已经归 support Transform

`science.curve.error.analyze.v1` 在
`plugins/curve_score/curve_score/science_operations.py:900` 声明为 `catalog_scope="support"`、
`executor.kind="transform"`。它消费计划、两个独立审查、曲线合同、完整 Metric 报告和曲线束，输出
一个 `CurveDiagnosticAnalysisPackage` 及 1—8 张 PNG。目录投影、preflight 和 invoke 都消费同一
`CompiledOperation`，没有第二 profile 表或领域专用 Root 分支。

机械计算复用 `plugins/curve_score/curve_score/analysis.py:184` 的既有 `analyze_curve_error`：先按精确
计划/合同重算评分并逐字节比较 Metric，再定位残差、分段和调用原有绘图函数。生产源码中只有一个
`analyze_curve_error`、一个 `evaluate_curve_consistency` 实现和一个曲线误差渲染实现；没有观察到为
本候选复制第二套评分、插值、残差或 PNG 算法。

`CurveConsistencyReport` 仍只表达可重放的 Metric、冻结阈值检查和
`deterministic_metrics_only_no_physical_interpretation` 边界。Transform 不生成
`LayeredDiagnosisReport`、hypothesis assessment、remaining contradiction 或 next action。
`_validate_diagnosis_against` 对目标键、计划摘要和完整检查覆盖做事实一致性校验；科学 gate、解释、
假设判断和下一行动仍来自 Agent。Metric 因而没有直接成为科学 verdict。

### 3.2 诊断 Agent 是一个输入、一个输出

当前编译合同精确为：

```text
输入  curve_analysis_package  1..1  scidiscovery.curve-diagnostic-analysis.v1
输出  layered_diagnosis       1..1  scidiscovery.layered-diagnosis.v1
```

见 `science_operations.py:410`—`:447`。输入包虽然包含可复算所需的计划、合同、Metric、曲线束和残差
报告，但只通过一个显式文件交接，限制为 12 MiB；输出只允许一个 128 KiB 结果文件。编译工具闭包只有
Run 生命周期和通用文件提交能力；`worker_curve_analyze`、图片原生查看和 Agent collection 均不在
合同中。Local 后端可运行，Hardened 仍因既有 `native_shell` 原型边界失败关闭，没有伪装成已解决。

输出在 `science_operations.py:632`—`:710` 重新解析整个分析包并校验精确计划、曲线合同、Metric 报告
和完整 validation plan；包模型自身又在 `analysis.py:283`—`:310` 重放分析。真实 Local Worker
提交后，只有通过同一输出 Schema 和 context validator 的 `LayeredDiagnosisReport` 才登记为不可变
Artifact。测试中的 Agent 内容由 fixture 写入，不证明模型科学准确率，但真实 Run 生命周期闭合。

## 4. 集合闭合、不可变登记与篡改负例

本候选没有声明一个实际上不会运行的 `CollectionSpec.bundle_validator`。曲线集合闭合是
`science_operations.py:713`—`:753` 中可信插件 Transform 的活动代码：生成包和命名 PNG 后，在返回
通用调用器前检查总大小，并调用 `validate_curve_error_plot_collection`。该函数在
`analysis.py:327`—`:354` 精确检查项目名集合、PNG magic、SHA-256、格式、1200×800 尺寸和 Pillow
完整性。随后通用 `CompiledTransformAdapter` 按编译端口校验每个输出的 Schema、媒体类型、单项大小
和基数，Root 再以同一个 invocation fingerprint、全部精确输入父引用和输出端口标签登记 Artifact。

把集合关系留在拥有算法、也是唯一真实消费者的曲线插件中是诚实且较小的选择：核心没有增加
曲线名称分支、第二集合协议或新的 validator 上下文；插件检查发生在任何 Artifact 写入之前，登记后
的字节由 CAS/Artifact 不可变性保护。这不等于信任任意 Worker 集合；Agent collection 仍由 Run v1
统一拒绝。

现有 `test_curve_analysis_package_and_plot_bundle_fail_closed_on_tampering` 直接调用包模型和集合校验器，
没有证明 `_curve_error_analysis` 到 Root 的调用边不会漏掉该校验。为避免把单元测试当成生产证明，本
审查另做了不落盘的一次性真实入口负探针：在编译目录完成后污染 Transform 产生的 PNG，调用真实
Root `operation_invoke`。调用沿 `CompiledTransformAdapter` 进入插件实现，并因
`curve analysis plot digest differs from report` 失败；检查确认没有建立 primary 或任何 sibling
绑定。另一个两 Metric/两 PNG 探针确认真实登记标签
`primary/curve_analysis_plots_001/curve_analysis_plots_002` 的字节 SHA-256 与包内两项 analysis 顺序
精确一致。

因此当前实现的集合闭合不是未执行 validator 或仅测试调用的死表面。把上述“污染 Transform 返回值”
负例固化进仓库测试仍有价值，见第 9 节，但当前生产行为已由真实入口独立复现，不构成本阶段阻断。

## 5. 真实 Root→Transform→Artifact→Agent Run 闭环

`tests/operations/test_m2_curve_analysis_boundary.py` 使用真实 `RootMCPRouter`、统一
`operation_invoke`、`ArtifactService`、`RunService`、`LocalTrustedBackend` 和
`LocalWorkerMCPRouter` 完成：

```text
六项精确输入
  -> science.curve.error.analyze.v1 preflight/invoke
  -> 一个分析包 Artifact + PNG sibling Artifact
  -> 同指纹重复调用幂等
  -> science.result.diagnose.curve-error.v1 preflight/invoke
  -> queued/running Run + 单一受控 result.json
  -> worker_submit_result
  -> completed Run + LayeredDiagnosisReport Artifact
```

Transform 输出的全部 sibling 具有相同有序父引用、operation id/version/digest 和 invocation
fingerprint；通用 family 恢复还会核对端口、媒体类型、基数和完整 sibling 集合。Agent 输出父链则由
Run v1 精确绑定唯一包输入。通用输入准入仍在
`mcp_root_operation_routes.py:1024`—`:1159` 执行 producer usage、精确 reviewer、cohort 和科学可采纳性
检查；本候选没有绕开 reviewer、current、revision 或 approval 权威。

测试为了聚焦 Transform 本体，通过内部 `ArtifactService.register` 建立了两个 `{}` 审查 fixture；这
不是 Root 可摄入任意结构化审查的产品入口。真实 Operation 产物仍携带编译生产者政策，进入非
reviewer Operation 时必须同时绑定精确 reviewer 输出。聚焦回归包含 L2 Run 不变量和 L3 独立审查/
人工决定测试，未发现本候选对旧 revision 不继承审查、查询纯读或 loopback UI 决定边界的退化。

## 6. 旧表面与知识更新消费者

对 `src/`、`plugins/`、`tests/` 和安装入口的当前源码扫描结果：

- 生产源码零命中 `worker_curve_analyze`、`curve_analyze_tool`、`CurveDiagnosisResult` 和
  `scidiscovery.curve-diagnosis.v1`；
- `plugins/curve_score/curve_score/worker_tool.py` 不存在，曲线插件组件也没有
  `curve_analyze_tool`；
- 当前唯一曲线专用分析 Schema 是插件内 `scidiscovery.curve-diagnostic-analysis.v1`，其生产者是
  新 support Transform，消费者是单输入诊断 Agent；
- 根目录 `build/lib`、`__pycache__` 和历史计划中的旧字节/旧名称不是当前源码、插件 entry point 或
  干净 wheel 消费者，不能据此恢复兼容层。

知识更新 `science.knowledge.update.diagnosis.v1` 的输入已是通用
`scidiscovery.layered-diagnosis.v1`。`_curve_knowledge_update` 在
`science_operations.py:225`—`:248` 先严格解析 `LayeredDiagnosisReport`，再调用既有通用 reducer；
`src/scidiscovery/artifact_agent/transforms.py:136`—`:180` 明确接受
`validation_report` 或 `layered_diagnosis` 二选一。增强后的测试已经实际运行 reducer 并解析两个
输出。本审查又通过编译后的 Root preflight/invoke 登记这两个输出，并分别以 `KnowledgeUpdate` 和
`KnowledgeStateProjection` 成功解析，未发现从删除旧 Schema 后断路。

## 7. 复杂度和物理表面复算

独立复算当前工作树得到：

| 指标 | 当前结果 | 与实现证据 |
|---|---:|---|
| `src/scidiscovery` Python | 96 文件 / 26,126 行 | 一致 |
| 插件 Python | 44 文件 / 22,829 行 | 一致 |
| 生产 Python 合计 | 140 文件 / 48,955 行 | 一致 |
| 生产树摘要 | `0823c86a...c57492b` | 一致 |
| 五插件完整目录 | 48 Operation | 一致 |
| public / support / internal | 26 / 22 / 0 | 一致 |
| Agent / Transform / Approval / Effect | 22 / 22 / 3 / 1 | 一致 |
| 插件组件 | 222 | 一致 |
| 目录摘要 | `0e75eec2...ba3e` | 一致 |
| Root 公共工具 | 30 个且名称唯一 | 一致 |
| 新建 Local 通用数据库表 | 18 | 未增长 |
| Run 状态 | queued/running/completed/failed | 未增长 |

M2-01 独立复审冻结的插件基线是 45 文件 / 22,875 行；当前为 44 文件 / 22,829 行，物理差值确为
-1 文件 / -46 行。增加的一个 support Operation 有诊断 Agent 这一真实消费者；删除的是专用 Worker
工具和双层诊断合同。核心 `src/scidiscovery`、`operations` 包、Root 工具、表、Run 状态、守护进程、
插件入口和 preflight/invoke 数量均未增长。没有用新 adapter、兼容别名或第二集合生命周期换取表面
通过，净复杂度判断成立。

## 8. 33 项约束判断

本审查不把一个结构测试或 219 项绿色回归夸大为 33/33 全部语义符合；登记中的
`pending_review` 和 `SEC-002 known_issue` 保持原状。与 M2-02 直接相关的判断如下：

- AUTH-001、AUTH-003、TOP-002、ROLE-002：目录、preflight、invoke、Transform 登记、Agent Run 和
  submit 继续消费同一编译 Operation；未增加控制权威；不退化。
- IMM-001、IMM-002、LIN-002：分析包和 PNG 以同一精确父集合登记，内容变化由指纹/revision 语义
  处理，旧审查不自动继承；不退化。
- ROLE-001、DET-001、DET-002：插件 Transform 只重放 Metric、定位和绘图；Agent 生成唯一科学诊断；
  本阶段通过。
- PLG-001、PLG-002：曲线 Schema、算法和闭合校验均在 `curve_score`，核心没有曲线分支；干净 wheel
  和组合目录测试通过；不退化。
- SEC-001、RES-001、RES-002：输入和输出均显式、有界、无网络；测试峰值远低于 8 GiB。
  Local 原生工具隔离仍是既有 `SEC-002 known_issue`，本阶段没有掩盖或扩大。
- HIL-001、HIL-002、CQRS-001/002、EFF-001/002、UI-001/002：候选没有改变人工决定、查询/命令、
  Effect 或 UI 路径；相关聚焦和全量回归未见退化。
- MIG-001、MIG-002：没有升级旧诊断/审查事实；干净安装 entry point 确认新 Operation 只来自唯一
  `scidiscovery.plugins` 入口。

## 9. 非阻断问题

### N1：曲线插件当前 README 仍描述旧工具路径

`plugins/curve_score/README.zh-CN.md:12` 仍说曲线误差诊断“借助注册的曲线分析工具定位残差区间”，
确定性支持 Operation 列表也没有 `science.curve.error.analyze.v1`；英文 README 同样没有列出新 support
Operation。当前目录、安装 wheel、Operation purpose、prompt 和生产代码均已采用 Transform→单文件
Agent 边界，因此这是当前插件文档滞后，不是隐藏生产消费者或运行旁路。建议在 M2-03 开始前或同一
文档整理边界更新中纠正，不能据此恢复旧 Worker 工具。

### N2：现有篡改回归没有直接证明 Transform 内调用边

当前测试分别运行 Transform 正例和直接 validator 负例，但移除
`_curve_error_analysis` 中的 validator 调用时，直接负例仍可能保持绿色。本审查的一次性 Root 污染
探针证明当前代码正确；建议将同类 monkeypatch/错误 renderer 返回值负例固化，以防未来回归。该缺口
不改变本次候选的当前行为结论。

此外，`docs/ARCHITECTURE.zh-CN.md:127`—`:132` 对“所有 Transform validator 获得同一种上下文”的
表述比当前一元端口 validator 和本候选插件内集合闭合更宽。M2-02 实现证据已如实记录通用 core
扩张被撤回；后续文档整理应把“通用逐项准入”和“可信插件内部集合关系校验”区分开。当前没有一个
为 M2-02 声明但未执行的 bundle validator，因此不构成生产阻断。

## 10. 独立执行证据

全部 pytest 串行执行，统一设置 `ulimit -v 7340032` 和 `MALLOC_ARENA_MAX=2`，未使用并行：

1. M2-02、后端能力、干净安装入口、平台配置、33 项结构、L2 Run 不变量和 L3 独立审查聚焦集合：
   **39 passed in 54.89s**，最大 RSS **102,596 KiB**；
2. 全量回归：**219 passed in 72.47s**，最大 RSS **137,712 KiB**；
3. 污染 PNG 的真实 Root Transform 负探针：在任何 Transform 输出绑定前拒绝；
4. 双 PNG 的真实 Root Transform 正探针：登记顺序和包内两个摘要逐项一致；
5. `LayeredDiagnosisReport` 知识更新真实 Root Transform：两个输出登记并严格解析；
6. 五插件目录、生产行数/摘要、30 个 Root 工具、18 张表和 Run 四态独立复算；
7. `git diff --check HEAD`：通过，无输出。

污染探针最初两次运行的产品路径都已按预期拒绝污染；第一次测试包装错误地要求公开 Root 错误文本
保留内部原因，第二次又错误假定 binding list 的末项顺序，因此包装断言退出 1。修正为遍历异常因果链
和比较完整名称集合后通过；没有修改生产代码、测试或放宽校验。

审查时关键文件 SHA-256：

```text
3d95dda0e34f76c5b4aa7e81659c394b4a1c197ca2eced62aac290eddbb8f106  R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md
36ebb37729b84f4eceb48e24ba135d7ed4fc57c595b7aab871f642a2e80f3954  R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_EVIDENCE.zh-CN.md
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
e08e8a64cf852044f22ba76c675990155cac3ab816f8cbda5b87b89b363663b1  analysis.py
099410a50807996e1f11a5a50fb10adaa69cad9baf89e9e05e9e92671bfedc32  science_operations.py
347670fe2cb8abad438a0e0bb8c24905774bccc805727ccfdebc7c9c428b25d2  mcp_root_operation_routes.py
40eaaef868d44b12b8baf4084608250fb29a66637cbe835b2e67db031d13bffa  transforms.py
998194ca322fd616171b9f2c93d6de5e8a6b39bbb4f076eddc081ab948882c87  test_m2_curve_analysis_boundary.py
```

## 11. 未由本阶段证明的事项

- 没有运行真实模型来评价曲线诊断的科学准确率；fixture 只证明合同和生命周期。
- M2 整阶段要求的真实通用模型 Agent 与 TCAD 模型 Agent 工具调用验收尚未在本子阶段执行。
- 默认 Local 仍有论文图证据 Agent collection 不可运行；其产品面判断属于 M2-03。
- 没有把 Local 的 SEC-002、审批 UI 可读性、真实 solver 或远端 Effect 恢复宣称为关闭。

## 12. 最终结论

**PASS。** R5-M2-02 已把可重放的曲线评分、残差定位和绘图收进曲线插件的一个 support Transform，
诊断 Agent 通过一个有界输入文件产生一个通用 `LayeredDiagnosisReport`；旧曲线专用 Worker 工具、
集合提交和双层诊断 Schema 已退出当前生产/安装路径。集合闭合在可信插件内真实执行，Root 登记、
不可变父链、幂等、多图摘要、单结果 Run 提交和知识更新消费者均通过真实入口验证。候选还实现了
插件生产代码净删 46 行，未扩张核心或控制面。

因此 R5-M2-02 可以标记完成，**只放行 M2-03**；M2 和 R5-M 仍未完成。
