# 科研论文曲线证据能力资格记录

## 结论

截至 2026-08-09，`scientific-paper-evidence` 已对论文原始 PDF 中的 Fig.7(a)、Fig.13、
Fig.10(a)、Fig.10(c) 和 Fig.10(d) 完成真实图像资格运行。共核验 21 个语义对象：15 条连续曲线、
两组 marker 数据和四个 Ea 拟合段；全部 manifest 为 `qualified`，图例或图内标注绑定均为
`matched`，且生产 schema 复验通过。

这不是论文科学结论的批准，也没有覆盖工作区现有 `targets/`。结果只证明当前确定性技能能够在
这些冻结图像上生成可审核的曲线证据。Fig.10(b) 是箱线图而非曲线，当前 alpha 曲线资格门不把它
伪装成连续系列；箱线图的 min/Q1/median/Q3/max/mean 语义提取仍是独立待办。

## 冻结来源

- PDF：`workspace/ingaas_inalas_photodetector/inputs/papers/123103_1_5.0242861.pdf`
- PDF SHA-256：`750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`
- Fig.7 embedded image：1000×582，SHA-256
  `7010bc72050bb69b100b91510eed448cc76c658d953d05f17288fbca0ae4c410`；PDF page 9，
  object 289。
- Fig.10 embedded image：2100×1590，SHA-256
  `237b01b883d72164fafd3b7a10bfc8745860d4f1cd949adab4aa2a549488c167`；PDF page 12，
  object 330。
- Fig.13 embedded image：1000×785，SHA-256
  `1c7d35a65db07e390094b70272b6cb6b6621a5adb0f27a87c728352e769c8c3f`；PDF page 14，
  object 349。

图像由 `pdfimages` 从上述 PDF 的 embedded image object 恢复；技能同时校验 PDF、图像哈希和
图像尺寸，不回退为来源不明的页面截图。另以 `-f/-l` 分别只恢复 page 9、12、14，所得三个
JPEG 的 SHA-256 与上述值逐项一致。

## 资格矩阵

| 对象 | 绑定对象 | 点数 | 最低可见率 | 最大断点 | manifest SHA-256 |
|---|---:|---:|---:|---:|---|
| Fig.7(a) | 3/3 | 906 | 0.4016 | 13 px | `f9a95665d7ef6679f30a836502656008cadaaa830edcc7894228ff2ae994cba2` |
| Fig.13 | 2/2 | 1345 | 0.9805 | 3 px | `273e5f0657cf29d2b20aff0e6291c8101944a6ca9e73d5f1b3216b5e6b86b8a7` |
| Fig.10(a) | 4/4 | 2421 | 0.5805 | 7 px | `db806da49bc54bb72623c9e77ad87dcdd4300c10db9d480f6bdd585e6757098c` |
| Fig.10(c) | 6/6 | 3244 | 0.6289 | 11 px | `38f4f37d7b0377480e5f3fdd25df0a32d9a44e562943aaf896a822ac4bbd2d8c` |
| Fig.10(d) | 6/6 | 689 | 0.5889 | 11 px | `a4348add4bff99d5c0643cb4f5aa3af803840e625004a4a5430e2fc5a94c6331` |

Fig.7 的低可见率来自 dotted/dashed 线型的空白周期，不是连续实线缺失；线型、最大断点和身份
叠加图共同参与门控。Fig.10(d) 的 6 个对象包括两组各 8 个 marker，以及分别绑定
`Ea=0.43eV`、`Ea=0.45eV`、`Ea=0.19eV`、`Ea=0.2eV` 标注的四个拟合段。

## 人工图像复核

- Fig.7：SIMS、`D∝C fit` 和 `erfc fit` 的审核色轨迹分别覆盖可见像素；两条蓝线未交换，
  SIMS 的陡降和低浓度尾部保持。
- Fig.13：Sample 1/2 的密集局部起伏和 2400 nm 附近截止边界均保留。
- Fig.10(a)：黑/蓝、solid/dashed 四条轨迹在近零偏压的陡峭区和正偏压重叠区未换线。
- Fig.10(c)：Measured、Jdiff、Jgr、Jshunt、Jtat、Jtotal 六条轨迹与图例一一对应；
  Measured/Jtotal 的近重叠仍由颜色和虚线身份分别审核。
- Fig.10(d)：两组 marker 均得到 8/8 个元件；四段拟合线绑定图内 Ea 标注，而没有伪造额外图例项。

每个面板的线性或 log10 标定均声明 1 px 重投影误差上限，低于计划中的 3 px 门。资格运行的
identity/fidelity overlays 已逐图查看，生产 `FigureEvidenceManifest` validator 对五个 manifest
再次严格验证通过。

## 资格过程中暴露并修复的问题

1. 普通 `line` 原先不支持只在部分横轴区间存在的真实曲线，排除的前导空白会被错误计入
   `max_gap_px`。现在 `pixel_range` 对 line、marker 和 fit segment 统一定义搜索与计量域。
2. `worker_run_analysis` 原先没有把技能脚本挂入隔离环境。现在安装包中的脚本以只读方式出现在
   `/tools/digitize_plot.py`，并有真实 sandbox 调用回归测试。
3. 分步分析原先会因尚未写齐必需附件而过早失败。分析阶段现在立即执行上限检查，最小数量只在
   validate/finalize 阶段执行。
4. manifest 的 provenance 原先只做内部 schema 校验，没有与 sibling bytes 交叉核对。现在控制面
   要求清单精确枚举所有 sibling，并逐项校验 SHA-256、字节数和 media type。
5. 首轮真实资格 spec 曾误把临时提取文件编号当成 PDF 页码/对象号。通过 `pdfimages -list` 独立
   复核后，旧 manifest 作废并以上述 page/object 重新运行五个门；文档同时明确 object ID 是需由
   恢复步骤核验的 provenance assertion，不是 Pillow 脚本能从 PDF 内部自动证明的关系。

## 2026-08-15 间隙语义回归与真实图复验

Fig.4 的一次正式证据修订暴露了两个确定性缺陷：曲线表把相隔多个源像素列的端点重新编号为相邻
`point_index`，support renderer 因而画出一条原图不存在的直线；renderer 还把低 alpha 的 RGBA
遮罩直接转换为 RGB，导致遮罩成为不透明色块。当前实现已作如下修复：

- `line`/`fit_segment` 的 `point_index` 增量必须与 `pixel_x_raw` 增量完全一致，验证器拒绝重编号；
- renderer 同时按 point index 和原始像素 x 切分 run，绝不跨源像素列间隙连线；
- 遮罩先与白色背景确定性合成，再写 RGB，不再出现不透明橙/灰块；
- 新增 seed guide corridor。即使陡峭前沿允许较大纵向步长，tracker 也不能跳到同色坐标轴、文字或
  其他分支；
- 连续实线出现超过容差的未声明缺口时 fail closed。只有原图可见的遮挡/中断才能声明
  `declared_gap_ranges`，不能用端点 mask 或重编号掩盖 tracker dropout。

修复后从同一冻结 PDF 重新恢复真实图像，逐项运行 digitizer、bundle validator、fidelity overlay 和
完整 observed-support renderer，并人工对照原图。像素一致性数字是独立重读 CSV 的
`pixel_x_raw/pixel_y_raw` 后，与源图 descriptor 重新计算的欧氏颜色距离；所有行均在各自配置容差内。

| 图 | 系列 | 行数 | 可见率 | 最大空档 | 像素颜色合规 | 结果 |
|---|---|---:|---:|---:|---:|---|
| Fig.4 | InAlAs measured | 589 | 0.727160 | 55 px | 100% | `unresolved`：黑线被其他轨迹覆盖的区段不可直接观测，不伪造连续性 |
| Fig.4 | InGaAs measured | 806 | 0.995062 | 2 px | 100% | 红色实线连续恢复；旧版伪直线/遮罩问题消失 |
| Fig.7(a) | SIMS / D∝C / erfc | 574 / 174 / 124 | 0.977853 / 0.465241 / 0.372372 | 8 / 12 / 15 px | 100% | `qualified`；同色 dotted/dashed 未换线 |
| Fig.10(a) | S1-300K / S2-300K / S1-140K / S2-140K | 588 / 621 / 348 / 318 | 0.924528 / 0.976415 / 0.547170 / 0.500000 | 14 / 15 / 14 / 35 px | 100% | `qualified`；solid/dashed 四轨迹未换线 |
| Fig.13 | Sample 1 / Sample 2 | 707 / 716 | 0.980583 / 0.993065 | 9 / 4 px | 100% | `qualified`；局部起伏和截止边界保留 |

Fig.10(a) 的复验先暴露了左轴/刻度被当成数据以及 Sample 2 (140K) 图例框少覆盖 6 px 的配置问题。
最终 spec 将定量域起点放在曲线首次清晰可见列，并按源图虚线的真实空白周期设置 `max_gap_px`；没有
提高颜色容差，也没有手改 CSV。Fig.4 的图级 `unresolved` 是预期的失败关闭结果：红线已经通过，
但黑线被覆盖的像素不能据颜色假定为可见黑色证据。该结果比强行让所有图返回 `qualified` 更符合
证据边界。

自动回归包括：源列间隙保存/重编号拒绝、renderer 不跨间隙、浅色遮罩、连续实线 tracker dropout
失败关闭，以及合成 Fig.7/Fig.10/Fig.13 复杂轨迹；focused suite 为 27 项全部通过，Skill
`quick_validate.py` 通过。Fig.7、Fig.10(a)、Fig.13 又分别从冻结 spec 写入全新目录重跑，所有
manifest、CSV、source panel 与 overlay 均逐文件 SHA-256 完全一致。仓库级 artifact-agent 回归为
645 项全部通过。

## 尚未完成的闭环

- 尚未在新研究实例中派发真实 `evidence_extractor`，也未通过本地审批 UI 形成完整 subject-set
  决定；当前是实现与资格验证，不是审批完成。
- 尚未把任何新曲线注册为替代旧 `targets/` 的新修订，也未触发 evidence auditor 或下游 TCAD
  scorer。
- Fig.10(b) 箱线图语义提取未实现；它不阻塞“每条曲线”的 alpha 门，但阻塞更广义的通用科研
  图表能力声明。
