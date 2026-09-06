# R5 E5.4：通用自动图证据与生产案例插件删除计划

日期：2026-09-06。状态：修订计划已获[独立 GPT-6 复审 PASS](reviews/R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN_GPT6_REVIEW.zh-CN.md#6-修订计划复审最终-pass)；P0/G0 已完成；P1/G1 通用归属迁移与案例插件删除已完成；[P2 底层自动候选](evidence/R5_E5_4_P2_AUTOMATIC_DETECTION.zh-CN.md)已完成，并获[G2 独立 GPT-6 复审 PASS](reviews/R5_E5_4_P2_G2_GPT6_REVIEW.zh-CN.md#有界返工复审)，首轮 FAIL 历史保留。真实轴因缺 OCR 未决，不能称定量提取成功。P3–P6 尚未实施，未通过真实验收，不产生科学结果，不授权历史证据晋级。

本轮以最小改动优先，只关闭既定方案不能编译、不能表示结果、不能安装或不能可信验收的缺口。禁止改调度器、Run 生命周期、资格／审批机制或编译器，禁止新增中央字段、Operation、Agent、插件、注册表、状态机，禁止重写 curve_score/tcad_artifact 或扩展图型范围。下文领域 guard 的调整只实现现有入口对新结果形状的拒绝／接纳，不更改资格机制。

| 本轮新增修改 | 必要条件及边界 |
|---|---|
| B1：迁移函数、删除 normalizer 直接依赖、纯 curve smoke | 否则未安装 figure 时 curve 不能导入；只切出既有 figure 函数，不改通用评分 |
| B2：三种结果 schema、附件基数、领域 validator／修订 guard 与零表拒绝测试 | 否则未决结果不能表示或修订；使用现有完整族和生命周期，不新增中央表示 |
| B3／S2：独立精度与覆盖门、两个验收负例、实际读失败探针及证据措辞 | 否则扩大误差、缩小范围或可读答案可伪装验收成功；只修改测试验收，不进入科学算法参数或控制协议 |
| B4：合法资源边、摘要编译测试、离线供应与安装依赖负测 | 否则资源编译拒绝或安装后不可执行；只用现有组件边与安装预检，不修改编译器 |

S1 的 P0a 最小真实图探针作为风险建议记录：来源恢复、三刻度轴解和一条无 seed 路径可从既定 P2 验证前置，失败停止迁移，但本轮不新增强制阶段、提交或审查门，不改生产 Operation。红测试提交策略只是澄清已有阶段须保持可检验，不新增实现范围。S3 删除文件数事前审批，由已有 diff 审查覆盖内部拆分。

## 1. 决策与文档所有权

删除整个生产 `plugins/ingaas_fig4/`，包括评分和冻结几何编译两条 Operation。InGaAs、Fig.4、论文身份、材料标签、目标曲线、项目和科学比较要求都是 ResearchInstance 的不可变 Artifact 内容，不构成可安装领域能力。不能把原插件换名、复制到通用模块、作为隐藏默认配置或改成核心分支。

自动图证据由已有 `curve_figure_evidence` 负责；通用曲线合同、评分、误差分析保留 `curve_score`；TCAD 项目、原始输出解析与执行保留 `tcad_artifact`。复用唯一 `scidiscovery.plugins` 入口、OperationSpec、文件 Worker、现有 request → materialize → ScientificIntake → 独立审查职责链。工程阶段顺序不是科研调度 DAG。

| 文档及真实入口 | 所有权与处置 |
|---|---|
| `docs/ARCHITECTURE.zh-CN.md`、`docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`、`src/scidiscovery/operations/spec.py` | 保留现有控制与科学边界；本文不另建控制协议 |
| `R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md` | 现有 E5.3 活动问题入口；实施文档收口阶段补链到本文，不把提案记为已修复 |
| `R5_E5_2_FIGURE_QUANTITATIVE_AND_VALIDATION_CONTRACT_REPAIR_PLAN.zh-CN.md` | 部分取代：保留共享支持、来源绑定、忠实性审查的已实现规则；冻结几何和旧请求兼容目标不再约束 E5.4 新生产合同 |
| `evidence/R5_E5_2_DEPLOYMENT_PREFLIGHT.zh-CN.md`、M7.1 安装矩阵及既有审查 | 历史审计，原样保留；旧四插件部署通过不能证明本次安装、通用提取或资格 |
| 本文 | 唯一 E5.4 实施与验收提案；后续各阶段报告绑定精确提交、安装物和输入，不能现场改计划使失败变通过 |

实施时只修受影响中英文现行入口和链接；不批量清理历史叙事。本次没有重跑已有审计或读取生产状态库。

## 2. 已核对的生产引用与删除矩阵

以下依据当前文件实际引用，不以名字推断能力。`figure_compilation.py` 读取包内几何，核对冻结 PDF hash、对象 ID、图名、标签，生成轴、seed、局部范围；`transform_adapter.py` 固定筛选 `material == "ingaas"`、读取 `ZnTotal`、`scoring/SCORER_CONTRACT.v2.json`，包含固定浓度水平、floor 和项目指标。两者都不能整体迁移。

| 精确位置／内容 | 删除或迁移动作 | 去向与完成判据 |
|---|---|---|
| `plugins/ingaas_fig4/ingaas_fig4/plugin.py`：`ingaas.fig4-baseline-recovery.v2` | 删除 Operation、组件、输入输出模型及专用 gate | 不保留别名或新名字的同等案例 Operation；已存在通用评分按显式曲线合同工作 |
| 同文件 `_CrossingTriplet`、`_CurveMetrics`、`_BaselineRecovery`、`_MetricReport` 及 `ingaas.fig4-*` schemas | 删除材料／项目专用 schema | 科学水平和接受准则若仍需要，作为新的实例实验／曲线合同 Artifact；不得把整个旧 JSON 模型装入通用配置 |
| `transform_adapter.py` 全文件 | 删除 frozen scorer、PLX 读取副本、特定文件名和常量 | TCAD 原始解析使用 `tcad_artifact` 已有实现；评分使用 `curve_score`。必要通用缺口只能由两个无关用例和单独合同证明，禁止本轮顺带复制算法 |
| `figure_compilation.py`：`ingaas.fig4.figure-request.compile.v1`、`GEOMETRY` | 整体删除，不迁移编译器 | 通用 materialize 内部重放自动检测；不新增替代 compile Operation |
| `figure_geometry.json` | 从生产、wheel、发行包、默认 fixture、运行搜索路径删除 | 不迁移至通用插件或可读取的配置。已封存历史 Artifact 只读保留，不能作为新提取输入；测试可保留历史出处记录，但不能让被测程序读取答案 |
| `__init__.py`、插件 `pyproject.toml`、入口、依赖、package-data | 删除；最终整个目录不存在 | installed entry point、distribution、import 均不再存在 |
| `deploy/apply_ingaas_fig4_profile.sh` | 删除整个 wrapper | 使用通用 `deploy/reinstall.sh` 和显式安装变量；案例输入从实例导入，不创建替代案例安装脚本 |
| 根 `pyproject.toml` pytest `pythonpath` | 删除 `plugins/ingaas_fig4` | 普通测试不能靠 checkout 注入该插件 |
| `scripts/build_git_release.py` 发布目录 | 删除案例目录项 | 发行清单和归档均无案例代码、几何和 package-data |
| `README.md`／`.zh-CN.md`，`docs/INSTALL.md`／`.zh-CN.md`，`deploy/README.md`／`.zh-CN.md` | 删除可选案例插件安装说明和 wrapper 引用；替换为三领域插件显式示例 | 中英文不再建议安装案例插件；历史 `docs/TCAD_AGENT_REAUDIT.zh-CN.md` 相关说明标历史，不改造历史证据 |
| `tests/operations/test_ingaas_operation_plugin.py` | 删除案例 scorer 生产契约测试 | 由通用评分已有测试及案例插件缺席负测覆盖边界，不保留完整 scorer 为 fixture 插件 |
| `test_figure_semantic_compilation.py`、`test_m5_figure_review_closure.py` | 删除 GEOMETRY／案例编译导入，改为自动候选与完整物化族 | 真实 source → detector → intent → materialize；手填请求测试不能充当自动提取验收 |
| `test_catalog_installed_entrypoint.py`、`tests/operations/conftest.py` | 删除构建／安装案例 wheel 和读取 geometry 的探针 | 干净 wheel 探针只安装声明组合，证明无源码或答案回退 |
| `test_m4_scientific_semantic_bridge_removal.py`、`test_m5_plugin_ownership_and_default_surface.py` | 更新组成与所有权断言 | 不能通过过滤掉未知条目来伪造目录一致 |
| `test_m3_transform_adapter_removal.py`、`test_m3_transform_equivalence.py`、`m3_transform_equivalence_runner.py` | 去除旧评分生产路径断言；保留仍适用的通用 transform 边界 | 历史等价性不再是生产发布门；不以恢复旧 Operation 令测试通过 |
| `tests/fixtures/plugins/r5_e2e_tcad_plugin/*` 的专用 schemas、依赖、`runtime.py` 导入及 `tests/fixtures/r5_e2e_tcad/manifest.json` | 移除其作为当前生产验收依赖；把仍有价值的通用 TCAD 验证接回通用合同 | 旧 manifest 可留历史记录但不得被当前资格探针加载；不搬运整个案例插件到测试再作为安装依赖 |
| `tests/artifact_agent/test_deploy_scripts.py` wrapper 测试 | 删除案例 wrapper 成功断言，增加通用三插件及残留插件拒绝检查 | 真正经过 `plugin_selection.py` 和安装入口 |
| `scripts/r5_baseline_metrics.py` 案例词边界扫描 | 保留其检查用途，必要时更新扫描范围 | 禁止将禁止词从扫描器删除来隐藏案例残留 |
| `plugins/curve_score/curve_score/transform_adapter.py::bundle_figure_evidence_outputs` 及 `.figure_evidence_normalizer` 直接依赖 | 将函数切到 figure 包 `operation_transforms.py`，移除 curve 适配器的 figure import／export，保留通用评分函数 | 不反向导入 figure、不复制 normalizer、不留 shim；未安装 figure wheel 时 curve 适配器导入和通用评分 smoke 通过 |

实施 P0 再用 `rg -n 'ingaas_fig4|ingaas\.fig4|figure_geometry|SCORER_CONTRACT|ZnTotal'` 核对生产入口、测试安装配置和发布清单；命中逐项分类。`ZnTotal` 等合法 TCAD 字段不能全仓机械删除；历史记录和独立实例数据也不是生产插件。根核心当前没有该案例生产导入，不能为了删除插件反向加入核心识别案例名的逻辑。

## 3. 最小目标架构与权责

### 3.1 唯一候选机制

扩展现有 `worker_curve_figure_inspect_source`，对绑定 source 自动恢复页面、检测 plot、轴和线，生成只读候选叠图及候选记录。候选是一次工具计算的可重放文件，不是新数据库实体、注册表、Artifact 生命周期或 Run 状态。材料、图号、标签不是检测器配置。候选 ID 从源内容、检测器合同版本和确定性候选内容生成，不能取遍历不稳定的随机序号。

Agent 可读取原文、来源页面与叠图；只做 figure/panel 与科学目标匹配、选择已有 candidate_id、绑定可见标签或说明身份不可靠。模型不得输出或修改像素点、bbox、轴端点、tick 坐标、seed、颜色阈值、点数、范围、coverage、max_gap、CSV 或统计。禁止以自然语言隐藏这些参数，再由代码解析执行。页码也由检测器候选提供；不开放坐标、页范围或算法调参工具参数。

materialize 从同一 `paper_source` 和 intent 重放检测器，重新确认候选集合及 ID。工具工作目录不是下一个 Operation 的隐式输入，也不能从 Worker 的输出摘要拼装几何。无可靠轴解、身份不清、预算不足都产出有界未决证据，不要求 Agent 补几何。

### 3.2 OperationSpec 合同

以下沿用既有 Operation 身份，修改版本／schema／受编译资源摘要；部署后调度器仍只从 startup catalog 选择，不从本文硬编码调度。OperationSpec 结构和 ABI 不因这些领域合同修改而增加字段。

| 现有职责／Operation | 精确输入与输出 | 工具、上下文、校验 |
|---|---|---|
| `science.figure.request.prepare.v1` | 必需 `paper_source`；可选显式 `research_objective` 使用已有目标 schema、usage 为 prior_signal，防止问题仅存在聊天。输出新版 `figure_intent` | 现有文件写入工具、PDF 文本检查和升级后的只读 figure inspect、原生看图；不开放执行 shell 或参数化 digitize。输出 extra=forbid，只含 source digest、detector receipt、已有候选 ID、语义绑定、未决原因 |
| `science.figure.evidence.materialize.v1` | 必需 `paper_source` + `figure_intent`，取代外部输入手填 `figure_request`。输出 `figure_request` + 既有 `figure_manifest`、`validation_report`、`source_panels`、`audit_overlays`、`curve_tables` | support transform；内部检测重放、校准、追踪和序列化；不启动 Agent、不依赖先前工具路径。`figure_request` 是确定性产生的测量记录，新代际禁止直接把旧几何 request 当入口 |
| `science.evidence.extract.figure.v2` | 同一 materialize 的完整输出族，加 exact `paper_source`、`figure_intent`；修订时仍用成对 `prior_draft`、`change_request` | 现有 evidence Agent；输出完整 ScientificIntake。保留 complete_transform_family、revision parentage、源码命名闭合；只能科学解释，不生成数字证据 |
| `science.figure.evidence.audit.v1` | exact Intake + 完整族 + source/intent | 现有独立 audit Agent、review_edge；忠实报告局部缺失可 pass，但不自动获得定量资格 |
| 现有 figure bundle／normalization | exact 完整族、Intake 与独立审查 | 复用既有 guard、版本身份和资格机制；不得接收历史案例 producer 的旧 request/metric_report 作为新证据 |

新版 intent 的 bindings 仅允许 `candidate_id`、已有身份锚点 ID、可见标签文字、科学语义身份及有界拒绝理由；detector receipt 是工具返回的只读身份字段，不是模型自报统计。source、receipt、ID 的跨输入校验与 schema 同时进 compiled components。context_sources 明确列出实际绑定来源，不能把 prior_signal 当论文证据。

P0 冻结 detector/OCR 合同资源的合法可达边：request 输出的现有 context validator 组件通过 `ComponentSpec.resources` 引用该资源，materialize transform 组件引用同一资源。资源包含检测算法版本、固定策略、PDF/OCR/图像依赖版本与模型数据摘要。不得挂在 Agent worker_tool 的资源边而触发 `agent_resources_unsupported`；不修改 catalog 编译器或放宽资源限制。最小编译测试证明仅改变 detector 版本或 OCR 模型摘要时，request 与 materialize 的 compiled digest 都变化、无关 curve Operation digest 不变，且整个目录正常编译。运行时核对实际依赖版本与模型摘要吻合该资源，provenance 不能只抄声明。

新增候选记录 schema 和确定性测量记录版本属于插件私有数据合同。几何字段可以出现在代码产出的记录中供审查，不能出现在 Agent 可写 intent 中；已封存历史 request 保持可浏览，但新 materialize 不接收旧 geometry。完整族声明需同时更改输入／输出 port 集及 parentage，禁止混用两个运行的 panel、CSV 或 overlay。

未决路径仍返回 manifest/report 与可恢复的页面、候选叠图；`curve_tables` 可以为零，端口的 min_items 与完整族检查须一致：声明的空集合是完整未决结果，缺失声明不是完整。不要为凑现有 `min_items=1` 生成假 CSV 或虚假点。无法恢复来源时返回结构化未决原因；程序故障／损坏运行环境按既有失败生命周期结束，不能冒充科学未决。

P0 冻结以下三种领域结果形状。采用新版 intent v2、digitization request v3、manifest v2、validation report v2；候选集合使用插件私有 v1。ScientificIntake／EvidenceAudit 沿用现有 schema。request/manifest/report 各一个，是所有路径稳定的非空族锚点；输出 schema 与输入 ports、验证器、完整族及修订 guard 一起升级。

| 结果形状 | request / manifest / report 内容（各 1） | source_panels / audit_overlays / curve_tables 基数 | 下游终点 |
|---|---|---|---|
| 有可信测量 | request 带真实来源、轴解和绑定；manifest 带真实 panel/series；report 带各系列验证与实际附件清单。部分目标未决逐项保留 | 1 / 1 / 1–32；单次仍只处理一个选定 panel | Intake、独立 audit 与合格表的 normalization，保持局部限制；不自动宣称整个目标覆盖 |
| 有恢复图，但没有可信轴或身份 | request 为 unresolved，缺轴时不填 calibration；身份不清时不填已确认 series。manifest 允许 unresolved panel 缺轴、空 measured series；report 空 measured series，保留候选拒绝、轴／身份原因和真实附件清单 | 1 / 1 / 0；叠图展示真实候选／拒绝，不能画出虚假测量 | 零表 Intake 初稿、audit、一次完整对象修订均合法；normalization 在现有 figure 领域 guard 明确拒绝无可计量表 |
| 没有可恢复图 | request 为 unresolved，只有源 hash、检测 receipt 和有界原因；无 image hash、宽高、轴或虚假 panel。manifest 的 panels 为空；report 系列与图像附件清单为空，保留恢复失败／受限原因 | 0 / 0 / 0 | 同样允许忠实的零图零表 Intake、audit、一次修订；领域 normalization 拒绝，不制造空定量库 |

新来源模型用判别分支区分 embedded image、page render、raster、unrecovered：仅 embedded 分支要求 PDF 对象身份，render 分支保存页和渲染变换，unrecovered 不伪造正宽高或 image hash。`figure_evidence.py` 的 panel/series/validated artifacts 非空约束按上表分支收口，`figure_evidence_validation.py` 先分派结果形状再做数值检查。附件 ports 全局 min_items 可为 0，但领域校验按形状检查精确数量；不能因为允许空集而接受可信测量丢 overlay。

`figure_revision_parentage` 只强制稳定锚点和 revision cohort 非空，对附件使用 producer 实际集合与 manifest 声明核对，不能继续要求每个族端口都有实体。现有 complete_transform_family 和 Root 按基数／实际成员集合检查足够；不改中央生命周期或核心 schema。P3 必须走通两种零表形状的初稿→独立 audit→一次修订，并测试缺锚点、丢应有附件、混族仍拒绝；normalization 的零表拒绝沿用现有领域 admission/guard，不引入新 Run 状态。

### 3.3 文件归属与不可变实例内容

现有 `curve_figure_evidence/plugin.py` 主要引用 `curve_score` 中的 figure 实现。此次将 `figure_source.py`、`figure_worker_tool.py`、`figure_digitization_contract.py`、`figure_line_tracker.py`、`figure_digitization.py`、`figure_evidence.py`、`figure_evidence_validation.py`、`figure_evidence_normalizer.py`、`figure_science_operations.py` 迁到 `plugins/curve_figure_evidence/curve_figure_evidence/`，更正 imports、组件 target 和 schemas 所有权。`operation_transforms.py` 仅切出 figure transforms/guards，保留通用曲线 transforms；`science_operations.py` 中 figure resource 归回 figure 插件。迁移通用图实现不等于搬迁任何案例代码；禁止保留反向 import shim。

同时把 `curve_score/transform_adapter.py::bundle_figure_evidence_outputs` 切入 figure 包 `operation_transforms.py`，移除其 `.figure_evidence_normalizer` 导入及该函数 export；原 `operation_transforms.py` 不再从 curve 适配器导入此函数。curve 评分适配器保留单一通用实现，P1 在未安装 figure wheel 的隔离环境做导入及通用评分 smoke。

新增自动候选算法优先集中在该包 `figure_detection.py`；内部函数与文件分拆按实际可读性决定，由现有阶段 diff 审查覆盖，不设文件数事前审批。`curve_score` 不反向依赖 figure；figure 可以依赖通用曲线 schema/normalizer 工具，但不能导入 TCAD。

论文 PDF、引用、研究目标、材料身份、目标曲线及实验评分准则分别绑定为已有实例 Artifact。新证据通过通用算法生成并重新独立审查；导入历史目标表只允许历史比较用途，不能改标签让其成为新提取观察。不得把旧 `SCORER_CONTRACT.v2.json` 当可执行模板任意加载脚本。若通用评分无法表达某个科学比较，本次报告该缺口，不借自动提取计划重建案例 scorer。

## 4. 自动提取最小算法

1. **来源恢复。** PDF 顺序处理页面，提取嵌入图，同时渲染页面用于矢量图、分块图和整页图。记录 PDF hash、页索引、对象身份（适用时）、渲染器与版本、DPI、旋转／裁剪变换及 canonical image hash；不能把 pdfimages 的某个对象 ID 当固定答案。栅格直接规范化，保留原始到规范坐标变换。候选叠图同时显示所在原页，保证图号、caption 与图区能视觉核对。页面／像素预算是版本化代码常量，超限明确未决，不静默漏掉后页。
2. **plot 与文字检测。** 以长线、矩形关系、刻度排列、PDF 文本布局和局部 OCR 获得有限 plot 候选；固定排序、去重、数量上限。OCR token 保留原始文字、位置和来源；图号／caption／legend 与 plot 的空间关系只生成候选，不能预置材料名。图内注释也进文字候选，不能靠颜色把标签当曲线。
3. **轴解候选。** 从 tick 位置和 OCR 数值（含负号、小数、科学计数、指数）对每轴拟合线性 `v=a*p+b` 与对数 `log10(v)=a*p+b`。至少三项一致刻度或有独立冗余证据的解才能自动确认；两个 tick 的恰好拟合不足以解决歧义。排除非正 log 值、方向冲突、残差过大、单位冲突和多个同样可信的解。拟合阈值按渲染分辨率／字形尺度使用固定通用策略，记录算法版本，不允许 Agent 调参或指定哪一个数值轴解为真。
4. **反向坐标。** 像素 y 向下不等于科学 y 递增；保留拟合系数正负，x 轴也允许反向。映射先在规范图像坐标成立，再转科学值；最后按科学 x 排序且保持原像素索引。对数只在数值空间转换，禁止两次 log。单元测试必须覆盖 x 反向、y 上升／下降、PDF 页面旋转。
5. **分割与追踪。** 彩色线采用颜色聚类与局部几何连续性，保留抗锯齿宽度不确定性。黑线与黑坐标轴／文字采用轴线位置、tick 周期、OCR 字形 mask 和局部走向联合区分；删除轴 mask 时不能整条消除与轴邻近的真实曲线。文字 mask 交叉处标记局部缺失／多解，不能让追踪器沿字母或数字转弯。同色标签和曲线靠形态／连续性区分，身份由 Agent 看候选锚点绑定。使用有界图搜索或动态规划；每列保留有限路径，曲线颜色不是独占身份。
6. **交叉、共享与缺失。** 同一像素允许多个曲线引用，保存共享 group 与同一 pixel_id；统计物理支持去重，曲线引用计数可重复。两侧独立支持能确定连接且图形真正重合时，可复用既有 coincident 规则；仅有黑色交点或被覆盖段不能推断隐藏线，更不能由 Agent 填区间证明共享。分叉无法区分就保留多解或局部未决。局部缺失不导致整条可见曲线消失；不得跨空白插值造点，不平均出“中间曲线”。
7. **身份选择。** 叠图编号展示 plot、路径和可见 legend／annotation 候选。Agent 选择 candidate_id 并解释与原文的语义对应；不得根据预期结果、材料顺序或历史 CSV 猜身份。拒绝某一候选保留该候选与拒绝理由，不能隐藏困难曲线使目标看似覆盖。无可靠坐标解的候选只可视觉说明，不能成为可计量曲线。
8. **确定性物化。** 根据 intent 重放、核验 receipt，输出轴残差与不确定性、直接／共享／缺失支持、eligible 连续段、CSV、manifest、验证报告与审查叠图。point_count、coverage、最大 gap、统计区间均从真实输出计算；禁止来自 Agent 值。采样行须有来源像素／路径证据，排序不丢 identity；有限差异检测、范围检查和重新读取 CSV 验证由代码完成。

首版支持普通二维 Cartesian 线图、线性／log 轴、黑白和彩色线、局部缺失。极坐标、3D、热图、多重坐标轴、严重透视或无法可靠 OCR 的来源输出不可确定；无人工硬填 geometry、交互描点或“给几个 seed 即可通过”兜底。受限成功比隐蔽案例专用成功更有价值，但真实验收要求至少两个可靠解图成功，不能全部未决宣称交付。

## 5. 分阶段实施、提交与独立审查

每阶段先冻结范围和反例，再实施；一个阶段一个可审查提交边界，失败修复另作有界提交。以下审查均要求独立 GPT-6、新鲜上下文，提供精确 diff、合同及测试证据；审查者不修改被审查实现，不继承前轮聊天结论。此计划不声称已完成这些审查。

红测试策略：P0 先在工作树观察并记录预期失败，新行为测试随对应实现提交转绿；P0 独立提交只含计划、已可通过的现状／合同探针，不提交阻断基础回归的红套件，不以 skip/xfail 长期留绿。每阶段提交必须恢复其已有基础编译与通用测试，不等待后续阶段补救。

P0 进度（2026-09-06）：[合同冻结与编译证据](evidence/R5_E5_4_P0_CONTRACT_FREEZE.zh-CN.md)已记录三种结果形状、职责、删除引用基线与红测分配；源码及干净 wheel 的同一资源边／digest 探针串行通过（2 passed）。本次只验证现有编译能力，未运行未来 detector／schema 红测，未实现 detector 或删除案例插件；G0 审查尚未完成。

| 阶段／提交边界 | 具体文件与修改动作 | 完成定义／GPT-6 门 |
|---|---|---|
| P0 范围与合同冻结 | 本文第 3.2 节三种形状及资源边；`test_figure_semantic_compilation.py`、`test_catalog_installed_entrypoint.py` 中最小合法资源／digest 编译探针和未来失败用例；记录生产引用矩阵 | G0 确认未决合同、资源边与无新增控制机制；红测试按上述策略分配到实现提交 |
| P1 通用归属与生产案例删除 | 第 2 节全部生产删除和关联安装测试；第 3.3 节 figure 模块迁移；figure／curve pyproject、plugin.py、现有 imports；切出 figure transforms 及 `curve_score.transform_adapter::bundle_figure_evidence_outputs` 到 figure 包 `operation_transforms.py`，移除 normalizer 直接依赖／export | 构建目录与各组合可编译；未安装 figure wheel 的 curve 导入／评分 smoke 通过；旧案例入口不存在。G1 审查单一实现与依赖无环；不部署 |
| P2 检测与测量合同 | figure 包 `figure_detection.py`、`figure_source.py`、`figure_digitization_contract.py`、`figure_line_tracker.py`；新增 `tests/operations/test_figure_automatic_detection.py` | 从原始像素自动产生可重放候选、轴解、路径与未决；黑线／文字／共享／方向反例通过。G2 审查算法有效性和无案例数字，不能以 synthetic-only 完成最终验收 |
| P3 接入现有角色链 | figure 包 `figure_worker_tool.py`、`figure_science_operations.py`、`operation_transforms.py`、`figure_digitization.py`、`figure_evidence.py`（三形状 schema）、`figure_evidence_validation.py`、`figure_evidence_normalizer.py`；`test_curve_figure_digitization_tool.py`、`test_m5_figure_review_closure.py`、`test_figure_local_observations.py` | Agent 禁几何；materialize 重放；两种零表的初稿／audit／一次修订通过，normalization 领域拒绝；丢应有附件、混族、旧 digest 拒绝。G3 审查完整路径，不改中央生命周期 |
| P4 干净发行与部署预检 | `deploy/install.sh` 离线依赖预检、`scripts/build_git_release.py`、`tests/operations/conftest.py`、`test_catalog_installed_entrypoint.py`、`tests/artifact_agent/test_deploy_scripts.py`；双语安装说明中的前置依赖供应 | 串行完整目录／干净 wheel、服务 Python/PATH/模型验证及缺依赖负测通过；实际读取负探针支持不可读声明；G4 审查安装矩阵及 digest 合同后才允许切换 |
| P5 真实安装／真实 PDF／真实 spawn | 新增 `docs/plans/evidence/R5_E5_4_LIVE_ACCEPTANCE.zh-CN.md` 和独立 `docs/plans/reviews/R5_E5_4_LIVE_GPT6_REVIEW.zh-CN.md`（实施时创建） | 两张真实图、真实 Agent 完整族与独立 audit；记录 sealed 结果和未决区域，不手写结果。G5 审查干净运行无预填几何和答案泄漏；未 PASS 不宣称 E5.4 关闭 |
| P6 结案文档 | 受影响 README、INSTALL、deploy 双语；活动缺陷账本、计划索引和本文状态；不重写历史 evidence | G6 对精确最终差异及资格边界复审，明确能力、限制、版本和回滚。只有全部门通过才能关闭 |

如果 G2 证明算法不可行，应在既定边界内返工检测；不得恢复案例几何或让 Agent 填参数。每门最多两轮有界返工仍无进展则冻结失败证据、停止该阶段并记录未完成；不能增加角色／状态机或把目标缩成单张已知图来绕过失败。工程审查与研究 EvidenceAudit 是不同对象，二者互不替代。

## 6. 测试与反作弊验收

### 6.1 串行和内存

所有测试、wheel 构建、OCR、真实 Agent 依次执行，禁止 pytest-xdist、多 Agent 并发和并行矩阵。本次验收进程树总内存必须小于 8 GiB，建议 cgroup MemoryMax=7G、禁止 swap 掩盖；代码还需页级释放图像和 bounded candidates。若环境不能设 cgroup，记录进程树 RSS/PSS 与系统增量，不能用单个 pytest RSS 代替。沿用 E5.2 更严的 live Codex 进程树 4 GiB 与 WSL 增量 8 GiB 门；两个指标分别报告。无法测量则该门未完成。

可用 `MALLOC_ARENA_MAX=2`、`OMP_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1` 控制内存与线程；OCR 库同样显式单 worker。`ulimit -v 7340032` 是每进程虚拟内存防线，不代表总内存证明。记录峰值、输入页数和耗时，触及预算中止并返工，不能调高预算通过。

### 6.2 必须存在的检查

| 检查层 | 正测与不可省略的负测 |
|---|---|
| 单元算法 | 黑线靠近轴、文字穿线、彩色线同色标签、交叉共享像素、局部空白、线性／log、负号 OCR、两个等可信轴解、反向 x/y、旋转 PDF、只有矢量无 embedded image；同输入重复运行候选 ID／CSV 相同 |
| Agent 合同 | JSON schema 与 submit 同时拒绝 bbox、seed、ticks、coverage、max_gap、points 和自由参数 map；伪造 candidate_id、错误 source/receipt、不存在身份锚点、跨来源 ID 拒绝；缺轴不能靠额外字段转 ready |
| 完整族／资格 | 少一个 overlay、换一张 CSV、混合两个 materialize、历史 request／旧 review、空表未决、shared pixel 去重与直接支持回归；忠实 limited Intake audit pass 仍不代表定量充分 |
| 目录与编译 | `test_m5_plugin_ownership_and_default_surface.py`、`test_m2_optional_figure_plugin.py`、`test_r5_general_plugin_split.py`、相关编译测试；core+general、+curve、+figure、+TCAD、全三插件分别验证 exact entry points 与 imports |
| 全目录 | 聚焦通过后，串行完整 `tests/operations` 和 `tests/artifact_agent`；删除旧路径测试后必须补有意义的通用边界，不能 skip 掩盖失败；未动其他目录无需重复全仓 |
| 发行 | 既有 release builder、MANIFEST、干净 wheel 内容、installed catalog、安装器 dry-run；最后 `git diff --check` 与文档链接检查 |

### 6.3 干净 wheel 反作弊

从精确提交构建 release，再构建 core、curve_score、curve_figure_evidence、tcad_artifact wheels；新 venv、仓外空 cwd、清空 PYTHONPATH，不 editable 安装。核对模块 `__file__` 全在安装前缀，entry_points 只有声明组合。运行期间 checkout、案例 workspace、旧 geometry、历史 CSV、目标指标文件对该进程不可读；仅绑定原始 PDF／问题 Artifact。记录允许路径和文件访问审计，拒绝从系统用户技能目录加载人工几何脚本。

“不可读”必须由 P4 在实际服务／Worker 运行身份及其子进程环境执行文件打开负探针证明，覆盖 checkout、旧 workspace、用户技能与答案目录；通过现成运行身份／环境隔离实现，不新增 hardened backend 或权限协议。Local 后端、仓外 cwd、清空 PYTHONPATH 和访问日志均不单独构成隔离。若负探针未证明读失败，只能记录“未观察到读取”，不能声称“不可读取”或通过强反作弊门；停止该验收门，保留已完成的其他证据。

静态检查生产发行包不存在 `ingaas_fig4` 包、Fig.4 geometry、固定 source hash、标签映射、旧 scorer；动态检查单一 installed catalog、真实 Worker schema 和实际工具集合一致。改变 PDF 元数据／重新渲染或缩放同一图后应重新计算候选，来源身份正确变化且科学测量在估计误差内，不得依赖源 hash 查答案。CSV 的每行能追溯到实际图像支持。

### 6.4 第二张盲测图

在算法提交和通用阈值冻结后，由独立 GPT-6 审查者选择另一论文的真实二维图，材料、配色／轴比例／版式至少两项不同；交给运行端的只有 PDF 和科学选择问题。两张真实图各自在看运行输出前，由独立测试端封存目标系列、应覆盖的可见范围、检查点取样与比较方法、有限允许误差、允许不确定性宽度上限、每系列最低 eligible coverage 和最大可接受缺口、未决计分规则。数值按图分辨率及科学问题预注册，不能只引用被测算法自报误差范围；科学目标系列可在问题表达，离线几何／阈值／真值不可进入 detector、Agent、可读目录或生产配置。

每个预定目标系列均须达到封存覆盖门；未决、拒绝及遗漏部分计入未覆盖，不得从分母删除。真实预先确认的不可见区间可按封存规则排除，不能运行后改范围。数值误差同时满足独立有限误差门和可信不确定性包络，包络宽度不得超过预设上限。审查忠实 pass 不抵消覆盖或精度失败。加入两个验收器负例：扩大输出不确定性包络令其包住真值仍被上限拒绝；只保留容易局部、把其余目标标未决仍因覆盖不足失败。两图均满足独立门才能称真实自动提取成功。

第二图失败需报告算法缺陷或明确不支持的情形；不能阅读真值再为该图添加阈值／坐标例外。修改通用算法后必须重新冻结版本并换一张未看过的盲测图。另设不可识别轴的真实负测，确认得到不可确定而不是人工兜底。

## 7. M7 安装变量与部署门

源码核对的入口是 `deploy/reinstall.sh`／`deploy/install.sh`，插件选择变量为 `SCID_PLUGINS`，不是 `SCIDISCOVERY_PLUGINS`。沿用 M7 Local 安装态，显式 `SCID_PLATFORM=codex`、`SCID_WORKER_BACKEND=local`。自动图本身不要求切换 hardened 或启动 TCAD 执行。

| 变量 | E5.4 要求 |
|---|---|
| `SCID_PLUGINS` | `tcad_artifact,curve_score,curve_figure_evidence`；无 ingaas_fig4；单图可选组合另测但不得替代此既定完整安装态 |
| `SCID_WORKSPACE` | 已存在的独立绝对项目目录；不等于源仓库，不隐式退回 `workspace/default`；实例选择仍由管理 UI |
| `SCID_CODEX_LAUNCH_ROOT` | 独立绝对 Codex 启动目录，防止 checkout 成为模型／测试隐式答案来源 |
| `SCID_PYTHON`、`SCID_SERVICE_USER`、`SCID_SERVICE_GROUP` | 真实 Python 路径和既定服务身份；wrapper 由服务用户运行，按现有 sudo 机制执行 |
| `SCID_INSTALL_ROOT`、`SCID_STATE_ROOT`、`TCAD_STATE_ROOT`、`SCID_CONFIG_ROOT`、`SCID_BACKUP_ROOT` | 精确现有路径；注意 TCAD 状态变量没有 SCID 前缀。预检用隔离绝对目录，真实安装不拿临时目录冒充生产 |
| `SCID_TCAD_COMMAND_CONFIG` | 仅在既有 command adapter 被显式配置时保留其真实配置路径；安装 TCAD 插件不是运行 solver 的授权 |
| `SCID_APPROVAL_PORT`、`SCID_CODEX_SKILL_ROOT` | 沿用实际 UI 端口及技能安装目标；检查实际渲染配置，不依赖案例 wrapper 默认值 |

P4 先运行通用 wrapper `--dry-run`，检查系统依赖、渲染服务和路径；真实安装按既有事务执行。dry-run 的源码导入不证明 wheel entry point 正确。安装后必须从实际服务 Python 读取 distribution、compiled catalog、Operation digest、生成 Codex profile 与 Worker 工具；确认旧包和旧 profile 项消失、自动提取依赖版本一致。检查是否安装或暴露 `scientific-paper-evidence` 手工几何技能：本自动 Operation 不绑定该人工技能，避免模型遵循其要求索要坐标。

`deploy/install.sh` 当前通过 `--no-index --no-deps` 安装本地包，增加 pyproject 依赖不等于已供应依赖。P2 确定最小 PDF/OCR/图像工具及模型版本后，P4 在部署说明列出离线前置供应：由既有包管理／离线 wheel 库将 Python 依赖装入 `SCID_PYTHON` 可见环境，系统 PDF/OCR 可执行文件与校验过的模型数据预先供应；不新增下载服务、不在运行时联网拉模型。安装器在事务切换前，以真实服务身份及渲染服务 PATH 校验命令位置、实际版本、模型可读性／hash、Python import 与最小 OCR/渲染调用，安装后用服务 Python 重验。缺 OCR、缺模型、错误模型摘要、服务 PATH 找不到命令、仅操作者 Python 有依赖五类负测均须在切换前明确失败并保持原安装；继续沿用既有事务回滚。

依赖工具版本（PDF 恢复／渲染、OCR 与模型数据、图像库）进入 figure 插件确定性资源合同和结果 provenance；不能只改普通 callable 就声称 compiled digest 会变化。安装前识别仍在 queued/running 的旧合同 Run，禁止无依据承诺可以迁移／恢复；沿用现有生命周期限制，不为本计划修改中央恢复机制。

## 8. 真实 PDF + 真实 spawn Agent 端到端

验收必须由真实交互父调度器执行，先 `instance_current`，仅在用户明确继续的实例或管理 UI 新建／选定实例中导入不可变原始 PDF 与问题。不能恢复共享默认实例，也不能从聊天代写批准。

1. 冻结真实安装版本、两张真实 PDF、输入 Artifact、实际读取负探针及第 6.4 节各图独立验收门；确认无旧 geometry、预提取 CSV、scorer_project 或历史目标答案作为输入。科学图名可在问题中声明，数值几何不可以。
2. 从 startup compiled catalog 选择 request public Operation，绑定 exact inputs，preflight 成功后以相同请求 invoke。严格使用控制返回的 agent_type，真实 `spawn_agent`、`fork_turns="none"`，只要求完成队列 assignment，不传运行元数据或答案。
3. Worker 打开 assignment，调用通用 inspect，实际查看候选叠图，输出 candidate ID 与语义绑定，走文件 begin/chunk/commit 或 apply_patch 及 `worker_submit_result`。不接受固定 responder、模拟 completion 或预写 envelope。
4. 父调度器在 `run_status` 为 completed 后读取 sealed output 与 scheduler_signal；孩子聊天只作为返回通知。调用现有 materialize support，核对它在无先前 Worker 工具目录时可重放并生成完整族。
5. 以完整族分别真实 spawn 既有 figure Intake Agent 和独立 figure audit Agent；不传父历史，依同一文件生命周期提交。检查包含黑线、彩线、共享和局部缺失的真实观察及明确限制，不用 audit pass 替代数值支持判断。
6. 新证据若要进入通用 curve normalization／qualification，走现有 review edge、完整父链和现行资格合同。需要人类决定或外部执行时只给控制返回的 exact loopback URL，并只读 approval_status；本图提取验收不额外启动 TCAD 求解。
7. 复查实际读取负探针、访问日志、Worker assignment、schema、工具调用参数、sealed intent 与 materialize provenance；证据仅为日志时只报告“未观察读取”。确认无人工 geometry 输入，并按第 6.4 节独立精度／不确定性／覆盖门计分；在仓外独立路径重放。第二图同样跑完整真实链，不以单元图代替。

报告区分工程执行完成、候选身份可信、数值提取有效、科学审查忠实、下游资格获得；逐项附精确 Artifact/版本证据。失败／超时必须记录，重试创建新 Run，不续接隐藏模型会话。没有真实 spawn 或第二图时，结论只能是“集成未完成”，不能标 E5.4 PASS。

## 9. 回滚、非目标与复杂度预算

回滚复用 `deploy/install_transaction.py` 与既有安装备份，按精确旧安装物／配置恢复；不修改或删除 ResearchInstance 的新旧 Artifact。先停止新调度，保存失败证据，确认无活跃不可兼容 Run 后切换。旧安装恢复仅恢复服务可用性，不允许旧案例 Artifact 晋级为新自动证据；若旧服务没有这项边界，应暂停相关资格动作而不是重新开放案例路径。旧 Run 不承诺跨摘要恢复。

非目标：旧 ingaas Operation 名兼容、旧科学结果重写、万能 OCR、人工描点 UI、训练视觉模型、新 candidate lifecycle、中央 DSL／registry／状态机、新 Agent、新调度 stage、TCAD 物理模型修改、重造通用评分器、数据库迁移、批量归档历史文档。科学共享像素不等于统计独立，本轮不发明协方差模型。

复杂度硬预算：新增生产插件 0、生产 Agent 0、新增 Operation 0（总数净减 2，删除两个案例 support，复用 materialize）、中央 schema／状态／表 0、Root MCP 工具 0；现有 figure inspect 扩展但公共工具数量不增加。候选只有只读计算文件和重放 receipt；内部模块／函数分拆不设事前审批或数量硬门，由现有阶段 diff 审查控制规模。第三方依赖只限必要 PDF/OCR/图像能力，不新增服务。所有迁移文件保留单一实现，无反向兼容 shim。若必须突破控制面硬预算，先证明现有合同无法表达并比较更小方案，再修订计划复审，不默默扩大范围。

最终成功条件是生产案例插件及其隐式答案完全消失，通用安装从两张真实 PDF 经真实 Agent 语义选择与确定性重放得到可审查、可追溯的图证据；不可靠轴明确不可确定。历史 Artifact 可读，资格必须依当前输入、版本、独立审查和既有规则重新建立。
