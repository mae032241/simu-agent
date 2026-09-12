# 可选论文图证据插件

本插件通过唯一的 `scidiscovery.plugins` 入口注册五个 Operation：

- `science.figure.request.prepare.v1`：智能体查看精确 PDF 或栅格来源，声明图框、刻度和曲线身份，
  并查看原图叠加图与数值重绘图后生成类型化数字化请求；
- `science.figure.evidence.materialize.v1`：确定性恢复来源图并逐项物化清单、叠图、曲线表和报告；
- `science.evidence.extract.figure.v2`：从完整附件族创建单一 `ScientificIntake`，或在同时绑定旧
  Intake 和精确非通过审查时由同一 Operation 产生完整修订版本；
- `science.figure.evidence.audit.v1`：独立审查 Intake、完整附件族及其精确来源；
- `scidiscovery.curve-bundle.figure-evidence.v2`：在独立审查通过后机械规范化曲线证据。

程序只负责真实像素取点、坐标换算、统计、共享像素标记和输出生成，不执行 OCR、自动图框、自动识轴或
科学身份判断。默认 TCAD 安装不包含本插件。提取和修订都只提交一个完整 Intake；后续 Intake 的独立
审查仍由单独 Operation 完成，但不属于曲线请求智能体的自检环节。

Agent 选择 PDF 页码和文档图像索引，或绑定的栅格图像。预览与提交时，程序从原文件生成恢复图像摘要、
尺寸和恢复工具信息。unresolved 请求只需保留原文件身份、已知的部分信息及明确缺口，不必编造恢复
元数据；只有定量提取的准入要求 ready 状态和完整恢复信息。
