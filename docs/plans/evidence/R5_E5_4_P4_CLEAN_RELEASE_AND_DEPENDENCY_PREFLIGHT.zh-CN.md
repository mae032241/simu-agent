# R5 E5.4 P4：干净发行与离线依赖预检

日期：2026-09-06。基线 `4a6ed35ce00442faf3187040f7a62ad26338f854`，仓库
`123/scidiscovery-e5.2`，本报告绑定未提交候选工作树。依据[已审计划](../R5_E5_4_GENERIC_AUTOMATIC_FIGURE_EXTRACTION_AND_CASE_PLUGIN_REMOVAL_PLAN.zh-CN.md)
P4、6.1–6.3、7及已通过的 P3/G3；不是精确 P4 提交后的发行证明。

**状态：P4 工程复审 PASS；manager PATH 有界返工已关闭首轮工程缺陷。
真实 OCR／模型／PDF 联合预检 PASS。首轮 G4 仍按过度强隔离条款判定部署门
FAIL；该口径现恢复为架构总章已冻结的可信本地软隔离，已获独立复审 PASS；修正后的 G4 部署前置门 PASS。** 没有部署、启停服务、修改系统权限、切换后端、提交或
读取控制数据库；没有编写科学结果。

## 合同与实现边界

`SCID_FIGURE_TESSERACT_VERSION`、`SCID_FIGURE_OCR_MODEL_PATH`、
`SCID_FIGURE_OCR_MODEL_SHA256` 是安装输入。模型须为已有绝对 `eng.traineddata`
路径；版本是供应者明确给出的精确 Tesseract 版本，摘要通过服务身份真实读取模型
字节核对。没有猜测或虚构本机版本／hash，没有下载或复制模型。

figure 插件的 `figure_dependencies.py` 只拥有依赖身份与最小真实调用。安装器把
服务 PATH 中实际找到并解析的 `pdfinfo`、`pdfimages`、`pdftoppm`、`tesseract`
绝对路径，以及 Pillow **12.1.1**、Poppler **22.02.0**、OCR 版本／模型路径／
真实 SHA-256 写入暂存包唯一 `curve_figure_evidence/figure_dependencies.json`。
其规范序列化内容直接并入现有 `DETECTOR_CONTRACT`，沿原 request context-validator
与 materialize transform 资源边进入两条 Operation digest；没有新增组件边、
Operation、Agent、plugin、registry、状态或中央字段。

运行时只读取这一包内绑定；不再读取三个安装变量。PDF 和 OCR 使用合同内绝对
可执行路径，OCR 显式 `--tessdata-dir`、`-l eng`，固定
`--psm 11 -c tessedit_create_tsv=1`，不依赖额外未绑定的 `configs/tsv` 文件。
每次重放核对实际依赖版本和模型字节；OCR provenance 包含实际版本与已核对摘要。
只在两个既有 PDF subprocess helper 与 OCR adapter 接入依赖路径，没有改变
P2 检测、轴、路径、预算或 P3 资格算法。未供应记录的源码／普通 wheel 明确为
`unavailable`，可以编译；没有 Tesseract 时保持原有未决，有未经绑定 OCR 则拒绝，
不能据此宣称具备真实 OCR 或通过 figure 安装预检。

安装预检由 `service_python` 在 `SCID_WORKSPACE` 下以 `SCID_SERVICE_USER`／
`SCID_SERVICE_GROUP` 执行，清空操作者环境，禁用 user site，使用真实
`SCID_PYTHON`。PATH 来自 systemd 默认搜索路径及 manager 的实际 PATH 覆盖；
无法读取 manager 环境则失败，不把操作者 `command -v` 当服务可执行性。
预检真实 import Pillow、读取各工具版本、读取模型、抽取最小 PDF embedded image、
渲染 PDF 并 OCR 现场生成的 `12345` 图像。初检在包构建和
`begin_install_transaction` 前；暂存安装包验证在事务前再次执行；安装后以实际
`SITE_ROOT` 和同一服务 Python 复验相同合同。原安装事务与回滚保持。

唯一补充授权是 `deploy/reinstall.sh` 既有 `INSTALL_ENV` 的三行变量转发，防止
dry-run 继承供应环境而真实 sudo/reinstall 丢失；未改 wrapper 其他语义。

激活沿用既有只读安装前缀。`runtime_identity.py` 只核对 Python 路径／版本及
pydantic/setuptools 版本，**不扫描也不覆盖这个 JSON**；本轮没有修改它。合同
绑定由现有 Operation resource/digest 以及安装前后实际预检承担。

## 工程检查

测试统一串行，无 xdist；环境 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS=''`。外层每 0.1 秒以 `ps` 汇总 pytest 及其
后代 RSS，达到 **8 GiB** 终止进程组。以下是采样进程树证据，不是 cgroup 强制
上限，也不是 live Codex／WSL 增量门。

初轮三个 owning 文件 **9 failed、120 passed，25.71s**，进程树峰值
**135,932 KiB**：新增预检以 `-m` 导入包初始化而先触及核心依赖，另有两条旧
静态断言／wrapper 测试配置错误。改为直接执行包内依赖文件并修正测试后，部署
聚焦 **45 passed，7.13s**，峰值 **113,340 KiB**。这些是 P4 新增问题与修复，
没有归为基线失败。

五类负测实际经过 `install_all` 中的依赖预检，只替换源／base/root 检查和后续
副作用入口：缺 OCR、缺模型、错误模型 hash、操作者能找到而服务 PATH 找不到
pdfinfo、操作者有 Pillow 而独立服务 Python 没有 Pillow。全部必须在构建／事务／
回滚标记出现之前失败。正例及模型变动反例使用 **模拟 OCR 可执行文件与明确假模型**，
Pillow／Poppler／PDF 调用是真实工具；不是模型正确性或生产可安装证明。

干净 wheel fixture 从候选 release 构建 core、curve_score、curve_figure_evidence、
tcad_artifact 和原有明确测试插件，全部非 editable 安装到新 venv；禁用
system_site_packages，离线复制当前依赖 RECORD 中的实际文件，清空 PYTHONPATH、
user site，并在仓外独立空 cwd 检查实际模块 `__file__` 和 entry points。首次
迁移碰到 cryptography 旧 `__pycache__` 不可读；改为直接解析 RECORD，先排除可
重建字节码后读取实际文件，没有改系统权限或隐藏运行依赖。

G4 首轮送审前完整命令 `python -m pytest -q --tb=line tests/operations tests/artifact_agent`：
**549 passed、9 failed，163.15s**；外层 **163.69s**，进程树峰值
**254,364 KiB**，8 GiB 止损未触发。最终运行包含全部部署检查、完整 figure
P2/P3/G3 回归、真实安装包资源摘要检查与 core／curve／figure／TCAD／全组合
wheel 矩阵。全组合仍 **48 个 Operation**，精确 plugin entry points 不含案例包；
安装路径检查和无 figure 的 curve smoke 均通过。仅变更实际供应模型 bytes/hash
时，request/materialize 两条 digest 变化，其余 Operation digest 不变。

九项失败与 P1/G1、P2/G2、P3/G3 已记录基线 node ID 与原因相同，未修改它们，
也未宣称完整目录全绿：

- `test_catalog_installed_entrypoint.py::test_clean_installed_pure_mcp_plugin_completes_a_hardened_run`；
- `test_l4_local_tcad.py::test_hardened_v1_rejects_tcad_native_shell_before_run_creation`；
- `test_l5_hardened_run_backend.py` 中 `test_hardened_transport_completes_the_same_run_without_task_science`、
  `test_hardened_rejects_missing_server_file_creation_before_run`、
  `test_hardened_transport_rejects_concurrent_owner_and_recovers_after_lease`、
  `test_hardened_exact_text_patch_is_real_for_a_shell_free_operation`、
  `test_hardened_server_write_rejects_parent_symlink_escape`、
  `test_hardened_stdio_process_recovers_the_exact_running_run`；
- `test_spec.py::test_operation_spec_is_the_frozen_declarative_contract`。

前八项为已知 `operation_runtime_unavailable`／旧拒绝码断言，最后一项是旧字段
列表遗漏 `complete_transform_family`。没有为消除失败改中央准入或添加 skip。

中间 installed 检查记录：依赖复制错误两次各 **22 errors**（11.58s／140,084 KiB；
12.07s／128,080 KiB），短追因 **1 error，11.47s／127,732 KiB**。
修复 RECORD 读取后 **21 passed、1 failed、1 deselected，53.50s／146,208 KiB**；
新增模型资源测试模拟新启动时遗漏清 catalog cache，修正仅测试代码后该项
**1 passed，40.01s／140,248 KiB**，随后以上最终完整目录复验包含它并通过。
这些运行都不是生产 OCR 证明。

最终测试所建四个生产 wheel 的 SHA-256（均为当前候选源码，不是提交发行）：

| wheel | SHA-256 |
|---|---|
| `scidiscovery-0.1.0-py3-none-any.whl` | `d650fa657e9efc7655840eed9ee0527b72449ad7ad6912394db4dd25ba6f9a00` |
| `scidiscovery_curve_score-0.2.1-py3-none-any.whl` | `dc3eadd8f430cc81aa6aa4d9dcbe3f83842f650e7bb40f8b33ad6c03a2581229` |
| `scidiscovery_curve_figure_evidence-0.1.0-py3-none-any.whl` | `34beec75502dcf119921295f45c5500479771d56a962695c17a193fd317f275b` |
| `tcad_artifact-0.1.0-py3-none-any.whl` | `6724f93e2d16f1d0cfb5bbcf0cb922e887b2bcbac026f0c3cd8e847dbcb99625` |

builder 仅补入本次 E5.4 活跃计划、已有审查与证据，原入口不变；没有增加
revision／git archive 模式。README 与 deploy README 双语只纠正已删除案例插件／
wrapper 的当前安装指引；INSTALL 保留原基础 apt／Conda 说明，追加 figure 的
离线供应合同与准确变量。历史 P0–P3 evidence/reviews 保留不改。

`git diff --check`、两个 shell 的 `bash -n`、变更安装文档的相对链接均通过。
四个实际 wheel 分别为 108／14／19／42 个文件，逐项检查路径和 Python 源码，
没有 `ingaas_fig4`、`ingaas.fig4`、`figure_geometry`、`SCORER_CONTRACT`。
生产 src／plugins 同样无上述案例残留；`src/`、curve_score、tcad_artifact
相对基线无改动。release 构建与 MANIFEST 校验包含在最终全目录通过的 owning
部署测试中；文档收口后仍使用原 builder 入口构建最终候选目录。

## 真实机器门

只读 `systemctl show scidiscovery-control.service` 确认既有服务 User/Group 为
`da`、实际 Python 为该用户 `miniconda3/bin/python3`、PYTHONPATH 为
`/opt/scidiscovery-m7/site`、后端为 Local，WorkingDirectory 为父目录中的
`workspace/ingaas_inalas_photodetector`。systemd 默认 PATH 为
`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`。

以同实际 uid **1000**／`da`、上述 Python、cwd 和 `env -i` 服务环境，逐个
`open('rb')` 后仅 `read(1)`；只报告成功／errno，没有输出文件内容：

| 范围 | 精确目标（相对外层 `git_release/scidiscovery-agent`；技能相对服务用户目录） | 结果 |
|---|---|---|
| checkout | `123/scidiscovery-e5.2/pyproject.toml` | READABLE，FAIL |
| 旧 workspace | `workspace/ingaas_inalas_photodetector/AGENTS.md` | READABLE，FAIL |
| 用户技能 | `.codex/skills/scientific-paper-evidence/SKILL.md` | READABLE，FAIL |
| 答案目录 | `workspace/ingaas_inalas_photodetector/targets/fig10a_sample2_140K_dark_iv_digitized.csv` | READABLE，FAIL |

宿主 systemd MainPID 不在当前进程命名空间中，不能冒称已进入宿主 service mount
namespace。此探针证明的是实际服务相同身份与当前 Local／Worker 可用环境仍可读；
强不可读声明没有证据，且四类均已有成功 open 反例。独立 cwd、清 PYTHONPATH、
Local、只读 mode 或“未观察访问”的日志均不能替代打开失败。**P4 强反作弊门
不通过，停止 G4/部署授权**，保留独立工程检查。不改权限／身份，不新增 hardened
后端或协议，不为此门伪造失败 errno。

真实服务 Python 的只读版本探针实测 Pillow **12.1.1**；`/usr/bin/pdfinfo`、
`/usr/bin/pdfimages`、`/usr/bin/pdftoppm` 各自实际 `-v` 为 **22.02.0**；
服务 PATH 中 `tesseract` 为 **null**。随后以真实 `da` 身份、该 Python、
`SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence` 和隔离绝对临时目录
运行原 `deploy/reinstall.sh --dry-run`，退出 **1**：
`figure dependency unavailable in service PATH: tesseract`，并明确
`figure dependency preflight failed before installation transaction`。
源／base Python 校验通过，预检目录仍为空，没有进入 build、事务切换或回滚。
这是实机缺 OCR 的有效拒绝证据，不是模拟正例；没有填写假版本／模型 hash。

上述“未供应”是首轮实机状态。有界复审时已供应 Tesseract **4.1.1**
及 `/usr/share/tesseract-ocr/4.00/tessdata/eng.traineddata`（SHA-256
`7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`）。独立复审者
以真实服务身份重跑 wrapper `--dry-run`，Pillow、Poppler、模型摘要、PDF
恢复／渲染与现场生成 `12345` 的 OCR 均通过；未进入安装事务。真实
安装后复验仍属 P5。没有真实论文、spawn、独立第二图、精度／覆盖验收或科学资格。候选
工作树构建不是精确 P4 提交发行；若之后获准提交，须在 clean HEAD 用原
`scripts/build_git_release.py --source <repo> --output <new-dir>` 入口重新验证。

## G4 首轮工程 FAIL 后的有界返工

首轮 G4 指出：`systemctl show-environment` 对特殊 PATH 可输出
`PATH=$'/g4/service tools:/usr/bin:/bin'`。直接使用 `${assignment#PATH=}`
会把 shell quoting 留在路径字符串中；即使部分目录被破坏，仍可能经保留的
`/usr/bin` 查到错误环境中的工具，不能证明服务实际可执行性。此为 P4 新增
工程阻断，不归入九项既有基线失败；首轮 FAIL 历史保留。

本次只在 `deploy/install.sh::service_python` 增加三行拒绝式检查，保留同一
manager/default PATH 选择入口。仅接受无需解引号／转义的绝对目录列表：每段以
`/` 开头且非空，段内字符限 `[A-Za-z0-9_./+-]`，段间以 `:` 分隔。遇 `$`、
引号、反斜杠、空白、控制字符、相对目录或空段即以
`unsafe systemd service PATH` 退出。没有 `eval`／`source` manager 输出，
没有增加解析器、PATH 配置层、依赖记录或中央规则。

在现有 `test_figure_dependency_failure_precedes_install_transaction` 中补十类
manager PATH 反例，包括上述精确 `$'...'` 形状、双引号、反斜杠、空格、tab、
相对段、连续／开头／结尾空段和空 PATH，均要求明确拒绝且 build／transaction／
rollback 三个副作用标记不存在。另以本机 `systemd-path search-binaries-default`
的普通 PATH 作为 manager 覆盖正例，真实执行服务 Python 并断言其 PATH 原样一致。
既有无 manager 覆盖的预检正例与五类依赖负例继续保留。这些 manager 输出为测试
模拟，不改实际 systemd 环境；该次返工时真实 OCR 仍未供应，随后的真实供应与预检见上节。

先运行新增测试观察 **10 failed、6 passed、40 deselected，2.46s**，进程树峰值
**92,544 KiB**；旧实现没有给出要求的 PATH 拒绝诊断。补三行校验后，执行
`python -m pytest -q --tb=line tests/artifact_agent/test_deploy_scripts.py`，
**56 passed，8.68s**；外层 **9.01s**，进程树峰值 **99,872 KiB**。
两次均沿用串行环境与每 0.1 秒进程树 RSS 采样，8 GiB 止损未触发；无 xdist。

本轮只改 installer 该函数、其部署测试、本文与计划状态；未改 G4 报告、插件、
其他生产代码或旧失败用例。`bash -n deploy/install.sh` 与 `git diff --check`
通过。没有重复完整两目录或 wheel 矩阵，上文 549/9 是首轮送审前记录；当前只
声明此有界部署回归通过。G4 独立复审确认 P4 工程 PASS；首轮强不可读门
FAIL 历史保留。该门与已冻结的 Local 软隔离目标冲突，本计划仅恢复原有
边界：发行、显式输入、提示、Schema 和工具清单不携带案例答案；如实记录宿主
文件仍可读，只声明“未提供且未观察访问”，`SEC-002` 继续为已知问题。
不新增沙箱、后端或权限协议。该最小验收更正已获独立复审 PASS，修正后的 G4
部署前置门 PASS，允许提交并进入 P5；尚未提交，未部署。
