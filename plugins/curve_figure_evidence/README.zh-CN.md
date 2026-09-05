# 可选论文图证据插件

本插件通过唯一的 `scidiscovery.plugins` 入口注册五个 Operation：

- `science.figure.request.prepare.v1`：从精确 PDF 或栅格来源生成类型化数字化请求；
- `science.figure.evidence.materialize.v1`：确定性恢复来源图并逐项物化清单、叠图、曲线表和报告；
- `science.evidence.extract.figure.v2`：从完整附件族创建单一 `ScientificIntake`，或在同时绑定旧
  Intake 和精确非通过审查时由同一 Operation 产生完整修订版本；
- `science.figure.evidence.audit.v1`：独立审查 Intake、完整附件族及其精确来源；
- `scidiscovery.curve-bundle.figure-evidence.v2`：在独立审查通过后机械规范化曲线证据。

插件不复制曲线算法，而是依赖 `curve_score` 中的确定性数字化、校准、验证和转曲线包实现。默认 TCAD
安装不包含本插件。提取和修订都只提交一个完整 Intake；独立审查仍由单独 Operation 完成。
