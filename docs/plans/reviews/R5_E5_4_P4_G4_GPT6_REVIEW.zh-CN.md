P4工程实现：PASS
G4部署门：PASS

当前结论见末节“既有软隔离架构口径的独立文档复审”。PASS 只指 P4 工程及进入 P5 的部署前置门。下文保留首轮 **P4工程实现 FAIL／G4部署门 FAIL**、工程修复后按旧强门仍判 FAIL 的完整历史；真实 OCR 供应和适用验收口径的变化均另列，不把旧失败改写成当时已通过。

日期：2026-09-06。这是独立 GPT-6 G4 工程审查；只有下述 G4-1 属于当前 P4 代码返工。真实 OCR 未供应、四类文件可读是独立环境／策略阻断，不据此要求重写 P4 算法或增加隔离后端。当前不授权提交后直接进入 P5 部署。

## 精确审查对象

仓库 `123/scidiscovery-e5.2`，HEAD／比较基线为 `4a6ed35ce00442faf3187040f7a62ad26338f854`。审查全部 17 个 tracked 变更及两个 untracked 候选文件，不含本报告。完整阅读已审 E5.4 计划，重点核对 P4、6.1–6.3、7；完整阅读 P3 evidence、G3 首轮及有界复审、P4 evidence 和 33 项约束，并核对 G1 已独立复现的九项基线失败。使用最小代码审查、跨边界审查与变更范围检查技能；没有调用科研控制面或 Worker，没有修改实现、测试、计划或 evidence，没有提交、部署、启停服务或改变权限。

| 检查点 | SHA-256 |
|---|---|
| `git diff --binary 4a6ed35ce00442faf3187040f7a62ad26338f854`，tracked 差异 | `d704a13383c754de1678aa9607f4b18c6f8e2c8f61e906fa4085a5dec218a3ff` |
| 新增 `figure_dependencies.py` | `ed4a8c80a8f4eeef4a1430eba53a2c395ac8dfbc833fbbb9f3f7b42a2c35bcbe` |
| 新增 P4 evidence | `1f0600f46c2c11ed82ec3baefe99d6bc9f1b18fa52dcff2e4c8bf1e8e901e76d` |
| `deploy/install.sh` | `aaf8f6d9055947b6cbb9b7606574fe88470d8b5ad21c6317c78f17e371750b6c` |
| E5.4 计划 | `9849694932e44b6ea8224c3b4eda28f5596877fb72c4f7a6bff0fa0a315a8025` |

审查定稿前的候选已将 manager 环境查询失败改成显式 `die`。本报告只判断上表版本，不把此前静默吞错的瞬时版本当作最终代码缺陷。下述 G4-1 是查询成功后处理输出格式的另一问题。

## G4-1：systemd 转义后的 PATH 被当成实际 PATH 使用

严重性：P2。位置：[deploy/install.sh:249](../../../deploy/install.sh#L249) 的 `service_python()` 循环。

`systemctl show-environment` 输出适合 shell 读取的赋值文本，并不保证等号后都是原始环境值。本机 systemctl 249 的随附手册 `/usr/share/man/man1/systemctl.1.gz` 在 `show-environment` 条目明确规定：值有空白或 shell 特殊字符时，使用 `VARIABLE=$'value'` 的 dollar-single-quote escaping。当前代码仅执行 `${assignment#PATH=}`，没有解码，也没有拒绝这种格式，然后通过 `env -i "PATH=$service_path"` 传入 Python。

独立反例不修改 system manager，也不创建或运行替代生产服务。只在加载真实安装脚本的子 shell 中替换只读查询函数，让它返回上述文档规定的序列化形状，其余 `service_python` 原样执行：

```bash
systemctl() { printf '%s\n' "PATH=\$'/g4/service tools:/usr/bin:/bin'"; }
service_python '' -c 'import json,os; print(json.dumps({"PATH":os.environ["PATH"]}))'
```

结果退出 **0**，实际子进程输出：

```json
{"PATH": "$'/g4/service tools:/usr/bin:/bin'"}
```

正确环境值应为 `/g4/service tools:/usr/bin:/bin`；当前首、尾目录被字面转义字符破坏，中间目录仍可用。因此这不只是一个必然失败的错误提示问题：服务首选目录可能被跳过，其他目录中的工具仍能让安装预检通过。初检、暂存复验和安装后复验共用此 helper，会重复同一个错误，不能互相纠正。

进一步复用刚完成 owning 测试生成的明确假 OCR／假模型供应，将其 `figure-bin` 放在这个 PATH 的中间项，实际执行 `validate_figure_dependencies`。它执行真实 Pillow、Poppler、PDF 恢复／渲染和测试 OCR 后退出 **0**，输出 `figure dependency preflight: pass` 与 `Verified figure dependencies:`。本反例是测试 OCR，不是生产 OCR；它证明错误 PATH 不会可靠地失败关闭。该串行探针耗时 **0.21s**、采样进程树峰值 **39,944 KiB**，8 GiB 止损未触发。

最小修复只限 P4：在这个 helper 中正确处理该已知序列化，或对尚不能安全处理的转义 PATH 明确拒绝，并保证在 build／transaction 前失败。无需支持任意环境表达式；不得 `eval` 整块 manager 环境，不新增环境管理系统、中央配置或服务协议。补一个采用真实 `PATH=$'…'` 输出格式的 owning 负测／正测，验证子进程获得精确 PATH，或明确拒绝且 build、transaction、rollback 均未进入。复跑相关部署聚焦即可；此项不要求 P5 或全套重型回归。

## 已通过的其余 P4 检查

1. **依赖记录与领域所有权。** 新模块只负责工具身份、包内记录读取和离线最小调用；安装把唯一记录写到暂存包 `curve_figure_evidence/figure_dependencies.json`。源码和普通 wheel 无记录时明确 `unavailable`；运行没有读取三个安装供应变量。verified 记录约束全部四个绝对可执行路径、Pillow 12.1.1、Poppler 22.02.0、精确 Tesseract 版本、eng 模型路径及 64 位小写 hash；错误形状失败，不降级成可用。另做 13 个独立内存负例验证版本、模型、路径、语言、adapter、status 与额外字段拒绝，以及安装环境变量不能改变未供应合同。
2. **原资源边和实际 provenance。** JSON 规范内容直接进入 `DETECTOR_CONTRACT`，只有原 request 输出 context validator 和 materialize transform 引用；未挂 worker_tool、未新增 resource 假入口、未修改编译器。实际 installed JSON 变更回归证明仅 request/materialize 两条 digest 改变，所有其他 Operation 不变，完整目录仍为 48 条。每次重放检查实际 Pillow、PDF 工具版本和 OCR 模型字节；OCR 返回的实际版本与已核对模型摘要进入 token／检测 provenance。PDF 两个 subprocess helper 和 OCR 均使用 verified 合同绝对路径。未供应且无 OCR 时保持显式未决；未绑定 OCR、版本／hash 不符或程序调用故障抛错，不伪装科学未决。
3. **固定 OCR 调用。** `--tessdata-dir`、`-l eng`、`--psm 11`、`-c tessedit_create_tsv=1` 由代码固定，没有额外未绑定 `configs/tsv` 输入，没有运行下载、调用者参数入口或循环依赖。普通未供应分支保留受限行为，并不能通过 figure 安装预检。
4. **事务顺序与服务身份。** 初检在 `install_packages` 之前；暂存记录写入后的复验仍在 `begin_install_transaction` 之前；安装后复验用相同服务身份、`SCID_PYTHON` 和实际 `SITE_ROOT`。原 rollback／activation 顺序未改变。五类 owning 负测均实经 `install_all` 的依赖预检，并断言未进入 build、transaction、rollback。另独立令 manager 查询返回 37，最终退出 1，两个明确错误为 `cannot inspect systemd service environment` 和 `before installation transaction`，上述三个后续标记均未出现。
5. **环境清理与传参。** 对未转义 PATH，独立实测 `env -i` 清除操作者专用变量，服务 HOME、指定 PYTHONPATH、manager PATH 与禁用 user site 均正确。wrapper 的三个新增变量只是带引号的数组参数；JSON 经标准序列化、命令替换捕获 stdout、按单个 argv 交给 Python 写入，未重新解释成 shell 代码。新模型路径中的特殊字符不会因此执行 shell；manager 输出转义不等于原值的问题单独列为 G4-1。
6. **文件边界。** 初检对可执行位置 `resolve(strict=True)`，记录最终绝对路径；模型按实际文件字节复核摘要，普通缺失或改动拒绝。暂存安装沿用 root 创建的前缀，激活后执行原有 `chmod -R a-w`，没有引入可由服务写入的第二份安装记录。`runtime_identity.py` 未改变，也不覆盖 JSON。外部模型允许符号链接，且没有证明 hash 检查到第三方加载间的外部文件不可替换；不能把安装前缀只读解释成外部供应模型防篡改或强隔离认证。这仍受当前可信离线供应前提限制，不借本次 P4 新建权限系统。
7. **干净 wheel 与依赖复制。** 新 venv 禁 system site，仓外 cwd、空 PYTHONPATH、禁 user site、非 editable；core、curve、figure、TCAD 和全组合的实际 entry points／模块路径验证通过。独立逐项核对 14 个离线依赖的 RECORD：**598** 个实际文件在 venv 中存在且 SHA-256 与源一致，排除 **387** 个可重建 bytecode，唯一前缀外项目是非运行依赖的 `../../../bin/jsonschema` CLI，缺失源文件 **0**。实际 installed `pip check` 退出 0，`No broken requirements found`。没有漏掉 cryptography／cffi 的运行文件。
8. **模型 digest 测试隔离。** 测试在实际 installed package 写入唯一 JSON，reload 依赖和 detector 并清 catalog cache，用于模拟重新启动编译；没有在生产加入热重载或第二份缓存。`finally` 删除测试 JSON／模型，子进程随即结束。独立确认 session venv 与 cwd 中这两个文件均不存在，后续矩阵没有继承供应状态。这是合理的启动模型测试，不能冒称真正生产服务重启。
9. **发行与文档范围。** 原 builder 只补当前 E5.4 计划、证据与审查清单，没有新 CLI；owning release／MANIFEST 回归通过。四个生产 wheel 和生产 src／plugins 没有案例包、geometry、旧 scorer 或固定论文 hash；唯一静态 64 位 hash 命中是 TCAD 已有手册摘要。README、INSTALL、deploy README 双语对应，保留一般 apt／Conda 安装路径，准确区分 runtime identity 与 detector JSON；没有声称真实 OCR、强隔离或 E5.4 最终验收已经通过。

`src/`、curve_score、tcad_artifact、中央 schema／状态／注册、Run／审批／资格／编译机制均没有 P4 修改。33 项约束用于核查 AUTH、IMM、DET、PLG、SEC、RES、MIG 等相关边界，没有将整个注册表重新标成 conformant。

## 独立执行证据

统一串行、无 xdist，设置 `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PYTEST_ADDOPTS='' PYTHONDONTWRITEBYTECODE=1`。主回归的外层每 0.1 秒读取 `ps -e -o pid=,ppid=,rss=`，递归汇总 pytest 及其全部后代 RSS，达到 8 GiB 即终止进程组。

```sh
python -m pytest -q -p no:cacheprovider --tb=line \
  tests/artifact_agent/test_deploy_scripts.py \
  tests/operations/test_figure_automatic_detection.py \
  tests/operations/test_figure_semantic_compilation.py \
  tests/operations/test_catalog_installed_entrypoint.py::test_installed_supply_bytes_change_only_existing_figure_resource_consumers \
  tests/operations/test_catalog_installed_entrypoint.py::test_clean_domain_wheel_matrix_has_exact_plugin_ownership \
  tests/operations/test_catalog_installed_entrypoint.py::test_installed_case_distribution_and_import_are_absent \
  tests/operations/test_catalog_installed_entrypoint.py::test_curve_wheel_scores_without_installing_figure \
  tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_domain_tools_execute_the_packaged_implementations
```

结果 **111 passed in 66.24s**，退出 0；外层 **66.92s**，采样进程树峰值 **202,280 KiB**，止损未触发。不是 cgroup 强制上限，也不是 live Codex／WSL 增量门。其后只有上述有界独立反例、只读机器／文件／依赖审计；没有并发测试、真实科学 Agent 或 solver。`git diff --check`、两个 shell 的 `bash -n` 均通过。

本次构建出的实际 wheel 如下；它们绑定当前候选，不是精确 P4 提交后的发行凭证，也不要求与前次非确定时间戳的构建 hash 相同。

| wheel | 文件数 | SHA-256 |
|---|---:|---|
| core 0.1.0 | 108 | `aecd019eb63dedbbbfcd4e6701c2b82b39abd60a93aea827b609999eeed8eb8a` |
| curve_score 0.2.1 | 14 | `e6eb37d6a635a272930a988be7dc6cede4bd3e1163f2f64cffbe8ada06c7fbbc` |
| curve_figure_evidence 0.1.0 | 19 | `54b92aec6dbbbb203665126276e48ce627e9a5f3fdd5ac9624b79e33cbbb8cee` |
| tcad_artifact 0.1.0 | 42 | `9a16e8fb0713f9bce204e57239260e60910084f7f264fe2eb7d8d889c7577824` |

P4 evidence 的完整两目录 **549 passed、9 failed**作为已阅读的完整回归证据，不冒充本次独立执行。九项 node ID 与 G1 在 Git blob 核验基线快照上独立复跑的九项一致，G2／G3 也保留相同原因：installed hardened 一项、L4 一项、L5 六项为既有 admission／旧拒绝码断言，`test_spec` 一项遗漏已有 `complete_transform_family`。本次未改相关生产实现或对应失败函数，未新增 skip／xfail，不归责 P4，也不称全目录全绿。没有必要为 G4 重跑该重型基线或完整全套。

## G4 环境／策略阻断

独立只读查询实际 `scidiscovery-control.service`：User／Group 为 `da`，Python 为该用户 `miniconda3/bin/python3`，PYTHONPATH 为 `/opt/scidiscovery-m7/site`，Local backend，WorkingDirectory 为既有项目 workspace。systemd 默认 PATH 不含 snap；**manager 实际 PATH 额外含 `/snap/bin`**，helper 在此次未转义值下正确采用完整 manager PATH。实际服务 Python 为 Pillow **12.1.1**，三个 Poppler 工具实际版本均 **22.02.0**，`shutil.which('tesseract')` 为 **null**。

以相同 uid／gid **1000**、服务 Python、cwd 和清理后的服务环境，四个目标只做 `open('rb')`／`read(1)`，不输出或消费文件内容：

| 类别 | 精确目标 | 结果 |
|---|---|---|
| checkout | `123/scidiscovery-e5.2/pyproject.toml` | READABLE |
| 旧 workspace | `workspace/ingaas_inalas_photodetector/AGENTS.md` | READABLE |
| 用户技能，相对服务用户目录 | `.codex/skills/scientific-paper-evidence/SKILL.md` | READABLE |
| 答案，相对外层仓库 | `workspace/ingaas_inalas_photodetector/targets/fig10a_sample2_140K_dark_iv_digitized.csv` | READABLE |

宿主 MainPID 不在当前进程命名空间中，未进入宿主 service mount namespace；以上证明实际相同身份与当前 Local 原生环境存在成功打开反例，不能声称强不可读。已审计划 6.3 要求实际打开失败，四项均不满足；独立 cwd、只读 mode、清 PYTHONPATH 或访问日志不能代替。

随后在独立绝对临时目录中，以实际服务身份／Python、Local、`SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence` 运行原 `deploy/reinstall.sh --dry-run`。源码和 base Python 校验通过，wrapper 退出 **1**，原因为 `figure dependency unavailable in service PATH: tesseract`，明确 `figure dependency preflight failed before installation transaction`。结束后临时根仅有预建 workspace／launch 两个空目录，没有 install／state／backup、build 或事务／回滚。本机拒绝是正确行为，不是代码返工事项。

因此，G4-1 修复只能使工程结论有资格复审。即使工程复审 PASS，也不得 P4 提交后直接进行 P5 部署：需用户明确决定如何处理当前 SEC-002 可信软隔离与 E5.4 已审强不可读验收门之间的冲突，并按该决定明确更新／复审适用计划；同时供应真实 Tesseract、真实 eng 模型及精确版本／hash，完成服务环境的真实正向预检。不能由实现者擅自降级门槛、改权限、切换后端或新增协议来制造通过。真实安装后复验、精确提交发行、两张真实图、真实 spawn、独立精度／覆盖与科学资格均未完成，本报告不提前要求以 P5 工作掩盖 P4 的这个最小代码修复。

## 有界返工独立复审

最终工程结论：**P4 PASS**。最终部署结论：**G4 FAIL**。日期：2026-09-06。G4-1 已关闭，未发现新的 P4 工程阻断；原工程 FAIL 和实际反例保留。真实 OCR 供应／真实服务身份的安装前 exercise 已独立通过；强读取隔离仍不满足已审计划，当前不得 P4 提交后直接进入 P5 部署。

### 精确返工对象

HEAD 仍为 `4a6ed35ce00442faf3187040f7a62ad26338f854`。相对首轮仅在 `service_python` 增加三行拒绝式 PATH 校验，更新 owning 部署测试与相应 evidence。figure 依赖、detector、installed fixture、digest 测试及其他生产代码未因本项返工改变。本次只追加审查记录并更新报告顶部当前结论，没有修改被审文件。

| 复审检查点 | SHA-256 |
|---|---|
| 当前 tracked binary diff，相对上述 HEAD | `75fe24e720519f982fa45900499135498d521278418f4bf19a307db4b86e80d7` |
| `deploy/install.sh` | `67b8cf3b39562e294a376d4908d7829f68f31b81ec1a0a843e14e038b270bf10` |
| `tests/artifact_agent/test_deploy_scripts.py` | `22893c27e0d6c9087eedc019c29cb7b45dd5e928fd984b7418311aceec2b30b0` |
| P4 evidence | `b249278636ba5c7fe49f2b4a648c1d34a7495082705530c4819688380ac7ac7e` |

### G4-1 关闭依据

`service_python` 只接受不需要解码的绝对 PATH 段列表，正则为 `^/[A-Za-z0-9_./+-]*(:/[A-Za-z0-9_./+-]*)*$`。遇转义、引号、空白、控制字符、相对段或空段立即报 `unsafe systemd service PATH`；没有 `eval`、环境解析框架、第二套 PATH 输入或中央修改。使用不支持的路径名会得到明确拒绝，这是本次有界修复的公开限制；它不再悄悄改变路径含义。

独立重放首轮原始 `PATH=$'/g4/service tools:/usr/bin:/bin'` 反例，经真实 `install_all` 路径得到退出 **1**，依次输出 `unsafe systemd service PATH` 与 `figure dependency preflight failed before installation transaction`；build、transaction、rollback 三个替代副作用标记均未出现。另重复 manager 查询返回 37 的反例，仍明确拒绝且三个标记均未出现。普通 manager PATH 的原样传递正例通过。

新增十类 owning manager PATH 反例和原五类依赖负测均保持真实预检入口；没有降低断言、增加 skip 或放宽前置事务边界。串行执行：

```sh
python -m pytest -q -p no:cacheprovider --tb=line \
  tests/artifact_agent/test_deploy_scripts.py
```

结果 **56 passed in 8.03s**，退出 0；外层 **8.37s**，整棵测试进程树采样峰值 **100,056 KiB**。沿用线程环境和每 0.1 秒 RSS 监测、8 GiB 止损，无 xdist，未触及阈值。返工只涉及该 helper，不重复完整两目录和 wheel 矩阵；首轮 111 项独立工程证据与九项既有失败归属继续保留。`bash -n` 与 `git diff --check` 通过。

### 真实 OCR 供应已独立通过安装前预检

复审时系统已有真实 `/usr/bin/tesseract` **4.1.1**，模型为 `/usr/share/tesseract-ocr/4.00/tessdata/eng.traineddata`，SHA-256 为 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`。这次供应由外部完成，审查者没有安装、改写或复制模型。首轮和返工 evidence 中“未供应”的表述记录的是此前状态；当前状态以本节实际执行为准。

独立以实际 `da` 服务身份、`/home/da/miniconda3/bin/python3`、Local、全部三个领域插件及上述精确供应变量，重新运行原 `deploy/reinstall.sh --dry-run`，所有安装／状态／workspace／launch 路径指向独立临时目录。它执行真实 Pillow import、四个工具版本调用、实际模型 hash、最小 PDF embedded-image extraction／render 和现场生成 `12345` 图像的真实 Tesseract 识别，随后完成服务预览，退出 **0**。

输出中 verified 合同为 Pillow **12.1.1**、Poppler **22.02.0**、Tesseract **4.1.1** 和上述真实模型摘要；四个 executable 均为 `/usr/bin/` 下对应绝对路径。实际预检身份 uid **1000**，manager PATH 含 `/snap/bin`。耗时 **0.95s**，采样进程树峰值 **48,912 KiB**，8 GiB 止损未触发。结束后临时根只有预建的 workspace／launch，没有安装物、状态或 backup；没有进入真实安装事务。

预览的 systemd 检查还输出两个外部 unit 提示：`netplan-ovs-cleanup.service` 在当前命名空间不可读，以及现有 `snapd.service` 的 `RestartMode` 不被此 systemd 识别。命令最终 `deployment preview: pass`，没有把这些提示隐藏成无 stderr，也没有改相关服务。

这个通过关闭了“当前机器缺 OCR／模型”这一安装前环境阻断，不等于新包已安装、安装后复验已通过或真实论文自动提取已成功。本轮没有把供应记录写入当前生产 `site`，也没有重启服务。

### 仍然失败的部署门

真实 OCR 预检之后，再以相同服务 Python、uid／gid **1000**、既有项目 cwd 和实际 manager PATH 重复四个原目标的 `open('rb')`／`read(1)`：checkout、旧 workspace、用户技能、答案文件 **仍全部 READABLE**。没有读取其正文。宿主 service MainPID 仍不在当前进程命名空间，未宣称进入其 mount namespace；当前 Local 身份的成功打开反例依然成立。

按已审 E5.4 计划 P4／6.3／7，这足以使 **G4 部署门继续 FAIL**。这一剩余问题是环境／验收策略冲突，当前没有由它导出的 P4 代码返工：需要用户明确决定是否继续要求强不可读，或改变为诚实的可信 Local 软隔离验收，并对适用计划作明确更新／复审；审查者和实现者不得擅自降级门、改权限或新增后端。真实 OCR 已供应，无需继续要求用户重复供应；但在隔离策略未得到明确处理前，工程 PASS 不授权 P4 提交后直接 P5 部署。精确提交发行、真实安装后复验、两张真实论文图／spawn／独立精度覆盖及科学资格仍未获得本报告授权或验收。

## 既有软隔离架构口径的独立文档复审

结论：**文档更正 PASS；P4 工程实现 PASS；修正后的 G4 部署前置门 PASS**。日期：2026-09-06。可以提交 P4 并进入 P5 的精确提交发行、既有事务安装及安装后验证；本结论不表示安装已经发生、P5／E5.4 已通过或任何科学证据已获资格。上节按旧 E5.4 强不可读条款判 FAIL 的历史保留。

### 规范所有权与更正依据

本次使用决策文档维护技能，完整阅读总章、R5-M 软隔离决策及 E5.4 受影响段落，并核对 33 项约束、当前安装教程和此前独立工程证据。相关文档的职责如下：

| 文档 | 权威范围与本次处置 |
|---|---|
| [设计总章第 5 节](../../architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md#5-通信与最小授权)、[当前架构](../../ARCHITECTURE.zh-CN.md) | 默认 Local 可信软隔离的现行规范；保持原样 |
| [R5-M 第 1.1 节](../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md#11-当前阶段的软隔离决策) | 已完成决策，明确取消当前阶段的宿主不可见、逐次读取授权和强沙箱完成门；保持原样 |
| [33 项约束](../../architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml) | `SEC-002 known_issue` 及其余边界；33 项和状态均未修改 |
| E5.4 计划 P4、6.3、6.4、8 | 恢复上述默认隔离边界，保留图证据防污染与科学验收要求 |
| 双语 INSTALL | 同步当前规范的安装指引；不再继续要求旧强门 |
| 本报告及 P4 evidence 的早期探针 | 精确历史记录，保留 PATH 缺陷、当时 OCR 缺失及四项 READABLE／旧门 FAIL |

总章第 5 节明确“默认可信本地路径采用软隔离”，并规定真正强隔离只在出现真实消费者后另行验证，不能增加默认路径成本。R5-M 第 1.1 节明确“不把宿主路径不可见、跨 Run 技术隔离或强沙箱作为 R5-M 完成条件”；`SEC-002` 的既有 evidence 同样写明强隔离不再是当前原型完成门。只读 Git 核对证明这些内容已在 HEAD 存在，本次未修改；最近涉及该组文件的提交是此前 M7 快照 `a6742b7bfd3113f68f7c9fd2705daa1403027aa9`。这不是为当前可读反例补造的新架构决策。

因此，删除 E5.4 另加的 OS 打开失败部署条件，是恢复既有默认范围和用户既定软隔离要求。它确实改变了 E5.4 这一条局部验收条件，故必须明确记录并独立复审；不能称旧强门实际上通过，也不能借此宣称对恶意 Worker 或多租户具有技术隔离。本次旧门失败、四类可读事实及 `SEC-002 known_issue` 均保留，满足这个要求。

初始文档候选 `3fd0fa31…` 仍在双语 INSTALL 保留“可读即停止部署”，且新 6.3 对整个发行目录的措辞与历史审计定位符冲突。本审查指出后，只同步了两段教程、6.3 的运行资源边界以及 6.4 的目录措辞；没有要求改生产、权限或测试。最终文本已消除这两处当前文档冲突。

### 防污染与科学门仍然成立

修正后的 6.3 明确禁止生产代码、包内运行资源、默认配置和 Worker 显式输入／提示／Schema／工具清单携带案例 workspace、旧 geometry、历史 CSV、目标指标文件或作为答案发现入口的路径。只提供原始 PDF 和科学问题；自动 Operation 不绑定人工几何技能。发行中的历史计划／审计定位符只作追溯，不是运行资源，也不能被运行端消费为发现或提示入口。中英文 INSTALL 的含义与之对应，没有把“历史可保留”变成隐式答案配置许可。

6.4 将含混的“可读目录”限定为运行端提供／物化目录，继续禁止将离线几何、阈值或真值交给 detector／Agent／生产配置。它没有删除第二图由独立审查者选择、算法和阈值先冻结、两图运行前预注册检查点／有限误差／不确定性上限／覆盖门／最大缺口的条件。未决和遗漏仍计入未覆盖；扩大误差包络和只保留容易局部的两个验收器负例仍必需。算法改变后需换未看过的盲图、真实不可识别轴负例、真实 spawn／完整族／独立 audit 等要求也保留。

P5 第 1／7 步继续审查实际显式输入、assignment、Schema、工具参数、sealed intent、materialize provenance 和可用访问日志；只能按实际观察范围报告“未提供／未观察访问”，不能从日志推出 OS 不可读。若实际观察到读取或使用历史答案，仍违反其未提供答案的验收条件；软隔离不是允许污染后照样通过的例外。Artifact 封存、完整父链、独立审查、人工审批及副作用授权没有改变，旧证据也不会自动晋级。

这些边界足以维持当前可信 Local 原型所承诺的发行和显式上下文控制，不构成对宿主任意文件访问的技术保证。此前独立 wheel 扫描、模块前缀、精确 entry points、48 条目录、真实资源 digest 和 Worker 合同检查仍是 P4 的相应证据；P5 实际新启动的 assignment／访问／科学产出还须按计划验证，不能提前记为通过。

### 精确文档对象与最终范围

HEAD 仍为 `4a6ed35ce00442faf3187040f7a62ad26338f854`。最终对象如下；与上一工程复审相比只有文档口径／状态同步，关键生产与测试文件的 SHA-256 均保持上一节数值。

| 当前检查点 | SHA-256 |
|---|---|
| tracked binary diff，相对上述 HEAD | `d0aa3d66f84221863d80e3cab4ed43ef99e31d17b144fedb46e2ff814c1a4823` |
| E5.4 计划 | `3d8af3042ca2f23dc7ab68a3f34c26f7adb6d1378e54e214e60cd6019c4de9d4` |
| P4 evidence | `3ac231e3155fdb53ae7b827baf1f78072a639b3218444584743e513e1e5daaba` |
| `docs/INSTALL.md` | `de41af308f2597bce7686d81bcb6f1aeca2706871c47a127d72290da67d5449a` |
| `docs/INSTALL.zh-CN.md` | `2a245960a877ebb39f34b586b7f0b3c83190d34ab0461c875e498e559aad55fc` |

本次只做精确文档差异、规范所有权、33 项与中英文含义核对、相关引用存在性及 `git diff --check`，未重复 pytest、wheel、OCR、打开探针或服务调用。依据仍是此前独立完成的 **111 项工程聚焦、56 项部署复审、真实服务身份的三插件 wrapper／OCR／模型／PDF 预检**；九项既有基线失败和完整目录非全绿事实不变，未利用文档修改抹去它们。

当前 P4 工程阻断为零；旧强门的适用冲突已通过这次文档更正及独立复审处理，真实 OCR 安装前条件也已有实际证据，因此 **G4 部署前置门 PASS**。阶段上允许提交当前 P4、从精确提交重建发行并按原事务进入 P5 安装；安装前旧合同 Run 检查、实际安装后同服务 Python／JSON／catalog／profile／工具复验、失败回滚仍按原计划执行。P5 真实两图、真实 Agent、盲测精度覆盖和后续科学资格仍未通过。此为工程阶段审查结论，不替代任何科研 Operation 的 loopback 人工决定，也不授权额外 solver 副作用。本审查者只更新本报告，没有提交、部署、启停服务、修改计划／evidence／实现或改变权限。
