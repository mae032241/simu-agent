# R5 E5.4 P2：独立 GPT-6 G2 审查

最新结论：**P2/G2 复审 PASS**，见文末“有界返工复审”。以下首轮 FAIL 内容原样保留，绑定首轮实现，不作为当前修订版结论。

结论：**FAIL**。日期：2026-09-06。真实源已经能产生有限、可重放且引用真实像素的局部路径，但下述四个直接可达缺陷使 P2 的坐标、轴闭合和轴线排除尚不成立。修复范围仅为现有两个 P2 生产模块及相应算法反例，不要求接入 P3、不扩展图型或 OCR 平台。

## 审查对象

仓库 `123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`，基线及 HEAD 为 `66bd74b908790e8dfd1765b6f673265515a72e59`。被审工作树共五个路径：修改的 `figure_source.py`、计划状态，新增的 `figure_detection.py`、自动检测测试和 P2 evidence。完整阅读仓库 AGENTS.md、E5.4 计划、P0/P1/P2 evidence、G0/G1 review，应用跨边界审查、变更范围检查和最小修改技能。没有读取 Git 历史内容、旧 geometry、CSV、overlay 或答案，也没有调用科研控制面、Worker 或调度另一 Agent。

| 被审文件 | SHA-256 |
|---|---|
| `figure_detection.py` | `553ea9a03b1f7fa2507252dbe896fd796a0efbbf08929b40b1dcab16358f0886` |
| `figure_source.py` | `e69e36187a2cac7ff4fe90708789e2a389795422859964ab0c38e4dc3626c6a7` |
| `test_figure_automatic_detection.py` | `389cb3664360a43c2d500052782b434e8d3aeebea642ccb8c08847a26070f17b` |
| P2 evidence | `443b8ce3deef443f82a4c675ab3d6e356178ab1714e5ff62fd652e7e7f6ad69a` |

## 阻断发现与最小修复

### G2-1：真实 PDF 的 CropBox 与 MediaBox 不同时，记录的变换错误

位置：`plugins/curve_figure_evidence/curve_figure_evidence/figure_source.py:123`，以及第 136–143 行。

代码从 `pdfinfo` 的 `Page size` 取宽高，却用未传 `-cropbox` 的 `pdftoppm` 渲染，再宣称坐标属于未旋转 MediaBox。实际 Poppler 的页面尺寸字段可以是 CropBox 尺寸，输出图像却仍覆盖 MediaBox，因而两个坐标空间被混用。

独立反例使用本次现场构造的最小合法矢量 PDF：MediaBox `[0 0 200 100]`、CropBox `[50 25 150 75]`、无旋转、无 embedded image，内容仅在页面中心绘制黑色 `99 49 2 2 re f` 方块。真实 `pdfinfo`、`pdftoppm`、`pdfimages` 执行后恢复为 1600×800 图像；黑色支持中心为 `(799.5,399.5)`，记录变换却是 `(16,0,0,0,16,0)`，把 MediaBox 左上角坐标 `(100,50)` 映射成 `(1600,800)`，偏到图像外沿。此反例没有 mock PDF 工具。现有四种旋转测试全部 mock `Page size` 与渲染尺寸，未覆盖这个实际接口差异。

最小修复：从同一实际渲染框的显式 box 数据计算宽高、原点与旋转；保留当前 MediaBox 渲染即可，不必引入新裁剪能力。补一个真实 Poppler、不同 CropBox/MediaBox 的通用反例，验证已知可见标记与记录变换闭合。

### G2-2：轴拟合使用 OCR 字框中心，丢掉已经找到的真实 tick 坐标

位置：`figure_detection.py:293` 的 `_tick_aligned` 与第 162 行的 `fit_axis`。

`_tick_aligned` 在标签中心左右两像素内寻找 tick ink，但只返回原 token，没有保存匹配的 tick 位置；`fit_axis` 随后直接把 OCR bbox 中心当成 tick 坐标。共同的字框偏移不会进入拟合残差，仍可得到 resolved。

独立反例：320×240 白底，轴框 `(50,25,290,190)`；实际 x tick 位于 70、170、270，对应 0、5、10。仅让 OCR 字框中心各偏右 2 px，其他图像和数值不变。结果为 resolved linear，ticks 被记录为 72、172、272，残差约 `1.78e-16`；在真实 tick 70、170、270 上却输出 `-0.1,4.9,9.9`。真实刻度误差为全范围的 1%，大于算法自身 0.5% 残差门，却因只在错误中心自检而通过。此问题不依赖放宽用户阈值或只有两个点。

最小修复：在内部候选中保留实际 tick ink 位置与 OCR token 关联，用 tick 坐标拟合和回验；多处可匹配时保留有限多解／未决。增加 OCR 字框整体偏移的反例。无需开放任何新的几何输入，也无需扩大模型接口。

### G2-3：正常分词形状下，冲突单位被丢弃并确认轴解

位置：`figure_detection.py:154` 的单位解析、第 329 行附近的 tick 筛选调用，以及第 393–396 行 OCR TSV 行到 token 的适配。

单位冲突只在单个 token 恰好包含空格形式 `"0 V"` 时生效。CLI adapter 为每个 TSV 行建立一个 token，没有将数值和相邻单位绑定；单独的单位 token 不是数值，且可能在 tick 筛选时先被丢弃。现有冲突单测注入了合并好的 `"0 V" / "5 A" / "10 V"`，不能证明 adapter 实际支持的分词形状。

独立反例沿用上述三个真实 tick，输入六个结构化 token：每个数值 bbox 为 `(x-4,200,x+4,210)`，相邻单位 bbox 为 `(x+5,200,x+13,210)`；文本依次为 `0,V,5,A,10,V`。`detect_raster` 得到 `resolved=True`、`unit=''`、残差 0，冲突未保留。这里验证的是实际 adapter 可产出的分行 token 形状，未声称本机运行过真实 tesseract OCR。

最小修复：在现有受限 adapter／轴候选内部根据局部文字布局关联数值与单位，显式冲突或关联不可靠时保持未决；不能把看得见的冲突单位静默当成无单位。补分开的数值／单位 token 回归，不新增 OCR 服务或平台。

### G2-4：仅有粗坐标框的空图会产生完整假路径

位置：`figure_detection.py:247` 的 `_paths`，尤其固定 `left+2` / `top+2` 边界裁减；相关重复框来自 `_long_lines` / `_plots`。

轴 mask 只是固定排除两像素，并不测量实际轴墨迹厚度。独立通过原始 bytes 入口 `detect_source` 输入 320×240 白底图，只画黑色矩形 `(50,25,290,190)`，没有数据线、文字或图例：线宽 1 时没有路径；线宽 3 时产生一条 235 点路径，所有点在 `y=27`，正是上边框内层；线宽 5 时得到 4 个 plot 和 6 条路径，线宽 8 时得到 9 个 plot 和 15 条路径。全部像素非白，但全部属于轴框。仅以非白像素和横向长度断言不能排除此缺陷。

缺 OCR 的未决标记诚实存在，但不能代替已经由几何确定的轴墨迹排除。这个无文字的普通输入已足以让假候选消耗路径预算，并给后续选择提供伪线段；不需要据论文图号或材料身份判断它。

最小修复：从已检测轴线的连通墨迹估计局部厚度并 mask，对同一粗框的近邻重复候选去重；保留与轴邻近但不属于轴墨迹的独立黑线。补空粗框无路径和邻轴真实黑线仍保留的成对反例，不通过整体加宽删除带解决。

## 原始 PDF 独立实测

只从授权的精确 `paper_source.pdf` 读取 raw bytes，直接调用 `detect_source(raw)`，没有传 page、figure、bbox、ticks、seed 或算法参数，也没有打开其相邻文件。原始 SHA-256 为 `750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3`。

独立得到 30 个恢复图像、21,677,754 个规范像素、23 个 plot、111 个路径／片段、0 个 resolved axis；receipt 为 `7c216afa02d791d449a1ab4e3c971c02580863c33179f71d02dabb4a3f809e18`，与 P2 evidence 相同。源级未决为 `embedded_image_unsupported_or_budget`、`ocr_dependency_unavailable:tesseract`、`source_page_budget`。

程序自动选取输出顺序中第一个有路径的 detection，索引为 23，把其 overlay 与对应恢复原图暂存 `/tmp/e54-g2-review-bdjlaoee/`。审查者实际用 `view_image` 查看 `first-overlay.png`：品红支持确实沿页面左上图区的黑线和红线局部线段分布，不是仅覆盖轴或文字；只覆盖部分可见段，标签部分重叠。这里不判断该候选对应什么 figure、材料或科学 series。

对每个 PathCandidate，不仅抽样，还逐一检查了全部 **16,622 个像素引用**：每一坐标均在其对应 `AutomaticImage.content` 解码图像内，且 **16,622/16,622 非白**。因此“真实像素支持”有独立证据；它不能单独证明曲线身份、排除轴框、定量准确性或目标覆盖。

111 是多页、多表示、多个 plot 的合计，不能与每个 plot 的 32 路径上限混同；当前固定预算有限。真实结果明确标出部分 `path_candidate_budget`，源码也在 plot/path 截断处保留预算未决。首张 overlay 已证明存在可供后续语义选择检查的真实片段，不能仅因 111 这个总数认定整套输出都是噪声或完全不可用；G2-4 则证明常见轴噪声排除仍有具体缺陷。没有按目标 figure 的检出与否给本次算法定性，也没有把候选数量充当科学曲线数量。

## 其余边界核对

- 新入口 `detect_source(content)`、`recover_automatic_source(content)` 均只有 raw bytes；媒体由实现识别。内部 `detect_raster(content,tokens)` / `fit_axis(tokens,axis)` 未变成 Worker 工具或 Operation 输入。几何、页范围、阈值、点数、coverage、max_gap 与任意参数 map 的外部拒绝测试通过。
- 候选与 receipt 使用规范序列化、源摘要和 detector 版本；文档层另绑定源、图像、页、表示种类和适用对象。合成重放、元数据改变导致跨源 ID 改变的测试通过，原始 PDF receipt 独立一致。没有随机 ID 或从固定 source hash 查答案的代码。
- 页面从 1 顺序处理，8 页、图像／总像素／源 bytes 预算是固定策略；包含 page render 与普通 embedded recovery。四向旋转、反向 x/y、至少三个 ticks、linear/log、多解和两 tick 拒绝的现有合成测试通过；不抵消 G2-1 至 G2-3。
- 路径点来自实际像素，没有跨空白插值；同色交叉可以共享 pixel_id/group；文字 mask 和局部缺失的合成测试通过。当前机器缺 tesseract，全部真实轴／文字 mask 明确未决；没有把 mock TSV 解析当作实机 OCR。CLI 固定 `--psm 11 tsv`，执行异常按代码抛系统失败，未引入下载、服务、pytesseract 或新图像平台。
- 生产变更只有 figure 两个底层模块；没有硬编码论文图号、页选择、材料、固定 hash/object 或旧 geometry。没有改 Worker、Operation、Agent、plugin 注册、中央字段或生命周期；科学身份选择仍留在既定后续职责。当前不是定量物化、资格或部署验收。

## 独立检查与限制

所有执行串行，未使用 xdist，固定 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2`；pytest 另设 `PYTEST_ADDOPTS=''`。下表三次正式运行均以外层监测器每 0.1 秒递归汇总 `ps` 中被测进程及子进程 RSS，达到 8 GiB 则终止进程组，均未触阈值。额外首次反例探索只记录进程自身／串行子进程 rusage，未冒充进程树采样；随后将四项反例正式串行重跑并监测。

| 检查 | 结果 | 总耗时／采样进程树峰值 |
|---|---|---|
| 下列五文件聚焦 pytest | **73 passed in 7.93s**，退出码 0 | 8.53s／151,792 KiB |
| 指定原始 PDF → `detect_source`，全像素检查 | 上述真实候选与 receipt，退出码 0 | 31.88s／108,500 KiB |
| 四项独立反例 | **4 failed of 4**，退出码 1；期望分别为空粗框无路径、冲突单位不 resolved、真实 tick 值闭合、MediaBox 变换闭合 | 1.64s／63,620 KiB |

```sh
python -m pytest -q tests/operations/test_figure_automatic_detection.py tests/operations/test_curve_figure_digitization_tool.py tests/operations/test_figure_local_observations.py tests/operations/test_figure_semantic_compilation.py tests/operations/test_m5_figure_review_closure.py
```

已有测试并未伪造原始 PDF 成功；但粗框、分开的单位 token、OCR 中心偏移、真实 CropBox/MediaBox 接口四个遗漏使绿测覆盖不足。报告中的新反例在内存与临时 subprocess 内运行，没有修改测试文件或被审实现。进程树数据是采样 RSS，不是 cgroup 强制上限，不包含整个 live Codex/WSL 增量。

`git diff --check` 通过。未重复全目录、安装矩阵、真实 OCR、Worker、solver 或部署：本次最小回归已足以界定 P2 差异，独立反例已经阻断本门。P2 evidence 中全目录的九项既有失败只作已读记录，不声称本审查重新证明了其基线来源。

本轮只新增本审查文件；未改源码、测试、计划、evidence，未 commit、未 deploy。四项修复均能留在 P2 范围内完成。

## 有界返工复审

结论：**PASS**。日期：2026-09-06。本结论仅覆盖首轮 G2-1..4、有界补充的科学计数／独立单位 token 链，以及修订后原始源候选的最低可用性。四项原阻断已关闭；本次限定范围未发现新的阻断。没有授予真实 OCR、科学身份、定量准确性、目标覆盖、P3–P6 或部署通过。

### 修订对象与独立验证

完整阅读更新后的 P2 evidence 和当前五路径实现差异；HEAD／比较基线仍为 `66bd74b908790e8dfd1765b6f673265515a72e59`。被审文件本轮摘要如下；原首轮摘要保留在上文。

| 文件 | SHA-256 |
|---|---|
| `figure_detection.py` | `5a289c40e1d043d4ed7da5311b86e1a2b5732b5d7f7790ca060c6f6607e66547` |
| `figure_source.py` | `53eaff67821576de6f851bc5a839f73d5cf884b4ec9fb97fa572e8dc205bfe25` |
| `test_figure_automatic_detection.py` | `94c44f7c20e7ba91371fd5992f25a2bbc54cd11840de0bfaf14076699fb71844` |
| P2 evidence | `df29344593dde8a8b6dc9ce438630e7b9ca66251eb6b79c24b3ed82393f63f57` |

除独立运行现有聚焦测试，本审查另在内存中构造六类输入，不导入被审测试 helper，不修改被审代码。轴图改用 340×250、框 `(40,30,300,200)`、ticks 80/170/260 和 0/3/6，避免仅重复实现者 fixture 的固定位置；科学计数改用 `1e12`、`1×10^13`、`10¹⁴`。这些是通用算法反例，未注入论文目标、材料或几何答案。

| 核对 | 独立结果与关闭依据 |
|---|---|
| G2-1：实际 PDF box／旋转 | 使用真实 Poppler，四个 PDF 均取非零 MediaBox `[11 17 211 117]`、不同 CropBox `[50 25 150 75]`，旋转分别 0/90/180/270。PDF 中 `(100,50)` 黑色标记对应 MediaBox 左上相对坐标 `(89,67)`。记录变换分别给 `(712,536)`、`(264,712)`、`(888,264)`、`(536,888)`；实际墨迹中心各坐标均比对应结果小 0.5 px，满足 1 px 图像栅格闭合门。实现现在读取显式 MediaBox、CropBox，按实际 MediaBox 渲染尺寸映射，并保存原点／旋转；没有再把 `Page size` 当成渲染框。 |
| G2-2：字框偏移 | 数字 OCR 中心各偏右 2 px，仍返回实际 ticks 80/170/260，值为 0/3/6；`tick_bindings` 保留原 token 与真实 ink 关联，生产图像入口用实际 tick 拟合。纯 `fit_axis` 仍是内部算法边界，没有新增外部几何参数。 |
| G2-2：多位置歧义 | 每个实际 tick 右侧再画一个相距 2 px 的 tick，结果不 resolved，明确含 `axis_tick_association_ambiguous`。有限组合预算和多解保留，未用最低残差投票选一个位置。 |
| G2-3：独立单位词 | 独立 V/A/V token 组合保留 `axis_unit_conflict`；一致 V/V/V 得到 resolved 且 unit 为 V。关联发生在 tick 过滤前，原单位 token 仍存在于检测 OCR 记录。 owning 回归另覆盖多个邻近单位词的关联歧义。 |
| 科学计数与独立单位完整链 | `1e12`、`1×10^13`、`10¹⁴` 旁各有独立 `cm⁻³` token，生产图像算法入口得到唯一 log10 解、正确的实际 tick 位置和单位，三个值闭合。把中间单位改为 `cm⁻²` 或把最后指数改为 `10^x`，两者均无 resolved／可用 solution，没有退成线性解。 |
| G2-4：粗框与邻轴线成对检查 | 3/5/8 px 空粗框经 raw bytes `detect_source` 均仅一个 plot、零路径；在内边缘只隔一个白像素的独立黑线均保留，所有输出路径点只落在该线的 y 上。实现按各截面的连通暗墨迹排除轴，到白色分隔停止，未统一加宽删除带。 |

六类独立检查全部通过；真实 PDF 工具没有 mock。结构化 OCR token 检查明确属于算法／adapter 形状验证，本机仍没有 tesseract，不声称执行过真实 OCR。现有五文件聚焦命令与首轮相同，独立结果为 **87 passed in 10.22s**，无新增 skip/xfail。

### 原始源重放与照片假阳性判断

再次只读同一授权 `paper_source.pdf` 的 raw bytes，调用 `detect_source(raw)`，未读取旧 workspace 输出或同级文件。独立结果为 **30 images、21,677,754 pixels、18 plots、115 paths／局部片段、0 resolved axes**。全部 **17,169/17,169** 个像素引用在对应规范图像内且非白。源级三项未决与更新 evidence 一致。

随后在同一进程中第二次从 raw bytes 完整重放，断言两个完整 `SourceDetection` 对象相等，包含图像、overlay bytes、候选、像素、未决与 provenance，而非只比较计数。两次 receipt 均为 `2c9d8c9492696f56779dac2389e61a4b07c7a374c225695cd2e3a2d25fc910fa`。来源合同 `automatic-source-v2`、检测合同 `cartesian-candidates-v2` 及新增策略／box／tick 内容进入摘要；新 receipt 与首轮 v1 不同，独立结果与修订 evidence 一致。

程序按检测输出顺序暂存全部有路径的 overlay 至 `/tmp/e54-g2-rereview-ienkn68f/`。本审查实际通过 `view_image` 查看前两张，不以 PDF 页、figure 号或材料选择输入：

- `overlay-20.png`：完整恢复图包含示意区域与右侧器件照片。照片中五个路径候选高度重叠，位于蓝色表面，没有可见的 Cartesian 数据曲线；属于真实的照片假阳性。该恢复图共 7 个 plot 候选、5 条路径、656 个引用。候选均有未绑定身份和未解决轴，另保留局部支持／共享歧义／缺文字 mask 信息。
- `overlay-23.png`：可见两个普通 Cartesian plot，品红支持沿左侧图区的真实黑／红线局部线段分布，共 5 个路径候选、414 个引用。它们仍是局部支持，未由本审查绑定 figure、材料或科学 series。

五条照片假阳性属于当前 P2 可接受的有限候选限制，**本次不构成阻断**。判断依据是：实际叠图足以看清它们位于照片中，轴与身份未被确认；候选数量受固定图像内预算限制，照片自身没有触发路径预算，且没有消耗其他恢复图的候选预算或阻止真实曲线片段生成。它们可以在既定后续语义选择职责中被视觉拒绝。这里承认算法没有判定“照片”，也不把非白像素等同于曲线；不要求新增通用视觉分类器、按论文内容排除照片或额外 OCR 平台。

此限制与首轮空粗轴框缺陷不同：首轮是已确定轴墨迹被系统性当成曲线且没有正确 mask；本轮该成对负例已经关闭，照片候选则仍作为未决、可见且数量有限的待筛选项存在。115 个候选是多个页面表示和 plot 的合计，不能当作 115 条科学曲线。当前真实轴全部未决，P2 evidence 未称定量提取成功。

### 执行范围与资源

测试、六类反例、原始 PDF 两次重放全部依次运行；没有 xdist 或并行 Agent。环境继续使用单线程 OMP／OPENBLAS 和 `MALLOC_ARENA_MAX=2`。每次外层监测每 0.1 秒递归汇总被测进程树 RSS，达到 8 GiB 终止，均未触发。

| 本轮独立执行 | 结果 | 外层耗时／采样峰值 |
|---|---|---|
| 五文件聚焦 pytest | 87 passed，退出码 0 | 10.63s／113,084 KiB |
| 六类独立正反例，包含四次真实 Poppler | 全部通过，退出码 0 | 5.37s／74,120 KiB |
| 原始 PDF 两次完整检测与全对象重放比较 | 全部相等、全部像素引用非白，退出码 0 | 64.79s／136,572 KiB；第二次检测 31.55s |

监测仍是进程树采样 RSS，不是 cgroup 强制总量或 live Codex／WSL 增量认证。没有重复全目录、安装、真实 OCR、Worker 或 solver，不把本次限定复审升级成后续阶段门。

API、插件／中央边界仍与首轮相同：生产仅两个 figure 底层模块；无 page／figure／材料选择，无新 Operation、Agent、插件或中央字段。返工修改均对应四项审查发现和通用反例，没有引入案例数字或改变后续职责。

本次只更新本审查文件，保留首轮 FAIL 历史并追加当前 PASS；未改被审源码、测试、计划或 evidence，未 commit、未 deploy。`git diff --check` 通过。
