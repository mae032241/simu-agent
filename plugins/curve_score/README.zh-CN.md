# Curve Score 确定性 transform 插件

`scidiscovery-curve-score` 将显式声明的原生 solver 输出规范化为 canonical
曲线，并执行预注册的通用曲线比较。它只做确定性解析与计算，不解释物理机制，也不修改
TCAD project。新 SProcess 流程以 PLX 承载曲线；log 只用于运行诊断。

## Profiles

- `scidiscovery.curve-normalize.sprocess-log.v1`：`source_spec` +
  `solver_output` -> `CurveBundle` + parser audit；
- `scidiscovery.curve-normalize.sprocess-plx.v1`：`source_spec` + 单个原生
  ASCII PLX -> 单序列 `CurveBundle` + parser audit；
- `scidiscovery.curve-bundle.sprocess-plx.v1`：通过的 runtime attestation +
  experiment plan + 每条 solver series 一个 `solver_output__<series_key>` PLX ->
  可追溯的多序列 `CurveBundle` + parser audit；
- `scidiscovery.curve-bundle.figure-evidence.v1`：保留旧版全图资格语义，只读兼容，
  不重新解释历史 Artifact。
- `scidiscovery.curve-bundle.figure-evidence.v2`：精确 figure manifest +
  控制面生成的 validation report + manifest 中每条 series 一个
  `curve_table__<panel_key>__<series_key>` CSV -> 完整 canonical evidence
  `CurveBundle` + 规范化审计。该桥接不依赖 experiment plan；合格行从像素标定得到，身份
  unresolved 或零合格行保持无数值的 `unavailable` series；
- `scidiscovery.curve-reference-coverage.v1`：experiment plan + 一个或多个完整
  `reference_curve__*` 曲线库 -> 执行前确定性覆盖报告。agent 编写的计划必须将曲线库中的
  每条 series 标成 `compare` 或带理由的 `exclude`；transform 校验映射、精确比较域以及
  reference 侧唯一 crossing 支持，但不替 agent 选择算子、level 或目标；
- `scidiscovery.curve-consistency.v1`：`curve_bundle` + `comparison_spec` ->
  独立的 `CurveConsistencyReport`，不作为研究级 `metric_report`；
- `scidiscovery.curve-score.v1`：canonical curve bundle + 通过的 runtime
  attestation + experiment plan，可选 `reference_curve__*` -> 完整计划 metric
  report、合并 bundle、审计以及确定性的 reference/candidate 对比 PNG。该 scorer
  不认识 solver 或文件格式；
- `scidiscovery.curve-score.sprocess-log.v1`：`solver_output` + 已通过的
  `runtime_attestation` + `experiment_plan`，可选 `source_spec` -> 完整计划
  metric report、规范曲线和审计（历史兼容入口）。

当 `ExperimentPortfolio` 中恰有一个 proposal 声明 `curve_comparison_spec` 时，组合入口可直接
读取实验计划。每个带阈值的 operator 必须绑定一个 `validation_check_key`；这些绑定必须完整且
仅完整覆盖对应 `ValidationPlan` 中的全部 `deterministic_threshold` 检查，并且阈值算符、数值和
单位完全一致。每个被覆盖的检查还必须固定 curve-score evaluator profile 和准确 operator kind，
因此不能把同一个 check key 偷换成另一种指标。部分或临时 comparison spec 会在 normalization
之前被拒绝，不能生成科学 `metric_report`。

figure-evidence bridge 要求控制面 validation report 是精确 manifest 与 manifest 中每个曲线表的
直接子产物，并保留完整证据清单。scorer 后续只选取 `CurveComparisonSpec` 中 agent 显式映射的
series；额外证据既不会造成失败，也不会被并入评分 bundle。存在外部 reference 的 TCAD project
只有在 exact-plan coverage report 通过后才能打包。它不会把 unresolved manifest 或不合格行升级成数值。

## SProcess log grammar

v1 normalizer 只识别以下 UTF-8 记录，其他 solver 日志行会被忽略：

```text
SCID_CURVE_V1|POINT|<case_key>|<series_key>|<zero_based_index>|<x>|<y>
SCID_CURVE_V1|END|<case_key>|<series_key>|<point_count>
```

为复用已由控制面注册的早期solver-only执行，同一profile还接受一个严格的历史兼容分支：
`<固定大写profile标签>,<case_key>,<zero_based_index>,<x>,<y>`，并要求对应的
`SOLVE_COMPLETED,<case_key>,<finite_summary_1>,<finite_summary_2>`完成行。点数由连续索引独立
计数并在扫描完整日志后对照source spec，不从完成行摘要或它与profile行的先后次序猜测。
历史`SOLVE_COMPLETED`表示solver完成，允许profile统一在其后导出。历史分支只在日志完全没有
`SCID_CURVE_V1`记录时启用；每个声明case只能对应一条series，标签必须全局一致，索引必须从0连续，
点值与完成摘要必须有限，实际点数与source spec边界必须一致。它不猜单位、不排序、不补点。

comparison/source spec 必须显式声明每条 series、坐标轴名称/单位/尺度和点数范围。未知、截断、
非有限或未声明的数据一律 fail closed。原始行序完整保留；声明为 `y(x)` 的算子只在计算时建立
不修改源数据的 x 索引。重复 x 的界面观测按原顺序保留，并从存在歧义的
数值采样中 mask；不会排序、去重、求平均，也不会据此把指标判为 fail。解析器不猜单位、不外推、
不填补缺失值。

SProcess ASCII PLX 解析器接受一个或多个带引号的数据集字段头，每个字段随后每行严格为两个有限数值列
`x y`。多数据集 PLX 必须显式给出 `dataset_name`，禁止静默选择第 0 个数据集。
允许空行且点数必须满足声明范围；原始行序不变，x 行序回退会在 normalization audit
中计数。重复 x 会作为接缝证据完整保留；下游评分 mask 该歧义坐标，同时让 diagnostician 在图中看到它。
多余列、重复/缺失的数据集名、非法 UTF-8 或非有限值均 fail closed。坐标轴、单位、case 和 series
身份只来自实验计划，绝不从文件名、表头或 log 推断。

报告中的 `pass|fail|unavailable|inconclusive` 只表示确定性检查结果。diagnostician 可以结合
runtime 与 control-equivalence 报告解释物理含义，但不得重新计算或覆盖这些值。对 log 指标，
零值区域会保留并显示，但不加 epsilon，且不进入数值评分；重复 x 接缝同样“可见但被 mask”。
若剩余有效支撑不足，指标只能是 unavailable/inconclusive，不能因为这些区域本身变成 fail。

交点发现返回按序排列的全部交点位置：零交点表示为空列表，多交点保持列表且不属于解析失败。
只有要求单一标量的 `crossing_shift`/`width_shift` 在未声明配对规则、且任一侧不恰好具有一个
所需交点时才 unavailable；metric report 会保留完整交点位置供下游诊断。
