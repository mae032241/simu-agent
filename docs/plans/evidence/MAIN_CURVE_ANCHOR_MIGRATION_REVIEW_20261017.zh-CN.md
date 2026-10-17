# main 曲线实际锚点移植：独立静态审查

结论：**当前冻结三文件静态 PASS**，可由root唯一串行运行6个新增目标；不是科学提取/真实论文图资格。评审者只读源码/文档、stdlib AST对照与文件SHA256；未运行测试、项目import、安装、模型或Git，也未修改main或作者代码。

## 来源与范围

已独立核对 `/123/main/plugins/curve_figure_evidence/curve_figure_evidence/figure_line_tracker.py` 与dev目标同为 `aeb6ca7f701624e15bdb83813b6fe4e9f9d2f81fb3330895f993d70d9f03578f`。这份本地WIP与原[选择性评估](MAIN_THIN_INTEGRATION_ASSESSMENT_20261017.zh-CN.md)一致；不等于合并main提交或其整套未提交修改。本轮不以旧评估的拉取失败推断最新远端状态；远端差异由root单独核实。

定点范围：tracker四函数相关改动、新 `tests/operations/test_figure_anchor_tracking.py` 的6个函数及[实施账](MAIN_CURVE_ANCHOR_MIGRATION_20261017.zh-CN.md)。不引入旧UI、SQL、Root/MCP或服务测试架构。

## 语义复核

- 正权重均值夹回当前真实像素支撑，避免浮点误差让单点落在支撑外；未改原像素或以平滑替代观测。
- 连通分量不再按全局anchor数量互相淘汰；真实断段仍须实际锚或guide近邻支撑，空列不补值、不跨gap连线。
- 每个实际anchor各自向两侧生长，guide-only分量仍只用最佳接续site。整数列先在原图round再变换方向，避免负方向半像素偏列。
- 候选的最优可达前缀与后缀在该像素会合后才累计实际anchor范围；同列互斥路径不能借用另一分支anchor。更强实际identity支持优先，同等支持仍留多个alternatives，由公开TracePoint保identity_ambiguous和禁止插值。

## 最小验收与限制

新增6个用例分别证伪断段被尾frame吞掉、单分量只从一个anchor长、straight guide干扰夺取弯曲真实路径、半像素/水平镜像偏列、互斥分支借锚与真实等支撑歧义、加权单点坐标超支撑。前五个含水平镜像，oracle来自固定绘图坐标或加frame前raster；不是把生产实现的另一遍输出当真值。新模块只导Pillow、pytest与公开trace接口，不依赖旧服务/安装fixture。

实际锚数量增多会增加生长次数；当前没有大图/密集候选时间或RSS实证，不应由小图通过承诺这些上界。完整CSV/normalizer/curve-score消费、真实论文图legend身份与科学结论均不在本节点资格。无需安装矩阵或全量回归；若首批出现共享轨迹问题，再按具体失败选原邻接/镜像负控。动态结果由root执行后追加，当前未记为通过。
