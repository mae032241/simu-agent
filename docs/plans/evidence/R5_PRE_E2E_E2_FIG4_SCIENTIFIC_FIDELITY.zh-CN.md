# R5 E2：Fig.4 科学保真度实施证据

日期：2026-09-04

状态：**完成；独立复审 PASS，阻断项 0，只放行 E3**

本阶段只恢复冻结 Fig.4 两条实测连续实线所需的能力。未增加 marker、拟合段、通用图理解、核心
Run 状态、数据库、MCP 路由、审批页或部署协议。

## 1. 最小实现边界

- `figure_digitization_contract.py`：唯一的类型化请求合同；可输出 `ready` 或带理由的 `unresolved`。
  `unresolved` 不允许夹带部分标定和部分序列，避免 Worker 为满足必填字段而猜测。
- `figure_line_tracker.py`：只实现连续实线的有界种子走廊、局部定义域、边界排除、断裂检测和候选
  路径歧义检测。
- `figure_digitization.py`：只负责图例/注释框颜色锚定、逐序列物化、显式共享遮挡、逐点 eligibility、
  合并身份/保真叠图和确定性附件。
- `figure_source.py`：请求与 manifest 同时记录固定的 `pdfimages`/Pillow 恢复器名称和版本；来源
  摘要、页、图像号、PDF 对象、恢复图摘要和尺寸仍逐项复核。

三块生产实现分别为 357、457、585 行，未恢复已删除的 1807 行通用图表脚本，也没有把 E2 逻辑
塞进核心控制面。

## 2. 冻结 Fig.4 结果

测试几何来自已找到的精确历史请求，只保留两条 measured 连续实线，删除三条不属于本轮范围的拟合
段；来源改为由冻结 PDF 独立恢复并绑定的对象 `241 0`。历史 PNG 与当前规范化 PNG 解码后逐像素
相同。

同一来源和请求连续物化两次，全部端口逐字节一致。当前输出为：

| 序列 | 直接观测行 | 可见率 | 最大源列空档 | 图例绑定 | 定量 eligible | 结论 |
|---|---:|---:|---:|---|---:|---|
| In0.83Al0.17As 黑线 | 565 | 0.698393078 | 56 px | matched | 0 | unresolved |
| In0.83Ga0.17As 红线 | 805 | 0.995055624 | 2 px | matched | 801 | available |

图级状态为 `unresolved`，但 v2 normalizer 只阻断黑线；红线仍形成 `available` 的规范曲线。黑线的
未声明 56 px 空档及多段由红线覆盖的几何候选形成明确 ambiguity，且其全部观测行被确定性标为
`series_unresolved`，不会进入评分。红线不继承黑线的图级未决状态。红色 SEM 竖向标注与曲线重叠
的源列 `[537,541)` 保留为 4 个 observed 点，但以 `same_color_annotation_overlap` 标为 ineligible；
规范化器在该内部区间切断定量有效域。

输出摘要：

- 类型化请求：`b0dc186d594e4d9471671e4938b5a66c22b51f912c88c0469c9d76cc435ba769`；
- manifest：`3e44d39f0db491faecb01c9de5d4ab4d7e443054c82858b32370a254008601c8`；
- source panel：`88358eb5658c75cf7eddb3cb71fab5f2f8d5bf0d6e7252481193142adb19be5a`；
- identity/fidelity overlay：`d1df02d94402ff15afe4d93d896f5a18e79a82f75a54de4bd7ffc17e68b9fe06`；
- 黑线/红线 CSV：`2505e7b590620da743ecc3955488b30a1a77c8e5d19946742d5e4ef5347ac6c8` / 
  `7c95af3dd07d90a8c6ecbca0b78d24c42bbe2f19672b1f9503549bd28d798b48`；
- validation report：`7b1e5ed9590edeb5931ed96be5986f6cf5ccaceb59574697d14355feb7b2eab4`；
- CurveBundle：`6217d04ca20cff45ca412129f765c5a13d92fecfa8d71adc97803a9f9726e40b`。

恢复器版本记录为 `pdfimages version 22.02.0; Pillow 12.1.1`。

## 3. 与 589/806 文档记录的差异

资格文档曾记录黑线 589 行、红线 806 行，但仓库及全部现存历史 CAS 中没有保存产生这组数字的精确
请求或 CSV。当前找到且能闭合 PDF、源图、请求、manifest 和 CSV 的历史家族是 565/786。首轮独立
审查进一步发现，旧请求的跳过代价 30 低于低浓度区真实红线相对粗导引线的逐列代价，导致路径选择
主动跳过仍有合法候选的源列。只把该红线请求的跳过代价修正为 50 后得到 805 个 observed、最大空档
2 像素；颜色容差、来源图、轴、种子和通用跟踪算法均未改变。

因此本阶段没有把 589/806 当作可继承的真值，也没有调高颜色容差或填补空档来追数字。805 与文档
806 的一行差异仍需独立复审按来源图判断；当前剩余空档均不超过 2 像素。黑线保持 565 个 observed、
0 eligible 的保守未决状态。

## 4. 负例和下游边界

新增或固化的负例包括：

- 来源摘要变化、轴超出 plot、种子落入同色坐标轴边界；
- 连续实线存在未声明空档；
- 两条序列未经 shared-support 声明复用同一像素；
- 未决序列伪造 eligible 行；
- 只给旧 CSV 而不给精确 source/request；
- shared-support 必须具有两端直接支撑，被覆盖行默认 ineligible；
- 一个内部 ineligible 空档会形成两个 `valid_intervals`，跨空档评分确定性返回
  `continuous_domain_unavailable`。

## 5. 测试证据

E2 单元、冻结 Fig.4、共享遮挡、normalizer、Operation 拓扑、父链、编译和保留 Transform 聚焦测试：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_m2_curve_analysis_boundary.py \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_h2b_domain_boundaries.py \
  tests/operations/test_m5_plugin_ownership_and_default_surface.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_agent_contract_alignment.py \
  tests/operations/test_m3_transform_equivalence.py
```

首轮结果：`91 passed in 40.90s`。阻断修复后的同一测试集结果：`91 passed in 41.38s`，峰值 RSS
`117904 KiB`。`py_compile` 与相关文件 `git diff --check` 均通过。复审材料保存在非临时目录
`deliverables/r5-pre-e2e-e2-rereview/`，包含类型化请求、manifest、两张 CSV、validation report、
CurveBundle 和合并叠图。

## 6. 尚未放行

- 首轮独立科学审查见 `reviews/R5_PRE_E2E_E2_INDEPENDENT_SCIENTIFIC_REVIEW.zh-CN.md`，结论
  `FAIL`、阻断 2；两项已按原边界最小修复。独立复审见
  `reviews/R5_PRE_E2E_E2_INDEPENDENT_REREVIEW.zh-CN.md`，结论 `PASS`、阻断 0，只放行 E3；
- 尚未执行 E3 预检/调用审批投影等价；
- 尚未安装部署，也未证明真实 Codex Agent 会使用图像检查工具；
- 尚未开始新的端到端科学实验。
