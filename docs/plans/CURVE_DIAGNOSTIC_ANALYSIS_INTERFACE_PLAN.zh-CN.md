# Diagnostician 曲线误差分析：最小实现计划

## 1. 决策

曲线误差分析不设计成一套可编排工作流，只增加一个确定性工具：

```text
worker_curve_analyze
```

它解决一个问题：已有全局 curve score 失败或需要检查 masked support 时，自动回答“误差主要集中在哪一段、哪些位置没有资格计分”，并保存对应的可视化图像。

diagnostician 负责解释结果；工具负责计算。agent 不填写区域、网格、插值、容差、计数或指标值。

## 2. 调用接口

请求最多只有一个可选字段：

```json
{}
```

或：

```json
{
  "comparison_key": "num_A_refinement"
}
```

- 未指定 `comparison_key`：分析 metric report 中失败的 residual comparison。
- 指定 `comparison_key`：只分析该 comparison。
- 失败 comparison 超过 8 个时，工具拒绝批量分析，要求指定一个 key。

不接受下列字段：

- 文件路径或 Artifact 标识；
- 区域边界；
- 插值方法、网格或容差；
- metric/operator/profile 名；
- Python、表达式或任意代码；
- 输出路径。

这些内容全部来自当前 task 已绑定的 exact inputs：

- `experiment_plan`：comparison、domain、operator 和评价规则；
- `metric_report`：失败项及全局评分；
- `curve_bundle`：scorer 已规范化的候选曲线和参考曲线。

工具不读取原始 PLX，也不要求实验计划重复登记论文数据。论文数字化曲线已经是独立 reference library。

## 3. 固定算法：自适应误差地图

固定等宽切片会稀释窄峰，也会把真实转折点切开，因此不使用固定 8 段。

`scidiscovery.curve-error-analysis.v1` 在 scorer 的同一评价网格上执行：

1. 生成逐点诊断原子：`x`、signed residual、absolute residual 和 support class；评分网格之外只额外插入重复-x 接缝坐标用于显示，不把它加入数值指标；
2. 先按不可跨越的事实边界分 run：有效区间/排除区间、数据间隙、正值/零值 support 状态变化；
3. 在每个连续且 support 相同的 run 内，对 `(signed residual, absolute residual)` 做确定性一边界/两边界变点检测；
4. 每次选择使区间内残差方差下降最多的切点，只有当两段模型的 BIC 优于一段模型时才接受；
5. 递归到没有受数据支持的新切点为止；并列切点固定选择较小 x；
6. 最多返回 16 段只是响应大小的安全上限，不是预设科学分段；达到上限时返回 `truncated=true`；
7. 单点 comparison 直接返回一个 point segment，不运行变点检测。

这样得到的结果具有预期行为：

- 窄峰或局部异常：自动形成窄区间；
- 全域均匀偏差：保留为一个宽区间；
- 正负偏差反转：signed residual 触发切分；
- 幅度变化但符号不变：absolute residual 触发切分；
- log 曲线的零区和正值区：由 support 状态强制分开，零区完整显示但不参与 log residual；
- 重复 x 接缝：原始两个或多个点完整保留，图上显示垂直接缝，歧义坐标不参与 residual；
- 多个分离热点：形成多个不相邻区间。

每个最终区间只计算 `rms_error`、`mean_signed_error`、`error_fraction` 和 `support`。精确零按数据值判断，不引入 agent 可调 epsilon。零区和重复-x 接缝只产生带范围/点数/原因的 mask 段，不能直接产生 `fail`；剩余有效支撑不足时指标只能是 `unavailable`。

通用 `CurveSeries` 不要求原始行序中的 x 单调。归一化结果保留原始行序和全部点；声明为 `y(x)` 的当前评分算子在内部建立不修改源数据的 x 索引。PLX audit 记录 x 行序回退次数。重复 x 仍然表示同一坐标的多值接缝，因此被 mask。当前版本不宣称支持回滞或一般参数曲线算子。

工具同时返回有界的逐点 residual trace，供 diagnostician 像查看曲线一样识别趋势；区间数值仍由确定性代码生成，agent 不手算或改写。每个 comparison 还自动生成一张与 report 绑定的 PNG，不增加请求字段。

## 4. 返回值

返回一个紧凑对象，并自动登记对应的图像附件：

```json
{
  "profile": "scidiscovery.curve-error-analysis.v1",
  "comparisons": [
    {
      "comparison_key": "num_A_refinement",
      "global_score": {
        "status": "available",
        "reported": 0.3796432753751781,
        "recomputed": 0.3796432753751781,
        "unit": "decade"
      },
      "segments": [
        {
          "x_start": 0.0,
          "x_stop": 0.0375,
          "support": "both_positive",
          "rms_error": 0.04,
          "mean_signed_error": -0.01,
          "error_fraction": 0.03
        }
      ],
      "residual_trace": [
        {"x": 0.0, "residual": -0.01, "support": "both_positive"}
      ],
      "plot_item": "num_A_refinement.png",
      "truncated": false
    }
  ]
}
```

数字仅为结构示例，不是当前 Fig.4 结果。

报告最大 64 KiB。若 scorer 网格超过响应上限，residual trace 使用保端点、极值和 support 转折的确定性有损显示采样；分段计算始终使用完整评分网格。diagnostician 根据自适应区间、trace 和图像判断误差是全域、边界、峰区还是尾区集中，并据此决定下一步。

PNG 使用固定的 `scidiscovery.curve-error-plot.v1` renderer，1200×800 px，包含：

- 上图：reference 与 candidate 原曲线；
- 下图：signed residual 和零基线；
- 自适应 segment 边界及交替底色；
- zero/nonzero/invalid support 带；
- comparison key、坐标名称、单位和全局 score。

图像只用于观察，不作为数值证据。所有数值以 JSON report 为准。PNG 不接受标题、颜色、尺寸或输出路径配置，避免样式参数重新膨胀接口。

工具响应还必须给当前 worker 一个可直接读取的 runtime descriptor：

```json
{
  "comparison_key": "num_A_refinement",
  "plot_item": "num_A_refinement.png",
  "plot_relative_path": "output/collections/curve_analysis_plots/num_A_refinement.png",
  "plot_local_path": "/var/lib/scidiscovery/workspaces/<current-session>/output/collections/curve_analysis_plots/num_A_refinement.png"
}
```

- `plot_local_path` 是当前 task workspace 内的临时绝对路径，供 agent 立即使用原生图像查看工具打开 PNG；
- `plot_relative_path` 用于核对它位于 assignment 声明的 collection 中；
- `plot_item` 是 portable 名称，随最终 bundle 注册；
- 最终 `LayeredDiagnosisReport` 只允许保存 `plot_item`，禁止写入非便携的绝对路径；
- retry 后 workspace 路径可能变化，agent 必须使用本次工具响应，不能复用旧绝对路径。

## 5. 同一任务内完成

不新增第二个 agent task或 transform。PNG 作为同一任务的受控附件随 primary output 一起 finalize：

```text
diagnostician
  -> worker_curve_analyze
  -> 读取确定性报告和 PNG
  -> 解释误差分布
  -> finalize LayeredDiagnosisReport
```

`LayeredDiagnosisReport` 只增加一个可选字段：

```text
curve_analysis: CurveErrorAnalysisReport | null
```

agent 只将工具响应中的 portable analysis report 原样带入诊断结果；runtime descriptor 不属于科学 schema。final validation 使用 exact 三个输入重新计算并 canonical compare；任何手改数字都会被拒绝。

diagnosis 使用固定 output profile，声明一个 collection：

```text
curve_analysis_plots
  media_type: image/png
  min_items: 1
  max_items: 8
  max_item_bytes: 1 MiB
  max_total_bytes: 8 MiB
```

工具自行决定受控 collection 路径；调用者不能传路径。工具返回当前 `plot_local_path` 后，diagnostician 应先用原生图像查看能力读取它，再形成解释。final validation 重算 report/renderer hash，并通过 collection 自己声明的 bundle validator 将实际 PNG 字节、尺寸、名称与 report 逐项核对；finalize 后由控制面注册附件并可在审批 UI 中预览。

## 6. 最小开发项

### P0-A：纯函数

在通用 curve-score 层增加：

```python
analyze_curve_error(plan, metric_report, curve_bundle, comparison_key=None)
```

复用现有统一评分网格和插值实现，不复制 scorer 算法。

完成条件：相同输入产生 byte-stable report，全局复算值与 metric report 一致，否则 fail closed。

### P0-B：worker 工具

增加 `worker_curve_analyze`，仅 diagnostician 的 active claimed session 可调用。工具从 task-local aliases 取 exact inputs，不接受路径或数据正文。

完成条件：其他 role、缺失 CurveBundle、未知 comparison、输入父链不一致均被拒绝。

### P0-C：diagnosis 集成

- diagnosis context profile 允许可选 `curve_bundle`；
- diagnostician prompt 要求：存在失败 residual comparison 和 CurveBundle 时，先调用工具再提出新仿真；
- `LayeredDiagnosisReport` 增加可选 `curve_analysis`；
- diagnosis 增加固定 `curve_analysis_plots` output profile；
- output validator 重算并比对报告。

完成条件：diagnostician 不能手写或篡改确定性数值。

### P0-D：确定性 PNG renderer

- 使用已有 Pillow 依赖生成固定 1200×800 PNG；
- 绘图数据只来自 CurveErrorAnalysisReport 与 exact 两条曲线；
- 清除时间戳和环境相关 PNG metadata；
- 输出文件名由已验证的 `comparison_key` 确定；
- worker 响应返回本次 workspace 的绝对读取路径，final schema 拒绝持久化该路径；
- validator 重绘并逐字节比对，UI 复用已有安全 raster preview。

完成条件：相同环境和输入得到相同 PNG；修改像素、尺寸、MIME 或 report 绑定均被拒绝。

### P0-E：调度规则与安装

- 更新 AGENTS 规则：失败 curve score 可定位时，先做同任务分析，后决定是否重跑 TCAD；
- 更新 worker tool 数量、安装探针和持久安装脚本；
- 不修改 experiment plan schema，不新增 approval。

## 7. 必测案例

1. 指定 comparison 时可对通过、失败或 unavailable 的 residual 显式生成分析；
2. 窄峰形成窄区间，不被全域平均稀释；
3. 全域均匀误差保持一个宽区间；
4. 相同幅度的正负反转产生变点；
5. 两个分离热点产生两个区间；
6. 参考为零、候选非零时形成独立 support 区间；
7. 重复 x/接缝点完整保留、形成零宽 mask 段且不重复计分；
8. log comparison 的零区不进入 log residual；
9. 全局复算与 metric report 不一致时拒绝；
10. agent 修改任一区间数字时 final validation 拒绝；
11. PNG 能同时显示原曲线、残差、segment 和 support；
12. PNG 像素、尺寸、名称或 report 绑定被修改时拒绝；
13. agent 能通过本次响应的 `plot_local_path` 打开图片；
14. retry 后旧 local path 不会进入最终结果；
15. 非 diagnostician 调用时拒绝。

## 8. 实施状态（2026-08-15）

- P0-A：完成。自适应定位、零 support、重复-x 接缝和原始行序保留已实现；
- P0-B：完成。`worker_curve_analyze` 只读取 task-local 三项输入，调用参数不含路径或数据；
- P0-C：完成。diagnostician 上下文、输出 profile、portable report 和 contextual recomputation 已接入；
- P0-D：完成。确定性 PNG、runtime 读取路径、bundle hash/尺寸/名称绑定及 UI 兼容格式已实现；
- P0-E：完成。调度提示、worker 工具计数和安装探针已更新。

当前聚焦回归覆盖算法、PLX 保真、worker 生成、PNG 打开、篡改拒绝和角色边界。全仓回归结果记录在本轮交付说明中。

## 9. 非目标

P0 不实现：

- 任意区域 DSL；
- agent 自定义公式；
- 新的曲线数字化；
- 原始 PLX 解析；
- 自动生成科学结论；
- 自动修改 experiment plan 或 deck；
- 新的 transform、审批或中间任务。

核心原则只有一句：**agent 选择要理解的失败项，确定性工具自动定位误差，agent 解释它。**
