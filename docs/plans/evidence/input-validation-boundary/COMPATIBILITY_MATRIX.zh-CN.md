# 与实际部署版本的合同影响矩阵

来源：catalog-installed.json（/opt/scidiscovery-m7/site，只读编译无实例访问）与 catalog-source.json（当前源码）；不是猜测HEAD等于部署版。

50项中20项变更、30项不变；ABI不变。新增缺省字段未使所有Operation失效。已纳入reviewer与可达组件传播。

| Operation | 合同变化 | 历史处理 |
| --- | --- | --- |
| `scidiscovery.curve-bundle.figure-evidence.v2` | 不变 | 沿用原合同身份。 |
| `scidiscovery.curve-reference-coverage.v1` | 不变 | 沿用原合同身份。 |
| `scidiscovery.curve-score.v1` | 不变 | 沿用原合同身份。 |
| `scidiscovery.objective-coverage.v1` | 不变 | 沿用原合同身份。 |
| `science.curve.contract.design.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.curve.contract.review.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.curve.error.analyze.v1` | 不变 | 沿用原合同身份。 |
| `science.evidence.audit.intake.v1` | 不变 | 沿用原合同身份。 |
| `science.evidence.audit.v1` | 不变 | 沿用原合同身份。 |
| `science.evidence.extract.figure.v2` | 不变 | 沿用原合同身份。 |
| `science.evidence.extract.v1` | 不变 | 沿用原合同身份。 |
| `science.evidence.qualify.v1` | 不变 | 沿用原合同身份。 |
| `science.evidence.revise-from-critic.v1` | 不变 | 沿用原合同身份。 |
| `science.experiment.design.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.experiment.materialize.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.experiment.revise.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.figure.evidence.audit.v1` | 不变 | 沿用原合同身份。 |
| `science.figure.evidence.materialize.v1` | 不变 | 沿用原合同身份。 |
| `science.figure.request.prepare.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.hypothesis.criticize.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.hypothesis.propose.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.hypothesis.revise.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.intake.revise.v1` | 不变 | 沿用原合同身份。 |
| `science.intake.split.v1` | 不变 | 沿用原合同身份。 |
| `science.object.review.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.objective.project.v1` | 不变 | 沿用原合同身份。 |
| `science.parameter.coverage.v1` | 不变 | 沿用原合同身份。 |
| `science.parameter.uncertainty.v1` | 不变 | 沿用原合同身份。 |
| `science.parameters.qualify.exception.v1` | 不变 | 沿用原合同身份。 |
| `science.parameters.qualify.pass.v1` | 不变 | 沿用原合同身份。 |
| `science.result.diagnose.curve-error.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `science.result.diagnose.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.control-equivalence.v1` | 不变 | 沿用原合同身份。 |
| `tcad.curve-bundle.sprocess-log.v1` | 不变 | 沿用原合同身份。 |
| `tcad.curve-bundle.sprocess-plx.v1` | 不变 | 沿用原合同身份。 |
| `tcad.deck-project-compare.v1` | 不变 | 沿用原合同身份。 |
| `tcad.deck-review-validate.v1` | 不变 | 沿用原合同身份。 |
| `tcad.deck.author.initial.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.deck.author.revise.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.deck.author.runtime-failure.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.deck.review.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.execution-context.project.v1` | 不变 | 沿用原合同身份。 |
| `tcad.parameter.evidence.audit.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.parameter.evidence.expand.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.parameter.evidence.extract.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.realization-snapshot-materialize.v1` | 不变 | 沿用原合同身份。 |
| `tcad.result.analyze.v1` | 变化 | 旧完成结果保留历史只读；新调用按现有历史/资格准入；旧活动Run不由新规则接管，失败材料可经明确draft_from进入新Run。 |
| `tcad.reviewed-deck-package.v2` | 不变 | 沿用原合同身份。 |
| `tcad.runtime-attestation.v1` | 不变 | 沿用原合同身份。 |
| `tcad.study.execute` | 不变 | 沿用原合同身份。 |

本矩阵不授予旧记录新资格，也不宣称真实研究实例已在新版本预检通过。历史兼容测试、旧合同保全和跨合同新Run交接测试提供工程证据；当前部署未修改。安装后只重做实际受影响的正常资格/审查动作，不重跑求解器来修合同。
