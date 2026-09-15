# 现场内容展示缺口

2026-09-15。用户在安装并绑定后报告：看不到论文提取 CSV 的曲线效果，参数普遍标为来源未记录，正文几乎为英文。本记录只诊断工程展示，不重新裁定科学依据，不修改科研数据或生产源码。此前安装及导航验收通过，不等于这些内容展示能力已经完备。

## 1. CSV 与已有重绘图没有形成证据查看入口

控制目录确认原实例中 `fig4_continuation_figure_materialized_1.curve_tables_001` 仍登记为 `digitized_curve_table` / `text/csv`，87590 字节；同批 `audit_overlays_002` 为 PNG，20775 字节。清单、CSV、图件具有相同的物化调用指纹和相同的论文/请求父记录，不是清单的直接父节点。此处只确认记录和来源关系，不将该历史版本认定为当前合格证据。

提取器 `figure_digitization.py` 调用 `figure_numeric_redraw.render_numeric_redraw`，已有按 CSV 数值绘制曲线的实现。UI 的 `_artifact_view` 把 CSV 作为普通 UTF-8 文本；`build_presentation` 只把当前已达上下文内的 PNG/JPEG 加入图件；`_lineage_views` 沿父引用读取，不会仅凭同批兄弟关系把 CSV、原图、重绘图自动组成一组。当前曲线插件没有声明 `scidiscovery.instance_views` 展示提供者。

应在已有证据身份/家族关系上组织原图、CSV 曲线或已有数值重绘、坐标和下载入口。没有理由要求重跑提取或增加科学 Agent 任务。

## 2. “来源未记录”混淆了视图未适配与原始证据缺失

[实际 HTTP 原记录探针](PARAMETER_SOURCE_DIAGNOSIS.json)显示当前工作台实际输出的 14 条参数行全部来自实验计划的 comparison variables，全部显示“来源未记录/是否默认未知”和“获得方式未记录”。三个逐行样本涉及两个变量，均存在原计划定位、`rationale`、`factor_type`、`comparison_role`、取值及单位字段。样本中的 `epistemic_status` 与直接文献引用字段不存在，但 `ComparisonVariable` / `IntentComparisonVariable` 的正式模型本来就没有这些字段，不能认定为作者漏填。

直接原因：`general_science_views._proposals` 将案例变量转换成统一 parameter 行，保留原记录定位和理由，却未提供 epistemic_status/sources；`presentation.parameter` 默认补“来源未记录/是否默认未知”。`_sources` 又对空列表显示相同文案。于是“这是计划中的对照取值，其证据分类尚未适配”被显示成“来源没记、是否默认也未知”。此外 acquisition 仅识别 `web_snapshot`，其他取得方式一律落入“未记录”，也不能据此证明原论文材料缺少来源。

这证明当前可见行的显示结论不可靠，不证明所有历史参数都有完整文献出处。应区分记录定位、文献证据、设计取值与工具默认，按已有记录映射；只有已核实的实际缺失才显示缺失，不能要求 Agent 给不存在的合同字段补表。

当前面板统计本轮/关联参数共 88 行，HTML 参数区的 26 KiB 预算只实际输出了 14 行及省略入口。本探针统计是实际可见行，不是对全部 88 行的来源审计。

## 3. 中文化停在标题和枚举，未形成可读的中文内容层

这 14 行的参数名均为 ASCII 原始 scientific_path。`_proposals` 直接用 scientific_path 作为名称，计划正文和理由也原样显示。`render_presentation` 只将已有中文且较短的摘要直接展示；其他正文折叠为“英文原文/报告原文”，没有提供中文说明。`_goal_panel` 采用相同处理。因此中文菜单和卡片标题并没有解决英文报告的阅读成本。

修订须把已有科学内容的中文呈现与原文追溯分开：普通 UI 字段、类别和说明由展示代码本地化；科学正文若增加中文译文或摘要，须保留对应原文、版本及来源，不让控制层自行改变科学结论，也不增加一次必跑的科学关卡。当前尚未实施这些修订。

## 核验范围

安装源码比对已于前次确认；本次通过既有用户会话管理凭据取得只读浏览 scope，再读取当前页面和精确字段原件。仅一次 read-access POST，其余 GET，无绑定、审批、执行或归档写入。探针耗时 0.414 秒，峰值 24.14 MiB，临时凭据已删除；资源日志为 `parameter-source-probe.json`。没有运行全量测试或调用新的科学 Operation。
