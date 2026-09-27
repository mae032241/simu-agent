# R5 E5.4 P2：自动候选检测底层证据

日期：2026-09-06。仓库 `123/scidiscovery-e5.2`，基线 `66bd74b`，工作树尚未提交。依据 [E5.4 计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)、[P0](R5_E5_4_P0_CONTRACT_FREEZE.zh-CN.md)、[G0](../reviews/R5_E5_4_P0_G0_GPT6_REVIEW.zh-CN.md)、[P1](R5_E5_4_P1_PLUGIN_OWNERSHIP_AND_CASE_REMOVAL.zh-CN.md) 与 [G1](../reviews/R5_E5_4_P1_G1_GPT6_REVIEW.zh-CN.md)。本阶段实现待独立 G2 审查；不授予 E5.4、科学资格或 P3–P6 通过。

状态补充：首轮 [G2 独立审查 FAIL](../reviews/R5_E5_4_P2_G2_GPT6_REVIEW.zh-CN.md)，发现 G2-1 至 G2-4 四项缺陷。下文原记录保留首轮 v1 实现和结果，不能当作当前 v2 修复已通过的证据；本页末尾单独记录有界返工与复验。G2 尚未取得 PASS。

## 修改与接口边界

生产修改仅有 `figure_source.py` 新增自动来源恢复，以及新建 `figure_detection.py`。旧来源接口保留当前 P1 行为；新入口 `detect_source(content: bytes)` 和 `recover_automatic_source(content: bytes)` 只有原始源 bytes 一个参数，自己识别 PDF／栅格。没有 page、object、figure、材料名、bbox、axis endpoints、ticks、seed、阈值、点数、coverage、max_gap 或自由参数 map。纯函数 `detect_raster(content, tokens)` 与 `fit_axis(tokens, axis)` 是内部结构化 OCR adapter 的算法测试边界，没有作为 Worker 工具或 Operation 输入暴露。

P2 只产生有限候选和可用的 OCR token 锚点，不判断哪一个候选对应 Fig.4，也不按 figure 号、page 或材料名自动选择。根据原文／图号／caption 将候选与科学目标匹配、选择 candidate_id 和绑定身份，是 P3 请求 Agent 的职责；当前没有接入该职责。

新增冻结 dataclass 领域对象包括来源图像／恢复结果、OCR token、轴解候选、plot 候选、真实像素支持、path 候选及检测 receipt。候选由源内容摘要、检测合同版本和规范化候选内容计算 ID，输出排序固定；文档入口重新绑定 document hash、页和恢复图像身份，不能跨源复用图片候选 ID。结果包含原页／原图叠图 PNG bytes、工具版本、来源坐标变换、候选拒绝／未决与固定策略。没有新增数据库实体、registry、生命周期、Operation、Agent 或中央字段。

`figure_digitization_contract.py`、`figure_line_tracker.py`、plugin.py、Worker 工具、science_operations、transforms、figure_evidence*、src、其他插件及部署均未修改。P2 不生成 CSV，不产生受资格认可的测量，现有角色链仍未调用新入口；P3 才负责新 intent、资源编译、确定性 materialize 与完整族接入。

## 固定算法与限制

来源合同 `automatic-source-v1` 从 PDF 第 1 页顺序扫描，最多 8 页、源 bytes 64,000,000、累计规范图像 24,000,000 pixels、单个原图 25,000,000 pixels、每页 32 个 embedded images；规范图像最长边 1600。页面以系统 pdftoppm 进行完整页面渲染，同时恢复普通 embedded image。保存规范图像 hash、页、适用的对象身份、实际工具版本、请求 DPI 120，以及原始坐标到规范像素的仿射变换；scale-to 导致的实际比例来自输出尺寸，不把请求 DPI 冒充实际比例。页面坐标空间明确为未旋转 MediaBox 左上角相对 points，embedded/raster 使用各自原始 pixels。页面／像素／图像预算或不支持的图像形式明确未决。缺渲染器、命令失败、超时等执行故障抛出 RuntimeError，不能变成“没有图”。

检测合同 `cartesian-candidates-v1` 使用 Pillow 与 stdlib。暗色长线、矩形边及垂直刻度邻接产生有限 plot 候选。数值 OCR 处理负号、科学计数和上标指数；轴候选要求至少三个一致数值 token，在图像检测入口还要求对应位置具有与轴垂直的真实 tick ink。同时拟合 linear/log10，保留 x/y 正反向与像素 y 向下；非正数不进入 log，单位冲突、方向／残差不一致和多解保留未决。纯函数不能把两点恰好拟合标为 resolved。

路径从 plot 内实际像素建立有限黑色／彩色支持列，去除轴边界和 OCR 字形 mask，按局部连续性延伸，允许多个轨迹引用同一 pixel_id。共享处保留 shared_group 与 junction ambiguity，不据此推断身份或独立统计样本。超过局部步幅、文字遮罩或真实空白时结束片段；不跨空白插值，不平均多条路径，不制造中间线。有限路径预算、局部片段、未绑定身份、未决轴和缺文字遮罩明确保留。候选不是已确认曲线；短图例线／字形依靠 mask、宽度和横向支持长度筛选，复杂文字与严重重叠仍可能出现候选假阳性。

OCR 只用受限系统 tesseract CLI adapter：固定 `--psm 11 tsv`，读取结构化 token，没有运行时下载、pytesseract 服务或新 OCR 平台。当前机器 **没有 tesseract**，生产分支返回 `ocr_dependency_unavailable:tesseract`；所有真实路径还带 `text_mask_unavailable`。adapter 的 CLI 输出解析只有 mock 测试，不能称系统 OCR 已验收。没有安装 tesseract、增加 numpy/scipy/cv2，或修改 pyproject；Pillow 已由核心声明为 `>=10,<13`。当前使用 Pillow 12.1.1、Poppler pdfimages/pdftoppm 22.02.0。P4 仍须供应并验证真实 OCR 可执行文件、模型及服务身份环境；P3/P4 的 compiled resource 和模型摘要校验尚未接入。

## 红测与合成验证

新增 `tests/operations/test_figure_automatic_detection.py` 后、生产实现前，运行 `python -m pytest -q tests/operations/test_figure_automatic_detection.py`，观察到 **1 collection error in 0.30s**：`ModuleNotFoundError: curve_figure_evidence.figure_detection`。第一轮实现后为 10 passed、5 failed（刻度伸出端点导致 plot 未识别）；修正通用端点邻接后为 14 passed、1 failed。最后一项合成交叉原图的两个整数阶梯线并没有真实共享像素，修正合成绘图使两线真实交叉后，首批 15 项转绿。没有 skip/xfail，也没有读真实几何修正该测试。

后续补入纯算法与边界测试：三刻度与两刻度反例、linear/log10、负号／指数、双等可信轴解、单位冲突、x/y 反向、真实 tick ink 与错位 token 拒绝、黑线靠轴、同色文字穿线、局部空白、交叉共享、原像素非白支持、候选 ID／overlay 重复一致、改变源元数据仍改变候选身份、空白与无效栅格、固定 byte budget、四种 PDF 页面旋转变换、无 embedded image 的 vector render 路径、受限 OCR TSV 解析、OCR 缺失与执行故障区别，以及入口签名和隐藏几何参数拒绝静态／动态断言。

聚焦命令：

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS='' python -m pytest -q tests/operations/test_figure_automatic_detection.py tests/operations/test_curve_figure_digitization_tool.py tests/operations/test_figure_local_observations.py tests/operations/test_figure_semantic_compilation.py tests/operations/test_m5_figure_review_closure.py
```

结果：**72 passed in 7.96s**（当时新增文件含 23 项）；其后补一项黑色文字穿越黑线的显式反例，最终结果见下节。该次聚焦运行未收集进程树峰值，不能以单 pytest RSS 代替；下述真实探针与完整目录运行有外层进程树监测。

## 原始 PDF 可行性探针

只读使用授权的原始 `paper_source.pdf`，其 SHA-256 为 `750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`。文件路径、hash、页／对象和材料标签没有写入生产或测试。没有读取删除前的 geometry、历史 CSV、历史 overlay 或答案；本记录不声称操作系统使它们不可读，P4 的实际文件打开负探针尚未执行。

探针直接调用 `detect_source(raw_pdf_bytes)`，没有传入页面、figure 身份或算法参数。首次进程因只配置 figure 源码 PYTHONPATH 而在导入处得到 `ModuleNotFoundError: scidiscovery`，这是启动环境错误；补全本仓库 src/curve/figure 导入路径后运行。第一次算法探针 32.64s、采样进程树峰值 108,448 KiB；检测到真实路径后未按论文页或几何调节算法常量。后续只补明确预算／共享／文字 mask 未决和真实 tick ink 校验。

最终探针从第一页顺序处理固定 8 页，恢复 **30 个图像，21,677,754 个规范 pixels**；共 **23 个 plot 候选、111 个路径／局部片段候选、0 个 resolved axis**。路径数包含分段、多解及页面／embedded 两种恢复表示，不能当作 111 条科学曲线。

| 自动结果所在页（检测输出，非输入） | 恢复表示 | plot 候选 | 路径／片段候选 | 像素引用数 |
|---|---|---:|---:|---:|
| 6 | page_render | 2 | 5 | 414 |
| 6 | embedded_image | 2 | 21 | 3,100 |
| 7 | page_render | 2 | 6 | 764 |
| 7 | embedded_image | 2 | 41 | 7,523 |
| 8 | embedded_image | 3 | 38 | 4,821 |

其余恢复表示保留 plot/path 未找到或候选预算未决。源级原因是 `source_page_budget`、`embedded_image_unsupported_or_budget` 与 `ocr_dependency_unavailable:tesseract`；相应图像还包含 `plot_candidate_budget` / `path_candidate_budget`。所有轴缺可靠 OCR，所有路径身份未绑定，不输出科学值。实际查看了代码自动选择的第一个具有路径的完整页面叠图，可见 plot 框及黑／红真实曲线上的局部像素支持；不是只靠候选计数宣称路径存在。该临时生成叠图未进入生产或测试 fixture。

最终 receipt：`7c216afa02d791d449a1ab4e3c971c02580863c33179f71d02dabb4a3f809e18`。最终探针 **31.91s，退出码 0，进程树采样峰值 108,504 KiB（约 106 MiB）**。外层监测每 0.1 秒用 `ps` 递归汇总子进程 RSS，达到 8 GiB 则终止进程组，未触阈值；固定 OMP/OPENBLAS 单线程。该数字不是 cgroup 强制总量，不覆盖 live Codex/WSL 增量门。探针不是强反作弊隔离、真实 OCR、第二图盲测、真实 Agent 或定量覆盖／精度验收。

## 完整回归与交付限制

完整目录命令为 `python -m pytest -q --tb=line tests/operations tests/artifact_agent`，环境同上，未用 xdist。结果 **474 passed、9 failed，零 skip/xfail，133.87s**；监测总耗时 134.35s，进程树采样峰值 **235,084 KiB（约 230 MiB）**，未触及 8 GiB 保护。所有生产修改均已在本次完整目录运行开始前完成；运行期间只新增最后一项黑色文字穿黑线的测试，该项随后单独随新增测试文件复跑。

九项失败与 G1 记录的 node ID 和原因一致：installed hardened Run 一项、L4 hardened admission 一项、L5 hardened backend 六项，均为既有 `operation_runtime_unavailable` 或对应旧拒绝码断言；`test_spec.py::test_operation_spec_is_the_frozen_declarative_contract` 一项仍因旧字段列表遗漏 `complete_transform_family`。上述中央文件与测试没有修改。本次未重新创建基线快照，只与 G1 已独立复现的清单核对；不能称完整目录全绿，没有改 admission、spec 或增加 skip 消除这些失败。

最终新增测试文件串行复跑 **24 passed in 1.46s**；监测总耗时 1.82s，进程树采样峰值 **67,712 KiB**。`git diff --check` 通过。变更路径为两个生产模块、一个新增测试文件、计划状态和本证据，共五个路径；未 commit、未部署。

新检测器仍只属于 figure 底层，没有接入 Worker inspect、新 intent、物化器、完整族、compiled resource、审批、资格或部署。旧测量合同不能被本记录当作自动输出接管。真实候选最低可行性得到证据，真实轴／身份／覆盖／精度尚未得到证据；P2 仍需 G2 独立审查，P3–P6 保持未实施。

## G2 第一次有界返工（待独立复审）

完整阅读 G2 FAIL 后，只在原两个 P2 生产模块、同一自动检测测试、本 evidence 和计划状态内修复 G2-1..4；没有触及 P3、Worker、Operation、plugin.py、中央代码或部署。没有新增依赖、服务或控制抽象。图号／材料／科学目标匹配仍属于 P3 请求 Agent，P2 不按页或 figure 号选择科学对象。

先增加审查反例，串行运行 `python -m pytest -q tests/operations/test_figure_automatic_detection.py -k g2`，观察到 **6 failed、24 deselected，1.70s**。失败为实际 tick 上数值偏移、分开的 V/A/V 单位被忽略、线宽 3/5/8 的空框产生路径，以及真实 Poppler 的 CropBox/MediaBox 变换错误。随后修复，不删除失败断言、不增加 skip/xfail。

- **G2-1：** 不再从 `Page size` 计算变换，读取并记录显式 MediaBox、CropBox 和 rotation，按照未传 `-cropbox` 的实际 pdftoppm MediaBox 渲染计算宽高和转向。坐标仍定义为该显式 MediaBox 未旋转左上角的相对 points，记录 box 原点以闭合回 PDF 坐标；没有新增裁剪功能。真实 Poppler 反例覆盖 0/90/180/270 度、CropBox 不同及部分非零 MediaBox 原点，已知黑色标记位置与变换结果闭合。既有旋转 mock 只补入现在实际读取的两个显式 box 字段。
- **G2-2：** 轴候选内部保存 `tick_bindings`，将数值 OCR token 的原字框与所有真实匹配 tick ink 位置关联；拟合、残差和输出 ticks 都使用实际位置。字框统一右偏 2 px 时仍在实际 70/170/270 ticks 上得到 0/5/10。可匹配多个位置时枚举固定预算内的组合，保留 `axis_tick_association_ambiguous`／有限多解；没有增加调用者几何参数。
- **G2-3：** 在轴的 tick 过滤前，根据数字右侧邻近 token 的间距与基线重叠关联单位。正常分词的 `0,V,5,A,10,V` 保留 `axis_unit_conflict`；一致的独立 V tokens 能保留单位；多个邻近词、弱基线重叠或共享所属关系保持 `axis_unit_association_ambiguous`。这仍是结构化 TSV token 的局部规则测试，不声称缺席的 tesseract 已实机通过。
- **G2-4：** 从检测边缘沿各局部垂直／水平截线上的实际连通暗墨迹估计厚度，逐像素排除轴 ink，到白色分隔立即停止；同一粗框的近邻边缘检测规范到其连通墨迹外缘再去重。3/5/8 px 空粗框均只有一个 plot、零路径；仅隔一个白色像素的独立黑线仍保留。未通过统一扩大裁减带掩盖问题。

来源合同提升为 `automatic-source-v2`，检测合同提升为 `cartesian-candidates-v2`，新策略与显式 box／tick 关联进入候选和 receipt；旧 receipt 不继续代表修复后结果。算法数值预算保持通用固定代码策略，没有依据原始论文页、对象、标签或答案调参。

最终五文件聚焦命令与上文相同，包含原 73 项和本轮新增 11 项，结果 **84 passed in 10.99s**。监测总耗时 **11.46s**，进程树采样峰值 **155,996 KiB**。环境为 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`，串行无 xdist，每 0.1 秒汇总子进程 RSS，8 GiB 中止保护未触发。先前单独新增测试文件复跑为 **35 passed in 5.50s**。

按补充要求，在相同 G2-3 范围增加三项完整集成反例：真实 tick ink 对应 `1e15`、`1×10^16`、`10¹⁷`，每个数值旁为独立 `cm⁻³` token，得到唯一 log10 轴、实际 tick 坐标与一致单位；混合 `cm⁻²` 或损坏 `10^x` 分别保留单位冲突／刻度不足未决，无可确认的线性替代解。原四项 parse_number 测试保留。此补测没有再改生产代码。

最终五文件聚焦 **87 passed in 11.00s**；总耗时 **11.45s**，进程树采样峰值 **113,048 KiB**。该运行接在上一组完成之后，随后才重放原始 PDF，未并行运行测试／真实图。

v2 只读使用同一授权 raw PDF，仍自动从第一页扫描固定 8 页，恢复 **30 个图像／21,677,754 pixels**，得到 **18 个 plot、115 个路径／局部片段候选、0 个 resolved axis**。逐一检验全部 **17,169/17,169** 个像素引用均在对应规范图像内且非白。源级未决仍为 `embedded_image_unsupported_or_budget`、`ocr_dependency_unavailable:tesseract`、`source_page_budget`。第一次 v2 探针退出码 0，**33.99s，进程树采样峰值 116,024 KiB**。

由于源码合同版本、box provenance、tick 关联和轴墨迹排除均已改变，receipt 合理变为 `2c9d8c9492696f56779dac2389e61a4b07c7a374c225695cd2e3a2d25fc910fa`，不同于首轮 v1；第二次从 raw bytes 完整重放取得完全相同 receipt 与 17,169 个像素引用，**32.21s，采样峰值 115,852 KiB**。第二次保留全部有路径输出的临时叠图供检查，未按 figure／页／材料筛选算法输入。

不能把 v2 候选数或“非白”判定当作真实科学曲线计数：首个有路径叠图出现了照片区域的五条假阳性候选。该限制明确保留，没有按真实图增加排除条件或调参。按输出顺序继续实际查看下一张有路径叠图，可见两个 Cartesian plot 及黑／红曲线上的五个真实局部路径支持，因此原始源上至少一个 plot 和无 seed 真实曲线路径仍有视觉证据。这里没有判断它对应哪个 figure、材料或目标 series；身份选择与假阳性拒绝仍属于后续请求 Agent，不代表自动定量或目标覆盖通过。

`git diff --check` 通过；未 commit、未部署。首轮完整目录的九项失败记录保留，本轮未重跑完整目录；有界修复用上述 owning figure 回归与原始源探针验证，不将工程复审替代科学资格。所有监测均为进程树采样 RSS，不是 cgroup 强制总量或整个 live Codex/WSL 增量证明。
