# 科研论文复杂曲线证据提取实施计划

## 1. 目标与边界

本计划补齐 alpha 科学闭环的证据入口：`evidence_extractor` 必须能够从冻结论文图像中生成可审核、
可追溯的曲线数据和图例绑定，而不是只提交文字摘要或依赖工作区中来源不明的 CSV。

本轮以 Fig.7、Fig.10 和 Fig.13 为资格对象，Fig.4 只作为冒烟测试。目标不是实现不受约束的通用
计算机视觉系统，而是实现一个配置驱动、确定性、失败关闭的科研图表数字化能力。面板、坐标标定、
图例区域和必要的跟踪种子可以由 worker 明确声明；工具必须验证这些声明并报告不确定性，不能在
歧义时猜测曲线身份。

不在本轮范围：三维曲面、热图数值反演、照片定量、任意 OCR、自动接受数字化结果，以及直接覆盖
现有 `targets/` 文件。

## 2. 成功条件

1. Worker 继续提交一个 `RoleResultEnvelope` 主结果，同时可按角色合同提交受限附件集合。
2. 控制面验证所有附件的路径、类型、数量和字节上限后逐个注册为不可变 Artifact；worker 不接触
   Artifact ID、哈希、任务 ID 或控制面名称。
3. `scientific-paper-evidence` skill 能处理线性/对数轴、多面板、同色不同线型、彩色重叠曲线、散点
   和分段拟合线，并生成逐系列 CSV、双重叠加图、图例映射和歧义报告。箱线图统计元件是曲线
   alpha 门之后的独立扩展。
4. 每个数据系列必须绑定图例、图内标注或 caption；无法唯一绑定时状态为 `unresolved`，不得形成
   “已正确提取”结论。
5. 审批 UI 在同一次精确 subject 集中展示原图、叠加图、系列映射、指标和歧义；只内联经过检查的
   PNG/JPEG/WebP，其他对象保持下载。
6. Fig.7、Fig.13、Fig.10(a/c/d) 的人工曲线真值门全部通过后，才允许另行创建新修订并迁移下游
   曲线 target；Fig.10(b) 通过独立的箱线图资格门后才能迁移统计量。

## 3. 对象与协议

### 3.1 Worker 输出

旧任务保持：

```text
output/result.json
```

启用附件的角色增加：

```text
output/bundle.json
output/collections/<collection>/<item>
```

`bundle.json` 只包含 task-local 的 collection、item、media type 和相对路径。控制面拥有 Artifact kind、
Schema、身份、哈希、父链和注册。首个 profile 为 `scientific-paper-evidence`，至少包括：

| collection | 允许类型 | 作用 |
|---|---|---|
| `figure_manifest` | JSON，恰好一个 | 面板、坐标、系列、绑定、指标、歧义总表 |
| `source_panels` | PNG/JPEG/WebP | 冻结原图或面板裁剪 |
| `audit_overlays` | PNG | 几何保真叠加和身份审计叠加 |
| `curve_tables` | CSV | 每个语义系列的像素坐标、数据坐标和不确定度 |

主 `ScientificIntake` 的父链包含附件；附件的父链包含原论文/图像输入。任务状态继续保留现有主输出
名称，并通过 `task_outputs` 枚举附件名称。

### 3.2 图表语义

```text
Figure -> Panel -> Axis
                -> SemanticSeries -> Primitive(line/marker/fit_segment/boxplot)
                -> LegendEntry / Annotation / Caption
                -> Binding
```

`Binding` 必须记录可见文字、视觉编码、绑定来源、置信度、备选项和状态。Fig.10(d) 的拟合线作为
Sample 1/2 的子图元，与对应颜色和 Ea 标注绑定，而不是伪造四个不存在的图例项。

## 4. 实施工作包

### PE-0：冻结真值和非循环验收

- 从原始 PDF 确定 image object、页码、尺寸和哈希。
- 单独标注面板范围、坐标刻度、图例项、系列数量和稀疏像素锚点。
- 现有 CSV 只作差异诊断，不作为真值生成源。
- 真值不得包含完整论文图片；测试使用合成图，真实论文资格数据留在研究实例的不可变输入中。

### PE-1：有界多 Artifact Worker 协议

- 为角色输出合同增加默认空的 collection specs，保持旧任务字节兼容。
- 物化 `bundle.json` Schema 和 collection 目录。
- 扩展现有 validate/finalize-file 生命周期，不增加第二套任务状态机。
- 拒绝路径穿越、符号链接、未声明文件、重复名称、类型不符、缺失必需项和所有越界情况。
- 以校验后的 bundle manifest 为集合协议记录，注册子 Artifact 并持久化归一化任务输出映射；
  实现 `task_outputs`。bundle 内容可由不可变子 Artifact 与归一化映射重建，不另造科学结果对象。
- 对启用 profile 的隔离分析开放 `/outputs`，分析结束后立即检查数量和总字节。

验收：旧单输出测试完全不变；任一附件失败时任务不完成且没有可枚举的部分输出。

### PE-2：`scientific-paper-evidence` skill

- 使用一个 Pillow + 标准库的配置驱动 CLI，绑定源图哈希和尺寸。
- 支持每个 panel 独立的 linear/log10 标定、排除区和误差传播。
- 使用颜色、线型周期、marker、连续性、斜率和种子做多轨迹跟踪。
- 输出逐系列 CSV、原样式保真叠加、唯一审核色身份叠加和 canonical manifest。
- 遮挡记录为 `occluded`，低置信匹配记录为 `unresolved`，禁止静默插值或覆盖现有目录。

验收：合成 Fig.7/10/13 类测试可重复、跨两次运行得到相同 CSV/JSON；错误哈希、错误坐标、空轨迹、
重复系列和不完整绑定均失败关闭。

### PE-3：角色与审批接入

- `evidence_extractor` 在存在科研图时必须使用该 skill，并将图像证据与正文事实分开。
- `ScientificIntake` 只承载科学问题和来源化基础；详细像素证据由附件 manifest 承载。
- 审批 UI 显示面板、系列、图例/标注绑定、点数、覆盖率、不确定度和歧义。
- 图像预览通过带 token 的同源端点；保持 `nosniff`、转义和默认下载语义。

验收：审批决定仍绑定完整有序 subject 集；移除或替换任一图、CSV 或 manifest 都会使原决定失效。

### PE-4：真实论文资格矩阵

| 门 | 必须提取的对象 | 特殊门槛 |
|---|---|---|
| Fig.7(a) | SIMS、D∝C fit、erfc fit | 3/3；两条蓝线的点线/虚线身份不可交换 |
| Fig.13 | Sample 1、Sample 2 | 2/2；密集起伏和截止边界保留 |
| Fig.10(a) | 两样品 × 两温度，共 4 条 | 全程不得在重叠区交换身份 |
| Fig.10(c) | Measured + 4 components + Jtotal | 6/6；Measured/Jtotal 遮挡必须可审核 |
| Fig.10(d) | 2 组散点 + 4 个拟合段 + 4 个 Ea 绑定 | 子图元归属正确，不伪造图例 |
| Fig.10(b) | 两个箱线图的 min/Q1/median/Q3/max/mean | 非曲线扩展；本轮明确不当作连续曲线 |

共同门槛：系列数和语义绑定 100% 正确；坐标刻度重投影最大误差不超过 3 px；人工锚点误差不超过
源线宽允许范围；任何超限、遮挡或歧义必须出现在 manifest 中。

### PE-5：迁移与闭环

- 通过资格门后，以新修订 Artifact 保存曲线，不原地覆盖旧 CSV。
- evidence auditor 独立审核 manifest、叠加图和正文锚点。
- 只有审核通过的曲线才能进入实验设计、scorer 或 TCAD 对比。
- 在真实 evidence intake → human review → downstream task 链完成一次恢复测试。

## 5. 执行顺序与停止规则

执行顺序为 `PE-0/PE-1 -> PE-2 -> PE-3 -> PE-4 -> PE-5`。PE-1 与 PE-2 可并行，PE-3 依赖两者
的稳定接口。真实资格失败时，只修复最早失败层；不得用手工改 CSV 绕过 skill，也不得因 Fig.4
通过而跳过 Fig.10。

本计划是 Alpha 主计划中“可信证据入口”的子计划。它不改变当前 TCAD 科学结论，也不授权新的
仿真执行。

## 6. 2026-08-09 执行状态

- PE-0：已完成本轮曲线对象的 PDF/image hash、尺寸、面板、坐标、图例和稀疏锚点冻结。
- PE-1：已完成。旧单输出保持兼容；新增受限 collection profile、bundle 校验、子 Artifact 注册、
  归一化输出映射、`task_outputs` 和隔离 `/outputs`。
- PE-2：已完成 alpha 曲线范围。真实资格运行额外发现并修复 partial-domain `pixel_range` 计量 bug。
- PE-3：代码完成；角色合同、scheduler profile/审批 subject-set 指令和审批 UI 已接入。尚待安装后
  的真实实例审批恢复测试。
- PE-4：Fig.7(a)、Fig.13、Fig.10(a/c/d) 的全部曲线、marker 和拟合段已通过。详见
  `docs/SCIENTIFIC_PAPER_EVIDENCE_QUALIFICATION.zh-CN.md`。Fig.10(b) 为箱线图，不属于“每条
  曲线”alpha 门，统计图元提取顺延为独立扩展。
- PE-5：未执行。不得据当前资格测试覆盖旧 target 或写成已批准科学结论。
