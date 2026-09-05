# R5-M2-02 曲线分析与诊断边界实现证据

日期：2026-09-01

状态：实现与全量回归完成，独立审查 PASS；M2-02 完成，仅放行 M2-03

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 本阶段回答的问题

旧 `science.result.diagnose.curve-error.v1` 同时要求诊断 Agent：

- 读取计划、审查、曲线合同、指标和曲线束；
- 调用 `worker_curve_analyze` 重放确定性残差分析；
- 提交一个 `CurveDiagnosisResult`；
- 同时提交最多八张 PNG 集合。

默认 Local 后端不实现 Agent 集合提交，所以该公开 Operation 在目录和 preflight 中必然不可用。若为
它扩建 Run 集合状态机，会把曲线插件的一个需求重新升级成通用控制面责任。

M2-02 改为：

```text
science.curve.error.analyze.v1（support Transform）
  输入：计划、两项审查、曲线合同、指标报告、曲线束
  输出：一个 CurveDiagnosticAnalysisPackage + 确定性 PNG 集合
                         ↓
science.result.diagnose.curve-error.v1（public Agent）
  输入：一个 CurveDiagnosticAnalysisPackage
  输出：一个 LayeredDiagnosisReport
```

确定性代码只重放已登记指标、定位残差和绘图；Agent 只解释结果。指标状态不被当作科学 verdict，
科学诊断仍由 Agent 给出。

## 2. 实现边界

### 2.1 可复算分析包

新增插件内 `CurveDiagnosticAnalysisPackage`，只组合既有：

- `ExperimentPortfolio`；
- `CurveExperimentContract`；
- `CurveConsistencyReport`；
- `CurveBundle`；
- `CurveErrorAnalysisReport`。

模型验证时用精确输入重放既有 `analyze_curve_error`，要求规范化分析报告完全一致。它不是新的控制实体、
状态或注册表，只是让单输入 Agent 得到一个可携带、可复算的科学上下文。

### 2.2 支持型确定性变换

新增唯一 support Operation `science.curve.error.analyze.v1`。它复用原有曲线评分、残差定位和 PNG
渲染函数，一次性产生分析包与图像集合；图像数量、总大小、PNG 格式、尺寸和 SHA-256 均在插件变换
内部闭合验证。输出仍经现有统一 `operation_invoke` 登记为不可变 Artifact，全部父引用是同一精确输入
集合。

实现过程中曾尝试为所有 Transform 集合在核心调用器增加通用 bundle 校验，但全量回归显示这会使
`operations` 核心包增加 46 行并越过既有复杂度门，而当前只有曲线插件一个真实消费者。该核心扩张已
完整撤回；约束留在拥有算法和真实消费者的插件组件中。`RunService`、核心 Transform 调用器和目录
均未增加状态或分支。

### 2.3 单输入、单输出诊断 Agent

曲线误差诊断 Operation 现在只有一个 `curve_analysis_package` 输入和一个 `layered_diagnosis` 输出，
不再声明 Agent 集合、图片原生查看或曲线分析 Worker 工具。提交上下文验证器重新验证分析包，并把
诊断精确绑定包内计划、合同和完整指标报告。

默认 Local 后端因此可运行该公开 Agent。Hardened 后端仍只因既有 `native_shell` 原型边界不可用，
本阶段没有掩盖或扩大该已知边界。

### 2.4 删除包装和专用工具

- 删除只为该 Operation 服务的 `curve_score/worker_tool.py`；
- 删除 `CurveDiagnosisResult` 双层包装；
- 知识更新 support Operation 直接消费通用 `LayeredDiagnosisReport`；
- 删除旧 `scidiscovery.curve-diagnosis.v1` 资源和相关组件；
- 保留既有纯确定性分析与绘图函数，未重新实现曲线算法。

## 3. 跨边界验证

新增 `tests/operations/test_m2_curve_analysis_boundary.py`，覆盖：

1. 支持变换和诊断 Agent 从同一个五插件编译目录取得；
2. 变换通过真实 Root `operation_invoke` 产生分析包和 PNG，重复请求幂等；
3. 分析包能从精确计划、合同、指标和曲线束重新计算；
4. PNG 摘要篡改和分析包摘要篡改均失败关闭；
5. 诊断 Operation 只有一个输入、一个输出，默认 Local 后端支持；
6. 使用真实 `RunService`、`LocalWorkerMCPRouter`、受控结果文件和提交边界完成一个诊断 Run；
7. 诊断 Agent 看不到 `worker_curve_analyze`；
8. 知识更新合同直接消费通用 layered diagnosis；
9. 旧 Worker 工具文件和组件均不存在。

原后端能力、平台配置和安装入口测试同步更新：曲线误差诊断不再被报告为
`agent_collection_outputs` 不可用；完整目录新增且仅新增一个 support Transform。

## 4. 复杂度变化

| 指标 | M2-01 | M2-02 候选 | 变化 |
|---|---:|---:|---:|
| `src/scidiscovery` Python | 96 文件 / 26,126 行 | 96 文件 / 26,126 行 | 0 |
| 插件 Python | 45 文件 / 22,875 行 | 44 文件 / 22,829 行 | -1 文件 / -46 行 |
| 生产 Python 合计 | 49,001 行 | 48,955 行 | -46 行 |
| 插件组件 | 222 | 222 | 0 |
| Operation | 47 | 48 | +1 support Transform |
| public / support | 26 / 21 | 26 / 22 | 0 / +1 |
| Agent / Transform / Approval / Effect | 22 / 21 / 3 / 1 | 22 / 22 / 3 / 1 | 0 / +1 / 0 / 0 |
| Local 可运行公开 Agent | 20 / 22 | 21 / 22 | +1 |
| `operations` 核心包 | 8 文件 / 2,103 行 | 8 文件 / 2,103 行 | 0 |
| Root 公共工具 | 30 | 30 | 0 |

生产树摘要按“相对路径、零字节、内容、零字节”的有序 SHA-256 规则计算为：

```text
0823c86ac9c4fb4a477dab30cd52ddaf378dade5e1b10b832ae8c52c4c57492b
```

完整五插件编译目录摘要为：

```text
0e75eec25453c31f6ad5ed6ec2da272affe2917fe2938b99988fa38ceb03ba3e
```

本阶段没有新增核心行、数据库表、Run 状态、Root 工具、集合提交协议、第二目录、第二 preflight、
第二 invoke、守护进程或兼容适配器。

## 5. 测试结果

全部 pytest 串行执行，设置 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2`：

```text
pytest -q tests/operations/test_m2_curve_analysis_boundary.py \
  tests/operations/test_l6_runtime_capabilities.py
5 passed in 10.27s

pytest -q
219 passed in 73.26s

git diff --check
通过，无输出
```

第一次全量回归发现三项问题：两个纯集合 Transform 夹具没有 primary，却被未必要的通用 bundle
校验错误拒绝；核心包行数门因该扩张超限。撤回通用扩张并将真实约束留在曲线插件后，上述问题和
复杂度门同时闭合。没有放宽测试上限或给夹具加伪 primary。

## 6. 尚未完成

- 未参与实现者的审查报告为
  `../reviews/R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`，结论
  PASS 且只放行 M2-03；
- 默认 Local 仍有一个公开 Agent 因集合输出不可运行，即 M2-03 要判断去留的论文图证据能力；
- M2 整阶段要求的真实通用模型 Agent 与 TCAD 模型 Agent 工具调用验收尚未执行；
- 没有声称本 fixture 证明真实 TCAD 曲线诊断科学准确率；
- M2-03、M3 及以后仍未放行。
