# Fig.4 本轮 P2 收尾独立 SOL 复审

日期：2026-09-22

结论：**PASS（仅限 P2 收尾的三个测试文件与本次证据）**。

P1：无。P2：无新增。本结论关闭原独立验收的 P2-1 测试债务，并确认 P2-2 已以可复核原始记录勘误；不重审原冻结 18 文件，不追认原实施者自报的 88 项，也不代表部署态或 Fig.4 科学流程通过。

## 1. 范围与冻结一致性

本次只复审：

- `tests/operations/test_analysis_tool_installed.py`
- `tests/operations/test_tcad_result_analysis.py`
- `tests/operations/test_tcad_scientific_skeleton.py`
- `docs/plans/evidence/fig4-round-remediation-20260921/p2-closeout/` 中的 closeout 报告、相对补丁、baseline/final 哈希、guard JSON、stdout/stderr 和专用 runner。

没有修改生产源码、测试、原实施报告或原独立验收报告；没有部署、模型调用或 TCAD。

- HEAD 仍为 `943c4626f8490530e9318eb9fbb409d2670908b9`。
- P2 相对补丁 SHA256：`9523e6410f703ca4434b44379a378cd31de2f4060335a3c1b1b7a29c7234ea14`。
- `git apply --reverse --check` 与三个文件的 `git diff --check` 均通过。
- 当前三个文件逐项匹配 `FINAL_SHA256.txt`：`31ea1775…8e22`、`f7761a48…239`、`645af4d3…c24`。
- 在 `/tmp` 副本反向应用同一补丁后，三个文件分别得到 `BASELINE_SHA256.txt` 所列 `583b64f1…d4f`、`5cab0c35…11d9`、`2aa66fd3…7152`，证明补丁与两端字节闭合。
- 原独立验收报告当前 SHA256 为 `903a78f4c48a6cbd87a6d2bd2893a8b241dc95b57a98176f7ec530e99340c03b`，与 P2 baseline 记录一致，未被改写。
- `FINAL_SHA256.txt` 列出的 guard、runner、报告、补丁与全部 stdout/stderr 哈希逐项匹配当前文件。

## 2. P2-1 合同与测试复审

生产合同的公共必填项确为 `experiment_plan`、`reviewed_package`、`runtime_manifest`。`experiment_review`、`execution_review`、`scientific_skeleton` 在 schema 层均为 `0..1`，schema id 分别为 scientific review、deck review report 和 scientific skeleton；这是条件必填的必要表达，不是运行时放宽。

`analysis_parentage` 在公共三项完整后首先检查 legacy review 与 execution review 恰好存在一种。legacy 分支继续要求精确通过的 `science.object.review.v1/scientific_review`；skeleton 分支继续要求 v3 `tcad.deck.review.v1/review`、原 skeleton、project-derived plan 和精确 producer inputs。`validate_analysis_inputs` 随后按 package 分支再次拒绝缺项或混绑。因此安装态测试把公共三项作为 required、把三个 branch port 作为 `0..1` 并核对 schema，和真实生产合同一致。

安装态 author 版本断言由 v2 改为 v3 也与当前 `tcad.deck.author.initial.v1` 生产声明一致；测试仍核对 `ImplementationGap` schema，没有删除原合同覆盖。

## 3. 缺 review 负例与正路径

两个新增负例均从完整有效请求出发，只删除相应 review：legacy 删除 `experiment_review`，skeleton 删除 `execution_review`。公共必填项和其他 branch 输入仍在，生产执行顺序会先命中 review 二选一 guard，而不是其他缺输入检查。

为排除通用 `guard_rejected` 误归因，本复审在不改文件的最小运行时探针中读取了两个真实 `operation_preflight` 响应。两者均为：

- `code/reason_code = guard_rejected`
- `path = $.inputs.execution_review`
- `phase = input_admission`
- `message = Bind the one review type required by the actual package branch.`

同一探针继续执行原 skeleton 测试的完整正路径；legacy 参数化测试的原始批次也在负例之后继续打开 Worker、提交 failed/cancelled 受限报告并完成。skeleton 测试在负例之后仍要求原请求 `admissible=true`，保留错误来源负例，并实际 invoke。因此新增负例没有弱化两条正路径。

测试代码当前只把 `reason_code` 锁入断言，未把 path/message 锁入测试。静态执行顺序和独立运行时探针已证明本次拒绝原因，且委托要求的真实 preflight `guard_rejected` 已满足；这是非阻断的测试精度观察，不要求扩大本次补丁。

## 4. 原始记录与资源复核

P2 closeout 三批证据均由同一个 `run_guarded_capture.py` 调用仓库既有 `compiled_worker_process_guard.run_process_group`，固定进程树 RSS 768 MiB、0.1 秒采样、串行无 xdist。guard JSON 保留精确命令、环境、HEAD、输入文件哈希、退出码、峰值 RSS 与 stdout/stderr 路径；runner 不覆盖既有尝试。

| 批次 | 结果 | 峰值树 RSS | 复核 |
|---|---:|---:|---|
| local branch contracts | 3 passed in 5.19s | 148088 KiB | stdout、空 stderr、exit 0、未超限一致 |
| installed full 首跑 | 1 failed in 44.70s | 171344 KiB | 原始失败保留；精确暴露旧 author v2 断言，exit 1 |
| installed full 重跑 | 1 passed in 44.93s | 169428 KiB | v3 断言后的相同目标用例，exit 0、未超限 |

本复审没有无意义重跑上述安装批次。额外最小诊断探针在同样 768 MiB/0.1 秒树 RSS 守卫下 exit 0，峰值 `134416 KiB`；探针同时输出两个精确 preflight 诊断并走完 skeleton 原正路径。第一次直接探针因未带 pytest 配置中的 plugin `PYTHONPATH` 而在导入期失败，峰值 `32088 KiB`；随后只补上 `pyproject.toml` 的既有 pythonpath 后成功，该导入失败没有被当作语义证据。

原实施报告的 `88 passed / 166128 KiB` 仍无对应原始批次文件。本次 P2 没有伪造或追认该数字；只认可上表 P2 原始记录和原独立验收自身已有的 guard 证据。

## 5. 判定边界

P2 closeout 的三个测试修改与证据 **PASS**：安装态合同断言已同步真实公共/分支输入和 author v3；legacy/skeleton 缺对应 review 确实由 input-admission review guard 拒绝；原正路径保持；相对补丁、baseline/final hash、失败与成功日志、退出码和资源记录闭合。

本 PASS 不表示真实 prior analysis/manifest 已在部署态重验，不表示真实曲线 PNG 已发布并完成节点预览/原图/下载/来源链，不表示真实 TDR inspect/accept 已零重算完成，也不表示 Root/Worker matched A/B 或 token 收益成立。原 execution failed 与科学结论均未改变。
