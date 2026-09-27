# 曲线科学插件

`scidiscovery-curve-score` 只拥有曲线领域的科学语义：曲线契约、规范曲线、确定性评价、覆盖检查和曲线诊断。它不读取 TCAD 原生输出，也不认识 SProcess、PLX、求解器证明或执行协议。TCAD 原生输出到规范曲线的转换由 `tcad_artifact` 插件负责。

## 公开科学操作

- `science.curve.contract.design.v1`：把通用研究目标与通用实验计划具体化为 `CurveExperimentContract`；
- `science.curve.contract.review.v1`：独立审查上述曲线契约；
- `science.result.diagnose.v1`：解释确定性曲线报告；
- `science.result.diagnose.curve-error.v1`：读取一个已闭合的确定性曲线误差分析包，给出科学诊断。


## 确定性支持操作

- `science.curve.error.analyze.v1`：从精确计划、合同、指标和曲线束重放残差分析，产生一个可复算分析包及有界 PNG 集合；
- `scidiscovery.curve-bundle.figure-evidence.v2`：把已经过控制面验证的图表数据转换为规范曲线证据；
- `scidiscovery.curve-score.v1`：根据通用实验计划和独立曲线契约评价一个规范曲线束；
- `scidiscovery.curve-reference-coverage.v1`：检查曲线契约是否明确处置全部参考曲线；
- `scidiscovery.objective-coverage.v1`：检查研究目标、通用计划、曲线契约和参考证据的闭合关系。

论文图证据 Agent 不属于 TCAD 默认闭环，已由独立的可选
`curve_figure_evidence` 插件注册。本插件保留规范图证据、校准、验证和转曲线包的确定性实现，供该
插件复用；仅安装本插件或 TCAD 插件不会把论文图提取/审查 Agent 放进目录。

通用 Worker 只提供领域无关的文件、PDF 和图像访问能力，不按固定路径挂载领域脚本；曲线
manifest、CSV、叠图、数字化算法和资格报告全部由本插件拥有。

曲线契约不是通用 `ExperimentPortfolio` 的字段。它必须作为独立产物接受独立审查，并精确绑定一个实验：

- 声明序列身份、坐标轴、单位、尺度和数据来源；
- 声明比较域、算子和阈值；
- 将每个算子一一绑定到通用 `ValidationPlan` 的确定性检查；
- 阈值、单位、评价器和指标必须完全一致；
- 外部参考曲线必须明确标记为比较或有理由地排除。

评分器只消费规范 `CurveBundle`，不猜文件格式、求解器、单位、序列身份或缺失值。身份未决、支撑不足或交点不唯一时返回 `unavailable` 或 `inconclusive`，不得伪造成通过或失败。

## 插件边界

TCAD 插件可以依赖本插件的公开曲线契约和规范曲线格式，并注册自己的适配操作，例如：

- `tcad.curve-bundle.sprocess-plx.v1`；
- `tcad.curve-bundle.sprocess-log.v1`。

依赖方向只能是 `tcad_artifact -> curve_score`。曲线插件不得反向导入 TCAD 代码。安装另一个领域插件时，也不应修改核心、通用科学插件、调度器或本插件。
