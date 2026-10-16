# B3 / B1 独立审查（2026-10-16）

结论：**B3 PASS；B1 PASS**，均限下述精确局部修复。未发现阻断缺陷。本报告不评定仍在单独验证的 B2，不构成整个仓库、实时 Worker 或完整发布资格。

## 审查范围与身份

- 只读审查仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- 基线 / HEAD：`70afb76004b0532e5cd26f9bfd93529660785853`，分支 dev；工作树有其他已声明修改与未跟踪证据目录，均未由本审查者修改、提交或推送。
- B3 冻结三个文件：controller.py、native.py、test_native_cli.py。`git diff -- <这三个文件>` 与 `/tmp/scid-b3-fix-20261016.patch` 的 SHA256 一致：`1b11bf4d11fa7eb3357af9121869b955e6a47e8fde06bce5459050eab00a8ef4`。
- B1 冻结三个测试文件：test_artifact_capture.py、test_capture_path_views.py、test_ledger_capture.py。精确 diff 与 `/tmp/scid-b1-fix-20261016.patch` SHA256 一致：`48b9b6a3001d14bb85090f892ab211bf5f342c092046262a8be1f94c8f64f4a1`。
- 另审查执行者随后获授权的 test_worker_fragments.py 两行 fixture 修正：包装器接受 `comparison=False`，原样转发给 `original(role, protocol, comparison)`，其余 fixture 逻辑、断言未变。
- 应用 scid-cross-boundary-review / scid-change-scope-checks；检查内外 AGENTS。审查者未参与上述修复的实现。

## B3：PASS

### 路径与语义

沿真实路径追踪了 controller 保留任务恢复 → wait_native → runtime.node_state/process_matches → continuation.seal_or_repair → contracts.seal_result → worker_delivery.writers_stopped / checkpoint.capture，以及 runtime._run 的 outcome、checkpoint、最终时钟写入顺序。

- 修复点为 native.py:99–108 与 controller.py:389–392。首次等待与 retained-terminal 重连都覆盖 W screen，避免 outcome 已发布、原 runner 尚有最终写入时提前截取 delivery checkpoint。
- 等待只接受当前 `execution.record` 的 `runner-process.json`，用 `execution.identity(root, step)` 校验；首尝试绑定 job，后续尝试绑定 accepted intent。process_matches 同时检查 PID、boot_id、start_ticks、PGID、SID 及 task binding，拒绝僵尸、PID 重用和任务失配。
- 无匹配 writer 的 screen 仍交给现有 sealer；这并非自动接受终态。sealer 继续验证 usage、returncode、stop_reason、raw hash、checkpoint 原件与 delivery，writers_stopped 继续拒绝仍活跃的 native writer。
- fragments=True 时原分支的等待及 checkpoint 缺失错误保持；已有 checkpoint / sealed 状态不新增等待。fragment continuation 仍重新获取 current record。未知执行保持原错误与不重投边界。
- 此变更不调用 start/accept_node，不新建 intent、不增加 repair 次数或预算。重连延续原 recover_original 时钟；新增真实 runner 测试核对三个 intent、三个 usage、315 observed tokens、无 continuations 与重复运行幂等。

### 验证证据

观察执行者持久化原始证据，并独立核对源码与测试断言：

1. `/tmp/scid-b3-before-20261016`：两个新真实 subprocess 回归（首次运行 / 重连）修前均以 seal_pending 失败，1.99s。
2. `/tmp/scid-b3-after-20261016`：native_cli、runtime、worker_delivery、worker_fragments 定向批次，50 passed / 8 failed / 5 deselected，监督耗时 22.718s、RSS 176,300,032、cleanup true。八项失败均发生于 H science_view 的旧 fixture 二参包装器，尚未到达此次等待路径；并叠加 controller 原有异常处理 UnboundLocalError。因此该批次本身不能作为分片路径通过的证据。
3. `/tmp/scid-b3-fragment-forward-20261016`：上述透明三参透传修正后，完整 test_worker_fragments.py **20 passed**（pytest 24.37s，监督 24.897s、RSS 178,655,232、cleanup true）。实际运行了先前被挡的 same_session/new_context、正常分片不耗 repair 次数、投资边界、writer 停止后重查 review、缺失输出修复不重放、unknown usage 不旋转不重投、已知失败恢复同一 thread 场景。八项覆盖缺口据此关闭，并非因其属于基线失败而豁免。
4. 审查者独立补测 `/tmp/test_scid_b3_independent_wait_20261016.py`，以仓库 `serial_lock` + `run_one` 单独监督执行：**9 passed**（pytest 0.21s、监督 0.356s、RSS 39,231,488、cleanup true），证据 `/tmp/scid-b3-independent-wait-20261016/{pytest.log,resource.json}`。覆盖当前 continuation 身份先等后 seal；task/start_ticks/boot_id 失配不等候；fragment 缺 checkpoint 保持 unavailable；同 writer 发布 checkpoint 后 seal；已有 seal/checkpoint 委托；unknown 不 replacement。禁止 start / accept_node 的守卫未触发。

独立补测是控制边界单测；真实进程竞态证据来自第 1–2 项。已通过的 runtime/delivery 测试另覆盖 controller 被杀重连、runner 丢失、身份失配、未知提交不重放、预算拒绝、进程清理以及禁止 live writer snapshot。

### 资格限制

没有运行全套 pytest、真实模型或实时外部执行。runner 终态后的 finalization 若自身长期挂起，等待仍依赖同一 writer 退出 / 发布 checkpoint；此补丁未建立新的 finalization 超时或授权。这不允许重试、加预算或把未知作成功。现有聚焦证据足以评定本次 race 修复，不能外推整个研究循环的完整资格。

## B1：PASS

- 六处改动仅把已知合成危险字符串拆成常量字符串/bytes 相加。断言、参数化数目、fixture 分支、实际捕获 guard 和发布 scanner 规则没有删除或放宽。
- 独立 AST 等价检查以基线原文和当前三文件为输入，求值常量相加后整个 AST 完全一致。test_ledger_capture.py 内嵌 installed_probe 脚本单独解析并作同样归一化，证明其中构造出的 JSONL 原始 bytes 也一致。结果：`/tmp/scid-b1-independent-equivalence-20261016.json`。
- 独立比较 build_git_release.py 的 `_scan_release`、FORBIDDEN_TEXT、FORBIDDEN_PATTERNS、BUNDLED_BINARY_REFERENCES：AST 与基线完全一致。B2 的清单改动不被当作 scanner 放宽。
- 观察 `/tmp/scid-b1-tests-20261016`：目标 secret/private-key/binary/capture-gap 测试、完整 ledger_capture 与既有 scanner 注入负控 **67 passed / 1 deselected**；pytest 47.16s、监督 47.614s、RSS 155,594,752、cleanup true。scanner 注入仍拒绝实际 home path、私网地址与 private key 文本。
- 观察 `/tmp/scid-b1-build-20261016`：实际 builder 退出 0，生成 manifest 与 archive，820 个 source files，监督 2.14s、RSS 33,669,120、cleanup true。
- 独立核对该 release 目录和 tar.gz 中三个 B1 文件均与冻结修复一致；manifest 存在。archive SHA256：`f5eb07529f15ad02b1db905b53fdcd61bd8b56bfb315f100d4aff4c46c67e4ab`；核对结果 `/tmp/scid-b1-independent-release-20261016.json`。
- installed_probe 这一个测试在 source lane 被有意 deselect，没有冒充安装执行成功；其本次改动的行为等价性由嵌套 AST 检查证明。当前 B1 结论为 scanner 可构建且负例强度保持，不包含 B2 依赖完备性的结论。

## 收口

审查前后冻结 B3/B1 diff 指纹均一致，`git diff --check` 通过。补测已释放 serial_lock 并通知执行者。无需因本报告新增阻断；后续最终集成仍应由执行者按精确合并 diff 进行既定门禁。
