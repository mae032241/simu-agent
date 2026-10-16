# R1/R2 独立只读审查（2026-10-16）

> **当前复审结论：PASS（R1/R2 精确修复范围）**。初审三个阻断均已关闭，未发现该冻结 diff 的新阻断。受审 patch SHA256：`c8cbbc57563a418da78e3f8da009c76ab81d290c8684ac17ffdbf77280694111`；复审范围与限制见报告末尾。以下初审内容是历史记录，不适用于当前冻结补丁。

## 初审结论：阻断（下文保留；已由复审关闭）

本次冻结补丁修复了 R1 的 `_run` 局部 `engineering` 绑定，并在 `run` / `closeout` 的普通异常路径中正确保持 writer 锁与保守预算判断。但 R2 尚有公开入口及中断边界遗漏，且新增诊断代码不兼容项目声明支持的 Python 3.10。以下三项应修复后重新审查；本报告不建议提交当前版本为 R1/R2 完成修复。

### 1. P2 — 公开 `continue` 入口绕过新预算收口，同一 R2 仍可复现

- 位置：`src/scidiscovery/research_loop/cli.py:166`、`:172`；新收口只挂在 `controller.py:227` 的 `run` 与 `:983` 的 `closeout`。
- 路径：`scid-research continue --root ...` 在 writer 内直接调用 `controller._run(root)`。当首轮 `contracts.build_job` 验证失败时，CLI 返回原错误但释放 writer 时没有调用 `budget.inactive`。
- 无模型因果复现：真实 `prepare`、真实 H job、仅篡改冻结 workspace objective 副本；`cli.main(['continue', '--root', ...])` 返回 1、`Bound input copy changed`。无任何 native intent。t=104 的消费 4 秒与 `clock_phase='advance'` 持续至 t=110 的消费 10 秒。相同实例构造经 `controller.run` 的对照是 paused 且 4→4 秒。
- 影响：操作者使用公开继续入口排障，仍消耗没有执行的空闲预算；R2 并未覆盖实际公开调用路径。
- 修复要求：在该入口仍持有原 writer 时复用同一异常收口，或将安全边界放到所有实际 `_run` 调用都覆盖的位置。避免递归获取 writer；继续动作的删除 pause / correction acknowledge 异常范围也应明确。

### 2. P2 — reconciliation 失败时 `add_note` 在 Python 3.10 遮蔽原异常

- 位置：`src/scidiscovery/research_loop/controller.py:218`；支持声明 `pyproject.toml:10` 为 `requires-python = ">=3.10"`。
- 条件：原控制异常逃逸后 `budget.inactive` 本身再因账本、设置或 I/O 失败而抛出异常。新增代码无条件调用 `error.add_note`，该方法在 Python 3.10 不存在。
- 独立补探针：在实际 `/usr/bin/python3.10`（3.10.12）中从冻结源提取并执行 `_inactive_on_error` 的完整 AST；body 抛 `ValueError('original failure')`，budget stub 抛 `OSError('ledger unavailable')`，实际顶层为 `AttributeError("'ValueError' object has no attribute 'add_note'")`，`original_preserved=false`。原异常只留在因果链。
- 影响：直接违反“reconcile 失败不能遮原异常”，在正式支持的最低 Python 版本发生。
- 修复要求：兼容缺失 `add_note` 的异常对象；诊断附加自身不能替换原异常。相应测试应兼容并实际覆盖 Python 3.10 路径。

### 3. P2 — 可捕获的提交前 `KeyboardInterrupt` 同样遗留 advance

- 位置：`src/scidiscovery/research_loop/controller.py:214` 仅捕获 `Exception`。
- 条件：控制器已启动 advance、尚未产生 native intent，操作者 Ctrl-C 在控制输入构造或读取期间触发 `KeyboardInterrupt`。Python 会展开 contextmanager 并释放 writer，但新增 handler 不运行。
- 独立补探针：真实 prepare、时钟账本及 `controller.run` 入口，在 `_run` 边界注入同一个 `KeyboardInterrupt` 对象；该对象确实原样传播，native_intents=[]，但 t=104→110 的 advance 消费 4→10 秒。此探针验证异常分派和账本后果，未声称发送真实操作系统信号。
- 影响：这是 R2 的同类无执行空闲计时，常见人工中断仍会发生。`closeout` 使用同一 helper，具有相同异常类型边界。
- 修复要求：在仍持 writer 时对可捕获的终止异常进行同一保守 `budget.inactive` 再原样传播；不可将 live/unknown 原执行无条件停表。进程被 SIGKILL 等无法执行 Python 收口的情况不属于此要求。

## 已确认正确的部分

- `_run` 两处局部 import 均删除，模块 `engineering` 绑定始终可用；剩余局部 imports 分属其他函数，没有 `_run` 同类遮蔽。真实 bound input 损坏经 run 返回原 ValueError，无 UnboundLocalError。
- `with _writer(root), _inactive_on_error(root)` 进入顺序与退出顺序正确：helper 执行 reconciliation 时 writer 尚未释放。writer 获取/协议校验失败时不会由不持锁调用者改预算。
- `budget.inactive` 未被改写：仍经 `execution_blocked` 检查 native original、live process、unknown outcome、closeout unresolved operation、cleanup、audit/selection 等；有疑问时保持 advance。没有新增重试或 native 提交。
- `budget.transition` 延续账本；没有退款、回写消费、重置 frozen settings 或增加额度。现有 tests 对消费保留、未知继续收费及 settings 不变有直接断言。
- `test_controller.py` 两组 fixture 更新与当前 W 字段、父 view 中 role/limitations 字段一致，没有放宽产品校验；当前补丁本身只包含 controller 和两份测试文件。

## 精确范围与指纹

- repo：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- branch：`dev`；base/HEAD：`4d7c6626f1d72a94a3ad9373c17e408d0820dd6d`。
- 只审 R 三文件的未提交 diff；H1/H2 的 lineage/selection/tests 及既有 untracked evidence 不属于受审变更，未修改。
- `git diff -- src/scidiscovery/research_loop/controller.py tests/research_loop/test_budget.py tests/research_loop/test_controller.py` SHA256 与提供的冻结 patch 一致：`153e8b8dcea525b4bec283b6b1e27ea1293553f5bf9df1724afc6d89d12fd44e`。

| 文件 | SHA256 |
| --- | --- |
| controller.py | `66b02561e1ae0864b56850bde94c09e48ab3679495ed1bf1a94f9b0d72813d05` |
| test_budget.py | `58f57fbcee1554397ba750c9b8b7d456beb847b6c02fc267f1b82e6796abbb7d` |
| test_controller.py | `cc07c3c91cf9a889d82fbb3f675d96710d24aedc74ee810c96b0bfafa2af2601` |
| cli.py（旁路追踪） | `13c16af53994ff3edd8765eaebc8ca2f92b2be9051c29ddb4a36b628f39a690e` |
| budget.py（未改） | `0fbb41cf0a53f4555ad56ee1db9e6176e2421acbf9a86e5b0756e294bea3e751` |
| pyproject.toml（未改） | `c16d858a00153dd97a99e5fdd0a893443aece4091c22eaa548d44154dca40dc2` |

## 验证证据与限制

- 已读内层 AGENTS.md 与外层 `scid-cross-boundary-review` / `scid-change-scope-checks`，追踪 CLI → run/continue/closeout/worker_resume → writer → job validation/engineering → native/runtime completion → budget execution-blocked / transition 路径。
- 独立执行 `git diff --check -- src/scidiscovery/research_loop/controller.py tests/research_loop/test_budget.py tests/research_loop/test_controller.py`：通过。
- 复核提供的 before 日志及 final2 日志：final2 执行 `tests/research_loop/test_budget.py tests/research_loop/test_controller.py` 为 78 passed in 3.02s；监督耗时 3.575s，RSS 高水位 59,760,640 bytes，cleanup_complete=true。这是被审执行者证据，未伪称独立重跑。
- 独立探针命令：`python -B /tmp/scid-r1r2-review-supervise-20261016.py`。先与执行者协调等待 H 最终测试释放 serial_lock，再复用仓库 `serial_lock` + `run_one`。Python 3.10 批 0.074s、RSS 16,777,216 bytes；实际入口批 0.226s、RSS 32,858,112 bytes；均 returncode=0、cleanup_complete=true。探针退出码 0 表示成功记录缺陷事实，不表示受审代码 PASS。
- 探针、监督及输出：`/tmp/scid-r1r2-review-probe-20261016.py`、`/tmp/scid-r1r2-review-supervise-20261016.py`、`/tmp/scid-r1r2-review-probe-20261016/{python310,entrypoints}/pytest.log` 与 resource.json、result.json。探针 SHA256=`7d817e1969ed4dbec41c9b0e1f5367a794b3c13b6d624bad838cd5f6de3d1ab4`；监督 SHA256=`ee67868e04cca7df7f6ee77141579b9dc22277c70981a6210fa8ed1ab9a3a7f1`；result.json SHA256=`e1bef0949da593bfb54bb943192e36ef4c72a4233b34c2d2e0b274d69ec5964b`。
- 未启动模型、solver、外部提交或旧实例；未改 repo、commit 或 push。本审查未重复已通过的 78 tests、未跑全 suite / installed wheel / 主机重启 / live platform。待修复后需对新增入口与中断负控补回归并刷新精确 diff；当前证据不构成完整平台或全库资格结论。


## 复审：PASS（2026-10-16，R1/R2 精确修复范围）

### 范围

- 基线仍为 dev / `4d7c6626f1d72a94a3ad9373c17e408d0820dd6d`；未提交 R diff 现为 `src/scidiscovery/research_loop/cli.py`、`controller.py`、`tests/research_loop/test_budget.py`、`test_controller.py` 四文件。
- 实际 `git diff --` 上述四文件的 SHA256 与冻结 patch 一致：`c8cbbc57563a418da78e3f8da009c76ab81d290c8684ac17ffdbf77280694111`。H1/H2 仍属于另一项独审；本审查未改动任何 repo 文件。

| 冻结文件 | 复审 SHA256 |
| --- | --- |
| cli.py | `1f0d2f999cec05b709e4a1ec55b8ec7711ec4d45eda764a6d954b962c552ba42` |
| controller.py | `a8a1f432b06394a7c3801a168d5de9d5225e40834aa16faea16342c684f7053d` |
| test_budget.py | `88693de8ce9ab028d39a1b9068cd9454bcaa9f808eeea97c65e4aa7db03f1ef1` |
| test_controller.py | `cc07c3c91cf9a889d82fbb3f675d96710d24aedc74ee810c96b0bfafa2af2601` |

`budget.py`、`pyproject.toml` 与初审指纹相同。

### 初审三个阻断的关闭证据

1. **公开 continue 旁路已关闭。** CLI 在既有 `_writer` 内使用同一 helper，覆盖 correction acknowledge、授权参数拒绝、pause marker 删除与 `_run`。没有递归获取 writer。独立重放初审的真实 prepare + H bound-input 副本损坏：continue 仍返回原 `Bound input copy changed`，预算现为 paused、t104→110 消费 4→4 秒，无 native intent。run 对照结果相同。新增拒绝无 exact correction trigger 的回归也保留原 pause marker。
2. **Python 3.10 兼容性已修复。** helper 对可选 `add_note` 进行 getattr/callable 保护，包含 note 查询、格式化及调用的保护范围；诊断自身失败不能替换原错误。独立使用实际 Python 3.10.12 执行当前 controller 完整 helper AST，ValueError / KeyboardInterrupt 主错误 × OSError / KeyboardInterrupt reconciliation 错误四组合均原样保留主错误对象。源码指纹与冻结 controller 相同。新增 notes supported / absent / broken 三分支回归与此一致。
3. **可捕获中断现已收口。** helper 外层与 reconciliation 内层均覆盖 BaseException，最后裸 raise 原样传播。独立重放初审 `_run` 边界 KeyboardInterrupt：原对象保留，无 native intent，clock paused、消费 4→4 秒。另已审阅新增 `test_interrupt_during_real_job_input_copy_stops_idle_clock`：在真实 `_copy_bound` 完成文件复制后中断，覆盖 run 与公开 continue，而不是只做 wrapper 注入。

### 跨边界复核

- 已搜索生产 `_run(root)` 的所有调用：run、CLI continue、worker_resume 三处现在都在 writer 内受到 helper 保护；closeout 入口亦有同样保护。
- worker_resume 仍对已知 ResumeUnavailable / NodeBudgetUnavailable 返回原有 `worker_resume_unavailable` 结构及 reason、保留正常 `worker_resume_unavailable` 停表原因；未处理错误使用 `worker_resume_failed` 原因。新增 helper 也覆盖 settings 读取与中断，原 catch-and-reconcile 的异常替换风险下降。
- writer 获取失败不会进入 helper；异常 reconciliation 在 writer 释放前完成。没有无锁停表窗口，helper 不增加执行、重试、续接或预算授权。
- unknown/live 条件仍由未改的 `budget.execution_blocked` 决定，helper 只复用 budget.inactive。已审的测试矩阵覆盖四个入口 × absent/unknown/running × OSError/KeyboardInterrupt：absent 在 4 秒暂停；unknown/running 继续从 4 累积到 10 秒，settings 字节与 native intent 数量不变。旧 consumption 不退款、不回写、不重置。
- R1 删除的两处 `_run` 局部 engineering import 仍未恢复，输入错误保留；两处 controller fixture 的最小同步仍与当前 schema/view 一致。
- 预算或可选诊断失败时 helper 对原未处理异常对象的保护成立；没有把无法执行 Python 清理的 SIGKILL / 主机掉电归入本次保证。

### 复审验证与边界

- 独立再次运行四文件 `git diff --check`：通过。
- 观察并核对 `/tmp/scid-r1r2-reviewed-20261016` 的监督记录与 pytest 日志：budget/controller 两文件及六个 worker_resume 实际过程测试，**108 passed in 11.48s**；监督 12.022s，RSS 高水位 120,799,232 bytes，cleanup_complete=true。六项覆盖已知失败同 thread 续接、预算拒绝、pause、不确定 intent 不重放、缺 meter、缺必须报告。此处是复核执行者证据，未重复独立跑 108 tests。
- 复核执行者 `/tmp/scid-r1r2-python310-fixed-20261016/{pytest.log,resource.json}`：实际 3.10.12 exact helper AST 四组合均保留原异常，0.085s、RSS 18,489,344 bytes、cleanup_complete=true。
- **独立复审探针**：`python -B /tmp/scid-r1r2-rereview-supervise-20261016.py`。复用仓库 serial_lock + run_one，协调后独占执行；3.10 批 0.110s、RSS 20,078,592 bytes，入口批 0.335s、RSS 32,968,704 bytes；均 returncode=0、cleanup_complete=true。输出在 `/tmp/scid-r1r2-rereview-probe-20261016/{python310,entrypoints}/pytest.log` 及 resource.json / result.json。探针重复初审的同一负控，现在结果符合修复要求。
- 独立复审 probe SHA256=`387a66360292c252cbe366604caba8877792c508af79ae8084b5c340322ea817`；supervisor SHA256=`31c1fde805d16a0ad12d2be373e2f70751d8314d2227369a66add2ca0457c997`；result.json SHA256=`79a2699b5f689fabc73ebcd938c42a8ec1ad808db0cd7ccab392ae8ea8b4a6be`。
- 当前结论允许将此精确 R 修复作为独立节点提交；不是全仓或平台资格结论。没有运行模型、solver、外部提交、旧实例、全 pytest suite、installed wheel、真实信号或主机重启。本次是局部失败收口语义审查及充分定向证据；完整 Python/平台矩阵仍由相应 CI / 资格验证承担。审查者未 commit、push 或修改 repo。
