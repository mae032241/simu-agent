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

v2 数字化器用前向/后向代价选择二维连通像素支撑上的路径。
有引导身份支撑的组件保留自然起止和缺口，观测可延伸到 seed 端点以外。
组件从有实际支撑的内部身份锚点向两侧采用相同自然终止规则增长，
水平翻转不能使无关前缀获得资格；等价锚点保留竞争证据。
无关长线不能覆盖所选轨迹或填补两端缺口；重获依据引导残差和像素容差，
仍无法分开的合并支路保留歧义。
歧义代价只按候选路径实际分歧的列数比较；延长公共前缀或尾段不改变局部判定。
引导点选择路径，坐标来自图像中心与局部法线截面，保留尖峰帽端。
solid、dashed、dotted 线型贯穿请求、manifest 和重绘；原图空白列仍保留为缺口。
同列粗线或陡坡不证明物理多值，宽度本身不禁止插值。仍无法区分的竞争连续路径
保留候选范围与身份歧义；不连通支撑和科学用途限制禁止跨越插值。
相邻列的不连通笔画依据 CSV 已记录的像素支撑范围切断插值与重绘段，
两端观测保留各自段内的合法资格；无支撑范围字段的旧表保持原语义。
CSV 定位几何分别给出图像法线线宽、提取轨迹斜率与一个像素的分辨率，
不把整个候选支撑范围当作定位误差。保守界为像素单位的 `dx=0.5`、
`dy=max(0,(normal_width-1)/2)*sqrt(1+slope²)+0.5*(1+abs(slope))`，
分别经各轴标定传播，不声称是统计误差。
CSV 的 `observed`、`identity_resolved`、定量资格和
`interpolation_eligible` 表示不同事实；manifest/报告计数及叠图使用相同记录。
数值重绘与曲线消费者不得跨越不允许插值的区间连线。
交点消费者拒绝不可用曲线，即使其端点仍可作为原始观测读取。

作者可在各曲线 `use_limits` 中给出 `pixel_bbox`、科学理由 `reason` 与用途
`applies_to`（`quantitative_measurement`、`interpolation` 或 `all`）。这些字段保留
原图观测并限制用途；`exclusion_regions` 移除非数据像素。逐行资格、候选范围、
缺口与共享组仍由程序导出。CSV 的 `use_limit_indices` 指向 manifest 中完整的科学理由。
manifest 各曲线记录全局与接收方合并后的有效 `exclusion_regions`；
共享分配和 CSV 校验均拒绝排除区内的 raw 或 subpixel 观测坐标。
选中的 v2/v7 图族还将排除与 `use_limits` 和原封存请求逐项核对，禁止 manifest 静默遗漏。

共享组保留各直接拥有者自己的坐标；本色被覆盖的拥有者可以保留关联可见源的
`shared_pixel` 观测。共享不会自动导致无效，近邻坐标也不会被强制统一。
主 CurveBundle 和规范化审计都保留共享依赖；是否独立计权由评分合同决定。
历史 overdraw 复制记录保留原语义。新族使用 `curve-figure-digitizer.v2` 与校验器 v7；
已有 v1/v6 选择按原报告版本和原字节重放。提取变化须产生新的完整证据族。

输入诊断指出可修改的科学字段。程序生成的图族无法通过自身完整性校验时，
返回 `figure_generation_inconsistent`，明确是程序缺陷，不要求作者编造机械共享字段。
机械完整性或忠实性审查不产生科学结论。
