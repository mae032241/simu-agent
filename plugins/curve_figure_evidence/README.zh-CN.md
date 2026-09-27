# 可选论文图证据插件

插件提供一个完整作者任务、独立审查和规范化消费者；默认 TCAD 安装不包含此插件。

- `science.evidence.extract.figure.v3`：一个作者在同一工作区查看精确栅格或 PDF、描述可见图框/标定/身份、预览提取、显式保存选定证据族、自检并提交 ScientificIntake。
- `science.figure.evidence.audit.v2`：另一 Agent 使用 `paper_source`、Intake 的精确控制清单 `figure_provenance` 和全部 `figure_family` 附件独立审查。
- `scidiscovery.curve-bundle.figure-evidence.v3`：完整证据族与其精确独立审查通过后规范化曲线。内部数值规范化 profile 仍是 v2；它不是旧公开 Operation 的别名。

作者连续使用 `worker_curve_figure_inspect_source`、`worker_curve_figure_preview` 和
`worker_curve_figure_save`。ready 请求必须有相同物化请求的控制层预览完成回执。
显式 save 选择一个请求，将全部正式文件及选定族清单登记为不可变 Artifact，并返回
只读本地路径和编写 Intake 所用的精确证据别名。相同 save 重试幂等；改变选择必须产生新 Run。
部分保存恢复按原件、请求、data_item 和字节精确复用原回执，即使输入别名改变也只补缺件。
失败调用保留在控制恢复清单中；缺件、来源被换或混入未选中文件时无法完成 Intake。

Intake 的不可变父对象是控制清单；控制清单绑定选定请求、算法身份、原件、文件和尝试。
消费者必须按 Artifact 精确身份绑定全部保存成员，包括选择记录。缺件、篡改、混用其他
证据族清单及复用旧 Intake 审查均拒绝。工具保存和忠实性审查均不自动授予定量资格。
修订必须同时绑定旧 Intake、其未通过审查、原 `figure_provenance` 与完整 `figure_family`。
只修改文字或局限时，用 `worker_curve_figure_reuse` 精确保留原回执和 Artifact 身份，
不重新数字化；输入别名不得覆盖保留的原 tool evidence 别名。新 Intake 与控制清单形成
新身份，必须重新独立审查，不继承旧判定。确需改变提取时显式 preview/save 新族，
同一 Run 不能混用 reuse 与新选择。

PDF 页文本与嵌入原图恢复继续保留。作者定位页码/图像序号并查看原件；确定性代码负责
哈希、尺寸、像素提取、CSV、报告、叠图和数值重绘，不执行 OCR、自动图检测或身份猜测。
无法确定图像/标定/身份时，只封存带显式局限的 unresolved 请求，不声称已提取曲线；
可以忠实审查，但不能产生定量曲线库。旧请求作者、独立物化及第二 Intake 作者入口已删除，
不提供兼容别名。
