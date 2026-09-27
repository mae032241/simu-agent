# R5 E5.4 P3：自动候选与现有角色链接入

日期：2026-09-06。仓库 `123/scidiscovery-e5.2`，基线 `bfc4e3997ecd54bb947bbe02ef6eba52f7a7c488`，未提交工作树。依据[已审 E5.4 计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)、P0 三形状／资源边冻结以及 P1/G1、P2/G2 的现有边界。P3 首轮工程聚焦 **176 passed** 后，[G3 独立审查判定 FAIL](../reviews/R5_E5_4_P3_G3_GPT6_REVIEW.zh-CN.md)。下文保留首轮历史，末节记录仅针对 G3-1/2/3 的有界返工：聚焦 **181 passed**，并获[G3 独立复审 PASS](../reviews/R5_E5_4_P3_G3_GPT6_REVIEW.zh-CN.md#有界返工复审)。本记录不授予真实 OCR、真实 Agent、科学资格、安装切换或 E5.4 关闭。

## 实现范围

生产只修改 figure 插件的八个既有模块：`figure_worker_tool.py`、`figure_science_operations.py`、`operation_transforms.py`、`figure_digitization.py`、`figure_digitization_contract.py`、`figure_evidence.py`、`figure_evidence_validation.py`、`figure_evidence_normalizer.py`。没有修改 P2 detector/source、plugin.py、其他插件、`src/`、部署／安装、README、调度、Run、资格、审批或编译器。

测试修改限定在已授权 figure/Worker/installed 文件，新增一个 `test_figure_role_chain_v2.py`。扩大聚焦回归发现白名单外 `test_m2_optional_figure_plugin.py` 仍断言旧 intent 与完整族端口，已暂停报告；获得明确补充授权后，只同步该文件三处直接相关合同断言，没有修改其他 M2 语义。没有新增生产 Operation、Agent、plugin、registry 或状态；完整组合仍为 **48 个 Operation**，其中 figure 仍为 5 个。没有增加 Worker 工具数。

## 输入、重放与职责

- 现有 `worker_curve_figure_inspect_source` 现在只接受绑定源名，拒绝 page、figure、geometry、tuning 和额外字段。内部从源 bytes 调用 P2 自动检测，把规范原图和候选 overlay 发布为 run-local 只读文件。公开投影只有 source digest、detector version/receipt、恢复表示／代码页码、P/L 叠图标识到 candidate ID 的映射、可见 OCR 文字／锚点 ID 和未决；不公开像素、bbox、轴 ticks、seeds、统计或调参接口。拒绝非论文／栅格绑定和预览路径偏离本 Run 的目录。
- request Operation 身份保留，输出改为严格 `intent.v2`。Agent 只选择 plot/path candidate ID，记录 visible label、semantic identity、可选已有文字锚点，以及未决／拒绝原因。可选 `research_objective` 使用既有 schema 和 `prior_signal`；源仍是唯一证据 context。图号、panel、材料与科学目标的匹配由 Agent 比对原文／caption／overlay 判断，检测器不代做。Agent 的任何自然语言都不被解析成算法参数。
- 输出 context validator 从同一 `paper_source` 完整重放，检查 source hash、receipt、plot/path 所属关系和适用的文字锚点。materialize 同样从 source+intent 重放，不读取先前 Worker 工具文件。外部旧 geometry request 已从新 Operation 输入删除。
- 确定性物化从检测的真实 pixel supports 和可信轴解生成 `request.v3`、`manifest.v2`、`report.v2` 与附件。CSV 按科学 x 排序，保留原像素和 path ID；反向 x 与 log y 不交换配对、不重复取 log。点数、范围、gap、可见比例、误差、CSV 与统计由代码计算。候选按稳定 ID 排序，Agent 调整选择顺序不会改变附件与 manifest 的绑定顺序。
- 首轮实现历史（已被 G3-1/2 否决，由末节返工替代）：共享像素保留同一 pixel_id/shared_group，引用可以重复而物理支持统计去重，但路径多解／共享依赖被统一标记不可计量；可见标签无法等于该恢复图某个完整 OCR token 时，以 `identity_visible_label_unconfirmed` 丢弃测量表。这两项限制不是当前已审合同的合法要求，不能再作为现行资格规则。局部缺失只保留实际像素、不跨空白插值的行为保留。

## 三种结果与完整族

| 结果形状 | request / manifest / report | source / overlay / tables |
|---|---|---|
| measured | 各 1，真实来源、轴和被选择的测量 series；局部限制保留 | 1 / 1 / 1–32 |
| unresolved_image | 各 1，明确未决；缺轴不填 calibration，无确认测量则 series 为空 | 1 / 1 / 0 |
| unrecovered | 各 1，源 hash、receipt、原因；无伪 image hash、宽高、对象、轴或 panel | 0 / 0 / 0 |

来源使用 `embedded`、`page_render`、`raster`、`unrecovered` 判别分支；只有 embedded 要求 PDF 对象。page_render 保存实际页／变换／MediaBox/CropBox，测试以现场合成 PDF 经真实 Poppler 验证。不可恢复分支不借正宽高或假图填充 schema。新版 validator 先检查结果形状再执行数值校验，附件声明必须存在，显式空集合可通过；可信测量缺附件或删掉相应声明均拒绝。

Intake/Audit schema 不变，两个既有 Agent 精确消费 paper_source+intent+同次 materialize 的 request/manifest/report/实际附件。稳定锚点在所有形状保持非空。复用现有 `complete_transform_family` 检查 producer 实际集合，revision guard 对实际存在的成员核对 prior/review parentage，不再要求每个附件端口非空。两种零表的初稿→独立 audit→一次完整修订→再次 audit 都通过真实本地 Root/Worker 文件生命周期测试；这些测试使用合成科学 payload 验证工程合同，不是科学 Agent live 结果。

normalization 继续用 figure 领域 guard，明确拒绝没有可计量表的完整族，并在确定性 normalizer 再次拒绝零表。bundle 同样声明完整 producer family。旧 Artifact 的底层模型仍可读取；新 Operation schema 只接新代际，不能把旧 request／manifest／review 改标签后晋级。原手填几何测试只保留为历史算法单元，不作为生产入口；旧测试 synthetic compile Operation 已删除，没有生产兼容 shim 或双入口。

## 编译资源与真实依赖边界

规范 bytes `DETECTOR_CONTRACT` 包含 P2 detector version、policy、固定预算、source contract/policy，以及 Pillow **12.1.1**、Poppler **22.02.0** 的版本声明。其合法引用边严格为 request 输出 context validator 与 materialize transform；没有挂到 worker_tool，也没有修改编译器。

源码测试直接修改实际资源 bytes，分别更改 detector version 与测试用 OCR model digest，验证两条 Operation digest 变化、全部 curve Operation digest 不变、完整目录仍 48 条。既有 P0 同资源边探针继续覆盖 installed wheel 的真实组件解析。

运行时核对当前 Pillow；PDF 分支执行各 Poppler 命令读取实际版本。当前缺 tesseract，实际 adapter 明确返回 `ocr_dependency_unavailable:tesseract`，不补造轴。OCR 合同的 version/model_sha256 为 **null，awaiting_P4**，没有伪填模型 hash；如果当前出现未经 P4 供应／核验的 OCR executable，运行时明确失败。P4 仍需供应真实版本与模型、核验真实 hash 并完成正向实机 OCR／安装预检；本阶段的 OCR token patch 只用于合成算法与生产 materialize 重放测试，不能充当真实模型验证。

## 红测、回归与内存

实现前，新测试观察 **3 failed、7 passed（0.39s）**：旧 inspect 接受 page，旧 intent 不接受 v2，两个零表合同缺失。随后实现转绿，没有 skip/xfail。

后续测试覆盖：公开／实际 Worker schema 与 submit 对机械字段的共同拒绝；nested binding 额外字段；伪造 source/receipt/plot/path/anchor、跨 source、跨 plot；删除工具目录后从同 bytes 重放；真实 detector resource digest；三形状／缺声明／丢附件；零表角色链、缺锚点、混两个物化族和 normalization guard；共享像素统计／不可计量性；反向 x、log y、局部缺失、选择顺序；缺 OCR、不匹配 Pillow／未供应 OCR、真实合成 PDF page_render。

| 串行执行 | 结果 | 监测 |
|---|---|---|
| 首轮完整 `tests/operations tests/artifact_agent` | 530 passed、10 failed，150.17s | 150.72s；进程树峰值 251,752 KiB |
| 最终生产代码的完整两目录 | 534 passed、10 failed，165.75s | 166.21s；进程树峰值 250,880 KiB |
| 最终 owning figure/Worker/M2 + installed tool/resource 聚焦 | **176 passed，72.19s，退出码 0** | 72.71s；进程树峰值 **209,684 KiB** |

完整命令为 `python -m pytest -q --tb=line tests/operations tests/artifact_agent`。环境统一 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`；串行无 xdist。外层每 0.1 秒通过 `ps` 递归汇总 pytest 及子进程 RSS，达到 8 GiB 终止进程组；均未触及。不是 cgroup 强制内存总量，不包括 live Codex/WSL 增量门。

两次全目录中的新增失败均为同一个 installed figure tool smoke 尚在读取旧公开字段：先是 `local_path`，迁移后暴露下一项旧 `access` 自报字段。最终改为检查 `source_preview`、`candidate_overlay` 的真实存在及文件只读 mode，并作上表定向复验。其余九项与 G1/G2 已记录 node ID／原因一致：installed hardened Run 一项、L4 一项、L5 六项为旧 `operation_runtime_unavailable`／旧拒绝码断言，`test_spec` 一项为旧字段列表未包含 `complete_transform_family`。本轮没有重新建立基线快照，没有改它们或中央来消除失败；完整目录不能称全绿。

最后只改上述 installed 测试断言与历史算法测试 helper 的显式名称，没有再改生产。最终聚焦命令包含：`test_figure_automatic_detection.py`、`test_figure_role_chain_v2.py`、`test_figure_semantic_compilation.py`、`test_m5_figure_review_closure.py`、`test_figure_local_observations.py`、`test_curve_figure_digitization_tool.py`、`test_agent_contract_alignment.py`、`test_m2_optional_figure_plugin.py`，以及 installed 文件的 `test_clean_installed_domain_tools_execute_the_packaged_implementations`、`test_installed_detector_resource_uses_existing_compilation_edges`。

## 未完成门

未安装 OCR、未部署、未运行真实论文 raw PDF P3 live、真实 spawn、独立第二图、solver、真实模型 hash、文件不可读隔离负探针或服务身份预检。没有读取历史几何／CSV／overlay 作为算法输入，没有使用真实论文的页／对象／标签／hash 编写生产或测试。本阶段是源码与安装包工程合同测试；installed fixture 仍使用既有 system_site_packages，不能据此宣称历史答案不可读或 P4 安装隔离已验收。真实 OCR、目标覆盖与独立精度门留给 P4/P5；P3/G3 已经独立复审通过。`git diff --check` 通过；`src/`、其他插件、deploy 和 README 无差异。未 commit、未 deploy。

## G3 首轮 FAIL 后的有界返工

首轮审查的三个阻断和独立反例完整保留在原 G3 报告，返工后由同一独立审查者复核并判定 P3/G3 PASS。返工只改三个既有生产模块 `figure_digitization.py`、`figure_digitization_contract.py`、`figure_science_operations.py`，以及现有 P3 测试 `test_figure_role_chain_v2.py`、`test_figure_semantic_compilation.py`；文档只更新本 evidence 与计划状态。没有改 P2 detector/source、normalizer、其他插件、中央 `src/` 或安装部署路径，没有新增字段、Operation、Agent、注册表或状态。完整 catalog 仍为 **48 个 Operation**，figure 仍为 5 个；资源 digest 回归同时重验此数。

- **G3-1**：删除完整 visible_label 必须等于单一 OCR token 的隐式硬门。已通过 source/receipt/plot/path context 的无 anchor 语义绑定，保留 Agent 的原图／原文身份判断并交现有独立 audit；没有把语义文本变成几何参数。显式提供 identity_anchor_id 时，原有同恢复图锚点存在性和完整文字匹配仍严格执行。新回归从现场合成原图和分词 `Reference`、`data` 出发，完整保留 `Reference data`，经实际 context 和生产 materialize 得到测量表；同源同标签加伪 anchor，context 和物化均拒绝。仅替换 OCR token adapter，不注入候选、像素或轴解。
- **G3-2**：仅使用已绑定、已选择路径的实际 pixel_id owners 与既有 shared/path.unresolved，逐行解释资格。一个 pixel_id 被多个所选系列引用时，该真实共享观测可由各系列定量；若路径带 `path_junction_ambiguous`，未被多个所选系列共同引用的行仍为 `ambiguous_path`、eligible=0。P2 shared 标记继续作为 provenance，但单凭未选候选留下的 shared 标记不会解除连接歧义。没有扫描未选候选或新增连通组／同列齐全判定器。全局统计仍按实际 pixel_id 去重，不新增协方差／字段。新生产 materialize→normalization 合成双线回归中，共享观测所在的三个所选系列有可用定量区间，另一纯独占歧义分支仍不可用；不把整条分支全部资格化。另选同图一条歧义路径时，所有行保持不可计量，normalization 返回 `no_quantitative_eligible_rows`。双方共享行 eligible、global_unique_pixel_count 去重、global_duplicate_pixel_rows 和独占歧义行均逐项断言。
- **G3-3**：同一个 intent 输出合同中的 bindings 和 rejected_candidates 数组均添加 JSON Schema `uniqueItems`；extra=forbid 不变。同 candidate_id 不同文字、selected/rejected 互斥等关联约束明确写入既有 `curve.figure.request.internal_consistency` payload 语义规则并由原 validator 执行，未引入另一规则注册表。四个新增负例实际运行 Root preflight/invoke→Local Worker assignment，读取当次 `result.schema.json` 后提交同一 envelope：完整重复 binding/rejection 在实际 schema 即拒绝，submit 诊断为 `runtime.schema`；同 ID 不同文字与 selected/rejected 冲突的可见语义规则明确，实际 submit 均按 `curve.figure.request.internal_consistency` 拒绝。

先红后绿：生产返工前针对新增 G3 用例观测 **6 failed、1 passed、57 deselected（4.30s）**；补齐单选真实歧义反例并修正测试对纯独占分支的过强“全系列可用”断言后，新增 G3 用例 **8 passed、57 deselected（4.32s）**。这两次短探针未采样内存，不冒充受监测执行。最终最小可信 owning 回归为以下八文件，串行 **181 passed in 31.13s，退出码 0**；外层耗时 **31.54s**，pytest 全进程树采样峰值 **147,828 KiB**，8 GiB 止损未触发：

```sh
python -m pytest -q --tb=line \
  tests/operations/test_figure_automatic_detection.py \
  tests/operations/test_figure_role_chain_v2.py \
  tests/operations/test_figure_semantic_compilation.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_figure_local_observations.py \
  tests/operations/test_curve_figure_digitization_tool.py \
  tests/operations/test_agent_contract_alignment.py \
  tests/operations/test_m2_optional_figure_plugin.py
```

环境 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`；无 xdist。外层每 0.1 秒用 `ps` 递归采样 pytest 及后代 RSS，达到 8 GiB 终止进程组；这不是 cgroup 强制上限或 live Codex/WSL 总量。本轮没有重跑安装矩阵或完整两目录，首轮九项既有基线失败记录保留，不能宣称全库绿。`git diff --check` 通过。独立 G3 复审同样运行 181 项聚焦测试并全部通过，采样进程树峰值 **158,016 KiB**；P4/P5 的真实 OCR 供应、真实模型 hash、隔离安装负探针、真实 Agent/PDF 与独立精度覆盖门仍未完成。未提交，未部署。
