# R5 E0：Fig.4 开跑合同与负控证据

日期：2026-09-04

状态：**完成**

本文件只冻结 E1—E6 所依赖的来源事实、结构负控和科学边界，不产生新的论文图科学证据，
也不授权端到端实验开跑。

## 1. 精确来源

- 冻结 PDF：
  `deliverables/m7-full-science-gpt56-20260903/state-resumed-m7-test0/artifacts/sha256/75/0c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`
- PDF SHA-256：
  `750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`
- 文件大小：4,714,974 字节；页数：15。
- Fig.4 位于 PDF 第 6 页；`pdfimages -list` 将目标嵌入图列为全局图像 47、PDF 对象
  `241`，RGB，1000×815。该页的另一幅 2100×812 JPEG（对象 `240`）是 Fig.3，明确排除。
- 对对象 `241` 的只读恢复得到原始 PPM SHA-256：
  `d68e77cc331558d2ddb715b72939a5fb4ea23fb6d0691a4ec437c12418be468f`。
  E1 的正式恢复器将其规范化为 RGB PNG 后的 SHA-256 为
  `88358eb5658c75cf7eddb3cb71fab5f2f8d5bf0d6e7252481193142adb19be5a`，大小 226,099 字节。
  E0 临时恢复结果只用于人工核对；正式请求和物化必须从冻结 PDF 独立重放，不能引用 `/tmp` 预览文件。

论文正文将 Fig.4 描述为单层 In0.83Al0.17As 与 In0.83Ga0.17As 的 SIMS 曲线，样品在
480°C 生长 8 分钟。来源中不存在本任务此前误提的 800°C/900°C 曲线；任何后续 Operation 都不得
重新引入这些条件。

## 2. 历史负控，而非本次资格

`docs/SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md` 中的历史资格记录只冻结如下预期边界：

- InGaAs 红色实线曾恢复 806 行、可见率 0.995062、最大间隙 2 像素，可形成直接可见证据；
- InAlAs 黑色实线曾恢复 589 行、可见率 0.727160、最大间隙 55 像素，因覆盖/遮挡保持
  `unresolved`。

当前活动 M7 CAS 中没有找到可与这次冻结 PDF 精确闭合的旧请求、清单、CSV 和叠图全家族。E1
实施后在只读历史状态中定位到旧请求及旧来源 PNG；该请求的 PDF 摘要、页码和对象号与本次冻结来源
一致，旧 PNG 与 E1 恢复的规范化 PNG 像素逐点一致，仅 PNG 文件编码摘要不同。旧请求的坐标、种子、
颜色和跟踪参数可作为 E2 的只读科学对照，但旧路径、旧 CSV、旧清单和旧资格决定均不得进入新父链，
也不得从旧 CSV 反推请求或继承旧资格。上述数字只用于检测科学降级：新实现不能为了流程通过而把
黑线强制标成合格，或因黑线未决而丢弃红线。

只读历史请求位置：
`.scidiscovery/staging/fig4-live-recovery-20260825/state-uireuse-probe-20260825-3/workspaces/ses_b0c05ca874134231b3881e89e90b2964/analysis/figure4_spec.json`。
只读历史 PNG SHA-256 为
`2c81663ced9ebfd43e1d053167468d2c64be22fca1a1ef85c8127ddbe7787bbd`；规范化 PNG SHA-256 为
`88358eb5658c75cf7eddb3cb71fab5f2f8d5bf0d6e7252481193142adb19be5a`，二者均为 1000×815，解码为
RGB 后逐像素相同。

## 3. 结构负控

E0 聚焦测试命令：

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_curve_figure_digitization_tool.py
```

结果：`11 passed in 1.48s`。

测试与目录检查共同证明：旧 `science.evidence.extract.figure.v1` 声明 Agent 集合输出；本地运行后端
报告 `agent_collection_outputs` 不受支持，因此该操作只在诊断视图出现，公共目录不可调度。仅把
`curve_figure_evidence` 加入 Fig.4 安装 profile 不能修复这条断边。

## 4. 后续成功与停止条件

后续必须同时证明：请求 Agent 真实调用图像检查工具、PDF 图像可确定性重放、物化附件逐项登记、
单输出 Intake、独立图审查、精确人工审批、真实求解器执行、结果证明、曲线评分与诊断均具有控制面
记录。科学结果允许为 `unresolved`、`inconclusive` 或“不确定”。

若 E2 不能从上述冻结 PDF 独立重现实图边界，必须停在论文图能力修复；禁止改用旧 targets 曲线、
手工截图、临时预览或放宽校验来伪造闭环。
