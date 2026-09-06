# R5 E5.4 P5：真实安装与科学链验收

日期：2026-09-06。状态：进行中，真实链在通用候选检测页覆盖处阻断。P4 精确
提交为 `86d4e85cff22db9dbd82fa35501a19a121deeb21`，依赖收简与当前安装提交为
`8fed358e75b3bda698a7ccc651661f8822c61f0b`；本文只记录 P5 现场事实，不提前
声称真实图提取、科学审查或资格已通过。

用户要求删除 P4 中派生的依赖身份输入及模型路径／摘要合同。
[有界后续修复](R5_E5_4_P4_CLEAN_RELEASE_AND_DEPENDENCY_PREFLIGHT.zh-CN.md#用户要求的依赖自动发现后续修复独立复审-pass)
首轮独立 GPT-6 复审 FAIL，三项有界返工完成后由同一审查者复审 PASS，阻断项
为 0。收简提交已形成并安装；下列旧 P4 发行与模型位置／摘要均为先前现场历史，
不是新安装输入，安装过程没有接受三个旧 `SCID_FIGURE_*` 变量。

## 1. 精确提交发行

从 P4 提交使用既有 `scripts/build_git_release.py` 构建临时干净发行：

- 跟踪源文件 249 个；
- `MANIFEST.sha256` 的 248 项全部核验通过；
- 发行不包含 `.git`；
- tarball SHA-256 为
  `592015fc13452b89d729f06ce65b4ea067a5b1ffc844ebd06001b447c35ee742`；
- 临时发行不是开发副本，不保存科学冻结数据。

## 2. 安装前现场检查

当前绑定实例为 `M7-test0`。读取到一个 2026-09-03 留下的旧合同
`queued` Run：`fig4_source_evidence_intake_retry_1`。当前无 `running`
Run。通过正式 `run_record_failure` 封存时，控制面以
`Run operation contract changed` 拒绝，未改写状态。现有代际测试保证新
Worker 不能领取、提交、恢复或改写该旧 Run；它仅作为不可恢复的
历史保留，不对数据库打补丁。

真实依赖已以服务身份通过 wrapper `--dry-run`：

- Pillow `12.1.1`；
- Poppler `22.02.0`；
- Tesseract `4.1.1`，可执行文件 `/usr/bin/tesseract`；
- `eng.traineddata` 位于
  `/usr/share/tesseract-ocr/4.00/tessdata/eng.traineddata`，SHA-256 为
  `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`；
- 最小 PDF 图像恢复、渲染和现场生成 `12345` 的 OCR 通过；
- 预检没有更改包、状态、服务或配置。

Local 后端仍是可信本地软隔离，`SEC-002` 保持已知问题。后续验收
检查发行、显式输入、提示、Schema 与工具清单不携带案例答案；
只能如实报告“未提供且未观察到访问”，不宣称宿主文件技术上不可读。

## 3. 待完成

1. 修复通用候选检测无法覆盖论文后部目标页的问题，不增加案例图号或手工像素输入。
2. 在两张真实图上完成真实 Agent request → materialize → Intake → audit 链。
3. 由独立 GPT-6 按预先冻结的精度、覆盖、不确定性和防泄漏门审查。

## 4. 无依赖身份输入的实机预检

未提交候选以真实 `da` 身份／服务 Python、原三插件和既有部署参数执行通用
wrapper `--dry-run`；三个旧 figure 身份输入全部清除，仍通过实际版本观察、
默认 `eng` 可用性和真实 PDF／OCR 调用。0.82s，进程树峰值 45,948 KiB；
没有安装、切换或修改包／状态／服务。内部记录只有实际工具路径／版本、`eng`
与固定 adapter，不冻结模型文件身份。新的精确提交发行与安装后复验须在本次
收简提交后执行；本节不替代两张真实图的科学链验收。

首轮复审后的定向对照确认：错误 `TESSDATA_PREFIX` 已在依赖调用和运行 OCR
环境中分别清除；无 `size` 参数的默认字体探针以确定性放大生成，真实识字通过。
同服务身份无旧变量的 wrapper dry-run 再次 PASS（0.92s、峰值 61,296 KiB），
仍无安装事务。依赖收简的首轮 FAIL 保留；三项返工复审 PASS 不更新科学状态。

## 5. 收简提交安装态

用户从干净提交 `8fed358e75b3bda698a7ccc651661f8822c61f0b` 完成事务安装并重启。
父调度会话随后实测：`scidiscovery-control.service` 与
`scidiscovery-approval-ui.service` 均为 `active`，两个 runtime identity
预启动检查退出 0，控制 socket 可用，审批 UI 的 GET 返回 HTTP 200。安装态公开
目录包含通用 `science.figure.request.prepare.v1`、
`science.evidence.extract.figure.v2` 和 `science.figure.evidence.audit.v1`；
support 视图包含确定性 `science.figure.evidence.materialize.v1`。旧 InGaAs
案例编译 Operation 不在公开或 support 目录。TCAD 使用已配置的外部 command
adapter，故本机 `tcad-control.service`／socket 不存在不是本阶段安装失败。

## 6. 第一张真实论文的自动选择阻断

会话重新绑定既有实例 `M7-test0`。首次公开动作只绑定冻结论文，不提供图号、
像素范围或点数；`science.figure.request.prepare.v1` 的预检、领取、提交、Schema
校验和封存均通过，但封存结果选择了论文 FIG. 5(a) 的材料扩散系数曲线，不能
直接检验当前器件级仿真与实测矛盾。该结果保留，不伪装为目标图。

同一 Operation 做一次有意修订：仍不提供图号，只明确要求选择与器件仿真输出
在相同自变量／因变量上直接比较的实验测量曲线，并排除纯材料参数拟合图。修订
同样一次提交即封存，没有格式拒绝；结果将器件级目标定位为 FIG. 10(a)，但返回
`inconclusive`：检测收据的页预算只产生到 PDF 第 8 页的候选，目标页没有
`plot_candidate_id`、路径候选或可绑定的可见系列身份。

这是通用候选生成覆盖不足，不是 Worker 输出格式、共享像素、点数统计或图号
选择错误。当前目录没有公开 Operation 能补生成后续页面候选，故停止该修订环，
不把早期 FIG. 5 结果送入物化，不手填 FIG. 10 像素边界，也不反复要求智能体
改写文本。P5 尚未通过，未产生曲线表、Intake、独立图证据审查或科学资格。

## 7. 固定八页截断的最小修复

独立 GPT-6 首先只读复核本节阻断，结论 PASS：安装及两次 Run 记录自洽，固定
八页上限有直接代码证据，停止修订和不物化错误图正确，修复可限制在既有候选
生成函数及直接测试内。审查明确禁止提出新 Operation、Schema、配置、注册表、
状态机、控制面或算法重构。

实现只删除 `recover_automatic_source` 的固定八页截断，按 PDF 实际页数顺序恢复，
仍由原有 2400 万总像素预算提前停止；源文件 64 MB、单图 2500 万像素、每页
32 个嵌入图和单命令 60 秒边界均未修改。没有增加操作者或 Agent 输入。内部
provenance 从 `automatic-source-v2/pages=8` 更新为
`automatic-source-v3/pages=all_until_total_pixel_budget`，公开 Schema 不变。

新直接回归在旧代码上先得到预期失败（只返回 1–8 页）；修复后确认十二页全部
恢复，并将测试总像素预算降低至 800 验证仍只保留前两页并返回
`source_pixel_budget`。自动检测与现有角色链串行聚焦 **85 passed**，峰值
**134,968 KiB**；`git diff --check` 通过。相同独立 GPT-6 复审最终 PASS：固定
八页根因关闭、原资源止损有效、未新增合同面、测试直接。尚未提交或重新部署；
因此本节 PASS 不改变上节真实 Run 的 `inconclusive`，安装态仍是 `8fed358`。

## 8. 目标漂移后的顺序更正

第 6 节两次 Run 不是 Fig.4 验收：旧代际 `research_objective` 绑定被预检以
`input_producer_contract_changed` 拒绝后，父调度器错误地用宽泛文字替代了固定
目标，第一轮选择 FIG. 5，第二轮又因“器件级实测曲线”措辞选择 FIG. 10(a)。
两者均保留为不可变历史，不进入物化。输出校验只证明来源候选内部一致，不证明
符合被遗漏的全局目标。

本轮目标明确固定为论文 Fig.4；Agent 不重新决定目标图，只定位其 PDF 参考页、
面板和可见系列身份。`science.figure.request.prepare.v1` 保持同一个 Agent
Operation，并在同一 Run 内先调用现有 PDF 文本工具，再以参考页调用现有 figure
检查工具。检查工具只在该页生成候选和叠图；Agent 最终提交语义绑定。Intent 仅
增加 `source_page`，使上下文校验和确定性物化按相同来源及页码重放。像素边界、
候选编号、坐标标定、点数、排序、CSV 和叠图仍完全由确定性代码产生。

`source_page` 可为空，但含义由来源类型唯一确定：栅格来源为空时保持现有单图
检测；PDF 来源为空时表示 PDF 文本工具未能定位目标页，检查工具返回确定性的
零候选未决结果及收据，校验器和物化器重放同一分支，禁止退回全篇扫描。这样
Agent 即使无法定位目标页，也能复制工具生成的来源摘要和收据，合法提交未决
结果，而不是自造收据或被迫猜测页码。

不新增 Operation、角色、实体、注册表、配置项、状态机或审批；不让操作者输入
页码，也不把 Fig.4 写进领域插件。Fig.4 来自当前研究任务，通用规约只表达“精确
目标不得被替换”。提交 `2f1246245e4220c3cac2d58741f53c8aec6c018e` 的全篇
扫描不作为最终设计：实现按页路径时恢复原有旧路径边界，避免用全篇 OCR 修补
调度目标漂移。修复范围只允许触及 figure prompt、检查工具输入、Intent 页字段、
页级确定性恢复／检测／重放及其直接测试。

独立 GPT-6 设计首审仅因上述“未定位页无合法收据”缺口判 FAIL；本节已按其
最小意见闭合，不附加其他设计；同一审查者复审 PASS 后进入实现，首轮 FAIL
历史保留。

实现保持同一个 Operation 和现有两个 Worker 工具：inspection 输入与输出统一
使用 `source_page`；prompt 明确固定目标不得替换、PDF 文本定位必须先于按页
inspection；Intent、上下文校验和物化器共享同一 `source_page` 与页级收据。
PDF 空页引用产生 `reference_page_unresolved` 的零候选稳定结果，raster 空页引用
保持单图行为。旧无语义页引用入口恢复最多八页的原边界，不再全篇扫描。

五个核心红测试在实现前全部按预期失败，分别暴露缺少页级检测、工具字段、提示
顺序、物化重放和 PDF 空页分支；实现后 **5 passed**。页码伪造负例、模型可见
Schema 探针、自动检测、角色链、工具真实处理、可选插件和 installed wheel
聚焦测试最终 **96 passed、19 deselected**，64.92s，峰值 **155,120 KiB**；
installed wheel 的 4 个 figure 定向入口另行复跑 **4 passed、19 deselected**，
40.69s，峰值 **83,188 KiB**；`git diff --check` 通过。独立 GPT-6 严格沿
prompt→工具→页级检测／收据→Intent→上下文校验→物化重放链复审，结论
**PASS**，没有新增审查项。尚待提交和重新部署，当前安装态仍为 `8fed358`，
不得用未部署源码继续科学链。
