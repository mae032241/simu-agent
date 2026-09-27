FAIL；阻断项 3：当前发行构建失败、默认 OCR 数据目录存在环境覆盖、Pillow 声明下界与预检调用不一致。

日期：2026-09-06。独立 GPT-6 工程审查，范围仅为依赖输入收简。
仓库 `123/scidiscovery-e5.2`；基线 HEAD
`86d4e85cff22db9dbd82fa35501a19a121deeb21`；审查前后 tracked diff SHA-256
均为 `a5d7e86fcdeb91899aeb55f9d5a9b37b7eb80b785c99a124f40b9f296d02bf7c`。
完整读取 15 个变更文件的差异、相关调用方、E5.4 计划、架构总章、设计宪章与全部
33 项约束。没有修改被审实现、测试、计划或 evidence，没有提交、部署、调用科研
控制面或读取历史科学答案。本文件是唯一新增的持久文件。

## 阻断项与最小修复

### D1 / P1：新增证据文字使当前候选无法通过现有发行入口

位置：[P4 evidence](../evidence/R5_E5_4_P4_CLEAN_RELEASE_AND_DEPENDENCY_PREFLIGHT.zh-CN.md)
第 261 行，新增了具体用户 home 下的 Python 路径。
[发行扫描器](../../../scripts/build_git_release.py)第 114–120、214–220 行明确
拒绝这类路径。本轮真实运行
`test_git_release_builder_emits_clean_manifested_source` 失败：

```text
RuntimeError: release scan failed:
  machine-specific user home path: docs/plans/evidence/R5_E5_4_P4_CLEAN_RELEASE_AND_DEPENDENCY_PREFLIGHT.zh-CN.md
```

这也阻断 [installed fixture](../../../tests/operations/conftest.py)第 74–90 行的
首个 release 构建步骤。因此 evidence 中“61 passed”和干净 wheel 通过的记录
不能证明当前精确差异已经通过，不据此判断此前运行是否真实。

最小修复：仅把本次新增证据里的本机路径改成可发行的中性定位说明，并在最终
文档内容确定后补记实际检查结果；保留发行扫描规则，不增加例外或扫描绕过。

### D2 / P2：安装验证默认数据目录，运行时却允许 TESSDATA_PREFIX 改写它

位置：[figure_dependencies.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_dependencies.py)
第 50–53、76、89–91 行，及
[figure_detection.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_detection.py)
第 500–502 行。本次删除 `--tessdata-dir` 后，两处 subprocess 仍直接继承
`os.environ`，包括 Tesseract 自身识别的 `TESSDATA_PREFIX`。
[service_python](../../../deploy/install.sh)第 245–269 行则通过 `env -i`
清除该变量。于是安装时验证的默认语言查找与运行时的查找不一致，JSON 和工具
版本保持不变时，进程环境仍可成为数据目录的另一输入。

独立真实探针调用现有 `validate_figure_dependencies`，以当前服务用户执行，
调用方环境带 `TESSDATA_PREFIX=/etc`；预检通过真实 PDF 恢复、渲染与 `12345`
OCR。随后把输出合同直接交给现有 `verify_ocr`，只改变该进程变量：

```text
SERVICE_PREFLIGHT_WITH_CALLER_TESSDATA_PREFIX: PASS
OBSERVED_VERSIONS: 12.1.1 22.02.0 4.1.1
RUNTIME_DEFAULT: tesseract 4.1.1
SAME_CONTRACT_WITH_TESSDATA_PREFIX: ambiguous OCR language list
RUNTIME_AFTER_ENV_REMOVAL: tesseract 4.1.1
```

这里证明的是环境导致的真实行为分歧；没有宣称已在生产 Worker 中观察到该变量，
也没有要求冻结模型字节。若覆盖目录具有 `eng`，当前检查还会接受该目录提供的
语言数据，因为它只比较工具版本并检查语言列表。

最小修复：现有依赖调用和实际 OCR 调用均从传给子进程的环境中删除
`TESSDATA_PREFIX`，保持与安装预检相同的默认查找。只补该分歧的定向反例；
不记录数据目录，不恢复模型路径／hash，不新增配置或环境协议。

### D3 / P2：放开 Pillow 固定版本后，预检仍调用声明下界不存在的参数

位置：[figure_dependencies.py](../../../plugins/curve_figure_evidence/curve_figure_evidence/figure_dependencies.py)
第 107 行调用 `ImageFont.load_default(size=42)`；本次
[安装指南](../../INSTALL.md)第 66 行推荐 `Pillow>=10.0,<13.0`，
`validate_base_python` 和根包依赖同样允许 10.0.x。
Pillow 官方 API 文档明确指出 `load_default` 的 `size` 参数在 **10.1.0**
加入。因此合规的 10.0.x 环境仍会在生成预检图像时因不支持该关键字参数失败，
无法兑现本次“沿用现有包范围”的声明。
[来源：Pillow ImageFont API](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.load_default)。

这是代码与上游 API 的静态确认；本轮没有安装 Pillow 10.0，也没有把模拟参数
签名当作真实旧版本安装测试。

最小修复：仅让现有预检图像使用包版本下界已支持的字体 API，保持探针文字可
识别；不增加版本分支框架，不把下界改成本机版本，不另添字体依赖或配置。

## 已确认的收简与边界

- 三个旧 `SCID_FIGURE_*` 身份变量、CLI 参数、模型路径／摘要字段与 hash
  校验已从生产入口和当前安装说明删除；没有替代指纹或用户派生身份输入。
- 唯一持久依赖记录仍是包内 `figure_dependencies.json`。安装器以服务身份及
  服务 PATH 自动观察四个绝对 executable 和工具版本，在暂存包切换前及安装后
  复验同一记录；没有新增配置层、注册表、生命周期或控制面字段。
- Pillow／Poppler 的本机固定值已删除；供应后仍严格比对观察版本。版本解析
  保留完整单个版本 token，语言列表接受现有测试的 Tesseract 4／5 两种标题。
  未发现需要新增版本兼容框架的证据；本轮不把可选增强列为缺陷。
- `DETECTOR_CONTRACT` 直接纳入同一记录；request context validator 与
  materialize transform 仍是既有两条资源消费边。源码 digest 反例通过，未发现
  第二份摘要配置或无关 Operation 摘要变化。
- 未供应记录时版本为空、OCR 为 unavailable；`_ocr` 与 `replay_detection`
  已删除 PATH 中 Tesseract 的回退／探测。已读 installed smoke 明确放置一个
  可执行 Tesseract，验证不会调用它；本轮因 D1 未能运行该 installed 路径。
- OCR 部署正例明确使用模拟 executable／数据，真实 PDF 和 Pillow 调用仍在；
  文档也明确模拟边界。没有据此认定真实模型或两图科学验收通过。
- 差异没有扩展科学检测算法、curve／TCAD 实现、调度、审批、恢复或隔离范围。
  33 项约束中直接相关的是 IMM-002、DET-001、PLG-002、RES-002、MIG-002；
  本审查不改变约束登记状态，也不继承历史 PASS。

## 本轮实际检查

统一使用 `PYTEST_ADDOPTS=''`、`PYTHONDONTWRITEBYTECODE=1`、
`OMP_NUM_THREADS=1`、`OMP_THREAD_LIMIT=1`、`OPENBLAS_NUM_THREADS=1`、
`MALLOC_ARENA_MAX=2`；pytest 使用 `-q -p no:cacheprovider --tb=line`。
全部串行，无 xdist。外层每 0.1 秒使用 `ps` 汇总监控进程及全部后代 RSS，
7 GiB 即停止；观察峰值均远低于 8 GiB。

| 检查 | 实际结果 | 外层耗时／进程树峰值 |
|---|---|---|
| `python -m pytest … tests/artifact_agent/test_deploy_scripts.py` | 60 passed、1 failed；失败为 D1 | 8.69s／113,868 KiB |
| 下列 5 个源码 node（包含 2 个参数化案例） | 6 passed | 1.75s／107,212 KiB |
| 现有安装预检与真实 Tesseract 环境对照 | 成功复现 D2；同合同清除变量即恢复 | 0.62s／65,272 KiB |
| `bash -n deploy/install.sh deploy/reinstall.sh` | PASS | 只读语法检查 |
| `git diff --check`、HEAD／diff 摘要复核 | PASS；被审 tracked 差异未改变 | 只读检查 |

源码 node：

```text
tests/operations/test_figure_automatic_detection.py::test_ocr_missing_and_environment_failure_are_distinct
tests/operations/test_figure_automatic_detection.py::test_ocr_cli_adapter_is_structured_and_restricted
tests/operations/test_figure_role_chain_v2.py::test_real_detector_resource_bytes_control_only_declared_consumers
tests/operations/test_figure_role_chain_v2.py::test_no_tesseract_never_invents_axes
tests/operations/test_figure_role_chain_v2.py::test_runtime_dependency_identity_is_verified
```

环境探针初次因单独导入插件触发未供应源码 PYTHONPATH 而失败；改为 `runpy`
直接加载唯一依赖模块后完成上述真实对照，没有修改被测代码。该探针组织错误
不计入产品缺陷或 pytest 结果。

遵循相关失败即调查的原则，D1 确认后未重复已知会在相同 release fixture 失败
的 installed 矩阵，没有绕过扫描器手工造 wheel；没有运行全仓或完整两目录。
本次没有改架构合同，未扩跑架构／控制面套件；真实部署和科学链不在本审查范围。

父会话的未跟踪 P5 evidence 始终未改写；审查前后 SHA-256 均为
`aa5ba43262a3a014ea07bc5cd6b5f33fc4a0384e3afcbf6730038109d233fefb`。
仅核对其文件完整性，未把其中科学内容或历史结论当作实现证明。

本轮 FAIL 只要求关闭 D1–D3 的上述最小差异，并复核对应依赖检查。没有附加
模型签名、供应指纹、配置系统、注册表、沙箱、权限、恢复或控制面任务。

## D1–D3 有界返工复审：最终 PASS

PASS；阻断项 0。日期：2026-09-06。首轮 FAIL 及其证据原样保留；本节是当前
依赖收简候选的最终工程复审结论，不代表 P5 部署或科学验收完成。

基线 HEAD 仍为 `86d4e85cff22db9dbd82fa35501a19a121deeb21`；本节绑定
tracked diff SHA-256
`9d54b9c82b4ca2bfe2a758645619f76039a99e0c586a23b04729948cedaa95ab`。
只复核 D1–D3 的修复和对应测试，没有重开算法、控制面、隔离或兼容性审查。

| 首轮阻断 | 复审结论与独立依据 |
|---|---|
| D1 发行构建 | 已关闭。P4 evidence 的新增机器 Python／临时路径改为中性说明；原 `test_git_release_builder_emits_clean_manifested_source` 通过，builder 与扫描规则未变。此前通过记录已明确限定为追加完整文字前的结果。 |
| D2 环境覆盖 | 已关闭。`_run` 与实际 `_ocr` 各自在传给子进程的环境中删除 `TESSDATA_PREFIX`。定向测试覆盖两条路径；独立真实探针在带错误变量的进程中直接调用依赖预检、`verify_ocr` 和实际 `_ocr`，均通过，不依靠 service `env -i` 掩盖变量。 |
| D3 字体 API | 已关闭。预检改用无参数 `ImageFont.load_default()`，先写小图再以既有 `Image.Resampling.LANCZOS` 放大；没有提高 Pillow 下界、增加版本分支或字体依赖。无 `size` 参数签名的定向测试通过；真实当前 Pillow 的新版探针仍识别 `12345`。未宣称已安装并测试 Pillow 10.0。 |

复审亲自执行下列最小 owning 测试，同一个串行 pytest 调用为 **3 passed，
1.79s**；外层 **2.19s**，监控进程及全部后代 RSS 峰值 **108,332 KiB**：

```text
tests/artifact_agent/test_deploy_scripts.py::test_git_release_builder_emits_clean_manifested_source
tests/artifact_agent/test_deploy_scripts.py::test_figure_preflight_uses_default_data_and_baseline_font_api
tests/operations/test_figure_automatic_detection.py::test_ocr_cli_adapter_is_structured_and_restricted
```

沿用首轮 `python -m pytest -q -p no:cacheprovider --tb=line` 和单线程环境，
无 xdist。真实环境对照独立顺序执行，**1.03s／95,424 KiB**，输出：

```text
DIRECT_PREFLIGHT_WITH_TESSDATA_PREFIX: PASS
OBSERVED_VERSIONS: 12.1.1 22.02.0 4.1.1
SAME_CONTRACT_WITH_TESSDATA_PREFIX: tesseract 4.1.1
ACTUAL_OCR_WITH_TESSDATA_PREFIX: ['12345'] tesseract 4.1.1
DEFAULT_AND_OVERRIDE_RESULTS_IDENTICAL: PASS
```

该探针设置 `TESSDATA_PREFIX=/etc`，直接调用现有 `main()` 完成真实 PDF／OCR
预检，把其输出合同仅在测试进程内交给运行 adapter；没有写入供应 JSON 或修改
被审文件。清除变量后版本校验结果相同。每 0.1 秒记录进程树 RSS，7 GiB 止损
未触发，总峰值远低于 8 GiB。`git diff --check` 与两个部署脚本的 `bash -n`
均通过。执行者报告的 63 passed 和 wrapper dry-run 不计作本审查亲自重跑结果。

返工限定于现有两处 subprocess 环境、预检图像生成、对应测试与事实说明。
五个生产文件相对基线共 55 行新增／62 行删除，净减 7 行；未增加身份输入、
模型指纹、配置层、注册表或控制面。唯一 JSON、绝对 executable／实际版本绑定、
未供应 OCR 行为及原 request／materialize 资源边保持原审查已确认的边界。

本次只追加本节；被审 tracked 差异未改。P5 evidence 在本次复审开始时的摘要为
`9c4581f783f84f4d991f3ad54fa2007712d77ce04f5b72772f5f3942168605f4`，
复审结束保持一致；未读取其科学内容。没有提交、安装、部署或科研控制面操作。
不新增后续工程任务；本 PASS 仅关闭本次依赖收简的工程审查门。
