# R5 E5.4 P5：真实安装与科学链验收

日期：2026-09-06。状态：进行中。P4 精确提交为
`86d4e85cff22db9dbd82fa35501a19a121deeb21`；本文只记录 P5 现场事实，
不提前声称安装、真实图提取、科学审查或资格已通过。

当前安装暂停：用户要求删除 P4 中派生的依赖身份输入及模型路径／摘要合同。
[有界后续修复](R5_E5_4_P4_CLEAN_RELEASE_AND_DEPENDENCY_PREFLIGHT.zh-CN.md#用户要求的依赖自动发现后续修复独立复审-pass)
首轮独立 GPT-6 复审 FAIL，三项有界返工完成后由同一审查者复审 PASS，阻断项
为 0；当前等待形成收简后的精确提交与发行。下列精确提交发行与模型位置／摘要
均为先前现场历史，不是新安装输入或新候选发行证明；不得据此安装旧合同版本。

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

1. 使用既有事务安装入 P4 精确提交，并完成安装后同服务身份复验。
2. 核对安装态插件、单一编译目录、Operation 摘要、Codex 配置和工具。
3. 在两张真实图上完成真实 Agent request → materialize → Intake → audit 链。
4. 由独立 GPT-6 按预先冻结的精度、覆盖、不确定性和防泄漏门审查。

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
